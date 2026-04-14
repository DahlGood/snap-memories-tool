"""CLI entry point for snap-memories-tool."""

import argparse
import logging
import shutil
from pathlib import Path

from tqdm import tqdm

from snap_memories.composite import composite_image, composite_video
from snap_memories.gps import write_image_gps, write_video_gps
from snap_memories.metadata import build_metadata_index

DEFAULT_BASE_DIR = Path.cwd()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Process Snapchat memories archive.")
    parser.add_argument(
        "--limit", type=int, default=None, help="Process only N files (for testing)"
    )
    parser.add_argument(
        "--memories-dir",
        type=Path,
        default=None,
        help="Path to the memories folder (default: <cwd>/memories)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Path to memories_history.json (default: <cwd>/json/memories_history.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Path to output folder (default: <cwd>/output)",
    )
    args = parser.parse_args()

    base = DEFAULT_BASE_DIR
    memories_dir = args.memories_dir or base / "memories"
    json_path = args.json or base / "json" / "memories_history.json"
    output_dir = args.output_dir or base / "output"

    output_dir.mkdir(exist_ok=True)

    logging.info("Building metadata index...")
    metadata = build_metadata_index(json_path)
    logging.info("%d records loaded from JSON.", len(metadata))

    # Build overlay lookup: UUID → overlay path
    overlays: dict[str, Path] = {}
    for f in memories_dir.glob("*-overlay.png"):
        parts = f.stem.split("_", 1)  # ["YYYY-MM-DD", "UUID-overlay"]
        if len(parts) == 2:
            uuid = parts[1].replace("-overlay", "").upper()
            overlays[uuid] = f

    # Collect all main snaps
    main_files = sorted(
        [f for f in memories_dir.iterdir() if f.stem.endswith("-main")],
        key=lambda f: f.name,
    )
    if args.limit:
        main_files = main_files[: args.limit]

    n_geotagged = 0
    n_composited = 0
    n_no_meta = 0

    logging.info("Processing %d files → %s/\n", len(main_files), output_dir)

    for main_path in tqdm(main_files, unit="file"):
        is_image = main_path.suffix.lower() == ".jpg"
        is_video = main_path.suffix.lower() == ".mp4"

        # Extract UUID from filename: YYYY-MM-DD_UUID-main.ext
        stem_parts = main_path.stem.split("_", 1)  # ["YYYY-MM-DD", "UUID-main"]
        if len(stem_parts) < 2:
            continue
        uuid = stem_parts[1].replace("-main", "").upper()

        meta = metadata.get(uuid)
        has_gps = meta and "lat" in meta
        overlay_path = overlays.get(uuid)

        # Copy main to output
        out_main = output_dir / main_path.name
        shutil.copy2(main_path, out_main)

        # Write GPS to main copy
        if has_gps:
            lat, lon = meta["lat"], meta["lon"]
            if is_image:
                write_image_gps(out_main, lat, lon)
            elif is_video:
                write_video_gps(out_main, lat, lon)
            n_geotagged += 1
        else:
            n_no_meta += 1

        # Composite + GPS
        if overlay_path:
            if is_image:
                out_comp = output_dir / main_path.name.replace("-main.jpg", "-composited.jpg")
                ok = composite_image(main_path, overlay_path, out_comp)
                if ok:
                    if has_gps:
                        write_image_gps(out_comp, lat, lon)
                    n_composited += 1

            elif is_video:
                out_comp = output_dir / main_path.name.replace("-main.mp4", "-composited.mp4")
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
