# VatioLibre vs tesla-cli — Gap Analysis

> Date: 2026-04-08
> Purpose: Identify VatioLibre features worth adopting for our OSS self-hosted model

---

## Philosophy Difference

| | VatioLibre | tesla-cli |
|---|---|---|
| **Model** | SaaS, hosted, subscription | OSS, self-hosted, free |
| **Revenue** | COP ~19K/month (~USD 5) Founders Pass | None (community) |
| **Scope** | Order tracking + drawings | Full vehicle lifecycle (175+ commands) |
| **APIs** | Fleet API + optional Owner API | Fleet + Owner + Tessie + TeslaMate + BLE + MQTT |
| **Control** | Read-only (monitoring) | Read + Write (full vehicle control) |
| **Data** | Their servers | Your machine |

**Bottom line:** VatioLibre is a thin monitoring layer. We are 20x broader. But they have a few UX touches worth stealing.

---

## Feature Comparison

### Where We Already Win

| Feature | tesla-cli | VatioLibre | Notes |
|---------|:---------:|:----------:|-------|
| Order tracking + timeline | ✅ 13-gate tracker | ✅ 5-stage tracker | Ours is more granular |
| VIN decoder | ✅ 11 fields | ✅ similar | Parity |
| Vehicle config/option codes | ✅ 140+ codes | ✅ basic config | We decode far more |
| Order snapshots/history | ✅ diff comparison | ✅ snapshot browser | Ours has diff engine |
| Notifications | ✅ Apprise (100+ channels) | ✅ email only (paid) | Ours is free + way more channels |
| Owner API + Fleet API | ✅ both + Tessie + BLE | ✅ Fleet + optional Owner | We support more backends |
| Theme (dark/light) | ✅ | ✅ | Parity |
| Language/i18n | ✅ 6 languages | ✅ EN/ES | We have more |
| Vehicle control | ✅ 140+ commands | ❌ none | Massive gap in our favor |
| Charging intelligence | ✅ sessions, costs, forecast | ❌ none | |
| Climate control | ✅ full (seats, defrost, dog mode) | ❌ none | |
| Analytics/TeslaMate | ✅ deep integration | ❌ none | |
| Automations | ✅ 9 trigger types | ❌ none | |
| BLE local control | ✅ | ❌ | |
| MQTT/Home Assistant | ✅ | ❌ | |
| Prometheus/Grafana | ✅ 27 gauges | ❌ | |
| Colombia RUNT/SIMIT | ✅ | ❌ | |
| Energy (Powerwall/Solar) | ✅ | ❌ | |
| CLI (tmux/scripts) | ✅ 175+ commands | ❌ web only | |
| REST API | ✅ 143+ endpoints | ❌ no public API | |
| Data export (CSV/JSON/GPX/PDF) | ✅ | ❌ | |

---

## Their Gaps (things they have that we DON'T)

### Gap 1: VatioBoard (In-Car Browser Tools) — ❌ Skip

**What they have:** Drawing canvas, calculator, trip cost estimator, speedometer, drive replay, GPS diagnostics, acceleration timer — all in Tesla's in-car browser.

**Should we build it?** **No.**
- Orthogonal to our mission (vehicle management, not entertainment)
- Tesla's in-car browser is limited and unreliable
- Low strategic value for a self-hosted CLI/API tool
- VatioBoard is already open-source — users can just use it directly

### Gap 2: AI-Powered Order Summary — ⭐ Worth Implementing

**What they have:** An AI icon with a generated summary: "Your Model Y already has a VIN. Your vehicle does not have a license plate yet."

**What we should build:**
- `tesla order summary` CLI command that generates a human-readable summary from structured order data
- No LLM needed — template-based with conditional logic:
  - VIN status (assigned/pending)
  - Delivery window (if available)
  - Next action needed (schedule appointment, upload documents, etc.)
  - Plate/registration status
  - Financing status
- Add to dashboard Order page as a summary card
- Add to `--oneline` output

**Effort:** Small (1-2 hours)
**Value:** High — makes order status instantly understandable

