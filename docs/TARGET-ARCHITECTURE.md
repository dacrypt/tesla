# TARGET ARCHITECTURE — dacrypt/tesla

## Principle

`dacrypt/tesla` remains the **ultimate app**:
- CLI
- API
- React Mission Control UI
- alerts
- exports
- automation

The product stays integrated. The change is internal architecture: the system should be **source-first**, not blob-first.

## Core doctrine

- **Product center:** `dacrypt/tesla`
- **Human interface center:** React Mission Control
- **Truth center:** independent sources + per-source history/diff + derived domain state
- **Legacy compatibility:** `mission-control-data.json` may remain temporarily as a derived UI payload, not as the primary truth store

## Implementation status (2026-04-07)

Already implemented in the repo:
- source registry + independent source cache
- source history + source diffs
- domain projections for `delivery`, `legal`, `financial`, `safety`, `identity`, and `source_health`
- Mission Control read model and dashboard summary
- persistent `events.jsonl` and `alerts.jsonl`
- `/api/sources`, `/api/domains`, `/api/events`, `/api/alerts`, `/api/mission-control`
- pre-delivery dashboard rewired to Mission Control read models
- `refresh-mission-control.py` demoted to a derived compatibility wrapper
- `mission-control-data.json` is now compatibility-only and derived

Still pending:
- richer domain coverage (`financial`, `safety`, `identity`, `source_health`)
- alert acknowledgement lifecycle
- full UI consumption of real alerts/timeline
- retirement or reduction of `change-detector.py`

---

## Layer 1 — Source Intelligence Layer

Primary unit: **Source**.

Each source must support:
- definition/registry metadata
- independent refresh
- normalized current state
- previous state lookup
- diff against previous state
- freshness/health/error tracking
- audit artifacts where relevant
- alert rules / severity mapping

### Canonical examples
- `tesla.owner.order`
- `tesla.tasks`
- `tesla.delivery`
- `co.runt`
- `co.simit`
- `us.nhtsa_recalls`
- `us.nhtsa_complaints`
- `us.epa_fuel_economy`

### Canonical source entities

#### SourceDefinition
- `source_id`
- `display_name`
- `provider`
- `domain_tags`
- `priority`
- `refresh_policy`
- `freshness_ttl`
- `supports_audit`
- `supports_diff`
- `normalizer`
- `alert_policy`

#### SourceSnapshot
- `source_id`
- `snapshot_id`
- `fetched_at`
- `status` (`ok|error|partial|stale`)
- `latency_ms`
- `data`
- `data_hash`
- `error`
- `meta`
- `audit_refs`

#### SourceDiff
- `source_id`
- `previous_snapshot_id`
- `current_snapshot_id`
- `detected_at`
- `changed`
- `changes[]`
- `priority`
- `semantic_summary`

Each `changes[]` item should contain:
- `field`
- `old`
- `new`
- `kind`
- `priority`

---

## Layer 2 — Domain Projection Layer

Independent source data is projected into **domain state**.

Domains are semantic, not transport-specific.

### Recommended domain projections
- `delivery`
- `legal`
- `financial`
- `safety`
- `identity`
- `vehicle_config`
- `source_health`

### Example
`delivery` may derive from:
- `tesla.tasks`
- `tesla.delivery`
- `co.runt`
- `co.runt_soat`
- `co.simit` (supporting)

### DomainProjection shape
- `domain_id`
- `computed_at`
- `inputs`
- `state`
- `derived_flags`
- `summary`
- `health`

---

## Layer 3 — Events and Alerts

Changes should generate **events** and optionally **alerts**.

### Event types
- `source_change`
- `domain_change`
- `source_error`
- `source_recovered`
- `alert_triggered`
- `alert_resolved`

### AlertEvent shape
- `event_id`
- `kind`
- `source_id`
- `domain_id`
- `severity`
- `title`
- `message`
- `diff_refs`
- `created_at`
- `resolved_at`

### Example alert rules
- `co.runt.placa` changes from empty → non-empty → **critical**
- `co.runt.prendas` changes false → true → **critical**
- `co.simit.total_deuda` increases above 0 → **high**
- `tesla.delivery.appointment` changes → **critical**
- critical source fails repeatedly → **warning/high**

---

## Layer 4 — Product Interfaces

These are consumers of the source/domain system:
- CLI
- FastAPI
- React UI
- PDFs / exports
- notifications
- cron/watchers

These should not own the truth model.

---

## Storage layout

Recommended local structure under `~/.tesla-cli/`:

```text
registry/sources.json
sources/<source_id>.json
source_history/<source_id>/<timestamp>.json
source_diffs/<source_id>.jsonl
source_audits/<source_id>/<timestamp>.json
source_audits/<source_id>/<timestamp>.pdf
source_audits/<source_id>/<timestamp>.png
domains/<domain_id>.json
events/events.jsonl
events/alerts.jsonl
ui/mission-control.json
ui/dashboard-summary.json
```

---

## API target shape

### Sources
- `GET /api/sources`
- `GET /api/sources/:id`
- `GET /api/sources/:id/history`
- `GET /api/sources/:id/diffs`
- `POST /api/sources/:id/refresh`

### Domains
- `GET /api/domains`
- `GET /api/domains/:id`

### Events / alerts
- `GET /api/events`
- `GET /api/alerts`
- `POST /api/alerts/:id/ack`

### UI aggregate / view model
- `GET /api/mission-control`
- `GET /api/dashboard-summary`

These endpoints are derived/read-model interfaces, not primary persistence.

---

## CLI target shape

### Source-centric
```bash
tesla source list
tesla source show co.runt
tesla source refresh co.runt
tesla source history co.runt
tesla source diff co.runt
tesla source health
```

### Domain-centric
```bash
tesla domain list
tesla domain show delivery
tesla domain show legal
```

### Events / alerts
```bash
tesla alerts
tesla events
tesla watch
```

Legacy/product commands remain valid (`tesla order`, `tesla vehicle`, `tesla serve`, etc.).

---

## React Mission Control target

Mission Control remains the primary human interface.

### It should show
- executive delivery readiness
- legal readiness
- safety posture
- active alerts
- source freshness/health
- recent important diffs
- timeline of events
- drill-down by source and by domain

### Recommended routes
- `/` → Executive Mission Control
- `/sources`
- `/sources/:id`
- `/domains`
- `/alerts`
- `/timeline`
- `/order`
- `/vehicle`
- `/dossier`

### Important rule
Mission Control is the best **view**, not the primary **truth store**.

---

## Role of `mission-control-data.json`

Current status: legacy aggregate snapshot.

Target status: **derived materialized view** used by:
- legacy React paths
- exports/PDFs
- temporary compatibility

It should not remain the canonical origin for diffing or alerting.

---

## Architectural anti-patterns to avoid

### Anti-pattern 1
Treating the entire system state as one monolithic JSON blob.

### Anti-pattern 2
Making the dashboard structure define the storage model.

### Anti-pattern 3
Diffing the whole world before understanding source-local changes.

### Anti-pattern 4
Mixing health, render payload, and semantic truth in one artifact.

---

## Target statement

> `dacrypt/tesla` is the super app.
> React Mission Control is the primary interface.
> The truth of the system lives in independent sources, per-source history/diff, derived domain state, and differential alerting.
> `mission-control-data.json` becomes a derived view, not the core of the system.
