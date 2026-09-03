---
phase: 26-postgresql-portability-append-only-parity
verified: 2026-07-19T00:00:00Z
status: human_needed
score: 3/3 must-haves verified (code artifacts); real-PG green run pending human
overrides_applied: 0
human_verification:
  - test: "Push the phase branch to GitHub and confirm the Actions `pg-parity` job is GREEN."
    expected: "`alembic upgrade head` completes on the empty postgres:17 service (SRV-01) and all 5 tests/test_pg_parity.py assertions pass — full history applies (products/operations/cash_movements exist), Cyrillic search parity holds, and UPDATE/DELETE on operations + cash_movements are rejected with an `append-only` error (SRV-02)."
    why_human: "The 5 PG-parity tests SKIP locally by design (no DATABASE_URL / no PostgreSQL on this Windows host). The actual proof executes only against the real postgres:17 CI service, which requires pushing the branch to GitHub. Config human_verify_mode: end-of-phase deferred this to end-of-phase verification."
---

# Phase 26: PostgreSQL Portability & Append-Only Parity Verification Report

**Phase Goal:** Prove the server's database layer before any server exists — the identical data models and the single Alembic migration history run unchanged on PostgreSQL, and PostgreSQL enforces the same append-only ledger guarantee as the SQLite client. Mechanical dialect-gating work with a real Postgres instance in CI. No sync logic yet.
**Verified:** 2026-07-19T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | The full Alembic migration history applies cleanly against an empty PostgreSQL DB in CI, producing the same schema the SQLite client uses (SRV-01) | ✓ VERIFIED (code) — human-confirm green run | `alembic/env.py:17` reads `settings.database_url` (no hardcoded sqlite URL; `grep -v '^#' | grep -c 'sqlite:///' == 0`); `render_as_batch` dialect-gated in both offline (`env.py:49`) and online (`env.py:77`) paths. Migration `0001` dialect-branches trigger DDL so SQLite `RAISE(ABORT)` (a PG syntax error) is not emitted on PG (`0001:111-116`). CI `test_full_history_applies` asserts `products`/`operations`/`cash_movements` exist via `to_regclass` (`test_pg_parity.py:84-97`). Runs against `postgres:17` in `ci.yml:16,43`. Skips on SQLite locally (5 skipped). |
| 2 | Cyrillic case-insensitive search returns identical results on PostgreSQL and SQLite (shadow-column approach holds uniformly) (SRV-01) | ✓ VERIFIED (code) — human-confirm green run | `test_cyrillic_search_parity` (`test_pg_parity.py:100-131`) seeds Cyrillic products with Python-folded `name_lc`, calls `search_products`, asserts `{p.id} == {"pg-cyr-1"}`. Search is Python-side lowercase-vs-`name_lc` (dialect-independent). Test collects and skips on SQLite. |
| 3 | On PostgreSQL, any attempt to UPDATE or DELETE a row in operations or cash_movements is rejected at the database, exactly as on SQLite (SRV-02) | ✓ VERIFIED (code) — human-confirm green run | Migrations `0001:57-65` and `0013:57-65` add PL/pgSQL `CREATE OR REPLACE FUNCTION …_append_only()` + `BEFORE UPDATE`/`BEFORE DELETE` triggers with names identical to SQLite (`operations_no_update/_no_delete`, `cash_movements_no_update/_no_delete`) and `RAISE EXCEPTION '… append-only'`. Tests `test_operations_update_rejected`, `test_operations_delete_rejected`, `test_cash_movements_immutable` assert `pytest.raises(Exception, match="append-only")`. SQLite regression: `tests/test_pragmas.py` + `tests/test_ledger.py` = 22 passed (triggers still ABORT on SQLite; WR-06 byte-for-behavior identical). |

