---
phase: 33
slug: back-dated-operations
status: verified
threats_open: 0
threats_total: 40
asvs_level: 1
block_on: open
created: 2026-09-04
mode: verify-mitigations
register_authored_at_plan_time: true
register_source: 33-01-PLAN.md … 33-15-PLAN.md `<threat_model>` blocks
audit_head: 30d398f
---

# Phase 33 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
>
> Phase 33 lets the operator enter an operation for a day **other than today**. It adds a
> nullable `business_date` (plus two unused `reverses_*` reversal-link columns) to both
> append-only ledger tables via migration `0027`, teaches both `*_no_update` triggers to
> guard all four, backfills the existing rows timezone-correctly, switches nine
> period-scoped reports / two CSV dumps / История from `created_at` to the business date,
> and puts a `<input type="date" name="op_date">` on 14 write surfaces. It also adds an
> HTTP 409 push gate (`SYNC-10`) so a client whose Alembic revision is AHEAD of the server
> can no longer have its rows silently dropped and acknowledged.
>
> New attack surface is therefore: **operator form text (`op_date`) → SQL predicate +
> Jinja template + stored ledger column**, **a URL-editable `dated` query parameter →
> WHERE branch**, and **a schema migration with a destructive-if-wrong `downgrade()` run
> against live production data**.
>
> Every `mitigate` row below was VERIFIED present in implemented code. Plan text,
> SUMMARY claims and code comments were NOT accepted as evidence — each row cites the
> exact line performing the control plus the test that proves it. The auditor
> independently re-ran, on 2026-09-04 at HEAD `30d398f`:
>
> ```
> uv run pytest tests/test_migrations.py tests/test_append_only_cursor.py \
>                tests/test_sync_schema_gate.py -q            -> 26 passed
> uv run pytest tests/test_business_date.py -q                -> 35 passed
> uv run pytest tests/test_history.py tests/test_export.py \
>                tests/test_finance_reports.py tests/test_merge.py \
>                tests/test_sync_client.py -q                 -> 175 passed
> uv run pytest tests/test_sales.py tests/test_transfers.py \
>                tests/test_mobile_sales.py tests/test_mobile_corrections.py \
>                tests/test_mobile_transfers.py tests/test_receipts.py \
>                tests/test_finance.py -q                     -> 376 passed
> uv run pytest tests/test_pg_parity.py -q -rs                -> 10 skipped
> ```
>
> 612 passed, 0 failed. The 10 skips are the PostgreSQL parity suite auto-skipping with
> no `DATABASE_URL` — this independently confirms the phase's own «не запускал» record is
> honest and not a dressed-up pass.

---

## Register provenance

The register was authored at plan time and is treated as COMPLETE. It was rebuilt for this
audit by parsing the `## STRIDE Threat Register` table out of each of the 15
`33-NN-PLAN.md` `<threat_model>` blocks. **40 distinct threat ids**: `T-33-01` … `T-33-39`
plus `T-33-SC`. Nine ids recur across plans (`T-33-03`, `T-33-07`, `T-33-08`, `T-33-11`,
`T-33-16`, `T-33-17`, `T-33-18`, `T-33-22`, `T-33-SC`); each is verified once, against the
union of every plan's mitigation text for it.

Dispositions as authored: **38 `mitigate`**, **2 `accept`** (`T-33-25`, `T-33-SC`). No
`transfer` rows. No `<config>` block exists in any Phase-33 plan, so `asvs_level: 1` /
`block_on: open` are carried forward from `32-SECURITY.md` rather than declared.

---

## Trust Boundaries

| # | Boundary | Introduced / touched by |
|---|----------|------------------------|
| B1 | device client → `POST /api/sync/push` — bearer-authenticated but untrusted NDJSON | 33-01, 33-03 |
| B2 | server HTTP status + body → local client control flow and operator-visible header text | 33-02 |
| B3 | migration chain → live schema; `alembic upgrade head` against s1's real ledger | 33-03, 33-05, 33-15 |
| B4 | operator form input (`op_date`) → service validation → SQL predicate, stored ledger column, Jinja template | 33-06, 33-10 … 33-13 |
| B5 | operator-chosen period (`from_date`/`to_date`) → WHERE clause + paginated count | 33-07, 33-08 |
| B6 | stored ledger text → CSV file opened in a formula-capable spreadsheet host | 33-09 |
| B7 | `dated` query parameter (URL-editable) → WHERE branch | 33-14 |
| B8 | local build → s1 production; s1 → self-updating client fleet | 33-04, 33-15 |

---

## Threat Verification

