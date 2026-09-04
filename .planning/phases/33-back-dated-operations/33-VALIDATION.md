---
phase: 33
slug: back-dated-operations
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-09-04
signed_off: 2026-09-04
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `33-RESEARCH.md` § `## Validation Architecture` (rows VA-1 … VA-17).
> Every command below was authored against executed evidence, not assumed.
> **Signed off by plan `33-15` Task 4 on 2026-09-04**, at HEAD `d6be4f5`. Every `Status` cell below
> is the result of running that row's own command on that commit — none is inferred.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 (`pyproject.toml:24`, pinned `pytest==9.1.*`) |
| **Config file** | `pyproject.toml:28-30` — `[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["."]`. No `pytest.ini` / `setup.cfg` / `tox.ini` exists |
| **Quick run command** | `uv run pytest tests/test_append_only_cursor.py tests/test_migrations.py tests/test_business_date.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Measured runtime** | quick run **16.4 s** (54 passed, measured 2026-09-04) · full suite **455 s** (measured 2026-09-04) |
| **PostgreSQL parity** | `uv run pytest tests/test_pg_parity.py -q` with a PostgreSQL connection env var; skipped when unset. Existing harness; CI runs `postgres:17` (`.planning/ROADMAP.md:141`) |

> **Known pre-existing red — do NOT attribute to this phase.** Four `tests/test_sync_ui.py`
> tests fail deterministically in a local full-suite run (the lifespan auto-sync thread holds
> `sync_client._run_lock`). Pre-existing since ≤ `49a53d2`. Do not "fix" them here.
> **Confirmed 2026-09-04:** all four **pass on Linux CI** (run `33887231153`), so this is a
> Windows-local test-isolation race, not a product defect. Recorded in `33-ROLLOUT.md`
> § Backlog item 5.

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/test_append_only_cursor.py tests/test_migrations.py tests/test_business_date.py -x -q`
- **After every plan wave:** `uv run pytest -q` (full suite), accepting the 4 known-red `test_sync_ui.py` cases
- **Before `/gsd-verify-work`:** full suite green (modulo the 4 known) **plus** one PostgreSQL run of `tests/test_pg_parity.py` — V4's PostgreSQL half could not be exercised locally (no PG instance; starting one is forbidden by CLAUDE.md)
- **Max feedback latency:** 30 seconds — **measured at 16.4 s** on 2026-09-04

> **Executed status of the pre-gate, stated precisely (2026-09-04).** The full suite ran with exactly
> the 4 known-red failures. **`tests/test_pg_parity.py` did NOT run** — a pre-existing, unrelated
> Linux-only failure in the preceding CI step (`tests/test_launcher.py::test_parse_pending_rejects_path_traversal`)
> aborts the parity job before its parity step is reached. The PostgreSQL half of V4 was instead
> proven by running `alembic upgrade head` against a **throwaway copy of the live production
> database** on real PostgreSQL 17 — stronger evidence for `0027` specifically, but **not** a standing
> regression guard. Both facts are recorded in full in `33-ROLLOUT.md` § Executed verification.
> The parity suite therefore remains owed: `33-ROLLOUT.md` § Backlog item 4.

---

## Per-Task Verification Map

Task IDs are assigned by `/gsd-plan-phase`'s planner (§8) and backfilled into this table by the
executor. The VA-ID is the stable key; the Task ID column is the join. **Backfilled 2026-09-04 by
plan `33-15` Task 4**, by grepping each plan for its VA references — not from the mapping `33-15`
predicted. Where the two disagree, the plans won; the corrections are listed under the table.

