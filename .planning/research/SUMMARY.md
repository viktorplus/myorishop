# Project Research Summary

**Project:** MyOriShop — Oriflame Warehouse Inventory (v4.0 "Distribution & Delivery")
**Domain:** Windows self-contained packaging + secure GitHub-Releases self-update for a FastAPI/Uvicorn/SQLite offline-first desktop client
**Researched:** 2026-07-22
**Confidence:** HIGH

## Executive Summary

v4.0 turns the already-shipped local client into something a non-technical Oriflame reseller can install on a bare Windows machine (no Python, no uv, no git, works offline) and that can safely upgrade itself from GitHub Releases. All four research files converge on one load-bearing constraint: a running server process cannot cleanly overwrite its own code files on Windows, and it must never touch operator data. Every recommendation flows from that. The answer is a two-process design — the FastAPI app detects/downloads/verifies/stages an update while running, then exits and hands off to a separate long-lived launcher (living outside the swappable code directory) that performs the actual directory swap, runs `alembic upgrade head`, restarts, and rolls back on any failure.

The second pillar is data preservation by physical layout, not by careful code. The SQLite DB, the .env, the per-install secret_key/device_id, and the backups/ folder must be siblings of a swappable app-current/ directory, never children of it — so an atomic directory-swap physically cannot reach them. Relocating this state out of the install/CWD-relative defaults is a Phase-A prerequisite; getting it wrong wipes the only copy of the operator's ledger. The third pillar is security-first authenticity: because the client executes fetched code, verification is a hard gate. A SHA-256 checksum proves integrity but not authenticity (an attacker who replaces the asset replaces the checksum too). The mandatory control is an Ed25519 detached signature (minisign) over the signed asset/manifest, verified against a public key vendored into the client, with the private key held offline / signed in CI — never in the repo. Verify the signed asset, not the mutable git tag, and enforce anti-downgrade (apply only if strictly newer).

The work is cleanly two dependency-ordered phases. Phase A (packaging + launcher + data relocation + signed-release pipeline) must exist before anything can self-update — there is no release format or apply-mechanism to update to yet. Phase B (in-app update-check, notify-and-confirm, verified download, staged apply, migrate, rollback, version tie-in, server no-op) builds on it and is the security-critical, threat-modelled phase. Throughout, the design reuses shipped mechanisms: `backup.create_backup()` (WAL-safe VACUUM INTO) as the pre-update DB anchor, the dialect gate (`engine.dialect.name == "sqlite"`) to make auto-update a hard no-op on the PostgreSQL central server, the `_auto_sync_loop` background-loop shape for periodic checks, and the `__version__`/RELEASE header tie-in. The biggest single risk beyond data loss is a version-compare bug: the "1.N" scheme breaks under string compare ("1.9" > "1.10" is True) — compare the integer N.

## Key Findings

### Recommended Stack

This is an additive pass — the running app stack (Python 3.13, FastAPI 0.139, Uvicorn, SQLAlchemy 2.0, SQLite, Jinja2, HTMX 2.0.10 vendored, Alembic, httpx) is already shipped. The only new runtime dependency the client gains is py-minisign (+ transitive cryptography) for signature verification. Everything else is stdlib, the already-present httpx, or build-time-only. The recommended packaging strategy is a bundled Python runtime + plain source in a "onedir" layout (Python embeddable zip, or PyInstaller --onedir as fallback) — never --onefile, which self-locks and defeats the directory-swap/rollback model.

**Core technologies:**
- Python Windows embeddable package (CPython 3.13) — bundled runtime; uses python.org's already-signed python.exe/pythonw.exe (no console window), sidesteps PyInstaller AV false-positives, lets Alembic/uvicorn run as normal files.
- Inno Setup 6.7.3 — builds the Windows installer (Start-Menu shortcut, uninstaller, install to %LOCALAPPDATA%); scriptable, SignTool-ready if a cert is added later.
- py-minisign 0.13.2 (verify) + minisign CLI 0.12 (sign) — Ed25519 detached-signature authenticity; public key baked into the client, secret key stays offline. The security control that actually matters.
- httpx 0.28.1 (already a dep) — GitHub Releases API calls + streamed asset download; no new networking dependency.
- Reuse uv at build time to export pinned deps into the bundle; no uv on the operator machine.

