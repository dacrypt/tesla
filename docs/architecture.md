# Architecture

> tesla-cli v4.5.2 — Clean Architecture + Monorepo + Managed TeslaMate Stack

---

## Directory Layout

```
src/tesla_cli/
├── app.py                # Entry point — registers all Typer sub-apps
├── config.py             # Pydantic-Settings config model (~/.tesla-cli/config.toml)
├── output.py             # Rich rendering + JSON mode + --anon anonymizer
├── i18n.py               # Lightweight i18n: t(key) — en/es/pt/fr/de/it
├── exceptions.py         # AuthenticationError, ApiError, BackendError, etc.
│
├── core/
│   ├── auth/             # OAuth2 + keyring token storage
│   │   ├── oauth.py      # Tesla OAuth2 + PKCE (browser flow + refresh token)
│   │   ├── tokens.py     # Keyring storage (macOS Keychain / Linux Secret Service)
│   │   ├── encryption.py # AES-256-GCM token encryption for headless servers
│   │   ├── tessie.py     # Tessie token helper
│   │   └── browser_login.py  # Headless browser login (patchright)
│   │
│   ├── backends/         # Raw API access layer
│   │   ├── base.py       # ABC VehicleBackend (abstract interface)
│   │   ├── owner.py      # Tesla Owner API (auto-wake + retry)
│   │   ├── fleet.py      # Tesla Fleet API direct (NA/EU/CN, 62 commands)
│   │   ├── tessie.py     # Tessie as Fleet API proxy
│   │   ├── order.py      # Order tracking (reverse-engineered endpoints)
│   │   ├── dossier.py    # Dossier aggregator (NHTSA, ships, VIN decode, 140+ option codes)
│   │   ├── teslaMate.py  # TeslaMate PostgreSQL read-only backend
│   │   ├── runt.py       # Colombia vehicle registry (RUNT)
│   │   └── simit.py      # Colombia fines system (SIMIT)
│   │
│   ├── models/           # Pydantic data models
│   │   ├── vehicle.py    # VehicleState, ChargeState, ClimateState, DriveState
│   │   ├── charge.py     # ChargingSession, ChargingForecast
│   │   ├── climate.py    # ClimateState
│   │   ├── drive.py      # DriveState
│   │   ├── order.py      # OrderStatus, OrderDetails, OrderTask, OrderChange
│   │   └── dossier.py    # VehicleDossier, VinDecode, OptionCodes, Recall
│   │
│   ├── providers/        # Provider registry (7 providers, 4 layers)
│   │   ├── base.py       # Capability enum + ProviderBase ABC
│   │   ├── registry.py   # ProviderRegistry: .for_capability(), .fanout()
│   │   ├── loader.py     # build_registry(cfg) factory
│   │   └── impl/         # Provider implementations
│   │       ├── ble.py          # L0: BLE local commands via tesla-control
│   │       ├── vehicle_api.py  # L1: Owner/Fleet/Tessie wrapper
│   │       ├── teslaMate.py    # L2: TeslaMate DB analytics
│   │       ├── abrp.py         # L3: ABRP live telemetry push
│   │       ├── ha.py           # L3: Home Assistant state sync
│   │       ├── apprise_notify.py  # L3: Notifications (100+ channels)
│   │       └── mqtt.py         # L3: MQTT publish + HA discovery
│   │
│   └── sources.py        # Data source registry (15 sources, TTL cache, change detection)
│
├── cli/                  # Typer CLI commands
│   ├── commands/
│   │   ├── config_cmd.py # tesla config show/set/alias/auth/validate/migrate
│   │   ├── setup.py      # tesla setup — onboarding wizard
│   │   ├── order.py      # tesla order status/details/watch
│   │   ├── vehicle.py    # tesla vehicle info/bio/health-check/watch/sentry/...
│   │   ├── charge.py     # tesla charge status/start/stop/profile/forecast/...
│   │   ├── climate.py    # tesla climate status/on/off/set-temp/seat/...
│   │   ├── security.py   # tesla security lock/unlock/trunk
│   │   ├── dossier.py    # tesla dossier build/show/vin/diff/checklist/gates/export
│   │   ├── stream.py     # tesla stream live (real-time Rich dashboard)
│   │   ├── notify.py     # tesla notify list/add/remove/test/set-template
│   │   ├── teslaMate.py  # tesla teslaMate connect/status/trips/charging/...
│   │   ├── mqtt_cmd.py   # tesla mqtt setup/status/test/publish/ha-discovery
│   │   └── serve_cmd.py  # tesla serve (launches FastAPI server)
│   └── output.py         # Rich table rendering + JSON mode
│
├── api/                  # FastAPI REST API + web dashboard
│   ├── app.py            # App factory, SSE stream, metrics, config validate
│   ├── routes/
│   │   ├── vehicle.py    # /api/vehicle/* (multi-VIN via ?vin=)
│   │   ├── charge.py     # /api/charge/*
│   │   ├── climate.py    # /api/climate/*
│   │   ├── order.py      # /api/order/*
│   │   └── teslaMate.py  # /api/teslaMate/*
│   └── ui_dist/          # Built React app (served as static)
│
├── infra/                # Infrastructure orchestration
│   └── teslamate_stack.py  # Docker Compose lifecycle for TeslaMate
│
ui/                       # React frontend (separate directory)
├── src/
│   ├── pages/            # Dashboard, Dossier, Analytics, Settings
│   ├── components/       # BatteryGauge, ModelYSilhouette, StatusBadge
│   ├── hooks/            # useDossierData, useVehicleData (SSE)
│   └── api/              # HTTP client for /api/*
└── vite.config.ts        # Vite + proxy to FastAPI in dev
```

