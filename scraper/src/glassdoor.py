"""Glassdoor company rating lookup.

Fetches overall company rating (out of 5.0) from Glassdoor using:
1. DuckDuckGo HTML search to resolve company name -> Glassdoor ID (+ sometimes rating from snippet)
2. Glassdoor overview page (via curl_cffi to bypass PerimeterX) to extract rating from schema.org data

Ratings are cached at the tracked_companies level and refreshed weekly.
"""

import asyncio
import re
from dataclasses import dataclass
from urllib.parse import quote_plus

import structlog
from curl_cffi.requests import AsyncSession

log = structlog.get_logger()

RATING_STALE_DAYS = 7

_IMPERSONATE = "chrome"


@dataclass
class GlassdoorCompany:
    glassdoor_id: int
    short_name: str
    url: str
    rating: float | None = None


async def _find_via_duckduckgo(
    session: AsyncSession, company_name: str
) -> tuple[int | None, str | None, float | None]:
    """Search DuckDuckGo HTML for the Glassdoor overview URL and rating snippet.

    Returns (glassdoor_id, short_name, snippet_rating).
    All may be None if not found.
    """
    q = quote_plus(f"{company_name} glassdoor rating")
    try:
        r = await session.get(f"https://html.duckduckgo.com/html/?q={q}")
        if r.status_code != 200:
            log.warning("ddg_search_failed", status=r.status_code, company=company_name)
            return None, None, None
    except Exception as e:
        log.warning("ddg_request_error", error=str(e), company=company_name)
        return None, None, None

    text = r.text

    # Extract Glassdoor employer ID from overview/reviews URLs
    id_matches = re.findall(
        r"glassdoor\.com/(?:Overview|Reviews)/[^\"\s]*?EI_IE(\d+)", text
    )
    gd_id = int(id_matches[0]) if id_matches else None

    # Extract short name from the URL pattern "Working-at-{ShortName}-EI_IE"
    name_matches = re.findall(r"Working-at-(.+?)-EI_IE", text)
    short_name = name_matches[0] if name_matches else None

    # Try to grab rating from search snippet. Matches common formats:
    # "4.1 out of 5", "4.1/5", "rated 4.1", "rating: 4.1", "★ 4.1", "4.1 stars"
    rating_matches = re.findall(
        r"(?:"
        r"(\d\.\d)\s*(?:out of|/)\s*5"       # "4.1 out of 5" or "4.1/5"
        r"|(?:rated?|rating)[:\s]+(\d\.\d)"   # "rated 4.1" or "rating: 4.1"
        r"|★\s*(\d\.\d)"                      # "★ 4.1"
        r"|(\d\.\d)\s*stars?"                 # "4.1 stars"
        r")",
        text,
    )
    snippet_rating = None
    for match in rating_matches:
        # Each match is a tuple of groups; take the first non-empty one
        val = next((g for g in match if g), None)
        if val:
            try:
                f = float(val)
                if 0 < f <= 5.0:
                    snippet_rating = f
                    break
            except ValueError:
                pass

    return gd_id, short_name, snippet_rating


def _extract_rating_from_html(html: str) -> float | None:
    """Extract ratingValue from Glassdoor page's schema.org structured data."""
    m = re.search(r'"ratingValue"\s*:\s*"?([\d.]+)"?', html)
    if m:
        try:
            val = float(m.group(1))
            if 0 < val <= 5.0:
                return val
        except ValueError:
            pass
    return None


async def _fetch_overview_rating(
    session: AsyncSession,
    glassdoor_id: int,
    short_name: str,
) -> float | None:
    """Fetch rating from the Glassdoor overview page using curl_cffi."""
    url = (
        f"https://www.glassdoor.com/Overview/"
        f"Working-at-{short_name}-EI_IE{glassdoor_id}.htm"
    )
    try:
        r = await session.get(url)
        if r.status_code != 200:
            log.warning(
                "glassdoor_overview_failed",
                status=r.status_code,
                glassdoor_id=glassdoor_id,
            )
            return None
        return _extract_rating_from_html(r.text)
    except Exception as e:
        log.warning("glassdoor_overview_error", error=str(e))
        return None


async def lookup_company_rating(company_name: str) -> GlassdoorCompany | None:
    """Full pipeline: company name -> Glassdoor ID + rating.

    Uses DuckDuckGo for discovery and Glassdoor overview page for rating.
    Returns a GlassdoorCompany or None if the company isn't found.
    """
    async with AsyncSession(impersonate=_IMPERSONATE) as session:
        gd_id, short_name, snippet_rating = await _find_via_duckduckgo(
            session, company_name
        )

        if not gd_id:
            log.info("glassdoor_company_not_found", company=company_name)
            return None

        if not short_name:
            short_name = company_name.replace(" ", "-")

        overview_url = (
            f"https://www.glassdoor.com/Overview/"
            f"Working-at-{short_name}-EI_IE{gd_id}.htm"
        )

        rating = snippet_rating
        if rating is None:
            await asyncio.sleep(1.5)
            rating = await _fetch_overview_rating(session, gd_id, short_name)

        gd = GlassdoorCompany(
            glassdoor_id=gd_id,
            short_name=short_name,
            url=overview_url,
            rating=rating,
        )
        log.info(
            "glassdoor_rating_fetched",
            company=company_name,
            glassdoor_id=gd_id,
            rating=rating,
        )
        return gd
