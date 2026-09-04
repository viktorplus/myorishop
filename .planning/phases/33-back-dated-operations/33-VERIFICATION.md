---
phase: 33-back-dated-operations
verified: 2026-09-04T00:00:00Z
status: human_needed
score: 11/11 must-haves verified
overrides_applied: 0
human_verification:
  - test: "B-1 — Open /receipts, set «Дата операции» to tomorrow, click «Сохранить приход»."
    expected: "A native browser validation bubble appears and NO request leaves the page (Network tab empty)."
    why_human: "Browser-rendered constraint UI (max= + htmx 2.0.10 checkValidity) has no server-side observable. Recorded NOT RUN in 33-ROLLOUT.md § Browser checks — the Chrome tooling had no site permission for localhost."
  - test: "B-2 — /m/receipts step 4: set the header date to tomorrow, click «Сохранить приход»."
    expected: "The request DOES leave (max is inert where hx-post sits on the button), and the swapped step renders «Дата операции не может быть в будущем.» directly under the still-filled date field."
    why_human: "Same reason as B-1; the server half is test-proven (VA-14, 5 passed) but the rendered placement of the error inside the swapped mobile step is not."
  - test: "B-3 — /m/sales: set a date, add a product, return to the basket, add a second product."
    expected: "The date is still the one you set and has NOT reset to today."
    why_human: "htmx swap/round-trip persistence of a field inside the persistent wizard shell; test coverage asserts the template renders it, not that a real multi-swap session preserves it."
  - test: "B-4 — /finance and /m/finance."
    expected: "Two date fields; clicking each label focuses ITS OWN input (ids withdraw-op-date and deposit-op-date)."
    why_human: "Label/for focus association is a browser behaviour."
  - test: "B-5 — /history at a 1024 px viewport with all four filters visible."
    expected: "No horizontal scrollbar."
    why_human: "CSS layout at a specific viewport width. VERIFIED BY CODE READ THAT THE RISK IS REAL: app/static/style.css:188-193 sets display:flex with NO flex-wrap (unlike .toolbar at :72-77), and this phase added the FOURTH <select> to that bar (app/templates/partials/history_rows.html:24-82 — 4 selects). Report only; the flex-wrap fix is deliberately deferred (D-21)."
  - test: "B-6 — /history and /m/history BEFORE any back-dated operation exists."
    expected: "Every «Когда» cell and every mobile card header looks exactly as before — one line dd.mm.yyyy hh:mm, no marker."
    why_human: "Visual byte-identity of the untouched path; the template guard is verified in code (r.is_backdated false branch) but the rendered result was never observed."
  - test: "B-7 — Export sales.csv and cash_movements.csv after at least one back-dated operation exists."
    expected: "Exactly one new column, header «Внесено», LAST; column 1 non-decreasing top to bottom; Код / Цена / Сумма at their previous positions."
    why_human: "Spreadsheet-consumer contract; the writers are test-pinned but the real downloaded file was never opened."
  - test: "Live pre-update-client push against s1: from a real client still at Alembic revision 0026, with its own valid device token, POST /api/sync/push."
    expected: "HTTP 200 and the rows merge (the D-01 accept-behind branch), NOT a 409."
    why_human: "Needs a real pre-update client and a real device token; using the developer's token would push local development data into production. Recorded as gap 1 in 33-ROLLOUT.md § Executed rollout. The server-side accept-behind path IS test-proven (VA-1, 7 passed) — this verifies it against live s1."
  - test: "Run tests/test_pg_parity.py against a PostgreSQL 17 instance (CI job 'PostgreSQL portability & append-only parity')."
    expected: "The parity suite runs and passes, restoring a STANDING PostgreSQL regression guard."
    why_human: "No PostgreSQL on this machine and starting one is forbidden by CLAUDE.md. The CI job aborts before its parity step on a pre-existing unrelated failure (tests/test_launcher.py::test_parse_pending_rejects_path_traversal). The 0027 PG branch itself IS proven by execution against a throwaway copy of production on PG 17 (33-ROLLOUT.md § Executed verification 3) plus the live s1 rollout — what is missing is the standing guard, not the evidence."
---

# Phase 33: Back-Dated Operations — Verification Report

