# Tesla CLI

[![CI](https://github.com/dacrypt/tesla/actions/workflows/ci.yml/badge.svg)](https://github.com/dacrypt/tesla/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Control your Tesla and track your order from the terminal.

```
tesla order status       → check your order status
tesla order watch -i 5   → monitor changes every 5 min + Telegram notifications
tesla vehicle info       → vehicle data
tesla vehicle lock       → lock doors
```

---

## Installation

```bash
git clone https://github.com/dacrypt/tesla.git
cd tesla
uv tool install -e .
```

This installs the `tesla` command globally. Works from any directory.

Verify:

```bash
tesla --version
tesla config show
```

### Requirements

- macOS, Linux, or Windows (macOS recommended — uses Keychain for tokens)
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) as package manager

---

## Quick Start

Configure your VIN and order number:

```bash
tesla config set default-vin YOUR_VIN_HERE
tesla config set reservation-number RNXXXXXXXXX
```

Config is stored at `~/.tesla-cli/config.toml`.
Tokens are stored in the system keyring (macOS Keychain / Linux Secret Service) — **never in plain text files**.

---

## 1. Order Tracking

### Authenticate

```bash
tesla config auth order
```

Two options:

**Option 1 — Browser (OAuth2 + PKCE):**

1. Browser opens, you log in with your Tesla account
2. Tesla redirects to a blank page
3. Copy the full URL (`https://auth.tesla.com/void/callback?code=...`)
4. Paste it in the terminal

**Option 2 — Refresh token:**

1. If you already have a refresh token (from TeslaMate, Tessie, browser DevTools, etc.)
2. Paste it directly

### Check status

```bash
tesla order status
```

Shows: status, VIN, model, country, configuration options, delivery window.

### Full details

```bash
tesla order details
```

Shows everything: status + pending tasks + vehicle info + delivery + financing + trade-in + registration.

### JSON mode

```bash
tesla -j order status                     # raw JSON
tesla -j order status | jq .raw           # raw API response only
tesla -j order status | jq .raw.mktOptions  # option codes
```

### Monitor changes

```bash
tesla order watch              # every 10 min (default)
tesla order watch -i 5         # every 5 min
tesla order watch --no-notify  # without notifications
```

Runs continuously and notifies you when any field changes. `Ctrl+C` to stop.

Run in background (survives terminal close):

```bash
nohup tesla order watch -i 5 > /dev/null 2>&1 &
```

---

## 2. Notifications

Tesla CLI uses [Apprise](https://github.com/caronc/apprise) for notifications. Supports 100+ services: Telegram, Slack, Discord, Email, ntfy, Pushover, etc.

### Configure

```bash
tesla config set notifications-enabled true
```

Then edit `~/.tesla-cli/config.toml`:

```toml
[notifications]
enabled = true
apprise_urls = [
    "tgram://BOT_TOKEN/CHAT_ID",        # Telegram
]
```

### Supported services (examples)

| Service | URL format |
|---------|-----------|
| **Telegram** | `tgram://BOT_TOKEN/CHAT_ID` |
| **Slack** | `slack://TokenA/TokenB/TokenC/#channel` |
| **Discord** | `discord://webhook_id/webhook_token` |
| **Email (Gmail)** | `mailto://user:app_password@gmail.com` |
| **ntfy.sh** | `ntfy://my-tesla` |
| **Pushover** | `pover://user_key@app_token` |

[Full list of 100+ services](https://github.com/caronc/apprise/wiki)

---

## 3. Vehicle Control

### Available backends

| Backend | Pros | Cons |
|---------|------|------|
| **Tessie** (recommended) | Easy setup, stable API, auto-wake | Third-party service, monthly cost |
| **Fleet API** | Direct with Tesla, free* | Complex setup, requires registered app |

*Fleet API is free up to a certain volume; then charges per request.

### Option A: Tessie (recommended)

1. Create account at [tessie.com](https://tessie.com) and link your Tesla
2. Go to [my.tessie.com/settings/api](https://my.tessie.com/settings/api) and copy your token
3. Configure:

```bash
tesla config auth tessie
# Paste your token when prompted
```

### Option B: Fleet API direct

1. Register app at [developer.tesla.com](https://developer.tesla.com)
2. Configure:

```bash
tesla config set client-id YOUR_CLIENT_ID
tesla config auth fleet
# Browser opens for OAuth
```

### Commands

```bash
# Information
tesla vehicle list             # list all your Teslas
tesla vehicle info             # full vehicle data
tesla vehicle location         # GPS + Google Maps link

# Charging
tesla charge status            # state: %, range, time remaining
tesla charge start             # start charging
tesla charge stop              # stop charging

# Climate
tesla climate status           # inside/outside temperature
tesla climate on               # turn on AC/heating
tesla climate off              # turn off

# Security
tesla security lock            # lock doors
tesla security unlock          # unlock doors

# Other
tesla vehicle horn             # honk horn
tesla vehicle flash            # flash lights
tesla vehicle wake             # wake vehicle
tesla security trunk rear      # open trunk
tesla security trunk front     # open frunk
```

> If the car is asleep, commands wake it automatically (with retries).

### Multi-vehicle

```bash
# Create aliases
tesla config alias modely YOUR_VIN_HERE
tesla config alias model3 OTHER_VIN_HERE

# Use aliases
tesla vehicle info --vin modely
tesla charge status --vin model3

# Change default
tesla config set default-vin OTHER_VIN_HERE
```

---

## 4. Vehicle Dossier

The dossier is a complete vehicle file that aggregates data from **all available sources**:

- Tesla Owner API (order, account, features)
- VIN decode (built-in, works with any country's VINs)
- NHTSA recalls (free US government API)
- Ship tracking (ships transporting Teslas)
- Historical archive (JSON snapshots)

### Build / update dossier

```bash
tesla dossier build
```

Queries all sources, decodes VIN and option codes, searches recalls, tracks ships, and saves a historical snapshot. Each run accumulates history.

### View saved dossier (without querying APIs)

```bash
tesla dossier show
tesla -j dossier show              # full JSON
tesla -j dossier show | jq .specs  # specs only
```

### Decode VIN

```bash
tesla dossier vin                       # your configured VIN
tesla dossier vin 5YJ3E1EA8PF123456    # any Tesla VIN
```

### View Tesla ships

```bash
tesla dossier ships
```

Shows car-carrier ships transporting Teslas with links to MarineTraffic for real-time tracking.

### View snapshot history

```bash
tesla dossier history
```

Each `tesla dossier build` saves a timestamped snapshot. Compare changes over time.

### Dossier structure

```
~/.tesla-cli/dossier/
├── dossier.json                    # Current dossier (master)
└── snapshots/
    ├── snapshot_20260324_141132.json  # Historical snapshot #1
    ├── snapshot_20260325_090000.json  # Historical snapshot #2
    └── ...
```

### Dossier sections

| Section | Contents |
|---------|----------|
| **Identity** | VIN decoded position by position, manufacturer, plant, serial |
| **Specs** | Model, variant, generation, battery, range, motor, power, weight, dimensions |
| **Option Codes** | Each code decoded with category and description |
| **Order Timeline** | Current status + history of all status changes |
| **Logistics** | Factory, departure port, arrival port, carrier ship, tracking URL |
| **Recalls** | Active NHTSA recalls with component, description, and remedy |
| **Software** | OTA version history (once vehicle is delivered) |
| **Service** | Service and maintenance history |
| **Financial** | Price, taxes, payment method, financing |
| **Account** | Tesla profile, enabled features, vault UUID |
| **Raw Snapshots** | Raw API responses from each source for future reference |

---

## 5. JSON mode

All commands support `-j` / `--json` for script integration:

```bash
tesla -j order status
tesla -j charge status
tesla -j vehicle location

# Combine with jq
tesla -j order status | jq .raw.mktOptions
tesla -j charge status | jq .battery_level
tesla -j vehicle location | jq .maps_url

# Save snapshot
tesla -j order status > ~/tesla-order-$(date +%Y%m%d).json
```

---

## Configuration Reference

### `tesla config set` keys

| Key | Description | Values |
|-----|-------------|--------|
| `default-vin` | Default vehicle VIN | `YOUR_VIN_HERE` |
| `backend` | Vehicle backend | `tessie`, `fleet` |
| `reservation-number` | Order number | `RNXXXXXXXXX` |
| `region` | Fleet API region | `na`, `eu`, `cn` |
| `client-id` | Fleet API client ID | (your app ID) |
| `notifications-enabled` | Enable notifications | `true`, `false` |

### Files

| File | Contents |
|------|----------|
| `~/.tesla-cli/config.toml` | General configuration |
| `~/.tesla-cli/state/last_order.json` | Last known state (for change detection) |
| `~/.tesla-cli/dossier/dossier.json` | Complete vehicle dossier |
| `~/.tesla-cli/dossier/snapshots/` | Historical snapshots (cumulative) |
| System Keyring | Authentication tokens (access + refresh) |

### Stored tokens

| Token | Keychain key | Purpose |
|-------|-------------|---------|
| Order access | `tesla-cli.order.access_token` | Order API |
| Order refresh | `tesla-cli.order.refresh_token` | Renew access token |
| Tessie | `tesla-cli.tessie.token` | Tessie API |
| Fleet access | `tesla-cli.fleet.access_token` | Fleet API |
| Fleet refresh | `tesla-cli.fleet.refresh_token` | Renew Fleet token |

---

## Architecture

```
src/tesla_cli/
├── app.py                # Entry point. Registers commands with Typer
├── config.py             # Config manager (~/.tesla-cli/config.toml)
├── output.py             # Rendering: Rich tables + JSON mode
├── exceptions.py         # Custom errors (AuthenticationError, ApiError, etc.)
│
├── auth/                 # Authentication
│   ├── oauth.py          # Tesla OAuth2 + PKCE (browser flow + refresh token)
│   ├── tokens.py         # Keyring storage (macOS Keychain / Linux Secret Service)
│   └── tessie.py         # Tessie token helper
│
├── backends/             # API access layer
│   ├── base.py           # ABC VehicleBackend (abstract interface)
│   ├── fleet.py          # Tesla Fleet API direct (NA/EU/CN)
│   ├── tessie.py         # Tessie as Fleet API proxy
│   ├── order.py          # Order tracking (reverse-engineered endpoints)
│   └── dossier.py        # Dossier aggregator (NHTSA, ships, VIN decode, archive)
│
├── commands/             # CLI commands (Typer)
│   ├── config_cmd.py     # tesla config show/set/alias/auth
│   ├── order.py          # tesla order status/details/watch
│   ├── vehicle.py        # tesla vehicle info/wake/...
│   ├── charge.py         # tesla charge status/start/stop
│   ├── climate.py        # tesla climate status/on/off
│   ├── security.py       # tesla security lock/unlock/trunk
│   ├── dossier.py        # tesla dossier build/show/vin/ships/history
│   └── stream.py         # tesla stream (real-time telemetry)
│
└── models/               # Data models (Pydantic)
    ├── order.py          # OrderStatus, OrderTask, OrderDetails, OrderChange
    ├── vehicle.py        # VehicleSummary, VehicleData
    ├── charge.py         # ChargeState
    ├── climate.py        # ClimateState
    ├── drive.py          # DriveState, Location
    └── dossier.py        # VehicleDossier (master model, 15+ sub-models)
```

### Data flow

```
User → CLI (Typer) → Command → Backend → Tesla API
                                   ↓
                            Auth (OAuth/Keyring)
                                   ↓
                            Model (Pydantic)
                                   ↓
                            Output (Rich/JSON)
```

### APIs used

| API | Base URL | Auth | Purpose |
|-----|----------|------|---------|
| **Owner API** (unofficial) | `owner-api.teslamotors.com` | OAuth2 Bearer | Orders, profile |
| **Tasks API** (unofficial) | `akamai-apigateway-vfx.tesla.com` | OAuth2 Bearer | Order tasks/milestones |
| **Fleet API** (official) | `fleet-api.prd.na.vn.cloud.tesla.com` | OAuth2 Bearer | Vehicle control |
| **Tessie API** (third-party) | `api.tessie.com` | API Key | Fleet API proxy |
| **Tesla Auth** | `auth.tesla.com` | OAuth2 + PKCE | Authentication |
| **NHTSA vPIC** (government) | `vpic.nhtsa.dot.gov/api` | None (free) | VIN decode, recalls |
| **NHTSA Recalls** | `api.nhtsa.gov` | None (free) | Recalls by model/year |
| **Ship Tracking** | `shipinfo.net` | None | Tesla ship positions |

---

## Development

```bash
git clone https://github.com/dacrypt/tesla.git
cd tesla

# Install dev dependencies
uv sync --extra dev

# Lint
uv run ruff check src/
uv run ruff format --check src/

# Tests (unit only, no real API calls)
uv run pytest -m "not integration"

# All tests including integration (requires credentials)
uv run pytest

# Reinstall globally after changes
uv tool install -e .
```

### Adding a new command

1. Create the model in `models/` (Pydantic BaseModel)
2. Add the logic in `backends/` (API calls)
3. Create the command in `commands/` (function with `@app.command()`)
4. Register the sub-app in `app.py`

### Adding a new notification service

Just add the Apprise URL to `~/.tesla-cli/config.toml`. No code changes needed.
[Apprise URL reference](https://github.com/caronc/apprise/wiki)

---

## Roadmap

- [x] `tesla dossier build` — Complete vehicle dossier
- [x] `tesla dossier vin` — Decode VIN position by position
- [x] `tesla dossier ships` — Tesla ship tracking
- [x] NHTSA recalls integration
- [x] Historical snapshots archive
- [x] Telegram notifications
- [ ] `tesla stream` — Real-time telemetry (WebSocket)
- [ ] `tesla vehicle sentry` — View Sentry Mode events
- [ ] `tesla vehicle trips` — Trip history
- [ ] `tesla dossier diff` — Compare two snapshots
- [ ] Shell autocompletion (bash/zsh/fish)
- [ ] TeslaMate integration for post-delivery data

---

## License

MIT — see [LICENSE](LICENSE)
