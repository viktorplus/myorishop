# Phase 14: List Pagination, Filtering, Sorting & Quick Delete - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-14
**Phase:** 14-list-pagination-filtering-sorting-quick-delete
**Areas discussed:** Pagination, Filters by column, Sorting, Quick delete

---

## Pagination

| Option | Description | Selected |
|--------|-------------|----------|
| Номера страниц | Classic page-number pagination | ✓ |
| «Показать ещё» | Load-more, reusing history's existing pattern | |
| По-разному для разных списков | History keeps load-more, others get a different style | |

**User's choice:** Номера страниц (page numbers), uniformly across all list pages.

| Option | Description | Selected |
|--------|-------------|----------|
| Да, перевести на номера страниц | Convert History from load-more to page numbers | ✓ |
| Нет, оставить «Показать ещё» только для истории | Keep History as-is | |

**User's choice:** Да — History also converts to page-number pagination for consistency.

| Option | Description | Selected |
|--------|-------------|----------|
| 20 | Matches current search cap for products/customers | ✓ |
| 50 | Matches current history page size | |
| Своё значение для каждого списка | Per-list page size | |

**User's choice:** 20 rows per page, one constant across all lists.

**Notes:** No further pagination questions — user moved to next area after confirming page size.

---

## Filters by column

| Option | Description | Selected |
|--------|-------------|----------|
| Одна строка фильтров над таблицей | Single filter row above the table (like history_filters.html expanded) | |
| Фильтры внутри шапки таблицы | Per-column inputs/selects inside the table header row | ✓ |

**User's choice:** Filters inside the table header row.

| Option | Description | Selected |
|--------|-------------|----------|
| Сразу при вводе (debounce) | Matches existing product/customer search pattern | ✓ |
| Кнопка «Применить» | Batch-apply multiple filters at once | |

**User's choice:** Debounce on input, no Apply button.

**Notes:** Which specific columns get filters per list was left to research/planning discretion.

---

## Sorting

| Option | Description | Selected |
|--------|-------------|----------|
| Клик по заголовку колонки | Clickable column header, toggles asc/desc | |
| Выпадающий список «Сортировать по…» | Separate select dropdown | ✓ |

**User's choice:** "Сортировать по…" dropdown.

| Option | Description | Selected |
|--------|-------------|----------|
| Сохранить текущие порядки | Keep each list's current default order as the dropdown's default | ✓ |
| Оставить на усмотрение при планировании | Let planner choose defaults | |

**User's choice:** Keep current default orders per list (products/customers by name, warehouses active-first, history newest-first, dictionary by code, catalogs newest-first).

---

## Quick delete

| Option | Description | Selected |
|--------|-------------|----------|
| Да, блокировать при остатке > 0 | Add a new stock-on-hand guard for product quick-delete | ✓ |
| Нет, оставить как есть | No guard, delete regardless of stock | |

**User's choice:** Yes — block product quick-delete if stock > 0 (new guard; none exists today).

| Option | Description | Selected |
|--------|-------------|----------|
| Браузерный confirm() перед отправкой | Native browser confirm dialog | ✓ |
| Инлайн-подтверждение в строке | Row swaps to "Точно? Да/Нет" via HTMX | |

**User's choice:** Browser-native `confirm()` for both products and warehouses.

| Option | Description | Selected |
|--------|-------------|----------|
| Строка просто исчезает из списка | Row disappears entirely (matches current product behavior) | ✓ |
| Показывать серым с восстановлением, как у складов | Keep row visible grayed-out with restore | |

**User's choice:** Row disappears entirely after product quick-delete (no change from current behavior).

**Follow-up (user-initiated clarification):** User asked to revisit the warehouse guard specifically — wanted the same "must be empty" rule as products, not just the existing last-active-warehouse check.

| Option | Description | Selected |
|--------|-------------|----------|
| Оба guard'а вместе: пустой + не последний активный | Both conditions must hold simultaneously | ✓ |
| Только новый guard по остаткам, старый last-active убрать | Replace last-active check with stock check | |

**User's choice:** Both guards apply together — warehouse must be empty AND not the last active warehouse.

**Follow-up:** User then added "после этого склад исчезает из списка" (the warehouse row should disappear too after delete) — a deliberate behavior change from the current warehouse list, which keeps deleted warehouses visible grayed-out with a restore button.

| Option | Description | Selected |
|--------|-------------|----------|
| Да, склад исчезает из списка полностью | Warehouse row fully disappears, matching product behavior | ✓ |
| Нет, оставить как есть (серый + восстановление) | Keep current grayed-out + restore behavior | |

**User's choice:** Yes — warehouse row disappears entirely from the list after quick-delete, same as products. This supersedes the current warehouse-list restore-visible UX for the quick-delete path.

**Notes:** User confirmed no further questions remained after this clarification round.

---

## Claude's Discretion

- Exact filterable columns per list beyond what's implied by existing search behavior.
- Exact sort options offered in each list's "Сортировать по…" dropdown.
- Whether/how a restore path for quick-deleted warehouses should be preserved elsewhere now that the list itself no longer shows them (flagged as an open question for planning, not silently dropped).

## Deferred Ideas

None — discussion stayed within phase scope.