| VA | Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|----|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| VA-1 | Task 1 (RED tests), Task 2 (`push_schema_ok`), Task 3 (409 gate) | `33-01` | 1 | SYNC-10 | T-33-01, T-33-02 | Client-ahead push refused `409` + RU constant; client-behind push accepted `200` and merged | integration | `uv run pytest tests/test_sync_schema_gate.py -x -q` | ✅ exists | ✅ green (7 passed, 2026-09-04) |
| VA-2 | Task 1 (RED test), Task 3 (409 gate) | `33-01` | 1 | SYNC-11 | T-33-04 | After a `409`, every row in the batch keeps `synced_at IS NULL` and `sync_state.last_sync_at` did not advance | integration | `uv run pytest tests/test_sync_schema_gate.py::test_refused_push_leaves_rows_unsynced -x` | ✅ exists | ✅ green (1 passed, 2026-09-04) |
| VA-3 | Task 3 | `33-03` | 1 | SYNC-12 | — | `cash_movement` with `currency` popped merges and lands `'RUB'`; with `business_date` popped merges and lands `NULL` | unit | `uv run pytest tests/test_merge.py -k missing_column -x` | ✅ exists | ✅ green (1 passed, 38 deselected, 2026-09-04) |
| VA-4 | Task 3 | `33-03` | 1 | SYNC-12 | T-33-01 | A record carrying an **unknown** field merges, the field is dropped, success is reported — the exact loss SYNC-10 gates. **Assert DROP, not reject** (ROADMAP:320 states the assertion backwards) | unit | `uv run pytest tests/test_merge.py -k unknown_field_is_dropped -x` | ✅ exists | ✅ green (1 passed, 38 deselected, 2026-09-04) |
| VA-5 | Task 2 | `33-03` (tripwire), enforced by `33-05` Tasks 1–3 | 2 | SYNC-13 | T-33-07 | The four triggers on an `alembic upgrade head` DB are whitespace-normalised-identical to `app/db.py::APPEND_ONLY_TRIGGERS` | integration | `uv run pytest tests/test_migrations.py::test_alembic_head_triggers_match_app_db -x` | ✅ exists | ✅ green (1 passed, 2026-09-04) |
| VA-6 | Task 2 | `33-03` (tripwire), enforced by `33-05` Task 2 | 2 | SYNC-13 | T-33-07, T-33-08 | `upgrade head → downgrade -1 → upgrade head` leaves exactly 4 triggers and the head column set | integration | `uv run pytest tests/test_migrations.py::test_downgrade_upgrade_roundtrip_preserves_triggers -x` | ✅ exists | ✅ green (1 passed, 2026-09-04) |
| VA-7 | Task 2 | `33-03` | 1 | SYNC-10 (D-04) | T-33-09 | Every `revision` / `down_revision` literal under `alembic/versions/` matches `^\d{4}$` | unit | `uv run pytest tests/test_migrations.py::test_revision_ids_are_fixed_width -x` | ✅ exists | ✅ green (1 passed, 2026-09-04) |
| VA-8 | Task 1 (both frozensets), proven in Task 3 (the lockstep commit) | `33-05` | 2 | SYNC-13 | T-33-07 | `test_trigger_column_list_matches_schema` + `test_declared_constants_match_trigger_ddl` green with the 4 new columns in **both** frozensets | unit | `uv run pytest tests/test_append_only_cursor.py -x -q` | ✅ exists (`:246`, `:261`) — constants extended at `:40-73` | ✅ green (16 passed, 2026-09-04) |
| VA-9 | Task 3 | `33-07` | 2 | DATE-07 | T-33-14 | A fixed past period's `sales_profit_report` is **byte-identical** before and after the migration (full dict, not just totals) | integration | `uv run pytest tests/test_business_date.py::test_sales_profit_byte_identical_across_migration -x` | ✅ exists | ✅ green (1 passed, 2026-09-04) |
| VA-10 | Task 1 (`business_date_bounds` half) | `33-06` | 2 | DATE-07 (Pitfall 14) | T-33-14 (the register names VA-9; VA-10 is the tz half of the same mitigation) | Same fixtures bucket correctly at `display_tz="America/New_York"` **and** `"UTC"`; the backfill's tz-correct result differs from the naive `substr` cut on the straddling fixtures | unit | `uv run pytest tests/test_business_date.py -k timezone -x` | ✅ exists | ✅ green (3 passed, 32 deselected, 2026-09-04) |
| VA-10 (2nd half) | Task 3 (migration `0027` loaded by path at +/−/0 offsets) | `33-07` | 2 | DATE-07 (Pitfall 14) | T-33-14 | as above, run against the real migration's backfill logic | unit | `uv run pytest tests/test_business_date.py -k timezone -x` | ✅ exists | ✅ green (same 3 passed, 2026-09-04) |
| VA-11 | Task 1 | `33-06` | 3 | DATE-04 (Pitfall 16) | T-33-19 | `business_date` appears in **zero** of `app/services/sync.py`, `app/services/sync_client.py`, `app/routes/sync.py` | unit | `uv run pytest tests/test_business_date.py::test_business_date_absent_from_sync_layer -x` | ✅ exists | ✅ green (1 passed, 2026-09-04) |
| VA-12 | Task 3 (`33-07`); foundation laid by `33-06` Task 3 | `33-07`, `33-06` | 3 | DATE-08 | T-33-21 | A row with `business_date IS NULL` still appears in every period report, bucketed by `substr(created_at,1,10)` via the read-time COALESCE | unit | `uv run pytest tests/test_business_date.py -k null_business_date -x` | ✅ exists | ✅ green (2 passed, 33 deselected, 2026-09-04) |
| VA-13 | `33-07` Tasks 1–2 · `33-08` Tasks 1–2 · `33-09` Task 3 | `33-07`, `33-08`, `33-09` | 3 | DATE-03 | T-33-20, T-33-22, T-33-26, T-33-27 | Each of the 9 switched predicates returns the back-dated row under the business-date period and **not** under the entry-date period | unit | `uv run pytest tests/test_reports.py tests/test_finance_reports.py tests/test_customers.py tests/test_export.py tests/test_history.py -q` | ✅ exists | ✅ green (236 passed, 2026-09-04) |
| VA-14 | `33-06` Task 3 (`parse_op_date`) · `33-10` Task 1 · `33-11` Task 1 · `33-12` Task 1 · `33-13` Task 1 | `33-06`, `33-10`, `33-11`, `33-12`, `33-13` | 3 | DATE-02 | T-33-16, T-33-17, T-33-18 | Future date → `OP_DATE_FUTURE_ERROR`; malformed → `OP_DATE_FORMAT_ERROR`; both under `errors["op_date"]`; **zero writes** on refusal | unit | `uv run pytest tests/test_receipts.py -k op_date -x` | ✅ exists | ✅ green (5 passed, 59 deselected, 2026-09-04) |
| VA-15 | Task 3 | `33-13` | 3 | DATE-01 | T-33-34 | Every one of the 14 D-16 write surfaces renders a `name="op_date"` input pre-filled with today | integration | `uv run pytest tests/test_business_date.py::test_every_write_surface_renders_op_date -x` | ✅ exists | ✅ green (14 passed — the 14-way parameterised table, 2026-09-04) |
| VA-16 | **Task 2 (desktop half) AND Task 3 (mobile half)** — satisfied only when BOTH pass | `33-14` | 4 | DATE-05, DATE-06 | T-33-36, T-33-35, T-33-22 | История renders one line when the dates match, two lines + «задним числом» when they differ — desktop **and** mobile | integration | `uv run pytest tests/test_history.py -k dated -x` **and** `uv run pytest tests/test_mobile_history.py -k dated -x` | ✅ exists | ✅ green — desktop 15 passed / 25 deselected, mobile 4 passed / 8 deselected (2026-09-04) |
| VA-17 | Task 1 | `33-08` | 3 | DATE-04 (D-22) | T-33-23 | `_SORT_MAP` and `_DEFAULT_ORDER` unchanged; a just-entered back-dated row is still first in every "recent N" feed | unit | `uv run pytest tests/test_history.py::test_recent_feeds_still_order_by_created_at -x` | ✅ exists | ✅ green (1 passed, 2026-09-04) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**On the `Threat Ref` column.** Where a plan's `<threat_model>` names the VA outright, that is the
reference given. Where no threat names the VA explicitly, the cell lists the threat(s) the *carrying
task* mitigates and which the VA is the evidence for — the two cases where this needed saying are
marked inline. `—` means the carrying plan's register genuinely carries no threat for that row
(VA-3, a library-behaviour pin, is the only one).

