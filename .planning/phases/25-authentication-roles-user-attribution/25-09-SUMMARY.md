---
phase: 25-authentication-roles-user-attribution
plan: 09
subsystem: nav-chrome
tags: [nav, active-state, template, role-03, uat-gap]
requires:
  - app/templates/base.html nav structure (Plan 25-06)
provides:
  - "nav active-state: «Финансы» owns the whole /finance subtree; «Настройки» owns only /settings"
affects:
  - app/templates/base.html
tech-stack:
  added: []
  patterns:
    - "Jinja2 nav active-state via request.url.path.startswith(...) — one prefix per top-level tab"
key-files:
  created: []
  modified:
    - app/templates/base.html
    - tests/test_nav.py
decisions:
  - "Finance report is operator-visible by product decision (UAT test 1), so it belongs under «Финансы»; access control (require_role) untouched — this is a CSS-class active-state fix only."
metrics:
  duration: "~5min"
  completed: "2026-07-18"
  tasks: 1
  files: 2
---

# Phase 25 Plan 09: Finance Report Nav Highlight Fix Summary

Moved the /finance/report nav highlight from the admin «Настройки» tab to the operator-visible «Финансы» tab — closing the single cosmetic UAT gap (25-UAT.md § Gaps, test 1) with a two-line template active-state change plus one render test.

## What Was Built

Two `{% if %}` active-state conditions in `app/templates/base.html` were corrected:

- **Line 44 («Финансы»):** dropped the ` and not request.url.path.startswith("/finance/report")` clause. «Финансы» now stays active for the entire `/finance` subtree, including `/finance/report`.
- **Line 49 («Настройки»):** dropped the ` or request.url.path.startswith("/finance/report")` clause. «Настройки» is active only for `/settings`.

One render test was added to `tests/test_nav.py` (`test_finance_report_activates_finance_not_settings`) that seeds an administrator, logs in via the existing `login(anon_client, ...)` idiom, and asserts:
- `/finance/report` renders `<a href="/finance" class="active">Финансы</a>` and does NOT render `<a href="/settings" class="active">Настройки</a>`;
- `/settings` renders `<a href="/settings" class="active">Настройки</a>`.

## Access Control Unchanged

No route, `require_role` gate, href, link text, the `{% if current_user and current_user.role == "administrator" %}` wrapper, or the CSV endpoint was touched. The finance report is operator-visible by product decision (UAT test 1); the authoritative server-side boundaries remain exactly as-is. This is a nav-highlight (CSS class) change only.

## Verification

- `uv run pytest tests/test_nav.py -x -q` → **4 passed** (three existing nav tests stay green alongside the new active-state test).
- `git diff` confined to the two `{% if %}` conditions on lines 44 and 49 plus the new test — no href/route/text change.

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- FOUND: app/templates/base.html
- FOUND: tests/test_nav.py
- FOUND: .planning/phases/25-authentication-roles-user-attribution/25-09-SUMMARY.md
- FOUND commit: 842bf30 (fix(25-09): finance report nav highlights «Финансы» not «Настройки»)
