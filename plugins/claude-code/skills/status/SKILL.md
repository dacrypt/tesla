---
name: status
description: >
  Quick Tesla vehicle status — battery level, charging state, location, climate,
  readiness. Use when someone asks "how's my Tesla?", "battery level?",
  "where's my car?", "is my car ready?", or similar status queries.
argument-hint: "[detail: battery|location|climate|full]"
allowed-tools: Bash(tesla *)
---

# Tesla Vehicle Status

Get a quick overview of the vehicle's current state.

## Quick Status

For a fast at-a-glance view:
```bash
tesla vehicle summary --oneline
```

For more detail:
```bash
tesla vehicle summary
```

## Specific Queries

### Battery & Charging
```bash
tesla charge status              # SoC %, range, charge rate, time remaining
tesla charge status --oneline    # compact: 🔋 72% | ⚡ 11kW | 1h30m to 80%
```

### Location
```bash
tesla vehicle location           # GPS coordinates + Google Maps link
```

### Readiness (morning check)
```bash
tesla vehicle ready              # 7-point system check
tesla vehicle ready --oneline    # ✅ Ready | 🔋 82% | 🌡 22°C
```

### Climate
```bash
tesla climate status             # interior/exterior temperatures
```

### Full Vehicle Data
```bash
tesla vehicle info               # complete vehicle state (JSON with -j)
tesla vehicle bio                # comprehensive 5-panel profile
tesla vehicle dashboard          # multi-panel Rich dashboard
```

### Health Check
```bash
tesla vehicle health-check       # 7-point diagnostic
tesla vehicle software           # firmware version + pending updates
tesla vehicle tires              # TPMS pressure readings
tesla vehicle alerts             # recent fault codes
```

## Response Guidelines

- Lead with the most relevant info (usually battery %)
- Include location only if asked or if the car is away from home
- Mention charging state if plugged in
- Flag any issues (low battery, open doors, sentry events)
- For `$ARGUMENTS`:
  - "battery" → `tesla charge status`
  - "location" / "where" → `tesla vehicle location`
  - "climate" / "temp" → `tesla climate status`
  - "full" / "everything" → `tesla vehicle info`
  - no args → `tesla vehicle summary`
