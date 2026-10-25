---
phase: quick-261026-wha
plan: 01
subsystem: auth, warehouses, every stock surface
commit: cff54e4
version: 1.142
---

# Summary: operators work only in their assigned warehouses

Implemented as planned (see PLAN). Choke points: security contextvar
(allowed set resolved once in auth_guard), batches pickers, ledger
record_operation guard. Admin tool on /settings/users.

Verification:
- tests/test_warehouse_access.py: 13 tests. Mutation check (scoping
  disabled) -> all 8 scope tests fail, so they test the filter.
- Full suite: 1928 passed / 13 skipped / 10 failed. The 10 are pre-existing:
  4 test_sync_ui lock failures and 5 «dated» history tests that fail between
  00:00 and 03:00 MSK (UTC day != local day; reproduced identically on a
  clean HEAD worktree); 1 test_mobile_home tabbar test updated for the
  admin-only Финансы tab and passing.
- s1: pg_dump backups/myorishop-2026-10-26-pre-0029.dump (verified with
  pg_restore --list), migration 0028 -> 0029 applied, Алла/Оксана/Ольга got
  all 4 warehouses, admin page shows the «Склады» column (browser).
- Live operator view (in-container GET-only script, Оксана restricted to
  «Склад по умолчанию» in memory, DB untouched): /finance, /m/finance,
  /export, /backup, /offline/export -> 403; Главная has no «Расход», 3 codes
  in stock, cost 4756,00; /reports/stock 5 rows; /history shows no «Офис».

Not done / known limits:
- Product list SORT by quantity still sorts by the global quantity.
- A real operator login on s1 was not exercised (no operator password).
- A new warehouse is not auto-assigned to operators.
