# Tesla Ecosystem — Comprehensive Feature Intelligence Report

**Generated:** 2026-03-30
**Scope:** 20 tools across 5 tiers — order tracking CLIs, vehicle control libraries, self-hosted loggers, mobile/web apps, and API documentation

---

## Executive Summary

The Tesla developer ecosystem is large and fragmented. No single tool dominates all verticals — each has carved out a niche. The key dynamics:

1. **Order tracking is an underserved CLI niche.** Most order trackers are abandoned Python scripts. TOST's desktop app is the most polished, but its CLI is basic. tesla-cli is the only tool that combines order tracking, vehicle control, NHTSA data, VIN decoding, ship tracking, and delivery journey management in one integrated tool.

2. **Vehicle control CLIs are few.** Tesla's own `tesla-control` (Go) is command-rich but requires complex key enrollment. TeslaPy has a passable `cli.py`. No other pure CLI tool comes close to the command breadth of `tesla-control`.

3. **Self-hosted loggers compete on data richness.** TeslaMate (7.8k stars) is the gold standard for trip/charge analytics. TeslaLogger and TeslaFi are solid alternatives. None has CLI access — they're all web dashboards.

4. **Mobile/web apps win on UX, lose on scriptability.** Tessie, TeslaFi, Stats for Tesla, and ABRP are polished consumer apps with no scriptable interface (or minimal API). They are not competitors to a CLI.

5. **The Owner API sunset is the biggest ecosystem inflection point.** Tesla is deprecating `owner-api.teslamotors.com` for new vehicles, forcing tools to adopt Fleet API or signed commands. Most older tools have not yet fully adapted. tesla-cli supports all three backends (Owner, Fleet, Tessie proxy).

6. **Colombia-specific features (RUNT, SIMIT) are unique to tesla-cli.** No other tool in any tier touches Colombian vehicle registry integration.

---

## Tool Profiles

---

### Tier 1 — Direct CLI/Script Competitors (Order Tracking Focus)

---

#### 1. TOST (Tesla Order Status Tracker)

**Website:** https://www.tesla-order-status-tracker.de/
**Repo:** https://github.com/chrisi51/tesla-order-status
**Stars:** ~50
**Last Updated:** Actively maintained (2025–2026)
**Language:** Python 3
**License:** Open source

**Core Functionality:**
Python CLI script for monitoring Tesla order status. Available both as a raw script and as a packaged cross-platform desktop app (macOS Apple Silicon, Windows 10/11 x64, Linux AppImage).

**Commands / Features:**
- `python3 tesla_order_status.py` — base invocation
- `--all` — verbose output of every available data key
- `--details` — show financing information and extended details
- `--share` — anonymized output hiding order ID and VIN
- `--status` — exit-code reporting (0=no changes, 1=changes, 2=pending, -1=error)
- `--cached` — use locally stored data without API calls
- `--order <referenceNumber>` — focus on a specific order
- `--update` — interactive update flow
- `--update path/to/release.zip --sha256 <hash>` — apply verified local archive
- `--help` — all options

**Desktop App Features:**
- Multi-order switching via overview list
- Timeline view: every refresh compared with previous snapshot
- Raw field change inspection with side-by-side comparison
- Multiple view modes: Standard, Details, All, Ignored
- Debug mode for raw JSON inspection
- Privacy mode (masks reference numbers and VINs)
- Markdown summary generation for Discord/chat
- Ascending/descending sort options
- One-click copy of individual timeline entries
- Offline capability — keeps last response on disk

**Unique Differentiators:**
- Cross-platform desktop app with Electron-style packaging
- Markdown export for forum/Discord posts
- SHA-256 verified self-update mechanism with zip-slip protection
- Bounded retry/backoff to prevent API rate-limit abuse

**Tech Stack:** Python 3, `requests`, `cryptography` (optional), `pyperclip` (optional)

**Auth Method:** OAuth PKCE with S256 challenge; browser redirect URL paste; optional token encryption via `TESLA_ORDER_STATUS_TOKEN_PASSPHRASE` env var; restrictive file permissions on stored tokens

**Data Sources:** Tesla Owner API, Tesla Auth (auth.tesla.com)

**Output Formats:** CLI text (colored), desktop GUI, Markdown for sharing

**Notification Support:** None (desktop app handles changes visually)

**Multi-vehicle:** Yes (`--order` filter)

**Offline Capability:** Yes — `--cached` mode; local option-code catalog; last response on disk

**i18n/Localization:** Auto-detects system locale; modular language support

**Data Stored:**
- `data/private/tesla_tokens.json`
- `data/private/settings.json`
- `data/private/tesla_orders.json`
- `data/private/tesla_order_history.json`
- `data/public/option-codes/` — local catalog

---

#### 2. enoch85/tesla-order-status

**Repo:** https://github.com/enoch85/tesla-order-status
**Stars:** ~20
**Last Updated:** 2025
**Language:** Python 3
**License:** Open source

**Core Functionality:**
A security-hardened fork of the TOST/chrisi51 codebase. Removes all remote telemetry, locks down outbound connections to a strict allowlist, and adds token encryption at rest. Intended for users running the script on a server or NAS where security posture matters.

**Commands / Features:**
- Same CLI flags as chrisi51 TOST: `--all`, `--details`, `--share`, `--status`, `--cached`, `--order`, `--update`, `--help`
- Token encryption via `TESLA_ORDER_STATUS_TOKEN_PASSPHRASE` env var
- Strict outbound allowlist: only Tesla API + optional GitHub for update checks
- SHA-256 archive verification on updates
- Zip-slip and symlink validation during archive extraction
- TLS verification enforced on all requests
- No third-party telemetry, no remote banners, no remote option-code lookups
- Auto-migration of legacy file layouts to `data/private/`
- Automatic locale detection with fallback to English

**Unique Differentiators:**
- Security-first hardening fork — the only order tracker with explicit allowlist networking
- Token encryption at rest (not just file permissions)
- Designed explicitly for self-hosted / NAS / server deployment

**Tech Stack:** Python 3, `requests`, `cryptography` (optional), `pyperclip` (optional)

**Auth Method:** OAuth PKCE + S256; tokens stored locally with restrictive permissions; optional encryption at rest

**Data Sources:** Tesla Owner API only (allowlist-enforced)

**Output Formats:** CLI text

**Notification Support:** None

**Multi-vehicle:** Yes

**Offline Capability:** Yes — `--cached` mode

**i18n/Localization:** Auto-detect + fallback to English

---

#### 3. WesSec/TeslaOrderChecker (teslaorderchecker)

**Repo:** https://github.com/WesSec/teslaorderchecker
**Stars:** 6
**Last Updated:** Archived February 29, 2024 (no longer maintained)
**Language:** Python
**License:** MIT

**Core Functionality:**
A simple daemon that polls the Tesla API every 10 minutes and sends Apprise notifications when order changes are detected. Local storage preserves state so changes are detected even when the script wasn't running. Config via JSON file.

**Commands / Features:**
- `python main.py` — run the monitoring daemon
- Polls every 10 minutes (hardcoded interval)
- Change detection against locally stored state
- Apprise notification integration (user configures URL in source code)
- Config file: `config.json` (must copy from `config.json.sample`)

**Unique Differentiators:**
- First tool in this tier to use Apprise for notifications
- "Persistent state" detection catches changes from offline periods

**Tech Stack:** Python, requests, Apprise

**Auth Method:** Tesla refresh token (obtained separately via adriankumpf/tesla-auth or similar)

