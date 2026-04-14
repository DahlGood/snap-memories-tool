"""Write GPS coordinates into image EXIF and video metadata."""

import logging
import subprocess
from pathlib import Path

import piexif

logger = logging.getLogger(__name__)


def _to_rational(value: float) -> tuple:
    """Convert decimal degrees to (degrees, minutes, seconds) as piexif rationals."""
    value = abs(value)
    d = int(value)
    m = int((value - d) * 60)
    s = round(((value - d) * 60 - m) * 60 * 10000)
    return ((d, 1), (m, 1), (s, 10000))


def write_image_gps(jpg_path: Path, lat: float, lon: float) -> None:
    """Embed GPS coordinates into a JPEG's EXIF metadata."""
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
    """Embed GPS coordinates into an MP4's metadata via exiftool."""
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
