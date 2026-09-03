---
phase: 31-packaging-launcher-signed-release-pipeline
reviewed: 2026-09-03T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - launcher/__main__.py
  - launcher/swap.py
  - launcher/adapters.py
  - launcher/__init__.py
  - build_release.py
  - tests/test_launcher.py
  - tests/test_packaging.py
findings:
  critical: 3
  warning: 11
  info: 0
  total: 14
status: issues_found
---

# Phase 31: Code Review Report

**Reviewed:** 2026-09-03
**Depth:** standard (diff `5d8958c..HEAD`, plans 31-06/31-07/31-08)
**Files Reviewed:** 7
**Status:** issues_found

## Summary

The gap-closure diff is genuinely better than what it replaced. The three specific
UAT defects it targeted are, mechanically, addressed:

- **GAP-1** — `boot()` calls `migrate(paths)` before `app_process.start()`; the
  exception propagates and `start()` is provably never reached
  (`launcher/__main__.py:171-172`). `alembic/env.py:28-32` really does create the
  sqlite parent dir, so the "no `mkdir` belongs here" claim holds.
- **GAP-3** — the pre-flight `staged\` check sits before `stop_app`, both
  `os.replace` calls are inside the guarded region, all four directory renames
  clear their destination first, the DB restore is gated on `migrate_attempted`,
  and the marker is quarantined on the `apply_update` failure path. I traced every
  rename/rollback branch and could not find a state where a *failed migrate* or a
  *failed health check* leaves the install without a usable `app\`.
- **GAP-2** — `dist\launcher\python.exe` is really built and the `.iss` really
  points at it (verified by generating the script and by listing the local
  `dist\`).

`pytest tests/test_launcher.py tests/test_packaging.py -q` → **29 passed** on this
box (both "skip-gated" real-dist tests actually ran, since `dist\` is populated).

That is where the good news stops. Three defects below break stated acceptance
criteria, two of them empirically reproduced in this session:

1. The **shipped release archive layout does not match the swap contract**. The
   published zip has *two* top-level dirs (`app/`, `launcher/`); the launcher
   renames `staged\` wholesale onto `app\`. A staged release therefore produces
   `app\app\python.exe` and no `app\python.exe`. GAP-2's premise — "a *successful*
   update can delete `app.prev\`" — is untestable because a successful update is
   currently impossible. It fails *safe* (rollback fires), but it fails every time.
2. A **non-UTF-8 `pending.json` escapes `run_once` uncaught**, so the marker is
   neither consumed nor quarantined and the 2-second watch loop replays the same
   failure forever — the exact invariant GAP-3 claims to have closed, on the exact
   input class T-31-04 declares untrusted.
3. The **GAP-1 abort message is not visible**. `run.bat` has `pause`; the launcher
   prints to stderr and immediately `SystemExit(1)`, which closes the shortcut's
   console window. The code comments assert the opposite.

Beyond those, the rollback has a swallowed-`stop_app` hole that can overwrite a
live SQLite file, `stop_app()` itself sits outside the guarded region, and the
`.iss` generator carries a dead `dist_dir` parameter that its own test proves is
ignored.

`launcher/adapters.py` and `launcher/__init__.py` are unchanged; they are cited
only where the new code's correctness depends on them.

## Critical Issues

### CR-01: The release archive's layout contradicts the swap contract — every self-update stages a bundle the launcher cannot run

**File:** `build_release.py:466-484` (`_zip_onedir`) ⇄ `launcher/swap.py:138` (`os.replace(paths.staged, paths.app)`)
**Also involves:** `app/services/update.py:399-415` (`_extract_guarded(archive, install_root/"staged")`), `.github/workflows/release.yml:79-88` (publishes `dist/MyOriShop-*.zip` verbatim)

**Issue:**
`_zip_onedir` writes members with `path.relative_to(dist_dir)`, where `dist_dir`
contains **both** `app\` and `launcher\`. Verified against the locally built
artifact:

```
dist/MyOriShop-1.59.zip -> members: 2624, top-level: {'app': 2586, 'launcher': 38}
first entries: app/_asyncio.pyd, app/_bz2.pyd, ...
```

Phase 32's `update.apply` extracts that archive verbatim into
`install_root/staged`, so `staged\` becomes `{staged\app\, staged\launcher\}`.
`apply_update` then does `os.replace(paths.staged, paths.app)` — the whole
`staged\` dir *becomes* `app\`. Result on the operator's box:

- `app\app\python.exe` exists; `app\python.exe` does **not**
- `adapters.migrate` (`Path(paths.app)/"python.exe"`) raises `FileNotFoundError`
- the matched-pair rollback fires, restores `app\`, quarantines the marker

So the install is not bricked, but **no self-update can ever succeed**, and the
GAP-2 guarantee under review ("so a successful update can delete `app.prev\`") is
vacuous — the happy path it protects is unreachable. Nothing in the test suite
covers archive-layout ⇄ staged-swap agreement; `test_launcher.py` hand-builds a
`staged\` whose contents are already the app-root shape, which is precisely the
shape the real archive does *not* have.

This mismatch predates the reviewed diff (the pre-31-08 zip also had a
`launcher/` top level), but 31-08 is the change that made `dist\launcher\` a full
15 MB runtime and cemented the two-top-level-dir archive, and the phase claims to
close GAP-2.

**Fix:** Make the archive root *be* the future `app\`, and treat the launcher as
installer-only payload (it is never applied by the swap anyway — see WR-11):

```python
def _zip_onedir(dist_dir: Path, version: str) -> Path:
    """Zip the assembled app\\ so the archive ROOT is what staged\\ must become.

    launcher\\ is deliberately excluded: the swap renames staged\\ -> app\\, so a
    `launcher/` member would land at app\\launcher\\ and push python.exe one level
    down. The launcher is shipped by the .iss only.
    """
    dist_dir = Path(dist_dir)
    archive = dist_dir / f"MyOriShop-{version}.zip"
    tmp = archive.with_suffix(".zip.partial")
    root = dist_dir / "app"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(root).as_posix())
        tmp.replace(archive)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return archive
