---
name: telemetry
description: >
  Fleet Telemetry management — self-hosted real-time vehicle streaming.
  Install, configure, and monitor the fleet-telemetry Docker stack.
argument-hint: "[action: install|start|stop|status|configure|logs]"
allowed-tools: Bash(tesla *) Bash(docker *)
disable-model-invocation: true
level: 2
---

# Tesla Fleet Telemetry

Self-hosted real-time telemetry streaming using the official `fleet-telemetry` server. Streams live vehicle data (location, speed, battery, climate, etc.) to your own infrastructure via WebSocket/MQTT.

## Install

```bash
tesla telemetry install          # pull and configure the fleet-telemetry Docker stack
```

This sets up the `fleet-telemetry` container with TLS certificates, configures your vehicle to stream to the server, and registers the server endpoint with the Fleet API.

## Configure Streaming Fields

```bash
tesla telemetry configure        # interactive field selector (what data to stream)
```

Common fields: `Location`, `Speed`, `BatteryLevel`, `ChargeState`, `ClimateState`, `InsideTemp`, `OutsideTemp`, `Odometer`, `SentryMode`.

## Start / Stop

```bash
tesla telemetry start            # start the fleet-telemetry container
tesla telemetry stop             # stop the container
tesla telemetry restart          # restart after config changes
```

## Monitor

```bash
tesla telemetry status           # container health, uptime, connected vehicles, message rate
tesla telemetry logs             # tail live logs from the telemetry server
tesla telemetry logs --tail 100  # last 100 lines
```

## Stream Live Vehicle Data

```bash
tesla vehicle stream-live        # stream real-time telemetry to the terminal (Ctrl-C to stop)
tesla vehicle stream-live --fields BatteryLevel,Speed,Location
```

## Response Guidelines

- If the CLI is not configured (no VIN, no auth), **stop and tell the user to run `/tesla:setup`** — never auto-configure
- Fleet Telemetry requires Fleet API backend — if the user is on Owner API or Tessie, explain the prerequisite
- Install must be run before start/configure
- `tesla vehicle stream-live` uses the telemetry server once it is running
- For `$ARGUMENTS`:
  - "install" / "setup" → `tesla telemetry install`
  - "configure" / "fields" → `tesla telemetry configure`
  - "start" → `tesla telemetry start`
  - "stop" → `tesla telemetry stop`
  - "status" / no args → `tesla telemetry status`
  - "logs" / "monitor" → `tesla telemetry logs`
  - "stream" / "live" → `tesla vehicle stream-live`
