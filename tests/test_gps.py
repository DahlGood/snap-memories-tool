"""Tests for snap_memories.gps: write_image_gps and write_video_gps."""

import logging
from pathlib import Path

import piexif
import pytest

from snap_memories.gps import write_image_gps, write_video_gps


class TestWriteImageGps:
    def test_positive_coords_write_north_east_refs(self, tiny_jpeg):
        write_image_gps(tiny_jpeg, 33.98, 20.0)

        gps = piexif.load(str(tiny_jpeg))["GPS"]
        assert gps[piexif.GPSIFD.GPSLatitudeRef].startswith(b"N")
        assert gps[piexif.GPSIFD.GPSLongitudeRef].startswith(b"E")

    def test_negative_lat_writes_south_ref(self, tiny_jpeg):
        write_image_gps(tiny_jpeg, -33.98, 20.0)

        gps = piexif.load(str(tiny_jpeg))["GPS"]
        assert gps[piexif.GPSIFD.GPSLatitudeRef].startswith(b"S")

    def test_negative_lon_writes_west_ref(self, tiny_jpeg):
        write_image_gps(tiny_jpeg, 33.98, -6.89)

        gps = piexif.load(str(tiny_jpeg))["GPS"]
        assert gps[piexif.GPSIFD.GPSLongitudeRef].startswith(b"W")

    def test_corrupt_jpeg_does_not_raise(self, tmp_path):
        bad_jpg = tmp_path / "corrupt.jpg"
        bad_jpg.write_bytes(b"this is not a jpeg")

        # Should log a warning but never propagate an exception
        write_image_gps(bad_jpg, 10.0, 20.0)


class TestWriteVideoGps:
    def test_positive_coords_command_uses_north_east(self, mocker, tmp_path):
        mock_run = mocker.patch(
            "snap_memories.gps.subprocess.run",
            return_value=mocker.MagicMock(returncode=0, stderr=""),
        )
        write_video_gps(tmp_path / "clip.mp4", 33.98, 20.0)

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "exiftool"
        assert any("GPSLatitudeRef=N" in arg for arg in cmd)
        assert any("GPSLongitudeRef=E" in arg for arg in cmd)

    def test_negative_lat_command_uses_south(self, mocker, tmp_path):
        mock_run = mocker.patch(
            "snap_memories.gps.subprocess.run",
            return_value=mocker.MagicMock(returncode=0, stderr=""),
        )
        write_video_gps(tmp_path / "clip.mp4", -33.98, 20.0)

        cmd = mock_run.call_args[0][0]
        assert any("GPSLatitudeRef=S" in arg for arg in cmd)

    def test_negative_lon_command_uses_west(self, mocker, tmp_path):
        mock_run = mocker.patch(
            "snap_memories.gps.subprocess.run",
            return_value=mocker.MagicMock(returncode=0, stderr=""),
        )
        write_video_gps(tmp_path / "clip.mp4", 33.98, -6.89)

        cmd = mock_run.call_args[0][0]
        assert any("GPSLongitudeRef=W" in arg for arg in cmd)

    def test_nonzero_returncode_logs_warning_without_raising(self, mocker, tmp_path, caplog):
        mocker.patch(
            "snap_memories.gps.subprocess.run",
            return_value=mocker.MagicMock(returncode=1, stderr="some exiftool error"),
        )

        with caplog.at_level(logging.WARNING, logger="snap_memories.gps"):
            write_video_gps(tmp_path / "clip.mp4", 10.0, 20.0)

        assert any("exiftool failed" in r.message for r in caplog.records)
