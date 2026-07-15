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

## Plan 17-03

- `tests/test_finance_reports.py` (pre-existing, unrelated to Plan 17-03
  changes): `ruff format --check` flags several lines in the pre-existing
  `_record_cash_at`-based tests (17-01's block) that exceed the wrapped-call
  style ruff's formatter now prefers. Confirmed pre-existing via
  `ruff format --check` against the file as it stood at `HEAD~1` (before
  this plan's edits) — the drift already existed. This plan's own new tests
  (the `test_web_finance_report_*` block) are already correctly formatted
  and excluded from the diff. Not fixed here — revisit only if
  `tests/test_finance_reports.py` is next touched for an unrelated reason.
