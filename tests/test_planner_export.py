"""Tests for tesla_cli.core.planner.export (GPX + KML serialization)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from tesla_cli.core.planner.export import to_gpx, to_kml
from tesla_cli.core.planner.models import ChargerSuggestion, PlannedRoute


def _make_plan() -> PlannedRoute:
    stops = [
        ChargerSuggestion(
            ocm_id=101,
            name="Tesla SC — Honda",
            lat=5.20,
            lon=-74.70,
            network="tesla",
            max_power_kw=250.0,
            arrival_soc_kwh=22.5,
            departure_soc_kwh=60.0,
            charge_duration_min=15,
        ),
        ChargerSuggestion(
            ocm_id=102,
            name='Terpel <Andrés & Co>',  # special chars for escaping
            lat=5.85,
            lon=-75.10,
            network="ccs",
            max_power_kw=120.0,
        ),
    ]
    return PlannedRoute(
        origin_address="Bogotá",
        origin_latlon=(4.7110, -74.0721),
        destination_address="Medellín",
        destination_latlon=(6.2442, -75.5812),
        total_distance_km=414.0,
        total_duration_min=360,
        stops=stops,
        planned_at="2026-04-22T03:00:00Z",
        routing_provider="openroute",
    )


def test_to_gpx_is_valid_xml_with_wpts_and_rte() -> None:
    plan = _make_plan()
    body = to_gpx(plan)
    root = ET.fromstring(body)
    ns = {"g": "http://www.topografix.com/GPX/1/1"}
    wpts = root.findall("g:wpt", ns)
    # origin + 2 stops + destination = 4
    assert len(wpts) == 4
    rte = root.find("g:rte", ns)
    assert rte is not None
    rtepts = rte.findall("g:rtept", ns)
    assert len(rtepts) == 4


def test_to_gpx_escapes_special_chars() -> None:
    plan = _make_plan()
    body = to_gpx(plan)
    # The ampersand in the charger name must be escaped in the raw payload
    assert "&amp;" in body
    assert "<Andrés" not in body  # should be escaped
    assert "&lt;Andrés" in body
    # And the document should still parse
    ET.fromstring(body)


def test_to_gpx_waypoint_coords_match_plan() -> None:
    plan = _make_plan()
    body = to_gpx(plan)
    root = ET.fromstring(body)
    ns = {"g": "http://www.topografix.com/GPX/1/1"}
    wpts = root.findall("g:wpt", ns)
    # First waypoint is origin
    assert float(wpts[0].attrib["lat"]) == 4.711000
    assert float(wpts[0].attrib["lon"]) == -74.072100
    # Last waypoint is destination
    assert float(wpts[-1].attrib["lat"]) == 6.244200


def test_to_kml_is_valid_xml_with_placemarks_and_linestring() -> None:
    plan = _make_plan()
    body = to_kml(plan)
    root = ET.fromstring(body)
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    doc = root.find("k:Document", ns)
    assert doc is not None
    placemarks = doc.findall("k:Placemark", ns)
    # origin + 2 stops + destination + linestring = 5
    assert len(placemarks) == 5
    # Last placemark should have a LineString
    ls = placemarks[-1].find("k:LineString", ns)
    assert ls is not None
    coords = ls.find("k:coordinates", ns)
    assert coords is not None and coords.text is not None
    # 4 coordinate tuples separated by spaces
    assert len(coords.text.split()) == 4


def test_to_kml_coordinates_use_lon_lat_order() -> None:
    plan = _make_plan()
    body = to_kml(plan)
    root = ET.fromstring(body)
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    doc = root.find("k:Document", ns)
    placemark = doc.findall("k:Placemark", ns)[0]
    pt = placemark.find("k:Point", ns)
    coords = pt.find("k:coordinates", ns)
    # KML uses lon,lat,alt — origin = (4.71, -74.07), so lon=-74.07 first
    parts = coords.text.strip().split(",")
    assert float(parts[0]) == -74.072100
    assert float(parts[1]) == 4.711000


def test_to_gpx_includes_soc_description_for_stops() -> None:
    plan = _make_plan()
    body = to_gpx(plan)
    # First stop has SoC + charge duration set
    assert "arrival SoC: 22.5 kWh" in body
    assert "charge: 15 min" in body


def test_to_kml_escapes_special_chars() -> None:
    plan = _make_plan()
    body = to_kml(plan)
    assert "&amp;" in body
    ET.fromstring(body)  # parses