### Sync schema gate (33-01 / 33-02 / 33-03)

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-33-01 | Tampering — `merge._ledger_row` silently dropping an unknown wire field behind a 200 | mitigate | **CLOSED** | Gate runs BEFORE any DB touch: `app/routes/sync.py:136-143` (`push_schema_ok(batch.schema_version, server_schema)` → `HTTPException(409)`). Predicate: `app/services/sync.py:238` (asymmetric `client <= server`, both-sided escape hatch). `_ledger_row` deliberately NOT changed (AP-3); the drop itself is pinned as a regression test — `tests/test_merge.py:751-793` (`test_unknown_field_is_dropped`, asserts DROP-not-reject and that no trace of the dropped value survives in the row). Route gate proven end-to-end at `tests/test_sync_schema_gate.py:136-155` (409 + zero `Operation` rows) and `:158-172` (a BEHIND client still merges). |
| T-33-02 | Information disclosure — the 409 response body | mitigate | **CLOSED** | `SCHEMA_AHEAD_ERROR` is a fixed RU constant with exactly two format slots: `app/routes/sync.py:56-58`. Formatted with `client=batch.schema_version, server=server_schema` only — `app/routes/sync.py:140-142`. No request bytes, no exception text, no token. Asserted byte-for-byte at `tests/test_sync_schema_gate.py:152-154`. |
| T-33-03 | Denial of service (self-inflicted) — permanent-409 client retrying every 300 s and burning a rate-limit token | mitigate | **CLOSED** | `app/main.py:111-114` — after the tick, `sync_state.last_status` is re-read from a fresh session and `interval = sync_client.MAX_INTERVAL_SECONDS` (3600, `app/services/sync_client.py:52`) when it is `schema_mismatch`. Self-clears on the first non-mismatch tick; the manual «Синхронизировать» path does not share this sleep. |
| T-33-04 | Repudiation — a refused client believing its rows were accepted | mitigate | **CLOSED** | Test-only by design (D-07). `tests/test_sync_schema_gate.py:178-218` drives the REAL client across the ASGI boundary and asserts, after a 409: `unsynced_count` unchanged, `COUNT(*) WHERE synced_at IS NOT NULL == 0`, zero rows on the server, and `sync_state.last_sync_at` did not advance. Backed by the code path: `synced_at` is stamped only after `raise_for_status()` (`app/services/sync_client.py:385, 404-405`). |
| T-33-05 | Information disclosure — server `detail` bytes reaching the operator's header | mitigate | **CLOSED** | The client inspects only the status code and returns early WITHOUT reading the body: `app/services/sync_client.py:386-397`. `format_sync_message` emits one fixed RU sentence for `schema_mismatch`: `app/services/sync_client.py:208-215`. Pinned by `tests/test_sync_client.py:700-718` — the mock server returns a 409 whose `detail` names both revisions, and the test asserts neither `"0027"` nor `"0026"` nor the server text reaches the message. |
| T-33-06 | Repudiation — suppressing `#sync-badge` on a refusal would hide the unsent backlog | mitigate | **CLOSED** | Verified as a NON-change: `git diff 4a39a9a..HEAD -- app/templates/partials/sync_status.html` is empty. The badge renders purely from the `unsynced` count (`app/templates/partials/sync_status.html:16`), which is passed unconditionally at `app/routes/sync.py:260` and `app/routes/__init__.py:160` — it is not gated on `last_status`. |
| T-33-09 | Spoofing — a non-fixed-width revision id makes `push_schema_ok`'s lexicographic ordering meaningless | mitigate | **CLOSED** | `tests/test_migrations.py:98-133` (`test_revision_ids_are_fixed_width`) globs `alembic/versions/[0-9]*.py`, asserts `>= 26` files, and `re.fullmatch(r"\d{4}", ...)` on every `revision` literal plus `r'"\d{4}"'` on every non-root `down_revision`. A regex tripwire, not a parser, as specified. Re-run green. |

