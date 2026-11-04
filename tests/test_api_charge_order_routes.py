"""Tests for the less-covered /api/charge/* and /api/order/* endpoints.

Charge: history, sessions, last, weekly, schedules (file-backed), analytics.
Order: summary, share, status, details (delivery enrichment).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402
from tesla_cli.core import charging  # noqa: E402
from tesla_cli.core.backends import order as order_mod  # noqa: E402
from tesla_cli.core.config import Config  # noqa: E402
from tesla_cli.core.exceptions import (  # noqa: E402
    BackendNotSupportedError,
    RateLimitError,
    VehicleAsleepError,
)
from tesla_cli.core.models.charge import ChargingSession  # noqa: E402
from tesla_cli.core.models.order import OrderDetails, OrderStatus, OrderTask  # noqa: E402
from tests.conftest import MOCK_VIN  # noqa: E402


@pytest.fixture(scope="module")
def app():
    # Building the app is the slow part; routes read config per request.
    with patch("tesla_cli.api.app.load_config", return_value=Config()):
        return create_app(vin=None)


@pytest.fixture
def env(app, tmp_path, monkeypatch):
    # Charge schedules live at Path.home()/.tesla-cli — redirect to tmp.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    cfg = Config()
    cfg.general.default_vin = MOCK_VIN
    cfg.order.reservation_number = "RN123456"
    backend = MagicMock()
    sessions = MagicMock(return_value=([], "none"))
    ps = [
        patch("tesla_cli.api.routes.charge.load_config", return_value=cfg),
        patch("tesla_cli.api.routes.charge.resolve_vin", return_value=MOCK_VIN),
        patch("tesla_cli.api.routes.charge.get_vehicle_backend", return_value=backend),
        patch("tesla_cli.api.routes.order.load_config", return_value=cfg),
        patch.object(charging, "fetch_charging_sessions", sessions),
    ]
    for p in ps:
        p.start()
    client = TestClient(app, raise_server_exceptions=False)
    yield SimpleNamespace(client=client, cfg=cfg, backend=backend, sessions=sessions, home=tmp_path)
    for p in ps:
        p.stop()


def _s(date: str, kwh: float, cost: float | None = None, est: bool = False) -> ChargingSession:
    return ChargingSession(date=date, kwh=kwh, cost=cost, cost_estimated=est, source="teslamate")


# ── /api/charge/history ─────────────────────────────────────────────────────


def test_charge_history_parsed(env):
    env.backend.get_charge_history.return_value = {
        "total_charged": {"value": "123.4", "after_adornment": "kWh"},
        "charging_history_graph": {"data_points": []},
    }
    r = env.client.get("/api/charge/history")
    assert r.status_code == 200
    body = r.json()
    assert body["total_kwh"] == 123.4


def test_charge_history_not_supported_501(env):
    env.backend.get_charge_history.side_effect = BackendNotSupportedError("charge history")
    r = env.client.get("/api/charge/history")
    assert r.status_code == 501
    assert "Fleet API" in r.json()["detail"]


# ── sessions / last / weekly ────────────────────────────────────────────────


def test_charge_sessions_limit_capped(env):
    env.sessions.return_value = ([_s("2026-01-01", 10.0)], "teslamate")
    r = env.client.get("/api/charge/sessions?limit=9999")
    assert r.status_code == 200
    assert r.json()[0]["kwh"] == 10.0
    env.sessions.assert_called_once_with(limit=500)


def test_charge_sessions_empty(env):
    assert env.client.get("/api/charge/sessions").json() == []


def test_analytics_sessions(env):
    env.sessions.return_value = ([_s("2026-01-01", 5.0), _s("2026-01-02", 6.0)], "fleet")
    body = env.client.get("/api/charge/analytics/sessions?limit=2").json()
    assert [x["kwh"] for x in body] == [5.0, 6.0]
    env.sessions.assert_called_once_with(limit=2)
    env.sessions.return_value = ([], "none")
    assert env.client.get("/api/charge/analytics/sessions").json() == []


def test_charge_last(env):
    env.sessions.return_value = ([_s("2026-02-01", 30.0, 12.5)], "teslamate")
    body = env.client.get("/api/charge/last").json()
    assert body["kwh"] == 30.0
    assert body["cost"] == 12.5
    assert body["source_name"] == "teslamate"
    env.sessions.assert_called_once_with(limit=1)


def test_charge_weekly_groups_by_iso_week(env):
    env.sessions.return_value = (
        [
            _s("2026-01-05T08:00:00", 10.0, 2.0),  # 2026-W02
            _s("2026-01-06", 5.04, None),  # 2026-W02
            _s("2026-01-12", 20.0, 4.0),  # 2026-W03
            _s("2025-12-01", 1.0, 1.0),  # 2025-W49
            _s("not-a-date", 99.0, 99.0),  # skipped
        ],
        "teslamate",
    )
    body = env.client.get("/api/charge/weekly?weeks=2").json()
    assert body["source"] == "teslamate"
    assert body["weeks"] == [
        {"week": "2026-W02", "kwh": 15.0, "cost": 2.0, "sessions": 2},
        {"week": "2026-W03", "kwh": 20.0, "cost": 4.0, "sessions": 1},
    ]


def test_cost_summary_monthly(env):
    env.sessions.return_value = (
        [
            _s("2026-01-05", 10.0, 2.5),
            _s("2026-01-20", 5.0, None, est=False),
            _s("2026-02-01", 8.0, 1.0, est=True),
            _s("garbage", 100.0, 100.0),
        ],
        "teslamate",
    )
    body = env.client.get("/api/charge/analytics/cost-summary").json()
    assert body["source"] == "teslamate"
    assert body["total_kwh"] == 23.0
    assert body["total_cost"] == 3.5
    assert body["months"] == [
        {"month": "2026-02", "kwh": 8.0, "cost": 1.0, "sessions": 1, "cost_estimated": True},
        {"month": "2026-01", "kwh": 15.0, "cost": 2.5, "sessions": 2, "cost_estimated": False},
    ]


# ── forecast ────────────────────────────────────────────────────────────────


def test_forecast_flat_state(env):
    env.backend.get_charge_state.return_value = {
        "battery_level": 55,
        "charge_limit_soc": 80,
        "minutes_to_full_charge": 90,
        "charging_state": "Charging",
        "charge_rate": 30.5,
        "charge_energy_added": 12.3,
    }
    body = env.client.get("/api/charge/analytics/forecast").json()
    assert body == {
        "battery_level": 55,
        "charge_limit_soc": 80,
        "charging_state": "Charging",
        "minutes_to_full_charge": 90,
        "charge_rate_mph": 30.5,
        "charge_energy_added_kwh": 12.3,
        "is_charging": True,
    }


def test_forecast_nested_state(env):
    env.backend.get_charge_state.return_value = {
        "charge_state": {"battery_level": 70, "charge_limit_soc": 90}
    }
    body = env.client.get("/api/charge/analytics/forecast").json()
    assert body["battery_level"] == 70
    assert body["charge_limit_soc"] == 90
    assert body["charging_state"] == "Unknown"
    assert body["is_charging"] is False


def test_forecast_asleep_and_error(env):
    env.backend.get_charge_state.side_effect = VehicleAsleepError("zzz")
    assert env.client.get("/api/charge/analytics/forecast").status_code == 503
    env.backend.get_charge_state.side_effect = RuntimeError("kaput")
    r = env.client.get("/api/charge/analytics/forecast")
    assert r.status_code == 502
    assert r.json()["detail"] == "kaput"


def test_charge_status_rate_limit_maps_to_429(env):
    env.backend.get_charge_state.side_effect = RateLimitError()
    r = env.client.get("/api/charge/status")
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "10"


# ── schedules (file-backed under ~/.tesla-cli) ─────────────────────────────


def test_schedules_crud_roundtrip(env):
    c = env.client
    assert c.get("/api/charge/schedules").json() == []

    r1 = c.post("/api/charge/schedules", json={"name": "Home", "limit_percent": 90})
    assert r1.json() == {"ok": True, "id": 1}
    r2 = c.post(
        "/api/charge/schedules",
        json={"name": "Work", "latitude": 4.6, "longitude": -74.0, "days": ["Mon"]},
    )
    assert r2.json()["id"] == 2

    path = env.home / ".tesla-cli" / "charge_schedules.json"
    on_disk = json.loads(path.read_text())
    assert [s["name"] for s in on_disk] == ["Home", "Work"]
    assert on_disk[0]["limit_percent"] == 90
    assert on_disk[0]["radius_km"] == 0.5
    assert on_disk[1]["days"] == ["Mon"]

    assert c.delete("/api/charge/schedules/1").json() == {"ok": True}
    assert [s["id"] for s in c.get("/api/charge/schedules").json()] == [2]

    # ids keep increasing after deletes
    assert c.post("/api/charge/schedules", json={"name": "Gym"}).json()["id"] == 3


def test_schedule_delete_missing_404(env):
    r = env.client.delete("/api/charge/schedules/42")
    assert r.status_code == 404
    assert "42" in r.json()["detail"]


def test_schedules_corrupt_file_reads_empty(env):
    path = env.home / ".tesla-cli" / "charge_schedules.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken")
    assert env.client.get("/api/charge/schedules").json() == []


def test_schedule_requires_name(env):
    assert env.client.post("/api/charge/schedules", json={}).status_code == 422


# ── Order routes ────────────────────────────────────────────────────────────


def _status(**kw) -> OrderStatus:
    base = dict(
        reservation_number="RN123456",
        order_status="BOOKED",
        model="Model Y",
        trim="Long Range",
        exterior_color="Stealth Grey",
        interior_color="Black",
        wheels='19" Gemini',
        vin=MOCK_VIN,
    )
    base.update(kw)
    return OrderStatus(**base)


@pytest.fixture
def order_backend():
    inst = MagicMock()
    inst.get_order_status.return_value = _status()
    with patch.object(order_mod, "OrderBackend", return_value=inst):
        yield inst


@pytest.mark.parametrize("path", ["summary", "share", "status", "details"])
def test_order_routes_require_reservation(env, order_backend, path):
    env.cfg.order.reservation_number = ""
    r = env.client.get(f"/api/order/{path}")
    assert r.status_code == 404
    assert "reservation" in r.json()["detail"]
    order_backend.get_order_status.assert_not_called()


@pytest.mark.parametrize("path", ["summary", "share", "status"])
def test_order_routes_backend_error_502(env, order_backend, path):
    order_backend.get_order_status.side_effect = RuntimeError("tesla 500")
    r = env.client.get(f"/api/order/{path}")
    assert r.status_code == 502
    assert r.json()["detail"] == "tesla 500"


def test_order_summary(env, order_backend):
    body = env.client.get("/api/order/summary").json()
    assert body["reservation_number"] == "RN123456"
    assert body["summary"].startswith("Your Model Y already has a VIN.")
    order_backend.get_order_status.assert_called_once_with("RN123456")


def test_order_share_hides_vin_by_default(env, order_backend):
    body = env.client.get("/api/order/share").json()
    lines = body["text"].split("\n")
    assert lines[0].endswith("Tesla Model Y Long Range — BOOKED")
    assert any("Stealth Grey / Black" in ln for ln in lines)
    assert MOCK_VIN not in body["text"]
    assert body["summary"] in body["text"]


def test_order_share_with_vin(env, order_backend):
    body = env.client.get("/api/order/share?include_vin=true").json()
    assert f"VIN: {MOCK_VIN}" in body["text"]


def test_order_status_includes_summary(env, order_backend):
    body = env.client.get("/api/order/status").json()
    assert body["order_status"] == "BOOKED"
    assert body["vin"] == MOCK_VIN
    assert "summary" in body


def test_order_details_plain(env, order_backend):
    order_backend.get_order_details.return_value = OrderDetails(
        status=_status(),
        tasks=[OrderTask(task_type="registration", completed=True)],
        financing={"type": "cash"},
        delivery={"location": "Bogotá"},
        vehicle_info={"model": "Y"},
    )
    body = env.client.get("/api/order/details").json()
    assert body["status"]["reservation_number"] == "RN123456"
    assert body["tasks"][0]["task_type"] == "registration"
    assert body["financing"] == {"type": "cash"}
    assert body["delivery"] == {"location": "Bogotá"}
    assert body["vehicle_info"] == {"model": "Y"}
    assert body["registration"] == {}


def test_order_details_enriches_delivery_from_raw(env, order_backend):
    raw = {
        "_details": {
            "tasks": {
                "scheduling": {
                    "deliveryAddressTitle": "Tesla Medellín",
                    "deliveryAddressDetail": "Cra 43A",
                    "appointmentDate": "2026-12-01T15:00:00Z",
                    "readyToAccept": True,
                },
                "deliveryAcceptance": {"vehicleIsReady": True, "withinAppointmentWindow": False},
            },
            "schedulingMapUrl": "https://maps.example/x",
            "schedulingDeliveryType": "PICKUP",
            "financing": {"amountDueCustomer": 1500},
        }
    }
    order_backend.get_order_details.return_value = OrderDetails(
        status=_status(raw=raw), delivery={"location": "Existing"}
    )
    d = env.client.get("/api/order/details").json()["delivery"]
    # setdefault keeps values already present
    assert d["location"] == "Existing"
    assert d["address"] == "Cra 43A"
    assert d["appointmentDateUtc"] == "2026-12-01T15:00:00Z"
    assert d["mapUrl"] == "https://maps.example/x"
    assert d["deliveryType"] == "PICKUP"
    assert d["readyToAccept"] is True
    assert d["vehicleIsReady"] is True
    assert d["withinAppointmentWindow"] is False
    assert d["amountDue"] == 1500


def test_order_details_raw_without_scheduling(env, order_backend):
    raw = {"_details": {"tasks": [], "financing": {"amountDueCustomer": None}}}
    order_backend.get_order_details.return_value = OrderDetails(status=_status(raw=raw))
    assert env.client.get("/api/order/details").json()["delivery"] == {}


def test_order_details_error_502(env, order_backend):
    order_backend.get_order_details.side_effect = RuntimeError("auth expired")
    r = env.client.get("/api/order/details")
    assert r.status_code == 502
    assert r.json()["detail"] == "auth expired"
