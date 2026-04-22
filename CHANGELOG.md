# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.9.4] - 2026-04-22

### Core — Route model extension (prerequisite for native EV planner)

- **`Route` dataclass** gains optional `source: str | None = None` and
  `source_id: str | None = None` fields, mirroring the `Place` model. Tracks
  where a saved route came from (e.g. `"native-planner"`, `"abrp"`, or
  `None` for hand-created via `tesla nav route create`).
- **`NavStore.save_route()`** replaces its hardcoded 3-key dict with the
  `save_place()` filter-None pattern: only serializes non-None optional
  fields, keeping TOML clean. Adds a **dedupe guard**: saving a route with
  `source != None` is skipped + stderr-warned when an existing route with
  the same name has `source=None` (hand-created). Imported/planned routes
  never overwrite user-created ones.
- **`NavStore.get_route()` + `list_routes()`** read the new fields with
  `.get()` defaults — old `nav.toml` files with only `name`+`created_at`
  +`waypoints` load unchanged.
- Zero code changes to `Waypoint` dataclass (5 fields, untouched).

### Why

Unblocks the phased native EV route planner roadmap
(`.omc/plans/native-ev-planner.md`): Phase 1 `tesla nav plan <from> <to>`
will tag generated routes with `source="native-planner"` so that re-running
a plan cannot clobber a route you created by hand with `tesla nav route
create`. Ships standalone (no dependency on later phases).

### Quality

- 6 new tests (default-None roundtrip, full-source roundtrip, old-TOML
  backward compat, hand-created dedupe, same-source overwrite, hand-
  created-over-hand-created overwrite).
- Full suite: **1888 passed**, 0 fail. Ruff clean.

## [4.9.3] - 2026-04-22

### i18n — English Default
- Translated the OAuth login flow, Fleet API setup walkthrough, and first-run
  wizard panels to English. Spanish prompts that were leaking into the default
  locale (auth method picker, browser-redirect instructions, token-exchange
  progress, partner-registration messages, post-login summary, RUNT lookup
  progress) now speak English. The README Fleet-auth transcript matches.
- Affected: `core/auth/oauth.py`, `cli/commands/login.py`, `cli/commands/config_cmd.py`,
  `cli/commands/data_cmd.py`, `core/sources.py`. Spanish/Portuguese translations
  in `cli/i18n.py` are unchanged — they're the locale bundles, not leaks.

### CLI — Favorites Importer
- **`tesla nav place import <path>`** — bulk-import favorites from Google Takeout
  (CSV + GeoJSON), KML, or GPX files. Auto-detects format by extension; explicit
  `--format` override available. Supports `--tag`, `--max-geocode`, `--dry-run`.
- **`tesla nav place send <alias>`** — dispatch a saved place to the car via the
  signed `share` command. Honors `--dry-run` and `--vin`; falls back to
  `"lat,lon"` when no raw address is stored.
- **Stable dedupe** via `(source, source_id)` — re-importing the same file after
  renaming an entry in Google Maps **updates** the existing place rather than
  duplicating. Hand-created places (`source=None`) are never overwritten.
- **File-size guard** at 25 MB; **geocode cap** at 20 calls (configurable).
- Stdlib-only parsers (`csv`, `json`, `xml.etree`) — zero new dependencies.

### Core
- **`core/nav/dispatch.py`** — new `send_place(backend, vin, address)` function
  decouples the share dispatch from the CLI layer so the upcoming REST API
  endpoint can reuse it. `_dispatch_share` in `cli/commands/nav.py` becomes a
  thin wrapper; `route go` / `route next` behavior unchanged.
- **`Place` model extended** with optional `lat`, `lon`, `tags`, `source`,
  `source_id`, `imported_at` fields. Backward-compatible with existing
  `nav.toml` files (old entries with just `alias`+`raw_address` load unchanged).
- **`NavStore.save_places_bulk(places)`** — idempotent bulk write, returns
  `(imported, updated, skipped)`. Single atomic rename-over, partial-failure
  safe.

### Quality
- 200 new tests (model round-trip, 4 parsers, slugify collision/accents,
  dedupe rules, CLI commands, dispatch mock, file-size guards).
- Full suite: **1882 passed**, 0 fail. Ruff clean.

### Documentation
- `docs/user-guide.md` — new "Favorites Importer" section with command examples
  and dedupe semantics.
- `docs/roadmap.md` — current state advanced to v4.9.3.
- `.omc/plans/nav-favorites-importer.md` — ralplan consensus design record.

## [4.9.2] - 2026-04-20

### CLI — Multi-stop Navigation
- **`tesla nav route`** family — CRUD for named routes, manual advance (`next`),
  simulated auto-advance (`--simulate-arrival-after`), atomic state writes.
- Real Fleet Telemetry arrival source deferred to v4.9.2.1.

## [4.9.0] - 2026-04-06

### Security & Hardening
- **Constant-time API key comparison** via `hmac.compare_digest`
- **PKCE state store bounded** — TTL cleanup (10min) + max 100 entries, 429 on overflow
- **Path traversal protection** on audit PDF download, SPA middleware (`.resolve()` containment), dashcam USB path (mount prefix allowlist)
- **SoQL injection fix** — input sanitization on peajes and estaciones_ev routes
- **Source ID regex validation** on all wildcard API routes
- **Shell automation blocking** — `command`/`exec` actions gated behind `server.allow_shell_automations` config
- **CORS restricted** to configurable origins (`server.cors_origins`, defaults to localhost)
- **Query param caps** — `limit` (500), `days` (3650), `lines` (1000), `months` (120), `sample` (floor 1) on all API routes
- **JSONL rotation** — events/alerts/notifications capped at 10K entries with size-triggered rotation
- **Portal session file** secured with `chmod 0600`
- **15 behavioral security regression tests** covering all hardening fixes
- **NHTSA recalls** now derive model/year from VIN (was hardcoded)
- **User-Agent** updated from `0.1.0` to `__version__`
- **Duplicate Prometheus metric** `tesla_climate_on_state` removed
- **OptionCodes iteration** fixed to use `.codes` list
- **11 ruff lint errors** fixed

### Dashboard
- **Dedicated Order page** with 15-step financing/delivery tracker
- **Energy page** — Powerwall controls, city tariff comparison, cost calculator
- **Automations page** — CRUD rules, quick setup, test/toggle/delete
- **Notification history** timeline in Settings
- **Offline mode** — cached vehicle data when server is down
- **Mobile responsive** — CSS breakpoints for phones/tablets
- **Scene cards** on dashboard (Morning/Goodnight/Trip)
- **Code-split routes** — lazy-loaded pages for faster initial load

### API (30+ new endpoints)
- Energy management: sites, status, backup, mode, storm
- Automations: CRUD, enable/disable, test, status
- Charge scheduling + analytics: sessions, cost, forecast
- Service: history, appointments, reminders
- Scenes: list + execute
- ABRP, BLE, MQTT, Dashcam endpoints
- Energy tariffs: by city/estrato + vehicle location
- 429 rate-limit retry with Retry-After

### CLI
- BLE key management (enroll, list, remove, state reads)
- Safety Score + Service scheduling (first-mover)
- EV vs gas savings calculator
- Location-based charge/precondition schedules
- Country-aware sources (9 countries, 35+ sources)
- Dashcam processing (list/process/export)
- Webhook automations (IFTTT/HomeKit/Google Home)
- Energy tariffs command

### Quality
- 17 UI bugs fixed (critical crashes, color errors, missing guards)
- Error boundary + React.Suspense on all lazy routes
- Flaky test fixed permanently
- 1682 tests passing

## [4.8.0] - 2026-04-05

### New Features

- **Signed Vehicle Commands** — `fleet-signed` backend using tesla-fleet-api for end-to-end encrypted commands (required for 2024.26+ firmware)
- **Self-hosted Fleet Telemetry** — Docker-managed fleet-telemetry Go server with auto-generated TLS certs, zero third-party dependencies
  - `tesla telemetry install/start/stop/restart/status/configure/logs`
  - `tesla vehicle stream-live` — real-time Rich table from fleet-telemetry
  - MQTT dispatcher bridges to TeslaMate Mosquitto
- **Automation Engine** — config-driven rules with 9 trigger types and notify/command actions
  - `tesla automations add/list/remove/enable/disable/run/test`
  - `tesla automations install` — daemon management (launchd on macOS, systemd on Linux)
  - MQTT subscription mode (`--source auto/poll/mqtt`)
  - Default rules: low battery, charge complete, sentry event
- **Portal Document Download** — `tesla order documents [--download]` extracts and downloads MVPA, invoices, registration docs from Tesla portal
- **Supercharging Invoice Tracking** — `tesla charge invoices [--csv]` via Tessie API with cost totals
- **Drive Path Export** — `tesla teslaMate drive-path <ID> [--format gpx|geojson]` for GPS trace export
- **Order Status --oneline** — `tesla order status --oneline` compact emoji output

### Infrastructure

- **Setup Wizard expanded to 7 steps** — `tesla setup` now auto-installs fleet telemetry, TeslaMate, notifications, default automations, and builds data in one command
- **Config doctor** checks fleet-telemetry container health and automation rule count
- **RUNT default VIN** — `tesla data runt` uses configured VIN automatically
- **Actionable 412 error** — `EndpointDeprecatedError` with Fleet/Tessie migration guidance

### Claude Code Plugin

