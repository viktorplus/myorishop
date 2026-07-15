# Deferred Items — Phase 17

Out-of-scope findings discovered during execution but not fixed (per
executor scope-boundary rule: only auto-fix issues directly caused by the
current task's changes).

## Plan 17-01

- `tests/test_export.py:124` (pre-existing, unrelated to Plan 17-01 changes):
  `ruff check` flags E501 (line too long, 102 > 100) on
  `test_sales_csv_roundtrip`'s docstring. Predates this plan (confirmed via
  `git show HEAD:tests/test_export.py`). Not fixed here — revisit if
  `tests/test_export.py` is next touched for an unrelated reason.
