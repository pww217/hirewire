"""Shared utilities for HireWire scraper."""

import re
from typing import Optional


def parse_location(raw: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse a location string into (raw, city, state) components.

    Handles common formats:
      "San Francisco, CA"
      "New York, NY, USA"
      "London, United Kingdom"
      "Remote"
      "Remote - US"

    Args:
        raw: Raw location string from ATS API

    Returns:
        Tuple of (location_raw, location_city, location_state)
        All may be None if input is empty/None.
    """
    if not raw or not raw.strip():
        return None, None, None

    raw = raw.strip()

    # Treat pure "Remote" variants as no specific location
    if re.match(r"^remote$", raw, re.IGNORECASE):
        return raw, None, None

    # Strip "Remote - " prefix
    cleaned = re.sub(r"^remote\s*[-–]\s*", "", raw, flags=re.IGNORECASE).strip()

    parts = [p.strip() for p in cleaned.split(",") if p.strip()]

    if len(parts) >= 3:
        city, state = parts[0], parts[1]
    elif len(parts) == 2:
        city = parts[0]
        # If second part looks like a US state abbreviation, treat as state
        state = parts[1] if len(parts[1]) <= 3 and parts[1].upper() == parts[1] else None
    elif len(parts) == 1:
        city = parts[0]
        state = None
    else:
        city = state = None

    return raw, city or None, state or None
