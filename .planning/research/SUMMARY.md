# Project Research Summary

**Project:** MyOriShop — Oriflame Warehouse Inventory
**Milestone:** v5.0 Corrections, Dates & Currency
**Domain:** Append-only, dual-dialect (SQLite + PostgreSQL), UUID-synced warehouse ledger with a self-updating offline Windows client and a central server
**Researched:** 2026-09-04
**Confidence:** HIGH

## Executive Summary

This is not a greenfield milestone. All four researchers converged on the same picture: **the milestone's real weight is two genuinely unbuilt ledger features — back-dated operations (`business_date`) and reversal/сторно — and both are schema changes to the two append-only tables that every report, the sync wire and four DB triggers depend on.** Per-warehouse currency shipped 2026-08-10 (quick task `260810-2g3` + predecessor `cdcec66`, migrations 0023–0026); what remains there is a render-coverage tail with no schema work and no ordering claim. Mobile editing of product/customer cards is the smallest item, shares no files with the ledger work, and has an exact shipped precedent (`/m/batches/{id}/edit`).

**The recommended approach adds no dependencies at all.** STACK.md verified by execution that `sqlalchemy.Date` is disqualified twice over (`json.dumps(date)` raises `TypeError` on the NDJSON sync wire; `Date` binds raise `TypeError` on SQLite for string params while PostgreSQL accepts them — green on the server, red on every operator's machine). Storage is `String(10)` ISO text, matching the shipped `Batch.expiry` convention. babel is rejected (a 9.7 MiB CLDR wheel inside a signature-verified offline archive, and it would silently change all existing money output); freezegun/time-machine are rejected (global clock patching next to a known-flaky lifespan auto-sync thread; the repo already has two working `monkeypatch` idioms). The whole milestone runs on `uv sync` unchanged.

**The dominant risk is not the features — it is the fleet.** Clients self-update from GitHub Releases and run `alembic upgrade head` themselves; the s1 server is a Docker image whose code only changes on a manual `up -d --build`. `POST /api/sync/push` performs **no schema-version check**, and `merge._ledger_row` builds inserts from the *receiver's* columns — so a client that self-updates before the server is rebuilt pushes `business_date`, the server drops it silently, returns 200, and the client stamps `synced_at`, permanently excluding the row from future pushes. That is unrecoverable data loss behind a success response. Mitigation is small (~30 lines reusing the shipped `offline.schema_version_ok`) and must land **before** any schema change reaches a client. The second-order risks are all consequences of the append-only design: a new ledger column escapes the column-enumerating trigger and silently becomes mutable (migration `0026` exists solely because this already happened once), and a reversal that lands on today's business date instead of the origin's leaves the misstated period broken **forever**, because the row is immutable.

## Key Findings

### Recommended Stack

No new runtime dependencies, no new dev dependencies, no version bumps. Every capability the milestone needs already exists in the repo as a working, tested precedent; the research value is in *naming those precedents* so each phase reuses them.

**Core technologies (all locked, unchanged):**

- `String(10)` ISO text + stdlib `datetime.date` — business-date storage/parse — JSON-native for the sync wire, no bind processor on either dialect, sorts lexicographically == chronologically, matches `Batch.expiry`
- `<input type="date">` — date entry, desktop + mobile — always posts ISO regardless of browser locale; no JS date lib, no CDN (offline requirement)
- Alembic 1.18.5 (locked) — the migration — the dual-dialect trigger-rewrite pattern is written twice already (`0018`, `0026`); **do not bump to 1.19.x mid-milestone** (CHECK-constraint autogenerate becomes default → diff noise on 26 migrations)
- `app.core.format_money` / `currency_symbol` + the registered `money` Jinja filter — currency render — already shipped; the gap is adoption, not mechanism
- pytest `monkeypatch` of `utcnow_iso` (Idiom A) or a frozen-`datetime` subclass (Idiom B) — deterministic time — 20+ existing call sites

**Explicitly rejected, with evidence:** `sa.Date`, babel, py-moneyed/any FX library, arrow/pendulum/dateutil, freezegun/time-machine, `op.batch_alter_table` on the ledger tables, `date(created_at)` / `created_at::date` backfills, JS date pickers, `Intl.NumberFormat`.

### Expected Features

**Must have (table stakes):**

- Business date on every operation-writing form (6 desktop forms + 5 mobile wizards), defaulting to today, date-only, future dates rejected (D1, D5, D6)
- **Every** period-scoped surface switches in one pass (D2) — 9 call sites. A half-migrated set is strictly worse than today's consistent drift: dashboard and report would disagree for the same week with no way to tell which is right
- Technical timestamp untouched — audit trail, display order, sync selection (D3)
- Both dates visible in История and CSV when they differ (D4)
- Reversal control on each reversible История row, desktop **and** mobile, behind a confirmation that states what will be written (R1)
- Compensating row of the **same type** with inverted `qty_delta`, written through `record_operation` (R2, R7) — makes every existing SUM-based report self-correct with zero query changes
- Whole-operation atomicity: a transfer's 2 rows and a sale's N rows + cash movement reverse as one unit (R3)
- Stored, queryable link both ways; reverse-once guard; availability guard with an actionable Russian message and **zero writes** on refusal (R4, R5, R6)
- Cash-movement reversal (R8) — today a mistyped deposit has no undo whatsoever
- Storno carries the **origin's** business date (D7 / Pitfall 19) — the hard dependency that fixes the phase order
- Currency render coverage on the remaining standalone-amount surfaces, desktop + mobile (C1), plus the never-done human browser check (C5, C6)
- Mobile edit route pairs for product and customer cards, same services, inline errors, explicit Save, entry points from card and list (M1–M8)

**Should have (competitive, defer to post-validation):**

- «Сторно и повторить» — re-open the entry form pre-filled after reversing (R11); this is the actual workflow ("I typed 15 instead of 5")
- Undo link in the post-save success message (R12)
- Soft warning past a back-dating threshold, warn-but-allow (D8)
- Optional reversal reason (R13); «сторнированные» / «задним числом» filters (R14, D10)
- Entry-time currency-mixing prevention on the basket header (C4)
- Sticky date within a session (D11)

**Defer (future milestone):**

- «Остаток на дату» point-in-time stock (D9) — genuinely valuable, own replay semantics, own phase
- Mobile edit-in-wizard (M9) — highest mobile value, highest risk (wizard state; prior CR-01 scar)
- Mobile CRUD parity beyond product/customer (M11) — already deferred in PROJECT.md
- Field-level reference-data merge so client edits win (Pitfall 8) — a real sync-semantics change, out of scope

**Anti-features, unanimously:** delete/edit a posted operation; lock dates / closed periods (they protect a statutory close that does not exist here — the only observable effect would be locking the operator out of their own data); automatic cascading reversal; a dedicated `storno` operation type (every existing `WHERE type == ...` filter would miss it and *nothing* would net); FX rates/conversion; an «все валюты» option anywhere; a `reversed` boolean column.

### Architecture Approach

Everything lands inside constraints that are already load-bearing: two write choke points (`record_operation`, `record_cash_movement`), no UPDATE/DELETE on the ledger, portable ORM only, integer minor units. The design adds four nullable columns across two tables in **one** migration, two shared helpers (one for period bounds, one for the read-time COALESCE), one new service, and a template sweep.

**Major components:**

1. **Migration 00NN** — `operations.business_date`, `cash_movements.business_date`, `operations.reverses_op_id`, `cash_movements.reverses_movement_id`; native `add_column` only; tz-correct Python backfill; then DROP/CREATE both `*_no_update` triggers in **both** dialects with both `downgrade()` halves. In lockstep, same commit: `app/db.py::APPEND_ONLY_TRIGGERS` + both `IMMUTABLE_*_COLUMNS` frozensets.
2. **`business_date_bounds()` (core) + `business_date_expr(model)` (reports)** — the two sanctioned helpers. `business_date_expr` = `coalesce(model.business_date, func.substr(model.created_at, 1, 10))`, mirroring `operation_currency_clause`'s outer-join+COALESCE discipline, so rows from un-upgraded clients never vanish from a report.
3. **`app/services/reversals.py`** — per-type contract (receipt / writeoff / correction / transfer / manual cash reversible; sale, return, price_change, product_created, product_edited, auto-cash and any row with `reverses_op_id IS NOT NULL` excluded); four read-only guards evaluated before any write; every field derived from the target row, never from current state or column defaults.
4. **Push-route schema gate** — `POST /api/sync/push` compares the batch header's `schema_version` against `current_schema_version(session)` via the shipped `offline.schema_version_ok`, returning 409 with a Russian message.
5. **Template sweep + tripwire** — `| cents` → `| money(<row currency>)` on the standalone-amount surfaces, plus a test asserting the swept templates cannot regress.
6. **Mobile edit route pairs** — 4 routes + 2 templates, zero service changes, following `mobile_batches.py`'s module shape.

### Critical Pitfalls

1. **Silent field loss to an older-code server (Pitfall 4).** `_ledger_row` iterates the *receiver's* `KIND_TO_FIELDS`; an unknown field is dropped by design, the push returns 200, and the client stamps `synced_at` — the row is never pushed again. Recovery is HIGH cost and manual. **Avoid:** ship the push schema-version gate before any schema change reaches a client; write the rollout order (server first, clients second) into both schema plans; add the inverted merge test with a monkeypatched old `KIND_TO_FIELDS`.
2. **A new ledger column escapes the append-only trigger (Pitfall 1).** The triggers enumerate columns by name since 0018; an unlisted column is freely mutable and the ledger fails **open**, silently. **Avoid:** the five-artifact lockstep in one commit. `test_trigger_column_list_matches_schema` is the tripwire — do not "fix" it by editing the constant alone.
3. **A reversal lands on today instead of the origin's business date (Pitfall 19).** The misstated period never heals and the current period acquires a phantom movement; unrepairable, because the ledger is append-only. The silent version is worse: if `record_operation` gains a `business_date` kwarg defaulting to today and `reversals.py` simply does not pass it, **every** reversal is wrong by default with no error. **Avoid:** lock "reversal copies the target's `business_date` verbatim, `created_at` is today" as a decision, and test that both periods are correct afterwards.
4. **Date-only column compared against UTC-timestamp bounds (Pitfall 14).** Reusing `local_day_bounds_utc` (14 call sites) against `business_date` is a lexicographic comparison between two formats. At UTC+3 it accidentally lands on the right day and every test passes; at any UTC− offset it is off by a full day. **Avoid:** a second, parallel helper with **closed** bounds; audit all 14 call sites so none mixes both shapes in one `where()`; add a `display_tz="America/New_York"` test — it is the only test that can catch this class.
5. **Storno breaks every aggregate that is not a plain SUM (Pitfall 26).** `writeoff_report` groups by a payload-derived `reason_code` (a storno without a copied payload lands in «прочее» with a negative qty and *both* per-reason lines are wrong while the grand total is right); `stale_products` uses `MAX(created_at)`; `sales_profit_report` counts rows for `cost_unknown_count`. **Avoid:** the compensating row copies the target's `type`, `payload`, `batch_id` and frozen prices verbatim; then walk `reports.py`/`dashboard.py`/`finance_reports.py`/`customers.py` for every non-SUM aggregate and decide each explicitly.
6. **Mobile edit forms NULL what they do not render (Pitfall 17).** `update_product` is a full-replacement service and `parse_optional_cents("")` returns `None`; `update_customer` with a partial contacts dict **hard-DELETEs** the omitted contact kinds. The customer case has HIGH recovery cost (contacts are neither in the ledger nor synced). **Avoid:** render every field the shared service reads, pass `contacts=None` unless all four `CONTACT_KINDS` render, and pin it with a GET→POST-unchanged byte-identical round-trip test.

## Reconciled Disagreements

The four documents largely agree. Where they diverge, here is the resolution.

### 1. Column count for the single migration — **they agree; the disagreement is with the stale brief**

PITFALLS §21 frames this as "a disagreement worth naming", but its counterparty is the *coordinator's original framing* ("only one migration lands this milestone"), not ARCHITECTURE. Read together:

- PITFALLS 10/21: the reversal link cannot live in `Operation.payload`, because the double-reversal cap and the «сторно операции X» render must **query** it, and there is no portable JSON query across SQLite and PostgreSQL under the project's no-dialect-SQL rule. Therefore a real `reverses_op_id` column.
- ARCHITECTURE §4.1 reaches the same conclusion by an independent and *stronger* route: `CashMovement` has **no `payload` column at all** (`models.py:496-499`, column list `:518-548`). So the payload option is not merely awkward for cash — it is structurally impossible, and choosing it would force two different link mechanisms for one feature.
- ARCHITECTURE §10 then recommends landing `business_date` + `reverses_*_id` in ONE migration; PITFALLS §21 recommends exactly the same ("Recommended: combine them into one migration delivered in Phase 1") and lists it in the debt table as "**Acceptable and recommended**".

**Recommendation: four nullable columns, one migration, one trigger rewrite, one lockstep pass, delivered with the back-dating phase. Phase 2 (reversal) only starts *writing* `reverses_*_id`.** No DB-level FK on the reversal columns — bare native column in the migration, ORM `ForeignKey` only for insert ordering and PG portability (the `sale_id`/`batch_id`/`author_id` precedent), so a reversal whose target has not yet arrived renders as a dangling link instead of rolling back an entire push (Pitfall 11).

**Cost if wrong (i.e. if the columns are split across two migrations):** two server redeploys, two dual-dialect trigger DDL rewrites, two passes through the five-artifact lockstep (the exact ritual that was already botched once, producing migration `0026`), and **two separate fleet skew windows** during which a self-updated client can push to an un-rebuilt server. The price of combining is that `reverses_*_id` sits unused for one phase — a mild deviation from "schema before its readers", which is a style rule, against a rollout risk that is a data-loss rule. Both documents say to put the choice to the operator rather than defaulting silently; it is listed under Open Operator Decisions below.

### 2. Measured currency gap — **both counts are correct at different scopes; plan against ~50 renders / 29 templates**

| Source | Count | What was counted |
|---|---|---|
| ARCHITECTURE §5.1 | **103 `\| cents` renders across 42 templates**, classified into ~45/9 (Class 1, correct as-is), **~50/29 (Class 2, genuine gaps)**, ~7/4 (Class 3, catalog reference prices) | Only the Jinja `\| cents` filter, only under `app/templates` |
| PITFALLS §5 | **124 `cents`/`format_cents` occurrences across 49 files**; `money(` in exactly 1 template | Both the `\| cents` filter **and** `format_cents` Python call sites, across all of `app/` |

The two are consistent, not contradictory: 124 − 103 = 21 and 49 − 42 = 7, which is the `format_cents` Python call sites (`core.py`, `export.py`, route/service formatting) plus the one `money(` template. PITFALLS measured the total footprint; ARCHITECTURE measured the template render surface and then did the classification work.

**One number for the roadmap: ~50 renders across 29 templates must change from `| cents` to `| money(...)`.** Use 103/42 as the denominator the sweep must account for — every one of the 103 is either switched or annotated with why it is already unambiguous, and both documents independently insist the sweep be **counted, not eyeballed**, with a tripwire test so it cannot regress. Both counts are single-point measurements at commit `b4ca98c`; re-run the count at plan time rather than trusting either number blind (`rg -c '\| cents' app/templates`).

### 3. Other contradictions found

- **"Currency must precede reversal."** FEATURES (§Feature Dependencies) states currency render C1 is *required-by* reversal, because «История must render amounts with their symbol before a storno row's sum means anything». ARCHITECTURE §10 Dependency 5 explicitly says this **does not hold as stated**: the currency data model is shipped and the render is independent of reversal *logic*. **Resolution: ARCHITECTURE is right on the logic and FEATURES is right on the file scope.** The real coupling is template-level (Dependency 3): the reversal control, the currency marker and the business-date column all edit `history_view`, `history_rows.html` and `history_cards.html`. Sequence the currency plan adjacent to the reversal phase to touch those files once, but it is **not** a functional prerequisite and blocks nothing.
- **Reversal date vs. the returns precedent.** ARCHITECTURE §4.7 notes that `register_return` takes a **fresh** timestamp and does *not* inherit the origin's — which superficially argues against inheritance. It then resolves it correctly: a return is a genuinely new business event that happened today; a storno is an assertion that the origin never happened. PITFALLS 19 and FEATURES D7 reach the same answer from the vendor conventions (Business Central: "the reverse entry must have the same posting date as the original"). **No open question remains here.**
- **Backfill method.** STACK §Rule 2 recommends a portable `UPDATE ... SET business_date = substr(created_at, 1, 10)`. ARCHITECTURE §2.6 and anti-pattern #10 reject exactly that: `created_at` is UTC and reports bucket by the local day, so at Europe/Moscow a row stamped `22:30Z` currently reports as the next day and would backfill as the previous one — **every past-period number silently changes**. PITFALLS 2 offers a third option: no backfill at all, with a read-time fallback. **Recommendation: ARCHITECTURE's tz-correct Python loop** (stdlib only, WR-06-compliant, frozen `_DEFAULT_TZ` literal), **plus** `business_date_expr`'s COALESCE as the safety net for rows arriving later from un-upgraded clients. The volume is one reseller's ledger; the loop is fine. `substr(created_at,1,10)` stays the correct *read-time* fallback expression (portable, only ever applies to rows with no business date at all) — it is the *write-time* backfill that must be tz-aware. Hard success criterion either way: `sales_profit_report` for a fixed past period returns byte-identical totals before and after.
- **Backfill ordering vs. the trigger.** STACK, ARCHITECTURE and PITFALLS all state the same rule and PROJECT.md:49 already records it: `add_column` → backfill → **then** extend the trigger WHEN list. Reversed, the migration aborts against its own guard on the live server mid-upgrade. No disagreement, but it is the single most reorderable line in the migration — write the ordering as a comment inside the file.

## Risk Ranking (severity × likelihood)

| # | Risk | Severity | Likelihood | Net |
|---|---|---|---|---|
| 1 | **Unguarded push route + receiver-driven field projection** — `_ledger_row` (`app/services/merge.py:459`) builds `{column: data.get(column) for column in KIND_TO_FIELDS[kind]}` over the RECEIVER's columns, so a legitimate unknown wire field is dropped by design; `POST /api/sync/push` (`app/routes/sync.py:66-133`) has no `schema_version` gate, while the offline path does (`app/routes/offline.py:233-243`, 409 `incompatible`). Client self-updates from GitHub Releases; the server needs a manual `up -d --build`. | **CRITICAL** — permanent, unrecoverable data loss behind a 200; the row leaves the `synced_at IS NULL` push set forever | **HIGH** — the fleet's update mechanics make client-ahead-of-server the *default* ordering unless someone intervenes | **#1. Fix before any schema change ships.** ~30 lines reusing `offline.schema_version_ok` |
| 2 | **New ledger column escapes the column-enumerating trigger** — ledger fails open, silently | CRITICAL (unrecoverable: no before-image) | MEDIUM — already happened once (0024 → 0026), but the tripwire tests now exist and fire immediately | **#2.** The tripwire makes this *detectable*; the risk is someone silencing it by editing the constant alone |
| 3 | **Reversal written with the wrong business date** | HIGH — unrepairable in place; remedy is two hand-composed back-dated corrections | MEDIUM–HIGH — it is the *default* behaviour if `reversals.py` omits one kwarg | **#3.** A one-line omission with a permanent consequence |
| 4 | **`CashMovement.currency` is `nullable=False`** (`app/models.py:526`) with `default`/`server_default`, and SQLAlchemy's `default=` does not fire for an explicit `None` in the insert dict — so an old-code client pushing a cash movement sends `currency: None` → `IntegrityError` → whole-batch rollback, permanently, for that client | HIGH — a hard sync brick, not just a lost field | UNKNOWN until tested — **pre-existing** bug, not introduced by this milestone | **#4.** Its answer *determines the new columns' definitions*, so it must be settled first regardless |
| 5 | **`batch_alter_table` on the ledger tables silently drops all four triggers** | CRITICAL if undetected | LOW — the rule is documented in `tests/test_pragmas.py:28-34` and in three research docs | **#5.** Low likelihood, catastrophic tail; close it with an Alembic-built (not `create_all`) trigger-liveness test |
| 6 | **Date-only column vs UTC-timestamp bounds (Pitfall 14)** | HIGH — a whole day of revenue in the wrong bucket | MEDIUM — invisible at Europe/Moscow, so every local test passes | **#6.** Only a UTC− timezone test can catch it |
| 7 | **Reversal drives stock/batch negative (Pitfall 12)** — `record_operation` does an unconditional `quantity += qty_delta` with no non-negativity check, and `recompute_derived` happily validates a consistent set of negative numbers | HIGH — corrupts valuation and the low-stock report while the invariant test stays green | MEDIUM — reversing a receipt whose stock was sold is a natural operator action | **#7.** Non-overridable guard, not the warn-but-allow oversell shape |
| 8 | **Storno breaks non-SUM aggregates (Pitfall 26)** | MEDIUM — per-line figures wrong while the grand total looks right | MEDIUM–HIGH — three concrete instances already exist in `reports.py` | **#8.** Same-type + verbatim-payload rule, then an explicit audit |
| 9 | **Mobile edit NULLs/deletes omitted fields (Pitfall 17)** | HIGH for customer contacts (backup restore or retyping); LOW–MEDIUM for products (recoverable from the audit ops) | MEDIUM — the "smaller phone screen, fewer fields" instinct is the direct cause, and this class already shipped once (CR-01) | **#9.** One round-trip test catches the whole family |
| 10 | **Warehouse currency editable after the warehouse holds stock (Pitfall 7)** | MEDIUM — retroactively relabels history through the join; recovery is LOW (flip it back) | LOW–MEDIUM — needs a deliberate edit | **#10.** Cheap guard, mirrors the shipped delete-path stock guard |
| 11 | **Reversal FK rolls back a whole push (Pitfall 11)** | MEDIUM — sync stalls, no data loss | LOW if no DB-level FK is emitted | **#11.** Avoided entirely by the bare-column decision; verify what the migration actually emits |
| 12 | **`Product.cost_cents` (currency-less) as the sale cost fallback for non-RUB warehouses (Pitfall 6)** | MEDIUM — a rouble cost subtracted from euro revenue, undetectable on screen | MEDIUM — every pre-0025 batch has `cost_cents = NULL` | **#12.** Currency-tail scope; the existing `cost_unknown_count` caveat is the cheap honest fix |
| 13 | **Reference edits made on a client are discarded/overwritten (Pitfall 8)**, and **`CustomerContact` is not a sync kind at all (Pitfall 24)** | MEDIUM — invisible, confusing loss of operator work | HIGH that it will be *noticed* once mobile editing exists (mobile is server-only, desktop is not) | **#13.** Not a bug to fix in v5.0 — a topology to state in the UI and scope mobile customer editing around |

Risks 1, 4 and the `_ledger_row` behaviour in 1 were independently verified by the orchestrator in HEAD and are treated as established fact throughout.

## The Phase 0 Question, Sharply

Both ARCHITECTURE (§10 row 0, §12) and PITFALLS (Pitfalls 3, 4, 21) want pre-work before any schema change. Consolidated and sorted:

### MUST happen before the migration (each *determines* what the migration says)

| Item | Smallest check that settles it | Cost |
|---|---|---|
| **A. Does an explicit `None` in the insert dict beat `server_default`?** (ARCHITECTURE §3.1) The answer decides whether the four new columns can ever be NOT NULL, and exposes the `CashMovement.currency` bug. | A ~6-line test on a current-schema session: build a cash `ExchangeRecord`, `record.pop("currency")`, `_apply(session, [record])`, observe `IntegrityError` vs a landed row. Mirror of `tests/test_merge.py:662`, inverted. | ~30 min. If it raises, the fix is one line in `merge._ledger_row` (drop `None` for columns carrying a `server_default`) — one shared function, both bugs closed. |
| **B. The `POST /api/sync/push` schema-version gate.** Without it, risk #1 is live the moment a client self-updates. | Add the gate reusing `offline.schema_version_ok` + `current_schema_version`; return 409 with a Russian message; assert `sync_client` leaves `synced_at` NULL on that status. Plus the old-`KIND_TO_FIELDS` monkeypatch test proving an older receiver *rejects* rather than silently drops. | ~30 lines + 2 tests. Non-negotiable — recovery from the failure it prevents is manual hand-merge. |
| **C. Confirm the trigger tests actually prove trigger liveness.** `tests/test_pragmas.py::test_append_only_triggers_survive_author_id_schema` may be built from `create_all` rather than `alembic upgrade head`, in which case it cannot catch a batch-recreate drop. | Read `tests/conftest.py`'s `engine` fixture. If it is `create_all`, add one test that builds a DB via `alembic upgrade head` and asserts all four trigger names are live **and** that a guarded-column UPDATE aborts. | ~15 min to read; ~1 test to add. |

**These three can be the first plans of the back-dating phase rather than a separate phase** — PROJECT.md commits to 3 phases + 1 plan, and ARCHITECTURE explicitly offers this collapse ("Merge 0 into 1"). What must not happen is any of the three landing *after* the migration.

### SHOULD happen this milestone (does not gate the migration text)

- **Rollout runbook, written into the phase plan:** migrate + redeploy s1 → verify `/api/sync/pull` and a push from a current client → *only then* cut the client release tag. Wrong order is what B turns from silent to loud.
- **Backfill dry run against a copy of the s1 dump** — assert rows-updated == rows-total, and that `sales_profit_report` for a fixed past period is byte-identical before and after (ARCHITECTURE §2.6's hard success criterion).
- **Confirm the offline-bundle rejection message** tells the operator to rebuild the bundle after updating, not merely that it failed.
- **`Warehouse.currency` write-once guard** once the warehouse holds any batch/operation/cash row (Pitfall 7) — cheap, and the retroactive-relabelling window is already open in production.

### Worth a todo (not this milestone's critical path)

- Verify s1's `alembic_version` is at `0026` and what `display_tz` its `.env.production` actually sets (both `needs verification`; no shell was run by the research agents).
- Confirm alembic 1.19.1 is still the newest at planning time (`uv pip index versions alembic`) — and **do not bump** regardless.
- Historical-transfer sibling probe: confirm transfer pairs really are `seq`-adjacent in production data before relying on it (ARCH §4.5).
- Client-side reference-edit topology (Pitfall 8) and `CustomerContact` sync absence (Pitfall 24) — decide the mobile-editing scope around them; the real fix is a follow-up milestone.

## Implications for Roadmap

PROJECT.md commits to **3 phases + 1 plan**. The research supports that shape exactly, provided the two correctness constraints below are honoured.

### Phase 1: Back-dated operations (the only schema work)

**Rationale:** the milestone's single schema change, read by every period-scoped surface, and a **hard** prerequisite for reversal (a storno must inherit the origin's business date, and the *readers* must already use it, or the feature ships visibly broken). Follows the project's own "schema before its readers" rule.
**Delivers:** Phase-0 pre-work (A/B/C above) → one migration adding all four nullable columns with a tz-correct backfill and one dual-dialect trigger rewrite → `record_operation`/`record_cash_movement` kwargs → `business_date_bounds` + `business_date_expr` → the 9 period call sites switched → `_DEFAULT_ORDER` and `dashboard` signatures → date input on 6 desktop forms + 5 mobile wizards → both dates in История and CSV.
**Addresses:** D1–D6 (all P1).
**Avoids:** Pitfalls 1, 2, 3, 4, 14, 15, 16, 20, 21.
**Notes:** the `reverses_*_id` columns land here **unused but guarded**. Hard success criterion: a fixed past period's `sales_profit_report` is byte-identical across the migration.

### Phase 2: One-tap reversal (сторно)

**Rationale:** hard-dependent on Phase 1 — schema *and* readers. Shipping it first would write reversals with no business date, and there is no retrofit: the ledger is append-only.
**Delivers:** `app/services/reversals.py` with the per-type contract and four pre-write guards; business-date inheritance; `transfer_group_id` on new transfers plus the `seq±1` sibling probe (with a hard "exactly one match" requirement) for historical ones; desktop + mobile История controls with a confirmation preview showing what will be written; «сторнирована» / «сторно операции X» rendering from `reverses_op_id`; the batched per-page reversed-state probe.
**Addresses:** R1–R10, D7.
**Avoids:** Pitfalls 9, 10, 11, 12, 13, 19, 23, 26.
**Notes:** the transfer case (ARCH §4.5) is the one part that can quietly produce a wrong result — give it its own explicit success criterion. Write down the non-SUM aggregate audit as an artifact, not a feeling.

### Phase 3: Mobile editing of product and customer cards

**Rationale:** shares no files with the ledger work, so it is independent — but it renders money and writes `price_change`/`product_edited` ledger rows via `update_product` → `record_operation`, so it inherits both the business-date contract and the money-render decision. Last is correct (v1.1 UI-01 precedent). It *could* run in parallel with Phase 2 if the currency plan has landed and the file scopes are declared disjoint.
**Delivers:** 4 routes + 2 templates following `mobile_batches.py`; entry points from the mobile product card and customer list; inline field errors preserving typed values; explicit Save with visible confirmation; correct input types.
**Addresses:** M1–M8.
**Avoids:** Pitfalls 8, 17, 18, 22, 24.
**Notes:** the customer scope must be decided against Pitfall 24 — recommend scoping to the synced columns (`name`, `surname`, `consultant_number`, `address`) and leaving contacts desktop-only, said plainly in the UI.

### Plan (not a phase): Currency render coverage

**Rationale:** the feature shipped 2026-08-10; this is a finishing tail with no schema work and no ordering claim. It blocks nothing.
**Delivers:** the counted `| cents` → `| money(...)` sweep (~50 renders / 29 templates, against a denominator of 103/42) with a per-file checklist and a regression tripwire; currency scoping for `customers.spend_totals`/`purchase_history` (the single most misleading number left in the app) and a decision recorded for `writeoff_report` / `top_selling_products` / `stale_products`; the `Warehouse.currency` write-once guard; the `Product.cost_cents` non-RUB fallback decision; collapsing the five verbatim `_clean_query_currency` copies into one helper; and the **human browser check that was never done**.
**Sequencing:** place it adjacent to Phase 2 so `history_rows.html` / `history_cards.html` are edited once rather than three times, and before Phase 3 so the mobile product form ships with the final render. Do **not** parallelize it with a phase that touches the История templates.

### Phase Ordering Rationale

- **1 → 2 is a hard dependency, not a preference.** A reversal must carry the origin's `business_date`, and the reports must already read that column. Confirmed independently by FEATURES (D7), ARCHITECTURE (§4.7) and PITFALLS (19).
- **All four columns in one migration.** One trigger rewrite, one lockstep pass, one fleet skew window instead of two. This is the single biggest rollout-risk reduction available and it costs only a phase of an unused column.
- **Currency is a tail, not a gate.** The only real coupling is template-level (the История files), which is a scheduling convenience.
- **Mobile is independent but last.** It renders money and writes ledger rows, so it inherits two decisions from upstream. Building it first would mean redoing it.

### Research Flags

Phases likely needing `--research-phase` during planning:

- **Phase 2 (reversal):** the transfer sibling-resolution problem has no existing handle in the data (no group id, no shared payload key), and the non-SUM aggregate audit spans four service modules. Both are discovery work, not implementation work.

Phases with standard patterns (skip research):

- **Phase 1 (back-dating):** the migration ritual is written verbatim in `0017`/`0018`/`0024`/`0026`, the helper shape is `local_day_bounds_utc`/`operation_currency_clause`, and STACK verified the type choice by execution. The call-site list is enumerated (9 must-switch, ~14 must-not).
- **Phase 3 (mobile editing):** `mobile_batches.py` is an exact, shipped route-pair precedent; the pitfalls are known and enumerated.
- **Currency plan:** mechanical sweep against a classified list.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | Both critical claims (`sa.Date` bind failure per dialect; `json.dumps(date)` `TypeError`) were **executed** against the project's own env, not inferred. Package facts fetched from PyPI JSON with byte sizes. One MEDIUM-HIGH spot: PyPI's `/json` endpoint returned a stale alembic version contradicting the project page — recheck at plan time. |
| Features | **HIGH** for reversal and the two-date convention (primary vendor docs: Business Central, SAP, Odoo, Xero, QuickBooks, plus ERPNext as a documented counter-example, and 1C for the «красное сторно» terminology). **MEDIUM** for mobile-edit specifics (practitioner guidance, no single authority). |
| Architecture | **HIGH** — every claim is cited `path:line` from the working tree at `b4ca98c`; the three-case sync-skew analysis is pinned against existing tests. Two items self-marked `needs verification` and carried below. |
| Pitfalls | **HIGH** — almost every finding is a direct read of this repo, cross-checked against migrations 0023–0026 as a worked example of this exact class of change (including its documented near-miss). External Alembic claims corroborated in-repo by `tests/test_pragmas.py:28-34`. |

**Overall confidence: HIGH.** All four researchers independently detected and corrected the same stale premise (currency already shipped) before writing, and the orchestrator verified it in HEAD. Where the documents differ, the differences are scope-of-measurement or a disagreement with the stale brief — not conflicting evidence.

**Caveat on freshness:** every count and `path:line` is a snapshot at `b4ca98c`. No research agent ran a shell (the mandatory console skill was unavailable to them), so **nothing about the s1 server's actual state was verified** — not its `alembic_version`, not its `display_tz`, not whether the currency commits are deployed there. Re-measure counts and confirm server state at plan time.

### Consolidated `needs verification` list

Every item from all four documents, each with the smallest check that settles it. None dropped.

| # | Item | Smallest check | Owner phase |
|---|---|---|---|
| V1 | Does an explicit `None` beat `server_default` in `session.execute(insert(model), rows)`? (also exposes the `CashMovement.currency` NOT NULL bug) | 6-line inverted merge test on a current-schema session; observe `IntegrityError` vs a landed row | **Phase 0/1 — blocking** |
| V2 | What an older-**code** receiver does with an unknown wire field (`business_date`, `reverses_op_id`) | Monkeypatch `merge.KIND_TO_FIELDS` to the pre-change set, apply a batch carrying the new key, assert reject-not-drop | **Phase 0/1 — blocking** |
| V3 | Does `tests/conftest.py`'s `engine` fixture build via `create_all` (making the trigger-liveness test non-migration-proving)? | Read the fixture | **Phase 0/1 — blocking** |
| V4 | Does the backfill UPDATE trip the pre-rewrite trigger, and does it cover every row? | Run the migration against a copy of the s1 dump; assert rows-updated == rows-total | Phase 1 |
| V5 | Does any report `COUNT` operations rather than SUM signed quantities (so a storno counts as a second event)? | Grep `reports.py`/`dashboard.py`/`finance_reports.py`/`customers.py` for `func.count`, `MAX`, `+= 1`, `.limit()` over an ordered aggregate; three instances already identified in `reports.py:108,153,224` | Phase 2 |
| V6 | Are historical transfer pairs really `seq`-adjacent in production data? | `SELECT device_id, seq, qty_delta FROM operations WHERE type='transfer' ORDER BY device_id, seq` on the s1 dump; assert every row pairs with `seq±1` | Phase 2 |
| V7 | Does `writeoff_report` sum money or only quantities? | Read `reports.py:127-171` (research says quantities only — confirm before scoping) | Currency plan |
| V8 | The exact per-surface list of templates still rendering bare `format_cents` / `\| cents` | `rg -c '\| cents' app/templates` re-run at plan time against ARCHITECTURE §5.1's classification | Currency plan |
| V9 | Does a rejected mixed-currency basket preserve the typed basket on re-render? | Route-level test: POST a two-warehouse basket, assert every typed code/qty/price and the customer mode survive in the response body — the service-level test at `tests/test_sales.py:617` does not cover the render | Currency plan |
| V10 | Does the **mobile** sale wizard render `errors.basket`? | POST a two-warehouse basket to the mobile finalize endpoint; grep the response for `MIXED_CURRENCY_ERROR` | Currency plan |
| V11 | Mobile currency-switcher coverage beyond `/m/finance` and the mobile home | Per-surface read of the mobile templates | Currency plan |
| V12 | Which batch-picker services already load `Warehouse` (so a per-row currency is available)? | Per-template read of the six picker partials + their route context builders | Currency plan |
| V13 | Is the s1 PostgreSQL deployment's `alembic_version` at `0026` today? | `alembic current` on s1 | Pre-rollout |
| V14 | What `display_tz` is actually configured in the s1 container's `.env.production`? | Read the file on s1 | Pre-rollout (it parameterises the backfill) |
| V15 | Is alembic 1.19.1 still the newest at planning time? (do not bump regardless) | `uv pip index versions alembic` | Advisory |
| V16 | How a storno of a *sale* would interact with the sale's cash movement and customer spend statistics | Depends on the R20 decision below; not investigated in code | Requirements |

### Gaps to Address

- **Nothing about the server was verified.** All findings are working-tree reads. V13/V14 must be answered before the rollout runbook is executable.
- **The counts are snapshots.** Re-measure the `| cents` sweep and the migration count at plan time rather than quoting this document.
- **The R20 sale-reversal question is an operator decision, not a research finding** — three of the four documents flag it and none can resolve it.
- **Reference-data sync topology (Pitfall 8) and `CustomerContact` (Pitfall 24)** are pre-existing design facts that mobile editing makes *visible* rather than causes. v5.0 should state them honestly in the UI; changing them is a follow-up milestone.
- **The 4 known-flaky `tests/test_sync_ui.py` failures** are pre-existing (project memory) and must not be attributed to any phase of this milestone.

## Open Operator Decisions (for requirements definition)

1. **R20 — a mis-entered sale is not a return.** Routing storno-on-a-sale through `register_return` is arithmetically correct for stock and cash but pollutes the returns report, the customer's purchase statistics and the «Возврат» cash category with an event that never happened. Options: (a) storno excludes sales, operator uses Возврат — cheapest, wrong data; (b) storno on a sale routes into the existing return flow but tags the row as a correction so reports can exclude it — medium; (c) sales get a real storno writing negative `sale` ops plus a negative `return`-category cash row — most correct, most work. **All four documents default to excluding sales** (a second undo path would double-handle cash and let two caps disagree), but that is a recommendation, not a decision. Settle before writing REQ-IDs.
2. **Migration column count.** Both ARCHITECTURE and PITFALLS recommend one migration with all four columns, and both explicitly say to put the choice to the operator rather than default. The trade: one rollout risk window instead of two, against `reverses_*_id` sitting unused for one phase.
3. **Back-dating boundary.** Bounded (clamp to `[today − N days, today]`, N ≈ 45 to cover an Oriflame catalog period) versus unbounded with a «задним числом» marker on rows where `date(created_at) != business_date`. Future dates rejected either way. Reversals must be exempt from any clamp — their date is copied, not typed. Phase 1 must pick one explicitly.
4. **Product card prices have no warehouse, therefore no currency.** Label them as reference prices in `DEFAULT_CURRENCY`, or render without a symbol under a labelled field?
5. **Warehouse "last receipt date"** (`warehouses.py:100`) — technical timestamp or business date? Default is to leave it.
6. **История: a currency filter, or per-row currency markers only?**
7. **May the operator override a storno's inherited business date?** The default is settled (inherit); whether the form exposes an editable date is a UX call.
8. **Mobile customer editing scope** given `CustomerContact` does not sync at all: scope to the synced columns and say so, or take on a wire-format change (bumps `FORMAT_VERSION`, re-triggers the whole rollout problem — not small).
9. **Reversal role split.** Recommended: operators may reverse their own rows; administrators may reverse any.

## Sources

### Primary (HIGH confidence)

- Working tree at `E:\dev\myorishop`, branch `main`, commit `b4ca98c` — every `path:line` in all four research documents was read directly
- Locally **executed** against the project env (SQLAlchemy 2.0.51): SQLite `Date` bind raises `TypeError`; PostgreSQL `Date.bind_processor` is `None`; `json.dumps(date)` raises `TypeError`
- `git log -- app/core.py` + `git merge-base --is-ancestor cdcec66 HEAD` — proved the currency feature is merged
- `alembic/versions/0017,0018,0023,0024,0025,0026` — the migration ritual and its documented near-miss
- `tests/test_merge.py:644-694`, `tests/test_append_only_cursor.py:37-290`, `tests/test_pragmas.py:28-44`, `tests/test_sales.py:617-637`
- `.planning/quick/260810-2g3-.../260810-2g3-SUMMARY.md`
- PyPI JSON for babel 2.18.0 (10,196,845-byte wheel), freezegun 1.5.5, time-machine 3.5.0
- Alembic batch docs / changelog; SQLite ALTER TABLE docs
- Microsoft Business Central, Odoo, SAP FB08, QuickBooks, Dynamics 365 Finance

### Secondary (MEDIUM confidence)

- frappe/erpnext issues #11130, #47652, #30547 — the mutate-on-cancel counter-example
- Xero / Odoo lock-date documentation; SYSPRO job-receipt reversal
- 1C «красное сторно», МойСклад inline restore
- Odoo/Finale on backdating vs FIFO cost layers
- Warehouse mobile-app UX and inline-validation guidance

### Tertiary (needs validation)

- Everything about the s1 server's deployed state — no shell was run by any research agent (V13, V14)
- PyPI's `/pypi/alembic/json` returned a stale version contradicting the project page on the same day (V15)

---
*Research completed: 2026-09-04*
*Ready for roadmap: yes*
