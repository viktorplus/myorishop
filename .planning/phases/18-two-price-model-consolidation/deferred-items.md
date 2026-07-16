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

## Plan 18-06

- **app/routes/mobile_sales.py:218** — `ruff` E501 (line too long, 103 > 100). Pre-existing,
  not touched by 18-06 (the `warehouse_name = ...` assignment predates this plan's edits).
- **app/routes/mobile_sales.py:284** — `ruff` E501 (line too long, 105 > 100). Pre-existing,
  not touched by 18-06 (the `"warehouse_name": ...` dict entry predates this plan's edits).

Both are out of scope for 18-06 (wording-only plan for sale prefill hints); revisit if
`mobile_sales.py` is touched again for an unrelated reason.

**RESOLVED at Plan 18-08:** both lines wrapped (`ruff check app/routes/mobile_sales.py`
is a hard acceptance criterion for 18-08's Task 2, which touches this file for the
data-ref-cents wiring) — the plan's own scope satisfies the "revisit" note above.

## Plan 18-02

- **app/routes/products.py:127** — `ruff` E501 (line too long, 106 > 100), on the
  `# Formalized under Phase 12 (PRICE-02) ...` comment above `product_price_lookup`.
  Pre-existing, not touched by 18-02's edits (confirmed via `git show
  HEAD:app/routes/products.py` before this plan's changes — the comment predates
  the catalog-autofill removal). Out of scope; revisit if this comment line is
  next touched.
