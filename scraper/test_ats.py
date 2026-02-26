#!/usr/bin/env python3
"""ATS API smoke test -- validates Greenhouse, Lever, and Ashby endpoints.

Tests connectivity, response time, data quality, field completeness,
and error handling for each provider before building scrapers on top.

Usage:
    python scraper/test_ats.py
"""

import json
import sys
import time
from dataclasses import dataclass, field

import httpx

TIMEOUT = 30.0
BAD_SLUG = "definitely-not-a-real-company-zzzz-12345"

THRESHOLDS = {
    "ashby": {"max_response_s": 2.0},
    "greenhouse": {"max_response_s": 2.0},
    "lever": {"max_response_s": 5.0},
}

REQUIRED_FIELDS = {
    "ashby": ["title", "jobUrl"],
    "greenhouse": ["title", "absolute_url"],
    "lever": ["text", "hostedUrl"],
}


@dataclass
class TestResult:
    provider: str
    slug: str
    passed: bool = True
    failures: list[str] = field(default_factory=list)
    job_count: int = 0
    response_ms: int = 0
    sample_titles: list[str] = field(default_factory=list)
    has_compensation: bool = False
    field_completeness_pct: float = 0.0
    error_handling_ok: bool = False

    def fail(self, reason: str):
        self.passed = False
        self.failures.append(reason)


def test_ashby(slug: str) -> TestResult:
    result = TestResult(provider="ashby", slug=slug)
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"

    start = time.monotonic()
    try:
        resp = httpx.get(url, params={"includeCompensation": "true"}, timeout=TIMEOUT)
    except Exception as e:
        result.fail(f"Connection error: {e}")
        return result
    elapsed = time.monotonic() - start
    result.response_ms = int(elapsed * 1000)

    if resp.status_code != 200:
        result.fail(f"HTTP {resp.status_code}")
        return result

    if elapsed > THRESHOLDS["ashby"]["max_response_s"]:
        result.fail(f"Too slow: {elapsed:.2f}s (max {THRESHOLDS['ashby']['max_response_s']}s)")

    try:
        data = resp.json()
    except json.JSONDecodeError:
        result.fail("Invalid JSON response")
        return result

    jobs = data.get("jobs", [])
    result.job_count = len(jobs)
    if not jobs:
        result.fail("No jobs returned")
        return result

    result.sample_titles = [j.get("title", "?") for j in jobs[:3]]

    # Field completeness
    complete = 0
    for job in jobs:
        if all(job.get(f) for f in REQUIRED_FIELDS["ashby"]):
            complete += 1
    result.field_completeness_pct = (complete / len(jobs)) * 100

    if result.field_completeness_pct < 95:
        result.fail(f"Field completeness {result.field_completeness_pct:.1f}% < 95%")

    # Compensation check
    comp_count = sum(1 for j in jobs if j.get("compensation"))
    result.has_compensation = comp_count > 0
    if not result.has_compensation:
        result.fail("No jobs have compensation data despite includeCompensation=true")

    # Description check
    desc_count = sum(1 for j in jobs if j.get("descriptionHtml") or j.get("descriptionPlain"))
    if desc_count < len(jobs) * 0.9:
        result.fail(f"Only {desc_count}/{len(jobs)} jobs have descriptions")

    return result


def test_greenhouse(slug: str) -> TestResult:
    result = TestResult(provider="greenhouse", slug=slug)
    url = f"https://api.greenhouse.io/v1/boards/{slug}/jobs"

    start = time.monotonic()
    try:
        resp = httpx.get(url, params={"content": "true"}, timeout=TIMEOUT)
    except Exception as e:
        result.fail(f"Connection error: {e}")
        return result
    elapsed = time.monotonic() - start
    result.response_ms = int(elapsed * 1000)

    if resp.status_code != 200:
        result.fail(f"HTTP {resp.status_code}")
        return result

    if elapsed > THRESHOLDS["greenhouse"]["max_response_s"]:
        result.fail(f"Too slow: {elapsed:.2f}s (max {THRESHOLDS['greenhouse']['max_response_s']}s)")

    try:
        data = resp.json()
    except json.JSONDecodeError:
        result.fail("Invalid JSON response")
        return result

    jobs = data.get("jobs", [])
    result.job_count = len(jobs)
    if not jobs:
        result.fail("No jobs returned")
        return result

    result.sample_titles = [j.get("title", "?") for j in jobs[:3]]

    # Field completeness
    complete = 0
    for job in jobs:
        if all(job.get(f) for f in REQUIRED_FIELDS["greenhouse"]):
            complete += 1
    result.field_completeness_pct = (complete / len(jobs)) * 100

    if result.field_completeness_pct < 95:
        result.fail(f"Field completeness {result.field_completeness_pct:.1f}% < 95%")

    # Description check (with content=true)
    desc_count = sum(1 for j in jobs if j.get("content"))
    if desc_count < len(jobs) * 0.9:
        result.fail(f"Only {desc_count}/{len(jobs)} jobs have content (description)")

    return result


