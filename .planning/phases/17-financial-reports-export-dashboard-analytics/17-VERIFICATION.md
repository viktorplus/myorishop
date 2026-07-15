---
phase: 17-financial-reports-export-dashboard-analytics
verified: 2026-07-15T00:00:00Z
status: human_needed
score: 7/7 must-haves verified (code-level); 3 items require human/visual verification
overrides_applied: 0
human_verification:
  - test: "Open /finance and /m/finance in a browser; change the light period selector"
    expected: "Три плитки («Валовая прибыль», «Чистая прибыль», «Стоимость склада») отображаются с точными подписями из UI-SPEC; плитка «Чистая прибыль» всегда показывает предупреждение «...Это не бухгалтерская прибыль.»; плитка склада всегда показывает «на текущий момент»; смена периода обновляет только валовую/чистую прибыль, плитка склада и баланс/формы/история остаются без изменений."
    why_human: "Visual rendering, caveat discoverability, and HX-swap-scope correctness on real DOM cannot be asserted by grep/pytest alone (though covered indirectly by web tests)."
  - test: "Download CSV from /finance/report and /m/finance/report, open in Excel with RU locale"
    expected: "One BOM, ';'-delimited columns (Когда/Категория/Комментарий/Сумма) render as separate Excel columns, Cyrillic text intact, signed amounts like '-12,00', no formula execution for notes starting with =/+/-/@."
    why_human: "Excel-specific rendering behavior cannot be verified by pytest; only byte-level BOM/delimiter/escape correctness was verified programmatically."
  - test: "Open /m/finance and /m/finance/report on a real ~360-414px phone viewport (or browser dev-tools mobile emulation)"
    expected: "The three dashboard tiles remain readable (no text overflow/clipping), now in a 2-column layout."
    why_human: "FIXED in commit 3b62940 (post-verification): `.mobile-shell .metric-grid { grid-template-columns: 1fr 1fr; }` added, mirroring `.mobile-tile-grid`'s 2-column choice for the same viewport. Visual confirmation on a real device is still the standard end-of-phase check, but this is no longer an unaddressed known risk."
---

# Phase 17: Financial Reports, Export & Dashboard Analytics Verification Report

**Phase Goal:** Operator can analyze cash flow and overall profitability for any period, export cash movements to CSV, and see the till's business-health metrics (profit, stock value) on the Финансы dashboard
**Verified:** 2026-07-15
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can view a report of cash movements for a chosen period, broken down by income (sales) vs. expense category | ✓ VERIFIED | `app/services/finance_reports.py::cash_flow_report` groups by `CASH_BUCKETS`; `/finance/report` + `/m/finance/report` render `partials/cash_flow_report.html` with Приход/Расход tables; live `GET /finance/report` returns 200 with both sections and CSV link (confirmed via TestClient probe). |
| 2 | Operator can export a period's cash movements to CSV, opening correctly in Excel (BOM/semicolon/formula-escape) | ✓ VERIFIED (code) / needs human for actual Excel render | `app/services/export.py::stream_cash_movements_csv` reuses `_encode_once/_csv_rows/_csv_safe` verbatim; `tests/test_export.py` asserts single BOM, `;` delimiter, RU labels, NULL-note→"", `=CMD()` escape, half-open bounds. `/finance/report.csv` and `/m/finance/report.csv` routes delegate correctly. |
| 3 | Финансы dashboard shows gross profit for the selected period | ✓ VERIFIED | `_metrics_context` calls `sales_profit_report`; `finance_tiles.html` renders «Валовая прибыль» tile with `metrics.gross_profit_cents \| cents` and the cost-unknown caveat. Present on both `/finance` and `/m/finance`. |
| 4 | Финансы dashboard shows net profit for the same period | ✓ VERIFIED | `net_profit_cents = gross["totals"]["profit_cents"] + expense` (plain addition, `cash_expense_total` rows already signed negative) — confirmed by reading `app/routes/finance.py:87` and `app/routes/mobile_finance.py`; net tile always renders the mandatory `.muted` cash-outflow caveat line (`не бухгалтерская прибыль`), never conditional. |
| 5 | Финансы dashboard shows total stock value at purchase cost and at sale price | ✓ VERIFIED | `stock_valuation(session)` — product-level SUM over active (non-deleted) products, NULL-price rows excluded from sums (not zero-filled) and counted separately; called unconditionally (point-in-time) in `_metrics_context`; tile shows «По закупке»/«По продаже» plus «на текущий момент» cue and conditional unknown-price caveats. |