---

## Provider Architecture

The provider registry decouples capability routing from command logic. Each provider declares what it can do; the registry routes requests to the best available source.

```
Layer  Provider          Capabilities
-----  --------          ------------
L0     BLE               Local Bluetooth commands (proximity required)
L1     VehicleAPI        Full vehicle control + data (Owner/Fleet/Tessie)
L2     TeslaMate         Trip analytics, charge history, timeline, heatmap
L3     ABRP              Live route telemetry push
L3     HomeAssistant     Home sync push (18 sensor entities)
L3     Apprise           Notifications (100+ channels)
L3     MQTT              Telemetry publish + HA discovery (15 sensors)
```

- `registry.for_capability(cap)` returns the highest-priority available provider
- `registry.fanout(data)` broadcasts to all push-type providers (MQTT + HA + ABRP + Apprise)
- Providers are instantiated by `build_registry(cfg)` based on config

---

## Data Flow

```
User → CLI (Typer) → Command → Provider Registry → Backend → Tesla API
                                      ↓
                               Auth (OAuth2 / Keyring)
                                      ↓
                               Model (Pydantic)
                                      ↓
                               Output (Rich / JSON)
```

For the REST API:

```
HTTP Request → FastAPI Router → Backend → Tesla API
                    ↓
              SSE Stream → Browser (EventSource)
                    ↓
              Prometheus /api/metrics → Grafana
```

---

## Backend Selection

| Backend | Auth | Cost | Limitations |
|---------|------|------|-------------|
| **Owner API** | Tesla OAuth2 token | Free | Vehicle endpoints blocked for modern VINs (LRW/7SA/XP7 → HTTP 412). Order + user endpoints still work. |
| **Fleet API** | App OAuth2 + virtual key | Free* | Requires developer.tesla.com registration + public domain for key hosting |
| **Tessie** | API token from dashboard | ~$13/month | Third-party proxy; adds caching + battery health + drive paths |

*Fleet API is free up to a volume threshold.

The Owner API remains the primary mechanism for order tracking (`/api/1/users/orders`). For vehicle control post-delivery, Fleet API or Tessie is required for newer VINs.

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Provider registry over direct backend calls | Decouples capability routing from command logic; makes fanout (MQTT+HA+ABRP) trivial |
| Keyring for all tokens | Prevents credentials in plain-text files or env vars leaking to shell history |
| Apprise for notifications | Single dependency covers 100+ services; no per-service code |
| PostgreSQL read-only for TeslaMate | No risk of corrupting user's TeslaMate data; psycopg2 is the only extra dep |
| Pydantic models everywhere | Validates API responses at boundary; catches Tesla API changes early |
| `core/` layer is framework-independent | Backends, models, providers have zero knowledge of CLI or API framework |
| React + Ionic for dashboard | Mobile-first UI; SSE for real-time updates; built and served as static by FastAPI |
| Managed TeslaMate stack (Docker Compose) | Eliminates manual PostgreSQL + Grafana setup; one-command install |

---

## Testing Patterns

- **Version assertions**: `packaging.version.Version(x) >= Version("X.Y.Z")` — never exact equality — survives version bumps
- **SSE routes**: test with source-code analysis (`assert "event: battery" in src`) rather than `TestClient.stream()`, which hangs on infinite generators
- **TeslaMate tests**: patch `tesla_cli.commands.teslaMate._backend` to return a mock
- **Vehicle tests**: patch `tesla_cli.commands.vehicle.get_vehicle_backend` at the module boundary
- **HTTP mocking**: `pytest-httpx` for all external API calls
- **No real API calls** in unit suite — all patched; integration tests marked with `@pytest.mark.integration`

---

## APIs Used

| API | Base URL | Auth | Purpose |
|-----|----------|------|---------|
| **Owner API** (unofficial) | `owner-api.teslamotors.com` | OAuth2 Bearer | Orders, profile |
| **Tasks API** (unofficial) | `akamai-apigateway-vfx.tesla.com` | OAuth2 Bearer | Order tasks/milestones |
| **Fleet API** (official) | `fleet-api.prd.{region}.vn.cloud.tesla.com` | OAuth2 Bearer | Vehicle control (62 commands) |
| **Tessie API** (third-party) | `api.tessie.com` | API Key | Fleet API proxy |
| **Tesla Auth** | `auth.tesla.com` | OAuth2 + PKCE | Authentication |
| **NHTSA vPIC** (government) | `vpic.nhtsa.dot.gov/api` | None | VIN decode, recalls |
| **Ship Tracking** | `shipinfo.net` | None | Tesla ship positions |
| **TeslaMate DB** (self-hosted) | PostgreSQL | Connection string | Trip history, charging, OTA |
| **OpenQuery** | Various | None | RUNT, SIMIT, Fasecolda, NHTSA |
