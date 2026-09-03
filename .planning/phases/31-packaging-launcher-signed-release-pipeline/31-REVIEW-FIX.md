---
phase: 31-packaging-launcher-signed-release-pipeline
fixed_at: 2026-09-03T00:00:00Z
review_path: .planning/phases/31-packaging-launcher-signed-release-pipeline/31-REVIEW.md
iteration: 1
findings_in_scope: 15
fixed: 15
skipped: 0
status: all_fixed
---

# Phase 31: Code Review Fix Report

**Fixed at:** 2026-09-03
**Source review:** `.planning/phases/31-packaging-launcher-signed-release-pipeline/31-REVIEW.md`
**Iteration:** 1
**Base commit:** `0cf32e0` (`docs(31): add code review report`)

**Summary:**

- Findings in scope: **15** (CR-01..CR-03, WR-01..WR-12) — ALL findings
- Fixed: **15**
- Skipped / adjudicated as false positives: **0**
- Commits: 14 fix commits + 1 lint follow-up
- `__version__` 1.59 → 1.60 (one bump for the whole review-fix task, in the CR-01 commit)

> Note on the review's own frontmatter: it declares `warning: 11 / total: 14`, but the
> body carries WR-01..WR-12 — twelve warnings, fifteen findings. The body is
> authoritative and all twelve were addressed.

---

## Verification

| Gate | Result |
|------|--------|
| `uv run pytest tests/test_launcher.py tests/test_packaging.py -q` | **43 passed** (0 skipped — the two real-artifact gates RAN against the freshly built dist) |
| `uv run pytest -q` (full suite) | **1484 passed, 13 skipped, 0 failed** in 385 s |
| `uv run ruff check launcher build_release.py` | `All checks passed!` |
| `uv run ruff check tests/test_packaging.py` | `All checks passed!` |
| `uv run ruff check tests/test_launcher.py` | 3 errors — byte-for-byte the PRE-EXISTING 31-01 scaffold findings (`B017`, `E501`, `UP031`) logged in `deferred-items.md`. No new finding on any line touched here. |

**The 4 documented pre-existing `tests/test_sync_ui.py` failures and the order-dependent
`test_offline.py::test_login_rate_limited` did NOT reproduce in this run.** They are
thread-timing dependent (`sync_client._run_lock` held by the lifespan auto-sync thread);
this run happened not to hit the race. They are not counted as fixed — nothing here
touches the sync path.

Passing-count arithmetic against the 31-08 baseline (`4 failed, 1465 passed, 14 skipped`):
1465 + 14 new tests + 4 no-longer-racing sync_ui tests + 1 skip-gate that flipped to RUN
(`test_real_launcher_runtime_resolves_the_sibling_package`, now that `dist/launcher/` is
built) = **1484**. Exact.

### Isolation

All work was done in a dedicated git worktree
(`C:\Users\Admin\AppData\Local\Temp\sv-31-reviewfix-oCWvTe`, branch
`gsd-reviewfix/31-1090`) so nothing raced the foreground session's index or working tree.
The commits were fast-forwarded onto `main` at the end.

**No server was started and no port was bound.** The CR-01 proof runs
`app\python.exe -c "import app.main …"` and `-m alembic upgrade head` as short-lived
child processes; it never binds a socket. Port 8000 was not touched.

---

## CR-01 proven against a REAL artifact

The review's headline defect. `_zip_onedir` wrote members relative to `dist\`, so the
published zip had two top-level dirs; Phase 32 extracts that archive verbatim into
`install_root\staged` and `apply_update` renames the whole `staged\` **onto** `app\`,
producing `app\app\python.exe` and no `app\python.exe`.

A fresh `uv run python build_release.py --version v1.60` was run in the worktree and the
resulting archive was driven through the real chain — extract into `staged\`, real
`apply_update`, then execute the swapped runtime.

Built archive:

```
dist/MyOriShop-1.60.zip   27,377,485 bytes   members: 2586
top-level: {'python.exe': 1, 'python313.dll': 1, 'python313.zip': 1, 'python313._pth': 1,
            'Lib': 2248, 'app': 273, 'alembic': 29, 'alembic.ini': 1, 'minisign.pub': 1,
            'pythonw.exe': 1, 'sqlite3.dll': 1, ... }
