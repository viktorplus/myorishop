# Feature Research

**Domain:** Self-updating local-web desktop app distribution (single-operator Windows tool, offline-capable, GitHub-Releases auto-update)
**Researched:** 2026-07-22
**Confidence:** HIGH (feature landscape = established self-updating-app practice: Sparkle/WinSparkle, Squirrel.Windows, electron-updater, Tauri updater; dependency mapping = verified against this codebase)

> Scope guard: this is a SINGLE operator per install, NOT a managed fleet. Every enterprise
> update-management feature (channels, staged rollout, remote kill-switch, telemetry) is an
> anti-feature here. The one non-negotiable is: **an update must never lose the operator's local
> data or corrupt the SQLite DB.** That single constraint reshapes the whole feature set — it pushes
> "notify-and-confirm" and "backup-before-apply" from differentiators up into table stakes.

## Feature Landscape

### Table Stakes (Users Expect These)

Features a self-updating app is expected to have. Missing these = the update feels unsafe or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Update check on startup (online only)** | The standard cadence for a desktop app the operator launches per session; on launch it asks GitHub Releases "is there a newer tag than `__version__`?" | LOW | Reuse the online-detection already built for sync (httpx). Must be a silent no-op when offline — never block or delay app launch. |
| **Notify-and-confirm, NOT silent auto-apply** | For a data-critical single-operator tool, an update that restarts the app mid-receipt/mid-sale would interrupt work and risk a half-written operation. The operator must choose "apply now". | LOW | A dismissable banner/panel: "Доступна версия 1.42 — Обновить / Позже". This is the single most important UX decision; silent apply is an anti-feature (below). |
| **Version display reflects the installed release (before & after)** | The operator must see which version they run and confirm the update took. The header already shows `1.<N>` from `app/__init__.py::__version__`. | LOW | **Dependency:** the update payload must carry the new `__version__` (it ships inside the release archive), so after restart the header shows the new number automatically. No separate wiring — but the value must live in the packaged code, not be computed. |
| **Integrity + authenticity verification of the downloaded archive** | The client downloads and then EXECUTES fetched code. An unverified download is a remote-code-execution vector (MITM, compromised release asset). | MEDIUM | Mandatory per milestone scoping. Minimum: SHA-256 checksum published in the release + verified after download. Stronger: a detached signature (minisign/GPG/cosign) over the archive verified with a public key baked into the client. Checksum alone stops corruption but not a malicious release; a signature stops both. Recommend signature. |
| **Backup-before-apply (VACUUM INTO snapshot)** | If the migration or unpack fails, the operator's DB must be restorable. This is the data-loss firewall. | LOW | **Dependency:** reuse `app/services/backup.py::create_backup()` (WAL-safe `VACUUM INTO`, already proven). Take a fresh snapshot immediately before `alembic upgrade head`. Rollback restores this exact file. |
| **Run `alembic upgrade head` as part of apply** | A new release almost always ships schema changes; the DB must be migrated to match the new code before first use. | MEDIUM | **Dependency:** existing Alembic setup (`render_as_batch=True` for SQLite). Migration runs AFTER the code is unpacked and the backup is taken. A failed migration is the primary rollback trigger. |
| **Rollback on failure** | Any step (download, verify, unpack, migrate, restart) can fail; the operator must end up on a working previous version with intact data, never a half-updated broken install. | MEDIUM-HIGH | Strategy: stage the new version in a sibling dir, swap by rename (atomic-ish on Windows), keep the previous version dir until the new one boots healthy. On migration failure: restore the pre-update DB backup AND revert to the previous code dir. |
| **Explicit "downloading / verifying / applying / restarting" states** | The operator needs feedback during the multi-second apply so they don't kill the process mid-migration (which is exactly what corrupts data). | LOW-MEDIUM | A simple progress panel with named steps. "Не закрывайте приложение" during apply/migrate. |
| **Windows launcher self-restart after apply** | After swapping code + migrating, the app must relaunch on the new version without the operator manually re-running anything. | MEDIUM | Windows can't overwrite a running exe/locked files cleanly; the pattern is a small updater/launcher process (or the `run.bat` successor) that: stops the server, swaps dirs, runs migration, relaunches, reopens the browser. **Dependency:** the packaging/installer feature must exist first (bundled runtime + launcher). |
| **Server no-op (dialect gate)** | The central server (PostgreSQL, Docker) is the update TARGET, not a self-updating client. Auto-update logic must be inert there. | LOW | **Dependency:** mirror the shipped pattern in `app/services/sync_client.py` (`engine.dialect.name == "sqlite"` ⇒ local client; PostgreSQL ⇒ server). Same rule that drives `auto_enabled`. Update-check code guards on dialect and returns early on Postgres. |
| **Graceful offline behaviour** | The app must launch and run fully with no internet; update-check simply doesn't happen. | LOW | Already the app's core stance. The update-check is a best-effort side task, never a launch gate. |

