"""CLI entry point for snap-memories-tool."""

import argparse
import logging
import os
from pathlib import Path

from tqdm import tqdm

from snap_memories.processing import ProcessConfig, process

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
    parser.add_argument(
        "--workers", type=int, default=os.cpu_count(),
        help="Number of parallel worker processes for images (default: CPU count)"
    )
    parser.add_argument(
        "--video-workers", type=int, default=max(2, (os.cpu_count() or 4) // 4),
        help="Number of parallel worker processes for videos (default: CPU count // 4)"
    )
    args = parser.parse_args()

    base = DEFAULT_BASE_DIR
    config = ProcessConfig(
        memories_dir=args.memories_dir or base / "memories",
        json_path=args.json or base / "json" / "memories_history.json",
        output_dir=args.output_dir or base / "output",
        limit=args.limit,
        workers=args.workers,
        video_workers=args.video_workers,
    )

    with tqdm(total=0, unit="file") as bar:
        def _cb(_completed: int, total: int, *_):
            bar.total = total
            bar.update(1)
        result = process(config, on_progress=_cb)

    logging.info("\nDone.")
    logging.info("  Files processed : %d", result["total"])
    logging.info("  Geo-tagged      : %d", result["geotagged"])
    logging.info("  Composited      : %d", result["composited"])
    logging.info("  No metadata     : %d", result["no_meta"])
