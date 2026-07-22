# Phase 31: Packaging, Launcher & Signed-Release Pipeline - Research

**Researched:** 2026-07-22
**Domain:** Windows application packaging, self-replace launcher design, offline-signed release engineering (Python/FastAPI/SQLite desktop client)
**Confidence:** HIGH (bundled-runtime strategy, data-separation, launcher sequencing, minisign) / MEDIUM (Inno Setup CI specifics, deterministic zip)

## Summary

Phase 31 converts the git+uv dev checkout into an installable, self-contained Windows distribution and stands up the release-signing pipeline that Phase 32 (self-update) will consume. The technical crux is four interlocking decisions: (1) which bundled runtime, (2) where operator data physically lives relative to swappable code, (3) how a launcher living *outside* the swappable directory can stop→swap→migrate→restart the app without hitting Windows file locks, and (4) how an OFFLINE minisign secret key can produce a signature that a GitHub Actions pipeline "publishes" without the key ever touching CI.

The strong recommendation is the **Python embeddable package (onedir), not PyInstaller**. The app is pure-Python + a handful of pre-built wheels (pydantic-core, argon2-cffi, cffi); the embeddable distribution is the genuine Microsoft-recognized `python.exe` + stdlib zip, which (a) minimizes SmartScreen/AV false positives — the exact concern PKG-02 is trying to keep to a one-time "Run anyway", (b) lets Alembic `versions/`, templates and static assets ship as plain copied files with zero `--add-data`/hidden-import archaeology, and (c) is inherently a non-self-locking onedir, satisfying PKG-01's explicit "never a self-locking single-file exe". PyInstaller's self-extracting bootloader is a documented AV trigger and turns "bundle the dynamically-imported Alembic migration scripts" into a hidden-import hunt — rejected.

Data separation (PKG-03) is a small, surgical `app/config.py` change: root `db_path`, `backup_dir`, the `secret_key`/`device_id` files, and the `.env` at an **absolute** sibling data directory (`%LOCALAPPDATA%\MyOriShop\data`) supplied by the launcher via one env var. The launcher (a tiny PyInstaller onedir stub or its own embeddable runtime at the stable install root) owns the app's child PID directly — so it stops the app by killing *its own child* and waiting on the process handle (no fragile netstat-by-port dance), then does directory *renames* (`os.replace`, atomic on one volume) to swap `app/ → app.prev/` and `staged/ → app/`, runs `alembic upgrade head`, and restarts; any failure reverses the renames and restores the pre-update DB backup as a matched pair.

