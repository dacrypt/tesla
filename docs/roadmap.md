# Roadmap

> Forward-looking only. For shipped features, see [CHANGELOG.md](../CHANGELOG.md).
> For competitive positioning, see [research/competitive-analysis.md](research/competitive-analysis.md).

---

## Current State (v4.8.0)

175+ commands across 25 groups, 1679 tests, 83 API endpoints, 27 Prometheus gauges, React dashboard with live map + Recharts analytics, 7 providers, managed TeslaMate + Fleet Telemetry stacks, 15 data sources, 6 i18n languages, 17 --oneline commands, Claude Code plugin (11 skills), automation engine, Powerwall/Solar support.

---

## Shipped (v4.0 → v4.8.0)

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

### P3 — Lower Priority

#### 1. Dashcam Video Processing
- Wrap `tesla_dashcam` for clip download and processing
- `tesla vehicle dashcam-export` — pull clips from USB drive

#### 2. Fleet Battery Benchmarking
- Community opt-in degradation dataset
- Compare your pack against fleet percentile by age/mileage

#### 3. TezLab Data Import
- Import historical data from TezLab app export
- Migration path for users switching from TezLab

#### 4. Smart Home Integrations
- HomeKit via HomeBridge plugin
- Google Home / IFTTT webhooks
- Alexa skill for voice control

#### 5. Customizable Dashboard Tiles
- User-configurable widget layout in React dashboard
- Drag-and-drop tile ordering, show/hide per preference

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
| tmux/polybar integration (10 --oneline) | ✅ | -- |
| Colombia-specific (RUNT, SIMIT, openquery) | ✅ | -- |
| Claude Code plugin (11 skills, marketplace) | ✅ | -- |
| Apprise notifications (100+ channels) | ✅ | -- |
| Signed commands (fleet-signed backend) | ✅ | tesla-control (native) |
| Fleet Telemetry streaming (self-hosted) | ✅ | -- |
| Automation engine (9 triggers + actions) | ✅ | Tessie |
| Supercharging invoices | ✅ | Tessie |
| Portal document download | ✅ | TOST |
| Drive path GPX/GeoJSON export | ✅ | TeslaMate |
| BLE key management (enroll, list, remove, state reads) | ✅ | tesla-control |
| Safety Score (Insurance telematics) | ✅ | -- (first-mover) |
| Service scheduling (history, appointments, reminders) | ✅ | -- (first-mover) |
| Location-based charging/precondition schedules | ✅ | tesla-control |
| EV vs gas savings calculator | ✅ | Stats for Tesla |
| Powerwall / Solar | ✅ | TeslaMate, TeslaFi |
