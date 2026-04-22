"""End-to-end CLI tests for `tesla nav plan` (Phase 1)."""

from __future__ import annotations

import re

import pytest
from pytest_httpx import HTTPXMock

OSRM_URL_RE = re.compile(r"^https://router\.project-osrm\.org/.*")
OCM_URL_RE = re.compile(r"^https://api\.openchargemap\.io/v3/poi/.*")

from tesla_cli.core.nav import route as _route_mod
from tesla_cli.core.nav.route import NavStore, Route, Waypoint
from tests.conftest import run_cli


@pytest.fixture
def isolated_nav(tmp_path, monkeypatch):
    """Redirect nav.toml + nav.state.toml to a tmp dir."""
    nav_file = tmp_path / "nav.toml"
    state_file = tmp_path / "nav.state.toml"
    monkeypatch.setattr(_route_mod, "NAV_FILE", nav_file)
    monkeypatch.setattr(_route_mod, "NAV_STATE_FILE", state_file)
    return NavStore(nav_file=nav_file, state_file=state_file)


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Redirect config + keyring to tmp so tests don't touch host config/keyring."""
    cfg_file = tmp_path / "config.toml"
    monkeypatch.setattr("tesla_cli.core.config.CONFIG_FILE", cfg_file)

    store: dict[tuple[str, str], str] = {}

    def _set(key: str, value: str) -> None:
        store[("tesla-cli", key)] = value

    def _get(key: str):
        return store.get(("tesla-cli", key))

    def _has(key: str) -> bool:
        return ("tesla-cli", key) in store

    monkeypatch.setattr("tesla_cli.core.auth.tokens.set_token", lambda k, v: _set(k, v))
    monkeypatch.setattr("tesla_cli.core.auth.tokens.get_token", lambda k: _get(k))
    monkeypatch.setattr("tesla_cli.core.auth.tokens.has_token", lambda k: _has(k))
    return store


def _seed_ocm_key(store: dict) -> None:
    store[("tesla-cli", "planner-openchargemap-key")] = "ocm-test-key"


def _osrm_response(distance_km=300.0, duration_min=180) -> dict:
    return {
        "code": "Ok",
        "routes": [
            {
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-74.07, 4.71], [-75.58, 6.24]],
                },
                "distance": distance_km * 1000.0,
                "duration": duration_min * 60.0,
            }
        ],
    }


def _ocm_one_charger() -> list[dict]:
    return [
        {
            "ID": 42,
            "AddressInfo": {"Title": "SC Honda", "Latitude": 5.4, "Longitude": -74.8},
            "OperatorInfo": {"ID": 23, "Title": "Tesla Motors Inc"},
            "Connections": [
                {
                    "ConnectionType": {"ID": 27, "Title": "Tesla (Model S/X)"},
                    "PowerKW": 250.0,
                }
            ],
        }
    ]


def test_nav_plan_osrm_end_to_end(httpx_mock: HTTPXMock, isolated_nav, isolated_config) -> None:
    _seed_ocm_key(isolated_config)
    httpx_mock.add_response(
        url=OSRM_URL_RE,
        method="GET",
        json=_osrm_response(),
    )
    httpx_mock.add_response(
        url=OCM_URL_RE,
        method="GET",
        json=_ocm_one_charger(),
    )
    r = run_cli("nav", "plan", "4.71,-74.07", "6.24,-75.58", "--router", "osrm")
    assert r.exit_code == 0, r.output
    assert "SC Honda" in r.output
    assert "300.0 km" in r.output or "300 km" in r.output
    assert "abetterrouteplanner.com" not in r.output  # no car, no link


def test_nav_plan_save_as_persists_route(
    httpx_mock: HTTPXMock, isolated_nav, isolated_config
) -> None:
    _seed_ocm_key(isolated_config)
    httpx_mock.add_response(url=OSRM_URL_RE, json=_osrm_response())
    httpx_mock.add_response(url=OCM_URL_RE, json=_ocm_one_charger())
    r = run_cli(
        "nav",
        "plan",
        "4.71,-74.07",
        "6.24,-75.58",
        "--router",
        "osrm",
        "--save-as",
        "bogmed",
    )
    assert r.exit_code == 0, r.output
    persisted = isolated_nav.get_route("bogmed")
    assert persisted is not None
    assert persisted.source == "native-planner"
    assert len(persisted.waypoints) >= 1  # at least the destination


def test_nav_plan_save_as_collides_with_hand_created_skips(
    httpx_mock: HTTPXMock, isolated_nav, isolated_config
) -> None:
    _seed_ocm_key(isolated_config)
    # Pre-seed a hand-created route under the same name
    isolated_nav.save_route(
        Route(
            name="commute",
            created_at="2026-04-22T00:00:00Z",
            waypoints=[
                Waypoint(
                    raw_address="home",
                    lat=0.0,
                    lon=0.0,
                    geocode_provider="user",
                    geocode_at="2026-04-22T00:00:00Z",
                )
            ],
        )
    )
    httpx_mock.add_response(url=OSRM_URL_RE, json=_osrm_response())
    httpx_mock.add_response(url=OCM_URL_RE, json=_ocm_one_charger())
    r = run_cli(
        "nav",
        "plan",
        "4.71,-74.07",
        "6.24,-75.58",
        "--router",
        "osrm",
        "--save-as",
        "commute",
    )
    # Should still exit 0 (the nav.save_route skips with stderr warn)
    assert r.exit_code == 0
    # Hand-created route survived
    persisted = isolated_nav.get_route("commute")
    assert persisted is not None
    assert persisted.source is None


def test_nav_plan_openroute_missing_key_exits_with_signup_url(
    isolated_nav, isolated_config
) -> None:
    r = run_cli("nav", "plan", "4.71,-74.07", "6.24,-75.58", "--router", "openroute")
    assert r.exit_code == 1
    assert "openrouteservice.org" in r.output


def test_nav_plan_no_abrp_link_hides_link(
    httpx_mock: HTTPXMock, isolated_nav, isolated_config
) -> None:
    _seed_ocm_key(isolated_config)
    httpx_mock.add_response(url=OSRM_URL_RE, json=_osrm_response())
    httpx_mock.add_response(url=OCM_URL_RE, json=_ocm_one_charger())
    r = run_cli(
        "nav",
        "plan",
        "4.71,-74.07",
        "6.24,-75.58",
        "--router",
        "osrm",
        "--car",
        "model_y_lr",
        "--no-abrp-link",
    )
    assert r.exit_code == 0, r.output
    assert "abetterrouteplanner.com" not in r.output


def test_nav_plan_json_output_parses(httpx_mock: HTTPXMock, isolated_nav, isolated_config) -> None:
    import json as _json

    _seed_ocm_key(isolated_config)
    httpx_mock.add_response(url=OSRM_URL_RE, json=_osrm_response())
    httpx_mock.add_response(url=OCM_URL_RE, json=_ocm_one_charger())
    r = run_cli("nav", "plan", "4.71,-74.07", "6.24,-75.58", "--router", "osrm", "--json")
    assert r.exit_code == 0, r.output
    # Extract first JSON object from output
    start = r.output.find("{")
    assert start >= 0
    payload = _json.loads(r.output[start:].rsplit("}", 1)[0] + "}")
    assert payload["routing_provider"] == "osrm"
    assert payload["total_distance_km"] == 300.0


def test_nav_plan_probe_taxonomy_without_key_exits_with_signup(
    isolated_nav, isolated_config
) -> None:
    r = run_cli("nav", "plan-probe-taxonomy")
    assert r.exit_code == 1
    assert "openchargemap.org" in r.output