### Corrections to the mapping `33-15` predicted

Plan `33-15` Task 4 supplied an expected mapping «to be CONFIRMED by grepping the plans rather than
trusted». Grepping found four divergences. In each, the plans won.

1. **VA-14 spans five plans, not two.** `33-15` predicted `33-06` Task 3 and `33-10` Task 1. The
   `parse_op_date` / `op_date` service-layer tests are extended by **`33-11` Task 1**
   (`33-11-PLAN.md:116`), **`33-12` Task 1** (`33-12-PLAN.md:108`) and **`33-13` Task 1**
   (`33-13-PLAN.md:109`) as well. Every write-path family carries its own half of VA-14.
2. **VA-13 does NOT reach `33-14`.** `33-15` predicted `33-07` Tasks 1-2, `33-08`, `33-09` **and
   `33-14`**. `33-14-PLAN.md` contains no VA-13 reference; what it carries is VA-16. VA-13's
   `tests/test_history.py` half is `33-08` Task 1 (`33-08-PLAN.md:124`), and its customers half is
   `33-08` Task 2 (`:194`). Corrected to `33-07` T1–2 · `33-08` T1–2 · `33-09` T3.
3. **VA-12 has a foundation task `33-15` did not name.** `33-07` Task 3 owns it
   (`test_null_business_date_still_reported`), but `33-06` Task 3 laid the foundation
   (`test_merge_inserted_row_keeps_null_business_date`, `33-06-PLAN.md:373`). Both are listed.
