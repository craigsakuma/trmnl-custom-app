# TRMNL Custom App — Architecture & Design Decisions

> Context document for Claude Code. Captures the design decisions, platform
> constraints, and reference snippets for this project. Reference this from the
> root `CLAUDE.md` rather than inlining it, to keep the root lean.

## 1. Overview

A custom TRMNL (e-ink) application that displays **time-of-day-scheduled
screens** — different content in different windows of the day (e.g. a morning
brief 08:00–08:15, standup 08:15–08:30, etc.).

The design uses a **single TRMNL private plugin** on the **Polling** strategy.
A **monolithic Liquid template** branches on a `slot` value to pick the layout.
A **FastAPI** backend computes the current slot from wall-clock time and returns
the slot + data as JSON. The Liquid template is **deployed to TRMNL via a GitHub
Action** so template changes ship from `git push`.

## 2. Stack

|Layer          |Choice                                                                    |
|---------------|--------------------------------------------------------------------------|
|Device         |TRMNL e-ink, 800×480, 1-bit                                               |
|Plugin         |One TRMNL Private Plugin, **Polling** strategy                            |
|Template       |One monolithic Liquid template, slot-based branching                      |
|Backend        |**FastAPI** (Python)                                                      |
|Backend hosting|Always-on instance (Railway / Fly) — avoids cold starts                   |
|Template deploy|`trmnlp` CLI run from GitHub Actions on push to `main`                    |
|Dev assist     |Claude Code (+ optional “TRMNL Display Manager” skill for interactive ops)|

## 3. How TRMNL works (the constraints that drive every decision)

- **Two independent timers.** (a) The *device wake cadence* — how often the
  device wakes, fetches, and displays. (b) The *server-side screen generation* —
  TRMNL re-renders the plugin on its own schedule, independent of device wakes.
- **Device wake is a fixed-interval chain, not a wall clock.** Each wake is
  ~N minutes after the *previous* wake; the phase is set by the last reset
  (power-on, button press, refresh-rate change). It does **not** align to
  :00/:15/:30. There is small drift from network + processing.
- **2-second timeout.** Any endpoint TRMNL calls (polling or redirect) must
  respond in under 2 seconds or it’s treated as a failure. → No slow work at
  request time.
- **Minimum device refresh ≈ 5 min** (default 15). More frequent wakes = faster
  battery drain (device targets months of battery life).
- **Redraw diffing.** TRMNL skips re-drawing the e-ink when the rendered screen
  is unchanged between requests (keyed on an image/filename identifier). Result:
  waking on identical content costs no flicker and minimal battery.
- **Sleep Mode.** A configurable start/end window during which the device does
  not wake at all — no requests, no battery use. E-ink holds the last image at
  zero power.

## 4. Architecture decisions (ADR-style)

### 4.1 Single polling plugin over the native Playlist Scheduler

TRMNL *can* schedule which plugin shows by time of day via the Playlist
Scheduler UI. We chose a single polling plugin with the logic in code because:

- Scheduling logic lives in Python (versioned, testable), not the TRMNL UI.
- No schedule drift — the API evaluates wall-clock time fresh on every request.
- Data and layout selection live in one place.

### 4.2 Polling strategy over the Redirect plugin

- **Polling** = TRMNL calls our endpoint for *data*, then renders our Liquid
  template itself. We keep TRMNL’s rendering + design system for free.
- **Redirect** = we return a pre-rendered image URL + a per-response sleep time.
  More control over wake timing, but we’d have to render images ourselves.
- **Tradeoff accepted:** Polling does **not** let us set the wait time per
  response (that’s a Redirect-only feature). The plugin refresh rate is fixed in
  the TRMNL UI. At a 5-minute fixed cadence this is fine — we don’t need
  boundary-precise wakes.

### 4.3 FastAPI / Python over Cloudflare Workers / TS

- Cloudflare Workers is excellent for the *simple* case: zero cold start,
  100k req/day free. But it’s a constrained V8 runtime, not native Python.
- We expect to grow into **complex Python tooling** (LLM calls, live-news search
  - summaries, RAG, agents). FastAPI keeps that in our existing Python
    ecosystem. Hosting on an always-on instance also sidesteps cold-start risk
    against the 2s timeout.

### 4.4 Monolithic Liquid template with slot branching

One template, `{% if slot == "..." %}` blocks per layout. Simpler to deploy and
reason about than many plugins; the API decides which branch renders.

### 4.5 Decouple generation from serving for slow work

Any feature whose generation exceeds ~2s (e.g. live-news LLM summary) must **not**
run inside the request TRMNL makes. Pattern:

1. A **background job** (cron/worker) does the slow LLM + news work on its own
   schedule (e.g. every 15–30 min).
1. It writes the finished result to a store (Postgres / Redis / KV / JSON blob).
1. The **request-time endpoint** only *reads* the latest precomputed result and
   returns instantly.

This also provides graceful failure: if an upstream search/LLM call errors, the
device keeps showing the last good screen instead of timing out.

## 5. Data flow

```
Device (every ~5 min)  ──wake──►  TRMNL /api/display  ──►  serves current rendered screen
                                        ▲
TRMNL (per plugin refresh rate) ──poll──┘──►  GET  https://<api>/trmnl
                                                     └─ returns { slot, ...data }
                                              TRMNL merges JSON into Liquid → renders screen
```

