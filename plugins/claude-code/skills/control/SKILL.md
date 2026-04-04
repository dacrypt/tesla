---
name: control
description: >
  Control your Tesla — lock, unlock, climate, trunk, horn, flash, windows,
  sentry mode, charge port, speed limit. Use when someone says "lock my car",
  "turn on the AC", "open the trunk", "honk the horn", etc.
argument-hint: "<action: lock|unlock|climate-on|climate-off|trunk|frunk|horn|flash|...>"
disable-model-invocation: true
allowed-tools: Bash(tesla *)
level: 2
---

# Tesla Vehicle Control

Execute vehicle commands. **Always confirm destructive or security-sensitive actions before executing.**

## Security Commands (ALWAYS CONFIRM FIRST)

```bash
tesla security lock              # lock all doors
tesla security unlock            # ⚠️ CONFIRM before executing
tesla security trunk rear        # ⚠️ open rear trunk
tesla security trunk front       # ⚠️ open frunk
tesla security remote-start      # ⚠️ enable keyless driving
```

## Climate Control

```bash
tesla climate on                 # turn on HVAC
tesla climate off                # turn off HVAC
tesla climate set-temp 22        # set target temperature (Celsius)
tesla climate temp               # show current target temp
tesla climate seat driver 3      # seat heater level (0=off, 1-3=heat)
tesla climate seat passenger 2
tesla climate steering-wheel --on
tesla climate steering-wheel --off
```

## Charging Control

```bash
tesla charge start               # start charging
tesla charge stop                # stop charging
tesla charge set-limit 80        # set charge limit (50-100%)
tesla charge set-amps 32         # set charge current (1-48A)
tesla vehicle charge-port open   # open charge port door
tesla vehicle charge-port close  # close charge port door
```

## Windows & Doors

```bash
tesla vehicle windows vent       # vent all windows
tesla vehicle windows close      # close all windows
```

## Sentry Mode

```bash
tesla vehicle sentry             # show current sentry status
tesla vehicle sentry --on        # ⚠️ enable sentry mode
tesla vehicle sentry --off       # ⚠️ disable sentry mode
```

## Other Controls

```bash
tesla vehicle horn               # honk horn
tesla vehicle flash              # flash headlights
tesla vehicle wake               # wake from sleep (~30s)
tesla vehicle homelink           # trigger garage door
tesla vehicle dashcam            # save dashcam clip
tesla vehicle speed-limit --on 90  # set speed limit
tesla vehicle speed-limit --off
```

## Media & Navigation

```bash
tesla media play                 # play/pause media
tesla media next / prev          # skip track
tesla media volume 7             # set volume (0-11)
tesla media send-destination "123 Main St"  # send nav destination
tesla media supercharger         # navigate to nearest Supercharger
tesla media home                 # navigate home
```

## Software Updates

```bash
tesla vehicle software           # check for updates
tesla vehicle software --install # ⚠️ schedule pending OTA update
```

## Important Notes

- The car may be **asleep** — if a command fails with timeout, run `tesla vehicle wake` first and wait ~30s
- **Security commands** (unlock, trunk, remote-start, sentry off) require explicit user confirmation
- All commands support `--vin <alias>` for multi-vehicle setups
- Use natural language mapping: "open the trunk" → `tesla security trunk rear`, "cool down the car" → `tesla climate on`