**Score:** 3/3 truths verified at the code-artifact level. The real-PostgreSQL green execution that actually exercises all three is routed to human verification (below).

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/config.py` | `settings.database_url` single source of truth, sqlite default, DATABASE_URL override, no hardcoded credential | ✓ VERIFIED | Field `database_url: str = ""` (`config.py:30`); `_resolve_local_identity` fills `sqlite:///{db_path}` only when empty (`config.py:65-66`). Runtime check: default prints `sqlite:///data/myorishop.db`; `DATABASE_URL=postgresql+psycopg://u:p@h/db` override prints exactly that. No host/user/password literal. |
| `pyproject.toml` | `psycopg[binary]==3.3.*` dependency | ✓ VERIFIED | `pyproject.toml:11` `"psycopg[binary]==3.3.*"`; `uv.lock` resolves 3.3.4. |
| `tests/test_pg_parity.py` | 5 SRV-01/SRV-02 tests, skipif not PG | ✓ VERIFIED | 5 tests collect (0 errors); 5 skipped on SQLite. `pytestmark` reads `settings.database_url` (single source). All-literal seeds, bound param for `to_regclass`. |
| `alembic/versions/0001_initial_schema.py` | PG plpgsql branch for operations alongside unchanged SQLite path | ✓ VERIFIED | `_PG_OPERATIONS_DDL` added; emit site branches on `op.get_bind().dialect.name` (2 occurrences); SQLite tuple `_APPEND_ONLY_TRIGGERS` unchanged (WR-06). |
| `alembic/versions/0013_cash_movements.py` | PG plpgsql branch for cash_movements | ✓ VERIFIED | `_PG_CASH_APPEND_ONLY_DDL` added; dialect branch (2 occurrences); message `cash ledger is append-only` preserved. |
| `app/db.py` | `build_engine_from_url(url)` dialect-gated; PRAGMA + mkdir sqlite-only | ✓ VERIFIED | `build_engine_from_url` (`db.py:46-76`) returns early for non-sqlite before mkdir/PRAGMA listener; `build_engine(db_path)` delegates via `sqlite:///{db_path}`; module engine `= build_engine_from_url(settings.database_url)` (`db.py:89`). |
| `alembic/env.py` | URL from settings; render_as_batch + mkdir dialect-gated | ✓ VERIFIED | `set_main_option("sqlalchemy.url", settings.database_url)` (`env.py:17`); mkdir gated `if settings.database_url.startswith("sqlite")` (`env.py:22`); no hardcoded sqlite URL. |
| `.github/workflows/ci.yml` | pg-parity job: postgres:17 + SQLite suite + PG parity | ✓ VERIFIED | Job `pg-parity`, `image: postgres:17`, `pg_isready` health check, SQLite step (no DATABASE_URL), PG step with `DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/postgres` running `test_pg_parity.py`. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `app/db.py` module engine | `settings.database_url` | `build_engine_from_url(settings.database_url)` | ✓ WIRED | `db.py:89` |
| `alembic/env.py` | `settings.database_url` | `set_main_option('sqlalchemy.url', settings.database_url)` | ✓ WIRED | `env.py:17` |
| `.github/workflows/ci.yml` | `tests/test_pg_parity.py` on postgres:17 | `DATABASE_URL=postgresql+psycopg://…@localhost:5432` + pytest | ✓ WIRED | `ci.yml:40-43` |
| `tests/test_pg_parity.py` | `settings.database_url` | `pytestmark skipif` | ✓ WIRED | `test_pg_parity.py:29-32` |
| `0001.upgrade()` | `operations_append_only()` / RAISE(ABORT) | dialect branch | ✓ WIRED | `0001:111-116` |
| `0013.upgrade()` | `cash_movements_append_only()` / RAISE(ABORT) | dialect branch | ✓ WIRED | `0013:97-102` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Default DB URL resolves to sqlite | `uv run python -c "print(settings.database_url)"` | `sqlite:///data/myorishop.db` | ✓ PASS |
| DATABASE_URL override wins | `DATABASE_URL=postgresql+psycopg://u:p@h/db … print(settings.database_url)` | `postgresql+psycopg://u:p@h/db` | ✓ PASS |
| PG-parity tests collect | `pytest tests/test_pg_parity.py --collect-only -q` | 5 tests collected, 0 errors | ✓ PASS |
| PG-parity tests skip on SQLite | `pytest tests/test_pg_parity.py -q` | 5 skipped | ✓ PASS |
| SQLite append-only regression | `pytest tests/test_pragmas.py tests/test_ledger.py -q` | 22 passed | ✓ PASS |
| env.py has no hardcoded sqlite URL | `grep -v '^#' env.py \| grep -c 'sqlite:///'` | 0 | ✓ PASS |
| Trigger names identical across dialects | `grep -oE 'operations_no_(update\|delete)' 0001` | update+delete each present in SQLite & PG DDL | ✓ PASS |
| Full PG parity run against real PostgreSQL | (requires postgres:17 CI service) | — | ? SKIP → human |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| SRV-01 | 26-01, 26-02, 26-03 | Same data models + single Alembic history run unchanged on SQLite and PostgreSQL | ✓ SATISFIED (code) — human-confirm | Dialect-branched migrations + settings-driven env.py/db.py + CI `test_full_history_applies`/`test_cyrillic_search_parity`. REQUIREMENTS.md maps SRV-01 → Phase 26. |
| SRV-02 | 26-01, 26-02, 26-03 | Central server on PostgreSQL enforces append-only ledger guarantee (UPDATE/DELETE blocked at DB) | ✓ SATISFIED (code) — human-confirm | PL/pgSQL BEFORE UPDATE/DELETE triggers on both ledgers + CI rejection tests. REQUIREMENTS.md maps SRV-02 → Phase 26. |

