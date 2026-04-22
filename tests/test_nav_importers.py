"""Tests for tesla_cli.core.nav.importers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tesla_cli.core.nav.importers import (
    _check_file_size,
    _extract_latlon_from_url,
    detect_and_parse,
    parse_gpx,
    parse_kml,
    parse_takeout_csv,
    parse_takeout_geojson,
    slugify,
)
from tesla_cli.core.nav.route import NavStore

# ---------------------------------------------------------------------------
# 1. slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic(self):
        assert slugify("Coffee Shop", set()) == "coffee-shop"

    def test_accent_stripping(self):
        assert slugify("Casa de Mamí", set()) == "casa-de-mami"

    def test_accent_stripping_more(self):
        assert slugify("Café Zürich", set()) == "cafe-zurich"

    def test_collision_appends_suffix(self):
        existing = {"coffee-shop"}
        assert slugify("Coffee Shop", existing) == "coffee-shop-2"

    def test_collision_increments(self):
        existing = {"coffee-shop", "coffee-shop-2"}
        assert slugify("Coffee Shop", existing) == "coffee-shop-3"

    def test_truncation_to_32(self):
        title = "A" * 40
        result = slugify(title, set())
        assert len(result) == 32

    def test_truncated_collision_suffix(self):
        long_title = "a" * 40
        base = "a" * 32
        existing = {base}
        result = slugify(long_title, existing)
        # suffix "-2" is 2 chars, so base truncated to 30 + "-2"
        assert result == "a" * 30 + "-2"
        assert len(result) == 32

    def test_special_chars_become_dashes(self):
        assert slugify("Hello, World!", set()) == "hello-world"

    def test_empty_string_becomes_place(self):
        assert slugify("", set()) == "place"

    def test_whitespace_only_becomes_place(self):
        assert slugify("   ", set()) == "place"

    def test_exhaustion_raises(self):
        # "place" + all suffixes -2 through -99 = 98 suffixes
        existing = {"place"} | {f"place-{n}" for n in range(2, 100)}
        # also need the trimmed versions that would be generated
        # The base is "place" (5 chars). Suffix "-2" to "-99" all fit within 32 chars.
        with pytest.raises(ValueError, match="exhausted"):
            slugify("", existing)

    def test_no_leading_trailing_dashes(self):
        assert slugify("---hello---", set()) == "hello"

    def test_numbers_preserved(self):
        assert slugify("Route 66", set()) == "route-66"

    def test_unicode_cjk_not_stripped_into_nothing(self):
        # CJK chars don't decompose to ASCII — they become a dash run then stripped
        result = slugify("東京", set())
        # Non-ascii characters that don't decompose become empty after combining filter → "place"
        assert result == "place"


# ---------------------------------------------------------------------------
# 2. _extract_latlon_from_url
# ---------------------------------------------------------------------------


class TestExtractLatlonFromUrl:
    def test_at_pattern(self):
        url = "https://www.google.com/maps/place/Bogot%C3%A1/@4.6097,-74.0817,15z"
        assert _extract_latlon_from_url(url) == pytest.approx((4.6097, -74.0817))

    def test_q_pattern(self):
        url = "https://www.google.com/maps?q=4.6097,-74.0817"
        assert _extract_latlon_from_url(url) == pytest.approx((4.6097, -74.0817))

    def test_protobuf_pattern(self):
        url = "https://www.google.com/maps/place/Place/data=!3d4.6097!4d-74.0817"
        assert _extract_latlon_from_url(url) == pytest.approx((4.6097, -74.0817))

    def test_no_coords_returns_none(self):
        assert _extract_latlon_from_url("https://example.com") is None

    def test_empty_string_returns_none(self):
        assert _extract_latlon_from_url("") is None

    def test_negative_coords(self):
        url = "https://www.google.com/maps/@-33.8688,151.2093,14z"
        assert _extract_latlon_from_url(url) == pytest.approx((-33.8688, 151.2093))


# ---------------------------------------------------------------------------
# 3. parse_takeout_csv
# ---------------------------------------------------------------------------


CSV_CONTENT = """\
Title,Note,URL,Comment
Coffee Shop,,"https://www.google.com/maps/place/Coffee/@4.6097,-74.0817,15z",
The Other Place,,https://example.com/no-coords,
Coffee Shop,,"https://www.google.com/maps/place/CS2/@4.6100,-74.0820,15z",
"""


class TestParseTakeoutCsv:
    def test_basic_parse(self, tmp_path: Path):
        f = tmp_path / "Want to go.csv"
        f.write_text(CSV_CONTENT, encoding="utf-8")

        places = parse_takeout_csv(f)
        assert len(places) == 3

    def test_tags_from_filename(self, tmp_path: Path):
        f = tmp_path / "Want to go.csv"
        f.write_text(CSV_CONTENT, encoding="utf-8")

        places = parse_takeout_csv(f)
        for p in places:
            assert p.tags == ["Want to go"]

    def test_explicit_list_name(self, tmp_path: Path):
        f = tmp_path / "saved.csv"
        f.write_text(CSV_CONTENT, encoding="utf-8")

        places = parse_takeout_csv(f, list_name="Favorites")
        for p in places:
            assert p.tags == ["Favorites"]

    def test_latlon_extracted(self, tmp_path: Path):
        f = tmp_path / "places.csv"
        f.write_text(CSV_CONTENT, encoding="utf-8")

        places = parse_takeout_csv(f)
        first = places[0]
        assert first.lat == pytest.approx(4.6097)
        assert first.lon == pytest.approx(-74.0817)

    def test_no_url_lat_lon_is_none(self, tmp_path: Path):
        f = tmp_path / "places.csv"
        f.write_text(CSV_CONTENT, encoding="utf-8")

        places = parse_takeout_csv(f)
        second = places[1]  # "The Other Place" has example.com URL → no coords
        assert second.lat is None
        assert second.lon is None

    def test_stderr_warning_for_no_coords(self, tmp_path: Path, capsys):
        f = tmp_path / "places.csv"
        f.write_text(CSV_CONTENT, encoding="utf-8")

        parse_takeout_csv(f)
        captured = capsys.readouterr()
        assert "The Other Place" in captured.err
        assert "will need geocoding" in captured.err

    def test_duplicate_title_collision_suffix(self, tmp_path: Path):
        f = tmp_path / "places.csv"
        f.write_text(CSV_CONTENT, encoding="utf-8")

        places = parse_takeout_csv(f)
        aliases = [p.alias for p in places]
        assert aliases[0] == "coffee-shop"
        assert aliases[2] == "coffee-shop-2"

    def test_source_fields(self, tmp_path: Path):
        f = tmp_path / "places.csv"
        f.write_text(CSV_CONTENT, encoding="utf-8")

        places = parse_takeout_csv(f)
        for p in places:
            assert p.source == "google-takeout-csv"
            assert p.source_id is not None

    def test_source_id_is_url_when_present(self, tmp_path: Path):
        f = tmp_path / "places.csv"
        f.write_text(CSV_CONTENT, encoding="utf-8")

        places = parse_takeout_csv(f)
        assert places[0].source_id == "https://www.google.com/maps/place/Coffee/@4.6097,-74.0817,15z"

    def test_source_id_fallback_no_url(self, tmp_path: Path):
        content = "Title,Note,URL,Comment\nNoURL,,,\n"
        f = tmp_path / "places.csv"
        f.write_text(content, encoding="utf-8")

        places = parse_takeout_csv(f)
        assert places[0].source_id == f"csv:NoURL:{f.name}"


# ---------------------------------------------------------------------------
# 4. parse_takeout_geojson
# ---------------------------------------------------------------------------


GEOJSON_CONTENT = """\
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "Title": "Parque Nacional",
        "Google Maps URL": "https://www.google.com/maps/@4.6097,-74.0817,15z",
        "Location": {"Address": "Cra. 7 #36-61, Bogotá"}
      },
      "geometry": {"type": "Point", "coordinates": [-74.0817, 4.6097]}
    },
    {
      "type": "Feature",
      "properties": {
        "Title": "Airport",
        "Location": {"Address": "El Dorado, Bogotá"}
      },
      "geometry": {"type": "Point", "coordinates": [-74.1469, 4.7016]}
    }
  ]
}
"""

GEOJSON_EMPTY = '{"type": "FeatureCollection", "features": []}'


class TestParseTakeoutGeojson:
    def test_basic_parse(self, tmp_path: Path):
        f = tmp_path / "saved.geojson"
        f.write_text(GEOJSON_CONTENT, encoding="utf-8")

        places = parse_takeout_geojson(f)
        assert len(places) == 2

    def test_geojson_lon_lat_convention(self, tmp_path: Path):
        f = tmp_path / "saved.geojson"
        f.write_text(GEOJSON_CONTENT, encoding="utf-8")

        places = parse_takeout_geojson(f)
        first = places[0]
        # GeoJSON coordinates = [lon, lat] → Place.lat/lon must be swapped
        assert first.lat == pytest.approx(4.6097)
        assert first.lon == pytest.approx(-74.0817)

    def test_second_feature_coords(self, tmp_path: Path):
        f = tmp_path / "saved.geojson"
        f.write_text(GEOJSON_CONTENT, encoding="utf-8")

        places = parse_takeout_geojson(f)
        second = places[1]
        assert second.lat == pytest.approx(4.7016)
        assert second.lon == pytest.approx(-74.1469)

    def test_address_from_location_dict(self, tmp_path: Path):
        f = tmp_path / "saved.geojson"
        f.write_text(GEOJSON_CONTENT, encoding="utf-8")

        places = parse_takeout_geojson(f)
        assert places[0].raw_address == "Cra. 7 #36-61, Bogotá"

    def test_empty_feature_collection(self, tmp_path: Path):
        f = tmp_path / "empty.geojson"
        f.write_text(GEOJSON_EMPTY, encoding="utf-8")

        places = parse_takeout_geojson(f)
        assert places == []

    def test_source_field(self, tmp_path: Path):
        f = tmp_path / "saved.geojson"
        f.write_text(GEOJSON_CONTENT, encoding="utf-8")

        places = parse_takeout_geojson(f)
        for p in places:
            assert p.source == "google-takeout-geojson"


# ---------------------------------------------------------------------------
# 5. parse_kml
# ---------------------------------------------------------------------------


KML_CONTENT = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark id="place-001">
      <name>Monserrate</name>
      <Point>
        <coordinates>-74.0557,4.6048,3152</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>Plaza Bolívar</name>
      <Point>
        <coordinates>-74.0761,4.5981,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""


class TestParseKml:
    def test_basic_parse(self, tmp_path: Path):
        f = tmp_path / "favorites.kml"
        f.write_text(KML_CONTENT, encoding="utf-8")

        places = parse_kml(f)
        assert len(places) == 2

    def test_names(self, tmp_path: Path):
        f = tmp_path / "favorites.kml"
        f.write_text(KML_CONTENT, encoding="utf-8")

        places = parse_kml(f)
        assert places[0].raw_address == "Monserrate"
        assert places[1].raw_address == "Plaza Bolívar"

    def test_coords(self, tmp_path: Path):
        f = tmp_path / "favorites.kml"
        f.write_text(KML_CONTENT, encoding="utf-8")

        places = parse_kml(f)
        assert places[0].lat == pytest.approx(4.6048)
        assert places[0].lon == pytest.approx(-74.0557)
        assert places[1].lat == pytest.approx(4.5981)
        assert places[1].lon == pytest.approx(-74.0761)

    def test_source_id_from_placemark_id_attr(self, tmp_path: Path):
        f = tmp_path / "favorites.kml"
        f.write_text(KML_CONTENT, encoding="utf-8")

        places = parse_kml(f)
        assert places[0].source_id == "place-001"

    def test_source_id_hashed_when_no_id_attr(self, tmp_path: Path):
        f = tmp_path / "favorites.kml"
        f.write_text(KML_CONTENT, encoding="utf-8")

        places = parse_kml(f)
        # Second Placemark has no id attr → hashed
        assert places[1].source_id is not None
        assert len(places[1].source_id) == 16  # sha1[:16]

    def test_source_field(self, tmp_path: Path):
        f = tmp_path / "favorites.kml"
        f.write_text(KML_CONTENT, encoding="utf-8")

        places = parse_kml(f)
        for p in places:
            assert p.source == "kml"


# ---------------------------------------------------------------------------
# 6. parse_gpx
# ---------------------------------------------------------------------------


GPX_CONTENT = """\
<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="4.6097" lon="-74.0817">
    <name>Bogotá Center</name>
  </wpt>
  <wpt lat="-33.8688" lon="151.2093">
    <name>Sydney Opera House</name>
  </wpt>
