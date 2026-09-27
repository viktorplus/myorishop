# Quick Task 260927-k1m: Per-currency product card prices (RUB/UAH/EUR) - Context

**Gathered:** 2026-09-27
**Status:** Ready for planning

<domain>
## Task Boundary

A product card carries its own price set per currency. Every operation works in
the currency of the warehouse it touches, and nothing ever writes into another
currency's fields. Trigger: s1 warehouse «Запорожье» is UAH, and the receipt form
filled RUB card prices (code 42499: 1434,00 / 2499,00) into a UAH receipt.

Replaces the abandoned plan 260927-j0z (autofill-only conversion), which would
have let a UAH receipt overwrite the RUB card and halve it on every receipt.

</domain>

<decisions>
## Implementation Decisions (user, 2026-09-27 — locked)

### Data model
- Product keeps `cost_cents`, `sale_cents`, `min_sale_cents` as the **RUB** set (no rename, no data change).
- Add the same three per extra currency: UAH and EUR (e.g. `cost_uah_cents`, `sale_uah_cents`, `min_sale_uah_cents`, `cost_eur_cents`, `sale_eur_cents`, `min_sale_eur_cents`), all nullable Integer cents.
- Migration **0028**, additive only (alembic batch mode, SQLite + PostgreSQL portable). No backfill.
- «у товара есть три валюты, для каждой валюты свое поле. ничего не должно перезаписывать»; «в зависимости от склада мы работаем с нужной валюты».

### Which fields an operation uses
- The warehouse's `currency` picks the field set. Unknown/empty currency → RUB set.
- Receipt into a UAH warehouse reads/writes only UAH card fields; a RUB receipt behaves exactly as today. Same for a new card created by a receipt: it gets prices only in the receipt warehouse's currency.
- Sale: cost freeze fallback (`batch.cost_cents` else card cost) uses the card cost **in the batch warehouse's currency**; min-sale guard compares against the min-sale **in that currency**.
- Finance report COALESCE fallback (`app/services/finance_reports.py`) uses the card field of the warehouse currency in scope.
- Export shows per-currency card prices.
- Missing card price in the warehouse currency stays **NULL** in any stored money (cost freeze, reports). No conversion ever reaches stored money.

### Autofill (form suggestion only)
- Order: card price in warehouse currency → else RUB card/catalog price converted: UAH = RUB / 2, EUR = RUB / 100, rounded to whole cents.
- Converted value is only a suggestion in the input; it is stored only if the operator saves the form (then into the warehouse-currency field). User: «мы будем менять цену там где будет уточнение» / «после этого мы установим верную цену там где она будет найдена».
- Colour-cue reference prices (data-ref-cents) follow the same rule so the cue compares like with like.
- Catalog reference prices (`catalog_prices`) stay RUB-only; no currency column in this task.
- This overrides `.planning/REQUIREMENTS.md:107` («no conversion / FX») for autofill only; totals still never mix currencies. Update that line.

### Product card form
- Desktop product form edits all three currency sets (₽ / ₴ / €); price_change ops name the exact field changed (same payload shape `{field, old_cents, new_cents}`).

### Orchestrator decisions after research (reversible, stated to user as assumptions)
- Desktop receipt form: changing the warehouse `<select>` re-runs the price suggestion for fields that were AUTOFILLED (not operator-typed) — otherwise RUB suggestions made under the default warehouse get saved into UAH fields. Operator-typed values are never replaced.
- `scripts/import_inventory_receipt.py`: for a non-RUB warehouse, do NOT pass RUB catalog prices into `register_receipt` — the card's currency fields stay empty (bulk import has no human review; converted prices are suggestions only).
- `update_product` new kwargs default to "not submitted → leave unchanged" (never clear UAH/EUR for existing callers).
- Conversion rounds half-up via Decimal (same rule as `to_cents`).
- Migration test `tests/test_migrations.py:108` retargets to "0026"; add a 0028 round-trip test; downgrade uses plain `op.drop_column`.
- Offline bundles made before 0028 are rejected afterwards (exact schema match) — note in SUMMARY for the operator.

### Claude's Discretion
- Exact column names, helper name/shape (one small helper next to `CURRENCIES` in `app/core.py` mapping currency → field names + the RUB divisor), form layout of the three rows, export column headers, history label wording for the new fields.
- Whether mobile product editing (Phase 35 scope, not built yet) needs anything now — expected: no.

</decisions>

<specifics>
## Specific Ideas

- Real case test: UAH warehouse, product card RUB 143400/249900, no UAH prices → desktop `/receipts/lookup` suggests 717,00 / 1249,50; saving that receipt writes `cost_uah_cents=71700`, `sale_uah_cents=124950` and leaves `cost_cents=143400`, `sale_cents=249900` untouched. Second lookup then suggests the stored UAH prices, not RUB/2 again.
- s1 today: 0 batches in non-RUB warehouses → no card has been corrupted yet (checked 2026-09-27).
- Sync: `merge.KIND_TO_FIELDS` is schema-derived; a stray wire field is dropped by `_reference_row`. Must prove with a test that an old-schema client payload (no new fields) and a new-schema payload both merge, and that pushing a product without the new keys does NOT null out existing UAH/EUR values on the server.
- Commit rules: no Claude attribution trailers; stage by path (untracked AGENTS.md, input/, plan1.txt are not ours); `git commit -F <file>`; bump `__version__` 1.138 → 1.139.
- Known pre-existing failures: 4 tests in `tests/test_sync_ui.py` (lifespan auto-sync lock) — not a regression.

</specifics>

<canonical_refs>
## Canonical References

- `app/core.py:55-80` CURRENCIES / DEFAULT_CURRENCY
- `app/models.py:173-183` Product prices; `:214-220` Warehouse.currency; `:269-272` Batch cost snapshot (CUR-02)
- `app/services/receipts.py:170-247` card create/update on receipt; `:324-360` lookup_prefill
- `app/services/sales.py:272-276` min-sale guard; `:326-333` cost freeze; `:372-392` lookup_prefill
- `app/services/catalog.py:177-290` product update + price_change ops
- `app/services/finance_reports.py:56-75` COALESCE fallback
- `app/services/export.py:105-112`
- `app/services/merge.py:79-83, 422-440` sync field derivation
- `app/routes/receipts.py`, `mobile_receipts.py`, `sales.py`, `mobile_sales.py`, `products.py`
- `.planning/REQUIREMENTS.md:107` FX exclusion (to amend)

</canonical_refs>