**Data Sources:** Tesla API

**Output Formats:** CLI text, Apprise notifications

**Notification Support:** Any Apprise-compatible service (Telegram, Discord, Slack, etc.)

**Multi-vehicle:** Likely single — not confirmed

**Offline Capability:** Partial — stores previous state locally

**i18n/Localization:** None

**Note:** Archived/abandoned. Not a viable active competitor.

---

#### 4. niklaswa/tesla-order-status

**Repo:** https://github.com/niklaswa/tesla-order-status
**Stars:** 50 | **Forks:** 42
**Last Updated:** Actively maintained (46 commits)
**Language:** Python 3 (100%)

**Core Functionality:**
Python script for retrieving Tesla order status and vehicle data including odometer readings. One of the earliest order-tracking scripts; inspired many forks.

**Commands / Features:**
- `python3 tesla_order_status.py` — run and compare to previous state
- OAuth 2.0 PKCE authentication flow with browser redirect
- Token persistence in local JSON files
- Change detection: recursive diff with path tracking, ANSI color output (green=added, red=removed)
- Displays: order details, reservation info, vehicle status, delivery data
- TeslaStore routing code → store label mapping via `tesla_stores.py`
- Odometer tracking
- Optional local data saving (prompts user)

**Unique Differentiators:**
- Original source many other tools forked from
- Includes Tesla store location mapping module (`tesla_stores.py`)
- Lightweight — only `requests` dependency

**Tech Stack:** Python 3, `requests`

**Auth Method:** OAuth 2.0 PKCE; browser URL redirect paste; tokens saved to local JSON

**Data Sources:** Tesla Owner API, Tesla Gateway API

**Output Formats:** ANSI-colored CLI text

**Notification Support:** None

**Multi-vehicle:** Not confirmed

**Offline Capability:** Partial (stores previous state)

**i18n/Localization:** None

---

#### 5. GewoonJaap/tesla-delivery-status-web

**Repo:** https://github.com/GewoonJaap/tesla-delivery-status-web
**Stars:** 13 | **Forks:** 8
**Live:** https://tesla-status.mrproper.dev/
**Last Updated:** 103 commits
**Language:** TypeScript (97.2%), HTML (2.8%)

**Core Functionality:**
A web application (not a CLI) for tracking Tesla order and delivery status. AI-powered using Google Gemini API. Provides real-time updates, change highlighting, and delivery timeline information.

**Features:**
- Real-time order monitoring
- Change highlighting since last check
- Delivery timeline display
- Cross-platform web UI (works in any browser with JavaScript)
- Dark mode
- Responsive design with animations

**Unique Differentiators:**
- Only web-based order tracker in this tier
- Uses Google Gemini API (AI-assisted features)
- Live hosted instance available

**Tech Stack:** React + TypeScript, Vite, Google Gemini API, npm

**Auth Method:** Not specified (likely Tesla credentials via browser session)

**Output Formats:** Web UI

**Notification Support:** None confirmed

**Multi-vehicle:** Not confirmed

**Offline Capability:** None

**i18n/Localization:** None confirmed

---

### Tier 2 — Vehicle Control CLIs

---

#### 6. tesla-control (teslamotors/vehicle-command)

**Repo:** https://github.com/teslamotors/vehicle-command
**Stars:** 632 | **Forks:** 165
**Language:** Go (99.5%)
**License:** Apache-2.0
**Latest Release:** v0.4.1 (Feb 4, 2026)

**Core Functionality:**
Tesla's official Go SDK for end-to-end authenticated vehicle commands. Includes four binaries: `tesla-control` (send commands), `tesla-keygen` (key management), `tesla-http-proxy` (REST proxy), and `tesla-auth-token` (OAuth management).

**Commands (tesla-control):**

*Locking & Access:*
- `lock` — lock vehicle
- `unlock` — unlock vehicle
- `valet-mode-on [PIN]` — enable valet mode
- `valet-mode-off` — disable valet mode
- `guest-mode-on` / `guest-mode-off` — Guest Mode toggle
- `erase-guest-data` — erase Guest Mode user data
- `drive` — remote start

*Climate:*
- `climate-on` / `climate-off`
- `climate-set-temp TEMP` — set temperature in Celsius
- `steering-wheel-heater STATE`
- `seat-heater SEAT LEVEL` — set seat heater level by position
- `auto-seat-and-climate POSITIONS [STATE]`

*Vehicle Operations:*
- `wake` — wake up vehicle
- `honk` — honk horn
- `ping` — ping vehicle
- `flash-lights`

*Charging:*
- `charging-start` / `charging-stop`
- `charging-set-limit PERCENT`
- `charging-set-amps AMPS`
- `charging-schedule MINS`
- `charging-schedule-cancel`
- `charging-schedule-add DAYS TIME LAT LON [REPEAT] [ID] [ENABLED]`
- `charging-schedule-remove TYPE [ID]`
- `charge-port-open` / `charge-port-close`

*Doors & Trunk:*
- `trunk-open` / `trunk-close` / `trunk-move`
- `frunk-open`
- `tonneau-open` / `tonneau-close` / `tonneau-stop` (Cybertruck)
- `autosecure-modelx` — close falcon-wing doors + lock

*Media:*
- `media-set-volume VOLUME`
- `media-volume-up` / `media-volume-down`
- `media-next-track` / `media-previous-track`
- `media-next-favorite` / `media-previous-favorite`
- `media-toggle-playback`

*Power & Modes:*
- `keep-accessory-power STATE`
- `low-power-mode STATE`
- `sentry-mode STATE`

*Software:*
- `software-update-start DELAY`
- `software-update-cancel`

*Windows:*
- `windows-vent` / `windows-close`

*Key Management:*
- `add-key PUBLIC_KEY ROLE FORM_FACTOR`
- `add-key-request` — NFC-card approval
- `remove-key` / `rename-key` / `list-keys`
- `session-info`

*Scheduling:*
- `precondition-schedule-add` / `precondition-schedule-remove`

*State & Info:*
- `state CATEGORY` — fetch vehicle state over BLE
- `body-controller-state` — limited state over BLE
- `product-info` — JSON product info

*Raw API:*
- `get ENDPOINT` — raw GET to Fleet API
- `post ENDPOINT [FILE]` — raw POST

**Global Flags:**
- `-ble` — use Bluetooth Low Energy
- `-h` — help

**Unique Differentiators:**
- **Only tool with BLE (Bluetooth Low Energy) vehicle control**
- Official Tesla SDK — most authoritative command set
- End-to-end encryption with public key enrollment
- HTTP proxy server for REST-to-BLE translation
- Cybertruck-specific commands (tonneau, autosecure)
- Session caching to reduce latency
- NFC card key pairing workflow

**Tech Stack:** Go 1.23+

**Auth Method:** Two-factor: OAuth 2.0 Bearer token + enrolled public key (cryptographic signature); system keyring for both tokens and private keys

**Data Sources:** Tesla Fleet API, BLE (direct to vehicle)

**Output Formats:** CLI text, JSON (product-info), HTTP proxy

**Notification Support:** None

**Multi-vehicle:** Via `TESLA_VIN` env var or `-vin` flag

**Offline Capability:** BLE commands work locally without internet

**Platform:** macOS + Linux (Windows unsupported due to BLE library limitations)

---

#### 7. TeslaPy

**Repo:** https://github.com/tdorssers/TeslaPy
**Stars:** 417 | **Forks:** ~130
**Language:** Python 3.10+
**License:** Open source
**Last Updated:** ~2024 (30 open issues, 203 commits)

