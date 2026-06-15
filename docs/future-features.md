# TRMNL Custom App — Future Features & Ideas

> **Brainstorming doc — speculative, not current design.** Committed work lives
> in YouTrack (project `TCA`); [`ARCHITECTURE.md`](../ARCHITECTURE.md) describes
> only what the current v1 issues implement. Ideas here may change or never
> ship. When one matures, it graduates into YouTrack issues (a new phase) and
> this entry should point at them.
>
> **Status legend:** `Idea` (raw) · `Exploring` (actively considering) ·
> `Planned` (committed, will be ticketed) · `Deferred` (parked).

## Slow-work background tier

**Status:** Exploring · _added 2026-06-15_

Any feature whose generation exceeds the ~2s TRMNL timeout (e.g. a live-news LLM
summary) must **not** run inside the request TRMNL makes. Pattern:

1. A **background job** (cron/worker) does the slow LLM + news work on its own
   schedule (e.g. every 15–30 min).
2. It writes the finished result to a **store** (Postgres / Redis / KV / JSON blob).
3. The **request-time endpoint** only *reads* the latest precomputed result and
   returns instantly.

Also gives graceful failure: if an upstream search/LLM call errors, the device
keeps showing the last good screen instead of timing out.

- **On Railway:** run as a separate service — cron service vs always-on worker.
- **Open questions:** store choice (Postgres / Redis / JSON blob); exactly how
  the request endpoint fails soft when no precomputed result exists.

> The fast-read-only **principle** that this implies already shapes the v1 API —
> see ARCHITECTURE.md §4.5. Only the slow tier itself is deferred.

## Named time-window slots (richer scheduling)

**Status:** Exploring · _added 2026-06-15_

Replace v1's hour-parity rule with a table of named slots bound to time windows:

```python
SLOTS = [
    {"start": (8, 0),  "end": (8, 15), "id": "morning_brief"},
    {"start": (8, 15), "end": (8, 30), "id": "standup"},
    # ...
]   # fall back to {"id": "default"} outside any window
```

The Liquid template's `{% if slot == "..." %}` pattern extends to each named
slot. Brings in two related behaviors:

- **Default / clock screen** outside scheduled hours (the device still wakes
  ~5 min until Sleep Mode).
- **Overnight Sleep Mode** (e.g. 23:00–07:00) — no wakes; ensure the last
  daytime slot ends a refresh cycle before sleep begins so the device doesn't
  sleep mid-transition.

## News-summary freshness

**Status:** Idea · _added 2026-06-15_

Per-wake fresh vs background-regenerated every 15–30 min. Determines how hard we
lean on the background tier above.

## Template render mode

**Status:** Idea · _added 2026-06-15_

HTML vs PNG accuracy in `trmnlp` previews — which to trust for design fidelity.

## PR template previews in CI

**Status:** Idea · _added 2026-06-15_

Optionally render the template in CI on PRs before merge, so reviewers see the
rendered screen.
