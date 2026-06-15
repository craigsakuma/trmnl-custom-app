"""Slot scheduling logic for the TRMNL polling endpoint.

v1 rule: the slot alternates by hour parity in `America/Los_Angeles` —
even hour -> slot "A", odd hour -> slot "B" — all day, every day. The chosen
slot carries a static quote. Content is intentionally trivial here; it gets
customized once the pipeline is proven (see ARCHITECTURE.md §1, §6).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Los_Angeles")

# Quotes returned per slot. Kept here (not in the Liquid template) so the full
# API -> template data flow is exercised.
QUOTES: dict[str, str] = {
    "A": "Eyes on the Prize. Finish Travel Roboto",
    "B": "Having Kiran's Love Makes Me the Luckiest Man in the World.",
}

# Slot used if anything goes wrong, so the device still gets a valid screen
# instead of an error (the endpoint must never fail; see ARCHITECTURE.md §4.5).
DEFAULT_SLOT = "A"


def current_slot(now: datetime) -> str:
    """Return the slot id for ``now``: "A" on even hours, "B" on odd hours."""
    return "A" if now.hour % 2 == 0 else "B"


def slot_payload(now: datetime | None = None) -> dict[str, str]:
    """Build the flat polling payload ``{"slot", "quote"}`` for ``now``.

    Fails soft: any unexpected error falls back to ``DEFAULT_SLOT`` so the
    endpoint always returns a renderable payload well within TRMNL's 2s timeout.
    """
    try:
        moment = now or datetime.now(TZ)
        # Parity must be measured in Pacific time: convert any tz-aware moment
        # so the slot doesn't depend on the caller's / server's timezone.
        if moment.tzinfo is not None:
            moment = moment.astimezone(TZ)
        slot = current_slot(moment)
        return {"slot": slot, "quote": QUOTES[slot]}
    except Exception:
        return {"slot": DEFAULT_SLOT, "quote": QUOTES[DEFAULT_SLOT]}