### Differentiators (Competitive Advantage / Operator Delight)

Not required to ship safely, but each adds real value at low-to-moderate cost.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Changelog / release notes surfacing** | The operator sees WHAT changed before choosing to update — builds trust in the update. | LOW | The GitHub Release `body` is already Markdown; render it in the "Обновить?" panel. Zero extra infra (comes back in the same Releases API call that detects the new tag). |
| **Manual "Проверить обновления" button in Настройки** | Lets the operator update on demand instead of waiting for the next startup check. | LOW | Reuses the same check function the startup path calls. Good fit for the existing Настройки hub. |
| **"Позже / напомнить позже" defer** | Respects the operator mid-work; the banner reappears next launch instead of nagging. | LOW | Persist a "dismissed until >= this version / next launch" flag in settings. |
| **Periodic background re-check (in addition to startup)** | For an app left running all day, catches a release published after launch without forcing a restart to notice. | LOW | **Dependency:** reuse the zero-dependency `asyncio.sleep(interval)` loop pattern from `app/main.py::_auto_sync_loop` — no APScheduler/Celery. A slow cadence (e.g. every few hours) is plenty for one operator. |
| **Pre-flight checks (disk space, write permission, migration dry-run)** | Fails the update BEFORE touching the install if the environment can't complete it — turns a mid-apply crash into a clean "не удалось, ничего не изменено". | MEDIUM | Cheapest high-value safety add. Verify the staging dir is writable and there's room for archive + unpack before committing. |
| **"Что нового" post-update confirmation** | After restart on the new version, a one-time "Обновлено до 1.42" note closes the loop and shows the release notes again. | LOW | Compare persisted last-seen version vs current `__version__` on boot. |
| **Retain N previous version dirs** | Enables manual downgrade if a new release misbehaves, complementing DB backups. | LOW-MEDIUM | Mirror the backup-retention idea (`prune_backups` keeps newest N). Note code-rollback alone is unsafe if the DB was migrated forward — pair with the matching DB backup. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Silent auto-apply (no confirmation)** | "Just keep it updated, don't bother me" | Can restart the app mid-operation, interrupt a receipt/sale, and risk a half-committed write; the operator loses control over WHEN their tool changes. Highest data-risk option. | Notify-and-confirm (table stakes). Apply only on operator click, ideally at a safe idle/startup moment. |
| **Update channels (beta/stable/nightly)** | Sounds professional; mimics big apps | One operator, one machine — there is no audience to segment. Pure config surface and test burden with zero payoff. | A single stable line: latest published (non-prerelease) GitHub Release tag. |
| **Staged rollout / percentage rollout / remote kill-switch / fleet dashboard** | Enterprise update-management expectation | This is explicitly NOT a fleet. No central management plane exists or is wanted. | Direct client → GitHub Releases pull. The server stays a plain sync target. |
| **Delta / binary-diff patching (bsdiff, courgette)** | "Smaller, faster downloads" | Massive complexity (per-pair patch generation, patch verification, base-version tracking) to save a few MB on an app one operator updates occasionally. | Download the full release archive each time. Simple, verifiable, robust. |
| **Auto-download every release in the background before asking** | "Ready instantly when I click update" | Burns bandwidth/disk on a possibly-metered connection for updates the operator may defer; complicates the offline story. | Detect-then-download-on-confirm. Only fetch the archive after the operator says "Обновить". |
| **Self-modifying running process overwriting its own exe in place** | "Simplest, no launcher" | On Windows a running exe and open DLLs/files are locked; in-place overwrite corrupts or fails mid-write with no clean rollback. | Stage in a sibling dir + swap on restart via a small launcher/updater step. |
| **Forced/mandatory updates that block app use until applied** | "Make sure they're never on an old version" | Can strand the operator (offline, bad release, no time) with a tool that won't open — directly hostile to "must always be able to record a sale". | Updates are always optional and deferrable; the current version keeps working. |
| **Multi-version DB downgrade / reversible migrations** | "Roll back cleanly to any prior version" | Down-migrations are notoriously fragile and rarely tested; maintaining them doubles migration work. | Roll back by RESTORING THE PRE-UPDATE DB BACKUP + reverting to the previous code dir — the backup is the ground truth, not a reverse migration. |
| **Authenticode / EV code-signing of the exe** | "No SmartScreen warning; fully trusted binary" | An EV certificate is costly and bureaucratic; SmartScreen reputation still takes time. Overkill for one known operator on a known machine. | Verify the ARCHIVE with a checksum + detached signature (minisign/GPG) against a key baked into the client. Revisit Authenticode only if wider distribution ever happens. |
| **Telemetry / update analytics ("did the update succeed?")** | "Know if updates land" | One operator you can just ask; adds a network/privacy surface for no benefit. | Local post-update confirmation note; no phone-home. |

