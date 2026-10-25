---
phase: quick-261025-rtn
plan: 01
subsystem: reports, finance, dashboard, export
commit: 4f8b1f7
version: 1.141
---

# Summary: returns reverse their sale in every report

- sales_profit_report / top_selling_products / stream_sales_csv now read
  sale + return ops; a return nets revenue, cost and profit on its own
  business date. Report shows Продано / Возвращено / Итого and Продажи /
  Возвраты lines.
- cash_expense_total = withdrawals only; cash_flow_report shows the refund as
  a negative income line. D-05 reconciliation unchanged.
- User guide: docs/PROFIT-RU.md.

Verification:
- RED first: 2 new tests failed with KeyError 'units_returned', then passed.
- Full suite: 1922 passed / 13 skipped / 4 failed — the 4 are the known
  test_sync_ui lock failures (pre-existing).
- Live s1 (1.141), 25.10.2026: /reports/sales 2 / 2 / 0, Продажи 400,00,
  Возвраты -400,00, Выручка 0,00, Прибыль 0,00; Главная today/week/month
  0,00 / 0,00 / 0,00; /finance gross 0,00, net 0,00, balance 0,00 ₽;
  /finance/report Приход 400,00 - 400,00 = 0,00, Расход 0,00.

Deferred: supplier payment vs COGS double count (user's item 4).
Noticed, not touched: /finance history shows the literal «None» in the
Комментарий column for sale/return rows (pre-existing).
