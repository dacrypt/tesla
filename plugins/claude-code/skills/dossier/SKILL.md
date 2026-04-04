---
name: dossier
description: >
  Tesla vehicle intelligence — VIN decode, option codes, NHTSA recalls, specs,
  data sources, snapshots. Use when someone asks about their VIN, recalls,
  vehicle specs, option codes, battery type, or wants a deep profile.
argument-hint: "[query: build|show|vin|recalls|history|sources]"
allowed-tools: Bash(tesla *)
level: 2
---

# Tesla Vehicle Dossier

Comprehensive vehicle intelligence from 15+ data sources.

## Build & View Dossier

```bash
tesla dossier build              # query ALL sources, save snapshot
tesla dossier show               # show saved dossier (no API calls)
tesla -j dossier show            # full dossier as JSON
```

## VIN Decode

```bash
tesla vehicle vin                # decode your configured VIN
tesla vehicle vin 7SAYGDEF1TF123456  # decode any Tesla VIN
tesla vehicle option-codes       # decode Tesla option codes (140+ codes)
```

## Recalls & Safety

```bash
tesla dossier build              # includes NHTSA recall check
# Recalls are part of the dossier — look for the recalls section
```

## Vehicle Profile

```bash
tesla vehicle bio                # comprehensive 5-panel profile
tesla vehicle profile            # multi-source profile (Tesla + NHTSA + more)
tesla vehicle battery-health     # battery degradation from snapshot history
```

## Data Sources & History

```bash
tesla data data-sources          # show all 15 sources + cache status + TTL
tesla data build                 # refresh all sources
tesla data history               # view historical snapshots
tesla data diff                  # compare last two snapshots
tesla data diff 1 3              # compare specific snapshots
```

## Export

```bash
tesla data export-html           # interactive HTML report (dark theme)
tesla data export-html --theme light
tesla data export-pdf            # PDF export (requires pdf extra)
tesla vehicle export             # raw JSON export
tesla vehicle export -f csv -o car.csv  # CSV with flattened fields
```

## Response Guidelines

- If the CLI is not configured (no VIN, no auth), **stop and tell the user to run `/tesla:setup`** — never auto-configure
- For VIN questions: decode position-by-position and explain each segment
- For recalls: list each recall with remedy status
- For option codes: explain what each code means (model, color, wheels, etc.)
- For "tell me everything": run `tesla dossier build` then summarize
- For `$ARGUMENTS`:
  - "build" / "refresh" → `tesla dossier build`
  - "show" / no args → `tesla dossier show`
  - "vin" / "decode" → `tesla vehicle vin`
  - "recalls" / "safety" → `tesla dossier build` (focus on recalls section)
  - "history" / "changes" → `tesla data history` + `tesla data diff`
  - "sources" → `tesla data data-sources`
