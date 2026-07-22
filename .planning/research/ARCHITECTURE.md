# Architecture Research

**Domain:** Windows self-contained, self-updating desktop distribution of a FastAPI/Uvicorn/SQLite local client (over-the-top updates from GitHub Releases)
**Researched:** 2026-07-22
**Confidence:** HIGH (grounded in the actual codebase — `app/config.py`, `app/db.py`, `app/main.py`, `app/services/backup.py`, `app/services/sync_client.py`, `run.bat`; external facts — Windows file-locking, GitHub Releases API — are stable within knowledge cutoff)

---

## The One Load-Bearing Constraint

> **A running server process cannot cleanly overwrite its own code files on Windows, and it must never touch operator data.**

Everything below follows from this. Two consequences drive the whole design:

1. **Two processes.** The thing that *applies* an update (swaps files, runs migrations, restarts) must be a **separate, long-lived launcher process** that outlives the app — not a FastAPI background task. The app can *detect, download, verify, and stage* an update, but it must **exit and hand off** the actual file swap.
2. **Code/data separation is physical, not conventional.** The update replaces a *code directory*; operator data (`data/`, `backups/`, `.env`) lives in a *different directory* that the swap never sees. This project already puts the identity/data outside the synced DB (`app/config.py` `_resolve_local_identity`, `data/secret_key`, `data/device_id`); the packaging layout must extend that separation to the code-vs-data boundary.

---

## Standard Architecture

### System Overview — two-process install

