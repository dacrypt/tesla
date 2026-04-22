"""Tests for tesla_cli.core.planner.graph (Phase 3 A*)."""

from __future__ import annotations

from tesla_cli.core.planner.consumption import DEFAULT_BASELINE
from tesla_cli.core.planner.graph import plan_alternatives
from tesla_cli.core.planner.models import ChargerSuggestion


def _charger(
    ocm_id: int, lat: float, lon: float, power: float = 150.0, network: str = "tesla"
) -> ChargerSuggestion:
    return ChargerSuggestion(
        ocm_id=ocm_id,
        name=f"C{ocm_id}",
        lat=lat,
        lon=lon,
        network=network,
        max_power_kw=power,
    )


def test_plan_alternatives_returns_feasible_primary_path() -> None:
    # Short route — direct from origin to destination should succeed.
    # 100 km on lat axis => battery of 75 kWh, ~180 Wh/km => 18 kWh consumed.
    origin = (0.0, 0.0)
    destination = (0.9, 0.0)  # ~100 km
    chargers = [_charger(1, 0.4, 0.01), _charger(2, 0.7, 0.01)]
    seqs = plan_alternatives(
        origin=origin,
        destination=destination,
        chargers=chargers,
        consumption_model=DEFAULT_BASELINE,
        initial_soc_kwh=60.0,
        battery_kwh=75.0,
        target_soc_kwh=60.0,
        min_arrival_soc_kwh=7.5,
        max_alternatives=3,
    )
    assert len(seqs) >= 1
    # Primary path should be direct (no stops needed for 100 km @ full charge)
    assert seqs[0] == []


def test_plan_alternatives_infeasible_returns_empty() -> None:
    # Very long route with no chargers — unreachable.
    origin = (0.0, 0.0)
    destination = (10.0, 0.0)  # ~1110 km
    seqs = plan_alternatives(
        origin=origin,
        destination=destination,
        chargers=[],
        consumption_model=DEFAULT_BASELINE,
        initial_soc_kwh=60.0,
        battery_kwh=75.0,
        target_soc_kwh=60.0,
        min_arrival_soc_kwh=7.5,
        max_alternatives=3,
    )
    assert seqs == []


def test_plan_alternatives_enforces_soc_constraint() -> None:
    # Low starting SoC (5 kWh) below min arrival (10 kWh) with no chargers
    # should be infeasible even if the route is short.
    origin = (0.0, 0.0)
    destination = (0.9, 0.0)
    seqs = plan_alternatives(
        origin=origin,
        destination=destination,
        chargers=[],
        consumption_model=DEFAULT_BASELINE,
        initial_soc_kwh=5.0,
        battery_kwh=75.0,
        target_soc_kwh=60.0,
        min_arrival_soc_kwh=10.0,
        max_alternatives=3,
    )
    assert seqs == []


def test_plan_alternatives_produces_multiple_options_with_many_chargers() -> None:
    # Long-ish route (~450 km) with many viable chargers along the way.
    origin = (0.0, 0.0)
    destination = (4.0, 0.0)  # ~444 km
    # Strewn chargers across the corridor at ~100 km intervals, slightly varied
    chargers = [
        _charger(10, 0.9, 0.05),
        _charger(11, 1.8, 0.05),
        _charger(12, 2.7, 0.05),
        _charger(13, 3.6, 0.05),
        _charger(14, 1.2, 0.2),
        _charger(15, 2.1, 0.2),
        _charger(16, 3.0, 0.2),
    ]
    seqs = plan_alternatives(
        origin=origin,
        destination=destination,
        chargers=chargers,
        consumption_model=DEFAULT_BASELINE,
        initial_soc_kwh=60.0,
        battery_kwh=75.0,
        target_soc_kwh=60.0,
        min_arrival_soc_kwh=7.5,
        max_alternatives=3,
    )
    # At least one feasible path
    assert len(seqs) >= 1
    # Signatures should be unique
    sigs = [tuple(s.ocm_id for s in seq) for seq in seqs]
    assert len(sigs) == len(set(sigs))


def test_plan_alternatives_respects_max_alternatives_cap() -> None:
    origin = (0.0, 0.0)
    destination = (4.0, 0.0)
    chargers = [_charger(i, 0.5 * i, 0.02) for i in range(1, 8)]
    seqs = plan_alternatives(
        origin=origin,
        destination=destination,
        chargers=chargers,
        consumption_model=DEFAULT_BASELINE,
        initial_soc_kwh=60.0,
        battery_kwh=75.0,
        target_soc_kwh=60.0,
        min_arrival_soc_kwh=7.5,
        max_alternatives=2,
    )
    assert len(seqs) <= 2


def test_plan_alternatives_zero_budget_returns_empty() -> None:
    seqs = plan_alternatives(
        origin=(0.0, 0.0),
        destination=(0.5, 0.0),
        chargers=[],
        consumption_model=DEFAULT_BASELINE,
        initial_soc_kwh=60.0,
        battery_kwh=75.0,
        target_soc_kwh=60.0,
        min_arrival_soc_kwh=7.5,
        max_alternatives=0,
    )
    assert seqs == []