### CR-01 / CR-02 Fix Verification (post-review commit b8cc123)

| # | Fix | Status | Evidence |
|---|-----|--------|----------|
| 6 | CR-01: `/finance/history` and `/m/finance/history` no longer 500 on plain (non-HX) GET | ✓ VERIFIED | Diff confirms `**_metrics_context(session, "", "")` merged into both routes' non-HX fallback context (`app/routes/finance.py:156`, `app/routes/mobile_finance.py:183`). Live probe: `GET /finance/history?bucket=withdrawal` → 200; `GET /m/finance/history?bucket=withdrawal` → 200. Regression tests `test_web_cash_history_non_hx_full_page_renders` and `test_mobile_cash_history_non_hx_full_page_renders` exist in `tests/test_finance.py` and pass. |
| 7 | CR-02: `/finance/report` and `/m/finance/report` are now reachable from the UI | ✓ VERIFIED | `pages/finance.html` and `mobile_pages/finance.html` each gained `<p><a href="/finance/report">Отчёт по кассе за период</a></p>` (resp. `/m/finance/report`); `pages/reports_landing.html` now lists `<a href="/finance/report">Движения кассы</a>` alongside the other period reports. Live probe: all three links present in rendered HTML (`/finance` → true, `/reports` → true, `/m/finance` → true). |

