# Roadmap

> Forward-looking only. For shipped features, see [CHANGELOG.md](../CHANGELOG.md).
> For competitive positioning, see [research/competitive-analysis.md](research/competitive-analysis.md).

---

## Current State (v4.7.3)

140+ commands across 17 groups, 1243+ tests, 70 documented API endpoints, 27 Prometheus gauges, React dashboard with 6 quick actions, 7 providers, managed TeslaMate stack, 15 data sources, 6 i18n languages, 9 --oneline commands for tmux/polybar, Claude Code plugin (9 skills).

---

## Shipped (v4.0 → v4.7.3)

- ✅ **Charge History Unification** — `charge sessions` merges TeslaMate + Fleet API
- ✅ **Battery Health** — `teslaMate battery-degradation` + `vehicle battery-health`
- ✅ **Vehicle Automations** — `vehicle watch --on-change-exec`
- ✅ **Daily Companion** — `vehicle ready`, `charge last`, `charge weekly`, `vehicle status-line`
- ✅ **REST API Surface** — 70 endpoints (security, notify, geofence, alerts, health probe)
- ✅ **Dashboard Polish** — Sentry/Trunk quick actions, dead pages removed, vehicle info footer
- ✅ **CLI Restructuring** — 25 → 17 groups, dossier redistributed
- ✅ **Output Consistency** — 9 --oneline commands, JSON mode on all data commands
- ✅ **Infrastructure** — config export-env, health probe, uninstall-service
- ✅ **Charge Notifications** — `charge watch-complete` with Apprise integration
- ✅ **Full Vehicle Control** — charge limit/amps, climate temp/seat/steering/dog/camp/bioweapon/defrost, remote-start, speed-limit, valet, homelink, dashcam, windows, media, navigation
- ✅ **Nearby Chargers** — `vehicle nearby` (Superchargers + destination)
- ✅ **Scheduled Charging/Departure** — `charge schedule`, `charge departure`, `charge schedule-preview`, `charge profile`
- ✅ **CSV Export** — `charge sessions --csv`, `charge cost-summary --csv`
- ✅ **TPMS Tires** — `vehicle tires`
- ✅ **Actionable 412 Error** — `EndpointDeprecatedError` with Fleet/Tessie migration guidance
- ✅ **Order Status --oneline** — compact emoji output for tmux/scripts
- ✅ **RUNT Default VIN** — `tesla data runt` uses configured VIN automatically
- ✅ **Claude Code Plugin v1.1.0** — marketplace-ready, 9 skills, guardrails, RUNT in pre-delivery fallback

---

## Remaining Gaps

### P1 — High Priority

#### 1. Vehicle Command Protocol (Signed Commands)
Required for 2024.26+ firmware vehicles that reject unsigned Fleet API commands.
- Key enrollment workflow (`tesla ble enroll`)
- End-to-end signed command dispatch
- NFC key pairing
- Alternative: `tesla-http-proxy` auto-signing
- **Blocker**: Without this, vehicle control fails on new firmware

#### 2. Fleet Telemetry Integration
Real-time WebSocket streaming eliminates polling (no vampire drain from API calls).
- Requires: FQDN, TLS cert, fleet-telemetry Go server
- Alternative: Teslemetry.com as hosted proxy (no infra needed)
- Sub-second data for location, energy monitoring
- **Value**: Only way to achieve zero vampire drain while logging

### P2 — Medium Priority

#### 3. Portal Document Download
- 7 documents available at `/teslaaccount/order/{RN}/documents/{id}`
- Requires authenticated browser session (patchright/playwright)
- Archive MVPA, invoice, registration docs locally
- `tesla order documents` — list and download

#### 4. Supercharging Invoice Tracking
- Tessie `/charging_invoices` provides this
- Fleet API may add this in future
- `tesla charge invoices` — expense tracking and tax documentation

#### 5. Drive Path Recording
- Tessie `driving_path` gives GPS traces per drive
- TeslaMate already stores GPS data in PostgreSQL
- `tesla teslaMate drive-path <trip_id>` — export GPX/GeoJSON
- Enables: heatmaps, route replay, geo-analysis

#### 6. Advanced Automation Engine
Only Tessie has this — major differentiator.
- Build on `--on-change-exec` with config-based rules
- `tesla automations add` — YAML rule definitions
- Triggers: battery_below, sentry_event, location_enter/exit, charging_complete, time_of_day
- Actions: notify, exec, climate-on, lock, charge-limit
- Daemon: `tesla automations run` — watches vehicle state and fires rules

### P3 — Lower Priority

#### 7. Powerwall / Solar Integration
Fleet API energy endpoints exist but require energy product ownership.
- `tesla energy status` — solar production, battery level, grid usage

#### 8. Additional Tessie Data
- `firmware_alerts`, `tire_pressure` history, `weather`, `consumption`
- Low priority — most available via TeslaMate already

#### 9. TeslaMate/TeslaFi Data Import
- `tesla teslaMate import` from CSV/JSON/TeslaFi export
- For users migrating from other platforms

---

## Feature Matrix (Summary)

Full 20-tool competitive analysis: [research/competitive-analysis.md](research/competitive-analysis.md)

| Capability | tesla-cli | Best Alternative |
|------------|:---------:|:----------------:|
| Order tracking + change detection | ✅ | TOST |
| Vehicle control (CLI, 140+ cmds) | ✅ | tesla-control (Go) |
| Daily companion (ready, last-seen, status-line) | ✅ | -- |
| Charging intelligence (sessions, weekly, cost, CSV) | ✅ | TeslaFi |
| Battery degradation tracking | ✅ | Tessie |
| VIN decode + NHTSA recalls | ✅ | -- |
| Climate (temp, seats, steering, dog/camp/bio/defrost) | ✅ | tesla-control |
| Media + Navigation | ✅ | tesla-control |
| Scheduled charging/departure | ✅ | TeslaFi |
| REST API (70 endpoints) | ✅ | Tessie (SaaS) |
| Prometheus metrics (27 gauges) | ✅ | TeslaMate native |
| TeslaMate integration | ✅ | TeslaMate native |
| MQTT + HA auto-discovery | ✅ | TeslaMate native |
| Web dashboard (React PWA) | ✅ | Tessie (SaaS) |
| tmux/polybar integration (9 --oneline) | ✅ | -- |
| Colombia-specific (RUNT, SIMIT, openquery) | ✅ | -- |
| Claude Code plugin (9 skills, marketplace) | ✅ | -- |
| Apprise notifications (100+ channels) | ✅ | -- |
| BLE signed commands | ⏳ Partial (wrapper) | tesla-control (native) |
| Fleet Telemetry streaming | ⏳ Not yet | Teslemetry |
| Automation engine (triggers + actions) | ⏳ Not yet | Tessie |
| Powerwall / Solar | ⏳ Not yet | TeslaMate, TeslaFi |
