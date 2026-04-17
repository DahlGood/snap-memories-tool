import os
from concurrent.futures import Future

from snap_memories.gps import _to_rational
from snap_memories.metadata import _extract_mid, _parse_location
from snap_memories.processing import ProcessConfig, process


class TestParseLocation:
    def test_valid_coordinates(self):
        result = _parse_location("Latitude, Longitude: 33.981457, -6.893662")
        assert result == (33.981457, -6.893662)

    def test_zero_coordinates_returns_none(self):
        assert _parse_location("Latitude, Longitude: 0.0, 0.0") is None

    def test_malformed_string_returns_none(self):
        assert _parse_location("no coordinates here") is None

    def test_empty_string_returns_none(self):
        assert _parse_location("") is None

    def test_negative_latitude(self):
        result = _parse_location("Latitude, Longitude: -33.8688, 151.2093")
        assert result == (-33.8688, 151.2093)


class TestExtractMid:
    VALID_URL = (
        "https://app.snapchat.com/dmd/memories"
        "?uid=37fb2e6d&sid=F787F2BD-54EB-4CD1-A116-06F884A7B3A2"
        "&mid=f787f2bd-54eb-4cd1-a116-06f884a7b3a2&ts=123"
    )

    def test_extracts_mid_uppercased(self):
        result = _extract_mid(self.VALID_URL)
        assert result == "F787F2BD-54EB-4CD1-A116-06F884A7B3A2"

    def test_missing_mid_returns_none(self):
        assert _extract_mid("https://app.snapchat.com/dmd/memories?uid=abc") is None

    def test_empty_string_returns_none(self):
        assert _extract_mid("") is None

    def test_malformed_url_returns_none(self):
        assert _extract_mid("not a url") is None

    def test_urlparse_exception_returns_none(self, mocker):
        # Force an exception inside the try block to exercise the except branch
        mocker.patch("snap_memories.metadata.urlparse", side_effect=RuntimeError("boom"))
        assert _extract_mid("https://example.com?mid=abc") is None


class TestToRational:
    def test_whole_degrees(self):
        deg, mins, secs = _to_rational(45.0)
        assert deg == (45, 1)
        assert mins == (0, 1)
        assert secs == (0, 10000)

    def test_known_conversion(self):
        # 33.981457° = 33° 58' 53.2452"
        deg, mins, secs = _to_rational(33.981457)
        assert deg == (33, 1)
        assert mins == (58, 1)
        # seconds should be close to 53.2452 * 10000 = 532452
        sec_value = secs[0] / secs[1]
        assert abs(sec_value - 53.2452) < 0.01

    def test_negative_treated_as_absolute(self):
        # _to_rational always works on abs(value); ref (N/S/E/W) is set by caller
        pos = _to_rational(6.893662)
        neg = _to_rational(-6.893662)
        assert pos == neg


UUID = "F787F2BD-54EB-4CD1-A116-06F884A7B3A2"


def _resolved_future(result):
    f = Future()
    f.set_result(result)
    return f


