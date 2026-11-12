"""Shared helpers: standardised logging, failure handling and env access."""
import functools
import logging
import os
from typing import Any, Callable

import pytest

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


def fail_on_exception(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Turn unexpected exceptions into a clear pytest failure.

    AssertionError is re-raised untouched so pytest keeps its rich diff.
    functools.wraps preserves the signature so fixture injection still works.
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except (AssertionError, pytest.skip.Exception, pytest.fail.Exception):
            raise
        except Exception as exc:
            log_fail(f"Unexpected error in {fn.__name__}: {type(exc).__name__}: {exc}")
            pytest.fail(f"Unexpected error in {fn.__name__}: {type(exc).__name__}: {exc}")

    return wrapper


def to_list(value: Any) -> list:
    """Coerce None / scalar / tuple / list into a plain list."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]
