# pytest-infra-portfolio

A from-scratch pytest framework that demonstrates patterns used when validating deployed infrastructure. The system under test is a small in-memory HTTP service, so everything runs offline.

## Concepts demonstrated
| Concept | Where |
|---|---|
| Config: `addopts`, registered markers, live logging | `pytest.ini` |
| Hooks (`pytest_configure`, `pytest_collection_modifyitems`, `pytest_sessionfinish`) | `conftest.py` |
| Fixture chain, scopes, `yield` teardown, guard fixture, isolation fixture | `tests/conftest.py` |
| Helpers: decorator, standard log lines | `framework/helpers.py` |
| Markers, `-m` selection, parametrization with ids | `tests/health`, `tests/api` |
| Ordered scenarios with `pytest-dependency` | `tests/lifecycle` |
| Env-driven auto-skip (`TARGET_MODE=local`) | `conftest.py` |
| CI + reports (JUnit, coverage, HTML) | `.github/workflows/tests.yml` |

## Run
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
pytest                              # everything
pytest -m smoketests                # fast tier
pytest -k TC011                     # one test
TARGET_MODE=local pytest            # skips remote_only tests
PYTEST_LOG_LEVEL=DEBUG pytest       # verbose logs
TARGET_BASE_URL=https://host pytest # test an external service
```

## Design notes
- `pytest.ini` holds stable defaults; CI passes per-run options (report paths, `-m`). Command-line options override `addopts`, and `--cov` options append, so they are not duplicated.
- The JUnit ANSI strip resolves relative paths against `config.invocation_params.dir`, because `--junitxml` is relative to where pytest was launched, not `rootdir`.
