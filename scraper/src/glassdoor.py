"""Glassdoor company rating lookup.

Fetches overall company rating (out of 5.0) from Glassdoor using a layered approach:
1. Search-engine snippets (DDG → Google → Bing) — resolves company name → Glassdoor ID
   and often surfaces the rating without touching Glassdoor at all
2. Glassdoor direct page fetch — only attempted if all snippet sources failed to find
   a rating; tries Overview then Reviews URL with a fresh session per attempt

A module-level rate-limit flag prevents wasting requests once Glassdoor starts 403/429ing.
Ratings are cached at the tracked_companies level and refreshed weekly.
"""

import asyncio
import random
import re
import time
from dataclasses import dataclass
from urllib.parse import quote_plus, unquote

import structlog
from curl_cffi.requests import AsyncSession

log = structlog.get_logger()

# Available impersonation targets — rotated per-session for fingerprint diversity
_IMPERSONATE_TARGETS = [
    "chrome120",
    "chrome123",
    "chrome124",
]

# Glassdoor rate-limit state (shared across lookups within a single refresh run)
_gd_rate_limited_until: float = 0.0

_REFERERS = [
    "https://www.google.com/",
    "https://www.google.com/search?q=glassdoor+reviews",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
]


def _random_impersonate() -> str:
    return random.choice(_IMPERSONATE_TARGETS)


def _random_referer() -> str:
    return random.choice(_REFERERS)


def _jitter(base: float) -> float:
    """Return base ± 30% for human-like timing."""
    return base * (0.7 + random.random() * 0.6)


def _browser_headers(*, referer: str | None = None) -> dict[str, str]:
    h = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site" if referer else "none",
        "Sec-Fetch-User": "?1",
    }
    if referer:
        h["Referer"] = referer
    return h