4. **VA-5 / VA-6 have a two-plan life.** `33-03` Task 2 *wrote* them as tripwires against HEAD;
   `33-05` is the plan they were written to catch, and `33-05-PLAN.md:281-284` re-runs them as its
   own gate. The Plan cell names both, because reading only `33-03` hides why they exist.

### One correction to a row's own Automated Command

**VA-16's command was incomplete as written.** The row shipped with
`uv run pytest tests/test_history.py -k dated -x` only, but `33-14-PLAN.md:324-326` states outright
that «VA-16 is satisfied only when BOTH halves pass; neither task closes it alone». A desktop-only
command can go green while the mobile mirror is broken, which is precisely the divergence D-21
forbids. The command cell now names both halves. Both were run; both are green.

*Wave numbers above are the researcher's dependency reading, not a planner commitment — the
planner owns wave assignment and may compact them, subject to the LOCKED ordering constraint
that SYNC-10..13 land before the migration.*

---

## Wave 0 Requirements

Verified on disk at HEAD `d6be4f5`, 2026-09-04 — each file was stat-ed and each file's tests were run.

- [x] `tests/test_migrations.py` — **new file.** `alembic_engine` fixture (fresh `tmp_path` SQLite DB built by invoking Alembic programmatically) + VA-5, VA-6, VA-7. **Must NOT re-point `tests/conftest.py::engine`** — 14 fixtures depend on it transitively (V3). **Exists (133 lines); VA-5/6/7 all green.** *Recorded deviation:* `alembic_engine` and `run_alembic` live in `tests/conftest.py` (`:103` and `:90`), not inside `tests/test_migrations.py` as this document originally suggested — `33-07`'s VA-9 needs the same fixture and a cross-test-file import would require making `tests/` an importable package. The V3 constraint this requirement actually protects (do not re-point `conftest.py::engine`) is honoured exactly.
- [x] `tests/test_business_date.py` — **new file.** VA-9, VA-10, VA-11, VA-12, VA-15. **Exists (811 lines); all green.** *Recorded deviation:* VA-17 lives in `tests/test_history.py` instead, per `33-08-PLAN.md:140-143` — it asserts `history_view`/feed ordering, and the repo convention is that a test lives beside the module it pins. `33-CONTEXT.md` § Claude's Discretion allows this.
- [x] `tests/test_sync_schema_gate.py` — **new file.** VA-1, VA-2. Must inject `schema_version` explicitly or monkeypatch `current_schema_version` — the whole suite builds via `create_all`, so `current_schema_version` returns `""` on both sides and D-03's escape hatch would otherwise short-circuit the gate. **Exists (218 lines); 7 tests green.**
- [x] No framework install needed — pytest 9.1.1 is already pinned and configured. **Confirmed: `pyproject.toml` was untouched by every plan in this phase (T-33-SC, accepted and vacuous).**