**Core Functionality:**
Python library providing remote monitoring and control of Tesla vehicles, Powerwalls, and solar panels via the unofficial Owner API. Includes three reference apps: `cli.py`, `menu.py` (tabular console), and `gui.py` (Tkinter GUI).

**CLI Commands (cli.py):**
- `-e EMAIL` — login email (required)
- `-f / --filter` — filter by id, vin, etc.
- `-l / --list` — list all vehicles/batteries
- `-g / --get` — full vehicle data rollup
- `-o / --option` — vehicle option codes
- `-v / --vin` — VIN decode
- `-w / --wake` — wake vehicle(s)
- `-m / --mobile` — get mobile enabled state
- `-n / --nearby` — list nearby charging sites
- `-G / --location` — GPS location
- `-B / --basic` — basic vehicle data only
- `-r / --stream` — streaming vehicle data (WebSocket on-change)
- `-H / --history` — charging history
- `-b / --battery` — detailed battery state and config
- `-s / --site` — current site generation data (solar)
- `-S / --service` — service scheduling eligibility
- `-a / --api ENDPOINT [k=v]` — raw API call
- `-c / --command ENDPOINT` — product command
- `-k / --keyvalue k=v` — API parameter
- `-R / --refresh TOKEN` — supply refresh token
- `-U / --url URL` — SSO service base URL
- `-p / --proxy URL` — proxy server
- `-t / --timeout N` — connect/read timeout
- `-V / --verify` — disable SSL verification
- `-d / --debug` — debug logging
- `-L / --logout` — clear token cache
- `--chrome / --edge` — browser choice for auth

**Library Features:**
- `vehicle_list()`, `battery_list()`, `solar_list()`
- `fetch_token()`, `refresh_token()`, `logout()`
- `get_vehicle_data()`, `get_vehicle_summary()`
- `sync_wake_up()` — blocking wake with retry
- `stream()` — WebSocket subscription for real-time data
- `compose_image()` — vehicle image composition
- `decode_vin()` — VIN parsing
- `dist_units()`, `temp_units()` — unit conversion per vehicle locale
- Battery: `get_history_data()`, `get_calendar_history_data()`
- Pluggable authenticators (pywebview, Selenium for headless)
- Multi-region: `auth.tesla.cn` for China

**Unique Differentiators:**
- **WebSocket streaming API** — real-time on-change data (not polling)
- Vehicle image composition from API
- Powerwall + Solar panel support
- Pluggable headless auth (Selenium/pywebview)
- Three reference UIs (CLI, tabular console, Tkinter GUI)
- China region support

**Tech Stack:** Python 3.10+, `requests`, `requests-oauthlib`, `websocket-client`

**Auth Method:** OAuth 2.0 SSO + PKCE; token cache in `cache.json`; pluggable authenticators; 3rd-party refresh token support

**Data Sources:** Tesla Owner API (unofficial), WebSocket streaming

**Output Formats:** JSON (cli.py), tabular console (menu.py), Tkinter GUI (gui.py)

**Notification Support:** None

**Multi-vehicle:** Yes (filter by VIN/ID)

**Offline Capability:** None

---

#### 8. teslajsonpy

**Repo:** https://github.com/zabuldon/teslajsonpy
**Stars:** 58 | **Forks:** 64
**Language:** Python (99.6%)
**License:** Apache-2.0
**Latest Release:** v3.13.2 (August 10, 2025)
**Total Commits:** 813

**Core Functionality:**
Async Python module for the Tesla API, designed primarily to power the Home Assistant Tesla integration. Provides comprehensive sensor and control classes.

**Sensors/Data Points:**
- Battery level, charge rate, energy added
- Charger power, inside/outside temperature
- Odometer, estimated range
- Time to charge completion
- TPMS tire pressure (all 4 wheels)
- Active route: arrival time, distance to destination
- Vehicle online/offline/sleeping state
- Parking brake status
- Door status (all doors)

**Controls:**
- Climate: HVAC on/off, target temperature, preset modes (defrost, keep-on, dog mode, camp mode)
- Device tracker: car location, active route destination
- Covers: charger door, frunk, trunk, windows
- Locks: door lock, charge port latch
- Buttons: horn, flash lights, wake up, force data update, trigger HomeLink, remote start

**Unique Differentiators:**
- Only async Python library in this tier (asyncio-native)
- Built explicitly for Home Assistant integration
- 100% test coverage requirement
- Poetry + make build system with typing enforcement
- Supports HomeLink trigger

**Tech Stack:** Python (async), Poetry, pytest, pylint, mypy

**Auth Method:** OAuth 2.0 (via underlying tesla API)

**Data Sources:** Tesla Owner API (unofficial), transitioning to Fleet API

**Output Formats:** Python objects (library, no CLI)

**Notification Support:** None (library only)

**Multi-vehicle:** Yes

**Offline Capability:** None

---

#### 9. python-tesla-fleet-api (Teslemetry)

**Repo:** https://github.com/Teslemetry/python-tesla-fleet-api
**Stars:** 33 | **Forks:** 12
**Language:** Python (99.9%)
**License:** Apache 2.0
**Latest Release:** v1.4.5 (March 24, 2026)
**Total Commits:** 388 | **Releases:** 115

**Core Functionality:**
Python library supporting Tesla Fleet API, signed vehicle commands, local Bluetooth (BLE) encrypted communication, and integrations with Teslemetry and Tessie services. Powers the official Home Assistant Tesla Fleet integration.

**Features:**
- Fleet API for vehicles (list, wake, commands)
- Fleet API for energy sites (Powerwall, Solar)
- Signed vehicle commands (VehicleSigned class)
- Local BLE encrypted communication (via `bleak`)
- Teslemetry service integration
- Tessie service integration
- OAuth2 flow: `TeslaFleetOAuth` (login URL, code exchange, refresh)
- Scopes: `openid`, `email`, `offline_access`
- aiohttp-based (fully async)
- Protobuf-based BLE protocol

**Unique Differentiators:**
- **BLE encrypted local communication** — no internet required for commands
- Fleet API + BLE in a single library
- Protobuf protocol implementation (car_server.proto, vcsec.proto, etc.)
- Multi-service abstraction: Tesla direct, Teslemetry, Tessie all via same interface
- Most actively released library in the ecosystem (115 releases)
- Powers Home Assistant Fleet integration

**Tech Stack:** Python, aiohttp, bleak (BLE), protobuf

**Auth Method:** OAuth 2.0 Fleet API; API token for Teslemetry/Tessie

**Data Sources:** Tesla Fleet API, BLE direct, Teslemetry API, Tessie API

**Output Formats:** Python objects (library only)

**Notification Support:** None (library only)

**Multi-vehicle:** Yes

**Offline Capability:** Yes (BLE mode)

---

### Tier 3 — Self-Hosted Dashboards / Data Loggers

---

#### 10. TeslaMate

**Repo:** https://github.com/teslamate-org/teslamate
**Stars:** 7.8k | **Forks:** 917
**Language:** Elixir (84.2%), HTML, JavaScript, Shell
**License:** AGPL-3.0
**Latest Release:** v3.0.0 (Feb 28, 2026)

**Core Functionality:**
The dominant self-hosted Tesla data logger. Records every drive, charge, and idle period with high precision. Provides 20+ Grafana dashboards. Designed to have zero vampire drain impact.

