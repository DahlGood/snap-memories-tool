"""Parse memories_history.json and build a UUID-keyed metadata index."""

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _parse_location(location_str: str) -> tuple[float, float] | None:
    """Parse 'Latitude, Longitude: 33.98, -6.89' → (lat, lon) or None."""
    m = re.search(r"Latitude, Longitude:\s*([\d.-]+),\s*([\d.-]+)", location_str)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if lat == 0.0 and lon == 0.0:
        return None
    return lat, lon


def _extract_mid(download_link: str) -> str | None:
    """Extract the 'mid' UUID from a Snapchat Download Link URL."""
    try:
        qs = parse_qs(urlparse(download_link).query)
        mid_list = qs.get("mid", [])
        return mid_list[0].upper() if mid_list else None
    except Exception:
        return None


def build_metadata_index(json_path: Path) -> dict:
    """
    Return {UUID_UPPER: {"lat": float, "lon": float, "date": str, "media_type": str}}.
    Records with no location or 0,0 coordinates are stored without lat/lon keys.
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    index = {}
    for record in data.get("Saved Media", []):
        mid = _extract_mid(record.get("Download Link", ""))
        if not mid:
            continue
        entry = {
            "date": record.get("Date", ""),
            "media_type": record.get("Media Type", ""),
        }
        coords = _parse_location(record.get("Location", ""))
        if coords:
            entry["lat"], entry["lon"] = coords
        index[mid] = entry

    return index
