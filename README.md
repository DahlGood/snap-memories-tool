# snap-memories-tool

Tool for processing Snapchat memories from My Data export. 

This tool processes the raw data and applies the geolocation information as well as any caption, drawing, or other overlay.

Originals in `memories/` are never modified. All output is written to `output/`.

---

## Requirements

| Dependency | Purpose |
|---|---|
| Python 3.10+ | Runtime |
| `ffmpeg` | Video compositing |
| `exiftool` | Writing GPS metadata to MP4 files |

Install system dependencies on macOS:

```bash
brew install ffmpeg exiftool
```

---


For full CLI reference, input layout details, output behavior, and development instructions, see [docs.md](docs.md).
