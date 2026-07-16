---
status: complete
phase: 18-two-price-model-consolidation
source: [18-VERIFICATION.md]
started: 2026-07-16T12:10:00Z
updated: 2026-07-16T14:25:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Criterion 3 — Colour cue visual sign-off
expected: Amber below reference, blue above (never the #e8effd selection tint), no cue when equal/no-reference, no cue ever on min_sale, cue survives OOB swaps. Test on product card, desktop receipt, desktop sale, mobile receipt wizard, mobile sale wizard.
result: pass

### 2. Text-badge expectation check
expected: Confirm whether a visible text label (e.g. «ниже справочной») alongside the colour is expected (per the original design note), or whether the shipped colour-only cue is acceptable. Current code explicitly documents that WCAG 1.4.1 (Use of Color) is not met as shipped.
result: pass

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
