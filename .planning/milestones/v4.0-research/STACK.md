# Stack Research

**Domain:** Windows self-contained distribution + secure GitHub-Releases auto-update for a FastAPI + Uvicorn + SQLite desktop app (v4.0)
**Researched:** 2026-07-22
**Confidence:** HIGH (version facts verified against PyPI/GitHub/vendor sites; packaging-strategy judgments MEDIUM-HIGH)

> **Scope note:** This is a v4.0 *additive* research pass. The existing runtime stack (Python 3.13, FastAPI 0.139, Uvicorn, SQLAlchemy 2.0, SQLite, Jinja2, HTMX 2.0.10 vendored, Alembic, pydantic-settings, uv, httpx) is already shipped and validated — see the root `CLAUDE.md`. Everything below is **new capability only**: (a) turning the client into a self-contained Windows distributable, and (b) securely self-updating from GitHub Releases. Nothing here changes the running app's dependencies except one small new runtime library for signature verification.

---

## The two problems, and the shape of the answer

1. **Package** the client so it runs on an operator's Windows machine with **no Python, no uv, no git** preinstalled, still works **offline**, and launches straight to the browser.
2. **Self-update** from GitHub Releases with real **authenticity** (not just integrity): download by tag → verify signature + checksum → stage → swap → `alembic upgrade head` → relaunch, with **rollback** on any failure.

The single most important design decision that ties both together: **package the app as a directory of plain files (a "onedir" layout), keep the SQLite database and config OUTSIDE that directory, and make "update" = swap the directory + run Alembic.** This makes rollback a directory rename and lets Alembic run as ordinary Python (no frozen-import magic). Every recommendation below flows from that decision.

---

## Recommended Stack

### Core Technologies (the packaging + update layer)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python Windows embeddable package** (CPython) | 3.13.x (`python-3.13.x-embed-amd64.zip` from python.org) | The bundled runtime shipped inside the distributable | Ships the **official, python.org-signed** `python.exe`/`pythonw.exe` + stdlib as a redistributable zip. No compilation, no freezing, so **no PyInstaller/Nuitka AV false-positives** and **Alembic/uvicorn just work as normal files**. `pythonw.exe` launches with **no console window**. Confidence: HIGH |
| **Inno Setup** | 6.7.3 (stable, 2026-05-26) — or 7.0.2 (2026-07-13) | Builds the Windows installer (Start-Menu shortcut, uninstaller, install to `%LOCALAPPDATA%`) | Free, mature, scriptable (`.iss`), the de-facto standard for non-MSI Windows installers. Supports SignTool integration for Authenticode when/if a cert is added. Stay on **6.7.3** unless you need 7.x features — 7.0.2 is very new. Confidence: HIGH |
| **py-minisign** | 0.13.2 (2026-04-09) | In-process verification of the release signature against a **baked-in public key** | The security control that matters: the update client verifies each release was signed by a key **you hold offline**, so a compromised GitHub account cannot push runnable malware. Pure-format minisign (Ed25519) verifier; depends on `cryptography` >= 46.0.7. Requires Python >= 3.9. Confidence: HIGH |
| **minisign** (CLI, dev-side signing) | 0.12 (jedisct1, 2025-01-15) | You (the developer) sign each release archive locally with your secret key | Tiny, audited, single-file Ed25519 signer. Secret key never leaves your machine → the strongest anti-supply-chain control for a solo dev. Client verifies with py-minisign; no need to bundle this binary in the client. Confidence: HIGH |
| **httpx** | 0.28.1 (**already a dependency**) | GitHub Releases API calls + asset download | Already used by FastAPI's TestClient and available in the app; no new dependency for networking. Use it to hit `GET /repos/{owner}/{repo}/releases/latest` and stream the asset. Confidence: HIGH |
| **uv** | 0.11.28 (**already the dev tool**) | *Build-time* dependency resolution/export into the embeddable bundle | Keeps the build in the existing toolchain: `uv export --format requirements-txt --no-hashes` produces the pinned list; install it into the bundle's `lib/` with `uv pip install --target lib -r requirements.txt`. No uv on the operator machine. Confidence: HIGH |

### Supporting Libraries / stdlib (no install needed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `hashlib` | stdlib | SHA-256 of the downloaded archive vs. the release's `SHA256SUMS` | Always — integrity check *before* signature check (cheap fail-fast). |
| `zipfile` / `shutil` | stdlib | Safe unpack + staging-dir copy/rename swap | Always. Guard against zip-slip: reject any member whose resolved path escapes the target dir. |
| `subprocess` | stdlib | Run the detached updater/swapper and `alembic upgrade head` | The running app cannot overwrite its own loaded DLLs; a short-lived detached process does the swap after the app exits. |
| `webbrowser` / `os.startfile` | stdlib | Open the operator's default browser at `http://127.0.0.1:<port>` on launch | In the launcher script. |
| `cryptography` | >= 46.0.7 (pulled in by py-minisign) | Ed25519 primitives under py-minisign | Transitive; do not call directly. Note: it ships a large compiled wheel — include it in the bundle. |

