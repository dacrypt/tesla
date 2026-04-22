"""Route / Waypoint / Place models and on-disk TOML store.

Persistence layout:
    ~/.tesla-cli/nav.toml        — routes + places (source of truth)
    ~/.tesla-cli/nav.state.toml  — run-time next_index counters for `route next`

Atomic write protocol (both files):
    1. Serialize to `<path>.tmp`
    2. `fsync()` the fd
    3. Close
    4. `os.rename(<path>.tmp, <path>)`
No lockfile — tesla-cli is single-user.
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import tomli_w

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


NAV_DIR = Path.home() / ".tesla-cli"
NAV_FILE = NAV_DIR / "nav.toml"
NAV_STATE_FILE = NAV_DIR / "nav.state.toml"


@dataclass
class Waypoint:
    raw_address: str
    lat: float
    lon: float
    geocode_provider: str  # "nominatim" | "user"
    geocode_at: str  # ISO-8601 UTC, e.g. "2026-04-22T02:15:00Z"


@dataclass
class Route:
    name: str
    waypoints: list[Waypoint]
    created_at: str  # ISO-8601 UTC
    source: str | None = None  # "native-planner", "abrp", or None for hand-created
    source_id: str | None = None  # stable id for dedupe (e.g. "{origin}→{dest}@{car_model}")


@dataclass
class Place:
    alias: str
    raw_address: str
    lat: float | None = None
    lon: float | None = None
    tags: list[str] | None = None
    source: str | None = None  # "google-takeout-csv", "google-takeout-geojson", "kml", "gpx", or None
    source_id: str | None = None  # stable id from source (URL, hash); for dedupe
    imported_at: str | None = None  # ISO-8601 UTC


def _atomic_write(path: Path, payload: dict) -> None:
    """Serialize payload as TOML to <path>.tmp, fsync, rename over path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    encoded = tomli_w.dumps(payload).encode("utf-8")
    # open with O_CREAT|O_WRONLY|O_TRUNC so we own the fd and can fsync
    fd = os.open(tmp_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
    try:
        os.write(fd, encoded)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rename(tmp_path, path)


def _read_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text())


