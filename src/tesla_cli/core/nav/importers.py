"""Parsers for bulk-importing favorites from Google Takeout, KML, GPX into Place objects.
Pure functions — return list[Place], no I/O side effects beyond reading the input file."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tesla_cli.core.nav.route import Place

__all__ = [
    "slugify",
    "detect_and_parse",
    "parse_gpx",
    "parse_kml",
    "parse_takeout_csv",
    "parse_takeout_geojson",
]

_KML_NS = "http://www.opengis.net/kml/2.2"
_GPX_NS_1_1 = "http://www.topografix.com/GPX/1/1"
_GPX_NS_1_0 = "http://www.topografix.com/GPX/1/0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify(title: str, existing: set[str]) -> str:
    """Return a URL-safe alias derived from *title*, unique within *existing*.

    Algorithm
    ---------
    1. NFKD-normalize to strip accents.
    2. Lowercase.
    3. Replace any run of non-[a-z0-9] characters with a single ``-``.
    4. Strip leading/trailing ``-``.
    5. Truncate to 32 characters.
    6. Empty result → ``"place"``.
    7. On collision with *existing*: append ``-2``, ``-3`` … ``-99``
       (always truncate the *base* back to 32 chars before appending the suffix).
       Raise ``ValueError`` if all 98 suffixes are exhausted.
    """
    # 1. NFKD + strip combining marks to remove accents
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = "".join(c for c in normalized if not unicodedata.combining(c))

    # 2-4. lowercase → replace non-alnum runs → strip dashes
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")

    # 5-6. truncate / fallback
    base = slug[:32] if slug else "place"

    candidate = base
    if candidate not in existing:
        return candidate

    # 7. collision resolution
    for n in range(2, 100):
        suffix = f"-{n}"
        # truncate base so that base+suffix fits in 32 chars
        trimmed_base = base[: 32 - len(suffix)]
        candidate = trimmed_base + suffix
        if candidate not in existing:
            return candidate

    raise ValueError(f"slugify: exhausted 99 suffixes for base '{base}'")


def _check_file_size(path: Path, max_mb: int = 25) -> None:
    """Raise ValueError if *path* exceeds *max_mb* megabytes."""
    size = path.stat().st_size
    cap = max_mb * 1024 * 1024
    if size > cap:
        raise ValueError(f"file too large: {size} bytes > {max_mb} MB cap")


def _now_iso() -> str:
    """Return current UTC time formatted as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_latlon_from_url(url: str) -> tuple[float, float] | None:
    """Extract ``(lat, lon)`` from a Google Maps URL, or ``None`` if not found.

    Patterns supported
    ------------------
    * ``@lat,lon,zoom``  — Maps embed / place link
    * ``?q=lat,lon``     — simple query-string coords
    * ``!3dLAT!4dLON``  — protobuf-style encoding in path
    """
    if not url:
        return None

    # Pattern 1: @lat,lon (followed by comma + anything, or end)
    m = re.search(r"@(-?\d+\.?\d*),(-?\d+\.?\d*)", url)
    if m:
        return float(m.group(1)), float(m.group(2))

    # Pattern 2: ?q=lat,lon or &q=lat,lon
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    q_vals = qs.get("q", [])
    for val in q_vals:
        m2 = re.fullmatch(r"(-?\d+\.?\d*),(-?\d+\.?\d*)", val.strip())
        if m2:
            return float(m2.group(1)), float(m2.group(2))

    # Pattern 3: !3dLAT!4dLON
    m3 = re.search(r"!3d(-?\d+\.?\d*)!4d(-?\d+\.?\d*)", url)
    if m3:
        return float(m3.group(1)), float(m3.group(2))

    return None


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_takeout_csv(path: Path, list_name: str | None = None) -> list[Place]:
    """Parse a Google Takeout saved-places CSV into a list of :class:`Place` objects."""
    _check_file_size(path)

    tag_name = list_name if list_name is not None else path.stem
    now = _now_iso()
    places: list[Place] = []
    seen_aliases: set[str] = set()

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            title = (row.get("Title") or "").strip()
            url = (row.get("URL") or "").strip()

            latlon = _extract_latlon_from_url(url)
            if latlon is None:
                print(
                    f"no coords in URL for '{title}' — will need geocoding",
                    file=sys.stderr,
                )
                lat: float | None = None
                lon: float | None = None
            else:
                lat, lon = latlon

            source_id = url if url else f"csv:{title}:{path.name}"
            alias = slugify(title, seen_aliases)
            seen_aliases.add(alias)

            places.append(
                Place(
                    alias=alias,
                    raw_address=title,
                    lat=lat,
                    lon=lon,
                    tags=[tag_name],
                    source="google-takeout-csv",
                    source_id=source_id,
                    imported_at=now,
                )
            )

    return places


