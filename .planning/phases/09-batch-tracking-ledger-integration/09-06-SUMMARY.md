---
phase: 09-batch-tracking-ledger-integration
plan: 06
subsystem: sales / batch-picker UI
tags: [htmx, oob-swap, templates, uat-gap-closure, LOT-02]
requires:
  - sale_lookup.html / sale_batch_pick.html OOB fragments (Phase 9 Plan 04)
  - register_sale positional batch_id[] zip (Phase 9 Plan 02)
provides:
  - "<template>-wrapped OOB table fragments so htmx parses the batch-wrap <tr> as an independent OOB element"
  - "single batch_id[] hidden input per sale line (no stale empty duplicate)"
  - "regression tests locking the fix (structural + 3-line attribution)"
affects:
  - /sales/lookup fragment
  - /sales/batch-pick fragment
tech-stack:
  added: []
  patterns:
    - "htmx OOB table elements wrapped in <template> (per htmx docs «Troublesome Tables and lists»)"
key-files:
  created: []
  modified:
    - app/templates/partials/sale_lookup.html
    - app/templates/partials/sale_batch_pick.html
    - tests/test_sales.py
decisions:
  - "Wrap only the OOB fragments in <template>; the main-swap <td>/<tr> (first top-level element in each partial) is left untouched so its own parse context stays correct."
metrics:
  duration: 6min
  completed: 2026-07-12
---

# Phase 09 Plan 06: Fix sale-line inline batch picker OOB parse context Summary

Wrapped the out-of-band htmx table fragments in `<template>` tags so htmx 2.0.10 processes the batch-wrap `<tr>` (and the price `<td>`) as independent OOB elements instead of the browser folding an unwrapped OOB `<tr>` into the open basket row — which had left two `batch_id[]` hidden inputs per line and caused every batched sale line to be rejected with «Выберите партию.» (UAT tests 4 and 5).

## What Was Built

**Task 1 — `<template>`-wrapped OOB fragments** (commit `2d7e545`):
- `app/templates/partials/sale_lookup.html`: the OOB price `<td id="price-…" hx-swap-oob="true">` and the critical OOB batch-wrap `<tr id="batch-wrap-{row}" hx-swap-oob="outerHTML">` are each now enclosed in a `<template>…</template>`, with the Jinja `{% if %}` guards kept outside the template so an empty template is never emitted. The main-swap `<td id="name-wrap">` (first top-level element, NOT an OOB element) was left exactly as-is.
- `app/templates/partials/sale_batch_pick.html`: the trailing OOB price `<td>` is wrapped in a `<template>` (removes the orphaned empty `<tr>` the browser otherwise emitted after the main `<tr>` swap). Its first element — the main-swap `<tr id="batch-wrap-{row}">` — was left untouched.
- A short Jinja comment above each new `<template>` marks it as the htmx table-OOB parse-context workaround (UAT tests 4/5) so it is not "cleaned up" later.
- No `hx-swap-oob`, `id`, `colspan`, or include logic changed; autoescape behavior (batch comment/location remain untrusted stored text, Jinja autoescape only) is unchanged.

**Task 2 — regression tests** (commit `344d89a`):
- `test_web_sale_lookup_oob_batch_row_is_template_wrapped`: seeds a 2-batch product, GETs `/sales/lookup`, asserts exactly one `name="batch_id[]"` in the fragment and a regex match for `<template>` immediately preceding the OOB `<tr id="batch-wrap-first" hx-swap-oob="outerHTML"`. Docstring notes the true DOM-merge manifestation is client-side (htmx) and was reproduced manually in the debug session; this structural assertion guards the fix inside the TestClient suite.
- `test_web_sale_three_line_basket_attributes_each_batch`: three products, one open batch each, POST `/sales` with a batch picked on every line — asserts status 200 (not a 422 «Выберите партию.» rejection) and that each product's sale op is attributed to its own batch.

## Verification

- `uv run pytest tests/test_sales.py -x -q` → 46 passed (Task 1, no fragment content changed, only OOB wrapping).
- `uv run pytest tests/test_sales.py -k "template_wrapped or three_line_basket" -q` → 2 passed.
- `uv run pytest tests/test_sales.py -q` → 48 passed (full suite).
- `uv run ruff check tests/test_sales.py` → All checks passed.
- Manual browser UAT (09-UAT.md tests 4/5) remains a human-verify step — the client-side htmx DOM-merge behavior cannot be exercised by the TestClient; the structural + attribution tests are the automated guard.

## Deviations from Plan

None — plan executed exactly as written.

## Success Criteria

- [x] OOB batch-wrap `<tr>` (sale_lookup.html) and OOB price `<td>` (both partials) each `<template>`-wrapped.
- [x] `/sales/lookup` fragment contains exactly one `batch_id[]` hidden input for the line.
- [x] A 3-line batched basket submits with each op attributed to its own batch.

## Self-Check: PASSED
- FOUND: app/templates/partials/sale_lookup.html (`<template>` wrappers present)
- FOUND: app/templates/partials/sale_batch_pick.html (`<template>` wrapper present)
- FOUND: tests/test_sales.py (two new tests present)
- FOUND commit: 2d7e545 (Task 1)
- FOUND commit: 344d89a (Task 2)
