---
status: testing
phase: 02-catalog-dictionary-search
source: [02-VERIFICATION.md]
started: 2026-07-08T21:15:00Z
updated: 2026-07-08T21:15:00Z
---

## Current Test

number: 1
name: Instant search feel in the browser
expected: |
  On /products, typing a partial Cyrillic name (e.g. «губная») or a partial code
  updates results in place without page reload, with a ~300ms debounce feel;
  matched substring highlighted with <mark>.
awaiting: user response

## Tests

### 1. Instant search feel in the browser
expected: Results update in place without page reload after a ~300ms pause; matched text highlighted with <mark>. Try both a partial Cyrillic name («губная») and a partial code on /products.
result: [pending]

### 2. Dictionary autofill fills empty name, never overwrites typed name
expected: Add a code→name pair at /dictionary, then on /products/new type that code with the name field empty — after ~300ms the name fills with the dictionary value plus hint «Название подставлено из справочника — можно изменить.». Separately, type your own name first and then the code — the pre-typed name is NEVER overwritten (nothing changes).
result: [pending]

### 3. WR-01 race guard — typed name survives in-flight lookup
expected: Type a known code, then immediately start typing a name BEFORE the ~300ms lookup returns — the in-flight lookup fragment is discarded and the operator's typed name survives.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
