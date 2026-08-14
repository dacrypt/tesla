"""API tests for /api/teslaMate/charging/{process_id}/{curve,stats}.

Patches the `_backend` factory in the route module to return a fully mocked
backend, so no fixtures, configs, or real DB are needed here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

# Skip module if fastapi / httpx not installed (consistent with test_api_routes.py).
fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402


def _make_cfg():
    from tesla_cli.core.config import Config

    cfg = Config()
    cfg.general.default_vin = "5YJYGDEE5MF000000"
    cfg.teslaMate.database_url = "postgresql://localhost/tm"
    return cfg


def _make_client(mock_backend) -> TestClient:
    cfg = _make_cfg()
    patches = [
        patch("tesla_cli.api.app.load_config", return_value=cfg),
        patch("tesla_cli.api.routes.teslaMate.load_config", return_value=cfg),
        patch("tesla_cli.api.routes.teslaMate._backend", return_value=mock_backend),
    ]
    for p in patches:
        p.start()
    app = create_app(vin=None)
    client = TestClient(app, raise_server_exceptions=False)
    client._patches = patches  # stash so caller can stop them
    return client


def _make_mock_curve(total_samples: int = 3):
    from tesla_cli.core.models.charge import ChargeCurve, ChargeSample

    samples = [
        ChargeSample(
            ts=datetime(2026, 4, 1, 10, 0, i, tzinfo=UTC),
            soc=15 + i,
            power_kw=180.0,
            current_a=400.0,
            voltage_v=450.0,
            phases=3,
            ideal_range_km=250.0,
        )
        for i in range(total_samples)
    ]
    return ChargeCurve(
        samples=samples,
        downsampled=False,
        total_samples=total_samples,
        stride=1,
    )


def _make_mock_stats():
    from tesla_cli.core.models.charge import ChargeCurveStats

    return ChargeCurveStats(
        peak_kw=180.0,
        avg_kw_20_80=142.58,
        taper_knee_soc=55,
        time_above_100kw_s=959,
        energy_above_100kw_kwh=43.39,
        phases_used=[3],
        duration_s=1199,
        kwh_added=48.46,
    )


# ── 503 on ping fail ─────────────────────────────────────────────────────────


def test_curve_503_on_ping_fail():
    backend = MagicMock()
    backend.ping.return_value = False

    client = _make_client(backend)
    try:
        resp = client.get("/api/teslaMate/charging/1/curve")
        assert resp.status_code == 503
        body = resp.json()
        # Error body can be shaped as {"detail": {...}} by FastAPI.
        hint_str = str(body).lower()
        assert "teslamate" in hint_str
        assert "hint" in hint_str
    finally:
        for p in client._patches:
            p.stop()


def test_stats_503_on_ping_fail():
    backend = MagicMock()
    backend.ping.return_value = False

    client = _make_client(backend)
    try:
        resp = client.get("/api/teslaMate/charging/1/stats")
        assert resp.status_code == 503
        hint_str = str(resp.json()).lower()
        assert "teslamate" in hint_str
    finally:
        for p in client._patches:
            p.stop()


# ── Cache headers ────────────────────────────────────────────────────────────


def test_curve_cache_header_completed():
    backend = MagicMock()
    backend.ping.return_value = True
    backend.get_charge_curve.return_value = _make_mock_curve(3)
    backend.get_charging_process_end_date.return_value = datetime(2026, 4, 1, 11, 0, 0, tzinfo=UTC)

    client = _make_client(backend)
    try:
        resp = client.get("/api/teslaMate/charging/42/curve")
        assert resp.status_code == 200
        assert resp.headers["Cache-Control"] == "public, max-age=86400, immutable"
        body = resp.json()
        assert body["total_samples"] == 3
        assert body["stride"] == 1
    finally:
        for p in client._patches:
            p.stop()


def test_curve_cache_header_in_progress():
    backend = MagicMock()
    backend.ping.return_value = True
    backend.get_charge_curve.return_value = _make_mock_curve(3)
    backend.get_charging_process_end_date.return_value = None

    client = _make_client(backend)
    try:
        resp = client.get("/api/teslaMate/charging/42/curve")
        assert resp.status_code == 200
        assert resp.headers["Cache-Control"] == "no-store"
    finally:
        for p in client._patches:
            p.stop()


def test_stats_cache_header_completed():
    backend = MagicMock()
    backend.ping.return_value = True
    backend.get_curve_stats.return_value = _make_mock_stats()
    backend.get_charging_process_end_date.return_value = datetime(2026, 4, 1, 11, 0, 0, tzinfo=UTC)

    client = _make_client(backend)
    try:
        resp = client.get("/api/teslaMate/charging/42/stats")
        assert resp.status_code == 200
        assert resp.headers["Cache-Control"] == "public, max-age=86400, immutable"
        body = resp.json()
        assert body["peak_kw"] == pytest.approx(180.0)
        assert body["taper_knee_soc"] == 55
    finally:
        for p in client._patches:
            p.stop()


def test_curve_404_when_no_samples():
    backend = MagicMock()
    backend.ping.return_value = True
    backend.get_charge_curve.return_value = _make_mock_curve(0)

    client = _make_client(backend)
    try:
        resp = client.get("/api/teslaMate/charging/9999/curve")
        assert resp.status_code == 404
    finally:
        for p in client._patches:
            p.stop()


def test_stats_404_when_backend_returns_none():
    backend = MagicMock()
    backend.ping.return_value = True
    backend.get_curve_stats.return_value = None

    client = _make_client(backend)
    try:
        resp = client.get("/api/teslaMate/charging/9999/stats")
        assert resp.status_code == 404
    finally:
        for p in client._patches:
            p.stop()
