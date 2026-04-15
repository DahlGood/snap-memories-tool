"""Tests for snap_memories.composite: composite_image and composite_video."""

import logging
from pathlib import Path

import pytest

from snap_memories.composite import composite_image, composite_video


class TestCompositeImage:
    def test_matching_size_returns_true_and_creates_output(
        self, ten_by_ten_jpeg, ten_by_ten_overlay, tmp_path
    ):
        out = tmp_path / "composited.jpg"
        result = composite_image(ten_by_ten_jpeg, ten_by_ten_overlay, out)

        assert result is True
        assert out.exists()

    def test_smaller_overlay_is_resized_and_returns_true(
        self, ten_by_ten_jpeg, five_by_five_overlay, tmp_path
    ):
        out = tmp_path / "composited.jpg"
        result = composite_image(ten_by_ten_jpeg, five_by_five_overlay, out)

        assert result is True
        assert out.exists()

    def test_nonexistent_main_returns_false(self, ten_by_ten_overlay, tmp_path):
        result = composite_image(
            Path("/nonexistent_xyz_main.jpg"), ten_by_ten_overlay, tmp_path / "out.jpg"
        )

        assert result is False


class TestCompositeVideo:
    def test_ffmpeg_args_contain_required_flags(self, mocker, tmp_path):
        mock_run = mocker.patch(
            "snap_memories.composite.subprocess.run",
            return_value=mocker.MagicMock(returncode=0, stderr=""),
        )
        composite_video(
            tmp_path / "clip.mp4", tmp_path / "overlay.png", tmp_path / "out.mp4"
        )

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert any("overlay=0:0" in arg for arg in cmd)
        assert "libx264" in cmd

    def test_returncode_zero_returns_true(self, mocker, tmp_path):
        mocker.patch(
            "snap_memories.composite.subprocess.run",
            return_value=mocker.MagicMock(returncode=0, stderr=""),
        )
        result = composite_video(
            tmp_path / "clip.mp4", tmp_path / "overlay.png", tmp_path / "out.mp4"
        )

        assert result is True

    def test_returncode_nonzero_returns_false(self, mocker, tmp_path):
        mocker.patch(
            "snap_memories.composite.subprocess.run",
            return_value=mocker.MagicMock(returncode=1, stderr="ffmpeg error"),
        )
        result = composite_video(
            tmp_path / "clip.mp4", tmp_path / "overlay.png", tmp_path / "out.mp4"
        )

        assert result is False
