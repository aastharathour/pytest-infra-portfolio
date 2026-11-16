"""Central reporting of unexpected errors (replaces a per-test decorator).

Any exception raised in a test or fixture that is not an assertion, skip,
fail or xfail is logged in the standard format and added to the report as an
"Unexpected error" section. The original traceback is left untouched, and
fixture (setup) errors are covered too.
"""
import logging

import pytest

logger = logging.getLogger("framework")

_EXPECTED = (
    AssertionError,
    pytest.skip.Exception,
    pytest.fail.Exception,
    pytest.xfail.Exception,
)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    excinfo = call.excinfo
    if excinfo is None or not report.failed or isinstance(excinfo.value, _EXPECTED):
        return
    message = (
        f"Unexpected error in {item.name} ({call.when}): "
        f"{excinfo.typename}: {excinfo.value}"
    )
    logger.error("Result: FAIL | %s", message)
    report.sections.append(("Unexpected error", message))