**Phase Goal:** The operator can record an operation with the date it actually happened, and every period-scoped figure in the app buckets by that date — while the technical timestamp keeps all three of its existing jobs (audit trail, display order, sync selection), and while the milestone's own schema change cannot open a silent data-loss window across the self-updating client fleet.

**Verified:** 2026-09-04
**Status:** human_needed
**Re-verification:** No — initial verification
**HEAD verified against:** `8121c65` (== `origin/main`), app version `1.100`

---

## Goal Achievement

### Observable Truths — ROADMAP Success Criteria

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | DATE-01/02 — every operation-writing form lets the operator set the date, pre-filled with today; a future date is refused in Russian, any past date accepted | ✓ VERIFIED | 14 templates render `name="op_date"` with `value="{{ form.op_date or today_iso() }}" max="{{ today_iso() }}"` (grep across `app/templates`, all 14 hits listed below). `today_iso` is a real Jinja global (`app/routes/__init__.py:242` → `core.local_today_iso`). Server refusal: `app/services/ledger.py:37-73` `parse_op_date` sets `OP_DATE_FUTURE_ERROR` / `OP_DATE_FORMAT_ERROR` and returns `None`, callers check `errors` before writing. **Ran** `pytest tests/test_business_date.py` — `test_every_write_surface_renders_op_date` passes as a 14-way parameterised table. **Ran** the 13 write-path test files: 480 passed. |
| 2 | DATE-03/04 — every period-scoped figure buckets by the business date, switched in ONE pass; `created_at` keeps audit/order/sync | ✓ VERIFIED | **Strongest evidence found, not claimed in any SUMMARY:** `local_day_bounds_utc` now has **ZERO production call sites** (`grep -rn local_day_bounds_utc app/ --include=*.py` returns only its own definition and three docstring mentions) — every period-scoped surface really did move. 9 switched predicates confirmed by read: `reports.py:119,197,258`, `finance_reports.py:40,138`, `operations.py:242` (applied to **both** `stmt` and `count_stmt` at `:245-246`), `customers.py:422`, `export.py:240`; bounds producers switched in lockstep at `routes/reports.py:111,143,208`, `routes/finance.py:89,367,401`, `routes/mobile_finance.py:82,369,400`, `routes/history.py:110`, `routes/mobile_history.py:92`, `dashboard.py:101`. `created_at` untouched: `_SORT_MAP`/`_DEFAULT_ORDER` still `Operation.created_at` (`operations.py:43-46`); `business_date` appears **0 times** in `app/services/sync.py`, `app/services/sync_client.py`, `app/routes/sync.py`, `app/services/merge.py`; `business_date` is inside both append-only trigger enumerations, so it cannot be UPDATEd at all. **Ran** 366 tests across reports/finance/customers/export/history/dashboard/warehouses — all green. |
| 3 | DATE-07/08 — a fixed past period's `sales_profit_report` is byte-identical across the migration; a NULL-business-date row still appears, bucketed by entry date | ✓ VERIFIED | `tests/test_business_date.py::test_sales_profit_byte_identical_across_migration` is **substantive, not a shell**: it builds a DB at revision `0026`, asserts `business_date` is absent from `PRAGMA table_info`, seeds a midnight-straddling row, snapshots the raw ledger, runs the **real** `alembic upgrade head`, asserts the raw ledger is byte-identical, asserts the straddler backfilled to `2026-09-01` while `created_at[:10]` is `2026-08-31`, then compares the pre-phase read (monkeypatched back to `created_at` + `local_day_bounds_utc`) against the current read. **Ran: passes.** DATE-08: `reports.py:77` `func.coalesce(model.business_date, func.substr(model.created_at,1,10))`, pinned by `test_null_business_date_still_reported` and `test_null_business_date_row_still_appears_in_all_three_reports`. Timezone-correctness re-proven on real PostgreSQL 17 against a production copy and again on live s1 (403 rows differ from the naive UTC prefix). |
| 4 | DATE-05/06 — История and CSV show both dates when they differ; the row is marked «задним числом» and filterable | ✓ VERIFIED | Desktop `partials/history_rows.html:156-158` and `:281-283` render `{{ r.business_day \| ru_date }}<br><span class="muted">задним числом · внесено {{ r.op.created_at \| local_dt }}</span>` only under `r.is_backdated`; mobile mirror at `mobile_partials/history_cards.html:40-42`. Fourth `<select name="dated">` present on **both** desktop (`history_rows.html:72-79`) and mobile (`mobile_pages/history.html:64-71`), backed by the `_DATED_FILTERS` allow-list (`operations.py:70`) applied to `stmt` **and** `count_stmt`. Empty state reads «Нет операций по выбранным фильтрам.» with `dated` in the condition (`:137`, `:271`). CSV: `export.py:148-159` and `:255` — «Когда» is the business date, «Внесено» appended LAST in both writers. |
| 5 | SYNC-10..13 — an ahead-schema push is refused in Russian, its rows stay unsynced, a pre-column client's cash movement still lands, and the triggers are proven against an `alembic upgrade head` DB | ✓ VERIFIED | `app/services/sync.py:238-275` `push_schema_ok` (asymmetric `<=`, dual `""` escape hatch); `app/routes/sync.py:56-58,136-143` raises `409` with `SCHEMA_AHEAD_ERROR` **before any DB touch** (step 4b, ahead of the `session.begin()` at `:150`) — so nothing is stamped. Client half: `sync_client.py:386-397` maps `409` → `SyncResult(status="schema_mismatch")` returning early with no pull; `:208-215` renders «Сервер ещё не обновлён — синхронизация отложена»; `main.py:111-114` backs the auto-sync loop off to `MAX_INTERVAL_SECONDS`. SYNC-12 pinned by `test_missing_column_lands_default` (lands `'RUB'`, not NULL, not IntegrityError) and `test_unknown_field_is_dropped` (asserts DROP, with the ROADMAP:320 inversion documented in the test body). SYNC-13: `tests/test_migrations.py` `alembic_engine` fixture + `test_alembic_head_triggers_match_app_db` / `test_downgrade_upgrade_roundtrip_preserves_triggers` / `test_revision_ids_are_fixed_width`. **Ran: 54 passed** in the quick gate. |

