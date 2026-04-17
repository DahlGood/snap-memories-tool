"""Public library API for snap-memories-tool processing."""

import logging
import os
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from snap_memories.composite import composite_image, composite_video
from snap_memories.gps import write_image_gps, write_video_gps
from snap_memories.metadata import build_metadata_index

# on_progress(completed, total, geotagged, composited, no_meta)
ProgressCallback = Callable[[int, int, bool, bool, bool], None]


@dataclass
class ProcessConfig:
    memories_dir: Path
    json_path: Path
    output_dir: Path
    limit: int | None = None
    workers: int = field(default_factory=lambda: os.cpu_count() or 4)
    video_workers: int = field(default_factory=lambda: max(2, (os.cpu_count() or 4) // 4))


def _process_file(
    main_path: Path,
    metadata: dict,
    overlays: dict[str, Path],
    output_dir: Path,
) -> tuple[bool, bool, bool]:
    """Process a single memory file. Returns (geotagged, composited, no_meta)."""
    is_image = main_path.suffix.lower() == ".jpg"
    is_video = main_path.suffix.lower() == ".mp4"

    stem_parts = main_path.stem.split("_", 1)
    if len(stem_parts) < 2:
        return False, False, False
    uuid = stem_parts[1].replace("-main", "").upper()

    meta = metadata.get(uuid)
    has_gps = meta and "lat" in meta
    overlay_path = overlays.get(uuid)

    out_main = output_dir / main_path.name
    if is_image:
        out_comp = output_dir / main_path.name.replace("-main.jpg", "-composited.jpg")
    elif is_video:
        out_comp = output_dir / main_path.name.replace("-main.mp4", "-composited.mp4")
    else:
        out_comp = None

    expected_done = out_main.exists() and (not overlay_path or (out_comp is not None and out_comp.exists()))
    if expected_done:
        return bool(has_gps), bool(overlay_path), not bool(meta)

    shutil.copy2(main_path, out_main)

    geotagged = False
    composited = False
    no_meta = False

    if has_gps:
        lat, lon = meta["lat"], meta["lon"]
        if is_image:
            write_image_gps(out_main, lat, lon)
        elif is_video:
            write_video_gps(out_main, lat, lon)
        geotagged = True
    else:
        no_meta = True

    if overlay_path:
        if is_image:
            ok = composite_image(main_path, overlay_path, out_comp)
            if ok:
                if has_gps:
                    write_image_gps(out_comp, lat, lon)
                composited = True
        elif is_video:
            ok = composite_video(main_path, overlay_path, out_comp)
            if ok:
                if has_gps:
                    write_video_gps(out_comp, lat, lon)
                composited = True

    return geotagged, composited, no_meta


def process(config: ProcessConfig, on_progress: ProgressCallback | None = None) -> dict:
    """
    Run processing for all memories. Returns summary:
      {total, geotagged, composited, no_meta}
    Calls on_progress(completed, total, geotagged, composited, no_meta) after each file.
    """
    config.output_dir.mkdir(exist_ok=True)

    logging.info("Building metadata index...")
    metadata = build_metadata_index(config.json_path)
    logging.info("%d records loaded from JSON.", len(metadata))

    overlays: dict[str, Path] = {}
    for f in config.memories_dir.glob("*-overlay.png"):
        parts = f.stem.split("_", 1)
        if len(parts) == 2:
            uuid = parts[1].replace("-overlay", "").upper()
            overlays[uuid] = f

    main_files = sorted(
        [f for f in config.memories_dir.iterdir() if f.stem.endswith("-main")],
        key=lambda f: f.name,
    )
    if config.limit:
        main_files = main_files[: config.limit]

    total = len(main_files)
    n_geotagged = 0
    n_composited = 0
    n_no_meta = 0
    completed = 0

    image_files = [f for f in main_files if f.suffix.lower() == ".jpg"]
    video_files = [f for f in main_files if f.suffix.lower() == ".mp4"]

    logging.info(
        "Processing %d images (workers=%d) + %d videos (workers=%d) → %s/",
        len(image_files), config.workers,
        len(video_files), config.video_workers,
        config.output_dir,
    )

    futures: dict = {}
    with (
        ProcessPoolExecutor(max_workers=config.workers) as image_pool,
        ProcessPoolExecutor(max_workers=config.video_workers) as video_pool,
    ):
        for p in image_files:
            fut = image_pool.submit(_process_file, p, metadata, overlays, config.output_dir)
            futures[fut] = p
        for p in video_files:
            fut = video_pool.submit(_process_file, p, metadata, overlays, config.output_dir)
            futures[fut] = p

        for fut in as_completed(futures):
            geotagged, composited, no_meta = fut.result()
            n_geotagged += geotagged
            n_composited += composited
            n_no_meta += no_meta
            completed += 1
            if on_progress:
                on_progress(completed, total, geotagged, composited, no_meta)

    return {
        "total": total,
        "geotagged": n_geotagged,
        "composited": n_composited,
        "no_meta": n_no_meta,
    }