- **v1.1.0** published to `dacrypt/tesla-claude-plugin`
- Marketplace-ready: `marketplace.json`, skill discovery, level metadata
- Guardrails: no auto-configure, no PII from memory, mask VINs
- RUNT query mandatory in pre-delivery fallback
- New skills: automations, telemetry
- Simplified install via `extraKnownMarketplaces`

### Tests

- FastAPI API tests now skip gracefully when fastapi not installed
- Added tests for order --oneline, RUNT default VIN, config doctor

## [4.7.3] - 2026-04-03

### Dashboard

- **Ready-to-Drive badge** in header — green "✓ Ready" or yellow "⚠ N" based on real-time SSE state
- **Vehicle info footer** — software version, sentry status, odometer (km)
- Claude Code Plugin section in README

### Housekeeping

- Removed accidentally committed .codex/.omx files, added to .gitignore
- Quickstart guide: `tesla quickstart`
- API reference: all 70 endpoints documented

### Tests

- 1243 tests passing

## [4.7.2] - 2026-04-03

### Discoverability

- **`tesla quickstart`** — built-in quick-start guide showing daily workflows
- Roadmap comprehensively updated with all shipped features
- API reference: all 70 endpoints documented

### Tests

- 1243 tests passing

## [4.7.1] - 2026-04-03

### New Commands

- **`tesla charge watch-complete`** — watch for charging to finish and send notification
  Polls charge state, shows progress, notifies via Apprise when battery reaches limit.

### Documentation

- **API reference completed** — all 70 endpoints now documented including:
  /api/health, /vehicle/status-line, /vehicle/last-seen, /charge/weekly,
  /teslaMate/battery-degradation, geofence CRUD, Colombia public data
- README: Claude Code Plugin section added

### Tests

- 1243 tests passing

## [4.7.0] - 2026-04-03

### Infrastructure Integration

- **`tesla config export-env`** — export config as environment variables for Docker/systemd
  - `tesla config export-env -o .env` — write .env file
  - `tesla config export-env --docker` — Docker Compose YAML format
- **`GET /api/health`** — liveness probe for Docker HEALTHCHECK / Kubernetes
- **`tesla vehicle status-line`** — tmux/polybar/waybar status bar integration
- **`GET /api/vehicle/status-line`** — minimal JSON for dashboard widgets

### Output Consistency

- `tesla climate status --oneline/--json` — was missing, now consistent
- `tesla vehicle sentry --oneline` — quick sentry check
- Security error messages: consistent `[red]` formatting

### Tests

- 1242 tests passing
- TypeScript strict mode: 0 errors
- React build: clean

## [4.6.3] - 2026-04-03

### Status Bar Integration

- **`tesla vehicle status-line`** — ultra-compact output for tmux, polybar, waybar, i3status:
  `🔋72% 🔒 🛡 🌡22°` (no Rich formatting, pure text + icons)
- **`GET /api/vehicle/status-line`** — minimal JSON for dashboard widgets
- tmux usage: `set -g status-right '#(tesla vehicle status-line 2>/dev/null)'`
- 1239 tests passing

## [4.6.2] - 2026-04-03

### Output Consistency

- **`tesla climate status --oneline`** — `🌡 22°C in | 18°C out | HVAC off`
- **`tesla climate status --json`** — raw JSON (was missing)
- **`tesla vehicle sentry --oneline`** — `🛡 Sentry ON`
- **`GET /api/vehicle/last-seen`** — vehicle online/asleep + last contact time
- Security error messages: consistent `[red]...[/red]` across all commands
- React: `getVehicleLastSeen()` client method
- 1237 tests passing

## [4.6.1] - 2026-04-03

### New Commands

- **`tesla teslaMate monthly-cost`** — month-over-month charging cost trend with arrows
- **`tesla vehicle last-seen`** — when was the vehicle last online? (online/asleep + time ago)

### Polish

- Setup wizard: completion message now shows config doctor + daily commands
- README hero examples: updated with daily-use commands (ready, oneline, weekly)
- App help text: more descriptive tagline

### Tests

- 1233 tests passing (+4 new)

## [4.6.0] - 2026-04-03

### Charging Intelligence

- **`tesla charge weekly`** — weekly charging summary (kWh, cost, sessions per ISO week)
- **`GET /api/charge/weekly`** — REST endpoint for weekly charge data

### Battery Intelligence

- **`tesla teslaMate battery-degradation`** — monthly degradation trend from high-SoC charges
- **`GET /api/teslaMate/battery-degradation`** — REST endpoint

### Daily Companion

- **`tesla vehicle ready`** — morning readiness check (battery, climate, alerts)
- **`tesla charge last`** — most recent session with cost
- **`GET /api/vehicle/ready`** + **`GET /api/charge/last`** — REST endpoints

### Documentation

- Roadmap: Battery Health and Charge History marked as done
- Media & Navigation section added to user-guide
- Architecture version updated

### Tests

- 1229 tests passing

## [4.5.2] - 2026-04-03

### Battery Intelligence

- **`tesla teslaMate battery-degradation`** — compute battery degradation from TeslaMate charging data
  - Analyzes high-SoC charges (>=95%) across months to track max rated range trend
  - Color-coded degradation: green (<3%), yellow (3-8%), red (>8%)
  - `--months N` to control analysis window (default 12)
  - JSON mode for scripting
- **`GET /api/teslaMate/battery-degradation`** — REST endpoint for degradation data

### Tests

- 1226 tests passing (+4 new)

## [4.5.1] - 2026-04-03

### API Completeness

- **`GET /api/vehicle/ready`** — readiness assessment (ready flag, battery, climate, issues list)
- **`GET /api/charge/last`** — most recent charging session with cost and source
- React API client: `getVehicleReady()`, `getChargeLast()` methods added

### Documentation

- **Media & Navigation section** added to user-guide.md (play, pause, volume, send-destination, supercharger, home, work)
- api-reference.md updated with all new endpoints
- 1222 tests passing

## [4.5.0] - 2026-04-03

### Daily Companion Commands

- **`tesla vehicle ready`** — morning check-in: "Am I ready to drive?"
  - Assesses battery level, charge status, cabin temperature, lock/sentry state, pending updates
  - Outputs ✅ Ready / ⚠️ Issues with checklist of good/bad items
  - `--oneline`: `✅ Ready | 🔋 82% | 🌡 22°C`
  - `--json`: structured readiness assessment with `ready: true/false`
- **`tesla charge last`** — show the most recent charging session with cost
  - Date, location, kWh, cost (actual or estimated), battery range
  - JSON mode for scripting

### Tests

- 1219 tests passing (+7 new)

## [4.4.2] - 2026-04-03

### Polish

- **i18n**: add 3 missing Spanish setup translations, update `--lang` help to show all 6 languages
- **Homebrew formula**: update from v1.0.0 → v4.4.2
- **CI pipeline**: install all extras in test job (was only installing `dev`, silently skipping ~400 tests)
- **i18n completeness test**: verify all 6 languages have the same translation keys
- 1212 tests passing

## [4.4.1] - 2026-04-03

### Test Quality

- **25 new FastAPI integration tests** for security, notify, and geofence API routes
  (10 security + 7 notify + 7 geofence — full request/response contract verification)
- **Fixed flaky PDF export test** — patched at correct module level, deterministic assertions
- **Zero excluded tests** — all 1209 tests now run in every suite (was excluding 1 flaky test)

## [4.4.0] - 2026-04-03

### Vehicle Automations

- **`tesla vehicle watch --on-change-exec`** — trigger shell commands on vehicle state changes
  (battery, charging, locks, climate, sentry). Changes passed as JSON via `TESLA_CHANGES` env var.

### Geofence REST API

- **`GET /api/geofences`** — list zones with vehicle distance + inside/outside flag
- **`GET /api/geofences/{name}`** — check proximity to a specific zone (haversine calculation)
- **`POST /api/geofences/{name}`** — add/update zone via REST
- **`DELETE /api/geofences/{name}`** — remove zone via REST

### Dashboard

- **Sentry toggle** + **Trunk button** in quick actions (6 total)
- 15 new API client methods (security, notify, alerts, geofences)
- 6 unused legacy pages deleted (-1,550 lines)

### Tests

- 1184 tests passing

## [4.3.2] - 2026-04-03

### React Dashboard

- **Sentry Mode toggle** added to Dashboard quick actions (green when active)
- **Trunk button** added to quick actions (6 total: Lock, AC, Flash, Sentry, Trunk, Horn)
- **API client methods** added for security (lock/unlock/sentry/trunk/horn/flash),
  notifications (list/test/add/remove), and vehicle alerts
- **6 unused pages deleted** (Home, Charge, Climate, Controls, Order, Schedule) — -1550 lines
  Superseded by the Vehicle tab structure.

### Tests

- 1181 tests, UI build clean (TypeScript strict mode)

## [4.3.1] - 2026-04-03

### New Features

- **`tesla charge status --watch`** — live charging monitor (30s refresh, configurable with `--interval`)
- **`tesla charge status --oneline`** — `🔋 65% | ⚡ 11kW | 1h30m to 80% | +12.3kWh`
- **`tesla serve uninstall-service`** — cleanly remove systemd/launchd service files

### Documentation

- Updated user-guide.md with all new commands from v4.1-v4.3
- Updated README.md feature descriptions
- Fixed `query` → `data` rename throughout docs

### Tests

- 1181 tests passing

## [4.3.0] - 2026-04-03

