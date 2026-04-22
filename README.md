# Tesla CLI

[![CI](https://github.com/dacrypt/tesla/actions/workflows/ci.yml/badge.svg)](https://github.com/dacrypt/tesla/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Control your Tesla and track your order from the terminal — with a live web dashboard, REST API, MQTT integration, and analytics.

```
tesla vehicle ready              → am I ready to drive?
tesla charge status --oneline    → 🔋 72% | ⚡ 11kW | 1h30m to 80%
tesla charge invoices            → download Supercharging invoices
tesla scene morning              → run morning scene (climate, sentry, etc.)
tesla energy status              → Powerwall/Solar backup + storm watch
tesla serve                      → start REST API + web dashboard
```

---

## Quick Start

```bash
# Requirements: Python 3.12+, uv
git clone https://github.com/dacrypt/tesla.git
cd tesla
uv tool install -e .
tesla setup
```

`tesla setup` is an interactive wizard: email + password is all you need. It handles OAuth2 authentication, VIN auto-discovery, optional vehicle control backend selection, and first data build — tiered so basic features work immediately.

Config: `~/.tesla-cli/config.toml` | Tokens: system keyring (never plain text)

### Optional extras

```bash
uv tool install -e ".[teslaMate]"   # TeslaMate PostgreSQL integration
uv tool install -e ".[serve]"       # REST API server + web dashboard
uv tool install -e ".[fleet]"       # Tesla Fleet API direct
uv tool install -e ".[pdf]"         # PDF dossier export
```

---

## Fleet API Setup

**Who needs this?** Owners of recent Teslas (VIN prefixes `LRW`, `7SA`, `XP7` — roughly 2024+ Model Y / Cybertruck / refreshed Model 3) whose Owner API calls return `HTTP 412 — Vehicle not accessible`. Tesla blocks the legacy Owner API for these VINs, so you need to register a Fleet API app (free) to control the car programmatically.

You can skip this section entirely if Owner API works for your VIN, or if you prefer the Tessie backend (`tesla config auth tessie`).

### 1. Register your Tesla Developer app

Go to [developer.tesla.com](https://developer.tesla.com) → **Create App**. Fill in:

| Field | Value |
|-------|-------|
| App Name | alphanumeric / spaces — Tesla rejects dashes (e.g. `CarMonitor` or `My Tesla Dashboard`) |
| Description | short sentence, e.g. "Personal CLI for my Tesla" |
| Scopes | Enable every scope the portal offers — tesla-cli requests them all. At minimum: `vehicle_device_data`, `vehicle_location`, `vehicle_cmds`, `vehicle_charging_cmds`. Optional: `user_data`, `energy_device_data`, `energy_cmds`. |
| OAuth Grant Type | `Authorization Code and Machine-to-Machine` |
| Redirect URI | `https://auth.tesla.com/void/callback` |
| Allowed Origin / Domain | a domain **you control** (see step 2) |

Tesla will give you a **Client ID** (UUID) and a **Client Secret** — keep both handy. Example shape (fake):

```
Client ID:     xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Client Secret: ta-secret.XXXXXXXXXXXXXXXX~XXXXXXXXXXXXXXXXXXXX
```

### 2. Host your public key (each OSS user does this ONCE on their own domain)

Tesla requires a domain **you control** to host your app's public key at a well-known path:

```
https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem
```

> ⚠ **Do not reuse another project's domain.** Every OSS user registers their own domain and publishes their own public key. Registering `dacrypt.github.io` (or any other user's domain) would give their private key authority over your car. See [`docs/fleet-signed-setup.md`](docs/fleet-signed-setup.md) for the full reasoning.

Three common hosting options (pick one; detailed walkthrough in [`docs/fleet-signed-setup.md`](docs/fleet-signed-setup.md#choosing-how-to-host-your-public-key)):

- **GitHub Pages** — `<username>.github.io` (free, 5 min — recommended for most OSS users)
- **Custom domain** — `tesla.yourdomain.com` (if you already own a host)
- **Netlify / Vercel / Cloudflare Pages** — `my-tesla-keys.netlify.app` (free tier)

The CLI generates the key pair for you on first run of `tesla config auth fleet-signed`. You only need to host the resulting `~/.tesla-cli/keys/public-key.pem` at the path above. Verify:

```bash
curl -sI https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem
# expect: HTTP/2 200
```

Then set the domain in tesla-cli:

```bash
tesla config set fleet-domain <your-domain>   # e.g. myusername.github.io
```

(The CLI will also prompt for this on first `tesla config auth fleet-signed` run if unset.)

### 3. Run the auth flow

```bash
tesla config auth fleet
```

Walkthrough of what you'll see (real output, secrets anonymized):

```
Fleet API Authentication

Client ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Client Secret: ****************

Registering partner account in Fleet API (region NA)...
  ✓ Partner account registered in region NA

Starting OAuth2 with vehicle scopes...

Choose method:
  1 - Login via browser (OAuth2 + PKCE)     ← pick this
  2 - Paste refresh token directly

Opening browser for Tesla login...
```

Your browser opens Tesla's login page. After you log in, Tesla redirects to a **blank page** whose URL looks like:

```
https://auth.tesla.com/void/callback?code=NA_<long-opaque-string>&issuer=...&state=...
```

Copy the **full URL** from the address bar and paste it back in the terminal:

```
Paste the redirect URL here: https://auth.tesla.com/void/callback?code=NA_...&state=...
Exchanging code for tokens...
✓ Fleet API authenticated. Backend set to 'fleet'.
```

That's it. Tokens are stored in your system keyring (never plain text). Verify:

```bash
tesla vehicle list
# ┏━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━┳━━━━━━━┓
# ┃ Vin               ┃ Name ┃ State   ┃ Model ┃
# ┡━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━╇━━━━━━━┩
# │ 5YJ3E1EA0JF000000 │      │ offline │       │
# └───────────────────┴──────┴─────────┴───────┘
```

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Partner registration failed: 403` | Public key not reachable. Re-check `curl -sI` against your domain — must return 200. |
| `Partner registration failed: 412` | Domain in `fleet.domain` config does not match what's registered in developer.tesla.com. |
| `invalid_client` on token exchange | Client Secret wrong, or Redirect URI in your app ≠ `https://auth.tesla.com/void/callback`. |
| `insufficient_scope` later | App missing one of `vehicle_device_data`, `vehicle_cmds`, `vehicle_charging_cmds`, `vehicle_location`. Edit the app and rerun `tesla config auth fleet`. |
| `tesla vehicle location` returns `0.0, 0.0` | App missing `vehicle_location` scope. Tesla split GPS into its own scope for privacy. Add it to the app, re-auth. |
| Vehicle shows as `offline` forever | Wake it first: `tesla vehicle wake`. Fleet API keeps the car asleep more aggressively than Owner API did. |
| `HTTP 412` after auth | Region mismatch — newer Colombian/LATAM VINs route through `na`. Check: `tesla config set fleet.region na`. |

### Signed commands — 2024.26+ firmware

Plain Fleet API (the setup above) supports **all read endpoints** — vehicle data, charge state, alerts, release notes, location, etc. — and that's ~80% of what tesla-cli does.

Vehicles on firmware **2024.26 or newer** reject unsigned write commands (lock/unlock, sentry, climate, window control, charge start/stop, etc.) with:

```
HTTP 403: Tesla Vehicle Command Protocol required
```

tesla-cli surfaces this as an actionable error:

> \`command 'window_control' …\` is not available on this backend.  
> Switch to the fleet-signed backend: `tesla config set backend fleet-signed`

The `fleet-signed` backend wraps the [`tesla-fleet-api`](https://pypi.org/project/tesla-fleet-api/) library, which speaks Tesla's Vehicle Command Protocol (end-to-end encrypted, handshake-based). Setup requires (a) installing the optional extras, and (b) a paired private/public key pair the vehicle trusts — the public key lives at your registered domain, and the private key must be importable by `tesla-fleet-api`. A step-by-step guide is tracked in [docs/roadmap.md](docs/roadmap.md); contributions welcome.

Reads always work on plain `fleet` — you can postpone `fleet-signed` until you actually need a write command.

### Rotating credentials

Client secrets can be regenerated in developer.tesla.com at any time. After rotating:

```bash
tesla config auth fleet   # paste new client_id + secret, re-auth
```

Tokens auto-refresh; the refresh token is stored in the keyring under `fleet-refresh-token`.

---

## Features

### Order Tracking
Track your Tesla order with change detection, push notifications, delivery ETA estimation, and a 13-gate delivery journey tracker.

### Vehicle Control
Lock/unlock, charging, climate, sentry mode, windows, trunk/frunk, software updates, speed limit, and 50+ more commands. Three backends: Owner API (free), Tessie, Fleet API (with signed-command support for 2024.26+ firmware). Scene commands (`tesla scene morning/goodnight/trip`) apply multi-step routines in one shot. Quick status with `--oneline` for tmux/cron. Export state to JSON/CSV.

### Charging Intelligence
Unified charging sessions from TeslaMate + Fleet API with cost tracking. Schedule preview, forecast, cost summary, CSV export. Supercharging invoices download (`tesla charge invoices`). 27 Prometheus gauges for Grafana dashboards.

### Energy (Powerwall / Solar)
Monitor Powerwall backup reserve, grid state, solar production, and storm watch mode. Set backup percentage and energy mode without leaving the terminal.

### Automation Engine
Event-driven automation with 9 trigger types (geofence, charge %, time, climate, sentry, battery, speed, odometer, custom). Daemon management — start, stop, status, and log tailing in one command group.

### Fleet Telemetry
Self-hosted real-time streaming via Tesla's Fleet Telemetry protocol. Docker-managed receiver with automatic config push — low-latency alternative to polling.

### Data Sources
15 registered sources with TTL caching: Tesla APIs, VIN decode (140+ option codes), NHTSA recalls, RUNT (Colombia), SIMIT, ship tracking. Historical snapshots with diff comparison and HTML/PDF export. Drive path export to GPX/GeoJSON from TeslaMate.

### Portal Documents
Download MVPA, purchase invoices, and other Tesla portal documents directly: `tesla portal documents`.

### TeslaMate Analytics
Trip history, charging sessions, cost reports, drive heatmaps, vampire drain analysis, and more — from your TeslaMate PostgreSQL database. Includes managed Docker stack (one-command install).

### REST API + Web Dashboard
FastAPI server with 143+ endpoints: vehicle, charge, climate, security, notifications, dossier, TeslaMate. SSE live stream, Prometheus metrics (27 gauges), mobile-friendly React dashboard with Leaflet live map (dark tiles) and Recharts analytics visualizations.

### Integrations
MQTT + Home Assistant auto-discovery (15 sensors), ABRP live telemetry, BLE local control, geofencing with alerts, Apprise notifications (100+ services), Apple Shortcuts via `web+tesla://` URL scheme. Config doctor validates all connections.

### Claude Code Plugin
Talk to your Tesla in natural language via [Claude Code](https://claude.ai/claude-code). The plugin lives in [`plugins/claude-code/`](plugins/claude-code/) — 12 skills covering status, control, charging, order tracking, dossier, analytics, automations, telemetry, and the web dashboard. See the [plugin README](plugins/claude-code/README.md) for setup.

---

## Project Structure

```
tesla/
├── src/tesla_cli/         # Python CLI + FastAPI backend
│   ├── core/              # Business logic (backends, models, providers)
│   ├── cli/               # Typer CLI (14 command groups, 278+ commands)
│   ├── api/               # FastAPI REST API (143+ endpoints, SSE, Prometheus)
│   └── infra/             # Docker Compose lifecycle
├── ui/                    # React 19 + Ionic web dashboard (10 pages)
├── plugins/
│   └── claude-code/       # Claude Code plugin (12 skills)
├── tests/                 # pytest suite (1682 tests)
├── docs/                  # Architecture, API ref, user guide, roadmap
└── docker/                # TeslaMate stack configs
```

---

## Documentation

| Document | Description |
|----------|-------------|
| **[User Guide](docs/user-guide.md)** | Complete command reference (13 command groups) |
| **[Architecture](docs/architecture.md)** | System design, provider layers, data flow, design decisions |
| **[Target Architecture](docs/TARGET-ARCHITECTURE.md)** | Source-first system design for Mission Control, domains, alerts, and storage |
| **[Migration Plan](docs/MIGRATION-PLAN-SOURCE-FIRST.md)** | Phased path from legacy Mission Control blob to source/domain/event architecture |
| **[Configuration](docs/configuration.md)** | Config keys, auth, tokens, environment variables |
| **[API Reference](docs/api-reference.md)** | REST endpoints, SSE stream, Prometheus metrics, web dashboard |
| **[Data Sources](docs/data-sources.md)** | Tesla API catalog, third-party services, registered sources |
| **[Roadmap](docs/roadmap.md)** | Upcoming features and remaining gaps |
| **[Competitive Analysis](docs/research/competitive-analysis.md)** | 20-tool ecosystem deep dive |
| **[Changelog](CHANGELOG.md)** | Version history (v0.1.0 → v4.9.0) |
| **[Contributing](CONTRIBUTING.md)** | Development setup, testing, pull requests |

---

## Docker

### Quick Start

```bash
docker compose up -d
```

Dashboard at `http://localhost:8080`.

## Development

Fastest local setup:

```bash
make install   # one-time: Python + Node deps
make dev       # backend on :8080 + Vite UI on :5173
```

Open:

- UI dev: `http://localhost:5173`
- API/docs: `http://localhost:8080/api/docs`

Useful commands:

```bash
make api       # backend only, with --reload
make ui        # frontend only, Vite dev server with proxy to :8080
make build     # compile UI into src/tesla_cli/api/ui_dist
make serve     # production-style run (build + backend-served UI on :8080)
```

Notes:

- In dev, the React app automatically uses Vite's `/api` proxy to `http://localhost:8080`.
- You do not need to set `localStorage.tesla_api_url` for local dev.
- For a non-default API target, set `VITE_TESLA_API_URL` before `make ui`.

### Full Stack (with TeslaMate + Grafana)

```bash
docker compose -f docker-compose.full.yml up -d
```

- Dashboard: `http://localhost:8080`
- TeslaMate: `http://localhost:4000`
- Grafana: `http://localhost:3000`

---

## Development

```bash
uv sync --extra dev --extra serve --extra teslaMate --extra fleet --extra pdf
uv run pytest -m "not integration"         # unit tests (1682 tests)
uv run ruff check src/ tests/              # lint
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full development workflow.

---

## License

MIT — see [LICENSE](LICENSE)