</gpx>
"""


class TestParseGpx:
    def test_basic_parse(self, tmp_path: Path):
        f = tmp_path / "waypoints.gpx"
        f.write_text(GPX_CONTENT, encoding="utf-8")

        places = parse_gpx(f)
        assert len(places) == 2

    def test_names(self, tmp_path: Path):
        f = tmp_path / "waypoints.gpx"
        f.write_text(GPX_CONTENT, encoding="utf-8")

        places = parse_gpx(f)
        assert places[0].raw_address == "Bogotá Center"
        assert places[1].raw_address == "Sydney Opera House"

    def test_coords(self, tmp_path: Path):
        f = tmp_path / "waypoints.gpx"
        f.write_text(GPX_CONTENT, encoding="utf-8")

        places = parse_gpx(f)
        assert places[0].lat == pytest.approx(4.6097)
        assert places[0].lon == pytest.approx(-74.0817)
        assert places[1].lat == pytest.approx(-33.8688)
        assert places[1].lon == pytest.approx(151.2093)

    def test_source_id_is_sha1_prefix(self, tmp_path: Path):
        f = tmp_path / "waypoints.gpx"
        f.write_text(GPX_CONTENT, encoding="utf-8")

        places = parse_gpx(f)
        for p in places:
            assert p.source_id is not None
            assert len(p.source_id) == 16

    def test_source_field(self, tmp_path: Path):
        f = tmp_path / "waypoints.gpx"
        f.write_text(GPX_CONTENT, encoding="utf-8")

        places = parse_gpx(f)
        for p in places:
            assert p.source == "gpx"


# ---------------------------------------------------------------------------
# 7. detect_and_parse
# ---------------------------------------------------------------------------


class TestDetectAndParse:
    def test_csv_routes_to_csv_parser(self, tmp_path: Path, monkeypatch):
        called = []

        def fake_csv(path, list_name=None):
            called.append(("csv", path, list_name))
            return []

        monkeypatch.setattr("tesla_cli.core.nav.importers.parse_takeout_csv", fake_csv)
        detect_and_parse(tmp_path / "places.csv", "MyList")
        assert called == [("csv", tmp_path / "places.csv", "MyList")]

    def test_json_routes_to_geojson_parser(self, tmp_path: Path, monkeypatch):
        called = []

        def fake_geo(path):
            called.append(("geo", path))
            return []

        monkeypatch.setattr("tesla_cli.core.nav.importers.parse_takeout_geojson", fake_geo)
        detect_and_parse(tmp_path / "saved.json")
        assert called == [("geo", tmp_path / "saved.json")]

    def test_geojson_routes_to_geojson_parser(self, tmp_path: Path, monkeypatch):
        called = []

        def fake_geo(path):
            called.append(("geo", path))
            return []

        monkeypatch.setattr("tesla_cli.core.nav.importers.parse_takeout_geojson", fake_geo)
        detect_and_parse(tmp_path / "saved.geojson")
        assert called == [("geo", tmp_path / "saved.geojson")]

    def test_kml_routes_to_kml_parser(self, tmp_path: Path, monkeypatch):
        called = []

        def fake_kml(path):
            called.append(("kml", path))
            return []

        monkeypatch.setattr("tesla_cli.core.nav.importers.parse_kml", fake_kml)
        detect_and_parse(tmp_path / "places.kml")
        assert called == [("kml", tmp_path / "places.kml")]

    def test_gpx_routes_to_gpx_parser(self, tmp_path: Path, monkeypatch):
        called = []

        def fake_gpx(path):
            called.append(("gpx", path))
            return []

        monkeypatch.setattr("tesla_cli.core.nav.importers.parse_gpx", fake_gpx)
        detect_and_parse(tmp_path / "track.gpx")
        assert called == [("gpx", tmp_path / "track.gpx")]

    def test_unsupported_extension_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="unsupported extension"):
            detect_and_parse(tmp_path / "data.xlsx")


# ---------------------------------------------------------------------------
# 8. _check_file_size
# ---------------------------------------------------------------------------


class TestCheckFileSize:
    def test_small_file_passes(self, tmp_path: Path):
        f = tmp_path / "small.txt"
        f.write_text("hello")
        _check_file_size(f)  # must not raise

    def test_large_file_raises(self, tmp_path: Path, monkeypatch):
        f = tmp_path / "big.bin"
        f.write_text("x")

        # Monkeypatch Path.stat to fake 26 MB

        fake_stat = os.stat_result((0o644, 0, 0, 1, 0, 0, 26 * 1024 * 1024 + 1, 0, 0, 0))

        original_stat = Path.stat

        def patched_stat(self, *args, **kwargs):
            if self == f:
                return fake_stat
            return original_stat(self, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", patched_stat)

        with pytest.raises(ValueError, match="file too large"):
            _check_file_size(f)

    def test_exact_limit_passes(self, tmp_path: Path, monkeypatch):
        f = tmp_path / "exact.bin"
        f.write_text("x")


        exact_stat = os.stat_result((0o644, 0, 0, 1, 0, 0, 25 * 1024 * 1024, 0, 0, 0))

        original_stat = Path.stat

        def patched_stat(self, *args, **kwargs):
            if self == f:
                return exact_stat
            return original_stat(self, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", patched_stat)

        _check_file_size(f)  # exactly at cap — must not raise


# ---------------------------------------------------------------------------
# 9. Integration smoke: KML → NavStore round-trip
# ---------------------------------------------------------------------------


class TestKmlNavStoreRoundTrip:
    def test_bulk_import_then_reimport(self, tmp_path: Path):
        kml_file = tmp_path / "favorites.kml"
        kml_file.write_text(KML_CONTENT, encoding="utf-8")

        nav_file = tmp_path / "nav.toml"
        state_file = tmp_path / "nav.state.toml"
        store = NavStore(nav_file=nav_file, state_file=state_file)

        places = parse_kml(kml_file)
        n = len(places)
        assert n == 2

        # First import
        result = store.save_places_bulk(places)
        assert result == (n, 0, 0), f"Expected ({n}, 0, 0) on first import, got {result}"

        # Re-import same data → all updated, none newly imported
        places2 = parse_kml(kml_file)
        result2 = store.save_places_bulk(places2)
        assert result2 == (0, n, 0), f"Expected (0, {n}, 0) on re-import, got {result2}"