Both requirement IDs from the plans' frontmatter (SRV-01, SRV-02) are accounted for in `.planning/REQUIREMENTS.md` (lines 38-39, 136-137, 160), both mapped to Phase 26. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | No TBD/FIXME/XXX/HACK/PLACEHOLDER in any modified file | ℹ️ Info | Debt-marker gate passes cleanly. |
| `alembic/versions/0001_initial_schema.py`, `0013_cash_movements.py` | 145-146 / 106-107 | PG downgrade `DROP TRIGGER IF EXISTS` omits `ON <table>` (WR-01) | ⚠️ Warning (advisory) | Breaks `alembic downgrade` on PG. Out of SRV-01/SRV-02 success-criteria scope (downgrade is not a phase goal). Plan-acknowledged/deferred in 26-REVIEW.md. Not a goal gap. |

### Human Verification Required

#### 1. Confirm the GitHub Actions `pg-parity` job is GREEN against real PostgreSQL

**Test:** Push the phase branch to GitHub and open the Actions run for the `pg-parity` job (postgres:17 service).
**Expected:** `alembic upgrade head` completes on the empty postgres:17 database (SRV-01), and all 5 `tests/test_pg_parity.py` assertions pass — the full history applies (`products`/`operations`/`cash_movements` created), Cyrillic search parity holds (`test_cyrillic_search_parity`), and UPDATE/DELETE on `operations` + `cash_movements` are rejected with an `append-only` error (`test_operations_update_rejected`, `test_operations_delete_rejected`, `test_cash_movements_immutable`).
**Why human:** The 5 PG-parity tests SKIP locally by design — this Windows dev host has no PostgreSQL on 5432 and no `DATABASE_URL`. The real proof executes only against the postgres:17 CI service, which requires pushing to GitHub. This is the planner-deferred human-check from Plan 03 Task 3 (`human_verify_mode: end-of-phase`).

### Gaps Summary

No code gaps. Every artifact that makes SRV-01/SRV-02 satisfiable is present, substantive, correctly wired, and dialect-gated: the single `settings.database_url` source of truth flows into both `app/db.py` and `alembic/env.py`; the two frozen migrations carry additive PG PL/pgSQL trigger branches with trigger names and `append-only` message substrings identical across dialects while leaving the SQLite emit path byte-for-behavior unchanged (WR-06); the CI `pg-parity` job runs the 5-test parity suite against a real `postgres:17`. Local behavioral checks all pass (config default/override, 5-test collect, 5-skip on SQLite, 22-pass SQLite append-only regression, no hardcoded credential, no debt markers).

The single outstanding item is the actual GREEN CI run against real PostgreSQL — inherently a human/end-of-phase verification because the proof cannot execute on this offline Windows host. Per the status decision tree, a non-empty human-verification section makes the phase status `human_needed` even though all code artifacts are VERIFIED.

The WR-01 PostgreSQL-downgrade defect (missing `ON <table>` clause) is advisory only: downgrade is outside the SRV-01/SRV-02 success criteria and was plan-acknowledged; it does not block the phase goal.

---

_Verified: 2026-07-19T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