```
┌──────────────────────────────────────────────────────────────────────┐
│  INSTALL ROOT   e.g.  C:\MyOriShop\                                    │
│                                                                        │
│  ┌────────────────────────┐        ┌──────────────────────────────┐   │
│  │  launcher.exe  (STABLE) │  spawn │  app-current\  (SWAPPABLE)    │   │
│  │  long-lived parent      │───────▶│   python-runtime\  (bundled) │   │
│  │  • starts uvicorn child │        │   app\  alembic\  static\ …  │   │
│  │  • on child exit:       │        │   RELEASE  (tag string)      │   │
│  │    apply staged update  │◀──exit─│   uvicorn app.main:app       │   │
│  │    swap → migrate → boot │  code  └──────────────────────────────┘   │
│  │    rollback on failure  │                                            │
│  └───────────┬────────────┘                                            │
│              │ reads/writes                                            │
│  ┌───────────▼──────────┐  ┌───────────────┐  ┌────────────────────┐  │
│  │ updates\ (SWAP AREA)  │  │ data\ (NEVER   │  │ backups\  .env      │  │
│  │  staging\<tag>\        │  │ TOUCHED)       │  │ (NEVER TOUCHED)     │  │
│  │  pending.json          │  │  myorishop.db  │  │  pre-update snaps    │  │
│  │  app.prev\ (rollback)  │  │  secret_key    │  │  SECRET_KEY          │  │
│  └────────────────────────┘  │  device_id     │  │  sync_token          │  │
│                              └───────────────┘  └────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                    ▲ HTTPS (online only)
                    │  GET /repos/{owner}/{repo}/releases/latest
              ┌─────┴───────────────┐
              │  GitHub Releases     │  signed archive + SHA256SUMS + .minisig
              └──────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Where it lives / implementation |
|-----------|----------------|---------------------------------|
| **Launcher** (`launcher.exe` / stable bootstrap) | Start the uvicorn child; on child exit, read `updates/pending.json`, take the pre-update backup, swap code dir, run `alembic upgrade head`, restart; roll back the matched (code, DB) pair on any failure | NEW — native exe or a *tiny* Python script run by a stable interpreter that is **not** inside `app-current\` (so it is never swapped mid-run) |
| **Update service** (`app/services/updates.py`) | Query GitHub `releases/latest`, compare tag to installed `RELEASE`, download the asset, verify SHA-256 **and** signature, unpack to `updates/staging/<tag>/`, write `pending.json`. **Dialect-gated no-op on PostgreSQL.** | NEW — mirrors `backup.py` / `sync_client.py` shape (own module, offline-safe, broad-guarded) |
| **Update UI surface** (`app/routes/settings*.py` + templates) | Admin-only "Проверить обновления" → show installed vs latest → "Обновить и перезапустить" → stage + trigger controlled shutdown | NEW routes + partials under the existing `settings` router (already `require_role("administrator")`) |
| **Release pipeline** (`.github/workflows/release.yml` + `scripts/build_release.py`) | On tag push: build the distributable archive, generate `SHA256SUMS`, sign it, upload all as release assets | NEW — the *producer* side; must exist before any client can self-update |
| **Existing backup service** (`app/services/backup.py`) | Take the **pre-update** VACUUM-INTO snapshot (the DB rollback anchor) | REUSED unchanged — `create_backup()` already WAL-safe and standalone |
| **Existing alembic** (`alembic upgrade head`) | Forward-migrate the SQLite schema after the code swap | REUSED — already invoked by `run.bat`/`install.bat`; launcher calls the same command |
| **Bundled runtime** (`python-runtime\`) | Run the app with no dev toolchain, no `uv`, no git on the operator machine | NEW packaging artifact (see "Packaging strategy") |

---

## Recommended Project Structure

### Runtime install layout (on the operator's machine)

```
C:\MyOriShop\                     # install root (chosen at install time)
├── launcher.exe                  # STABLE parent — never swapped while running
├── app-current\                  # SWAPPABLE code dir (the only thing an update replaces)
│   ├── python-runtime\           #   bundled Python + site-packages (frozen deps)
│   ├── app\                      #   the FastAPI source tree (unchanged from repo)
│   ├── alembic\  alembic.ini     #   migrations, run post-swap
│   ├── RELEASE                   #   e.g. "v1.126" — the installed release tag
│   └── updater_pubkey.pem        #   vendored PUBLIC signing key (verify-only)
├── updates\                      # SWAP scratch — gitignored, not data, not code
│   ├── staging\<tag>\            #   verified-unpacked next version
│   ├── app.prev\                 #   previous code dir kept for rollback
│   └── pending.json              #   {tag, staged_path, sha256, pre_update_backup}
├── data\                         # OPERATOR DATA — update NEVER touches this
│   ├── myorishop.db (+ -wal/-shm)
│   ├── secret_key                #   per-install signing key (app/config.py)
│   └── device_id                 #   per-install sync identity
├── backups\                      # VACUUM-INTO snapshots incl. pre-update anchor
└── .env                          # SECRET_KEY / sync_token / DATABASE_URL (untouched)
```

### Repository additions (new files vs modified)

```
NEW
├── launcher\                     # launcher source (native or stable-python bootstrap)
│   └── launcher.py / launcher.rs / .c
├── app\services\updates.py       # detect/download/verify/stage service (dialect-gated)
├── app\routes\updates.py         # (or extend settings.py) admin update UI routes
├── app\templates\...\updates.html + partials
├── scripts\build_release.py      # produce the distributable archive + SHA256SUMS
├── .github\workflows\release.yml # tag-triggered build+sign+upload
└── app-current\RELEASE           # written at build time (installed release tag)

