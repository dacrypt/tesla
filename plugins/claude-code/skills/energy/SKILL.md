---
name: energy
description: >
  Tesla energy management — Powerwall status, Solar production, electricity
  tariffs by city, backup reserve, operation mode, storm watch.
argument-hint: "[query: status|tariffs|backup|mode|storm|savings]"
allowed-tools: Bash(tesla *)
level: 2
---

# Tesla Energy Management

Monitor and control Powerwall, solar production, and electricity tariffs.

## Powerwall Status

```bash
tesla energy status              # Powerwall charge %, solar W, grid W, home W
tesla energy status --oneline    # compact: 🔋 82% | ☀️ 3.2kW solar | 🏠 1.1kW home
```

## Tariffs by City

```bash
tesla data energia --ciudad bogota --estrato 4   # tariff for Bogotá estrato 4
tesla data energia --ciudad medellin --estrato 3  # Medellín estrato 3
tesla data energia                                # use vehicle location automatically
```

Shows COP/kWh rate, tier breakdown, and estimated monthly cost.

## Backup Reserve

```bash
tesla energy backup              # show current backup reserve %
tesla energy backup 30           # set backup reserve to 30%
```

## Operation Mode

```bash
tesla energy mode                        # show current mode
tesla energy mode self_consumption       # maximize solar self-consumption
tesla energy mode autonomous             # Time-Based Control (TOU)
tesla energy mode backup                 # full backup mode
```

## Storm Watch

```bash
tesla energy storm --on          # enable Storm Watch (charge to 100%)
tesla energy storm --off         # disable Storm Watch
```

## Savings Calculator

```bash
tesla charge savings             # EV vs gas savings summary
tesla charge savings --months 6  # last 6 months comparison
```

## Response Guidelines

- If the CLI is not configured, **stop and tell the user to run `/tesla:setup`** — never auto-configure
- Start with Powerwall % and current solar/grid/home power flows
- For tariff queries: show rate in COP/kWh and compare to grid cost
- For backup/mode changes: confirm the new setting after applying
- For `$ARGUMENTS`:
  - "status" / no args → `tesla energy status`
  - "tariffs" / "precio" / "estrato" → `tesla data energia`
  - "backup" → `tesla energy backup`
  - "mode" / "modo" → `tesla energy mode`
  - "storm" → `tesla energy storm`
  - "savings" / "ahorro" → `tesla charge savings`
