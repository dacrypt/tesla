# Tesla CLI

[![CI](https://github.com/dacrypt/tesla/actions/workflows/ci.yml/badge.svg)](https://github.com/dacrypt/tesla/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Control your Tesla and track your order from the terminal — with a live web dashboard, REST API, MQTT integration, and analytics.

```
tesla vehicle ready              → am I ready to drive?
tesla charge status --oneline    → 🔋 72% | ⚡ 11kW | 1h30m to 80%
tesla charge last                → most recent charge session + cost
tesla charge weekly              → weekly kWh + cost summary
tesla teslaMate battery-degradation → battery health trend
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

`tesla setup` is an interactive wizard: Tesla OAuth2 authentication, auto-discovery of your VIN and order number, optional vehicle control backend, and first data build.

Config: `~/.tesla-cli/config.toml` | Tokens: system keyring (never plain text)

### Optional extras

```bash
uv tool install -e ".[teslaMate]"   # TeslaMate PostgreSQL integration
uv tool install -e ".[serve]"       # REST API server + web dashboard
uv tool install -e ".[fleet]"       # Tesla Fleet API direct
uv tool install -e ".[pdf]"         # PDF dossier export
```

---

## Features

### Order Tracking
Track your Tesla order with change detection, push notifications, delivery ETA estimation, and a 13-gate delivery journey tracker.

### Vehicle Control
Lock/unlock, charging, climate, sentry mode, windows, trunk/frunk, software updates, speed limit, and 50+ more commands. Three backends: Owner API (free), Tessie, Fleet API. Quick status with `--oneline` for tmux/cron. Export state to JSON/CSV.

### Charging Intelligence
Unified charging sessions from TeslaMate + Fleet API with cost tracking. Schedule preview, forecast, cost summary, CSV export. 27 Prometheus gauges for Grafana dashboards.

### Data Sources
15 registered sources with TTL caching: Tesla APIs, VIN decode (140+ option codes), NHTSA recalls, RUNT (Colombia), SIMIT, ship tracking. Historical snapshots with diff comparison and HTML/PDF export.

### TeslaMate Analytics
Trip history, charging sessions, cost reports, drive heatmaps, vampire drain analysis, and more — from your TeslaMate PostgreSQL database. Includes managed Docker stack (one-command install).

### REST API + Web Dashboard
FastAPI server with 45+ endpoints: vehicle, charge, climate, security, notifications, dossier, TeslaMate. SSE live stream, Prometheus metrics (27 gauges), mobile-friendly React dashboard.

### Integrations
MQTT + Home Assistant auto-discovery (15 sensors), ABRP live telemetry, BLE local control, geofencing with alerts, Apprise notifications (100+ services). Config doctor validates all connections.

### Claude Code Plugin
Talk to your Tesla in natural language via [Claude Code](https://claude.ai/claude-code). Install the [tesla-claude-plugin](https://github.com/dacrypt/tesla-claude-plugin) and ask Claude *"how's my battery?"* or *"lock my car"*. Nine skills covering status, control, charging, order tracking, dossier, analytics, and the web dashboard.

### Data Sources
15 registered sources with TTL caching and change detection: Tesla APIs, NHTSA, RUNT (Colombia), SIMIT, Fasecolda, ship tracking, and more via the OpenQuery library.

---

## Documentation

| Document | Description |
|----------|-------------|
| **[User Guide](docs/user-guide.md)** | Complete command reference (13 command groups) |
| **[Architecture](docs/architecture.md)** | System design, provider layers, data flow, design decisions |
| **[Configuration](docs/configuration.md)** | Config keys, auth, tokens, environment variables |
| **[API Reference](docs/api-reference.md)** | REST endpoints, SSE stream, Prometheus metrics, web dashboard |
| **[Data Sources](docs/data-sources.md)** | Tesla API catalog, third-party services, registered sources |
| **[Roadmap](docs/roadmap.md)** | Upcoming features and remaining gaps |
| **[Competitive Analysis](docs/research/competitive-analysis.md)** | 20-tool ecosystem deep dive |
| **[Changelog](CHANGELOG.md)** | Version history (v0.1.0 → v4.0.0) |
| **[Contributing](CONTRIBUTING.md)** | Development setup, testing, pull requests |

---

## Development

```bash
uv sync --extra dev --extra serve --extra teslaMate --extra fleet --extra pdf
uv run pytest -m "not integration"         # unit tests (1132 tests)
uv run ruff check src/ tests/              # lint
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full development workflow.

---

## License

MIT — see [LICENSE](LICENSE)