## Feature Dependencies

```
Packaging / installer (bundled runtime + launcher, NO git/uv)   [prerequisite milestone feature]
    └──enables──> Windows launcher self-restart
                       └──enables──> Self-updating distribution (the whole apply pipeline)

Self-updating distribution
    ├──requires──> Update check (GitHub Releases tag vs __version__)
    │                   └──requires──> Online detection (reuse sync's httpx connectivity)
    ├──requires──> Archive download
    │                   └──requires──> Integrity/authenticity verification (checksum + signature)   [MANDATORY]
    ├──requires──> Backup-before-apply  ──reuses──> app/services/backup.py::create_backup (VACUUM INTO)
    ├──requires──> alembic upgrade head ──reuses──> existing Alembic (render_as_batch)
    ├──requires──> Rollback on failure  ──requires──> Backup-before-apply + previous-version dir retained
    └──requires──> Server no-op         ──reuses──> dialect gate (sync_client.py, engine.dialect.name=="sqlite")

Version display (header __version__)  ──enhances──> post-update confirmation, notify-and-confirm panel
Changelog surfacing  ──enhances──> notify-and-confirm panel   (same Releases API response)
Periodic background re-check  ──reuses──> _auto_sync_loop asyncio.sleep pattern (app/main.py)

Silent auto-apply  ──conflicts──> "never lose local data / never interrupt an operation"
Code-only rollback ──conflicts──> forward DB migration  (must restore DB backup too)
```

### Dependency Notes

