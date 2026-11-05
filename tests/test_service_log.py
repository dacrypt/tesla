"""Maintenance log + reminders (core/service_log.py), CLI and API surfaces."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from tesla_cli.core import config as config_mod
from tesla_cli.core import service_log as sl
from tests.conftest import run_cli


@pytest.fixture(autouse=True)
def _tmp_home(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)


def _row(rows, item_id):
    return next(r for r in rows if r["id"] == item_id)


def test_unlogged_items_are_estimates_and_never_overdue():
    rows = sl.reminders(25_000)
    tires = _row(rows, "tires")
    assert tires["basis"] == "estimated"
    assert tires["next_service_km"] == 30_000
    assert tires["overdue"] is False


def test_logged_service_overdue_by_distance():
    sl.record("tires", km=10_000, on=date(2026, 1, 1))
    tires = _row(sl.reminders(21_000, today=date(2026, 2, 1)), "tires")
    assert tires["basis"] == "logged"
    assert tires["next_service_km"] == 20_000
    assert tires["km_until_service"] == -1_000
    assert tires["overdue"] is True


def test_logged_service_overdue_by_time():
    sl.record("cabin_air", km=5_000, on=date(2023, 1, 1))
    cabin = _row(sl.reminders(10_000, today=date(2026, 1, 1)), "cabin_air")
    assert cabin["next_service_date"] == "2024-12-31"  # 730 days, 2024 is a leap year
    assert cabin["days_until_service"] < 0
    assert cabin["overdue"] is True  # time limit reached before the km limit


def test_due_soon_by_date():
    sl.record("brake_fluid", on=date(2022, 1, 20))
    row = _row(sl.reminders(None, today=date(2026, 1, 5)), "brake_fluid")
    assert row["due_soon"] is True and row["overdue"] is False


def test_latest_entry_wins():
    sl.record("tires", km=10_000, on=date(2025, 1, 1))
    sl.record("tires", km=20_000, on=date(2026, 1, 1))
    assert sl.last_service("tires")["km"] == 20_000


def test_record_validates():
    with pytest.raises(ValueError, match="Unknown maintenance item"):
        sl.record("flux_capacitor")
    with pytest.raises(ValueError):
        sl.record("tires", km=-5)


def test_cli_done_and_log():
    result = run_cli("service", "done", "tires", "--km", "30500", "--date", "2026-03-01")
    assert result.exit_code == 0, result.output
    out = run_cli("--json", "service", "log")
    assert json.loads(out.output.strip().splitlines()[-1]) == [
        {"item": "tires", "date": "2026-03-01", "km": 30500}
    ]
    assert run_cli("service", "done", "nope").exit_code == 1


def test_cli_reminders_use_logged_dates():
    sl.record("cabin_air", on=date(2020, 1, 1))
    with patch("tesla_cli.cli.commands.service._backend", side_effect=RuntimeError("offline")):
        result = run_cli("service", "reminders", "--odometer", "1000")
    assert result.exit_code == 0, result.output
    assert "2020-01-01" in result.output


def test_api_log_roundtrip_and_reminders():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from tesla_cli.api.app import create_app
    from tesla_cli.core.config import Config

    backend = MagicMock()
    backend.get_vehicle_state.return_value = {"odometer": 13_000}  # ~20,921 km
    with (
        patch("tesla_cli.api.app.load_config", return_value=Config()),
        patch("tesla_cli.api.routes.service.load_config", return_value=Config()),
        patch("tesla_cli.api.routes.service.get_vehicle_backend", return_value=backend),
        patch("tesla_cli.api.routes.service.resolve_vin", return_value="5YJ3E1EA1PF000001"),
    ):
        client = TestClient(create_app())
        assert client.post("/api/service/log", json={"item": "nope"}).status_code == 422
        r = client.post("/api/service/log", json={"item": "tires", "km": 10_000})
        assert r.status_code == 200
        assert client.get("/api/service/log").json()[0]["item"] == "tires"
        tires = _row(client.get("/api/service/reminders").json(), "tires")
    assert tires["basis"] == "logged" and tires["overdue"] is True
