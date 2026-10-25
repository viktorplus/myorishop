---
quick_id: 261026-wha
phase: quick-261026-wha
plan: 01
type: execute
mode: quick
autonomous: true
---

# Operator warehouse access (admin assigns warehouses per operator)

Decisions agreed with the user (2026-10-25, «да по всем»):
1. Scope = warehouse restriction only (no per-section permission toggles).
2. Every stock-moving op (receipt, sale, writeoff, correction, return,
   transfer) only from/into the operator's warehouses.
3. Transfer: source must be the operator's, destination may be any warehouse.
4. Operator sees nothing of other warehouses (stock, batches, history, search).
5. Reports / Главная scoped to the operator's warehouses; Финансы (cash) and
   Экспорт closed for operators (cash is per currency, not per warehouse).
6. Migration assigns every active warehouse to every existing operator; a new
   operator has none and sees «обратитесь к администратору».
7. Admin tool: warehouse checkboxes per operator on /settings/users.
8. Customers and the product dictionary stay shared.

Mechanism:
- `user_warehouses` (user_id, warehouse_id) + migration 0029 (seed).
- auth_guard resolves the allowed set once per request into a contextvar;
  `security.allowed_warehouse_ids()` -> None (admin / no user = unrestricted)
  or a frozenset; `security.warehouse_scope(column)` -> SQL predicate.
- Choke points: batches.active_warehouses (scoped=False for transfer
  destinations), open_batches, batches_for_products, expiring_batches;
  ledger.record_operation guard (except the incoming transfer leg).
- Read surfaces: history_view, dashboard (metrics, stock, feed), reports
  (sales, top, writeoffs, stale, stock), locations, customers purchase views,
  product quantities (scoped sum), returns origin + recent sales, batch edit.
- finance / mobile_finance / export / backup routers -> administrator only;
  nav links hidden.
