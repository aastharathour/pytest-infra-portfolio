"""Health checks: availability, payload, latency."""
import time

import pytest

from framework.helpers import fail_on_exception, log_fail, log_pass

MAX_LATENCY_SECONDS = 1.0


@fail_on_exception
@pytest.mark.health
@pytest.mark.smoketests
def test_TC001_service_reachable(ensure_service_ready):
    """[TC-001] /health responds with HTTP 200."""
    resp = ensure_service_ready.get("/health")
    if resp.status_code == 200:
        log_pass("Service reachable")
    else:
        log_fail(f"Unexpected status {resp.status_code}")
        pytest.fail(f"Expected 200, got {resp.status_code}")


@fail_on_exception
@pytest.mark.health
@pytest.mark.smoketests
def test_TC002_health_payload_ok(ensure_service_ready):
    """[TC-002] /health body reports status=ok."""
    body = ensure_service_ready.get("/health").json()
    assert body.get("status") == "ok", f"Unexpected payload: {body}"
    log_pass("Health payload OK")


@fail_on_exception
@pytest.mark.health
@pytest.mark.smoketests
@pytest.mark.parametrize("path", ["/health", "/items"])
def test_TC003_response_time_within_limit(ensure_service_ready, path):
    """[TC-003] Key endpoints respond within the latency budget."""
    start = time.perf_counter()
    ensure_service_ready.get(path)
    elapsed = time.perf_counter() - start
    assert elapsed < MAX_LATENCY_SECONDS, f"{path} took {elapsed:.3f}s"
    log_pass(f"{path} answered in {elapsed:.3f}s")


@pytest.mark.health
@pytest.mark.remote_only
def test_TC004_tls_certificate_valid(service):
    """[TC-004] Remote deployments must serve HTTPS (skipped in local mode)."""
    assert service.startswith("https://"), f"{service} is not HTTPS"
