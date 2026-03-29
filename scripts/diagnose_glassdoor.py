#!/usr/bin/env python3
"""Diagnostic script for Glassdoor rating accuracy.

Checks stored ratings against actual Glassdoor page ratings for companies in DB.
Also tests the search-snippet parsing to identify false positives.

Usage:
    python scripts/diagnose_glassdoor.py [--limit N] [--company NAME]
"""
import asyncio
import argparse
import os
import sys

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from scraper.src.glassdoor import (
    _extract_rating_from_text,
    _find_via_duckduckgo,
    _find_via_google,
    _parse_ddg_results,
    _random_impersonate,
)
from curl_cffi.requests import AsyncSession

DB_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://hirewire:localdev@localhost:5432/hirewire",
)

SUSPICIOUS_RATINGS = {1.0, 2.0}  # Ratings that are likely parsing errors


async def fetch_companies(conn, company_filter=None, limit=None):
    where = "glassdoor_url IS NOT NULL"
    params = []
    if company_filter:
        where += " AND lower(name) LIKE $1"
        params.append(f"%{company_filter.lower()}%")
    sql = f"""
        SELECT name, glassdoor_id, glassdoor_rating, glassdoor_url
        FROM tracked_companies
        WHERE {where}
        ORDER BY glassdoor_rating NULLS LAST, name
    """
    if limit:
        sql += f" LIMIT {limit}"
    return await conn.fetch(sql, *params)


async def check_direct_glassdoor(glassdoor_id: int, short_name: str) -> float | None:
    """Fetch rating directly from Glassdoor overview page."""
    from scraper.src.glassdoor import _browser_headers, _random_referer
    url = f"https://www.glassdoor.com/Overview/Working-at-{short_name}-EI_IE{glassdoor_id}.htm"
    async with AsyncSession(impersonate=_random_impersonate()) as session:
        try:
            r = await session.get(url, headers=_browser_headers(referer=_random_referer()), timeout=15)
            if r.status_code == 200:
                return _extract_rating_from_text(r.text)
            return None
        except Exception as e:
            print(f"  [direct fetch error] {e}")
            return None


async def fetch_ddg_raw(session: AsyncSession, company_name: str):
    """Fetch raw DDG HTML and show per-block parsing result vs whole-page extraction."""
    import re
    from urllib.parse import quote_plus

    from scraper.src.glassdoor import _browser_headers

    q = quote_plus(f"{company_name} glassdoor rating")
    url = f"https://html.duckduckgo.com/html/?q={q}"
    try:
        r = await session.get(url, headers=_browser_headers())
        if r.status_code != 200:
            return None, None, None
        text = r.text
        whole_page_rating = _extract_rating_from_text(text)
        per_block_id, per_block_slug, per_block_rating = _parse_ddg_results(text, company_name)

        contexts = []
        for m in re.finditer(r"glassdoor\.com", text, re.IGNORECASE):
            start = max(0, m.start() - 200)
            end = min(len(text), m.end() + 200)
            chunk = text[start:end].replace("\n", " ").strip()
            contexts.append(chunk[:300])

        return (whole_page_rating, (per_block_id, per_block_slug, per_block_rating)), contexts[:3]
    except Exception as e:
        return None, None, [str(e)]


async def diagnose_company(conn, name: str, glassdoor_id: int, stored_rating, glassdoor_url: str):
    print(f"\n{'='*60}")
    print(f"Company: {name}")
    print(f"Stored rating: {stored_rating}")
    print(f"URL: {glassdoor_url}")

    import re
    m = re.search(r"Working-at-(.+?)-EI_IE", glassdoor_url)
    short_name = m.group(1) if m else name.replace(" ", "-")

    results = {}

    async with AsyncSession(impersonate=_random_impersonate()) as session:
        # Show whole-page vs per-block extraction on raw DDG HTML
        ratings, contexts = await fetch_ddg_raw(session, name)
        if ratings:
            whole_page, (pb_id, pb_slug, pb_rating) = ratings
            print(f"  [ddg raw] whole_page={whole_page}  per_block=id={pb_id} slug={pb_slug!r} rating={pb_rating}")
        if contexts:
            print("  [ddg raw] glassdoor context snippet:")
            print(f"    ...{contexts[0][:200]}...")
        await asyncio.sleep(1.0)

        for finder_name, finder in [
            ("duckduckgo", _find_via_duckduckgo),
            ("google", _find_via_google),
        ]:
            try:
                gd_id, found_name, rating = await finder(session, name)
                results[finder_name] = {"gd_id": gd_id, "rating": rating}
                print(f"  [{finder_name}] id={gd_id} (match={gd_id == glassdoor_id if gd_id else '?'}) rating={rating}")
                await asyncio.sleep(1.0)
            except Exception as e:
                print(f"  [{finder_name}] ERROR: {e}")

    # Direct Glassdoor check
    print("  [glassdoor direct] fetching...")
    direct_rating = await check_direct_glassdoor(glassdoor_id, short_name)
    print(f"  [glassdoor direct] rating={direct_rating}")

    # Summary
    print(f"\n  SUMMARY for {name}:")
    print(f"    Stored:   {stored_rating}")
    print(f"    Direct:   {direct_rating}")

    if stored_rating and direct_rating and abs(float(stored_rating) - float(direct_rating)) > 0.5:
        print(f"  *** MISMATCH DETECTED: stored={stored_rating} vs actual={direct_rating} ***")
    elif stored_rating in SUSPICIOUS_RATINGS:
        print(f"  *** SUSPICIOUS RATING {stored_rating} - likely a false positive parse ***")


async def main():
    parser = argparse.ArgumentParser(description="Diagnose Glassdoor rating accuracy")
    parser.add_argument("--limit", type=int, default=5, help="Number of companies to check (default: 5)")
    parser.add_argument("--company", type=str, help="Filter to specific company name")
    parser.add_argument("--suspicious-only", action="store_true", help="Only check companies with suspicious ratings (1.0, 2.0)")
    args = parser.parse_args()

    conn = await asyncpg.connect(DB_URL)
    companies = await fetch_companies(conn, company_filter=args.company, limit=args.limit if not args.suspicious_only else None)

    if args.suspicious_only:
        companies = [c for c in companies if c["glassdoor_rating"] in SUSPICIOUS_RATINGS]
        print(f"Found {len(companies)} companies with suspicious ratings: {[c['name'] for c in companies]}")

    print(f"Diagnosing {len(companies)} companies...\n")

    for c in companies[:args.limit]:
        await diagnose_company(
            conn,
            name=c["name"],
            glassdoor_id=c["glassdoor_id"],
            stored_rating=c["glassdoor_rating"],
            glassdoor_url=c["glassdoor_url"],
        )
        await asyncio.sleep(2.0)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
