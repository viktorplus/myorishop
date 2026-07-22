# Pitfalls Research

**Domain:** Windows self-contained packaging + secure self-update (GitHub Releases) for a FastAPI/HTMX/SQLite desktop client that owns the operator's only copy of their business data
**Researched:** 2026-07-22
**Confidence:** HIGH on the security/data-loss mechanics (well-established, stable knowledge); MEDIUM on version-sensitive specifics (code-signing cost/rules, SmartScreen behaviour, PyInstaller AV heuristics — verify at implementation time)

> Two roadmap phases are assumed below:
> - **Phase A — Packaging/Installer** (bundle a runtime, produce a distributable, replace the `run.bat`+`uv` dev flow, sign, get past SmartScreen/AV).
> - **Phase B — Self-Update** (check GitHub Releases → verify → unpack over install → `alembic upgrade head` → restart, with rollback).
>
> This app is unusually high-stakes for self-update because **it runs fetched code** and **the install directory sits next to the operator's single irreplaceable SQLite DB, `.env` identity (`secret_key`, `device_id`) and backups**. A bad update can silently exfiltrate/destroy a reseller's entire ledger. Treat the security and data-loss pitfalls below as mandatory, not "nice to have."

---

## Critical Pitfalls

### Pitfall 1: Running fetched code with no signature verification (integrity ≠ authenticity)

**What goes wrong:**
The updater downloads a release archive and unpacks/executes it after checking only that the download "succeeded," or after checking a SHA-256 that is published *right next to the archive* on the same GitHub release. A checksum stored beside the asset proves the bytes arrived intact — it proves **nothing** about *who* produced them. Anyone who can alter the asset (compromised GitHub token, malicious maintainer, a leaked Actions secret, a MITM on a broken TLS path) can alter the checksum in the same breath. Result: the operator's machine executes attacker-controlled Python that already has full read/write access to the SQLite ledger, `.env` `secret_key`, and sync credentials.

**Why it happens:**
"It downloaded and the hash matched" *feels* like verification. Developers conflate transport integrity (TLS + checksum) with code authenticity (signature over a key the attacker cannot forge).

**How to avoid:**
- **Sign the release artifact and verify against a public key baked into the client binary.** Use a detached signature the client checks before touching the archive: `minisign`/`signify` (tiny, one Ed25519 public key hard-coded in the app) or `cosign`/Sigstore, or GPG. The *private* key lives only on the release machine / in a protected CI secret; the *public* key ships inside the app.
- Verify **before** unpack and before running any code from the archive. Verify the signature over the *archive*, then verify the archive's inner file digests if you unpack incrementally.
- Keep the signing key **separate** from the GitHub token that publishes releases, so compromising the publish path alone does not let an attacker forge a signature.
- Checksums are still useful — but only as a *second, cheaper* integrity gate, never as the authenticity gate.

**Warning signs:**
Code that does `if sha256(download) == published_hash: unpack()` and nothing else. No public key anywhere in the repo/app. "We trust GitHub's HTTPS" used as the whole argument.

**Phase to address:** **Phase B** (design the trust model before writing the downloader — it dictates the release build in Phase A).

---

### Pitfall 2: Verifying the git tag instead of the release asset

**What goes wrong:**
The updater trusts "release tagged `v1.5` exists" and pulls whatever the `latest` release currently points at, or resolves the tag and downloads the tarball GitHub auto-generates. **Git tags are mutable** (a maintainer or a compromised token can force-move `v1.5` to a different commit), and **release assets can be edited/replaced after publication**. Auto-generated source tarballs are also not the same artifact you built, signed, and tested. So "the tag is valid" does not mean "these bytes are the release you vetted."

**Why it happens:**
The GitHub Releases API makes tag/`latest` lookups trivial, so people key the whole update on the tag name and never pin the specific asset digest.

