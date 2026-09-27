# Quick 260927-k1m: Per-currency product card prices - Research

**Researched:** 2026-09-27
**Domain:** Codebase change map (FastAPI + SQLAlchemy 2.0 + Alembic, SQLite/PG). Nothing outside the repo was looked up.
**Confidence:** HIGH. Every claim below was read from the repo in this session. The few inferences are marked `[ASSUMED]`.

<user_constraints>
## User Constraints (from CONTEXT.md, locked 2026-09-27)

- Product keeps `cost_cents`/`sale_cents`/`min_sale_cents` as the **RUB** set. Add the same three for UAH and EUR, all nullable Integer cents. Migration **0028**, additive only (batch mode, SQLite + PG). No backfill.
- The warehouse `currency` picks the field set. An unknown or empty currency gets the RUB set. Nothing ever writes another currency's fields.
- Receipt: reads and writes only the fields of the warehouse currency. A new card gets prices only in that currency.
- Sale: the cost freeze fallback and the min-sale guard use the card field for the batch warehouse's currency.
- Finance COALESCE uses the field of the currency in scope. Export shows per-currency card prices.
- A missing price in the warehouse currency stays NULL in stored money. No conversion ever reaches stored money.
- Autofill order: card price in the warehouse currency, else the RUB card/catalog price converted (UAH = RUB/2, EUR = RUB/100, rounded to whole cents). Suggestion only. Colour-cue `data-ref-cents` follows the same rule. `catalog_prices` stays RUB-only.
- Amend `.planning/REQUIREMENTS.md:107` (FX exclusion) for autofill only.
- The desktop product form edits all three sets. `price_change` names the exact field (`{field, old_cents, new_cents}`).
- Discretion: column names, the helper (next to `CURRENCIES` in `app/core.py`), form layout, export headers, history labels. Mobile product editing (Phase 35) is expected to need nothing.
- Commit: no attribution trailers, stage by path, `git commit -F`, bump `__version__` 1.138 → 1.139 (`app/__init__.py:5`).
</user_constraints>

## Summary

The change is mechanical but touches about 12 call sites. The risk is in three places that are **not** in CONTEXT's canonical refs:

1. **The desktop receipt warehouse select does not re-run the lookup.** It only refreshes the batch chooser (`app/templates/partials/receipt_form.html:56-60`, `hx-get="/receipts/batches"`). If the operator types a code with the default (RUB) warehouse selected, the RUB prices are filled. Switching to Запорожье then leaves them in the inputs, and saving writes them into the UAH fields. That is the reported bug, and it survives a service-only fix.
2. **`scripts/import_inventory_receipt.py:299-321` pushes RUB `catalog_prices` straight into `register_receipt`** for new codes, whatever the warehouse currency. After this change they land in `cost_uah_cents`/`sale_uah_cents` and in the batch snapshot as UAH values.
3. **`tests/test_migrations.py:108` runs `downgrade -1`.** It asserts the 0027 columns are gone. Once 0028 exists, `-1` lands on 0027 and the test goes red.

Sync is safe by construction, so no code change is needed there, only proof tests:
- The server discards pushed rows whose product UUID already exists: `merge._upsert_reference` (`app/services/merge.py:539-566`) is insert-only.
- A 0027 client never receives the new keys it cannot store: `_apply_pull_page` projects through the client's own `KIND_TO_FIELDS` (`sync_client.py:537-543`).
- A 0028 client talking to a 0027 server gets a 409 and skips the pull (`sync_client.py:385-398`).

**Primary recommendation:**
- Add one mapping plus a converter in `app/core.py`.
- Thread `currency` through `receipts.lookup_prefill` / `register_receipt`, `sales.register_sale`, `finance_reports.stock_valuation` (it already has the param), and the receipt/sale routes' `ref_*` values.
- Fix the warehouse-change autofill leak on the desktop receipt form.
- Pin the sync behaviour with tests.

## Helper (discretion: recommended shape)

