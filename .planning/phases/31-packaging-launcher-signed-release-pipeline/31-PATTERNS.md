# Phase 31: Packaging, Launcher & Signed-Release Pipeline - Pattern Map

**Mapped:** 2026-07-22
**Files analyzed:** 7 (1 modified, 6 new)
**Analogs found:** 6 / 7 (launcher swap state-machine has no in-repo analog — see No Analog Found)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/config.py` (MODIFIED) | config | transform (path resolution) | `app/config.py` itself (current db_path/backup_dir/identity seam) | exact (in-place edit) |
| `build_release.py` | build tool | batch / file-I/O | `app/services/backup.py` (path assembly, atomic-write, dialect gate idioms) + `run.bat` (launch cmd) | role-partial |
| `launcher.py` / `launcher/swap.py` | launcher (process orchestrator) | event-driven (marker) + file-I/O | `run.bat` (start app, port, taskkill) + `restore.bat` (WAL-sidecar delete) | role-partial |
| `MyOriShop.iss` (Inno Setup) | config (installer) | batch | none in repo — RESEARCH Pattern 2 template | no analog |
| `.github/workflows/release.yml` | config (CI) | event-driven (tag push) | `.github/workflows/ci.yml` | role-match |
| `manifest.txt` generator (part of `build_release.py`) | utility | transform (checksum) | `app/services/backup.py` `create_backup` (stamp + bound-param write) | role-partial |
| `app/minisign.pub` (vendored) | asset (public key) | static | `app/static/htmx.min.js` (vendored-offline-asset convention) | convention-match |

## Pattern Assignments

### `app/config.py` (MODIFIED — config, path-transform) — PKG-03, the highest-risk change

**Analog:** the file itself. This is a surgical in-place edit, NOT a new file. The planner must patch the exact lines below, preserving all comments and the `_resolve_local_identity` validator.

**Current db_path / backup_dir / identity resolution** (`app/config.py:20-22`, `:68`, `:78-96`):
```python
model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")   # line 20

db_path: str = "data/myorishop.db"                                              # line 22
...
backup_dir: str = "backups"                                                     # line 68  ← CWD-relative, the single wipe-risk line
...
@model_validator(mode="after")
def _resolve_local_identity(self) -> "Settings":                                # line 79
    data_dir = Path(self.db_path).parent                                        # line 87  ← secret_key/device_id already root here
    if not self.database_url:
        self.database_url = f"sqlite:///{self.db_path}"
    if not self.secret_key:
        self.secret_key = get_or_create_local_id(data_dir / "secret_key")       # line 93
    if self.device_id == "device-01":
        self.device_id = get_or_create_local_id(data_dir / "device_id")         # line 95
    return self
```

**What PKG-03 must change (illustrative — preserve existing comments):**
- Introduce an absolute data-dir root read from `MYORISHOP_DATA_DIR` (default `"data"` so dev behavior is byte-identical):
  ```python
  import os
  _DATA_DIR = Path(os.environ.get("MYORISHOP_DATA_DIR", "data")).resolve()
  ```
- `env_file=str(_DATA_DIR / ".env")` (line 20) — so `.env` survives an app-dir swap.
- `db_path: str = str(_DATA_DIR / "myorishop.db")` (line 22).
- `backup_dir: str = str(_DATA_DIR / "backups")` (line 68) — **the critical line**: today CWD-relative `"backups"`; under packaging CWD is `app\`, so leaving it relative lands backups inside the swappable dir and destroys the operator's only ledger copy (RESEARCH Pitfall 2 / STATE.md "Data preservation by physical layout").
- `secret_key` / `device_id` need NO change — `data_dir = Path(self.db_path).parent` (line 87) now resolves to `_DATA_DIR` automatically.
- `catalogs_dir` (line 76) is also CWD-relative — note but out of the PKG-03 data-preservation scope unless flagged.

**Test gate (RESEARCH → `tests/test_packaging.py`):** assert every data path (`db_path`, `backup_dir`, `.env`, `secret_key`, `device_id`) resolves under `_DATA_DIR` and NONE resolves under a simulated app dir.

---

### `build_release.py` (NEW — build tool, batch/file-I/O) — PKG-01, PKG-05 manifest

**Analog:** `app/services/backup.py` for path-assembly + atomic-write + timestamp idioms; `run.bat:19` for the exact launch command the onedir must reproduce.

**Timestamp/stamp + safe-target-write idiom to imitate** (`app/services/backup.py:34-48`):
```python
backup_dir.mkdir(parents=True, exist_ok=True)
stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
target = backup_dir / f"myorishop-{stamp}.db"
...
try:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.exec_driver_sql("VACUUM INTO ?", (str(target),))
except Exception:
    target.unlink(missing_ok=True)   # ← delete partial artifact on failure — mirror this for the zip/manifest
    raise
