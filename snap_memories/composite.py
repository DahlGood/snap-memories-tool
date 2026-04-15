"""Composite PNG overlays onto images and videos."""

import logging
import subprocess
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def composite_image(main_path: Path, overlay_path: Path, out_path: Path) -> bool:
    """Alpha-composite a PNG overlay onto a JPEG and save the result."""
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
    """Burn a static PNG overlay onto all frames of an MP4 via ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(main_path),
        "-i", str(overlay_path),
        "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
        "-map", "[v]",
        "-map", "0:a?",
        "-codec:v", "libx264",
        "-crf", "18",
        "-preset", "medium",
        "-codec:a", "copy",
        "-loglevel", "error",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("ffmpeg failed for %s: %s", main_path.name, result.stderr.strip())
        return False
    return True
