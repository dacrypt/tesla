# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
