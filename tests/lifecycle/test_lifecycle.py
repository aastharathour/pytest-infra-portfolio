"""Ordered scenario: each step depends on the previous one (pytest-dependency).

If a step fails, later steps are skipped instead of producing noisy failures.
"""
import pytest


_state: dict = {}


@pytest.mark.lifecycle
@pytest.mark.dependency(name="create")
def test_TC020_create(clean_state):
    """[TC-020] Create an item."""
    resp = clean_state.post("/items", json={"name": "lifecycle"})
    assert resp.status_code == 201
    _state["id"] = resp.json()["id"]


@pytest.mark.lifecycle
@pytest.mark.dependency(name="read", depends=["create"])
def test_TC021_read(ensure_service_ready):
    """[TC-021] Read the item created in TC-020."""
    assert ensure_service_ready.get(f"/items/{_state['id']}").status_code == 200


@pytest.mark.lifecycle
@pytest.mark.dependency(name="delete", depends=["read"])
def test_TC022_delete(ensure_service_ready):
    """[TC-022] Delete the item."""
    assert ensure_service_ready.delete(f"/items/{_state['id']}").status_code == 204


@pytest.mark.lifecycle
@pytest.mark.dependency(depends=["delete"])
def test_TC023_gone_after_delete(ensure_service_ready):
    """[TC-023] The deleted item is no longer retrievable."""
    assert ensure_service_ready.get(f"/items/{_state['id']}").status_code == 404