**Dual-cadence note:** the *device wake* and the *plugin data poll* are separate
schedules. Set **both** to ~5 min so the rendered screen reflects the current
slot by the time the device picks it up. The slot is computed in the API from
the current time, so whenever the device wakes it gets content correct to within
one refresh.

## 6. Slot scheduling logic

- FastAPI computes the current slot from **timezone-aware** wall-clock time and
  returns `slot` + the data for that slot.
- The Liquid template branches on `{{ slot }}`.
- **Outside scheduled hours** → return a default/blank/clock screen (the device
  still wakes every 5 min until Sleep Mode).
- **Overnight** → TRMNL **Sleep Mode** stops wakes entirely (e.g. 23:00–07:00).
  Ensure the last daytime slot ends a refresh cycle before sleep begins so the
  device doesn’t sleep mid-transition.

## 7. Reference snippets

### 7.1 FastAPI polling endpoint (sketch)

```python
from datetime import datetime, time
from zoneinfo import ZoneInfo
from fastapi import FastAPI

app = FastAPI()
TZ = ZoneInfo("America/Los_Angeles")

SLOTS = [
    {"start": (8, 0),  "end": (8, 15), "id": "morning_brief"},
    {"start": (8, 15), "end": (8, 30), "id": "standup"},
    {"start": (8, 30), "end": (9, 0),  "id": "focus_block"},
    # ...
]

def current_slot(now: datetime):
    t = (now.hour, now.minute)
    for s in SLOTS:
        if s["start"] <= t < s["end"]:
            return s
    return {"id": "default"}

def fetch_slot_data(slot_id: str) -> dict:
    # Read PRE-COMPUTED data from a store. Keep this fast (<2s).
    # Slow work (LLM/news) happens in a separate background job.
    return {}

@app.get("/trmnl")
def trmnl():
    now = datetime.now(TZ)
    slot = current_slot(now)
    # NOTE: polling does NOT return refresh_rate (that's Redirect-only).
    # The plugin refresh rate is configured in the TRMNL UI.
    # TODO: confirm how TRMNL namespaces these keys in Liquid for this plugin.
    return {"slot": slot["id"], **fetch_slot_data(slot["id"])}
```

### 7.2 Monolithic Liquid template (skeleton)

```liquid
{% if slot == "morning_brief" %}
  <!-- morning brief layout, uses {{ ... }} from the API -->
{% elsif slot == "standup" %}
  <!-- standup layout -->
{% elsif slot == "focus_block" %}
  <!-- focus layout -->
{% else %}
  <!-- default / clock screen -->
{% endif %}
```

### 7.3 GitHub Action — deploy template to TRMNL

```yaml
name: Deploy TRMNL plugin
on:
  push:
    branches: [main]
    paths: ['src/**']      # only when the template changes
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.x'
      - run: gem install trmnl_preview
      - run: trmnlp push
        env:
          TRMNL_API_KEY: ${{ secrets.TRMNL_API_KEY }}   # repo secret
```

`trmnlp` is a Ruby gem (`trmnl_preview`). In CI, set `$TRMNL_API_KEY` instead of
running `trmnlp login`. Alternative: run the `trmnl/trmnlp` Docker image instead
of installing Ruby.

### 7.4 `trmnlp` CLI workflow

```
trmnlp login                   # auth (saves key to ~/.config/trmnlp/config.yml)
trmnlp clone <name> <id>       # download an existing web-editor plugin
trmnlp serve                   # local dev server w/ live preview (HTML or PNG)
trmnlp push                    # upload markup to TRMNL
```

### 7.5 Plugin repo structure (per `trmnlp`)

```
.
├── .trmnlp.yml            # local dev config (watch, time_zone, variable overrides)
└── src
    ├── full.liquid        # main template
    ├── half_horizontal.liquid
    ├── half_vertical.liquid
    ├── quadrant.liquid
    ├── shared.liquid      # reusable components
    └── settings.yml       # plugin config (strategy = polling, polling URL, etc.)
```

> PNG preview in `trmnlp serve` needs Firefox + ImageMagick installed.

### 7.6 Key limits / facts

|Thing                 |Value                                  |
|----------------------|---------------------------------------|
|Display               |800×480, 1-bit                         |
|Endpoint timeout      |2 seconds (polling & redirect)         |
|Min device refresh    |~5 min (default 15)                    |
|Webhook payload cap   |2 KB free / 5 KB TRMNL+                |
|Webhook rate limit    |12/hr free, 30/hr TRMNL+               |
|Redirect dynamic sleep|down to 1×/min (Redirect strategy only)|
|Sleep Mode            |configurable window; no wakes/requests |

## 8. Open questions / next steps

- **News-summary freshness:** per-wake fresh vs background-regenerated every
  15–30 min. Determines how hard we lean on the background tier (§4.5).
- **Template render mode:** HTML vs PNG accuracy in `trmnlp` previews.
- **Failure behavior:** confirm the device shows the last good screen on upstream
  error; make `fetch_slot_data` fail soft.
- **Hosting:** Railway (reuse existing infra) vs Fly. Both always-on.
- **Merge-variable shape:** verify exactly how the polling JSON is exposed /
  namespaced inside the Liquid template.
- **PR previews:** optionally render the template in CI on PRs before merge.