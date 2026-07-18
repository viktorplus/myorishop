---
status: complete
phase: 25-authentication-roles-user-attribution
source: [25-VERIFICATION.md]
started: 2026-07-18T07:43:04Z
updated: 2026-07-18T21:19:34Z
---

## Current Test

[testing complete]

## Tests

### 1. Product decision on WR-02 — finance report visibility
expected: |
  Human confirms operator-visible vs administrator-only for /finance/report and
  /finance/report.csv. Success Criterion 4 is NOT violated as written (finance is not one
  of the four enumerated admin-only sections), so this is a product-intent confirmation,
  not a codebase gap. If admin-only is chosen, the routes need a require_role gate.
result: issue
reported: "виден оператору — access is correct as-is; but /finance/report still highlights the admin «Настройки» nav tab in base.html"
severity: cosmetic

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
result: pass
notes: |
  Verified live via browser against a fresh empty DB (DB_PATH=data/uat_fresh.db):
  - / redirected to /setup; /login, /products, /settings/users, /finance/report all 303
    while zero users existed; /setup returned 200. (/sales is POST-only → GET 405 is
    expected; the page is /sales/new.)
  - Created initial administrator on /setup → landed straight on / logged in as «Админ Тест»
    (auto-login, no shipped default credentials).
  - Session persisted across navigations/refresh (signed cookie); «Выйти» returned to /login
    with the nav hidden.
  - Created an operator, logged in as operator: «Настройки» tab absent from nav; admin sees it.
  - Server-side gate confirmed: operator hitting /settings/users returns
    {"detail":"Доступ только для администратора."} (403) — not merely nav-hidden.
  - /login and /setup render correctly.

## Summary

total: 2
passed: 1
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "The operator-visible finance report (/finance/report) must not highlight the administrator-only «Настройки» nav tab in base.html."
  status: failed
  reason: "User confirmed finance report is intentionally operator-visible; the active-state logic in base.html incorrectly highlights the «Настройки» admin tab when /finance/report is open."
  severity: cosmetic
  test: 1
  root_cause: |
    app/templates/base.html hard-codes the finance report under the admin «Настройки» tab,
    written under the assumption the report is administrator-only:
    - line 49: «Настройки» is active when path startswith "/settings" OR "/finance/report"
    - line 44: «Финансы» is explicitly de-activated on "/finance/report"
    Confirmed live: as administrator on /finance/report the «Настройки» tab renders bold/active.
    Product decision (Test 1): the report is operator-visible, so it belongs to «Финансы».
  fix: |
    In app/templates/base.html:
    - line 44: highlight «Финансы» for the whole /finance subtree — drop the
      `and not request.url.path.startswith("/finance/report")` exclusion.
    - line 49: highlight «Настройки» only for /settings — drop the
      `or request.url.path.startswith("/finance/report")` clause.
  artifacts: ["app/templates/base.html:44", "app/templates/base.html:49"]
  missing: []