**How to avoid:**
- Update decisions key on a **signed manifest** (e.g. a small `latest.json` that lists version, asset filename, and the asset's SHA-256, and is itself signed with the offline key), not on the tag string.
- Download the **explicitly uploaded, signed release asset** (your built archive), never the GitHub auto-generated `Source code (zip/tar.gz)`.
- Re-verify the downloaded asset's digest against the value in the signed manifest, then verify the signature. Tag/release name is at most a hint.

**Warning signs:**
Code that constructs a download URL from a tag string; reliance on `/releases/latest` with no per-asset digest check; no signed manifest.

**Phase to address:** **Phase B** (paired with Pitfall 1 — same trust root).

---

### Pitfall 3: Overwriting a running executable / locked files on Windows

**What goes wrong:**
On Windows you **cannot delete or overwrite an executable or DLL while it is loaded/running** (unlike POSIX). The updater tries to unpack the new build directly over `MyOriShop.exe` / the bundled `python*.dll` while the app (the very process doing the update) is still running, and gets `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`. The update aborts half-written, leaving a corrupt mix of old and new files — a bricked install.

**Why it happens:**
Developers test the unpack logic on the dev checkout (loose `.py` files, nothing locked) and never hit the lock, which only appears against a packed/frozen exe that has itself mapped into memory.

**How to avoid:**
- **Never unpack over the live install from inside the running app.** Standard patterns:
  - **Rename-then-replace:** Windows *allows renaming* a running exe. Rename the current exe/dir aside (`app.exe` → `app.old.exe`), lay down the new files, then relaunch. A tiny separate **updater/bootstrapper process** (or the OS) does the swap after the main app exits.
  - **Side-by-side + launcher:** install each version into `versions\1.5\`, and have a stable launcher flip a `current` junction/pointer, then restart. No file is ever overwritten in place.
  - **`MoveFileEx(..., MOVEFILE_DELAY_UNTIL_REBOOT)`** as a fallback for stubborn locks (applies at next boot).
- Apply the update in a **staging directory** first (download + verify + unpack there), and make the final swap the only step that touches the live install — so a failure before the swap leaves the running install untouched.
- The process that performs the swap must not be a child that dies when the app exits; use a detached helper or scheduled relaunch.

**Warning signs:**
Update works when run against the dev tree but `WinError 32` the moment it's tested against the packaged exe; the updater is a function *inside* `app.main` that expects to overwrite its own exe.

**Phase to address:** **Phase B** for the swap mechanics; **Phase A** must choose a packaging layout (side-by-side dir vs onefile) that makes an atomic swap *possible* — this is why the two phases are coupled.

---

### Pitfall 4: Over-the-top unpack destroys the operator's SQLite DB, `.env` identity, or backups

**What goes wrong:**
The release archive is unpacked over the install directory and **clobbers or deletes runtime data** that lives there: the SQLite `.db` (the operator's entire ledger — receipts, sales, cash), the `.env` holding `secret_key` and `device_id` (losing `device_id` breaks sync identity and orphans the append-only ledger on the server), and the local `backups/` folder. If the archive ships a stub `.env` or an empty seed DB "for first run," the update overwrites the real one. This is the single most catastrophic failure mode for this app — irreversible loss of the only copy of the business's data.

**Why it happens:**
The dev checkout mixes code and data in one tree, so the archive is built from a layout where `data/` and `.env` look like normal project files. A naïve "extract zip to install dir, replacing existing files" then wipes them.

**How to avoid:**
- **Physically separate code from data.** Runtime state (`*.db`, `.env`, `backups/`) must live in a directory the updater **never writes to** — e.g. `%LOCALAPPDATA%\MyOriShop\data\` — while code lives in a replaceable `app/` install dir. The app already externalizes `data/`; enforce that the updater's unpack target and the data dir are disjoint paths.
- The release archive **must not contain** `.env`, any `.db`, or `backups/`. Add them to the packaging ignore list and assert their absence in the release build (fail CI if a `.db`/`.env` is inside the artifact).
- **Take a fresh DB + `.env` backup immediately before applying any update**, into a location outside the swap target, tagged with the from/to version. Reuse the shipped `create_backup()` (`VACUUM INTO`) path.
- On first run after a fresh install, *create* `.env`/DB only if absent — never overwrite.

**Warning signs:**
`.env` or a `.db` file appears inside the built release archive; the install dir and data dir are the same path; no pre-update backup step; `device_id` regenerates after an update (telltale that `.env` was clobbered).

**Phase to address:** **Phase A** must lock the code/data split and guarantee the archive contains no data files. **Phase B** adds the mandatory pre-update backup + absence assertions.

---

### Pitfall 5: Alembic migration fails mid-update with no rollback → half-migrated DB

**What goes wrong:**
The update runs `alembic upgrade head` against the operator's real DB. A migration raises partway (bad data, an interrupted power event, a SQLite batch-mode `ALTER` that fails, a migration that assumed data not present). SQLite DDL is only partly transactional and the app already uses **batch mode** (table-copy) for `ALTER`, so a failure can leave a renamed/temp table behind. Now the schema is half-applied: the old code won't run against it, the new code errors, and there is no `downgrade` that reliably reverses a table-rebuild. The operator is stuck with an unopenable app and a corrupted schema.

**Why it happens:**
Migrations are tested on clean/dev data, never on the operator's accumulated real data. "`upgrade head` just works" holds until it doesn't, and nobody wrote/verified the reverse path.

**How to avoid:**
- **Back up the DB file immediately before `alembic upgrade head`** (Pitfall 4's backup). Recovery = restore the pre-update copy, not `alembic downgrade`.
- Run migrations against a **copy first** where feasible, or wrap the upgrade so any exception triggers: stop, restore the pre-update DB, roll back to the previous app version, surface a clear RU error.
- Keep migrations **idempotent and defensive** (check for existence before create/drop) so a re-run after partial failure can recover.
- Do **not** rely on `downgrade()` for recovery on SQLite batch migrations — treat the file backup as the source of truth.
- Gate "update succeeded" on the app actually **booting and answering a health check** *after* migration, not on the migration command's exit code alone.

**Warning signs:**
Migrations only ever tested on empty/seed DBs; no pre-migration backup; recovery plan says "run alembic downgrade"; leftover `_alembic_tmp_*` tables after a failed run.

**Phase to address:** **Phase B** (the migration-with-rollback step is the core of a safe apply).

---

### Pitfall 6: No rollback / no recovery path → a failed update bricks the install

**What goes wrong:**
The update is applied "in place" and something fails *after* files are swapped (migration error, missing bundled DLL, the new exe crashes on boot, AV quarantines a new file). The old version is already gone, there is no way back, and the operator — a non-technical reseller with no git and no dev toolchain — is left with an app that won't start and their only data locked behind a broken binary. There is no "reinstall previous version" button and no offline recovery.

**Why it happens:**
The happy path (download → apply → restart) is easy to demo; the failure/rollback path is extra work that only matters when something breaks, so it's skipped.

**How to avoid:**
- **Keep the previous version on disk** (side-by-side `versions\` layout or the renamed-aside `app.old`). Rollback = point the launcher back at the previous version + restore the pre-update DB backup.
- Make the swap the **last, atomic-as-possible** step; verify the new version **boots and passes a health check** before deleting/retiring the old one. If health check fails within N seconds, auto-revert to the previous version.
- Provide a **manual recovery path** the operator can run without tooling: a `restore-previous.bat` / a "revert to previous version" entry, plus written RU instructions. The pre-update backups must be findable.
- Never delete the last-known-good version until the new one has proven itself running.

**Warning signs:**
Only one version dir ever exists on disk; no health check after restart; "rollback" is a manual dev task; the operator would need to redownload to recover.

**Phase to address:** **Phase B** (rollback + health-gate), enabled by **Phase A**'s side-by-side layout choice.

---

### Pitfall 7: Version-comparison bug on the "1.\<N>" scheme (string vs numeric) + downgrade attacks

**What goes wrong:**
The app version is a single string `"1.1"` (`app/__init__.py`, `__version__ = "1.1"`). Two failures:
1. **Lexical comparison:** comparing versions as strings makes `"1.9" > "1.10"` evaluate **True** (because `"9" > "1"`), so the client refuses a genuine newer release, or applies an older one thinking it's newer. Once `<N>` crosses 9→10, string ordering silently breaks.
2. **Downgrade / rollback attack:** an attacker (or a stale mirror) serves a correctly *signed* but **older** release. If the client only checks "is remote version != installed," it happily "updates" backward to a version with known bugs/vulns.

**Why it happens:**
`"1.<N>"` reads like a number, so string compare "looks fine" in early single-digit testing. And update logic naturally asks "is it different?" rather than "is it strictly newer?"

**How to avoid:**
- Parse both sides into a **numeric tuple** (or use `packaging.version.Version`) before comparing — never compare version strings lexically. Given the `1.<N>` scheme, compare the integer `<N>`.
- **Only ever move forward:** apply an update **iff** remote version > installed version. Refuse equal or lower, even when correctly signed — this is the anti-downgrade rule.
- Record the highest version ever installed and refuse anything at or below it (defends against replay of an old signed manifest). Signed manifests should carry a monotonically increasing counter / timestamp.
- Add a test that asserts `1.10 > 1.9` under your comparator.

**Warning signs:**
`if remote_version != local_version:` or `if remote > local` on raw strings; no test crossing the 9→10 boundary; "update available" fires for an older release.

**Phase to address:** **Phase B** (comparator + anti-downgrade), with the version single-source (`app/__init__.py`) wired to reflect the installed release (the "visible version tie-in" requirement).

---

### Pitfall 8: Auto-update accidentally enabled on the central server

**What goes wrong:**
The self-update logic runs everywhere the code runs — including the central PostgreSQL server (s1, Dockerized). The server tries to download a Windows client archive, unpack over its Docker filesystem, run migrations, and restart mid-flight. Best case it errors noisily in a container; worst case it corrupts the server that every operator syncs to — turning a client convenience feature into a single point of total-system failure.

**Why it happens:**
Same codebase, same `main.py`, same lifespan hooks run on both client and server. If the updater is wired into app startup unconditionally, the server inherits it.

**How to avoid:**
- **Gate auto-update on the exact role signal the app already uses: the DB dialect.** `backup.py` already does `if engine.dialect.name != "sqlite": return None`, and the auto-sync default is dialect-based (SQLite client = enabled, PostgreSQL server = disabled). Mirror this: **self-update is a hard no-op unless `engine.dialect.name == "sqlite"`.** Make it a single early guard, not scattered checks.
- Additionally guard on running-inside-Docker / non-Windows platform as a belt-and-suspenders check (`sys.platform != "win32"` → no-op).
- Add a test asserting the updater short-circuits under the Postgres dialect.

**Warning signs:**
Update check wired into shared lifespan with no dialect guard; the server logs "checking for updates"; the no-op relies on the server "just not having a GitHub token" rather than an explicit dialect gate.

**Phase to address:** **Phase B** (first line of the updater is the dialect no-op — mirrors the shipped 1.1 `auto_enabled` rule).

---

### Pitfall 9: Partial / interrupted downloads applied as if complete

**What goes wrong:**
The archive download is interrupted (flaky reseller internet, laptop sleep, connection drop). The updater gets a truncated file but proceeds to verify/unpack it. Without a length + digest check the truncation may pass a naïve "file exists / non-empty" test, and a partial archive either fails to unpack mid-way (bricked, per Pitfall 6) or — worse — unpacks a subset of files.

**Why it happens:**
Downloads are tested on a fast dev connection where they never truncate; the "download" step is treated as atomic.

**How to avoid:**
- Download to a **temp file in the staging dir**, verify **expected byte length AND SHA-256** from the signed manifest, and only then treat it as a candidate. A digest mismatch = discard and retry, never apply.
- Support **resume / retry with backoff**; treat any verification failure as "no update this cycle," leaving the running install untouched.
- The signature check (Pitfall 1) also catches truncation — but check length/digest first to fail cheap and clear.

**Warning signs:**
Unpack starts before a digest check; no size check; a dropped connection leaves a half-applied install; retries re-use a partial temp file.

**Phase to address:** **Phase B** (downloader: staging + digest + resume before any apply).

---

### Pitfall 10: TLS not enforced / no cert validation on the update channel

**What goes wrong:**
The updater fetches the manifest/asset over a client that has certificate verification disabled (`verify=False` copied from some sync-debugging snippet), or silently allows HTTP. A network attacker on the operator's café/hotel Wi-Fi serves a forged manifest pointing at a malicious asset. Even with a signature check, a broken TLS layer widens the attack surface and enables downgrade/replay games.

**Why it happens:**
`verify=False` is a common "make it work behind a proxy" hack that leaks into production; corporate MITM proxies push people to disable verification.

**How to avoid:**
- Enforce **HTTPS only** and **full certificate validation** on every update request (the app already ships `httpx` for sync — reuse it with defaults, never `verify=False`).
- The signed-manifest + baked-in-public-key design (Pitfalls 1–2) is the real authenticity guarantee, so **you do not need fragile TLS cert pinning** — pinning GitHub's cert risks bricking updates when GitHub rotates certs. Rely on the code signature for authenticity and standard TLS for transport. (If pinning is ever wanted, pin your *signing* public key, which you control, not GitHub's TLS cert.)
- Refuse redirects to non-HTTPS.

**Warning signs:**
`verify=False`, a custom SSL context that disables checks, `http://` URLs, or a pinned GitHub TLS cert that will expire.

**Phase to address:** **Phase B**.

---

### Pitfall 11: SmartScreen / "Windows protected your PC" blocks the unsigned exe

**What goes wrong:**
The packaged exe is unsigned (or signed with a brand-new certificate with no reputation). Windows Defender SmartScreen shows "Windows protected your PC — unrecognized app," and the non-technical operator either can't get past it or is trained to click through security warnings (a bad habit for an app that self-updates). Every self-update that ships a new unsigned exe re-triggers the warning.

**Why it happens:**
Code signing is treated as an afterthought; developers on their own machine never see SmartScreen for a locally built exe.

**How to avoid:**
- **Authenticode-sign** the exe and installer with a code-signing certificate. Note (verify at implementation, MEDIUM): since 2023 CA/B Forum rules, code-signing private keys must be stored on **hardware (HSM/USB token)** or a cloud signing service; **EV** certificates grant SmartScreen reputation ~immediately, while standard **OV** certs build reputation over downloads/time.
- Sign **every** released binary with the **same** certificate so reputation accrues and self-updates don't re-trip the warning.
- If a cert is not viable initially, at minimum: document the expected warning in RU, ship a signed installer later, and prefer an **installer format** (MSI/Inno Setup/MSIX) that users trust more than a bare exe.
- Timestamp signatures so they remain valid after the cert expires.

**Warning signs:**
Test machines (not the dev box) show the blue SmartScreen dialog; support questions about "is this safe?"; each update re-triggers the warning (sign of an unsigned or inconsistently signed binary).

**Phase to address:** **Phase A** (signing is part of the release build), and every Phase-B release must ship the *same-cert*-signed binary.

---

### Pitfall 12: Antivirus false-positives / quarantines the packed exe (PyInstaller)

**What goes wrong:**
Packers like PyInstaller (onefile especially) trip heuristic AV engines — the self-extracting stub, the `%TEMP%\_MEIxxxxxx` extraction, and "packed Python interpreter" patterns are common false-positive signatures. AV quarantines or deletes the exe; mid-self-update this can remove a freshly downloaded new version and brick the swap (Pitfall 6). CLAUDE.md already flags PyInstaller as fiddly for this stack.

**Why it happens:**
Frozen Python exes statistically resemble malware droppers to heuristic scanners; onefile's temp extraction looks like unpacking behaviour.

**How to avoid:**
- Prefer a **one-folder / side-by-side layout over onefile** — fewer heuristic hits, no `%TEMP%` extraction, *and* it's the layout that makes atomic swap + rollback possible (Pitfalls 3/6). This aligns with the milestone's "bundled runtime" goal without the onefile downsides.
- **Sign the binary** (Pitfall 11) — signatures materially reduce AV false positives.
- Consider a **plain bundled interpreter + your source** (e.g. an embeddable Python distribution laid down beside the app) instead of a packer, keeping code as readable `.py` — often the lowest-AV-friction option and closest to the current `uv`/`run.bat` model.
- Test against Windows Defender on a clean machine before release; if a specific build trips a definition, that's a release blocker.

**Warning signs:**
The exe vanishes after download; Defender history shows a quarantine; onefile builds work on the dev box but disappear on operator machines; self-update downloads get deleted before the swap.

**Phase to address:** **Phase A** (packaging strategy: prefer one-folder/embeddable over onefile; sign).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Checksum-only "verification" (no signature) | Fastest to ship; no key management | Zero authenticity — runs attacker code; a rewrite once a real trust model is added | **Never** for a code-running updater |
| Onefile PyInstaller build | Single-file distribution, simplest to hand over | AV false positives, `%TEMP%` extraction, hard/impossible atomic swap + rollback | Only for a throwaway internal demo, never the shipped self-updater |
| In-place overwrite of the install dir | Simple "extract zip here" code | `WinError 32` file locks; no rollback; can clobber data | **Never** on Windows for a running app |
| Reuse dev tree layout (code+data mixed) in the archive | No repackaging work | Clobbers DB/`.env`/backups on update = total data loss | **Never** — code/data split is mandatory |
| String version compare | "1.1" reads like a number | Silent break at 9→10; no anti-downgrade | **Never** — use numeric/tuple compare |
| Skip pre-update DB backup | One less step, faster update | A failed migration = unrecoverable ledger loss | **Never** for this app |
| Rely on server "not having a token" to skip updates | No extra code | Server runs client update logic by accident | **Never** — use the explicit dialect no-op |
| Manual (dev-run) rollback only | Ship the happy path sooner | Non-technical operator can't recover a bricked install | Only if a one-click/`.bat` recovery ships in the same phase |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| GitHub Releases API | Keying updates on the tag / `latest` string and downloading the auto-generated source tarball | Download the explicitly uploaded, signed asset; decide on a signed manifest with a per-asset SHA-256, not the tag |
| GitHub token in CI | Reusing the publish token as the signing key | Keep signing key offline/separate from the publish token so a token leak can't forge signatures |
| `httpx` (already in stack) | Copying `verify=False` from a sync-debug snippet | HTTPS + default cert validation; no `verify=False`; refuse non-HTTPS redirects |
| Alembic | Running `upgrade head` on real operator data with `downgrade` as the recovery plan | Back up the DB file first; recover by restoring the file, not by `downgrade` (batch migrations don't reliably reverse) |
| Windows shell / process | Update helper is a child of the app, dies when the app exits mid-swap | Detached updater/bootstrapper process (or scheduled relaunch) performs the swap after the app fully exits |
| Windows file system | Overwriting the running exe / loaded DLL | Rename-aside or side-by-side version dirs; `MoveFileEx(MOVEFILE_DELAY_UNTIL_REBOOT)` fallback |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Blocking the app on the update check at startup | App is slow/hangs to open when GitHub is slow/unreachable | Run the check async/in background with a short timeout; never block boot; offline = silently skip | Any time the operator has flaky/no internet (a core scenario) |
| Re-downloading the full archive every check | Bandwidth waste, slow, more partial-download risk | Compare versions from the small signed manifest first; only download the asset when strictly newer | On metered/slow reseller connections |
| Migration on a large accumulated DB during a blocking update | Long freeze / apparent hang while `upgrade head` copies tables (batch mode) | Show progress; run against the backup copy; set expectations in UI | After a year of daily data — the table-copy batch migrations get slow |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| No signature over fetched code | Remote code execution as the operator, full ledger/`secret_key`/`device_id` compromise | Ed25519/cosign signature verified against a baked-in public key before unpack |
| Trusting mutable tag/asset over a signed manifest | Attacker moves the tag or replaces the asset | Signed manifest with per-asset digest; download only the signed asset |
| No anti-downgrade rule | Replay a signed old (vulnerable) version | Apply only if strictly newer; remember highest-ever version; monotonic manifest counter |
| `verify=False` / HTTP on the update channel | MITM serves forged manifest | HTTPS + full cert validation; signature is the authenticity root |
| Signing key stored with the publish token / in the repo | One leak forges all future updates | Offline/HSM signing key, separate from CI publish credentials |
| Update logic active on the central server | Corrupts the shared sync target for every operator | Hard dialect no-op (`sqlite` only) + non-Windows/Docker guard |
| Shipping `.env`/`.db` inside the archive | Overwrites `secret_key`/`device_id`/ledger; may leak dev secrets | Assert the artifact contains no `.env`/`.db`/`backups`; fail the release build if present |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent auto-apply mid-work, restarting during data entry | Operator loses in-progress receipt/sale; distrust | Apply on next launch / when idle; or notify + let operator choose; never interrupt an active entry |
| SmartScreen/AV warnings with no explanation | Operator can't install, or is trained to click through security prompts | Signed binaries; RU documentation of any expected first-run prompt |
| Opaque failure ("update failed") | Non-technical operator stuck, no next step | Clear RU message + automatic rollback + "you're still on the working version X" reassurance |
| Version in header doesn't change after update | Operator unsure if update worked | Single-source `__version__` reflects the installed release (the milestone's visible-version requirement) |
| No offline/"remind me" behaviour | Update nags or errors when the reseller has no internet | Offline = silently skip; this app is offline-capable by design |

## "Looks Done But Isn't" Checklist

- [ ] **Signature verification:** Often "done" as a checksum only — verify a *signature* against a *baked-in public key* is checked *before* unpack, and that a tampered asset is actually rejected in a test.
- [ ] **Running-exe swap:** Often only tested on the dev tree — verify the update applies against the **packaged exe** without `WinError 32`, using rename-aside/side-by-side.
- [ ] **Data preservation:** Often assumed — verify after an update the SQLite DB, `.env` (`secret_key`, `device_id` unchanged), and `backups/` all survive; assert the archive contains none of them.
- [ ] **Migration rollback:** Often "runs upgrade head" only — verify a *deliberately failing* migration triggers DB restore + version rollback, and the app still boots on the old version.
- [ ] **Rollback / recovery:** Often missing — verify the previous version stays on disk and there's an operator-runnable recovery path; verify auto-revert on a failed post-update health check.
- [ ] **Anti-downgrade + 9→10:** Often single-digit tested — verify `1.10 > 1.9` and that a signed *older* release is refused.
- [ ] **Server no-op:** Often assumed — verify the updater short-circuits under the PostgreSQL dialect (test), not merely "because the server has no token."
- [ ] **Partial download:** Often untested — verify a truncated/interrupted download is rejected (length+digest) and leaves the running install untouched.
- [ ] **Signed + consistent binary:** Verify each released exe is signed with the *same* cert so self-updates don't re-trigger SmartScreen.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Clobbered DB/`.env` during update (Pitfall 4) | HIGH (data loss if no backup) | Restore pre-update DB + `.env` backup; if none, restore from last auto-backup and accept lost interim data; regenerate `device_id` only as a last resort (re-registers device with server) |
| Half-applied migration (Pitfall 5) | MEDIUM | Restore the pre-update DB file backup; relaunch previous app version; investigate migration on a copy before retrying |
| Bricked install / bad new version (Pitfall 6) | MEDIUM | Launcher points back to previous version dir; restore DB backup; surface RU "reverted to working version" |
| Locked-file half-write (Pitfall 3) | MEDIUM | Because the swap is the only step touching the live install, a pre-swap failure leaves the old install intact — just retry; post-swap failure = revert to renamed-aside old version |
| AV quarantined the exe (Pitfall 12) | MEDIUM | Re-download; if signed build still trips, block release and re-package (one-folder/embeddable); provide an AV-exception note as stopgap |
| Accidental server update (Pitfall 8) | HIGH | Restore server from Docker/DB backup; add the dialect no-op guard + test before redeploying |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Unsigned fetched code | Phase B (trust model set in A's release build) | Tampered asset is rejected in a test; public key baked into app |
| 2. Verifying tag not asset | Phase B | Update keys on a signed manifest + per-asset digest, not the tag |
| 3. Overwriting running exe (locks) | Phase B mechanics / Phase A layout | Update applies against the packaged exe with no `WinError 32` |
| 4. Over-the-top unpack destroys data | Phase A (code/data split) + Phase B (backup) | DB/`.env`/backups survive; archive asserted free of them |
| 5. Alembic mid-update failure | Phase B | Forced migration failure → DB restored + rolled back, app boots |
| 6. No rollback / bricked install | Phase B (Phase A side-by-side layout) | Previous version retained; auto-revert on failed health check; operator recovery path exists |
| 7. Version compare + downgrade | Phase B | `1.10 > 1.9`; signed older release refused |
| 8. Auto-update on the server | Phase B | Updater no-ops under PostgreSQL dialect (test) |
| 9. Partial downloads | Phase B | Truncated download rejected; running install untouched |
| 10. TLS not enforced | Phase B | No `verify=False`; HTTPS enforced |
| 11. SmartScreen blocks exe | Phase A (every B release re-signs same cert) | Signed exe; no SmartScreen block on a clean machine |
| 12. AV false-positive | Phase A | Defender clean on a clean machine; one-folder/embeddable + signed |

## Sources

- Windows executable/DLL file-locking semantics (cannot overwrite a loaded image; rename-then-replace, `MoveFileEx(MOVEFILE_DELAY_UNTIL_REBOOT)`) — Win32 platform behaviour, HIGH.
- Update-security first principles (integrity ≠ authenticity, signed manifests, anti-downgrade/replay) — The Update Framework (TUF) design rationale and general secure-update practice, HIGH.
- Signature tooling options (minisign/signify Ed25519, Sigstore/cosign, GPG) — established tooling, HIGH.
- Authenticode / SmartScreen reputation and post-2023 CA/B hardware-key requirement for code-signing certs, EV vs OV reputation behaviour — MEDIUM (verify current specifics at implementation).
- PyInstaller onefile `%TEMP%\_MEIxxxx` extraction and heuristic AV false-positives; CLAUDE.md's own "avoid PyInstaller for v1" note — MEDIUM/HIGH.
- Alembic SQLite batch-mode (`render_as_batch=True`) migration semantics and non-reversibility of table-copy migrations — project CLAUDE.md + Alembic docs knowledge, HIGH.
- Project-specific grounding (verified in repo): `app/__init__.py` `__version__ = "1.1"` single-source version; dialect-based role guard already used in `app/services/backup.py` (`engine.dialect.name != "sqlite"`) and the 1.1 `auto_enabled` dialect default; externalized `data/` (DB, `.env` `secret_key`/`device_id`, backups) — HIGH.

---
*Pitfalls research for: Windows packaging + secure GitHub-Releases self-update of a SQLite desktop client*
*Researched: 2026-07-22*
