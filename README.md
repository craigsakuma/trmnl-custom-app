# TRMNL Custom App

A custom [TRMNL](https://usetrmnl.com) e-ink plugin that displays **time-of-day
scheduled screens**. A FastAPI backend computes the current "slot" from
wall-clock time and returns it as JSON; a single Liquid template branches on the
slot to pick the layout. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full
design and platform constraints.

## v1 behavior

Two screens alternate by the hour (Pacific time):

- **Even hours** → slot `A`: _"Eyes on the Prize. Finish Travel Roboto"_
- **Odd hours** → slot `B`: _"Having Kiran's Love Makes Me the Luckiest Man in the World."_

## Layout

```
.
├── app/        # FastAPI backend (slot logic + /trmnl polling endpoint)
├── src/        # trmnlp plugin: Liquid templates + settings.yml
├── tests/      # backend tests
├── ARCHITECTURE.md
└── pyproject.toml
```

## Backend — local dev

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
# http://127.0.0.1:8000/health
```

## Plugin — local dev

The TRMNL plugin lives in `src/` and is previewed/deployed with the
[`trmnlp`](https://github.com/usetrmnl/trmnlp) CLI (`trmnlp serve` for live
preview, `trmnlp push` to deploy). See `ARCHITECTURE.md` §7.

## Project management

Work is tracked in YouTrack project **TCA** (TRMNL Custom App). Each issue is
developed on its own branch named `TCA-<n>-<slug>`.