### Development / Build Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `uv export` / `uv pip install --target` | Assemble pinned deps into the bundle | One command each; stays in the current uv world. |
| Inno Setup Compiler (`ISCC.exe`) | Compile `installer.iss` → `MyOriShopSetup.exe` | Can run headless in CI. |
| `minisign -G` / `minisign -Sm` | Generate keypair once; sign each release archive + `SHA256SUMS` | Publish `minisign.pub` in the repo; **bake it into the client**. Secret key stays offline. |
| GitHub Actions (release-on-tag) | Build bundle → checksum → (sign) → create Release with assets | Optional but recommended for reproducible releases; see the signing-location tradeoff under "Stack Patterns". |

---

## Installation (build-machine only; the operator installs nothing but the produced setup.exe)

```bash
# --- one-time: signing key (developer machine, kept OFFLINE) ---
minisign -G                      # produces minisign.key (secret) + minisign.pub (public)
#   -> commit minisign.pub into the repo AND embed it in the client source

# --- per-release build (developer machine or CI) ---
# 1. pin deps from the existing uv project
uv export --format requirements-txt --no-hashes -o build/requirements.txt

# 2. lay down the embeddable runtime + deps
#    (unzip python-3.13.x-embed-amd64.zip into build/runtime/, edit python313._pth:
#     add '../app' and '../lib', and uncomment 'import site')
uv pip install --target build/lib -r build/requirements.txt

# 3. checksum + sign the release archive
#    (zip the staged app -> MyOriShop-1.N.zip)
sha256sum MyOriShop-1.N.zip > SHA256SUMS
minisign -Sm SHA256SUMS         # -> SHA256SUMS.minisig  (upload both to the Release)

# 4. build the installer
ISCC.exe installer.iss           # -> dist/MyOriShopSetup.exe

# --- new RUNTIME dependency added to the app itself ---
uv add py-minisign               # only new package the shipped client needs
```

The shipped client's only new dependency is **py-minisign** (+ its transitive `cryptography`). Everything else is stdlib, the already-present httpx, or build-time-only.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Embeddable-Python onedir | **PyInstaller 6.21.0 (`--onedir`)** | If assembling the embeddable bundle proves fiddly and you accept spec-file work. `--onedir` (never `--onefile`) keeps a swappable directory. Requires hidden-import wrangling (`uvicorn.lifespan.*`, `uvicorn.protocols.*`) and bundling Alembic's `versions/` as `--add-data`. More mature tooling, but **higher AV false-positive rate** and Alembic script discovery needs manual `script_location`. See re-evaluation below. Confidence: HIGH |
| Embeddable-Python onedir | **Nuitka 4.1.3 (`--standalone`)** | If you want compiled/obfuscated output and faster startup, and can absorb long build times + a C toolchain. Sometimes fewer AV hits than PyInstaller, but the most complex build of the three and still a swappable dir. Overkill for a single-operator internal tool. |
| minisign / py-minisign | **sigstore 4.4.0 (keyless) / cosign** | Move here when releases are **CI-built** and you want keyless OIDC signing + a public transparency log (Rekor) instead of managing a secret key. Heavier client + infra; justified once you have multiple maintainers or a CI-only release process. |
| minisign / py-minisign | **GitHub artifact attestations** | If you stay entirely inside GitHub Actions and only need provenance for CI-built assets. Verifies "built by this workflow," not "approved by the human who holds the offline key." |
| Inno Setup | **Plain `.zip` (no installer)** | Simplest possible: operator unzips to a folder, runs a shortcut. Acceptable for the single-operator case, but no Start-Menu entry, no clean uninstall, and no place to register the file/DB-outside-install convention. Use only for a throwaway pilot. |
| Inno Setup | **MSIX / WiX MSI** | If you later need enterprise deployment, per-machine policy, or Store distribution. MSIX **requires** code signing and its self-update model (App Installer) fights our directory-swap approach. Too much ceremony for one operator. |
| uv-export build | **pyapp (ofek), Briefcase (BeeWare)** | pyapp = a Rust bootstrapper that fetches Python on first run (needs internet at first launch — violates offline-first). Briefcase = nice native MSI packaging but a GUI-app-oriented toolchain to learn. Consider Briefcase only if you want a maintained end-to-end packager and can drop the directory-swap update model. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **PyInstaller `--onefile`** | Unpacks to a temp dir on every launch (slow, litters `%TEMP%`), the exe is self-locked so you **cannot swap it while running**, and it defeats the directory-swap/rollback model | `--onedir`, or the embeddable-Python onedir |
| **Checksum-only "verification"** | A SHA256SUMS file lives in the **same** release; a compromised GitHub account regenerates it. It proves integrity, **not authenticity** — the client would happily run attacker-signed malware | Checksum **plus** a minisign signature verified against a **baked-in public key** whose secret half never touches GitHub |
| **Embedding the signing secret key in the client, or in a plaintext CI secret used for release signing** | Bakes the "who can publish runnable code" trust into a place an attacker can reach | Keep the minisign **secret key offline** (sign locally), or move to sigstore keyless. Only the **public** key ships in the client |
| **Replacing the running app's own files in-place** | Windows locks loaded `python*.exe`/`*.dll`; overwrite fails mid-update → corrupt install | Detached updater process: wait for app exit → rename `current`→`backup`, `staged`→`current` → Alembic → relaunch → rollback rename on failure |
| **Storing the SQLite DB / config inside the install directory** | A directory swap or uninstall would destroy user data, and rollback couldn't preserve it | Put the DB + `.env` in `%LOCALAPPDATA%\MyOriShop\data\` (via pydantic-settings), **outside** the swappable app dir |
| **PyOxidizer** | Effectively unmaintained (author stepped back); Rust-embedded-Python is a debugging dead-end for a beginner | Embeddable Python or PyInstaller |
| **Fetching deps from a CDN or at first run** | App must work offline | Everything vendored into the bundle at build time (htmx is already vendored) |
| **Auto-updating the central server** | The Docker server at ori.viktorplus.com is the update *target*, not a client; auto-update there would be dangerous | Gate auto-update on the SQLite dialect (mirror the shipped `auto_enabled` role rule) so it is a **no-op** on PostgreSQL/server |