### Observable Truths — LOCKED Ordering Constraints (ROADMAP:309-317)

| # | Constraint | Status | Evidence |
|---|-----------|--------|----------|
| 6 | SYNC-10..13 land BEFORE the migration | ✓ VERIFIED | `git log --reverse 4a39a9a..HEAD`: `7c529e4 … 9a51aed` (plans 33-01…33-04, 15 commits) all precede `615be81` (migration `0027`). |
| 7 | All four ledger columns land in ONE migration | ✓ VERIFIED | `alembic/versions/0027_*.py:342-347` — four `op.add_column` calls, one revision. No second Phase-33 migration exists (`git diff --name-only` shows exactly one new file under `alembic/versions/`). |
| 8 | Internal order `add_column` → tz-correct backfill → trigger rewrite, written as a comment in the migration | ✓ VERIFIED | `0027.upgrade()` lines 319-369: the ordering rationale is a 20-line comment inside the function, then §1 add_column, §2 backfill via `_local_business_date` (`ZoneInfo(_DISPLAY_TZ)`, never `substr`), §3 trigger DDL. `downgrade()` mirrors it (guards restored first, then `op.drop_column`). `op.batch_alter_table` appears **nowhere** in the file. |
| 9 | The five-artifact lockstep is ONE commit | ✓ VERIFIED | `git show --stat 615be81` = `alembic/versions/0027_*.py` + `app/db.py` + `app/models.py` + `tests/test_append_only_cursor.py` (+ the version bump). All four new column names present in `app/db.py::APPEND_ONLY_TRIGGERS` (`:62,67,86,91`), in `app/models.py` (`:398,420,562,587`) and in both `IMMUTABLE_*` frozensets (`test_append_only_cursor.py:51,56,69,74`). |
| 10 | Rollout order: migrate+redeploy s1 → verify pull and a current-client push → only then cut the client release tag; never edit `0018`/`0026` | ✓ VERIFIED (with an open tail — see human verification) | `git diff --stat 4a39a9a..HEAD -- alembic/versions/0018*.py 0024*.py 0026*.py` returns **empty** — no applied revision was edited. Steps 1–3 executed on s1 with verbatim output in `33-ROLLOUT.md` § Executed rollout (`0026 → 0027`, coverage `1504\|1504` and `0\|0`, exactly four triggers, `/health` 200 version `1.100`, retained backup). Step 4's push half is unverified and step 5 (the tag) was correctly NOT done — the order was honoured, not violated. |
| 11 | `business_date` gets its OWN period-bounds helper; `local_day_bounds_utc` is not reused | ✓ VERIFIED | `app/core.py:134-168` `business_date_bounds` is a separate function with the closed-range contract stated in the docstring FIRST. `git diff` of `app/core.py` shows **only additive lines** around `local_day_bounds_utc` — its body is byte-unchanged (`:125-131`). |