**Data Tracked:**
- High-precision drive data (speed, power, GPS coordinates)
- Charge history (energy, cost, efficiency, location, charger type)
- Battery health and degradation over time
- Vampire drain (parasitic power loss when parked)
- Vehicle online/asleep/idle states
- Software update history
- Addresses (automatic reverse geocoding)
- Geofence events
- Energy consumption (gross and net)

**Dashboards (20 bundled):**
Battery Health, Charge Level, Charges, Charge Details, Charging Stats, Database Information, Drive Stats, Drives, Drive Details, Efficiency, Locations, Mileage, Overview, Projected Range, States, Statistics, Timeline, Trip, Updates, Vampire Drain, Visited (lifetime map)

**Integrations:**
- MQTT broker (publishes vehicle data locally)
- Home Assistant (via MQTT)
- Node-Red (via MQTT)
- Telegram (via MQTT)
- Grafana (built-in visualization)
- TeslaFi data import
- tesla-apiscraper data import

**Unique Differentiators:**
- **Zero additional vampire drain** — the gold standard claim
- Lifetime driving map (Visited dashboard)
- 20 pre-built dashboards covering every angle
- MQTT integration enables any automation system
- Geo-fencing for custom location labeling
- Import from TeslaFi and tesla-apiscraper
- Multi-vehicle per account
- CLA-protected open source

**Tech Stack:** Elixir + Phoenix LiveView, PostgreSQL, Grafana, Docker, MQTT, Nix

**Auth Method:** Tesla OAuth2 (official Fleet API for new vehicles; Owner API for older ones)

**Data Sources:** Tesla API

**Output Formats:** Grafana dashboards (web), MQTT messages, PostgreSQL (queryable)

**Notification Support:** Telegram (via MQTT), any MQTT-connected system

**Multi-vehicle:** Yes

**Offline Capability:** Self-hosted — fully local after setup

**i18n/Localization:** Not confirmed

---

#### 11. TeslaFi

**Website:** https://www.teslafi.com / https://about.teslafi.com
**Type:** Commercial SaaS
**Price:** $7.99/month or $79.99/year (7-day free trial)
**Models:** S, 3, X, Y

**Core Functionality:**
The original Tesla data logger (predates TeslaMate). Cloud-based — no software to install. Logs every drive, charge, and idle with comprehensive analytics. 811 million miles logged across user fleet.

**Features:**
- Automatic trip logging with category tagging
- Weather data per drive
- Charging log by location and type (Home/Travel/Supercharger)
- Per-charge: kWh used, kWh added, efficiency, cost, voltage/amperage (avg+max), range added, odometer
- Per-minute charge data with graphs
- 100+ configurable data points in layout editor
- Battery health and degradation tracking
- Temperature efficiency analysis
- Fleet software update tracker
- Monthly calendar activity view
- Vehicle remote control scheduling
- Amazon Alexa skill (US, CA, AU, UK)
- API tokens for programmatic access
- Smart home integration (SmartThings)
- Fleet tracking for businesses (mileage, efficiency, cost)
- Expense tracking
- Custom alerts (software updates, battery levels)
- Multi-country availability

**Unique Differentiators:**
- Oldest and most battle-tested logger in the ecosystem
- Amazon Alexa skill with voice queries
- SmartThings integration
- 100+ configurable data columns
- API token access for programmatic use
- "Software Tracker" feature for fleet-wide firmware monitoring

**Tech Stack:** Cloud SaaS (proprietary backend)

**Auth Method:** Tesla account credentials (user provides to TeslaFi cloud)

**Data Sources:** Tesla API (cloud-polled)

**Output Formats:** Web dashboard, email summaries, CSV export, Alexa voice

**Notification Support:** Email, Alexa, custom alerts

**Multi-vehicle:** Yes

**Offline Capability:** None (cloud-only)

**i18n/Localization:** English

---

#### 12. Tessie

**Website:** https://tessie.com
**Type:** Commercial SaaS + API platform
**Price:** $12.99/month, $129.99/year, $299.99 lifetime

**Core Functionality:**
A comprehensive Tesla management platform described as "apps, analytics, automations and APIs for the world's most sophisticated vehicles." Goes beyond logging to offer automation, real-time control, and a developer API.

**Features:**
- Trip tracking (drive history)
- Battery health tracking + fleet comparison
- Charging history + phantom drain monitoring
- Cost projections and savings recommendations
- 200+ real-time OBD-style data points
- Full vehicle remote control via web browser
- Automation engine: custom workflows (triggers + conditions + actions)
- Sentry Mode automations (flash lights, honk, lock on detection)
- Geofence alerts (enter/exit notifications)
- Custom charging schedules
- Smart alerts (movement detection, maintenance reminders)
- Data import from TezLab and TeslaMate
- Smart home integrations: HomeKit, Alexa, Google Home, Home Assistant, IFTTT
- Apple Watch app (via official Tessie app)
- Wear OS app
- Amazon Alexa integration
- Developer API (drop-in Fleet API proxy)
- FSD / Self-Driving stats tracking
- Insurance data access via API
- 10 customizable dashboard tiles

**Platform Coverage:**
- Web dashboard
- iOS (iPhone + iPad)
- macOS
- Apple Watch (watchOS)
- Android
- Wear OS
- Amazon Alexa
- Web (browser access to car from any computer)

**Unique Differentiators:**
- **Automation engine** — unique in the ecosystem for conditional automations
- **200+ OBD data points** real-time
- **Developer API** that acts as a Fleet API proxy (no complex setup)
- **Self-Driving/FSD statistics** via API
- Drop-in Fleet API replacement at `api.tessie.com`
- Control car from any web browser (no app needed)
- Multi-platform: web + iOS + Android + Apple Watch + Wear OS + Alexa

**Tech Stack:** Commercial SaaS

**Auth Method:** Tesla account credentials (stored by Tessie)

**Data Sources:** Tesla API (polled via Tessie cloud)

**Output Formats:** Web UI, mobile apps, Alexa voice, API responses

**Notification Support:** Push notifications, geofence alerts, movement alerts, Alexa

**Multi-vehicle:** Yes

**Offline Capability:** None (cloud-only)

**i18n/Localization:** Not confirmed

---

#### 13. TeslaLogger

**Repo:** https://github.com/bassmaster187/TeslaLogger
**Stars:** 607 | **Forks:** ~120
**Language:** C# (84.6%), PHP (10.9%), CSS (4.0%)
**License:** GPL-3.0
**Latest Version:** V1.63.0 (Feb 26, 2025)

**Core Functionality:**
Self-hosted data logger for Tesla Model S/3/X/Y/Cybertruck and Lucid Air. Runs on Raspberry Pi, Docker, or Synology NAS. Provides Grafana dashboards and fleet analytics.

**Features:**
- Trip statistics and consumption metrics
- Charging speed and history
- Battery degradation tracking (+ fleet comparison)
- Vampire drain analysis
- Cell voltages + temperatures (with ScanMyTesla integration)
- HVAC performance data
- Firmware version history
- Visited locations (GPS)
- Custom Points of Interest (POI)
- Geofencing with timeline visualization
- Automatic Supercharger invoice download
- A Better Route Planner integration (without credential sharing)
- ScanMyTesla integration for deep battery data
- Tesla Fleet API support (new vehicles, post-Dec 2023)
- Import from TeslaFi and TeslaMate
- Fleet degradation + charging curve comparison

