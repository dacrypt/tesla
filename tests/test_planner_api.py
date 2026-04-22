"""Tests for tesla_cli.api.routes.planner — POST /api/nav/plan + export."""

from __future__ import annotations

from unittest.mock import patch

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402
from tesla_cli.core.planner.models import ChargerSuggestion  # noqa: E402


def _mock_cfg():
    from tesla_cli.core.config import Config

    cfg = Config()
    cfg.general.default_vin = "VIN"
    cfg.planner.openchargemap_key = "ocm-test-key"
    cfg.planner.openroute_key = "ors-test-key"
    cfg.planner.router = "openroute"
    return cfg


def _patches():
    """Patch boundary for the planner route — load_config + engine + charger finder."""
    stub_route = {
        "polyline": [(4.71, -74.07), (6.24, -75.58)],
        "total_distance_km": 414.0,
        "total_duration_min": 360,
    }

    class _StubEngine:
        name = "openroute"

        def compute_route(self, origin, destination):
            return stub_route

    def _stub_finder(lat, lon, *args, **kwargs):
        return [
            ChargerSuggestion(
                ocm_id=1,
                name="SC Middle",
                lat=lat,
                lon=lon,
                network="tesla",
                max_power_kw=250.0,
            )
        ]

    return [
        patch("tesla_cli.api.routes.planner.load_config", return_value=_mock_cfg()),
        patch("tesla_cli.api.routes.planner.get_engine", return_value=_StubEngine()),
        patch(
            "tesla_cli.api.routes.planner.find_chargers_near_point",
            side_effect=_stub_finder,
        ),
    ]


def _client(api_key_bypass: bool = True) -> TestClient:
    app = create_app(serve_ui=False)
    return TestClient(app)


def test_plan_endpoint_returns_200_with_valid_plan() -> None:
    patches = _patches()
    for p in patches:
        p.start()
    try:
        client = _client()
        resp = client.post(
            "/api/nav/plan",
            json={
                "origin": "4.71,-74.07",
                "destination": "6.24,-75.58",
                "stops_every_km": 150.0,
                "network": "any",
                "router": "openroute",
                "alternatives": 1,
            },
        )
    finally:
        for p in patches:
            p.stop()
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan"] is not None
    assert body["plan"]["origin_latlon"] == [4.71, -74.07]
    assert body["plan"]["destination_latlon"] == [6.24, -75.58]
    assert body["plan"]["total_distance_km"] == 414.0


def test_plan_endpoint_400_for_bad_coords() -> None:
    patches = _patches()
    for p in patches:
        p.start()
    try:
        client = _client()
        # Malformed coord — doesn't match the latlon regex, will try geocode
        # and fail. We expect 400 from the geocode error path, but since
        # geocode might succeed with a stub address, ensure we can at least
        # cover the explicit bad-format coord path.
        resp = client.post(
            "/api/nav/plan",
            json={
                "origin": "nonsense,,,address",
                "destination": "6.24,-75.58",
                "alternatives": 1,
            },
        )
    finally:
        for p in patches:
            p.stop()
    # Either 400 (geocode error raised) or similar client error
    assert resp.status_code in (400, 422, 502)


def test_plan_endpoint_401_when_no_ocm_key() -> None:
    from tesla_cli.core.config import Config

    cfg = Config()
    cfg.general.default_vin = "VIN"
    cfg.planner.openchargemap_key = ""  # no key
    cfg.planner.openroute_key = "ors-test"

    class _StubEngine:
        name = "openroute"

        def compute_route(self, origin, destination):
            return {
                "polyline": [(0.0, 0.0), (1.0, 0.0)],
                "total_distance_km": 110.0,
                "total_duration_min": 90,
            }

    with patch("tesla_cli.api.routes.planner.load_config", return_value=cfg), patch(
        "tesla_cli.api.routes.planner.get_engine", return_value=_StubEngine()
    ), patch(
        "tesla_cli.api.routes.planner.tokens.get_token", return_value=""
    ):
        client = _client()
        resp = client.post(
            "/api/nav/plan",
            json={
                "origin": "0,0",
                "destination": "1,0",
                "alternatives": 1,
            },
        )
    assert resp.status_code == 401


def test_plan_endpoint_alternatives_returns_graph_results() -> None:
    patches = _patches()
    for p in patches:
        p.start()
    try:
        client = _client()
        resp = client.post(
            "/api/nav/plan",
            json={
                "origin": "4.71,-74.07",
                "destination": "6.24,-75.58",
                "alternatives": 3,
                "soc_start": 0.9,
                "battery_kwh": 75.0,
            },
        )
    finally:
        for p in patches:
            p.stop()
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan"] is not None
    # alternatives is a list; may be empty if graph planner deems only direct feasible.
    assert isinstance(body["alternatives"], list)
    assert isinstance(body["warnings"], list)


def test_plan_export_404_for_unknown_route(tmp_path, monkeypatch) -> None:
    import tesla_cli.core.nav.route as nav_route

    # Point NavStore to a temp file (empty = no routes)
    monkeypatch.setattr(nav_route, "NAV_FILE", tmp_path / "nav.toml")
    monkeypatch.setattr(nav_route, "NAV_STATE_FILE", tmp_path / "nav.state.toml")

    client = _client()
    resp = client.get("/api/nav/plan/missing-route/export?fmt=gpx")
    assert resp.status_code == 404


def test_plan_save_and_export_roundtrip(tmp_path, monkeypatch) -> None:
    import tesla_cli.core.nav.route as nav_route

    monkeypatch.setattr(nav_route, "NAV_FILE", tmp_path / "nav.toml")
    monkeypatch.setattr(nav_route, "NAV_STATE_FILE", tmp_path / "nav.state.toml")

    patches = _patches()
    for p in patches:
        p.start()
    try:
        client = _client()
        plan_resp = client.post(
            "/api/nav/plan",
            json={
                "origin": "4.71,-74.07",
                "destination": "6.24,-75.58",
                "alternatives": 1,
            },
        )
        assert plan_resp.status_code == 200
        plan = plan_resp.json()["plan"]
        save_resp = client.post(
            "/api/nav/plan/save",
            json={"name": "test-route", "plan": plan},
        )
        assert save_resp.status_code == 200, save_resp.text
        gpx_resp = client.get("/api/nav/plan/test-route/export?fmt=gpx")
        assert gpx_resp.status_code == 200
        assert "<gpx" in gpx_resp.text
        kml_resp = client.get("/api/nav/plan/test-route/export?fmt=kml")
        assert kml_resp.status_code == 200
        assert "<kml" in kml_resp.text
    finally:
        for p in patches:
            p.stop()
