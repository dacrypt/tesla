# Tesla CLI

[![CI](https://github.com/dacrypt/tesla/actions/workflows/ci.yml/badge.svg)](https://github.com/dacrypt/tesla/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Control your Tesla and track your order from the terminal — with a live web dashboard, REST API, MQTT integration, and analytics.

```
tesla order status           → check your order status
tesla vehicle health-check   → quick 7-point system health check
tesla charge forecast        → charging ETA + kWh estimate
tesla teslaMate trip-stats   → trip analytics from TeslaMate
tesla serve                  → start local REST API + web dashboard
```

---

## Installation

### Requirements

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)

### Quick Start

```bash
git clone https://github.com/dacrypt/tesla.git
cd tesla
uv tool install -e .
tesla setup
```

`tesla setup` is an interactive wizard: Tesla OAuth2 authentication, auto-discovery of your VIN and order number, optional vehicle control backend (Tessie or Fleet API), and first dossier build.

Run `tesla setup --force` to re-configure at any time.

Config is stored at `~/.tesla-cli/config.toml`.
Tokens are stored in the system keyring (macOS Keychain / Linux Secret Service) — **never in plain text files**.

### Optional extras

```bash
uv tool install -e ".[teslaMate]"   # TeslaMate PostgreSQL integration
uv tool install -e ".[serve]"       # REST API server + web dashboard
uv tool install -e ".[fleet]"       # Tesla Fleet API direct
uv tool install -e ".[pdf]"         # PDF dossier export
```

---

## 1. Order Tracking

### Authenticate

```bash
tesla config auth order
```

Two options:

**Option 1 — Browser (OAuth2 + PKCE):**

1. Browser opens, you log in with your Tesla account
2. Tesla redirects to a blank page
3. Copy the full URL (`https://auth.tesla.com/void/callback?code=...`)
4. Paste it in the terminal

**Option 2 — Refresh token:**

1. If you already have a refresh token (from TeslaMate, Tessie, browser DevTools, etc.)
2. Paste it directly

### Check status

```bash
tesla order status
```

Shows: status, VIN, model, country, configuration options, delivery window.

### Full details

```bash
tesla order details
```

Shows everything: status + pending tasks + vehicle info + delivery + financing + trade-in + registration.

### JSON mode

```bash
tesla -j order status                     # raw JSON
tesla -j order status | jq .raw           # raw API response only
tesla -j order status | jq .raw.mktOptions  # option codes
```

### Monitor changes

```bash
tesla order watch              # every 10 min (default)
tesla order watch -i 5         # every 5 min
tesla order watch --no-notify  # without notifications
```

Runs continuously and notifies you when any field changes. `Ctrl+C` to stop.

---

## 2. Notifications

Tesla CLI uses [Apprise](https://github.com/caronc/apprise) for notifications. Supports 100+ services: Telegram, Slack, Discord, Email, ntfy, Pushover, etc.

```bash
# Manage notification channels
tesla notify add tgram://BOT_TOKEN/CHAT_ID      # add Telegram
tesla notify add discord://webhook_id/token     # add Discord
tesla notify list                               # show configured channels
tesla notify test                               # send live test to all channels
tesla notify remove 1                           # remove channel #1

# Custom message template
tesla notify set-template "{event}: {vehicle} — {detail}"
tesla notify show-template
```

Template placeholders: `{event}`, `{vehicle}`, `{detail}`, `{ts}`.

### Supported services (examples)

| Service | URL format |
|---------|-----------|
| **Telegram** | `tgram://BOT_TOKEN/CHAT_ID` |
| **Slack** | `slack://TokenA/TokenB/TokenC/#channel` |
| **Discord** | `discord://webhook_id/webhook_token` |
| **Email (Gmail)** | `mailto://user:app_password@gmail.com` |
| **ntfy.sh** | `ntfy://my-tesla` |
| **Pushover** | `pover://user_key@app_token` |

[Full list of 100+ services](https://github.com/caronc/apprise/wiki)

---

## 3. Vehicle Control

### Available backends

| Backend | Setup | Cost | Notes |
|---------|-------|------|-------|
| **Owner API** (recommended) | Zero — reuses your Tesla account token | Free | Same credentials as order tracking |
| **Tessie** | Tessie account + API token | ~$10/month | Third-party proxy |
| **Fleet API** | Register app at developer.tesla.com | Free* | Requires public domain for OAuth callback |

*Fleet API is free up to a certain volume; then charges per request.

### Option A: Owner API (recommended, free)

No extra setup — uses the same token from `tesla setup` / `tesla config auth order`.

```bash
tesla config set backend owner
```

### Option B: Tessie

```bash
tesla config auth tessie
```

### Option C: Fleet API direct

```bash
tesla config set client-id YOUR_CLIENT_ID
tesla config auth fleet
```

### Core commands

```bash
# Information
tesla vehicle list             # list all your Teslas
tesla vehicle info             # full vehicle data
tesla vehicle bio              # comprehensive single-screen vehicle profile
tesla vehicle location         # GPS + Google Maps link
tesla vehicle health-check     # 7-point system health check (battery/climate/drive/software/locks/sentry/charging)

# Charging
tesla charge status            # state: %, range, time remaining
tesla charge start             # start charging
tesla charge stop              # stop charging
tesla charge set-limit 80      # set charge limit (%)
tesla charge set-amps 16       # set charge current (A)
tesla charge profile           # view/set limit + amps + schedule in one command
tesla charge forecast          # ETA + kWh estimate to reach target SoC
tesla charge schedule-amps 22:00 32  # schedule time + amperage together

# Climate
tesla climate status           # inside/outside temperature
tesla climate on               # turn on AC/heating
tesla climate off              # turn off
tesla climate set-temp 22.5    # set target temperature (°C)

# Security
tesla security lock            # lock doors
tesla security unlock          # unlock doors
tesla security trunk rear      # open trunk
tesla security trunk front     # open frunk

# Sentry Mode
tesla vehicle sentry           # show status
tesla vehicle sentry --on      # enable
tesla vehicle sentry --off     # disable
tesla vehicle sentry-events    # recent sentry events from TeslaMate

# Cabin Overheat Protection
tesla vehicle cabin-protection            # view status
tesla vehicle cabin-protection --on       # enable
tesla vehicle cabin-protection --off      # disable
tesla vehicle cabin-protection --level FAN_ONLY   # set mode (FAN_ONLY / NO_AC / CHARGE_ON)

# Windows & Charge Port
tesla vehicle windows vent         # vent all windows
tesla vehicle windows close        # close all windows
tesla vehicle charge-port open     # open charge port door
tesla vehicle charge-port close    # close charge port door
tesla vehicle charge-port stop     # stop charging + unlock port

# Software
tesla vehicle software             # current version + pending update
tesla vehicle software --install   # schedule pending update
tesla vehicle schedule-update --delay 30   # schedule update after N minutes

# Watch / Live monitor
tesla vehicle watch            # live Rich dashboard, refresh every 5s
tesla vehicle watch --interval 10   # every 10s
tesla vehicle watch --all      # watch ALL vehicles simultaneously (multi-vehicle)
tesla vehicle watch --all --notify  # per-vehicle notifications on changes

# Speed limit
tesla vehicle speed-limit         # view current limit
tesla vehicle speed-limit --on 90 # activate at 90 mph
tesla vehicle speed-limit --off   # deactivate

# Other
tesla vehicle horn             # honk horn
tesla vehicle flash            # flash lights
tesla vehicle wake             # wake vehicle
```

> If the car is asleep, commands wake it automatically (3 retries with 8s back-off).

### Multi-vehicle

```bash
# Create aliases
tesla config alias modely YOUR_VIN_HERE
tesla config alias model3 OTHER_VIN_HERE

# Use aliases
tesla vehicle info --vin modely
tesla charge status --vin model3

# Watch all vehicles simultaneously
tesla vehicle watch --all

# Change default
tesla config set default-vin OTHER_VIN_HERE
```

---

## 4. Vehicle Dossier

The dossier is a complete vehicle file that aggregates data from **all available sources**:

- Tesla Owner API (order, account, features)
- VIN decode (built-in, works with any country's VINs)
- NHTSA recalls (free US government API)
- Ship tracking (ships transporting Teslas)
- Historical archive (JSON snapshots)

### Build / update dossier

```bash
tesla dossier build
```

Queries all sources, decodes VIN and option codes, searches recalls, tracks ships, and saves a historical snapshot. Each run accumulates history.

### View saved dossier (without querying APIs)

```bash
tesla dossier show
tesla -j dossier show              # full JSON
tesla -j dossier show | jq .specs  # specs only
```

### Decode VIN

```bash
tesla dossier vin                       # your configured VIN
tesla dossier vin 5YJ3E1EA8PF123456    # any Tesla VIN
```

### View Tesla ships

```bash
tesla dossier ships
```

### View snapshot history

```bash
tesla dossier history
```

### Compare two snapshots

```bash
tesla dossier diff              # compare last two snapshots
tesla dossier diff 1 3          # compare snapshot #1 vs #3
tesla -j dossier diff | jq .    # JSON output of all differences
```

### Delivery inspection checklist

```bash
tesla dossier checklist                  # show all 34 items
tesla dossier checklist --mark 5,12,18  # check items off
tesla dossier checklist --reset          # start over
```

### Delivery journey gates

```bash
tesla dossier gates
```

Tracks the 13-gate journey from order placed to keys in hand.

### Export

```bash
tesla dossier export-html                     # dark theme (default)
tesla dossier export-html --theme light       # light theme
tesla dossier export-html -o my-car.html      # custom output path
tesla dossier export-pdf                      # PDF export (requires pdf extra)
```

---

## 5. TeslaMate Integration

Connect tesla-cli to your [TeslaMate](https://github.com/adriankumpf/teslamate) PostgreSQL database for post-delivery analytics.

```bash
# One-time setup
tesla teslaMate connect postgresql://user:pass@localhost:5432/teslaMate

# Core analytics
tesla teslaMate status               # lifetime stats + connection info
tesla teslaMate trips                # last 20 trips
tesla teslaMate trips --limit 100    # last 100 trips
tesla teslaMate charging             # last 20 charging sessions
tesla teslaMate updates              # OTA update history

# Advanced analytics
tesla teslaMate timeline             # unified drive/charge/update event timeline (last 7 days)
tesla teslaMate timeline --days 30   # last 30 days
tesla teslaMate cost-report          # charging cost breakdown by month
tesla teslaMate cost-report --month 2026-02  # specific month
tesla teslaMate cost-report --limit 12       # last 12 months
tesla teslaMate trip-stats           # trip summary + top routes (last 30 days)
tesla teslaMate trip-stats --days 90 # last 90 days
tesla teslaMate charging-locations   # most-visited charging locations (aggregated)
tesla teslaMate charging-locations --days 90 --limit 20
tesla teslaMate heatmap              # drive days heatmap (current year)
tesla teslaMate heatmap --year 2025  # specific year
tesla teslaMate graph                # ASCII bar chart of recent charging sessions
tesla teslaMate graph --limit 30     # last 30 sessions

# JSON mode for scripting
tesla -j teslaMate trips | jq '.[0]'
tesla -j teslaMate charging | jq '.[] | select(.cost != null)'
```

Requires the `teslaMate` extra: `uv tool install -e ".[teslaMate]"`

---

## 6. MQTT Integration

Publish real-time vehicle telemetry to any MQTT broker (Mosquitto, EMQX, HiveMQ, etc.) and auto-configure Home Assistant sensors via MQTT Discovery.

```bash
# Setup
tesla mqtt setup           # interactive broker configuration wizard
tesla mqtt status          # connection test + configured topic prefix
tesla mqtt test            # publish one test message

# Publish telemetry
tesla mqtt publish         # single publish of current vehicle state

# Home Assistant Discovery
tesla mqtt ha-discovery    # publish 15 HA sensor auto-discovery payloads (retained)
```

HA discovery publishes sensors for: battery level, battery range, charge limit, charging state, charger power, energy added, odometer, inside/outside temp, GPS coordinates (lat/lon), speed, locked state, sentry mode, and software version.

Configure in `~/.tesla-cli/config.toml`:

```toml
[mqtt]
broker = "192.168.1.100"
port = 1883
topic_prefix = "tesla"
username = ""
password = ""
qos = 0
retain = false
tls = false
```

---

## 7. REST API Server + Web Dashboard

Start a local FastAPI server with a live web dashboard:

```bash
tesla serve                 # http://localhost:8000
tesla serve --port 9000     # custom port
tesla serve --host 0.0.0.0  # bind to all interfaces
tesla serve --reload        # dev mode (auto-reload on file changes)
```

Requires the `serve` extra: `uv tool install -e ".[serve]"`

### Web Dashboard

Navigate to `http://localhost:8000` for a mobile-friendly web dashboard featuring:

- **Real-time Battery card** — SVG ring gauge, charge state, charging animation, rate and ETA rows when charging
- **Climate card** — inside/outside temperature
- **Drive card** — location, GPS coordinates
- **Vehicle state** — locked/unlocked, sentry mode, software version
- **Geofence overlay** — visual zone indicators on Location card
- **VIN switcher** — `<select>` for multi-vehicle households
- **Theme toggle** — dark/light mode (persisted in localStorage)
- **Config health badge** — footer badge shows ok/warn/err from config validation
- **SSE backoff** — automatic exponential reconnect (1s → 2s → 4s … max 30s)
- **PWA-ready** — installable as a Progressive Web App (manifest + service worker)

### REST API Endpoints

#### System

| Endpoint | Description |
|----------|-------------|
| `GET /api/status` | Version, backend, default VIN |
| `GET /api/vehicles` | All configured vehicles (aliases + default) |
| `GET /api/config` | Full config summary |
| `GET /api/config/validate` | Config health check (same as `tesla config validate`) |
| `GET /api/providers` | Provider registry status |
| `GET /api/providers/capabilities` | Capability map per provider |
| `GET /api/geofences` | Configured geofence zones |
| `GET /api/metrics` | Prometheus text-format metrics (11 gauges) |

#### Vehicle

| Endpoint | Description |
|----------|-------------|
| `GET /api/vehicle/data` | Full vehicle state snapshot |
| `GET /api/vehicle/stream` | Server-Sent Events live stream |
| `POST /api/vehicle/wake` | Wake vehicle |
| `POST /api/vehicle/command/{cmd}` | Send arbitrary vehicle command |

#### Charge

| Endpoint | Description |
|----------|-------------|
| `GET /api/charge/state` | Charge state |
| `POST /api/charge/start` | Start charging |
| `POST /api/charge/stop` | Stop charging |
| `POST /api/charge/set-limit` | Set charge limit |
| `POST /api/charge/set-amps` | Set charge current |

#### Climate

| Endpoint | Description |
|----------|-------------|
| `GET /api/climate/state` | Climate state |
| `POST /api/climate/on` | Turn on climate |
| `POST /api/climate/off` | Turn off climate |

#### TeslaMate

| Endpoint | Description |
|----------|-------------|
| `GET /api/teslaMate/status` | Lifetime stats |
| `GET /api/teslaMate/trips` | Recent trips |
| `GET /api/teslaMate/charging` | Recent charging sessions |
| `GET /api/teslaMate/timeline` | Unified event timeline |
| `GET /api/teslaMate/cost-report` | Monthly cost breakdown |
| `GET /api/teslaMate/trip-stats` | Trip summary + top routes |

### Multi-vehicle API

All `/api/vehicle/` routes accept `?vin=` to target a specific vehicle:

```
GET /api/vehicle/data?vin=5YJ3E1EA...
GET /api/charge/state?vin=modely
```

### SSE Stream

```bash
# All data
curl -N http://localhost:8000/api/vehicle/stream

# Fine-grained topics (comma-separated)
curl -N "http://localhost:8000/api/vehicle/stream?topics=battery,location,geofence"
```

Topic events: `vehicle` (always), `battery`, `climate`, `drive`, `location`, `geofence`.

### Prometheus metrics

```
GET /api/metrics
```

Exposes 11 gauges in `text/plain; version=0.0.4` format, ready for Prometheus scraping:
`tesla_battery_level`, `tesla_battery_range`, `tesla_charge_limit`, `tesla_charger_power`,
`tesla_energy_added`, `tesla_odometer`, `tesla_speed`, `tesla_latitude`, `tesla_longitude`,
`tesla_locked`, `tesla_sentry_mode`.

### API Key Authentication

```bash
tesla config set server.api_key MY_SECRET_KEY
```

Once set, all `/api/` requests require `X-Api-Key: MY_SECRET_KEY` header.

---

## 8. Config Management

### View and set values

```bash
tesla config show                      # show full config
tesla config set backend owner
tesla config set default-vin 5YJ3...
tesla config set cost-per-kwh 0.22     # for charging cost calculations
tesla config alias modely 5YJ3...     # named VIN alias
```

### Validate config

```bash
tesla config validate                  # checks format + values + reachability
echo $?                                # 0 = all ok, 1 = errors found
```

### Migrate config

```bash
tesla config migrate                   # update config to current schema (dry-run by default)
tesla config migrate --apply           # apply changes (auto-backs up first)
```

---

## 9. Provider Architecture

Tesla CLI uses a layered provider registry to serve capabilities from the best available source:

| Layer | Provider | Capabilities |
|-------|----------|-------------|
| L0 | **BLE** | Local Bluetooth commands (proximity required) |
| L1 | **VehicleAPI** | Full vehicle control + data via Owner/Fleet/Tessie |
| L2 | **TeslaMate** | Trip analytics, charge history, timeline, heatmap |
| L3 | **ABRP** | Live route telemetry push |
| L3 | **HomeAssistant** | Home sync push |
| L3 | **Apprise** | Notifications (100+ channels) |
| L3 | **MQTT** | Telemetry publish + HA discovery |

```bash
tesla providers           # show all providers + availability status
```

---

## 10. Live Telemetry Stream

```bash
tesla stream live                    # refresh every 5s (default)
tesla stream live --interval 10      # every 10s
tesla stream live --count 20         # stop after 20 refreshes
```

Real-time Rich dashboard: battery %, charge rate, inside/outside temperature, GPS location, door lock state, Sentry Mode, software version, odometer.

---

## 11. Multi-Language UI

```bash
tesla --lang es order status     # Spanish output
TESLA_LANG=es tesla order watch  # via environment variable
```

Supported: `en` (default), `es` (Spanish). Falls back to English for any untranslated string.

---

## 12. Privacy — Anonymize Mode

```bash
tesla --anon order status           # VIN and RN masked
tesla --anon dossier show           # safe to screenshot and share
tesla --anon -j order status        # JSON with PII stripped
```

---

## 13. JSON Mode

All commands support `-j` / `--json` for script integration:

```bash
tesla -j order status
tesla -j charge status
tesla -j vehicle location

# Combine with jq
tesla -j order status | jq .raw.mktOptions
tesla -j charge status | jq .battery_level
tesla -j vehicle location | jq .maps_url
tesla -j teslaMate trip-stats | jq '.top_routes[0]'

# Save snapshot
tesla -j order status > ~/tesla-order-$(date +%Y%m%d).json
```

---

## Configuration Reference

### `tesla config set` keys

| Key | Description | Values |
|-----|-------------|--------|
| `default-vin` | Default vehicle VIN | `YOUR_VIN_HERE` |
| `backend` | Vehicle backend | `owner`, `tessie`, `fleet` |
| `reservation-number` | Order number | `RNXXXXXXXXX` |
| `region` | Fleet API region | `na`, `eu`, `cn` |
| `client-id` | Fleet API client ID | (your app ID) |
| `notifications-enabled` | Enable notifications | `true`, `false` |
| `cost-per-kwh` | kWh cost for charging cost calculations | `0.22` |
| `server.api_key` | API server authentication key | (any string) |

### Files

| File | Contents |
|------|----------|
| `~/.tesla-cli/config.toml` | General configuration |
| `~/.tesla-cli/state/last_order.json` | Last known state (for change detection) |
| `~/.tesla-cli/dossier/dossier.json` | Complete vehicle dossier |
| `~/.tesla-cli/dossier/snapshots/` | Historical snapshots (cumulative) |
| System Keyring | Authentication tokens (access + refresh) |

---

## Architecture

```
src/tesla_cli/
├── app.py                # Entry point. Registers all Typer sub-apps
├── config.py             # Config manager (~/.tesla-cli/config.toml)
├── output.py             # Rendering: Rich tables + JSON mode + anonymize
├── i18n.py               # Internationalization: t(key) — en + es built-in
├── exceptions.py         # Custom errors
│
├── auth/                 # Authentication
│   ├── oauth.py          # Tesla OAuth2 + PKCE (browser flow + refresh token)
│   ├── tokens.py         # Keyring storage (macOS Keychain / Linux Secret Service)
│   └── tessie.py         # Tessie token helper
│
├── backends/             # API access layer
│   ├── base.py           # ABC VehicleBackend (abstract interface)
│   ├── fleet.py          # Tesla Fleet API direct (NA/EU/CN)
│   ├── tessie.py         # Tessie as Fleet API proxy
│   ├── owner.py          # Tesla Owner API (auto-wake retry)
│   ├── order.py          # Order tracking (reverse-engineered endpoints)
│   ├── dossier.py        # Dossier aggregator (NHTSA, ships, VIN decode, 140+ option codes)
│   └── teslaMate.py      # TeslaMate PostgreSQL read-only backend
│
├── providers/            # Provider registry (7 providers, 4 layers)
│   ├── base.py           # Capability enum + ProviderBase ABC
│   ├── registry.py       # Provider registry (fanout, for_capability)
│   ├── loader.py         # build_registry() factory
│   └── impl/             # Provider implementations
│       ├── vehicle_api.py    # L1: Owner/Fleet/Tessie
│       ├── teslaMate.py      # L2: TeslaMate DB
│       ├── abrp.py           # L3: ABRP push
│       ├── home_assistant.py # L3: HA sync push
│       ├── apprise_notif.py  # L3: Notifications
│       └── mqtt.py           # L3: MQTT publish + HA discovery
│
├── server/               # FastAPI REST API + web dashboard
│   ├── app.py            # App factory, SSE stream, metrics, config validate
│   ├── auth.py           # ApiKeyMiddleware
│   └── routes/
│       ├── vehicle.py    # /api/vehicle/* (multi-VIN via ?vin= param)
│       ├── charge.py     # /api/charge/*
│       ├── climate.py    # /api/climate/*
│       ├── order.py      # /api/order/*
│       └── teslaMate.py  # /api/teslaMate/* (timeline, cost-report, trip-stats)
│   └── static/
│       └── index.html    # Single-page dashboard (VIN switcher, SSE, theme toggle, PWA)
│
└── commands/             # CLI commands (Typer)
    ├── config_cmd.py     # tesla config show/set/alias/auth/validate/migrate
    ├── setup.py          # tesla setup — onboarding wizard
    ├── order.py          # tesla order status/details/watch
    ├── vehicle.py        # tesla vehicle info/bio/health-check/watch/sentry/schedule-update/...
    ├── charge.py         # tesla charge status/start/stop/profile/forecast/schedule-amps
    ├── climate.py        # tesla climate status/on/off/set-temp
    ├── security.py       # tesla security lock/unlock/trunk
    ├── dossier.py        # tesla dossier build/show/vin/diff/checklist/gates/export-html
    ├── stream.py         # tesla stream live (real-time Rich dashboard)
    ├── notify.py         # tesla notify list/add/remove/test/set-template/show-template
    ├── teslaMate.py      # tesla teslaMate connect/status/trips/charging/timeline/...
    ├── mqtt_cmd.py       # tesla mqtt setup/status/test/publish/ha-discovery
    └── serve_cmd.py      # tesla serve (launches FastAPI server)
```

### Data flow

```
User → CLI (Typer) → Command → Provider Registry → Backend → Tesla API
                                      ↓
                               Auth (OAuth/Keyring)
                                      ↓
                               Model (Pydantic)
                                      ↓
                               Output (Rich/JSON)
```

### APIs used

| API | Base URL | Auth | Purpose |
|-----|----------|------|---------|
| **Owner API** (unofficial) | `owner-api.teslamotors.com` | OAuth2 Bearer | Orders, profile |
| **Tasks API** (unofficial) | `akamai-apigateway-vfx.tesla.com` | OAuth2 Bearer | Order tasks/milestones |
| **Fleet API** (official) | `fleet-api.prd.na.vn.cloud.tesla.com` | OAuth2 Bearer | Vehicle control |
| **Tessie API** (third-party) | `api.tessie.com` | API Key | Fleet API proxy |
| **Tesla Auth** | `auth.tesla.com` | OAuth2 + PKCE | Authentication |
| **NHTSA vPIC** (government) | `vpic.nhtsa.dot.gov/api` | None (free) | VIN decode, recalls |
| **NHTSA Recalls** | `api.nhtsa.gov` | None (free) | Recalls by model/year |
| **Ship Tracking** | `shipinfo.net` | None | Tesla ship positions |
| **TeslaMate DB** (self-hosted) | PostgreSQL | Connection string | Trip history, charging, OTA |

---

## Development

```bash
git clone https://github.com/dacrypt/tesla.git
cd tesla

# Install all dev dependencies
uv sync --extra dev --extra serve --extra teslaMate --extra fleet --extra pdf

# Lint
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Tests (unit only, no real API calls)
uv run pytest -m "not integration"

# All tests including integration (requires credentials)
uv run pytest

# Reinstall globally after changes
uv tool install -e .
```

### Adding a new command

1. Create/update the model in `backends/` (API call or DB query)
2. Create the command in `commands/` (Typer function)
3. Register the sub-app in `app.py` if it's a new group
4. Write tests in `tests/`

### Adding a new notification service

Just add the Apprise URL to `~/.tesla-cli/config.toml`. No code changes needed.
[Apprise URL reference](https://github.com/caronc/apprise/wiki)

---

## Roadmap

- [x] Order tracking (status, details, watch)
- [x] `tesla dossier build` — complete vehicle dossier
- [x] `tesla dossier vin` — decode VIN position by position
- [x] `tesla dossier ships` — Tesla ship tracking
- [x] NHTSA recalls integration
- [x] Historical snapshots + `tesla dossier diff`
- [x] Telegram/Slack/Discord/ntfy notifications (Apprise 100+)
- [x] `tesla stream live` — real-time telemetry dashboard
- [x] `tesla vehicle sentry` — Sentry Mode status + toggle
- [x] `tesla dossier checklist` — 34-item delivery inspection checklist
- [x] `tesla dossier gates` — 13-gate delivery journey tracker
- [x] `tesla --anon` — anonymize PII in any command output
- [x] 140+ option codes embedded offline
- [x] TeslaMate PostgreSQL integration (trips, charging, updates)
- [x] Multi-language UI — `--lang es` / `TESLA_LANG=es`
- [x] `tesla dossier estimate` — community delivery date estimation
- [x] `tesla vehicle windows / charge-port / software` — expanded control
- [x] `tesla notify list/add/remove/test` — full notification management
- [x] ABRP live telemetry push
- [x] Home Assistant sync
- [x] `tesla serve` — FastAPI REST API + web dashboard
- [x] Provider registry architecture (7 providers, 4 layers)
- [x] MQTT integration + Home Assistant auto-discovery (15 sensors)
- [x] `tesla mqtt setup/status/test/publish/ha-discovery`
- [x] TeslaMate timeline, cost-report, heatmap
- [x] Prometheus metrics endpoint (`/api/metrics`)
- [x] Dashboard theme toggle (dark/light)
- [x] Multi-vehicle VIN switcher in dashboard
- [x] SSE exponential backoff reconnect
- [x] `tesla config validate / migrate`
- [x] `tesla notify set-template / show-template`
- [x] `tesla vehicle watch --all` — simultaneous multi-vehicle watch
- [x] `tesla charge profile / forecast / schedule-amps`
- [x] `tesla teslaMate trip-stats / charging-locations`
- [x] `tesla vehicle health-check` — 7-point system check
- [x] Dashboard: charging animation + health badge + multi-vehicle
- [x] `tesla vehicle bio` — comprehensive single-screen vehicle profile
- [x] `tesla vehicle cabin-protection` — cabin overheat protection control
- [ ] BLE vehicle control (proximity, no internet)
- [ ] Vehicle Command Protocol (signed commands for 2024+ vehicles)
- [ ] Powerwall / solar energy integration
- [ ] Scheduled departure preconditioning

---

## License

MIT — see [LICENSE](LICENSE)
