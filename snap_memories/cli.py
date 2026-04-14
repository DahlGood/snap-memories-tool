"""CLI entry point for snap-memories-tool."""

import argparse
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

from snap_memories.composite import composite_image, composite_video
from snap_memories.gps import write_image_gps, write_video_gps
from snap_memories.metadata import build_metadata_index

BASE_DIR = Path.cwd()
MEMORIES_DIR = BASE_DIR / "memories"
JSON_PATH = BASE_DIR / "json" / "memories_history.json"
OUTPUT_DIR = BASE_DIR / "output"


def _process_file(
    main_path: Path,
    metadata: dict,
    overlays: dict[str, Path],
    output_dir: Path,
) -> tuple[bool, bool, bool]:
    """Process a single memory file. Returns (geotagged, composited, no_meta)."""
    is_image = main_path.suffix.lower() == ".jpg"
    is_video = main_path.suffix.lower() == ".mp4"

    # Extract UUID from filename: YYYY-MM-DD_UUID-main.ext
    stem_parts = main_path.stem.split("_", 1)  # ["YYYY-MM-DD", "UUID-main"]
    if len(stem_parts) < 2:
        return False, False, False
    uuid = stem_parts[1].replace("-main", "").upper()

    meta = metadata.get(uuid)
    has_gps = meta and "lat" in meta
    overlay_path = overlays.get(uuid)

    # Copy main to output
    out_main = output_dir / main_path.name
    shutil.copy2(main_path, out_main)

    geotagged = False
    composited = False
    no_meta = False

    # Write GPS to main copy
    if has_gps:
        lat, lon = meta["lat"], meta["lon"]
        if is_image:
            write_image_gps(out_main, lat, lon)
        elif is_video:
            write_video_gps(out_main, lat, lon)
        geotagged = True
    else:
        no_meta = True

    # Composite + GPS
    if overlay_path:
        if is_image:
            out_comp = output_dir / main_path.name.replace("-main.jpg", "-composited.jpg")
            ok = composite_image(main_path, overlay_path, out_comp)
            if ok:
                if has_gps:
                    write_image_gps(out_comp, lat, lon)
                composited = True

        elif is_video:
            out_comp = output_dir / main_path.name.replace("-main.mp4", "-composited.mp4")
            ok = composite_video(main_path, overlay_path, out_comp)
            if ok:
                if has_gps:
                    write_video_gps(out_comp, lat, lon)
                composited = True

    return geotagged, composited, no_meta


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Process Snapchat memories archive.")
    parser.add_argument(
        "--limit", type=int, default=None, help="Process only N files (for testing)"
    )
    parser.add_argument(
        "--workers", type=int, default=os.cpu_count(),
        help="Number of parallel worker threads (default: CPU count)"
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)

    logging.info("Building metadata index...")
    metadata = build_metadata_index(JSON_PATH)
    logging.info("%d records loaded from JSON.", len(metadata))

    # Build overlay lookup: UUID → overlay path
    overlays: dict[str, Path] = {}
    for f in MEMORIES_DIR.glob("*-overlay.png"):
        parts = f.stem.split("_", 1)  # ["YYYY-MM-DD", "UUID-overlay"]
        if len(parts) == 2:
            uuid = parts[1].replace("-overlay", "").upper()
            overlays[uuid] = f

    # Collect all main snaps
    main_files = sorted(
        [f for f in MEMORIES_DIR.iterdir() if f.stem.endswith("-main")],
        key=lambda f: f.name,
    )
    if args.limit:
        main_files = main_files[: args.limit]

    n_geotagged = 0
    n_composited = 0
    n_no_meta = 0

    logging.info("Processing %d files → %s/ (workers=%d)\n", len(main_files), OUTPUT_DIR, args.workers)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_process_file, p, metadata, overlays, OUTPUT_DIR): p
            for p in main_files
        }
        with tqdm(total=len(main_files), unit="file") as bar:
            for fut in as_completed(futures):
                geotagged, composited, no_meta = fut.result()
                n_geotagged += geotagged
                n_composited += composited
                n_no_meta += no_meta
                bar.update(1)

    logging.info("\nDone.")
    logging.info("  Files processed : %d", len(main_files))
    logging.info("  Geo-tagged      : %d", n_geotagged)
    logging.info("  Composited      : %d", n_composited)
    logging.info("  No metadata     : %d", n_no_meta)
