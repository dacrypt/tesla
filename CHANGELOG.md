# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
