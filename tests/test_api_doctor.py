"""Integration test for GET /api/doctor."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402


def test_api_doctor_returns_feature_health_list():
    app = create_app(vin=None)
    client = TestClient(app)

    resp = client.get("/api/doctor")
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) >= 22

    allowed = {"ok", "missing-scope", "external-blocker", "not-configured"}
    for row in rows:
        assert set(row.keys()) >= {"name", "tier", "status"}
        assert row["status"] in allowed
    # Contract: there is at least one row with a valid status
    assert any(r["status"] in allowed for r in rows)