---

## Re-evaluation: the CLAUDE.md "PyInstaller is a v1 rabbit hole" flag

**Original verdict (v1, HIGH-confidence, still correct for its context):** for a solo beginner who only needs to run the app on their own machine, freezing FastAPI+Uvicorn into an exe (hidden imports, uvloop/watchfiles hooks) was pure yak-shaving with zero payoff — `run.bat` + uv was the right answer.

**v4.0 re-evaluation:** packaging is now the *point* of the milestone, so investing in a real distributable is justified. But the v1 concerns did not disappear — they got *more* relevant because we now also need **self-update + Alembic migrations + rollback**:

- PyInstaller still needs hidden-import wrangling for uvicorn and must ship Alembic's `versions/` scripts as bundled data with a corrected `script_location` — exactly the fiddliness the v1 note warned about, now compounded by migrations.
- Packed bootloaders draw **antivirus false positives** and unsigned exes trigger **SmartScreen**; the embeddable approach reuses python.org's already-trusted, signed `python.exe`/`pythonw.exe`, sidestepping the AV problem.
- The directory-swap update model wants **plain, swappable files**; embeddable Python is plain files, a PyInstaller build is a semi-opaque `_internal` blob.

**Conclusion:** the flag is **relaxed, not reversed.** PyInstaller `--onedir` is now an acceptable, well-documented fallback (moved from "What NOT to Use" to "Alternatives"). But for *this* app — beginner-maintained, Alembic-driven, self-updating, offline-first — **embeddable CPython onedir is the lower-magic, better-debuggable, fewer-AV-surprises primary choice.** `--onefile` remains firmly on the do-not-use list.

---

## Stack Patterns by Variant

