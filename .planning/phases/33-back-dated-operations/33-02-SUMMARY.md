---
phase: 33-back-dated-operations
plan: 02
subsystem: sync
tags: [fastapi, httpx, http-409, htmx, auto-sync, back-off, pytest]

# Dependency graph
requires:
  - phase: 33-back-dated-operations
    plan: 01
    provides: "the HTTP 409 push gate (push_schema_ok + SCHEMA_AHEAD_ERROR) this client half reacts to"
  - phase: 29-sync-client
    provides: "run_sync_once (the httpx.HTTPStatusError branch), format_sync_message, SyncResult, MAX_INTERVAL_SECONDS"
  - phase: 29-sync-client
    provides: "_auto_sync_iteration — the loop whose interval is read at the top and returned at the bottom"
provides:
  - "SyncResult(status='schema_mismatch') — the 409 push refusal as its own client status, distinct from the generic `error`"
  - "format_sync_message branch rendering «Сервер ещё не обновлён — синхронизация отложена»"
  - "D-09 auto-sync back-off: MAX_INTERVAL_SECONDS (3600) while the server keeps refusing, self-clearing"
affects: [33-03-migration-tripwires, 33-04-migration-0027, sync, rollout-runbook]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A distinguishable refusal status: one status_code branch inside the SHIPPED except httpx.HTTPStatusError, one elif in the SHIPPED formatter chain — no new template, CSS token, column or setting"
    - "Self-clearing back-off derived from already-persisted state (sync_state.last_status) instead of a new stored counter — nothing to unwind on recovery"
    - "The refusal is inspected by status code ONLY; the response body is never read, so no server bytes can reach the operator"

key-files:
  created: []
  modified:
    - app/services/sync_client.py
    - app/main.py
    - tests/test_sync_client.py
    - tests/test_autosync.py
    - tests/test_sync_schema_gate.py
    - app/__init__.py

key-decisions:
  - "33-02 (D-08): a 409 gets its own SyncResult status rather than reusing `error`, because the refusal is temporary and self-healing — «Ошибка сервера, попробуйте позже» would tell the operator to do something about a condition that resolves itself when s1 is rebuilt."
  - "33-02 (D-08): the refused tick returns EARLY without pulling. A receiver too old to accept our push necessarily holds reference data OLDER than ours, so the pull could only cost a round trip; it can never repair the mismatch."
  - "33-02 (D-08): #sync-badge is deliberately NOT suppressed on a refusal. The growing unsynced count is the visible pressure signal, and SYNC-11 guarantees every one of those rows is still re-pushable — hiding it would be the repudiation threat T-33-06."
  - "33-02 (D-09): the back-off reads sync_state.last_status AFTER the tick instead of storing a retry counter. No new column, no new setting, and it self-clears on the first non-mismatch tick — there is no state to unwind when s1 comes back."
  - "33-02 (D-09): the accepted cost of a 3600s back-off is up to an hour of recovery lag after s1 is rebuilt. Mitigated by an existing surface: the manual «Синхронизировать» link shares the `_run_lock` but NOT the loop's sleep, so the operator can always resync instantly."
  - "33-02: the word `detail` was kept out of app/services/sync_client.py entirely (comments included) so the plan's `grep -c detail` == HEAD criterion stays a real signal that the client never reads the server's response body (T-29-07)."

patterns-established:
  - "Server-response handling in the client: branch on the status CODE, never on the body — the body is the untrusted half of the boundary"
  - "A downstream plan that changes a status label owns retargeting the upstream plan's incidental assertion, in its own commit, with the reason in the diff"

requirements-completed: [SYNC-10, SYNC-11]

# Metrics
duration: 24min
completed: 2026-09-04
---

# Phase 33 Plan 02: Schema-Mismatch Refusal, Client Half Summary