```

Add a regression that pins the contract end to end, e.g. in
`tests/test_packaging.py`:

```python
def test_archive_root_is_the_future_app_dir(tmp_path):
    """The launcher renames staged\\ ONTO app\\, so python.exe must sit at the
    archive ROOT — not under an app/ member."""
    import build_release
    build_release.assemble_onedir(...)          # as in the other tests
    archive = build_release._zip_onedir(tmp_path / "dist", "1.59")
    names = zipfile.ZipFile(archive).namelist()
    assert "python.exe" in names, "archive root is not the app dir"
    assert not any(n.startswith("launcher/") for n in names)
```

If the launcher must instead be updatable in-field, the alternative fix is to
teach `apply_update` the two-subdir shape (`staged\app` → `app\`, `staged\launcher`
→ staged launcher swap on next boot) — but that is a larger design change and
should not be decided inside a bug fix.

---

### CR-02: A non-UTF-8 `pending.json` escapes `run_once` uncaught — the marker is never consumed and the watch loop replays it forever

**File:** `launcher/__main__.py:106-112`

**Issue:**
`raw = marker.read_text(encoding="utf-8")` is on line 106, **outside** the
`try:` that starts on line 107. `UnicodeDecodeError` is a `ValueError` subclass,
so it *would* have been handled had the read been inside the guard — but it is
not. Reproduced in this session:

```
1) ESCAPED: UnicodeDecodeError 'utf-8' codec can't decode byte 0xff in position 0
   marker still there: True | quarantined: False
```

Consequence: the exception unwinds through `run_once` to `main()`'s watch-loop
`except Exception`, which prints «Обновление не применено…» and sleeps 2 s — then
reads the same bytes again. Forever. Neither the `unlink` (invalid-marker) path
nor `_quarantine_marker` (failed-apply) path is reached, because both live below
the failing line. This is exactly the invariant the docstring on lines 95-98
claims to have closed ("The marker is ALWAYS consumed … can therefore never be
replayed by `main()`'s 2-second watch loop").

Trigger is not theoretical: Phase 31's documented workflow is *hand-placing*
`pending.json` (a cp1251-saved file with a Russian path does it), and T-31-04
explicitly treats the marker as attacker-controlled — anyone who can write
`data\pending.json` can permanently wedge the update channel and flood stderr.
`OSError` from the same call (Windows sharing violation while the app is writing
the marker) escapes identically.

**Fix:** Move the read inside the guard and treat any unreadable marker like an
invalid one:

```python
    marker = Path(paths.data) / _MARKER_NAME
    if not marker.exists():
        return False

    try:
        pending = parse_pending(marker.read_text(encoding="utf-8"), paths.install_root)
    except ValueError:
        # Invalid/undecodable marker: never act on it — quarantine, keep running.
        _quarantine_marker(marker)
        return False
    except OSError:
        # Transient (marker being written): retry on the next tick, do not consume.
        return False
