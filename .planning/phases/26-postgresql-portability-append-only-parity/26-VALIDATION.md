---
phase: 26
slug: postgresql-portability-append-only-parity
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-18
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Sourced from 26-RESEARCH.md §"Validation Architecture" (test map + sampling rate).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* `[VERIFIED: pyproject.toml]` |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| **Quick run command** | `uv run pytest tests/test_pragmas.py tests/test_ledger.py -x` |
| **Full suite command** | `uv run pytest` |
| **PG-parity run (CI / local docker only)** | `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/postgres uv run pytest tests/test_pg_parity.py -x` |
| **Estimated runtime** | ~30s full SQLite suite (≈45 tests); <5s quick regression subset (estimate) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_pragmas.py tests/test_ledger.py -x` (SQLite append-only triggers unbroken) + `uv run ruff check <changed files>`
- **After every plan wave:** Run `uv run pytest` (full SQLite suite); PG parity runs on CI (or local docker if available)
- **Before `/gsd-verify-work`:** Full SQLite suite green AND the CI `pg-parity` job green (`alembic upgrade head` on empty postgres:17 + all 5 `test_pg_parity.py` assertions)
- **Max feedback latency:** ~30 seconds (full SQLite suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 26-03-03 | 03 | 2 | SRV-01 | — | N/A (schema parity: full Alembic history applies to empty PG) | integration (PG) | `uv run pytest tests/test_pg_parity.py::test_full_history_applies -x` | ❌ W0 (26-01-02) | ⬜ pending |
| 26-03-03 | 03 | 2 | SRV-01 | — | N/A (Cyrillic case-insensitive search returns identical rows on PG) | integration (PG) | `uv run pytest tests/test_pg_parity.py::test_cyrillic_search_parity -x` | ❌ W0 (26-01-02) | ⬜ pending |
| 26-03-03 | 03 | 2 | SRV-02 | T-26-01 | UPDATE on `operations` rejected at DB (append-only) | integration (PG) | `uv run pytest tests/test_pg_parity.py::test_operations_update_rejected -x` | ❌ W0 (26-01-02) | ⬜ pending |
| 26-03-03 | 03 | 2 | SRV-02 | T-26-01 | DELETE on `operations` rejected at DB (append-only) | integration (PG) | `uv run pytest tests/test_pg_parity.py::test_operations_delete_rejected -x` | ❌ W0 (26-01-02) | ⬜ pending |
| 26-03-03 | 03 | 2 | SRV-02 | T-26-01 | UPDATE + DELETE on `cash_movements` rejected at DB (append-only) | integration (PG) | `uv run pytest tests/test_pg_parity.py::test_cash_movements_immutable -x` | ❌ W0 (26-01-02) | ⬜ pending |
| 26-02-01 | 02 | 1 | SRV-02 (regression) | T-26-01 | SQLite append-only triggers still ABORT after the 0001/0013 dialect-branch edit | unit (SQLite) | `uv run pytest tests/test_pragmas.py -x` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Notes:**
- The 5 PG-parity tests are **scaffolded** in Plan 01 Task 2 (`26-01-02`, the Wave 0 deliverable) as `skipif not PG`, so they are collected but SKIP on SQLite. They only RUN non-skipped when `DATABASE_URL` targets PostgreSQL, which happens **only** in the CI `pg-parity` job created in Plan 03 Task 3 (`26-03-03`, Wave 2) — hence they are mapped to that proving task.
- The append-only **trigger DDL** the SRV-02 rows exercise is authored in Plan 02 (`operations` in `26-02-01`, `cash_movements` in `26-02-02`); the SQLite side of that same DDL is regression-guarded by the `test_pragmas.py` row (Wave 1).
- `tests/test_ledger.py` (existing) is part of the per-commit quick subset but has no phase-new behavior mapped here; it is a SQLite append-only regression backstop.

---

## Wave 0 Requirements

- [ ] `tests/test_pg_parity.py` — scaffold for the 5 SRV-01/SRV-02 assertions (`test_full_history_applies`, `test_cyrillic_search_parity`, `test_operations_update_rejected`, `test_operations_delete_rejected`, `test_cash_movements_immutable`); module-level `skipif` unless `DATABASE_URL` is PostgreSQL. Created in Plan 01 Task 2 (`26-01-02`).
- [ ] `psycopg[binary]==3.3.*` dependency — required to import the `postgresql+psycopg://` driver; added in Plan 01 Task 1 (`26-01-01`).
- [ ] `.github/workflows/ci.yml` — the `postgres:17` service job that sets `DATABASE_URL` and runs `tests/test_pg_parity.py` on real PG (the ONLY place the 5 PG tests execute non-skipped). Created in Plan 03 Task 3 (`26-03-03`).

*Existing SQLite infrastructure (`tests/conftest.py` fixtures, `tests/test_pragmas.py`, `tests/test_ledger.py`) already covers the SQLite side of parity — no new SQLite scaffold needed; those suites must stay green after the migration edits.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full Alembic history applies to empty `postgres:17` and all 5 PG-parity assertions pass | SRV-01, SRV-02 | No PostgreSQL on the Windows dev host; the proof executes only in GitHub Actions (or an optional local docker PG). The `-x` commands above SKIP locally without a PG service. | Push the branch; confirm the GitHub Actions `pg-parity` job is GREEN — `alembic upgrade head` completes on the empty `postgres:17` service (SRV-01), Cyrillic search parity holds (SRV-01), and UPDATE/DELETE on `operations` + `cash_movements` are rejected with an `append-only` error (SRV-02). Matches Plan 03 Task 3 `<human-check>`. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (`tests/test_pg_parity.py`, `psycopg`, `.github/workflows/ci.yml`)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-19