### Gap 3: Share Button (Order Status Sharing) — ⭐ Worth Implementing

**What they have:** macOS share sheet integration — share order summary to Mail, Messages, Notes, Freeform, Journal, Reminders, Copy.

**What we should build:**
- `tesla order share` — generates a shareable text/image summary
- `GET /api/order/share` — returns a formatted summary (text, markdown, or image)
- Dashboard: "Copy summary" button on Order page
- Optional: Generate a simple status card image (PNG) for sharing
- Privacy-conscious: no VIN or personal data in shared output by default, `--include-vin` flag

**Effort:** Small-Medium (2-4 hours)
**Value:** Medium — nice for community sharing, order tracking groups

### Gap 4: Visual VIN Decoder with Color-Coded Positions — ⭐ Worth Implementing

**What they have:** Beautiful visual breakdown where each VIN character is color-coded by field (WMI=blue, Model=purple, Body=green, Safety=yellow, Battery=orange, Motor=red, etc.) with labels underneath.

**What we currently have:** Text-based VIN decode output in CLI and dossier page.

**What we should build:**
- Dashboard: Visual VIN decoder component with color-coded character boxes
- Each position labeled (WMI, MODEL, BODY, SAFETY, BATTERY, MOTOR, CHECK, YEAR, PLANT, SERIAL)
- Expandable detail below (manufacturer, plant location, battery chemistry, etc.)
- Already have all the data in `VinDecode` model — just need the UI component

**Effort:** Small (2-3 hours, UI only)
**Value:** High — makes dossier page much more polished

### Gap 5: Delivery Dashboard Card (Rich Layout) — ⭐ Worth Implementing

**What they have:** A dedicated DELIVERY section with:
- Delivery Center name + address + "Open map" (Google Maps link)
- Delivery Type (Pickup at Service Center)
- Delivery Appointment date/time + "SCHEDULED" badge
- Delivery Window
- Credit Balance + License Plate status (Pending)
- Status message: "Your order is ready for scheduling once Tesla opens appointment booking"

**What we currently have:** `DeliveryCard` in Order.tsx — shows date, location, address, window. But missing: delivery type, credit balance, license plate status, map link, status message.

**What we should build:**
- Enrich `DeliveryCard` with: delivery type badge, credit balance, license plate status, Google Maps link
- These fields are already in the Owner API `_details` data — just need UI rendering
- Add "Open map" link using Google Maps search URL from scheduling data

**Effort:** Small (1-2 hours)
**Value:** High — makes delivery tracking comprehensive

### Gap 6: Delivery Progress Tracker (Task List with States) — ⭐ Worth Implementing

**What they have:** "DELIVERY PROGRESS 4/6" section showing 6 tasks:
- Registration (complete, details: registrant name, type, loan type)
- Agreements (COMPLETE badge, lists signed docs)
- Financing (DEFAULT, loan confirmation message)
- Scheduling (location shown)
- Final Payment (SELF-ARRANGED, shows amounts)
- Delivery Acceptance (pending, "Vehicle ready • Outside appointment window")

**What we currently have:** `TasksCard` in Order.tsx — shows tasks with check/pending icons. But doesn't have: progress counter (4/6), detailed subtitles per task, status badges (COMPLETE, DEFAULT, SELF-ARRANGED), or the rich task descriptions.

**What we should build:**
- Enhanced `TasksCard` with progress counter header (N/M)
- Status badges per task (COMPLETE, DEFAULT, SELF-ARRANGED, etc.)
- Rich subtitle line per task with relevant details
- All data already available in `_details.tasks` from Owner API

**Effort:** Small (1-2 hours)
**Value:** High — gives clear visibility into what's done and what's next

### Gap 7: Order Snapshot History Table — ⭐ Worth Implementing

**What they have:** "Order Snapshot History" table with columns:
- Timestamp, Action (Load Snapshot button), Status, Odometer, Type, Summary, Substatus
- Shows: "04/09/2026 · 12:35 AM | BOOKED | New order detected | _Z"
- "Load Snapshot" button loads historical state into the timeline

