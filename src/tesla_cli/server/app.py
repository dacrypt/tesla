"""FastAPI application for tesla-cli API server."""

from __future__ import annotations

import asyncio
import json
import math
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from tesla_cli import __version__
from tesla_cli.backends import get_vehicle_backend
from tesla_cli.config import load_config, resolve_vin

# ── App factory ───────────────────────────────────────────────────────────────

def create_app(vin: str | None = None) -> FastAPI:
    app = FastAPI(
        title="tesla-cli API",
        description="REST API for Tesla vehicle control and monitoring.",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API Key auth middleware (no-op when key not configured)
    from tesla_cli.server.auth import ApiKeyMiddleware
    cfg0 = load_config()
    app.add_middleware(ApiKeyMiddleware, api_key=cfg0.server.api_key)

    # Store resolved VIN in app state
    app.state.override_vin = vin

    # ── Register routes ───────────────────────────────────────────────────────
    from tesla_cli.server.routes.charge import router as charge_router
    from tesla_cli.server.routes.climate import router as climate_router
    from tesla_cli.server.routes.order import router as order_router
    from tesla_cli.server.routes.teslaMate import router as teslaMate_router
    from tesla_cli.server.routes.vehicle import router as vehicle_router

    app.include_router(vehicle_router,   prefix="/api/vehicle",    tags=["Vehicle"])
    app.include_router(charge_router,    prefix="/api/charge",     tags=["Charge"])
    app.include_router(climate_router,   prefix="/api/climate",    tags=["Climate"])
    app.include_router(order_router,     prefix="/api/order",      tags=["Order"])
    app.include_router(teslaMate_router, prefix="/api/teslaMate",  tags=["TeslaMate"])

    # ── System endpoints ──────────────────────────────────────────────────────

    @app.get("/api/status", tags=["System"])
    def api_status(request: Request) -> dict:
        cfg = load_config()
        return {
            "version":  __version__,
            "backend":  cfg.general.backend,
            "vin":      cfg.general.default_vin,
            "server":   "tesla-cli API",
        }

    @app.get("/api/vehicles", tags=["System"])
    def api_vehicles() -> list:
        """List all configured vehicles (aliases + default VIN)."""
        cfg = load_config()
        vehicles = []
        # Always include the default VIN first
        default = cfg.general.default_vin
        if default:
            vehicles.append({"vin": default, "alias": "default", "is_default": True})
        # Add any aliases that are different from the default
        for alias, vin in cfg.vehicles.aliases.items():
            if vin != default:
                vehicles.append({"vin": vin, "alias": alias, "is_default": False})
        return vehicles

    @app.get("/api/config", tags=["System"])
    def api_config() -> dict:
        cfg = load_config()
        return {
            "backend":          cfg.general.backend,
            "default_vin":      cfg.general.default_vin,
            "cost_per_kwh":     cfg.general.cost_per_kwh,
            "teslaMate_url":    bool(cfg.teslaMate.database_url),
            "ha_url":           cfg.home_assistant.url,
            "abrp_configured":  bool(cfg.abrp.user_token),
            "geofences":        list(cfg.geofences.zones.keys()),
            "notifications":    cfg.notifications.enabled,
            "vehicles":         cfg.vehicles.aliases,
            "auth_enabled":     bool(cfg.server.api_key),
        }

    # ── Provider registry endpoints ───────────────────────────────────────────

    @app.get("/api/providers", tags=["System"])
    def api_providers() -> list:
        """Ecosystem provider status — availability and capabilities."""
        from tesla_cli.providers import get_registry
        return get_registry().status()

    @app.get("/api/providers/capabilities", tags=["System"])
    def api_provider_capabilities() -> dict:
        """Capability map — which providers serve which capabilities."""
        from tesla_cli.providers import get_registry
        from tesla_cli.providers.base import Capability
        registry = get_registry()
        out = {}
        for cap in sorted(Capability.all()):
            available = [p.name for p in registry.for_capability(cap)]
            all_p     = [p.name for p in registry.for_capability(cap, available_only=False)]
            out[cap]  = {"available": available, "all": all_p}
        return out

    # ── Geofences endpoint ────────────────────────────────────────────────────

    @app.get("/api/geofences", tags=["Geofences"])
    def api_geofences() -> list:
        """Return all configured geofence zones."""
        cfg = load_config()
        return [
            {"name": name, **zone}
            for name, zone in cfg.geofences.zones.items()
        ]

    # ── Prometheus metrics endpoint ──────────────────────────────────────────

    @app.get("/api/metrics", tags=["System"])
    def api_metrics(request: Request):
        """Prometheus text format metrics — battery level, range, odometer, etc.

        Designed to be scraped by Prometheus or read by Grafana.
        Returns 200 with text/plain; set=0.0.4 even if vehicle is unreachable
        (uses stale/empty values rather than error).
        """
        from fastapi.responses import PlainTextResponse

        cfg = load_config()
        v   = resolve_vin(cfg, app.state.override_vin)

        # Try to get fresh data; fall back to empty on any error
        try:
            backend = get_vehicle_backend(cfg)
            data = backend.get_vehicle_data(v)
        except Exception:  # noqa: BLE001
            data = {}

        cs = data.get("charge_state") or {}
        ds = data.get("drive_state")  or {}
        vs = data.get("vehicle_state") or {}

        def _g(name: str, help_text: str, value, labels: str = "") -> str:
            lbl = f'{{vin="{v}"{", " + labels if labels else ""}}}'
            val = float(value) if value is not None else float("nan")
            # Prometheus uses NaN for missing; but many exporters use 0 — use NaN for clarity
            val_str = str(val) if val == val else "NaN"
            return f"# HELP {name} {help_text}\n# TYPE {name} gauge\n{name}{lbl} {val_str}\n"

        lines = [
            _g("tesla_battery_level",   "Battery level percent",         cs.get("battery_level")),
            _g("tesla_battery_range",   "Estimated range in miles",       cs.get("battery_range")),
            _g("tesla_charge_limit",    "Charge limit SoC percent",       cs.get("charge_limit_soc")),
            _g("tesla_charger_power",   "Charger power in kW",            cs.get("charger_power")),
            _g("tesla_energy_added",    "Energy added in kWh this session",cs.get("charge_energy_added")),
            _g("tesla_odometer",        "Odometer in miles",              vs.get("odometer")),
            _g("tesla_speed",           "Vehicle speed in mph",           ds.get("speed")),
            _g("tesla_latitude",        "Vehicle latitude",               ds.get("latitude")),
            _g("tesla_longitude",       "Vehicle longitude",              ds.get("longitude")),
            _g("tesla_locked",          "Doors locked (1=locked 0=unlocked)", int(bool(vs.get("locked"))) if vs.get("locked") is not None else None),
            _g("tesla_sentry_mode",     "Sentry mode active (1=on 0=off)",    int(bool(vs.get("sentry_mode"))) if vs.get("sentry_mode") is not None else None),
        ]

        return PlainTextResponse("".join(lines), media_type="text/plain; version=0.0.4")

    @app.get("/api/config/validate", tags=["System"])
    def api_config_validate() -> dict:
        """Run config validation checks — same as `tesla config validate`.

        Returns {valid, errors, warnings, checks[]} suitable for a dashboard health widget.
        """
        from tesla_cli.commands.config_cmd import _run_config_checks
        cfg = load_config()
        checks = _run_config_checks(cfg)
        errors   = sum(1 for c in checks if c["status"] == "error")
        warnings = sum(1 for c in checks if c["status"] == "warn")
        return {"valid": errors == 0, "errors": errors, "warnings": warnings, "checks": checks}

    # ── Real-time SSE stream ──────────────────────────────────────────────────

    @app.get("/api/vehicle/stream", tags=["Vehicle"])
    async def vehicle_stream(
        request: Request,
        interval: int  = 10,
        fanout: bool   = False,
        topics: str    = "",
    ) -> StreamingResponse:
        """Server-Sent Events stream of live vehicle data.

        Query params:
        - `interval` — polling interval in seconds (default 10)
        - `fanout` — also push each tick to ABRP + Home Assistant
        - `topics` — comma-separated filter: `geofence`, `battery`, `climate`, `drive`, `location`

        Event types:
        - `vehicle`  — full vehicle state snapshot (always emitted)
        - `battery`  — charge_state snapshot (when `topics` includes `battery`)
        - `climate`  — climate_state snapshot (when `topics` includes `climate`)
        - `drive`    — drive_state snapshot (when `topics` includes `drive`)
        - `location` — {lat, lon, heading} (when `topics` includes `location`)
        - `geofence` — enter/exit zone event (when `topics` includes `geofence`)
        """
        cfg = load_config()
        v   = resolve_vin(cfg, app.state.override_vin)
        topic_set      = {t.strip() for t in topics.split(",") if t.strip()}
        want_geofence  = "geofence" in topic_set
        want_battery   = "battery"  in topic_set
        want_climate   = "climate"  in topic_set
        want_drive     = "drive"    in topic_set
        want_location  = "location" in topic_set
        geofence_state: dict[str, bool] = {}  # zone_name → was_inside

        async def _generate():
            nonlocal geofence_state
            backend = get_vehicle_backend(cfg)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: backend.get_vehicle_data(v)
                    )
                    ts = int(time.time())
                    payload = json.dumps({
                        "ts":   ts,
                        "data": _sanitize(data),
                    })
                    yield f"event: vehicle\ndata: {payload}\n\n"

                    # Fine-grained named topic events
                    if want_battery:
                        cs = data.get("charge_state") or {}
                        yield f"event: battery\ndata: {json.dumps({'ts': ts, 'data': _sanitize(cs)})}\n\n"

                    if want_climate:
                        cl = data.get("climate_state") or {}
                        yield f"event: climate\ndata: {json.dumps({'ts': ts, 'data': _sanitize(cl)})}\n\n"

                    if want_drive:
                        ds = data.get("drive_state") or {}
                        yield f"event: drive\ndata: {json.dumps({'ts': ts, 'data': _sanitize(ds)})}\n\n"

                    if want_location:
                        ds = data.get("drive_state") or {}
                        loc = {
                            "lat":     ds.get("latitude"),
                            "lon":     ds.get("longitude"),
                            "heading": ds.get("heading"),
                            "speed":   ds.get("speed"),
                        }
                        yield f"event: location\ndata: {json.dumps({'ts': ts, 'data': loc})}\n\n"

                    # Fan-out to all telemetry sinks if requested
                    if fanout:
                        await asyncio.get_event_loop().run_in_executor(
                            None, _fanout_telemetry, data, v, cfg
                        )

                    # Geofence crossing detection
                    if want_geofence:
                        drive = (
                            data.get("drive_state")
                            or data.get("response", {}).get("drive_state", {})
                        )
                        lat = drive.get("latitude") if isinstance(drive, dict) else None
                        lon = drive.get("longitude") if isinstance(drive, dict) else None
                        if lat is not None and lon is not None:
                            reload_cfg = load_config()
                            for name, zone in reload_cfg.geofences.zones.items():
                                dist   = _haversine_km(lat, lon, zone["lat"], zone["lon"])
                                inside = dist <= zone.get("radius_km", 0.5)
                                was_inside = geofence_state.get(name)
                                if was_inside is None:
                                    geofence_state[name] = inside
                                elif inside != was_inside:
                                    geofence_state[name] = inside
                                    event = "enter" if inside else "exit"
                                    gf_payload = json.dumps({
                                        "ts":      ts,
                                        "zone":    name,
                                        "event":   event,
                                        "lat":     lat,
                                        "lon":     lon,
                                        "dist_km": round(dist, 3),
                                    })
                                    yield f"event: geofence\ndata: {gf_payload}\n\n"

                except Exception as exc:  # noqa: BLE001
                    yield f"event: vehicle\ndata: {json.dumps({'error': str(exc)})}\n\n"
                await asyncio.sleep(interval)

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control":     "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Web UI ────────────────────────────────────────────────────────────────
    _static_dir = Path(__file__).parent / "static"

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def web_ui() -> str:
        html_file = _static_dir / "index.html"
        if html_file.exists():
            return html_file.read_text()
        return "<h1>tesla-cli API</h1><p><a href='/api/docs'>API Docs →</a></p>"

    @app.get("/manifest.json", include_in_schema=False)
    def pwa_manifest() -> JSONResponse:
        manifest = {
            "name":             "Tesla Dashboard",
            "short_name":       "Tesla",
            "description":      "tesla-cli vehicle dashboard",
            "start_url":        "/",
            "display":          "standalone",
            "background_color": "#0d0d0d",
            "theme_color":      "#e82127",
            "icons": [
                {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
            ],
        }
        return JSONResponse(manifest)

    # Serve remaining static files (sw.js, icons, etc.)
    if _static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    return app


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fanout_telemetry(data: dict, vin: str, cfg) -> None:
    """Push vehicle state to all configured telemetry/home-sync sinks."""
    from tesla_cli.providers.base import Capability
    from tesla_cli.providers.loader import build_registry
    registry = build_registry(cfg)
    registry.fanout(Capability.TELEMETRY_PUSH, "push", data=data, vin=vin)
    registry.fanout(Capability.HOME_SYNC,      "push", data=data, vin=vin)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two GPS points."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def _sanitize(data: Any) -> Any:
    """Recursively convert non-serializable values."""
    if isinstance(data, dict):
        return {k: _sanitize(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize(i) for i in data]
    try:
        json.dumps(data)
        return data
    except (TypeError, ValueError):
        return str(data)
