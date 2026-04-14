#!/usr/bin/env python3
import argparse
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import piexif
from PIL import Image
from tqdm import tqdm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
MEMORIES_DIR = BASE_DIR / "memories"
JSON_PATH = BASE_DIR / "json" / "memories_history.json"
OUTPUT_DIR = BASE_DIR / "output"

# ---------------------------------------------------------------------------
# Metadata index
# ---------------------------------------------------------------------------


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
    Returns {UUID_UPPER: {"lat": float, "lon": float, "date": str, "media_type": str}}
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


# ---------------------------------------------------------------------------
# GPS EXIF helpers
# ---------------------------------------------------------------------------


def _to_rational(value: float) -> tuple:
    """Convert decimal degrees to (degrees, minutes, seconds) as piexif rationals."""
    value = abs(value)
    d = int(value)
    m = int((value - d) * 60)
    s = round(((value - d) * 60 - m) * 60 * 10000)
    return ((d, 1), (m, 1), (s, 10000))


def write_image_gps(jpg_path: Path, lat: float, lon: float) -> None:
    try:
        exif_dict = piexif.load(str(jpg_path))
    except Exception:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

    exif_dict["GPS"] = {
        piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
        piexif.GPSIFD.GPSLatitude: _to_rational(lat),
        piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
        piexif.GPSIFD.GPSLongitude: _to_rational(lon),
    }
    try:
        piexif.insert(piexif.dump(exif_dict), str(jpg_path))
    except Exception as e:
        logger.warning("GPS write failed for %s: %s", jpg_path.name, e)


def write_video_gps(mp4_path: Path, lat: float, lon: float) -> None:
    lat_ref = "N" if lat >= 0 else "S"
    lon_ref = "E" if lon >= 0 else "W"
    cmd = [
        "exiftool",
        f"-GPSLatitude={abs(lat)}",
        f"-GPSLatitudeRef={lat_ref}",
        f"-GPSLongitude={abs(lon)}",
        f"-GPSLongitudeRef={lon_ref}",
        "-overwrite_original",
        "-q",
        str(mp4_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("exiftool failed for %s: %s", mp4_path.name, result.stderr.strip())


# ---------------------------------------------------------------------------
# Compositing
# ---------------------------------------------------------------------------


def composite_image(main_path: Path, overlay_path: Path, out_path: Path) -> bool:
    try:
        main_img = Image.open(main_path).convert("RGBA")
        overlay_img = Image.open(overlay_path).convert("RGBA")

        if overlay_img.size != main_img.size:
            overlay_img = overlay_img.resize(main_img.size, Image.LANCZOS)

        composited = Image.alpha_composite(main_img, overlay_img)
        composited.convert("RGB").save(out_path, "JPEG", quality=95)
        return True
    except Exception as e:
        logger.warning("Image composite failed for %s: %s", main_path.name, e)
        return False


def composite_video(main_path: Path, overlay_path: Path, out_path: Path) -> bool:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(main_path),
        "-i",
        str(overlay_path),
        "-filter_complex",
        "overlay=0:0",
        "-codec:a",
        "copy",
        "-loglevel",
        "error",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("ffmpeg failed for %s: %s", main_path.name, result.stderr.strip())
        return False
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Process Snapchat memories archive.")
    parser.add_argument(
        "--limit", type=int, default=None, help="Process only N files (for testing)"
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)

    logging.info("Building metadata index...")
    metadata = build_metadata_index(JSON_PATH)
    logging.info("%d records loaded from JSON.", len(metadata))

    # build overlay lookup: UUID → overlay path
    overlays: dict[str, Path] = {}
    for f in MEMORIES_DIR.glob("*-overlay.png"):
        # filename: YYYY-MM-DD_UUID-overlay.png
        parts = f.stem.split("_", 1)  # ["YYYY-MM-DD", "UUID-overlay"]
        if len(parts) == 2:
            uuid = parts[1].replace("-overlay", "").upper()
            overlays[uuid] = f

    # collect all main snaps
    main_files = sorted(
        [f for f in MEMORIES_DIR.iterdir() if f.stem.endswith("-main")],
        key=lambda f: f.name,
    )
    if args.limit:
        main_files = main_files[: args.limit]

    n_geotagged = 0
    n_composited = 0
    n_no_meta = 0

    logging.info("Processing %d files → %s/\n", len(main_files), OUTPUT_DIR)

    for main_path in tqdm(main_files, unit="file"):
        is_image = main_path.suffix.lower() == ".jpg"
        is_video = main_path.suffix.lower() == ".mp4"

        # extract UUID from filename: YYYY-MM-DD_UUID-main.ext
        stem_parts = main_path.stem.split("_", 1)  # ["YYYY-MM-DD", "UUID-main"]
        if len(stem_parts) < 2:
            continue
        uuid = stem_parts[1].replace("-main", "").upper()

        meta = metadata.get(uuid)
        has_gps = meta and "lat" in meta
        overlay_path = overlays.get(uuid)

        # copy main to output
        out_main = OUTPUT_DIR / main_path.name
        shutil.copy2(main_path, out_main)

        # write gps to main copy
        if has_gps:
            lat, lon = meta["lat"], meta["lon"]
            if is_image:
                write_image_gps(out_main, lat, lon)
            elif is_video:
                write_video_gps(out_main, lat, lon)
            n_geotagged += 1
        else:
            n_no_meta += 1

        # composite + gps
        if overlay_path:
            if is_image:
                out_comp = OUTPUT_DIR / main_path.name.replace("-main.jpg", "-composited.jpg")
                ok = composite_image(main_path, overlay_path, out_comp)
                if ok:
                    if has_gps:
                        write_image_gps(out_comp, lat, lon)
                    n_composited += 1

            elif is_video:
                out_comp = OUTPUT_DIR / main_path.name.replace("-main.mp4", "-composited.mp4")
                ok = composite_video(main_path, overlay_path, out_comp)
                if ok:
                    if has_gps:
                        write_video_gps(out_comp, lat, lon)
                    n_composited += 1

    logging.info("\nDone.")
    logging.info("  Files processed : %d", len(main_files))
    logging.info("  Geo-tagged      : %d", n_geotagged)
    logging.info("  Composited      : %d", n_composited)
    logging.info("  No metadata     : %d", n_no_meta)


if __name__ == "__main__":
    main()
