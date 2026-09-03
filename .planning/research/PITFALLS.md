# Pitfalls Research

**Domain:** Adding reversal, business dates, per-warehouse currency and mobile card editing to an existing append-only, UUID-synced warehouse-inventory system with live production data
**Researched:** 2026-09-04
**Confidence:** HIGH (almost every finding below is a direct read of this repo at `b4ca98c`; external claims are marked)

---

## READ THIS FIRST: the currency backlog entry is stale

`.planning/ROADMAP.md:327-350` (Phase 999.1) and `.planning/OPEN-WORK-AUDIT-2026-09-04.md:65-79` both describe per-warehouse currency as unstarted, and state that `services/reports.py`, `dashboard.py` and `finance.py` "contain **zero** occurrences of `warehouse`". **That was true on 2026-08-09. It has not been true since 2026-08-10.**

Verified in the code at HEAD:

| Claim in the backlog | Reality at HEAD |
|---|---|
| `Warehouse.currency` not added | Migration `0023_warehouse_currency.py` — shipped |
| Sync needs no schema edit | Migrations `0024_cash_movement_currency`, `0025_batch_cost_cents`, `0026_cash_movements_trigger_guards_currency` — all shipped (26 migrations total, not 22) |
| reports/dashboard/finance have no warehouse dimension | `reports.operation_currency_clause()` (`app/services/reports.py:21-38`), `dashboard.period_metrics(..., currency)` (`:75-103`), currency-scoped `finance_reports` — all shipped |
| Mixed-currency baskets possible | `register_sale` rejects them before any write (`app/services/sales.py:199-204`) |
| CSV export sums across currencies | `export.py:144` emits a «Валюта» column |

The work landed as **two quick tasks** (`cdcec66` part 1, `260810-2g3` part 2, `__version__` 1.17 → 1.28), not a phase, so no roadmap artifact records it. `business_date`, `reversal` and `сторно` have **zero occurrences repo-wide** — those two are genuinely unbuilt.

**Consequence for the roadmapper — three things change:**

1. **Currency is a completion-and-audit phase, not a build phase.** It runs over a partial rollout already live against real operator data on `ori.viktorplus.com`. Its residual gaps (Pitfalls 5, 6, 7, 25 below) are *sharper* than a greenfield build's would have been, because the operator is already reading multi-currency numbers today and cannot tell which currency they are in. The scope is a render sweep, three un-scoped reports, and two guards — not a schema migration.
2. **Only one genuinely new *data* migration lands: `business_date`.** The reversal link needs a second one — see Pitfall 21, where I disagree with the "one migration" framing and say why.
3. **The freed effort belongs to reversal and back-dating**, which now carry the milestone's whole weight.

**Migrations 0023–0026 are a worked example of exactly this milestone's risk — mine them.** They shipped the same class of change (a new column on an append-only, synced, dual-dialect table, deployed to a live server with offline clients), and the record is unusually legible:

| What went right — copy it | What went wrong — do not repeat it |
|---|---|
| `server_default` instead of a backfill `UPDATE`, so the append-only trigger was never fought (0023, 0024) | 0024 added `cash_movements.currency` and **forgot the trigger's column enumeration**. Migration `0026` exists solely to repair that near-miss; the column was silently mutable in between (Pitfall 1) |
| `add_column` only, so SQLite batch mode never recreated the table and the four triggers survived (Pitfall 3) | The display sweep was never done: `money()` reached 1 template out of 49 (Pitfall 5) |
| Dual-dialect trigger DDL, `IS NOT` vs `IS DISTINCT FROM` (0026) | Three reports were left un-scoped and nobody noticed (Pitfall 25) |
| A loud-failure test for the under-migrated *server DB* (`tests/test_merge.py:662,677`) | The *other* mismatch direction — server running **older code** — was never gated and still is not (Pitfall 4) |
| `_clean_query_currency` allow-list on the untrusted `?currency=` param | `Warehouse.currency` left freely editable after the warehouse holds stock (Pitfall 7) |

**Action before planning:** re-derive the currency phase's scope from the code and from `.planning/quick/260810-2g3-currency-correctness-part-2-per-currency/260810-2g3-SUMMARY.md`, not from `ROADMAP.md:327`. Correct `ROADMAP.md:327-350` and `PROJECT.md:50` — the `needs verification` question there ("what happens when a new-schema client pushes `currency` to an old-schema server") is answered in Pitfall 4: **it depends on which side is stale, and one of the two directions loses data silently with a 200 response.**

Phase numbering below follows `PROJECT.md:41-45`:
**Phase 1** Back-dated operations · **Phase 2** Per-warehouse currency · **Phase 3** One-tap reversal · **Phase 4** Mobile editing · **Phase 0** = cross-cutting, must be settled before Phase 1 starts.

---

## Critical Pitfalls

### Pitfall 1: The `business_date` column escapes the append-only trigger

**What goes wrong:**
A new column is added to `operations` and the append-only triggers keep passing — because `operations_no_update` is a **column-enumerating** `WHEN` clause (`app/db.py:39-56`), not a blanket `BEFORE UPDATE`. A column not named in that list can be `UPDATE`d freely on an already-synced ledger row. The ledger silently fails open: the operator, or a bad merge, can rewrite history and nothing aborts.

**Why it happens:**
Migration 0018 relaxed the triggers from "reject every UPDATE" to "reject an UPDATE that changes an immutable column", so the sync cursor `synced_at` could be stamped. That relaxation made the trigger schema-coupled. **This has already bitten this project:** migration 0024 added `cash_movements.currency` and forgot the trigger; migration `0026` exists solely to fix it, and its own docstring calls it a "LOCKSTEP RULE fix" and a "fail-open in the append-only ledger invariant".

**How to avoid:**
A **five-artifact lockstep, in one commit**, for every new ledger column (`business_date` in Phase 1, `reverses_op_id` in Phase 3):
1. the model column (`app/models.py`);
2. a NEW migration mirroring `0026`'s DROP/CREATE technique — **both** `_SQLITE_DDL` (`IS NOT`) and `_PG_DDL` (`IS DISTINCT FROM`) branches;
3. `app/db.py::APPEND_ONLY_TRIGGERS` (the live source for `create_all` test fixtures);
4. `tests/test_append_only_cursor.py::IMMUTABLE_OPERATION_COLUMNS`;
5. never edit migration 0018/0026 retroactively — an applied migration is historical fact.

**Warning signs:**
`tests/test_append_only_cursor.py::test_trigger_column_list_matches_schema` goes red with the `_DRIFT_HINT` message. That test is the tripwire and fires the moment the model column is added — **do not "fix" it by adding the name to `IMMUTABLE_OPERATION_COLUMNS` alone**; that satisfies the model check while `test_declared_constants_match_trigger_ddl` then fails against the DDL, which is the real signal.

**Phase to address:** Phase 1 (`business_date`), repeated in Phase 3 (`reverses_op_id`).

---

### Pitfall 2: The `business_date` backfill deadlocks against its own new trigger

**What goes wrong:**
Migration 0027 adds `business_date`, adds it to the trigger's `WHEN` clause, then runs `UPDATE operations SET business_date = <derived from created_at>`. The `UPDATE` changes a now-guarded column → `RAISE(ABORT, 'operations ledger is append-only')` → **the migration itself fails**, on the live server, mid-upgrade.

**Why it happens:**
The obvious ordering (define the column fully, then fill it) is exactly the wrong one once the column is guarded. 0023/0024 sidestepped it by using `server_default`, so no `UPDATE` was ever strictly needed — the escape was structural, not deliberate, and will not repeat by luck.

**How to avoid:**
Fill the column **without an UPDATE**, copying the 0023/0024 pattern exactly:
```python
with op.batch_alter_table("operations") as batch_op:
    batch_op.add_column(sa.Column("business_date", sa.String(10),
                                  nullable=False, server_default=""))
```
If a real per-row value is needed, the order inside the migration is **add column → backfill → DROP/CREATE the trigger with the column guarded**, never the reverse. Write that sequence as a comment in the migration so a later editor cannot reorder it.

Better still: decide that `business_date` **falls back to the date part of `created_at` at read time** for historical rows, so no backfill runs at all. Smallest change; every pre-0027 row stays byte-identical.

**Warning signs:**
`alembic upgrade head` fails with `append-only` in the exception text. On a client this surfaces through the v4.0 self-update path as a failed migrate → matched-pair rollback — safe, but it strands every client on the old version.

**Phase to address:** Phase 1.

---

### Pitfall 3: `batch_alter_table` on `operations` silently deletes all four append-only triggers

**What goes wrong:**
Any batch operation on `operations` or `cash_movements` other than `add_column`/`create_index`/`drop_index` makes Alembic recreate the table by move-and-copy. Triggers belong to the dropped table and are **not** re-created. The append-only guarantee — this project's single most load-bearing invariant — vanishes with no error and no test failure.

**Why it happens:**
Alembic's batch mode defaults to `recreate="auto"` and recreates whenever the op is not natively supported by SQLite. The docs warn that unnamed CHECK/UNIQUE constraints are silently omitted from the recreate; triggers are in the same category and are not mentioned at all. This project already recorded the hazard: `tests/test_pragmas.py:28-34` — *"adding `author_id` (migration 0017) must NEVER use batch_alter_table on operations/cash_movements — a batch rebuild silently DROPS the four append-only triggers."*

**How to avoid:**
- In Phase 1 and Phase 3, restrict the ledger-table migration to `add_column` **only** (which does not trigger a recreate). No type changes, no constraint additions, no column drops on `operations`/`cash_movements`.
- If a recreate is ever unavoidable, re-issue `APPEND_ONLY_TRIGGERS` explicitly at the end of that migration.
- Add a migration-level test: build a DB via `alembic upgrade head` (not `create_all`) and assert all four trigger names are present **and** that `UPDATE operations SET business_date=...` aborts.

