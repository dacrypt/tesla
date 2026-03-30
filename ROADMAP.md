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
| **Multi-language UI** | — | ✅ (5 langs) | — | — | — | — |
| **Share / anonymize mode** | — | ✅ | — | — | — | — |
| **Token encryption at rest (AES-256-GCM)** | — | — | ✅ | — | — | — |
| **Offline option-code catalog** | — | — | ✅ | — | — | — |
| **Color-coded recursive diff (change display)** | — | — | — | — | ✅ | — |
| **Delivery checklist** | — | — | — | — | — | ✅ (12 items) |
| **Delivery gates / milestones tracker** | — | — | — | — | — | ✅ (13 gates) |
| **Community delivery estimation** | — | — | — | — | — | ✅ |
| **Web UI** | — | — | — | — | — | ✅ |
| **Store location DB (200+ EU locations)** | — | — | — | — | ✅ | — |
| **RUNT integration (Colombia registry)** | ✅ | — | — | — | — | — |
| **SIMIT integration (Colombia fines)** | ✅ | — | — | — | — | — |
| **Fleet API support** | ✅ | — | — | — | — | — |
| **Tessie proxy support** | ✅ | — | — | — | — | — |
| **Historical snapshot archive** | ✅ | — | — | — | — | — |
| **Real-time telemetry (WebSocket stream)** | partial | — | — | — | — | — |

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
| **Multi-language UI** | TOST | 🔲 Spanish UI first, then Portuguese / French |
| **TeslaMate integration** | — | 🔲 Import trip history, charging sessions, software OTA log |
| **Community delivery estimation** | GewoonJaap | 🔲 Crowdsourced avg days from status to delivery |

---

## What Makes tesla-cli Unique

No competing tool combines all of these in one CLI:

1. **Dossier** — aggregated vehicle file with 10+ data sources, historical snapshots, and `jq`-friendly JSON
2. **Free vehicle control** — Owner API backend, zero cost, zero registration
3. **Deepest integration** — NHTSA recalls, RUNT (Colombia), SIMIT (Colombia), VIN decode, ship tracking
4. **`tesla setup` wizard** — single command from clone to full configuration
5. **JSON mode everywhere** — scriptable output on every command, composable with `jq`
6. **Three backends** — Owner API, Tessie, Fleet API — pick your tradeoff

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

### v1.0.0 — Stable release
- [ ] TeslaMate integration — trip history, charging sessions, OTA log
- [ ] Multi-language UI (Spanish first)
- [ ] Published to PyPI (`pip install tesla-cli`)
- [ ] Homebrew formula
- [ ] Full test coverage (unit + integration)
