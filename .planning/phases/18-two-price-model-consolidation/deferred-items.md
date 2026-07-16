# Deferred Items — Phase 18

Out-of-scope discoveries acknowledged during plan execution but not fixed
(SCOPE BOUNDARY: only auto-fix issues directly caused by the current task's
changes).

## Plan 18-03

- **Pre-existing unused import** — `tests/test_mobile_receipts.py:16` imports
  `add_entry` from `app.services.dictionary` but never calls it (confirmed via
  `git show 8a9a42e:tests/test_mobile_receipts.py` — present before this
  plan's changes). `ruff check` flags it (F401). Not fixed here since it
  predates Plan 18-03 and is unrelated to the catalog-field removal; revisit
  next time this test file is touched.