MODIFIED
├── app\config.py                 # + github_repo, update_check_on_startup, updates_dir,
│                                 #   data root paths that resolve OUTSIDE app-current\
├── app\main.py                   # + optional startup update-check & auto-update loop
│                                 #   (mirror _auto_sync_loop); controlled-shutdown hook
├── app\__init__.py / routes\__init__.py  # header shows installed RELEASE tag, not just
│                                 #   the source __version__ counter
├── run.bat                       # stays for DEV; the distribution boots via launcher.exe
├── pyproject.toml                # + verify-only signature dep (cryptography or pynacl)
└── .gitignore                    # + updates\
```

### Structure Rationale

- **`app-current\` is the atomic unit of replacement.** A directory rename on the same volume is atomic on Windows; keeping the whole runnable app (including its bundled deps) in one dir means "apply update" = "rename dirs", never a partial file-by-file patch.
- **`updates\`, `data\`, `backups\`, `.env` are siblings of `app-current\`, not children.** The swap physically cannot reach them. This is the data-preservation guarantee, enforced by layout rather than by careful code.
- **The launcher is outside `app-current\`.** If it lived inside the swapped dir it would be holding open the very files it's trying to replace — the exact self-replace-while-running trap.

---

## Architectural Patterns

### Pattern 1: In-app *stage*, external launcher *apply* (the self-replace fix)

**What:** The FastAPI app does everything that is safe to do while running — check, download, verify signature+checksum, unpack to `updates/staging/<tag>/`, take a pre-update backup, write `pending.json`. It then requests a **controlled shutdown**. The launcher, seeing the child exit with a "pending update" signal, performs the swap while nothing holds the code files open.

**When to use:** Always, for a running server that must replace its own files on Windows.

**Trade-offs:** Requires a second process and an exit/hand-off protocol (a marker file + exit code). Buys correctness — no locked-file failures, no half-imported modules.

**Handoff sketch:**
```python
# app/services/updates.py  (runs INSIDE the app, old code)
def stage_update(release) -> None:
    archive = download_asset(release)                 # httpx (already a dep)
    verify_sha256(archive, release.sha256)            # integrity
    verify_signature(sums_file, PUBKEY)               # authenticity — MANDATORY
    staged = unpack(archive, UPDATES / "staging" / release.tag)
    pre_backup = backup.create_backup(engine, BACKUPS)  # DB rollback anchor (reuse!)
    write_json(UPDATES / "pending.json", {
        "tag": release.tag, "staged_path": str(staged),
        "pre_update_backup": str(pre_backup),
    })
    request_shutdown()   # signal launcher; do NOT touch app-current\ from here
```
```text
launcher.exe loop:
  start child (uvicorn) ; wait for exit
  if updates/pending.json exists:
      apply_update()            # swap → migrate → verify boot, else rollback
  restart child
```

### Pattern 2: Swap → migrate → rollback as a *matched (code, DB) pair*

**What:** Code and schema move together. The launcher, after the app has exited:
1. rename `app-current\` → `updates\app.prev\`  (rollback copy of the OLD code)
2. rename `updates\staging\<tag>\` → `app-current\`  (the NEW code)
3. run `alembic upgrade head` using the NEW code against the untouched `data\myorishop.db`
4. start the new app; probe `http://127.0.0.1:8000` for a healthy boot

**Rollback** (any step 3–4 fails): restore `app.prev` → `app-current`, **and** restore `data\myorishop.db` from `pending.json.pre_update_backup`, then relaunch the old version. The DB restore is essential — a partially-applied migration leaves a schema the old code can't read; the pre-update backup is the only safe anchor.

**When to use:** Any over-the-top update that runs migrations.

**Trade-offs:** Keeping `app.prev` doubles the code-dir disk footprint transiently (cheap). Restoring both halves together is the only way to avoid a code/schema mismatch.

### Pattern 3: Dialect-gated role no-op (auto-update is a no-op on the server)

**What:** The update service short-circuits on the central PostgreSQL server exactly the way `sync_client` already decides auto-sync defaults — the **DB dialect is the role signal, no separate flag**.

**When to use:** Every entry point of the update service (startup check, periodic loop, UI route, launcher apply).

**Example (mirror of the shipped `sync_client` gate at `sync_client.py:90`):**
```python
# app/services/updates.py
def updates_enabled(engine) -> bool:
    # The central server is PostgreSQL + Docker; it is the update TARGET,
    # never a self-updating client. Mirrors sync_client is_local_client.
    return engine.dialect.name == "sqlite"
```
Belt-and-suspenders: the Docker server never ships `launcher.exe` at all, and its `.env` can leave `github_repo`/`update_check_on_startup` empty (env wins over defaults, same posture as `SYNC_SERVER_URL=""` and `SESSION_HTTPS_ONLY`). Two independent guards, both already-established idioms.

