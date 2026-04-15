"""Tests for snap_memories.cli._process_file and main."""

import sys
from concurrent.futures import Future
from pathlib import Path

import pytest

from snap_memories.cli import _process_file, main

UUID = "F787F2BD-54EB-4CD1-A116-06F884A7B3A2"
JPG_NAME = f"2024-01-15_{UUID.lower()}-main.jpg"
MP4_NAME = f"2024-01-15_{UUID.lower()}-main.mp4"

META_WITH_GPS = {UUID: {"lat": 33.98, "lon": -6.89, "date": "", "media_type": "IMAGE"}}
META_WITHOUT_GPS = {UUID: {"date": "", "media_type": "IMAGE"}}


def _resolved_future(result):
    """Return an already-resolved Future with the given result."""
    f = Future()
    f.set_result(result)
    return f


class TestProcessFile:
    def test_malformed_filename_returns_triple_false(self, mocker, tmp_path):
        mocker.patch("snap_memories.cli.shutil.copy2")
        result = _process_file(tmp_path / "malformed.jpg", {}, {}, tmp_path)
        assert result == (False, False, False)

    def test_jpg_with_gps_no_overlay_is_geotagged(self, mocker, tmp_path):
        mocker.patch("snap_memories.cli.shutil.copy2")
        mock_write_gps = mocker.patch("snap_memories.cli.write_image_gps")

        geotagged, composited, no_meta = _process_file(
            tmp_path / JPG_NAME, META_WITH_GPS, {}, tmp_path
        )

        assert geotagged is True
        assert composited is False
        assert no_meta is False
        mock_write_gps.assert_called_once()

    def test_jpg_with_gps_and_overlay_composite_succeeds(self, mocker, tmp_path):
        mocker.patch("snap_memories.cli.shutil.copy2")
        mock_write_gps = mocker.patch("snap_memories.cli.write_image_gps")
        mocker.patch("snap_memories.cli.composite_image", return_value=True)

        overlays = {UUID: tmp_path / f"2024-01-15_{UUID.lower()}-overlay.png"}
        geotagged, composited, no_meta = _process_file(
            tmp_path / JPG_NAME, META_WITH_GPS, overlays, tmp_path
        )

        assert geotagged is True
        assert composited is True
        assert no_meta is False
        # GPS written twice: once for the main copy, once for the composited copy
        assert mock_write_gps.call_count == 2

    def test_jpg_with_gps_and_overlay_composite_fails(self, mocker, tmp_path):
        mocker.patch("snap_memories.cli.shutil.copy2")
        mock_write_gps = mocker.patch("snap_memories.cli.write_image_gps")
        mocker.patch("snap_memories.cli.composite_image", return_value=False)

        overlays = {UUID: tmp_path / f"2024-01-15_{UUID.lower()}-overlay.png"}
        geotagged, composited, no_meta = _process_file(
            tmp_path / JPG_NAME, META_WITH_GPS, overlays, tmp_path
        )

        assert geotagged is True
        assert composited is False
        assert mock_write_gps.call_count == 1

    def test_jpg_uuid_not_in_index_sets_no_meta(self, mocker, tmp_path):
        mocker.patch("snap_memories.cli.shutil.copy2")

        geotagged, composited, no_meta = _process_file(
            tmp_path / JPG_NAME, {}, {}, tmp_path
        )

        assert geotagged is False
        assert no_meta is True

    def test_jpg_uuid_in_index_without_gps_sets_no_meta(self, mocker, tmp_path):
        mocker.patch("snap_memories.cli.shutil.copy2")

        geotagged, composited, no_meta = _process_file(
            tmp_path / JPG_NAME, META_WITHOUT_GPS, {}, tmp_path
        )

        assert geotagged is False
        assert no_meta is True

    def test_mp4_with_gps_no_overlay_calls_video_gps(self, mocker, tmp_path):
        mocker.patch("snap_memories.cli.shutil.copy2")
        mock_write_video_gps = mocker.patch("snap_memories.cli.write_video_gps")

        meta = {UUID: {"lat": 33.98, "lon": -6.89, "date": "", "media_type": "VIDEO"}}
        geotagged, composited, no_meta = _process_file(
            tmp_path / MP4_NAME, meta, {}, tmp_path
        )

        assert geotagged is True
        assert composited is False
        assert no_meta is False
        mock_write_video_gps.assert_called_once()
        call_args = mock_write_video_gps.call_args[0]
        assert call_args[1] == pytest.approx(33.98)
        assert call_args[2] == pytest.approx(-6.89)

    def test_mp4_with_gps_and_overlay_composite_succeeds(self, mocker, tmp_path):
        mocker.patch("snap_memories.cli.shutil.copy2")
        mock_write_video_gps = mocker.patch("snap_memories.cli.write_video_gps")
        mocker.patch("snap_memories.cli.composite_video", return_value=True)

        meta = {UUID: {"lat": 33.98, "lon": -6.89, "date": "", "media_type": "VIDEO"}}
        overlays = {UUID: tmp_path / f"2024-01-15_{UUID.lower()}-overlay.png"}
        geotagged, composited, no_meta = _process_file(
            tmp_path / MP4_NAME, meta, overlays, tmp_path
        )

        assert geotagged is True
        assert composited is True
        assert no_meta is False
        # GPS written twice: once for main, once for composited
        assert mock_write_video_gps.call_count == 2

    def test_mp4_with_gps_and_overlay_composite_fails(self, mocker, tmp_path):
        mocker.patch("snap_memories.cli.shutil.copy2")
        mock_write_video_gps = mocker.patch("snap_memories.cli.write_video_gps")
        mocker.patch("snap_memories.cli.composite_video", return_value=False)

        meta = {UUID: {"lat": 33.98, "lon": -6.89, "date": "", "media_type": "VIDEO"}}
        overlays = {UUID: tmp_path / f"2024-01-15_{UUID.lower()}-overlay.png"}
        geotagged, composited, no_meta = _process_file(
            tmp_path / MP4_NAME, meta, overlays, tmp_path
        )

        assert geotagged is True
        assert composited is False
        assert mock_write_video_gps.call_count == 1


