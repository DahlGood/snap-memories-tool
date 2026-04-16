---

## Input Layout

By default the tool reads paths relative to the current working directory:

```
memories/                        # exported media files
json/memories_history.json       # Snapchat metadata export
output/                          # created automatically if missing
```

**File naming convention:** `YYYY-MM-DD_<UUID>-(main|overlay).<ext>`

Main files are `.jpg` or `.mp4`; overlays are always `.png`. The UUID in each filename matches the `mid=` parameter in the corresponding JSON record's `Download Link`.

## Installation

Create and activate a virtual environment, then install the package:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install .
```

For development (includes test and lint tooling):

```bash
pip install ".[dev]"
```

---

## Usage

Process all memories:

```bash
snap-process
```

---

## CLI Reference

| Option | Default | Description |
|---|---|---|
| `--limit N` | *(all)* | Process only the first N main files |
| `--memories-dir PATH` | `<cwd>/memories` | Directory containing exported memories media |
| `--json PATH` | `<cwd>/json/memories_history.json` | Path to `memories_history.json` |
| `--output-dir PATH` | `<cwd>/output` | Destination for processed output files |
| `--workers N` | CPU count | Parallel worker processes for image jobs |
| `--video-workers N` | CPU count ÷ 4 | Parallel worker processes for video jobs |

---

---

## Development

Run tests:

```bash
pytest tests/ -v
```

Run lint checks:

```bash
ruff check .
```
