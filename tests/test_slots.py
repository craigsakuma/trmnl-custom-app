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


def test_slot_is_timezone_aware_not_server_local() -> None:
    # 09:00 UTC is 02:00 Pacific (even -> A). If the logic used UTC/server time
    # it would read hour 9 (odd -> B); the conversion must win.
    nine_utc = datetime(2026, 6, 15, 9, 0, tzinfo=ZoneInfo("UTC"))
    assert current_slot(nine_utc.astimezone(TZ)) == "A"
    assert slot_payload(nine_utc)["slot"] == "A"


def test_slot_payload_fails_soft_on_bad_input() -> None:
    # A naive datetime (no tzinfo) still yields a valid renderable payload.
    payload = slot_payload(datetime(2026, 6, 15, 9, 0))
    assert payload["slot"] in QUOTES
    assert payload["quote"] == QUOTES[payload["slot"]]