**Primary recommendation:** Bundle with the **Python 3.13 embeddable package** laid out as `%LOCALAPPDATA%\MyOriShop\{launcher\, app\, data\, staged\, app.prev\}`; make the launcher the stable PID-owning parent; sign a small `manifest.txt` (version + archive SHA-256) offline with **minisign 0.12**, and have CI build+draft the release while a human attaches the one `.minisig` — the secret key never enters GitHub.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PKG-01 | Bare Windows install, bundled runtime + app source, onedir, never self-locking exe | Python embeddable-package strategy (Standard Stack, Pattern 1); CI smoke-launch proof |
| PKG-02 | Windows installer: Start-Menu shortcut, uninstaller, per-user %LOCALAPPDATA%, shipped unsigned + documented SmartScreen step | Inno Setup 6.4.x `PrivilegesRequired=lowest` + `{autopf}`/`{localappdata}` (Pattern 2); SmartScreen surface minimized by embeddable choice |
| PKG-03 | Operator data (DB, .env, secret_key/device_id, backups/) sibling of swappable app dir | `app/config.py` absolute data-dir rooting via one env var (Pattern 3); already-persisted identity files make this a small change |
| PKG-04 | Stable launcher outside swappable dir: stop/swap/migrate/restart + matched-pair rollback | Launcher PID-ownership + directory-rename sequencing (Pattern 4); Windows file-lock pitfalls documented |
| PKG-05 | GitHub Actions on tag builds distributable + publishes archive + SHA-256 + Ed25519 minisign signature over signed asset/manifest; OFFLINE key; pubkey vendored in client | Two-stage build-draft-in-CI / sign-offline-attach pattern (Pattern 5); minisign 0.12 CLI (Code Examples) |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Bundled Python runtime + app source | Client / Distribution (onedir `app/`) | — | Runs the operator's local FastAPI+SQLite exactly as `run.bat` does today, but self-contained |
| Operator data persistence (DB, .env, secrets, backups) | Client / Data dir (sibling `data/`) | — | Must survive an over-the-top app-dir swap; physically separated from code |
| Stop / swap / migrate / restart | Client / Launcher process (stable `launcher/`) | — | The only actor allowed to touch `app/` while the app is down; lives outside the swap target |
| Build the distributable + checksum + manifest | CI (GitHub Actions Windows runner) | Local dev (fallback) | Repeatable, deterministic, no secrets needed for build |
| Produce the Ed25519 signature | **Offline / human machine** | — | The secret key must never enter CI (PKG-05); signing happens off-CI |
| Publish release assets | CI (draft) + human (attach signature, publish) | — | CI prepares everything; human attaches the one offline signature and publishes |
| Central PostgreSQL server | **NO-OP** | — | Server is the update *target*, never a packaging/update client; dialect-gated out (Phase 32's UPD-06) |

## Standard Stack

### Core

| Library / Tool | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python Windows **embeddable package** | 3.13.x (match `requires-python >=3.13`) | The bundled runtime shipped inside `app/` | Genuine Microsoft-recognized `python.exe`; lowest AV/SmartScreen surface; inherently onedir/no-self-lock `[CITED: docs.python.org/3.13/using/windows.html#the-embeddable-package]` |
| minisign | **0.12** (jedisct1 reference binary) | Offline Ed25519 signing + client-side verify | The named tool (PKG-05); Ed25519, tiny, deterministic signatures, trusted-comment support `[VERIFIED: github.com/jedisct1/minisign]` |
| Inno Setup | **6.4.x** (6.4.0 on windows-2022; install via Chocolatey on windows-2025) | Windows installer: shortcut, uninstaller, per-user install | Named tool (PKG-02); mature; native per-user (`PrivilegesRequired=lowest`) support `[CITED: jrsoftware.org/isinfo.php]` |
| GitHub Actions (windows-latest runner) | current | Repeatable build pipeline on version tag | Named tool (PKG-05); already used for pg-parity CI (`.github/workflows/ci.yml`) `[VERIFIED: repo]` |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyInstaller (**launcher stub ONLY**, not the app) | 6.21.0 | Compile the tiny stable `launcher.exe` if a compiled launcher is preferred over a second embeddable runtime | Optional — the launcher can equally be a second copy of the embeddable runtime running `launcher.py` (see Pattern 4 alternatives) `[VERIFIED: PyPI]` |
| `pip --target` (build-time only) | bundled with build python | Vendor locked wheels into the embeddable `site-packages` | At build time only; embeddable dist has no pip by default `[CITED: docs.python.org/3.13/using/windows.html]` |
| minisign python impl (`minisign` on PyPI) | 0.1.0 | *Candidate* pure-Python verify for Phase 32 | **Phase 32 decision — flagged, see Package Legitimacy Audit.** Prefer vendoring `minisign.exe` + shelling out, or PyNaCl-based verify |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python embeddable onedir | **PyInstaller `--onedir`** | Rejected: self-extracting bootloader is a documented AV/SmartScreen false-positive source `[CITED: pythonguis.com/faq/problems-with-antivirus-software-and-pyinstaller]`; dynamically-imported Alembic migrations + uvicorn/anyio need hidden-import + `--add-data` tuning; larger blast radius for over-the-top swap. Its ONLY win here is auto-collecting deps — not worth the AV surface |
| minisign (Ed25519) | GPG detached sig / sigstore keyless | Rejected for now: GPG is heavier and key-mgmt-heavier; sigstore keyless is CI-side signing, explicitly deferred in REQUIREMENTS.md ("CI-side signing (sigstore keyless) as an alternative … if release production moves fully into CI"). Offline minisign is the locked decision |
| Inno Setup | MSIX / WiX / NSIS | Rejected: MSIX needs signing to install cleanly (defeats "ship unsigned"); WiX/MSI leans admin/machine-wide; Inno Setup has first-class per-user `%LOCALAPPDATA%` support and is the named tool |
| Launcher = compiled `.exe` | Launcher = plain `.bat` | `.bat` can `taskkill`/`move`/restart but cannot cleanly own a child PID, poll a process handle, or do transactional rollback with good error handling; a small Python launcher (embeddable or PyInstaller stub) is far more robust for PKG-04's rollback requirement |

**Installation (build-time, on the CI Windows runner / build machine):**
```bash
# 1. Bundled app runtime: the embeddable zip is DOWNLOADED by build_release.py
#    (pinned URL, e.g. python-3.13.x-embed-amd64.zip from python.org), not pip-installed.
# 2. Vendor the locked wheels into the embeddable site-packages using a NORMAL python:
python -m pip install --target dist/app/Lib/site-packages --no-deps -r requirements-locked.txt
#    (requirements-locked.txt derived from uv.lock — see build_release.py responsibilities)
# 3. minisign: download the official Windows binary (jedisct1 releases), vendor minisign.exe
# 4. Inno Setup on the runner: preinstalled on windows-2022; on windows-2025:
choco install innosetup -y
```

**Version verification (performed this session):**
- Python embeddable package documented for 3.13 `[CITED: docs.python.org/3.13/using/windows.html]`
- minisign current stable **0.12** `[VERIFIED: github.com/jedisct1/minisign]`
- PyInstaller **6.21.0** latest `[VERIFIED: pip index versions pyinstaller]`
- Inno Setup **6.4.0** on GitHub windows-2022 runner image, needs Chocolatey install on windows-2025 `[CITED: github.com/actions/runner-images/issues/12746]`
- `minisign` PyPI package exists at **0.1.0** only (pure-Python impl, gitlab.com/hackancuba/minisign-py) `[VERIFIED: pip index versions minisign]`

## Package Legitimacy Audit

> Phase 31 adds **no new Python runtime dependencies** to `pyproject.toml`. The tooling is build/CI-side (embeddable zip, minisign binary, Inno Setup) or deferred to Phase 32.

| Package/Tool | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| Python embeddable dist | python.org | 3.13 line | n/a (official) | python/cpython | OK | Approved (download pinned URL, verify SHA against python.org) |
| minisign (CLI binary) | github releases | mature (0.12) | widely used | github.com/jedisct1/minisign | OK | Approved (vendor `minisign.exe` + `minisign.pub`; verify release checksum) |
| Inno Setup | jrsoftware.org | mature (6.4.x) | widely used | jrsoftware/issrc | OK | Approved (installer tool, CI only) |
| pyinstaller (PyPI) | PyPI | 6.21.0 | unknown (seam) | pyinstaller.org | SUS→OK | Approved *only if* launcher-stub route chosen; seam flagged solely on "unknown-downloads", it is the canonical PyInstaller. Dev/build dep only |
| `minisign` (PyPI, pure-Python) | PyPI | 2020, 0.1.0 | unknown | gitlab.com/hackancuba/minisign-py | **SUS** | **Phase 32 decision — DO NOT adopt in Phase 31.** Prefer vendored `minisign.exe` shell-out or PyNaCl verify. Planner: gate any Phase-32 adoption behind `checkpoint:human-verify` |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** `minisign` (PyPI 0.1.0) — deferred to Phase 32, not installed here. `pyinstaller` — canonical, SUS only from missing download stats.

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────────── RELEASE SIDE ───────────────────────────┐
  git tag v1.<N> ──push──▶ GitHub Actions (windows runner)                                       │
                          │  build_release.py ─▶ dist/app/ (embeddable + wheels + app + alembic) │
                          │        │              │                                              │
                          │        ▼              ▼                                              │
                          │  onedir .zip     Inno Setup ─▶ MyOriShop-Setup-1.<N>.exe             │
                          │        │                                                             │
                          │        ▼                                                             │
                          │  SHA-256 ─▶ manifest.txt (version + archive sha256)                  │
                          │        │                                                             │
                          │        ▼                                                             │
                          │  DRAFT GitHub Release  (archive, .exe, SHA256SUMS, manifest.txt)     │
                          └────────────────────────────┬────────────────────────────────────────┘
                                                        │ human downloads manifest.txt
                          ┌──── OFFLINE MACHINE ────────▼──────────┐
                          │ minisign -S -m manifest.txt (secret key │
                          │ never leaves this box) ─▶ manifest.txt.minisig │
                          └────────────────────────────┬────────────┘
                                                        │ attach .minisig, PUBLISH release
                                                        ▼
   ══════════════════════════════════════ CLIENT SIDE (operator PC) ══════════════════════════════════
   %LOCALAPPDATA%\MyOriShop\
     ├─ launcher\  ── launcher.exe (+its runtime) ── STABLE, never swapped ──┐ owns child PID
     │                                                                        │
     ├─ app\       ── embeddable python + app source + alembic\versions\ ─────┼─▶ spawns:
     │                (SWAPPABLE — replaced on update)                        │   python.exe -m uvicorn app.main:app
     │                                                                        │        │
     ├─ staged\    ── next version, hand-placed / Phase-32-downloaded ────────┘        ▼
     ├─ app.prev\  ── previous app dir, kept for rollback                      127.0.0.1:8000 (browser UI)
     └─ data\      ── myorishop.db, .env, secret_key, device_id, backups\  ◀── app reads/writes here
                       (SIBLING — swap of app\ physically cannot reach it)      (via MYORISHOP_DATA_DIR)
```

### Recommended Install-Root Structure (PKG-01/03/04)
```
%LOCALAPPDATA%\MyOriShop\
├── launcher\              # STABLE. Never swapped. The PID-owning parent.
│   ├── launcher.exe       # small PyInstaller onedir stub OR second embeddable runtime + launcher.py
│   └── ... (its runtime)  # must NOT depend on files inside app\ (or it would lock the swap target)
├── app\                   # SWAPPABLE. Whole dir replaced on update.
│   ├── python.exe         # Python 3.13 embeddable
│   ├── python313.zip      # stdlib
│   ├── python313._pth     # search path: '.', app source, Lib\site-packages, 'import site'
│   ├── Lib\site-packages\ # vendored wheels (fastapi, uvicorn, sqlalchemy, jinja2, argon2-cffi, ...)
│   ├── app\               # THE APP PACKAGE (app.main:app)
│   ├── alembic\           #   including alembic\versions\  ◀── MUST be present for `alembic upgrade head`
│   ├── alembic.ini
│   ├── minisign.pub       # vendored public key (Phase 32 verifies against this)
│   └── VERSION            # or read from app\app\__init__.py __version__
├── staged\                # a fully-built next-version app dir waiting to be applied
├── app.prev\              # previous app dir (rollback source)
└── data\                  # SIBLING PERSISTENT STATE (survives any app\ swap)
    ├── myorishop.db (+ -wal/-shm)
    ├── .env               # operator-editable (sync_token, etc.)
    ├── secret_key         # per-install
    ├── device_id          # per-install
    └── backups\           # VACUUM INTO snapshots (pre-update anchor)
```

### Pattern 1: Bundled runtime = Python embeddable package (PKG-01)
**What:** Ship the official `python-3.13.x-embed-amd64` distribution inside `app\`, configure `python313._pth`, and vendor dependencies into `app\Lib\site-packages`. The app launches with `python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` — byte-identical behavior to today's `run.bat`, just no `uv`.
**When to use:** This phase's PKG-01 (locked: onedir, never single-file exe).
**Key `._pth` content** (this is the #1 embeddable gotcha):
```
python313.zip
.
app
Lib\site-packages
import site
```
`[CITED: docs.python.org/3.13/using/windows.html#finding-modules]` — the embeddable dist restricts `sys.path` to the `._pth`; without adding `Lib\site-packages` and uncommenting/adding `import site`, vendored wheels are un-importable.

### Pattern 2: Per-user Inno Setup installer (PKG-02)
**What:** An `.iss` script with `PrivilegesRequired=lowest`, `DefaultDirName={localappdata}\MyOriShop`, a Start-Menu `[Icons]` entry pointing at `launcher\launcher.exe`, and the auto-generated uninstaller. Ships unsigned; document the one-time SmartScreen «Подробнее → Выполнить в любом случае».
**When to use:** PKG-02.
**Example:**
```ini
; Source: build_release.py-generated MyOriShop.iss
[Setup]
AppName=MyOriShop
AppVersion=1.42
PrivilegesRequired=lowest              ; per-user, no admin, no UAC
DefaultDirName={localappdata}\MyOriShop
DisableProgramGroupPage=yes
OutputBaseFilename=MyOriShop-Setup-1.42
[Files]
Source: "dist\launcher\*"; DestDir: "{app}\launcher"; Flags: recursesubdirs
Source: "dist\app\*";      DestDir: "{app}\app";      Flags: recursesubdirs
; NOTE: data\ is NOT shipped — created empty on first run under {app}\data (PKG-03)
[Icons]
Name: "{autoprograms}\MyOriShop"; Filename: "{app}\launcher\launcher.exe"
```
`[CITED: jrsoftware.org/ishelp — PrivilegesRequired, {localappdata}, {autoprograms}]`. Note `{app}` here resolves under `{localappdata}\MyOriShop`; the launcher then treats `{app}\data` as the sibling data dir.

### Pattern 3: Absolute-rooted data dir (PKG-03) — the config seam
**What:** The launcher exports `MYORISHOP_DATA_DIR=%LOCALAPPDATA%\MyOriShop\data` (absolute) before spawning the app. `app/config.py` roots `db_path`, `backup_dir`, the identity files, and the `.env` under it. Today all four already derive from `Path(db_path).parent` (secret_key/device_id) or CWD-relative defaults (`backup_dir`, `.env`) — so the change is small and surgical.
**When to use:** PKG-03 (locked: siblings, never children of `app\`).
**Concrete change (illustrative):**
```python
# app/config.py — add a data-dir root read from env, default preserves dev behavior
import os
_DATA_DIR = Path(os.environ.get("MYORISHOP_DATA_DIR", "data")).resolve()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_DATA_DIR / ".env"),   # .env now lives in data dir (survives swaps)
        env_file_encoding="utf-8",
    )
    db_path: str = str(_DATA_DIR / "myorishop.db")     # absolute
    backup_dir: str = str(_DATA_DIR / "backups")       # absolute — was CWD-relative "backups"
    # secret_key/device_id already resolve to Path(db_path).parent == _DATA_DIR ✓ (no change)
```
**Why it matters:** `backup_dir` is TODAY a CWD-relative `"backups"` — under packaging, CWD is the app dir, so without this change backups would land *inside* the swappable dir and be destroyed on update. This is the single highest-risk line in the phase (getting it wrong wipes the operator's only ledger copy — see STATE.md decision "Data preservation by physical layout, not careful code").

### Pattern 4: The stable launcher (PKG-04)
**What:** A small process at `launcher\` that (a) starts the app as a child and remembers its PID/handle, (b) opens the browser, (c) watches for a `pending.json` marker (in `data\` or root), and on seeing one performs the transactional swap.
**When to use:** PKG-04, and the mechanism Phase 32 drives.
**Stop→swap→migrate→restart sequence (Windows-lock-safe):**
```
1. Read pending.json → { staged_dir, expected_version, db_backup_path }
2. Graceful stop: signal child to shut down (or terminate the OWNED child PID);
   WAIT on the process handle until it fully exits.        ← owns PID ⇒ no netstat/port race
   (Windows will not let you rename app\ while python.exe inside it is running.)
3. os.replace(app\, app.prev\)        # rename #1 — atomic on same volume
4. os.replace(staged\, app\)          # rename #2
5. Run  app\python.exe -m alembic upgrade head   (CWD=app\, MYORISHOP_DATA_DIR unchanged)
6. Start child on new app\, poll 127.0.0.1:8000 for a health response
7. Success → delete app.prev\, delete pending.json
   FAILURE at 5/6 → ROLLBACK (matched pair):
     - stop child if started
     - os.replace(app\, app.failed\); os.replace(app.prev\, app\)
     - restore pre-update DB: copy db_backup_path → data\myorishop.db,
       delete -wal/-shm sidecars (mirrors restore.bat)   ← code+DB reverted together
     - restart child on restored app\
```
**Why the launcher must live outside `app\`:** if the launcher's own executable/DLLs lived inside `app\`, they would lock the very directory being renamed at step 3. PKG-04 says exactly this ("living outside the swappable code directory").
**Launcher runtime options** (pick one, planner decision):
- **(a) Second embeddable runtime** in `launcher\` running `launcher.py` — reuses the same Python, no PyInstaller, but ~+15MB.
- **(b) PyInstaller onedir stub** `launcher.exe` — smaller, self-contained, but adds PyInstaller to the build and a (small) AV surface for the *launcher only* (the app itself stays embeddable). Recommended if size matters; the launcher is tiny so its AV surface is minimal.

### Pattern 5: Offline-key release pipeline (PKG-05) — resolving the CI/offline tension
**What:** PKG-05 says the *pipeline* "publishes … a minisign signature" produced with an *OFFLINE* secret key. These are only reconcilable with a two-stage flow; an offline key must never be a GitHub Actions secret.
**Recommended flow:**
```
STAGE A — CI (on push of tag v1.<N>):
  - build_release.py → onedir zip + Inno Setup .exe
  - compute SHA-256 of the archive → SHA256SUMS
  - write manifest.txt  (version=1.<N>, archive=<name>, sha256=<hex>)
  - assert app\__init__.py __version__ == tag  (fail build on mismatch)   ← tag↔version contract
  - create a DRAFT GitHub Release, upload: archive, .exe, SHA256SUMS, manifest.txt
STAGE B — HUMAN, offline (holds minisign.key):
  - download manifest.txt (or reproduce it deterministically)
  - minisign -S -m manifest.txt -t "MyOriShop 1.<N>"   → manifest.txt.minisig
  - upload manifest.txt.minisig to the draft release, then PUBLISH
```
**Why sign the manifest, not the archive:** the manifest binds *version + archive SHA-256* in one signed blob, so Phase 32 verifies one small signature then checks the (large) archive's SHA-256 against the signed manifest — no mix-and-match, fast verify, and the version is inside the signed payload (feeds UPD-05 anti-downgrade). Signing the archive directly with a trusted-comment carrying `version=` is a valid alternative but couples the signature to the multi-hundred-MB file.
**Rejected:** storing an encrypted minisign key in GitHub Actions secrets and signing in CI — violates PKG-05's "OFFLINE secret key" and is exactly the sigstore-keyless-vs-offline trade-off REQUIREMENTS.md defers. Do NOT put the secret key in CI.

### Anti-Patterns to Avoid
- **Single-file PyInstaller exe** — explicitly forbidden (PKG-01); self-extracts to temp, locks itself, worst AV surface.
- **Backups/DB under `app\`** — an over-the-top swap destroys them (PKG-03 violation). Root everything under `data\`.
- **Stopping the app by port (netstat/taskkill by PID-on-port)** — `run.bat` does this today as a *stale-server* guard, but the launcher OWNS the child PID and must stop *that*, then wait on the handle. Port-based killing races and can kill the wrong process.
- **Deleting the old `app\` before the new one is proven** — keep `app.prev\` until the post-update health check passes; it's half the matched-pair rollback.
- **Minisign key in CI** — see Pattern 5.
- **String-comparing "1.9" vs "1.10"** — Phase 32's problem (UPD-05), but the tag↔`__version__` contract is set here; keep the tag `v1.<N>` and `__version__ = "1.<N>"` identical and integer-comparable.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ed25519 signing/verify | Custom crypto | **minisign** (reference binary) | Hand-rolled crypto is the classic ASVS V6 violation; minisign is audited, deterministic, tiny |
| Windows installer (shortcut/uninstaller/per-user) | Custom `.bat`/registry writes | **Inno Setup** | Uninstaller registration, Start-Menu, upgrade-in-place are all solved; hand-rolling misses uninstall entries |
| Bundling a Python runtime | Zipping your system Python | **official embeddable dist** | The embeddable dist is purpose-built (isolated `._pth`, no user-site leakage, ships required DLLs) |
| Pre-update DB snapshot | New backup code | **existing `backup.create_backup()` VACUUM INTO** | Already WAL-safe, standalone, tested (STATE.md: reused as the pre-update anchor) |
| Server no-op gate | New flag | **`engine.dialect.name == "sqlite"`** | Already the shipped pattern for backup/auto-sync; Phase 32's UPD-06 reuses it |
| Atomic dir swap | Copy-then-delete | **`os.replace()` (MoveFileEx)** | Same-volume rename is near-atomic and fast; copy leaves a window where neither dir is complete |

**Key insight:** Almost every runtime mechanism this phase needs already exists in the codebase (VACUUM INTO backup, dialect gate, persisted identity files, `restore.bat`'s WAL-sidecar-delete). Phase 31 is mostly *relocation + orchestration*, not new runtime logic. The genuinely new artifacts are `build_release.py`, the launcher, the `.iss`, and the workflow.

## Common Pitfalls

### Pitfall 1: Embeddable `._pth` omits site-packages → ImportError at launch
**What goes wrong:** App won't start; `ModuleNotFoundError: fastapi`.
**Why it happens:** The embeddable dist's `python313._pth` restricts `sys.path` and does NOT include `Lib\site-packages` or run site by default.
**How to avoid:** Ship a `._pth` with `Lib\site-packages` and `import site` (Pattern 1). CI smoke-launch (build → `python.exe -m uvicorn` → curl localhost) catches this deterministically.
**Warning signs:** Import errors only in the built onedir, never in dev.

### Pitfall 2: `backup_dir` / `.env` land inside the swappable app dir
**What goes wrong:** First over-the-top update deletes the operator's backups and `.env`.
**Why it happens:** Current defaults (`backup_dir="backups"`, `.env` from CWD) are CWD-relative; under packaging CWD is `app\`.
**How to avoid:** Pattern 3 — absolute-root everything under `data\` via `MYORISHOP_DATA_DIR`. **Unit-test that no data path resolves under the app dir.**
**Warning signs:** A test that swaps `app\` and finds `data\` untouched is the gate.

### Pitfall 3: Renaming `app\` fails with "process cannot access the file" (WinError 32)
**What goes wrong:** Step 3 of the swap throws; update aborts mid-way.
**Why it happens:** A file inside `app\` (the running `python.exe`, an open `.pyd`, or even an open SQLite handle if the DB were mistakenly inside `app\`) is still locked.
**How to avoid:** Stop the child and WAIT ON ITS PROCESS HANDLE before renaming (Pattern 4 step 2). Ensure the launcher itself is not inside `app\`. Ensure DB is in `data\`.
**Warning signs:** Intermittent WinError 32; usually a shutdown-wait race.

### Pitfall 4: WAL sidecars survive a DB rollback → corrupt DB
**What goes wrong:** After restoring a pre-update `.db`, SQLite replays a stale `-wal` into it and corrupts it.
**Why it happens:** `-wal`/`-shm` from the newer run linger next to the restored file.
**How to avoid:** On rollback, delete `myorishop.db-wal` and `-shm` after copying the backup — exactly what `restore.bat` already does. Reuse that logic.
**Warning signs:** DB opens then errors on integrity check post-rollback.

### Pitfall 5: Alembic `versions/` missing from the bundle → `alembic upgrade head` no-ops or errors
**What goes wrong:** Migrations don't apply on the operator's machine; schema drifts.
**Why it happens:** Build script forgets to copy `alembic\versions\` (22 migrations, `0001`–`0022`) or `alembic.ini`.
**How to avoid:** `build_release.py` copies `alembic\` (incl. `versions\`), `alembic.ini`, `app\`, static, templates verbatim (trivial with embeddable — no `--add-data`). Add a build assertion that `alembic\versions\*.py` count matches the repo.
**Warning signs:** `alembic current` shows base/empty on the built onedir.

### Pitfall 6: Inno Setup absent on windows-2025 runner
**What goes wrong:** CI `iscc.exe` step fails.
**Why it happens:** InnoSetup ships on windows-2022 image but not windows-2025.
**How to avoid:** Pin `runs-on: windows-2022`, or add `choco install innosetup -y` before compiling `[CITED: github.com/actions/runner-images/issues/12746]`.
**Warning signs:** `iscc: command not found` in CI logs.

### Pitfall 7: `psycopg[binary]` and other wheels are Windows-platform-specific
**What goes wrong:** Vendored `site-packages` built on Linux won't import on the operator's Windows.
**Why it happens:** Wheels for `pydantic-core` (Rust), `argon2-cffi`/`cffi` (C), `psycopg[binary]` are platform+ABI specific.
**How to avoid:** Build the vendored `site-packages` on a **Windows** runner (`pip install --target` on windows-latest), matching cp313 win_amd64 wheels. `psycopg` is only imported when a `postgresql+psycopg://` URL is used — the client never does — but it is a hard dep in `pyproject.toml`; either keep it (weight only) or make it a server-only extra (larger change; note but don't force).
**Warning signs:** `ImportError: DLL load failed` only on the operator machine.

## Code Examples

### minisign: keygen, sign (offline), verify (client) `[VERIFIED: github.com/jedisct1/minisign]`
```bash
# ONE-TIME, offline: generate the keypair. Keep minisign.key OFFLINE; vendor minisign.pub.
minisign -G
# ⇒ minisign.pub (vendored into app\minisign.pub) + minisign.key (offline only)

# RELEASE, offline: sign the manifest (trusted comment is part of the signed data)
minisign -S -m manifest.txt -t "MyOriShop 1.42"
# ⇒ manifest.txt.minisig

# CLIENT (Phase 32) verify — public key inline or from the vendored file:
minisign -Vm manifest.txt -p app/minisign.pub
minisign -Vm manifest.txt -P RW....<pubkey string>....
```
For large archives, minisign supports prehashing (`-H` at sign time; verify auto-detects the prehashed algorithm marker) `[ASSUMED — confirm exact flag against minisign 0.12 man page at Phase 32 plan time]`. Signing the small `manifest.txt` sidesteps this entirely.

### CI workflow skeleton (Stage A, draft) `[CITED: composed from repo ci.yml + runner-images notes]`
```yaml
name: release
on:
  push:
    tags: ['v1.*']
jobs:
  build:
    runs-on: windows-2022        # Inno Setup present on 2022 image
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Build onedir + wheels (Windows-native for correct wheels)
        run: uv run python build_release.py --version ${{ github.ref_name }}
      - name: Compile installer
        run: '& "${env:ProgramFiles(x86)}\Inno Setup 6\iscc.exe" dist\MyOriShop.iss'
      - name: Checksums + manifest
        run: uv run python build_release.py --manifest --version ${{ github.ref_name }}
      - name: Draft release (unsigned; human attaches .minisig offline)
        uses: softprops/action-gh-release@v2
        with:
          draft: true
          files: |
            dist/MyOriShop-*.zip
            dist/MyOriShop-Setup-*.exe
            dist/SHA256SUMS
            dist/manifest.txt
```

### Launcher swap core as a testable pure function (design for Nyquist) `[ASSUMED — pattern recommendation]`
```python
# launcher/swap.py — pure state machine; process-kill/port-wait injected as callbacks
def apply_update(paths, pending, *, stop_app, start_app, migrate, health_ok, backup_restore):
    stop_app()                                  # waits on the owned child handle
    os.replace(paths.app, paths.app_prev)
    os.replace(paths.staged, paths.app)
    try:
        migrate()                               # app\python.exe -m alembic upgrade head
        start_app()
        if not health_ok():
            raise RuntimeError("post-update health check failed")
    except Exception:
        stop_app()
        os.replace(paths.app, paths.app_failed)
        os.replace(paths.app_prev, paths.app)
        backup_restore(pending.db_backup_path)  # copy + delete -wal/-shm
        start_app()
        raise
    else:
        shutil.rmtree(paths.app_prev, ignore_errors=True)
```
Injecting `stop_app`/`migrate`/`health_ok` makes the swap+rollback sequencing unit-testable on any OS with fake dirs; the Windows process/port specifics live in thin adapters.

## Runtime State Inventory

> Phase 31 is a packaging/relocation phase, not a rename. But it *relocates* runtime state (PKG-03), so the inventory matters:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `data/myorishop.db` (+ `-wal`/`-shm`); `backups/*.db` | Relocate to absolute `%LOCALAPPDATA%\MyOriShop\data` via `MYORISHOP_DATA_DIR`; `backup_dir` must become absolute (currently CWD-relative — highest-risk line) |
| Live service config | `.env` (sync_token, secret_key overrides) read from CWD | Point `env_file` at `data\.env` so it survives app-dir swaps and is operator-editable |
| OS-registered state | Start-Menu shortcut + uninstaller (NEW, created by Inno Setup) | Register via `.iss` `[Icons]` + auto-uninstaller; point shortcut at `launcher\launcher.exe` |
| Secrets/env vars | `secret_key`, `device_id` files (already under `Path(db_path).parent`) | No code change — they follow `db_path` to `data\` automatically. Verify they are NOT bundled into the installer (created on first run) |
| Build artifacts | uv `.venv`, `__pycache__` | Excluded from the onedir; embeddable uses vendored `site-packages`, not `.venv` |

**Nothing found in category:** OS-registered state is *new* (no scheduled tasks / services on the client today; `run.bat` is manual). The central server's systemd units (`deploy/*.service`) are OUT of scope — server is a no-op.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.x (already in `pyproject.toml` dev group) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=`tests`, pythonpath=`.`) |
| Quick run command | `uv run pytest -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PKG-01 | Built onedir launches + localhost answers | integration (CI, windows) | build → `python.exe -m uvicorn` → assert 127.0.0.1:8000 responds (302→/login) | ❌ Wave 0 (CI job step) |
| PKG-02 | Installer compiles; shortcut/uninstaller/per-user | manual UAT + partial | `iscc.exe` produces `.exe` (CI); install on clean VM = UAT | ❌ manual UAT |
| PKG-03 | Data paths resolve to sibling data dir, none under app dir | unit | `pytest tests/test_packaging.py::test_data_paths_are_siblings -x` | ❌ Wave 0 |
| PKG-04 | swap→migrate→restart + matched-pair rollback | integration (scriptable) | `pytest tests/test_launcher.py -x` (fake staged dir + pending marker; failure injection asserts rollback) | ❌ Wave 0 |
| PKG-05 | minisign verify passes / tamper fails; pipeline emits assets | unit + dry-run | `pytest tests/test_release_verify.py -x`; tag-push/workflow_dispatch dry-run produces assets | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest -x`
- **Per wave merge:** `uv run pytest` (full suite — current baseline ~1144 passed / 12 skipped)
- **Phase gate:** full suite green + CI release-workflow dry-run produces assets before `/gsd-verify-work`

### What is inherently MANUAL / UAT (cannot be fully automated)
- **PKG-01 bare-Windows install** — needs a clean Windows VM with no Python/uv/git. UAT: install → launch → login page in browser. (CI can prove the onedir *launches*, not that a *bare* machine has nothing preinstalled.)
- **PKG-02 SmartScreen "Run anyway" + Start-Menu/uninstaller UX** — SmartScreen reputation and shell integration are OS-interactive. UAT with screenshots.
- **PKG-05 offline human sign step** — by design the signature is produced off-CI; the *verify* is unit-testable, the *human sign+attach+publish* is a documented manual runbook.

### Wave 0 Gaps
- [ ] `tests/test_packaging.py` — data-dir resolution / no-data-under-app-dir (PKG-03)
- [ ] `tests/test_launcher.py` — swap/rollback state machine, failure injection (PKG-04)
- [ ] `tests/test_release_verify.py` — minisign verify pass/tamper-fail with a throwaway test key (PKG-05)
- [ ] `build_release.py` — onedir assembler (also the SUT for a build-smoke test)
- [ ] `launcher/` module (or `launcher.py`) — the swap state machine + Windows adapters
- [ ] `.github/workflows/release.yml` — tag-triggered build+draft
- [ ] `MyOriShop.iss` (or generated by build_release.py)

## Security Domain

> `security_enforcement: true`, ASVS L1 (`.planning/config.json`). Phase 31 establishes a code-execution trust boundary (the launcher swaps and runs code) and a signing pipeline — both security-relevant even though the *verification gate* is Phase 32.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Validate the version tag format (`^v1\.\d+$`) and parse `manifest.txt`/`pending.json` strictly before acting on them |
| V6 Cryptography | yes | Ed25519 via **minisign** — never hand-roll; secret key stays offline; public key vendored read-only in `app\` |
| V10 Malicious Code / V1 Architecture | yes | The launcher must refuse to swap without a valid `pending.json`; the *content* trust gate (signature/checksum verify before staging) is Phase 32 — Phase 31 must not create a path that swaps *unverified* code silently |
| V12 File Handling | yes | Directory renames confined to the install root; reject `staged\`/`pending.json` paths that escape the install root (path-traversal on the marker) |
| V2/V3/V4 (auth/session/access) | no (this phase) | App auth unchanged; installer is per-user (no privilege escalation) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Tampered/forged release archive | Tampering | minisign Ed25519 signature over manifest (version+sha256); Phase 32 verifies before unpack |
| Signature key exfiltration from CI | Info Disclosure / Spoofing | Key never enters CI (offline two-stage flow, Pattern 5) |
| Swap runs attacker-staged code | Elevation / Tampering | Launcher acts only on a valid `pending.json`; Phase 32 gates staging behind verify; per-user install limits blast radius |
| Path traversal via `staged`/marker | Tampering | Resolve + confine all swap paths under `%LOCALAPPDATA%\MyOriShop\`; reject absolute/`..` targets |
| Half-applied update / data loss | DoS (data integrity) | Matched-pair rollback (code + pre-update DB via VACUUM INTO backup + WAL-sidecar delete) |
| SmartScreen "unknown publisher" trains users to click through | Spoofing | Documented one-time step (PKG-02, accepted); cert deferred; keep AV surface low via embeddable (not PyInstaller) |

## Environment Availability

| Dependency | Required By | Available (dev box) | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | app runtime / build | ✓ (`requires-python >=3.13`) | 3.13.x | — |
| uv | dev + CI build | ✓ | 0.11.x | pip (embeddable build uses `pip --target` anyway) |
| GitHub Actions windows runner | PKG-05 pipeline | ✓ (repo has CI) | windows-2022 | local `build_release.py` run |
| Inno Setup (`iscc.exe`) | PKG-02 installer | ✗ likely absent locally | 6.4.x | CI (`choco install innosetup`); dev fallback = manual download |
| minisign binary | PKG-05 signing/verify | ✗ likely absent locally | 0.12 | download official Windows binary; vendor `minisign.exe` |
| Python embeddable zip | PKG-01 bundle | ✗ (downloaded by build) | 3.13.x | pinned python.org URL fetched in build |

**Missing dependencies with no fallback:** none — every build tool is fetchable in CI or by the build script.
**Missing dependencies with fallback:** Inno Setup + minisign are not on the dev box today; both are trivially installed (Chocolatey in CI / official binaries). Planner should include an install step, not assume presence.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `run.bat` + `uv run uvicorn` (dev checkout) | Bundled embeddable runtime launched by a stable launcher | This phase | Operator needs no Python/uv/git |
| Kill-server-by-port before start (`run.bat`) | Launcher owns child PID, waits on handle | This phase (PKG-04) | Deterministic stop, no port race |
| CWD-relative `data/` + `backups/` | Absolute sibling `data\` via `MYORISHOP_DATA_DIR` | This phase (PKG-03) | Survives over-the-top swap |
| Manual `restore.bat` | Automated matched-pair rollback in launcher | This phase (PKG-04) | Reuses restore.bat's WAL-delete logic |
| No release artifacts | Signed GitHub Releases (archive + SHA256 + minisign) | This phase (PKG-05) | Foundation for Phase 32 self-update |

**Deprecated/outdated:**
- PyInstaller single-file exe for FastAPI+uvicorn: known-fiddly (hidden imports, uvloop/watchfiles hooks) and forbidden by PKG-01 (CLAUDE.md already lists PyInstaller as "What NOT to Use" for v1).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Embeddable `._pth` with `Lib\site-packages` + `import site` makes vendored wheels importable | Pattern 1 | App won't start; caught by CI smoke-launch before release |
| A2 | `os.replace()` on same-volume dirs is atomic enough for the swap | Pattern 4 | If install spans volumes, rename fails → keep install root single-volume; low risk (per-user LOCALAPPDATA) |
| A3 | Windows wheels (pydantic-core, argon2-cffi, cffi, psycopg) install cleanly via `pip --target` on windows runner | Pitfall 7 | ImportError on operator box; mitigated by building vendored site-packages on Windows CI |
| A4 | minisign `-H` prehash flag / verify auto-detection for large files | Code Examples | Only matters if signing the archive directly; recommendation signs the small manifest, avoiding it. Confirm at Phase 32 |
| A5 | Inno Setup `{localappdata}\MyOriShop` + `PrivilegesRequired=lowest` yields a clean per-user install w/ uninstaller | Pattern 2 | UAT catches; well-documented Inno behavior |
| A6 | The launcher can gracefully signal FastAPI/uvicorn shutdown (or terminate its owned child) and the port frees promptly | Pattern 4 | Slow shutdown → longer swap wait; bounded by a timeout then hard-terminate |
| A7 | `minisign` PyPI (0.1.0) is unsuitable for production verify; vendored binary or PyNaCl preferred | Standard Stack / Audit | Phase 32 decision, not Phase 31 — no impact here |

## Open Questions

1. **Launcher runtime: PyInstaller stub vs second embeddable copy?**
   - What we know: both work; stub is smaller, embeddable avoids adding PyInstaller.
   - What's unclear: operator sensitivity to install size vs. build simplicity.
   - Recommendation: PyInstaller onedir stub for the launcher only (tiny AV surface, keeps `app\` pure embeddable) — but defer to planner/operator; either satisfies PKG-04.

2. **Sign the manifest vs sign the archive (with trusted-comment version)?**
   - What we know: manifest-signing is faster to verify and binds version+sha256.
   - What's unclear: Phase 32's exact verify ergonomics.
   - Recommendation: sign `manifest.txt`; note the alternative for the Phase 32 research pass.

3. **Keep `psycopg[binary]` in the client bundle?**
   - What we know: it's a hard dep but the client never uses PostgreSQL.
   - What's unclear: whether making it a server-only extra is worth the pyproject churn now.
   - Recommendation: keep it bundled for v4.0 (weight only, ~10MB); revisit as a "distribution slimming" future item.

4. **Where does `pending.json` live and what's its exact schema?**
   - Recommendation: `data\pending.json` (survives swaps, launcher-readable); schema `{staged_dir, expected_version, db_backup_path}`. The full IPC/controlled-shutdown contract is flagged for the Phase 32 `--research-phase` pass (ROADMAP) — Phase 31 only needs the hand-placed-marker proof.

## Sources

### Primary (HIGH confidence)
- docs.python.org/3.13/using/windows.html — embeddable package, `._pth`, pip-not-supported, vendoring guidance `[CITED]`
- github.com/jedisct1/minisign (README) — minisign 0.12, `-G`/`-S`/`-V`, `-p`/`-P`, `.minisig` format `[VERIFIED]`
- Repo files: `app/config.py`, `app/db.py`, `app/device_id.py`, `app/services/backup.py`, `alembic/env.py`, `run.bat`, `restore.bat`, `install.bat`, `.github/workflows/ci.yml`, `pyproject.toml`, `.planning/{REQUIREMENTS,ROADMAP,STATE}.md` `[VERIFIED]`
- `pip index versions` — pyinstaller 6.21.0, minisign(PyPI) 0.1.0 `[VERIFIED]`

### Secondary (MEDIUM confidence)
- github.com/actions/runner-images/issues/12746, /12464 — Inno Setup 6.4.0 on windows-2022, absent on windows-2025 `[CITED]`
- jrsoftware.org (Inno Setup help) — `PrivilegesRequired=lowest`, `{localappdata}`, `{autoprograms}` `[CITED]`
- pythonguis.com / Microsoft Q&A / code4lib — PyInstaller AV/SmartScreen false-positive surface `[CITED]`
- andreasrohner.at / hermes-agent#41178 / OpenAsar capybara — Windows self-replace-while-running: launcher-owns-child + rename-swap pattern, file-lock (WinError 32) `[CITED]`

### Tertiary (LOW confidence)
- minisign `-H` prehash exact flag behavior on 0.12 — confirm at Phase 32 plan time `[ASSUMED]`
- Medium/DEV embeddable-python how-tos — corroborate `._pth`/`pip --target` but non-authoritative `[ASSUMED]`

## Metadata

**Confidence breakdown:**
- Bundled-runtime strategy (embeddable vs PyInstaller): HIGH — official docs + documented AV surface + PKG-01's explicit onedir/no-single-file constraint all point one way.
- Data separation (PKG-03): HIGH — verified against actual `config.py`; change is small and the risk line (`backup_dir`) is identified.
- Launcher sequencing (PKG-04): HIGH on the rename/PID-ownership pattern (well-documented Windows constraint); MEDIUM on graceful-shutdown timing specifics (A6).
- Signing pipeline (PKG-05): HIGH on minisign CLI + the offline two-stage resolution; MEDIUM on the exact GitHub Action versions/runner image pinning.
- Inno Setup CI specifics: MEDIUM — runner image version drift (2022 vs 2025) is real; mitigated by explicit install step.

**Research date:** 2026-07-22
**Valid until:** ~2026-08-21 (30 days; stable tooling. Re-verify Inno Setup runner-image availability and minisign latest at plan time.)
