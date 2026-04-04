---
name: order
description: >
  Tesla order tracking — delivery status, ETA, gates, ship tracking, inspection
  checklist. Use when someone asks about their Tesla order, delivery date,
  order status, when their car arrives, delivery appointment, or tracking.
argument-hint: "[query: status|delivery|eta|gates|watch|checklist|ships]"
allowed-tools: Bash(tesla *)
---

# Tesla Order Tracking

Track your Tesla order from placement through delivery.

## Order Status

```bash
tesla order status               # current status, VIN, model, delivery window
tesla order details              # full: status + tasks + vehicle + delivery + financing
tesla order delivery             # delivery appointment (date, time, location)
```

## Delivery Intelligence

```bash
tesla order eta                  # delivery ETA (best/typical/worst estimates)
tesla order gates                # 13-gate delivery journey tracker
tesla order estimate             # community-based delivery date estimation
tesla order stores               # nearby Tesla stores/Service Centers
tesla order stores --near 4.6,-74.1  # stores near coordinates
```

## Ship Tracking

```bash
tesla dossier ships              # Tesla car carrier vessel positions
```

## Delivery Prep

```bash
tesla order checklist            # 34-item delivery inspection checklist
tesla order checklist --mark 5,12  # check off items during inspection
tesla order set-delivery 2026-04-15  # set confirmed delivery date
```

## Continuous Monitoring

```bash
tesla order watch                # monitor every 10 min with notifications
tesla order watch -i 5           # every 5 minutes
tesla order watch --no-notify    # without push notifications
tesla order watch --on-change-exec "echo changed"  # shell hook
```

## Response Guidelines

- Start with the **current order status** and **delivery date** if available
- Show the gate progress (which of 13 gates have been passed)
- If the car hasn't been delivered yet, include ETA estimates
- If delivery is upcoming, suggest the checklist
- For `$ARGUMENTS`:
  - "status" / no args → `tesla order status` + `tesla order delivery`
  - "delivery" → `tesla order delivery`
  - "eta" / "when" → `tesla order eta`
  - "gates" / "progress" → `tesla order gates`
  - "watch" → `tesla order watch`
  - "checklist" / "inspect" → `tesla order checklist`
  - "ships" / "shipping" → `tesla dossier ships`
