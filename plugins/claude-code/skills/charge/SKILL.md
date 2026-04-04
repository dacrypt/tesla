---
name: charge
description: >
  Tesla charging management — battery status, charge sessions, cost tracking,
  weekly summaries, schedule, forecast. Use when someone asks about charging,
  battery, range, kWh, cost per charge, charge history, or Supercharger usage.
argument-hint: "[query: status|last|weekly|sessions|forecast|cost]"
allowed-tools: Bash(tesla *)
---

# Tesla Charging

Manage and analyze charging state, history, and costs.

## Current State

```bash
tesla charge status              # full: SoC %, range, power, time remaining, limit
tesla charge status --oneline    # compact: 🔋 72% | ⚡ 11kW | 1h30m to 80%
tesla charge last                # most recent charge session with cost
```

## Cost & Usage Tracking

```bash
tesla charge weekly              # weekly kWh, cost, sessions (default: last 4 weeks)
tesla charge weekly --weeks 8    # last 8 weeks
tesla charge cost-summary        # aggregated cost report
tesla charge cost-summary --csv costs.csv  # export to CSV
tesla teslaMate cost-report      # monthly cost breakdown (requires TeslaMate)
tesla teslaMate cost-report --month 2026-03  # specific month
```

## Charge History

```bash
tesla charge sessions            # unified sessions (TeslaMate + Fleet API)
tesla charge sessions -n 50      # last 50 sessions
tesla charge sessions --csv charges.csv  # export to CSV
tesla charge history             # Fleet API raw charge history
```

## Schedule & Forecast

```bash
tesla charge forecast            # ETA + kWh estimate to reach target SoC
tesla charge schedule-preview    # scheduled charge + departure times
tesla charge schedule-preview --oneline  # 🔌 Charge @ 23:30 | 🚗 Depart @ 07:00
tesla charge profile             # view/set limit + amps + schedule
```

## Charging Control

```bash
tesla charge start               # begin charging
tesla charge stop                # stop charging
tesla charge set-limit 80        # set target SoC (50-100%)
tesla charge set-amps 32         # set current (1-48A)
tesla charge limit               # show current limit
tesla charge amps                # show current amperage
```

## Response Guidelines

- Always include **SoC %** and **charge state** (charging, stopped, disconnected)
- If charging: show power (kW), time remaining, and target limit
- For cost queries: show kWh consumed and cost (using configured `cost_per_kwh`)
- For weekly/monthly: show trends and comparisons
- Mention if TeslaMate is needed for deeper analytics
- For `$ARGUMENTS`:
  - "status" / no args → `tesla charge status`
  - "last" → `tesla charge last`
  - "weekly" / "week" → `tesla charge weekly`
  - "sessions" / "history" → `tesla charge sessions`
  - "forecast" / "eta" → `tesla charge forecast`
  - "cost" / "money" / "spent" → `tesla charge cost-summary`