- **Self-update requires the packaging feature first:** auto-update assumes a bundled runtime and a launcher that can stop/swap/relaunch. On a `git`+`uv` dev checkout there is nothing coherent to "unpack over". Packaging must land before (or with) self-update.
- **Backup-before-apply is the rollback mechanism:** rollback is not a separate reverse-migration system — it is "restore the `VACUUM INTO` snapshot taken seconds earlier + revert to the retained previous code dir". The two are one feature.
- **Verification gates execution:** the download is executable code, so checksum/signature verification MUST pass before unpack. Treat a verification failure as a hard stop, not a warning.
- **Server no-op reuses the shipped dialect signal:** the exact rule that sets `auto_enabled=1` on SQLite clients and `0` on the PostgreSQL server (`sync_client.py`) is the rule that must disable update-check on the server. One consistent role signal.
- **Version number ships inside the payload:** because the header reads `app/__init__.py::__version__`, the new value must be present in the unpacked release. The update doesn't "set" the version — it replaces the file that defines it, so restart shows it automatically.
- **DB must live OUTSIDE the overwritten install dir:** if the SQLite file sits inside the directory the update replaces, a swap could destroy it. The DB (and backups) must live in a stable per-user data location that updates never touch. **Flag this to architecture/roadmap — it is the top data-loss risk in this milestone.**

## MVP Definition

### Launch With (this milestone, v4.0)

The minimum for a SAFE self-updating single-operator Windows client.

- [ ] **Packaging/installer with bundled runtime + launcher** — prerequisite; nothing to update without it.
- [ ] **Startup update-check against GitHub Releases** (latest non-prerelease tag vs `__version__`), silent no-op offline.
- [ ] **Notify-and-confirm panel** ("Доступна версия X — Обновить / Позже"), never silent apply.
- [ ] **Download + checksum & signature verification** of the release archive — mandatory security gate.
- [ ] **Backup-before-apply** via existing `create_backup()` (VACUUM INTO).
- [ ] **Staged unpack + `alembic upgrade head` + swap** with named progress states.
- [ ] **Rollback on any failure** — restore DB backup + revert to previous code dir; app still opens on the old version.
- [ ] **Windows launcher self-restart** onto the new version, reopening the browser.
- [ ] **Server no-op via dialect gate** — inert on PostgreSQL.
- [ ] **DB/backups relocated to a stable per-user data dir** the update never overwrites (data-safety prerequisite).

### Add After Validation (v4.x)

- [ ] **Changelog/release-notes rendering** in the confirm panel — add once the basic apply pipeline is trusted (near-free, high delight).
- [ ] **Manual "Проверить обновления" button** in Настройки.
- [ ] **"Позже / напомнить позже" defer + post-update "Обновлено до X" note.**
- [ ] **Pre-flight checks** (disk space, writable staging, migration dry-run).

### Future Consideration (later)

- [ ] **Periodic background re-check** — only if operators routinely leave the app running for very long sessions; startup-check covers most cases.
- [ ] **Retain N previous version dirs for manual downgrade** — pair carefully with DB backups (code rollback alone is unsafe after a forward migration).
- [ ] **Authenticode/EV signing of the launcher exe** — only if distribution ever widens beyond known machines.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Packaging/installer (bundled runtime + launcher) | HIGH | HIGH | P1 |
| Startup update-check vs GitHub Releases | HIGH | LOW | P1 |
| Notify-and-confirm (no silent apply) | HIGH | LOW | P1 |
| Archive download + checksum & signature verify | HIGH | MEDIUM | P1 |
| Backup-before-apply (reuse VACUUM INTO) | HIGH | LOW | P1 |
| Staged unpack + `alembic upgrade head` + swap | HIGH | MEDIUM | P1 |
| Rollback on failure | HIGH | MEDIUM-HIGH | P1 |
| Windows launcher self-restart | HIGH | MEDIUM | P1 |
| Server no-op (dialect gate) | HIGH | LOW | P1 |
| DB/backups moved out of the install dir | HIGH | LOW-MEDIUM | P1 |
| Progress/state surfacing during apply | MEDIUM | LOW-MEDIUM | P1 |
| Changelog/release-notes surfacing | MEDIUM | LOW | P2 |
| Manual "Check for updates" button | MEDIUM | LOW | P2 |
| "Later"/defer + post-update confirmation | MEDIUM | LOW | P2 |
| Pre-flight disk/permission/migration checks | MEDIUM | MEDIUM | P2 |
| Periodic background re-check | LOW-MEDIUM | LOW | P3 |
| Retain previous versions for downgrade | LOW-MEDIUM | LOW-MEDIUM | P3 |
| Authenticode/EV exe signing | LOW | HIGH | P3 |