**Score: 11/11 truths verified.**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/0027_ledger_business_date_and_reversal_links.py` | add_column ×4 → tz backfill → trigger rewrite; mirrored downgrade; `_DISPLAY_TZ` literal | ✓ VERIFIED | 395 lines. `_DISPLAY_TZ = "Europe/Moscow"` at `:103`, sourced from the MEASURED s1 value (V14), not from `app/config.py`. Both `_SQLITE_DDL` (`IS NOT`) and `_PG_DDL` (`IS DISTINCT FROM`, with the `payload::text` json cast) branches present, plus both downgrade halves. All four columns `nullable=True` with **no** `default=` and **no** `server_default=` — confirmed by read at `:342-347`. |
| `app/db.py::APPEND_ONLY_TRIGGERS` | extended with the four new columns | ✓ VERIFIED + WIRED | `:62,67,86,91`. Diffed against a real `alembic upgrade head` DB by `test_alembic_head_triggers_match_app_db` — green. |
| `app/models.py` | four mapped columns | ✓ VERIFIED + WIRED | `:398` `reverses_op_id` (ORM `ForeignKey` only, no native FK in the migration — matches the LOCKED shape), `:420` `Operation.business_date`, `:562` `reverses_movement_id`, `:587` `CashMovement.business_date`. All read by `business_date_expr` and the write services. |
| `app/core.py` | `business_date_bounds` + `local_today_iso` | ✓ VERIFIED + WIRED | `:134`, `:171`. 20 production call sites across routes/services. |
| `app/services/reports.py::business_date_expr` | shared read expression with COALESCE fallback | ✓ VERIFIED + WIRED | `:46-77`. Imported by `operations.py`, `customers.py`, `warehouses.py`, `export.py`, `finance_reports.py`. |
| `app/services/ledger.py` | `parse_op_date` + two RU constants + `business_date` kwarg | ✓ VERIFIED + WIRED | `:29-30` constants, `:37-73` parser, `:100` kwarg, `:193` `business_date or local_today_iso(...)`. Called by all 8 write services. |
| `app/services/sync.py::push_schema_ok` | asymmetric push predicate | ✓ VERIFIED + WIRED | `:238`; imported and called at `app/routes/sync.py:41,137`. |
| `app/routes/sync.py::SCHEMA_AHEAD_ERROR` | RU 409 message | ✓ VERIFIED + WIRED | `:56-58`, raised at `:138-143`. |
| `app/services/sync_client.py` | `schema_mismatch` status + formatter branch | ✓ VERIFIED + WIRED | `:396` produced, `:208-215` formatted, `app/main.py:113` consumed for the back-off. |
| 14 write-surface templates | `name="op_date"` pre-filled with today | ✓ VERIFIED + WIRED | `partials/{receipt,writeoff,sale,return,correction,transfer,withdraw,deposit}_form.html` + `mobile_pages/{receipts,writeoff,sales}.html` + `mobile_partials/{corrections_step_value,transfers_step_dest,return_confirm}.html`. All 15 route modules accept `op_date: str = Form("")` and thread it into the service (81 occurrences across `app/routes`). |
| `app/templates/partials/history_rows.html` | muted second line + fourth filter | ✓ VERIFIED | `:72-79` (filter), `:156-158` and `:281-283` (both layouts). |
| `app/templates/mobile_partials/history_cards.html` + `mobile_pages/history.html` | mobile mirror | ✓ VERIFIED | `:40-42` and `:64-71`. D-21 parity holds. |
| `app/services/export.py` | business-date row selection, «Когда» + appended «Внесено» | ✓ VERIFIED | `:139` (ORDER BY), `:148-159` and `:255` (headers), `:174,185` (values), `:240` (cash predicate). `stream_products_csv` / `stream_customers_csv` untouched. |
| `app/static/style.css` | `.field.op-date { flex-basis: 100%; }` | ✓ VERIFIED | `:505-507`. |
| `tests/test_migrations.py` | VA-5/6/7 | ✓ VERIFIED | 3 named tests present, all green. `alembic_engine`/`run_alembic` live in `tests/conftest.py` (recorded deviation, V3's real constraint — not re-pointing `conftest.py::engine` — is honoured). |
| `tests/test_business_date.py` | VA-9/10/11/12/15 | ✓ VERIFIED | All five named tests present and substantive. |
| `tests/test_sync_schema_gate.py` | VA-1/2 | ✓ VERIFIED | Present, 7 tests, green. |
| `33-ROLLOUT.md`, `33-VALIDATION.md` | executed rollout log + signed contract | ✓ VERIFIED | Both present. `33-VALIDATION.md` has `nyquist_compliant: true`, no `TBD` Task IDs, and box 7 deliberately left UNTICKED with its three open items named — an honest artifact, not a rubber stamp. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/routes/sync.py` | `sync.py::push_schema_ok` | import + call | ✓ WIRED | `:41` import, `:137` call, gate placed **before** `session.begin()` at `:150`. |
| `sync_client.py` | `partials/sync_status.html` | `format_sync_message` return | ✓ WIRED | Branch at `:208`; no template change needed (pre-existing render). |
| `0027` | `app/db.py::APPEND_ONLY_TRIGGERS` | identical DDL | ✓ WIRED | Proven at runtime by `test_alembic_head_triggers_match_app_db`, not by eyeball. |
| `routes/__init__.py` | `core.local_today_iso` | zero-arg `today_iso` Jinja global | ✓ WIRED | `:242`. Exercised by all 14 surfaces in VA-15. |
| `ledger.record_operation` | `Operation.business_date` | kwarg beside `created_at` | ✓ WIRED | `:100`, `:193`. `created_at` still `utcnow_iso()` — never replaced. |
| `operations.history_view` | `reports.business_date_expr` | same expression on `stmt` AND `count_stmt` | ✓ WIRED | `:240-246`; the `dated` filter also lands on both (`:284`+). |
| `export.py` | `reports.business_date_expr` | period predicate + both ORDER BYs | ✓ WIRED | `:139`, `:240`. |
| Mobile wizard shells | persistent `<form>` | date input above `#wizard-step` | ✓ WIRED | `mobile_pages/receipts.html:32`, `sales.html:37`, `writeoff.html:39`. |
| `routes/history.py` | `qs_parts` | `"dated"` in the pagination query string | ✓ WIRED | Filter state survives paging (pinned in `tests/test_history.py`, green). |

