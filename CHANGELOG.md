# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