python.exe in root:     True
any launcher/ member:   False
first entries: ['_asyncio.pyd', '_bz2.pyd', '_ctypes.pyd', '_decimal.pyd']
```

(Compare the review's measurement of the shipped `dist/MyOriShop-1.59.zip`:
`top-level: {'app': 2586, 'launcher': 38}`, `first entries: app/_asyncio.pyd, …`.)

Extract → real swap → run:

```
archive: MyOriShop-1.60.zip  (27,377,485 bytes)
staged\python.exe exists after extract: True
staged\app\  exists after extract:     True
--- after the real swap ---
app\python.exe exists:       True
app\app\python.exe exists:  False (the CR-01 bug)
app\OLD.txt gone (swapped):  True
app.prev\ removed:           True
import probe rc: 0
RUNNABLE app 1.60 | sqlalchemy 2.0.51 | fastapi 0.139.0 | 3.13.1
alembic upgrade head rc: 0
INFO  [alembic.runtime.migration] Running upgrade 0025 -> 0026, cash_movements_no_update: guard the new currency column (CUR-02)
data\myorishop.db created: True
```

So the swapped `app\` is a genuinely runnable bundle: it imports `app.main` with the whole
vendored dependency graph and runs `alembic upgrade head` to head against an empty data
dir. That is the happy path the review showed was unreachable.

**The regression is built from the real shape, not a hand-built fixture.**
`tests/test_packaging.py::test_release_archive_extracts_into_a_runnable_app_dir` runs
`assemble_onedir` → `_zip_onedir` → `extractall` into `staged\` → `apply_update`. Proven
RED against the old `_zip_onedir`:

```
E  AssertionError: the archive root is not the app dir — the swap renames staged\ ONTO app\,
   so python.exe must be a top-level member;
   got ['app/alembic/env.py', 'app/alembic/README', ...]
