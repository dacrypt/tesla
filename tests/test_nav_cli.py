"""CLI integration tests for `tesla nav` sub-app (v4.9.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def _wp(addr: str = "4.6,-74.0") -> Waypoint:
    return Waypoint(
        raw_address=addr,
        lat=4.6,
        lon=-74.0,
        geocode_provider="user",
        geocode_at="2026-04-22T00:00:00Z",
    )


def test_nav_help_lists_route_and_place(isolated_nav):
    r = run_cli("nav", "--help")
    assert r.exit_code == 0
    assert "route" in r.output
    assert "place" in r.output


def test_route_create_latlon_shortcircuit(isolated_nav):
    r = run_cli("nav", "route", "create", "commute", "4.6487,-74.0672")
    assert r.exit_code == 0, r.output
    route = isolated_nav.get_route("commute")
    assert route is not None
    assert len(route.waypoints) == 1
    assert route.waypoints[0].geocode_provider == "user"


def test_route_create_caps_at_max_geocode(isolated_nav):
    # 3 lat/lon pairs + 1 non-geocoded string with --max-geocode 0 triggers cap
    r = run_cli(
        "nav",
        "route",
        "create",
        "mixed",
        "Fake Address 1",
        "Fake Address 2",
        "--max-geocode",
        "1",
    )
    assert r.exit_code != 0
    assert "too many unresolved addresses" in r.output


def test_route_show_reprints_without_network(isolated_nav):
    isolated_nav.save_route(
        Route(
            name="smoke",
            waypoints=[_wp("4.6,-74.0"), _wp("4.7,-74.1")],
            created_at="2026-04-22T00:00:00Z",
        )
    )
    r = run_cli("nav", "route", "show", "smoke")
    assert r.exit_code == 0
    assert "4.6" in r.output and "4.7" in r.output


def test_route_list_shows_routes(isolated_nav):
    isolated_nav.save_route(
        Route(name="alpha", waypoints=[_wp()], created_at="2026-04-22T00:00:00Z")
    )
    r = run_cli("nav", "route", "list")
    assert r.exit_code == 0
    assert "alpha" in r.output


def test_route_delete_removes(isolated_nav):
    isolated_nav.save_route(
        Route(name="gone", waypoints=[_wp()], created_at="2026-04-22T00:00:00Z")
    )
    r = run_cli("nav", "route", "delete", "gone")
    assert r.exit_code == 0
    assert isolated_nav.get_route("gone") is None


def test_route_go_dry_run_prints_plan(isolated_nav):
    isolated_nav.save_route(
        Route(
            name="dry",
            waypoints=[_wp("4.6,-74.0"), _wp("4.7,-74.1")],
            created_at="2026-04-22T00:00:00Z",
        )
    )
    r = run_cli("nav", "route", "go", "dry", "--dry-run")
    assert r.exit_code == 0
    assert "Would send" in r.output
    assert "Trip complete (dry-run)" in r.output


def test_route_go_without_simulate_exits_2(isolated_nav):
    isolated_nav.save_route(
        Route(name="blocked", waypoints=[_wp()], created_at="2026-04-22T00:00:00Z")
    )
    r = run_cli("nav", "route", "go", "blocked")
    assert r.exit_code == 2
    assert "Auto-advance not available" in r.output


def test_route_verify_no_stale(isolated_nav):
    from datetime import UTC, datetime

    fresh_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    wp = Waypoint(
        raw_address="4.6,-74.0",
        lat=4.6,
        lon=-74.0,
        geocode_provider="user",
        geocode_at=fresh_ts,
    )
    isolated_nav.save_route(Route(name="fresh", waypoints=[wp], created_at=fresh_ts))
    r = run_cli("nav", "route", "verify", "fresh")
    assert r.exit_code == 0
    assert "no stale" in r.output


def test_route_verify_reports_stale_without_write(isolated_nav):
    stale_wp = Waypoint(
        raw_address="4.6,-74.0",
        lat=4.6,
        lon=-74.0,
        geocode_provider="user",
        geocode_at="2020-01-01T00:00:00Z",
    )
    isolated_nav.save_route(
        Route(name="old", waypoints=[stale_wp], created_at="2020-01-01T00:00:00Z")
    )
    r = run_cli("nav", "route", "verify", "old")
    assert r.exit_code == 0
    assert "stale" in r.output
    # Without --write, file is not mutated
    assert isolated_nav.get_route("old").waypoints[0].geocode_at == "2020-01-01T00:00:00Z"


def test_place_save_list_delete(isolated_nav):
    r1 = run_cli("nav", "place", "save", "home", "4.6,-74.0")
    assert r1.exit_code == 0
    r2 = run_cli("nav", "place", "list")
    assert r2.exit_code == 0
    assert "home" in r2.output
    r3 = run_cli("nav", "place", "delete", "home")
    assert r3.exit_code == 0
    assert isolated_nav.get_place("home") is None


def test_route_show_unknown_route_exits_nonzero(isolated_nav):
    r = run_cli("nav", "route", "show", "missing")
    assert r.exit_code == 1
    assert "No route" in r.output


def test_route_name_validation(isolated_nav):
    r = run_cli("nav", "route", "show", "BAD NAME!")
    assert r.exit_code != 0


def test_simulate_arrival_after_help_contains_test_only(isolated_nav):
    # Terminal-width word wrap can split help text arbitrarily; assert against
    # the source to guarantee the verbatim "TEST ONLY" + "no real telemetry"
    # markers landed (per plan §4 CLI copy).
    from tesla_cli.cli.commands import nav as nav_mod

    src = Path(nav_mod.__file__).read_text()
    assert "[TEST ONLY]" in src
    assert "no real telemetry" in src


def test_route_next_dispatch_and_increment(isolated_nav, monkeypatch):
    """Stub _dispatch_share so we don't need the backend; assert state advances."""
    from tesla_cli.cli.commands import nav as nav_cmd

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(nav_cmd, "_dispatch_share", lambda vin, addr: calls.append((vin, addr)))
    monkeypatch.setattr(nav_cmd, "_vin", lambda v: "5YJ3E1EA1PF000001")

    isolated_nav.save_route(
        Route(
            name="trip",
            waypoints=[_wp("A"), _wp("B")],
            created_at="2026-04-22T00:00:00Z",
        )
    )
    r1 = run_cli("nav", "route", "next", "trip")
    assert r1.exit_code == 0
    assert len(calls) == 1
    assert isolated_nav.read_state("trip")["next_index"] == 2

    r2 = run_cli("nav", "route", "next", "trip")
    assert r2.exit_code == 0
    assert len(calls) == 2
    # After last waypoint, next_index resets to 1 and "Trip complete" printed
    assert isolated_nav.read_state("trip")["next_index"] == 1
    assert "Trip complete" in r2.output