### Append-only ledger + migration 0027 (33-03 / 33-05)

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-33-07 | Tampering — a ledger column escaping the trigger enumeration is freely mutable on an already-synced row; the ledger fails OPEN, silently | mitigate | **CLOSED** | All four new columns present in **both dialect branches**: SQLite `_SQLITE_DDL` — `alembic/versions/0027_ledger_business_date_and_reversal_links.py:138` (`reverses_op_id`), `:143` (`business_date`), `:158` (`reverses_movement_id`), `:163` (`business_date`); PostgreSQL `_PG_DDL` — same file `:183`, `:188`, `:200`, `:205`. Present in `app/db.py::APPEND_ONLY_TRIGGERS` at `app/db.py:62, 67, 86, 91`. Present in **both frozensets**: `tests/test_append_only_cursor.py:51, 56` and `:69, 74`. VA-5 diffs the live `alembic upgrade head` triggers against `APPEND_ONLY_TRIGGERS` **as a whole name→DDL map** — `tests/test_migrations.py:50-69`. VA-8 closes both remaining directions — models↔constants at `tests/test_append_only_cursor.py:250-262`, constants↔DDL at `:265-294`. All re-run green. **Residual, see § Residual risks R1:** VA-5 reads `sqlite_master`, so no automated tripwire covers `_PG_DDL`'s `WHEN` enumeration; the PG half is closed by direct inspection plus the live PG run, not by a standing test. |
| T-33-08 | Tampering — a `downgrade()` silently dropping the four triggers / destroying the cash guards via a batch-mode recreate | mitigate | **CLOSED** | `downgrade()` restores the pre-0027 guards FIRST (`0027…py:384-389`, dispatching to `_SQLITE_DOWNGRADE_DDL:213-253` / `_PG_DOWNGRADE_DDL:255-289`), THEN drops the columns with plain `op.drop_column` (`:391-394`). `batch_alter_table` appears **nowhere** in the file (verified by grep). The shipped `0024.downgrade()` defect is named in the docstring (`:26-36`) and deliberately NOT fixed. Pinned by VA-6 — `tests/test_migrations.py:72-95`: head → `downgrade -1` → `upgrade head` still yields exactly the four trigger names. Re-run green. |
| T-33-13 | Tampering — SQL injection through the backfill | mitigate | **CLOSED** | The timezone is a file-local literal constant, never an app-config read: `0027…py:103` (`_DISPLAY_TZ = "Europe/Moscow"`). Every SQL string is a module-level literal: `_BACKFILL_SELECT:107-110`, `_BACKFILL_UPDATE:112-115`. The per-row values are bound parameters only: `0027…py:353-361` (`sa.text(update_sql)` with `{"bd": …, "id": …}`). No f-string reaches SQL. WR-06 holds — the module imports only `datetime`, `zoneinfo`, `sqlalchemy`, `alembic` (`:84-89`); no `app.*` import. |
| T-33-14 | Tampering (data corruption) — a naive `substr(created_at,1,10)` backfill silently moving evening rows into the wrong month | mitigate | **CLOSED** | Real timezone conversion, not a slice: `0027…py:292-315` (`_local_business_date` → `datetime.fromisoformat` → naive-is-UTC → `.astimezone(ZoneInfo(_DISPLAY_TZ)).date().isoformat()`). DATE-07 byte-identity proven by VA-9 — `tests/test_business_date.py:430-557`: builds a DB at revision 0026, seeds a row straddling local midnight, runs the REAL migration on the same file, asserts the raw pre-0027 column snapshot is byte-identical afterwards (`:501`), asserts the straddler backfilled to `2026-09-01` while its own `created_at[:10]` is `2026-08-31` (`:507-508`), and asserts the full report dict is unchanged (`:557`). **The test has teeth**: `:532-550` runs the naive-`substr` counterfactual and asserts it DIVERGES (13 units vs the correct 6), so "tz-correct" is measured, not adjectival. Second pin at `:560-598` exercises `_local_business_date` at a positive AND a negative UTC offset. Confirmed on real data: 403 of 1504 production rows have a business date differing from their naive UTC prefix (`33-ROLLOUT.md:449-450`). |
| T-33-15 | Denial of service — `alembic upgrade head` aborting mid-upgrade because the backfill trips its own new trigger | mitigate | **CLOSED** | Order is LOCKED and commented in place: `0027…py:318-369` — (1) `op.add_column` ×4 `:342-347`, (2) backfill `:352-361`, (3) trigger rewrite `:364-369`. The rationale (value-based `FOR EACH ROW WHEN` over an explicit enumeration, so an UPDATE of a not-yet-named column evaluates false) is written at `:319-333`. Proven **necessary and sufficient by execution**, not by argument: real PostgreSQL 17 upgrade over a throwaway copy of the live 1504-row production database ran to completion (`33-ROLLOUT.md:275-278`), and again on s1 itself (`33-ROLLOUT.md:428-433`). SQLite half proven by VA-6's round trip. |

