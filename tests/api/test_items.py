"""CRUD behaviour with per-test isolation via the clean_state fixture."""
import pytest

from framework.helpers import log_pass


@pytest.mark.crud
@pytest.mark.smoketests
def test_TC010_items_empty_initially(clean_state):
    """[TC-010] A freshly reset service has no items."""
    assert clean_state.get("/items").json() == []
    log_pass("Item list empty after reset")


@pytest.mark.crud
def test_TC011_create_item(clean_state):
    """[TC-011] POST /items returns 201 with the new item."""
    resp = clean_state.post("/items", json={"name": "widget"})
    assert resp.status_code == 201
    assert resp.json() == {"id": 1, "name": "widget"}
    log_pass("Item created")


@pytest.mark.crud
def test_TC012_get_created_item(clean_state):
    """[TC-012] A created item can be fetched by id."""
    created = clean_state.post("/items", json={"name": "gadget"}).json()
    fetched = clean_state.get(f"/items/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "gadget"


@pytest.mark.crud
def test_TC013_missing_item_returns_404(clean_state):
    """[TC-013] Unknown ids return 404."""
    assert clean_state.get("/items/999").status_code == 404


@pytest.mark.crud
@pytest.mark.parametrize(
    "payload",
    [{}, {"name": ""}, {"name": "   "}, {"name": 123}, {"other": "x"}],
    ids=["empty", "blank", "whitespace", "non-string", "wrong-key"],
)
def test_TC014_invalid_payload_rejected(clean_state, payload):
    """[TC-014] Invalid payloads are rejected with 400."""
    assert clean_state.post("/items", json=payload).status_code == 400