```

Note the deliberate change from `unlink` to `_quarantine_marker` for the invalid
case — see WR-03, which depends on the same line.

---

### CR-03: The migration-abort message is not actually visible to the operator — the console closes on `SystemExit(1)`

**File:** `launcher/__main__.py:180-183`; contract asserted in `build_release.py:336-342`

**Issue:**
GAP-1 requires "a failing migration aborts boot with a **visible message** and
non-zero exit". `run.bat` gets this right:

```bat
uv run alembic upgrade head
if errorlevel 1 (
  echo Migration failed - server not started.
  pause
  exit /b 1
)
```

The launcher prints to `stderr` and immediately raises `SystemExit(1)`. The
Start-Menu shortcut targets `{app}\launcher\python.exe` (a console-subsystem
binary), so Windows allocates a console for the process and destroys it the
instant the process exits. The operator sees a window flash and nothing else: the
app "just doesn't start", with no diagnostic anywhere on disk either (nothing is
logged to a file). `generate_iss`'s docstring asserts the opposite — "`python.exe`
(console), not `pythonw.exe`, is deliberate: it **is the only place the operator
sees** the «Migration failed - server not started» abort" — which is a false claim
about the shipped behaviour, and it is the stated justification for a console
window on every normal launch.

Secondary: the message is English while every other operator-facing string in
this module (`launcher/__main__.py:193-195`, `launcher/swap.py:169-171`) is
Russian, contrary to the project's UI-language convention.

**Fix:** Hold the console open on the abort path (and only there), and match the
project's language:

```python
    try:
        boot(paths, app_process)
    except Exception as exc:
        # run.bat parity: report, HOLD the console open (a shortcut-spawned
        # console dies with the process), and exit non-zero WITHOUT serving.
        print(f"Миграция не выполнена — сервер не запущен: {exc}", file=sys.stderr)
        if sys.stdin is not None and sys.stdin.isatty():
            input("Нажмите Enter, чтобы закрыть окно...")
        raise SystemExit(1) from exc
```

The `isatty()` guard keeps `main()` non-blocking under CI/tests. Add a regression
asserting the abort path does not return before the operator is prompted (patch
`builtins.input`), or at minimum extend
`test_main_boots_through_migration_before_the_watch_loop` to cover the failing
`boot`.

## Warnings

### WR-01: `stop_app()` sits outside the guarded region — a stop failure skips the entire rollback and leaves the app stopped

**File:** `launcher/swap.py:121` (call) vs `125` (`try:`)

**Issue:** `stop_app()` is the last statement before the `try`. Reproduced:

```
raised: PermissionError
events: ['stop'] -> start_app called: False
```

`adapters.AppProcess.stop` can raise for real on Windows: `Popen.terminate()`
re-raises `PermissionError` when `TerminateProcess` fails on a still-`STILL_ACTIVE`
process, and `wait(timeout)` can raise beyond `TimeoutExpired`. Worse,
`AppProcess.stop`'s `finally: self.proc = None` (`launcher/adapters.py:82-83`)
drops the child handle *even when terminate raised* — so the launcher loses
ownership of a still-running server. Two bad outcomes:

- terminate failed, app alive: `main()`'s `finally: app_process.stop()` is now a
  no-op, the orphan keeps serving old code on 8000, and the next launch cannot
  bind — the precise "stale server" problem `run.bat` needed a `netstat` hack for
  and that `AppProcess`'s docstring claims to have eliminated.
- app died but `wait` raised: nothing restarts it; the watch loop spins forever
  against a dead app.

**Fix:** Bring the stop inside the guarded region and record whether it succeeded,
so the rollback can both restart and (see WR-04) decide about the DB:

```python
    prev_renamed = staged_swapped = migrate_attempted = stopped = False
    try:
        stop_app()
        stopped = True
        shutil.rmtree(paths.app_prev, ignore_errors=True)
        ...