**A 409 from the 33-01 push gate now reads as «Сервер ещё не обновлён — синхронизация отложена» in the header instead of the generic «Ошибка сервера», skips the pointless pull, leaves the whole backlog re-pushable, and backs the auto-sync loop off from every 5 minutes to once an hour so a permanent refusal cannot become a self-inflicted retry storm.**

## Performance

- **Duration:** ~24 min (11:05Z → 11:29Z, including a 7m24s full-suite run)
- **Tasks:** 3 planned + 1 auto-fix commit
- **Files modified:** 6 (0 created, 6 modified)

## Accomplishments

- **The refusal is now legible.** Plan 33-01 deliberately shipped a server that answers 409 while
  the client still collapsed it into `error`. The operator would have been told «Ошибка сервера,
  попробуйте позже» — an instruction to act on a condition that resolves itself the moment s1 is
  rebuilt. It now says the true thing: the server is not updated yet, sync is postponed.
- **T-33-03 is closed — the threat this phase created on purpose.** The interval is read at the TOP
  of `_auto_sync_iteration`, so a permanent 409 would have retried every 300s forever, each time
  re-serializing and re-uploading the WHOLE growing unsynced closure and burning a push rate-limit
  token (`app/routes/sync.py:84-86`). The loop now sleeps 3600s while the mismatch persists.
- **The back-off costs no state.** It is derived from the `last_status` the tick already commits, so
  there is nothing to reset: the first non-mismatch tick returns the configured interval by
  construction. Pinned by `test_auto_sync_interval_restored_after_recovery`.
- **The badge was left alone, deliberately.** Suppressing `#sync-badge` on a refusal would hide a
  growing unsent backlog from the only person who can act on it (T-33-06). The rendered partial
  below shows the count still displayed alongside the refusal message.
- **No server bytes can leak.** Only `exc.response.status_code` is inspected; the 409 body — which
  names both Alembic revisions — is never read. `test_schema_mismatch_message_carries_no_server_bytes`
  drives a real 409 carrying a distinctive payload and asserts neither revision id reaches the message.

## Task Commits

Each task was committed atomically:

1. **Task 1: RED cases for the refusal path** — `5107b19` (test)
2. **Task 2: schema_mismatch status + formatter branch (D-08)** — `a2b92e6` (feat)
3. **Task 3: auto-sync back-off on schema_mismatch (D-09)** — `7fe0211` (feat)
4. **Auto-fix: retarget the 33-01 VA-2 assertion** — `4ca5497` (test, Rule 1 — see Deviations)

## Files Created/Modified

- `app/services/sync_client.py` — the shipped `except httpx.HTTPStatusError` now binds the exception
  and splits on `status_code == 409`, returning `SyncResult(status="schema_mismatch", pushed=0,
  pushed_total=pushed_total)` and keeping the early return; every other non-2xx still returns
  `error` unchanged. One `elif status == "schema_mismatch"` was added above the final `else` in
  `format_sync_message`. The `SyncResult` docstring's status enumeration was extended by reference
  rather than by name (see Decisions).
- `app/main.py` — `_auto_sync_iteration` re-reads the sync_state row after the offloaded tick and
  raises `interval` to `sync_client.MAX_INTERVAL_SECONDS` while `last_status == "schema_mismatch"`.
  The broad `except Exception: pass` guard is unchanged, so the loop still cannot die.
- `tests/test_sync_client.py` — 5 new cases (the fixed sentence, 409 → `schema_mismatch` with
  `pushed == 0`, the skipped pull asserted via the paths the mock transport actually saw, SYNC-11 at
  the client boundary, and the no-server-bytes case).
- `tests/test_autosync.py` — 2 new cases plus a `_tick_recording` helper that fakes the driver's
  D-10 exit point with its OWN session, mirroring the fact that the real tick runs offloaded in a
  worker thread.
- `tests/test_sync_schema_gate.py` — one assertion retargeted (Deviations).
- `app/__init__.py` — `__version__` 1.65 → 1.69 (one bump per completed-task commit).

