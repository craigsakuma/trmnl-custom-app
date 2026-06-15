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
A **FastAPI** backend (hosted on **Railway**) computes the current slot from
wall-clock time and returns the slot + data as JSON. The Liquid template is
**deployed to TRMNL via a GitHub Action** so template changes ship from
`git push`.

### v1 scope (current)

v1 is the **foundation only** — it proves the end-to-end pipeline with the
simplest possible content, before we invest in richer screens or the slow
background tier (future work — see [`docs/future-features.md`](docs/future-features.md)):

- **Two slots that alternate by the hour** (`America/Los_Angeles`): **even hour
  → slot `A`**, **odd hour → slot `B`** (08:00→A, 09:00→B, 10:00→A, …).
- **Static quotes** returned from the FastAPI endpoint (not hardcoded in the
  template) so the full data-flow is exercised:
  - `A` → "Eyes on the Prize. Finish Travel Roboto"
  - `B` → "Having Kiran's Love Makes Me the Luckiest Man in the World."
- **No data store, no LLM/news** yet. CI auto-deploys the template from day one.

Once the infrastructure is proven, the next phase customizes the Liquid layouts
and populates the API with real, scheduled content (weather, calendar, news,
etc.). Execution is tracked as YouTrack issues — see §9.

## 2. Stack

|Layer          |Choice                                                                    |
|---------------|--------------------------------------------------------------------------|
|Device         |TRMNL e-ink, 800×480, 1-bit                                               |
|Plugin         |One TRMNL Private Plugin, **Polling** strategy                            |
|Template       |One monolithic Liquid template, slot-based branching                      |
|Backend        |**FastAPI** (Python)                                                      |
|Backend hosting|**Railway** (always-on) — avoids cold starts against the 2s timeout       |
|Template deploy|`trmnlp` CLI run from GitHub Actions on push to `main`                    |
|Source / CI    |Public GitHub repo `craigsakuma/trmnl-custom-app` + GitHub Actions        |
|Project mgmt   |YouTrack project **TCA**; one branch per issue (`TCA-<n>-<slug>`)         |
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
- **Merge-variable shape (resolved):** with Polling, TRMNL injects the JSON
  response at the **Liquid root**. A **flat** payload like
  `{ "slot": "A", "quote": "..." }` is read directly as `{{ slot }}` /
  `{{ quote }}`; a nested payload (`{ "data": {...} }`) needs dot access
  (`{{ data.x }}`). TRMNL’s own globals live under the `{{ trmnl }}` namespace.
  → We return a **flat** payload.

### 4.3 FastAPI / Python over Cloudflare Workers / TS

- Cloudflare Workers is excellent for the *simple* case: zero cold start,
  100k req/day free. But it’s a constrained V8 runtime, not native Python.
- We expect to grow into **complex Python tooling** (LLM calls, live-news search
  - summaries, RAG, agents). FastAPI keeps that in our existing Python
    ecosystem. Hosting on an always-on instance also sidesteps cold-start risk
    against the 2s timeout.
- **Hosting decided: Railway** (always-on service). Reuses existing infra and
  keeps the 2s budget safe. A future slow-work tier (§4.5) can run as a separate
  Railway service (cron or always-on worker).

### 4.4 Monolithic Liquid template with slot branching

One template, `{% if slot == "..." %}` blocks per layout. Simpler to deploy and
reason about than many plugins; the API decides which branch renders.

### 4.5 Decouple generation from serving for slow work

**Principle (shapes the current API):** the request-time endpoint stays fast
(<2s) and only *reads* — any slow generation (LLM/news) must run out-of-band and
write a result the endpoint reads, never inside the request TRMNL makes. v1 has
no slow work; the full background-tier design (job cadence, store, fail-soft) is
future work — see [`docs/future-features.md`](docs/future-features.md).

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
- **v1 rule:** slot is chosen by **hour parity** — `A` on even hours, `B` on
  odd hours — all day, every day. Intentionally trivial, to validate the
  pipeline end-to-end.

> The richer design — named time-window slots, a default/clock screen outside
> scheduled hours, and overnight Sleep Mode — is future work. See
> [`docs/future-features.md`](docs/future-features.md).

## 7. Reference snippets

### 7.1 FastAPI polling endpoint (sketch)

v1 (hour-parity, static quotes):

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI

app = FastAPI()
TZ = ZoneInfo("America/Los_Angeles")

QUOTES = {
    "A": "Eyes on the Prize. Finish Travel Roboto",
    "B": "Having Kiran's Love Makes Me the Luckiest Man in the World.",
}

def current_slot(now: datetime) -> str:
    return "A" if now.hour % 2 == 0 else "B"

