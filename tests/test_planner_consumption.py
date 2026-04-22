"""Tests for tesla_cli.core.planner.consumption."""

from __future__ import annotations

import pytest

from tesla_cli.core.planner.consumption import (
    BASELINES,
    DEFAULT_BASELINE,
    ConsumptionModel,
    estimate_wh_per_km,
    fit_from_dataset,
    get_model,
    save_calibrated,
)


def test_get_model_returns_baseline_for_known_car() -> None:
    m = get_model("tesla:my:22:bt37:lr")
    assert m.car_model == "tesla:my:22:bt37:lr"
    assert m.base_wh_per_km == 170
    assert m.source == "baseline"


def test_get_model_returns_default_for_unknown_car() -> None:
    m = get_model("tesla:xx:99:nope:lr")
    # With no calibration file, unknown car falls back to default
    assert m.car_model == DEFAULT_BASELINE.car_model
    assert m.base_wh_per_km == DEFAULT_BASELINE.base_wh_per_km


def test_get_model_returns_default_for_none() -> None:
    m = get_model(None)
    assert m.car_model == DEFAULT_BASELINE.car_model


def test_estimate_wh_per_km_flat_90_equals_baseline() -> None:
    m = BASELINES["tesla:my:22:bt37:lr"]
    wh = estimate_wh_per_km(m, avg_speed_kmh=90.0, elevation_delta_m=0.0, distance_km=1.0)
    # At 90 km/h, flat, no temp → exactly base
    assert wh == pytest.approx(170.0, rel=1e-6)


def test_estimate_wh_per_km_elevation_adds_expected_wh_per_km() -> None:
    m = BASELINES["tesla:my:22:bt37:lr"]
    # 1000m climb over 100km → (1000/100)*40 = 400 Wh total → 4 Wh/km added
    wh = estimate_wh_per_km(m, avg_speed_kmh=90.0, elevation_delta_m=1000.0, distance_km=100.0)
    assert wh == pytest.approx(170.0 + 4.0, rel=1e-3)


def test_estimate_wh_per_km_speed_factor_at_130_matches_gain() -> None:
    m = BASELINES["tesla:my:22:bt37:lr"]
    wh = estimate_wh_per_km(m, avg_speed_kmh=130.0, elevation_delta_m=0.0, distance_km=1.0)
    # At 130 km/h: base * speed_gain == 170 * 1.30 == 221
    assert wh == pytest.approx(221.0, rel=1e-3)


def test_estimate_wh_per_km_cold_temperature_increases_consumption() -> None:
    m = BASELINES["tesla:my:22:bt37:lr"]
    warm = estimate_wh_per_km(m, 90.0, 0.0, ambient_temp_c=20.0, distance_km=1.0)
    cold = estimate_wh_per_km(m, 90.0, 0.0, ambient_temp_c=-10.0, distance_km=1.0)
    assert cold > warm
    # -10 °C should be roughly temp_factor_at_minus10 × warm
    assert cold == pytest.approx(warm * m.temp_factor_at_minus10, rel=1e-3)


def test_estimate_wh_per_km_descent_regen_half_value() -> None:
    m = BASELINES["tesla:my:22:bt37:lr"]
    climb = estimate_wh_per_km(m, 90.0, 1000.0, distance_km=100.0)
    descent = estimate_wh_per_km(m, 90.0, -1000.0, distance_km=100.0)
    base = estimate_wh_per_km(m, 90.0, 0.0, distance_km=100.0)
    # Descent recovers half of what a climb adds
    assert climb - base == pytest.approx(4.0, rel=1e-3)
    assert base - descent == pytest.approx(2.0, rel=1e-3)


def test_fit_from_dataset_with_few_samples_returns_baseline_shape() -> None:
    segs = [
        {
            "avg_speed_kmh": 90.0,
            "elevation_delta_m": 0.0,
            "distance_km": 50.0,
            "energy_kwh": 8.5,
            "outside_temp_c": 20.0,
        }
    ] * 10  # only 10 samples: under the 30-sample threshold
    m = fit_from_dataset("tesla:my:22:bt37:lr", segs)
    assert m.source == "teslamate-calibrated"
    assert m.samples == 10
    # Should still have baseline-like coefficients (not zero)
    assert m.base_wh_per_km == BASELINES["tesla:my:22:bt37:lr"].base_wh_per_km


def test_fit_from_dataset_with_synthetic_segments_returns_calibrated() -> None:
    # Synthetic dataset: all drives at 90 km/h flat, 20 °C, ~170 Wh/km → 100 km = 17 kWh
    segs = []
    for i in range(50):
        dist = 50.0 + (i % 10) * 5.0
        segs.append(
            {
                "avg_speed_kmh": 90.0 + (i % 5),
                "elevation_delta_m": 0.0,
                "distance_km": dist,
                "energy_kwh": 0.170 * dist,  # Wh/km = 170 → kWh/km = 0.170
                "outside_temp_c": 20.0,
            }
        )
    m = fit_from_dataset("tesla:my:22:bt37:lr", segs)
    assert m.source == "teslamate-calibrated"
    assert m.samples == 50
    assert m.r_squared is not None
    # On synthetic noise-free data, fit should be very good
    assert m.r_squared > 0.5
    assert m.mape_pct is not None


def test_consumption_model_roundtrip_via_save_calibrated(tmp_path, monkeypatch) -> None:
    calib = tmp_path / "consumption.toml"
    monkeypatch.setattr("tesla_cli.core.planner.consumption.CALIBRATION_FILE", calib)
    m = ConsumptionModel(
        car_model="tesla:my:22:bt37:lr",
        base_wh_per_km=165.0,
        speed_gain=1.28,
        elevation_wh_per_100m=38.0,
        temp_factor_at_minus10=1.22,
        source="teslamate-calibrated",
        samples=123,
        r_squared=0.82,
        mape_pct=7.5,
        fitted_at="2026-04-22T00:00:00Z",
    )
    save_calibrated(m)
    loaded = get_model("tesla:my:22:bt37:lr")
    assert loaded.base_wh_per_km == pytest.approx(165.0)
    assert loaded.source == "teslamate-calibrated"
    assert loaded.samples == 123
