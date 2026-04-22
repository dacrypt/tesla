"""Tests for tesla_cli.core.planner.models."""

from __future__ import annotations

import pytest

from tesla_cli.core.planner.models import ChargerSuggestion, PlannedRoute


def _make_planned(stops=None) -> PlannedRoute:
    stops = stops if stops is not None else []
    return PlannedRoute(
        origin_address="Bogota",
        origin_latlon=(4.71, -74.07),
        destination_address="Medellin",
        destination_latlon=(6.24, -75.58),
        total_distance_km=415.0,
        total_duration_min=480,
        stops=stops,
        car_model="tesla:my:22:bt37:lr",
        initial_soc=0.8,
        abrp_deep_link="https://abetterrouteplanner.com/?x=y",
        planned_at="2026-04-22T12:00:00Z",
        routing_provider="osrm",
    )


def test_charger_suggestion_minimal_fields() -> None:
    c = ChargerSuggestion(
        ocm_id=42,
        name="Test SC",
        lat=5.0,
        lon=-74.0,
        network="tesla",
    )
    assert c.ocm_id == 42
    assert c.max_power_kw is None
    assert c.connection_types == []
    assert c.distance_from_route_km == 0.0
    assert c.interp_index == 0


def test_planned_route_json_roundtrip() -> None:
    stop = ChargerSuggestion(
        ocm_id=1,
        name="SC Honda",
        lat=5.2,
        lon=-74.7,
        operator="Tesla Motors Inc",
        network="tesla",
        max_power_kw=250.0,
        connection_types=["Tesla (Model S/X)"],
        distance_from_route_km=0.9,
        interp_index=1,
    )
    plan = _make_planned([stop])
    as_json = plan.model_dump_json()
    roundtrip = PlannedRoute.model_validate_json(as_json)
    assert roundtrip.total_distance_km == pytest.approx(415.0)
    assert len(roundtrip.stops) == 1
    assert roundtrip.stops[0].ocm_id == 1
    assert roundtrip.stops[0].max_power_kw == pytest.approx(250.0)
    assert roundtrip.car_model == "tesla:my:22:bt37:lr"


def test_to_nav_route_projects_stops_and_destination() -> None:
    stop = ChargerSuggestion(
        ocm_id=10,
        name="SC Medellin Nordeste",
        lat=6.0,
        lon=-75.4,
        network="tesla",
    )
    plan = _make_planned([stop])
    route = plan.to_nav_route("bog_med")
    assert route.name == "bog_med"
    assert route.source == "native-planner"
    assert route.source_id is not None
    assert "tesla:my:22:bt37:lr" in route.source_id
    # Waypoints: 1 stop + final dest
    assert len(route.waypoints) == 2
    assert route.waypoints[0].raw_address == "SC Medellin Nordeste"
    assert route.waypoints[0].geocode_provider == "openchargemap"
    assert route.waypoints[1].raw_address == "Medellin"
    assert route.waypoints[1].lat == pytest.approx(6.24)
    assert route.waypoints[1].geocode_provider == "native-planner"
    assert route.created_at == "2026-04-22T12:00:00Z"


def test_to_nav_route_with_zero_stops_just_destination() -> None:
    plan = _make_planned([])
    route = plan.to_nav_route("short")
    assert len(route.waypoints) == 1
    assert route.waypoints[0].raw_address == "Medellin"