```

and in the `except`, keep `_best_effort(start_app)` as-is — it then also covers the
stop-failed case.

---

### WR-02: The watch loop's error message asserts a state the code does not guarantee

**File:** `launcher/__main__.py:192-196`

**Issue:** Every exception out of `run_once` is reported as «Обновление не
применено, приложение работает на прежней версии». That is false in at least two
reachable states: (a) the WR-01 stop-failure path, where the app was never
restarted; (b) the documented double-fault branch in `swap.py:165-172`, where
`app\` deliberately keeps the **bad** code and `app.prev\` holds the good one — the
swap module prints its own «Откат неполный…» line, and then `main()` immediately
contradicts it. An operator reading only the last line will believe the install is
healthy.

**Fix:** Report the failure without asserting the recovery state, and let
`swap.py`'s own stderr lines carry the state:

```python
                print(f"Обновление не применено: {exc}", file=sys.stderr)
```

---

### WR-03: A torn read of `pending.json` silently deletes a valid, in-flight marker — the staged update is lost with no error

**File:** `launcher/__main__.py:109-112`

**Issue:** `app/services/update.py:361` writes the marker with
`Path.write_text`, which truncates then writes — non-atomic. The launcher polls
every 2 s. A read landing in that window yields `""` or a prefix, `json.loads`
raises `JSONDecodeError` (a `ValueError`), and the handler calls
`marker.unlink(missing_ok=True)` — **deleting the marker the app just staged**.
Reproduced with a truncated file:

```
2) ran: False | marker deleted: True | quarantined: False
```

Aftermath: `staged\` is populated, a VACUUM DB backup was taken, the user clicked
«Обновить и перезапустить», and nothing happens — with no record anywhere of why.
The window is small (a few ms per update) but the failure is silent and
unrecoverable without a manual re-trigger.

**Fix (two halves, either alone shrinks the risk):**
- consumer: quarantine instead of destroy, so the evidence survives —
  `_quarantine_marker(marker)` in place of `marker.unlink(...)` (folded into the
  CR-02 patch above);
- producer: make `stage_pending` atomic —

```python
    tmp = marker.with_suffix(".json.partial")
    tmp.write_text(json.dumps({...}), encoding="utf-8")
    os.replace(tmp, marker)          # atomic on NTFS
```

---

### WR-04: The rollback restores the DB even when `stop_app` failed — `shutil.copy` over a live SQLite file risks corruption

**File:** `launcher/swap.py:147` + `173-174`, with `launcher/adapters.py:152-165`

**Issue:** The rollback opens with `_best_effort(stop_app)`, which **swallows** the
stop failure, and later runs `_best_effort(lambda: backup_restore(...))`
unconditionally on `migrate_attempted`. `backup_restore` does
`shutil.copy(backup_path, db_path)` and then unlinks `-wal`/`-shm`. On the
health-check-failure path the new app has *already been started*
(`swap.py:142-144`), so if the subsequent stop fails the DB file is overwritten
byte-for-byte underneath an open SQLite connection, and its WAL sidecars are
deleted out from under it. That is a data-corruption path in the very routine
whose docstring promises "code and DB revert together".

**Fix:** Gate the DB half on a confirmed stop (using the `stopped` flag from WR-01)
and surface the skip:

```python
        if migrate_attempted and stopped:
            _best_effort(lambda: backup_restore(pending.db_backup_path))
        elif migrate_attempted:
            print(
                "БД не откачена: приложение не удалось остановить — "
                "восстановите резервную копию вручную",
                file=sys.stderr,
            )
```

---

### WR-05: `pending.staged_dir` is validated and confined but never used — the confinement is decorative

**File:** `launcher/swap.py:189-219` (`parse_pending`) vs `launcher/swap.py:114,138` (`apply_update` uses `paths.staged`)

**Issue:** T-31-05 is described as confining `staged_dir` "BEFORE any `os.replace`",
but `apply_update` never receives or consults `pending.staged_dir` — it always
renames `paths.staged`. `run_once`'s docstring acknowledges the two paths "are NOT
the same path" and checks both for existence, which papers over the real issue: a
marker declaring `staged_dir: "data"` passes validation *and* the existence check,
and the launcher then swaps the unrelated `staged\` anyway. The field is a
decoration that reads like a security control, which invites a future caller to
trust it. (`db_backup_path` *is* consumed, so its confinement is load-bearing —
keep it.)

**Fix:** Either consume the field —

```python
        apply_update(
            replace(paths, staged=Path(pending.staged_dir)),   # dataclasses.replace
            pending,
            ...
        )
```

— or drop the pretence and require it to equal `paths.staged`:

```python
    if Path(pending.staged_dir) != Path(paths.staged).resolve():
        _quarantine_marker(marker)
        return False
