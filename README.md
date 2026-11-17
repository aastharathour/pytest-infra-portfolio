# pytest-infra-portfolio

A from-scratch pytest framework that demonstrates the patterns used when validating deployed infrastructure (clusters, services, pipelines). The system under test is a small in-memory HTTP service, so everything runs offline and fast.

It is written to be **read and explained**: each section below says what a piece does, why it was designed that way, and the interview question it answers.

## Contents
1. [Quick start](#quick-start)
2. [Project layout](#project-layout)
3. [The system under test](#the-system-under-test)
4. [Configuration: `pytest.ini`](#configuration-pytestini)
5. [Hooks: root `conftest.py`](#hooks-root-conftestpy)
6. [Fixtures: `tests/conftest.py`](#fixtures-testsconftestpy)
7. [Framework code](#framework-code)
8. [Test catalogue](#test-catalogue)
9. [CI pipeline](#ci-pipeline)
10. [Design decisions](#design-decisions)
11. [Gotchas and lessons learned](#gotchas-and-lessons-learned)
12. [Interview Q&A](#interview-qa)

## Quick start
```
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

pytest                                # everything
pytest -m smoketests                  # fast tier
pytest -m "crud and not slow"         # marker expression
pytest -k TC011                       # one test by name
pytest tests/api/test_items.py::test_TC011_create_item   # one test by node id
pytest -rs                            # show skip reasons
pytest --collect-only -q              # list tests without running

TARGET_MODE=local pytest              # skip remote_only tests
PYTEST_LOG_LEVEL=DEBUG pytest         # verbose logs
TARGET_BASE_URL=https://host pytest   # test an external service instead of the mock
```
On Windows PowerShell set variables with `$env:TARGET_MODE="local"; pytest`.

Expected result: run with `TARGET_MODE=local` (as CI does) to get 25 passed, 1 skipped, 2 reruns. Without it, `test_TC004` runs and fails on purpose, because the local mock serves plain HTTP and that test requires HTTPS.

## Project layout
```
conftest.py                     Root hooks (log level, sorting, auto-skip, ANSI strip)
pytest.ini                      Stable defaults, markers, live logging
requirements.txt                pytest + plugins
framework/
  helpers.py                    log_pass/log_warn/log_fail, get_env, to_list
  mock_service.py               In-memory HTTP service (system under test)
  error_reporting.py            Hook that reports unexpected errors centrally
tests/
  conftest.py                   Fixtures: service -> api -> ensure_service_ready -> clean_state
  health/test_health.py         TC001-TC004
  api/test_items.py             TC010-TC014
  api/test_flaky.py             TC040 (targeted rerun)
  lifecycle/test_lifecycle.py   TC020-TC023 (ordered, dependent)
  hooks/test_error_reporting.py TC030-TC033 (tests of the framework itself)
  hooks/test_reruns.py          TC041 (proves rerun behaviour)
.github/workflows/tests.yml     CI
```

## The system under test
`framework/mock_service.py` starts a `ThreadingHTTPServer` on `127.0.0.1` port `0` (the OS picks a free port, so parallel runs never collide) in a daemon thread.

| Endpoint | Behaviour |
|---|---|
| `GET /health` | `200 {"status": "ok"}` |
| `GET /items` | list of items |
| `POST /items` | needs a non-blank string `name`; returns `201` with `{"id", "name"}`; otherwise `400` |
| `GET /items/<id>` | the item, or `404` |
| `DELETE /items/<id>` | `204`, or `404` |
| `POST /reset` | clears items and resets ids (test-isolation helper) |

State sits behind a `threading.Lock` because the server handles each request in its own thread. `log_message` is overridden to keep test output clean.

Setting `TARGET_BASE_URL` points the same tests at a real deployment, which is how infra suites are reused across environments.

## Configuration: `pytest.ini`
| Setting | Why |
|---|---|
| `testpaths = tests` | `pytest` with no arguments only collects `tests/`, not the virtualenv or the framework folder |
| `python_files = test_*.py` | Discovery pattern |
| `addopts = -v --tb=short --no-header --strict-markers` | Stable defaults only. `--strict-markers` turns a typo such as `@pytest.mark.smoketest` into an error instead of a silently unselected test |
| `markers = ...` | Registers every marker with a description (`smoketests`, `slow`, `health`, `crud`, `framework`, `lifecycle`, `remote_only`) |
| `log_cli = true`, `log_cli_level = INFO`, format/date | Live logging to the console while tests run |
| `log_level = INFO` | Level captured into the report sections for failed tests |

**Rule used here:** `pytest.ini` holds stable defaults; CI passes per-run options (report paths, `-m` filters). Command-line options override `addopts` for options where the last value wins (for example `--junitxml`), while options like `--cov` and `-v` accumulate, so putting the same flag in both places is redundant at best and confusing at worst (`-v` plus `-v` becomes `-vv`).

## Hooks: root `conftest.py`
A `conftest.py` is a local plugin that pytest loads automatically. Hooks are functions with fixed names that pytest calls at defined points.

- `pytest_plugins = ["pytester", "framework.error_reporting"]` registers plugins. `pytester` provides the `pytester` fixture used to test the framework itself. `pytest_plugins` is only allowed in the root conftest.
- `pytest_configure(config)` runs once at start. If `PYTEST_LOG_LEVEL` is a valid level, it overrides `log_cli_level` and `log_level` with `config.override_ini` and sets the root logger level. Invalid values are ignored.
- `pytest_collection_modifyitems(config, items)` runs after collection and may reorder or mark tests.
  - Sorting by `test_TC<number>_` uses `list.sort`, which is stable, so tests with no number keep their relative order (they get key `9999`).
  - When `TARGET_MODE=local`, every item with the `remote_only` marker gets a `skip` marker, with a reason that appears in `-rs` output.
- `pytest_sessionfinish(session, exitstatus)` runs at the end. It removes ANSI colour codes from the JUnit XML using a regex, because colour output can leak into XML and break parsers or dashboards.
  - The path is `config.option.xmlpath`. A relative `--junitxml` is relative to the directory where pytest was **launched**, not `rootdir`, so the code resolves it against `config.invocation_params.dir`. Joining it to `rootdir` instead would look in the wrong place and silently do nothing whenever the two differ.
  - The file is rewritten only when something changed.

## Fixtures: `tests/conftest.py`
Fixture chain (each layer depends on the previous one):

```
service (session) -> api (session) -> ensure_service_ready (session) -> clean_state (function)
```

| Fixture | Scope | What it does |
|---|---|---|
| `service` | session | Returns the base URL. Uses `TARGET_BASE_URL` if set, otherwise starts `MockService`. Code after `yield` is teardown (stops the server) and runs even if tests fail |
| `api` | session | Wraps `requests.Session` in `ApiClient` (base URL, default 5 s timeout, `get/post/delete`) and closes it on teardown |
| `ensure_service_ready` | session | **Guard fixture.** Calls `/health`; on `requests.RequestException` it calls `pytest.skip`, so dependent tests are *skipped*, not failed, when the environment is down |
| `clean_state` | function | **Isolation fixture.** Calls `POST /reset` before every test so tests do not depend on each other's data |

Why scopes matter: expensive or read-only objects (server, HTTP session) are created once per session; anything that mutates state is function-scoped so every test starts clean.

`ApiClient.request` uses `kwargs.setdefault("timeout", ...)`: a caller can override the timeout, but no call can ever run without one (a missing timeout is a classic cause of hung pipelines).

## Framework code
**`framework/helpers.py`**
- `log_pass` / `log_warn` / `log_fail` emit uniform `Result: PASS | ...` lines, which makes pipeline logs greppable.
- `get_env(name, default)` is the single place that reads and strips environment variables.
- `to_list(value)` turns `None` into `[]`, a list or tuple into a list, and anything else into `[value]`.

**`framework/error_reporting.py`** is a `pytest_runtest_makereport` **hookwrapper**.
1. `yield` lets pytest build the report, then `outcome.get_result()` returns it.
2. If there is no exception, the report did not fail, or the exception is *expected* (`AssertionError`, skip, fail, xfail), the hook returns and does nothing.
3. Otherwise it logs a standard line and appends an `"Unexpected error"` section to the report, e.g. `Unexpected error in test_boom (call): KeyError: 'missing'`.

It replaces a per-test `@fail_on_exception` decorator. pytest already fails a test on any exception, so the decorator's real value was log consistency, and it had drawbacks: it needed repeating on every test, it re-raised and could alter the traceback, and it could not see fixture (setup) errors. The hook is applied once, keeps the original traceback, and reports the phase (`setup`, `call`, `teardown`).

## Test catalogue
| ID | File | What it checks | Technique |
|---|---|---|---|
| TC001 | health | `/health` returns 200 | smoke, `log_pass/log_fail` |
| TC002 | health | payload `status == "ok"` | assert with message |
| TC003 | health | `/health` and `/items` respond under 1 s | `parametrize`, `time.perf_counter` |
| TC004 | health | remote deployment serves HTTPS | `remote_only`: skipped when `TARGET_MODE=local`, fails against the plain-HTTP mock otherwise |
| TC010 | api | list is empty after reset | isolation fixture |
| TC011 | api | POST returns 201 and `{"id": 1, "name": "widget"}` | status plus body |
| TC012 | api | created item can be fetched | create-then-read |
| TC013 | api | unknown id returns 404 | negative test |
| TC014 | api | five invalid payloads return 400 | `parametrize` with readable `ids` |
| TC020-023 | lifecycle | create, read, delete, verify gone | `pytest-dependency`: if a step fails, later steps are **skipped**, not failed |
| TC030-033 | hooks | the error-reporting hook: counts unchanged, `KeyError` reported, fixture error reported, expected outcomes not flagged | `pytester` in-process |
| TC040 | api | read that succeeds on the third attempt | `@pytest.mark.flaky(reruns=2)` |
| TC041 | hooks | only the marked test is rerun; the unmarked one fails once | `pytester`, asserts `2 rerun` |

Notes:
- Lifecycle tests share data through a module-level `_state` dict, which is deliberate: the steps form one scenario. They use `ensure_service_ready` after the first step because `clean_state` would wipe the item.
- `pytester` runs a nested pytest session inside a temporary directory. Use `runpytest_inprocess` for speed, and `-o log_cli=false` to stop inner logging from polluting the outer output.

## CI pipeline
`.github/workflows/tests.yml` runs on every push and pull request, on `ubuntu-latest`, Python 3.12 with pip caching.

1. **Smoke gate:** `pytest -m smoketests -q` with `TARGET_MODE=local`. A fast failure here stops the job early.
2. **Full suite with reports:** JUnit XML, coverage XML plus terminal summary, and a self-contained HTML report.
   - `--cov=framework` measures the framework code. `--cov-fail-under=80` fails the build if coverage drops below 80 % (currently about 88 %).
3. **Artifacts:** `actions/upload-artifact` with `if: always()` so reports are uploaded even when tests fail, which is when you need them most.

This mirrors a real pre/post-deployment pipeline: a cheap gate first, then the full suite, with machine-readable reports for dashboards.

## Design decisions
- **Skip vs fail:** an unreachable environment is a *skip* (guard fixture); a wrong result is a *fail*. This keeps failures meaningful.
- **Central hook instead of decorators:** one place, covers fixtures, no behaviour change.
- **Single source of truth for options:** ini for stable defaults, CI for per-run outputs.
- **Targeted reruns only:** `--reruns` globally would hide real defects. Only genuinely timing-dependent tests carry `@pytest.mark.flaky`, with a limited count, and a rerun shows up in the report as `RERUN` so the flakiness stays visible.
- **Strict markers and registered markers:** prevents silently unselected tests.
- **Isolation by design:** function-scoped reset, no ordering dependence except in the explicit lifecycle scenario.
- **Offline system under test:** no cloud credentials, so anyone can clone and run it.

## Gotchas and lessons learned
- A green gutter icon in the IDE only means pytest *started*. Always check the summary line for skipped tests (`-rs` shows reasons).
- A saved IDE run configuration with a bare module name and the wrong working directory can pick a different test file or ignore `pytest.ini`. Run from the project root or point the configuration at the right folder.
- Relative `--junitxml` paths are relative to the launch directory, not `rootdir`.
- `--cov` accumulates across `addopts` and the command line; most other options are last-wins.
- `pytester.assert_outcomes` has no `rerun` argument in some versions, so the rerun count is asserted on the summary line instead.
- `pytest-rerunfailures` being installed does **not** enable reruns. They only apply with `--reruns` or `@pytest.mark.flaky`.
- Test files with a UTF-8 BOM must be read with `utf-8-sig` when parsed by scripts.

## Interview Q&A
**What is a fixture and how do scopes work?** A function that provides setup (and teardown after `yield`) via dependency injection by parameter name. `function` (default) runs per test, `session` once per run; `module`/`class`/`package` sit in between. Use the widest scope that is safe.

**How do you share fixtures?** Put them in a `conftest.py`; it applies to its directory and below with no import needed.

**Skip vs xfail vs fail?** Skip: not applicable or environment missing. xfail: known bug, expected to fail. Fail: the behaviour is wrong.

**How do you select tests?** Markers (`-m "smoketests and not slow"`), keywords (`-k`), node ids (`file::test`), or auto-skip hooks driven by environment variables.

**How do you stop flaky tests?** First fix the cause (waits, polling, isolation). For genuinely timing-dependent checks use `@pytest.mark.flaky(reruns=N)` on those tests only; never a global `--reruns`, and keep rerun counts visible in reports.

**How do you test your own framework?** `pytester` creates a temporary project, runs pytest on it, and asserts on outcomes and output (`assert_outcomes`, `stdout.fnmatch_lines`).

**What does `parametrize` give you?** One test body over many inputs; `ids=` makes failures readable (`test_TC014_invalid_payload_rejected[blank]`).

**Why a hookwrapper?** It runs around other implementations, so it can read or modify the result (`outcome.get_result()`) after pytest has built it.

**How do you make the suite work across environments?** Configuration through environment variables (`TARGET_BASE_URL`, `TARGET_MODE`), no hard-coded hosts, markers for environment-specific tests, and guard fixtures that skip cleanly.

**What do you put in CI?** Fast gate first, full run second, JUnit plus coverage plus HTML artifacts uploaded even on failure, and a coverage threshold.

**What would you improve next?** Run tests in parallel with `pytest-xdist` (needs isolation per worker), add `workflow_dispatch` for manual runs, add a check that every test belongs to exactly one pipeline gate, and publish JUnit results to a dashboard.
