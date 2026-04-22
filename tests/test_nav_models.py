"""Tests for tesla_cli.core.nav.route (models + NavStore)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tesla_cli.core.nav.route import NavStore, Place, Route, Waypoint


@pytest.fixture()
def store(tmp_path: Path) -> NavStore:
    return NavStore(
        nav_file=tmp_path / "nav.toml",
        state_file=tmp_path / "nav.state.toml",
    )


def _wp(label: str, lat: float, lon: float) -> Waypoint:
    return Waypoint(
        raw_address=label,
        lat=lat,
        lon=lon,
        geocode_provider="nominatim",
        geocode_at="2026-04-22T02:15:00Z",
    )


def test_route_roundtrip_persists_to_nav_toml(store: NavStore) -> None:
    route = Route(
        name="commute",
        created_at="2026-04-22T02:00:00Z",
        waypoints=[
            _wp("Calle 100 #19-54, Bogota", 4.6860, -74.0500),
            _wp("4.6487,-74.0672", 4.6487, -74.0672),
            _wp("Centro Andino", 4.6670, -74.0540),
        ],
    )
    store.save_route(route)

    roundtrip = store.get_route("commute")
    assert roundtrip is not None
    assert roundtrip.name == "commute"
    assert roundtrip.created_at == "2026-04-22T02:00:00Z"
    assert len(roundtrip.waypoints) == 3
    assert roundtrip.waypoints[1].lat == pytest.approx(4.6487)
    assert roundtrip.waypoints[1].lon == pytest.approx(-74.0672)
    assert roundtrip.waypoints[0].raw_address == "Calle 100 #19-54, Bogota"


def test_state_file_roundtrip(store: NavStore, tmp_path: Path) -> None:
    # initial write
    store.write_state("commute", next_index=1, last_dispatch_ts="2026-04-22T01:00:00Z")
    state = store.read_state("commute")
    assert state["next_index"] == 1
    assert state["last_dispatch_ts"] == "2026-04-22T01:00:00Z"

    # update (simulates an advance)
    store.write_state("commute", next_index=2, last_dispatch_ts="2026-04-22T01:23:45Z")
    state = store.read_state("commute")
    assert state["next_index"] == 2
    assert state["last_dispatch_ts"] == "2026-04-22T01:23:45Z"

    # atomic: no lingering .tmp file (fsync + rename completed cleanly)
    tmp_file = tmp_path / "nav.state.toml.tmp"
    assert not tmp_file.exists()

    # unknown route returns empty dict
    assert store.read_state("not-a-route") == {}


def test_delete_route_removes_entry(store: NavStore) -> None:
    route = Route(
        name="trip",
        created_at="2026-04-22T02:00:00Z",
        waypoints=[_wp("a", 1.0, 2.0)],
    )
    store.save_route(route)
    assert store.get_route("trip") is not None

    store.delete_route("trip")
    assert store.get_route("trip") is None

    # deleting a missing route is a no-op
    store.delete_route("not-a-route")
    assert store.get_route("not-a-route") is None


def test_place_save_list_delete(store: NavStore) -> None:
    store.save_place(Place(alias="home", raw_address="Calle 100 #19-54"))
    store.save_place(Place(alias="work", raw_address="Centro Andino"))

    places = {p.alias: p for p in store.list_places()}
    assert set(places) == {"home", "work"}
    assert places["home"].raw_address == "Calle 100 #19-54"

    got = store.get_place("home")
    assert got is not None and got.raw_address == "Calle 100 #19-54"

    store.delete_place("home")
    assert store.get_place("home") is None
    assert {p.alias for p in store.list_places()} == {"work"}


def test_list_routes_returns_all(store: NavStore) -> None:
    store.save_route(Route(name="a", created_at="2026-04-22T00:00:00Z", waypoints=[_wp("x", 1, 2)]))
    store.save_route(Route(name="b", created_at="2026-04-22T00:00:00Z", waypoints=[_wp("y", 3, 4)]))
    names = {r.name for r in store.list_routes()}
    assert names == {"a", "b"}