### Expected Features

The domain is established self-updating-app practice (Sparkle/WinSparkle, Squirrel.Windows, electron-updater, Tauri updater). The one non-negotiable that reshapes everything: an update must never lose operator data or corrupt the SQLite DB. That pushes notify-and-confirm and backup-before-apply up from "nice" into table stakes. This is a single operator per install, not a managed fleet — every enterprise update-management feature is an anti-feature here.

**Must have (table stakes):**
- Startup update-check vs GitHub Releases latest tag (silent no-op offline) — expected desktop cadence.
- Notify-and-confirm, NOT silent auto-apply — a mid-sale restart risks a half-written operation.
- Integrity + authenticity verification (checksum + signature) — download is executed code; hard gate.
- Backup-before-apply via existing create_backup() (VACUUM INTO) — the data-loss firewall.
- alembic upgrade head inside apply + rollback on failure + Windows launcher self-restart.
- Server no-op via dialect gate; DB/backups relocated outside the install dir.

**Should have (competitive):**
- Changelog/release-notes rendered in the confirm panel (free — same Releases API response).
- Manual "Проверить обновления" button in Настройки; "Позже/напомнить позже" defer + post-update "Обновлено до X" note.
- Pre-flight checks (disk space, writable staging, migration dry-run).

**Defer (v4.x+):**
- Periodic background re-check (startup-check covers most cases); retain-N-versions for manual downgrade; Authenticode/EV exe signing (only if distribution widens).

### Architecture Approach

A two-process install: a stable launcher.exe (never swapped while running) spawns the uvicorn child from a swappable app-current/ directory; on child exit it reads updates/pending.json, takes the pre-update backup, swaps the code dir, runs alembic upgrade head, health-probes the new boot, and rolls back the matched (code, DB) pair on any failure. updates/, data/, backups/, and .env are siblings of app-current/, so the swap physically cannot reach operator state. Code and schema move together as one unit — rollback restores both the previous code dir and the pre-update DB snapshot, because a partially-applied migration leaves a schema the old code cannot read.

**Major components:**
1. Launcher (new, stable, outside app-current/) — start child; on exit apply staged update: swap, migrate, health-check, rollback.
2. Update service (app/services/updates.py, new) — query releases/latest, compare tag to RELEASE, download, verify SHA-256 + signature, unpack to staging, take pre-update backup, write pending.json, request shutdown; dialect-gated no-op.
3. Update UI (admin-only, under existing settings router) — installed vs latest, "Обновить и перезапустить", release notes.
4. Release pipeline (.github/workflows/release.yml + scripts/build_release.py, new) — tag-triggered build, SHA256SUMS, sign, upload assets. The producer side; must exist before any client can update.
5. Reused — backup.create_backup() (pre-update anchor), Alembic (alembic upgrade head), the dialect role signal, the _auto_sync_loop loop shape, the APP_VERSION header global.

### Critical Pitfalls

1. Integrity != authenticity — checksum-only "verification" runs attacker code. Verify an Ed25519 signature against a baked-in public key before unpack; keep the signing key separate from the GitHub publish token.
2. Verifying the tag, not the asset — git tags/assets are mutable. Key updates on a signed manifest with a per-asset SHA-256 and download the explicitly uploaded signed asset (never the auto-generated source tarball).
3. Overwriting a running exe / locked files (WinError 32) — never unpack over the live install from inside the app. Stage in a sibling dir; a detached launcher does the rename-swap after the app exits.
4. Over-the-top unpack destroys the DB/.env/backups — the single most catastrophic failure. Physically separate code from data; assert the release archive contains no .db/.env/backups; back up before applying.
5. Alembic mid-update failure, half-migrated DB — recover by restoring the pre-update file backup, not downgrade() (batch migrations do not reliably reverse). Gate "success" on the app actually booting + health check.
6. No rollback, bricked install — keep the previous version on disk; auto-revert on a failed post-update health check; ship an operator-runnable RU recovery path.
7. Version-compare bug on "1.N" — string compare makes "1.9" > "1.10" True. Compare the integer N; apply only if strictly newer (anti-downgrade); test the 9-to-10 boundary.
8. Auto-update accidentally running on the central server — hard no-op unless engine.dialect.name == "sqlite" (+ belt-and-suspenders non-Windows guard); test the short-circuit.

