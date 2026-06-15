"""FastAPI application entrypoint.

Exposes:
- ``/health`` — readiness check.
- ``/trmnl``  — the TRMNL polling endpoint; returns the current slot + quote as
  a flat JSON payload (exposed at the Liquid root as ``{{ slot }}`` /
  ``{{ quote }}``). See ARCHITECTURE.md §6, §7.1.
"""

from fastapi import FastAPI

from app.slots import slot_payload

app = FastAPI(title="TRMNL Custom App")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/trmnl")
def trmnl() -> dict[str, str]:
    # Slot is computed fresh from wall-clock time on every poll. Polling does
    # not return refresh_rate (Redirect-only); the rate is set in the TRMNL UI.
    return slot_payload()
