# Tesla Data Sources: Complete Ecosystem Map

> Last updated: 2026-04-01
> Scope: All known Tesla APIs, portals, and third-party services

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Tesla Portals & Websites](#2-tesla-portals--websites)
3. [Tesla APIs (Official)](#3-tesla-apis-official)
4. [Tesla APIs (Unofficial / Reverse-Engineered)](#4-tesla-apis-unofficial--reverse-engineered)
5. [Third-Party Services](#5-third-party-services)
6. [Authentication Methods](#6-authentication-methods)
7. [What We Currently Access](#7-what-we-currently-access)
8. [What We Are Missing](#8-what-we-are-missing)
9. [Gaps & Opportunities](#9-gaps--opportunities)

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
   Orders, basic         Vehicle data,          Full order detail,
   vehicle list          commands, energy,       delivery, documents,
   (deprecated)          telemetry streaming     financing, registration
          |                    |
          |              +-----+------+
          |              |            |
          |         REST API    Fleet Telemetry
          |         (polling)   (WebSocket streaming)
          |
   +------+-------+
   |              |
  Tessie       TeslaMate       TeslaFi
  (proxy)      (self-hosted)   (SaaS)
```

---

## 2. Tesla Portals & Websites

### A. tesla.com/teslaaccount (Ownership Portal)

**URL**: `https://www.tesla.com/teslaaccount`
**Auth**: Web session cookies (email + password + MFA)
**Technology**: Next.js SSR, data in `window.Tesla.App.*` and `window.__NEXT_DATA__`

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

### B. tesla.com/teslaaccount/order-details/{RN}

**URL**: `https://www.tesla.com/teslaaccount/order-details/{reservation_number}`
**Auth**: Same web session
**Extra data**: Deep order-specific data not available via REST APIs -- delivery appointment specifics, registration workflow state, document download links

### C. Tesla App (Mobile)

**Auth**: OAuth2 tokens (same as Fleet API or Owner API)
**Unique data not in REST API**:
- Supercharging session history + invoices (viewable under Account > Charging > History)
- Service appointment scheduling and history
- Referral credits and rewards
- Wall Connector management
- Premium Connectivity subscription status
- Loot Box / gamification features
- Push notification preferences

### D. developer.tesla.com (Developer Portal)

**URL**: `https://developer.tesla.com`
**Purpose**: App registration, API key management, scope configuration
**Capabilities**:
- Create and manage applications
- Configure OAuth scopes
- Register partner accounts
- Generate partner tokens
- Manage virtual key pairing
- View API usage and quotas

### E. Tesla for Business

**URL**: Fleet management portal for business accounts
**Purpose**: Third-party business token authorization, fleet management
**Capabilities**:
- Authorize developer apps for business fleets
- Manage fleet vehicle access
- Business admin email approval flow

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

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/1/vehicles` | List vehicles (paginated, 100/page) |
| GET | `/api/1/vehicles/{id_or_vin}/vehicle_data` | Full vehicle state blob |
| GET | `/api/1/vehicles/{id}/mobile_enabled` | Mobile access enabled check |
| GET | `/api/1/vehicles/{id}/nearby_charging_sites` | Superchargers + destination chargers nearby |
| GET | `/api/1/vehicles/{id}/release_notes` | OTA firmware release notes |
| GET | `/api/1/vehicles/{id}/service_data` | Service/maintenance data |
| GET | `/api/1/vehicles/{id}/recent_alerts` | Recent vehicle fault alerts |
| GET | `/api/1/vehicles/charge_history` | Lifetime charging history |
| GET | `/api/1/vehicles/{id}/fleet_status` | Fleet registration status |
| GET | `/api/1/vehicles/{id}/fleet_telemetry_config` | Current telemetry configuration |
| GET | `/api/1/vehicles/{id}/invitations` | Driver sharing invitations |
| POST | `/api/1/vehicles/{id}/invitations` | Create driver invitation |
| POST | `/api/1/vehicles/{id}/invitations/{inv_id}/revoke` | Revoke invitation |

#### vehicle_data Sub-Endpoints (query param `endpoints=`)

| Endpoint Name | Fields Include |
|---------------|----------------|
| `charge_state` | battery_level, battery_range, charge_rate, charge_limit_soc, charger_voltage, charger_actual_current, charging_state, time_to_full_charge, charge_port_door_open, charge_port_latch, scheduled_charging_mode, scheduled_charging_start_time, charge_energy_added, charge_miles_added_rated, charge_miles_added_ideal |
| `climate_state` | inside_temp, outside_temp, driver_temp_setting, passenger_temp_setting, is_auto_conditioning_on, is_climate_on, fan_status, seat_heater_*, steering_wheel_heater, cabin_overheat_protection, climate_keeper_mode, bioweapon_mode |
| `drive_state` | latitude, longitude, heading, speed, power, shift_state, gps_as_of, timestamp |
| `location_data` | Detailed GPS (required for firmware 2023.38+) |
| `vehicle_state` | odometer, firmware_version, locked, sentry_mode, fd_window, fp_window, rd_window, rp_window, ft (frunk), rt (trunk), valet_mode, speed_limit_mode, software_update, tpms_pressure_*, homelink_nearby, media_state |
| `vehicle_config` | car_type, trim_badging, exterior_color, wheel_type, roof_color, spoiler_type, plg (has_ludicrous), perf_config, can_actuate_trunks, motorized_charge_port, has_seat_cooling, has_air_suspension |

#### Vehicle Commands (Scope: `vehicle_cmds` or `vehicle_charging_cmds`)

Commands require the Tesla Vehicle Command Protocol for vehicles with firmware 2024.26+. Commands must be signed with a virtual key paired to the vehicle.

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
| **Navigation** | `share` (send address/place), `navigation_sc_request`, `navigation_gps_request` |
| **Media** | `media_toggle_playback`, `media_next_track`, `media_prev_track`, `media_next_fav`, `media_prev_fav`, `media_volume_up`, `media_volume_down`, `adjust_volume` |
| **Software** | `schedule_software_update`, `cancel_software_update` |
| **HomeLink** | `trigger_homelink` |
| **Boombox** | `remote_boombox` |
| **Signed (generic)** | `signed_command` (base64 RoutableMessage for Vehicle Command Protocol) |

#### Energy Endpoints (Scope: `energy_device_data` / `energy_cmds`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/1/energy_sites/{id}/site_info` | Site info (solar, Powerwall, settings) |
| GET | `/api/1/energy_sites/{id}/live_status` | Real-time power flow |
| GET | `/api/1/energy_sites/{id}/calendar_history` | Historical energy data (kWh) |
| GET | `/api/1/energy_sites/{id}/telemetry_history` | Wall Connector charging history |
| POST | `/api/1/energy_sites/{id}/operation` | Set mode (autonomous/self_consumption) |
| POST | `/api/1/energy_sites/{id}/backup` | Set backup reserve percentage |
| POST | `/api/1/energy_sites/{id}/storm_mode` | Enable/disable storm mode |

#### User Endpoints (Scope: `user_data`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/1/users/me` | Account holder info |
| GET | `/api/1/users/orders` | All orders for the account |
| GET | `/api/1/users/feature_config` | Feature flags/config |

#### Partner Endpoints (Partner tokens)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/1/partner_accounts` | Register partner / pair virtual key |
| GET | `/api/1/partner_accounts/public_key` | Get partner's public key |

### B. Fleet Telemetry (Streaming API)

**Repo**: https://github.com/teslamotors/fleet-telemetry
**Protocol**: WebSocket over TLS with mutual certificate auth
**Data Format**: Protocol Buffers (protobuf), optional JSON
**Server**: Go-based reference implementation
**Firmware Requirement**: 2023.20.6+

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
| V (Vehicle Data) | Configurable telemetry fields, transmit on-change at configurable intervals |
| Alerts | System warnings, fault codes |
| Connectivity | Vehicle online/offline state events |

#### Available Telemetry Fields (from vehicle_data.proto)

Categories of streamable signals include:
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
| GET | `/api/1/vehicles/{vin}/fleet_telemetry_config` | Get current config (check `synced=true`) |
| DELETE | `/api/1/vehicles/{vin}/fleet_telemetry_config` | Remove telemetry config |

#### Setup Requirements

1. Register app on developer.tesla.com
2. Generate EC keypair (secp256r1 curve)
3. Host public key at `https://{domain}/.well-known/appspecific/com.tesla.3p.public-key.pem`
4. Deploy fleet-telemetry server with FQDN + TLS
5. Configure vehicles via API endpoint
6. Wait for `synced: true`

---

## 4. Tesla APIs (Unofficial / Reverse-Engineered)

### A. Owner API (Deprecated but Partially Working)

**Base URL**: `https://owner-api.teslamotors.com`
**Auth**: OAuth2 Bearer tokens (client_id: `ownerapi`)
**Status**: Officially deprecated Jan 2024. Vehicle control endpoints blocked for newer vehicles (firmware 2024.26+). Orders endpoint still works.

| Method | Endpoint | Status | Description |
|--------|----------|--------|-------------|
| GET | `/api/1/users/orders` | WORKS | Order list (all orders for account) |
| GET | `/api/1/vehicles` | BLOCKED (412) | Vehicle list -- returns "use fleetapi" |
| GET | `/api/1/vehicles/{id}/vehicle_data` | BLOCKED (412) | Vehicle data for modern VINs |
| POST | `/api/1/vehicles/{id}/wake_up` | PARTIAL | Works for some older vehicles |
| POST | `/api/1/vehicles/{id}/command/*` | BLOCKED | Unsigned commands rejected |

**Key finding**: The `/api/1/users/orders` endpoint STILL WORKS with ownerapi tokens. This is our primary order tracking mechanism.

### B. Tasks API (Mobile App)

**Base URL**: `https://akamai-apigateway-vfx.tesla.com`
**Auth**: Same OAuth2 Bearer token
**Source**: Reverse-engineered from Tesla mobile app

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tasks?referenceNumber={RN}&deviceLanguage=en&deviceCountry=US&appVersion=4.40.0` | Order task list (milestones, steps) |

Returns structured task data:
- `taskType`: Insurance, Payment, Registration, Delivery, TradeIn
- `taskStatus`: Complete, InProgress, NotStarted
- `taskName`: Human-readable task name
- `completed`: boolean
- `active`: boolean

### C. Streaming API (Legacy, Pre-Fleet Telemetry)

**URL**: `wss://streaming.vn.teslamotors.com/streaming/`
**Status**: Deprecated in favor of Fleet Telemetry
**Used by**: TeslaMate (still uses this for real-time position polling)

---

## 5. Third-Party Services

### A. Tessie

**API Base**: `https://api.tessie.com`
**Auth**: Single Bearer token (generated in Tessie dashboard)
**Pricing**: Subscription-based per vehicle
**Documentation**: https://developer.tessie.com

#### Unique Value Over Raw Tesla API

- Automatic wake handling (no need to manage sleep/wake cycle)
- Automatic firmware error handling and retries
- Unlimited `vehicle_data` polling at no additional cost
- Historical data storage (drives, charges, idles)
- Battery health tracking and measurements over time
- Driving path recording (GPS traces)
- Firmware alert history
- Consumption calculations (Tesla API does not return trip consumption)
- License plate storage
- Weather data at vehicle location
- Map image generation

#### Key Endpoints (Beyond Standard Tesla)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/{vin}/state` | Full vehicle state (cached, no wake) |
| GET | `/{vin}/status` | Online/offline/asleep status |
| GET | `/{vin}/location` | Location + street address + saved location name |
| GET | `/{vin}/battery` | Battery state |
| GET | `/{vin}/battery_health` | Battery degradation data |
| GET | `/{vin}/battery_health_measurements` | Historical battery health over time |
| GET | `/{vin}/charges` | Charging session history |
| GET | `/{vin}/drives` | Drive history |
| GET | `/{vin}/driving_path` | GPS trace during timeframe |
| GET | `/{vin}/consumption` | Consumption since last charge |
| GET | `/{vin}/firmware_alerts` | Firmware-generated alerts |
| GET | `/{vin}/historical_states` | Historical state snapshots |
| GET | `/{vin}/idles` | Idle/parked sessions |
| GET | `/{vin}/last_idle_state` | Data from when vehicle last stopped |
| GET | `/{vin}/map` | Map image of vehicle location |
| GET | `/{vin}/tire_pressure` | Tire pressure (bar) |
| GET | `/{vin}/weather` | Weather forecast at vehicle location |
| GET | `/{vin}/nearby_charging_sites` | Nearby chargers |
| GET | `/charging_invoices` | Supercharging invoices (all vehicles) |
| GET | `/vehicles` | All vehicles with latest state |

#### Tessie Also Proxies Fleet API

Tessie can act as a transparent proxy to the Fleet API, handling Vehicle Command Protocol signing automatically.

### B. TeslaMate (Self-Hosted)

**Repo**: https://github.com/teslamate-org/teslamate
**Tech Stack**: Elixir + PostgreSQL + Grafana
**Auth**: Tesla tokens stored in its own database
**Data Source**: Polls Owner API or Fleet API continuously

#### Unique Data

TeslaMate does not access any data that the Tesla API does not provide. Its value is in **continuous recording and aggregation**:

| Data Type | What It Records |
|-----------|-----------------|
| Drives | Start/end time, distance, duration, start/end address, start/end range, energy used |
| Charges | Start/end time, energy added, cost, location, start/end battery level |
| Updates | OTA firmware version history with timestamps |
| Positions | Continuous GPS position logging |
| States | Vehicle state transitions (online, asleep, driving, charging) |
| Addresses | Reverse-geocoded location names |
| Geofences | Custom named zones |

#### Derived/Calculated Data (Not From Tesla API)

- **Consumption estimates**: Calculated from range loss during drives
- **Vampire drain**: Estimated from range loss while parked
- **Efficiency**: Wh/km and kWh/100mi per trip
- **Battery degradation**: Tracked over time from full charge readings
- **Monthly/yearly reports**: Aggregated driving and charging stats
- **Top locations**: Most visited places
- **Charging costs**: User-entered cost per kWh

#### Database Schema (Key Tables)

- `cars` -- VIN, name, model, trim, color, wheel type, efficiency
- `drives` -- Per-trip records with full telemetry
- `charging_processes` -- Per-charge records
- `positions` -- Continuous position log
- `updates` -- OTA update history
- `addresses` -- Reverse-geocoded locations
- `geofences` -- Named geographic zones
- `settings` -- Per-car settings

### C. TeslaFi (SaaS)

**URL**: https://www.teslafi.com
**Auth**: Tesla tokens (user provides)
**Data**: Similar to TeslaMate but hosted

#### Unique Features

- Battery health visualization and tracking
- Trip logging with energy efficiency
- Tire pressure history
- Sleep tracking (vampire drain analysis)
- Range loss reporting
- Firmware version tracking across the fleet
- Community data (aggregated anonymous statistics)
- CSV data export

### D. Teslemetry

**URL**: https://teslemetry.com
**API**: Wraps Fleet API + Fleet Telemetry
**Unique**: Hosted Fleet Telemetry server -- eliminates need to self-host the WebSocket server

### E. A Better Route Planner (ABRP)

**Integration**: Live telemetry feed from vehicle
**Data consumed**: SoC, location, speed, outside temp, elevation
**Data provided**: Route planning with charging stops, range prediction

---

## 6. Authentication Methods

### Token Type Matrix

| Token Type | Client ID | How to Get | What It Accesses | Expiry |
|------------|-----------|------------|------------------|--------|
| Owner API token | `ownerapi` | OAuth2 PKCE via auth.tesla.com | Orders, (legacy) vehicle data | 8 hours |
| Fleet API 3rd-party token | App-specific | OAuth2 PKCE + user consent | Vehicle data, commands, energy (per scope) | 8 hours |
| Fleet API partner token | App-specific | Client credentials grant | Partner account management | 8 hours |
| Fleet API business token | App-specific | Business admin email approval | Fleet vehicle management | 8 hours |
| Tessie token | N/A | Generated in Tessie dashboard | All Tessie endpoints | Long-lived |
| Web session cookie | N/A | Browser login to tesla.com | Portal SSR data (delivery, docs, etc.) | Session |
| Refresh token | Same as access | Returned with access token | Exchange for new access token | 3 months |

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

### Vehicle Command Protocol (Required for Modern Vehicles)

Vehicles with firmware 2024.26+ require end-to-end signed commands:

1. Register app on developer.tesla.com
2. Generate EC keypair (secp256r1)
3. Host public key at `https://{domain}/.well-known/appspecific/com.tesla.3p.public-key.pem`
4. Call `/api/1/partner_accounts` to register and auto-pair virtual key
5. User approves virtual key on vehicle touchscreen
6. Commands are signed with private key before sending
7. Alternatively: Use `tesla-http-proxy` to sign commands automatically
8. Or: Use BLE (`tesla-control`) for direct local command signing

---

## 7. What We Currently Access

### Token Storage (keyring-based)

| Key | Source | Used By |
|-----|--------|---------|
| `order-access-token` | Owner API OAuth (client_id=ownerapi) | OrderBackend, OwnerApiVehicleBackend |
| `order-refresh-token` | Owner API OAuth | Token refresh |
| `fleet-access-token` | Fleet API OAuth (app client_id) | FleetBackend |
| `fleet-refresh-token` | Fleet API OAuth | Token refresh |
| `tessie-token` | Tessie dashboard (paste) | TessieBackend |
| `fleet-client-secret` | developer.tesla.com | (stored, not currently used) |
| `teslamate-db-password` | TeslaMate stack install | TeslaMateBackend DB connection |
| `teslamate-grafana-password` | TeslaMate stack install | Grafana access |
| `teslamate-encryption-key` | TeslaMate stack install | TeslaMate encryption |

### Active Backends

| Backend | Class | Base URL | Auth | Capabilities |
|---------|-------|----------|------|-------------|
| `owner` | `OwnerApiVehicleBackend` | owner-api.teslamotors.com | order-access-token | Vehicle data (older VINs), commands (older VINs) |
| `fleet` | `FleetBackend` | fleet-api.prd.{region}.vn.cloud.tesla.com | fleet-access-token | Full vehicle data, all commands, energy, sharing |
| `tessie` | `TessieBackend` | api.tessie.com | tessie-token | Vehicle data (cached), commands (auto-wake), nearby chargers |
| `teslaMate` | `TeslaMateBacked` | PostgreSQL direct | DB connection | Trips, charges, updates, stats, efficiency, vampire drain, timeline |

### Registered Data Sources

| Source ID | Name | Category | Auth | Method |
|-----------|------|----------|------|--------|
| `tesla.portal` | Tesla Portal -- Orden Completa | financiero | order | Browser scrape (patchright) |
| `tesla.order` | Tesla Order | financiero | order | Owner API /users/orders |
| `vin.decode` | VIN Decode | vehiculo | none | NHTSA API |
| `co.runt` | RUNT -- Registro Vehicular | registro | none | Playwright (openquery) |
| `co.runt_soat` | RUNT -- SOAT | registro | none | Playwright |
| `co.runt_rtm` | RUNT -- Tecnico-Mecanica | registro | none | Playwright |
| `co.runt_conductor` | RUNT -- Conductor | registro | none | Playwright |
| `co.simit` | SIMIT -- Multas | infracciones | none | Playwright |
| `co.pico_y_placa` | Pico y Placa | servicios | none | API (openquery) |
| `co.estaciones_ev` | Electrolineras | servicios | none | datos.gov.co API |
| `co.recalls` | SIC -- Recalls | seguridad | none | Playwright |
| `co.fasecolda` | Fasecolda -- Valor Comercial | financiero | none | Playwright |
| `us.nhtsa_recalls` | NHTSA Recalls | seguridad | none | API |
| `us.nhtsa_vin` | NHTSA VIN Decode | vehiculo | none | API |
| `intl.ship_tracking` | Ship Tracking | servicios | none | Playwright |

### Data Flow Diagram (Current)

```
Order Tracking:
  owner-api.teslamotors.com/api/1/users/orders --> OrderBackend --> tesla.order source
  akamai-apigateway-vfx.tesla.com/tasks --> OrderBackend.get_order_tasks()

Delivery Data:
  tesla.com/teslaaccount/order-details/{RN} --> portal_scrape.py (patchright)
    --> window.Tesla.App.DeliveryDetails --> tesla.portal source

Vehicle Data (when delivered):
  fleet-api.prd.na.vn.cloud.tesla.com --> FleetBackend --> all vehicle_data endpoints
  OR api.tessie.com --> TessieBackend --> cached vehicle state
  OR owner-api.teslamotors.com --> OwnerApiVehicleBackend --> (limited, deprecated)

Historical Data:
  TeslaMate PostgreSQL --> TeslaMateBacked --> trips, charges, updates, efficiency
```

---

## 8. What We Are Missing

### A. Data We Could Access But Do Not

| Data | Source | Blocked By | Priority |
|------|--------|------------|----------|
| **Supercharging invoices** | Tessie `/charging_invoices` | Not implemented | Medium |
| **Battery health over time** | Tessie `/battery_health_measurements` | Not implemented | High |
| **Drive GPS paths** | Tessie `/{vin}/driving_path` | Not implemented | Medium |
| **Firmware alerts** | Fleet API `/recent_alerts` or Tessie `/firmware_alerts` | Implemented in Fleet, not surfaced in UI | Medium |
| **Release notes** | Fleet API `/{vin}/release_notes` | Implemented in Fleet, not surfaced | Low |
| **Tire pressure history** | Tessie `/{vin}/tire_pressure` | Not implemented | Low |
| **Weather at vehicle** | Tessie `/{vin}/weather` | Not implemented | Low |
| **Consumption data** | Tessie `/{vin}/consumption` | Not implemented | Medium |
| **Fleet Telemetry streaming** | Fleet Telemetry server | Requires infrastructure (FQDN, TLS, server) | High |
| **Energy site data** | Fleet API `/energy_sites/*` | No energy products registered | N/A |
| **Charge history** | Fleet API `/vehicles/charge_history` | Implemented but not sourced | Medium |

### B. Data That Requires Portal Scraping (No API)

| Data | Where It Lives | Why No API |
|------|---------------|-----------|
| Delivery appointment details | window.Tesla.App.DeliveryDetails | Tesla never exposed this via REST |
| Purchase documents (MVPA, sticker) | tesla.com/teslaaccount Documents tab | Web-only, download links |
| Finance contract details | tesla.com/teslaaccount Documents tab | Web-only |
| Registration workflow state | window.Tesla.App.OrderDetails | Not in order API response |
| Service appointment history | Tesla mobile app only | No known API endpoint |
| Supercharging session invoices | Tesla mobile app Account > Charging | Tessie has this but we do not use it |
| Referral credits | Tesla mobile app Account | No known API endpoint |

### C. VIN Blocking Issue (HTTP 412)

Modern VINs (prefixes LRW, 7SA, XP7) receive HTTP 412 from the Owner API for vehicle data/command endpoints. The error says "use Fleet API". Our order tracking still works because `/api/1/users/orders` is a user-level endpoint, not a vehicle-level one.

**Impact**: We cannot use `OwnerApiVehicleBackend` for vehicle data on our Model Y (VIN: 7SAYGDEF*). Must use Fleet API or Tessie.

---

## 9. Gaps & Opportunities

### High Priority

1. **Fleet Telemetry Integration**
   - Real-time streaming eliminates polling (no vampire drain from API calls)
   - Requires: FQDN, TLS cert, fleet-telemetry server deployment
   - Alternative: Use Teslemetry.com as hosted Fleet Telemetry (no infra needed)
   - **Opportunity**: Sub-second data for location tracking, energy monitoring

2. **Battery Health Source**
   - Add Tessie battery_health_measurements as a data source
   - Track degradation over time (important for EV resale value)
   - TeslaMate also calculates this from charge data

3. **Charge History Unification**
   - Fleet API `charge_history` + TeslaMate `charging_processes` + Tessie `charges`
   - Combine into a unified charging history with cost tracking

### Medium Priority

4. **Supercharging Invoice Tracking**
   - Tessie `/charging_invoices` provides this
   - Useful for expense tracking and tax documentation

5. **Drive Path Recording**
   - Tessie `driving_path` gives GPS traces
   - Could build heatmaps, route analysis

6. **Portal Scrape Automation**
   - Currently manual (requires email+password entry each time)
   - Could use stored session cookies for periodic refresh
   - Risk: Tesla may block automated access

7. **BLE Direct Control**
   - Config exists (`ble.key_path`, `ble.ble_mac`) but not implemented
   - `tesla-control` binary can send commands locally without internet
   - Fastest command execution, works offline

### Lower Priority

8. **ABRP Live Telemetry**
   - Config exists (`abrp.api_key`, `abrp.user_token`) but not pushing data
   - Push SoC + location to ABRP for live route planning

9. **Home Assistant Integration**
   - Config exists (`home_assistant.url`, `home_assistant.token`) but not implemented
   - Could expose vehicle state as HA entities

10. **MQTT Telemetry Publishing**
    - Config exists (`mqtt.*`) but not implemented
    - TeslaMate already publishes to MQTT; could bridge or replace

### Architecture Recommendations

| Current Gap | Recommended Solution |
|-------------|---------------------|
| No real-time streaming | Deploy fleet-telemetry OR use Teslemetry.com |
| Portal data requires manual login | Implement session cookie caching + periodic refresh |
| Battery health not tracked | Add Tessie battery_health source + TeslaMate degradation calc |
| No unified charging history | Merge Fleet charge_history + TeslaMate + Tessie into single view |
| Commands blocked on Owner API | Already using Fleet API; ensure virtual key is paired |
| No BLE fallback | Implement tesla-control wrapper for offline commands |
| 3 separate vehicle backends | Consider consolidating to Fleet API primary + Tessie fallback |

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
- [Tesla API Postman Collection](https://documenter.getpostman.com/view/781424/2s9YRCWB4f)
