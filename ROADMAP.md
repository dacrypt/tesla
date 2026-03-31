# Roadmap — Ultimate Tesla Management Tool

This document benchmarks `tesla-cli` against competing community tools and tracks the features needed to become the most capable Tesla CLI available.

---

## Competing Tools — Feature Matrix

| Feature | **tesla-cli** | [TOST](https://github.com/chrisi51/TOST) | [enoch85](https://github.com/enoch85/tesla-order-status) | [WesSec](https://github.com/WesSec/TeslaOrder) | [niklaswa](https://github.com/niklaswa/tesla-order) | [GewoonJaap](https://gewoonjaap.nl/tesla) |
|---------|:---:|:---:|:---:|:---:|:---:|:---:|
| **Order tracking** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Change detection / watch loop** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Push notifications (Apprise / multi-channel)** | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| **Vehicle control (lock/unlock/charge/climate)** | ✅ | — | — | — | — | partial |
| **Vehicle info / location** | ✅ | — | — | — | — | ✅ |
| **VIN decode (position-by-position)** | ✅ | — | — | — | — | ✅ |
| **NHTSA recall lookup** | ✅ | — | — | — | — | — |
| **Ship tracking** | ✅ | — | — | — | ✅ | — |
| **Dossier (aggregated vehicle file + snapshots)** | ✅ | — | — | — | — | — |
| **JSON mode everywhere** | ✅ | — | — | — | — | — |
| **`tesla setup` onboarding wizard** | ✅ | — | — | — | — | — |
| **Free vehicle backend (Owner API)** | ✅ | — | — | — | — | — |
| **Secure token storage (system keyring)** | ✅ | — | partial | — | — | — |
| **Multi-vehicle support (aliases)** | ✅ | — | — | — | — | ✅ |
| **Multi-language UI** | ✅ (en/es/pt/fr/de/it) | ✅ (5 langs) | — | — | — | — |
| **Share / anonymize mode** | ✅ | ✅ | — | — | — | — |
| **Token encryption at rest (AES-256-GCM)** | — | — | ✅ | — | — | — |
| **Offline option-code catalog** | ✅ (140+) | — | ✅ | — | — | — |
| **Color-coded recursive diff (change display)** | ✅ | — | — | — | ✅ | — |
| **Delivery checklist** | ✅ (34 items) | — | — | — | — | ✅ (12 items) |
| **Delivery gates / milestones tracker** | ✅ (13 gates) | — | — | — | — | ✅ (13 gates) |
| **TeslaMate integration (trips/charging/OTA)** | ✅ | — | — | — | — | — |
| **Community delivery estimation** | — | — | — | — | — | ✅ |
| **Web UI** | — | — | — | — | — | ✅ |
| **Store location DB (200+ EU locations)** | ✅ | — | — | — | ✅ | — |
| **RUNT integration (Colombia registry)** | ✅ | — | — | — | — | — |
| **SIMIT integration (Colombia fines)** | ✅ | — | — | — | — | — |
| **Fleet API support** | ✅ | — | — | — | — | — |
| **Tessie proxy support** | ✅ | — | — | — | — | — |
| **Historical snapshot archive** | ✅ | — | — | — | — | — |
| **Real-time telemetry (WebSocket stream)** | partial | — | — | — | — | — |
| **Nearby Supercharger availability** | ✅ | — | — | — | — | partial |
| **Energy efficiency per trip** | ✅ | — | — | — | — | — |
| **Portuguese (pt) i18n** | ✅ (en/es/pt/fr/de/it) | ✅ (5 langs) | — | — | — | — |
| **TPMS tire pressure** | ✅ | — | — | — | — | — |
| **HomeLink trigger** | ✅ | — | — | — | — | — |
| **Dashcam clip save** | ✅ | — | — | — | — | — |
| **Vehicle rename** | ✅ | — | — | — | — | — |
| **Remote start** | ✅ | — | — | — | — | — |
| **Battery degradation estimate** | ✅ | — | — | — | — | — |
| **Vampire drain analysis** | ✅ | — | — | — | — | — |
| **CSV export** | ✅ | — | — | — | — | — |
| **Automation hook (on-change-exec)** | ✅ | — | — | — | — | — |
| **MQTT telemetry publish** | ✅ | — | — | — | — | — |
| **Energy cost tracking** | ✅ | — | — | — | — | — |

---

## Gap Analysis — Prioritized

### P1 — High Impact, Low Effort ✅ DONE

| Gap | Inspiration | Status |
|-----|-------------|--------|
| **Color-coded diff for order changes** | niklaswa | ✅ `order watch` shows +/−/≠ colored table |
| **Offline option-code catalog** | enoch85 | ✅ 140+ codes embedded, fully offline |
| **Change display symbols (+/−/≠)** | TOST | ✅ Green/red/yellow per change type |

### P2 — High Impact, Medium Effort ✅ DONE

| Gap | Inspiration | Status |
|-----|-------------|--------|
| **Delivery checklist** | GewoonJaap | ✅ `tesla dossier checklist` — 34 items, persistent `--mark N` |
| **`tesla dossier diff`** | niklaswa | ✅ Any two snapshots, colored +/−/≠ recursive diff |
| **Shell autocompletion (bash/zsh/fish)** | — | ✅ `tesla --install-completion` (Typer native) |
| **`tesla stream live`** | — | ✅ Rich Live dashboard: battery, climate, location, locks |

### P3 — Medium Impact, Medium Effort ✅ DONE

| Gap | Inspiration | Status |
|-----|-------------|--------|
| **Share / anonymize mode** | TOST | ✅ `tesla --anon <command>` masks VIN, RN, email in output |
| **Delivery gates tracker** | GewoonJaap | ✅ `tesla dossier gates` — 13 milestones, current highlighted |
| **Auto-wake in Owner API backend** | TeslaPy | ✅ `command()` auto-wakes + retries 3× with 8s back-off |

### P4 — Nice to Have

| Gap | Inspiration | Status |
|-----|-------------|--------|
| **`tesla vehicle sentry`** | — | ✅ Status + `--on`/`--off` toggle |
| **`tesla vehicle trips`** | — | ✅ Drive state + TeslaMate pointer |
| **Token encryption at rest** | enoch85 | 🔲 Keyring handles OS-level encryption; AES-256 for headless servers is future |
| **Multi-language UI** | TOST | ✅ `--lang es` / `TESLA_LANG=es` — Spanish built-in, fallback to English |
| **TeslaMate integration** | — | ✅ `tesla teslaMate connect/status/trips/charging/updates` |
| **Community delivery estimation** | GewoonJaap | ✅ `tesla dossier estimate` — optimistic/typical/conservative window from phase |

---

## What Makes tesla-cli Unique

No competing tool combines all of these in one CLI:

1. **Dossier** — aggregated vehicle file with 10+ data sources, historical snapshots, and `jq`-friendly JSON
2. **Free vehicle control** — Owner API backend, zero cost, zero registration
3. **Deepest integration** — NHTSA recalls, RUNT (Colombia), SIMIT (Colombia), VIN decode, ship tracking, TeslaMate
4. **`tesla setup` wizard** — single command from clone to full configuration
5. **JSON mode everywhere** — scriptable output on every command, composable with `jq`
6. **Three backends** — Owner API, Tessie, Fleet API — pick your tradeoff
7. **Privacy-first** — `--anon` flag masks all PII; tokens always in system keyring, never plain text

---

## Milestone Plan

### v0.3.0 — All Gaps Closed ✅ SHIPPED
- [x] Color-coded diff output in `order watch` (+/−/≠ symbols)
- [x] `tesla dossier diff <snapshot1> <snapshot2>`
- [x] Offline option-code catalog (140+ codes embedded)
- [x] `tesla dossier checklist` — 34-item delivery inspection
- [x] `tesla dossier gates` — 13-gate delivery journey tracker
- [x] `tesla stream live` — real-time vehicle telemetry dashboard
- [x] Auto-wake + retry in Owner API backend (3× retries, 8s back-off)
- [x] `tesla --anon` — anonymize PII in any command output
- [x] `tesla vehicle sentry` — status + toggle
- [x] `tesla vehicle trips` — drive state + TeslaMate pointer
- [x] Shell autocompletion via `tesla --install-completion`

### v0.4.0 — v1.0.0 Milestone Complete ✅ SHIPPED
- [x] TeslaMate integration — trip history, charging sessions, OTA log
- [x] Multi-language UI — `--lang es` / `TESLA_LANG=es` (Spanish built-in)
- [x] PyPI Trusted Publishing workflow (`.github/workflows/publish.yml`)
- [x] Homebrew formula (`Formula/tesla-cli.rb`)
- [x] 149 tests passing, ruff lint clean

### v1.0.0 — Stable Release ✅ SHIPPED
- [x] `tesla dossier estimate` — community-sourced delivery date estimation (optimistic/typical/conservative)
- [x] `tesla vehicle windows` — vent / close all windows
- [x] `tesla vehicle charge-port` — open / close / stop charging port
- [x] `tesla vehicle software` — current SW version + pending update status + `--install`
- [x] `tesla notify list/add/remove/test` — full Apprise notification management
- [x] 178 tests, ruff clean
- [x] Tagged v1.0.0, pushed to GitHub → PyPI publish triggered
- [ ] Submit Homebrew formula to tap

### v1.1.0 — More Commands ✅ SHIPPED
- [x] `tesla vehicle nearby` — real-time Supercharger stall availability
- [x] `tesla teslaMate efficiency` — per-trip energy efficiency (Wh/km)
- [x] Portuguese (pt) i18n
- [x] 220 tests, ruff clean

### v1.2.0 — Fleet-Only Features ✅ SHIPPED
- [x] `tesla vehicle alerts` — recent fault alerts
- [x] `tesla vehicle release-notes` — OTA firmware notes
- [x] `tesla vehicle valet` — valet mode toggle
- [x] `tesla vehicle schedule-charge` — scheduled charging control
- [x] `tesla dossier clean` — prune old snapshots
- [x] French (fr) i18n
- [x] 260 tests, ruff clean

### v1.2.1 — Free Backends Hardening ✅ SHIPPED
- [x] `BackendNotSupportedError` with actionable migration hints
- [x] Graceful errors for all 6 Fleet-only commands on free backends
- [x] TessieBackend completed (vehicle_state, service_data, nearby_sites)
- [x] 272 tests, ruff clean

### v1.3.0 — All Competitive Gaps Closed ✅ SHIPPED
- [x] `tesla vehicle tires` — TPMS pressure (bar + PSI), color-coded warnings
- [x] `tesla vehicle homelink` — trigger garage door opener
- [x] `tesla vehicle dashcam` — save clip to USB
- [x] `tesla vehicle rename` — rename vehicle
- [x] `tesla security remote-start` — keyless drive
- [x] `tesla dossier battery-health` — degradation from snapshot history
- [x] `tesla teslaMate vampire` — vampire drain via SQL CTE
- [x] `--csv` export on teslaMate trips/charging/efficiency
- [x] `order watch --on-change-exec` — shell automation hook
- [x] `stream live --mqtt` — MQTT telemetry publishing
- [x] Energy cost tracking (`charge status` + `cost_per_kwh`)
- [x] German (de) + Italian (it) i18n → 6 languages total
- [x] 338 tests, ruff clean

### v1.4.0 — Headless Security + New Commands ✅ SHIPPED
- [x] `tesla charge departure` — scheduled departure with preconditioning + off-peak window
- [x] `tesla vehicle precondition` — max preconditioning toggle (blast heat/cool)
- [x] `tesla vehicle screenshot` — trigger display screenshot → TeslaConnect
- [x] `tesla vehicle tonneau` — Cybertruck tonneau cover (open/close/stop/status)
- [x] `tesla teslaMate geo` — most-visited locations ranked by visit count + CSV export
- [x] `tesla config encrypt-token` — AES-256-GCM token encryption for headless servers
- [x] `tesla config decrypt-token` — reverse token encryption
- [x] `cryptography` dependency added
- [x] 388 tests, ruff clean

### v1.5.0 — PDF, Backup, Monthly Reports ✅ SHIPPED
- [x] `tesla dossier export-pdf` — full PDF dossier (fpdf2 optional dep)
- [x] `tesla config backup` / `tesla config restore` — config export/import with token redaction
- [x] `tesla teslaMate report` — monthly driving + charging summary (DC vs AC, Wh/km)
- [x] `tesla vehicle sentry-events` — sentry-filtered alert log (Fleet API)
- [x] 413 tests, 2 skipped (fpdf2 optional), ruff clean

### v1.6.0 — HTML Export, Schedule Preview, Store DB ✅ SHIPPED
- [x] `tesla dossier export-html` — standalone HTML report (no extra deps), dark-themed, self-contained CSS
- [x] `tesla charge schedule-preview` — scheduled charge + departure settings in one consolidated view
- [x] `tesla order stores` — 100+ embedded Tesla store/SC locations (EU/US/CA/AU/CN/JP); `--country`, `--city`, `--near lat,lon`
- [x] 443 tests, ruff clean

### v1.7.0 — OTA Watch, Speed Limit, Lifetime Stats ✅ SHIPPED
- [x] `tesla vehicle sw-update` — one-shot or `--watch` mode + `--notify` Apprise on OTA detection
- [x] `tesla vehicle speed-limit` — show/set/activate/deactivate/clear Speed Limit Mode with PIN
- [x] `tesla teslaMate stats` — lifetime driving + charging stats with efficiency banner
- [x] 471 tests, ruff clean

### v1.8.0 — Bio, Graph, HTML Themes, Cabin Protection ✅ SHIPPED
- [x] `tesla vehicle bio` — 5-panel comprehensive vehicle profile (identity/battery/climate/drive/scheduling)
- [x] `tesla teslaMate graph` — ASCII bar chart of charging sessions (kWh, color-coded, terminal-scaled)
- [x] `tesla dossier export-html --theme light|dark` — light mode with WCAG-AA deep red `#c0001a`
- [x] `tesla vehicle cabin-protection` — show/set/toggle Cabin Overheat Protection
- [x] 501 tests, ruff clean

### v1.9.0 — Daily Chart, Order ETA, Config Doctor ✅ SHIPPED
- [x] `tesla teslaMate daily-chart` — per-day kWh added chart (new SQL `get_daily_energy(days)`); `--days N`
- [x] `tesla order eta` — delivery ETA (best/typical/worst) from community phase durations; phase breakdown table
- [x] `tesla config doctor` — health check: token, VIN, RN, backend, TeslaMate, config file; exit 1 on fail
- [x] 523 tests, ruff clean

### v2.0.0 — Heatmap + Live Watch ✅ SHIPPED
- [x] `tesla teslaMate heatmap` — GitHub-style calendar grid of driving days (color-coded by km, week columns, month labels)
- [x] `tesla vehicle watch` — continuous monitoring loop: alerts on battery/lock/door/climate/charging state changes, `--notify` Apprise
- [x] `get_drive_days(days)` SQL query in TeslaMate backend
- [x] 536 tests, ruff clean

### v2.1.0 — Next Milestone
- [ ] WebSocket streaming backend (real-time Fleet API telemetry)
- [ ] `tesla vehicle map` — ASCII terminal map showing current vehicle location on a coordinate grid
- [ ] Complete competitor feature parity audit + gap-close sprint
