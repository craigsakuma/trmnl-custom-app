"""FastAPI application entrypoint.

Exposes:
- ``/health`` — readiness check.
- ``/trmnl``  — the TRMNL polling endpoint; returns the current slot + quote as
  a flat JSON payload (exposed at the Liquid root as ``{{ slot }}`` /
  ``{{ quote }}``). Slot is computed fresh from wall-clock time on every poll;
  refresh rate is configured in the TRMNL UI, not returned here. See
  ARCHITECTURE.md §6, §7.1.
"""

from fastapi import FastAPI

from app.slots import SlotPayload, slot_payload

app = FastAPI(title="TRMNL Custom App")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/trmnl")
def trmnl() -> SlotPayload:
    return slot_payload()