```

---

### WR-06: Rollback and quarantine are keyed on `except Exception` — Ctrl+C / console-close mid-swap leaves the install half-swapped

**File:** `launcher/swap.py:145`, `launcher/__main__.py:133`

**Issue:** Both handlers catch `Exception`, not `BaseException`. The shipped
launcher is a **console** process (CR-03), so Ctrl+C and closing the window are the
normal ways an operator stops it — and `KeyboardInterrupt` raised between the two
`os.replace` calls, or during `migrate()`, bypasses the rollback entirely *and*
the marker quarantine. The install is left with `app\` = new code, `app.prev\` =
old code, an un-migrated schema, and a live `pending.json`. The next boot happens
to survive (the pre-flight refuses the marker because `staged\` is gone, and
`boot()` migrates), but `app.prev\` leaks permanently and the outcome is
accidental rather than designed.

**Fix:** Guard the swap window against `BaseException` while still re-raising it:

```python
    except BaseException:
        # KeyboardInterrupt / console-close mid-swap must roll back too.
        ...
        raise
```

and mirror it in `run_once`'s quarantine handler.

---

### WR-07: `generate_iss(dist_dir=...)` is a dead parameter, and correctness silently depends on `dest.parent == dist_dir`

**File:** `build_release.py:321-371`

**Issue:** The function body never references `dist_dir`. The generated `[Files]`
`Source:` paths are relative to the **`.iss` file's own directory** (Inno's
`SourceDir` default), i.e. to `dest.parent` — so passing a `dist_dir` that differs
from `dest.parent` produces a script that silently points at the wrong tree.
Proven: `generate_iss(dist_dir=<nonexistent>, dest=<tmp>/MyOriShop.iss)` succeeds
and emits a normal script. The function's own unit test
(`tests/test_packaging.py:284-286`) passes `dist_dir=tmp/dist` with
`dest=tmp/MyOriShop.iss` — mismatched — and still passes, which is the tell.

**Fix:** Either delete the parameter, or make it authoritative:

```python
def generate_iss(*, dist_dir: Path, version: str, dest: Path) -> Path:
    dest = Path(dest)
    if dest.parent.resolve() != Path(dist_dir).resolve():
        raise ValueError(
            "the .iss must be generated INTO dist_dir — [Files] Source paths are "
            f"relative to the script's own directory ({dest.parent}), not {dist_dir}"
        )
```

---

### WR-08: `assemble_onedir`'s delete-partial-on-failure does not clean the launcher it just built

**File:** `build_release.py:225-247`

**Issue:** `assemble_launcher_runtime` is invoked at step 5, *inside* the `try`;
the handler at 244-247 only does `shutil.rmtree(dest, ignore_errors=True)` — i.e.
`dist\app` — leaving a fully assembled `dist\launcher\` behind. The migration-count
gate at step 6 (the most likely failure in this block) fires **after** the launcher
exists, so the documented invariant "a half-written bundle is removed so it can
never pass for a valid one" is false for the launcher half. A rerun of `iscc
dist\MyOriShop.iss` against that residue would package a launcher with no app.

**Fix:**

```python
    except Exception:
        # Delete-partial-on-failure — BOTH halves of the install-root layout.
        shutil.rmtree(dest, ignore_errors=True)
        shutil.rmtree(dest.parent / "launcher", ignore_errors=True)
        raise
```

---

### WR-09: The generated installer leaves swap residue behind and pins no `AppId` / `ignoreversion`

**File:** `build_release.py:349-369`

**Issue:** Three under-specifications in a script whose whole job is a correct
per-user install:

1. No `[UninstallDelete]`. Inno removes only what it installed, so uninstalling
   leaves `{app}\app.prev\`, `{app}\app.failed\` and `{app}\staged\` — each a full
   ~30 MB bundle copy — plus `{app}` itself. `swap.py:110-112` states `app.failed\`
   is "deliberately RETAINED … until the NEXT rollback rotates it", so on a normal
   install it is retained forever, uninstall included. (`data\` staying is correct
   and must not be swept.)
2. No `AppId`. Inno falls back to `AppName`, so any future rename of `AppName`
   silently creates a *second* uninstall entry instead of upgrading in place.
3. No `ignoreversion` on the `[Files]` entries. Inno's default compares version
   resources and skips replacing a file whose installed copy has an equal-or-higher
   version — so a repair/reinstall over an install whose `app\` was already
   self-updated can silently keep stale versioned binaries.

**Fix:**

```
[Setup]
AppId={{...generate one GUID and hard-code it...}}
...
[Files]
Source: "launcher\*"; DestDir: "{app}\launcher"; Flags: recursesubdirs ignoreversion
Source: "app\*";      DestDir: "{app}\app";      Flags: recursesubdirs ignoreversion