## Implications for Roadmap

Based on research, the milestone is two dependency-ordered phases. This ordering is forced: you cannot self-update to a release format and apply-mechanism that do not yet exist, and the data-relocation must precede any swap.

### Phase A: Packaging, Launcher & Signed-Release Pipeline
**Rationale:** Prerequisite for everything — there is nothing coherent to "unpack over" on a git+uv dev checkout, and the launcher/data-split must exist before any swap is safe.
**Delivers:** Bundled-runtime distributable (app-current/ + stable launcher.exe), Inno Setup installer, install-root layout with code/data physical separation (config edits pointing data/, backups/, .env at install-root siblings), and .github/workflows/release.yml producing signed archive + SHA256SUMS + .minisig (public key vendored, private key offline/CI secret). The launcher apply logic (swap + migrate + pre-update backup + rollback) lands here, independently testable by hand-placing a staged dir + pending.json.
**Addresses:** Packaging/installer, Windows launcher self-restart, DB/backups relocation.
**Avoids:** Pitfall 3 (layout enables atomic swap), 4 (code/data split + archive-free-of-data assertion), 6 (side-by-side previous version), 11/12 (embeddable-onedir + same-cert signing over onefile/PyInstaller AV surface).
**Uses:** Python embeddable runtime, Inno Setup, minisign, uv export.
**Exit criterion:** Two releases exist and a hand-placed pending.json makes the launcher swap+migrate+restart, with a proven rollback.

### Phase B: In-App Secure Self-Update (security-critical)
**Rationale:** Builds directly on A; this is the threat-modelled phase where fetched code is executed.
**Delivers:** app/services/updates.py (check releases/latest, compare RELEASE, download, verify SHA-256 + signature, unpack to staging, pre-update backup, pending.json, controlled shutdown, dialect-gated); startup check + optional periodic loop (mirror _auto_sync_loop); admin notify-and-confirm UI with release notes under the settings router; header version tie-in to RELEASE; anti-downgrade integer version compare.
**Implements:** Update service, update UI, version detection/tie-in.
**Avoids:** Pitfalls 1, 2, 5, 7, 8, 9, 10 (signature-before-unpack, signed manifest not tag, migration+backup rollback, integer version compare + anti-downgrade, server dialect no-op, partial-download digest gate, HTTPS-only no verify=False).
**Exit criterion:** A clean install on v1.N detects and (on operator confirm) updates to v1.N+1, operator data intact, header reflects the new tag, and an intentionally-broken release rolls back cleanly.

### Phase Ordering Rationale
- Hard dependency: self-update assumes a bundled runtime, a launcher that can stop/swap/relaunch, and a signed release format — all Phase A. Phase B cannot be tested without two real releases (cut throwaway v1.N/v1.N+1 late in A or early in B to exercise the round trip).
- Data-safety first: relocating DB/.env/backups out of the swappable dir is a Phase-A structural change; every Phase-B swap depends on it being correct.
- Security root set in A, enforced in B: the signing-key setup (public key vendored, private key offline) lands with the release pipeline in A; the verify-before-unpack gate is Phase B's first responsibility.

### Research Flags

