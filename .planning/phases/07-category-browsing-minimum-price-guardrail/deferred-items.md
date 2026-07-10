# Deferred Items — Phase 07 (category-browsing-minimum-price-guardrail)

Items discovered during execution that are out of scope for the current plan
(pre-existing, unrelated to the files this plan touches) and were left
unfixed per the executor's scope-boundary rule.

## Plan 07-04

- **Pre-existing `ruff check` I001 (import block un-sorted)** in
  `tests/test_sales.py`, line 20 — confirmed via `git show <prior-commit>:tests/test_sales.py
  | ruff check --stdin-filename tests/test_sales.py -` that the same warning
  fires on the file as it existed before this plan's edits (documented
  previously for other test files in
  `.planning/milestones/v1.0-phases/06-reports-data-export/deferred-items.md`).
  Not fixed here — out of scope; this plan only adds a negative-price guard
  to `app/services/sales.py` (clean on `ruff check`) and three new test
  functions to `tests/test_sales.py`.
