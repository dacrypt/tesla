# Data Sources

> Definitive reference: what Tesla data exists, where it lives, how we access it, and our implementation status.

---

## Tesla Data Ecosystem

Tesla data lives in multiple disconnected systems. No single API gives everything.

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

---

## Tesla APIs (Official)

### Fleet API

**Base URLs**: `fleet-api.prd.{na|eu|cn}.vn.cloud.tesla.com`
**Auth**: OAuth2 Bearer tokens (third-party or partner)
**Docs**: https://developer.tesla.com/docs/fleet-api

#### OAuth Scopes

| Scope | Purpose |
|-------|---------|
| `openid` | Required for OpenID Connect |
| `offline_access` | Refresh tokens (valid 3 months) |
| `user_data` | Account info |
| `vehicle_device_data` | Read vehicle telemetry and state |
| `vehicle_cmds` | Send vehicle commands |
| `vehicle_charging_cmds` | Charging control |
| `energy_device_data` | Powerwall/solar data |
| `energy_cmds` | Control energy products |

#### Vehicle Endpoints

| Endpoint | Description | Status |
|----------|-------------|--------|
| `GET /api/1/vehicles` | List vehicles | IMPLEMENTED |
| `GET /api/1/vehicles/{id}/vehicle_data` | Full vehicle state | IMPLEMENTED |
| `GET /api/1/vehicles/{id}/nearby_charging_sites` | Superchargers + destination chargers | IMPLEMENTED |
| `GET /api/1/vehicles/{id}/release_notes` | OTA firmware notes | IMPLEMENTED |
| `GET /api/1/vehicles/{id}/service_data` | Service/maintenance data | IMPLEMENTED |
| `GET /api/1/vehicles/{id}/recent_alerts` | Fault alerts | IMPLEMENTED |
| `GET /api/1/vehicles/charge_history` | Lifetime charging history | IMPLEMENTED |
| `GET /api/1/vehicles/{id}/invitations` | Driver sharing | IMPLEMENTED |
| `GET /api/1/vehicles/{id}/fleet_telemetry_config` | Telemetry config | NOT IMPLEMENTED |

#### vehicle_data Sub-Endpoints (`?endpoints=`)

| Name | Key Fields |
|------|-----------|
| `charge_state` | battery_level, battery_range, charge_rate, charge_limit_soc, charging_state, time_to_full_charge, charge_energy_added |
| `climate_state` | inside_temp, outside_temp, seat_heater_*, cabin_overheat_protection, climate_keeper_mode |
| `drive_state` | latitude, longitude, heading, speed, power, shift_state |
| `vehicle_state` | odometer, firmware_version, locked, sentry_mode, tpms_pressure_*, software_update |
| `vehicle_config` | car_type, trim_badging, exterior_color, wheel_type |

#### Vehicle Commands (62 implemented in FleetBackend)

Wake, doors, charging (start/stop/limit/amps/schedule/departure), climate (on/off/temp/seats/steering/preconditioning), windows, trunk/frunk, horn/lights, sentry, valet, speed limit, PIN to drive, guest mode, remote start, navigation, media, software updates, HomeLink, boombox.

#### Energy Endpoints (NOT IMPLEMENTED)

`/api/1/energy_sites/{id}/site_info`, `live_status`, `calendar_history`, `telemetry_history`, `operation`, `backup`, `storm_mode` — requires Powerwall/Solar ownership.

### Fleet Telemetry (Streaming API)

**Protocol**: WebSocket over TLS with mutual certificate auth
**Status**: NOT IMPLEMENTED (requires FQDN + TLS + Go server)
**Alternative**: Teslemetry.com as hosted proxy

Streams: battery, charging, climate, drive, location, vehicle state, tire pressure, software — all on-change, sub-second latency.

---

## Tesla APIs (Unofficial / Reverse-Engineered)

### Owner API (Deprecated, Partially Working)

**Base URL**: `owner-api.teslamotors.com`
**Status**: Vehicle endpoints blocked for modern VINs (HTTP 412). User-level endpoints still work.

| Endpoint | Status |
|----------|--------|
| `GET /api/1/users/orders` | **WORKS** — primary order tracking mechanism |
| `GET /api/1/users/me` | **WORKS** |
| `GET /api/1/vehicles` | BLOCKED (412) for LRW/7SA/XP7 VINs |
| `GET /api/1/vehicles/{id}/vehicle_data` | BLOCKED (412) |

### Tasks API (Mobile App Backend)

**Base URL**: `akamai-apigateway-vfx.tesla.com`
**Status**: Returns 403/503 for all endpoints as of 2026-04-02 (Akamai gateway blocking)

### Tesla Portal (SSR)

**URL**: `tesla.com/teslaaccount`
**Tech**: Next.js SSR; data in `window.Tesla.App.*` and `window.__NEXT_DATA__`
**Blocker**: hCaptcha blocks `client_id=ownership`; Fleet API `client_id` bypasses

Data available via portal only: delivery appointment details, purchase documents (7 types), finance contracts, registration workflow, manage order config.

---

## Third-Party Services

### Tessie

**API**: `api.tessie.com` | **Price**: ~$13/month | **Status**: IMPLEMENTED

Unique data beyond raw Tesla API: battery health tracking, drive GPS paths, consumption calculations, weather at vehicle, Supercharging invoices, 200+ OBD-style data points.

Key unimplemented Tessie endpoints: `battery_health`, `battery_health_measurements`, `charges`, `drives`, `driving_path`, `consumption`, `firmware_alerts`, `charging_invoices`.

### TeslaMate (Self-Hosted)

**Status**: FULLY INTEGRATED (managed Docker stack in v4.0.0)