```python
# app/core.py, directly after DEFAULT_CURRENCY (line 65)
CARD_PRICE_FIELDS: dict[str, dict[str, str]] = {
    "RUB": {"cost": "cost_cents", "sale": "sale_cents", "min_sale": "min_sale_cents"},
    "UAH": {"cost": "cost_uah_cents", "sale": "sale_uah_cents", "min_sale": "min_sale_uah_cents"},
    "EUR": {"cost": "cost_eur_cents", "sale": "sale_eur_cents", "min_sale": "min_sale_eur_cents"},
}
_RUB_DIVISOR = {"RUB": 1, "UAH": 2, "EUR": 100}

def card_price_fields(currency: str | None) -> dict[str, str]:  # unknown/empty -> RUB set
def rub_suggestion(rub_cents: int | None, currency: str | None) -> int | None:  # ROUND_HALF_UP
```

- **Names must end in `_cents`.** Three things depend on it: `merge._money_fields` (`merge.py:163-165`) validates wire money by that suffix, `tests/test_ledger.py:124` asserts `*_cents` columns are Integer, and CSV/format code assumes it.
- **Rounding.** Use `Decimal(...).quantize(Decimal(1), ROUND_HALF_UP)`. `core.py` already imports both for `to_cents`. Do not use `round()`: it is banker's rounding, so `round(71700.5) == 71700`.
- The spec example is exact: 143400/2 = 71700 and 249900/2 = 124950.

## Call-site map (a = switch to warehouse-currency field, b = unchanged by design, c = display-only)

