---
name: serve
description: >
  Start the Tesla web dashboard and REST API server. Self-hosted on localhost
  with a React UI for vehicle control, charging analytics, and order tracking.
  Use when someone says "start the dashboard", "open the web UI", or "run the server".
disable-model-invocation: true
allowed-tools: Bash(tesla *) Bash(uv *)
level: 2
---

# Tesla Web Dashboard & API

Start the self-hosted web dashboard and REST API.

## Quick Start

```bash
tesla serve                      # start on default port 8080
tesla serve --port 3000          # custom port
tesla serve --host 0.0.0.0      # expose to LAN
```

The dashboard opens at `http://localhost:8080` (or your custom port).

## Prerequisites

The `serve` extra must be installed:
```bash
uv tool install "tesla-cli[serve]"
```

## What the Dashboard Includes

- **Dashboard page**: Battery status, recent charges, quick action buttons
- **Vehicle page**: Charge history, climate controls, door/trunk controls
- **Dossier page**: VIN decode, specs, option codes, recalls, logistics
- **Analytics page**: TeslaMate trip history, charging costs, heatmaps
- **Settings page**: Configuration form

## API Endpoints

The REST API is available at `/api/`:
- `GET /api/vehicle/state` — full vehicle state
- `GET /api/charge/status` — charging status
- `POST /api/vehicle/wake` — wake vehicle
- `POST /api/security/lock` — lock doors
- `GET /api/live` — SSE stream for real-time updates
- `GET /api/metrics` — Prometheus metrics (27 gauges)

Full API docs: `http://localhost:8080/docs` (Swagger UI)

## Response Guidelines

- Check if the `serve` extra is installed first
- Provide the URL after starting
- Mention the Swagger UI at `/docs` for API exploration
- If the user wants to expose to their network, remind them about security (no auth by default — set an API key with `tesla config set server.api_key <key>`)
