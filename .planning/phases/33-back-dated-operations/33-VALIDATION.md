---
phase: 33
slug: back-dated-operations
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-04
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `33-RESEARCH.md` § `## Validation Architecture` (rows VA-1 … VA-17).
> Every command below was authored against executed evidence, not assumed.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 (`pyproject.toml:24`, pinned `pytest==9.1.*`) |
| **Config file** | `pyproject.toml:28-30` — `[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["."]`. No `pytest.ini` / `setup.cfg` / `tox.ini` exists |
| **Quick run command** | `uv run pytest tests/test_append_only_cursor.py tests/test_migrations.py tests/test_business_date.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~30 s quick · full suite dominated by the existing suite |
| **PostgreSQL parity** | `uv run pytest tests/test_pg_parity.py -q` with `DATABASE_URL=postgresql+psycopg://…`; skipped when unset. Existing harness; CI runs `postgres:17` (`.planning/ROADMAP.md:141`) |

> **Known pre-existing red — do NOT attribute to this phase.** Four `tests/test_sync_ui.py`
> tests fail deterministically in a local full-suite run (the lifespan auto-sync thread holds
> `sync_client._run_lock`). Pre-existing since ≤ `49a53d2`. Do not "fix" them here.

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/test_append_only_cursor.py tests/test_migrations.py tests/test_business_date.py -x -q`
- **After every plan wave:** `uv run pytest -q` (full suite), accepting the 4 known-red `test_sync_ui.py` cases
- **Before `/gsd-verify-work`:** full suite green (modulo the 4 known) **plus** one PostgreSQL run of `tests/test_pg_parity.py` — V4's PostgreSQL half could not be exercised locally (no PG instance; starting one is forbidden by CLAUDE.md)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

Task IDs are assigned by `/gsd-plan-phase`'s planner (§8) and backfilled into this table by the
executor. The VA-ID is the stable key; the Task ID column is the join.

| VA | Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|----|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| VA-1 | TBD | TBD | 1 | SYNC-10 | TBD | Client-ahead push refused `409` + RU constant; client-behind push accepted `200` and merged | integration | `uv run pytest tests/test_sync_schema_gate.py -x -q` | ❌ W0 | ⬜ pending |
| VA-2 | TBD | TBD | 1 | SYNC-11 | TBD | After a `409`, every row in the batch keeps `synced_at IS NULL` and `sync_state.last_sync_at` did not advance | integration | `uv run pytest tests/test_sync_schema_gate.py::test_refused_push_leaves_rows_unsynced -x` | ❌ W0 | ⬜ pending |
| VA-3 | TBD | TBD | 1 | SYNC-12 | TBD | `cash_movement` with `currency` popped merges and lands `'RUB'`; with `business_date` popped merges and lands `NULL` | unit | `uv run pytest tests/test_merge.py -k missing_column -x` | ⚠ extend | ⬜ pending |
| VA-4 | TBD | TBD | 1 | SYNC-12 | TBD | A record carrying an **unknown** field merges, the field is dropped, success is reported — the exact loss SYNC-10 gates. **Assert DROP, not reject** (ROADMAP:320 states the assertion backwards) | unit | `uv run pytest tests/test_merge.py -k unknown_field_is_dropped -x` | ⚠ extend | ⬜ pending |
| VA-5 | TBD | TBD | 2 | SYNC-13 | TBD | The four triggers on an `alembic upgrade head` DB are whitespace-normalised-identical to `app/db.py::APPEND_ONLY_TRIGGERS` | integration | `uv run pytest tests/test_migrations.py::test_alembic_head_triggers_match_app_db -x` | ❌ W0 | ⬜ pending |
| VA-6 | TBD | TBD | 2 | SYNC-13 | TBD | `upgrade head → downgrade -1 → upgrade head` leaves exactly 4 triggers and the head column set | integration | `uv run pytest tests/test_migrations.py::test_downgrade_upgrade_roundtrip_preserves_triggers -x` | ❌ W0 | ⬜ pending |
| VA-7 | TBD | TBD | 1 | SYNC-10 (D-04) | TBD | Every `revision` / `down_revision` literal under `alembic/versions/` matches `^\d{4}$` | unit | `uv run pytest tests/test_migrations.py::test_revision_ids_are_fixed_width -x` | ❌ W0 | ⬜ pending |
| VA-8 | TBD | TBD | 2 | SYNC-13 | TBD | `test_trigger_column_list_matches_schema` + `test_declared_constants_match_trigger_ddl` green with the 4 new columns in **both** frozensets | unit | `uv run pytest tests/test_append_only_cursor.py -x -q` | ✅ exists (`:246`, `:261`) — extend constants at `:40-73` | ⬜ pending |
| VA-9 | TBD | TBD | 2 | DATE-07 | TBD | A fixed past period's `sales_profit_report` is **byte-identical** before and after the migration (full dict, not just totals) | integration | `uv run pytest tests/test_business_date.py::test_sales_profit_byte_identical_across_migration -x` | ❌ W0 | ⬜ pending |
| VA-10 | TBD | TBD | 2 | DATE-07 (Pitfall 14) | TBD | Same fixtures bucket correctly at `display_tz="America/New_York"` **and** `"UTC"`; the backfill's tz-correct result differs from the naive `substr` cut on the straddling fixtures | unit | `uv run pytest tests/test_business_date.py -k timezone -x` | ❌ W0 | ⬜ pending |
| VA-11 | TBD | TBD | 3 | DATE-04 (Pitfall 16) | TBD | `business_date` appears in **zero** of `app/services/sync.py`, `app/services/sync_client.py`, `app/routes/sync.py` | unit | `uv run pytest tests/test_business_date.py::test_business_date_absent_from_sync_layer -x` | ❌ W0 | ⬜ pending |
| VA-12 | TBD | TBD | 3 | DATE-08 | TBD | A row with `business_date IS NULL` still appears in every period report, bucketed by `substr(created_at,1,10)` via the read-time COALESCE | unit | `uv run pytest tests/test_business_date.py -k null_business_date -x` | ❌ W0 | ⬜ pending |
| VA-13 | TBD | TBD | 3 | DATE-03 | TBD | Each of the 9 switched predicates returns the back-dated row under the business-date period and **not** under the entry-date period | unit | `uv run pytest tests/test_reports.py tests/test_finance_reports.py tests/test_customers.py tests/test_export.py tests/test_history.py -q` | ⚠ extend | ⬜ pending |
| VA-14 | TBD | TBD | 3 | DATE-02 | TBD | Future date → `OP_DATE_FUTURE_ERROR`; malformed → `OP_DATE_FORMAT_ERROR`; both under `errors["op_date"]`; **zero writes** on refusal | unit | `uv run pytest tests/test_receipts.py -k op_date -x` | ⚠ extend | ⬜ pending |
| VA-15 | TBD | TBD | 3 | DATE-01 | TBD | Every one of the 14 D-16 write surfaces renders a `name="op_date"` input pre-filled with today | integration | `uv run pytest tests/test_business_date.py::test_every_write_surface_renders_op_date -x` | ❌ W0 | ⬜ pending |
| VA-16 | TBD | TBD | 4 | DATE-05, DATE-06 | TBD | История renders one line when the dates match, two lines + «задним числом» when they differ — desktop **and** mobile | integration | `uv run pytest tests/test_history.py -k dated -x` | ⚠ extend | ⬜ pending |
| VA-17 | TBD | TBD | 3 | DATE-04 (D-22) | TBD | `_SORT_MAP` and `_DEFAULT_ORDER` unchanged; a just-entered back-dated row is still first in every "recent N" feed | unit | `uv run pytest tests/test_history.py::test_recent_feeds_still_order_by_created_at -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Wave numbers above are the researcher's dependency reading, not a planner commitment — the
planner owns wave assignment and may compact them, subject to the LOCKED ordering constraint
that SYNC-10..13 land before the migration.*

