"""GPX + KML export for planned routes.

Stdlib-only (no lxml dep). Uses explicit string templates with XML-escaping
so the serialized output is stable and diffable. Both formats emit origin,
each charger stop as a waypoint, and the destination — with a description
that includes SoC and power info when available.
"""

from __future__ import annotations

from xml.sax.saxutils import escape as _xml_escape

from tesla_cli.core.planner.models import ChargerSuggestion, PlannedRoute


def _esc(text: str) -> str:
    """Escape text for safe embedding in XML element content + attributes."""
    return _xml_escape(text, {'"': "&quot;", "'": "&apos;"})


def _stop_description(s: ChargerSuggestion) -> str:
    """Plain-text description for a charging stop — SoC + power info when set."""
    parts: list[str] = []
    if s.max_power_kw is not None:
        parts.append(f"max {s.max_power_kw:.0f} kW")
    if s.network:
        parts.append(f"network: {s.network}")
    if s.arrival_soc_kwh is not None:
        parts.append(f"arrival SoC: {s.arrival_soc_kwh:.1f} kWh")
    if s.departure_soc_kwh is not None:
        parts.append(f"departure SoC: {s.departure_soc_kwh:.1f} kWh")
    if s.charge_duration_min is not None:
        parts.append(f"charge: {s.charge_duration_min} min")
    if s.soc_warning:
        parts.append(f"WARNING: {s.soc_warning}")
    return "; ".join(parts)


def to_gpx(plan: PlannedRoute) -> str:
    """Serialize a PlannedRoute to GPX 1.1 XML.

    Uses <wpt> for origin + each stop + destination, plus a <rte> connecting
    them in order. Matches the GPX 1.1 schema.
    """
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="tesla-cli" '
        'xmlns="http://www.topografix.com/GPX/1/1">',
        "  <metadata>",
        f"    <name>{_esc(plan.origin_address)} to {_esc(plan.destination_address)}</name>",
        f"    <time>{_esc(plan.planned_at)}</time>",
        "  </metadata>",
    ]

    # Origin waypoint
    olat, olon = plan.origin_latlon
    lines.append(f'  <wpt lat="{olat:.6f}" lon="{olon:.6f}">')
    lines.append(f"    <name>{_esc(plan.origin_address)}</name>")
    lines.append("    <type>origin</type>")
    lines.append("  </wpt>")

    # Intermediate charging stops
    for s in plan.stops:
        lines.append(f'  <wpt lat="{s.lat:.6f}" lon="{s.lon:.6f}">')
        lines.append(f"    <name>{_esc(s.name)}</name>")
        desc = _stop_description(s)
        if desc:
            lines.append(f"    <desc>{_esc(desc)}</desc>")
        lines.append("    <type>charger</type>")
        lines.append("  </wpt>")

    # Destination waypoint
    dlat, dlon = plan.destination_latlon
    lines.append(f'  <wpt lat="{dlat:.6f}" lon="{dlon:.6f}">')
    lines.append(f"    <name>{_esc(plan.destination_address)}</name>")
    lines.append("    <type>destination</type>")
    lines.append("  </wpt>")

    # Route linking origin → stops → destination in order
    lines.append("  <rte>")
    lines.append(
        f"    <name>{_esc(plan.origin_address)} to {_esc(plan.destination_address)}</name>"
    )
    lines.append(f'    <rtept lat="{olat:.6f}" lon="{olon:.6f}">')
    lines.append(f"      <name>{_esc(plan.origin_address)}</name>")
    lines.append("    </rtept>")
    for s in plan.stops:
        lines.append(f'    <rtept lat="{s.lat:.6f}" lon="{s.lon:.6f}">')
        lines.append(f"      <name>{_esc(s.name)}</name>")
        lines.append("    </rtept>")
    lines.append(f'    <rtept lat="{dlat:.6f}" lon="{dlon:.6f}">')
    lines.append(f"      <name>{_esc(plan.destination_address)}</name>")
    lines.append("    </rtept>")
    lines.append("  </rte>")
    lines.append("</gpx>")
    return "\n".join(lines) + "\n"


def to_kml(plan: PlannedRoute) -> str:
    """Serialize a PlannedRoute to KML 2.2 XML.

    Each waypoint is a <Placemark> with <Point><coordinates>; the full route
    is also drawn as a <LineString> so viewers like Google Earth show it.
    """
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "  <Document>",
        f"    <name>{_esc(plan.origin_address)} to {_esc(plan.destination_address)}</name>",
        f"    <description>Planned by tesla-cli at {_esc(plan.planned_at)}</description>",
    ]

    olat, olon = plan.origin_latlon
    dlat, dlon = plan.destination_latlon

    # Origin placemark
    lines.append("    <Placemark>")
    lines.append(f"      <name>{_esc(plan.origin_address)}</name>")
    lines.append("      <description>origin</description>")
    lines.append("      <Point>")
    # KML uses lon,lat ordering
    lines.append(f"        <coordinates>{olon:.6f},{olat:.6f},0</coordinates>")
    lines.append("      </Point>")
    lines.append("    </Placemark>")

    # Stop placemarks
    for s in plan.stops:
        lines.append("    <Placemark>")
        lines.append(f"      <name>{_esc(s.name)}</name>")
        desc = _stop_description(s) or "charger"
        lines.append(f"      <description>{_esc(desc)}</description>")
        lines.append("      <Point>")
        lines.append(f"        <coordinates>{s.lon:.6f},{s.lat:.6f},0</coordinates>")
        lines.append("      </Point>")
        lines.append("    </Placemark>")

    # Destination placemark
    lines.append("    <Placemark>")
    lines.append(f"      <name>{_esc(plan.destination_address)}</name>")
    lines.append("      <description>destination</description>")
    lines.append("      <Point>")
    lines.append(f"        <coordinates>{dlon:.6f},{dlat:.6f},0</coordinates>")
    lines.append("      </Point>")
    lines.append("    </Placemark>")

    # LineString for the route path
    lines.append("    <Placemark>")
    lines.append("      <name>Route</name>")
    lines.append("      <LineString>")
    lines.append("        <tessellate>1</tessellate>")
    coords: list[str] = [f"{olon:.6f},{olat:.6f},0"]
    for s in plan.stops:
        coords.append(f"{s.lon:.6f},{s.lat:.6f},0")
    coords.append(f"{dlon:.6f},{dlat:.6f},0")
    lines.append("        <coordinates>" + " ".join(coords) + "</coordinates>")
    lines.append("      </LineString>")
    lines.append("    </Placemark>")

    lines.append("  </Document>")
    lines.append("</kml>")
    return "\n".join(lines) + "\n"