### Pattern 4: Startup check + optional periodic loop (mirror `_auto_sync_loop`)

**What:** Reuse the exact background-loop shape already in `app/main.py`. A `_auto_update_loop` (or a one-shot startup check) reads its on/off toggle fresh each tick, offloads the blocking network call off the event loop via `anyio.to_thread.run_sync`, and swallows offline/transport errors so a missing internet connection is a silent no-op (the app is offline-capable by requirement).

**When to use:** For the "when connected, auto-update" cadence. **Recommendation:** *notify + apply-on-confirm/next-restart*, not silent auto-apply — the app runs fetched code, and a surprise restart mid-sale is hostile. Download+verify+stage silently in the background; surface "доступна версия v1.126 — обновить и перезапустить" and let the admin pick the moment. This also keeps the security-sensitive "apply" behind an explicit human action.

---

## Data Flow

### Update flow (happy path)

```
[startup / periodic tick]  (sqlite only; postgres → no-op)
      ↓
GET releases/latest ──▶ tag_name "v1.126"
      ↓ compare to app-current\RELEASE "v1.125"   (newer? online?)
[download asset] ─httpx─▶ myorishop-v1.126.zip
      ↓
verify SHA-256  AND  verify Ed25519 signature of SHA256SUMS  ← MANDATORY gate
      ↓ (fail → discard, log-free skip, stay on current)
unpack → updates\staging\v1.126\
      ↓
backup.create_backup()  → backups\myorishop-<ts>.db   (pre-update DB anchor)
      ↓
write updates\pending.json ; request controlled shutdown
      ↓                          ┌──────────── launcher takes over ────────────┐
app process exits  ──────────────▶ swap app-current ↔ staging (app.prev kept)  │
                                 │ alembic upgrade head  (new code, same data\) │
                                 │ start uvicorn ; health-probe 127.0.0.1:8000  │
                                 │   ok → delete app.prev ; header shows v1.126 │
                                 │   fail → restore app.prev + restore pre-DB   │
                                 │          backup → relaunch v1.125            │
                                 └──────────────────────────────────────────────┘
```

### What moves vs what is pinned