**Unique Differentiators:**
- **ScanMyTesla integration** — cell-level battery data
- **Automatic Supercharger invoice download**
- **ABPR integration** without sharing credentials
- Lucid Air support (not just Tesla)
- 11-language localization
- Monthly subscription model for Fleet API costs

**Tech Stack:** C#, PHP, Grafana, MariaDB, Docker, OpenStreetMap/Nominatim/MapQuest

**Auth Method:** Tesla Fleet API (official, for new vehicles); Owner API (legacy)

**Data Sources:** Tesla API, ScanMyTesla, ABPR

**Output Formats:** Grafana dashboards, web admin UI

**Notification Support:** MQTT (connect to any MQTT consumer)

**Multi-vehicle:** Yes

**Offline Capability:** Self-hosted — local after setup

**i18n/Localization:** English, German, Danish, Spanish, Chinese, French, Italian, Norwegian, Nederlands, Portuguese, Russian (11 languages)

---

#### 14. tesla_dashcam

**Repo:** https://github.com/ehendrix23/tesla_dashcam
**Stars:** 722 | **Forks:** 95
**Language:** Python 3.13.0+
**License:** Open source
**Last Updated:** Actively maintained (433 commits)

**Core Functionality:**
CLI tool that merges Tesla dashcam footage from up to 6 cameras (front, rear, left/right repeaters, left/right pillars) into single video files. Supports SavedClips and SentryClips.

**Layout Options:**
- FULLSCREEN, MOSAIC, PERSPECTIVE, CROSS, DIAMOND, HORIZONTAL
- Custom camera positioning and ordering

**Key Flags:**
- `--layout` — choose video arrangement
- `--merge [TEMPLATE]` — combine events into one video
- `--no-front/rear/left/right/left-pillar/right-pillar` — exclude cameras
- `--perspective` / `--mirror` — view transformations
- `--scale`, `--camera_position`, `--camera_order`
- `--speedup/--slowdown MULTIPLIER` — time manipulation
- `--motion_only` — fast-forward static sections
- `--fps N` — frame rate (default 24)
- `--quality LOWEST|LOWER|LOW|MEDIUM|HIGH`
- `--encoding x264|x265`
- `--gpu/--no-gpu`, `--gpu_type nvidia|intel|qsv|rpi|vaapi`
- `--no-timestamp` / `--text_overlay_fmt`
- `--fontcolor`, `--fontsize`, `--font`
- `--start_timestamp`, `--end_timestamp`
- `--sentry_offset`, `--chapter_offset`
- `--monitor` — watch for USB drive insertion
- `--delete_source` — remove originals after processing
- `--skip_existing`
- `--loglevel DEBUG|INFO|WARNING|ERROR|CRITICAL`
- `--check_for_update` / `--no-check_for_update`
- `@filename` — read parameters from file
- `--version`, `--help`

**Unique Differentiators:**
- **Only dashcam processing tool in the ecosystem**
- GPU acceleration (NVIDIA CUDA, Intel QSV, VAAPI, Raspberry Pi)
- USB drive auto-detection trigger (`--monitor`)
- Merge template variables: `{event_city}`, `{event_reason}`, `{event_latitude}`, etc.
- Pre-compiled executables (Windows/macOS — no Python needed)
- 6-camera mosaic layouts

**Tech Stack:** Python 3.13+, FFmpeg

**Auth Method:** None (local filesystem access to dashcam files)

**Data Sources:** Local USB/SD card dashcam clips

**Output Formats:** MP4 video files

**Notification Support:** Desktop notification on completion

**Multi-vehicle:** N/A (processes local files)

**Offline Capability:** Fully offline (local processing only)

**i18n/Localization:** None

---

### Tier 4 — Mobile/Web Apps

---

#### 15. A Better Route Planner (ABRP)

**Website:** https://abetterrouteplanner.com
**Type:** Freemium web/mobile app + B2B API
**Platforms:** Web, iOS, Android, Android Automotive, in-car browser

**Core Functionality:**
The leading EV route planner. Plans trips with optimal charging stops, accounting for vehicle model, elevation, weather, and driving conditions.

**Free Features:**
- Optimal route calculation with charging stops
- 1,000+ data-driven EV models
- Customizable routing preferences
- Adaptive consumption profiles
- Save and share plans
- Mobile navigation
- Android Automotive app
- Charging station search/filter + amenities
- Community charger data

**Premium Features:**
- Live traffic integration
- Weather forecasts for range prediction
- Real-time charger availability
- Advanced charger filters (trailer-friendly, dog-friendly, restrooms)
- Android Auto + Apple CarPlay navigation
- Speed camera alerts
- Unlimited saved vehicles
- Family vehicle sharing
- Drive + charge history with export
- Apple Watch monitoring + alerts
- **Vehicle Live Data**: Connect Tesla (requires Premium) for real-time battery/consumption
- Automatic route adaptation while driving

**Unique Differentiators:**
- **Best-in-class multi-stop EV routing** across 1,000+ models
- Live telemetry integration predicts SOC within 3-5% accuracy (vs 15-20% for native nav)
- B2B EV Routing API for automakers and charging networks
- In-car browser deployment option
- Apple CarPlay + Android Auto support

**Tech Stack:** Web + React Native (estimated), B2B API

**Auth Method:** Account-based; Tesla API for live telemetry (Premium)

**Data Sources:** Tesla API (telemetry), charging network APIs, weather APIs, traffic APIs

**Output Formats:** Web UI, mobile app, in-car browser, turn-by-turn navigation

**Notification Support:** Apple Watch alerts (Premium)

**Multi-vehicle:** Yes (Premium)

**Offline Capability:** Partial (cached plans)

**i18n/Localization:** Multi-language (global coverage)

---

#### 16. Stats for Tesla (Stats — For your Tesla)

**App Store:** https://apps.apple.com/us/app/stats-for-your-tesla/id1191100729
**Type:** iOS-only paid app
**Price:** $49.99 USD (one-time, no subscription)
**Platform:** iPhone only

**Core Functionality:**
Detailed Tesla statistics and battery health tracking app. Registered third-party app with Tesla Motors.

**Features:**
- Battery health tracking and degradation graphs
- Phantom drain statistics with location data
- Driving efficiency over past 30 miles
- Miles driven per day/week/month
- Charging session analytics
- Charge scheduling (stop at specified time — useful for TOU plans)
- Climate scheduling (on at configured days/times)
- Smart battery prep (warm up battery on schedule)
- Dash-cam integration (connect storage to view on iPhone/iPad)
- Cost savings calculation (EV vs gas)
- Compare max range against similar vehicles (fleet benchmarking)
- EV vs gas cost comparison
- Export all stats to spreadsheet
- Multi-vehicle support
- Metric + imperial units
- Home screen widgets (2): door status, battery level, charge time
- Dynamic Island charging info
- Apple Watch app (included)
- Solar widget for Tesla Solar generation
- Siri Shortcuts (climate on, charge port)
- Charging reminder notification (low battery + home + unplugged)
- Door/trunk open notifications when away
- Unlocked door alert + optional auto-lock
- Climate activation notification (prevent battery depletion)

**Unique Differentiators:**
- **One-time purchase** — no subscription in a subscription-heavy ecosystem
- **Battery fleet benchmarking** — compare degradation vs other Teslas
- Built-in Apple Watch app
- Solar generation widget
- Dash-cam footage viewer

**Tech Stack:** iOS (Swift/native), Tesla official API

**Auth Method:** Tesla official API (registered third-party app)

**Output Formats:** Mobile UI, widgets, Apple Watch, CSV export

