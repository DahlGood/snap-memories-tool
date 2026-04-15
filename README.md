# snap-memories-tool

Process a Snapchat memories export by:

- copying each `*-main` memory into an output folder,
- embedding GPS metadata from `memories_history.json` when available,
- generating composited media for memories that have matching `*-overlay.png` files.

The project provides a CLI command: `snap-process`.

## Requirements

- Python 3.10+
- `ffmpeg` (required for video compositing)
- `exiftool` (required for writing GPS metadata to MP4 files)

## Installation

```bash
pip install .
```

For development:

```bash
pip install -e .[dev]
```

## Expected input layout

By default, the tool reads paths relative to the current working directory:

- `memories/` (media files)
- `json/memories_history.json` (Snap metadata export)
- `output/` (created if missing)

See detailed layout and filename expectations in
[`docs/archive-layout.md`](docs/archive-layout.md).

## Usage

```bash
snap-process
```

Process only a subset:

```bash
snap-process --limit 100
```

Use custom paths:

```bash
snap-process \
  --memories-dir /path/to/memories \
  --json /path/to/json/memories_history.json \
  --output-dir /path/to/output
```

Tune parallel workers:

```bash
snap-process --workers 8 --video-workers 2
```

## CLI options

- `--limit`: Process only the first N `*-main` files.
- `--memories-dir`: Directory containing exported memories media.
- `--json`: Path to `memories_history.json`.
- `--output-dir`: Destination for copied/composited output files.
- `--workers`: Process count for image jobs.
- `--video-workers`: Process count for video jobs.

## Output behavior

For each detected `*-main` media file:

1. Copy original media to output.
2. If GPS metadata exists in JSON, write GPS tags to copied media.
3. If a matching overlay exists, create a `*-composited` output:
   - JPG: alpha composite of main + overlay.
   - MP4: ffmpeg overlay render.
4. If GPS metadata exists, write it to composited output as well.

## Development

Run tests:

```bash
pytest --tb=short
```

Run lint checks:

```bash
ruff check .
```

> Note: the current repository has pre-existing Ruff warnings in test files.