def test_simulate_arrival_dispatches_all_waypoints(isolated_nav, monkeypatch):
    from tesla_cli.cli.commands import nav as nav_cmd

    calls: list[str] = []
    monkeypatch.setattr(nav_cmd, "_dispatch_share", lambda vin, addr: calls.append(addr))
    monkeypatch.setattr(nav_cmd, "_vin", lambda v: "5YJ3E1EA1PF000001")

    isolated_nav.save_route(
        Route(
            name="sim",
            waypoints=[_wp("A"), _wp("B")],
            created_at="2026-04-22T00:00:00Z",
        )
    )
    r = run_cli("nav", "route", "go", "sim", "--simulate-arrival-after", "0", "--max-wait", "1")
    assert r.exit_code == 0, r.output
    assert len(calls) == 2
    assert "Trip complete" in r.output


# ─── KML fixture helper ───────────────────────────────────────────────────────


def _write_kml(tmp_path: Path, placemarks: list[tuple[str, float, float]]) -> Path:
    """Write a minimal KML file with the given (name, lat, lon) placemarks."""
    ns = "http://www.opengis.net/kml/2.2"
    marks = ""
    for name, lat, lon in placemarks:
        marks += f"""
  <Placemark>
    <name>{name}</name>
    <Point><coordinates>{lon},{lat},0</coordinates></Point>
  </Placemark>"""
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{ns}">
<Document>{marks}
</Document>
</kml>"""
    kml_path = tmp_path / "places.kml"
    kml_path.write_text(content)
    return kml_path


# ─── place import tests ───────────────────────────────────────────────────────


def test_place_import_dry_run(isolated_nav, tmp_path):
    kml = _write_kml(tmp_path, [("Home", 4.6, -74.0), ("Work", 4.7, -74.1)])
    r = run_cli("nav", "place", "import", str(kml), "--dry-run")
    assert r.exit_code == 0, r.output
    assert "Would import" in r.output
    # nav.toml must NOT have been written
    assert not isolated_nav.list_places()


def test_place_import_kml_writes_to_store(isolated_nav, tmp_path):
    kml = _write_kml(tmp_path, [("Home", 4.6, -74.0), ("Work", 4.7, -74.1)])
    r = run_cli("nav", "place", "import", str(kml))
    assert r.exit_code == 0, r.output
    places = isolated_nav.list_places()
    assert len(places) == 2
    sources = {p.source for p in places}
    assert sources == {"kml"}


def test_place_import_idempotent(isolated_nav, tmp_path):
    kml = _write_kml(tmp_path, [("Home", 4.6, -74.0), ("Work", 4.7, -74.1)])
    run_cli("nav", "place", "import", str(kml))
    r2 = run_cli("nav", "place", "import", str(kml))
    assert r2.exit_code == 0, r2.output
    assert "imported: 0" in r2.output
    assert "updated: 2" in r2.output


def test_place_import_with_tag(isolated_nav, tmp_path):
    kml = _write_kml(tmp_path, [("Home", 4.6, -74.0)])
    r = run_cli("nav", "place", "import", str(kml), "--tag", "bogota")
    assert r.exit_code == 0, r.output
    places = isolated_nav.list_places()
    assert len(places) == 1
    assert "bogota" in (places[0].tags or [])


def test_place_import_bad_extension(isolated_nav, tmp_path):
    txt = tmp_path / "places.txt"
    txt.write_text("not a supported format")
    r = run_cli("nav", "place", "import", str(txt))
    assert r.exit_code == 1
    assert "unsupported" in r.output.lower()


def test_place_import_oversize_file(isolated_nav, tmp_path, monkeypatch):
    from tesla_cli.core.nav import importers as imp_mod

    def _raise(path, max_mb=25):
        raise ValueError("file too large: 99999999 bytes > 25 MB cap")

    monkeypatch.setattr(imp_mod, "_check_file_size", _raise)
    kml = _write_kml(tmp_path, [("Home", 4.6, -74.0)])
    r = run_cli("nav", "place", "import", str(kml))
    assert r.exit_code == 1
    assert "too large" in r.output


# ─── place send tests ─────────────────────────────────────────────────────────


def test_place_send_dry_run_no_backend_call(isolated_nav, monkeypatch):
    from tesla_cli.cli.commands import nav as nav_cmd
    from tesla_cli.core.nav.route import Place

    calls: list = []
    monkeypatch.setattr(nav_cmd, "_dispatch_share", lambda vin, addr: calls.append((vin, addr)))
    isolated_nav.save_place(Place(alias="home", raw_address="Calle 1 # 2-3, Bogotá"))

    r = run_cli("nav", "place", "send", "home", "--dry-run")
    assert r.exit_code == 0, r.output
    assert "Would send" in r.output
    assert calls == []


def test_place_send_invokes_dispatch(isolated_nav, monkeypatch):
    from tesla_cli.cli.commands import nav as nav_cmd
    from tesla_cli.core.nav.route import Place

    calls: list = []
    monkeypatch.setattr(nav_cmd, "_dispatch_share", lambda vin, addr: calls.append((vin, addr)))
    monkeypatch.setattr(nav_cmd, "_vin", lambda v: "5YJ3E1EA1PF000001")
    isolated_nav.save_place(Place(alias="home", raw_address="Calle 1 # 2-3, Bogotá"))

    r = run_cli("nav", "place", "send", "home")
    assert r.exit_code == 0, r.output
    assert len(calls) == 1
    assert calls[0] == ("5YJ3E1EA1PF000001", "Calle 1 # 2-3, Bogotá")


def test_place_send_missing_alias(isolated_nav):
    r = run_cli("nav", "place", "send", "nope")
    assert r.exit_code == 1
    assert "No place" in r.output


def test_place_send_lat_lon_fallback(isolated_nav, monkeypatch):
    from tesla_cli.cli.commands import nav as nav_cmd
    from tesla_cli.core.nav.route import Place

    monkeypatch.setattr(nav_cmd, "_dispatch_share", lambda vin, addr: None)
    isolated_nav.save_place(Place(alias="x", raw_address="", lat=4.7, lon=-74.0))

    r = run_cli("nav", "place", "send", "x", "--dry-run")
    assert r.exit_code == 0, r.output
    assert "4.7" in r.output
    assert "-74.0" in r.output


def test_dispatch_share_uses_send_place(monkeypatch):
    """_dispatch_share must delegate to send_place via _with_wake's lambda."""
    import tesla_cli.core.nav.dispatch as dispatch_mod
    from tesla_cli.cli.commands import nav as nav_cmd

    send_calls: list = []

    def fake_send_place(backend, vin, address, locale="en-US"):
        send_calls.append((backend, vin, address))

    monkeypatch.setattr(dispatch_mod, "send_place", fake_send_place)

    # Fake _with_wake: immediately invoke the lambda with a mock backend + vin
    fake_backend = object()

    def fake_with_wake(fn, vin):
        fn(fake_backend, vin)

    monkeypatch.setattr(nav_cmd, "_with_wake", fake_with_wake)

    nav_cmd._dispatch_share("VIN123", "Test Address")

    assert len(send_calls) == 1
    assert send_calls[0] == (fake_backend, "VIN123", "Test Address")
