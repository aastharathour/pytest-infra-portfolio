"""Shared helpers: standardised logging, failure handling and env access."""
import logging
import os
from typing import Any

logger = logging.getLogger("framework")


def log_pass(message: str) -> None:
    logger.info("Result: PASS | %s", message)


def log_warn(message: str) -> None:
    logger.warning("Result: WARN | %s", message)


def log_fail(message: str) -> None:
    logger.error("Result: FAIL | %s", message)


def get_env(name: str, default: str = "") -> str:
    """Single place that reads and strips environment variables."""
    return os.environ.get(name, default).strip()


def to_list(value: Any) -> list:
    """Coerce None / scalar / tuple / list into a plain list."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]