---

## Manual-Only Verifications

Results column added and filled by plan `33-15` on 2026-09-04. **Nothing here is inferred from
source.** Full detail for every row is in `33-ROLLOUT.md`.

| Behavior | Requirement | Why Manual | Test Instructions | Result (2026-09-04) |
|----------|-------------|------------|-------------------|---------------------|
| Native validation bubble on a `max`-violating date submit | DATE-02 (D-13) | Browser-rendered constraint UI has no server-side observable. Research settled the htmx half from vendored source (htmx 2.0.10 uses `checkValidity()`, `reportValidityOfForms` defaults false and is never overridden; the 8 desktop forms carry `hx-post` on the `<form>` with a native submit button so the **browser** validates first) — what remains is confirming the bubble actually appears. | Open `/receipts`, set the date input to tomorrow, click «Сохранить приход». Expect a native validation bubble and no request. Then repeat on a mobile shell wizard (приход) where `hx-post` sits on the button — expect `max` to be inert and the server's `OP_DATE_FUTURE_ERROR` to render. | **NOT RUN** (B-1, B-2). Browser tooling has no site permission for `localhost`/`127.0.0.1`; the app itself answered `200` on `curl`. `33-ROLLOUT.md` § Browser checks |
| `.filter-bar` overflow with the fourth `<select>` | DATE-06 (D-20) | CSS layout at a specific viewport width. `app/static/style.css:188-193` sets no `flex-wrap` (unlike `.toolbar` at `:72-77`). | Open `/history` at 1024 px wide. Look for a horizontal scrollbar. If present, this is a deferred one-line fix touching every `.filter-bar` page — record it, do not fix it inside this phase. | **NOT RUN** (B-5) — and therefore **still open**. The fourth `<select>` shipped in `33-14`; `flex-wrap` is still absent. No fix made. `33-ROLLOUT.md` § Backlog item 8 |
| PostgreSQL half of the trigger/backfill behaviour (V4) | SYNC-13, DATE-07 | No PostgreSQL instance on the dev machine; starting one is forbidden by CLAUDE.md. | CI: `uv run pytest tests/test_pg_parity.py -q` against the `postgres:17` service. Required before the phase gate. | **Parity suite «не запускал»** — the CI job aborts on a pre-existing unrelated failure before reaching the parity step. **But the `0027` PostgreSQL branch IS proven**: `alembic upgrade head` ran clean against a throwaway copy of the live production database on real PostgreSQL 17, with post-migration coverage, trigger and tz-correctness SQL. `33-ROLLOUT.md` § Executed verification 2–3 |
| **V13** — s1's `alembic_version` is `0026` | SYNC-10 (pre-rollout) | Live server state. | On s1: `docker compose -f docker-compose.prod.yml exec ori-app uv run alembic current` | **MEASURED** — `0026 (head)`, plan `33-04`. `33-ROLLOUT.md` § 1 |
| **V14** — s1's `.env.production` `display_tz` | DATE-07 (pre-rollout) | Live server config; it **parameterises the backfill** and must be baked into the migration as a literal, since migrations may not import app code. **Hard blocker for writing the migration.** | On s1: `grep -i 'DISPLAY_TZ\|display_tz' .env.production` | **MEASURED** — unset in the file and unset in the container; effective value `Europe/Moscow` from the `app/config.py:76` default. Baked into `0027` as `_DISPLAY_TZ`. `33-ROLLOUT.md` § 1–2 |
| Rollout order: migrate + redeploy s1 → verify `/api/sync/pull` and a push from a current client → **only then** cut the client release tag | SYNC-10..13 (LOCKED constraint 5) | Cross-machine sequencing across a self-updating client fleet. | Follow ROADMAP LOCKED ordering constraint 5 verbatim. Never edit migrations `0018`/`0026` retroactively. | **PARTIALLY EXECUTED 2026-09-04.** Steps 1–3 done on s1: `0026 → 0027`, coverage `1504\|1504` and `0\|0`, exactly four triggers, `/health` 200. Step 4's **push half is UNVERIFIED** (needs a real pre-update client token). **Step 5 — the client release tag — NOT cut**, correctly, since step 4 is only half-verified. `0018`/`0026` untouched. `33-ROLLOUT.md` § Executed rollout |
| Any deployed client below `alembic_version` `0024` | SYNC-12 | Fleet state is not observable from the repo. | Log `batch.schema_version` server-side for a week; determines whether V1 is live risk or theory. | **NOT ENABLED.** Advisory only; changes no decision (D-01 accepts a behind client either way). `33-ROLLOUT.md` § Executed rollout, advisory |

