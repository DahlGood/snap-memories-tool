# Snapchat archive layout and matching rules

This project expects Snapchat export files to follow specific naming patterns so
it can match media, overlays, and metadata.

## Required metadata file

- `json/memories_history.json`

The tool reads the `Saved Media` array and extracts each record's `Download Link`
query parameter `mid` as the media UUID key.

## Media naming conventions

Inside `memories/`, files are matched by UUID embedded in the filename.

- Main media:
  - `YYYY-MM-DD_<UUID>-main.jpg`
  - `YYYY-MM-DD_<UUID>-main.mp4`
- Overlay image:
  - `YYYY-MM-DD_<UUID>-overlay.png`

The date prefix can vary, but filenames must include `_` and the `-main` /
`-overlay` suffix patterns shown above.

## Matching behavior

For each `*-main` file:

1. Extract UUID from `<UUID>-main`.
2. Look up metadata by UUID in `memories_history.json`.
3. Look up overlay by UUID among `*-overlay.png` files.

If either metadata or overlay is missing, processing continues with the data that
is available.

## GPS metadata behavior

- Coordinates are read from the `Location` field when it contains:
  - `Latitude, Longitude: <lat>, <lon>`
- `0.0, 0.0` is treated as missing GPS data.
- JPG GPS tags are written with `piexif`.
- MP4 GPS tags are written with `exiftool`.

## Compositing behavior

- JPG output: Pillow alpha compositing.
  - Overlay is resized to main image dimensions if needed.
- MP4 output: ffmpeg overlay filter.
  - Video stream is re-encoded and existing audio is preserved when present.