---

### Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Produces real data | Status |
|----------|--------------|--------|--------------------|--------|
| 14 write templates | `today_iso()` | `core.local_today_iso(settings.display_tz)` | Yes — a real `datetime.now(ZoneInfo(...))`, not a constant | ✓ FLOWING |
| 14 write routes | `op_date` Form value | real `Form("")` param → `parse_op_date` → `record_operation(business_date=...)` → DB column | Yes — end-to-end, no hardcoded pass-through | ✓ FLOWING |
| Report/dashboard/finance readers | `start_iso`/`end_iso` | `core.business_date_bounds(period[...])` matched against `business_date_expr` | Yes — no static bounds, no `return []` shortcut anywhere on the path | ✓ FLOWING |
| `history_rows.html` `r.business_day` / `r.is_backdated` | row dict keys | `operations.history_view` computes `_is_backdated(op, tz)` per row from real column + real `created_at` | Yes | ✓ FLOWING |
| `warehouse_rows.html` `w.last_receipt` | `func.max(business_date_expr(Operation))` | real aggregate (`warehouses.py:118`), rendered with `\| ru_date` (`:83`) | Yes | ✓ FLOWING |
| `customer_insights.html` `last_order_iso` | `func.max(business_date_expr(Operation))` (`customers.py:566`) | recomputed as its own aggregate, no longer `history[0]` — call site updated at `routes/customers.py:203` | Yes | ✓ FLOWING |
| CSV writers | `op.business_date or op.created_at[:10]` | mirrors the SQL COALESCE the row set was selected by | Yes | ✓ FLOWING |

