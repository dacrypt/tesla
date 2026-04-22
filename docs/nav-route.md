# Multi-stop navigation (`tesla nav route`) — v4.9.2

`tesla nav route` is the free alternative to ABRP Premium's multi-waypoint
driver. v4.9.2 ships **CRUD + dispatch + manual advance + simulated
auto-advance**. Real auto-advance via Fleet Telemetry is deferred to **v4.9.2.1**
(see the ADR at the bottom of this page).

## What works in v4.9.2

| Feature | Command | Status |
|---|---|---|
| Save a named route of 1–10 waypoints | `tesla nav route create` | ✅ |
| List / show / delete routes | `tesla nav route list / show / delete` | ✅ |
| Refresh stale geocodes (>30 days) | `tesla nav route verify [--write]` | ✅ |
| Dispatch one waypoint at a time (manual) | `tesla nav route next <name>` | ✅ |
| Dispatch all waypoints with synthetic arrivals (tests) | `tesla nav route go <name> --simulate-arrival-after <s>` | ✅ |
| Named address book (reusable in routes) | `tesla nav place save / list / delete` | ✅ |
| Real auto-advance on a driving car | `tesla nav route go <name>` *(no `--simulate-arrival-after`)* | 🕓 **v4.9.2.1** |

## Prerequisites

- VCP paired (`tesla config auth fleet-signed`) — `share` is a signed command.
- Scope `vehicle_cmds` on the Fleet token.
- Run `tesla doctor` — the rows `nav_route_dispatch` and `nav_route_auto_advance`
  explain the state of each layer.

## Quickstart

```bash
# 1) Save a 3-stop route. The second waypoint uses "lat,lon" to bypass Nominatim.
tesla nav route create commute \
  "Calle 100 #19-54, Bogota" \
  "4.6487,-74.0672" \
  "Centro Andino"

# 2) Inspect cached coords (no network call).
tesla nav route show commute

# 3) Dry-run the plan (prints every leg, calls no APIs).
tesla nav route go commute --dry-run

# 4a) Live trip, manual advance between legs — works today:
tesla nav route next commute         # dispatches waypoint 1
# ... drive to waypoint 1, then when you're ready:
tesla nav route next commute         # dispatches waypoint 2
tesla nav route next commute         # dispatches waypoint 3 → "Trip complete"

# 4b) End-to-end simulation for tests / demos:
tesla nav route go commute --simulate-arrival-after 30
```

## Command reference

### `tesla nav route create <name> <addresses...>`

- `<name>` must match `^[a-z0-9_-]{1,32}$` (e.g. `commute`, `weekend-loop`).
- Each address is either free text (Nominatim-geocoded) or a `"lat,lon"` pair
  (short-circuit: zero Nominatim calls).
- `--max-geocode` caps Nominatim network calls (default **10**; warns past 5).
- If >10 addresses need geocoding, the command aborts before writing anything:
  `route create: too many unresolved addresses (N > 10). Pre-geocode with
  'lat,lon' syntax or split into multiple routes.`

### `tesla nav route go <name>`

Blocking driver. Sends each waypoint via the signed `share` command, then waits
for arrival before advancing.

| Flag | Default | Purpose |
|---|---|---|
| `--tolerance <m>` | 150 | Arrival radius in meters. |
| `--dry-run` | off | Print plan without touching the car. |
| `--simulate-arrival-after <s>` | *unset* | [TEST ONLY] Fire a synthetic arrival event after N seconds. No real telemetry is read. |
| `--start-from <idx>` | 1 | Resume from waypoint `<idx>` (1-based). |
| `--max-wait <min>` | 45 | Per-waypoint max wait before giving up. |

**Without `--simulate-arrival-after`, `go` exits 2** with a yellow hint pointing
at `tesla nav route next <name>`. Real auto-advance ships in v4.9.2.1 —
see ADR-012 below.

**Exit codes:**
- `0` — trip complete (all waypoints dispatched + arrived)
- `130` — `SIGINT` (Ctrl-C); prints `cancelled at waypoint N/M` on stderr
- `1` — dispatch / API error
- `2` — auto-advance unavailable or arrival source lost

### `tesla nav route next <name>`

Manually dispatches the next un-visited waypoint of `<name>`. State is persisted
in `~/.tesla-cli/nav.state.toml` via atomic `tmp + fsync + rename`. After the
last waypoint, `next_index` resets to 1 and the command prints
`Trip complete`.

### `tesla nav route verify <name>`

Re-geocodes waypoints whose `geocode_at` is older than **30 days**.

- Without `--write`: prints stale entries only. Exits 0. `nav.toml` untouched.
- With `--write`: re-geocodes stale entries in place, saves atomically. No
  interactive prompt, no diff UI — the 30-day threshold is the whole contract.

### `tesla nav place save/list/delete`

A separate address book. Saved places can be referenced by alias as arguments
to `tesla nav route create`.

```bash
tesla nav place save home "Calle 100 #19-54, Bogota"
tesla nav place save work "4.6487,-74.0672"
tesla nav route create daily home work
```

## Storage layout

```
~/.tesla-cli/
  nav.toml           # routes + places (source of truth, TOML)
  nav.state.toml     # next_index counter per route (used by `nav route next`)
```

Writes are atomic: serialize to `<path>.tmp`, `fsync`, then `os.rename` over
the real path. Single-user CLI — no lockfile.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `route create: address '...' could not be geocoded by Nominatim (404).` | Try a different spelling, or use `"lat,lon"` syntax. |
| `route create: Nominatim rate limit (429).` | Wait 60s; or pre-geocode offline and pass `"lat,lon"`. |
| `route create: too many unresolved addresses (N > 10).` | Split the route or provide some waypoints as `"lat,lon"`. |
| `Auto-advance not available in v4.9.2.` | Expected — use `nav route next <name>` between legs, or `--simulate-arrival-after` for testing. Real auto-advance ships in v4.9.2.1. |
| `cancelled at waypoint N/M` (exit 130) | You pressed Ctrl-C. State is preserved; re-run with `--start-from N`. |

## Related docs

- `docs/fleet-signed-setup.md` — how to get `share` working (VCP pairing).
- `docs/roadmap.md` — v4.9.2.1 plan (real `TelemetryArrivalSource`).
- `.omc/plans/nav-route-telemetry.md` — full design + ADR-012.

## ADR-012 — Why the split?

**Decision:** Ship manual-advance now (v4.9.2). Defer real `TelemetryArrivalSource`
to v4.9.2.1.

**Why:** the in-repo Fleet Telemetry compose template exposes only port 4443
(Tesla → receiver ingress). There is no downstream publisher (no Kafka / NATS /
SSE) today, so the subscriber can't be built in the same PR without blowing the
180-min cap. `NullArrivalSource` + `tesla nav route next` give 100% of the
ABRP-Premium UX minus one keypress.

**Consequences:**
- `nav route next` stays useful even after v4.9.2.1 lands (receiver outages,
  dead-zone driving, debugging).
- `ArrivalSource` protocol lets v4.9.2.1 plug in a real subscriber with zero
  changes to the detector, dispatcher, or CLI.

Full rationale: `.omc/plans/nav-route-telemetry.md` §7.