### New API Routes

- **`/api/security/*`** — lock, unlock, sentry on/off, trunk front/rear, horn, flash
- **`/api/notify/*`** — list channels, send test, add channel, remove channel
- **`/api/vehicle/alerts`** — recent vehicle alerts and fault codes
- All security + notification features now accessible from web UI and external integrations

### Extended Config Doctor

- **MQTT broker check** — socket connect test for broker reachability
- **Notifications check** — validates channels are configured
- **Home Assistant check** — HTTP connectivity test for HA URL

### New CLI Features

- **`--oneline` flag** on `vehicle summary` and `charge schedule-preview`
  - `tesla vehicle summary --oneline` → `🔋 72% | 🔒 Locked | 🛡 Sentry ON | 🌡 22°C`
  - `tesla charge schedule-preview --oneline` → `🔌 Charge @ 23:30 | 🚗 Depart @ 07:00`
- **`tesla vehicle export`** — dump vehicle state to JSON or CSV file

### Improvements

- Prometheus metrics expanded from 11 → 27 gauges (TPMS, temperatures, charger details)
- Charge session merge: TeslaMate + Fleet API data combined when both available
- 6 stale delegate files inlined and deleted (-849 lines)
- data_cmd.py organized with clear section headers

### Tests

- 1177 tests passing

## [4.2.3] - 2026-04-03

### New Features

- **`--oneline` flag** for daily-use commands:
  - `tesla vehicle summary --oneline` → `🔋 72% | 🔒 Locked | 🛡 Sentry ON | 🌡 22°C`
  - `tesla charge schedule-preview --oneline` → `🔌 Charge @ 23:30 | 🚗 Depart @ 07:00`
- **`GET /api/vehicle/alerts`** — REST endpoint for recent vehicle alerts and fault codes
- 1172 tests passing

## [4.2.2] - 2026-04-03

### Improvements

- **Prometheus metrics expanded** from 11 → 27 gauges:
  - Charger: voltage, current, charge rate, time to full
  - Temperature: inside, outside, driver setting, climate active
  - TPMS: tire pressure for all 4 tires (fl, fr, rl, rr)
  - State: heading, charge port open
- **Charge session merge** — `_fetch_sessions()` now queries BOTH TeslaMate and Fleet API,
  using TeslaMate as primary source and filling gaps from Fleet API. Source attribution
  shows "TeslaMate + Fleet API" when both contribute.
- 1169 tests passing

## [4.2.1] - 2026-04-03

### Improvements

- **`tesla vehicle export`** — export vehicle state to JSON or CSV file
  - `tesla vehicle export` → JSON to stdout
  - `tesla vehicle export -o state.json` → JSON file
  - `tesla vehicle export -f csv -o state.csv` → CSV with flattened fields
- **Inline 6 stale delegate files** — stream, dashboard, sharing, nav, runt_cmd, simit_cmd
  inlined into vehicle.py, media.py, data_cmd.py and deleted (-849 lines net)
- **Organize data_cmd.py** — clear section headers: Colombian queries vs Vehicle data & export
- 1165 tests passing

## [4.2.0] - 2026-04-02

### Architecture — CLI Restructuring

Cleaned up the CLI from 25 command groups to 17. Every command now has exactly one home — no fallbacks, no deprecation wrappers, no duplicate paths.

**Removed command groups** (absorbed into natural homes):
- `dossier` → commands live in `order`, `vehicle`, `data`
- `query` → renamed to `data`
- `runt`, `simit` → use `data runt`, `data simit`
- `stream` → `vehicle stream`
- `dashboard` → `vehicle dashboard`
- `sharing` → `vehicle invite/invitations/revoke-invite`
- `nav` → `media send-destination/supercharger/home/work`

**New structure:**
```
tesla order gates/estimate/checklist/ships     (delivery lifecycle)
tesla vehicle vin/profile/stream/dashboard     (vehicle identity + monitoring)
tesla data build/history/diff/runt/simit/...   (data sources + exports)
tesla media play/volume/send-destination/...   (media + navigation)
```

Backend layer (`core/backends/dossier.py`, `core/models/dossier.py`) unchanged — only CLI routing changed.

1162 tests passing. Lint clean.

## [4.1.0] - 2026-04-02

### Architecture — Dossier Redistribution

All 16 dossier commands redistributed to their natural homes while preserving full backward compatibility:

- **`tesla order`** +5 commands: `gates`, `estimate`, `checklist`, `ships`, `set-delivery`
- **`tesla vehicle`** +4 commands: `vin`, `option-codes`, `battery-health`, `profile`
- **`tesla query`** +7 commands: `build`, `history`, `diff`, `export-html`, `export-pdf`, `clean`, `data-sources`
- **`tesla dossier *`** still works with migration hints pointing to new locations
- Backend layer unchanged: `core/backends/dossier.py`, `core/models/dossier.py`, API routes
- 13 new migration tests, 1164 total

## [4.0.4] - 2026-04-02

### Bug Fixes

