---
status: closed
phase: 17-financial-reports-export-dashboard-analytics
source: [17-VERIFICATION.md]
started: 2026-07-15T00:00:00Z
updated: 2026-07-15T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Dashboard tiles + period selector behavior (desktop and mobile)
expected: |
  Open /finance and /m/finance; change the light period selector preset. Three tiles
  render with exact UI-SPEC copy; net tile always shows the cash-outflow caveat; stock
  tile always shows «на текущий момент»; changing the period updates gross/net only —
  stock tile, balance, forms, and history stay visually unchanged.
result: pass

### 2. CSV export opens correctly in Excel
expected: |
  Download CSV from /finance/report and /m/finance/report, open in Excel (RU locale).
  Single BOM detected, ;-separated columns (Когда/Категория/Комментарий/Сумма), correct
  Cyrillic, signed amounts like «-12,00», no formula execution on notes starting with
  =/+/-/@.
result: issue
reported: "все хорошо но ненащел точку входа на эту страницу начиная с главной"
severity: major

### 3. Mobile dashboard tile layout on a real/emulated phone viewport
expected: |
  Open /m/finance and /m/finance/report on a ~360-414px viewport. Tiles remain readable
  without overflow/clipping, in a 2-column layout (fixed in commit 3b62940 — standard
  end-of-phase visual confirmation).
result: pass

## Summary

total: 3
passed: 2
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "CSV export page is reachable via navigation from the main page"
  status: resolved
  resolved_by: "17-05-PLAN.md / 17-05-SUMMARY.md (commits 5ff71b7, 2308d01, a3bb704)"
  reason: "User reported: все хорошо но ненащел точку входа на эту страницу начиная с главной"
  severity: major
  test: 2
  root_cause: "The link to /finance/report exists but is low-prominence and mislabeled. Desktop top nav (base.html) has no direct entry to /finance/report; the only link is a bare unstyled <a> in pages/finance.html sandwiched between the metrics tiles and a heavier 'Баланс кассы' section. A second path exists via reports_landing.html but it's one of 6 links crammed into a paragraph. Mobile has no persistent nav at all (mobile_base.html) — only the home tile grid, and mobile_pages/finance.html has the same unstyled inline-link pattern as desktop. Link text ('Отчёт по кассе за период' / 'Движения кассы') never says 'export'/'CSV'/'скачать', which mismatches the tester's mental model."
  artifacts:
    - path: "app/templates/pages/finance.html"
      issue: "Report link present (line 10) but unstyled plain <a>, no button/CTA treatment, buried between tiles and balance section"
    - path: "app/templates/mobile_pages/finance.html"
      issue: "Same low-prominence unstyled link pattern (line 15) on mobile"
    - path: "app/templates/pages/reports_landing.html"
      issue: "Alternate path to report exists but crowded among 6 links in one paragraph"
    - path: "app/templates/base.html"
      issue: "Desktop top nav has 'Финансы' -> /finance but no direct entry to /finance/report"
    - path: "app/templates/mobile_pages/home.html"
      issue: "Mobile home tile grid has no direct report/export tile; mobile_base.html has no persistent nav"
  missing:
    - "A distinctly-labeled, higher-prominence entry point (.button or .mobile-tile styled) using 'export'/'CSV'/'скачать' wording, reachable in one hop from the main page on both desktop and mobile"
  debug_session: ".planning/debug/finance-report-nav-entry-missing.md"
