# Roadmap

> Forward-looking only. For shipped features, see [CHANGELOG.md](../CHANGELOG.md).
> For competitive positioning, see [research/competitive-analysis.md](research/competitive-analysis.md).

---

## Current State (v4.7.1)

130+ commands across 17 groups, 1243 tests, 70 documented API endpoints, 27 Prometheus gauges, React dashboard with 6 quick actions, 7 providers, managed TeslaMate stack, 15 data sources, 6 i18n languages, 8 --oneline commands for tmux/polybar.

---

## Shipped (v4.0 → v4.7)

- ✅ **Charge History Unification** — `charge sessions` merges TeslaMate + Fleet API
- ✅ **Battery Health** — `teslaMate battery-degradation` + `vehicle battery-health`
- ✅ **Vehicle Automations** — `vehicle watch --on-change-exec`
- ✅ **Daily Companion** — `vehicle ready`, `charge last`, `charge weekly`, `vehicle status-line`
- ✅ **REST API Surface** — 70 endpoints (security, notify, geofence, alerts, health probe)
- ✅ **Dashboard Polish** — Sentry/Trunk quick actions, dead pages removed
- ✅ **CLI Restructuring** — 25 → 17 groups, dossier redistributed
- ✅ **Output Consistency** — 8 --oneline commands, JSON mode on all data commands
- ✅ **Infrastructure** — config export-env, health probe, uninstall-service
- ✅ **Charge Notifications** — `charge watch-complete` with Apprise integration

---

## Remaining Gaps

### P1 — High Priority

#### Vehicle Command Protocol (Signed Commands)
Required for 2024.26+ firmware vehicles that reject unsigned Fleet API commands.
- Key enrollment workflow
- End-to-end signed command dispatch
- NFC key pairing
- Alternative: `tesla-http-proxy` auto-signing

#### Fleet Telemetry Integration
Real-time WebSocket streaming eliminates polling (no vampire drain from API calls).
- Requires: FQDN, TLS cert, fleet-telemetry Go server
- Alternative: Teslemetry.com as hosted proxy (no infra needed)
- Sub-second data for location, energy monitoring

### P2 — Medium Priority

#### Portal Document Download
- 7 documents available at `/teslaaccount/order/{RN}/documents/{id}`
- Requires authenticated browser session (patchright)
- Archive MVPA, invoice, registration docs locally

#### Supercharging Invoice Tracking
- Tessie `/charging_invoices` provides this
- Expense tracking and tax documentation

#### Drive Path Recording
- Tessie `driving_path` gives GPS traces
- Heatmaps, route analysis

#### Advanced Automation Engine
- Build on `--on-change-exec` with config-based rules
- Triggers: battery_below, sentry_armed, location_changed, charging_complete
- Actions: notify, exec, climate-on, lock

### P3 — Lower Priority

#### Powerwall / Solar Integration
Fleet API energy endpoints exist but require energy product ownership.

#### Additional Tessie Data
- `firmware_alerts`, `tire_pressure` history, `weather`, `consumption`

#### TeslaMate/TeslaFi Data Import
- `tesla teslaMate import` from CSV/JSON

---

## Feature Matrix (Summary)

Full 20-tool competitive analysis: [research/competitive-analysis.md](research/competitive-analysis.md)

| Capability | tesla-cli | Best Alternative |
|------------|:---------:|:----------------:|
| Order tracking + change detection | Yes | TOST |
| Vehicle control (CLI) | Yes (130+ cmds) | tesla-control (Go) |
| Daily companion (ready, last-seen, status-line) | Yes | -- |
| Charging intelligence (sessions, weekly, cost) | Yes | TeslaFi |
| Battery degradation tracking | Yes | Tessie |
| VIN decode + NHTSA recalls | Yes | -- |
| REST API (70 endpoints) | Yes | Tessie (SaaS) |
| Prometheus metrics (27 gauges) | Yes | TeslaMate native |
| TeslaMate integration | Yes | TeslaMate native |
| MQTT + HA auto-discovery | Yes | TeslaMate native |
| Web dashboard (React) | Yes | Tessie (SaaS) |
| tmux/polybar integration | Yes | -- |
| Colombia-specific (RUNT, SIMIT) | Yes | -- |
| Claude Code plugin | Yes | -- |
| BLE signed commands | Partial (wrapper) | tesla-control (native) |
| Fleet Telemetry streaming | Not yet | Teslemetry |
| Powerwall / Solar | Not yet | TeslaMate, TeslaFi |
