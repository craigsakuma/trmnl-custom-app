"""Slot scheduling logic for the TRMNL polling endpoint.

v1 rule: the slot alternates by hour parity in `America/Los_Angeles` —
even hour -> slot "A", odd hour -> slot "B" — all day, every day. The chosen
slot carries a static quote. Content is intentionally trivial here; it gets
customized once the pipeline is proven (see ARCHITECTURE.md §1, §6).
"""

from datetime import datetime
from typing import Literal, TypedDict
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Los_Angeles")

SlotId = Literal["A", "B"]


class SlotPayload(TypedDict):
    slot: SlotId
    quote: str


# Quotes returned per slot. Kept here (not in the Liquid template) so the full
# API -> template data flow is exercised.
QUOTES: dict[SlotId, str] = {
    "A": "Eyes on the Prize. Finish Travel Roboto",
    "B": "Having Kiran's Love Makes Me the Luckiest Man in the World.",
}


def current_slot(now: datetime) -> SlotId:
    """Return the slot id for ``now``: "A" on even hours, "B" on odd hours."""
    return "A" if now.hour % 2 == 0 else "B"


def slot_payload(now: datetime | None = None) -> SlotPayload:
    """Build the flat polling payload ``{"slot", "quote"}`` for ``now``.

    ``now`` must be timezone-aware or ``None`` (defaults to current Pacific
    time). Passing a naive datetime raises ``TypeError``.
    """
    if now is not None and now.tzinfo is None:
        raise TypeError("now must be a timezone-aware datetime")
    moment = (now or datetime.now(TZ)).astimezone(TZ)
    slot = current_slot(moment)
    return {"slot": slot, "quote": QUOTES[slot]}