| Category | Members | On update |
|----------|---------|-----------|
| **CODE (replaced)** | `app-current\` = python runtime + `app\` + `alembic\` + templates/static + `RELEASE` + vendored pubkey | Swapped atomically; old kept as `app.prev` for rollback |
| **DATA (pinned)** | `data\myorishop.db` (+ WAL/shm), `data\secret_key`, `data\device_id` | Never touched; only *read* by `alembic upgrade`, and snapshotted first |
| **CONFIG (pinned)** | `.env` — `SECRET_KEY`, `sync_token`, `DATABASE_URL` | Never touched (sits outside `app-current\`) |
| **BACKUPS (pinned, appended)** | `backups\` incl. the pre-update anchor | Never overwritten; pre-update snapshot added |

**Config change this forces:** today `db_path`/`backup_dir`/`catalogs_dir` default to paths *relative to CWD* (`data/…`, `backups/…` in `app/config.py`). In the packaged layout the working dir is inside/near `app-current\`, so these defaults must resolve to the **install-root siblings**, not paths inside the swappable code dir. Set them via the pinned `.env` (or launcher-exported env) to absolute install-root paths. This is the single most important packaging edit — get it wrong and an update wipes the DB.

---

## Packaging Strategy (the phase-A decision)

**Recommendation: ship source + a bundled Python runtime; do NOT use PyInstaller.**

The project's own `CLAUDE.md` already rejected PyInstaller/cx_Freeze for v1 ("notoriously fiddly… a rabbit hole… revisit real packaging in a later milestone"). This *is* that milestone, and the self-update requirement makes the case even stronger:

| Option | Fit for self-update | Verdict |
|--------|--------------------|---------|
| **Bundled runtime + source dir** (Python embeddable zip *or* a copied uv venv, plus the `app\` tree) | Update = replace a directory of `.py` + deps. `.py` files aren't OS-locked like a mapped `.exe`. Aligns 1:1 with the existing `run.bat` + `alembic upgrade` flow. | **RECOMMENDED** |
| PyInstaller **onefile** | The whole app is one `.exe` the OS maps and locks while running — cannot be patched in place; forces the exe to relaunch a replacement of itself. Hidden-import/uvicorn/watchfiles hooks already flagged as fiddly. | Avoid |
| PyInstaller **onedir** | Better than onefile (dir swap possible) but still adds freezing complexity and hidden-import risk for zero benefit over shipping source. | Avoid |

The only compiled artifact worth building is the **launcher** — a tiny, stable, rarely-changing parent (a small Go/Rust/C exe, or a stable-python bootstrap). It is deliberately *not* part of the swappable set, so it never needs freezing gymnastics and never self-replaces mid-run.

---

## Security Model (fetched code — mandatory gates)

The client executes code fetched from the internet. Two gates, both required:

1. **Integrity — SHA-256.** Publish `SHA256SUMS` as a release asset; verify the downloaded archive matches before unpacking. Protects against truncation/corruption. *Not* sufficient alone (an attacker who can replace the asset can replace the sums file too).
2. **Authenticity — detached signature.** Sign `SHA256SUMS` with an **Ed25519** key (minisign, or `cryptography`/`pynacl` verify-only in ~15 lines). **Public key vendored** into `app-current\updater_pubkey.pem`; **private key never in the repo** — held only as a CI secret or signed on the maintainer's machine. This is what stops a malicious/compromised release asset from being trusted.

Additional posture: fetch over **HTTPS only**; use `releases/latest` (excludes drafts/prereleases so a beta is never auto-served); never log the sync token or secret_key (existing `CLAUDE.md` rule) — the update path must uphold the same. Verify signature **before** unpacking (never unpack untrusted archives to a path you then execute).

---

## Version Detection & Tie-in

- **Installed version:** written to `app-current\RELEASE` at build time (e.g. `v1.126`). The running app reads it; the header shows it (extend the existing `APP_VERSION` template global in `app/routes/__init__.py`, which today only reads the plain `__init__.__version__` counter).
- **Latest version:** `releases/latest.tag_name` from GitHub.
- **Comparison:** the project's scheme is `"1.<N>"` — a *plain incrementing counter, not semver* (per `app/__init__.py`). Map release tags to it (`v1.<N>`) and compare the integer `N`; "newer if latest N > installed N". Do **not** pull semver ordering libraries — the counter is monotonic by construction.
- Guard the check behind connectivity (offline → silent skip) and the dialect gate (postgres → never checks).

---

## Scaling Considerations (installs & release cadence, not users)

| Scale | Adjustment |
|-------|-----------|
| 1 operator / 1 install (today) | Manual or CI-produced release; startup check is plenty. No update server needed — GitHub Releases is the CDN. |
| A handful of country operators (v3.0 sync world) | Same mechanism; unauthenticated `releases/latest` is 60 req/hr per IP — trivially within budget for per-startup checks. |
| Frequent releases | Add release notes to the GitHub Release body and surface them in the update UI; keep `backup_keep` retention aware of the extra pre-update snapshots. |

### Scaling priorities
1. **First thing that "breaks":** a bad release bricking installs. Mitigation is the rollback pair (Pattern 2) + notify-don't-silently-apply, not more infrastructure.
2. **Second:** GitHub rate limits on aggressive periodic checks — cap cadence (once per startup + at most hourly) and treat 403/rate-limit as a silent skip.

---

## Anti-Patterns

### Anti-Pattern 1: The server updates its own running files (in-app apply)
**What people do:** A FastAPI background task downloads and overwrites `app\` while uvicorn is serving.
**Why it's wrong:** On Windows, open/mapped files (the interpreter, DLLs, `.pyd`, even a module mid-import) can't be replaced; you get `PermissionError`/`WinError 32`, or worse a half-swapped tree that imports inconsistent modules.
**Do this instead:** App *stages*; external launcher *applies* after the app exits (Pattern 1).

### Anti-Pattern 2: PyInstaller onefile for a self-updating app
**What people do:** Freeze everything into one `.exe`, then try to auto-update it.
**Why it's wrong:** A onefile exe is locked while running and can't be partially patched; freezing FastAPI/uvicorn/watchfiles is exactly the hidden-import rabbit hole `CLAUDE.md` already called out.
**Do this instead:** Ship source + bundled runtime; swap a directory (Packaging Strategy).

### Anti-Pattern 3: `data\` (or `.env`) inside the swappable code dir
**What people do:** Keep `data/myorishop.db` under `app-current\data\` because that's where CWD points today.
**Why it's wrong:** The atomic dir-swap then deletes/replaces the operator's DB, `secret_key`, and `device_id` — total data loss, and a new `secret_key` invalidates every session and breaks sync identity.
**Do this instead:** Data/backups/.env are *siblings* of `app-current\`; point config at absolute install-root paths (the required config edit).

### Anti-Pattern 4: `alembic upgrade head` without a matched pre-update backup
**What people do:** Migrate first, "we'll deal with failure later."
**Why it's wrong:** A partially-applied migration leaves a schema neither old nor new code fully handles; without a snapshot there's no way back.
**Do this instead:** Snapshot (reuse `backup.create_backup`) → swap code → migrate → on failure restore the *pair* (old code **and** pre-update DB).

### Anti-Pattern 5: Auto-applying unverified fetched code
**What people do:** Download the release zip and run it because it came from GitHub over HTTPS.
**Why it's wrong:** A compromised release asset (or MITM on a mis-configured mirror) becomes remote code execution on the operator's machine.
**Do this instead:** Mandatory SHA-256 + Ed25519 signature verified *before* unpack; private key never in the repo (Security Model).

---

## Integration Points

### External services

| Service | Integration pattern | Notes / gotchas |
|---------|--------------------|-----------------|
| GitHub Releases API | `GET /repos/{owner}/{repo}/releases/latest` → `tag_name`, `assets[].browser_download_url` | Unauthenticated for a public repo (60 req/hr/IP — fine). Excludes drafts/prereleases (won't serve a beta). Use `httpx` (already a dependency). |
| GitHub release asset download | HTTPS GET of `browser_download_url` | Stream to `updates\`; verify before unpack. |
| Signing key | Ed25519 (minisign or `cryptography`/`pynacl`) | Public key vendored in client; **private key = CI secret / offline only**, never committed. |

### Internal boundaries (reuse, don't rebuild)

| Boundary | Communication | Notes |
|----------|---------------|-------|
| updates service ↔ `app/services/backup.py` | direct call `create_backup(engine, backups_dir)` | Pre-update DB anchor — already WAL-safe/standalone; do not reinvent. |
| launcher ↔ alembic | subprocess `alembic upgrade head` (new code) | Same command `run.bat`/`install.bat` already run; keep `render_as_batch=True`. |
| updates service ↔ dialect role signal | `engine.dialect.name == "sqlite"` | Mirror `sync_client` `is_local_client` (`sync_client.py:90`); postgres = no-op. |
| update UI ↔ auth | mount under `settings` router (`require_role("administrator")`) | Update is an admin action; reuse the shipped server-side role gate. |
| app ↔ launcher | `updates\pending.json` + controlled-shutdown signal (marker file / exit code) | The only IPC needed; keep it a plain file contract. |
| version display ↔ header | `APP_VERSION` template global in `routes/__init__.py` | Point it at `app-current\RELEASE`, not just the source counter. |
| main.py lifespan ↔ update loop | mirror `_auto_sync_loop` / `_auto_sync_iteration` | Same offload + broad-guard + fresh-config-each-tick pattern. |

---

## Suggested Build Order (dependencies respected)

**Phase A — Packaging & the launcher (must come first).** You cannot self-update to a release format and an apply-mechanism that don't exist yet.
- Bundled-runtime distributable (`scripts/build_release.py`) producing `app-current\` + `launcher.exe`.
- Install-root layout with the **code/data separation** and the config edit pointing `data\`/`backups\`/`.env` at install-root siblings.
- The launcher: start child, and — even before anything stages updates — implement **apply** (swap + `alembic upgrade` + pre-update backup + rollback). This is independently testable by *manually* dropping a staged dir + `pending.json`.
- `.github/workflows/release.yml`: tag-triggered build, `SHA256SUMS`, **signature**, asset upload. The signing-key setup (public key vendored, private key as CI secret) lands here.
- **Exit criterion:** two releases exist and a hand-placed `pending.json` makes the launcher swap+migrate+restart, with a proven rollback.

**Phase B — In-app self-update (builds on A).**
- `app/services/updates.py`: check `releases/latest`, compare `RELEASE`, download, **verify SHA-256 + signature**, unpack to staging, take pre-update backup, write `pending.json`, request shutdown. Dialect-gated no-op.
- `app/main.py`: startup check + optional periodic loop (mirror `_auto_sync_loop`); controlled-shutdown hook.
- Admin update UI (installed vs latest, "Обновить и перезапустить", release notes) under the `settings` router.
- Header version tie-in to `RELEASE`.
- **Exit criterion:** clean install on v1.<N> detects and (on operator confirm) updates itself to v1.<N+1>, operator data intact, header reflects the new tag, and an intentionally-broken release rolls back cleanly.

> **Chicken-and-egg to plan around:** end-to-end self-update testing needs *two* real releases. Cut a throwaway v1.<N> and v1.<N+1> early in Phase B (or late in Phase A) purely to exercise the round trip.

---

## Sources

- Codebase (read directly, HIGH): `app/config.py` (`_resolve_local_identity`, data-outside-DB identity, env-wins pattern), `app/db.py` (`build_engine_from_url`, dialect gate, WAL/foreign_keys pragmas), `app/main.py` (`lifespan`, `_auto_sync_loop`, role-gated routers), `app/services/backup.py` (`create_backup` VACUUM INTO, WAL-safe), `app/services/sync_client.py:90` (dialect = role signal, offline-safe short-circuit), `app/routes/__init__.py` (`APP_VERSION` global), `app/__init__.py` (`"1.<N>"` counter scheme), `run.bat` / `install.bat` (`alembic upgrade head` boot flow), `.github/workflows/ci.yml`, `pyproject.toml`, `.gitignore`, `data/` layout.
- `.planning/PROJECT.md` — v4.0 milestone scope and scoping notes (HIGH).
- `CLAUDE.md` — stack, PyInstaller rejection rationale, data-outside-DB and backup patterns (HIGH).
- Windows file-locking (running executable / open module files cannot be replaced in place) — stable platform behavior, practitioner consensus (HIGH).
- GitHub REST `GET /repos/{owner}/{repo}/releases/latest` shape (`tag_name`, `assets[].browser_download_url`, excludes drafts/prereleases; 60 req/hr unauthenticated) — stable public API (HIGH).
- Ed25519 detached-signature / minisign update-authenticity pattern; atomic same-volume directory rename for staged swaps — established distribution practice (MEDIUM-HIGH on exact tooling choice, HIGH on approach).

---
*Architecture research for: Windows self-updating FastAPI/SQLite desktop distribution (GitHub Releases)*
*Researched: 2026-07-22*