**Warning signs:**
`tests/test_pragmas.py::test_append_only_triggers_survive_author_id_schema` passing is **not** sufficient evidence — its `engine` fixture mirrors the migrated schema rather than executing the migrations (`needs verification`: confirm by reading `tests/conftest.py`'s `engine` fixture). Only a test built from `alembic upgrade head` can catch this.

**Phase to address:** Phase 0 (add the migration-built trigger test), enforced in Phases 1 and 3.

---

### Pitfall 4: A new column is silently dropped by a server running older code, and the client marks it synced anyway

**What goes wrong:**
The client at schema 0027 pushes an `operation` carrying `business_date`. The server is still running pre-0027 **code**. `merge._ledger_row` builds the insert row as `{column: data.get(column) for column in KIND_TO_FIELDS[kind]}` (`app/services/merge.py:460`), and `KIND_TO_FIELDS` is derived from the **receiver's** mapper columns (`:80-83`). A field the receiver's model does not know is never asked for, so it is **dropped without a word**. The merge succeeds, `POST /api/sync/push` returns 200, and `sync_client` stamps `synced_at` (`app/services/sync_client.py:384-390` — "Stamp synced_at ONLY after the 2xx"). The row is now excluded from every future push (`WHERE synced_at IS NULL`). **The business date, or the reversal link, is lost forever with no error anywhere.**

**Why it happens:**
`POST /api/sync/push` (`app/routes/sync.py:66-133`) does **no schema-version check at all**. The NDJSON header already carries `schema_version`, and `app/services/offline.py:61 schema_version_ok()` already implements the exact gate — but only the *offline bundle* upload uses it. The online push route ignores the header entirely.

The existing tests cover the **opposite** direction only: `tests/test_merge.py:662` and `:677` prove that a server whose **code is current but DB is under-migrated** fails loudly with `OperationalError` (the insert names a column the DB lacks → whole batch rolls back → non-2xx → client does not stamp). That case is safe. The code-lagging case is uncovered — and it is the realistic one here: clients auto-update from GitHub Releases (v4.0 UPD-01..07), while the server is a Docker image whose code only changes on a manual `up -d --build` (project memory `s1-image-baked-code-gotcha`). A client that self-updates first *is* this scenario.

**How to avoid:**
- **Phase 0, before any schema change ships:** gate `POST /api/sync/push` on the header's `schema_version`, reusing `offline.schema_version_ok`. Reject with a distinct non-2xx (409) and a Russian client message ("Сервер ещё не обновлён — синхронизация отложена"). `sync_client` must treat that status as *not synced* and leave `synced_at` NULL.
- Add the mirror of `test_push_cash_movement_currency_to_pre_0024_db_fails_loudly`: an **old-model** receiver (monkeypatch `merge.KIND_TO_FIELDS` to the pre-change set) must reject the batch, not silently drop the field and return 200.
- Rollout order becomes mandatory: **migrate and redeploy the server first, clients second.** Write it into both schema phases' plans.

**Warning signs:**
A push reporting `operations_inserted: N` (N > 0) while those rows on the server have an empty `business_date` / NULL `reverses_op_id` and the client shows them populated. The client's unsynced badge reaching 0 while server-side reports still behave pre-feature.

**Phase to address:** Phase 0 (the gate + test), relied on by Phases 1 and 3.

---

### Pitfall 5: Money is rendered without a currency almost everywhere

**What goes wrong:**
The operator reads `500,00` on a history row, a batch card, a product card or a dashboard tile and cannot tell roubles from hryvnia from euro. With genuinely multi-currency data live today, this is not cosmetic — it is a wrong business decision (pricing, restocking, cash withdrawal) taken from a number the UI refused to qualify.

**Why it happens:**
The currency quick task built the machinery (`app/core.py:60-86`: `CURRENCIES`, `currency_symbol`, `format_money`) and registered it as a Jinja filter (`app/routes/__init__.py:227`, `{{ cents | money(currency) }}`) — and then stopped. Measured at HEAD:

- `money(...)` is used in **exactly one** template: `app/templates/partials/cash_balance.html:7`.
- the bare, currency-less `cents` filter / `format_cents` appear **124 times across 49 files**, including `partials/history_rows.html`, `product_rows.html`, `receipt_rows.html`, `dashboard_tiles.html`, `finance_tiles.html`, `batch_picker.html`, `recent_sales.html`, `purchase_history.html`, `sales_report_results.html`, `price_history.html`, and every mobile surface (`mobile_partials/history_cards.html`, `batch_card_picker.html`, `sale_step_qty_price.html`, `search_product_detail.html`, `mobile_pages/home.html`).
- The only currency signal on the report/dashboard/finance pages is the filter `<select>` — **not the numbers**. On History, Products, Receipts, Sales and every mobile card there is no signal at all.

**How to avoid:**
Phase 2 owns a **sweep with a hard stop**: enumerate every template rendering `| cents` and decide, per site, one of exactly two outcomes — (a) switch to `| money(<resolved currency>)`, or (b) prove the column is already unambiguously labelled by a nearby currency header, and say why in a comment. No third option. Land it as a checklist in the phase plan, one line per file, so "done" is countable rather than felt.

Then pin it: a test that greps the rendered HTML of History, Products and mobile History for a currency symbol, so a future template edit cannot regress it.

**Warning signs:**
`money(` occurrences staying far below `cents` occurrences in `app/templates`. Any money figure on screen not within a labelled column and not adjacent to `₽`/`₴`/`€`.

**Phase to address:** Phase 2 (and Phase 4 must not ship mobile edit forms displaying prices without a currency — `PROJECT.md:45` already sequences Phase 4 last for exactly this reason).

---

### Pitfall 6: `Product.cost_cents` has no currency and is the fallback cost for sales out of every warehouse

**What goes wrong:**
A sale from a EUR warehouse whose batch has `cost_cents = NULL` freezes `unit_cost_cents` from `Product.cost_cents` — a number that is, in practice, roubles (`app/services/sales.py:295-299`):

```python
unit_cost_cents=(
    line["batch"].cost_cents
    if line["batch"].cost_cents is not None
    else product.cost_cents
),
```

The EUR sales/profit report then subtracts a rouble cost from a euro revenue and reports the result as euro profit. It is not detectably wrong on screen: the number is plausible and carries no unit.

**Why it happens:**
`Batch.cost_cents` arrived with migration 0025 on 2026-08-10, so **every batch created before that date has `cost_cents = NULL`**, and the receipt form only stamps it going forward. The fallback was deliberately chosen as "byte-identical to pre-existing behavior" (`sales.py:292-294`) — correct with one currency, a cross-currency leak the moment there were two. `Product.cost_cents`/`sale_cents` are product-level, warehouse-agnostic, have no currency column and no plan for one; `export.py:108-109` exports them with no «Валюта» column either.

**How to avoid:**
Phase 2 picks one and writes it as a locked decision:
- **(a)** the fallback is allowed only when the warehouse currency equals `DEFAULT_CURRENCY`; for any other currency `unit_cost_cents` stays NULL and the report's existing `cost_unknown_count` caveat (`reports.py:52-56` — already built and already surfaced) shows it honestly; **or**
- **(b)** the receipt form makes `Batch.cost_cents` mandatory for non-RUB warehouses, plus a one-off report listing every non-RUB batch with `cost_cents IS NULL` so the operator can fill them.

(a) is smaller and reuses existing machinery. Test: a sale from a EUR warehouse with a NULL-cost batch must not inherit a RUB `Product.cost_cents`.

**Warning signs:**
A EUR/UAH profit margin implausibly near 100% or implausibly negative. `cost_unknown_count` staying at 0 on a non-RUB report while pre-0025 batches are being sold.

**Phase to address:** Phase 2.

---

### Pitfall 7: A warehouse's currency can be changed after it holds stock, retroactively relabelling history

**What goes wrong:**
`update_warehouse` (`app/services/warehouses.py:149-178`) accepts a new `currency` with **no guard** on existing batches, operations or cash movements. Flip a warehouse RUB → EUR and every historical row resolving its currency through `operation_currency_clause` (`Operation → Batch → Warehouse.currency`) instantly leaves the RUB report and enters the EUR report, cents unchanged. A 500 000,00 ₽ month silently becomes a 500 000,00 € month. Cash movements written earlier carry their own stored `currency`, so cash and stock reports now disagree and neither looks wrong.

**Why it happens:**
Warehouse currency is derived at read time by join, not stored per operation — the right normalisation for a value assumed immutable. Nobody made it immutable. Note the asymmetry already in the codebase: warehouse **deletion** is blocked while stock > 0 (LIST-04, shipped), the currency edit is not. `update_warehouse`'s own comment (`:163-165`) worries about a *partial form post* relabelling money, then permits a deliberate one.

**How to avoid:**
Phase 2: make `Warehouse.currency` **write-once**. Reject a change when any `Batch`, `Operation` (via batch) or `CashMovement` resolves through the warehouse; reuse the non-overridable stock-guard shape from the delete path. Render the field read-only with an explanatory line on `pages/warehouse_form.html` once locked. Test: create warehouse → receipt → attempt currency change → rejected, Russian error, zero writes.

**Warning signs:**
A month's revenue figure changing with no new operation. Cash balance and stock valuation for one warehouse reporting different currencies.

**Phase to address:** Phase 2.

---

### Pitfall 8: Reference-data edits made on a client never reach the server — and are overwritten on the next pull

**What goes wrong:**
The operator fixes a product's cost, min sale price, category or low-stock threshold on the desktop client. Nothing propagates. At the next sync the server's older values come back down and **overwrite the local edit**. The work disappears, silently, minutes later. Same for customers (name, surname, phone, consultant number, address) and for `Warehouse.currency`.

**Why it happens:**
Reference sync is deliberately one-directional and server-authoritative, and the two halves reinforce each other:
- **push:** `merge._upsert_reference` (`app/services/merge.py:421-448`) — *"A NEW UUID inserts verbatim; an EXISTING UUID is **DISCARDED** — the server row is authoritative and wins at the ROW level, never field-merged."*
- **pull:** `sync_client._apply_pull_page` (`:417-428`) — existing UUIDs are *"UPDATED with the server's values for every column EXCEPT `id` and the cached `quantity`"*.

This is a deliberate v3.0 decision (SYNC-05/DD-1), not a bug. **Phase 4 makes it acutely visible**: mobile is server-only, so a mobile edit lands on the server and propagates down correctly, while the *same edit* on the desktop client is discarded. Two editing surfaces, opposite outcomes, no UI difference. It also silently defeats Pitfall 7's remedy if the operator sets a warehouse currency on a client.

**How to avoid:**
Phase 4 states the topology as a locked decision and makes it visible rather than pretending it does not exist. Minimum viable: on the desktop product/customer edit forms, when the install is a configured client, show a persistent note that reference edits are local-only until made on the server. Cheap, honest, no architecture change.

If the operator wants client edits to win, that is a genuine sync-semantics change (field-level merge, or a reference-edit ledger) — **out of scope for v5.0**; flag it as a follow-up milestone rather than smuggling it into a mobile-UI phase. Test either way: edit locally → sync → assert whether the local value survived, and assert the behaviour matches what the UI promised.

**Warning signs:**
"I changed the price and it went back." A `product_edited` / `price_change` audit row on the client with no counterpart on the server.

**Phase to address:** Phase 4 (decision + UI note); Phase 2 must not rely on client-side currency edits.

---

### Pitfall 9: Double-reversal guarded by a flag column instead of a ledger-derived cap

**What goes wrong:**
The natural design is `Operation.reversed = True` on the row being reversed. It cannot work here, three times over: (1) the append-only trigger ABORTs the `UPDATE`; (2) leaving the column unguarded to permit it *is* Pitfall 1; (3) the flag would not survive sync — `merge._insert_new` inserts ledger rows verbatim by origin UUID and never updates an existing one, so a flag set on device A after the row was pushed is invisible to the server and to device B. Two devices each reverse the same receipt, and stock goes double-negative.

**Why it happens:**
A boolean feels like the smallest change. The project already solved the identical problem correctly, and the solution is not a boolean: `returns.returnable_qty` (`app/services/returns.py:65-74`) computes `sold − already-returned` as a **live SUM over the ledger**, keyed on indexed columns, evaluated immediately before the write.

**How to avoid:**
Mirror `returnable_qty` exactly. Phase 3 gets `reversible_qty(session, op_id)` = the target's `qty_delta` minus `SUM(qty_delta)` of every operation whose `reverses_op_id == op_id`. Enforce **before any write**; Russian error and zero writes on failure (`returns.py:127-146` is the shape to copy). Test: reverse twice → second attempt rejected, `ops` count unchanged, **second attempt run in a fresh session** so it cannot pass on in-session state.

**Warning signs:**
Any plan mentioning a `reversed` / `is_reversed` / `storno_done` column on `operations`.

**Phase to address:** Phase 3.

---

### Pitfall 10: The reversal link stored in `payload` JSON instead of an indexed column

**What goes wrong:**
`returns.py:165` stores `payload={"origin_op_id": origin.id}` — and **never queries it**; the cap is computed from indexed `sale_id`/`product_id`/`type` columns instead. If Phase 3 stores the reversal link only in `payload`, the double-reversal cap (Pitfall 9) and История's «сторно операции X» rendering both need `WHERE payload->>'reverses_op_id' = ?`. SQLite JSON1 and PostgreSQL JSONB expose that through **different, non-portable operators**, and this project bans dialect SQL outright (`reports.py:1-7`, `sync.py:37-41`, CLAUDE.md portability rule). The result is either a portability violation that breaks the server, or a full-table Python scan of the ledger on every История render.

**Why it happens:**
`payload` looks like the free slot for "one more field", and the returns precedent appears to endorse it — but that precedent deliberately does *not* query it.

**How to avoid:**
Add a real nullable column `Operation.reverses_op_id`, modelled on `sale_id`/`batch_id`/`author_id` (`app/models.py:379-398`): `index=True`, set at INSERT time only. Keep a mirrored copy in `payload` only if История already reads payload for display. Pitfall 1's lockstep then applies to this column too.

**Warning signs:**
Any `json_extract`, `->>`, `.astext` or `func.json_*` in `app/services/`. A reversal lookup implemented as a Python loop over `session.scalars(select(Operation))`.

**Phase to address:** Phase 3.

---

### Pitfall 11: A reversal whose target has not arrived yet rolls back the entire push

**What goes wrong:**
Device A reverses operation `X` and pushes the reversal, but `X` itself may not be in the same batch (pushed earlier, or originated on device B and not yet on the server). The `reverses_op_id` FK fails. `apply_merge` never commits and the route owns one transaction (`app/routes/sync.py:116-122`), so **the entire batch rolls back** — including dozens of unrelated sales. The client sees a non-2xx, does not stamp `synced_at`, retries forever, and the unsynced badge never clears. The operator's only symptom is "синхронизация не проходит".

**Why it happens:**
`merge._REFERENCE_INSERT_ORDER` handles FK ordering *between kinds*, but `operations` is a single bucket inserted with one bulk `insert(Operation)` (`merge.py:515-517`). A **self-referential** FK inside that bucket has no ordering guarantee, and a reference to a row outside the batch has none at all. `operations` currently has zero self-FKs, so this shape is genuinely new.

**How to avoid — pick one in the Phase 3 plan, and test it:**
- **Preferred:** no DB-level FK on `reverses_op_id`. Follow the precedent already documented in `models.py:382-390` — bare native column in the migration, ORM `ForeignKey` for insert ordering and PostgreSQL portability only. A dangling link then renders as «сторно операции (ещё не получена)» in История instead of destroying a push. Verify what the migration actually emits — a bare column, not `sa.ForeignKeyConstraint`.
- If a real FK is kept, `apply_merge` must sort the operation bucket so a reversal inserts after its target, **and** the push closure must include the target — which contradicts "the ledger is pushed by `synced_at IS NULL`".

Test: push a reversal whose target is absent from both batch and server; assert the rest of the batch lands and the reversal is deferred or dangling-but-harmless — never a whole-batch rollback.

**Warning signs:**
`POST /api/sync/push` returning 500 repeatedly with a stable unsynced count. `operations_inserted: 0` on a batch the client believes is large.

**Phase to address:** Phase 3.

---

### Pitfall 12: A reversal drives stock or a batch negative, and nothing stops it

**What goes wrong:**
The operator reverses a receipt of 10 units after 8 have been sold. The compensating `−10` takes the batch to `−8`. Nothing rejects it: `record_operation` performs an unconditional `quantity = quantity + qty_delta` (`app/services/ledger.py:129-133`) with no non-negativity check, and `recompute_derived` (`:171-210`) asserts only that `Product.quantity == SUM(batch quantities) + NULL bucket` — a consistent set of negative numbers passes cleanly. Stock valuation goes negative, the low-stock report fills with impossible rows, and the invariant test still reports green.

**Why it happens:**
Oversell is deliberately **warn-but-allow** (a v1.0 decision), and every existing stock-decreasing path is operator-initiated at the moment the stock is looked at. A reversal decrements stock *retroactively*, for a quantity the operator is not currently thinking about, so warn-but-allow does not transfer.

**How to avoid:**
Phase 3 adds a **non-overridable** guard (the LIST-04/LIST-05 quick-delete shape, not the warn-but-allow shape): a receipt/return reversal is rejected when the target batch's current quantity is less than the amount to be pulled back. Russian message, zero writes. For cash, the existing warn-but-allow negative-balance gate (FIN-05) is the right precedent and can be reused as-is — cash going negative is a real, recoverable business state; negative physical stock is not.

Consider extending `recompute_derived` to also raise on `quantity < 0` for any batch. That is a behaviour change to a shared function — propose it, do not ship it silently.

**Warning signs:**
A negative quantity on `/products` or a batch card. Stock valuation smaller than expected with no matching write-off.

**Phase to address:** Phase 3.

---

### Pitfall 13: Reversing a compensating row — return-of-a-reversal, reversal-of-a-reversal

**What goes wrong:**
Reversal rows are ordinary ledger rows, so they appear in История and grow a «сторно» button of their own. Reversing a reversal is arithmetically a no-op pair, but it defeats `reversible_qty` if the cap looks only one level deep, and it makes История unreadable. Worse: `return` rows are already compensating writes capped by `returnable_qty`. Reversing a `sale` that already has a `return` double-restores stock; reversing a `return` un-restores stock the customer physically has.

**Why it happens:**
"Reversal covers every operation type" is a natural scope statement, and `OPERATION_TYPES` includes `return` (`ledger.py:19-21`).

**How to avoid:**
Phase 3 declares an explicit **allow-list** and **exclusion list**, both as constants next to `STOCK_AFFECTING_TYPES`:
- reversible: `receipt`, `writeoff`, `transfer`, `correction`, manual `cash_movement` — the four types `ROADMAP.md:353` actually scopes;
- **not** reversible: any row with `reverses_op_id IS NOT NULL`; and `sale`/`return`, because sales already have the returns flow as the sanctioned capped compensation path and a second one would let the two caps disagree;
- additionally, a `receipt` reversal is rejected when any `sale`/`return` exists against that batch (Pitfall 12's guard covers most of it — state the rule anyway).

One test per exclusion-list entry; that list is where the bugs hide.

**Warning signs:**
A «сторно» control rendered on a `sale`, a `return`, or a row carrying `reverses_op_id`. Stock arithmetic right for one reversal and wrong for a pair.

**Phase to address:** Phase 3.

---

### Pitfall 14: A date-only `business_date` compared against UTC-timestamp period bounds

**What goes wrong:**
`local_day_bounds_utc` (`app/core.py:108-126`) returns *UTC ISO timestamps* — e.g. `('2026-09-03T21:00:00+00:00', '2026-09-04T21:00:00+00:00')` for local day 2026-09-04 at Europe/Moscow. Every period report filters `created_at >= start_iso AND created_at < end_iso` with those. If `business_date` is a date-only string (`'2026-09-04'`) and someone reuses the same bounds against it, the comparison is a **lexicographic string comparison between two different formats**. At UTC+3 it accidentally lands on the right day and every test passes. At any UTC− offset it is off by a full day and the day's revenue silently belongs to the previous day.

**Why it happens:**
`local_day_bounds_utc` is the project's single sanctioned date-math helper, reused unchanged across **14 call sites** (`routes/finance.py:89,344,376`, `routes/history.py:103`, `routes/mobile_finance.py:82,347,377`, `routes/mobile_history.py:88`, `routes/reports.py:111,145,212`, `services/customers.py:446,468`, `services/dashboard.py:95`). Reusing it for the new column is the path of least resistance and it is wrong. Its own docstring warns *"never slice the UTC created_at string by date directly"* — the inverse mistake is just as bad.

**How to avoid:**
Add a **second, parallel** helper beside it — do not modify or overload `local_day_bounds_utc`:
```python
def local_day_range(start_day: date, end_day: date) -> tuple[str, str]:
    """Closed ISO date bounds for a business_date column: ('2026-09-01', '2026-09-04')."""
```
Filter `business_date >= start AND business_date <= end` — **closed**, because the granularity is a day; a half-open range is only correct for timestamps. Then audit all 14 call sites: each uses exactly one of the two helpers and never mixes shapes in one `where()`.

Add a test at a **UTC− timezone** (`display_tz="America/New_York"`). It is the only test that can catch this class of bug, because every UTC+ offset hides it.

**Warning signs:**
A period report correct at Europe/Moscow and wrong when `display_tz` changes. Any `where()` containing both a `T`-bearing ISO string and a bare `YYYY-MM-DD` against the same table.

**Phase to address:** Phase 1.

---

### Pitfall 15: Ordering by `business_date` loses the total order that `created_at, seq` provided

**What goes wrong:**
История's default order is `(created_at desc, seq desc)` (`app/services/operations.py:68,92`) — a **total** order, because `created_at` has second resolution and `UNIQUE(device_id, seq)` breaks any remaining tie. `business_date` has day resolution: every operation of a single day ties. Sorting by it alone gives a non-deterministic row order that varies between page loads and between SQLite and PostgreSQL, so `LIMIT/OFFSET` pagination can show one row on two pages and skip another entirely.

**Why it happens:**
The sort allow-list `_SORT_MAP` (`operations.py:26-28`) makes adding a "по дате операции" option a one-line change, and one-line changes do not attract tie-break scrutiny.

**How to avoid:**
Any `business_date` entry in `_SORT_MAP` must be a **tuple ending in the existing total order**: `(business_date.desc(), created_at.desc(), seq.desc())`. Same rule for every dashboard/report ordering that switches. Test: three operations sharing one `business_date` on one device, paged at `page_size=1`, each appearing exactly once.

The project already documented the same reasoning elsewhere: the sync pull cursor is composite `(cursor_column, id)` *specifically* because a single-column timestamp cursor cannot terminate across ties (`app/services/sync.py:23-30`).

**Warning signs:**
A row appearing on two pages of История. A date-sort test passing on SQLite and failing on PostgreSQL.

**Phase to address:** Phase 1.

---

### Pitfall 16: The sync cursor accidentally follows the business date

**What goes wrong:**
Reports switch from `created_at` to `business_date`, and a well-meaning "make it consistent" edit moves a cursor onto the same column. A back-dated operation then has a cursor value *behind the high-water mark* and is never delivered, forever.

**Why it happens:**
The word "date" names three different things in this codebase, and only the audit timestamp is safe to move.

**How to avoid — state these three as locked invariants in the Phase 1 plan, each pinned by a test:**
1. **Ledger push cursor is `synced_at IS NULL`**, not a timestamp (`sync_client.py:281,284`). It is structurally immune — *keep it that way*. Never introduce a `business_date > last_pushed` selection.
2. **Reference pull cursor is `sync.CURSOR_COLUMN`** (`sync.py:70-77`) and covers only the six reference kinds. `business_date` lives on `operations`, which is not a pull kind. Do not add it.
3. **`Operation.created_at` remains the audit stamp and the ordering tie-break.** `record_operation` keeps stamping it from `utcnow_iso()` (`ledger.py:123`); the operator-supplied value goes to `business_date` only, via a new `business_date: str | None = None` kwarg defaulting to `created_at`'s date part.

**Warning signs:**
`business_date` appearing anywhere in `app/services/sync.py`, `sync_client.py` or `routes/sync.py`. A back-dated operation that never leaves the client while the badge shows 0.

**Phase to address:** Phase 1.

---

### Pitfall 17: A mobile edit form silently NULLs every field it does not render

**What goes wrong:**
The mobile product edit screen shows the four fields `ROADMAP.md:402` names — min sale price, cost, category, low-stock threshold — and posts them. `update_product` (`app/services/catalog.py:162-238`) takes **every** field as a full replacement value, and `parse_optional_cents("")` / `parse_optional_int("")` return `None`, which is written to the column (`catalog.py:38-40`, `:59-61`). So the omitted `sale` (ПЦ) and `stale_days` are **set to NULL on every mobile save** — and `update_product` faithfully writes a `price_change` audit op recording the wipe, so the ledger says the operator meant it.

The customer form is worse. `_replace_contacts` (`customers.py:100`) issues a hard `DELETE FROM customer_contacts WHERE customer_id = ?` and re-inserts. `update_customer`'s contract (`:192-194`): `contacts=None` → untouched; a **dict** → full replace, *"a dict that omits a kind clears that kind"*. A mobile form showing only phones and posting `{"phone": [...]}` **deletes every telegram, email and social row** the customer had.

**Why it happens:**
FastAPI `Form("")` defaults make an omitted field indistinguishable from a cleared one, and the shared service — correctly — treats blank as "clear". This exact class of bug already shipped here: Phase 12 CR-01, *"mobile receipt wizard silently discarded operator-typed prices on a Назад→Далее round trip"*.

**How to avoid:**
Phase 4's rule, in the plan and enforced by tests: **a mobile edit form posts every field the shared service reads, or it does not use the shared service.**
- Render the full field set of `pages/product_form.html` on mobile. The `/m/batches/{id}/edit` precedent does exactly this (`app/routes/mobile_batches.py` posts all six fields `update_batch` reads).
- For customers, pass `contacts=None` unless the mobile screen renders all four `CONTACT_KINDS`.
- Test each: GET the mobile edit form → POST it back **unchanged** → assert every column and every `customer_contacts` row is byte-identical. That single round-trip test catches the whole family.

**Warning signs:**
A `price_change`/`product_edited` audit row whose new value is empty, authored from a mobile session. A customer losing their Telegram handle after an unrelated name fix.

**Phase to address:** Phase 4.

---

### Pitfall 18: HTMX partial-swap traps this codebase has already been bitten by

**What goes wrong:** three distinct failures, all previously shipped here, all silent.

1. **`| tojson` in a double-quoted attribute.** `tojson` always emits JSON's mandatory double quotes; the HTML parser truncates the attribute at the first one. Five `hx-vals="{{ ... | tojson }}"` attributes silently dropped `batch_id`/`code`/`name`/`row` before they reached the server, killing batch selection in every mobile wizard. Fixed in quick task `260813-ezt` by switching to **single** quotes. Rule: `hx-vals='{{ ... | tojson }}'`, always.
2. **Out-of-band table fragments.** A bare `<td>` or `<tr>` returned as an OOB swap is discarded or misfiled by the browser's table-parsing context. Fixed by wrapping each in `<template>` (`app/templates/partials/sale_lookup.html:18-45`, commit `2d7e545`). Rule: every OOB `<td>`/`<tr>`/`<tbody>` is `<template>`-wrapped.
3. **Filter/sort/page state dropped on the write response.** Phase 14's blocker: a write handler re-rendered the list partial without re-serialising the active filter/sort/page, so a row-specific error was rendered on a reset default page where the operator could not see it. `routes/history.py:117-135` shows the `extra_qs` re-serialisation that fixes it.

**Why it happens:**
All three are invisible in a test that asserts only status 200 and a substring, and invisible in a browser unless you happen to walk the exact path.

**How to avoid:**
Phase 4 copies the existing regression-test shape rather than inventing one: `tests/test_mobile_corrections.py::test_mobile_correction_batch_step_hx_vals_batch_id_survives_html_attribute` asserts the **exact rendered attribute string** and additionally guards `'hx-vals="{' not in response.text`. Add the equivalent for every new mobile edit partial. For (3): a 422 from a mobile edit must re-render with the same context the GET had (`mobile_batches.py:58-80` is the template to copy).

**Warning signs:**
`rg 'hx-vals="' app/templates` returning anything. An OOB `<tr` not immediately preceded by `<template>`. A 422 whose body lacks the filter/sort inputs the GET rendered.

**Phase to address:** Phase 4.

---

### Pitfall 19: The reversal's business date — get it wrong and the corrected period never heals

**What goes wrong:**
A receipt was recorded with business date 2026-08-15 and was wrong. The operator reverses it on 2026-09-04. If the compensating row carries **today's** business date, August keeps the erroneous quantity forever and September shows a phantom negative that corresponds to nothing that happened in September. Neither period is true, and no later action can repair August without a second back-dated correction.

The silent version of this is worse: **if `record_operation` gains a `business_date` kwarg that defaults to today and Phase 3's reversal service simply does not pass it, every reversal lands in the wrong period by default** — no error, no warning, and the operator only discovers it when a month's totals refuse to reconcile.

**Why it happens:**
"The correction happened today" is an intuitive but wrong reading. It confuses the *audit* question (when did the operator act? — answered by `created_at`, which correctly says today) with the *business* question (which period was misstated? — answered by `business_date`, which must say August). The append-only design already separates these two; the reversal must respect the separation rather than collapse it.

**How to avoid:**
Phase 3 locks this as a decision with a one-line rationale:
> A reversal carries the **`business_date` of the operation it reverses**, copied verbatim. Its `created_at` is today, so the audit trail truthfully records when the correction was made. The erroneous period nets to zero; the current period is untouched.

This is the same freeze-from-the-origin discipline the returns flow already uses for price and cost (D-07, `returns.py:161-162`) — extend it to the date. Test: reverse an operation whose `business_date` is in a previous month; assert the compensating row's `business_date` equals the target's, its `created_at` is today, and **both** the previous month's and the current month's period reports are correct.

**Ordering dependency, and why the stated phase order matters:** this rule is only expressible once `business_date` exists. `PROJECT.md:41-45` already sequences Phase 1 before Phase 3, which is correct — **do not reorder them.** If reversal shipped first, every reversal written in the interim would carry no business date, and there is no way to retrofit one afterwards: the ledger is append-only and the rows are immutable. That is an irreversible data defect, not a deferred feature.

**Warning signs:**
A reversal whose `business_date` equals its `created_at` date when the target's does not. A closed month whose totals still include an operation the operator has already reversed.

**Phase to address:** Phase 3 (the rule), enabled by Phase 1 (the column). The dependency is hard, not soft.

---

### Pitfall 20: Back-dating into a period that has already been reported or reconciled

**What goes wrong:**
The operator enters a sale today with `business_date = 2026-08-15`. Last month's report was already read, exported to CSV and acted on. The number changes retroactively with no marker that it did. Cash is sharpest: the balance is a live `SUM(amount_cents)` (`finance.compute_balance`, D-00b), so a back-dated cash movement rewrites a period balance the operator may have physically reconciled against a cash box.

**Why it happens:**
There is no concept of a closed period, and adding one is a much larger feature than back-dating. The gap is therefore a boundary to draw explicitly, not a bug to fix.

**How to avoid — Phase 1 picks one and states it; do not leave it implicit:**
- **(a) Bounded back-dating, recommended:** clamp `business_date` to `[today − N days, today]`, N configurable, default ~45 to cover an Oriflame catalog period. Future dates rejected outright — a future business date poisons every "current period" report and has no legitimate use. One validation function shared by desktop and mobile, sitting beside `parse_optional_cents`.
- **(b) Unbounded with a visible marker:** История and every period report flag rows where `date(created_at) != business_date` as «задним числом», so a changed historical total is at least explicable.

Note (a) and Pitfall 19 interact: a reversal of an operation older than the window must still be allowed to carry that older date. Exempt reversals from the operator-facing clamp — the date is copied, not typed.

**Warning signs:**
A closed month's revenue changing between two viewings. A `business_date` in the future.

**Phase to address:** Phase 1.

---

### Pitfall 21: One migration, or two? — and the rollout order against a live server plus late-syncing clients

**What goes wrong:**
Phase 1 ships migration 0027 (`business_date`). Phase 3 needs `reverses_op_id` (Pitfall 10) — a second one, 0028. Meanwhile the server is a Docker image with **code baked in** (project memory `s1-image-baked-code-gotcha`: updates need `up -d --build`, not `git pull`), clients auto-update from GitHub Releases and run `alembic upgrade head` themselves (v4.0 UPD-01..07), and the offline USB path can carry a bundle built days earlier. Any ordering other than server-first produces Pitfall 4 (silent field loss) or a hard sync stall.

**A disagreement worth naming.** The coordinator's framing is that only one migration lands this milestone, the business date. That holds **only if the reversal link avoids a new column** — i.e. if it lives in `payload`. Pitfall 10 argues that is not viable: the double-reversal cap and История's rendering must *query* the link, and there is no portable way to query JSON across SQLite and PostgreSQL under this project's no-dialect-SQL rule. I can find no third option: the link cannot be derived from existing columns, because a compensating row is otherwise indistinguishable from an ordinary one of the same type. So **plan for two columns.** If the roadmapper disagrees, the decision needs to be made explicitly with Pitfall 9's cap in hand — not assumed.

**How to avoid:**
- **Recommended: combine them into one migration delivered in Phase 1.** Add `business_date` *and* `reverses_op_id` together; Phase 3 only starts *writing* `reverses_op_id`. One server redeploy instead of two, one trigger DDL rewrite instead of two (and one pass through Pitfall 1's five-artifact lockstep instead of two), and the gap between the two phases stops mattering. It trades a little "schema before its readers" purity for a large cut in rollout risk. Put the choice to the operator rather than defaulting.
- **Rollout order, written into the plan:** migrate + redeploy s1 → verify `/api/sync/pull` and a push from a current client → only then cut the client release tag.
- **The Phase 0 push gate (Pitfall 4) is the safety net** that makes a wrong order fail loudly instead of losing data. Ship it before any schema change.
- **The offline bundle path is already safe** — `offline.schema_version_ok` (`app/services/offline.py:61-71`) is exact-match and rejects a stale bundle before any merge. Confirm the message tells the operator to rebuild the bundle after updating, not merely that it failed.

**Warning signs:**
A client release tag cut before the s1 image is rebuilt. `alembic_version` on s1 lagging the client's. Sync succeeding with `operations_inserted > 0` while the new column is empty server-side.

**Phase to address:** Phase 0 (gate + rollout runbook), enforced by Phases 1 and 3.

---

### Pitfall 22: Editing a record while it is being synced

**What goes wrong:**
The operator opens a product edit form, the background auto-sync tick fires (interval sync, default 300 s, `sync_client.py:49-53`), the pull overwrites that product row with the server's values, and the operator's POST then saves a form rendered from now-stale data — clobbering what the server just sent. No error, no conflict marker.

**Why it happens:**
`sync_client._run_lock` serialises sync runs against each other (`:228`) but not against interactive request handlers. Reference upsert on pull is a blind server-wins UPDATE; there is no version token on the form.

**How to avoid:**
At this scale (one operator, one device at a time) the proportionate fix is **not** optimistic locking. Phase 4: render the record's `updated_at` as a hidden field and reject the POST with a Russian "запись изменилась, откройте заново" when it no longer matches. Ten lines, reuses an existing column, no schema change. Note it is only meaningful on the server (where mobile edits land) and on a client for the pull direction — combined with Pitfall 8's decision, keep the scope honest.

**Warning signs:**
An edit that "did not save" with no error shown. A product whose `updated_at` is newer than the edit the operator remembers making.

**Phase to address:** Phase 4.

---

### Pitfall 23: A reversal loses its currency, or a legacy-row reversal buckets as RUB

**What goes wrong:**
Two currency × reversal interactions:
1. `CashMovement.currency` is NOT NULL with a `DEFAULT_CURRENCY` server default since 0024. A storno that omits it silently takes RUB — a EUR withdrawal reversed as a RUB deposit, leaving *both* currencies' balances wrong.
2. `operation_currency_clause` (`reports.py:21-38`) resolves currency via `Operation.batch_id → Batch.warehouse_id → Warehouse.currency`, falling back to `DEFAULT_CURRENCY` when `batch_id IS NULL` (pre-Phase-9 legacy rows). A reversal must therefore be written **against the same batch** as its target, or it lands in a different currency's report than the row it cancels — the two never net to zero in any single-currency report.

**Why it happens:**
The compensating row gets built from scratch rather than derived from the target. `returns.py:154-179` already shows the correct derivation: resolve the batch, read `warehouse.currency`, pass it explicitly to `record_cash_movement`.

**How to avoid:**
Phase 3's reversal service **derives every field from the target row**, never from current state or column defaults: same `product_id`, same `batch_id`, negated `qty_delta`, frozen `unit_price_cents`/`unit_cost_cents` copied verbatim (the D-07 precedent), the target's own `currency` for cash, and the target's `business_date` (Pitfall 19). Test: reverse a EUR withdrawal → the compensating row is EUR and both balances are right. Test: reverse a legacy NULL-batch operation → both rows land in the same currency bucket.

**Warning signs:**
A reversal that does not net to zero in the currency-filtered report it appears in. A cash balance changing in a currency the operator did not touch.

**Phase to address:** Phase 3 (depends on Phase 2 having locked the currency-resolution rules).

---

### Pitfall 24: `CustomerContact` is not a sync kind at all

**What goes wrong:**
`merge.KIND_TO_MODEL` (`app/services/merge.py:67-76`) covers `warehouse, product, customer, dictionary, batch, sale, operation, cash_movement`. **`CustomerContact` is absent.** Phones, Telegram handles, emails, social links and their ordering exist only on the machine where they were entered. Phase 4 adds mobile customer editing — mobile is server-only, so those edits live on the server and **never** reach the desktop client, in either direction, ever.

**Why it happens:**
`CustomerContact` arrived in Phase 21 (v2.0), after the sync engine's design in Phase 27's terms but before the v3.0 wire vocabulary was finalised — it simply never got added. Nothing surfaces the omission because contacts are display-only.

**How to avoid:**
Phase 4 states this explicitly rather than letting the operator discover it. Either:
- **(a)** scope the mobile customer edit to the columns that *are* synced (`name`, `surname`, `consultant_number`, `address`) and leave contacts desktop-only, saying so in the UI; **or**
- **(b)** add `customer_contact` to `RECORD_KINDS` / `KIND_TO_MODEL` / `_REFERENCE_INSERT_ORDER` (after `customer`) — a real wire-format change that bumps `FORMAT_VERSION` and re-triggers Pitfall 4's whole rollout problem. Not small; do not do it casually inside a mobile-UI phase.

(a) is the right call for v5.0. Test that the phase's scope matches whichever is chosen.

**Warning signs:**
A phone number entered on the phone that is missing on the desktop after a successful sync reporting no errors.

**Phase to address:** Phase 4.

---

### Pitfall 25: Three reports were never currency-scoped, and the operator cannot tell

**What goes wrong:**
The operator picks EUR on `/reports/sales` and reads a correctly scoped euro report. The write-offs report, top-selling products and stale products on the neighbouring pages **silently keep aggregating every warehouse in every currency**. Verified in `app/routes/reports.py`:

| Report | Call | Currency-scoped? |
|---|---|---|
| Sales / profit | `sales_profit_report(session, start_iso, end_iso, author or None, currency)` (`:114`) | **yes** |
| Write-offs | `writeoff_report(session, start_iso, end_iso)` (`:148`) | **no** |
| Top-selling products | `top_selling_products(session, start_iso, end_iso)` (`:215`) | **no** |
| Stale products | `stale_products(session)` (`:217`) | **no** |

These three aggregate *quantities*, not money, so no wrong money total is printed — which is exactly why the gap survived review. But the scope is silently inconsistent: "write-offs for the period" includes another country's warehouse while the report next to it does not, and there is no label saying so.

**Why it happens:**
The currency quick task scoped the surfaces that summed money and stopped there. Quantity-summing reports looked currency-neutral. They are not: a *warehouse* dimension is what the operator is actually filtering by, and currency is its proxy.

**How to avoid:**
Phase 2 decides per report and writes the decision down — the goal is that no report is silently un-scoped:
- pass `currency` through `writeoff_report` and `top_selling_products` using the same `operation_currency_clause` + **outer** join chain the sales report uses (`reports.py:31-37` documents why an inner join would be a data-loss-shaped bug — legacy NULL-batch rows would vanish rather than bucket as RUB); **or**
- label each explicitly as "все склады" in the UI, so the inconsistency is visible rather than assumed away.

`stale_products` is period-independent and product-level; leaving it global is defensible — say so in a comment rather than leaving it ambiguous.

**Warning signs:**
Switching the currency selector changes one report on the page and not its neighbours. A write-off total that cannot be reconciled against the same period's currency-scoped sales.

**Phase to address:** Phase 2.

---

### Pitfall 26: Storno breaks every aggregate that is not a plain SUM

**What goes wrong:**
A compensating row nets correctly through `SUM(qty_delta)` — that is the whole design. It does **not** net through `MAX`, `COUNT`, or a `GROUP BY` on a key the compensating row does not carry. Three concrete breaks, all verified in `app/services/reports.py`:

1. **`writeoff_report` groups by a payload-derived key.** `reason_code = (op.payload or {}).get("reason_code", "other")` (`:153`). A storno of a write-off that does not copy the target's `payload` lands in the **`"other"`** bucket with a *negative* qty, while the original reason keeps its full positive qty. The grand total is right and **both** per-reason lines are wrong — and `"other"` can display a negative number.
2. **`stale_products` uses `MAX(created_at)`** over `type == 'sale'` (`:224`). Any compensating row written with a `sale` type refreshes "last sold", so a product whose only sale was cancelled looks freshly sold and drops off the stale report. (Pitfall 13 excludes `sale` from reversal, which closes this — but only if that exclusion actually ships.)
3. **`sales_profit_report` counts rows, not units:** `cost_unknown_count += 1` (`:108`). A compensating row adds another count, so the operator-facing caveat overstates how many lines lack a cost.

**Why it happens:**
"Append a compensating row and every total fixes itself" is true for SUM and quietly false for everything else. The three non-SUM shapes are scattered and none of them looks like money code.

**How to avoid:**
Phase 3 adopts one rule and then audits against it:
> The compensating row carries the **same `type` and a verbatim copy of the target's `payload`**, plus `reverses_op_id`. It differs from its target only in the sign of `qty_delta` and in its own identity/audit fields.

Same type keeps every existing `WHERE type == ...` filter finding it, so SUMs net without touching any report. Copied payload keeps every `GROUP BY payload[...]` netting inside the right bucket. Then walk `reports.py`, `dashboard.py`, `finance_reports.py` and `customers.py` for aggregates that are **not** `SUM` — `MAX`, `COUNT`, `func.count`, `.limit()` over an ordered aggregate — and decide each one explicitly: exclude reversal rows and their targets, or accept and document.

Reject the tempting alternative of a dedicated `storno` operation type: every existing `type ==` filter would then miss the compensating row entirely and *nothing* would net.

**Warning signs:**
A write-off report whose «прочее» line is negative. A product missing from the stale report with no real sale behind it. Per-reason lines that do not add up to a total that is nonetheless correct.

**Phase to address:** Phase 3 (the rule and the audit), with the report-side fixes landing wherever the audit finds them.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| Store the reversal link in `Operation.payload` JSON only | No migration, no trigger lockstep, no FK question | Double-reversal cap and История rendering need non-portable JSON SQL or a full ledger scan; breaks the PostgreSQL parity rule (Pitfall 10) | Never |
| A `reversed` boolean on the reversed row | Trivially simple check | Blocked by the append-only trigger; invisible across sync; two devices double-reverse (Pitfall 9) | Never |
| Reversal carries today's business date instead of the target's | One less field to thread through | The misstated period never heals; unrepairable once written, because the ledger is append-only (Pitfall 19) | Never |
| A dedicated `storno` operation type | Clean discriminator, easy to spot in История | Every existing `WHERE type == ...` filter misses the compensating row, so nothing nets anywhere (Pitfall 26) | Never |
| Reuse `local_day_bounds_utc` for `business_date` filters | Zero new code, all 14 call sites unchanged | Off-by-one-day at any UTC− timezone, invisible at Europe/Moscow (Pitfall 14) | Never |
| Ship the currency phase as "add a symbol where it's obviously missing" | Fast, visible progress | The 48 unlabelled templates are exactly the ones nobody looks at; partial labelling is *worse* than none, because a labelled surface teaches the operator to trust unlabelled ones (Pitfall 5) | Never — the sweep must be exhaustive and checklisted |
| Skip the push schema-version gate because "we'll deploy in the right order" | Saves ~30 lines in Phase 0 | One wrong-order deploy silently destroys back-dated/reversal data behind a 200 response (Pitfall 4) | Never — this milestone adds a schema change and clients self-update |
| Leave `Warehouse.currency` editable | No new guard code | Retroactive relabelling of all history through the join (Pitfall 7) | Only until the first non-RUB warehouse exists — which it already does |
| One combined migration for `business_date` + `reverses_op_id` | One server redeploy, one trigger rewrite, one lockstep pass; halves rollout risk (Pitfall 21) | Slight deviation from "schema before its readers"; Phase 3's column sits unused for a phase | **Acceptable and recommended** — put it to the operator |
| Mobile edit form rendering a subset of the desktop fields | Smaller phone screen, less scrolling | Silently NULLs omitted columns / deletes omitted contact kinds (Pitfall 17) | Only with `contacts=None` and a service that accepts partial updates — which `update_product` does not |
| Leaving write-offs / top-selling un-scoped by currency | Nothing to change | Silently inconsistent scope next to a scoped report, with no label (Pitfall 25) | Acceptable **only** with an explicit "все склады" label |
| No closed-period concept; unbounded back-dating | Ships Phase 1 faster | Reported and exported figures change retroactively with no marker (Pitfall 20) | Acceptable **only** with the «задним числом» marker, option (b) |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| `POST /api/sync/push` (online) | Assuming it validates schema compatibility because the offline path does | It performs **no** schema check (`app/routes/sync.py:66-133`). Add the gate reusing `offline.schema_version_ok` |
| `merge.KIND_TO_FIELDS` | Reading "derived from model columns → the field propagates automatically" as "the field is safe" | It is derived from the **receiver's** columns. An older receiver drops unknown fields silently (Pitfall 4) |
| `merge._upsert_reference` (push) | Expecting a client-side product/customer/warehouse edit to reach the server | Existing UUIDs are **discarded**. Reference data is server-authoritative and one-directional (Pitfall 8) |
| `sync_client._apply_pull_page` (pull) | Expecting a local edit to survive the next sync | Existing UUIDs are **overwritten** with server values (Pitfall 8) |
| `Operation.synced_at` | Adding a `business_date`-based push selection "for consistency" | The push cursor is `synced_at IS NULL` and is structurally immune to back-dating. Keep it (Pitfall 16) |
| Append-only triggers | Treating them as a blanket `BEFORE UPDATE` | They enumerate columns since migration 0018. A new column escapes them (Pitfall 1) |
| Alembic + SQLite | Using `batch_alter_table` freely on `operations`/`cash_movements` | Only `add_column`/`create_index`/`drop_index` avoid a table recreate; a recreate silently drops all four triggers (Pitfall 3) |
| PostgreSQL trigger DDL | Writing only the SQLite branch of a trigger migration | Both branches required, with `IS NOT` vs `IS DISTINCT FROM` null semantics (migration `0026`) |
| `operation_currency_clause` | Reaching it through an INNER join | Its docstring is explicit: an inner join silently DROPS legacy NULL-batch rows from every currency's report — a data-loss-shaped bug. OUTER join chain only |
| `CustomerContact` | Assuming every model syncs | It is not in `RECORD_KINDS` (Pitfall 24) |
| Docker server on s1 | `git pull` to update the server | App code and data files are **COPY-baked into the image**; needs `up -d --build` (project memory) |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| Computing "is this operation already reversed?" per rendered История row | История page load slows with page size × ledger size; shows on the s1 server first | One aggregate query per page: `SELECT reverses_op_id, SUM(qty_delta) ... WHERE reverses_op_id IN (<page ids>) GROUP BY reverses_op_id`, chunked under `merge._IN_CHUNK` (500) like every other id-membership probe here | Immediately at 20 rows/page against a real ledger |
| `reverses_op_id` without `index=True` | Reversal cap and История lookups full-scan `operations` | Mirror `sale_id`/`batch_id`/`author_id`: `index=True` | Once the ledger passes a few thousand rows |
| `business_date` unindexed while it becomes the period-filter column | Every report degrades; `created_at` had implicit help from insertion order | Index `business_date`; add a composite `(business_date, type)` only if a profile shows the need | Likely already, at s1's current volume |
| Python-side reversal-chain walking | CPU spike on История render | Forbid reversal chains outright (Pitfall 13); depth is then always ≤ 1 | Never, if the exclusion rule ships |
| `local_day_range` string comparisons on an unindexed text column | Slow period reports, PostgreSQL especially | Store `business_date` as `String(10)` ISO text (consistent with `created_at`'s text storage and the portability rule) **and** index it | At a few tens of thousands of ledger rows |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| Reversal route trusting a client-supplied `op_id` without re-validating existence, type and reversibility server-side | An operator, or a forged request, reverses an arbitrary or already-reversed row, corrupting stock and cash | Mirror `returns.register_return`'s opening guard (`returns.py:129-131`): re-fetch the op, check it exists, check its type is in the reversible allow-list, check the cap — **all before any write**, zero writes on failure |
| Reversal exposed to the `operator` role without thought | An operator silently erases an administrator-recorded correction | Decide the role split explicitly in Phase 3 (ROLE-01..04 exist). Recommended: operators may reverse their **own** rows within the back-dating window; administrators may reverse any |
| `?currency=` reaching a query unvalidated | Injection surface / unlabelled money | Already solved; copy it — `_clean_query_currency` (`app/routes/mobile_home.py:21-27`, `routes/reports.py:33`, T-quick-260810-02): allow-list against `CURRENCIES`, never the raw value |
| Operator-supplied `business_date` parsed with a bare `datetime.fromisoformat` | 500 on malformed input; a far-past/far-future date poisoning every report | Validate in the project's existing guard style: `date.fromisoformat` in try/except returning a Russian field error, plus Pitfall 20's range clamp |
| Mobile edit routes added outside the session guard | AUTH-01..05 bypassed on the new surface | Confirm the new route pair is not under `security.OFFLINE_PATH_PREFIX` and that CSRF flows via the `hx-headers` on `mobile_base.html:33` |
| Echoing raw exception text from a failed reversal or a rejected push | Leaks internal ids / SQL to an untrusted caller | Follow `routes/sync.py`'s V7 rule: fixed strings and integer counts only |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---|---|---|
| A «сторно» button that acts on one tap | An irreversible ledger write from a mis-tap on a phone | Confirmed control, as `ROADMAP.md:353` already specifies. Show *what* will be written ("будет создана компенсирующая операция −10 шт, партия X, дата 15.08.2026") before confirming — and show the copied business date, since Pitfall 19 makes it load-bearing |
| Reversal succeeding with no visible trace on the reversed row | The operator reverses the same receipt twice because the first left no mark | История renders «сторнирована» on the target and «сторно операции X» on the compensating row, both derived from `reverses_op_id` |
| Business-date field defaulting to blank | Every operation gets hand-typed dates; typos become permanent ledger data | Default to today in `display_tz`, pre-filled and visible, `type="date"` so the phone gets a native picker |
| Back-dated rows indistinguishable from same-day rows | A changed monthly total is inexplicable | Mark rows where `date(created_at) != business_date` (Pitfall 20b) |
| Currency shown only in the filter `<select>`, not on the numbers | The operator scrolls past the filter and misreads UAH as RUB | Pitfall 5's sweep — label the figures, not just the control |
| A currency `<select>` that renders empty | Silent dead end; no report at all | The global CLAUDE.md check: every select the change touches renders non-empty. The currency quick task verified this on 3 surfaces over live HTTP — repeat for every new one |
| Mixed-currency basket rejected with the typed basket wiped | Data loss of exactly the CR-01 kind this project has shipped before | **Already handled — keep it that way.** The rejection surfaces via `errors["basket"]` and is rendered by `partials/sale_form.html:8` and `mobile_partials/sale_basket.html:11`, while `_build_lines` and `_customer_context` (`routes/sales.py:58-137`) re-echo every typed row and all three customer modes. The gap is that only the **service** contract is pinned by a test (`tests/test_sales.py:617`); no route-level test asserts the basket survives the render (see the checklist) |
| Mobile edit form scrolling past the save button | Edits abandoned | Follow the `/m/batches/{id}/edit` layout precedent; 44 px touch targets as in `mobile_base.html` |
| Russian-language gaps in new error strings | Inconsistent with every other message | Every new error is a module-level RU constant, as in `returns.py:39-43`, `sales.py:40-48`, `warehouses.py:18-19` |

---

## "Looks Done But Isn't" Checklist

- [ ] **Business date:** trigger updated in **all five** artifacts (model, SQLite DDL, PG DDL, `app/db.py`, `IMMUTABLE_OPERATION_COLUMNS`) — verify `test_trigger_column_list_matches_schema` **and** `test_declared_constants_match_trigger_ddl` are green *for the right reason*
- [ ] **Business date:** a UTC− timezone test exists (`display_tz="America/New_York"`) — without it the date-boundary bug is untestable
- [ ] **Business date:** all 14 `local_day_bounds_utc` call sites audited; each uses exactly one date helper, never both shapes in one `where()`
- [ ] **Business date:** every ordering that mentions it ends in `created_at desc, seq desc`
- [ ] **Business date:** `rg business_date app/services/sync.py app/services/sync_client.py app/routes/sync.py` returns nothing
- [ ] **Currency:** counted sweep — every `| cents` site either switched to `| money(...)` or annotated with why it is already unambiguous. Count them; do not eyeball
- [ ] **Currency:** a EUR sale from a pre-0025 NULL-cost batch does not inherit the RUB `Product.cost_cents`
- [ ] **Currency:** `Warehouse.currency` rejected on edit once the warehouse has any batch/operation/cash row
- [ ] **Currency:** write-offs and top-selling are currency-scoped **or** labelled "все склады"; `stale_products`' global scope is documented
- [ ] **Currency:** a route-level test posts a mixed-currency basket and asserts the response still contains every typed code/qty/price and the selected customer mode — the service-level test at `tests/test_sales.py:617` does not cover the render
- [ ] **Currency:** product CSV export carries a currency or is documented as warehouse-agnostic
- [ ] **Reversal:** double-reversal blocked by a ledger-derived cap, proven by a test whose second attempt runs in a **fresh session**
- [ ] **Reversal:** the compensating row copies the target's `business_date`, `payload`, `batch_id`, `type` and frozen prices; only `qty_delta`'s sign and its own identity fields differ
- [ ] **Reversal:** reversing a `receipt` whose stock has been sold is rejected, zero writes
- [ ] **Reversal:** `sale`, `return` and any row with `reverses_op_id IS NOT NULL` render **no** «сторно» control
- [ ] **Reversal:** a push containing a reversal whose target is absent does not roll back the whole batch
- [ ] **Reversal:** a reversed EUR cash movement produces a EUR compensating row; both balances correct
- [ ] **Reversal:** every non-SUM aggregate (`MAX`, `COUNT`, `GROUP BY payload[...]`) in `reports.py`/`dashboard.py`/`finance_reports.py`/`customers.py` has been walked and decided
- [ ] **Reversal:** desktop **and** mobile История both carry the control (`ROADMAP.md:366`)
- [ ] **Mobile editing:** GET the form → POST it back unchanged → every column and every `customer_contacts` row byte-identical
- [ ] **Mobile editing:** every new `hx-vals` is single-quoted; `rg 'hx-vals="' app/templates` returns nothing
- [ ] **Mobile editing:** every new OOB `<td>`/`<tr>` is `<template>`-wrapped
- [ ] **Mobile editing:** the 422 error branch re-renders with the same context the GET had
- [ ] **Cross-cutting:** `POST /api/sync/push` rejects a batch whose `schema_version` mismatches, and the client leaves `synced_at` NULL on that rejection
- [ ] **Cross-cutting:** a migration-built (not `create_all`) DB still has all four append-only triggers, live
- [ ] **Cross-cutting:** rollout runbook written — s1 rebuilt and verified **before** the client release tag is cut
- [ ] **Cross-cutting:** the 4 known-flaky `tests/test_sync_ui.py` failures are recognised as pre-existing (project memory) and not attributed to this milestone

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| Field silently dropped on push, client already stamped `synced_at` (Pitfall 4) | **HIGH** | The value exists only on the client. Export the affected client rows and hand-merge into the server; there is no automatic path, because the rows are no longer selected by `synced_at IS NULL`. This is why the Phase 0 gate is non-negotiable |
| Append-only triggers dropped by a batch recreate (Pitfall 3) | LOW to detect, HIGH if undetected | Re-issue `APPEND_ONLY_TRIGGERS` in a follow-up migration (the `0026` shape). If undetected, any UPDATE in the window is unrecoverable — the ledger has no before-image |
| Reversal written with the wrong business date (Pitfall 19) | **HIGH** | Unrepairable in place: the row is immutable. The only remedy is a second, hand-composed back-dated correction in each of the two affected periods — which is precisely the manual work this milestone exists to remove |
| Warehouse currency flipped after it held stock (Pitfall 7) | LOW | Flip it back; nothing is stored per-row, so reports self-correct. Which is also why it must be blocked *before* the operator learns to use it as a feature |
| Double reversal already written (Pitfall 9) | MEDIUM | Cannot delete — append-only. Write a `correction` for the delta and mark it, then verify with `ledger.rebuild_stock`, which recomputes every cached quantity from the ledger and asserts the invariant |
| Stock driven negative by a reversal (Pitfall 12) | MEDIUM | Same: a compensating `correction`, then `rebuild_stock`. The ledger is intact; only the cached projection and the operator's trust need repair |
| Mobile save NULLed `sale_cents` / `stale_days` (Pitfall 17) | LOW–MEDIUM | The `price_change`/`product_edited` audit ops written by `update_product` contain the old values — recover from the ledger. This works only because the audit path exists; never bypass it |
| Mobile save deleted customer contacts (Pitfall 17) | **HIGH** | `_replace_contacts` hard-DELETEs, and `CustomerContact` is neither in the ledger nor synced (Pitfall 24). Recovery is a backup restore (`backups/`, VACUUM INTO) or retyping. Prevent, do not recover |
| Back-dated row changed an already-exported report (Pitfall 20) | LOW | Re-export. The cost is the operator's trust, not the data — which is the argument for the «задним числом» marker |
| Client reference edit lost to a pull overwrite (Pitfall 8) | MEDIUM | Redo the edit on the server. Unavoidable under the current topology; the fix is the UI note, not a recovery procedure |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| 4 — new column silently dropped by an older-code server | **Phase 0** | Push gate returns non-2xx on schema mismatch; test with a monkeypatched old `KIND_TO_FIELDS`; client leaves `synced_at` NULL |
| 3 — batch recreate drops append-only triggers | **Phase 0** (test) / 1 & 3 (enforce) | Alembic-built DB has all four triggers, and an UPDATE on a guarded column aborts |
| 21 — migration count and rollout order | **Phase 0** (runbook + decision) / 1 & 3 | One-or-two-migrations decision recorded; s1 verified before the client tag; offline bundle rejection message actionable |
| 1 — new ledger column escapes the trigger | Phase 1, repeated Phase 3 | Both append-only cursor tests green; both DDL branches present |
| 2 — backfill aborts against its own trigger | Phase 1 | `alembic upgrade head` succeeds on a DB seeded with pre-existing operations |
| 14 — date-only column vs UTC-timestamp bounds | Phase 1 | Period-report test at a UTC− `display_tz` |
| 15 — ordering ties on `business_date` | Phase 1 | Three same-date ops paged at `page_size=1` appear exactly once each |
| 16 — sync cursor follows the business date | Phase 1 | `business_date` absent from all three sync modules; back-dated op still pushes |
| 20 — back-dating into a reported period | Phase 1 | Future dates rejected; out-of-window dates rejected or marked; reversals exempt from the clamp |
| 5 — unlabelled money surfaces | Phase 2 | Counted sweep checklist complete; rendered-HTML test on History/Products/mobile History |
| 6 — currency-less `Product.cost_cents` fallback | Phase 2 | EUR sale from a NULL-cost batch does not inherit the RUB product cost |
| 7 — warehouse currency editable after use | Phase 2 | Currency change rejected with zero writes once stock/ops/cash exist |
| 25 — write-offs / top-selling / stale not currency-scoped | Phase 2 | Each of the three is scoped, or labelled, or documented — none left silently ambiguous |
| 9 — double reversal | Phase 3 | Second reversal rejected in a fresh session, `ops` count unchanged |
| 10 — reversal link in JSON payload | Phase 3 | `reverses_op_id` is a real indexed column; no JSON operators in `app/services/` |
| 11 — reversal FK rolls back a whole push | Phase 3 | Push with an absent target lands the rest of the batch |
| 12 — reversal drives stock negative | Phase 3 | Reversal of a partly-sold receipt rejected, zero writes |
| 13 — reversal of a return / of a reversal | Phase 3 | No «сторно» on `sale`/`return`/already-reversal rows; one test per exclusion |
| 19 — reversal's business date | Phase 3 (needs Phase 1 first — hard dependency) | Compensating row's `business_date` equals the target's, `created_at` is today, both periods correct |
| 23 — reversal loses currency / batch bucket | Phase 3 | EUR withdrawal reversal is EUR; legacy NULL-batch reversal shares its target's bucket |
| 26 — storno breaks non-SUM aggregates | Phase 3 | Write-off storno lands in the target's reason bucket, not «прочее»; the non-SUM audit is recorded |
| 17 — mobile form NULLs omitted fields | Phase 4 | Unchanged GET→POST round trip is byte-identical, products and customers |
| 18 — HTMX swap traps | Phase 4 | Exact-attribute assertions; `rg 'hx-vals="'` empty; OOB fragments `<template>`-wrapped |
| 8 — client reference edits lost | Phase 4 | UI note present, or the decision recorded; sync test asserts the documented behaviour |
| 22 — editing during sync | Phase 4 | Stale `updated_at` POST rejected with a Russian message |
| 24 — `CustomerContact` not synced | Phase 4 | Phase scope matches the chosen option; a test pins it |

---

## Sources

**Primary — this repository at `b4ca98c` (HIGH confidence, direct reads):**

- `app/services/ledger.py` — `record_operation` single write path, no non-negativity guard, `recompute_derived` invariant
- `app/services/merge.py` — `KIND_TO_FIELDS` (`:80-83`), `_ledger_row` (`:451-462`), `_reference_row`, `_upsert_reference` (`:421-448`), `_insert_new`, `apply_merge`, `KIND_TO_MODEL` (`:67-76`, no `CustomerContact`)
- `app/services/reports.py` — `operation_currency_clause` (`:21-38`), currency-scoped `sales_profit_report`, un-scoped `writeoff_report` (`:127-171`) / `top_selling_products` (`:186-209`) / `stale_products` (`:212-263`), payload-derived `reason_code` (`:153`), row-counting `cost_unknown_count` (`:108`), `MAX(created_at)` (`:224`)
- `app/routes/reports.py:104-232` — which report gets a `currency` argument and which does not
- `app/services/sync.py` — `CURSOR_COLUMN` (`:70-77`), composite-cursor rationale (`:23-30`), `current_schema_version`
- `app/services/sync_client.py` — push selection by `synced_at IS NULL` (`:281,284`), stamp-after-2xx (`:384-390`), `_apply_pull_page` server-wins (`:417-428`)
- `app/services/offline.py:61-71` — `schema_version_ok`, the gate the online push route lacks
- `app/routes/sync.py:66-133` — `POST /api/sync/push`, no schema check
- `app/services/returns.py` — `returnable_qty` cap precedent (`:65-74`), frozen origin price/cost (`:161-162`), currency-aware compensating cash write (`:154-179`)
- `app/services/sales.py:40-48,199-204,291-299` — `MIXED_CURRENCY_ERROR` and its pre-write check; `Product.cost_cents` fallback
- `app/routes/sales.py:58-137` — `_customer_context` and `_build_lines` basket-preservation contracts
- `app/templates/partials/sale_form.html:8`, `mobile_partials/sale_basket.html:11` — where `errors.basket` renders
- `app/services/warehouses.py:149-178` — unguarded currency edit
- `app/services/catalog.py:31-65,162-238` — blank→NULL parsing, `update_product` full-replacement semantics
- `app/services/customers.py:100-115,177-224` — `_replace_contacts` hard DELETE, `update_customer` two-state contract
- `app/services/operations.py:26-28,68,92` — sort allow-list and default total order
- `app/core.py:49-126` — `format_cents` / `format_money` / `currency_symbol` / `local_day_bounds_utc`
- `app/db.py:37-85` — column-enumerating append-only triggers + LOCKSTEP RULE
- `app/models.py:348-404,493-540` — `Operation` (no business date, no reversal link), `CashMovement.currency`
- `app/config.py:76` — `display_tz` default, loaded from `.env`, outside the synced DB
- `app/routes/__init__.py:203,227` — `cents` and `money` Jinja filters
- `app/templates/**` — measured: `money(` in 1 file, `cents`/`format_cents` in 49 files / 124 occurrences
- `alembic/versions/0023..0026` — currency migrations, `server_default` backfill idiom, dual-dialect trigger DDL, the 0026 lockstep repair
- `tests/test_append_only_cursor.py` — `IMMUTABLE_*_COLUMNS`, `test_trigger_column_list_matches_schema`, `_DRIFT_HINT`
- `tests/test_pragmas.py:28-44` — the recorded batch-recreate / trigger hazard
- `tests/test_merge.py:662,677` — the under-migrated-DB loud-failure contract
- `tests/test_sales.py:617-637` — the service-level mixed-currency rejection test (no route-level counterpart)
- `.planning/quick/260810-2g3-.../260810-2g3-SUMMARY.md` — the shipped currency work, 20/20 live-HTTP scenarios
- `.planning/quick/260813-ezt-.../260813-ezt-SUMMARY.md` — the `hx-vals`/`tojson` quoting failure and its regression tests

**Project history (HIGH confidence):**
- `.planning/PROJECT.md` — Key Decisions, phase-ordering precedents, Phase 12 CR-01, Phase 14 blocker
- `.planning/ROADMAP.md:327-410`, `.planning/OPEN-WORK-AUDIT-2026-09-04.md` — **stale** on currency; see the correction at the top
- Project memory: `s1-image-baked-code-gotcha`, `preexisting-sync-ui-test-failures`, `jinja-tojson-attribute-quotes`, `packaging-fixtures-must-match-real-archive`

**External (MEDIUM–HIGH):**
- [Running "Batch" Migrations for SQLite and Other Databases — Alembic docs](https://alembic.sqlalchemy.org/en/latest/batch.html) — `recreate="auto"` recreates for anything beyond `add_column`/`create_index`/`drop_index`; the move-and-copy reflects table structure and silently omits objects it cannot reflect (documented for unnamed CHECK/UNIQUE constraints; triggers are not reflected either). Corroborated in-repo by `tests/test_pragmas.py:28-34`.
- [Operation Reference — Alembic docs](https://alembic.sqlalchemy.org/en/latest/ops.html)

**Marked `needs verification`:**
- Whether `tests/conftest.py`'s `engine` fixture builds via `create_all` (making the trigger-liveness test non-migration-proving) — read the fixture before relying on it
- The `display_tz` value actually configured in the s1 container's `.env.production`
- Whether the s1 PostgreSQL deployment's `alembic_version` is at `0026` today

---
*Pitfalls research for: reversal, business dates, per-warehouse currency and mobile card editing on an existing append-only synced inventory system*
*Researched: 2026-09-04*
