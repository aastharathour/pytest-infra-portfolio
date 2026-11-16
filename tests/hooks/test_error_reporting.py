"""Tests for the framework itself: unexpected-error reporting hook."""
import pytest

pytestmark = pytest.mark.framework

BODY = '''
import pytest

@pytest.fixture
def broken_fixture():
    raise RuntimeError("fixture exploded")

def test_boom():
    {}["missing"]

def test_assertion():
    assert 1 == 2

def test_skipped():
    pytest.skip("not today")

def test_explicit_fail():
    pytest.fail("explicit")

def test_fixture_error(broken_fixture):
    pass
'''


@pytest.fixture
def result(pytester):
    pytester.makepyfile(BODY)
    return pytester.runpytest_inprocess(
        "-p", "framework.error_reporting", "-o", "log_cli=false"
    )


def test_TC030_outcome_counts_unchanged(result):
    """[TC-030] The hook does not change pass/fail/skip/error classification."""
    result.assert_outcomes(failed=3, skipped=1, errors=1)


def test_TC031_unexpected_exception_reported(result):
    """[TC-031] A KeyError in a test is reported with its type and phase."""
    result.stdout.fnmatch_lines(["*Unexpected error in test_boom (call): KeyError: 'missing'*"])


def test_TC032_fixture_error_reported(result):
    """[TC-032] Errors raised in fixtures are covered too (the decorator could not)."""
    result.stdout.fnmatch_lines(
        ["*Unexpected error in test_fixture_error (setup): RuntimeError: fixture exploded*"]
    )


@pytest.mark.parametrize("name", ["test_assertion", "test_skipped", "test_explicit_fail"])
def test_TC033_expected_outcomes_not_reported_as_unexpected(result, name):
    """[TC-033] Assertions, skips and pytest.fail are not flagged as unexpected."""
    result.stdout.no_fnmatch_line(f"*Unexpected error in {name}*")