## Decisions Made

All decisions are recorded in the frontmatter `key-decisions` block (D-08 and D-09 as they apply
here). Two judgement calls are worth naming:

1. **The `SyncResult` docstring was updated without spelling the new status.** The plan's acceptance
   criterion requires exactly two occurrences of `schema_mismatch` in `sync_client.py` (the
   construction and the formatter branch), which would have forced the docstring's status
   enumeration to go stale. It now ends "…plus the Phase-33 push-refusal status handled in
   `format_sync_message` below" — accurate, discoverable, and the grep contract holds at 2.
2. **The word `detail` was kept out of the module entirely**, comments included. `grep -c "detail"`
   is 0 at HEAD and had to stay 0; more usefully, that count is only a meaningful T-29-07 signal
   while the module never mentions the server's response body by name.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Retargeted plan 33-01's VA-2 status assertion**

- **Found during:** the plan's own verification step, after Task 3
- **Issue:** `tests/test_sync_schema_gate.py::test_refused_push_leaves_rows_unsynced` asserted
  `result.status == "error"`. That was correct when 33-01 shipped — a 409 had no status of its own
  yet — and this plan's entire purpose is to give it one. The test went red as a direct consequence
  of Task 2, inside the same subsystem, so it is in scope.
- **Fix:** the single assertion now expects `"schema_mismatch"`, with a comment in the diff
  explaining why it changed. The SYNC-11 properties the case exists to pin — zero stamped client
  rows, zero rows on the server, `last_sync_at` unchanged — were not touched.
- **Files modified:** `tests/test_sync_schema_gate.py`, `app/__init__.py`
- **Commit:** `4ca5497`

**Total deviations:** 1
**Impact on plan:** None on scope or design; one extra commit. It is arguably a plan gap rather
than a deviation — 33-01's VA-2 case was a foreseeable casualty of introducing the status, and
neither plan listed `tests/test_sync_schema_gate.py` in `files_modified`.

## Issues Encountered

- **Cross-thread DB access in the new auto-sync tests.** The fake tick runs inside
  `anyio.to_thread.run_sync`, so it writes `last_status` from a worker thread. It was given its own
  `sessionmaker(bind=engine)` rather than borrowing the test's `session` fixture — matching what
  `run_sync_tick` really does (a fresh `SessionLocal()` per tick) and sidestepping any question
  about sharing one Session across threads. Worked first try.
- **Nothing else.** No blocker, no architectural question, no fix-attempt loop.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_sync_client.py tests/test_autosync.py -q --collect-only` | 44 collected, exit 0 (RED scaffold collects cleanly) |
| `uv run pytest tests/test_sync_client.py -k schema_mismatch -q` after Task 1 | 5 failed — assertion failures, no collection error |
| `uv run pytest tests/test_autosync.py -k "backs_off or restored_after_recovery" -q` after Task 1 | 2 failed — `assert 120 == 3600`, i.e. genuinely RED |
| `uv run pytest tests/test_sync_client.py tests/test_autosync.py tests/test_sync_schema_gate.py -q` | **51 passed** |
| `uv run pytest tests/ -q --junitxml=reports/33-02.xml` (full suite) | **4 failed, 1498 passed, 14 skipped** in 444.56s — the 4 are the known-red `tests/test_sync_ui.py` cases, pre-existing since ≤ `49a53d2` |
| `git diff --stat app/templates/` | empty (no template change, D-08) |
| `grep -n "schema_mismatch" app/services/sync_client.py` | exactly 2: `:208` formatter elif, `:396` SyncResult construction |
| `grep -c "detail" app/services/sync_client.py` | 0 — unchanged from HEAD |
| `grep -c "business_date" app/services/sync_client.py` | 0 (Pitfall 16) |
| `grep -n "MAX_INTERVAL_SECONDS" app/main.py` | `:114` — the new reference |
| `git diff --stat app/models.py alembic/` | empty (no column, no migration) |
| broad `except Exception` in `_auto_sync_iteration` | still present (`app/main.py:115`) |
| `uv run ruff check` on all five touched files | All checks passed |

### Real-path check (not a test)

`_render_sync_status` — the exact seam `POST /sync/run` calls — was driven with a
`schema_mismatch` result against a throwaway SQLite DB carrying one unsynced operation. Observed
output:

```html
<span id="sync-status" class="muted" hx-swap-oob="true">Сервер ещё не обновлён — синхронизация отложена<br>Ещё не синхронизировано</span>
<span id="sync-badge" hx-swap-oob="true"><span class="sync-badge-count" style="font-size:14px;font-weight:600;color:#b45309;background:#fef9e7;padding:4px 8px;border-radius:4px">1</span></span>
```

This closes the plan's `key_links` claim by observation: the formatter's return value reaches
`#sync-status` through the unmodified template, and `#sync-badge` still renders the unsynced count
on a refusal (D-08).

