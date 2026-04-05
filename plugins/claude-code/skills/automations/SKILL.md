---
name: automations
description: >
  Tesla automation rules — create triggers that fire notifications or commands
  when vehicle state changes. Battery alerts, charge complete, sentry events.
argument-hint: "[action: list|add|remove|run|test|status]"
allowed-tools: Bash(tesla *)
level: 2
---

# Tesla Automations

Rule-based automation engine that monitors vehicle state and fires notifications or shell commands when conditions are met.

## List Rules

```bash
tesla automations list           # show all configured rules (name, trigger, action, enabled)
tesla automations list --json    # machine-readable output
```

## Add Rules

```bash
tesla automations add            # interactive wizard (name, trigger, condition, action)
```

Rules have three parts: a **trigger** (what to watch), a **condition** (threshold/value), and an **action** (notify or run command).

## Default Rules

The following rules are available out of the box:

| Rule name           | Trigger              | Default condition  | Action            |
|---------------------|----------------------|--------------------|-------------------|
| `battery_below`     | battery SoC          | < 20%              | push notification |
| `charging_complete` | charge state         | becomes `Complete` | push notification |
| `sentry_event`      | sentry mode          | new event detected | push notification |

```bash
tesla automations add --preset battery_below    # add the 20% low-battery alert
tesla automations add --preset charging_complete
tesla automations add --preset sentry_event
```

## Remove Rules

```bash
tesla automations remove <name>  # delete a rule by name
tesla automations enable <name>  # re-enable a disabled rule
tesla automations disable <name> # disable without deleting
```

## Run Daemon

```bash
tesla automations run            # start the rules daemon (foreground)
tesla automations run --source auto  # auto-select best data source (TeslaMate → Fleet → Owner)
tesla automations run --interval 60  # poll every 60 seconds (default: 30)
```

The daemon polls vehicle state on the configured interval and evaluates all enabled rules.

## Install as System Service

```bash
tesla automations install        # install as launchd (macOS) or systemd (Linux) service
tesla automations uninstall      # remove the service
```

## Test a Rule

```bash
tesla automations test <name>    # fire the rule action once, regardless of conditions
```

Use this to verify notification delivery before enabling the rule in the daemon.

## Status

```bash
tesla automations status         # daemon running? last evaluation? last fired rule?
```

## Response Guidelines

- If the CLI is not configured (no VIN, no auth), **stop and tell the user to run `/tesla:setup`** — never auto-configure
- List rules first before suggesting add/remove operations
- Suggest presets for the three most common use cases (battery_below, charging_complete, sentry_event)
- Remind the user the daemon must be running (or installed as a service) for rules to fire
- For `$ARGUMENTS`:
  - "list" / no args → `tesla automations list`
  - "add" / "create" / "new" → `tesla automations add`
  - "remove" / "delete" → `tesla automations remove <name>`
  - "run" / "start" / "daemon" → `tesla automations run`
  - "install" / "service" → `tesla automations install`
  - "test" → `tesla automations test <name>`
  - "status" → `tesla automations status`
