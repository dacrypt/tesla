# Roadmap

> Forward-looking only. For shipped features, see [CHANGELOG.md](../CHANGELOG.md).
> For competitive positioning, see [research/competitive-analysis.md](research/competitive-analysis.md).

---

## Current State (v4.0.0)

100+ commands across 14 groups, 1132 tests, 7 providers across 4 layers, React dashboard, managed TeslaMate stack, 15 registered data sources.

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

#### Battery Health Source
- Add Tessie `battery_health_measurements` as a registered data source
- Track degradation over time (important for EV resale value)
- TeslaMate also calculates from charge data (already in `dossier battery-health`)

#### Charge History Unification
- Fleet API `charge_history` + TeslaMate `charging_processes` + Tessie `charges`
- Unified view with cost tracking across all sources

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

#### Automation Engine
- Generalize `order watch --on-change-exec` to vehicle state change automations
- Triggers + conditions + actions (inspired by Tessie)

### P3 — Lower Priority

#### Powerwall / Solar Integration
Fleet API energy endpoints exist but require energy product ownership.
- Energy site status, solar generation, grid flow
- Operating mode (self-powered, backup, time-of-use)
- Storm watch

#### Additional Tessie Data
- `firmware_alerts`, `tire_pressure` history, `weather`, `consumption`
- `historical_states`, `idles`, `map` image generation

#### TeslaMate/TeslaFi Data Import
- `tesla teslaMate import` from CSV/JSON

#### Alexa / Siri Integration

---

## Feature Matrix (Summary)

Full 20-tool competitive analysis: [research/competitive-analysis.md](research/competitive-analysis.md)

| Capability | tesla-cli | Best Alternative |
|------------|:---------:|:----------------:|
| Order tracking + change detection | Yes | TOST |
| Vehicle control (CLI) | Yes (62 cmds) | tesla-control (Go) |
| VIN decode + NHTSA recalls | Yes | -- |
| Dossier (aggregated vehicle file) | Yes | -- |
| TeslaMate integration | Yes | TeslaMate native |
| MQTT + HA auto-discovery | Yes | TeslaMate native |
| REST API + Web dashboard | Yes | Tessie (SaaS) |
| Colombia-specific (RUNT, SIMIT) | Yes | -- |
| BLE signed commands | Partial (wrapper) | tesla-control (native) |
| Fleet Telemetry streaming | Not yet | Teslemetry |
| Powerwall / Solar | Not yet | TeslaMate, TeslaFi |