```

---

## Fixed Issues

Every fix below was proven RED against the pre-fix code before being committed (the RED
output is quoted in each commit message).

### CR-01: Release archive layout contradicts the swap contract

**Files:** `build_release.py`, `tests/test_packaging.py`, `app/__init__.py`
**Commit:** `723e9ff`
**Applied fix:** `_zip_onedir` now zips the contents of `dist\app` at the archive ROOT and
excludes `launcher\` entirely (installer-only payload — the swap never applies it, WR-11).
New end-to-end regression `test_release_archive_extracts_into_a_runnable_app_dir`.
`__version__` 1.59 → 1.60.

The review's alternative — teaching `apply_update` a two-subdir staged shape so the
launcher becomes field-updatable — was **not** taken: the review itself calls it a larger
design change that should not be decided inside a bug fix. It is recorded as an open
roadmap question in `deferred-items.md`.

### CR-02: A non-UTF-8 `pending.json` escapes `run_once` uncaught

**Files:** `launcher/__main__.py`, `tests/test_launcher.py`
**Commit:** `75d49b9`
**Applied fix:** `marker.read_text()` moved inside the `try`. `ValueError` (which
`UnicodeDecodeError` is) → quarantine; `OSError` → `return False` **without** consuming, so
a marker that is merely being written is retried rather than destroyed. Two regressions
(undecodable marker, torn marker).

### CR-03: The migration-abort message is not visible to the operator

**Files:** `launcher/__main__.py`, `build_release.py`, `tests/test_launcher.py`
**Commit:** `57936fd` (with WR-02)
**Applied fix:** new `_hold_console()` — run.bat's `pause`, guarded by
`sys.stdin.isatty()` so CI/tests stay non-blocking and swallowing any failure so a broken
prompt cannot change the exit path. The abort message is now Russian
(«Миграция не выполнена — сервер не запущен: …»), matching every other operator-facing
string. `generate_iss`'s docstring, which asserted the false "only place the operator
sees the abort" claim as the justification for a console window, now states the real
mechanism.

### WR-01: `stop_app()` outside the guarded region

**Files:** `launcher/swap.py`, `tests/test_launcher.py`
**Commit:** `fa84558`
**Applied fix:** the stop moved inside the `try`, so a `PermissionError` from
`terminate()` now goes through the rollback and `_best_effort(start_app)`.
RED evidence: `events == ['stop']`, `start_app` never called.

### WR-02: The watch-loop message asserts a state the code does not guarantee

**Files:** `launcher/__main__.py`, `tests/test_launcher.py`
**Commit:** `57936fd` (with CR-03 — both are the operator-facing prints in `main()`, and
the orchestrator's priority order groups them; splitting them would have meant a commit
whose own test was failing)
**Applied fix:** «Обновление не применено: {exc}» — the failure is reported without
claiming a recovery state, so `swap.py`'s own «Откат неполный…» line is no longer
contradicted on the next line.

### WR-03: A torn read silently deletes a valid in-flight marker

**Files:** `app/services/update.py` (producer), `launcher/__main__.py` (consumer),
`tests/test_launcher.py`
**Commits:** `d5745f2` (producer), consumer half in `75d49b9`
**Applied fix:** both halves, as the review recommended. Producer: `stage_pending` writes
`pending.json.partial` and `os.replace`s it in (atomic on NTFS). Consumer: quarantine
instead of `unlink`. The producer regression keys its `os.replace` patch on the
**destination argument**, not a counter — the same discipline WR-12 asks for.

### WR-04: The rollback restores the DB even when `stop_app` failed

**Files:** `launcher/swap.py`, `tests/test_launcher.py`
**Commit:** `e042549`
**Applied fix:** the rollback's own stop records a `stopped` flag; the DB half now requires
`migrate_attempted and stopped`, otherwise it prints «БД не откачена: приложение не
удалось остановить — восстановите резервную копию вручную».

Deliberate deviation from the review's snippet: `stopped` is computed **in the handler**
rather than carried from the forward path. What matters at the moment of
`shutil.copy(backup, db)` is whether the app is stopped *now* — and on the health-check
path `start_app()` has run since the forward stop, so the forward flag would have been the
wrong answer.

### WR-05: `pending.staged_dir` validated and confined but never used

**Files:** `launcher/__main__.py`, `tests/test_launcher.py`
**Commit:** `a04ad48`
**Applied fix:** the review offered two options; the **equality gate** was chosen over
consuming the field. `run_once` now requires
`Path(pending.staged_dir) == Path(paths.staged).resolve()` and quarantines otherwise.
Rationale: consuming the field would give `apply_update` two possible sources of truth for
the path it renames, while the equality gate makes `parse_pending`'s confinement
load-bearing at zero behavioural cost — both the hand-placed Phase-31 marker and Phase
32's `stage_pending` write literally `"staged"`. `db_backup_path` IS consumed, so its
confinement was left untouched. The two existence checks collapse into one now that the
paths are provably identical.
RED evidence: `apply_update was entered on a mismatched marker` (a marker naming `data`).

### WR-06: Rollback and quarantine keyed on `except Exception`

**Files:** `launcher/swap.py`, `launcher/__main__.py`, `tests/test_launcher.py`
**Commit:** `eb6cebf`
**Applied fix:** both handlers catch `BaseException` and still re-raise. The best-effort
rollback steps keep catching `Exception` only, so an interrupt *during* the rollback still
propagates instead of being swallowed. One regression drives a `KeyboardInterrupt` from
`migrate()` through `run_once`, covering both guards.
RED evidence: with `except Exception`, `app\` was left holding the staged v2 code.

### WR-07: `generate_iss(dist_dir=...)` is a dead parameter

**Files:** `build_release.py`, `tests/test_packaging.py`
**Commit:** `9392df0`
**Applied fix:** made authoritative — `ValueError` unless `dest.parent` resolves to
`dist_dir`, raised before anything is written. The function's own unit test, which passed
a mismatched pair and still passed (the tell the review identified), now generates INTO
`dist_dir` the way the shipped CLI path already does.

### WR-08: delete-partial-on-failure misses the launcher

**Files:** `build_release.py`, `tests/test_packaging.py`
**Commit:** `7967e92`
**Applied fix:** the handler also removes `dest.parent / "launcher"`. `assemble_onedir`
already owns that directory (`assemble_launcher_runtime` wipes and rebuilds it), so this
extends existing ownership to the failure path rather than adding a new one. The
regression forces the step-6 migration-count gate by patching `_version_files` to shorten
only the BUNDLED count.

### WR-09: Installer leaves swap residue and pins no `AppId` / `ignoreversion`

**Files:** `build_release.py`, `tests/test_packaging.py`
**Commit:** `bc848af`
**Applied fix:** all three sub-items. `AppId={{1BF2D689-291E-4E44-B502-BC4EAEBE4C32}`
(one uuid4, hard-coded and documented as never-regenerate), `ignoreversion` on both
`[Files]` entries, and a `[UninstallDelete]` block sweeping `app.prev` / `app.failed` /
`staged` — with `data\` deliberately absent and that asserted by the test.

The emitted script was verified by generating and parsing it (the `AppId` line comes out
Inno-escaped as `{{GUID}`). It was **not** compiled: `iscc` is not installed here. See
"Pending human checks".

### WR-10: `EMBEDDABLE_SHA256`'s comment contradicts the code

**Files:** `build_release.py`
**Commit:** `bf5f519`
**Applied fix:** comment rewritten to describe the real control (a version absent from the
map is refused) and the real provenance (python.org MD5 match, SHA-256 self-computed from
that same download — a download-integrity pin, not a publisher attestation), with the
upgrade path recorded. `fetch_embeddable`'s docstring carried the same overstatement and
was corrected to point at the map's note. Comment-only; no behaviour change.

### WR-11: The launcher can never be updated in the field

**Files:** `launcher/__init__.py`, `docs/RELEASE.md`, `deferred-items.md`
**Commit:** `1d21dfc`
**Applied fix:** the constraint is written where it will be seen — the launcher package
docstring ("treat every change in this package as a re-install-required change"), and a
`docs/RELEASE.md` callout telling the release author to check `git log -- launcher/`
before writing the notes. `deferred-items.md` records the still-open design question.

**Deliberately not done:** the roadmap item. Roadmap edits belong to the planning workflow,
not a code fixer; the item is parked in the phase's own `deferred-items.md` instead, which
is the mechanism this phase already uses for exactly this.

### WR-12: process-wide `os.replace` patch gated on a call counter

**Files:** `tests/test_launcher.py`
**Commit:** `5845645`
**Applied fix:** the failure is selected by the destination argument (the
`app\ → app.prev\` rename) instead of `len(calls) == 1`. Newly relevant: this review-fix
made `update.stage_pending` itself call `os.replace`.

Honest caveat recorded in the test docstring: `launcher.swap.os` **is** the stdlib `os`
module object, so writing the patch target that way does not narrow the patch scope. The
argument keying — not the patch target — is what removes the fragility.

---

## Skipped Issues

None. Every finding was actionable; none was a false positive.

---

## Deviations from the review's suggested fixes

Recorded so the next reader does not have to diff the patches against the review:

1. **WR-04** — `stopped` is recomputed in the rollback handler, not threaded from the
   forward path (see above: `start_app()` may have run in between).
2. **WR-05** — the equality gate was chosen over consuming `pending.staged_dir`, keeping
   one source of truth for the path `apply_update` renames.
3. **CR-03 + WR-02** share one commit (both are `main()`'s operator-facing prints;
   splitting them would have produced a commit whose own regression was red).
4. **WR-11** — no roadmap item written; parked in `deferred-items.md` instead.
5. The CR-01 regression asserts `not (app_dir/"app"/"python.exe").exists()` rather than
   `not (app_dir/"app").exists()`: `app\app\` IS the FastAPI package (`app\app\main.py`)
   and legitimately exists. A nested **runtime** there is the CR-01 signature.

---

## Pending human checks

These cannot be run here and are NOT claimed as verified:

- **`iscc` compile + a real uninstall (WR-09).** Inno Setup is not installed on this box.
  The `.iss` was emitted and parsed, not compiled. Confirm `iscc dist\MyOriShop.iss`
  succeeds, then install → self-update → uninstall and check that `app.prev\`,
  `app.failed\` and `staged\` are gone while `data\` survives.
- **The held-open console on a real Start-Menu shortcut (CR-03).** Verified in-process
  (the prompt fires on a tty, never otherwise); observing the actual shortcut-spawned
  console staying open needs an installed copy.
- **A real end-to-end self-update (CR-01).** Proven here down to "the swapped `app\` runs
  and migrates". The remaining machine-level step is Phase 32's
  download → verify → stage → launcher-driven swap on an installed copy.
- The four items already in `31-UAT.md` (bare-Windows install + SmartScreen, live launcher
  swap, offline minisign keygen, a real pipeline run) are unchanged.

## Notes for the next build

- **`dist\` in the main working tree is stale**: it still holds `MyOriShop-1.59.zip` with
  the broken two-top-level-dir layout, plus a `dist\app` / `dist\launcher` built before
  these fixes. Rebuild before releasing — that archive must never be published.
- `vendor_wheels` shells out to `sys.executable -m pip`, and a `uv sync`-created venv has
  no `pip`. On a fresh checkout the build needs `uv pip install pip` first. Not changed
  here (out of scope), but it will bite the next person who builds from a clean worktree.

---

_Fixed: 2026-09-03_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
