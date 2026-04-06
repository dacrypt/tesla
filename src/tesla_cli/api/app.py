"""FastAPI application for tesla-cli API server."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from tesla_cli import __version__
from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin

# ── App factory ───────────────────────────────────────────────────────────────


def _auto_provision_teslamate() -> None:
    """Install or start the managed TeslaMate stack if Docker is available."""
    log = logging.getLogger("tesla-cli.teslamate-auto")
    cfg = load_config()

    try:
        from tesla_cli.infra.teslamate_stack import TeslaMateStack

        stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
        stack.check_docker()
        stack.check_docker_compose()
    except Exception:
        return  # Docker not available — skip silently

    if cfg.teslaMate.managed and stack.is_installed():
        _ensure_teslamate_running(stack, log)
    elif not cfg.teslaMate.managed and not cfg.teslaMate.database_url:
        _auto_install_teslamate(stack, cfg, log)


def _ensure_teslamate_running(stack, log) -> None:
    """Start TeslaMate if installed but stopped, then sync tokens."""
    if not stack.is_running():
        log.info("TeslaMate stack installed but stopped — starting...")
        try:
            stack.start()
            log.info("TeslaMate stack started.")
        except Exception as exc:
            log.warning("Failed to start TeslaMate stack: %s", exc)
    # Always sync tokens from keyring → TeslaMate
    try:
        import time as _t

        _t.sleep(5)  # Wait for TeslaMate to be fully ready
        if stack.sync_tokens_from_keyring():
            log.info("Tesla tokens synced to TeslaMate.")
        else:
            log.debug("No tokens to sync or sync failed.")
    except Exception as exc:
        log.debug("Token sync skipped: %s", exc)


def _auto_install_teslamate(stack, cfg, log) -> None:
    """Install TeslaMate managed stack and update config."""
    log.info("TeslaMate not configured — auto-installing managed stack...")
    try:
        from tesla_cli.core.config import save_config

        ports = _find_free_ports(stack)
        result = stack.install(**ports)
        cfg = load_config()
        cfg.teslaMate.database_url = result["database_url"]
        cfg.teslaMate.managed = True
        cfg.teslaMate.stack_dir = result["stack_dir"]
        cfg.teslaMate.postgres_port = result["postgres_port"]
        cfg.teslaMate.grafana_port = result["grafana_port"]
        cfg.teslaMate.teslamate_port = result["teslamate_port"]
        cfg.teslaMate.mqtt_port = result["mqtt_port"]
        cfg.grafana.url = f"http://localhost:{result['grafana_port']}"
        cfg.mqtt.broker = "localhost"
        cfg.mqtt.port = result["mqtt_port"]
        save_config(cfg)
        health = "healthy" if result["healthy"] else "starting"
        log.info(
            "TeslaMate stack installed (%s). UI: http://localhost:%s  Grafana: http://localhost:%s",
            health,
            result["teslamate_port"],
            result["grafana_port"],
        )
        import time as _t

        _t.sleep(8)  # Wait for TeslaMate to fully start
        if stack.sync_tokens_from_keyring():
            log.info("Tesla tokens synced to TeslaMate after install.")
    except Exception as exc:
        log.warning("Auto-install of TeslaMate stack failed: %s", exc)


def _find_free_ports(stack) -> dict:
    """Find available ports for the TeslaMate stack services."""
    defaults = {
        "postgres_port": 5432,
        "grafana_port": 3000,
        "teslamate_port": 4000,
        "mqtt_port": 1883,
    }
    ports = {}
    for key, default in defaults.items():
        port = default
        while stack.port_in_use(port):
            port += 1
        ports[key] = port
    return ports


def _auto_refresh_sources() -> None:
    """Periodically refresh stale data sources."""
    import time as _t

    log = logging.getLogger("tesla-cli.sources-refresh")
    _t.sleep(60)  # Wait for server to be fully ready
    while True:
        try:
            from tesla_cli.core.sources import refresh_stale

            result = refresh_stale()
            refreshed = result.get("refreshed", [])
            failed = result.get("failed", [])
            if refreshed:
                log.info("Sources refreshed: %s", ", ".join(refreshed))
            if failed:
                log.debug("Sources failed: %s", ", ".join(f["id"] for f in failed))
        except Exception as exc:
            log.debug("Source auto-refresh failed: %s", exc)
        _t.sleep(1800)  # Every 30 minutes


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for the API server."""
    import threading

    threading.Thread(target=_auto_provision_teslamate, daemon=True).start()
    threading.Thread(target=_auto_refresh_sources, daemon=True).start()
    yield