No HOLLOW, ORPHANED or DISCONNECTED artifact found. One deliberate non-consumer: `reverses_op_id` / `reverses_movement_id` ship **unused but trigger-guarded** by design (Phase 34 starts writing them) — this is the LOCKED constraint, not orphaning.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase quick gate (triggers + migrations + business date) | `uv run pytest tests/test_append_only_cursor.py tests/test_migrations.py tests/test_business_date.py -q` | `54 passed` in 17.26 s | ✓ PASS |
| Every period reader + sync gate + merge | `uv run pytest tests/test_reports.py tests/test_finance_reports.py tests/test_customers.py tests/test_export.py tests/test_history.py tests/test_mobile_history.py tests/test_sync_schema_gate.py tests/test_merge.py tests/test_warehouses.py tests/test_dashboard.py -q` | `366 passed` in 111.8 s | ✓ PASS |
| Every write surface, desktop + mobile | `uv run pytest tests/test_{receipts,writeoffs,sales,returns,corrections,transfers,finance,mobile_*}.py -q` | `480 passed` in 157.4 s | ✓ PASS |
| Debt markers in the 96 files this phase touched | `grep -nE "TBD\|FIXME\|XXX" <changed files>` | no matches | ✓ PASS |
| `local_day_bounds_utc` fully retired from production | `grep -rn local_day_bounds_utc app/ --include=*.py` | definition + 3 docstring mentions only; **0 call sites** | ✓ PASS |
| `business_date` absent from the sync layer | `grep -c business_date app/services/sync.py app/services/sync_client.py app/routes/sync.py app/services/merge.py` | `0 0 0 0` | ✓ PASS |
| Applied migrations never edited | `git diff --stat 4a39a9a..HEAD -- alembic/versions/0018* 0024* 0026*` | empty | ✓ PASS |
| Five-artifact lockstep is one commit | `git show --stat 615be81` | 5 files, one commit | ✓ PASS |
| Full local suite | not re-run here (455 s); reported by the phase as `4 failed, 1683 passed, 14 skipped` | the 4 failures are all `tests/test_sync_ui.py`, pre-existing since ≤ `49a53d2`, green on Linux CI | ? SKIP (not attributable to this phase) |
| PostgreSQL parity suite | `uv run pytest tests/test_pg_parity.py` | **не запускал** — no PG on this machine, starting one is forbidden by CLAUDE.md | ? SKIP → human verification |

### Probe Execution

Not applicable — this project has no `scripts/*/tests/probe-*.sh` probes and none is declared by any Phase 33 plan. `find scripts -path '*tests/probe-*'` returns nothing.

---

### Requirements Coverage

| Requirement | Source plan(s) | Status | Evidence |
|-------------|----------------|--------|----------|
| SYNC-10 | 33-01, 33-02, 33-04, 33-15 | ✓ SATISFIED | `push_schema_ok` + 409 + `SCHEMA_AHEAD_ERROR` + client `schema_mismatch` surface. VA-1 green. |
| SYNC-11 | 33-01, 33-02, 33-15 | ✓ SATISFIED | Gate raises before `session.begin()`; `synced_at` stamped only after 2xx (`sync_client.py:404`). VA-2 green. |
| SYNC-12 | 33-03, 33-05, 33-15 | ✓ SATISFIED | `test_missing_column_lands_default` + `test_unknown_field_is_dropped`; all four new columns nullable with no default of any kind. |
| SYNC-13 | 33-03, 33-04, 33-05, 33-15 | ✓ SATISFIED | `alembic_engine` fixture + VA-5/6/7 green; triggers diffed against a real `upgrade head` DB. |
| DATE-01 | 33-06, 33-10, 33-11, 33-12, 33-13, 33-15 | ✓ SATISFIED | 14 surfaces, VA-15 as a runnable 14-way contract. |
| DATE-02 | 33-06, 33-10..33-13, 33-15 | ✓ SATISFIED | `parse_op_date` + two RU constants; VA-14 green; zero writes on refusal. |
| DATE-03 | 33-05..33-09, 33-15 | ✓ SATISFIED | 9 predicates + all bounds producers; `local_day_bounds_utc` has no production caller left. |
| DATE-04 | 33-05, 33-06, 33-08, 33-15 | ✓ SATISFIED | `_SORT_MAP`/`_DEFAULT_ORDER` unchanged (VA-17); `business_date` absent from sync (VA-11); the column is trigger-immutable. |
| DATE-05 | 33-09, 33-14, 33-15 | ✓ SATISFIED | Second line in История (desktop + mobile) + «Внесено» in both CSV writers. |
| DATE-06 | 33-14, 33-15 | ✓ SATISFIED (one visual check pending) | Marker + fourth `<select name="dated">` on both surfaces. B-5 (`.filter-bar` overflow at 1024 px) NOT RUN — see human verification. |
| DATE-07 | 33-04, 33-05, 33-07, 33-15 | ✓ SATISFIED | VA-9 byte-identity across the real migration; tz-correct backfill re-proven on real PG 17 with production data. |
| DATE-08 | 33-05..33-07, 33-09, 33-15 | ✓ SATISFIED | Read-time COALESCE, pinned by VA-12 and by the CSV fallback that mirrors the SQL predicate. |