- **Fix `_fetch_sessions()` TeslaMate lookup** — `cfg.teslaMate.dsn` → `cfg.teslaMate.database_url` (property didn't exist, silently skipped TeslaMate data)

### New Commands

- **`tesla dossier sources`** — show all 15 registered data sources with cache status (fresh/stale/empty/error), TTL, category, last refresh. JSON mode support.

### New API Endpoints

- **`GET /api/dossier/sources`** — list data sources with cache freshness (also documented existing dossier endpoints)

### Tests

- 1151 tests passing (+3 new for dossier sources)

## [4.0.3] - 2026-04-02

### Improvements

- **`--csv` export** on `charge sessions` and `charge cost-summary` for analytics workflows
- **Data Sources section** in `dossier export-html` showing API attribution per section
- **RecentCharges dashboard card** — last 5 charging sessions with kWh, cost, location
- **Config validation** — Pydantic Field constraints: cost_per_kwh >= 0, ports 1-65535, QoS 0-2
- **Refactored** `_fetch_sessions()` helper — eliminated ~80 LOC duplication across 3 call sites
- **Fixed** all fpdf2 deprecation warnings (`ln=True` → `new_x`/`new_y` params)
- **New tests** for MQTT commands, providers commands, config validation, CSV export
- 1148 tests passing, 0 deprecation warnings

## [4.0.2] - 2026-04-02

### New Commands

- **`tesla charge sessions`** — unified charging sessions from TeslaMate + Fleet API:
  - Prefers TeslaMate (per-session costs, battery levels, locations)
  - Falls back to Fleet API (aggregated history)
  - Applies `cost_per_kwh` estimation when actual cost is missing
  - Rich table with #, Date, Location, kWh, Cost, Battery columns
- **`tesla charge cost-summary`** — aggregated charging cost report:
  - Total sessions, kWh, cost, avg $/kWh
  - Distinguishes actual vs estimated cost data
  - Works with any source (TeslaMate, Fleet API)
- **`tesla vehicle summary`** — compact one-screen vehicle snapshot:
  - Battery %, range, charging state, climate, location, locks, sentry, software
  - Rich panel with emoji indicators

### New API Endpoints

- **`GET /api/charge/sessions`** — unified charging sessions (TeslaMate > Fleet API)
- **`GET /api/vehicle/summary`** — compact vehicle state JSON

### New Models

- **`ChargingSession`** — unified session model with `from_teslamate()` and `from_fleet_point()` factory methods
- **`ChargingHistoryPoint`** / **`ChargingHistory`** — structured Fleet API charge_history parser

### Tests

- 1133 tests passing (+19 new)

## [4.0.1] - 2026-04-02

### Documentation

- **Restructured documentation** into `docs/` directory with single-responsibility files:
  - `docs/user-guide.md` — complete CLI command reference (13 groups)
  - `docs/architecture.md` — system design, provider layers, ADRs, testing patterns
  - `docs/configuration.md` — config keys, auth, tokens, environment variables
  - `docs/api-reference.md` — REST endpoints, SSE, Prometheus, web dashboard
  - `docs/data-sources.md` — Tesla API catalog, 15 registered sources
  - `docs/roadmap.md` — forward-looking only (shipped features in CHANGELOG)
  - `docs/research/competitive-analysis.md` — 20-tool ecosystem deep dive
- **README.md** reduced from 857 to 99 lines (intro + quick start + links to docs)
- **CLAUDE.md** added for Claude Code project context in every session
- **Eliminated**: IMPLEMENTATION-PLAN.md (obsolete), redundant ROADMAP.md
- **Custom slash commands**: `.claude/commands/test.md`, `review.md`, `release.md`

### Improvements

- **`tesla charge history`** — improved with structured `ChargingHistory` Pydantic model:
  - Rich table output with Date/kWh/Location columns
  - Breakdown summary (Home vs Supercharging)
  - JSON mode support (`-j`)
  - Graceful fallback to TeslaMate when Fleet API unavailable
- **`GET /api/charge/history`** — new REST endpoint returning parsed charging history
- **Fleet backend** — fixed `charge_history` to use POST (per Tesla API spec)

### Fixes

- Mark `TestBrowserLogin` and `TestBrowserLoginAPI` as `@pytest.mark.integration`
- Fix vampire drain test mock to match current SQL schema (`km_per_hour`)
- Fix TeslaMate status test assertion for managed stack mode
- Remove stale `has_token` patches from teslamate_stack tests
- Fix 76 lint issues (ruff auto-fix: unsorted imports, unused imports)
- Simplify `is_running()` to use `any()` (SIM110)

### Tests

- 1121 tests passing (7 new for charge history)

## [4.0.0] - 2026-04-01

### Architecture — Clean Architecture + Monorepo + TeslaMate Managed Stack

- **Clean architecture restructuring** — reorganized `tesla_cli` package into 4 layers:
  - `core/` — business logic (config, exceptions, auth, backends, models, providers) with zero framework deps
  - `cli/` — CLI layer (Typer app, commands, output, i18n)
  - `api/` — API layer (FastAPI factory, auth middleware, routes, UI build serving)
  - `infra/` — infrastructure orchestration (TeslaMate Docker Compose stack)
- **Monorepo** — React frontend (`tesla-app`) moved into `ui/` directory inside the main project
  - Vite proxy: `/api` requests proxied to backend in development
  - Production: `tesla serve --build-ui` builds React app and serves from FastAPI on single port
  - `Makefile` with unified commands: `make dev`, `make build`, `make test`, `make serve`
- **TeslaMate managed stack** — full Docker Compose lifecycle management:
  - 7 new CLI commands: `install`, `start`, `stop`, `restart`, `update`, `logs`, `uninstall`
  - Auto-provisioning on server startup (installs if Docker available and TeslaMate not configured)
  - Credentials stored in system keyring, Tesla tokens forwarded to TeslaMate container
  - Settings page in React app with container status, action buttons, log viewer
  - 6 new API endpoints: `stack/status`, `stack/start`, `stack/stop`, `stack/restart`, `stack/update`, `stack/logs`
- **Removed** vanilla JS dashboard (`index.html`) — React app is the single UI

### Tests

- 1113 unit tests passing, 34 new TeslaMate stack tests

## [3.5.0] - 2026-03-31

### Added — Energy Report, Charging-Locations API, Odometer API

- **`tesla teslaMate energy-report`** — monthly energy usage summary aggregated from TeslaMate daily data; columns: Month, kWh, km, Wh/km; totals row; `--months N` (default 6, max 24); JSON returns list of `{month, kwh, km, wh_per_km}`; empty-data graceful fallback
- **`GET /api/teslaMate/charging-locations`** — top charging locations REST endpoint; `?days=N` (default 90) and `?limit=N` (default 10); returns list of `{location, sessions, kwh_total, last_visit}`; 503 when TeslaMate not configured; 502 on backend error
- **`GET /api/vehicle/odometer`** — current odometer reading REST endpoint; returns `{vin, odometer_miles, car_version, queried_at}`; 503 when vehicle is asleep; 502 on other errors

### Tests

- 1132 unit tests passing, 2 skipped, ruff clean
- `TestTeslaMateEnergyReport` (8 tests), `TestTeslaMatChargingLocationsApi` (3 tests), `TestVehicleOdometerApi` (4 tests) in `tests/test_new_commands.py`

## [3.4.0] - 2026-03-31

### Added — Charging Locations, Vehicle Health Check, Charging Animation, Trip-Stats API

- **`tesla teslaMate charging-locations`** — top charging locations ranked by session count; `--days N` (default 90) and `--limit N` (default 10); shows location, sessions, total kWh, avg kWh/session, last visit; JSON mode returns list of dicts; summary footer with totals
- **`tesla vehicle health-check`** — comprehensive vehicle health summary: battery level (ok/warn/error thresholds), charge limit (70–90% range check), firmware version + pending update detection, TPMS tyre pressure (warn < 2.4 bar), door lock status, sentry mode, odometer; JSON mode returns `{vin, checks: [{name, status, value, detail}]}`
- **Dashboard charging animation** — `#ring-fg.charging` CSS pulse animation (1.8s ease-in-out); `#charge-rate-row` shown only while charging (kW from `charger_power`); `#charge-eta-row` shows estimated full-charge ETA from `time_to_full_charge`; `classList.add/remove('charging')` toggled in `render()`
- **`GET /api/teslaMate/trip-stats`** — aggregate trip statistics REST endpoint; `?days=N` (default 30); returns `{summary, top_routes, days}`; 502 on backend error, 503 when TeslaMate not configured

### Tests

- ~1090+ unit tests passing, ruff clean
- `tests/test_v340.py` — ~45 tests across 5 test classes (ChargingLocations, VehicleHealthCheck, DashboardChargingAnim, ApiTripStats, Version340)

## [3.3.0] - 2026-03-31

### Added — Charge Forecast, Trip Stats, Health Badge, Cost-Report API

- **`tesla charge forecast`** — estimates time to reach charge limit based on current charge rate; shows status, battery level, charger power, time-to-limit (e.g. "1h 30m"), ETA (HH:MM), energy to add (kWh), and range; JSON mode returns all fields; hints when not charging
- **`tesla teslaMate trip-stats`** — aggregate trip statistics over `--days N` (default 30): total trips, total/avg/longest/shortest distance, avg duration; top-5 routes table; JSON mode returns `{summary, top_routes, days}`
- **Dashboard config health badge** — `#health-badge` pill in footer calls `GET /api/config/validate` on load; shows ✓ healthy (green), ⚠ N warning (yellow), or ✗ N error (red); CSS classes `ok`/`warn`/`err`; `loadHealthBadge()` JS function
- **`GET /api/teslaMate/cost-report`** — monthly charging cost report; groups charging sessions by YYYY-MM; optional `?month=YYYY-MM` filter and `?limit=N`; returns `{cost_per_kwh, months: {YYYY-MM: {sessions, kwh, cost}}, sessions}`

### Tests

- ~1060+ unit tests passing, ruff clean
- `tests/test_v330.py` — ~45 tests across 5 test classes (ChargeForecast, TeslaMateTripsStats, DashboardHealthBadge, ApiCostReport, Version330)

## [3.2.0] - 2026-03-31

### Added — Watch Notify Per-Vehicle, Schedule-Amps, Heatmap --year, Config Validate API

- **`tesla vehicle watch --all --notify`** — per-vehicle notification titles: when `--all` is active, each thread sends `"Tesla Watch — {label}"` so the user can identify which vehicle triggered the alert
- **`tesla charge schedule-amps HH:MM AMPS`** — combined command to set charge amperage and enable scheduled charging in one step; validates time format and amps range (1–48); JSON mode returns `{ok, schedule, amps, vin}`
- **`tesla teslaMate heatmap --year N`** — year selector for the GitHub-style driving heatmap; calls `get_drive_days_year(year)` backend method; start=Jan 1, end=min(today, Dec 31); `--days` path unchanged
- **`GET /api/config/validate`** — REST endpoint exposing config validation; returns `{valid, errors, warnings, checks[]}` for dashboard health widgets; backed by `_run_config_checks()` helper extracted from `config validate`
- **`_run_config_checks(cfg)`** — module-level helper in `config_cmd.py`; shared by CLI and REST endpoint; returns list of `{field, status, message}` dicts; status values: `ok`, `warn`, `error`

### Tests

- ~1030+ unit tests passing, ruff clean
- `tests/test_v320.py` — ~45 tests across 5 test classes (WatchAllNotify, ChargeScheduleAmps, HeatmapYear, ApiConfigValidate, Version320)

## [3.1.0] - 2026-03-31

### Added — Multi-Vehicle Watch, Charge Profile, SSE Back-off, Config Validate

- **`tesla vehicle watch --all`** — simultaneous multi-vehicle monitoring in separate threads; collects all configured VINs (default + aliases), deduplicates, spawns one thread per VIN with prefix labels; `threading.Event` stop_event for clean Ctrl+C shutdown
- **`tesla charge profile`** — unified charge profile command: no args shows current limit/amps/schedule; `--limit`, `--amps`, `--schedule HH:MM` (or `""` to disable) set profile fields in one command; JSON mode returns `{ok, results}` dict
- **Dashboard SSE exponential back-off** — `startStream()` now retries on error with `2^n` second delay (capped at 64s); closes existing connection before reconnect; resets retry counter on successful `vehicle` event; integrates `_activeVin` in stream URL
- **`tesla config validate`** — validates config structure, required fields, URL formats, port ranges, MQTT QoS; exits 0 if valid (warns OK), exits 1 on any failures; JSON mode returns `{version, checks, summary, valid}`

### Tests

- ~1015+ unit tests passing, ruff clean
- `tests/test_v310.py` — ~50 tests across 5 test classes (VehicleWatchAll, ChargeProfile, DashboardBackoff, ConfigValidate, Version310)

## [3.0.0] - 2026-03-31

### Added — Multi-Vehicle Dashboard, Schedule-Update, Timeline API, Notify Templates, Config Migrate

- **Multi-vehicle dashboard** — VIN switcher `<select>` in header; `GET /api/vehicles` endpoint lists default + aliased VINs; `switchVin()` / `loadVehicleList()` JS; all `/api/vehicle/` fetch calls inject `?vin=` when active; `_backend_and_vin()` reads `?vin=` query param
- **`tesla vehicle schedule-update`** — schedule a pending OTA update immediately or with `--delay N` minutes; JSON mode; calls `b.schedule_software_update(v, offset_sec=...)`
- **`GET /api/teslaMate/timeline`** — unified event timeline (trips + charges + OTA) with `?days=N`; proxies `TeslaMateBacked.get_timeline()`; 502 on backend errors, 503 when not configured
- **Notification templates** — `message_template` field in `NotificationsConfig` (default `"{event}: {vehicle} — {detail}"`); `tesla notify set-template` / `tesla notify show-template` commands; `notify test` uses template for body
- **`tesla config migrate`** — fills in new config defaults, shows additions diff, makes `.bak.YYYY-MM-DD` backup before saving; `--dry-run` mode; JSON mode

### Tests

- ~965+ unit tests passing, ruff clean
- `tests/test_v300.py` — ~50 tests across 6 test classes

## [2.9.0] - 2026-03-31

### Added — Timeline, Cost Report, Prometheus Metrics, Theme Toggle

- **`tesla teslaMate timeline`** — unified chronological event feed merging trips, charges, and OTA updates; `--days N`; JSON mode; duration column; type icons (🚗 ⚡ 🔄)
- **`tesla teslaMate cost-report`** — charging cost report grouped by month; uses `cost_per_kwh` from config; `--month YYYY-MM` filter; `--limit N` sessions; JSON mode with per-month kWh + cost summary
- **`GET /api/metrics`** — Prometheus text-format metrics endpoint (`text/plain; version=0.0.4`); exposes battery level, range, charge limit, charger power, energy added, odometer, speed, latitude, longitude, locked, sentry mode; NaN for missing values; graceful fallback on vehicle errors
- **`get_timeline(days)`** added to `TeslaMateBacked` — UNION ALL SQL across drives, charging_processes, and updates tables ordered by start_date DESC
- **Dashboard theme toggle** — 🌙/☀️ button in header; `body.light` CSS class with light-mode variable overrides; `localStorage` persistence across page loads; `toggleTheme()` + `initTheme()` JS functions

### Tests

- ~900 unit tests passing, 2 skipped, ruff clean
- `tests/test_v290.py` — 45 tests: TeslaMate timeline CLI (15), cost-report CLI (14), Prometheus metrics API (17), dashboard theme HTML (13), version assertions (2)

## [2.8.0] - 2026-03-30

### Added — MQTT CLI, HA Discovery, SSE Topic Filtering, Geofence Overlay

- **`tesla mqtt` command group** — full MQTT broker management CLI:
  - `tesla mqtt setup <broker>` — configure broker (host, port, username, password, prefix, TLS)
  - `tesla mqtt status` — show configuration + live connectivity check; JSON mode
  - `tesla mqtt test` — publish test message and report round-trip latency; JSON mode
  - `tesla mqtt publish [--ha-discovery]` — one-shot vehicle state push via MqttProvider; optional HA discovery publish
  - `tesla mqtt ha-discovery` — publish 15 Home Assistant MQTT discovery configs (retained) for auto-registration of sensors in HA
- **15 HA sensor discovery configs**: battery_level, battery_range, charging_state, charge_limit, energy_added, charger_power, speed, latitude, longitude, inside_temp, outside_temp, climate_on, locked, odometer, sw_version
- **SSE fine-grained topic filtering** — `/api/vehicle/stream?topics=battery,climate,drive,location,geofence`:
  - `event: battery` — yields `charge_state` snapshot
  - `event: climate` — yields `climate_state` snapshot
  - `event: drive` — yields `drive_state` snapshot
  - `event: location` — yields `{lat, lon, heading, speed}` subset
  - `event: geofence` — enter/exit zone crossing (pre-existing, now documented alongside new topics)
- **Dashboard geofence overlay** — Location card shows zone chips (`📍 Home`, `🏢 Work`) that highlight green when vehicle is inside; updates live on SSE `geofence` events; zones loaded from `/api/geofences` on page load

### Tests

- 853 unit tests passing, 2 skipped, ruff clean
- `tests/test_v280.py` — 45 tests: MQTT setup/status/test/publish/ha-discovery CLI (25), SSE topic filtering source analysis (14), dashboard geofence overlay HTML (8), version assertions (2)

## [2.7.0] - 2026-03-31

### Added — MQTT Provider + Service Files + Dashboard TeslaMate Charts

- **MQTT Provider** (`tesla_cli/providers/impl/mqtt.py`) — L3 telemetry sink:
  - Publishes vehicle state to any MQTT broker (paho-mqtt optional dep: `pip install 'tesla-cli[mqtt]'`)
  - Topics: `<prefix>/<vin>/<key>` per state block + `<prefix>/<vin>/state` full blob
  - Config: `mqtt.broker`, `port`, `topic_prefix`, `username`, `password`, `qos`, `retain`, `tls`
  - Integrated into `ProviderRegistry` fan-out (7th provider, TELEMETRY_PUSH capability)
- **`MqttConfig`** added to `Config` model
- **`tesla serve install-service`** — generate and install OS service file for autostart:
  - `--platform systemd` → `~/.config/systemd/user/tesla-cli.service` (Linux)
  - `--platform launchd` → `~/Library/LaunchAgents/com.tesla-cli.server.plist` (macOS)
  - `--print` → preview service file without installing
  - Auto-detects platform from `platform.system()` when `--platform` omitted
- **Web dashboard TeslaMate section** (shows only when TeslaMate is configured):
  - Lifetime stats bar: total km, energy, charge count, avg efficiency
  - Daily energy bar chart (last 30 days, pure CSS bars, no external libs)
  - Recent trips table (date, km, duration, Wh/km)
  - Recent charging sessions table (date, kWh, SoC %, duration)
  - Gracefully hidden if TeslaMate returns 503 (not configured)
- **SSE geofence toast notifications** — browser shows `📍 Entered <zone>` / `🚗 Left <zone>` toasts in real time
- **Named SSE events** — stream now uses `event: vehicle` and `event: geofence` typed events; dashboard uses `addEventListener` for each type

### Optional Dependencies

- `paho-mqtt>=1.6` → `pip install 'tesla-cli[mqtt]'`

### Tests

- 808 unit tests passing, 2 skipped, ruff clean
- `tests/test_v270.py` — 34 tests: MqttConfig (3), MqttProvider (13), install-service CLI (6), dashboard HTML (9)
- Updated `tests/test_providers.py` — 7 providers now registered (added mqtt assertion)

---

## [2.6.0] - 2026-03-30

### Added — TeslaMate API + Auth + Daemon

- **`GET /api/teslaMate/trips`** — recent driving trips from TeslaMate (`?limit=N`)
- **`GET /api/teslaMate/charges`** — recent charging sessions (`?limit=N`)
- **`GET /api/teslaMate/stats`** — lifetime driving + charging statistics
- **`GET /api/teslaMate/efficiency`** — per-trip energy efficiency in Wh/km (`?limit=N`)
- **`GET /api/teslaMate/heatmap`** — driving-day data for calendar heatmap (`?days=N`)
- **`GET /api/teslaMate/vampire`** — vampire drain analysis (`?days=N`)
- **`GET /api/teslaMate/daily-energy`** — daily kWh added (`?days=N`)
- **`GET /api/teslaMate/report/{month}`** — monthly driving + charging summary (YYYY-MM)
- **`GET /api/geofences`** — list all configured geofence zones (name, lat, lon, radius_km)
- **API Key Auth middleware** (`tesla_cli/server/auth.py`):
  - `X-API-Key` header or `?api_key=` query param
  - `TESLA_API_KEY` env var overrides config
  - Protects all `/api/*` paths; `/` (dashboard) always open
  - Enabled via `server.api_key` in config or `tesla serve --api-key TOKEN`
- **`tesla serve --daemon`** — detach server to background; writes PID to `~/.tesla-cli/server.pid`
- **`tesla serve stop`** — gracefully stop running daemon (SIGTERM + PID cleanup)
- **`tesla serve status`** — show running/stopped state with PID; `--json` for scripting
- **`tesla serve --api-key TOKEN`** — set API key and persist to config in one step
- **SSE geofence events** — `/api/vehicle/stream?topics=geofence` emits typed `geofence` events (`enter`/`exit`) with zone name, coordinates and distance; uses haversine formula
- **`ServerConfig`** added to `Config` model (`api_key`, `pid_file`)
- **`auth_enabled` field** in `GET /api/config` response

### Tests

- 774 unit tests passing, 2 skipped, ruff clean
- `tests/test_v260.py` — 42 tests: TeslaMate routes (10), Auth middleware (7), Geofences endpoint (3), Haversine (3), Middleware unit (3), ServerConfig (4), Daemon helpers (5), Serve CLI (7)

---

## [2.5.0] - 2026-03-30

### Added — Provider Architecture

- **Provider ABC** (`tesla_cli/providers/base.py`) — `Provider`, `ProviderResult`, `Capability` (11 capability constants), `ProviderPriority` (CRITICAL/HIGH/MEDIUM/LOW/MINIMAL) standardise how every data source and sink is represented
- **ProviderRegistry** (`tesla_cli/providers/registry.py`) — single orchestration hub:
  - `get(capability)` → highest-priority available provider; raises `CapabilityNotAvailableError` if none
  - `fetch_with_fallback()` / `execute_with_fallback()` — try providers in priority order, return first success
  - `fanout(capability, operation)` — execute against ALL available providers simultaneously (telemetry sinks, notifications)
  - `status()` / `health_report()` / `capability_map()` — full ecosystem observability
- **6 provider implementations** across 4 priority layers:
  - **L0 `BleProvider`** (CRITICAL=100) — `VEHICLE_COMMAND`; wraps `tesla-control` binary; available when binary + key present
  - **L1 `VehicleApiProvider`** (HIGH=80) — `VEHICLE_STATE`, `VEHICLE_COMMAND`, `VEHICLE_LOCATION`; wraps Owner/Tessie/Fleet backends
  - **L2 `TeslaMateProvider`** (MEDIUM=60) — `HISTORY_TRIPS`, `HISTORY_CHARGES`, `HISTORY_STATS`; wraps TeslaMate PostgreSQL
  - **L3 `AbrpProvider`** (LOW=40) — `TELEMETRY_PUSH`; translates vehicle state to ABRP `/1/tlm/send` format
  - **L3 `HomeAssistantProvider`** (LOW=40) — `HOME_SYNC`; pushes 18 `sensor.tesla_*` entities to HA REST API
  - **L3 `AppriseProvider`** (LOW=40) — `NOTIFY`; multi-channel notification via Apprise
- **`tesla providers status`** — rich table of all registered providers (layer, availability, capabilities) + capability routing summary showing which provider wins each capability
- **`tesla providers test`** — runs `health_check()` on every provider with Rich progress spinner; shows latency + detail
- **`tesla providers capabilities`** — full capability map: which providers serve which operations
- **`GET /api/providers`** + **`GET /api/providers/capabilities`** — provider registry exposed via REST API
- **SSE fan-out** — `/api/vehicle/stream?fanout=true` pushes each polling tick to all configured telemetry + home-sync sinks (ABRP + HA simultaneously)
- **Singleton registry** via `get_registry()` in `tesla_cli/providers/__init__.py` — lazy-loaded, force-reloadable

### Tests

- 732 unit tests passing, 2 skipped (fpdf2 optional), ruff clean
- `tests/test_providers.py` — 61 tests covering: Capability, ProviderResult, ProviderRegistry (routing, fallback, fanout, unregister), all 6 provider implementations, loader, and CLI commands

---

## [2.4.0] - 2026-03-30

### Added — API Server + Web Dashboard (`tesla serve`)

- **`tesla serve`** — one-command local API server + web dashboard; FastAPI + uvicorn optional dependency (`pip install 'tesla-cli[serve]'`); auto-opens browser; `--port`, `--host`, `--no-open`, `--vin`, `--reload` flags
- **REST API** — all vehicle backends exposed as HTTP endpoints:
  - `GET /api/status` — version, backend, VIN
  - `GET /api/config` — public config (no tokens)
  - `GET /api/vehicle/state` — full vehicle data
  - `GET /api/vehicle/location` — drive state + GPS
  - `GET /api/vehicle/charge` — charge state
  - `GET /api/vehicle/climate` — climate state
  - `GET /api/vehicle/vehicle-state` — locks, doors, software
  - `GET /api/vehicle/list` — account vehicles
  - `POST /api/vehicle/command` — send any command with params
  - `POST /api/vehicle/wake` — wake vehicle
  - `GET /api/charge/status` + `POST /api/charge/limit|amps|start|stop`
  - `GET /api/climate/status` + `POST /api/climate/on|off|temp`
  - `GET /api/order/status` — order delivery status
  - `GET /api/vehicle/stream` — **Server-Sent Events** real-time stream (configurable interval)
  - `GET /api/docs` — interactive Swagger UI (auto-generated from FastAPI)
- **Web dashboard** (`/`) — single-page dark-themed HTML/CSS/JS, zero build step:
  - Battery ring gauge with SoC%, range, limit, charging state, power
  - Climate card with cabin/outside temp, on/off buttons
  - Security card with lock icon, door states, sentry, user present
  - Drive card with speed, power, heading, odometer, SW version
  - Location card with coordinates, Google Maps link, ASCII mini-map
  - Quick actions card: wake, sentry on/off, HomeLink, remote start
  - Live updates via SSE stream (30s interval)
  - All action buttons call the REST API
- **PWA** — `manifest.json` (name, theme color, display standalone) + `sw.js` service worker for offline shell; installable from browser

### Optional Dependencies

- `fastapi>=0.110` + `uvicorn[standard]>=0.29` → `pip install 'tesla-cli[serve]'`

### Tests

- 671 unit tests passing, 2 skipped (fpdf2 optional), ruff clean
- `tests/test_server.py` — 31 FastAPI endpoint tests (system, vehicle, charge, climate)

---

## [2.3.0] - 2026-03-30

### Added — Vehicle Map, Geofencing, Home Assistant

- **`tesla vehicle map`** — ASCII terminal map centered on current GPS position; `--span` controls degree window (default 0.05 ≈ 5 km); overlays named geofence zones as `░` fill; heading arrow (↑↗→↘↓↙←↖▲), shift state, speed; JSON mode returns `{lat, lon, heading, speed, shift_state}`
- **`tesla geofence add <name> --lat <lat> --lon <lon>`** — add a named geographic zone; `--radius` in km (default 0.5); stored in config
- **`tesla geofence list`** — table of all zones; JSON mode
- **`tesla geofence remove <name>`** — delete a zone
- **`tesla geofence watch`** — continuous polling (default 30s); prints `ENTER`/`EXIT` events when vehicle crosses zone boundaries; `--notify URL` Apprise alerts; first poll establishes baseline silently; JSON mode emits `{ts, lat, lon, inside, events}` each cycle
- **`tesla ha setup <URL> <TOKEN>`** — configure Home Assistant URL and long-lived access token
- **`tesla ha status`** — show HA config + live connectivity check; JSON mode
- **`tesla ha push`** — one-shot push of 18 vehicle sensor entities to HA REST API (`sensor.tesla_*`); reports per-entity errors gracefully; JSON mode
- **`tesla ha sync`** — continuous HA push loop; `--interval` seconds (default 60); `--notify URL` error alerts; JSON mode

### Config

- `GeofencesConfig(zones: dict)` — named zone store for geofencing; serialized to `[geofences]` in config.toml

### Tests

- 640 unit tests passing, 2 skipped (fpdf2 optional), ruff clean

---

## [2.2.0] - 2026-03-30

### Added — Ecosystem Hub: ABRP + BLE + Grafana

- **`tesla abrp send`** — one-shot push of current vehicle state (SoC, speed, power, GPS, charging status, cabin temp) to A Better Route Planner live telemetry API; JSON mode returns `{telemetry, abrp_response}`
- **`tesla abrp stream`** — continuous ABRP telemetry loop; `--interval N` seconds (default 30); prints timestamped push log each cycle; `--notify URL` Apprise alert on push errors; Ctrl+C exits gracefully
- **`tesla abrp status`** — show configured user token and API key presence; JSON mode; setup hint when unconfigured
- **`tesla abrp setup <TOKEN>`** — save ABRP user token (and optional `--api-key`) to config
- **`tesla ble lock|unlock|climate-on|climate-off|charge-start|charge-stop|flash|honk`** — L0 BLE direct control via `tesla-control` binary (no internet required); graceful `ExternalToolNotFoundError` with install hint when binary absent; JSON mode returns `{status, command, vin, returncode, stdout, stderr}`
- **`tesla ble status`** — check `tesla-control` binary presence, BLE key path, and MAC; JSON mode
- **`tesla ble setup-key <PATH>`** — configure BLE private key path (and optional `--mac`); validates file existence
- **`tesla teslaMate grafana [DASHBOARD]`** — open a TeslaMate Grafana dashboard in the system browser; supports `overview|trips|charges|battery|efficiency|locations|vampire|updates`; `--grafana.url` configurable (default `http://localhost:3000`); JSON mode returns `{dashboard, url}`

### Config

- `AbrpConfig(api_key, user_token)` — ABRP integration credentials
- `BleConfig(key_path, ble_mac)` — BLE key path and optional MAC override
- `HomeAssistantConfig(url, token)` — Home Assistant long-lived token (future use)
- `GrafanaConfig(url)` — Grafana base URL (default `http://localhost:3000`)

### Exceptions

- `ExternalToolNotFoundError(tool_name, install_hint)` — raised by L0/L3 wrappers when a required binary is absent from PATH

### Tests

- 616 unit tests passing, 2 skipped (fpdf2 optional), ruff clean

---

## [2.1.0] - 2026-03-30

### Enhanced — All Competitive Gaps Closed

- **`tesla charge limit [PERCENT]`** — no-arg mode shows current `charge_limit_soc` from `charge_state`; set mode validates 50–100 and calls `set_charge_limit`; JSON output in both read and write paths
- **`tesla charge amps [AMPS]`** — no-arg mode shows current `charge_amps`; set mode validates 1–48 and calls `set_charging_amps`; JSON output in both paths
- **`tesla climate temp [CELSIUS]`** — no-arg mode shows current driver + passenger temps; `--passenger TEMP` option sets independent passenger temp; validation 15.0–30.0 °C; JSON output
- **`tesla climate seat [POSITION [LEVEL]]`** — new named-position command (`driver | passenger | rear-left | rear-center | rear-right`); no-arg shows all 5 seat heater levels with color indicators; per-position level set with validation 0–3; JSON output; original integer `seat-heater` command retained for backward compatibility
- **`tesla climate steering-wheel [--on|--off]`** — new command replacing clunky bool-arg `steering-heater`; no-arg shows current state; `--on/--off` flags; JSON output; original `steering-heater` command retained
- **`tesla media volume`** — added range validation (0.0–11.0); JSON output already present via `render_success`
- **`tesla media play/next/prev`** — JSON output confirmed working via `render_success`; no structural change needed
- **`tesla nav send`** — JSON output confirmed working via `render_success`; no structural change needed

### Models

- `ChargeState`: added `charge_amps: int = 0`
- `ClimateState`: added `seat_heater_rear_left`, `seat_heater_rear_center`, `seat_heater_rear_right`, `steering_wheel_heater`

### Tests

- 590 unit tests passing, 2 skipped (fpdf2 optional), ruff clean

---

## [2.0.0] - 2026-03-30

### Added

- **`tesla teslaMate heatmap`** — GitHub-style calendar heatmap of driving activity; 7-row × N-week grid (Mon–Sun); color-coded cells: `·` no drive (dim), `▪` <50 km (blue), `▪` 50–150 km (yellow), `█` 150+ km (green); month labels across top; activity summary footer (active days, total km); `--days N` window (default 365); new SQL `get_drive_days(days)` in TeslaMate backend groups drives by calendar day; JSON mode returns `[{date, drives, km}]`
- **`tesla vehicle watch`** — continuous vehicle monitoring loop; polls every `--interval N` seconds (default 60); detects and prints alerts on state changes to battery level, charging state, charge limit, lock state, user presence, individual door open/close, climate on/off, cabin temp, shift state, and speed; first poll establishes baseline silently; Ctrl+C exits gracefully; `--notify URL` sends Apprise push notification on any change; JSON mode emits `{ts, changes}` payload each cycle

### Tests

- 536 unit tests passing, 2 skipped (fpdf2 optional), ruff clean

---

## [1.9.0] - 2026-03-30

### Added

- **`tesla teslaMate daily-chart`** — ASCII bar chart of kWh added per day over the last N days from TeslaMate; new SQL query `get_daily_energy(days)` groups charging sessions by calendar day; `--days N` (default 30); color-coded bars; multi-session days annotated; totals footer; JSON mode
- **`tesla order eta`** — delivery ETA estimation based on current order phase; best-case / typical / worst-case windows for each remaining phase using community-sourced duration data; auto-reads current phase from latest dossier snapshot (with live API fallback); phase breakdown table; JSON mode with full duration breakdown
- **`tesla config doctor`** — configuration health check; diagnoses order auth token, default VIN, reservation number, vehicle backend token (fleet/tessie/owner), TeslaMate DB connectivity, and config file presence; each check reports ✅ ok / ⚠️ warn / ❌ fail with fix hint; exits code 1 if any check fails; full JSON mode

### Tests

- 523 unit tests passing, 2 skipped (fpdf2 optional), ruff clean

---

## [1.8.0] - 2026-03-30

### Added

- **`tesla vehicle bio`** — comprehensive single-screen vehicle profile: one `get_vehicle_data` call renders 5 Rich panels (Identity, Battery, Climate, Drive State, Scheduling); color-coded battery level (green/yellow/red); gracefully handles missing fields with `—` placeholders; full JSON mode with structured `identity/battery/climate/drive/scheduling` keys
- **`tesla teslaMate graph`** — ASCII bar chart of recent charging sessions from TeslaMate; bars scaled to terminal width via `shutil.get_terminal_size`; color-coded by kWh (green ≥30, yellow ≥10, red <10); fixed-width label column for alignment; summary footer with session count, total kWh, and total cost; `--limit N`; JSON mode returns raw session list
- **`tesla dossier export-html --theme light|dark`** — theme flag for HTML dossier export; `dark` preserves existing dark CSS (default); `light` switches to white background with deep-red Tesla accent `#c0001a` (WCAG AA compliant); CSS injected via Python string variables into the existing f-string, no template engine required
- **`tesla vehicle cabin-protection`** — view and control Cabin Overheat Protection; no flags = show current level from `climate_state`; `--on/--off` toggles; `--level FAN_ONLY|NO_AC|CHARGE_ON` sets specific mode (case-insensitive); JSON mode; invalid level exits with helpful message

### Tests

- 501 unit tests passing, 2 skipped (fpdf2 optional), ruff clean

---

## [1.7.0] - 2026-03-30

### Added

- **`tesla vehicle sw-update`** — check for pending OTA software update; one-shot or `--watch` mode that polls every N minutes until an update is detected; `--notify` fires Apprise notification on detection; full JSON mode with all update fields (`status`, `version`, `download_perc`, `install_perc`, `expected_duration_sec`)
- **`tesla vehicle speed-limit`** — view and control Speed Limit Mode; show current status + limit (default); `--limit MPH` to set (50–90); `--on --pin XXXX` to activate; `--off --pin XXXX` to deactivate; `--clear --pin XXXX` to clear PIN; full JSON mode
- **`tesla teslaMate stats`** — lifetime driving and charging statistics from TeslaMate DB; total drives, distance (km + mi), avg/longest trip, total kWh used, first/last drive; charging sessions, kWh added, cost, avg per session, last session; lifetime Wh/km efficiency banner; full JSON mode

### Tests

- 471 unit tests passing, 2 skipped (fpdf2 optional), ruff clean

---

## [1.6.0] - 2026-03-30

### Added

- **`tesla dossier export-html`** — export the full dossier to a standalone HTML report with zero extra dependencies; sections: Vehicle Identity (with color/wheel/drive), Battery & Charging (with live bar), Order Status, NHTSA Recalls, Snapshot History; dark-themed self-contained CSS; `--output` flag; default filename `dossier.html`
- **`tesla charge schedule-preview`** — consolidated view of all scheduled charging and departure settings in one command; shows scheduled charging mode + start time, departure time, preconditioning (with weekdays-only flag), off-peak charging window; full JSON mode
- **`tesla order stores`** — embedded offline database of 100+ Tesla store and service center locations across EU, US, CA, AU, CN, JP; filter by `--country` (ISO code), `--city`, or find nearest with `--near lat,lon`; `--limit N`; distance shown in km when using `--near`; full JSON mode

### Tests

- 443 unit tests passing, 2 skipped (fpdf2 optional), ruff clean

---

## [1.5.0] - 2026-03-30

### Added

- **`tesla dossier export-pdf`** — generate a full formatted PDF report from the latest dossier snapshot; sections: Vehicle Identity, Battery/Charging, Order Status, NHTSA Recalls, Snapshot History; dark header bar, grey section dividers, footer; install with `uv pip install fpdf2`
- **`tesla config backup`** — export full configuration to a JSON file; all token/secret/key/password fields automatically redacted; includes `_meta` version block
- **`tesla config restore FILE`** — restore configuration from a JSON backup; skips `[REDACTED]` entries; prompts for confirmation (bypass with `--force`)
- **`tesla teslaMate report`** — monthly driving + charging summary from TeslaMate DB; trips, total km, avg efficiency (Wh/km), sessions, total kWh, total cost, DC fast vs AC session breakdown; `--month YYYY-MM` (default: current month); full JSON mode
- **`tesla vehicle sentry-events`** — filter recent vehicle alerts to sentry-triggered events (detection, camera, tampering); `--limit N`; Fleet API only with graceful `BackendNotSupportedError` on other backends; full JSON mode

### Dependencies

- `fpdf2>=2.7` added as optional dependency (`uv pip install tesla-cli[pdf]`)

### Tests

- 413 unit tests passing, 2 skipped (fpdf2 optional dep), ruff clean

---

## [1.4.0] - 2026-03-30

### Added

- **`tesla charge departure`** — set scheduled departure time (HH:MM) with optional cabin preconditioning (`--precondition`) and off-peak charging window (`--off-peak --off-peak-end HH:MM`); `--disable` to cancel; full JSON mode
- **`tesla vehicle precondition`** — toggle max preconditioning on/off (blast heat/cool before a trip); full JSON mode
- **`tesla vehicle screenshot`** — trigger a screenshot of the vehicle's display; saves to TeslaConnect mobile app; full JSON mode
- **`tesla vehicle tonneau`** — Cybertruck tonneau cover control: `open|close|stop|status`; full JSON mode
- **`tesla teslaMate geo`** — most-visited locations from TeslaMate ranked by visit count with lat/lon and arrival battery range; `--limit N`; `--csv FILE`; full JSON mode
- **`tesla config encrypt-token`** — AES-256-GCM encrypt any keyring token for headless server deployments; PBKDF2-SHA256 key derivation (260,000 iterations); `enc1:` prefix marker; interactive `--password` prompt
- **`tesla config decrypt-token`** — reverse AES-256-GCM encryption back to plaintext in keyring
- **`src/tesla_cli/auth/encryption.py`** — new module: `is_encrypted()`, `encrypt_token()`, `decrypt_token()`; lazy `cryptography` import with helpful install hint

### Dependencies

- `cryptography>=46.0.5` added for AES-256-GCM token encryption

### Tests

- 388 unit tests passing (50 new tests for all v1.4.0 features); ruff clean

---

## [1.3.0] - 2026-03-30

### Added

- **`tesla vehicle tires`** — TPMS tire pressure in bar + PSI for all four wheels; color-coded status (OK / LOW / HARD WARN); `--vin`; full JSON mode
- **`tesla vehicle homelink`** — trigger HomeLink garage door opener using live GPS coordinates from drive state; full JSON mode
- **`tesla vehicle dashcam`** — save the current dashcam clip to USB storage; full JSON mode
- **`tesla vehicle rename`** — rename the vehicle (requires firmware 2023.12+); full JSON mode
- **`tesla security remote-start`** — enable keyless drive for 2 minutes; full JSON mode
- **`tesla dossier battery-health`** — estimate battery degradation from local snapshot history; computes estimated rated range per snapshot (battery_range ÷ battery_level%); shows peak, latest, average, and degradation %; no paid service required; full JSON mode
- **`tesla teslaMate vampire`** — analyze daily vampire drain (battery loss while parked) from TeslaMate PostgreSQL DB via CTE SQL query; shows avg %/hour with color coding; `--days N`; full JSON mode
- **`--csv FILE`** flag on `teslaMate trips`, `teslaMate charging`, `teslaMate efficiency` — export any dataset to CSV with header row
- **`order watch --on-change-exec CMD`** — run a shell hook whenever order changes are detected; change data passed as JSON via `TESLA_CHANGES` env var
- **`stream live --mqtt URL`** — publish vehicle state to any MQTT broker after each poll; format: `mqtt://host:1883/topic`; graceful `ImportError` hint if `paho-mqtt` not installed
- **Energy cost tracking** — `charge status` now displays estimated session cost when `cost_per_kwh` is configured (`tesla config set cost-per-kwh 0.15`)
- **German (de) i18n** — complete German translation catalog; `--lang de` / `TESLA_LANG=de`
- **Italian (it) i18n** — complete Italian translation catalog; `--lang it` / `TESLA_LANG=it`
- Now supports 6 languages: en, es, pt, fr, de, it

### Fixed

- `order._exec_on_change`: use `model_dump(mode="json")` to correctly serialize `datetime` fields in `OrderChange`
- `test_commands`: set `cfg.general.cost_per_kwh = 0.0` in mock config fixture to avoid `MagicMock > int` comparison error

### Tests

- 338 unit tests passing (66 new tests); ruff clean

---

## [1.2.1] - 2026-03-30

### Added

- **`BackendNotSupportedError`** — new exception for Fleet-only features; includes actionable "switch to fleet" hint and `tesla config set backend fleet` instruction
- **Graceful errors** for 6 Fleet-only commands on Owner API / Tessie backends: `charge history`, `vehicle alerts`, `vehicle release-notes`, `sharing invite/list/revoke`
- **TessieBackend** completed: added `get_vehicle_state`, `get_service_data`, `get_nearby_charging_sites`; all Fleet-only methods raise `BackendNotSupportedError`
- **`VehicleBackend` ABC** extended with default stubs for all Fleet-only methods (no breaking change for existing backends)

### Tests

- 272 unit tests passing (12 new backend-not-supported tests); ruff clean

---

## [1.2.0] - 2026-03-30

### Added

- **`tesla vehicle alerts`** — show recent vehicle fault alerts with name, audience, start/expiry time; full JSON mode
- **`tesla vehicle release-notes`** — display OTA firmware release notes as Rich panels; full JSON mode
- **`tesla vehicle valet`** — show Valet Mode status or toggle on/off (`--on`/`--off`); optional `--password` PIN
- **`tesla vehicle schedule-charge`** — show scheduled charging status, set time (`HH:MM`), or disable (`--off`); full JSON mode
- **`tesla dossier clean`** — prune old snapshots keeping the N most recent (`--keep N`, default 10); `--dry-run` preview; full JSON mode
- **French (fr) i18n** — complete French translation catalog; `--lang fr` / `TESLA_LANG=fr`

### Tests

- 260 unit tests passing (40 new tests); ruff clean

---

## [1.1.0] - 2026-03-30

### Added

- **`tesla vehicle nearby`** — show nearby Superchargers and destination chargers with real-time stall availability (green ≥ 4, yellow 1–3, red = 0); full JSON mode support
- **`tesla teslaMate efficiency`** — per-trip energy efficiency table (Wh/km + kWh/100 mi) with average summary; `--limit N`; full JSON mode
- **Portuguese (pt) i18n** — complete Brazilian Portuguese translation catalog; `--lang pt` / `TESLA_LANG=pt`

### Tests

- 220 unit tests passing (26 new tests for vehicle nearby, teslaMate efficiency, Portuguese i18n)

---

## [1.0.0] - 2026-03-30

### Added

- **`tesla dossier estimate`** — community-sourced delivery date estimation; shows optimistic / typical / conservative delivery window from current phase; falls back to confirmed date if set via `set-delivery`; full JSON mode support
- **`tesla vehicle windows`** — vent or close all windows (`tesla vehicle windows vent` / `close`)
- **`tesla vehicle charge-port`** — open, close, or stop the charging port (`tesla vehicle charge-port open|close|stop`)
- **`tesla vehicle software`** — show current software version, pending update status (available / downloading / scheduled / installing), download %, estimated install duration, scheduled time; `--install` flag triggers the update
- **`tesla notify list/add/remove/test`** — full Apprise notification management; `list` shows configured channels with masked tokens; `add <url>` appends and auto-enables; `remove <N>` removes by index; `test` fires a live test notification to all channels with per-channel success/failure reporting

### Tests

- 178 unit tests passing (14 new tests for software, notify list/add/remove/test)

---

## [0.4.0] - 2026-03-30

### Added

- **`tesla teslaMate connect/status/trips/charging/updates`** — read-only TeslaMate PostgreSQL integration; trip history, charging sessions, OTA update log, lifetime stats; optional `psycopg2-binary` dependency
- **`--lang` global flag / `TESLA_LANG` env var** — multi-language UI; Spanish (`es`) built-in with ~40 translated keys, falls back to English for any untranslated string
- **PyPI Trusted Publishing workflow** — `.github/workflows/publish.yml` publishes to PyPI on git tag push using OIDC (no API token required)
- **Homebrew formula** — `Formula/tesla-cli.rb` with `Language::Python::Virtualenv` pattern for all dependencies

### Fixed

- `tesla dossier checklist` — Rich markup error `[/]` when a checklist item is not done (empty style string generated invalid closing tag)
- `tesla stream live` — suppress "Starting live stream…" banner when `--json` flag is active (output was not valid JSON)

### Tests

- 149 unit tests passing, 0 failures
- Added `tests/test_new_commands.py` with 57 tests covering VIN decoder, option codes, anonymize mode, i18n, checklist, gates, diff, sentry, trips, stream, TeslaMate config, order change display, and Owner API auto-wake

---

## [0.3.0] - 2026-03-30

### Added

- **`tesla dossier diff`** — compare any two saved snapshots side-by-side with +/−/≠ colored symbols; supports index or filename selection
- **`tesla dossier checklist`** — 34-item Tesla delivery inspection checklist (exterior, interior, mechanicals, electronics); persistent `--mark N` to check items, `--reset` to start over
- **`tesla dossier gates`** — 13-gate delivery journey tracker from order placed to keys; current gate highlighted based on real dossier phase
- **`tesla vehicle sentry`** — show Sentry Mode status or toggle on/off (`--on`/`--off`)
- **`tesla vehicle trips`** — show current drive state, odometer, and last location; pointer to TeslaMate for full history
- **`tesla stream live`** — real-time vehicle telemetry dashboard using Rich Live; polls battery, climate, location, locks, software version every N seconds (`--interval`)
- **`--anon` global flag** — anonymize PII (VIN, reservation number, email, name) in any command output before sharing screenshots or bug reports (`tesla --anon order status`)
- **Color-coded change display** — `tesla order watch` now shows +/−/≠ symbols with green/red/yellow coloring per change type (added / removed / changed)
- **Auto-wake in Owner API backend** — `command()` now auto-wakes the vehicle and retries up to 3× (8s back-off) before giving up, so commands no longer fail silently when the car is asleep
- **Expanded option-code catalog** — OPTION_CODE_MAP grown from 55 → 140+ codes covering all models, motors, paints, interiors, wheels, seats, autopilot HW, charging, connectivity, and feature codes

### Changed

- `tesla stream live` replaces the "coming soon" stub with a working implementation
- Shell autocompletion available via `tesla --install-completion` (Typer built-in)

---

## [0.2.0] - 2026-03-30

### Added

- **`tesla setup` wizard** — single command onboarding: OAuth2 auth, auto-discovers VIN and
  reservation number from the Tesla API, optional vehicle backend setup, builds first dossier
- **Owner API vehicle backend** — free vehicle control with zero extra setup; reuses the
  existing order-tracking token (`owner-api.teslamotors.com`), same API used by TeslaPy and
  TeslaMate; no developer app registration or third-party service required
  (`tesla config set backend owner`)

### Changed

- Default vehicle backend changed from `tessie` to `owner`
- `tesla setup` Step 3 now presents `owner` as the recommended free option

---

## [0.1.0] - 2026-03-29

### Added

- **Order tracking** — `tesla order status/details/watch` via Tesla Owner API (OAuth2 + PKCE)
- **Vehicle control** — charge, climate, security, media, navigation via Fleet API and Tessie
- **Vehicle dossier** — `tesla dossier build/show/vin/ships/history` aggregating Tesla Owner API, NHTSA recalls, VIN decode, and ship tracking
- **RUNT integration** — Colombia vehicle registry queries via Playwright + OCR
- **SIMIT integration** — Colombia traffic fines queries via Playwright
- **Notifications** — Apprise integration supporting 100+ services (Telegram, Slack, Discord, email, ntfy, etc.)
- **JSON mode** — All commands support `-j/--json` for scripting and `jq` pipelines
- **Secure token storage** — System keyring (macOS Keychain / Linux Secret Service / Windows Credential Manager)
- **Multi-vehicle support** — VIN aliases and per-command `--vin` override
- **Change detection** — `tesla order watch` detects and notifies on any order field change
- **Historical snapshots** — Dossier builds accumulate timestamped snapshots