**Directory & data layout (drives everything):**
- Install to `%LOCALAPPDATA%\MyOriShop\app\` (the swappable "current" dir). DB + config in `%LOCALAPPDATA%\MyOriShop\data\`. Staging + backups in `%LOCALAPPDATA%\MyOriShop\updates\`.
- `run.bat` + `uv run` (dev) survives unchanged for development; the installer produces a **shortcut → `runtime\pythonw.exe app\launcher.py`** for the operator. Two launch stories, one codebase.

**Secure update flow (concrete):**
1. On launch (and/or on an interval) call `GET /repos/<owner>/<repo>/releases/latest`; compare tag `1.<N>` to `app.__version__`.
2. Download the release **archive**, `SHA256SUMS`, and `SHA256SUMS.minisig` via httpx to `updates\`.
3. `py-minisign`: verify `SHA256SUMS.minisig` against the **baked-in public key** → then `hashlib` check the archive against `SHA256SUMS`. **Both must pass** before any file is trusted.
4. Unpack to `updates\staged-1.N\` with zip-slip guarding.
5. Spawn a detached updater; the app exits; updater renames `app`→`backup-<old>`, `staged`→`app`, runs `runtime\python.exe -m alembic upgrade head` (DB lives outside, so migrations apply to the real data), relaunches.
6. **Rollback:** if unpack/verify/Alembic/launch fails at any step, restore `backup-<old>`→`app` and keep the old DB (SQLite backup/`VACUUM INTO` already exists in the app — snapshot the DB before `upgrade head`).

**Where to sign (open decision to surface in the roadmap):**
- **Strongest:** developer signs archives locally with an **offline** minisign key; uploads signatures to the Release. GitHub compromise cannot forge runnable releases.
- **Convenient:** CI signs with a minisign secret in Actions secrets — but that key now lives on GitHub, weakening the guarantee. If you want CI signing, prefer **sigstore keyless** (no long-lived secret) over a stored minisign key.

**Windows trust surface (SmartScreen / Authenticode — separate from minisign):**
- minisign secures the **update channel**; it does nothing for the **first** installer download. An unsigned `MyOriShopSetup.exe` shows SmartScreen "unknown publisher."
- For a **single known operator**, document the one-time "More info → Run anyway" bypass — a code-signing cert is **optional/deferrable**.
- If wider distribution comes later: an **OV** cert still warns until reputation builds; an **EV** cert gives instant SmartScreen reputation but now **requires a hardware token / cloud HSM** and costs more. Wire `SignTool` into Inno Setup at that point.

**Role-aware no-op (mirrors shipped v1.1 rule):** gate the entire updater on `engine.dialect.name == "sqlite"`; on PostgreSQL (the server) it returns immediately.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| py-minisign 0.13.2 | Python >= 3.9 | Fine on 3.13. Pulls `cryptography` >= 46.0.7 (large compiled wheel — include in bundle) |
| PyInstaller 6.21.0 | Python >=3.8,<3.16 | Supports 3.13. Use `--onedir` only; add uvicorn hidden imports + Alembic `versions/` data |
| Nuitka 4.1.3 | Python 3.4–3.14 (CPython) | Supports 3.13; needs a C compiler; `--standalone` |
| sigstore 4.4.0 | Python >= 3.10 | Alternative signing path; heavier than minisign |
| Inno Setup 6.7.3 / 7.0.2 | Windows (any target) | 6.7.3 is the safe default; 7.0.2 (2026-07-13) is very new |
| Python 3.13 embeddable | httpx 0.28.1, Alembic 1.18.5, SQLAlchemy 2.0.51, FastAPI 0.139.0 | All already validated on 3.13 in the existing stack; embeddable runs the identical wheels |
| minisign CLI 0.12 | py-minisign 0.13.2 | Same Ed25519 minisign signature format; sign with CLI, verify in-process with the library |

---

## Sources

- https://pypi.org/pypi/pyinstaller/json — PyInstaller **6.21.0**, requires-python `>=3.8,<3.16` (verified 2026-07-22, HIGH). Note: an `upload_time` value returned by the fetch looked like a placeholder — treat the *date* as unverified, the *version/requires-python* as verified.
- https://pypi.org/pypi/nuitka/json — Nuitka **4.1.3**, CPython 3.4–3.14 (HIGH)
- https://pypi.org/pypi/sigstore/json — sigstore-python **4.4.0**, requires-python `>=3.10` (HIGH)
- https://pypi.org/pypi/py-minisign/json — py-minisign **0.13.2**, released 2026-04-09, requires-python `>=3.9`, depends on `cryptography` >= 46.0.7, MIT (HIGH)
- https://api.github.com/repos/jedisct1/minisign/releases/latest — minisign CLI **0.12**, published 2025-01-15 (HIGH)
- https://jrsoftware.org/isdl.php — Inno Setup **6.7.3** (2026-05-26 stable) and **7.0.2** (2026-07-13) (HIGH)
- Existing root `CLAUDE.md` — validated runtime stack + the v1 PyInstaller flag being re-evaluated here (HIGH)
- Practitioner judgments (embeddable-onedir vs PyInstaller for self-update, checksum-vs-signature threat model, offline-key vs CI-signing tradeoff, Windows running-process self-replace pattern, SmartScreen/AV surface, DB-outside-install-dir) — architecture reasoning from official Python/PyInstaller/minisign/Inno Setup docs knowledge (MEDIUM-HIGH)

---
*Stack research for: Windows self-contained distribution + secure GitHub-Releases auto-update (v4.0)*
*Researched: 2026-07-22*