```
Reuse the pattern: build into a temp/target path, delete-on-failure so a half-written onedir/zip never masquerades as valid.

**Launch command the built onedir must reproduce byte-identically** (`run.bat:12`, `:19`):
```bat
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```
In the bundle this becomes `app\python.exe -m alembic upgrade head` then `app\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` (no `uv`). Same host/port/module path.

**Version↔tag contract source** (`app/__init__.py:5`):
```python
__version__ = "1.1"     # scheme: "1.<N>", integer-comparable trailing counter (see MEMORY versioning-scheme)
```
`build_release.py --manifest` must assert `__version__ == tag` (tag `v1.<N>` ↔ `__version__ = "1.<N>"`) and FAIL the build on mismatch (RESEARCH Pattern 5, Stage A). Read it without importing the app: parse `app/__init__.py` or read `app.__version__`.

**Alembic bundle assertion** (RESEARCH Pitfall 5): copy `alembic/`, `alembic.ini`, `app/`, static, templates verbatim; assert `alembic/versions/*.py` count matches repo (currently 0001–0022, 22 migrations).

---

### `launcher.py` / `launcher/swap.py` (NEW — launcher, event-driven + file-I/O) — PKG-04

**Analog:** `run.bat` (how the app is started + the stale-server stop it REPLACES) and `restore.bat` (the exact WAL-sidecar-delete rollback logic to reuse). RESEARCH also gives a testable pure-function skeleton (Code Examples, `apply_update`).

**What the launcher REPLACES from `run.bat:5-10`** — the port-based stale-server kill (an ANTI-pattern for the launcher, which owns the child PID instead):
```bat
rem Kill any stale server left listening on 127.0.0.1:8000 ...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr "127.0.0.1:8000" ^| findstr "LISTENING"') do (
  taskkill /F /PID %%P >nul 2>&1
)
```
Launcher instead: spawn app as a child, keep its PID/handle, stop by terminating THAT child and WAITing on the handle (RESEARCH Pattern 4 step 2; Pitfall 3 WinError 32). No netstat/port race.

**Rollback DB restore — reuse `restore.bat:11-14` verbatim in Python** (the matched-pair's DB half):
```bat
copy /y "%~1" data\myorishop.db
del /q data\myorishop.db-wal 2>nul     ← MUST delete WAL sidecars or SQLite replays stale wal → corruption
del /q data\myorishop.db-shm 2>nul
```
In the launcher `backup_restore(db_backup_path)`: `shutil.copy(backup, data/myorishop.db)` then `unlink(missing_ok=True)` on `myorishop.db-wal` and `-shm` (RESEARCH Pitfall 4).

**Migrate step** reuses `run.bat:12` semantics: `app\python.exe -m alembic upgrade head` with CWD=`app\`, `MYORISHOP_DATA_DIR` unchanged.

**Pure swap state machine to implement** (RESEARCH Code Examples — inject `stop_app`/`start_app`/`migrate`/`health_ok`/`backup_restore` as callbacks so `tests/test_launcher.py` can fault-inject on any OS):
```python
def apply_update(paths, pending, *, stop_app, start_app, migrate, health_ok, backup_restore):
    stop_app()
    os.replace(paths.app, paths.app_prev)      # atomic same-volume rename
    os.replace(paths.staged, paths.app)
    try:
        migrate(); start_app()
        if not health_ok(): raise RuntimeError(...)
    except Exception:
        stop_app()
        os.replace(paths.app, paths.app_failed)
        os.replace(paths.app_prev, paths.app)
        backup_restore(pending.db_backup_path)  # copy + delete -wal/-shm
        start_app(); raise
    else:
        shutil.rmtree(paths.app_prev, ignore_errors=True)
```
**Health signal:** no `/health` route exists; the app redirects anonymous requests `302/303 → /login` (see `app/services/security.py:39` `PUBLIC_PATHS`). `health_ok()` polls `127.0.0.1:8000` and treats the login-redirect as alive (matches RESEARCH PKG-01 test map "responds 302→/login").

**Security (V12):** confine all swap paths under `%LOCALAPPDATA%\MyOriShop\`; reject `staged`/`pending.json` paths with `..`/absolute escapes; refuse to swap without a valid `pending.json` (`{staged_dir, expected_version, db_backup_path}` in `data\`).

---

### `.github/workflows/release.yml` (NEW — CI config, tag-triggered) — PKG-05 Stage A

**Analog:** `.github/workflows/ci.yml` — match its conventions exactly.

**Conventions to copy** (`.github/workflows/ci.yml:27-35`):
```yaml
steps:
  - name: Checkout
    uses: actions/checkout@v4
  - name: Install uv
    uses: astral-sh/setup-uv@v5
  - name: Install dependencies
    run: uv sync --dev
```
Differences for `release.yml` (RESEARCH Pattern 5 / CI skeleton): trigger `on: push: tags: ['v1.*']`; `runs-on: windows-2022` (Inno Setup present on 2022, absent on 2025 — Pitfall 6; else `choco install innosetup -y`); build vendored `site-packages` on Windows for correct cp313 win_amd64 wheels (Pitfall 7); draft-only release via `softprops/action-gh-release@v2` with `draft: true` (human attaches `.minisig` offline). The secret key NEVER becomes a repo secret.

**Existing CI throwaway-credential convention to mirror** (`ci.yml:14-18` comment) — any CI-only secret is documented as non-production, never from repo secrets. `release.yml` needs no secrets at all for Stage A.

---

### `MyOriShop.iss` (NEW — Inno Setup installer config) — PKG-02

**Analog:** none in repo. Use RESEARCH Pattern 2 template verbatim. Key locked settings: `PrivilegesRequired=lowest`, `DefaultDirName={localappdata}\MyOriShop`, `[Icons]` → `{app}\launcher\launcher.exe`, `AppVersion` synced to `__version__`. `data\` is NOT shipped (created on first run). May be generated by `build_release.py` (so `AppVersion`/`OutputBaseFilename` interpolate the tag).

---

### `app/minisign.pub` (NEW — vendored public key asset) — PKG-05

**Analog:** `app/static/htmx.min.js` — the project's established "vendor-offline-asset, no network fetch" convention (CLAUDE.md: "Vendor the file locally … the app must work offline"). Ship `minisign.pub` read-only inside `app\`; Phase 32 verifies against it. The secret key stays offline, never committed.

## Shared Patterns

### Server no-op / dialect gate
**Source:** `app/services/backup.py:110`, `app/db.py:96`
**Apply to:** any Phase-31 runtime code that could run on the central PostgreSQL server (server is the update TARGET, never a packaging/update client — RESEARCH Responsibility Map).
```python
if engine.dialect.name != "sqlite":
    return   # no-op on PostgreSQL server
```
This is the shipped pattern (backup startup gate + PRAGMA gate). Phase 32's UPD-06 reuses it; Phase 31 launcher/build code should not assume SQLite when a dialect check is cheap.

### Vendored-offline asset
**Source:** `app/static/htmx.min.js` (CLAUDE.md offline requirement)
**Apply to:** `app/minisign.pub`, the embeddable python zip, `minisign.exe` — all fetched/pinned at build, never at runtime.

### Delete-partial-on-failure (safe artifact write)
**Source:** `app/services/backup.py:45-47`
**Apply to:** `build_release.py` (onedir/zip/manifest), launcher swap (`app.failed\` retained, `app.prev\` kept until health passes).

### Version single-source-of-truth
**Source:** `app/__init__.py:5` (`__version__ = "1.<N>"`)
**Apply to:** `build_release.py` tag assertion, `MyOriShop.iss` `AppVersion`, `manifest.txt` `version=` field. All must equal the git tag `v1.<N>`.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `launcher/swap.py` state machine | launcher | event-driven | No process-orchestration/self-replace code exists in the repo today; `run.bat`/`restore.bat` supply the *primitives* (start cmd, WAL-delete) but not the transactional swap. Use RESEARCH Code Examples `apply_update` skeleton. |
| `MyOriShop.iss` | installer config | batch | No installer artifact in repo. Use RESEARCH Pattern 2 template. |
| minisign signing/verify plumbing | crypto | transform | No crypto code today (auth uses argon2/itsdangerous, unrelated). Shell out to vendored `minisign.exe`; do NOT adopt PyPI `minisign` 0.1.0 (RESEARCH Package Audit — Phase 32 decision behind `checkpoint:human-verify`). |

## Metadata

**Analog search scope:** `app/config.py`, `app/db.py`, `app/services/backup.py`, `app/__init__.py`, `app/services/security.py`, `run.bat`, `restore.bat`, `pyproject.toml`, `.github/workflows/ci.yml`
**Files scanned:** 9 (worktree copies under `.claude/worktrees/` ignored)
**Pattern extraction date:** 2026-07-22
