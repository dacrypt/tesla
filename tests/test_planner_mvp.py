"""Tests for tesla_cli.core.planner.mvp."""

from __future__ import annotations

import pytest

from tesla_cli.core.planner.models import ChargerSuggestion
from tesla_cli.core.planner.mvp import (
    _haversine_km,
    _interp_points,
    build_abrp_link,
    plan_route,
)


class _StubEngine:
    name = "stub"

    def __init__(self, polyline, total_km=300.0, total_min=180):
        self._polyline = polyline
        self._km = total_km
        self._min = total_min

    def compute_route(self, origin, destination):
        return {
            "polyline": self._polyline,
            "total_distance_km": self._km,
            "total_duration_min": self._min,
        }


def test_haversine_bogota_to_medellin_approx_230_to_270() -> None:
    # Great-circle distance Bogota (4.71, -74.07) -> Medellin (6.24, -75.58) ~ 245 km
    d = _haversine_km((4.71, -74.07), (6.24, -75.58))
    assert 230.0 < d < 270.0


def test_interp_points_short_route_returns_empty() -> None:
    poly = [(0.0, 0.0), (0.0, 0.5)]  # ~55 km
    assert _interp_points(poly, every_km=150.0) == []


def test_interp_points_exact_300km_every_150_returns_one_point() -> None:
    # Use a longitude line; 1 deg lat ~ 111 km. 2.6 deg -> ~289 km
    poly = [(0.0, 0.0), (2.6, 0.0)]  # ~289 km: only the 150km interp fits
    pts = _interp_points(poly, every_km=150.0)
    assert len(pts) == 1
    # 150/289 ~= 0.519 of 2.6 deg ~= 1.348 deg
    assert pts[0][0] == pytest.approx(1.35, rel=0.05)
    assert pts[0][1] == pytest.approx(0.0, abs=1e-6)


def test_build_abrp_link_with_car_and_soc_has_initial_soc_percent() -> None:
    url = build_abrp_link(
        (4.71, -74.07),
        (6.24, -75.58),
        car_model="tesla:my:22:bt37:lr",
        initial_soc=0.8,
    )
    assert url is not None
    assert "initial_soc=80" in url
    assert "car_model=tesla%3A" in url  # colons URL-encoded
    assert "from_lat=4.710000" in url
    assert url.startswith("https://abetterrouteplanner.com/?")


def test_build_abrp_link_no_car_returns_none() -> None:
    assert build_abrp_link((0, 0), (1, 1), car_model=None, initial_soc=0.5) is None


def test_plan_route_basic_produces_one_stop_and_abrp_link() -> None:
    # ~289 km route along lat axis: triggers exactly 1 interp point at 150km
    polyline = [(0.0, 0.0), (2.6, 0.0)]
    engine = _StubEngine(polyline, total_km=289.0, total_min=180)

    def finder(lat, lon):
        return [
            ChargerSuggestion(
                ocm_id=1,
                name="SC Middle",
                lat=lat,
                lon=lon,
                network="tesla",
                max_power_kw=250.0,
            )
        ]

    plan = plan_route(
        origin_address="A",
        origin_latlon=(0.0, 0.0),
        destination_address="B",
        destination_latlon=(2.6, 0.0),
        routing=engine,
        charger_finder=finder,
        stops_every_km=150.0,
        car_model_alias="model_y_lr",
        initial_soc=0.8,
        emit_abrp_link=True,
    )
    assert plan.total_distance_km == pytest.approx(289.0)
    assert plan.total_duration_min == 180
    assert len(plan.stops) == 1
    assert plan.stops[0].interp_index == 1
    assert plan.abrp_deep_link is not None
    # URL-encoded colons: tesla%3Amy%3A22%3Abt37%3Alr
    assert "tesla%3Amy%3A22%3Abt37%3Alr" in plan.abrp_deep_link
    assert plan.routing_provider == "stub"
    assert plan.car_model == "tesla:my:22:bt37:lr"


def test_plan_route_no_abrp_link_when_disabled() -> None:
    polyline = [(0.0, 0.0), (2.6, 0.0)]
    engine = _StubEngine(polyline)

    def finder(lat, lon):
        return []

    plan = plan_route(
        origin_address="A",
        origin_latlon=(0.0, 0.0),
        destination_address="B",
        destination_latlon=(2.6, 0.0),
        routing=engine,
        charger_finder=finder,
        emit_abrp_link=False,
        car_model_alias="model_y_lr",
    )
    assert plan.abrp_deep_link is None


def test_plan_route_deduplicates_same_ocm_id_across_interps() -> None:
    # Longer route to force 2 interps
    polyline = [(0.0, 0.0), (4.0, 0.0)]  # ~444 km, 2 interps at 150 and 300
    engine = _StubEngine(polyline, total_km=444.0, total_min=300)

    def finder(lat, lon):
        # Always returns the same charger by id
        return [
            ChargerSuggestion(
                ocm_id=7,
                name="Dup",
                lat=lat,
                lon=lon,
                network="tesla",
            )
        ]

    plan = plan_route(
        origin_address="A",
        origin_latlon=(0.0, 0.0),
        destination_address="B",
        destination_latlon=(4.0, 0.0),
        routing=engine,
        charger_finder=finder,
        stops_every_km=150.0,
        emit_abrp_link=False,
    )
    assert len(plan.stops) == 1
    assert plan.stops[0].ocm_id == 7
