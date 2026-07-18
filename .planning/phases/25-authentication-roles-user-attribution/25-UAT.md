---
status: testing
phase: 25-authentication-roles-user-attribution
source: [25-VERIFICATION.md]
started: 2026-07-18T07:43:04Z
updated: 2026-07-18T07:43:04Z
---

## Current Test

number: 1
name: Product decision on WR-02 — intended visibility of the whole-business cash-flow/profit report (/finance/report, /finance/report.csv)
expected: |
  A human/product owner confirms whether the finance profit/cash-flow report is
  operator-visible (as the code + the operator-reachable «Отчёт и экспорт CSV» button
  on /finance imply) or administrator-only.
  - If operator-visible (current behaviour): correct the base.html nav active-state so
    /finance/report no longer highlights the admin «Настройки» tab (cosmetic only).
  - If administrator-only: add a server-side require_role("administrator") gate to the
    finance report routes (currently absent) and file them under «Настройки» in the nav.
awaiting: user response

## Tests

### 1. Product decision on WR-02 — finance report visibility
expected: |
  Human confirms operator-visible vs administrator-only for /finance/report and
  /finance/report.csv. Success Criterion 4 is NOT violated as written (finance is not one
  of the four enumerated admin-only sections), so this is a product-intent confirmation,
  not a codebase gap. If admin-only is chosen, the routes need a require_role gate.
result: [pending]

### 2. First-run + authentication browser flow (visual UAT)
expected: |
  Launch the app against an empty database and confirm the end-to-end auth UX on both
  desktop and mobile:
  - Zero users → the app lands on /setup and no other page is reachable.
  - Creating the initial administrator logs you straight in (no shipped default credentials).
  - A browser refresh keeps the session (signed cookie); «Выйти» ends it.
  - An operator does NOT see «Настройки»; an administrator does.
  - The /login and /setup screens render correctly.
  The underlying behaviours are covered by automated tests (981 passed); this test verifies
  the visual/UX layer (UI-SPEC line 206 UAT gates) that grep cannot check.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