Phases likely needing deeper research during planning:
- Phase A: Recommend a small spike to settle embeddable-Python vs PyInstaller-onedir before committing the build script — the tradeoff (AV surface, Alembic versions/ bundling, ._pth config) is real and version-sensitive. Also verify current SmartScreen/code-signing (post-2023 CA/B hardware-key) specifics if a cert is pursued.
- Phase B: Security-critical; carries a threat model. The signed-manifest-vs-SHA256SUMS shape, the exact minisign verify call, and the launcher/app IPC contract (pending.json + shutdown signal) warrant a focused design pass. Flag /gsd-plan-phase --research-phase B for the trust model and controlled-shutdown protocol.

Phases with standard patterns (lighter research):
- The reused mechanisms (backup VACUUM INTO, dialect gate, _auto_sync_loop cadence, APP_VERSION header) are already shipped and well-understood — no research needed for those integration points.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified against PyPI/GitHub/vendor (py-minisign, Inno Setup, PyInstaller, minisign CLI). Packaging-strategy judgment MEDIUM-HIGH. |
| Features | HIGH | Feature landscape = established self-updating-app practice; dependency mapping verified against this codebase. |
| Architecture | HIGH | Grounded in the actual codebase (config.py, db.py, main.py, backup.py, sync_client.py); Windows file-locking + GitHub API are stable facts. |
| Pitfalls | HIGH | Security/data-loss mechanics are stable, well-established. Code-signing cost/SmartScreen/AV specifics MEDIUM — verify at implementation. |

**Overall confidence:** HIGH

### Gaps to Address
- Packaging strategy (embeddable vs PyInstaller-onedir): settle with a Phase-A spike before writing build_release.py; both are viable, embeddable is the recommended primary.
- Where to sign (offline dev key vs CI): strongest is offline signing; if CI signing is wanted, prefer sigstore keyless over a stored minisign secret. Decide during Phase-A pipeline design.
- Code-signing / SmartScreen for the first-installer download: minisign secures the update channel but not the first download; an unsigned installer trips SmartScreen. For one known operator, document the one-time "Run anyway" bypass; a cert is deferrable. Verify current CA/B hardware-key rules at implementation.
- Two-release test dependency: end-to-end self-update needs two real releases — plan throwaway tags to exercise the round trip.

## Sources

### Primary (HIGH confidence)
- Codebase (read directly): app/config.py, app/db.py, app/main.py (_auto_sync_loop, lifespan), app/services/backup.py (create_backup VACUUM INTO, dialect gate), app/services/sync_client.py (engine.dialect.name == "sqlite" role signal), app/routes/__init__.py (APP_VERSION), app/__init__.py ("1.N" counter), run.bat/install.bat.
- PyPI/GitHub/vendor version facts: py-minisign 0.13.2, minisign CLI 0.12, Inno Setup 6.7.3, PyInstaller 6.21.0, Nuitka 4.1.3, sigstore 4.4.0 (verified 2026-07-22).
- GitHub REST GET /repos/{owner}/{repo}/releases/latest shape (excludes drafts/prereleases; 60 req/hr unauthenticated); Windows executable/DLL file-locking semantics — stable platform behaviour.
- The Update Framework (TUF) design rationale — integrity != authenticity, signed manifests, anti-downgrade/replay.
- CLAUDE.md, .planning/PROJECT.md — validated runtime stack, PyInstaller v1-rejection rationale (re-evaluated), v4.0 milestone scope.

### Secondary (MEDIUM confidence)
- Established self-updating frameworks (Sparkle/WinSparkle, Squirrel.Windows, electron-updater, Tauri updater) — feature landscape & UX/security models.
- Practitioner judgments: embeddable-onedir vs PyInstaller for self-update, offline-key vs CI-signing tradeoff, atomic same-volume directory rename.

### Tertiary (LOW confidence — verify at implementation)
- Authenticode/SmartScreen reputation and post-2023 CA/B hardware-key requirement for code-signing certs (EV vs OV behaviour); PyInstaller onefile AV heuristic specifics.

---
*Research completed: 2026-07-22*
*Ready for roadmap: yes*
