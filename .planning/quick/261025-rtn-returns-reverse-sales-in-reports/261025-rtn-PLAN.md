---
quick_id: 261025-rtn
phase: quick-261025-rtn
plan: 01
type: execute
mode: quick
autonomous: true
---

# Returns reverse their sale in every report (never an expense)

Live repro on s1 (2026-10-25): 2 sales of 38838 at 200,00 (cost 100,00), both
fully returned. /reports/sales showed 2 / 400 / 200 / 200 (returns ignored);
Главная and /finance showed revenue 400, expense -400, net profit -200 (refund
booked as an expense while the returned goods' cost was never added back).

Decisions (agreed with the user):
1. A return is bucketed by ITS OWN business date — closed periods never change.
2. Returns are shown separately (Возвращено column, Продажи / Возвраты lines).
3. Top sellers net returns (net <= 0 drops out); sales CSV lists returns as
   negative-qty rows (no new column — D-23 keeps «Внесено» last); stale
   products and customer purchase history unchanged.
4. Supplier payments vs COGS double count — DEFERRED, named in docs/PROFIT-RU.md.

Tasks:
- RED: tests/test_reports.py scenario test (2 sells + 2 returns -> 0 everywhere)
  and the period test (return books on the return day).
- sales_profit_report: sale+return, net figures + sold/returned/returns_cents.
- top_selling_products: sale+return, HAVING net > 0.
- cash_expense_total: withdrawals only; cash_flow_report: return -> income.
- Templates: sales_report_results.html, finance_tiles.html caption.
- export.stream_sales_csv: include returns.
- Update the 5 tests that pinned «refund = expense».
- docs/PROFIT-RU.md user-facing guide (RU). Version 1.140 -> 1.141.