@dataclass
class GlassdoorCompany:
    glassdoor_id: int
    short_name: str
    url: str
    rating: float | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_rating_from_text(text: str) -> float | None:
    """Extract a Glassdoor-style rating (0–5) from arbitrary HTML/text.

    Ordered from most-specific (structured data) to least-specific.
    Only accepts values that look like ratings (1.0–5.0, one decimal place or integer).
    """
    patterns = [
        r'"ratingValue"\s*:\s*"?([\d.]+)"?',
        r"([\d.]+)\s*(?:out of|/)\s*5",
        r"(?:overall\s+)?rating\s+(?:of\s+)?([\d.]+)",
        r"rated?\s*[:\s]\s*([\d.]+)",
        r"[★⭐]\s*([\d.]+)",
        r"([\d.]+)\s+stars?",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            try:
                val = float(m.group(1))
                # Glassdoor ratings are always ≥ 1.0 in practice; reject implausibly low
                # values that are likely page-number artifacts ("1 of 5 pages") or
                # single-review outliers extracted from the wrong context.
                if 1.5 <= val <= 5.0:
                    return val
            except ValueError:
                pass
    return None


def _parse_ddg_results(
    html: str, company_name: str
) -> tuple[int | None, str | None, float | None]:
    """Parse DDG HTML result-by-result so each employer ID is paired with its own
    snippet rating — never from a different company's result block.

    DDG commonly returns 10 results for a company name query, often including
    multiple distinct companies that share the same name (e.g. searching "Enable"
    returns Enable.com, Enable International, Enable rebates software, etc. with
    different Glassdoor employer IDs). Extracting the ID and the rating from the
    full page independently means they can silently come from different companies.

    This function splits the page into individual result blocks, then for each block:
    - extracts the Glassdoor employer ID from the URL in that block only
    - extracts the rating from the snippet text in that same block only

    Candidates are scored to pick the best-matching company:
      1. Prefer glassdoor.com (US) over international subdomains
      2. Prefer result whose company slug most closely matches the query (Jaccard ratio)
      3. Use result order (earlier = higher DDG relevance) as tiebreaker

    Note: "has rating" is deliberately NOT in the score so we don't bias toward
    a wrong company that happens to have a rating snippet.
    """
    query_words = {
        w for w in re.sub(r"[^\w\s]", "", company_name.lower()).split() if len(w) > 2
    }

    # DDG wraps each search result in a div with this class
    blocks = re.split(r'(?=class="result results_links)', html)

    # candidates: gd_id → (short_name, rating, score_tuple)
    candidates: dict[int, tuple[str, float | None, tuple]] = {}

    for block_idx, block in enumerate(blocks):
        decoded = unquote(block)

        # Find the first glassdoor URL in this block (DDG encodes the href, so we
        # unquote first to make the real glassdoor URL visible)
        url_m = re.search(
            r"(https?://(?:www\.)?glassdoor\.[a-z.]+/(?:Overview|Reviews)/[^\s\"&]+)",
            decoded,
        )
        if not url_m:
            continue
        url = url_m.group(1)

        # Extract employer ID from the URL
        id_m = re.search(r"EI_IE(\d+)", url)
        if id_m:
            gd_id = int(id_m.group(1))
        else:
            # Reviews/SLUG-Reviews-E{id}.htm format
            id_m2 = re.search(r"-E(\d+)(?:\.|$)", url)
            if not id_m2:
                continue
            gd_id = int(id_m2.group(1))

        # Extract slug for name matching and URL construction
        slug_m = re.search(r"Working-at-(.+?)-EI_IE", url)
        if slug_m:
            short_name = slug_m.group(1)
        else:
            slug_m2 = re.search(r"/Reviews/(.+?)-Reviews-E\d", url)
            short_name = slug_m2.group(1) if slug_m2 else company_name.replace(" ", "-")

        # Prefer the canonical glassdoor.com US domain over .ca, .co.uk, etc.
        is_us = bool(re.match(r"https?://(?:www\.)?glassdoor\.com/", url))

        # Jaccard similarity between query words and slug words — punishes slugs
        # with extra words like "International" or "Learning" that aren't in the query
        slug_words = {
            w
            for w in re.sub(r"[^\w\s]", "", short_name.lower().replace("-", " ")).split()
            if len(w) > 2
        }
        union = query_words | slug_words
        match_ratio = len(query_words & slug_words) / len(union) if union else 0.0

        # Extract rating from THIS block's snippet only — never cross-block
        snippet_m = re.search(
            r'class="result__snippet"[^>]*>(.*?)</a>', block, re.DOTALL
        )
        snippet_text = (
            re.sub(r"<[^>]+>", "", snippet_m.group(1)).strip() if snippet_m else ""
        )
        rating = _extract_rating_from_text(snippet_text) if snippet_text else None

        # Higher score = better candidate. Earlier blocks have smaller block_idx so
        # we negate it: a smaller index (earlier result) gives a larger value.
        score = (1 if is_us else 0, round(match_ratio, 4), -block_idx)

        if gd_id not in candidates or score > candidates[gd_id][2]:
            candidates[gd_id] = (short_name, rating, score)

    if not candidates:
        return None, None, None

    best_id = max(candidates, key=lambda gid: candidates[gid][2])
    best_slug, best_rating, _ = candidates[best_id]
    log.debug(
        "ddg_best_candidate",
        company=company_name,
        gd_id=best_id,
        slug=best_slug,
        rating=best_rating,
    )
    return best_id, best_slug, best_rating


def _extract_gd_id_and_name(text: str) -> tuple[int | None, str | None]:
    """Pull the Glassdoor employer ID and short-name slug from HTML."""
    id_matches = re.findall(
        r"glassdoor\.com/(?:Overview|Reviews)/[^\"\s]*?EI_IE(\d+)", text
    )
    gd_id = int(id_matches[0]) if id_matches else None

    # Also try the -Reviews-E{id} URL format
    if not gd_id:
        id_matches2 = re.findall(r"glassdoor\.com/Reviews/[^\"\s]*?-E(\d+)", text)
        gd_id = int(id_matches2[0]) if id_matches2 else None

    name_matches = re.findall(r"Working-at-(.+?)-EI_IE", text)
    short_name = name_matches[0] if name_matches else None
    return gd_id, short_name


# ---------------------------------------------------------------------------
# Search-engine snippet extractors
# ---------------------------------------------------------------------------

async def _search_snippet(
    session: AsyncSession,
    url: str,
    company_name: str,
    source: str,
) -> tuple[int | None, str | None, float | None]:
    """GET a search-engine HTML page and extract Glassdoor employer ID + slug.

    Used only for Google and Bing, which obfuscate Glassdoor URLs and don't
    reliably surface ratings in their HTML. Whole-page rating extraction on
    Google/Bing produces too many false positives (stray "X/5" patterns from
    unrelated content), so we return None for rating and let the direct
    Glassdoor page fetch handle it.
    """
    try:
        r = await session.get(url, headers=_browser_headers())
        if r.status_code != 200:
            log.debug(f"{source}_search_failed", status=r.status_code, company=company_name)
            return None, None, None
    except Exception as e:
        log.debug(f"{source}_request_error", error=str(e), company=company_name)
        return None, None, None

    gd_id, short_name = _extract_gd_id_and_name(r.text)
    return gd_id, short_name, None


async def _find_via_duckduckgo(
    session: AsyncSession, company_name: str
) -> tuple[int | None, str | None, float | None]:
    """Fetch DDG results and parse per-result-block to pair IDs with their own ratings."""
    q = quote_plus(f"{company_name} glassdoor rating")
    try:
        r = await session.get(
            f"https://html.duckduckgo.com/html/?q={q}",
            headers=_browser_headers(),
        )
        if r.status_code != 200:
            log.debug("ddg_search_failed", status=r.status_code, company=company_name)
            return None, None, None
    except Exception as e:
        log.debug("ddg_request_error", error=str(e), company=company_name)
        return None, None, None

    return _parse_ddg_results(r.text, company_name)


async def _find_via_google(
    session: AsyncSession, company_name: str
) -> tuple[int | None, str | None, float | None]:
    q = quote_plus(f"{company_name} glassdoor rating")
    return await _search_snippet(
        session, f"https://www.google.com/search?q={q}&hl=en", company_name, "google",
    )


async def _find_via_bing(
    session: AsyncSession, company_name: str
) -> tuple[int | None, str | None, float | None]:
    q = quote_plus(f"{company_name} glassdoor rating site:glassdoor.com")
    return await _search_snippet(
        session, f"https://www.bing.com/search?q={q}", company_name, "bing",
    )


# ---------------------------------------------------------------------------
# Direct Glassdoor page fetch
# ---------------------------------------------------------------------------

async def _fetch_glassdoor_page(
    glassdoor_id: int,
    short_name: str,
) -> tuple[float | None, bool]:
    """Try Overview page, then Reviews page using a fresh session each time.

    Returns (rating_or_none, was_rate_limited).
    """
    global _gd_rate_limited_until

    if time.monotonic() < _gd_rate_limited_until:
        log.debug("glassdoor_skipped_rate_limited", glassdoor_id=glassdoor_id)
        return None, True

    urls = [
        f"https://www.glassdoor.com/Overview/Working-at-{short_name}-EI_IE{glassdoor_id}.htm",
        f"https://www.glassdoor.com/Reviews/{short_name}-Reviews-E{glassdoor_id}.htm",
    ]

    for url in urls:
        async with AsyncSession(impersonate=_random_impersonate()) as session:
            headers = _browser_headers(referer=_random_referer())
            try:
                r = await session.get(url, headers=headers)
                if r.status_code == 200:
                    rating = _extract_rating_from_text(r.text)
                    if rating is not None:
                        return rating, False
                    return None, False
                log.warning(
                    "glassdoor_page_failed",
                    status=r.status_code,
                    glassdoor_id=glassdoor_id,
                    url=url,
                )
                if r.status_code == 429:
                    _gd_rate_limited_until = time.monotonic() + 120
                    log.warning("glassdoor_rate_limited", backoff_secs=120)
                    return None, True
                if r.status_code != 403:
                    return None, False
            except Exception as e:
                log.warning("glassdoor_page_error", error=str(e), url=url)
                return None, False
            # 403 → try next URL after brief pause
            await asyncio.sleep(_jitter(1.5))

    return None, False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def lookup_company_rating(company_name: str) -> GlassdoorCompany | None:
    """Full pipeline: company name → Glassdoor ID + rating.

    Strategy (stops as soon as a rating is found):
    1. DDG snippet → 2. Google snippet → 3. Bing snippet
    4. Direct Glassdoor page (only if snippets all failed AND we're not rate-limited)

    Returns a GlassdoorCompany (rating may still be None if all sources fail),
    or None if the company isn't found on Glassdoor at all.
    """
    # Each lookup gets a fresh session with a random Chrome fingerprint
    async with AsyncSession(impersonate=_random_impersonate()) as session:
        # --- Snippet cascade: DDG → Google → Bing ---
        gd_id: int | None = None
        short_name: str | None = None
        rating: float | None = None

        for i, finder in enumerate([_find_via_duckduckgo, _find_via_google, _find_via_bing]):
            if i > 0:
                await asyncio.sleep(_jitter(1.0))
            found_id, found_name, found_rating = await finder(session, company_name)
            if found_id and not gd_id:
                gd_id = found_id
            if found_name and not short_name:
                short_name = found_name
            if found_rating is not None:
                rating = found_rating
                log.debug(
                    "glassdoor_rating_from_snippet",
                    company=company_name,
                    source=finder.__name__,
                    rating=rating,
                )
                break

        if not gd_id:
            log.info("glassdoor_company_not_found", company=company_name)
            return None

        if not short_name:
            short_name = company_name.replace(" ", "-")

    # --- Direct Glassdoor page (only when snippet cascade found no rating) ---
    if rating is None:
        await asyncio.sleep(_jitter(2.0))
        rating, _was_limited = await _fetch_glassdoor_page(gd_id, short_name)

    overview_url = (
        f"https://www.glassdoor.com/Overview/"
        f"Working-at-{short_name}-EI_IE{gd_id}.htm"
    )

    log.info(
        "glassdoor_rating_fetched",
        company=company_name,
        glassdoor_id=gd_id,
        rating=rating,
    )
    return GlassdoorCompany(
        glassdoor_id=gd_id,
        short_name=short_name,
        url=overview_url,
        rating=rating,
    )
