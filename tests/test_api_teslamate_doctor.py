"""API tests for GET /api/teslaMate/doctor.

Patches ``run_doctor`` at the route boundary so no real DB or Docker
connections are needed.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402
from tesla_cli.core.diagnostics.teslamate_doctor import DoctorCheck, DoctorReport  # noqa: E402


def _make_report(failed: int = 2, total: int = 8) -> DoctorReport:
    checks = [
        DoctorCheck(
            name=f"check_{i}",
            label=f"Check {i}",
            ok=(i >= failed),
            message="ok" if i >= failed else "failed",
            hint=None if i >= failed else "Fix it",
        )
        for i in range(total)
    ]
    return DoctorReport(checks=checks, failed=failed, total=total)


def _make_client() -> TestClient:
    from tesla_cli.core.config import Config

    cfg = Config()
    patches = [
        patch("tesla_cli.api.app.load_config", return_value=cfg),
        patch("tesla_cli.api.routes.teslaMate.load_config", return_value=cfg),
    ]
    for p in patches:
        p.start()
    app = create_app(vin=None)
    client = TestClient(app, raise_server_exceptions=False)
    client._patches = patches  # type: ignore[attr-defined]
    return client


# ── 1. Shape ─────────────────────────────────────────────────────────────────


def test_doctor_route_returns_report_shape():
    report = _make_report(failed=2, total=8)
    client = _make_client()
    try:
        with patch("tesla_cli.api.routes.teslaMate.run_doctor", return_value=report):
            resp = client.get("/api/teslaMate/doctor")
        assert resp.status_code == 200
        body = resp.json()
        assert "checks" in body
        assert "failed" in body
        assert "total" in body
        assert len(body["checks"]) == 8
        assert body["failed"] == 2
        assert body["total"] == 8
        # Spot-check first check fields
        first = body["checks"][0]
        assert "name" in first
        assert "label" in first
        assert "ok" in first
        assert "message" in first
    finally:
        for p in client._patches:  # type: ignore[attr-defined]
            p.stop()


# ── 2. failed=8 is still 200, not 503 ────────────────────────────────────────


def test_doctor_route_never_raises_when_run_doctor_succeeds():
    report = _make_report(failed=8, total=8)
    client = _make_client()
    try:
        with patch("tesla_cli.api.routes.teslaMate.run_doctor", return_value=report):
            resp = client.get("/api/teslaMate/doctor")
        # All 8 checks failed, but the route itself must return 200
        assert resp.status_code == 200
        body = resp.json()
        assert body["failed"] == 8
    finally:
        for p in client._patches:  # type: ignore[attr-defined]
            p.stop()


# ── 3. Unexpected exception → 500/503 (FastAPI default) ──────────────────────


def test_doctor_route_returns_500_when_run_doctor_itself_raises():
    client = _make_client()
    try:
        with patch(
            "tesla_cli.api.routes.teslaMate.run_doctor",
            side_effect=RuntimeError("unexpected internal error"),
        ):
            resp = client.get("/api/teslaMate/doctor")
        assert resp.status_code in {500, 503}
    finally:
        for p in client._patches:  # type: ignore[attr-defined]
            p.stop()
