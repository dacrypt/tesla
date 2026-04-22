"""Tests for tesla_cli.core.nav.route (models + NavStore)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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


# ---- Place extended fields ----


def test_place_minimal_roundtrip(store: NavStore) -> None:
    """Place with only alias+raw_address round-trips; no extra fields written to TOML."""
    place = Place(alias="x", raw_address="y")
    store.save_place(place)

    got = store.get_place("x")
    assert got is not None
    assert got.alias == "x"
    assert got.raw_address == "y"
    assert got.lat is None
    assert got.lon is None
    assert got.tags is None
    assert got.source is None
    assert got.source_id is None
    assert got.imported_at is None

    # Verify the TOML file contains no null/None entries for optional fields
    raw = store.nav_file.read_text()
    assert "lat" not in raw
    assert "source" not in raw


def test_place_full_roundtrip(store: NavStore) -> None:
    """Place with all 8 fields round-trips correctly."""
    place = Place(
        alias="casa",
        raw_address="Calle 100 #19-54, Bogota",
        lat=4.6860,
        lon=-74.0500,
        tags=["home", "frequent"],
        source="google-takeout-csv",
        source_id="https://maps.google.com/?cid=123",
        imported_at="2026-04-22T00:00:00Z",
    )
    store.save_place(place)

    got = store.get_place("casa")
    assert got is not None
    assert got.alias == "casa"
    assert got.raw_address == "Calle 100 #19-54, Bogota"
    assert got.lat == pytest.approx(4.6860)
    assert got.lon == pytest.approx(-74.0500)
    assert got.tags == ["home", "frequent"]
    assert got.source == "google-takeout-csv"
    assert got.source_id == "https://maps.google.com/?cid=123"
    assert got.imported_at == "2026-04-22T00:00:00Z"


def test_old_toml_loads_without_error(store: NavStore) -> None:
    """Old-format TOML with only alias+raw_address loads into extended Place without error."""
    # Hand-craft a minimal TOML that pre-dates the extended model
    store.nav_file.parent.mkdir(parents=True, exist_ok=True)
    store.nav_file.write_text(
        '[places.home]\nalias = "home"\nraw_address = "Calle 50"\n\n'
        '[places.work]\nalias = "work"\nraw_address = "Centro Andino"\n'
    )

    places = {p.alias: p for p in store.list_places()}
    assert set(places) == {"home", "work"}
    assert places["home"].raw_address == "Calle 50"
    assert places["home"].lat is None
    assert places["home"].source is None

    got = store.get_place("work")
    assert got is not None
    assert got.source_id is None


# ---- save_places_bulk ----


def test_save_places_bulk_idempotent(store: NavStore) -> None:
    """Bulk saving the same list twice yields (0, N, 0) on the second call."""
    places = [
        Place(alias="a", raw_address="Addr A", source="kml", source_id="id-a"),
        Place(alias="b", raw_address="Addr B", source="kml", source_id="id-b"),
    ]
    first = store.save_places_bulk(places)
    assert first == (2, 0, 0)

    second = store.save_places_bulk(places)
    assert second == (0, 2, 0)

    # Data unchanged
    assert store.get_place("a") is not None
    assert store.get_place("b") is not None


def test_bulk_dedupe_by_source_id(store: NavStore, capsys: pytest.CaptureFixture) -> None:
    """Two imports with same (source, source_id) but different alias: second updates first;
    original alias is preserved and a warning is printed."""
    first_import = [Place(alias="original", raw_address="Addr", source="kml", source_id="sid-1")]
    store.save_places_bulk(first_import)

    second_import = [
        Place(alias="renamed", raw_address="Addr Updated", source="kml", source_id="sid-1")
    ]
    counts = store.save_places_bulk(second_import)
    assert counts == (0, 1, 0)

    # Original alias preserved
    got = store.get_place("original")
    assert got is not None
    assert got.raw_address == "Addr Updated"

    # Renamed alias should NOT exist as a new entry
    assert store.get_place("renamed") is None

    # Warning printed to stderr
    captured = capsys.readouterr()
    assert "warning" in captured.err
    assert "original" in captured.err


def test_bulk_skips_hand_created_collision(
    store: NavStore, capsys: pytest.CaptureFixture
) -> None:
    """Importing a place whose alias matches a hand-created place is skipped with warning."""
    # Pre-save a hand-created place (no source)
    store.save_place(Place(alias="casa", raw_address="My Home"))

    import_list = [Place(alias="casa", raw_address="Some Other Addr", source="kml", source_id="x")]
    counts = store.save_places_bulk(import_list)
    assert counts == (0, 0, 1)

    # Hand-created entry unchanged
    got = store.get_place("casa")
    assert got is not None
    assert got.raw_address == "My Home"
    assert got.source is None

    captured = capsys.readouterr()
    assert "skipped" in captured.err
    assert "casa" in captured.err


def test_bulk_uses_alias_match_for_no_source(store: NavStore) -> None:
    """Bulk-saving a Place(source=None) twice updates, not duplicates."""
    place = Place(alias="x", raw_address="First")
    first = store.save_places_bulk([place])
    assert first == (1, 0, 0)

    place2 = Place(alias="x", raw_address="Updated")
    second = store.save_places_bulk([place2])
    assert second == (0, 1, 0)

    # Only one entry, updated
    all_places = store.list_places()
    assert len([p for p in all_places if p.alias == "x"]) == 1
    assert store.get_place("x").raw_address == "Updated"  # type: ignore[union-attr]


def test_atomic_write_via_existing_helper(store: NavStore, tmp_path: Path) -> None:
    """save_places_bulk leaves original file intact if serialization raises mid-bulk."""
    import tomli_w

    # Pre-populate with one place
    store.nav_file.parent.mkdir(parents=True, exist_ok=True)
    store.nav_file.write_text('[places.existing]\nalias = "existing"\nraw_address = "Safe"\n')
    original_content = store.nav_file.read_text()

    places = [Place(alias="new", raw_address="New Addr")]

    with patch.object(tomli_w, "dumps", side_effect=RuntimeError("boom")), pytest.raises(
        RuntimeError, match="boom"
    ):
        store.save_places_bulk(places)

    # Original file must be unchanged
    assert store.nav_file.read_text() == original_content
    # No .tmp file lingering
    assert not store.nav_file.with_suffix(store.nav_file.suffix + ".tmp").exists()