| Site | Class | What to do / where the currency comes from |
|---|---|---|
| `app/services/receipts.py:173-183` new card `Product(cost_cents=…, sale_cents=…)` | a | Set only the currency's fields. Resolve with `session.get(Warehouse, warehouse_id).currency` **after** the `active_ids` check at `:136-141`. |
| `receipts.py:216-243` `entered = {"cost_cents":…, "sale_cents":…}` loop + `price_change` | a | Key the dict by the mapped names, e.g. `fields["cost"]`. The payload `field` becomes e.g. `"cost_uah_cents"`. Keep PD-8 (None never clears). |
| `receipts.py:271-280, 300-310` batch `price_cents`/`cost_cents`, op `unit_*` | b | Already the operator-entered value in the warehouse currency (CUR-02). |
| `receipts.py:324-360` `lookup_prefill(session, code)` | a | Add `currency: str = DEFAULT_CURRENCY`. Product branch, per field: currency card value, else `rub_suggestion(RUB card, else catalog)`. Catalog branch: `rub_suggestion(catalog)`. Keep the default RUB so the name-only callers (`transfers.py:41`, `writeoffs.py:52`, `mobile_transfers.py:166`, `mobile_writeoff.py:88`) stay identical. |
| `app/routes/receipts.py:66-86` `_form_extras` → `reference_prices_for_code` | a | `selected` warehouse id is in scope. Convert both refs with `rub_suggestion(ref, currency)`. |
| `routes/receipts.py:120-195` `/receipts/lookup` | a | `warehouse_id` is already hx-included (`receipt_form.html:39`). Resolve its currency, pass it to `lookup_prefill`, and convert `ref_*`. An empty or unknown id means RUB. |
| `receipt_form.html:56-60` warehouse `<select>` | **a (gap)** | On `change`, clear cost/sale inputs the lookup filled (mark them, like `name`'s `data-autofilled` at `:36`) and re-trigger the code lookup. Values the operator typed must survive (PD-10). See Pitfall 1. |
| `app/routes/mobile_receipts.py:118` `lookup_prefill` in step/batch | a | `selected` warehouse from step 1 is in scope. The "fresh lookup wins" rule (`:125-133`) already re-resolves after «Назад» + a warehouse change. |
| `mobile_receipts.py:173` step/details `reference_prices_for_code` | a | `warehouse_id` Form field. Convert refs. |
| `app/services/sales.py:264-277` below-minimum guard | a | `basket_currency` is already computed at `:238-252`, before the guard. Use `getattr(product, card_price_fields(basket_currency)["min_sale"])`, with an `is not None` check (D-06). |
| `sales.py:326-333` cost freeze `batch.cost_cents` else `product.cost_cents` | a | Else `getattr(product, fields(basket_currency)["cost"])`. The result may be NULL. **No conversion.** |
| `sales.py:370-392` `lookup_prefill` `prices.sale` | b | Used only when the product has **zero** open batches (`routes/sales.py:190-191`). No warehouse is knowable and the sale cannot complete. Leave it RUB. |
| `routes/sales.py:232` (single auto batch), `:329` (`/sales/batch-pick`), `mobile_sales.py:401` (qty-price): NULL-price batch falls back to the card `sale_cents` | a | Batch known → `Warehouse.currency` of `batch.warehouse_id`. Card field of that currency, else `rub_suggestion(product.sale_cents)`. It is only a fill. |
| `ref_pc_cents` at `routes/sales.py:126` (`_echo_lines`), `:206`, `:344`; `mobile_sales.py:263` (dictionary-only, no batch → RUB), `:408` | a where a batch is known | Convert with the picked batch's warehouse currency. With no batch, leave it RUB. |
| `app/services/catalog.py:159` `_PRICE_FIELDS` + `create_product` `:68-127` + `update_product` `:162-290` | a | Extend to 9 fields and add 6 `*_raw` kwargs. **Caution:** `update_product` writes every price unconditionally (`:259-261`, empty = clear), and `min_sale_raw=""` already defaults to "clear". Default the new kwargs to `None` = "not submitted → unchanged", or every existing test or caller that omits them wipes UAH/EUR. |
| `app/routes/products.py:208-331` create/update Form params + 422 `form` echo | a | Add 6 `Form("")` fields, pass them through, echo them. |
| `routes/products.py:136-172` `/products/price-autofill` | b | The product form has no warehouse. It stays RUB → `#cost`/`#sale` only. |
| `app/templates/pages/product_form.html:77-103` | a | Add ₴ and € rows. There are no `data-ref-cents` on the new rows (no warehouse context). The `min_sale` row stays grouped as a guardrail (D-21). |
| `app/templates/partials/price_history.html:20-24` field labels | a | Add 6 labels (e.g. «Закупочная ₴»). Unknown fields already fall back to the raw name (`:24`). Optionally format old/new with `format_money`. |
| `app/services/finance_reports.py:71-72` COALESCE | a | `stock_valuation(session, currency)` already has `currency`. Use `getattr(Product, fields["cost"])` / `["sale"]`. The callers `routes/finance.py:97`, `mobile_finance.py:90`, `dashboard.py:143` are unchanged. |
| `app/services/export.py:96-112` products CSV | a | Add columns such as «Закупка ₴», «Продажа ₴», «Закупка €», «Продажа €». Update the exact-header assertion at `tests/test_export.py:316-324`. No importer reads this CSV (grep: «Закупка» appears only in `export.py:99`). |
| `reports.py:143-162`, `returns.py:182`, `transfers.py:141-193`, `batches.py:171-181` | b | Frozen op values or batch-level money only. |
| `pages/categories.html:31-32`, `partials/product_rows.html:64-65`, `mobile_partials/search_product_detail.html:25` | c | RUB card display. Leave it, or add ₽ via `format_money` (discretion). |
| `sale_warning.html:12`, `sale_price_warning.html:8` `e.minimum` | c | The value becomes currency-specific automatically. Optionally render with `format_money(…, basket_currency)`. |
| `scripts/import_inventory_receipt.py:299-321` | **a (gap)** | RUB catalog prices are passed as `cost_raw`/`sale_raw` for new codes. Before calling, convert with `rub_suggestion(…, warehouse.currency)`, or pass empty for non-RUB. See Open Q1. |

**Can a desktop basket line span currencies?** Lines can pick batches from any warehouse: `open_batches(session, product.id)` has no warehouse filter (`routes/sales.py:210`). A mixed basket is hard-rejected before any write (`sales.py:238-243`, `MIXED_CURRENCY_ERROR`). So after that check, one `basket_currency` applies to every line's min-guard and cost freeze. Mobile uses the same `register_sale`.

## Sync / merge (file:line evidence)

| Scenario | Code path | Outcome |
|---|---|---|
| Client at 0027 pushes an **existing** product (no new keys) to a 0028 server | `merge._upsert_reference` `merge.py:539-566`: `_partition_new` drops existing UUIDs; "Insert-only — no UPDATE" | Server row untouched. **UAH/EUR cannot be nulled.** Pinned today for `sale_cents` by `tests/test_merge.py:592-605`. |
| 0027 client pushes a **new** product | `_reference_row` `merge.py:422-436`: `data.get(col)` → None for the new columns | Inserts with NULL UAH/EUR (correct: no price in that currency). |
| 0028 server → 0027 client pull | `_apply_pull_page` `sync_client.py:524-543`: `update_fields = merge.KIND_TO_FIELDS[kind] - {"id","quantity"}` uses the **client's** schema | Surplus keys ignored. `parse_exchange` validates only the receiver's `_money_fields`. No break. |
| 0028 client → 0027 server | push gate `sync.py:238-313` (`client <= server`) → 409 → `sync_client.py:385-398` returns `schema_mismatch` **before the pull** | No pull, so the client's UAH/EUR are never overwritten with None. The rows re-push once s1 is migrated. |
| 0028 client ← 0028 server pull | same `update(...)`, server wins on every column | The server's UAH/EUR overwrite local ones. This is the existing server-wins behaviour for RUB card prices too, not new. |
| Offline bundle (mobile) | `offline.py:61-72` `schema_version_ok` is an **exact match** | Bundles generated at 0027 are rejected after s1 moves to 0028. The operator must re-download. See Pitfall 5. |

**The "five-artifact lockstep" (`STATE.md:147`) does NOT apply.** It covers ledger tables: migration + `app/db.py::APPEND_ONLY_TRIGGERS` + the `IMMUTABLE_*_COLUMNS` frozensets + test constants. `products` has no triggers (grep for `ON products` in `app/db.py` and `alembic/versions` finds none). Artifacts that must move with 0028:
1. `alembic/versions/0028_product_currency_prices.py`: `revision = "0028"` (fixed width, enforced by `test_migrations.py:180-215`) and `down_revision = "0027"`.
2. The 6 `Mapped[int | None] = mapped_column(Integer)` columns in `app/models.py:178-183`. **No `default=` or `server_default`**: a Python default would replace an explicit None on merge inserts (STATE.md:241 precedent).
3. `tests/test_migrations.py:108`: change `run_alembic(url, "downgrade", "-1")` to `"0026"` so VA-6 still checks 0027's downgrade DDL. Add a 0028 round-trip test: head → `downgrade 0027` → no `*_uah_*`/`*_eur_*` columns, `uq_products_code_active` still present with its WHERE, all 4 triggers intact → head.
4. Optional: `tests/test_sync_schema_gate.py:40-42` (`SERVER="0027"`, `AHEAD="0028"`) is monkeypatch-pinned, so it stays correct. `test_merge.py:677-697`'s docstring ("product upsert succeeds first") becomes inaccurate because the product INSERT now fails first on a 0024 DB. The test still passes.
5. Rollout (`STATE.md:148`): migrate and redeploy s1 with `up -d --build` (the code is baked into the image, per the memory note), verify pull and a push from a current client, and only then cut the client tag.

## Migration shape

Follow `0025_batch_cost_cents.py` for the upgrade: `with op.batch_alter_table("products") as batch_op: batch_op.add_column(sa.Column("cost_uah_cents", sa.Integer(), nullable=True))` ×6. That honours the locked "batch mode" decision. `add_column` inside batch does **not** recreate the table on SQLite (`0027:29-36` note; `env.py:57,85` sets `render_as_batch` for SQLite only).

**Downgrade:** use plain `op.drop_column("products", …)` ×6, as `0027:382-392` does, not `batch_alter_table`. A batch `drop_column` triggers a move-and-copy rebuild of `products`, which is referenced by FKs from `batches`/`operations` and carries the partial unique index `uq_products_code_active` (`models.py:158-165`). I have not verified whether the rebuild keeps `sqlite_where` `[ASSUMED risk]`. The new round-trip test above is the guard.

## Common Pitfalls

1. **Autofill survives a warehouse change (desktop).** The lookup re-renders prices only for fields that arrived empty (`routes/receipts.py:170-171`). The `<select>` never re-triggers it. Fix: the select's `hx-on:change` clears inputs marked `data-autofilled` and re-fires the `#code` lookup. Test the whole path: lookup with the RUB warehouse → switch to UAH → lookup response carries 717,00/1249,50.
2. **`update_product` clears whatever is not posted** (`catalog.py:259-261`). New kwargs defaulting to `""` would null UAH/EUR for every existing caller or test. Use `None`.
3. **`round()` is banker's rounding.** Use `ROUND_HALF_UP`, matching `to_cents`.
4. **Autofill must not leak conversion into stored money.** Only form suggestions and the stock-valuation input change. `rub_suggestion` must never be called in `register_receipt`, `register_sale`, or `stock_valuation`.
5. **Offline bundles go stale on deploy.** An exact schema match rejects 0027 bundles after the s1 migration. Tell the operator to re-download after deploying.
6. **`| tojson` must sit in single-quoted attributes** (memory note). This only matters if a new `hx-vals` is added, e.g. to re-trigger the lookup with the warehouse id. Prefer `hx-include`, as `receipt_form.html:39` does.
7. **Known red tests:** 4 in `tests/test_sync_ui.py` (lifespan lock). They were red before this change.

## Open Questions

1. **Import script and non-RUB warehouses** (`scripts/import_inventory_receipt.py:299-321`). This is not in CONTEXT. Options: (a) convert with `rub_suggestion` (matches "we will fix prices where refined"), or (b) import with empty prices into non-RUB warehouses. Recommendation: (a), because it uses the same helper and a one-line change. **It needs the user's confirmation**, since (a) stores converted values without an operator save.
2. **Mixed cross-currency transfer** copies the source `price_cents` (RUB) into a UAH destination batch (`transfers.py:189`). This is pre-existing, and batch money is out of this task's scope. Report it only.

## Validation Architecture

| Property | Value |
|---|---|
| Framework | pytest 9.1 (`pyproject.toml:24,28-29`, `testpaths=["tests"]`) |
| Quick run | `uv run pytest tests/test_receipts.py tests/test_sales.py tests/test_catalog.py -x -q` |
| Full suite | `uv run pytest -q` (4 known `test_sync_ui.py` failures) |

| Behaviour | Test (extend) | Idiom |
|---|---|---|
| UAH receipt suggests 71700/124950 and writes only UAH fields; the second lookup returns the stored UAH values | `tests/test_receipts.py` (near `:686` price_sync, `:870` web lookup) | `Warehouse(id=new_id(), name=…, currency="UAH")` (as `test_export.py:392`) |
| RUB receipt is byte-identical to today | existing `test_receipts.py:686-760` stay green | the `warehouse` fixture defaults to RUB (`conftest.py:159-165`) |
| Warehouse change re-suggests in the new currency | new web test on `/receipts/lookup?warehouse_id=` | `client` fixture |
| Min-sale guard and cost freeze use the UAH fields; NULL UAH cost → NULL `unit_cost_cents` | `tests/test_sales.py:527-620, 712` | UAH batch |
| Mobile receipt and sale fill | `tests/test_mobile_receipts.py`, `tests/test_mobile_sales.py` | |
| Product form round-trip of 9 fields, 6 new `price_change` field names, history labels | `tests/test_catalog.py:462-560, 848` | |
| `stock_valuation(currency="UAH")` COALESCEs to `cost_uah_cents` | `tests/test_finance_reports.py:227` | |
| CSV header gains per-currency columns | `tests/test_export.py:307` | |
| Old-schema push (existing and new product without new keys) keeps server UAH/EUR, inserts NULLs; new-schema push merges | `tests/test_merge.py` near `:592`, `:700` | `_product_rec`, `_apply` |
| Pull into a client keeps working with surplus keys | `tests/test_sync_client.py:379` | monkeypatch `merge.KIND_TO_FIELDS` as `test_merge.py:772-776` |
| 0028 up/down round-trip; VA-6 retargeted to 0026 | `tests/test_migrations.py` | `alembic_engine`, `run_alembic` |

## Security Domain

- **Input validation:** the new form fields go through `catalog.parse_optional_cents`, which already rejects negatives and bad input.
- **Wire safety:** the new `*_cents` columns are validated as int by `merge.parse_exchange` automatically.
- **Other areas:** no auth, crypto, or new dependency.
- **Package audit:** no packages are installed.

## Sources

All sources are this repo, read on 2026-09-27: the files and line numbers cited inline, `.planning/STATE.md:146-148,237,241`, and the memory notes (tojson, s1 image-baked, sync_ui failures). No web or Context7 lookups were needed, because this is a codebase-only question.

**Valid until:** the next commit that touches receipts, sales, catalog, merge, or sync_client.