---

## Wave 0 Requirements

- [ ] `tests/test_migrations.py` — **new file.** `alembic_engine` fixture (fresh `tmp_path` SQLite DB built by invoking Alembic programmatically with `DATABASE_URL` pointed at it) + VA-5, VA-6, VA-7. **Must NOT re-point `tests/conftest.py::engine`** — 14 fixtures depend on it transitively (V3).
- [ ] `tests/test_business_date.py` — **new file.** VA-9, VA-10, VA-11, VA-12, VA-15, VA-17.
- [ ] `tests/test_sync_schema_gate.py` — **new file.** VA-1, VA-2. Must inject `schema_version` explicitly or monkeypatch `current_schema_version` — the whole suite builds via `create_all`, so `current_schema_version` returns `""` on both sides and D-03's escape hatch would otherwise short-circuit the gate.
- [ ] No framework install needed — pytest 9.1.1 is already pinned and configured.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Native validation bubble on a `max`-violating date submit | DATE-02 (D-13) | Browser-rendered constraint UI has no server-side observable. Research settled the htmx half from vendored source (htmx 2.0.10 uses `checkValidity()`, `reportValidityOfForms` defaults false and is never overridden; the 8 desktop forms carry `hx-post` on the `<form>` with a native submit button so the **browser** validates first) — what remains is confirming the bubble actually appears. | Open `/receipts`, set the date input to tomorrow, click «Сохранить приход». Expect a native validation bubble and no request. Then repeat on a mobile shell wizard (приход) where `hx-post` sits on the button — expect `max` to be inert and the server's `OP_DATE_FUTURE_ERROR` to render. |
| `.filter-bar` overflow with the fourth `<select>` | DATE-06 (D-20) | CSS layout at a specific viewport width. `app/static/style.css:188-193` sets no `flex-wrap` (unlike `.toolbar` at `:72-77`). | Open `/history` at 1024 px wide. Look for a horizontal scrollbar. If present, this is a deferred one-line fix touching every `.filter-bar` page — record it, do not fix it inside this phase. |
| PostgreSQL half of the trigger/backfill behaviour (V4) | SYNC-13, DATE-07 | No PostgreSQL instance on the dev machine; starting one is forbidden by CLAUDE.md. | CI: `uv run pytest tests/test_pg_parity.py -q` against the `postgres:17` service. Required before the phase gate. |
| **V13** — s1's `alembic_version` is `0026` | SYNC-10 (pre-rollout) | Live server state. | On s1: `docker compose -f docker-compose.prod.yml exec ori-app uv run alembic current` |
| **V14** — s1's `.env.production` `display_tz` | DATE-07 (pre-rollout) | Live server config; it **parameterises the backfill** and must be baked into the migration as a literal, since migrations may not import app code. **Hard blocker for writing the migration.** | On s1: `grep -i 'DISPLAY_TZ\|display_tz' .env.production` |
| Rollout order: migrate + redeploy s1 → verify `/api/sync/pull` and a push from a current client → **only then** cut the client release tag | SYNC-10..13 (LOCKED constraint 5) | Cross-machine sequencing across a self-updating client fleet. | Follow ROADMAP LOCKED ordering constraint 5 verbatim. Never edit migrations `0018`/`0026` retroactively. |
| Any deployed client below `alembic_version` `0024` | SYNC-12 | Fleet state is not observable from the repo. | Log `batch.schema_version` server-side for a week; determines whether V1 is live risk or theory. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (3 new test files above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30 s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
