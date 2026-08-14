"""API tests for /api/teslaMate/charging/{process_id}/enrichment."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

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
    client._patches = patches
    return client


def _make_mock_enrichment():
    from tesla_cli.core.models.charge import (
        AbrpCost,
        ChargeEnrichment,
        PreconditioningInfo,
        RankInfo,
        SharedStallInfo,
    )

    return ChargeEnrichment(
        rank=RankInfo(
            fastest_20_to_80_position=2,
            fastest_20_to_80_total=10,
            is_personal_best=False,
        ),
        preconditioning=PreconditioningInfo(detected=True, duration_minutes=3, confidence="medium"),
        shared_stall=SharedStallInfo(detected=False),
        abrp_cost=AbrpCost(
            estimated_cost=12.0,
            actual_cost=14.5,
            delta_pct=20.83,
            currency="USD",
            available=True,
        ),
    )


# ── 1. Populated response shape ──────────────────────────────────────────────


def test_enrichment_route_returns_shape():
    backend = MagicMock()
    backend.ping.return_value = True
    backend.get_charge_curve_enrichment.return_value = _make_mock_enrichment()
    backend.get_charging_process_end_date.return_value = datetime(2026, 4, 1, 11, 0, 0, tzinfo=UTC)

    client = _make_client(backend)
    try:
        resp = client.get("/api/teslaMate/charging/42/enrichment")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) >= {"rank", "preconditioning", "shared_stall", "abrp_cost"}
        assert body["rank"]["fastest_20_to_80_position"] == 2
        assert body["preconditioning"]["detected"] is True
        assert body["abrp_cost"]["available"] is True
    finally:
        for p in client._patches:
            p.stop()


# ── 2. 503 on ping fail ──────────────────────────────────────────────────────


def test_enrichment_503_on_ping_fail():
    backend = MagicMock()
    backend.ping.return_value = False

    client = _make_client(backend)
    try:
        resp = client.get("/api/teslaMate/charging/1/enrichment")
        assert resp.status_code == 503
        body = resp.json()
        hint_str = str(body).lower()
        assert "teslamate" in hint_str
        assert "hint" in hint_str
    finally:
        for p in client._patches:
            p.stop()


# ── 3. Cache-Control on completed sessions ───────────────────────────────────


def test_enrichment_cache_completed():
    backend = MagicMock()
    backend.ping.return_value = True
    backend.get_charge_curve_enrichment.return_value = _make_mock_enrichment()
    backend.get_charging_process_end_date.return_value = datetime(2026, 4, 1, 11, 0, 0, tzinfo=UTC)

    client = _make_client(backend)
    try:
        resp = client.get("/api/teslaMate/charging/42/enrichment")
        assert resp.status_code == 200
        assert resp.headers["Cache-Control"] == "public, max-age=86400, immutable"
    finally:
        for p in client._patches:
            p.stop()
