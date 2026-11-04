"""Tests for tesla_cli.core.computed (real_status / specs derivation)."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from tesla_cli.core import computed
from tesla_cli.core.computed import _get_epa_data, compute_real_status, compute_specs

VIN = "7SAYGDEE4RF000001"  # US plant, pos7=E, model year S


# ── compute_real_status ─────────────────────────────────────────────────────


def test_ordered_when_nothing_known():
    rs = compute_real_status(order_data=None, runt_data=None)
    assert rs["phase"] == "ordered"
    assert rs["vin_assigned"] is False
    assert rs["is_produced"] is False
    assert rs["is_delivered"] is False


def test_produced_with_vin_and_api_status_nested():
    rs = compute_real_status(
        order_data={"current": {"order_status": "BOOKED"}}, runt_data=None, vin=VIN
    )
    assert rs["phase"] == "produced"
    assert rs["tesla_api_status"] == "BOOKED"
    assert rs["is_produced"] is True


def test_api_status_falls_back_to_order_status_camelcase():
    rs = compute_real_status(order_data={"orderStatus": "DELIVERED"}, runt_data=None)
    assert rs["tesla_api_status"] == "DELIVERED"


def test_registered_in_runt():
    rs = compute_real_status(
        order_data=None, runt_data={"estado": "REGISTRADO", "placa": ""}, vin=VIN
    )
    assert rs["phase"] == "registered"
    assert rs["in_runt"] is True
    assert rs["is_shipped"] and rs["is_in_country"] and rs["is_customs_cleared"]
    assert rs["has_placa"] is False


def test_runt_not_registered_is_produced():
    rs = compute_real_status(order_data=None, runt_data={"estado": "PENDIENTE"}, vin=VIN)
    assert rs["in_runt"] is False
    assert rs["runt_status"] == "PENDIENTE"
    assert rs["phase"] == "produced"


def test_delivered_by_placa_and_soat():
    rs = compute_real_status(
        order_data=None,
        runt_data={"estado": "REGISTRADO", "placa": "ABC123", "soat_vigente": True},
        vin=VIN,
    )
    assert rs["is_delivered"] is True
    assert rs["phase"] == "delivered"


def test_placa_without_soat_not_delivered():
    rs = compute_real_status(
        order_data=None,
        runt_data={"estado": "REGISTRADO", "placa": "ABC123", "soat_vigente": False},
        vin=VIN,
    )
    assert rs["is_delivered"] is False
    assert rs["phase"] == "registered"


def test_delivered_when_delivery_date_in_past():
    past = (date.today() - timedelta(days=3)).isoformat()
    rs = compute_real_status(order_data=None, runt_data=None, vin=VIN, delivery_date=past)
    assert rs["is_delivery_scheduled"] is True
    assert rs["is_delivered"] is True
    assert rs["phase"] == "delivered"


def test_delivery_today_counts_as_delivered():
    rs = compute_real_status(
        order_data=None, runt_data=None, delivery_date=date.today().isoformat() + "T10:00:00Z"
    )
    assert rs["phase"] == "delivered"


@pytest.mark.parametrize(
    "appointment,location,expected",
    [
        ("Sat, Dec 6 at 10:00 AM", "Bogotá", "Sat, Dec 6 at 10:00 AM"),
        ("", "Tesla Bogotá", "Entrega programada: {d} — Tesla Bogotá"),
        ("", "", "Entrega programada: {d}"),
    ],
)
def test_delivery_scheduled_descriptions(appointment, location, expected):
    future = (date.today() + timedelta(days=10)).isoformat()
    rs = compute_real_status(
        order_data=None,
        runt_data=None,
        vin=VIN,
        delivery_date=future,
        delivery_location=location,
        delivery_appointment=appointment,
    )
    assert rs["phase"] == "delivery_scheduled"
    assert rs["is_delivered"] is False
    assert rs["phase_description"] == expected.format(d=future)
    assert rs["delivery_location"] == location


def test_unparseable_delivery_date_is_scheduled_not_delivered():
    rs = compute_real_status(order_data=None, runt_data=None, delivery_date="next week")
    assert rs["is_delivery_scheduled"] is True
    assert rs["is_delivered"] is False
    assert rs["phase"] == "delivery_scheduled"


# ── compute_specs ───────────────────────────────────────────────────────────


def test_specs_defaults_without_epa_or_vin():
    with patch.object(computed, "_get_epa_data", return_value={}):
        specs = compute_specs()
    assert specs["model"] == "Model Y"
    assert specs["model_year"] == 0
    assert specs["factory"] == ""
    assert specs["horsepower"] == 389
    assert specs["range_km"] == 600
    assert specs["motor_config"] == "Dual Motor AWD (90 kW front + 200 kW rear ACPM)"
    assert specs["exterior_color"] == "Stealth Grey"
    assert specs["interior"] == "Premium Black"
    assert specs["wheels"] == '19" Gemini'
    assert specs["supercharging"] == "Pay Per Use"
    assert specs["connectivity"] == "Standard"


def test_specs_from_epa_and_vin_and_options():
    epa = {"ev_motor": "90 kW AC PMSM front, 200 kW rear", "range_mi": "311"}
    with patch.object(computed, "_get_epa_data", return_value=epa):
        specs = compute_specs(vin=VIN, option_codes_raw="PPSB,IPB0,WY20P,SC04,CPF0,ZZZZ")
    assert specs["model_year"] == 2024  # VIN year code "R"
    assert specs["battery_type"].startswith("NMC")
    assert specs["horsepower"] == int(290 * 1.341)
    assert specs["range_km"] == int(311 * 1.60934)
    assert specs["motor_config"] == f"Dual Motor AWD ({epa['ev_motor']})"
    assert specs["exterior_color"] == "Negro Obsidiana Metálico"
    assert specs["interior"] == "Interior Premium Negro"
    assert specs["wheels"] == 'Rines 20" Performance'
    assert specs["supercharging"] == "Supercharging de Pago"
    assert specs["connectivity"] == "Conectividad Estándar"


def test_specs_epa_motor_without_kw_uses_default_hp():
    with patch.object(computed, "_get_epa_data", return_value={"ev_motor": "Dual PMSM"}):
        specs = compute_specs()
    assert specs["horsepower"] == 389
    assert specs["motor_config"] == "Dual Motor AWD (Dual PMSM)"


# ── _get_epa_data ───────────────────────────────────────────────────────────


def test_epa_prefers_source_cache(httpx_mock):
    cached = {"ev_motor": "cached motor", "range_mi": 300}
    with patch("tesla_cli.core.sources.get_cached", return_value=cached):
        assert _get_epa_data() == cached
    assert httpx_mock.get_requests() == []


def test_epa_fetches_api_when_cache_empty(httpx_mock):
    httpx_mock.add_response(
        url="https://www.fueleconomy.gov/ws/rest/vehicle/49744",
        json={"evMotor": "220 kW", "range": 320, "rangeCity": 330, "rangeHwy": 300},
    )
    with patch("tesla_cli.core.sources.get_cached", return_value={"range_mi": 1}):
        out = _get_epa_data()
    assert out == {
        "ev_motor": "220 kW",
        "range_mi": 320,
        "range_city_mi": 330,
        "range_hwy_mi": 300,
    }


def test_epa_api_non_200_returns_empty(httpx_mock):
    httpx_mock.add_response(
        url="https://www.fueleconomy.gov/ws/rest/vehicle/49744", status_code=503
    )
    with patch("tesla_cli.core.sources.get_cached", side_effect=RuntimeError("cache broken")):
        assert _get_epa_data() == {}


def test_epa_api_network_error_returns_empty(httpx_mock):
    import httpx

    httpx_mock.add_exception(httpx.ConnectError("down"))
    with patch("tesla_cli.core.sources.get_cached", return_value=None):
        assert _get_epa_data() == {}
