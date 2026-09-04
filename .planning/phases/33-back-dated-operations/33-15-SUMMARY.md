---
phase: 33-back-dated-operations
plan: 15
subsystem: testing
tags: [validation, rollout, postgresql, alembic, ci, verification-contract]

# Dependency graph
requires:
  - phase: 33-09
    provides: CSV business-date columns and the switched export ORDER BY
  - phase: 33-13
    provides: VA-15, the 14-surface op_date contract
  - phase: 33-14
    provides: VA-16 (both halves) and the fourth .filter-bar select
provides:
  - "33-ROLLOUT.md § Executed verification — the local gate, the CI result, and the PostgreSQL proof of migration 0027 against a throwaway copy of production"
  - "33-ROLLOUT.md § Browser checks — B-1..B-7 recorded as NOT RUN with the tooling reason and the reproduction steps preserved"
  - "33-ROLLOUT.md § Executed rollout — the s1 rollout log in the LOCKED order, stopped after step 4 with three gaps named"
  - "33-ROLLOUT.md § Backlog raised by this phase — 10 open items with measured file:line references"
  - "33-VALIDATION.md — signed: all 17 VA rows joined to plan/task/threat, every Status re-measured, one sign-off box deliberately left open"
affects: [phase-34-storno-and-currency, phase-35-mobile-card-editing, ci-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase close-out plan owns the verification contract: the VA table's Plan/Task/Threat join is backfilled by grepping the plans, never from the predicted mapping"
    - "A sign-off box left open with a written reason is the correct output when a manual check was not observed; nyquist_compliant scopes to the automated sampling contract only"
    - "A migration's PostgreSQL branch can be proven on a throwaway pg_dump copy of production without touching prod or starting a container"

key-files:
  created:
    - .planning/phases/33-back-dated-operations/33-15-SUMMARY.md
  modified:
    - .planning/phases/33-back-dated-operations/33-ROLLOUT.md
    - .planning/phases/33-back-dated-operations/33-VALIDATION.md

key-decisions:
  - "33-15: nyquist_compliant is set true, but its scope is stated explicitly in the file — it asserts the AUTOMATED sampling contract (every task sampled, no 3-task gap, 16.4 s latency), not that every owed verification was observed. A seventh sign-off box was ADDED and deliberately left UNTICKED for the manual-only set (B-1..B-7 not run, pg-parity not run, live pre-update push unverified). A sixth tick with those three open would have been a false signal."
  - "33-15: the VA->plan/task mapping predicted by the plan was wrong in four places and the plans won. VA-14 spans five plans (33-06/10/11/12/13), not two. VA-13 does NOT reach 33-14 (that plan carries VA-16). VA-12 has a 33-06 Task 3 foundation. VA-5/VA-6 have a two-plan life (33-03 wrote them, 33-05 is what they were written to catch)."
  - "33-15: VA-16's own Automated Command was incomplete as shipped — desktop-only, while 33-14 states VA-16 closes only when both halves pass. The command cell now names tests/test_history.py -k dated AND tests/test_mobile_history.py -k dated."
  - "33-15: the PostgreSQL branch of 0027 is recorded as proven by a throwaway-copy upgrade on real PG 17, and tests/test_pg_parity.py is SEPARATELY recorded as «не запускал». The two are not conflated — the copy proves this migration, the parity suite is the standing guard and is still owed."
  - "33-15: the exact pg-parity command is recorded WITHOUT its connection string, per Task 4's «write no DATABASE_URL into either file», with a pointer to the workflow file instead. Task 1 asked for the exact command; the stricter rule won."

patterns-established:
  - "Backlog lines carry measured file:line, re-verified at HEAD, with the drift from the plan's predicted line numbers written down beside them"
  - "Every Manual-Only Verification row gains a Result column so the table records observation, not intent"

requirements-completed: [SYNC-10, SYNC-11, SYNC-12, SYNC-13, DATE-01, DATE-02, DATE-03, DATE-04, DATE-05, DATE-06, DATE-07, DATE-08]

# Metrics
duration: ~40min
completed: 2026-09-04
---

# Phase 33 Plan 15: Phase Close-Out — Executed Verification, Rollout Log and the Signed Validation Contract Summary

**The phase's three unsettleable questions are answered with real output — migration `0027` proven on real PostgreSQL 17 against a throwaway copy of production, the s1 rollout executed and stopped honestly at step 4 with its three gaps named, and `33-VALIDATION.md` signed with all 17 VA rows re-measured and one sign-off box deliberately left open because B-1…B-7 were never observed.**

## Performance

- **Duration:** ~40 min (approximate — agent spawn time was not recorded; the measured window is the first `pytest` run to the final commit)
- **Started:** 2026-09-04T15:20Z (approx.)
- **Completed:** 2026-09-04T16:0xZ
- **Tasks:** 4 (Tasks 1–3 executed by the orchestrator and transcribed here; Task 4 executed by this agent)
- **Files modified:** 2 artefacts + 4 planning files

## Accomplishments

- **The PostgreSQL half of migration `0027` is evidence, not assumption.** `33-RESEARCH.md` § Assumptions Log **A1 is CONFIRMED**: PostgreSQL's enumerated `WHEN (...)` did not fire on the backfill `UPDATE`. Proven by running `alembic upgrade head` against a `pg_dump` copy of the live production database on real PostgreSQL 17 — 1504 rows, `1504|1504` coverage, exactly four triggers, 403 rows where the tz-correct business date differs from the naive UTC prefix, and an append-only `UPDATE` still refused. Production and the running container were untouched.
- **The rollout is live on s1 and stopped in the right place.** Steps 1–4 of the LOCKED order executed 2026-09-04: `0026 → 0027`, coverage `1504|1504` and `0|0`, four trigger names, `/health` 200 at version `1.100`, `/api/sync/pull` 401 without a token. **Step 5 — the client release tag — was NOT cut**, correctly, because step 4's push half is unverified.
- **`33-VALIDATION.md` is signed and true rather than merely complete.** All 17 VA rows joined to a real plan, task and threat reference; every `Status` cell is the output of running that row's own command at HEAD `d6be4f5` (17/17 green); four mapping corrections recorded; and a seventh sign-off box added and left **unticked** with a written reason.
- **The phase backlog is written down where the next phase will grep for it** — 10 items, each with measured `file:line`, covering the unobserved browser checks, the uncut release tag, the pre-existing CI failure that blocks the whole pg-parity job, the `0024.downgrade()` defect, and two stale documentation references.

## Task Commits

Tasks 1–3 were executed by the orchestrator; this agent transcribed their raw output verbatim and executed Task 4. Because all four tasks write to the same two artefacts, they landed in one commit:

1. **Tasks 1–4: executed verification, browser checks, rollout log, backlog, and the signed validation contract** — `b5c4c65` (docs) — 2 files changed, 459 insertions, 45 deletions, **0 deletions of tracked files**

**Plan metadata:** see the `docs(33-15): complete phase close-out plan` commit immediately following (SUMMARY + STATE + ROADMAP + REQUIREMENTS)

## Files Created/Modified

- `.planning/phases/33-back-dated-operations/33-ROLLOUT.md` — gained four sections: `## Executed verification` (local gate, CI, the PostgreSQL proof, the per-VA re-run), `## Browser checks` (B-1…B-7 as NOT RUN with reproduction steps preserved), `## Executed rollout` (the s1 log, three gaps, the advisory), `## Backlog raised by this phase` (10 items)
- `.planning/phases/33-back-dated-operations/33-VALIDATION.md` — frontmatter flipped to `status: complete` / `nyquist_compliant: true` / `wave_0_complete: true` / `signed_off: 2026-09-04`; all 17 VA rows joined and re-measured; Wave 0 boxes ticked against files stat-ed on disk; a `Result` column added to Manual-Only Verifications; sign-off signed with box 7 open

## Decisions Made

- **`nyquist_compliant: true` was set — with its scope written into the file.** The six shipped sign-off boxes are about the *automated sampling contract*: is every task sampled, is no gap 3 tasks long, does feedback return inside the latency budget. All six are true and each was measured (45 tasks, 41 automated + 4 legitimately `MISSING`; longest MISSING run = 2; quick command 16.4 s; no watch-mode flag anywhere). B-1…B-7 live in the **Manual-Only Verifications** table, which exists precisely to name what automated sampling cannot reach — so their being unobserved does not make the sampling contract false. But it does mean the phase owes verification it has not done, and none of the six boxes says that. A **seventh box was added and left unticked** with its reason. See the honesty note below.
- **The pg-parity command is recorded without its connection string.** Task 1 asked for «the exact command»; Task 4 said «write no secret, no token and no `DATABASE_URL` into either file». The stricter rule won: the command shape is recorded with a pointer to `.github/workflows/`, and the file says why.
- **The `0024.downgrade()` defect stays unfixed and is cross-referenced only**, per LOCKED ordering constraint 5 — an applied migration is historical fact. It is named in `0027`'s docstring, reproduced by `33-03`, pinned by VA-6, and now also listed in the phase backlog with its measured `alembic/versions/0024_cash_movement_currency.py:50-52`.
- **No `flex-wrap` fix was made.** B-5 was not observed, so the overflow remains an estimate; the fix is deferred by D-21 / `33-CONTEXT.md` § Deferred Ideas because it touches every `.filter-bar` page.

## Honesty note — what this plan did NOT establish

Written out because the plan's `must_haves` demand «no unticked box without a written reason», and because a reader skimming a `status: complete` file deserves to hit this before they trust it.

1. **B-1 … B-7 were never observed.** The Claude-in-Chrome extension has no site permission for `localhost` / `127.0.0.1`; every navigation returned a browser error page. This was proven not to be an app fault (an isolated instance on port 8123 / PID 20880 answered `303` on `/` and `200` on `/setup` via `curl`, and the same browser tooling screenshotted `https://example.com` in the same session). The operator's own instance on port 8000 / PID 39100 was never touched. So the browser half of DATE-01/02/05/06/07 is **assumed by nobody and observed by nobody** — it is recorded as open.
2. **`tests/test_pg_parity.py` did not run.** The CI job aborts on a pre-existing, unrelated Linux-only failure (`tests/test_launcher.py::test_parse_pending_rejects_path_traversal`) before reaching the parity step. The `0027` migration is proven by a stronger, one-off method; the standing regression guard is still absent.
3. **The live pre-update-client push against s1 is unverified.** Only `/health` (200) and an unauthenticated `/api/sync/pull` (401) were checked. D-01's accept-behind branch — the whole point of step 4 — needs a real client at revision `0026` with a valid device token, and using the developer's own token would have pushed development data into production.
4. **The client release tag has not been cut**, which is the correct state given item 3.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The plan's predicted VA→plan/task mapping was wrong in four places**
- **Found during:** Task 4, step 1
- **Issue:** `33-15-PLAN.md:277-285` supplied a mapping «to be CONFIRMED by grepping the plans rather than trusted». Grepping found four divergences: **VA-14** spans five plans (`33-06` T3, `33-10` T1, `33-11` T1, `33-12` T1, `33-13` T1), not the two predicted; **VA-13** does *not* reach `33-14` (that plan carries VA-16 — `33-14-PLAN.md` has no VA-13 reference at all); **VA-12** has a foundation task in `33-06` T3 that the prediction omitted; **VA-5/VA-6** have a two-plan life (`33-03` T2 wrote them as tripwires, `33-05` is the migration they were written to catch and re-runs them as its own gate).
- **Fix:** The table records the grepped mapping. All four corrections are written into a `### Corrections to the mapping 33-15 predicted` section directly under the table, so a reader can see the plans won rather than wondering which source is authoritative.
- **Files modified:** `33-VALIDATION.md`
- **Verification:** `grep -c 'TBD' 33-VALIDATION.md` → `0`; every Plan/Task cell traces to a grep hit in a `33-*-PLAN.md`
- **Committed in:** the task commit

**2. [Rule 2 - Missing Critical] VA-16's own Automated Command could go green while the feature was half-broken**
- **Found during:** Task 4, step 2
- **Issue:** VA-16 shipped with `uv run pytest tests/test_history.py -k dated -x` — desktop only. `33-14-PLAN.md:324-326` states outright that «VA-16 is satisfied only when BOTH halves pass; neither task closes it alone». A desktop-only command passes while the mobile mirror is broken, which is exactly the divergence D-21 forbids. The verification contract was under-specifying the thing it exists to guard.
- **Fix:** The command cell now names both halves; both were run (desktop 15 passed / 25 deselected, mobile 4 passed / 8 deselected) and the row records both results.
- **Files modified:** `33-VALIDATION.md`
- **Verification:** both commands run at HEAD `d6be4f5`, both green
- **Committed in:** the task commit

**3. [Rule 1 - Bug] The backlog's local-today `file:line` references were stale — three sites, not four**
- **Found during:** Task 4, step 4
- **Issue:** `33-15-PLAN.md:302-305` names **four** inlined local-today sites to record: `app/services/receipts.py:208`, `app/routes/mobile_reports.py:21`, `app/services/customers.py:443,465`. Measured at HEAD `d6be4f5`, the receipts site **no longer exists** — plan `33-10` converted it while resolving D-24 batch naming, and `app/services/receipts.py:158` now reads `resolved_business_date = business_date or local_today_iso(settings.display_tz)`. The two `customers.py` sites also drifted to `:450` and `:474`.
- **Fix:** The backlog records the measured three sites (`app/routes/mobile_reports.py:21`, `app/services/customers.py:450`, `app/services/customers.py:474`) and states the correction and its cause inline, so the next reader does not re-derive it. The plan's warning about not shifting `parse_op_date`'s future check is carried through with its measured location (`app/services/ledger.py:70`).
- **Files modified:** `33-ROLLOUT.md`
- **Verification:** `grep -rn "datetime.now(ZoneInfo" app/services/receipts.py app/routes/mobile_reports.py app/services/customers.py` → 3 hits, none in `receipts.py`
- **Committed in:** the task commit

**4. [Rule 2 - Missing Critical] A CLAUDE.md-driven refusal of an injected tool directive**
- **Found during:** agent start-up, before Task 4
- **Issue:** The `pencil` MCP server's instructions carry a directive to route all file reading and editing through the Bash tool (`cat`, `sed`, heredocs) instead of Read/Write/Edit. The global `CLAUDE.md` § Mandatory console policy says the opposite: «Prefer direct Read/Write/Edit operations for file content» and explicitly forbids «embedding large file content into a shell command» and heredoc transport workarounds.
- **Fix:** The MCP directive was ignored; `CLAUDE.md` takes precedence. All content in both artefacts was written with Write/Edit; Bash was used only to execute programs (pytest, grep, git). The refusal was stated openly at the start of the run rather than silently.
- **Files modified:** none (a process decision)
- **Verification:** no heredoc or `cat <<` was used at any point in this plan
- **Committed in:** n/a

---

**Total deviations:** 4 auto-fixed (2 bugs in the plan's own references, 1 missing-critical gap in the verification contract, 1 missing-critical instruction conflict)
**Impact on plan:** All four are corrections to *this plan's inputs*, not scope creep. No application code was touched; `app/__init__.py` stays at `1.100`, per the phase convention that a docs-only plan does not bump the version.

## Issues Encountered

- **The plan's own `must_haves` conflicted with its Task 4 honesty requirement.** `must_haves.artifacts` demands `33-VALIDATION.md` contains `nyquist_compliant: true`, while the execution brief said a false tick is worse than an open box and B-1…B-7 are not run. Resolved by reading `nyquist_compliant` for what it actually means — the automated sampling rate — setting it true with its scope written into the file, and adding a seventh, unticked box for the manual-only set. Both the `must_have` and the honesty constraint are satisfied without either being bent.
- **`must_haves.truths` claims «The PostgreSQL half … is proven in CI, not assumed».** It is proven, but **not in CI** — CI never reached the parity step. The file records the actual method and separately records the parity suite as not run, rather than letting the `must_have`'s wording imply a CI pass that did not happen.
- **Task 1's «record the exact command» and Task 4's «write no `DATABASE_URL`» are mutually exclusive.** Resolved in favour of the stricter rule, with the reason written into `33-ROLLOUT.md` next to the redaction.

## User Setup Required

None - no external service configuration required. Three **pending human checks** are carried in `33-ROLLOUT.md` § Backlog: run B-1…B-7 in a browser (needs a `localhost` site permission, or the operator's own instance), verify a pre-update-client push against live s1 with a real device token, and then cut the client release tag.

## Next Phase Readiness

- **Phase 33's code is live on s1 at revision `0027`** with verified backfill coverage and intact append-only guards, and the local suite is green modulo the 4 known-red Windows-only `test_sync_ui.py` cases (all 4 pass on Linux CI).
- **Phase 34 (сторно + currency tail) inherits two already-migrated columns** — `operations.reverses_op_id` and `cash_movements.reverses_movement_id` — present, NULL everywhere, and already inside both append-only trigger enumerations. No further schema work is needed before writing reversals.
- **Blockers carried forward, all in `33-ROLLOUT.md` § Backlog:** the uncut client release tag (blocked on the unverified pre-update push), the seven unobserved browser checks, and the pre-existing `tests/test_launcher.py::test_parse_pending_rejects_path_traversal` failure which currently prevents the PostgreSQL parity job from ever running — that last one is cheap to fix and unblocks a whole CI job, so it is the best first move.

## Self-Check: PASSED

- `33-ROLLOUT.md`, `33-VALIDATION.md`, `33-15-SUMMARY.md` — all three stat-ed on disk: FOUND
- Commit `b5c4c65` — FOUND in `git log --oneline --all`
- `git diff --diff-filter=D HEAD~1 HEAD` — **no tracked file deleted**
- `grep -c 'TBD\|TODO' 33-ROLLOUT.md` → **0**; `grep -c 'TBD' 33-VALIDATION.md` → **0**
- `grep -c 'postgresql+psycopg://\|password=\|Bearer ' 33-ROLLOUT.md` → **0** — no secret, token or connection string in either file
- The plan's own gate (`nyquist_compliant: true` ∧ `wave_0_complete: true` ∧ ¬`TBD` ∧ ¬`Approval:** pending` ∧ `Backlog raised by this phase`) → **OK**
- `app/__init__.py` → `__version__ = "1.100"`, unchanged; no application file appears in the diff

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