[UninstallDelete]
; Swap residue the app creates at runtime; data\ is deliberately NOT listed.
Type: filesandordirs; Name: "{app}\app.prev"
Type: filesandordirs; Name: "{app}\app.failed"
Type: filesandordirs; Name: "{app}\staged"
```

---

### WR-10: `EMBEDDABLE_SHA256`'s comment contradicts the code and overstates the supply-chain guard

**File:** `build_release.py:69-78`

**Issue:** The block comment says "**It is left empty on purpose**: an UNVERIFIED
hash would silently defeat the supply-chain guard (T-31-SC)" — but the dict
directly below it is populated with `"3.13.1": "7b7923ff…"`. The comment is stale
and now actively misleads a reader about the state of the control. The pin's own
provenance note is also weaker than the surrounding prose implies: the digest was
derived by MD5-checking a download and then SHA-256-ing *that same file* — MD5 is
not collision-resistant, and the SHA-256 is self-computed rather than
python.org-published, so this is a download-integrity check, not the independent
publisher attestation "verified against python.org" suggests.

**Fix:** Rewrite the comment to describe reality, and record the actual provenance
so the next bump can be audited:

```python
# Pinned Python embeddable releases. A version absent from this map is REFUSED by
# fetch_embeddable (T-31-SC) — never add an entry without recording how the digest
# was established.
EMBEDDABLE_SHA256: dict[str, str] = {
    # Provenance: python.org publishes MD5 for the embeddable zips. The download
    # was MD5-matched (d5c8030976b5eaf55ed6b321c073dda7) and this SHA-256 computed
    # from it. Upgrade path: verify the release's GPG/sigstore signature instead —
    # MD5 alone is not collision-resistant.
    "3.13.1": "7b7923ff0183a8b8fca90f6047184b419b108cb437f75fc1c002f9d2f8bcec16",
}
```

---

### WR-11: The launcher can never be updated in the field, and this is documented nowhere

**File:** `launcher/swap.py:76-113` (swap covers `app\` only), `build_release.py:252-294`

**Issue:** By design the swap replaces `app\` and never touches `launcher\`. Since
the `.iss` is the only thing that ever writes `launcher\`, **a bug in
`launcher/swap.py`, `launcher/adapters.py` or `launcher/__main__.py` is permanent
for every installed copy** — the only remedy is a full re-install of the setup exe.
That is exactly the situation this phase is in (three launcher blockers just
fixed). Meanwhile the archive ships a `launcher/` copy that nothing ever applies
(see CR-01), which reads as if updates *do* cover it.

**Fix:** No code change is mandatory, but the constraint must be written down where
it will be seen — `launcher/__init__.py`'s module docstring and `docs/RELEASE.md`
— and the roadmap should carry an explicit item. Suggested docstring addendum:

```
The launcher is NOT self-updating: the swap replaces app\\ only. A launcher fix
reaches operators solely through a new installer run — treat every change in this
package as a re-install-required change and say so in the release notes.
```

---

### WR-12: `test_rollback_leaves_db_untouched_when_no_swap_happened` patches `os.replace` process-wide and gates on a global call counter

**File:** `tests/test_launcher.py:265-300`

**Issue:** `monkeypatch.setattr(os, "replace", failing_replace)` replaces the
**stdlib** function for the whole process, and the failure is selected by
`if len(calls) == 1`. Any other `os.replace` executed while the patch is live —
another thread's atomic write, a library's temp-file rename, or a future
`_quarantine_marker` call added to this path — consumes call #1 and the intended
first-rename failure never happens, turning the test green for the wrong reason.
This suite already has a documented history of cross-test interference from
process-global state (`reload_config` had to snapshot `app.config.settings`).

**Fix:** Patch the *module under test*'s reference and key the failure on the
arguments rather than a counter:

```python
    def failing_replace(src, dst):
        if Path(dst) == Path(paths.app_prev):
            raise OSError(32, "The process cannot access the file")
        return real_replace(src, dst)

    monkeypatch.setattr(launcher.swap.os, "replace", failing_replace)
```

---

_Reviewed: 2026-09-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