def create_app(vin: str | None = None, serve_ui: bool = False) -> FastAPI:
    app = FastAPI(
        title="tesla-cli API",
        description="REST API for Tesla vehicle control and monitoring.",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )

    _register_middleware(app)
    _register_routes(app)
    _register_system_endpoints(app)
    _register_metrics(app)
    _register_sse_stream(app)
    _register_ui(app, serve_ui)

    # Store resolved VIN in app state
    app.state.override_vin = vin

    return app


# ── Registration helpers ───────────────────────────────────────────────────────


def _register_middleware(app: FastAPI) -> None:
    """Add CORS and API key middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from tesla_cli.api.auth import ApiKeyMiddleware

    cfg = load_config()
    app.add_middleware(ApiKeyMiddleware, api_key=cfg.server.api_key)


def _register_routes(app: FastAPI) -> None:
    """Include all API routers."""
    from tesla_cli.api.routes.auth import router as auth_router
    from tesla_cli.api.routes.charge import router as charge_router
    from tesla_cli.api.routes.climate import router as climate_router
    from tesla_cli.api.routes.colombia import router as colombia_router
    from tesla_cli.api.routes.dossier import router as dossier_router
    from tesla_cli.api.routes.geofence import router as geofence_router
    from tesla_cli.api.routes.notify import router as notify_router
    from tesla_cli.api.routes.order import router as order_router
    from tesla_cli.api.routes.security import router as security_router
    from tesla_cli.api.routes.sources import router as sources_router
    from tesla_cli.api.routes.teslaMate import router as teslaMate_router
    from tesla_cli.api.routes.vehicle import router as vehicle_router

    app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
    app.include_router(sources_router, prefix="/api/sources", tags=["Sources"])
    app.include_router(colombia_router, prefix="/api/co", tags=["Colombia"])
    app.include_router(vehicle_router, prefix="/api/vehicle", tags=["Vehicle"])
    app.include_router(charge_router, prefix="/api/charge", tags=["Charge"])
    app.include_router(climate_router, prefix="/api/climate", tags=["Climate"])
    app.include_router(security_router, prefix="/api/security", tags=["Security"])
    app.include_router(order_router, prefix="/api/order", tags=["Order"])
    app.include_router(dossier_router, prefix="/api/dossier", tags=["Dossier"])
    app.include_router(notify_router, prefix="/api/notify", tags=["Notify"])
    app.include_router(geofence_router, prefix="/api/geofences", tags=["Geofences"])
    app.include_router(teslaMate_router, prefix="/api/teslaMate", tags=["TeslaMate"])


def _register_system_endpoints(app: FastAPI) -> None:
    """Register /api/health, /api/status, /api/vehicles, /api/config, and provider endpoints."""

    @app.get("/api/health", tags=["System"])
    def api_health(deep: bool = False) -> dict:
        """Health check for Docker/Kubernetes liveness probes.

        Returns 200 with {"status": "ok"} — always succeeds if server is running.
        Use as: GET /api/health for Docker HEALTHCHECK or k8s livenessProbe.
        Add ?deep=true for extended config/auth diagnostics.
        """
        result: dict = {"status": "ok", "version": __version__}
        if deep:
            from tesla_cli.core.auth import tokens

            cfg = load_config()
            result["backend"] = cfg.general.backend
            result["vin_configured"] = bool(cfg.general.default_vin)
            result["has_auth_token"] = tokens.has_token(tokens.ORDER_REFRESH_TOKEN)
            result["telemetry_enabled"] = cfg.telemetry.enabled
            result["teslamate_managed"] = cfg.teslaMate.managed
        return result

    @app.get("/api/status", tags=["System"])
    def api_status(request: Request) -> dict:
        cfg = load_config()
        return {
            "version": __version__,
            "backend": cfg.general.backend,
            "vin": cfg.general.default_vin,
            "server": "tesla-cli API",
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
            "backend": cfg.general.backend,
            "default_vin": cfg.general.default_vin,
            "cost_per_kwh": cfg.general.cost_per_kwh,
            "teslaMate_url": bool(cfg.teslaMate.database_url),
            "ha_url": cfg.home_assistant.url,
            "abrp_configured": bool(cfg.abrp.user_token),
            "geofences": list(cfg.geofences.zones.keys()),
            "notifications": cfg.notifications.enabled,
            "vehicles": cfg.vehicles.aliases,
            "auth_enabled": bool(cfg.server.api_key),
        }

    @app.get("/api/providers", tags=["System"])
    def api_providers() -> list:
        """Ecosystem provider status — availability and capabilities."""
        from tesla_cli.core.providers import get_registry

        return get_registry().status()

    @app.get("/api/providers/capabilities", tags=["System"])
    def api_provider_capabilities() -> dict:
        """Capability map — which providers serve which capabilities."""
        from tesla_cli.core.providers import get_registry
        from tesla_cli.core.providers.base import Capability

        registry = get_registry()
        out = {}
        for cap in sorted(Capability.all()):
            available = [p.name for p in registry.for_capability(cap)]
            all_p = [p.name for p in registry.for_capability(cap, available_only=False)]
            out[cap] = {"available": available, "all": all_p}
        return out

    @app.get("/api/config/validate", tags=["System"])
    def api_config_validate() -> dict:
        """Run config validation checks — same as `tesla config validate`.

        Returns {valid, errors, warnings, checks[]} suitable for a dashboard health widget.
        """
        from tesla_cli.cli.commands.config_cmd import _run_config_checks

        cfg = load_config()
        checks = _run_config_checks(cfg)
        errors = sum(1 for c in checks if c["status"] == "error")
        warnings = sum(1 for c in checks if c["status"] == "warn")
        return {"valid": errors == 0, "errors": errors, "warnings": warnings, "checks": checks}


def _register_metrics(app: FastAPI) -> None:
    """Register the Prometheus-format /api/metrics endpoint."""

    @app.get("/api/metrics", tags=["System"])
    def api_metrics(request: Request):
        """Prometheus text format metrics — battery level, range, odometer, etc.

        Designed to be scraped by Prometheus or read by Grafana.
        Returns 200 with text/plain; set=0.0.4 even if vehicle is unreachable
        (uses stale/empty values rather than error).
        """
        from fastapi.responses import PlainTextResponse

        cfg = load_config()
        v = resolve_vin(cfg, app.state.override_vin)

        try:
            backend = get_vehicle_backend(cfg)
            data = backend.get_vehicle_data(v)
        except Exception:  # noqa: BLE001
            data = {}

        cs = data.get("charge_state") or {}
        cl = data.get("climate_state") or {}
        ds = data.get("drive_state") or {}
        vs = data.get("vehicle_state") or {}

        def _g(name: str, help_text: str, value, labels: str = "") -> str:
            lbl = f'{{vin="{v}"{", " + labels if labels else ""}}}'
            val = float(value) if value is not None else float("nan")
            val_str = str(val) if val == val else "NaN"
            return f"# HELP {name} {help_text}\n# TYPE {name} gauge\n{name}{lbl} {val_str}\n"

        def _bool_g(name: str, help_text: str, value) -> str:
            return _g(name, help_text, int(bool(value)) if value is not None else None)

        lines = [
            # Battery & Charging
            _g("tesla_battery_level", "Battery level percent", cs.get("battery_level")),
            _g("tesla_battery_range", "Estimated range in miles", cs.get("battery_range")),
            _g("tesla_charge_limit", "Charge limit SoC percent", cs.get("charge_limit_soc")),
            _g("tesla_charger_power", "Charger power in kW", cs.get("charger_power")),
            _g("tesla_charger_voltage", "Charger voltage in V", cs.get("charger_voltage")),
            _g("tesla_charger_current", "Charger current in A", cs.get("charger_actual_current")),
            _g("tesla_charge_rate", "Charge rate in mph added", cs.get("charge_rate")),
            _g(
                "tesla_energy_added",
                "Energy added in kWh this session",
                cs.get("charge_energy_added"),
            ),
            _g("tesla_time_to_full", "Hours to full charge", cs.get("time_to_full_charge")),
            # Temperature
            _g("tesla_inside_temp", "Inside temperature in Celsius", cl.get("inside_temp")),
            _g("tesla_outside_temp", "Outside temperature in Celsius", cl.get("outside_temp")),
            _g(
                "tesla_driver_temp_setting",
                "Driver temp setting in Celsius",
                cl.get("driver_temp_setting"),
            ),
            _bool_g(
                "tesla_climate_on", "Climate system active (1=on 0=off)", cl.get("is_climate_on")
            ),
            # TPMS Tire Pressure
            _g("tesla_tpms_fl", "Tire pressure front-left in bar", vs.get("tpms_pressure_fl")),
            _g("tesla_tpms_fr", "Tire pressure front-right in bar", vs.get("tpms_pressure_fr")),
            _g("tesla_tpms_rl", "Tire pressure rear-left in bar", vs.get("tpms_pressure_rl")),
            _g("tesla_tpms_rr", "Tire pressure rear-right in bar", vs.get("tpms_pressure_rr")),
            # Location & Movement
            _g("tesla_odometer", "Odometer in miles", vs.get("odometer")),
            _g("tesla_speed", "Vehicle speed in mph", ds.get("speed")),
            _g("tesla_latitude", "Vehicle latitude", ds.get("latitude")),
            _g("tesla_longitude", "Vehicle longitude", ds.get("longitude")),
            _g("tesla_heading", "Vehicle heading in degrees", ds.get("heading")),
            # State
            _bool_g("tesla_locked", "Doors locked (1=locked 0=unlocked)", vs.get("locked")),
            _bool_g("tesla_sentry_mode", "Sentry mode active (1=on 0=off)", vs.get("sentry_mode")),
            _bool_g("tesla_climate_on_state", "HVAC active (1=on 0=off)", cl.get("is_climate_on")),
            _bool_g(
                "tesla_charge_port_open", "Charge port door open", cs.get("charge_port_door_open")
            ),
        ]

        return PlainTextResponse("".join(lines), media_type="text/plain; version=0.0.4")


def _register_sse_stream(app: FastAPI) -> None:
    """Register the real-time SSE vehicle stream endpoint."""

    @app.get("/api/vehicle/stream", tags=["Vehicle"])
    async def vehicle_stream(
        request: Request,
        interval: int = 10,
        fanout: bool = False,
        topics: str = "",
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
        v = resolve_vin(cfg, app.state.override_vin)
        topic_set = {t.strip() for t in topics.split(",") if t.strip()}
        want_geofence = "geofence" in topic_set
        want_battery = "battery" in topic_set
        want_climate = "climate" in topic_set
        want_drive = "drive" in topic_set
        want_location = "location" in topic_set
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
                    payload = json.dumps(
                        {
                            "ts": ts,
                            "data": _sanitize(data),
                        }
                    )
                    yield f"event: vehicle\ndata: {payload}\n\n"

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
                            "lat": ds.get("latitude"),
                            "lon": ds.get("longitude"),
                            "heading": ds.get("heading"),
                            "speed": ds.get("speed"),
                        }
                        yield f"event: location\ndata: {json.dumps({'ts': ts, 'data': loc})}\n\n"

                    if fanout:
                        await asyncio.get_event_loop().run_in_executor(
                            None, _fanout_telemetry, data, v, cfg
                        )

                    if want_geofence:
                        drive = data.get("drive_state") or data.get("response", {}).get(
                            "drive_state", {}
                        )
                        lat = drive.get("latitude") if isinstance(drive, dict) else None
                        lon = drive.get("longitude") if isinstance(drive, dict) else None
                        if lat is not None and lon is not None:
                            reload_cfg = load_config()
                            for name, zone in reload_cfg.geofences.zones.items():
                                dist = _haversine_km(lat, lon, zone["lat"], zone["lon"])
                                inside = dist <= zone.get("radius_km", 0.5)
                                was_inside = geofence_state.get(name)
                                if was_inside is None:
                                    geofence_state[name] = inside
                                elif inside != was_inside:
                                    geofence_state[name] = inside
                                    event = "enter" if inside else "exit"
                                    gf_payload = json.dumps(
                                        {
                                            "ts": ts,
                                            "zone": name,
                                            "event": event,
                                            "lat": lat,
                                            "lon": lon,
                                            "dist_km": round(dist, 3),
                                        }
                                    )
                                    yield f"event: geofence\ndata: {gf_payload}\n\n"

                except Exception as exc:  # noqa: BLE001
                    yield f"event: vehicle\ndata: {json.dumps({'error': str(exc)})}\n\n"
                await asyncio.sleep(interval)

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )


def _register_ui(app: FastAPI, serve_ui: bool) -> None:
    """Mount static UI assets or redirect root to API docs."""
    _ui_dist = Path(__file__).resolve().parent / "ui_dist"

    if serve_ui and _ui_dist.exists() and (_ui_dist / "index.html").exists():
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import FileResponse as StarletteFileResponse

        _index = str(_ui_dist / "index.html")

        class SPAMiddleware(BaseHTTPMiddleware):
            """Serve React SPA with client-side routing fallback.

            For paths that don't start with /api/ and don't match a static
            file in ui_dist, serve index.html so the React router handles it.
            """

            async def dispatch(self, request, call_next):
                path = request.url.path

                # Let API routes pass through.
                if path.startswith("/api"):
                    return await call_next(request)

                # Try serving a static file from ui_dist.
                file = _ui_dist / path.lstrip("/")
                if file.is_file() and ".." not in path:
                    return StarletteFileResponse(str(file))

                # Fallback: serve index.html for client-side routing.
                return StarletteFileResponse(_index)

        app.add_middleware(SPAMiddleware)
    else:
        from fastapi.responses import RedirectResponse

        @app.get("/", include_in_schema=False)
        def root_redirect():
            return RedirectResponse(url="/api/docs")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _fanout_telemetry(data: dict, vin: str, cfg) -> None:
    """Push vehicle state to all configured telemetry/home-sync sinks."""
    from tesla_cli.core.providers.base import Capability
    from tesla_cli.core.providers.loader import build_registry

    registry = build_registry(cfg)
    registry.fanout(Capability.TELEMETRY_PUSH, "push", data=data, vin=vin)
    registry.fanout(Capability.HOME_SYNC, "push", data=data, vin=vin)


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