**Orphaned requirements: none.** `grep "Phase 33" .planning/REQUIREMENTS.md` maps exactly these 12 IDs to this phase, and every one appears in at least one plan's `requirements` frontmatter.

---

### Locked Decisions (33-CONTEXT.md D-01…D-25) — spot audit

| Decision | Status | Evidence |
|----------|--------|----------|
| D-01/D-02/D-03/D-04 (asymmetric gate, own sibling predicate, dual `""` hatch, lexicographic invariant bought with a test) | ✓ HONOURED | `sync.py:238-275`; `offline.schema_version_ok` neither imported nor modified; `test_revision_ids_are_fixed_width` present. |
| D-09 (back-off to 3600 s) | ✓ HONOURED | `main.py:100-114`, reads `last_status` after the tick, self-clears. |
| D-11 (persistent shell for 3 mobile wizards, final step for the 2 shell-less ones) | ✓ HONOURED | `mobile_pages/{receipts,sales,writeoff}.html` above `#wizard-step`; `mobile_partials/{corrections_step_value,transfers_step_dest}.html` on the final step. |
| D-13 (`max="{{ today_iso() }}"`) | ✓ HONOURED | Present on all 14 inputs. |
| D-16 (14 write surfaces, cash included) | ✓ HONOURED | Exactly 14 templates carry `name="op_date"`. |
| D-22 (`_SORT_MAP`/`_DEFAULT_ORDER` NOT changed) | ✓ HONOURED | `operations.py:43-46` unchanged, with an explicit DO-NOT comment. |
| D-23 (CSV «Когда» becomes business date, «Внесено» appended LAST) | ✓ HONOURED | `export.py:148-159`, `:255`; positions 1..N unshifted. |
| D-24 (three borderline readers switched) | ✓ HONOURED | `warehouses.py:118` + `warehouse_rows.html:83` `\| ru_date` with the misleading comment rewritten; `receipts.py:158,240` batch name uses the business date; `customers.py:566` `last_order_date` recomputed as `MAX(...)` with its call site updated; return labels at `routes/returns.py:66` and `routes/mobile_returns.py:69`. |
| D-25 (`stale_products` STAYS on `created_at`; the `reports_products.html` filter edit is CANCELLED) | ✓ HONOURED | `reports.py:281-288` keeps `func.max(Operation.created_at)` with a DO-NOT-SWITCH comment; `reports_products.html:32` still `\| local_dt`, i.e. the cancelled edit was correctly not made. **This narrows ROADMAP SC-2's «stock report» wording; `/reports/stock` (`routes/reports.py:163`) is not period-scoped at all, so nothing there was left unswitched.** |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/core.py` | 181-191 | Stale factual comment shipped in production code: `local_today_iso`'s docstring says «**four** sites still inline …» and lists `app/services/receipts.py:209` and `app/services/customers.py:443/465`. Measured at HEAD: there are **three** (`receipts.py` was converted by this phase to `:158 local_today_iso(...)`) and the customers sites are at `:450`/`:474`. | ⚠️ Warning | Misleads the next author who tries to converge them. `33-ROLLOUT.md` § Backlog item 6 records the correct numbers, but the shipped docstring was never updated to match. Cosmetic — no behavioural effect. |
| `app/static/style.css` | 188-193 | `.filter-bar` is `display:flex` with **no** `flex-wrap`, and this phase added the 4th `<select>` to it | ⚠️ Warning | Possible horizontal overflow at 1024 px. Unmeasured (B-5 NOT RUN). Deliberately deferred by D-21; recorded, not fixed. Confirmed by direct code read, not taken on trust. |
| — | — | `TBD` / `FIXME` / `XXX` in the 96 files this phase touched | ✓ none | Debt-marker gate passes. |
| — | — | `TODO` / `HACK` / `PLACEHOLDER` | ✓ none (one hit is test data, `test_merge.py:596 code="HACKED"`) | Clean. |
| `alembic/versions/0024_cash_movement_currency.py` | 50-52 | `op.batch_alter_table` in `downgrade()` destroys both `cash_movements` triggers on SQLite | ℹ️ Info — pre-existing, deliberately unfixed | An applied migration is historical fact (LOCKED constraint 5). Named in `0027`'s docstring, reproduced in 33-03, and now permanently pinned by `test_downgrade_upgrade_roundtrip_preserves_triggers`. **Correct handling — not a Phase 33 defect.** |

