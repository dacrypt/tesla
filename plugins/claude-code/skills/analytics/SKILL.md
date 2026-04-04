---
name: analytics
description: >
  Tesla analytics via TeslaMate — trip history, charging costs, battery
  degradation, vampire drain, efficiency, heatmaps. Requires TeslaMate.
argument-hint: "[query: trips|charging|costs|battery|vampire|efficiency|heatmap]"
allowed-tools: Bash(tesla *)
---

# Tesla Analytics (TeslaMate)

Deep analytics from your TeslaMate PostgreSQL database.

> **Prerequisite**: TeslaMate must be connected. If not set up, guide the user:
> ```bash
> uv tool install tesla-cli[teslaMate]
> tesla teslaMate connect postgresql://user:pass@host:5432/teslamate
> ```
> For a managed Docker stack: `tesla teslaMate install`

## Connection Status

```bash
tesla teslaMate status           # lifetime stats + connection health
```

## Trip History

```bash
tesla teslaMate trips            # last 20 trips
tesla teslaMate trips --limit 50 # last 50 trips
tesla teslaMate trip-stats       # summary + top routes
tesla teslaMate trip-stats --days 30  # last 30 days
tesla teslaMate efficiency       # per-trip energy efficiency (Wh/km)
```

## Charging Analytics

```bash
tesla teslaMate charging         # last 20 charging sessions
tesla teslaMate charging-locations  # top charging locations
tesla teslaMate charging-locations --days 90 --limit 10
tesla teslaMate graph            # ASCII bar chart of sessions
tesla teslaMate daily-chart      # daily kWh chart
tesla teslaMate daily-chart --days 30
```

## Cost Reports

```bash
tesla teslaMate cost-report      # current month cost breakdown
tesla teslaMate cost-report --month 2026-03  # specific month
tesla teslaMate report           # monthly summary (DC vs AC, Wh/km)
tesla charge weekly              # weekly kWh + cost (last 4 weeks)
tesla charge cost-summary        # aggregated cost totals
```

## Battery Health

```bash
tesla teslaMate battery-degradation  # monthly max range trend
tesla vehicle battery-health     # degradation from snapshot history
```

## Other Analytics

```bash
tesla teslaMate vampire          # vampire drain analysis
tesla teslaMate heatmap          # drive days calendar
tesla teslaMate heatmap --year 2026
tesla teslaMate geo              # most-visited locations
tesla teslaMate timeline         # unified events timeline
tesla teslaMate timeline --days 7
tesla teslaMate updates          # OTA update history
tesla teslaMate stats            # lifetime stats
tesla teslaMate sentry-events    # sentry mode events
```

## Grafana Dashboards

```bash
tesla teslaMate grafana          # open Grafana in browser
```

## Response Guidelines

- If TeslaMate is not connected, explain what it is and guide through setup
- For cost queries: break down by AC vs DC charging, show cost per kWh
- For battery health: show the trend and explain what's normal (1-3% loss/year)
- For trips: include distance, duration, and efficiency
- For `$ARGUMENTS`:
  - "trips" / "drives" → `tesla teslaMate trips`
  - "charging" / "sessions" → `tesla teslaMate charging`
  - "costs" / "money" / "spent" → `tesla teslaMate cost-report`
  - "battery" / "health" / "degradation" → `tesla teslaMate battery-degradation`
  - "vampire" / "drain" → `tesla teslaMate vampire`
  - "efficiency" → `tesla teslaMate efficiency`
  - "heatmap" / "calendar" → `tesla teslaMate heatmap`
