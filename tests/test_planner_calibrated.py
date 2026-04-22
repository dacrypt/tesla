"""Tests for tesla_cli.core.planner.calibrated (SoC-aware planner)."""

from __future__ import annotations

import pytest

from tesla_cli.core.planner.calibrated import plan_with_soc
from tesla_cli.core.planner.consumption import BASELINES
from tesla_cli.core.planner.models import ChargerSuggestion


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


def _one_charger(lat, lon):
    return [
        ChargerSuggestion(
            ocm_id=42 + int(lat * 100),
            name=f"SC ({lat:.2f},{lon:.2f})",
            lat=lat,
            lon=lon,
            network="tesla",
            max_power_kw=250.0,
        )
    ]


def test_plan_with_soc_tracks_energy_and_arrival_soc() -> None:
    # ~444 km, 2 interps at 150 and 300 km
    polyline = [(0.0, 0.0), (4.0, 0.0)]
    engine = _StubEngine(polyline, total_km=444.0, total_min=300)

    def finder(lat, lon):
        return _one_charger(lat, lon)

    m = BASELINES["tesla:my:22:bt37:lr"]
    plan = plan_with_soc(
        origin_address="A",
        origin_latlon=(0.0, 0.0),
        destination_address="B",
        destination_latlon=(4.0, 0.0),
        routing=engine,
        charger_finder=finder,
        consumption_model=m,
        initial_soc_kwh=60.0,  # start with 60 kWh
        battery_kwh=75.0,
        target_soc_kwh=60.0,  # charge to 60 kWh at each stop
        min_arrival_soc_kwh=7.5,  # 10% of 75
        stops_every_km=150.0,
        car_model_alias="model_y_lr",
        initial_soc_frac=0.8,
        emit_abrp_link=False,
    )
    assert len(plan.stops) >= 1
    assert plan.total_energy_kwh is not None
    assert plan.total_energy_kwh > 0
    assert plan.consumption_source == "baseline"
    assert plan.segments, "segments list should be populated"
    # Each segment dict has required keys
    seg = plan.segments[0]
    for key in ("from", "to", "distance_km", "duration_min", "energy_kwh", "soc_arrive_kwh"):
        assert key in seg
    # First stop has arrival/departure SoC assigned
    first = plan.stops[0]
    assert first.arrival_soc_kwh is not None
    assert first.departure_soc_kwh is not None
    assert first.charge_duration_min is not None


def test_plan_with_soc_flags_insufficient_range() -> None:
    # Very small initial SoC forces a range warning on the first leg
    polyline = [(0.0, 0.0), (4.0, 0.0)]
    engine = _StubEngine(polyline, total_km=444.0, total_min=300)

    def finder(lat, lon):
        return _one_charger(lat, lon)

    m = BASELINES["tesla:my:22:bt37:lr"]
    plan = plan_with_soc(
        origin_address="A",
        origin_latlon=(0.0, 0.0),
        destination_address="B",
        destination_latlon=(4.0, 0.0),
        routing=engine,
        charger_finder=finder,
        consumption_model=m,
        initial_soc_kwh=5.0,  # barely any charge
        battery_kwh=75.0,
        target_soc_kwh=60.0,
        min_arrival_soc_kwh=7.5,
        stops_every_km=150.0,
        car_model_alias="model_y_lr",
        initial_soc_frac=0.05,
        emit_abrp_link=False,
    )
    warnings = [s.soc_warning for s in plan.stops if s.soc_warning]
    assert warnings, "should produce at least one insufficient-range warning"


def test_plan_with_soc_with_elevation_and_temp_callbacks() -> None:
    polyline = [(0.0, 0.0), (4.0, 0.0)]
    engine = _StubEngine(polyline, total_km=444.0, total_min=300)

    def finder(lat, lon):
        return _one_charger(lat, lon)

    def fetch_elev(_poly):
        return [100.0, 500.0]  # 400 m climb over the route

    def fetch_temp(_lat, _lon):
        return 5.0  # cold

    m = BASELINES["tesla:my:22:bt37:lr"]
    plan_cold = plan_with_soc(
        origin_address="A",
        origin_latlon=(0.0, 0.0),
        destination_address="B",
        destination_latlon=(4.0, 0.0),
        routing=engine,
        charger_finder=finder,
        consumption_model=m,
        initial_soc_kwh=60.0,
        battery_kwh=75.0,
        target_soc_kwh=60.0,
        min_arrival_soc_kwh=7.5,
        stops_every_km=150.0,
        car_model_alias="model_y_lr",
        initial_soc_frac=0.8,
        emit_abrp_link=False,
        fetch_elevation=fetch_elev,
        fetch_temp=fetch_temp,
    )
    plan_warm = plan_with_soc(
        origin_address="A",
        origin_latlon=(0.0, 0.0),
        destination_address="B",
        destination_latlon=(4.0, 0.0),
        routing=engine,
        charger_finder=finder,
        consumption_model=m,
        initial_soc_kwh=60.0,
        battery_kwh=75.0,
        target_soc_kwh=60.0,
        min_arrival_soc_kwh=7.5,
        stops_every_km=150.0,
        car_model_alias="model_y_lr",
        initial_soc_frac=0.8,
        emit_abrp_link=False,
    )
    # Cold + climbing route should consume more energy than warm + flat
    assert plan_cold.total_energy_kwh is not None
    assert plan_warm.total_energy_kwh is not None
    assert plan_cold.total_energy_kwh > plan_warm.total_energy_kwh
    # Temperature and elevation propagate into segment dicts
    seg = plan_cold.segments[0]
    assert seg["ambient_temp_c"] == pytest.approx(5.0)