---

### Human Verification Required

Nine items. Seven are the browser checks the phase itself recorded as NOT RUN (a Chrome-extension site-permission blocker, proven not to be an app fault — the isolated instance answered `200` on `curl` and `alembic upgrade head` built its DB cleanly through `0001 → 0027`); the other two are the live-server push and the standing PostgreSQL guard. Full instructions are in the frontmatter `human_verification:` block and, verbatim in Russian, in `33-ROLLOUT.md` § Browser checks.

1. **B-1** — native validation bubble on a future date, desktop `/receipts`.
2. **B-2** — server guard renders in the swapped mobile step, `/m/receipts`.
3. **B-3** — the typed date survives the mobile sale basket round-trip.
4. **B-4** — two cash date fields, each label focuses its own input.
5. **B-5** — `.filter-bar` overflow at 1024 px. **Highest-value item:** the risk is code-confirmed (no `flex-wrap`, four selects), only the outcome is unmeasured.
6. **B-6** — nothing changed visually before any back-dating exists.
7. **B-7** — the CSV column contract in a real downloaded file.
8. **Live pre-update-client push against s1** — needs a real `0026` client with its own device token.
9. **PostgreSQL parity suite** — needs the CI job unblocked (the pre-existing `test_launcher.py` failure aborts it before the parity step).

None of these is a code gap. Items 1–7 and 9 verify *observations* the automated suite structurally cannot make; item 8 verifies a *live-fleet* behaviour whose code path is already test-proven.

---

### Gaps Summary

**No blocking gaps.** Every one of the 11 must-have truths is verified against the codebase, not against SUMMARY prose:

- The phase's central risk — that «all 15 plans completed» could mean fifteen files touched and no behaviour changed — is falsified by executed evidence: `local_day_bounds_utc` has **zero** remaining production call sites, so the DATE-03 sweep is provably complete rather than partially applied; `business_date` appears **zero** times in the entire sync layer, so DATE-04's «never moves in the sync queue» is structural rather than asserted; and VA-9 is a real before/after migration comparison, not a tautology.
- The three disclosed open items were assessed on their merits, not accepted on the phase's say-so:
  - **Browser checks B-1…B-7 NOT RUN** — genuinely open, and B-5 is a real unmeasured risk this phase created (fourth select into a non-wrapping flex bar). None of the seven can invalidate a code truth; all seven are routed to human verification.
  - **The live pre-update-client push is unverified** — the *code* path (accept-behind, `push_schema_ok` returning True for `client < server`) is test-proven by VA-1; what is missing is the live confirmation. Correctly recorded as PENDING rather than assumed.
  - **The client release tag is uncut** — this is the *correct* state, not an omission: LOCKED constraint 5 places the tag strictly after step 4 passes, and step 4 is half-verified. Cutting it would have been the violation.
- Two ⚠️ warnings worth carrying forward but not blocking: a stale four-vs-three docstring in `app/core.py:181-191`, and the missing `.filter-bar` `flex-wrap` (deferred by decision, measurement owed).
- The phase's own artifacts are unusually honest — `33-VALIDATION.md` leaves sign-off box 7 deliberately unticked with a written reason, and `33-ROLLOUT.md` records «не запускал» for the parity suite rather than dressing the throwaway-copy proof up as a CI pass. Nothing in either file was found to overclaim when checked against code.

**Status is `human_needed`, not `passed`, solely because the human verification list is non-empty.** The goal — «the operator can record an operation with the date it actually happened, and every period-scoped figure buckets by that date» — is achieved in the codebase and live on s1 at version `1.100`.

---

_Verified: 2026-09-04 at HEAD `8121c65`_
_Verifier: Claude (gsd-verifier), goal-backward, FORCE stance_
