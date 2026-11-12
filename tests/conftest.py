"""Fixtures for the suite.

Fixture chain (like a real infra suite):
    service  ->  base_url  ->  api  ->  ensure_service_ready
Session scope for expensive/read-only objects, function scope for isolation.
"""
import logging

import pytest
import requests

from framework.helpers import get_env
from framework.mock_service import MockService

logger = logging.getLogger(__name__)


class ApiClient:
    """requests.Session wrapper that applies a base URL and default timeout."""

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self._session.request(method, f"{self.base_url}{path}", **kwargs)

    def get(self, path: str, **kw):
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw):
        return self.request("POST", path, **kw)

    def delete(self, path: str, **kw):
        return self.request("DELETE", path, **kw)

    def close(self) -> None:
        self._session.close()


@pytest.fixture(scope="session")
def service():
    """Start the local mock service, or use TARGET_BASE_URL when provided.

    Code after ``yield`` is teardown and runs even if tests fail.
    """
    external = get_env("TARGET_BASE_URL")
    if external:
        logger.info("Using external service at %s", external)
        yield external
        return
    svc = MockService()
    svc.start()
    logger.info("Started mock service at %s", svc.base_url)
    yield svc.base_url
    svc.stop()
    logger.info("Stopped mock service")


@pytest.fixture(scope="session")
def api(service: str):
    client = ApiClient(service)
    yield client
    client.close()


@pytest.fixture(scope="session")
def ensure_service_ready(api: ApiClient) -> ApiClient:
    """Guard fixture: skip dependent tests when the service is unreachable."""
    try:
        api.get("/health")
    except requests.RequestException as exc:
        pytest.skip(f"Service unreachable: {exc}")
    return api


@pytest.fixture
def clean_state(ensure_service_ready: ApiClient):
    """Function-scoped isolation: empty the item store before each test."""
    ensure_service_ready.post("/reset")
    return ensure_service_ready