def parse_takeout_geojson(path: Path) -> list[Place]:
    """Parse a Google Takeout GeoJSON FeatureCollection into Place objects."""
    _check_file_size(path)

    with path.open(encoding="utf-8") as fh:
        doc = json.load(fh)

    features = doc.get("features", [])
    if not features:
        return []

    now = _now_iso()
    places: list[Place] = []
    seen_aliases: set[str] = set()

    for feature in features:
        props = feature.get("properties") or {}
        geom = feature.get("geometry") or {}

        title = props.get("Title") or props.get("title") or "place"

        url = props.get("Google Maps URL") or props.get("google_maps_url") or ""

        loc = props.get("Location")
        if isinstance(loc, dict):
            address = loc.get("Address") or title
        else:
            address = props.get("Address") or title

        # GeoJSON convention: coordinates = [lon, lat]
        coords = geom.get("coordinates")
        if coords and len(coords) >= 2:
            lon_val: float | None = float(coords[0])
            lat_val: float | None = float(coords[1])
        else:
            lat_val = None
            lon_val = None

        source_id = url or f"geojson:{title}"
        alias = slugify(str(title), seen_aliases)
        seen_aliases.add(alias)

        places.append(
            Place(
                alias=alias,
                raw_address=address,
                lat=lat_val,
                lon=lon_val,
                tags=None,
                source="google-takeout-geojson",
                source_id=source_id,
                imported_at=now,
            )
        )

    return places


def parse_kml(path: Path) -> list[Place]:
    """Parse a KML file into Place objects."""
    _check_file_size(path)

    tree = ET.parse(path)  # noqa: S314  (stdlib ET, safe for trusted input)
    root = tree.getroot()
    ns = _KML_NS
    tag = f"{{{ns}}}"

    now = _now_iso()
    places: list[Place] = []
    seen_aliases: set[str] = set()

    for placemark in root.iter(f"{tag}Placemark"):
        name_el = placemark.find(f"{tag}name")
        name = name_el.text.strip() if (name_el is not None and name_el.text) else "place"

        lat_val: float | None = None
        lon_val: float | None = None
        point_el = placemark.find(f"{tag}Point")
        if point_el is not None:
            coords_el = point_el.find(f"{tag}coordinates")
            if coords_el is not None and coords_el.text:
                parts = coords_el.text.strip().split(",")
                if len(parts) >= 2:
                    try:
                        lon_val = float(parts[0])
                        lat_val = float(parts[1])
                    except ValueError:
                        pass

        placemark_id = placemark.get("id")
        if not placemark_id:
            raw = f"{name}{lat_val}{lon_val}".encode()
            placemark_id = hashlib.sha1(raw).hexdigest()[:16]  # noqa: S324

        alias = slugify(name, seen_aliases)
        seen_aliases.add(alias)

        places.append(
            Place(
                alias=alias,
                raw_address=name,
                lat=lat_val,
                lon=lon_val,
                tags=None,
                source="kml",
                source_id=placemark_id,
                imported_at=now,
            )
        )

    return places


def parse_gpx(path: Path) -> list[Place]:
    """Parse a GPX file (waypoints only) into Place objects."""
    _check_file_size(path)

    tree = ET.parse(path)  # noqa: S314
    root = tree.getroot()

    # Detect namespace from root tag
    ns = _GPX_NS_1_1
    if _GPX_NS_1_0 in (root.tag or ""):
        ns = _GPX_NS_1_0
    tag = f"{{{ns}}}"

    now = _now_iso()
    places: list[Place] = []
    seen_aliases: set[str] = set()

    for wpt in root.iter(f"{tag}wpt"):
        try:
            lat_val: float | None = float(wpt.get("lat", ""))
            lon_val: float | None = float(wpt.get("lon", ""))
        except (ValueError, TypeError):
            lat_val = None
            lon_val = None

        name_el = wpt.find(f"{tag}name")
        name = name_el.text.strip() if (name_el is not None and name_el.text) else "place"

        raw = f"{name}{lat_val}{lon_val}".encode()
        source_id = hashlib.sha1(raw).hexdigest()[:16]  # noqa: S324

        alias = slugify(name, seen_aliases)
        seen_aliases.add(alias)

        places.append(
            Place(
                alias=alias,
                raw_address=name,
                lat=lat_val,
                lon=lon_val,
                tags=None,
                source="gpx",
                source_id=source_id,
                imported_at=now,
            )
        )

    return places


def detect_and_parse(path: Path, list_name: str | None = None) -> list[Place]:
    """Dispatch to the correct parser based on file extension."""
    ext = path.suffix.lower()
    if ext == ".csv":
        return parse_takeout_csv(path, list_name)
    if ext in {".json", ".geojson"}:
        return parse_takeout_geojson(path)
    if ext == ".kml":
        return parse_kml(path)
    if ext == ".gpx":
        return parse_gpx(path)
    raise ValueError(f"unsupported extension: {path.suffix}")
