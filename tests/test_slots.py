from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.slots import QUOTES, TZ, current_slot, slot_payload


def at(hour: int) -> datetime:
    """A Pacific-time datetime at the given hour."""
    return datetime(2026, 6, 15, hour, 30, tzinfo=TZ)


@pytest.mark.parametrize(
    "hour,expected",
    [
        (0, "A"),   # midnight — even
        (8, "A"),   # 08:00 — even
        (9, "B"),   # 09:00 — odd
        (10, "A"),  # 10:00 — even
        (23, "B"),  # 23:00 — odd
    ],
)
def test_current_slot_parity(hour: int, expected: str) -> None:
    assert current_slot(at(hour)) == expected


def test_slot_payload_shape_and_quote() -> None:
    payload = slot_payload(at(8))
    assert payload == {"slot": "A", "quote": QUOTES["A"]}

    payload = slot_payload(at(9))
    assert payload == {"slot": "B", "quote": QUOTES["B"]}


def test_current_slot_converts_non_pacific_tz() -> None:
    # 09:00 UTC is 02:00 Pacific (even -> A). current_slot must operate on the
    # converted hour, not the caller's hour.
    nine_utc = datetime(2026, 6, 15, 9, 0, tzinfo=ZoneInfo("UTC"))
    assert current_slot(nine_utc.astimezone(TZ)) == "A"


def test_slot_payload_converts_non_pacific_tz() -> None:
    # slot_payload must convert tz-aware input before evaluating parity.
    nine_utc = datetime(2026, 6, 15, 9, 0, tzinfo=ZoneInfo("UTC"))
    assert slot_payload(nine_utc)["slot"] == "A"


def test_slot_payload_raises_on_naive_datetime() -> None:
    # Naive datetimes are a caller bug; they must not be silently swallowed.
    with pytest.raises(TypeError):
        slot_payload(datetime(2026, 6, 15, 9, 0))
