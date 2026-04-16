# MIGRATION PLAN — Source-First Tesla Architecture

## Goal

Migrate from a Mission-Control-blob-centered refresh model toward a **source-first / domain-derived** architecture, without breaking the existing product experience.

## Constraints

- Keep `dacrypt/tesla` as one integrated app.
- Keep React Mission Control as the primary UI.
- Avoid big-bang rewrites.
- Preserve working CLI/API paths where possible.
- Prefer additive migration with compatibility layers.

## Current status (2026-04-07)

Completed or materially in progress:
- Phase 1: source registry/current state
- Phase 2: source history + source diffs
- Phase 3: first domain projectors (`delivery`, `legal`, `financial`, `safety`, `identity`, `source_health`)
- Phase 4: persistent events + alerts
- Phase 5: Mission Control read model, dashboard summary, and partial UI rewire
- Phase 6: `refresh-mission-control.py` reduced to compatibility output generation

Remaining gaps:
- broaden domain coverage
- add richer alert lifecycle beyond `ack`/auto-resolve
- finish migrating every UI/CLI consumer off legacy compat expectations
- retire `change-detector.py` or rewrite it on top of source/domain events

---

## Phase 0 — Freeze the direction

### Decision
Stop treating `mission-control-data.json` as the canonical state model.

### Outcome
Any new work should target one of these layers instead:
- source registry / source state
- source diffing
- domain projections
- alerts/events
- derived UI payloads

---

## Phase 1 — Introduce source registry + current state

## Deliverables
- `registry/sources.json`
- `sources/<source_id>.json`
- canonical source metadata model

## Tasks
1. Enumerate the currently active Tesla sources.
2. Assign stable canonical `source_id`s.
3. Normalize current output paths so each source writes its latest state independently.
4. Preserve fetch metadata (`status`, `latency`, `fetched_at`, `error`).

## Success criteria
- Every important source can be refreshed and inspected independently.
- The app no longer depends exclusively on a single aggregate blob to know source state.

---

## Phase 2 — Add per-source history and diff engine

## Deliverables
- `source_history/<source_id>/...`
- `source_diffs/<source_id>.jsonl`
- source-local diff engine

## Tasks
1. On every successful refresh, persist a timestamped snapshot per source.
2. Compare only against that source’s previous successful snapshot.
3. Emit structured diffs with field-level priority.
4. Track source health separately from source data.

## Success criteria
- You can answer: “what changed in `co.runt`?” without loading a global snapshot.
- You can alert directly on source-local events.

---

## Phase 3 — Introduce domain projectors

## Deliverables
- `domains/delivery.json`
- `domains/legal.json`
- `domains/financial.json`
- `domains/safety.json`
- `domains/source_health.json`

## Tasks
1. Map sources → domains.
2. Create projector functions that recompute domain state from current source states.
3. Produce domain summaries + derived readiness flags.
4. Define domain-level semantic changes separately from raw source changes.

## Success criteria
- Delivery/legal/safety can be reasoned about independently from raw transport payloads.
- Mission Control can read domains first, sources second.

---

## Phase 4 — Build alert engine on top of source/domain events

## Deliverables
- `events/events.jsonl`
- `events/alerts.jsonl`
- alert rules registry

## Tasks
1. Convert current hardcoded change detection rules into explicit alert rules.
2. Differentiate between:
   - raw source change
   - semantic domain change
   - source health degradation
3. Emit alert lifecycle events (`triggered`, `resolved`, optionally `acked`).

## Success criteria
- Alerts are explainable and source-aware.
- Notifications no longer depend on scanning a monolithic aggregate diff.

---

## Phase 5 — Rebuild Mission Control as a derived read model

## Deliverables
- `/api/mission-control`
- `/api/dashboard-summary`
- `ui/mission-control.json` (optional materialized cache)

## Tasks
1. Build UI payloads from:
   - source current state
   - domain projections
   - active alerts
   - recent diffs/events
2. Update the React UI to consume those read models.
3. Keep the current UI/visual richness, but swap the data model underneath.

## Success criteria
- React Mission Control stays the main UI.
- The frontend no longer needs `mission-control-data.json` as the architectural center.

---

## Phase 6 — Deprecate blob-centric legacy scripts

## Candidates for deprecation or refactor
- `refresh-mission-control.py`
- `change-detector.py`
- `build-activity-log.sh`
- direct dependence on `mission-control-data.json`

## Replacement concepts
- `refresh-sources.py`
- `source-diff-engine.py`
- `domain-projector.py`
- `alert-engine.py`
- `build-mission-control-view.py`

## Success criteria
- Legacy files become wrappers or compatibility shims.
- The new architecture owns the truth.

---

## Initial source map recommendation

### Delivery domain
- `tesla.tasks`
- `tesla.delivery`
- `tesla.owner.order`
- `co.runt`
- `co.runt_soat`

### Legal domain
- `co.runt`
- `co.simit`
- `co.runt_soat`
- `co.runt_rtm`
- `co.runt_conductor`

### Safety domain
- `us.nhtsa_recalls`
- `us.nhtsa_complaints`
- `us.nhtsa_investigations`
- `co.recalls`

### Identity/config domain
- `tesla.owner.order`
- `vin.decode`
- Tesla config/compositor/order detail sources

### Health domain
- all source runtime statuses

---

## Recommended immediate engineering order

1. Create canonical source IDs and registry.
2. Write current-state-per-source persistence.
3. Add source-local diffing.
4. Build `delivery` + `legal` domain projectors first.
5. Move Telegram/WhatsApp alerts to source/domain event engine.
6. Rewire React Mission Control to use domain + source read models.
7. Leave `mission-control-data.json` only as compatibility output until fully retired.

---

## Short policy statement

> New Tesla monitoring logic should be source-first.
> New UI logic should consume derived read models.
> New alerts should be driven by source and domain events.
> `mission-control-data.json` is a compatibility layer, not the source of truth.