**Notification Support:** Push notifications (low battery, door open, climate)

**Multi-vehicle:** Yes

**Offline Capability:** Cached data

**i18n/Localization:** Not confirmed

---

#### 17. Watch for Tesla / Watchla (Apple Watch apps)

**Official:** Tesla app v4.39.5+ includes native Apple Watch support
**Third-party:** Watchla (`https://apps.apple.com/us/app/watchla-for-tesla/id1546599747`), Teri

**Official Tesla Apple Watch App Features:**
- Lock/unlock car
- Open frunk / trunk
- Battery level + remaining range
- Climate control on/off
- Locate car in parking
- Charge port open
- Use watch as car key (UWB + digital key)

**Watchla (Third-Party) Additional Features:**
- BLE (Bluetooth) Tesla key — works without internet
- Real-time: charge state, climate state, door closures
- Gear/mode indicator (Dog Mode, Sentry Mode, etc.)
- Charge rate + remaining range
- Frunk/trunk/charge port controls
- Lock/unlock
- Full offline functionality via BLE

**Unique Differentiators (Watchla):**
- **BLE-only operation** — works without internet
- Offline control from Apple Watch

---

### Tier 5 — API Documentation / Libraries

---

#### 18. Tesla Fleet API (Official)

**Website:** https://developer.tesla.com/docs/fleet-api
**Type:** Official Tesla developer API

**Core Capabilities:**
- Paginated vehicle list endpoints
- Real-time vehicle data (live calls)
- Vehicle wake-up
- Mobile access check
- Nearby charging sites
- Fleet telemetry configuration (self-hosted streaming)
- Vehicle Command Protocol (signed commands)

**Endpoint Categories (from reverse-engineered endpoint catalog):**
- Vehicle commands: lock, unlock, horn, flash, remote start, trunk/frunk, windows, sunroof, valet mode, sentry mode, speed limit, charge port, climate, seat heaters, steering wheel heater, bioweapon mode, software update, scheduled charging/departure, media, navigation
- Vehicle state: data, summary, service data
- Charging: history, managed charging sites, balance, invoices
- Energy: Powerwall management, solar, tariffs, TOU, storm mode, programs
- Service: scheduling, appointments, estimates, invoices, mobile service
- Roadside assistance: incidents, warranty, locations
- Orders and products: product list, add key
- User: profile, license plates, profile picture
- Notifications: preferences, subscriptions, news/events
- Messages: inbox, message center
- Safety rating: telematics, daily breakdown, trips, score
- Upgrades: eligible upgrades, purchase, ESA
- Subscriptions: billing, management
- Financing: loan details, buyout, esign, acquisition
- Documents: invoices, inspection, fapiao (China)
- Map/location: place suggestions, route planning, trip planning, geocoding
- Vehicle sharing: invite drivers, revoke access
- Energy sharing: invite users to energy sites
- Insurance (China)
- Commerce: cart, payment, accessories
- Referrals + rewards
- Miscellaneous: dashcam save clip, drive note, vehicle rename, screenshot

**Auth Method:** OAuth 2.0 with registered app (client_id + redirect URI required); scopes including `openid`, `offline_access`, vehicle-specific scopes

**Pricing:** Free up to a certain volume; charges per command beyond threshold

**Unique Features:**
- Fleet telemetry streaming (self-hosted)
- Signed vehicle commands (end-to-end encryption)
- VIN-based key enrollment

---

#### 19. timdorr Tesla API (Unofficial Documentation)

**Website:** https://tesla-api.timdorr.com
**Repo:** https://github.com/timdorr/tesla-api
**Type:** Community documentation wiki
**Language:** Documentation (Ruby gem also available)

**Core Value:**
The original reverse-engineered documentation of Tesla's Owner API. Foundation for nearly every Tesla third-party tool.

**Documented Endpoints:**
- Owner API base: `owner-api.teslamotors.com`
- Authentication: `auth.tesla.com`
- Streaming telemetry (up to 0.5s increments)
- Autopark / Summon (WebSocket)
- Vehicle state: door positions, trunk states, sun roof, center display, sentry mode, valet mode, odometer, car version, autopark state, smart summon, speed limit mode, software update progress, TPMS, homelink, calendar support, remote start status, media state

**Vehicle Commands documented:**
- All standard commands (lock, unlock, climate, charging, windows, etc.)
- `take_drivenote` (not implemented by Tesla)
- `set_vehicle_name` (2023.12+)
- `screenshot` (instrument cluster + main display)
- `remote_boombox` (fart sounds, 2022.44.25.1+)

**Unique Features:**
- Documents Easter egg commands (`remote_boombox`, screenshot)
- Documents the vehicle_id vs id disambiguation
- Covers Powerwall endpoints
- Original source that shaped the entire ecosystem

**Status:** Owner API is deprecated for new vehicles; docs partially outdated for Fleet API

---

#### 20. Tesla JSON API (Community Wiki / ownerapi_endpoints.json)

**Repo:** https://github.com/timdorr/tesla-api/blob/master/ownerapi_endpoints.json
**Type:** Machine-readable endpoint catalog

**Value:**
A JSON catalog of every known Tesla mobile app endpoint as of app version 4.13.3. Contains 300+ endpoints spanning vehicle control, energy, service, roadside, financing, insurance (China), safety rating, upgrades, subscriptions, payments, documents, commerce, referrals, and more (fully cataloged in Tier 5 section above).

**Unique Feature:**
The most comprehensive known listing of Tesla's full internal API surface, including many endpoints not covered by the official Fleet API docs (service scheduling, roadside assistance, financing details, Chinese insurance, safety telematics, etc.).

---

## Master Feature Matrix

The following matrix compares all tools across 60+ features. Ratings: ✅ Yes | ⚠️ Partial | ❌ No | — Not applicable

