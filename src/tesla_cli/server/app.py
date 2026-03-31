"""FastAPI application for tesla-cli API server."""

from __future__ import annotations

import asyncio
import json
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

    # Store resolved VIN in app state
    app.state.override_vin = vin

    # ── Register routes ───────────────────────────────────────────────────────
    from tesla_cli.server.routes.charge import router as charge_router
    from tesla_cli.server.routes.climate import router as climate_router
    from tesla_cli.server.routes.order import router as order_router
    from tesla_cli.server.routes.vehicle import router as vehicle_router

    app.include_router(vehicle_router,  prefix="/api/vehicle",  tags=["Vehicle"])
    app.include_router(charge_router,   prefix="/api/charge",   tags=["Charge"])
    app.include_router(climate_router,  prefix="/api/climate",  tags=["Climate"])
    app.include_router(order_router,    prefix="/api/order",    tags=["Order"])

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
        }

    # ── Provider registry endpoint ────────────────────────────────────────────

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

    # ── Real-time SSE stream ──────────────────────────────────────────────────

    @app.get("/api/vehicle/stream", tags=["Vehicle"])
    async def vehicle_stream(
        request: Request,
        interval: int  = 10,
        fanout: bool   = False,
    ) -> StreamingResponse:
        """Server-Sent Events stream of live vehicle data.

        When fanout=true, each tick also triggers a fan-out push to all
        configured telemetry sinks (ABRP, Home Assistant, etc.).
        """
        cfg = load_config()
        v   = resolve_vin(cfg, app.state.override_vin)

        async def _generate():
            backend = get_vehicle_backend(cfg)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: backend.get_vehicle_data(v)
                    )
                    payload = json.dumps({
                        "ts":   int(time.time()),
                        "data": _sanitize(data),
                    })
                    yield f"data: {payload}\n\n"

                    # Fan-out to all telemetry sinks if requested
                    if fanout:
                        await asyncio.get_event_loop().run_in_executor(
                            None, _fanout_telemetry, data, v, cfg
                        )
                except Exception as exc:  # noqa: BLE001
                    yield f"data: {json.dumps({'error': str(exc)})}\n\n"
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


def _fanout_telemetry(data: dict, vin: str, cfg) -> None:
    """Push vehicle state to all configured telemetry/home-sync sinks."""
    from tesla_cli.providers.base import Capability
    from tesla_cli.providers.loader import build_registry
    registry = build_registry(cfg)
    registry.fanout(Capability.TELEMETRY_PUSH, "push", data=data, vin=vin)
    registry.fanout(Capability.HOME_SYNC,      "push", data=data, vin=vin)


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