**What we currently have:** `OrderTimeline` model with `_save_snapshot()` and `get_history()` in the backend. We save snapshots but don't expose them in the dashboard.

**What we should build:**
- `GET /api/order/snapshots` endpoint returning snapshot history
- Snapshot history card in Order page (table or timeline view)
- "Load snapshot" to view historical state in the tracker
- We already have the backend — just need API route + UI component

**Effort:** Medium (3-4 hours)
**Value:** Medium-High — enables order change tracking visually

### Gap 8: Owner API Connection Status Panel — ✅ Partially Have

**What they have:** Panel showing: Connected email, Status (Active), Expires At, Last Auth, Refresh/Disconnect buttons.

**What we have:** Provider status in Settings page with connection indicators. We could add expiry/last auth details.

**Effort:** Small (30 min)
**Value:** Low — nice to have but not critical

### Gap 9: Subscription/Billing System — ❌ Skip

**What they have:** Stripe integration, Founders Pass, subscriber-only features.

**Should we build it?** **No.**
- We are OSS and self-hosted. No billing needed.
- Our model is: everything free, run on your own hardware.

### Gap 6: Fleet Dashboard "Connected" Status Indicator — ✅ Already Have

We already show provider connection status in Settings page. Parity.

---

## Summary: What to Implement

### Round 1 — DONE (v4.9.1)

| # | Feature | Status | Effort | Impact |
|---|---------|--------|--------|--------|
| 1 | **Smart Order Summary** (template-based, no LLM) | ✅ Done | 1-2h | High |
| 2 | **Visual VIN Decoder** (color-coded UI component) | ✅ Done | 2-3h | High |
| 3 | **Order Share** (copy/export formatted summary) | ✅ Done | 2-4h | Medium |

### Round 2 — Next (discovered from live browsing 2026-04-09)

| # | Feature | Priority | Effort | Impact |
|---|---------|----------|--------|--------|
| 4 | **Rich Delivery Card** (type, map link, credit balance, plate status) | P1 | 1-2h | High |
| 5 | **Enhanced Task Progress** (N/M counter, status badges, rich subtitles) | P1 | 1-2h | High |
| 6 | **Snapshot History Table** (expose existing backend in dashboard) | P2 | 3-4h | Medium-High |
| 7 | **Owner API Status Panel** (expiry, last auth in Settings) | P3 | 30min | Low |

**Round 2 total effort:** ~6-9 hours.

### What NOT to build from VatioLibre:
- ❌ VatioBoard/in-car tools — out of scope
- ❌ Billing/subscription — against our OSS model
- ❌ Hosted SaaS — we are self-hosted by design

---

## Our Overwhelming Advantages

Things VatioLibre will likely never have that we already ship:

1. **Full vehicle control** (140+ commands) — they are read-only
2. **CLI + API + Dashboard** — they only have web
3. **Self-hosted** — user owns their data completely
4. **TeslaMate integration** — deep PostgreSQL analytics
5. **Automation engine** — 9 trigger types with conditions
6. **BLE local control** — works without internet
7. **100+ notification channels** — vs their email-only
8. **Prometheus/Grafana** — production-grade observability
9. **Home Assistant + MQTT** — smart home integration
10. **Colombia-specific** (RUNT, SIMIT, peajes) — and they claim to be Colombia-focused
11. **Energy management** (Powerwall, Solar, tariffs)
12. **Charging intelligence** (sessions, costs, forecasts, CSV export)
13. **15 data sources** with TTL cache — vs their 1 (Fleet API)
14. **Claude Code plugin** — AI-native integration
15. **Fleet Telemetry streaming** — real-time vehicle data

**Conclusion:** VatioLibre is a nice-looking but thin product. The three features worth stealing are cosmetic/UX improvements, not architectural. Our platform is orders of magnitude more capable. The gap analysis confirms we should stay focused on depth and self-hosted excellence, not chase their SaaS model.
