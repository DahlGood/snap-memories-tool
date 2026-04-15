"""Shared fixtures for snap-memories-tool tests."""

import json

import pytest
from PIL import Image


@pytest.fixture
def tiny_jpeg(tmp_path):
    """1×1 RGB JPEG for GPS round-trip tests."""
    p = tmp_path / "test.jpg"
    Image.new("RGB", (1, 1), color=(200, 100, 50)).save(str(p), "JPEG")
    return p


@pytest.fixture
def ten_by_ten_jpeg(tmp_path):
    """10×10 RGB JPEG for composite tests."""
    p = tmp_path / "main.jpg"
    Image.new("RGB", (10, 10), color=(100, 150, 200)).save(str(p), "JPEG")
    return p


@pytest.fixture
def ten_by_ten_overlay(tmp_path):
    """10×10 semi-transparent RGBA PNG for composite tests."""
    p = tmp_path / "overlay.png"
    Image.new("RGBA", (10, 10), color=(0, 255, 0, 128)).save(str(p), "PNG")
    return p


@pytest.fixture
def five_by_five_overlay(tmp_path):
    """5×5 RGBA PNG — smaller than the main image, to test resize path."""
    p = tmp_path / "overlay5.png"
    Image.new("RGBA", (5, 5), color=(255, 0, 0, 100)).save(str(p), "PNG")
    return p


@pytest.fixture
def write_memories_json(tmp_path):
    """Factory that writes a memories_history.json with the given records list."""

    def _write(records):
        p = tmp_path / "memories.json"
        p.write_text(json.dumps({"Saved Media": records}), encoding="utf-8")
        return p

    return _write
