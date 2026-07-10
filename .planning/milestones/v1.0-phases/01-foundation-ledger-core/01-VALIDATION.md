---
phase: 1
slug: foundation-ledger-core
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-08
updated: 2026-07-08
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x (+ httpx 0.28.x for TestClient) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` — installed by Plan 01-01 Task 1 (Wave 0) |
| **Quick run command** | `uv run pytest -q -x` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q -x`
- **After every plan wave:** Run `uv run pytest -q` + `uv run ruff check .`
- **Before `/gsd-verify-work`:** Full suite green + run.bat manual check (end-of-phase)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | FND-01/02/03 (infra) | T-1-SC, T-1-05 | canonical pinned deps; .env gitignored | import/smoke | `uv run python -c "import fastapi, sqlalchemy, alembic, jinja2, pydantic_settings, python_multipart"` + htmx size check | ✅ (no test file needed) | ⬜ pending |
| 1-01-02 | 01 | 1 | FND-01, FND-02, FND-03 | — | N/A (contract authoring) | RED gate | `uv run python -m py_compile tests/*.py && ! uv run pytest -q` | ❌ W0 (this task CREATES them) | ⬜ pending |
| 1-02-01 | 02 | 2 | FND-02, FND-03 (fields) | T-1-06, T-1-07 | Integer cents only; PRAGMA listener w/ autocommit fix | unit (inline asserts) | `uv run python -c "...to_cents/format_cents/APPEND_ONLY_TRIGGERS/metadata Numeric scan..."` (full command in 01-02-PLAN Task 1) | ✅ after 1-01-02 | ⬜ pending |
| 1-02-02 | 02 | 2 | FND-01, FND-02 | T-1-03 | DB-level append-only triggers | integration | `uv run alembic upgrade head` + trigger/seed sqlite check + `uv run pytest tests/test_pragmas.py -q` | ✅ after 1-01-02 | ⬜ pending |
| 1-03-01 | 03 | 3 | FND-01, FND-02, FND-03 | T-1-03 | single write path (grep gate) | unit/integration | `uv run pytest tests/test_ledger.py tests/test_pragmas.py -q` | ✅ after 1-01-02 | ⬜ pending |
| 1-03-02 | 03 | 3 | FND-01, FND-03 (visible) | T-1-01, T-1-04 | typed Form input; autoescape, no \|safe | smoke/e2e | `uv run pytest -q` | ✅ after 1-01-02 | ⬜ pending |
| 1-03-03 | 03 | 3 | deploy (Success Criterion 1) | T-1-02 | loopback-only bind (grep gate) | full gate | `uv run pytest -q && uv run ruff check .` + run.bat grep gates | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Grep-gate hygiene note: run.bat gates use content greps (`grep -q "127.0.0.1"`, negated `! grep -q -- "--reload"`), not bare `grep -c == 0` on unfiltered files.

---

## Wave 0 Requirements

Created by Plan 01-01 Task 2 (RED before any implementation):

- [ ] `tests/conftest.py` — tmp-path file SQLite engine (build_engine + APPEND_ONLY_TRIGGERS), session, seeded product, lazy TestClient fixture
- [ ] `tests/test_pragmas.py` — WAL / foreign_keys / busy_timeout on live pooled connection
- [ ] `tests/test_ledger.py` — FND-01 (append-only, projection, rebuild), FND-02 (uuid4/cents/UTC + no Numeric/Float in metadata), FND-03 (created_by/created_at, seq audit)
- [ ] `tests/test_smoke.py` — GET / renders htmx + product; POST /ops records correction end-to-end
- [ ] Framework install: `uv add --dev pytest httpx ruff` + `[tool.pytest.ini_options]` in pyproject.toml (Plan 01-01 Task 1)

(`wave_0_complete` flips to true when Plan 01-01 executes.)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| run.bat starts app offline, browser opens, correction survives restart | ROADMAP Success Criterion 1 (+ FND-01 persistence) | Requires real Windows shell + default browser + network-off state | See `<human-check>` in 01-03-PLAN.md Task 3 (end-of-phase, per workflow.human_verify_mode) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (created in Plan 01-01 before implementation plans)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planner sign-off 2026-07-08 (execution flips per-task Status + wave_0_complete)
