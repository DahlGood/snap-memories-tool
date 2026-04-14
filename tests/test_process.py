from snap_memories.gps import _to_rational
from snap_memories.metadata import _extract_mid, _parse_location


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