Records: drives, charges, OTA updates, positions, states, addresses, geofences. Derives: consumption estimates, vampire drain, efficiency, battery degradation, monthly reports, top locations.

### Others (Reference Only)

- **TeslaFi** — SaaS logger with Alexa skill, 100+ data columns, firmware tracker
- **TeslaLogger** — Self-hosted with ScanMyTesla cell-level battery data
- **Teslemetry** — Hosted Fleet Telemetry server (eliminates self-hosting)
- **ABRP** — FULLY INTEGRATED (send/stream/status/setup)
- **Stats for Tesla** (iOS) — Battery fleet benchmarking, charge scheduling

---

## Authentication Methods

| Token Type | Client ID | Accesses | Expiry |
|------------|-----------|----------|--------|
| Owner API token | `ownerapi` | Orders, /users/me | 8 hours |
| Fleet API 3rd-party | App-specific | Vehicle data + commands (per scope) | 8 hours |
| Fleet API partner | App-specific | Partner account management | 8 hours |
| Tessie token | N/A | All Tessie endpoints | Long-lived |
| Refresh token | Same as access | Exchange for new access token | 3 months |

### Vehicle Command Protocol (Firmware 2024.26+)

Required for newer vehicles that reject unsigned commands:
1. Register app on developer.tesla.com
2. Generate EC keypair (secp256r1)
3. Host public key at `https://{domain}/.well-known/appspecific/com.tesla.3p.public-key.pem`
4. Register partner + auto-pair virtual key
5. User approves on vehicle touchscreen
6. Commands signed with private key

Alternatives: `tesla-http-proxy` (auto-signs), `tesla-control` (BLE direct signing).

---

## Registered Data Sources (15)

These sources are registered in `src/tesla_cli/core/sources.py`:

| Source ID | Name | Category | Method | TTL |
|-----------|------|----------|--------|-----|
| `tesla.portal` | Tesla Portal -- Orden Completa | financiero | Browser scrape (patchright) | 1h |
| `tesla.order` | Tesla Order | financiero | Owner API `/users/orders` | 30m |
| `vin.decode` | VIN Decode | vehiculo | NHTSA vPIC API | 30d |
| `co.runt` | RUNT -- Registro Vehicular | registro | Playwright (openquery) | 1h |
| `co.runt_soat` | RUNT -- SOAT | registro | Playwright (openquery) | 1h |
| `co.runt_rtm` | RUNT -- Tecnico-Mecanica | registro | Playwright (openquery) | 1h |
| `co.runt_conductor` | RUNT -- Conductor | registro | Playwright (openquery) | 24h |
| `co.simit` | SIMIT -- Multas de Transito | infracciones | Playwright (openquery) | 1h |
| `co.pico_y_placa` | Pico y Placa | servicios | API (openquery) | 12h |
| `co.estaciones_ev` | Electrolineras | servicios | datos.gov.co API | 24h |
| `co.recalls` | SIC -- Recalls | seguridad | Playwright (openquery) | 24h |
| `co.fasecolda` | Fasecolda -- Valor Comercial | financiero | Playwright (openquery) | 7d |
| `us.nhtsa_recalls` | NHTSA Recalls | seguridad | API (openquery) | 24h |
| `us.nhtsa_vin` | NHTSA VIN Decode | vehiculo | API (openquery) | 30d |
| `intl.ship_tracking` | Ship Tracking | servicios | Playwright (openquery) | 1h |

### Source Infrastructure

- **Cache**: `~/.tesla-cli/sources/{source_id}.json`
- **History**: `~/.tesla-cli/source_history/{source_id}.jsonl` (append-only with data hashes)
- **Audits**: `~/.tesla-cli/source_audits/{source_id}_{timestamp}.pdf` (Playwright screenshots)
- **Change detection**: Automatic field-level diff on every refresh
- **Subprocess isolation**: Playwright sources run as subprocesses to avoid uvicorn conflicts

### OpenQuery Library

Our sources leverage the `openquery` library (100+ sources across CO, US, AR, CL, EC, MX, PE). Key available but unregistered: `us.epa_fuel_economy`, `us.carfax_free`.

---

## Discovery Log (2026-04-02)

### Portal URL Structure

```
/teslaaccount/order/{RN}                    -- Order overview
/teslaaccount/order/{RN}/manage             -- Vehicle config
/teslaaccount/order/{RN}/documents/{id}     -- Document download
```

### Documents Found (RN126460939)

Order Agreement, Final Invoice, Identification Form, Vehicle Manifest, Registration Application, Registration Power of Attorney, Motor Vehicle Purchase Agreement.

### Authentication Findings

- hCaptcha blocks `client_id=ownership` on portal
- Fleet API `client_id` bypasses captcha for OAuth login
- Owner API user-level endpoints (`/users/orders`, `/users/me`) still work
- Akamai gateway blocks Tasks API (403/503)
- MFA uses 6 separate `<input>` boxes (codeBox1-6, type=tel)
- TeslaMate token injection via Ecto RPC is possible for managed stack

---

## External References

- [Tesla Fleet API Docs](https://developer.tesla.com/docs/fleet-api)
- [Fleet Telemetry Server](https://github.com/teslamotors/fleet-telemetry)
- [Vehicle Command Protocol](https://github.com/teslamotors/vehicle-command)
- [Tessie Developer API](https://developer.tessie.com)
- [TeslaMate](https://github.com/teslamate-org/teslamate)
- [Community API Docs (timdorr)](https://github.com/timdorr/tesla-api)
- [TeslaPy](https://github.com/tdorssers/TeslaPy)
- [python-tesla-fleet-api](https://github.com/Teslemetry/python-tesla-fleet-api)
- [Teslemetry](https://teslemetry.com)
