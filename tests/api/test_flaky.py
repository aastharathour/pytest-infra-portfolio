"""Targeted reruns with pytest-rerunfailures.

Only tests that depend on timing are marked; everything else fails on the
first attempt so real defects are never hidden.
"""
import pytest

_attempts = {"count": 0}


@pytest.mark.crud
@pytest.mark.flaky(reruns=2, reruns_delay=0)
def test_TC040_eventually_consistent_read(clean_state):
    """[TC-040] Simulates a read that succeeds on the third attempt."""
    _attempts["count"] += 1
    clean_state.post("/items", json={"name": "eventual"})
    assert _attempts["count"] >= 3, f"not ready yet (attempt {_attempts['count']})"
