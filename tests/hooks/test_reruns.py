"""Proves rerun behaviour: marked tests are retried, unmarked tests are not."""
import pytest

pytestmark = pytest.mark.framework

BODY = '''
import pytest

calls = {"marked": 0, "plain": 0}

@pytest.mark.flaky(reruns=2, reruns_delay=0)
def test_marked():
    calls["marked"] += 1
    assert calls["marked"] == 3

def test_plain():
    calls["plain"] += 1
    assert calls["plain"] == 2
'''


def test_TC041_only_marked_tests_are_rerun(pytester):
    """[TC-041] The flaky test passes after 2 reruns; the plain test fails once."""
    pytester.makepyfile(BODY)
    result = pytester.runpytest_inprocess("-o", "log_cli=false")
    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines(["*1 failed, 1 passed, 2 rerun*"])