def test_lever(slug: str) -> TestResult:
    result = TestResult(provider="lever", slug=slug)
    url = f"https://api.lever.co/v0/postings/{slug}"

    start = time.monotonic()
    try:
        resp = httpx.get(url, timeout=TIMEOUT)
    except Exception as e:
        result.fail(f"Connection error: {e}")
        return result
    elapsed = time.monotonic() - start
    result.response_ms = int(elapsed * 1000)

    if resp.status_code != 200:
        result.fail(f"HTTP {resp.status_code}")
        return result

    if elapsed > THRESHOLDS["lever"]["max_response_s"]:
        result.fail(f"Too slow: {elapsed:.2f}s (max {THRESHOLDS['lever']['max_response_s']}s)")

    try:
        jobs = resp.json()
    except json.JSONDecodeError:
        result.fail("Invalid JSON response")
        return result

    if not isinstance(jobs, list):
        result.fail(f"Expected list, got {type(jobs).__name__}")
        return result

    result.job_count = len(jobs)
    if not jobs:
        result.fail("No jobs returned")
        return result

    result.sample_titles = [j.get("text", "?") for j in jobs[:3]]

    # Field completeness
    complete = 0
    for job in jobs:
        if all(job.get(f) for f in REQUIRED_FIELDS["lever"]):
            complete += 1
    result.field_completeness_pct = (complete / len(jobs)) * 100

    if result.field_completeness_pct < 95:
        result.fail(f"Field completeness {result.field_completeness_pct:.1f}% < 95%")

    # Description check
    desc_count = sum(1 for j in jobs if j.get("description") or j.get("descriptionPlain"))
    if desc_count < len(jobs) * 0.9:
        result.fail(f"Only {desc_count}/{len(jobs)} jobs have descriptions")

    return result


def test_error_handling(provider: str) -> tuple[bool, str]:
    """Test that a bad slug fails gracefully (no crash, returns 404 or empty)."""
    try:
        if provider == "ashby":
            resp = httpx.get(
                f"https://api.ashbyhq.com/posting-api/job-board/{BAD_SLUG}",
                timeout=TIMEOUT,
            )
            if resp.status_code == 404:
                return True, "404"
            data = resp.json()
            if not data.get("jobs"):
                return True, f"{resp.status_code} empty"
            return False, f"{resp.status_code} with {len(data['jobs'])} jobs (unexpected)"

        elif provider == "greenhouse":
            resp = httpx.get(
                f"https://api.greenhouse.io/v1/boards/{BAD_SLUG}/jobs",
                timeout=TIMEOUT,
            )
            if resp.status_code == 404:
                return True, "404"
            data = resp.json()
            if not data.get("jobs"):
                return True, f"{resp.status_code} empty"
            return False, f"{resp.status_code} with {len(data['jobs'])} jobs (unexpected)"

        elif provider == "lever":
            resp = httpx.get(
                f"https://api.lever.co/v0/postings/{BAD_SLUG}",
                timeout=TIMEOUT,
            )
            if resp.status_code == 404:
                return True, "404"
            data = resp.json()
            if isinstance(data, list) and len(data) == 0:
                return True, f"{resp.status_code} empty list"
            return False, f"{resp.status_code} unexpected response"

    except httpx.TimeoutException:
        return True, "timeout (handled)"
    except Exception as e:
        return False, f"unhandled exception: {e}"

    return False, "unknown provider"


def print_result(r: TestResult):
    status = "PASS" if r.passed else "FAIL"
    print(f"\n{'='*60}")
    print(f"  [{status}] {r.provider.upper()} -- {r.slug}")
    print(f"{'='*60}")
    print(f"  Response time:      {r.response_ms}ms")
    print(f"  Jobs returned:      {r.job_count}")
    print(f"  Field completeness: {r.field_completeness_pct:.1f}%")
    if r.has_compensation:
        print("  Compensation data:  yes")
    print(f"  Error handling:     {'ok' if r.error_handling_ok else 'not tested'}")
    print("  Sample titles:")
    for t in r.sample_titles:
        print(f"    - {t}")
    if r.failures:
        print("  Failures:")
        for f in r.failures:
            print(f"    ! {f}")


def main() -> int:
    print("HireWire ATS API Smoke Test")
    print(f"{'='*60}\n")

    results: list[TestResult] = []

    # --- Ashby (Notion) ---
    print("Testing Ashby (notion)...", flush=True)
    r = test_ashby("notion")
    ok, msg = test_error_handling("ashby")
    r.error_handling_ok = ok
    if not ok:
        r.fail(f"Error handling failed: {msg}")
    else:
        print(f"  Error handling: {msg}")
    results.append(r)

    # --- Greenhouse (Stripe) ---
    print("Testing Greenhouse (stripe)...", flush=True)
    r = test_greenhouse("stripe")
    ok, msg = test_error_handling("greenhouse")
    r.error_handling_ok = ok
    if not ok:
        r.fail(f"Error handling failed: {msg}")
    else:
        print(f"  Error handling: {msg}")
    results.append(r)

    # --- Lever (Spotify) ---
    print("Testing Lever (spotify)...", flush=True)
    r = test_lever("spotify")
    ok, msg = test_error_handling("lever")
    r.error_handling_ok = ok
    if not ok:
        r.fail(f"Error handling failed: {msg}")
    else:
        print(f"  Error handling: {msg}")
    results.append(r)

    # --- Summary ---
    for r in results:
        print_result(r)

    print(f"\n{'='*60}")
    all_passed = all(r.passed for r in results)
    print(f"  OVERALL: {'ALL PASS' if all_passed else 'FAILURES DETECTED'}")
    print(f"{'='*60}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