**Priority key:** P1 = must have for a safe launch · P2 = should have, add soon after · P3 = nice to have / future.

## Competitor Feature Analysis

How established self-updating desktop frameworks handle the same problems, and our fit.

| Concern | Squirrel.Windows / electron-updater | Sparkle / WinSparkle | Tauri updater | Our Approach |
|---------|-------------------------------------|----------------------|---------------|--------------|
| Update source | GitHub Releases / feed URL | Appcast XML feed | Static JSON manifest + GitHub | **GitHub Releases API (latest non-prerelease tag)** — reuse existing GitHub infra |
| Authenticity | Code-signed installers | DSA/EdDSA signature over the archive | Ed25519 signature (mandatory) | **Checksum + detached signature (minisign/GPG) over the archive; public key baked in** — Tauri-style, no cert bureaucracy |
| Apply model | Background download, apply on quit/restart | Notify → download → relaunch | Download → verify → replace → relaunch | **Notify-and-confirm → verify → stage → backup → migrate → swap → relaunch** (extra DB backup + migration steps they don't have) |
| Rollback | Limited (keeps prior app dir) | None built in | None built in | **Explicit: DB backup restore + previous-dir revert** — stronger, because we carry a stateful SQLite DB they don't |
| Release notes | Optional | Appcast description shown | Manifest `notes` field | **Render the GitHub Release Markdown body** in the confirm panel |
| DB migration | N/A (apps are stateless) | N/A | N/A | **`alembic upgrade head` inside apply** — our differentiating risk; none of these frameworks migrate a user DB, so we can't lift their flow wholesale |

> Key insight: general desktop updaters assume a **stateless** app — swap files, relaunch, done. Our
> differentiator (and our risk) is a stateful **SQLite DB + schema migration**. That is exactly why
> backup-before-apply and DB-aware rollback move up to table stakes here, and why silent auto-apply
> and code-only rollback become anti-features.

## Data-Safety Flags (for architecture / roadmap)

1. **DB and backups must NOT live inside the directory an update overwrites.** Relocate to a stable per-user data dir first; otherwise a swap can delete the operator's data. Top risk.
2. **Forward migration is one-way in practice.** Rollback = restore the pre-update `VACUUM INTO` backup, never a reverse Alembic migration.
3. **Never apply while an operation may be mid-write.** Apply at startup or an explicit confirmed idle moment; guard against interrupting a ledger write.
4. **Downloaded code is executed → verification is a hard gate, not a warning.** Checksum + signature must pass before unpack.
5. **The apply sequence must be crash-safe at every step:** verify → backup → stage → migrate → swap → relaunch, with the previous version retained until the new one boots healthy.

## Sources

- Established self-updating-app frameworks and their documented UX/security models: Squirrel.Windows, electron-updater, Sparkle/WinSparkle (appcast + signed archive), Tauri updater (mandatory Ed25519 signature) — practitioner consensus, HIGH confidence on the feature landscape.
- This codebase (verified 2026-07-22): `app/__init__.py` (`__version__` header source), `app/services/backup.py` (`create_backup` VACUUM INTO, `startup_backup` dialect gate), `app/services/sync_client.py` (SQLite-vs-Postgres role signal, `auto_enabled`), `app/main.py` (`lifespan`, `startup_backup()`, zero-dependency `_auto_sync_loop` asyncio cadence), existing Alembic setup (`render_as_batch`).
- `.planning/PROJECT.md` — v4.0 "Distribution & Delivery" milestone scope and open questions.

---
*Feature research for: self-updating single-operator Windows local-web app (GitHub Releases auto-update)*
*Researched: 2026-07-22*
