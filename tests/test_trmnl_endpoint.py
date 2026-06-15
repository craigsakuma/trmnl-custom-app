from fastapi.testclient import TestClient

from app.main import app
from app.slots import QUOTES

client = TestClient(app)


def test_trmnl_returns_flat_slot_payload() -> None:
    resp = client.get("/trmnl")
    assert resp.status_code == 200

    body = resp.json()
    # Flat payload (root-level keys) so TRMNL exposes {{ slot }} / {{ quote }}.
    assert set(body) == {"slot", "quote"}
    assert body["slot"] in ("A", "B")
    assert body["quote"] == QUOTES[body["slot"]]