**Score:** 7/7 truths verified at the code/test level. 0 gaps. 3 items flagged for mandatory human/visual verification (deferred per `human_verify_mode: end-of-phase`, harvested from 17-02/17-03/17-04 PLAN `<verify><human-check>` blocks and 17-VALIDATION.md's Manual-Only Verifications table).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/finance_reports.py` | `cash_expense_total`, `stock_valuation`, `cash_flow_report` — SELECT-only | ✓ VERIFIED | All three functions present, compose category sets from `CASH_BUCKETS`, use `.is_(None)` NULL-exclusion, no write calls. |
| `app/services/export.py` | `stream_cash_movements_csv` + T-06-09 docstring exception | ✓ VERIFIED | Function present, reuses `_encode_once(_csv_rows(...))` verbatim; docstring documents the bounded `_resolve_period`-clamped exception. |
| `app/routes/finance.py` | `/finance/metrics`, `/finance/report`, `/finance/report.csv`, `_metrics_context` | ✓ VERIFIED | All routes present and wired; `_metrics_context` reused by `finance_page`, `finance_metrics`, and (post-fix) `finance_history`. |
| `app/routes/mobile_finance.py` | `/m/finance/metrics`, `/m/finance/report`, `/m/finance/report.csv` | ✓ VERIFIED | All present, structural clones of desktop with `finance_base=/m/finance`; `mobile_finance_history` post-fix merges `_metrics_context`. |
| `app/templates/partials/finance_tiles.html` | gross/net/stock tiles, mandatory net caveat | ✓ VERIFIED | Exact UI-SPEC copy, mandatory caveat unconditional, unknown-price caveats conditional, no sign-coloring. |
| `app/templates/partials/cash_flow_report.html` | Приход/Расход results partial | ✓ VERIFIED | Three-branch structure (error/empty/tables), labels via `CASH_CATEGORIES` global only. |
| `app/templates/pages/finance_report.html` / `mobile_pages/finance_report.html` | report page shells + CSV link | ✓ VERIFIED | Plain `<a href>` CSV download (never `hx-get`), `#cashflow-results` div, period filter wired. |
| `app/static/style.css` | `.metric-grid`/`.metric-tile` | ✓ VERIFIED (existence) / ⚠️ see WR-01 | Present, reuses existing tokens; NO responsive breakpoint — flagged as human-verification item above. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `finance_reports.py::cash_expense_total` | `CASH_BUCKETS["withdrawal"]`/`["return"]` | category composition | ✓ WIRED | grep confirms `CASH_BUCKETS["withdrawal"] + CASH_BUCKETS["return"]`, no hardcoded string list. |
| `finance_reports.py::cash_flow_report` | `cash_expense_total` | expense-subtotal reconciliation (D-05) | ✓ WIRED | Reconciliation is structural (same bucket sets) and covered by a dedicated test asserting equality. |
| `export.py::stream_cash_movements_csv` | `_encode_once`/`_csv_rows`/`_csv_safe` | verbatim reuse | ✓ WIRED | grep confirms `_encode_once(_csv_rows(...))` call. |
| `pages/finance.html` | `/finance/metrics` | period_filter → `#finance-metrics` | ✓ WIRED | `period_action`/`period_target` set correctly, div id matches. |
| `pages/finance.html` | `/finance/report` | plain `<a href>` link | ✓ WIRED | Confirmed present (and post-CR-02 fix, actually reachable). |
| `routes/finance.py::finance_report_page` | `cash_flow_report` service | `_resolve_period → local_day_bounds_utc → cash_flow_report → HX branch` | ✓ WIRED | Matches `reports_sales_page` shape exactly. |
| `routes/finance.py::finance_history` (post-fix) | `_metrics_context` | merged into non-HX fallback | ✓ WIRED | Confirmed via diff + live 200 probe + regression tests. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Plain GET /finance/history no longer 500s (CR-01) | `TestClient().get("/finance/history?bucket=withdrawal")` | 200 | ✓ PASS |
| Plain GET /m/finance/history no longer 500s (CR-01) | `TestClient().get("/m/finance/history?bucket=withdrawal")` | 200 | ✓ PASS |
| /finance/report reachable + CSV link present | `TestClient().get("/finance/report")` | 200, contains `/finance/report.csv` | ✓ PASS |
| /finance links to /finance/report (CR-02) | `TestClient().get("/finance")` | contains `/finance/report` | ✓ PASS |
| /reports landing links to /finance/report (CR-02) | `TestClient().get("/reports")` | contains `/finance/report` | ✓ PASS |
| /m/finance links to /m/finance/report (CR-02) | `TestClient().get("/m/finance")` | contains `/m/finance/report` | ✓ PASS |
| Full test suite green | `uv run pytest -q` | 676 passed, 0 failed | ✓ PASS |
| Phase-scoped tests green | `uv run pytest tests/test_finance_reports.py tests/test_export.py tests/test_finance.py -q` | 123 passed | ✓ PASS |
| Ruff clean on touched modules | `uv run ruff check app/services/finance_reports.py app/services/export.py app/routes/finance.py app/routes/mobile_finance.py` | All checks passed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FIN-08 | 17-01, 17-03, 17-04 | Отчёт по движениям кассы за период (приход/расход по категориям) | ✓ SATISFIED | `cash_flow_report` + `/finance/report` + `/m/finance/report`, marked Complete in REQUIREMENTS.md |
| FIN-09 | 17-01, 17-03, 17-04 | CSV-экспорт движений кассы | ✓ SATISFIED | `stream_cash_movements_csv` + `.csv` routes, marked Complete |
| FIN-10 | 17-01, 17-02, 17-04 | Дашборд показывает валовую прибыль | ✓ SATISFIED | Gross tile via `sales_profit_report`, marked Complete |
| FIN-11 | 17-01, 17-02, 17-04 | Дашборд показывает чистую прибыль | ✓ SATISFIED | Net tile = gross + cash_expense_total, marked Complete |
| FIN-12 | 17-01, 17-02, 17-04 | Дашборд показывает стоимость товара на складе | ✓ SATISFIED | Stock tile via `stock_valuation`, marked Complete |

No orphaned requirements — `.planning/REQUIREMENTS.md` maps exactly FIN-08..FIN-12 to Phase 17, all five declared across the four plans' `requirements:` frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/static/style.css` | 331-343 | `.metric-grid` fixed 3-column, shared by desktop (960px) and mobile (480px) shells | ✓ FIXED (commit 3b62940) | `.mobile-shell .metric-grid` now overrides to 2 columns, mirroring `.mobile-tile-grid`. Still routed to human verification above for standard end-of-phase visual confirmation. |
| `app/routes/finance.py` + `app/routes/mobile_finance.py` | throughout | `_metrics_context`, `_history_context` byte-for-byte duplicated across desktop/mobile routers (code review WR-02, unfixed) | ℹ️ INFO | Same duplication pattern that caused CR-01; not a functional gap today (both call sites are now patched), but a latent maintenance risk if either router changes and the other is forgotten. |
| `app/services/export.py:198` | `op.created_by` bypasses `_csv_safe` (code review IN-01, unfixed) | ℹ️ INFO | Out of Phase 17 scope (pre-existing `stream_sales_csv` code, not touched by this phase); noted for completeness, does not affect Phase 17 goal. |

No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers found in any Phase-17-touched file.

### Human Verification Required

### 1. Dashboard tiles + period selector behavior (desktop and mobile)

**Test:** Open `/finance` and `/m/finance`; change the light period selector preset.
**Expected:** Three tiles render with exact UI-SPEC copy; net tile always shows the cash-outflow caveat; stock tile always shows «на текущий момент»; changing the period updates gross/net only — stock tile, balance, forms, and history stay visually unchanged.
**Why human:** Visual/DOM-swap-scope confirmation beyond what pytest's HTML-substring assertions cover.

### 2. CSV export opens correctly in Excel

**Test:** Download from `/finance/report` and `/m/finance/report`, open in Excel (RU locale).
**Expected:** Single BOM detected, `;`-separated columns (Когда/Категория/Комментарий/Сумма), correct Cyrillic, signed amounts like «-12,00», no formula execution on notes starting with `=`/`+`/`-`/`@`.
**Why human:** Excel's own file-open behavior cannot be exercised by pytest; only byte-level correctness was verified programmatically.

### 3. Mobile dashboard tile layout on a real/emulated phone viewport (FIXED, needs visual confirmation)

**Test:** Open `/m/finance` and `/m/finance/report` on a ~360-414px viewport.
**Expected:** Tiles remain readable without overflow/clipping, in a 2-column layout.
**Why human:** WR-01 (fixed 3-column grid shared with the 960px desktop container) was fixed in commit `3b62940` — `.mobile-shell .metric-grid` now uses 2 columns, mirroring `.mobile-tile-grid`. Standard end-of-phase visual confirmation still applies; no longer an unaddressed known risk.

### Gaps Summary

No FAILED must-haves at the code level — all 5 roadmap success criteria and both post-review-fix claims (CR-01, CR-02) are verified present, substantive, and wired, with passing automated tests (676/676 full suite) and live route probes confirming the previously-500ing routes now return 200 and the previously-unreachable report page is now linked from three places.

Status is `human_needed` rather than `passed` solely because of mandatory end-of-phase human/visual checks (dashboard tile rendering, Excel CSV behavior) that this workflow always routes to a human, plus one specific known-risk item (WR-01, the un-fixed non-responsive `.metric-grid` on mobile) that static analysis strongly suggests will fail a real-device visual check even though it was not part of the required CR-01/CR-02 fix scope.

---

_Verified: 2026-07-15_
_Verifier: Claude (gsd-verifier)_