### Operator input `op_date` (33-06 / 33-10 / 33-11 / 33-12 / 33-13)

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-33-16 | Tampering — SQL injection via `op_date` or a period bound | mitigate | **CLOSED — all entry points checked** | Single validator: `app/services/ledger.py:37-73` — `date.fromisoformat(s)` then `parsed.isoformat()`; the value that leaves is a re-serialised 10-char ISO string, never the raw input. It reaches SQL only as a bound ORM parameter (`record_operation`'s `business_date=` kwarg, `app/services/ledger.py:193`). **Every one of the 14 write surfaces routes through it**: `app/services/corrections.py:110`, `app/services/finance.py:188`, `app/services/receipts.py:148`, `app/services/returns.py:161`, `app/services/sales.py:203`, `app/services/transfers.py:92`, `app/services/writeoffs.py:83`. All 14 routes delegate rather than writing directly — desktop `receipts.py:245`, `sales.py:562`, `writeoffs.py:154`, `corrections.py:141`, `transfers.py:192`, `returns.py:138`, `finance.py:244,323`; mobile `mobile_receipts.py:274`, `mobile_sales.py:541`, `mobile_writeoff.py:235`, `mobile_corrections.py:231`, `mobile_transfers.py:242-294`, `mobile_returns.py:142`, `mobile_finance.py:246,323`. Period bounds are parsed `date` objects re-serialised by `app/core.py:134-168` (`business_date_bounds`) and bound via `.where(...)`. `max=` on the input is browser convenience only — the server refuses regardless (`tests/test_business_date.py:182-195`). |
| T-33-17 | Tampering — XSS via the echoed value on a 422 re-render | mitigate | **CLOSED (with a documentation discrepancy, see § Residual risks R2)** | Jinja autoescaping is genuinely ON: Starlette builds the environment with `autoescape=jinja2.select_autoescape()` (`.venv/Lib/site-packages/starlette/templating.py:95`) and `app/routes/__init__.py:185-188` uses the stock `Jinja2Templates`. Every template directory file is `.html`, so autoescape applies. `op_date` is never rendered with `\|safe` — grep of `app/templates/` returns 20 `\|safe` mentions, **all of them prose comments forbidding it**, plus one unrelated `offline/self_upload.html:112`. The value is rendered only inside double-quoted attributes: e.g. `app/templates/partials/withdraw_form.html:87`, `deposit_form.html:73`, `correction_form.html:113`, `transfer_form.html:83`. The RU error strings are fixed module constants, not operator text: `app/services/ledger.py:29-30`. |
| T-33-18 | Repudiation — an operator-supplied date overwriting the audit timestamp | mitigate | **CLOSED** | `created_at=utcnow_iso()` is untouched at the single write path: `app/services/ledger.py:183`. `business_date` is a separate column stamped at `:193`. Both are enumerated in the append-only triggers (`app/db.py:66-67`, `:90-91`), so neither is mutable after insert. Asserted directly at `tests/test_transfers.py:904` (`all(op.created_at[:10] != "2026-08-15" for op in ops)`). |
| T-33-19 | Tampering — the sync queue silently following the business date | mitigate | **CLOSED** | VA-11 — `tests/test_business_date.py:136-154` reads all three sync modules line-by-line and fails on ANY occurrence of `business_date`. Independently confirmed: `grep -c business_date` returns **0** for `app/services/sync.py`, `app/services/sync_client.py` and `app/routes/sync.py`. The push cursor remains `synced_at IS NULL`. |
| T-33-28 | Tampering — a batch auto-named with today while its receipt line reads a back-date | mitigate | **CLOSED** | The fallback is resolved exactly once, before the batch name is built: `app/services/receipts.py:158` (`resolved_business_date = business_date or local_today_iso(...)`), consumed by the auto-name at `:240` (`f"{product.name} — {format_ru_date(resolved_business_date)}"` → `:245`) and by every `record_operation` call at `:186, 213, 279`. Existing names are snapshots and are not migrated (0027 touches only the two ledger tables). |
| T-33-29 | Repudiation — a sale whose ledger rows and cash movement carry different business dates | mitigate | **CLOSED** | One parse, one resolve, threaded into both write paths: `app/services/sales.py:203` → `:291` → ledger lines `:330` and `finance.record_cash_movement(..., business_date=resolved_business_date)` `:345`. Pinned by the equality assertion at `tests/test_sales.py:1847-1848` — the same `back_date` is asserted on both `_sale_ops(...)[0].business_date` and `_sale_cash(...)[0].business_date` through the real `POST /sales`. |
| T-33-30 | Tampering (silent data loss) — the mobile sale basket re-render resetting a typed date to today | mitigate | **CLOSED** | D-11 shell placement: the input lives in the persistent wizard shell OUTSIDE `#wizard-step`, which is the only node htmx swaps — `app/templates/mobile_pages/sales.html:35-40` (input) vs `:41-43` (`#wizard-step`). Pinned twice: structurally at `tests/test_mobile_sales.py:1000-1023` (no swapped fragment contains the string `op_date` at all — a future hidden-field "fix" reddens here), and behaviourally at `:1026-…` (`test_sale_date_survives_the_basket_product_round_trip` — set date → add product → back to basket → add a second → finalize, and the back-date lands on the ledger). Both re-run green. |
| T-33-31 | Repudiation — a transfer's two ledger rows carrying different business dates | mitigate | **CLOSED** | One resolve at `app/services/transfers.py:199`, both call sites at `:211` and `:220`. Pinned at `tests/test_transfers.py:902-903` (`len({op.business_date for op in ops}) == 1`) and, for the empty-date path, `:922-923`. |
| T-33-32 | Information disclosure (usability-grade) — a duplicated or detached date error confusing which field is wrong | mitigate | **CLOSED** | Per-key error under the input: `app/templates/mobile_partials/corrections_step_value.html:71` and `app/templates/mobile_partials/transfers_step_dest.html:101` (both `<p class="error" id="op_date-error">`, tied by `aria-describedby` at `:70` / `:100`). Exclusion from the loop-all block: `corrections_step_value.html:26` (`errors.keys() \| reject("eq", "op_date")`). Desktop forms carry only per-key blocks — `correction_form.html:114`, `transfer_form.html:84`. Exactly-once asserted at `tests/test_mobile_corrections.py:424` and `:452`, and `tests/test_mobile_transfers.py:712`. |
| T-33-33 | Tampering (usability-grade) — duplicate `id="op_date"` on the finance page breaking `<label for>` | mitigate | **CLOSED** | Prefixed ids shipped: `app/templates/partials/withdraw_form.html:85-86` (`withdraw-op-date`) and `deposit_form.html:71-72` (`deposit-op-date`). Asserted directly by VA-15's data-driven exception rows — `tests/test_business_date.py:682-685` and `:719-722` (the exception set is asserted as a property of the table, so it cannot silently grow), with the `<label for="…">Дата операции</label>` association checked per surface at `:803-805`. |
| T-33-34 | Repudiation — a cash column populated only by the backfill and by Phase 34, never by the operator | mitigate | **CLOSED** | VA-15 — `tests/test_business_date.py:662-709` is the locked 14-surface table INCLUDING `снятие` and `внесение`; `:712-726` locks the count at 14 and rejects silent growth; `:781-811` parametrises over all 14 and asserts each renders `name="op_date"`, the right `id`, its `<label for>`, `value="{{ today }}"` and the right wrapper class. 14/14 re-run green. Write path exists: `app/services/finance.py:188` → `:235` → `record_cash_movement(..., business_date=…)` `:112`. |

### Period-scoped reads (33-07 / 33-08 / 33-09 / 33-14)

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-33-20 | Tampering (silent wrong answer) — a half-switched family: predicate on `business_date`, bounds still UTC timestamps | mitigate | **CLOSED** | Verified as an exhaustive sweep, not a spot check: **`local_day_bounds_utc` has zero remaining call sites in `app/`** — every occurrence outside its own definition (`app/core.py:108`) is a docstring cross-reference (`app/core.py:139,149`, `app/services/export.py:233`). All 20 live bound-producing call sites use `business_date_bounds` (`app/routes/finance.py:89,367,401`, `mobile_finance.py:82,369,400`, `history.py:110`, `mobile_history.py:92`, `reports.py:111,143,208`, `app/services/customers.py:455,479`, `dashboard.py:101`). All predicates use `business_date_expr` (`app/services/reports.py:119,197,258`, `finance_reports.py:40,138`, `operations.py:242`, `customers.py:422,566`, `export.py:139,240`, `warehouses.py:118`). The one deliberate non-switch is documented as decision D-25 with its reason: `app/services/reports.py:281-287` (`stale_products` answers elapsed real time, not a bookkeeping period). `cash_expense_total` and `cash_flow_report` moved together and are pinned by the equality assertion at `tests/test_finance_reports.py:882` (`flow["expense_total_cents"] == total`) over a deliberately mixed row set (on-time + back-dated-onto-the-last-day + income + a NULL-`business_date` row). |
| T-33-21 | Repudiation — a period report silently dropping rows from an un-upgraded client | mitigate | **CLOSED** | `app/services/reports.py:77` — `func.coalesce(model.business_date, func.substr(model.created_at, 1, 10))`, a portable ORM construct (no `strftime`/`date_trunc`/`::date`). Pinned by VA-12 — `tests/test_business_date.py:601-628`: a row inserted the way `merge` does (bypassing `record_operation`, so `business_date IS NULL`) is still counted by `sales_profit_report` and `top_selling_products` for its `created_at` day, **and** is correctly absent from the following day, so the fallback buckets rather than matching everything. Reinforced at `:276-…` (the bulk sync path must still land a genuine NULL). |
| T-33-22 | Tampering (silent wrong answer) — `stmt` switched, `count_stmt` not; the pager total disagrees with its own rows | mitigate | **CLOSED — both predicates, both filters** | Period predicate lands on both statements in one block: `app/services/operations.py:240-246` (`period` tuple applied to `stmt` at `:245` and `count_stmt` at `:246`). `dated` predicate likewise: `:284-285`. Pinned by four independent `len(rows) == total` assertions — `tests/test_history.py:582-597` (period, with noise on both sides of the range), `:731-742` (`dated=backdated`), `:744-756` (`dated=same_day`), `:759-771` (the NULL-`business_date` case in both directions). Re-run green. |
| T-33-23 | Repudiation — a just-entered back-dated row disappearing from the «recent N» feed used to confirm the entry landed | mitigate | **CLOSED** | VA-17 — `tests/test_history.py:600-648`. Asserts that a row entered LAST but back-dated to `2020-01-01` is still first in all three feeds: `ledger_view(...)["operations"][0]`, `recent_operations(...)[0]`, `recent_writeoffs(...)[0]`. Additionally pins the allow-list itself against re-keying: `set(_SORT_MAP) == {"oldest"}`, `_SORT_MAP["oldest"] == [created_at ASC, seq ASC]`, `_DEFAULT_ORDER == [created_at DESC, seq DESC]` (`:640-648`). Second pin at `:651-662` through `history_view` itself. |
| T-33-24 | Information disclosure — a date-only string rendered through `local_dt` printing a fabricated time | mitigate | **CLOSED** | Every switched cell uses `\| ru_date`: `app/templates/partials/history_rows.html:157` and `:282`, `mobile_partials/history_cards.html:40`, `partials/warehouse_rows.html:83`, `partials/customer_insights.html:20,26,32,38`, `mobile_partials/return_confirm.html:22`. Cross-checked in the other direction: every remaining `\| local_dt` receives a genuine `created_at`/`last_used_at`/`created_iso` timestamp — including `pages/reports_products.html:32`, which is correct precisely because `stale_products` deliberately stayed on `created_at` (D-25). The misleading comment was **rewritten, not left in place**: `app/templates/partials/warehouse_rows.html:71-82`. |
| T-33-26 | Repudiation — an export whose headline date column contradicts the period the file was selected for | mitigate | **CLOSED** | Row-set predicate and column 1 use the same expression and the same fallback. Cash: predicate `app/services/export.py:240-244` (`business_date_expr(CashMovement)`), render `:261` (`movement.business_date or movement.created_at[:10]`). Sales: `business_date_expr(Operation)` in the ORDER BY at `:138`, render `:174` (`op.business_date or op.created_at[:10]`). The Python `or` fallback mirrors the SQL `COALESCE` exactly. Pinned at `tests/test_export.py:651-…` (one movement back-dated INTO the period appears, one back-dated OUT does not — a split impossible under the old `created_at` predicate). |
| T-33-27 | Tampering (silent wrong answer) — a dump that reads as unsorted by its own first column | mitigate | **CLOSED** | **Both** ORDER BY clauses switched, including the CD-9 one the decision log never enumerated: `app/services/export.py:138` (sales) and `:250` (cash). Pinned by `tests/test_export.py:629-648` (`test_csv_first_column_non_decreasing`), which **seeds rows in an order that contradicts their business dates** (`2026-06-20`, `2026-06-10`, `2026-06-15`) and asserts column 1 is non-decreasing in BOTH dumps — a dump still ordered by `created_at` fails immediately. Re-run green. |
| T-33-35 | Tampering — SQL injection via `dated` | mitigate | **CLOSED** | Three-value allow-list resolved before any predicate is built: `app/services/operations.py:70` (`_DATED_FILTERS = ("backdated", "same_day")`) and `:265` (`dated_key = dated if dated in _DATED_FILTERS else ""`). The branches at `:268-283` construct fixed ORM predicates only; the operator string never reaches SQL. Proven with a real payload at `tests/test_history.py:774-790`: `history_view(session, dated="'; DROP TABLE operations; --")` returns the unfiltered row set, echoes `dated == ""`, and the `operations` table is still queryable afterwards. |
| T-33-36 | Repudiation — a back-dated row indistinguishable from a same-day one | mitigate | **CLOSED** | Marker is RU WORDS on both desktop layouts and on mobile: `app/templates/partials/history_rows.html:156-161` and the type-narrowed twin `:280-287` (`задним числом · внесено {{ … }}`), `app/templates/mobile_partials/history_cards.html:40-42`. Plus the 4th filter `<select id="dated">` at `history_rows.html:69-79`. **Colour is never the cue**: the entire Phase-33 CSS delta is `.field.op-date { flex-basis: 100% }` — `git diff 4a39a9a..HEAD -- app/static/style.css` adds no colour and no new token. Row keys pinned at `tests/test_history.py:706-716`; the NULL case renders byte-identically to today at `:719-728`. |

### Rollout to production (33-04 / 33-15)

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-33-10 | Tampering (data corruption) — a backfill parameterised by a guessed timezone rewriting s1's entire history by one day | mitigate | **CLOSED** | The value was MEASURED, not guessed: `33-ROLLOUT.md:28` (V14a — `.env.production` has no `DISPLAY_TZ` line), `:29` (V14b — `printenv DISPLAY_TZ` in the container is empty), `:30` (V14 — therefore `Europe/Moscow` from the `app/config.py:76` fallback). Transcribed into the migration as a literal: `0027…py:97-103`. WR-06 holds — the migration imports no `app.*` module (`0027…py:84-89`). Pinned as a test, not a comment: `tests/test_business_date.py:584` asserts `module._DISPLAY_TZ == "Europe/Moscow"`. |
| T-33-11 | Denial of service — migrating s1 mid-flight, or cutting the client tag first | mitigate | **CLOSED** | The LOCKED order was written down before the migration was authored (`33-ROLLOUT.md:111` onward) and executed in that order on 2026-09-04: steps 1–4 done, **step 5 (cutting the client release tag) deliberately NOT done** because step 4's push half is only half-verified — `33-ROLLOUT.md:406-408, 461-463` and `33-VALIDATION.md:152`. The failure mode the threat names (client ahead of server) therefore has not occurred, and the SYNC-10 409 gate (T-33-01) bounds it if the order ever slips. |
| T-33-12 | Information disclosure — pasting `.env.production` contents into a planning artifact | mitigate | **CLOSED** | Only the `DISPLAY_TZ` line was read (`33-ROLLOUT.md:40`). Independent scan of `33-ROLLOUT.md` and `33-VALIDATION.md` for `DATABASE_URL\|password\|token\|secret` returns **no secret values** — every hit is either a prose statement that nothing was recorded (`33-ROLLOUT.md:22, 406`), an empty-string demonstration (`:364` — `SYNC_TOKEN=""`), a CI service-container placeholder deliberately elided (`:239, 242`), or a procedural instruction about which token to use (`:477, 510`). No password, no connection string, no bearer token. |
| T-33-37 | Tampering (unproven dialect) — the PostgreSQL branch never exercised before it runs on production | mitigate | **CLOSED** | The mitigation as authored is an either/or, and the honest branch is what shipped: `tests/test_pg_parity.py` is recorded as **«не запускал» with the exact command** at `33-ROLLOUT.md:239, 249-250`, never as a pass — independently confirmed by this audit (`uv run pytest tests/test_pg_parity.py -q -rs` → 10 skipped, `tests/test_pg_parity.py:34-36` skipif on `DATABASE_URL`). The threat itself is nonetheless closed by a **stronger** proof: `pg_dump` of live production → restored into a throwaway `parity_0027` database on the running `postgres:17-alpine` → `alembic upgrade head` in a one-off container → smoke SQL → dropped. Verbatim output at `33-ROLLOUT.md:262-311` shows the real `0026 -> 0027` upgrade, `1504\|1504` and `0\|0` coverage, exactly four trigger names, 403 tz-corrected rows with samples, and `ERROR: operations ledger is append-only` still raised from `operations_append_only()`. **Residual, see § Residual risks R1.** |
| T-33-38 | Tampering (data corruption) — an incomplete backfill leaving NULL business dates on the server | mitigate | **CLOSED** | The `total == filled` query was run against the real s1 data after the real migration: `33-ROLLOUT.md:441-447` — `operations` `1504\|1504`, `cash_movements` `0\|0`, applied revision `0027`. Run a second time on the throwaway copy beforehand with the same result (`:284-288`). Backed in code by the `if created_at` guard and the malformed-timestamp fallback that prevents a NULL from surviving a parse failure (`0027…py:307-310, 357-358`). |
| T-33-39 | Denial of service — restarting or killing the operator's live instance while verifying | mitigate | **CLOSED** | Recorded explicitly: `33-ROLLOUT.md:402-406` — "Nothing was started, stopped or restarted other than the intended `up -d --build` recreation of `ori-app`", performed with the operator's explicit authorisation in that session. The PG parity proof ran against a throwaway COPY on the already-running container, with production and the container untouched (`:253-258`). The seven browser checks ran in the operator's own instance (`33-ROLLOUT.md` § Browser checks → `33-UAT.md`). No process was killed to free a port. |

---

## Accepted Risks Log

| Threat ID | Category | Component | Accepted because | Premise re-verified |
|-----------|----------|-----------|------------------|---------------------|
| **T-33-25** | Tampering — CSV formula injection through a cell | `app/services/export.py` | Unchanged by this phase. The existing `_csv_safe` path still handles every free-text cell, and the two columns Phase 33 touched are machine-rendered dates that cannot carry a leading `=`, `+`, `-` or `@`. | **TRUE.** `_csv_safe` is intact at `app/services/export.py:51-55` with `_INJECTION_PREFIXES`. `git diff 4a39a9a..HEAD -- app/services/export.py` changes **no** `_csv_safe` line — the phase neither added nor removed a call. The two touched cells are `format_ru_date(...)` (`:174`, `:261`) and `iso_to_local(...)` (`:185`, `:266`), both of which emit `dd.mm.yyyy[ HH:MM]` — digit-leading by construction. Pre-existing un-wrapped cells (`op.created_by`, `movement.currency`) predate this phase and are outside the register. |
| **T-33-SC** | Tampering — npm/pip/cargo supply chain | dependency manifests | No package is installed by this phase; the gate is vacuous, not skipped. | **TRUE.** `git diff 4a39a9a..HEAD -- pyproject.toml uv.lock requirements.txt package.json` is **empty** — all four untouched across the entire phase. Recorded at `33-RESEARCH.md:442-447` ("Not applicable — this phase installs no external packages"; 0 `[SLOP]`, 0 `[SUS]`). |

---

## Residual risks (not blockers — recorded for the next phase)

**R1 — no standing PostgreSQL tripwire for the trigger `WHEN` enumeration.**
`T-33-07`'s named proofs (VA-5, VA-8) are both SQLite-only: VA-5 queries `sqlite_master`
(`tests/test_migrations.py:45`), and VA-8 inspects `app/db.py::APPEND_ONLY_TRIGGERS`, which
is the SQLite DDL. Neither can see `0027`'s `_PG_DDL`. If a future migration omitted a
column from the PostgreSQL branch only, both stay green while the server-side ledger fails
open. For Phase 33 specifically this is closed by direct inspection (`0027…py:183, 188,
200, 205`) plus the live PG run, but the **standing guard is absent** and
`tests/test_pg_parity.py` contains no assertion touching `business_date` or
`reverses_*` (it was not modified by this phase). Already recorded as open backlog in
`33-ROLLOUT.md` § Backlog (items 1, 2) and `33-VALIDATION.md:171`. Suggested closure: add a
PG-side immutability case for the four new columns to `tests/test_pg_parity.py`, and fix
the pre-existing unrelated `tests/test_launcher.py::test_parse_pending_rejects_path_traversal`
failure that aborts the CI parity job before it reaches the step.

**R2 — `T-33-17`'s mitigation text overstates by one clause.**
`33-06-PLAN.md` claims the echoed value "is additionally normalised to a 10-char ISO date
before it can be echoed". It is not: the routes echo the **raw** form string
(`app/routes/receipts.py:230`, `finance.py:221,301`, `sales.py:534`, `transfers.py:164`,
`corrections.py:127`, and the mobile twins), and `parse_op_date` returns `None` on a
malformed value without normalising it. The threat is still CLOSED because the primary
control — Jinja autoescaping with no `\|safe`, inside a double-quoted attribute — is real
and sufficient (`"` escapes to `&#34;`, so attribute breakout is impossible). Recorded so
nobody later removes the autoescape defence believing a normalisation layer exists behind
it. Suggested closure: none required; correct the claim if the register is ever reused.

**R3 — two rollout items remain open by design.** The live pre-update-client push against
s1 (LOCKED step 4, push half) is unverified, and the client release tag is deliberately not
cut. Both are correctly sequenced (`T-33-11`) and preserved with reproduction steps in
`33-ROLLOUT.md:477, 510`.

---

## Unregistered Flags

**None.** All 14 `33-NN-SUMMARY.md` files that carry a `## Threat Flags` section declare
`None`, and each states its reasoning against an already-enumerated boundary:

| Plan | Declared surface | Maps to |
|------|------------------|---------|
| 33-01, 33-02, 33-03, 33-04 | none — refusal branch / client handler / tests / one planning doc | — |
| 33-05 | four columns entering `merge.KIND_TO_FIELDS` (mapper-derived) | B3, `T-33-07` — the exact surface its own register enumerates |
| 33-06, 33-10, 33-11, 33-12, 33-13 | `op_date` operator-input boundary | B4, `T-33-16` / `T-33-17` |
| 33-07, 33-08 | operator-chosen period | B5, `T-33-16` |
| 33-09 | stored ledger text → spreadsheet host | B6, `T-33-25` |
| 33-14 | the `dated` query parameter | B7, `T-33-35` |

**Process note (WARNING, not a blocker):** `33-15-SUMMARY.md` has **no `## Threat Flags`
section at all** — the only one of the 15 that omits it. Its scope was
`.planning/*.md` documents plus an s1 rollout, so no application surface was added; the
omission is a template gap, not undeclared attack surface. Its plan's four threats
(`T-33-11`, `T-33-37`, `T-33-38`, `T-33-39`) are all verified above.

---

## Audit trail

| Item | Value |
|------|-------|
| Audited at | HEAD `30d398f`, 2026-09-04 |
| Register parsed from | 15 × `33-NN-PLAN.md` `<threat_model>` → `## STRIDE Threat Register` |
| Threats total / closed / open | 40 / 40 / 0 |
| Dispositions | 38 `mitigate`, 2 `accept`, 0 `transfer` |
| Tests re-run independently by the auditor | 612 passed, 0 failed, 10 skipped (PG parity, no `DATABASE_URL`) |
| Implementation files modified by this audit | **none** — read-only |
| Files written by this audit | this file only |