class TestMain:
    def _make_mock_pool(self, mocker):
        """Return a MagicMock that satisfies the context-manager + submit protocol."""
        pool = mocker.MagicMock()
        pool.__enter__ = mocker.MagicMock(return_value=pool)
        pool.__exit__ = mocker.MagicMock(return_value=False)
        return pool

    def test_empty_memories_dir_runs_without_error(self, mocker, tmp_path):
        memories_dir = tmp_path / "memories"
        memories_dir.mkdir()
        json_path = tmp_path / "memories.json"
        json_path.write_text('{"Saved Media": []}', encoding="utf-8")
        output_dir = tmp_path / "output"

        mocker.patch.object(
            sys, "argv",
            [
                "snap-process",
                "--memories-dir", str(memories_dir),
                "--json", str(json_path),
                "--output-dir", str(output_dir),
                "--workers", "1",
                "--video-workers", "1",
            ],
        )
        mocker.patch("snap_memories.cli.tqdm")

        main()

        assert output_dir.exists()

    def test_processes_image_and_video_with_mocked_pool(self, mocker, tmp_path):
        memories_dir = tmp_path / "memories"
        memories_dir.mkdir()
        json_path = tmp_path / "memories.json"
        json_path.write_text('{"Saved Media": []}', encoding="utf-8")
        output_dir = tmp_path / "output"

        # One image + one overlay + one video in memories dir
        (memories_dir / f"2024-01-15_{UUID.lower()}-main.jpg").touch()
        (memories_dir / f"2024-01-15_{UUID.lower()}-main.mp4").touch()
        (memories_dir / f"2024-01-15_{UUID.lower()}-overlay.png").touch()

        mocker.patch.object(
            sys, "argv",
            [
                "snap-process",
                "--memories-dir", str(memories_dir),
                "--json", str(json_path),
                "--output-dir", str(output_dir),
                "--limit", "5",
            ],
        )
        mocker.patch("snap_memories.cli.build_metadata_index", return_value={})

        submitted: list[Future] = []

        def _submit(fn, *args, **kwargs):
            f = _resolved_future((False, False, True))
            submitted.append(f)
            return f

        mock_pool = self._make_mock_pool(mocker)
        mock_pool.submit.side_effect = _submit
        mocker.patch("snap_memories.cli.ProcessPoolExecutor", return_value=mock_pool)
        mocker.patch(
            "snap_memories.cli.as_completed",
            side_effect=lambda d: iter(d.keys()),
        )
        mocker.patch("snap_memories.cli.tqdm")

        main()

        # One image + one video file submitted across both pools
        assert mock_pool.submit.call_count == 2

    def test_processes_only_image_files_without_overlay(self, mocker, tmp_path):
        memories_dir = tmp_path / "memories"
        memories_dir.mkdir()
        json_path = tmp_path / "memories.json"
        json_path.write_text('{"Saved Media": []}', encoding="utf-8")
        output_dir = tmp_path / "output"

        UUID2 = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
        (memories_dir / f"2024-01-15_{UUID.lower()}-main.jpg").touch()
        (memories_dir / f"2024-01-16_{UUID2.lower()}-main.jpg").touch()

        mocker.patch.object(
            sys, "argv",
            [
                "snap-process",
                "--memories-dir", str(memories_dir),
                "--json", str(json_path),
                "--output-dir", str(output_dir),
                "--limit", "1",
            ],
        )
        mocker.patch("snap_memories.cli.build_metadata_index", return_value={})

        submitted: list[Future] = []

        def _submit(fn, *args, **kwargs):
            f = _resolved_future((True, False, False))
            submitted.append(f)
            return f

        mock_pool = self._make_mock_pool(mocker)
        mock_pool.submit.side_effect = _submit
        mocker.patch("snap_memories.cli.ProcessPoolExecutor", return_value=mock_pool)
        mocker.patch(
            "snap_memories.cli.as_completed",
            side_effect=lambda d: iter(d.keys()),
        )
        mocker.patch("snap_memories.cli.tqdm")

        main()

        # --limit 1 restricts to one file even though two exist
        assert mock_pool.submit.call_count == 1
