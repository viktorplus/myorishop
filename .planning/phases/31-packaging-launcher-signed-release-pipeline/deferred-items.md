# Deferred Items — Phase 31

Out-of-scope discoveries logged during execution. NOT fixed by the plan that found them.

## Pre-existing ruff findings in tests/test_launcher.py

**Found during:** Plan 31-06, Task 1 (`uv run ruff check launcher tests`)
**Owner:** whoever next touches `tests/test_launcher.py` in refactor mode
**Status:** deferred (pre-existing, authored by Plan 31-01's Wave-0 scaffold)

`uv run ruff check tests/test_launcher.py` reports 3 errors, all on pre-existing lines:

| Rule | Line | Detail |
|------|------|--------|
| `B017` | 196 | `with pytest.raises(Exception):` — blind exception assert in `test_apply_update_rolls_back_on_failed_health_check` |
| `E501` | 251 | line too long (113 > 100) in the `parse_pending` traversal payload table |
| `UP031` | 432 | percent-format `('{"version": "%s"}' % version_payload)` in the `http.server` stub |

The lines Plan 31-06 added are clean (`ruff check launcher tests/test_packaging.py app/__init__.py` → `All checks passed!`). Fixing these three would touch code unrelated to the GAP-1 boot-migration change, so they were left alone per the executor scope boundary.
