# Deferred Items — Phase 18

Out-of-scope discoveries logged during execution (not fixed per scope-boundary rule).

## Plan 18-06

- **app/routes/mobile_sales.py:218** — `ruff` E501 (line too long, 103 > 100). Pre-existing,
  not touched by 18-06 (the `warehouse_name = ...` assignment predates this plan's edits).
- **app/routes/mobile_sales.py:284** — `ruff` E501 (line too long, 105 > 100). Pre-existing,
  not touched by 18-06 (the `"warehouse_name": ...` dict entry predates this plan's edits).

Both are out of scope for 18-06 (wording-only plan for sale prefill hints); revisit if
`mobile_sales.py` is touched again for an unrelated reason.
