---
status: diagnosed
trigger: "history-return-button-and-code-column: On /history there is no discoverable return (возврат) action for a legacy (pre-batch) sale, and the table lacks a product-code column."
created: 2026-07-12T12:45:26Z
updated: 2026-07-12T12:45:26Z
---

## Current Focus

hypothesis: CONFIRMED — /history's row template (history_rows.html) was built as an
8-column "every operation type" view but never carried over the «Вернуть» return
link or the separate «Код» column that the two sibling sale-listing templates
(recent_sales.html on /sales, purchase_history.html on customer_detail) already
have, despite the row dict having identical data available (r.op.sale_id, r.op.id,
r.product.id, r.product.code).
test: read history_rows.html, history.html, recent_sales.html, purchase_history.html,
returns.py, operations.py side by side
expecting: confirmed via direct code comparison
next_action: none — diagnosis complete, returning to caller (goal: find_root_cause_only)

## Symptoms

expected: A pre-Phase-9 (NULL batch_id) stock op renders the muted «До внедрения
партий» second line; a batched op renders «Партия: {срок}{ — comment}»;
price-change/product rows show no batch second line; a return of a legacy sale
shows «Возврат в партию: Остаток до внедрения партий» — this last part requires
the ability to actually initiate a return from /history.
actual: "все хорошо но кнопки возврат не нашел и нужна еще одна колонка код
продукта вместо поиска ее в поле Товар" (everything else looked fine, but no
return button could be found, and a product-code column is needed instead of
searching for it inside the Товар field).
errors: None reported.
reproduction: Test 6 in UAT (.planning/phases/09-batch-tracking-ledger-integration/09-UAT.md)
— open /history, look for a way to initiate a return on a legacy sale row, and
look for a product-code column.
started: Discovered during UAT of Phase 9 (batch tracking / ledger integration).

## Eliminated

(none — root cause found on first pass via direct comparison of sibling templates)

## Evidence

- timestamp: 2026-07-12T12:45:00Z
  checked: app/templates/partials/history_rows.html (the /history table body)
  found: |
    Product cell renders `{{ r.product.name }} ({{ r.product.code }})` — code is
    inline in parentheses inside the same "Товар" cell, not a separate `<th>Код</th>`
    column. thead in app/templates/pages/history.html has 8 columns: Когда, Тип,
    Товар, Кол-во, Цена, Себестоимость, Причина, Кто — no "Код" column, no
    "Действие" column.
  implication: Confirms the code-column gap exactly as reported — code exists in
    the DOM but requires reading/searching inside the Товар cell text, not a
    sortable/scannable dedicated column.

- timestamp: 2026-07-12T12:45:00Z
  checked: app/templates/partials/recent_sales.html (used on /sales page, GET /sales)
  found: |
    Has a dedicated "Код" `<th>` column (`{{ r.product.code }}` in its own `<td>`)
    AND a "Действие" column with:
    `<a href="#" hx-get="/returns?sale_id={{ r.op.sale_id }}&product_id={{ r.product.id }}&origin_op_id={{ r.op.id }}" hx-target="#return-slot" hx-swap="innerHTML">Вернуть</a>`
    plus a sibling `<div id="return-slot"></div>` that the GET /returns response
    swaps into.
  implication: The «Вернуть» return-entry-point pattern already exists and is
    fully wired (route, service, template) — it's just never rendered on the
    /history page.

- timestamp: 2026-07-12T12:45:00Z
  checked: app/templates/partials/purchase_history.html (used on customer_detail
    page, per app/routes/customers.py + app/services/customers.py)
  found: |
    Identical pattern to recent_sales.html — separate "Код" column, separate
    "Действие" column with the same «Вернуть» hx-get link shape, own
    `<div id="return-slot"></div>`. Comment explicitly: "D-05: entry point into
    the return-linked slice, same shape as recent_sales.html's «Вернуть» link."
  implication: This is the THIRD sale-listing surface in the app, and the THIRD
    time the Код+Действие(Вернуть) pattern was implemented identically — /history
    is the only sale-listing view that omits both.

- timestamp: 2026-07-12T12:45:00Z
  checked: app/services/operations.py history_view() — the query backing /history
  found: |
    Each row dict already contains `"op": Operation` (has .sale_id, .id, .type)
    and `"product": Product` (has .id, .code) via
    `select(Operation, Product, Batch).join(Product, ...).outerjoin(Batch, ...)`.
    Identical shape to what recent_sales()/purchase_history's query provide.
  implication: No data-availability blocker. Adding a Код column and a
    conditional (`r.op.type == "sale"`) «Вернуть» link to history_rows.html would
    require zero backend/query changes — this is purely a template omission, not
    a deeper architectural gap.

- timestamp: 2026-07-12T12:45:00Z
  checked: app/routes/returns.py GET /returns handler + _resolve_origin()
  found: |
    GET /returns accepts sale_id/product_id/origin_op_id as plain query params
    from ANY caller — it has no dependency on being linked from recent_sales.html
    specifically. It resolves the origin sale op the same way regardless of
    entry point (recent_sales, purchase_history, or a hypothetical /history link).
  implication: The return flow is entry-point-agnostic; a /history "Вернуть" link
    using the exact same hx-get URL shape as the other two templates would work
    without any change to routes/returns.py or services/returns.py.

- timestamp: 2026-07-12T12:45:00Z
  checked: app/services/sales.py recent_sales(session, limit=10)
  found: |
    /sales page's "Последние продажи" list (where the only currently-existing
    return entry point lives, besides per-customer purchase history) is capped
    at the last 10 sale operations, newest first.
  implication: A pre-Phase-9 "legacy" sale (by definition older than the
    batch-tracking migration) is very unlikely to still appear in that last-10
    list, and the user may not have an associated customer to view via
    customer_detail's purchase_history either. /history (unbounded, paginated,
    filterable by product) is the only view where a UAT tester could realistically
    locate an old legacy sale row at all — which is exactly why its missing
    return action blocked Test 6 in the UAT.

## Resolution

root_cause: |
  app/templates/partials/history_rows.html (the /history table row partial) was
  built to cover all 8 operation types uniformly (per its own header comment:
  "extending the recent_sales.html/purchase_history.html row shape") but the
  implementation stopped short of actually carrying over two things those two
  sibling templates already have: (1) a dedicated "Код" `<th>`/`<td>` column
  (code is instead squeezed inline into the "Товар" cell as "Name (CODE)"), and
  (2) a "Действие" column with the «Вернуть» hx-get link
  (`/returns?sale_id=...&product_id=...&origin_op_id=...`) for `sale`-type rows,
  plus the accompanying `<div id="return-slot"></div>` target the return form
  swaps into. All underlying data (op.sale_id, op.id, product.id, product.code)
  and backend routes (GET/POST /returns) already exist and are entry-point-
  agnostic — this is a template-only omission on /history, not a missing backend
  feature and not a bug in the return flow itself. Because /history is the only
  unbounded, filterable, paginated view of all operations (recent_sales.html on
  /sales is capped to the last 10 sales), it is also the only realistic place a
  user could find and act on an old ("legacy", pre-batch-tracking) sale — so the
  omission fully explains why Test 6 of the UAT could not be completed.
fix: (not applied — goal: find_root_cause_only)
verification: (not applicable — diagnosis only)
files_changed: []