@app.get("/trmnl")
def trmnl():
    slot = current_slot(datetime.now(TZ))
    # Flat payload → exposed at the Liquid root: {{ slot }}, {{ quote }}.
    # Polling does NOT return refresh_rate (Redirect-only); the refresh rate is
    # set in the TRMNL UI.
    return {"slot": slot, "quote": QUOTES[slot]}
```

### 7.2 Monolithic Liquid template (skeleton)

v1 (two slots, quote from the API at the Liquid root):

```liquid
{% if slot == "A" %}
  <!-- layout A: render {{ quote }} -->
{% elsif slot == "B" %}
  <!-- layout B: render {{ quote }} -->
{% else %}
  <!-- default / clock screen -->
{% endif %}
```

### 7.3 GitHub Action — deploy template to TRMNL

The `trmnlp` repo ships a ready-made workflow: **`trmnlp lint` on PRs** (gate
merges) and **`trmnlp push --force` on `main`**. Sketch:

```yaml
name: TRMNL
on:
  push:
    branches: [main]
  pull_request:
jobs:
  lint:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ruby/setup-ruby@v1
        with: { ruby-version: '3.x' }
      - run: gem install trmnl_preview
      - run: trmnlp lint
  push:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ruby/setup-ruby@v1
        with: { ruby-version: '3.x' }
      - run: gem install trmnl_preview
      - run: trmnlp push --force
        env:
          TRMNL_API_KEY: ${{ secrets.TRMNL_API_KEY }}   # repo secret
```

`trmnlp` is a Ruby gem (`trmnl_preview`). In CI, set `$TRMNL_API_KEY` instead of
running `trmnlp login`. **`src/settings.yml` must carry the plugin `id`** so
`push` updates the existing plugin instead of creating a new one each run.
Alternative: run the `trmnl/trmnlp` Docker image instead of installing Ruby.

### 7.4 `trmnlp` CLI workflow

```
trmnlp login                   # auth (saves key to ~/.config/trmnlp/config.yml)
trmnlp clone <name> <id>       # download an existing web-editor plugin
trmnlp serve                   # local dev server w/ live preview (HTML or PNG)
trmnlp push                    # upload markup to TRMNL
```

### 7.5 Plugin repo structure (per `trmnlp`)

This repo combines the FastAPI backend (`app/`) with the `trmnlp` plugin
(`src/`):

```
.
├── .github/workflows/trmnl.yml   # lint on PR, push on main
├── .trmnlp.yml                   # local dev config (watch, time_zone, variable overrides)
├── pyproject.toml                # backend deps + tooling
├── app/                          # FastAPI backend (slot logic + /trmnl, /health)
├── tests/                        # backend tests
└── src/
    ├── full.liquid               # main template (slot-branching)
    ├── half_horizontal.liquid
    ├── half_vertical.liquid
    ├── quadrant.liquid
    ├── shared.liquid             # reusable components
    └── settings.yml              # plugin config (strategy = polling, polling URL, id)
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

## 8. Decisions (resolved)

- **Hosting → Railway** (always-on). (was: Railway vs Fly)
- **Merge-variable shape → flat payload at the Liquid root** (`{{ slot }}`,
  `{{ quote }}`); TRMNL globals under `{{ trmnl }}`. (§4.2)
- **CI → on from day one** — `trmnlp lint` on PRs, `trmnlp push --force` on
  `main`; `TRMNL_API_KEY` as a repo secret; plugin `id` pinned in
  `src/settings.yml`. (§7.3)

> **Future work & open questions** — news freshness, richer scheduling, the
> background tier + store choice, render mode, PR previews — live in
> [`docs/future-features.md`](docs/future-features.md), not here. This document
> describes only what the current v1 issues (TCA-1…TCA-7) implement.

## 9. Execution & project management

- Work is tracked in **YouTrack project `TCA`** (TRMNL Custom App). v1 is broken
  into issues **TCA-1 … TCA-7** and worked one at a time.
- **One branch per issue**, named `TCA-<n>-<slug>` (e.g.
  `TCA-1-repo-scaffolding`), opened as a PR against `main`. Merging `main` is
  what triggers the template deploy (§7.3).
- Public GitHub repo: `craigsakuma/trmnl-custom-app`.

**v1 backlog**

| Issue | Summary |
|-------|---------|
| TCA-1 | Repo & project scaffolding |
| TCA-2 | FastAPI: slot engine + `/trmnl` endpoint |
| TCA-3 | trmnlp plugin scaffold + Liquid template |
| TCA-4 | Deploy FastAPI to Railway |
| TCA-5 | Create TRMNL private plugin + polling config |
| TCA-6 | GitHub Action: auto-deploy Liquid template |
| TCA-7 | End-to-end verification & docs |