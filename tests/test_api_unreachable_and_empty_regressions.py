"""Regressions for bugs found while raising coverage (v5.5)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402
from tesla_cli.core.config import Config  # noqa: E402


@pytest.fixture
def client():
    with patch("tesla_cli.api.app.load_config", return_value=Config()):
        yield TestClient(create_app(), raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("path", "status", "body"),
    [
        ("/api/charge/last", 404, None),
        ("/api/charge/weekly", 200, {"weeks": []}),
        (
            "/api/charge/analytics/cost-summary",
            200,
            {"total_kwh": 0.0, "total_cost": 0.0, "months": []},
        ),
    ],
)
def test_charge_endpoints_without_sessions_are_not_500(client, path, status, body):
    """They returned [] from `-> dict` routes, which FastAPI turned into a 500."""
    with patch("tesla_cli.core.charging.fetch_charging_sessions", return_value=([], "")):
        r = client.get(path)
    assert r.status_code == status
    if body:
        assert body.items() <= r.json().items()


def test_init_reports_automation_counts(client, tmp_path, monkeypatch):
    """/api/init imported a non-existent module, so automations were always null."""
    from tesla_cli.core import automation

    rules = tmp_path / "automations.json"
    rules.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "name": "low",
                        "enabled": True,
                        "trigger": {"type": "battery_below", "threshold": 20},
                        "action": {"type": "notify", "message": "low"},
                    },
                    {
                        "name": "off",
                        "enabled": False,
                        "trigger": {"type": "battery_below", "threshold": 10},
                        "action": {"type": "notify", "message": "x"},
                    },
                ]
            }
        )
    )
    monkeypatch.setattr(automation, "AUTOMATIONS_FILE", rules)
    monkeypatch.setattr(
        automation.AutomationEngine.__init__, "__defaults__", (rules,), raising=False
    )
    with patch("tesla_cli.api.routes.init.load_config", return_value=Config()):
        r = client.get("/api/init")
    assert r.status_code == 200
    assert r.json()["automations"] == {"total": 2, "enabled": 1}


def test_service_appointments_calls_backend_without_vin(client):
    """Backends take no VIN; passing one raised TypeError → 502."""
    from tesla_cli.core.backends.cached import CachedVehicleBackend

    inner = MagicMock()
    inner.get_service_appointments.return_value = {"appointments": [{"id": 1}]}
    with (
        patch("tesla_cli.api.routes.service.load_config", return_value=Config()),
        patch(
            "tesla_cli.api.routes.service.get_vehicle_backend",
            return_value=CachedVehicleBackend(inner),
        ),
    ):
        r = client.get("/api/service/appointments")
    assert r.status_code == 200
    assert r.json() == [{"id": 1}]


@pytest.mark.parametrize(
    "path", ["/api/scenes/", "/api/service/reminders", "/api/energy/mgmt/sites"]
)
def test_previously_unmounted_routers_are_reachable(client, path):
    paths = {getattr(r, "path", "") for r in client.app.routes}
    assert path in paths