| Feature | tesla-cli | TOST (chrisi51) | enoch85 | WesSec | niklaswa | GewoonJaap | tesla-control | TeslaPy | teslajsonpy | fleet-api-py | TeslaMate | TeslaFi | Tessie | TeslaLogger | tesla_dashcam | ABRP | Stats (iOS) | Watch/Watchla |
|---------|:---------:|:---------------:|:-------:|:------:|:--------:|:----------:|:-------------:|:-------:|:-----------:|:------------:|:---------:|:-------:|:------:|:-----------:|:-------------:|:----:|:-----------:|:-------------:|
| **ORDER TRACKING** |
| Order status (API) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Order details (tasks, timeline) | ✅ | ✅ | ✅ | ❌ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Order watch / polling daemon | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Change detection with history | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Multi-order support | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Financing details | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Delivery appointment details | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Order timeline view | ✅ | ✅ | ✅ | ❌ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Share/anonymize mode | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Configurable poll interval | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| **VEHICLE DATA** |
| Vehicle info / data dump | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ | ✅ |
| GPS location + maps link | ✅ | ❌ | ❌ | ❌ | ⚠️ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | — |
| Charge status (%, range, time) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ | ✅ |
| Climate status | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| Lock status | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | ✅ |
| Software version + updates | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| Odometer | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ | — |
| TPMS tire pressure | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | — | — | — | — |
| Real-time streaming (live) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| VIN decode | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Option codes decode | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | ✅ | — |
| Vehicle list (multi-vehicle) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | — |
| **VEHICLE CONTROL** |
| Wake vehicle | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | — | — | — | — |
| Lock / Unlock | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | — | — | — | ✅ |
| Climate on / off | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | — | — | ✅ | ✅ |
| Set temperature | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | — | — | — | — |
| Seat heaters | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | — | — | — | — |
| Steering wheel heater | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | — | — | — | — |
| Charge start / stop | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | — | — | — | — |
| Set charge limit | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | — | — | — | — |
| Set charging amps | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | — | — | — | — |
| Charge port open / close | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | — | ✅ | ✅ | ✅ |
| Trunk open / close | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | — | — | ✅ | ✅ |
| Frunk open | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | — | — | ✅ | ✅ |
| Windows vent / close | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | — | — | — | — |
| Sentry mode toggle | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | — | — | — | — |
| Valet mode | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Speed limit mode | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Honk horn | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | — | — | — | — |
| Flash lights | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | — | — | — | — |
| Media controls | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Navigation / send address to car | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Software update trigger | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | — | — | — | — |
| Remote start | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | — | — | — | — |
| BLE (Bluetooth) control | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ⚠️ | ❌ | — | — | — | ✅ |
| Scheduled charging | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | — | — | ✅ | — |
| Auto-wake + retry | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | — | — | — | — | — | — | — | — |
| **ANALYTICS / LOGGING** |
| Trip history logging | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | — |
| Charging history log | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | — |
| Battery degradation tracking | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ | — |
| Vampire drain analysis | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ | — |
| Grafana dashboards | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | — | — | — | — |
| Energy cost tracking | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| Geofencing | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | — | ❌ | — | — |
| **DOSSIER / VIN INTELLIGENCE** |
| VIN decode | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| NHTSA recalls integration | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Ship tracking | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Delivery inspection checklist | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Delivery journey gates | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Delivery date estimation | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Snapshot diffing | ✅ | ⚠️ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Historical snapshot archive | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| **NOTIFICATIONS** |
| Any notification support | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ |
| Telegram | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Slack | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Discord | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Email | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Push (ntfy/Pushover) | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Alexa | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| MQTT | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 100+ services (Apprise) | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **AUTH / SECURITY** |
| OAuth2 + PKCE | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | — | — | — | — |
| System keyring storage | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ | — | — | — | — |
| Token encryption at rest | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | ❌ | — | — | — | — |
| Refresh token input | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | — | ✅ | — | — | — | — |
| API key (third-party proxy) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | — | — | — | — |
| End-to-end key enrollment (BLE) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| **OUTPUT / UX** |
| JSON output mode | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | — | ✅ | ✅ | — | ❌ | ❌ | ❌ | ❌ |
| Rich/colored terminal output | ✅ | ✅ | ✅ | ❌ | ✅ | — | ❌ | ❌ | ❌ | ❌ | — | — | — | — | ❌ | — | — | — |
| Web dashboard | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | — |
| Desktop app | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Mobile app | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Apple Watch | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ |
| CSV / spreadsheet export | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ |
| Shell autocomplete | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **INTEGRATIONS** |
| Home Assistant | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| MQTT publisher | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| TeslaMate DB integration | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Tessie proxy support | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | — | ❌ | ❌ | ❌ | ❌ | ❌ |
| ABRP integration | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | — | ❌ | ❌ |
| ScanMyTesla integration | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Alexa skill | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| SmartThings | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| IFTTT | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **MISC / UNIQUE** |
| Anonymize PII flag | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Multi-language UI | ✅ | ⚠️ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Setup wizard | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ | ❌ | — | — | — |
| Config aliases (VIN aliases) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Driver sharing / invitations | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| NHTSA recalls | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Ship tracking | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Delivery inspection checklist | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| RUNT (Colombia registry) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| SIMIT (Colombia traffic fines) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Dashcam video processing | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ⚠️ | ❌ |
| EV route planning | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | ✅ | ❌ | ❌ |
| Automation engine | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | — | — | — | — |
| Cybertruck-specific commands | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — |
| Powerwall / Solar support | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | ✅ | — |

---

## Gap Analysis for tesla-cli

Features present in competing tools that tesla-cli does **not yet** have, prioritized by user value and feasibility.

### Priority 1 — High Value, Low Complexity

These gaps are straightforward to close and frequently requested by users of competing tools:

**1. Set Charge Limit**
Supported by: tesla-control, TeslaPy, teslajsonpy, fleet-api-py, TeslaFi, Tessie
Gap: tesla-cli can start/stop charging but cannot set the % limit target
Add: `tesla charge limit [PERCENT]` + backend `set_charge_limit(vin, percent)` call

**2. Set Temperature (Climate)**
Supported by: tesla-control, TeslaPy, teslajsonpy, fleet-api-py, Tessie
Gap: tesla-cli can turn climate on/off but cannot set target temp
Add: `tesla climate temp CELSIUS` command

**3. Set Charging Amps**
Supported by: tesla-control, fleet-api-py, Tessie
Gap: tesla-cli does not allow adjusting charge current
Add: `tesla charge amps AMPS`

**4. Scheduled Charging / Scheduled Departure**
Supported by: tesla-control, TeslaPy, TeslaFi, Tessie, Stats for Tesla
Gap: tesla-cli cannot schedule when charging begins or set departure time
Add: `tesla charge schedule MINS` and `tesla charge departure HH:MM`

**5. TPMS Tire Pressure**
Supported by: teslajsonpy, python-tesla-fleet-api, Tessie
Gap: tesla-cli `vehicle info` dumps all data but has no dedicated TPMS subcommand
Add: `tesla vehicle tires` for a formatted tire pressure display

**6. Nearby Charging Sites**
Supported by: TeslaPy cli.py (`-n`), tesla-control implicit, Tesla Fleet API
Gap: tesla-cli has no command to find nearby Superchargers/chargers
Add: `tesla charge nearby [--lat LAT --lon LON]`

---

### Priority 2 — High Value, Medium Complexity

**7. CSV/Spreadsheet Export**
Supported by: TeslaFi, Tessie, Stats for Tesla, ABRP
Gap: tesla-cli JSON mode outputs to stdout but has no `--export-csv FILE` flag
Impact: Power users and analysts want to pull data into Excel/Sheets
Add: `--csv` global flag or `tesla teslaMate export trips trips.csv`

**8. Seat Heater Control**
Supported by: tesla-control (per-seat, per-level), teslajsonpy, fleet-api-py, Tessie
Gap: tesla-cli has no seat heater commands
Add: `tesla climate seat POSITION LEVEL` (0-3, positions 0-4)

**9. Steering Wheel Heater**
Supported by: tesla-control, teslajsonpy, fleet-api-py
Add: `tesla climate steering-wheel [on|off]`

**10. Remote Start**
Supported by: tesla-control, TeslaPy, teslajsonpy, TeslaFi, Tessie
Gap: tesla-cli has no `remote_start` command
Add: `tesla security start` (requires passphrase handling per Owner API)

**11. Speed Limit Mode**
Supported by: TeslaPy, fleet-api-py (Owner API)
Gap: Missing from tesla-cli; useful for shared/fleet vehicles
Add: `tesla security speed-limit [on|off] [--limit MPH]`

**12. Valet Mode**
Supported by: tesla-control, TeslaPy
Add: `tesla security valet [on|off] [--pin PIN]`

---

### Priority 3 — Medium Value, Medium Complexity

**13. Battery Degradation Tracking**
Supported by: TeslaMate, TeslaFi, Tessie, TeslaLogger, Stats for Tesla
Gap: tesla-cli logs dossier snapshots but does not compute battery degradation over time
Add: Track `battery_range` and `usable_battery_level` in dossier snapshots; add `tesla dossier battery-health` command that computes estimated degradation from snapshot history

