"""Root conftest: pytest hooks that apply to the whole suite.

pytest_configure              -> PYTEST_LOG_LEVEL overrides the ini log level.
pytest_collection_modifyitems -> sort by TC number; auto-skip by TARGET_MODE.
pytest_sessionfinish          -> strip ANSI codes from the JUnit XML.
"""
import logging
import os
import re

import pytest

pytest_plugins = ["pytester", "framework.error_reporting"]

_TC_RE = re.compile(r"test_TC(\d+)_", re.IGNORECASE)
_ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-9;]*[ -/]*[@-~])")


def pytest_configure(config: pytest.Config) -> None:
    level = os.environ.get("PYTEST_LOG_LEVEL", "").strip().upper()
    if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        return
    config.override_ini("log_cli_level", level)
    config.override_ini("log_level", level)
    logging.getLogger().setLevel(getattr(logging, level))


def _tc_sort_key(item: pytest.Item) -> int:
    match = _TC_RE.search(item.name)
    return int(match.group(1)) if match else 9999


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    # list.sort is stable, so tests without a TC number keep their relative order.
    items.sort(key=_tc_sort_key)

    # TARGET_MODE=local skips tests that only make sense on a remote deployment.
    if os.environ.get("TARGET_MODE", "").strip().lower() == "local":
        skip = pytest.mark.skip(reason="TARGET_MODE=local: remote-only test")
        for item in items:
            if "remote_only" in item.keywords:
                item.add_marker(skip)


def _strip_ansi(path: str) -> None:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        original = fh.read()
    cleaned = _ANSI_RE.sub("", original)
    if cleaned != original:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(cleaned)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    xml_path = getattr(session.config.option, "xmlpath", None)
    if not xml_path:
        return
    # A relative --junitxml path is relative to where pytest was launched,
    # not to rootdir, so resolve it against invocation_params.dir.
    if not os.path.isabs(xml_path):
        xml_path = os.path.join(str(session.config.invocation_params.dir), xml_path)
    if os.path.exists(xml_path):
        _strip_ansi(xml_path)
