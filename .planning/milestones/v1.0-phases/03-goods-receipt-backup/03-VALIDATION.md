---
phase: 3
slug: goods-receipt-backup
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-08
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* (installed, dev group) + httpx TestClient |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=tests, pythonpath=.) |
| **Quick run command** | `uv run pytest tests/test_receipts.py tests/test_backup.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~10–20 seconds (Phase 2 suite runs in seconds; file-based tmp SQLite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_receipts.py tests/test_backup.py -x -q` (plus `uv run ruff check .`)
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | RCP-01 | — | N/A (RED contract) | unit+integration | `uv run pytest -q tests/test_receipts.py; test $? -ne 0` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 1 | RCP-01 | T-3-01/T-3-03 | strict qty/money validation; single write path; 422 never raw 500 | unit+integration | `uv run pytest -q tests/test_receipts.py -k "not recent and not nav"` | ✅ after W0 | ⬜ pending |
| 3-01-03 | 01 | 1 | RCP-01 | T-3-02 | autoescaped recent rows, no \|safe | integration | `uv run pytest -q` | ✅ | ⬜ pending |
| 3-02-01 | 02 | 2 | RCP-02 | — | N/A (RED contract) | unit+integration | `uv run pytest -q tests/test_receipts.py -k "lookup or price_sync"; test $? -ne 0` | ✅ (extends) | ⬜ pending |
| 3-02-02 | 02 | 2 | RCP-02 (D-07) | T-3-03 | one-transaction price sync via record_operation | unit | `uv run pytest -q tests/test_receipts.py -k "price_sync"` | ✅ | ⬜ pending |
| 3-02-03 | 02 | 2 | RCP-02 | T-3-05/T-3-06/T-3-07 | read-only lookup; 204 guard; autoescape | integration | `uv run pytest -q` | ✅ | ⬜ pending |
| 3-03-01 | 03 | 2 | BCK-01 | — | conftest gate: suite never VACUUMs real DB | unit | `uv run pytest -q tests/test_backup.py; test $? -ne 0` | ❌ W0 | ⬜ pending |
| 3-03-02 | 03 | 2 | BCK-01 | T-3-08/T-3-12 | bound-param VACUUM; partial-file cleanup; gated startup | unit | `uv run pytest -q tests/test_backup.py -k "not web_backup and not nav"` | ✅ after W0 | ⬜ pending |
| 3-03-03 | 03 | 2 | BCK-01 | T-3-09/T-3-10/T-3-11 | no client paths; sidecar cleanup in restore.bat; no HTTP download | integration | `uv run pytest -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_receipts.py` — RED stubs for RCP-01 (Plan 03-01 Task 1); RCP-02 tests appended by Plan 03-02 Task 1
- [ ] `tests/test_backup.py` — RED stubs for BCK-01 incl. restore roundtrip (Plan 03-03 Task 1)
- [ ] `tests/conftest.py` — client fixture disables `settings.backup_on_startup` (RESEARCH Pitfall 1; Plan 03-03 Task 1)
- [ ] `app/config.py` — backup settings fields exist so the conftest gate can monkeypatch them (Plan 03-03 Task 1)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Form clears AND focus lands on «Код» after a save without a click | RCP-01/D-02 | DOM focus is not observable via TestClient | /receipts/new → save a receipt → type immediately; characters must land in «Код» |
| Lookup never overwrites values typed during the 300ms debounce flight | RCP-02/D-03 | in-flight swap race needs a real browser | type a price, then a known code fast; typed price must survive |
| restore.bat end-to-end on Windows | BCK-01/D-11 | batch script replaces the live DB with the app stopped | run.bat → note a backup file → close app → `restore.bat backups\<file>` → run.bat → data intact (automated roundtrip test covers the copy semantics) |
| Startup backup appears on real launch | BCK-01/D-09 | real lifespan against the real data/ DB | run.bat → new myorishop-*.db in backups/ |

All checks run at end-of-phase UAT (workflow.human_verify_mode = end-of-phase; no in-plan checkpoints).

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test_receipts.py, test_backup.py, conftest gate)
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-08