**14. Vampire Drain Analysis**
Supported by: TeslaMate, TeslaFi, Tessie, TeslaLogger
Gap: Not tracked; requires streaming or periodic energy sampling
Feasibility: Can be computed from TeslaMate DB queries if user has TeslaMate; add to `tesla teslaMate` command group

**15. Media Controls**
Supported by: tesla-control (full: volume, track, playback), fleet-api-py
Gap: tesla-cli has a `media_app` registered in app.py but commands not shown in README
Verify actual implementation; if stubs only, complete `tesla media volume/play/next/prev`

**16. Navigation — Send Destination to Car**
Supported by: TeslaPy (`-a`), Fleet API (NAVIGATION_ROUTE, SEND_TO_VEHICLE)
Add: `tesla nav send "ADDRESS"` — sends a navigation destination to the car's screen

**17. HomeLink Trigger**
Supported by: teslajsonpy
Add: `tesla vehicle homelink` — triggers HomeLink garage door when nearby

---

### Priority 4 — Lower Priority / Specialized

**18. Automation Engine / Triggers**
Supported by: Tessie (unique, mature)
Gap: tesla-cli has no event-driven automation
Note: This is a large feature requiring a daemon process model. Could start simple: `tesla order watch` already has event detection — extend with `--on-change-exec "COMMAND"` hook

**19. MQTT Publisher**
Supported by: TeslaMate, TeslaLogger
Gap: tesla-cli does not publish to MQTT
Add: Optional MQTT sink in `tesla stream live` — `tesla stream live --mqtt mqtt://localhost`

**20. Dashcam Clip Save Trigger**
Supported by: Tesla API (`DASHCAM_SAVE_CLIP`)
Add: `tesla vehicle dashcam save` — triggers saving of current dashcam clip

**21. Vehicle Screenshot**
Supported by: timdorr API docs (`TRIGGER_VEHICLE_SCREENSHOT`)
Add: `tesla vehicle screenshot` — captures display screenshot via API

**22. Drive Note**
Supported by: Tesla API (`TAKE_DRIVENOTE`) — noted as "not_supported" but documented
Add: `tesla vehicle note "text"` for when Tesla implements it

**23. Energy Cost Per Charge**
Supported by: TeslaFi, Tessie, TeslaMate
Gap: tesla-cli charging history from TeslaMate shows sessions but not per-kWh cost
Add: Cost configuration per kWh in config + cost display in `tesla teslaMate charging`

**24. Fleet Comparison (Battery Benchmarking)**
Supported by: Stats for Tesla, TeslaLogger
Gap: no fleet-relative battery comparison
Note: Requires external data source or opt-in community data

**25. Cybertruck Tonneau Commands**
Supported by: tesla-control only
Gap: tesla-cli has no Cybertruck-specific commands (tonneau-open/close/stop, autosecure-modelx)
Add as part of a `tesla vehicle cybertruck` subgroup if Cybertruck demand grows

---

## Unique Features (by tool)

Features found in only ONE tool in the ecosystem — prime candidates for evaluation and adoption:

| Feature | Only Tool | Notes |
|---------|-----------|-------|
| RUNT Colombia vehicle registry query | **tesla-cli** | Unique integration for Colombia market |
| SIMIT Colombia traffic fines query | **tesla-cli** | Unique integration for Colombia market |
| NHTSA recalls by model/year + VIN | **tesla-cli** | No other tool fetches government recall data |
| Tesla car-carrier ship tracking | **tesla-cli** | No other tool tracks ships transporting Teslas |
| 34-item delivery inspection checklist | **tesla-cli** | No other tool has an interactive checklist |
| 13-gate delivery journey tracker | **tesla-cli** | No other tool maps the full delivery funnel |
| Community-sourced delivery date estimation | **tesla-cli** | No other tool crowd-sources delivery predictions |
| `tesla dossier diff` — snapshot diffing | **tesla-cli** | TOST has timeline but no structured diff with ±symbols |
| Apprise 100+ notification services | **tesla-cli** | Widest notification channel support of any tool |
| VIN alias system (`tesla config alias`) | **tesla-cli** | No other CLI has named aliases for VINs |
| Setup wizard (interactive onboarding) | **tesla-cli** | No other CLI has a guided wizard |
| TeslaMate PostgreSQL CLI integration | **tesla-cli** | Query TeslaMate DB from terminal without Grafana |
| JavaScript bookmarklet for delivery data extraction | **tesla-cli** | Unique browser-assisted data import workflow |
| Driver invitation management | **tesla-cli** | `tesla sharing invite/list/revoke` |
| SHA-256 verified self-update | **TOST/enoch85** | No other CLI tool verifies update integrity |
| Token encryption at rest (env passphrase) | **enoch85** | Only order tracker with encryped token storage |
| BLE vehicle control (Go SDK) | **tesla-control** | Only CLI with Bluetooth Low Energy support |
| Cybertruck tonneau/autosecure commands | **tesla-control** | Cybertruck-specific control |
| NFC key pairing workflow | **tesla-control** | Key enrollment with physical NFC card |
| End-to-end signed commands (official SDK) | **tesla-control** | Official cryptographic command auth |
| WebSocket real-time streaming (Python) | **TeslaPy** | Event-driven push data (not polling) |
| Powerwall + Solar panel control | **TeslaPy** | Only Python CLI with energy product support |
| Tkinter GUI | **TeslaPy** | Only cross-platform desktop Python GUI |
| Automation engine (triggers + conditions) | **Tessie** | No other tool has IF/THEN automation logic |
| 200+ OBD real-time data points | **Tessie** | Widest OBD data surface of any consumer tool |
| Self-Driving / FSD statistics | **Tessie** | Unique tracking of FSD engagement/stats |
| ScanMyTesla cell-level battery data | **TeslaLogger** | Only logger with cell voltage/temp integration |
| Supercharger invoice auto-download | **TeslaLogger** | Automates invoice retrieval |
| ABRP integration (credential-free) | **TeslaLogger** | No credential sharing required |
| 11-language localization | **TeslaLogger** | Widest i18n of any self-hosted tool |
| Lucid Air support | **TeslaLogger** | Only Tesla logger supporting non-Tesla EVs |
| GPU-accelerated dashcam processing | **tesla_dashcam** | CUDA/Intel/VAAPI acceleration |
| USB drive auto-trigger for dashcam | **tesla_dashcam** | Monitor mode for automatic processing |
| Multi-stop EV route optimization | **ABRP** | No other tool plans optimized charging stops |
| Live telemetry route adaptation | **ABRP** | Adjusts route plan based on real SOC during trip |
| Battery fleet benchmarking (vs similar cars) | **Stats for Tesla** | Only tool with community degradation comparison |
| One-time purchase pricing | **Stats for Tesla** | No subscription in subscription-heavy ecosystem |
| Solar generation widget | **Stats for Tesla** | Only mobile app with dedicated solar widget |
| BLE Apple Watch key (offline) | **Watchla** | Apple Watch as BLE key without internet |
| Lifetime driving map (visited places) | **TeslaMate** | Visualizes every location ever visited |
| 20 pre-built Grafana dashboards | **TeslaMate** | Most comprehensive visual analytics |
| Zero vampire drain architecture | **TeslaMate** | Only tool explicitly designed for zero drain |

---

*Document generated by comprehensive research across 20 tools, 40+ web fetches, and direct source code inspection. Last updated: 2026-03-30.*
