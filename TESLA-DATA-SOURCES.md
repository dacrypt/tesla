# Tesla Data Sources: Complete Ecosystem Map

> Last updated: 2026-04-02
> Version: tesla-cli v4.0.0 (Clean Architecture + Monorepo + TeslaMate Managed Stack)
> Scope: All known Tesla APIs, portals, third-party services, and external data sources
> Purpose: DEFINITIVE reference — what data exists, where, how we get it, what is our status

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Tesla Portals and Websites](#2-tesla-portals-and-websites)
3. [Tesla APIs (Official)](#3-tesla-apis-official)
4. [Tesla APIs (Unofficial / Reverse-Engineered)](#4-tesla-apis-unofficial--reverse-engineered)
5. [Third-Party Services](#5-third-party-services)
6. [Authentication Methods](#6-authentication-methods)
7. [Our Registered Data Sources (15 Sources)](#7-our-registered-data-sources-15-sources)
8. [OpenQuery External Sources](#8-openquery-external-sources)
9. [Codebase Implementation Status](#9-codebase-implementation-status)
10. [What We Currently Access](#10-what-we-currently-access)
11. [What We Are Missing](#11-what-we-are-missing)
12. [Competitor Data Sources (Intelligence)](#12-competitor-data-sources-intelligence)
13. [Gaps and Opportunities](#13-gaps-and-opportunities)
14. [Discovery Log (2026-04-02)](#14-discovery-log-2026-04-02)

---

## 1. Architecture Overview

Tesla data lives in multiple disconnected systems. No single API gives you everything. The ecosystem breaks into:

```
                      +----------------------------+
                      |   Tesla Account (Owner)    |
                      +----------------------------+
                               |
          +--------------------+---------------------+
          |                    |                      |
   Owner API (legacy)    Fleet API (official)   Portal SSR (web)
   owner-api.tesla       fleet-api.prd.*        tesla.com/teslaaccount
   motors.com            vn.cloud.tesla.com
          |                    |                      |
   Orders, /users/me     Vehicle data,          Full order detail,
   (STILL WORKS)         commands, energy,       delivery, documents,
                         telemetry streaming     financing, registration
          |                    |
          |              +-----+------+
          |              |            |
          |         REST API    Fleet Telemetry
          |         (polling)   (WebSocket streaming)
          |
   +------+-------+--------+
   |              |         |
  Tessie       TeslaMate   TeslaFi
  (proxy)      (self-host)  (SaaS)
                  |
          +-------+-------+
          |       |       |
        MQTT   Grafana  PostgreSQL
```

### Our Provider Architecture (v2.5.0+)

```
Layer  Provider          Capabilities                           Status
-----  --------          ------------                           ------
L0     BLE               Local Bluetooth commands               CONFIG EXISTS, tesla-control wrapper
L1     VehicleAPI        Full vehicle control + data            IMPLEMENTED (Owner/Fleet/Tessie)
L2     TeslaMate         Trip analytics, charge history         IMPLEMENTED (PostgreSQL + managed stack)
L3     ABRP              Live route telemetry push              IMPLEMENTED
L3     HomeAssistant     Home sync push (18 sensors)            IMPLEMENTED
L3     Apprise           Notifications (100+ channels)          IMPLEMENTED
L3     MQTT              Telemetry publish + HA discovery       IMPLEMENTED
```

---

## 2. Tesla Portals and Websites

### A. tesla.com/teslaaccount (Ownership Portal)

**URL**: `https://www.tesla.com/teslaaccount`
**Auth**: Web session cookies (email + password + MFA)
**Technology**: Next.js SSR, data in `window.Tesla.App.*` and `window.__NEXT_DATA__`
**Anti-bot**: hCaptcha blocks automated access when client_id=ownership

| Section | Data Available |
|---------|---------------|
| Order Details | Order status, substatus, VIN, config, mkt options, country |
| Delivery | Appointment date/time, location, address, duration, disclaimer |
| Documents | MVPA, window sticker, finance contract, registration docs |
| Financing | Loan/lease status, monthly payment, term, lender |
| Registration | Registration status, plate, state/province |
| Trade-In | Trade-in vehicle details, offer amount |
| Vehicle Config | Model, trim, exterior color, interior, wheels, FSD |
| Tasks/Steps | Order milestones (insurance, payment, registration, delivery) |

**Key data paths** (from `window.Tesla.App`):
- `DeliveryDetails` -- appointment, timing, pickup location
- `OrderDetails` -- full order record
- `UserInfo` -- account holder info
- `Documents` -- downloadable document links
- `__NEXT_DATA__.props.pageProps` -- server-rendered page data

### B. Portal URLs (Discovered 2026-04-02)

| URL Pattern | Data |
|-------------|------|
| `/teslaaccount/order/{RN}` | Order overview page |
| `/teslaaccount/order/{RN}/manage` | Manage Order: model, trim, color, wheels, interior, autopilot package |
| `/teslaaccount/order/{RN}/documents/{id}` | Individual document download |

**Documents available** (7 confirmed for RN126460939):
1. Order Agreement
2. Final Invoice
3. Identification Form
4. Vehicle Manifest
5. Registration Application
6. Registration Power of Attorney
7. Motor Vehicle Purchase Agreement

### C. Tesla App (Mobile)

**Auth**: OAuth2 tokens (same as Fleet API or Owner API)
**Unique data not in REST API**:
- Supercharging session history + invoices (Account > Charging > History)
- Service appointment scheduling and history
- Referral credits and rewards
- Wall Connector management
- Premium Connectivity subscription status
- Loot Box / gamification features
- Push notification preferences

### D. developer.tesla.com (Developer Portal)

**URL**: `https://developer.tesla.com`
**Purpose**: App registration, API key management, scope configuration
**Capabilities**: Create/manage apps, configure OAuth scopes, register partner accounts, generate partner tokens, manage virtual key pairing, view API usage and quotas

### E. Tesla for Business

**URL**: Fleet management portal for business accounts
**Purpose**: Third-party business token authorization, fleet management

---

## 3. Tesla APIs (Official)

### A. Fleet API (Current Official API)

**Base URLs**:
- NA: `https://fleet-api.prd.na.vn.cloud.tesla.com`
- EU: `https://fleet-api.prd.eu.vn.cloud.tesla.com`
- CN: `https://fleet-api.prd.cn.vn.cloud.tesla.cn`

**Auth**: OAuth2 Bearer tokens (third-party or partner)
**Documentation**: https://developer.tesla.com/docs/fleet-api

#### OAuth Scopes

| Scope | Purpose |
|-------|---------|
| `openid` | Required for OpenID Connect |
| `offline_access` | Get refresh tokens (valid 3 months) |
| `user_data` | Account info |
| `vehicle_device_data` | Read vehicle telemetry and state |
| `vehicle_cmds` | Send vehicle commands (lock, climate, etc.) |
| `vehicle_charging_cmds` | Charging control (start/stop, set limit, amps) |
| `energy_device_data` | Powerwall/solar data |
| `energy_cmds` | Control energy products |

#### Vehicle Endpoints (Scope: `vehicle_device_data`)

| Method | Endpoint | Description | Our Status |
|--------|----------|-------------|------------|
| GET | `/api/1/vehicles` | List vehicles (paginated, 100/page) | IMPLEMENTED |
| GET | `/api/1/vehicles/{id_or_vin}/vehicle_data` | Full vehicle state blob | IMPLEMENTED |
| GET | `/api/1/vehicles/{id}/mobile_enabled` | Mobile access enabled check | IMPLEMENTED |
| GET | `/api/1/vehicles/{id}/nearby_charging_sites` | Superchargers + destination chargers | IMPLEMENTED |
| GET | `/api/1/vehicles/{id}/release_notes` | OTA firmware release notes | IMPLEMENTED |
| GET | `/api/1/vehicles/{id}/service_data` | Service/maintenance data | IMPLEMENTED |
| GET | `/api/1/vehicles/{id}/recent_alerts` | Recent vehicle fault alerts | IMPLEMENTED |
| GET | `/api/1/vehicles/charge_history` | Lifetime charging history | IMPLEMENTED |
| GET | `/api/1/vehicles/{id}/fleet_status` | Fleet registration status | IMPLEMENTED |
| GET | `/api/1/vehicles/{id}/fleet_telemetry_config` | Current telemetry configuration | NOT IMPLEMENTED |
| GET | `/api/1/vehicles/{id}/invitations` | Driver sharing invitations | IMPLEMENTED |
| POST | `/api/1/vehicles/{id}/invitations` | Create driver invitation | IMPLEMENTED |
| POST | `/api/1/vehicles/{id}/invitations/{inv_id}/revoke` | Revoke invitation | IMPLEMENTED |

#### vehicle_data Sub-Endpoints (query param `endpoints=`)

| Endpoint Name | Fields Include |
|---------------|----------------|
| `charge_state` | battery_level, battery_range, charge_rate, charge_limit_soc, charger_voltage, charger_actual_current, charging_state, time_to_full_charge, charge_port_door_open, charge_port_latch, scheduled_charging_mode, scheduled_charging_start_time, charge_energy_added, charge_miles_added_rated, charge_miles_added_ideal |
| `climate_state` | inside_temp, outside_temp, driver_temp_setting, passenger_temp_setting, is_auto_conditioning_on, is_climate_on, fan_status, seat_heater_*, steering_wheel_heater, cabin_overheat_protection, climate_keeper_mode, bioweapon_mode |
| `drive_state` | latitude, longitude, heading, speed, power, shift_state, gps_as_of, timestamp |
| `location_data` | Detailed GPS (required for firmware 2023.38+) |
| `vehicle_state` | odometer, firmware_version, locked, sentry_mode, fd_window, fp_window, rd_window, rp_window, ft (frunk), rt (trunk), valet_mode, speed_limit_mode, software_update, tpms_pressure_*, homelink_nearby, media_state |
| `vehicle_config` | car_type, trim_badging, exterior_color, wheel_type, roof_color, spoiler_type, plg (has_ludicrous), perf_config, can_actuate_trunks, motorized_charge_port, has_seat_cooling, has_air_suspension |

#### Vehicle Commands (62 commands implemented in FleetBackend)

| Category | Commands |
|----------|----------|
| **Wake** | `wake_up` |
| **Doors** | `door_lock`, `door_unlock` |
| **Charging** | `charge_start`, `charge_stop`, `set_charge_limit`, `set_charging_amps`, `charge_port_door_open`, `charge_port_door_close`, `set_scheduled_charging`, `set_scheduled_departure` |
| **Climate** | `auto_conditioning_start`, `auto_conditioning_stop`, `set_temps`, `remote_seat_heater_request`, `remote_steering_wheel_heater_request`, `set_preconditioning_max`, `set_bioweapon_mode`, `set_climate_keeper_mode`, `set_cop_temp` |
| **Windows** | `window_control` (vent/close) |
| **Trunk** | `actuate_trunk` (front/rear) |
| **Horn/Lights** | `honk_horn`, `flash_lights` |
| **Sentry** | `set_sentry_mode` |
| **Valet** | `set_valet_mode`, `reset_valet_pin` |
| **Speed Limit** | `speed_limit_activate`, `speed_limit_deactivate`, `speed_limit_set_limit`, `speed_limit_clear_pin` |
| **PIN to Drive** | `set_pin_to_drive` |
| **Guest Mode** | `guest_mode` |
| **Remote Start** | `remote_start_drive` |
| **Navigation** | `share`, `navigation_sc_request`, `navigation_gps_request` |
| **Media** | `media_toggle_playback`, `media_next_track`, `media_prev_track`, `media_next_fav`, `media_prev_fav`, `media_volume_up`, `media_volume_down`, `adjust_volume` |
| **Software** | `schedule_software_update`, `cancel_software_update` |
| **HomeLink** | `trigger_homelink` |
| **Boombox** | `remote_boombox` |

#### Energy Endpoints (Scope: `energy_device_data` / `energy_cmds`)

| Method | Endpoint | Description | Our Status |
|--------|----------|-------------|------------|
| GET | `/api/1/energy_sites/{id}/site_info` | Site info (solar, Powerwall) | NOT IMPLEMENTED |
| GET | `/api/1/energy_sites/{id}/live_status` | Real-time power flow | NOT IMPLEMENTED |
| GET | `/api/1/energy_sites/{id}/calendar_history` | Historical energy data | NOT IMPLEMENTED |
| GET | `/api/1/energy_sites/{id}/telemetry_history` | Wall Connector charging history | NOT IMPLEMENTED |
| POST | `/api/1/energy_sites/{id}/operation` | Set mode | NOT IMPLEMENTED |
| POST | `/api/1/energy_sites/{id}/backup` | Set backup reserve % | NOT IMPLEMENTED |
| POST | `/api/1/energy_sites/{id}/storm_mode` | Storm mode toggle | NOT IMPLEMENTED |

#### User Endpoints (Scope: `user_data`)

| Method | Endpoint | Description | Our Status |
|--------|----------|-------------|------------|
| GET | `/api/1/users/me` | Account holder info | WORKS (Owner API) |
| GET | `/api/1/users/orders` | All orders for the account | WORKS (Owner API) |
| GET | `/api/1/users/feature_config` | Feature flags/config | NOT IMPLEMENTED |

#### Partner Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/1/partner_accounts` | Register partner / pair virtual key |
| GET | `/api/1/partner_accounts/public_key` | Get partner public key |

### B. Fleet Telemetry (Streaming API)

**Repo**: https://github.com/teslamotors/fleet-telemetry
**Protocol**: WebSocket over TLS with mutual certificate auth
**Data Format**: Protocol Buffers (protobuf), optional JSON
**Firmware Requirement**: 2023.20.6+
**Our Status**: NOT IMPLEMENTED (requires infrastructure: FQDN, TLS, Go server)

#### Architecture

```
Vehicle --> WebSocket/TLS --> Fleet Telemetry Server --> Dispatcher --> Backend
                                                        (Kafka, Kinesis,
                                                         Pub/Sub, ZMQ,
                                                         MQTT, Logger)
```

#### Record Types

| Type | Description |
|------|-------------|
| V (Vehicle Data) | Configurable telemetry fields, transmit on-change |
| Alerts | System warnings, fault codes |
| Connectivity | Vehicle online/offline state events |

#### Streamable Signal Categories

- **Battery**: SoC, range, voltage, current, power, cell temps, degradation
- **Charging**: Charger type, voltage, current, energy added, charge rate
- **Climate**: Cabin temp, outside temp, HVAC state, seat heater levels
- **Drive**: Speed, power, heading, elevation, odometer
- **Location**: Latitude, longitude, GPS accuracy
- **Vehicle State**: Lock status, doors, windows, trunk, sentry mode
- **Tire Pressure**: All four tires (TPMS)
- **Software**: Firmware version, update status

#### Configuration Endpoint

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/1/vehicles/{vin}/fleet_telemetry_config` | Configure telemetry streaming |
| GET | `/api/1/vehicles/{vin}/fleet_telemetry_config` | Get current config |
| DELETE | `/api/1/vehicles/{vin}/fleet_telemetry_config` | Remove telemetry config |

---

## 4. Tesla APIs (Unofficial / Reverse-Engineered)

### A. Owner API (Deprecated but Partially Working)

**Base URL**: `https://owner-api.teslamotors.com`
**Auth**: OAuth2 Bearer tokens (client_id: `ownerapi`)
**Status**: Officially deprecated Jan 2024. Vehicle endpoints blocked for newer VINs. User-level endpoints still work.

| Method | Endpoint | Status | Description |
|--------|----------|--------|-------------|
| GET | `/api/1/users/orders` | **WORKS** | Order list (primary order tracking mechanism) |
| GET | `/api/1/users/me` | **WORKS** | Account holder info |
| GET | `/api/1/vehicles` | BLOCKED (412) | Vehicle list -- "use fleetapi" |
| GET | `/api/1/vehicles/{id}/vehicle_data` | BLOCKED (412) | Modern VINs (LRW/7SA/XP7) |
| POST | `/api/1/vehicles/{id}/command/*` | BLOCKED | Unsigned commands rejected |

**Key finding**: `/api/1/users/orders` and `/api/1/users/me` STILL WORK with ownerapi tokens. This is our primary order tracking mechanism.

### B. Tasks API (Mobile App Backend)

**Base URL**: `https://akamai-apigateway-vfx.tesla.com`
**Auth**: Same OAuth2 Bearer token
**Status**: Returns 403/503 for all endpoints as of 2026-04-02 (Akamai gateway blocking)
**Source**: Reverse-engineered from Tesla mobile app

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tasks?referenceNumber={RN}&deviceLanguage=en&deviceCountry=US&appVersion=4.40.0` | Order tasks/milestones |

Returns structured task data: taskType (Insurance, Payment, Registration, Delivery, TradeIn), taskStatus (Complete, InProgress, NotStarted), taskName, completed, active.

### C. Streaming API (Legacy)

**URL**: `wss://streaming.vn.teslamotors.com/streaming/`
**Status**: Deprecated in favor of Fleet Telemetry
**Used by**: TeslaMate (still uses this for real-time position polling)

---

## 5. Third-Party Services

### A. Tessie

**API Base**: `https://api.tessie.com`
**Auth**: Single Bearer token (from Tessie dashboard)
**Pricing**: $12.99/month, $129.99/year, $299.99 lifetime
**Our Status**: TessieBackend IMPLEMENTED (vehicle_state, commands, nearby_sites)

#### Unique Data Beyond Raw Tesla API

- Automatic wake handling (no sleep/wake management)
- Historical data storage (drives, charges, idles)
- Battery health tracking and measurements over time
- Driving path recording (GPS traces)
- Firmware alert history
- Consumption calculations (Tesla API does not return trip consumption)
- Weather data at vehicle location
- Map image generation
- Supercharging invoices (all vehicles)
- 200+ real-time OBD-style data points
- Automation engine (triggers + conditions + actions)
- FSD / Self-Driving stats tracking

#### Key Endpoints (Beyond Standard Tesla)

| Method | Endpoint | Description | Our Status |
|--------|----------|-------------|------------|
| GET | `/{vin}/state` | Full vehicle state (cached, no wake) | IMPLEMENTED |
| GET | `/{vin}/status` | Online/offline/asleep status | IMPLEMENTED |
| GET | `/{vin}/location` | Location + street address | IMPLEMENTED |
| GET | `/{vin}/battery_health` | Battery degradation data | NOT IMPLEMENTED |
| GET | `/{vin}/battery_health_measurements` | Historical battery health | NOT IMPLEMENTED |
| GET | `/{vin}/charges` | Charging session history | NOT IMPLEMENTED |
| GET | `/{vin}/drives` | Drive history | NOT IMPLEMENTED |
| GET | `/{vin}/driving_path` | GPS trace during timeframe | NOT IMPLEMENTED |
| GET | `/{vin}/consumption` | Consumption since last charge | NOT IMPLEMENTED |
| GET | `/{vin}/firmware_alerts` | Firmware-generated alerts | NOT IMPLEMENTED |
| GET | `/{vin}/historical_states` | Historical state snapshots | NOT IMPLEMENTED |
| GET | `/{vin}/idles` | Idle/parked sessions | NOT IMPLEMENTED |
| GET | `/{vin}/map` | Map image of vehicle location | NOT IMPLEMENTED |
| GET | `/{vin}/tire_pressure` | Tire pressure (bar) | NOT IMPLEMENTED |
| GET | `/{vin}/weather` | Weather forecast at location | NOT IMPLEMENTED |
| GET | `/{vin}/nearby_charging_sites` | Nearby chargers | IMPLEMENTED |
| GET | `/charging_invoices` | Supercharging invoices (all vehicles) | NOT IMPLEMENTED |

### B. TeslaMate (Self-Hosted)

**Repo**: https://github.com/teslamate-org/teslamate
**Stars**: 7.8k
**Tech Stack**: Elixir + PostgreSQL + Grafana
**Our Status**: FULLY INTEGRATED (managed Docker stack in v4.0.0)

#### v4.0.0 Managed Stack

- 7 CLI commands: `install`, `start`, `stop`, `restart`, `update`, `logs`, `uninstall`
- Auto-provisioning on server startup
- Credentials stored in system keyring, Tesla tokens forwarded to container
- Settings page in React app with container status, action buttons, log viewer
- 6 API endpoints: `stack/status`, `stack/start`, `stack/stop`, `stack/restart`, `stack/update`, `stack/logs`

#### Data Recorded

| Data Type | What It Records |
|-----------|-----------------|
| Drives | Start/end time, distance, duration, addresses, range, energy used |
| Charges | Start/end time, energy added, cost, location, battery level |
| Updates | OTA firmware version history with timestamps |
| Positions | Continuous GPS position logging |
| States | Vehicle state transitions (online, asleep, driving, charging) |
| Addresses | Reverse-geocoded location names |
| Geofences | Custom named zones |

#### Derived/Calculated Data (Not From Tesla API)

- Consumption estimates (from range loss during drives)
- Vampire drain (range loss while parked)
- Efficiency (Wh/km and kWh/100mi per trip)
- Battery degradation (tracked over time from full charge readings)
- Monthly/yearly reports (aggregated driving and charging stats)
- Top locations (most visited places)
- Charging costs (user-entered cost per kWh)

#### Database Schema (Key Tables)

`cars`, `drives`, `charging_processes`, `positions`, `updates`, `addresses`, `geofences`, `settings`

#### Our TeslaMate REST Surface (v2.6.0+)

| Endpoint | Description |
|----------|-------------|
| `GET /api/teslaMate/trips` | Recent trips |
| `GET /api/teslaMate/charges` | Recent charging sessions |
| `GET /api/teslaMate/stats` | Lifetime driving + charging stats |
| `GET /api/teslaMate/efficiency` | Per-trip energy efficiency |
| `GET /api/teslaMate/heatmap` | GitHub-style calendar of driving days |
| `GET /api/teslaMate/vampire` | Vampire drain analysis |
| `GET /api/teslaMate/daily-energy` | Daily kWh added chart |
| `GET /api/teslaMate/report/{month}` | Monthly driving + charging summary |
| `GET /api/teslaMate/timeline` | Unified event timeline |
| `GET /api/teslaMate/cost-report` | Monthly cost breakdown |
| `GET /api/teslaMate/trip-stats` | Trip summary + top routes |
| `GET /api/teslaMate/charging-locations` | Top charging locations |

### C. TeslaFi (SaaS)

**URL**: https://www.teslafi.com
**Price**: $7.99/month or $79.99/year
**Our Status**: NOT INTEGRATED (competitor reference only)

Unique features we do not replicate: Amazon Alexa skill, SmartThings integration, 100+ configurable data columns, fleet-wide firmware monitoring ("Software Tracker"), weather data per drive.

### D. TeslaLogger

**Repo**: https://github.com/bassmaster187/TeslaLogger
**Stars**: 607
**Our Status**: NOT INTEGRATED (competitor reference only)

Unique features: ScanMyTesla integration (cell-level battery data), automatic Supercharger invoice download, Lucid Air support, 11-language localization.

### E. Teslemetry

**URL**: https://teslemetry.com
**Purpose**: Hosted Fleet Telemetry server (eliminates need to self-host WebSocket server)
**Our Status**: NOT INTEGRATED (potential alternative to self-hosting fleet-telemetry)

### F. A Better Route Planner (ABRP)

**Our Status**: FULLY INTEGRATED (`tesla abrp send/stream/status/setup`)
**Data consumed**: SoC, location, speed, outside temp, elevation
**Data provided back**: Route planning with charging stops, range prediction

### G. Stats for Tesla (iOS)

**Price**: $49.99 one-time
**Our Status**: NOT INTEGRATED (competitor reference only)

Unique features we could learn from: battery fleet benchmarking (compare degradation vs other Teslas), charge scheduling (stop at specified time for TOU plans), climate scheduling, smart battery prep, dash-cam footage viewer, Dynamic Island charging info.

---

## 6. Authentication Methods

### Token Type Matrix

| Token Type | Client ID | How to Get | What It Accesses | Expiry |
|------------|-----------|------------|------------------|--------|
| Owner API token | `ownerapi` | OAuth2 PKCE via auth.tesla.com | Orders, /users/me | 8 hours |
| Fleet API 3rd-party token | App-specific | OAuth2 PKCE + user consent | Vehicle data, commands, energy (per scope) | 8 hours |
| Fleet API partner token | App-specific | Client credentials grant | Partner account management | 8 hours |
| Tessie token | N/A | Generated in Tessie dashboard | All Tessie endpoints | Long-lived |
| Web session cookie | N/A | Browser login to tesla.com | Portal SSR data | Session |
| Refresh token | Same as access | Returned with access token | Exchange for new access token | 3 months |

### Our Authentication Chain (4 Levels)

| Level | Method | Token Stored As | Used By |
|-------|--------|-----------------|---------|
| L1 | Email+password via patchright headless browser | `order-access-token`, `order-refresh-token` | OrderBackend, OwnerApiVehicleBackend |
| L2 | OAuth PKCE popup with void/callback (Fleet API client_id) | `fleet-access-token`, `fleet-refresh-token` | FleetBackend |
| L3 | Tessie token paste from dashboard | `tessie-token` | TessieBackend |
| L4 | CLI `tesla config auth fleet` (full developer registration) | `fleet-access-token` + `fleet-client-secret` | FleetBackend (signed commands) |

**Additional tokens** (TeslaMate managed stack):
- `teslamate-db-password` -- TeslaMateBackend DB connection
- `teslamate-grafana-password` -- Grafana access
- `teslamate-encryption-key` -- TeslaMate encryption

### Key Discoveries (2026-04-02)

- **hCaptcha blocks automated access** to ownership portal (client_id=ownership)
- **Fleet API client_id bypasses captcha** for OAuth login flow
- **MFA uses 6 separate input boxes** (codeBox1-6, type=tel) -- not a single field
- **TeslaMate token injection** via Ecto RPC is possible for managed stack

### OAuth Flow (Fleet API)

```
1. Generate PKCE code_verifier + code_challenge (SHA-256)
2. Redirect user to:
   https://auth.tesla.com/oauth2/v3/authorize
     ?client_id={app_client_id}
     &redirect_uri=https://auth.tesla.com/void/callback
     &response_type=code
     &scope={scopes}
     &state={random_state}
     &code_challenge={challenge}
     &code_challenge_method=S256
3. User logs in (email + password + MFA)
4. Tesla redirects to void/callback?code={code}&state={state}
5. Exchange code for tokens:
   POST https://auth.tesla.com/oauth2/v3/token
     grant_type=authorization_code
     client_id={app_client_id}
     code={code}
     code_verifier={verifier}
     redirect_uri=https://auth.tesla.com/void/callback
```

### Vehicle Command Protocol (Required for Firmware 2024.26+)

1. Register app on developer.tesla.com
2. Generate EC keypair (secp256r1)
3. Host public key at `https://{domain}/.well-known/appspecific/com.tesla.3p.public-key.pem`
4. Call `/api/1/partner_accounts` to register and auto-pair virtual key
5. User approves virtual key on vehicle touchscreen
6. Commands signed with private key before sending
7. Alternative: `tesla-http-proxy` signs commands automatically
8. Alternative: `tesla-control` for BLE direct local command signing

---

## 7. Our Registered Data Sources (15 Sources)

These are the 15 sources registered in `src/tesla_cli/core/sources.py` via `_register_defaults()`:

| # | Source ID | Name | Category | Country | Auth | Method | TTL |
|---|-----------|------|----------|---------|------|--------|-----|
| 1 | `tesla.portal` | Tesla Portal -- Orden Completa | financiero | -- | order | Browser scrape (patchright) | 1h |
| 2 | `tesla.order` | Tesla Order | financiero | -- | order | Owner API `/users/orders` | 30m |
| 3 | `vin.decode` | VIN Decode | vehiculo | -- | none | NHTSA vPIC API | 30d |
| 4 | `co.runt` | RUNT -- Registro Vehicular | registro | CO | none | Playwright (openquery, by VIN) | 1h |
| 5 | `co.runt_soat` | RUNT -- SOAT | registro | CO | none | Playwright (openquery, by placa) | 1h |
| 6 | `co.runt_rtm` | RUNT -- Tecnico-Mecanica | registro | CO | none | Playwright (openquery, by placa) | 1h |
| 7 | `co.runt_conductor` | RUNT -- Conductor | registro | CO | none | Playwright (openquery, by cedula) | 24h |
| 8 | `co.simit` | SIMIT -- Multas de Transito | infracciones | CO | none | Playwright (openquery, by cedula) | 1h |
| 9 | `co.pico_y_placa` | Pico y Placa | servicios | CO | none | API (openquery, by placa) | 12h |
| 10 | `co.estaciones_ev` | Electrolineras | servicios | CO | none | datos.gov.co REST API | 24h |
| 11 | `co.recalls` | SIC -- Recalls | seguridad | CO | none | Playwright (openquery) | 24h |
| 12 | `co.fasecolda` | Fasecolda -- Valor Comercial | financiero | CO | none | Playwright (openquery) | 7d |
| 13 | `us.nhtsa_recalls` | NHTSA Recalls | seguridad | US | none | API (openquery) | 24h |
| 14 | `us.nhtsa_vin` | NHTSA VIN Decode | vehiculo | US | none | API (openquery, by VIN) | 30d |
| 15 | `intl.ship_tracking` | Ship Tracking | servicios | -- | none | Playwright (openquery) | 1h |

### Source Categories

- **financiero** (3): tesla.portal, tesla.order, co.fasecolda
- **vehiculo** (2): vin.decode, us.nhtsa_vin
- **registro** (4): co.runt, co.runt_soat, co.runt_rtm, co.runt_conductor
- **infracciones** (1): co.simit
- **seguridad** (2): co.recalls, us.nhtsa_recalls
- **servicios** (3): co.pico_y_placa, co.estaciones_ev, intl.ship_tracking

### Source Infrastructure

- **Cache**: `~/.tesla-cli/sources/{source_id}.json`
- **History**: `~/.tesla-cli/source_history/{source_id}.jsonl` (append-only log with data hashes)
- **Audits**: `~/.tesla-cli/source_audits/{source_id}_{timestamp}.pdf` (Playwright screenshots/PDFs)
- **Change detection**: Automatic field-level diff on every refresh
- **Subprocess isolation**: Playwright sources run as subprocesses to avoid uvicorn conflicts

---

## 8. OpenQuery External Sources

Our sources leverage the `openquery` library which provides 100+ sources across multiple countries:

### Available by Region

| Region | Sources | Examples |
|--------|---------|---------|
| CO (Colombia) | 20+ | runt, simit, pico_y_placa, estaciones_ev, recalls, fasecolda, transito, impuestos |
| US | 10+ | nhtsa_recalls, nhtsa_vin, epa_fuel_economy, carfax_free |
| INTL | 5+ | ship_tracking, ev_database |
| AR (Argentina) | 5+ | dnrpa, infracciones |
| CL (Chile) | 5+ | registro_civil, multas |
| EC (Ecuador) | 3+ | ant, sri |
| MX (Mexico) | 5+ | repuve, tenencia |
| PE (Peru) | 3+ | sunarp, sat |

### Key Sources for Tesla Owners

| Source | What It Provides | Our Status |
|--------|-----------------|------------|
| `co.runt` | Vehicle registration, owner, plate, brand, model, year | REGISTERED |
| `co.simit` | Traffic fines/tickets against cedula | REGISTERED |
| `co.pico_y_placa` | Driving restriction schedule by plate | REGISTERED |
| `co.estaciones_ev` | EV charging station locations | REGISTERED |
| `co.recalls` | SIC vehicle recalls (Colombia) | REGISTERED |
| `co.fasecolda` | Commercial vehicle value (insurance reference) | REGISTERED |
| `us.nhtsa_recalls` | NHTSA recalls by make/model/year | REGISTERED |
| `us.nhtsa_vin` | Full VIN decode (NHTSA government API) | REGISTERED |
| `us.epa_fuel_economy` | EPA fuel economy / range data | AVAILABLE (not registered) |
| `intl.ship_tracking` | Tesla ship positions (Grand Venus etc.) | REGISTERED |

---

## 9. Codebase Implementation Status

### Current Version: v4.0.0 (2026-04-01)

| Component | Status | Details |
|-----------|--------|---------|
| Clean architecture | SHIPPED | core/, cli/, api/, infra/ layers |
| React frontend (monorepo) | SHIPPED | ui/ directory, Vite proxy, `tesla serve --build-ui` |
| TeslaMate managed stack | SHIPPED | 7 CLI commands, 6 API endpoints, settings UI |
| Provider registry | SHIPPED | 7 providers, 4 layers, capability routing |
| REST API server | SHIPPED | FastAPI + uvicorn, SSE stream, Prometheus metrics |
| MQTT integration | SHIPPED | HA auto-discovery, 15 sensors |
| BLE control | SHIPPED | `tesla-control` wrapper, 8 commands |
| ABRP integration | SHIPPED | Send/stream/status/setup |
| Home Assistant | SHIPPED | 18 sensor entities pushed |
| Geofencing | SHIPPED | Add/list/remove/watch with Apprise alerts |
| Multi-vehicle | SHIPPED | VIN switcher, aliases, `watch --all` |
| 1132 tests | PASSING | Unit + integration, ruff clean |

### Backend Classes

| Class | File | Methods |
|-------|------|---------|
| `FleetBackend` | `core/backends/fleet.py` | 62 methods (list_vehicles, get_vehicle_data, 6 state endpoints, 50+ commands, sharing) |
| `OrderBackend` | `core/backends/order.py` | get_orders, get_order_status, get_order_tasks, get_order_details, detect_changes, get_delivery_appointment, import_delivery_data |
| `OwnerApiVehicleBackend` | `core/backends/owner.py` | Vehicle data + commands (limited to older VINs) |
| `TessieBackend` | `core/backends/tessie.py` | vehicle_state, service_data, nearby_sites, commands |
| `TeslaMateBacked` | `core/backends/teslaMate.py` | trips, charges, updates, stats, efficiency, vampire, timeline, daily_energy, drive_days, cost_report, trip_stats, charging_locations, energy_report |
| `DossierBackend` | `core/backends/dossier.py` | VIN decode, NHTSA recalls, ship tracking, 140+ option codes |

### CLI Command Count (v3.4.0+)

100+ commands across 14 command groups: config, setup, order, vehicle, charge, climate, security, dossier, stream, notify, teslaMate, mqtt, serve, providers, abrp, ble, ha, geofence.

---

## 10. What We Currently Access

### Token Storage (keyring-based)

| Key | Source | Used By |
|-----|--------|---------|
| `order-access-token` | Owner API OAuth (client_id=ownerapi) | OrderBackend, OwnerApiVehicleBackend |
| `order-refresh-token` | Owner API OAuth | Token refresh |
| `fleet-access-token` | Fleet API OAuth (app client_id) | FleetBackend |
| `fleet-refresh-token` | Fleet API OAuth | Token refresh |
| `tessie-token` | Tessie dashboard (paste) | TessieBackend |
| `fleet-client-secret` | developer.tesla.com | Stored, used for partner registration |
| `teslamate-db-password` | TeslaMate stack install | TeslaMateBackend DB connection |
| `teslamate-grafana-password` | TeslaMate stack install | Grafana access |
| `teslamate-encryption-key` | TeslaMate stack install | TeslaMate encryption |

### Data Flow Diagram (Current)

```
Order Tracking:
  owner-api.teslamotors.com/api/1/users/orders --> OrderBackend --> tesla.order source
  akamai-apigateway-vfx.tesla.com/tasks --> OrderBackend.get_order_tasks() [BLOCKED as of 2026-04-02]

Portal Scrape:
  tesla.com/teslaaccount/order/{RN} --> portal_scrape.py (patchright headless)
    --> window.Tesla.App.DeliveryDetails --> tesla.portal source
    --> hCaptcha blocks client_id=ownership; Fleet API client_id bypasses

Vehicle Data (post-delivery):
  fleet-api.prd.na.vn.cloud.tesla.com --> FleetBackend --> all vehicle_data + 62 commands
  OR api.tessie.com --> TessieBackend --> cached vehicle state + commands
  OR owner-api.teslamotors.com --> OwnerApiVehicleBackend --> (BLOCKED for modern VINs)

Historical Data:
  TeslaMate PostgreSQL --> TeslaMateBacked --> trips, charges, updates, efficiency, timeline
  TeslaMate managed via Docker Compose --> infra/ layer --> install/start/stop/restart/update

External Sources:
  openquery library --> 15 registered sources --> RUNT, SIMIT, NHTSA, Fasecolda, ship tracking
  datos.gov.co API --> co.estaciones_ev (EV charging stations)
  NHTSA vPIC API --> vin.decode (direct, no openquery)

Push Sinks:
  Vehicle state --> ABRP (SoC, speed, power, GPS)
  Vehicle state --> Home Assistant (18 sensor entities)
  Vehicle state --> MQTT broker (per-key topics + HA discovery)
  Change events --> Apprise (100+ notification channels)
```

---

## 11. What We Are Missing

### A. Data We Could Access But Do Not

| Data | Source | Blocked By | Priority |
|------|--------|------------|----------|
| **Supercharging invoices** | Tessie `/charging_invoices` | Not implemented | Medium |
| **Battery health over time** | Tessie `/battery_health_measurements` | Not implemented | High |
| **Drive GPS paths** | Tessie `/{vin}/driving_path` | Not implemented | Medium |
| **Firmware alerts (Tessie)** | Tessie `/{vin}/firmware_alerts` | Not implemented | Medium |
| **Tire pressure history** | Tessie `/{vin}/tire_pressure` | Not implemented | Low |
| **Weather at vehicle** | Tessie `/{vin}/weather` | Not implemented | Low |
| **Consumption data** | Tessie `/{vin}/consumption` | Not implemented | Medium |
| **Fleet Telemetry streaming** | Fleet Telemetry server | Requires infrastructure (FQDN, TLS) | High |
| **Energy site data** | Fleet API `/energy_sites/*` | No energy products registered | N/A |
| **Feature config** | Fleet API `/users/feature_config` | Not implemented | Low |
| **Fleet telemetry config** | Fleet API `fleet_telemetry_config` | Not implemented | Medium |
| **EPA fuel economy** | openquery `us.epa_fuel_economy` | Not registered as source | Low |

### B. Data That Requires Portal Scraping (No API)

| Data | Where It Lives | Why No API |
|------|---------------|-----------|
| Delivery appointment details | window.Tesla.App.DeliveryDetails | Tesla never exposed via REST |
| Purchase documents (7 types) | tesla.com/teslaaccount/order/{RN}/documents/{id} | Web-only download links |
| Finance contract details | tesla.com/teslaaccount Documents tab | Web-only |
| Registration workflow state | window.Tesla.App.OrderDetails | Not in order API response |
| Manage Order config (model/trim/color/wheels) | tesla.com/teslaaccount/order/{RN}/manage | Portal SSR only |
| Service appointment history | Tesla mobile app only | No known API endpoint |
| Supercharging session invoices | Tesla mobile app Account > Charging | Tessie has this |
| Referral credits | Tesla mobile app Account | No known API endpoint |

### C. VIN Blocking Issue (HTTP 412)

Modern VINs (prefixes LRW, 7SA, XP7) receive HTTP 412 from the Owner API for vehicle data/command endpoints. Error says "use Fleet API".

**Impact**: Cannot use `OwnerApiVehicleBackend` for vehicle data on Model Y (VIN: 7SAYGDEF*). Must use Fleet API or Tessie.

**Workaround**: Owner API `/api/1/users/orders` and `/api/1/users/me` are user-level endpoints and still work regardless of VIN.

---

## 12. Competitor Data Sources (Intelligence)

Data sources used by competitors that reveal capabilities we should consider:

### From TeslaMate (7.8k stars)
- 20 Grafana dashboards (we expose 12 REST endpoints from same DB)
- MQTT broker publishing (we have MqttProvider)
- Geo-fencing with custom location labeling (we have geofence commands)
- Import from TeslaFi and tesla-apiscraper (we do not have import)

### From TeslaFi
- Amazon Alexa skill for voice queries
- SmartThings integration
- 100+ configurable data columns (layout editor)
- Fleet-wide firmware monitoring ("Software Tracker")
- Weather data per drive
- Monthly calendar activity view

### From Tessie
- Automation engine (triggers + conditions + actions)
- 200+ OBD-style data points
- FSD / Self-Driving stats tracking
- Insurance data access via API
- Drop-in Fleet API proxy (developer API)
- Sentry Mode automations

### From TeslaLogger
- ScanMyTesla integration (cell-level battery data)
- Automatic Supercharger invoice download
- ABRP integration without credential sharing

### From Stats for Tesla (iOS)
- Battery fleet benchmarking (compare vs other Teslas)
- Charge scheduling (stop at specified time for TOU)
- Climate scheduling (on at configured days/times)
- Smart battery prep (warm up on schedule)
- Dynamic Island charging info
- Siri Shortcuts integration

### From tesla-control (Official Go SDK)
- BLE encrypted local communication (we wrap via `tesla-control` binary)
- Cybertruck-specific commands (tonneau, autosecure)
- NFC card key pairing workflow
- `state CATEGORY` -- fetch vehicle state over BLE
- `body-controller-state` -- limited state over BLE

### From TOST (Order Tracker)
- SHA-256 verified self-update mechanism
- Markdown export for Discord/chat
- Cross-platform desktop app packaging

---

## 13. Gaps and Opportunities

### High Priority

1. **Fleet Telemetry Integration**
   - Real-time streaming eliminates polling (no vampire drain from API calls)
   - Requires: FQDN, TLS cert, fleet-telemetry Go server deployment
   - Alternative: Use Teslemetry.com as hosted Fleet Telemetry (no infra needed)
   - Sub-second data for location tracking, energy monitoring

2. **Battery Health Source**
   - Add Tessie `battery_health_measurements` as a data source
   - Track degradation over time (important for EV resale value)
   - TeslaMate also calculates this from charge data (we already expose via dossier battery-health)

3. **Charge History Unification**
   - Fleet API `charge_history` + TeslaMate `charging_processes` + Tessie `charges`
   - Combine into a unified charging history with cost tracking

4. **Portal Document Download**
   - 7 documents available at `/teslaaccount/order/{RN}/documents/{id}`
   - Requires authenticated browser session (patchright)
   - Could archive MVPA, invoice, registration docs locally

### Medium Priority

5. **Supercharging Invoice Tracking**
   - Tessie `/charging_invoices` provides this
   - Useful for expense tracking and tax documentation

6. **Drive Path Recording**
   - Tessie `driving_path` gives GPS traces
   - Could build heatmaps, route analysis

7. **Portal Scrape Reliability**
   - hCaptcha blocks client_id=ownership
   - Fleet API client_id bypasses captcha for OAuth (discovered 2026-04-02)
   - Could implement session cookie caching for periodic refresh

8. **Automation Engine**
   - Tessie has triggers + conditions + actions
   - We have `order watch --on-change-exec` as a primitive version
   - Could generalize to vehicle state change automations

### Lower Priority

9. **Energy Site Integration**
   - Fleet API energy endpoints exist but require Powerwall/Solar
   - Not applicable until user has energy products

10. **TeslaFi / TeslaMate Data Import**
    - TeslaMate supports import from TeslaFi
    - TeslaLogger supports import from both
    - Could add `tesla teslaMate import` from CSV/JSON

11. **Alexa / Siri Integration**
    - TeslaFi has Alexa skill, Stats has Siri Shortcuts
    - Low priority but high "cool factor"

### Architecture Recommendations

| Current Gap | Recommended Solution |
|-------------|---------------------|
| No real-time streaming | Deploy fleet-telemetry OR use Teslemetry.com |
| Portal data requires manual login | Fleet API client_id bypasses captcha; implement session caching |
| Battery health not tracked over time | Add Tessie battery_health source + TeslaMate degradation calc |
| No unified charging history | Merge Fleet charge_history + TeslaMate + Tessie into single view |
| Commands blocked on Owner API | Already using Fleet API; ensure virtual key is paired |
| Tasks API blocked (Akamai 403/503) | Monitor; use portal scrape as fallback for milestones |
| 7 portal documents not archived | Implement patchright download + local storage |

---

## 14. Discovery Log (2026-04-02)

### Portal URL Structure

```
/teslaaccount/order/{RN}                    -- Order overview
/teslaaccount/order/{RN}/manage             -- Vehicle config (model, trim, color, wheels, interior, autopilot)
/teslaaccount/order/{RN}/documents/{id}     -- Individual document download
```

### Documents Found (RN126460939)

1. Order Agreement
2. Final Invoice
3. Identification Form
4. Vehicle Manifest
5. Registration Application
6. Registration Power of Attorney
7. Motor Vehicle Purchase Agreement

### Authentication Findings

- **hCaptcha**: Blocks automated access to ownership portal when `client_id=ownership`
- **Fleet API client_id**: Bypasses captcha for OAuth login flow
- **Owner API**: `/users/orders` and `/users/me` still work with ownerapi tokens
- **Akamai gateway**: Tasks API (`akamai-apigateway-vfx.tesla.com`) returns 403/503 for all endpoints
- **MFA input**: 6 separate `<input>` boxes (codeBox1 through codeBox6, type=tel)
- **TeslaMate token injection**: Possible via Ecto RPC for managed stack

---

## Appendix: External References

- [Tesla Fleet API Docs](https://developer.tesla.com/docs/fleet-api)
- [Fleet Telemetry Server (GitHub)](https://github.com/teslamotors/fleet-telemetry)
- [Vehicle Command Protocol (GitHub)](https://github.com/teslamotors/vehicle-command)
- [Tessie Developer API](https://developer.tessie.com)
- [TeslaMate (GitHub)](https://github.com/teslamate-org/teslamate)
- [TeslaMate Fleet API Config](https://docs.teslamate.org/docs/configuration/api/)
- [Community API Docs (timdorr)](https://github.com/timdorr/tesla-api)
- [TeslaPy (Python)](https://github.com/tdorssers/TeslaPy)
- [python-tesla-fleet-api (Teslemetry)](https://github.com/Teslemetry/python-tesla-fleet-api)
- [Teslemetry](https://teslemetry.com)
- [TeslaFi](https://www.teslafi.com)
- [Stats for Tesla (iOS)](https://apps.apple.com/us/app/stats-for-your-tesla/id1191100729)
- [TeslaLogger (GitHub)](https://github.com/bassmaster187/TeslaLogger)
- [tesla_dashcam (GitHub)](https://github.com/ehendrix23/tesla_dashcam)
- [ABRP](https://abetterrouteplanner.com)
- [TOST Order Tracker](https://github.com/chrisi51/tesla-order-status)
- [Tesla API Postman Collection](https://documenter.getpostman.com/view/781424/2s9YRCWB4f)