class NavStore:
    """Reads/writes ~/.tesla-cli/nav.toml and ~/.tesla-cli/nav.state.toml."""

    def __init__(
        self,
        nav_file: Path | None = None,
        state_file: Path | None = None,
    ) -> None:
        # Resolve module-level constants at call time so monkeypatched
        # paths (tests) are honored by callers that don't pass explicit files.
        import tesla_cli.core.nav.route as _self

        self.nav_file = nav_file if nav_file is not None else _self.NAV_FILE
        self.state_file = state_file if state_file is not None else _self.NAV_STATE_FILE

    # ---- routes ----

    def save_route(self, route: Route) -> None:
        """Save a route. Dedupe rule: if incoming route.source is not None and the
        existing entry with the same name has source=None (hand-created), SKIP
        with a stderr warning — imported/planned routes never overwrite
        hand-created ones.
        """
        data = _read_toml(self.nav_file)
        routes = data.get("routes", {})
        existing = routes.get(route.name)
        if (
            existing is not None
            and route.source is not None
            and existing.get("source") is None
        ):
            print(
                f"skipped saving route '{route.name}' — collides with hand-created route",
                file=sys.stderr,
            )
            return
        # Serialize all non-None fields; waypoints are always present.
        entry: dict = {
            "name": route.name,
            "created_at": route.created_at,
            "waypoints": [asdict(w) for w in route.waypoints],
        }
        if route.source is not None:
            entry["source"] = route.source
        if route.source_id is not None:
            entry["source_id"] = route.source_id
        routes[route.name] = entry
        data["routes"] = routes
        _atomic_write(self.nav_file, data)

    def get_route(self, name: str) -> Route | None:
        data = _read_toml(self.nav_file)
        entry = data.get("routes", {}).get(name)
        if entry is None:
            return None
        return Route(
            name=entry["name"],
            created_at=entry["created_at"],
            waypoints=[Waypoint(**w) for w in entry["waypoints"]],
            source=entry.get("source"),
            source_id=entry.get("source_id"),
        )

    def list_routes(self) -> list[Route]:
        data = _read_toml(self.nav_file)
        out: list[Route] = []
        for entry in data.get("routes", {}).values():
            out.append(
                Route(
                    name=entry["name"],
                    created_at=entry["created_at"],
                    waypoints=[Waypoint(**w) for w in entry["waypoints"]],
                    source=entry.get("source"),
                    source_id=entry.get("source_id"),
                )
            )
        return out

    def delete_route(self, name: str) -> None:
        data = _read_toml(self.nav_file)
        routes = data.get("routes", {})
        if name in routes:
            del routes[name]
            data["routes"] = routes
            _atomic_write(self.nav_file, data)

    # ---- places ----

    def save_place(self, place: Place) -> None:
        data = _read_toml(self.nav_file)
        places = data.get("places", {})
        places[place.alias] = {k: v for k, v in asdict(place).items() if v is not None}
        data["places"] = places
        _atomic_write(self.nav_file, data)

    def get_place(self, alias: str) -> Place | None:
        data = _read_toml(self.nav_file)
        entry = data.get("places", {}).get(alias)
        if entry is None:
            return None
        return Place(
            alias=entry["alias"],
            raw_address=entry["raw_address"],
            lat=entry.get("lat"),
            lon=entry.get("lon"),
            tags=entry.get("tags"),
            source=entry.get("source"),
            source_id=entry.get("source_id"),
            imported_at=entry.get("imported_at"),
        )

    def list_places(self) -> list[Place]:
        data = _read_toml(self.nav_file)
        return [
            Place(
                alias=e["alias"],
                raw_address=e["raw_address"],
                lat=e.get("lat"),
                lon=e.get("lon"),
                tags=e.get("tags"),
                source=e.get("source"),
                source_id=e.get("source_id"),
                imported_at=e.get("imported_at"),
            )
            for e in data.get("places", {}).values()
        ]

    def save_places_bulk(self, places: list[Place]) -> tuple[int, int, int]:
        """Bulk-save places. Returns (imported, updated, skipped).

        Dedupe rules:
        - If incoming place has source AND source_id → match existing entries by (source, source_id).
          On match: update in place; preserve original alias to avoid breaking user shortcuts
          (warn to stderr if alias differs).
        - Otherwise (hand-created or legacy entries with no source) → fall back to alias-match.
        - If imported entry's slug collides with an existing HAND-CREATED entry (existing.source is None
          AND incoming.source is not None) → skip the import for that entry, emit stderr warning
          "skipped 'X' — alias collides with hand-created place".

        Single read-modify-write cycle via _atomic_write (rename-over). Partial-failure mid-bulk
        leaves the original nav.toml intact.
        """
        data = _read_toml(self.nav_file)
        places_data: dict[str, dict] = data.get("places", {})

        # Build reverse index: (source, source_id) -> alias for existing imported entries
        source_index: dict[tuple[str, str], str] = {}
        for alias, entry in places_data.items():
            src = entry.get("source")
            sid = entry.get("source_id")
            if src is not None and sid is not None:
                source_index[(src, sid)] = alias

        imported = 0
        updated = 0
        skipped = 0

        for place in places:
            serialized = {k: v for k, v in asdict(place).items() if v is not None}

            if place.source is not None and place.source_id is not None:
                # Match by (source, source_id)
                key = (place.source, place.source_id)
                if key in source_index:
                    existing_alias = source_index[key]
                    if existing_alias != place.alias:
                        print(
                            f"warning: alias changed from '{existing_alias}' to '{place.alias}'"
                            f" for source_id '{place.source_id}' — preserving original alias",
                            file=sys.stderr,
                        )
                    # Update in place under the original alias
                    serialized["alias"] = existing_alias
                    places_data[existing_alias] = serialized
                    updated += 1
                else:
                    # New imported entry — check for alias collision with hand-created place
                    if place.alias in places_data and places_data[place.alias].get("source") is None:
                        print(
                            f"skipped '{place.alias}' — alias collides with hand-created place",
                            file=sys.stderr,
                        )
                        skipped += 1
                    else:
                        places_data[place.alias] = serialized
                        source_index[key] = place.alias
                        imported += 1
            else:
                # Fall back to alias-match
                if place.alias in places_data:
                    places_data[place.alias] = serialized
                    updated += 1
                else:
                    places_data[place.alias] = serialized
                    imported += 1

        data["places"] = places_data
        _atomic_write(self.nav_file, data)
        return (imported, updated, skipped)

    def delete_place(self, alias: str) -> None:
        data = _read_toml(self.nav_file)
        places = data.get("places", {})
        if alias in places:
            del places[alias]
            data["places"] = places
            _atomic_write(self.nav_file, data)

    # ---- state (next_index) ----

    def read_state(self, route_name: str) -> dict:
        """Return {"next_index": int, "last_dispatch_ts": str} or empty dict."""
        data = _read_toml(self.state_file)
        return dict(data.get(route_name, {}))

    def write_state(self, route_name: str, next_index: int, last_dispatch_ts: str) -> None:
        data = _read_toml(self.state_file)
        data[route_name] = {
            "next_index": next_index,
            "last_dispatch_ts": last_dispatch_ts,
        }
        _atomic_write(self.state_file, data)
