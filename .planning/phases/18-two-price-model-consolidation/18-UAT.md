---
status: testing
phase: 18-two-price-model-consolidation
source: [18-VERIFICATION.md]
started: 2026-07-16T12:10:00Z
updated: 2026-07-16T12:10:00Z
---

## Current Test

number: 1
name: Criterion 3 — Colour cue visual sign-off
expected: |
  Amber border/tint (#b45309/#fef9e7) below the reference price, blue border/tint
  (#2563eb/#eff6ff — never #e8effd, the existing search-match tint) above it, no cue
  when exactly equal or when the code has no CatalogPrice reference row. No cue ever
  appears on «Минимальная цена продажи». The cue still fires after an HTMX OOB autofill
  swap. Check across: product card, desktop receipt, desktop sale basket, mobile
  receipt wizard, mobile sale wizard.
awaiting: user response

## Tests

### 1. Criterion 3 — Colour cue visual sign-off
expected: Amber below reference, blue above (never the #e8effd selection tint), no cue when equal/no-reference, no cue ever on min_sale, cue survives OOB swaps. Test on product card, desktop receipt, desktop sale, mobile receipt wizard, mobile sale wizard.
result: [pending]

### 2. Text-badge expectation check
expected: Confirm whether a visible text label (e.g. «ниже справочной») alongside the colour is expected (per the original design note), or whether the shipped colour-only cue is acceptable. Current code explicitly documents that WCAG 1.4.1 (Use of Color) is not met as shipped.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
