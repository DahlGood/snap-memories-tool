"""Tests for snap_memories.metadata.build_metadata_index."""

import pytest

from snap_memories.metadata import build_metadata_index

UUID = "F787F2BD-54EB-4CD1-A116-06F884A7B3A2"
UUID2 = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def _make_record(uuid=UUID, location="Latitude, Longitude: 33.98, -6.89"):
    """Helper: build a minimal valid Saved Media record."""
    return {
        "Download Link": (
            f"https://app.snapchat.com/dmd/memories"
            f"?uid=abc&mid={uuid.lower()}&ts=1"
        ),
        "Date": "2024-01-15 12:00:00 UTC",
        "Media Type": "IMAGE",
        "Location": location,
    }


class TestBuildMetadataIndex:
    def test_valid_record_with_gps_has_lat_lon(self, write_memories_json):
        path = write_memories_json([_make_record()])
        index = build_metadata_index(path)

        assert UUID in index
        assert index[UUID]["lat"] == pytest.approx(33.98)
        assert index[UUID]["lon"] == pytest.approx(-6.89)

    def test_zero_zero_coords_entry_exists_but_has_no_lat_lon(self, write_memories_json):
        path = write_memories_json([_make_record(location="Latitude, Longitude: 0.0, 0.0")])
        index = build_metadata_index(path)

        assert UUID in index
        assert "lat" not in index[UUID]
        assert "lon" not in index[UUID]

    def test_missing_download_link_record_is_skipped(self, write_memories_json):
        record = {
            "Date": "2024-01-15",
            "Media Type": "IMAGE",
            "Location": "Latitude, Longitude: 1.0, 2.0",
        }
        path = write_memories_json([record])
        index = build_metadata_index(path)

        assert len(index) == 0

    def test_missing_location_entry_has_no_lat_lon(self, write_memories_json):
        record = {
            "Download Link": (
                f"https://app.snapchat.com/dmd/memories?uid=abc&mid={UUID.lower()}&ts=1"
            ),
            "Date": "2024-01-15",
            "Media Type": "IMAGE",
        }
        path = write_memories_json([record])
        index = build_metadata_index(path)

        assert UUID in index
        assert "lat" not in index[UUID]
        assert "lon" not in index[UUID]

    def test_empty_saved_media_returns_empty_dict(self, write_memories_json):
        path = write_memories_json([])
        assert build_metadata_index(path) == {}

    def test_multiple_mixed_records_all_indexed_correctly(self, write_memories_json):
        records = [
            _make_record(UUID),  # valid GPS
            _make_record(UUID2, location="Latitude, Longitude: 0.0, 0.0"),  # 0,0 → no GPS
            {  # no Download Link → skipped entirely
                "Date": "2024-01-17",
                "Media Type": "IMAGE",
                "Location": "Latitude, Longitude: 5.0, 5.0",
            },
        ]
        path = write_memories_json(records)
        index = build_metadata_index(path)

        assert set(index.keys()) == {UUID, UUID2}
        assert "lat" in index[UUID]
        assert "lat" not in index[UUID2]