class TestProcessConfig:
    def test_defaults_use_cpu_count(self):
        config = ProcessConfig(
            memories_dir=None, json_path=None, output_dir=None
        )
        assert config.workers == (os.cpu_count() or 4)
        assert config.video_workers == max(2, (os.cpu_count() or 4) // 4)

    def test_custom_values_stored(self, tmp_path):
        config = ProcessConfig(
            memories_dir=tmp_path / "memories",
            json_path=tmp_path / "meta.json",
            output_dir=tmp_path / "out",
            limit=10,
            workers=2,
            video_workers=1,
        )
        assert config.limit == 10
        assert config.workers == 2
        assert config.video_workers == 1


class TestProcess:
    def _make_mock_pool(self, mocker):
        pool = mocker.MagicMock()
        pool.__enter__ = mocker.MagicMock(return_value=pool)
        pool.__exit__ = mocker.MagicMock(return_value=False)
        return pool

    def _setup(self, mocker, tmp_path, file_names, metadata=None):
        memories_dir = tmp_path / "memories"
        memories_dir.mkdir()
        json_path = tmp_path / "meta.json"
        json_path.write_text('{"Saved Media": []}', encoding="utf-8")
        output_dir = tmp_path / "output"

        for name in file_names:
            (memories_dir / name).touch()

        mocker.patch(
            "snap_memories.processing.build_metadata_index",
            return_value=metadata or {},
        )

        return ProcessConfig(
            memories_dir=memories_dir,
            json_path=json_path,
            output_dir=output_dir,
            workers=1,
            video_workers=1,
        ), output_dir

    def test_empty_directory_returns_zero_counts(self, mocker, tmp_path):
        config, output_dir = self._setup(mocker, tmp_path, [])
        result = process(config)
        assert result == {"total": 0, "geotagged": 0, "composited": 0, "no_meta": 0}
        assert output_dir.exists()

    def test_returns_correct_summary(self, mocker, tmp_path):
        names = [
            f"2024-01-15_{UUID.lower()}-main.jpg",
            f"2024-01-15_{UUID.lower()}-main.mp4",
        ]
        config, _ = self._setup(mocker, tmp_path, names)

        mock_pool = self._make_mock_pool(mocker)
        mock_pool.submit.side_effect = lambda fn, *a, **kw: _resolved_future((True, True, False))
        mocker.patch("snap_memories.processing.ProcessPoolExecutor", return_value=mock_pool)
        mocker.patch(
            "snap_memories.processing.as_completed",
            side_effect=lambda d: iter(d.keys()),
        )

        result = process(config)

        assert result["total"] == 2
        assert result["geotagged"] == 2
        assert result["composited"] == 2
        assert result["no_meta"] == 0

    def test_on_progress_called_once_per_file(self, mocker, tmp_path):
        names = [
            f"2024-01-15_{UUID.lower()}-main.jpg",
            f"2024-01-16_{UUID.lower()}-main.jpg",
        ]
        config, _ = self._setup(mocker, tmp_path, names)

        mock_pool = self._make_mock_pool(mocker)
        mock_pool.submit.side_effect = lambda fn, *a, **kw: _resolved_future((False, False, True))
        mocker.patch("snap_memories.processing.ProcessPoolExecutor", return_value=mock_pool)
        mocker.patch(
            "snap_memories.processing.as_completed",
            side_effect=lambda d: iter(d.keys()),
        )

        calls = []
        process(config, on_progress=lambda *args: calls.append(args))

        assert len(calls) == 2
        # completed increments each call; total stays at 2
        assert calls[0][0] == 1 and calls[0][1] == 2
        assert calls[1][0] == 2 and calls[1][1] == 2

    def test_limit_restricts_files_processed(self, mocker, tmp_path):
        names = [
            f"2024-01-15_{UUID.lower()}-main.jpg",
            f"2024-01-16_{UUID.lower()}-main.jpg",
            f"2024-01-17_{UUID.lower()}-main.jpg",
        ]
        config, _ = self._setup(mocker, tmp_path, names)
        config.limit = 1

        mock_pool = self._make_mock_pool(mocker)
        mock_pool.submit.side_effect = lambda fn, *a, **kw: _resolved_future((False, False, True))
        mocker.patch("snap_memories.processing.ProcessPoolExecutor", return_value=mock_pool)
        mocker.patch(
            "snap_memories.processing.as_completed",
            side_effect=lambda d: iter(d.keys()),
        )

        result = process(config)

        assert result["total"] == 1
        assert mock_pool.submit.call_count == 1

    def test_no_progress_callback_runs_without_error(self, mocker, tmp_path):
        names = [f"2024-01-15_{UUID.lower()}-main.jpg"]
        config, _ = self._setup(mocker, tmp_path, names)

        mock_pool = self._make_mock_pool(mocker)
        mock_pool.submit.side_effect = lambda fn, *a, **kw: _resolved_future((True, False, False))
        mocker.patch("snap_memories.processing.ProcessPoolExecutor", return_value=mock_pool)
        mocker.patch(
            "snap_memories.processing.as_completed",
            side_effect=lambda d: iter(d.keys()),
        )

        result = process(config)  # no on_progress — must not raise
        assert result["total"] == 1