---

## Validation Sign-Off

Each box below was checked against the artefacts, not assumed. The scope of these six boxes is the
**automated sampling contract** — whether this phase's automated feedback was frequent enough and
fast enough to catch a regression within the latency budget. Box 7 was added because that scope does
not cover everything this phase owed, and pretending otherwise with six ticks would be the false
signal.

- [x] **All tasks have `<automated>` verify or Wave 0 dependencies.** 45 tasks across 15 plans. 41 carry a runnable `<automated>` command. The 4 that carry `<automated>MISSING — …` are legitimate and each names why no server-side observable exists and where its result is recorded instead: `33-04` Tasks 1 and 2 (live remote server state and config — recorded in `33-ROLLOUT.md` § 1 as measured facts), and `33-15` Tasks 2 and 3 (browser-rendered constraint UI, and a cross-machine rollout against live production — recorded in `33-ROLLOUT.md` § Browser checks and § Executed rollout). `33-04` Task 3 and `33-15` Tasks 1 and 4 each carry a real automated command, so no MISSING run is unbounded.
- [x] **Sampling continuity: no 3 consecutive tasks without automated verify.** The longest run of consecutive MISSING tasks is **2** (`33-04` T1–T2, closed by T3's `grep`/`test -f` gate; and `33-15` T2–T3, closed by T4's `grep` gate and preceded by T1's full-suite run). Verified by listing every `<automated>` line in all 15 plans.
- [x] **Wave 0 covers all MISSING references (3 new test files above).** All three exist on disk at HEAD `d6be4f5` and all their tests are green — see § Wave 0 Requirements.
- [x] **No watch-mode flags.** `grep` for `--watch`, `pytest-watch` and `ptw` across all 15 plan files and this document returns nothing. Every command is a single-shot run.
- [x] **Feedback latency < 30 s.** Measured 2026-09-04: the quick command completes in **16.4 s** (54 passed).
- [x] **`nyquist_compliant: true` set in frontmatter.** Set. **What it asserts and what it does not:** it asserts the four boxes above — every task is sampled by an automated command or by a named, recorded manual observation, no gap runs 3 tasks long, and feedback returns in under half the budget. It does **not** assert that every verification this phase owed has been observed. Box 7 is where that is recorded.
- [ ] **Manual-only verification set observed.** **NOT TICKED — reason:** the seven browser checks B-1 … B-7 are **NOT RUN** (browser tooling has no site permission for `localhost`/`127.0.0.1`; the app itself answered `200`), `tests/test_pg_parity.py` did not run (its CI job aborts on a pre-existing unrelated failure), and the live pre-update-client push against s1 is unverified. All three are open items in `33-ROLLOUT.md` § Backlog (items 1, 2, 4) with reproduction steps preserved. A tick here would be false.

**Approval:** 2026-09-04 — signed by plan `33-15` Task 4, with box 7 deliberately left open and its
three outstanding items carried into `33-ROLLOUT.md` § Backlog raised by this phase.