**Pending human check:** the same partial swapped into a live browser after a REAL 409 from s1.
That needs an s1 whose Alembic revision is behind a client's, which does not exist until migration
`0027` ships in plan 33-04 — it belongs to that rollout, not here.

## Success Criteria

- [x] A 409 produces `status="schema_mismatch"`, the RU sentence in `#sync-status`, an untouched
      `#sync-badge`, and no pull attempt.
- [x] The next auto-sync tick after a mismatch sleeps 3600s; the one after recovery sleeps the
      configured interval.
- [x] No template, CSS token, model column or setting was added.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-03 (self-inflicted DoS: a refused client retrying every 300s) | **Mitigated** — this was the threat plan 33-01 explicitly deferred here. `_auto_sync_iteration` returns 3600s while the mismatch persists; pinned by `test_auto_sync_backs_off_on_schema_mismatch` |
| T-33-05 (info disclosure: server bytes in the operator's header) | Mitigated — only the status code is inspected, the body is never read; pinned by `test_schema_mismatch_message_carries_no_server_bytes` |
| T-33-06 (repudiation: hiding the unsent backlog) | Mitigated — `#sync-badge` untouched, verified by the real-path render above |
| T-33-SC (supply chain) | Vacuous — no package installed, `pyproject.toml` untouched |

## Known Stubs

None. Nothing was left hardcoded, placeholdered or unwired.

## Threat Flags

None — no new network endpoint, auth path, file access pattern or schema change. This plan only
adds a branch to an existing client-side response handler and a bound on an existing sleep.

## User Setup Required

None.

## Next Phase Readiness

- **Ready:** the SYNC-10/11 pair is now complete on both halves. A client that self-updates ahead of
  s1 fails loudly, legibly, cheaply, and recoverably.
- **Still blocked:** wave 2 remains gated on the human-only plan 33-04 inputs, both already measured
  read-only on s1 and carried forward unchanged: **`alembic current` = `0026 (head)`** and the
  effective **`DISPLAY_TZ` = `Europe/Moscow`** (supplied by the `app/config.py:76` fallback — there
  is no `DISPLAY_TZ` line in `.env.production` and the container env value is empty). That is the
  literal to bake into migration `0027`'s backfill.
- **Carry forward for 33-04's rollout step:** the back-off means a client refused just before s1 is
  rebuilt can lag up to an hour before it resyncs on its own. The runbook should tell the operator
  to click «Синхронизировать» once after the server redeploy rather than wait — the manual path
  shares the `_run_lock` but not the loop's sleep.
- **Note for 33-03:** unchanged from 33-01 — `push_schema_ok`'s lexicographic comparison is a live
  dependency on `test_revision_ids_are_fixed_width`.

## Self-Check: PASSED

All six claimed files exist on disk; all four commits (`5107b19`, `a2b92e6`, `7fe0211`, `4ca5497`)
are present in `git log`.

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
