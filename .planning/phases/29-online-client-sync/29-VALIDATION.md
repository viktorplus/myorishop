---
phase: 29
slug: online-client-sync
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-20
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `29-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x + FastAPI `TestClient` (httpx-backed); `httpx.ASGITransport` + `httpx.MockTransport` for driver tests |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| **Quick run command** | `uv run pytest tests/test_sync_client.py tests/test_sync_ui.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~quick <15s; full ~1079 tests |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_sync_client.py tests/test_sync_ui.py -x`
- **After every plan wave:** Run `uv run pytest` (full suite — project post-merge gate)
- **Before `/gsd-verify-work`:** Full suite green **AND** PG parity green (`tests/test_pg_parity.py`, `tests/test_merge_pg.py` on postgres:17)
- **Max feedback latency:** ~15 seconds (quick), full suite in CI

---

## Per-Task Verification Map

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| SYNC-01 | Push flips `synced_at`; server merges ops+cash **and referenced reference rows (D-13)**; pull applies reference; stock stays correct | integration (ASGITransport) | `uv run pytest tests/test_sync_client.py::test_push_marks_synced_and_pulls -x` | ❌ W0 | ⬜ pending |
| SYNC-01 | Offline-authored sale/receipt (local `Sale`/`Batch`) pushes without FK failure (D-13 closure) | integration | `uv run pytest tests/test_sync_client.py::test_push_includes_referenced_reference_rows -x` | ❌ W0 | ⬜ pending |
| SYNC-01 | Idempotent re-sync (already-synced rows not re-pushed; replay skipped) | integration | `uv run pytest tests/test_sync_client.py::test_second_sync_is_noop -x` | ❌ W0 | ⬜ pending |
| SYNC-01 | Pull applies **server UPDATE** to an existing reference row (server-wins on client, D-14) | integration | `uv run pytest tests/test_sync_client.py::test_pull_applies_server_update -x` | ❌ W0 | ⬜ pending |
| SYNC-06 | Offline (`ConnectError`) → status "offline", `Нет связи с сервером`, handler returns 200 partial not 5xx | unit (MockTransport) | `uv run pytest tests/test_sync_client.py::test_offline_returns_partial_not_5xx -x` | ❌ W0 | ⬜ pending |
| SYNC-06 | `sync_state` row written on BOTH success and failure (`finally` path) | unit | `uv run pytest tests/test_sync_client.py::test_sync_state_written_on_failure -x` | ❌ W0 | ⬜ pending |
| SYNC-06 | D-12 RU strings for ok / no-change / partial / offline / server-error | unit | `uv run pytest tests/test_sync_client.py::test_result_messages -x` | ❌ W0 | ⬜ pending |
| SYNC-07 | `unsynced_count` = ops+cash where `synced_at IS NULL`; badge hidden at 0 | unit | `uv run pytest tests/test_sync_client.py::test_unsynced_count -x` | ❌ W0 | ⬜ pending |
| SYNC-07 | Header partial renders badge OOB after `/sync/run` | integration (client fixture) | `uv run pytest tests/test_sync_ui.py::test_sync_run_returns_oob_partial -x` | ❌ W0 | ⬜ pending |
| SYNC-08 | Tick with toggle OFF does nothing; ON runs driver; offline tick swallowed; toggle+interval read fresh from `sync_state` (D-15) | unit (call `run_sync_tick` directly) | `uv run pytest tests/test_sync_client.py::test_tick_respects_toggle -x` | ❌ W0 | ⬜ pending |
| SYNC-08 | `_run_lock` prevents overlap (manual + tick) | unit | `uv run pytest tests/test_sync_client.py::test_single_run_lock -x` | ❌ W0 | ⬜ pending |
| SRV-03 | Local receipt/sale succeeds with `sync_server_url` empty / server down | integration | `uv run pytest tests/test_sync_client.py::test_local_work_unaffected_offline -x` | ❌ W0 | ⬜ pending |
| SRV-01 | New migration + `sync_state` (5 cols) + unsynced partial indexes apply on PostgreSQL | PG parity | `uv run pytest tests/test_pg_parity.py -x` (extend) | ⚠️ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_sync_client.py` — driver push/pull/stamp/offline/lock/tick/messages + D-13 reference-closure push + D-14 server-update-wins (SYNC-01/06/07/08, SRV-03)
- [ ] `tests/test_sync_ui.py` — `POST /sync/run` returns OOB header partial; badge visibility (SYNC-06/07)
- [ ] Extend `tests/test_pg_parity.py` — assert `sync_state` + unsynced partial indexes build on PG (SRV-01)
- [ ] Fixture: `httpx.Client(transport=httpx.ASGITransport(app=main.app), base_url=...)` + device-token helper (build on existing `device_client` mint path)
- [ ] Framework install: **none** — httpx/pytest already present; just promote httpx to a runtime dep in `pyproject.toml`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Header sync button/status/badge is glanceable on every desktop page | SYNC-06/07 (D-01) | Visual placement in `base.html` nav across pages | Open any desktop page; confirm button + status + badge visible in header; click «Синхронизировать» and confirm in-place OOB refresh (no full reload) |
| Auto-sync keeps running with the browser tab closed | SYNC-08 (D-06) | Background lifespan loop; not observable from a single request | With auto-sync ON and a short interval, close the tab, make a server-side reference change, reopen after one interval, confirm it pulled |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s (quick)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
