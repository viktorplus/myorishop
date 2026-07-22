# Phase 32: In-App Secure Self-Update - Research

**Researched:** 2026-07-22
**Domain:** Secure client self-update — signed-artifact verification, over-the-top code swap, DB-migration-with-rollback, on a bundled-Python Windows client
**Confidence:** HIGH (the Phase 31 mechanisms this phase reuses are all shipped and read at file:line; the one genuinely new primitive — pure-Python minisign Ed25519 verification — is grounded in the minisign spec + a PyCA library)

## Summary

Phase 32 adds the security-critical self-update on top of a nearly-complete Phase 31 foundation. Almost every hard part already exists in the repo and was read for this research: the transactional stop→swap→`alembic upgrade head`→restart state machine with matched-pair (code + DB) rollback (`launcher/swap.py:60-103`), the `pending.json` IPC marker with strict path-confinement (`launcher/swap.py:106-153`), the launcher watch loop that drives one swap cycle per valid marker (`launcher/__main__.py:50-91`), the `VACUUM INTO` pre-update backup anchor (`app/services/backup.py:27-48`), the SQLite-dialect no-op gate pattern (`app/services/backup.py:110`, `app/services/sync_client.py:90`), the background-loop shape for a startup check (`app/main.py:100-128`), the SHA-256 manifest bind+verify helpers (`build_release.py:300-345`), and the `"1.<N>"` integer version single-source (`app/__init__.py:5`, surfaced as `APP_VERSION` at `app/routes/__init__.py:103-105`).

The **one new primitive** is verifying the Ed25519 minisign signature on the operator's machine, where the `minisign` binary is NOT installed (only CI/the offline signer have it — `docs/RELEASE.md`, `tests/test_release_verify.py`). Python's stdlib has no Ed25519, so this phase must add a crypto dependency. The recommendation is **`cryptography`** (PyCA, audited, ships a `cp311-abi3-win_amd64` wheel that runs on the embeddable cp313 runtime) plus a ~30-line pure-Python minisign envelope parser. BLAKE2b-512 (needed for minisign's prehashed `ED` mode) is already in the stdlib (`hashlib.blake2b(digest_size=64)`). Verification is a **hard gate before unpack**: download archive + `manifest.txt` + `manifest.txt.minisig` → verify the minisign signature of `manifest.txt` against the vendored `app/minisign.pub` → verify the archive's SHA-256 against the now-trusted manifest → only then unpack into `staged\` and stage `pending.json`. The **trusted version comes from inside the signed manifest** (`version=1.<N>`), never from the mutable git tag — this is the anti-downgrade authority.

**Primary recommendation:** Split the work exactly along the existing process boundary. The running **app** (has `cryptography`) owns *check → download → verify → unpack-to-`staged\` → `create_backup()` → write `data\pending.json`*; the stdlib-only **launcher** owns *swap → migrate → restart → health-check → rollback* (already built). No new launcher code is strictly required beyond optionally enforcing `expected_version`. Add `cryptography` to `pyproject.toml`, vendor `app/minisign.pub` (currently absent — a blocking prerequisite), and gate the entire path on `engine.dialect.name == "sqlite"`.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UPD-01 | Startup check vs latest GitHub Release; silent no-op offline | GitHub `releases/latest` REST call via `httpx` (already a dep, `pyproject.toml:9`); startup hook mirrors `_auto_sync_loop`/lifespan (`app/main.py:100-128`); offline-safe pattern proven in `sync_client.run_sync_once` (`app/services/sync_client.py:370-382`) |
| UPD-02 | SHA-256 **and** Ed25519 verify of the signed manifest before unpack | SHA-256 bind/verify shipped (`build_release.py:300-345`); Ed25519 verify = new `cryptography` dep + minisign envelope parse (spec grounded below); manifest is the signed blob, not the tag (`docs/RELEASE.md:14-18`) |
| UPD-03 | Notify-and-confirm UI with new version + release notes; «Позже» | New settings surface; release `body` field = notes; mirrors `pages/settings.html` form idiom; locked decision "notify-and-confirm, never silent auto-apply" (STATE.md) |
| UPD-04 | Pre-update backup → `alembic upgrade head` → matched-pair rollback | `backup.create_backup()` (`app/services/backup.py:27-48`); swap+migrate+rollback fully shipped (`launcher/swap.py:60-103`); health check `adapters.health_ok` (`launcher/adapters.py:103-126`) |
| UPD-05 | Header version = installed release; integer `"1.<N>"` compare, anti-downgrade | `__version__` single-source (`app/__init__.py:5`) → `APP_VERSION` global (`app/routes/__init__.py:103-105`); trusted version read from signed manifest; int(N) compare (the `_TAG_RE ^v1\.\d+$` shape already validated at `build_release.py:297`) |
| UPD-06 | Hard no-op on the PostgreSQL server, dialect-gated | Exact pattern shipped at `app/services/backup.py:110` (`if engine.dialect.name != "sqlite": return None`) and `app/services/sync_client.py:90` |
| UPD-07 | Manual «Проверить обновления» from Настройки, independent of startup | New `POST /settings/update/check` route beside the existing `POST /settings/sync` (`app/routes/settings.py:26-56`); `pages/settings.html` is the host page |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Check GitHub Releases for a newer version | App (FastAPI service) | — | Needs `httpx`, `settings`, `__version__`, dialect gate — all app-side. The launcher is stdlib-only and must not import `app.*` (`launcher/__init__.py:6-11`) |
| Download + SHA-256 + Ed25519 verify (hard gate) | App (new `app/services/update.py`) | — | `cryptography` lives in the app's `site-packages`; verification must precede any unpack |
| Unpack verified archive → `staged\`, take pre-update backup, write `pending.json` | App | — | `create_backup()` is app-side; staging into `install_root/staged` is a filesystem op the app performs while still running |
| Stop app → swap `staged\`→`app\` → `alembic upgrade head` → restart | **Launcher (shipped)** | — | Must run OUTSIDE `app\` or it locks the rename target (`launcher/__init__.py:6-11`, WinError 32). Already implemented (`launcher/swap.py:60-103`) |
| Post-update health check + matched-pair rollback | **Launcher (shipped)** | — | `health_ok` polls `127.0.0.1:8000` (`launcher/adapters.py:103-126`); rollback restores `app.prev` + pre-update DB (`launcher/swap.py:94-101`) |
| Notify-and-confirm UI (version + notes, «Обновить и перезапустить» / «Позже») | App (routes + Jinja) | — | Server-rendered HTMX, consistent with `pages/settings.html` |
| Version display in header | App (Jinja global) | — | `APP_VERSION` re-read from `__version__` on each process start (`app/routes/__init__.py:103-105`) |
| Central PostgreSQL server | **No-op** | — | Entire path returns early on non-sqlite dialect (UPD-06) |

## Standard Stack

### Core (all already present except `cryptography`)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cryptography` | **49.0.0** (latest) | Ed25519 signature verification on the operator box | PyCA reference library; stdlib has no Ed25519; ships `cp311-abi3-win_amd64` wheel that runs on the embeddable cp313 runtime [VERIFIED: PyPI — wheel `cryptography-49.0.0-cp311-abi3-win_amd64.whl` present] |
| `httpx` | 0.28.* (installed) | GitHub Releases API call + asset download | Already a dependency (`pyproject.toml:9`); the sync client uses it with strict timeouts (`app/services/sync_client.py:233`) [VERIFIED: pyproject.toml] |
| `hashlib` (stdlib) | — | SHA-256 archive digest + BLAKE2b-512 for minisign prehashed mode | `blake2b(digest_size=64)` confirmed working on this runtime [VERIFIED: local python -c] |
| `alembic` | 1.18.* (installed) | `upgrade head` during swap | Already invoked by the launcher's `migrate` adapter (`launcher/adapters.py:85-100`) [VERIFIED: pyproject.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `zipfile` (stdlib) | — | Unpack the verified onedir archive into `staged\` | The archive is a plain zip built by `build_release._zip_onedir` (`build_release.py:384-402`) |
| `json` (stdlib) | — | Parse GitHub API response; write `pending.json` | `pending.json` schema is 3 keys (`launcher/swap.py:30`) |
| `webbrowser`/`threading` (stdlib) | — | (launcher, already used) | No new use needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `cryptography` (Ed25519 verify) | `PyNaCl` 1.6.2 (libsodium bindings — what minisign is built on) | PyNaCl is also PyCA and legitimate, and its `crypto_sign_open` maps 1:1 to minisign's Ed25519. But `cryptography` is the broader ecosystem default, more likely already understood, and its abi3 wheel story on the embeddable runtime is clean. Either works; recommend `cryptography` for familiarity. [ASSUMED — either is defensible] |
| `cryptography` + hand-written envelope parser | `minisign-py` / `py-minisign` pure-Python packages | Adding a low-download single-maintainer package to the **security-critical verify path** is worse than delegating the actual Ed25519 to an audited library and parsing a tiny, stable envelope ourselves. CLAUDE.md "don't hand-roll crypto" is honored: we do not implement Ed25519, only parse a documented base64 envelope. [CITED: docs.rs/minisign spec; CLAUDE.md] |
| Verifying via the shipped `minisign` **binary** | Bundling `minisign.exe` into the client | The operator box has no minisign binary (`tests/test_release_verify.py` skip-gates the whole round-trip on `shutil.which("minisign")`). Bundling a native exe enlarges the AV/SmartScreen surface the project deliberately minimized (`docs/RELEASE.md:130-133`). Pure-Python verify avoids a second signed native artifact. |

**Installation:**
```bash
uv add cryptography
```
This adds it to `pyproject.toml` `[project].dependencies`; `build_release.vendor_wheels` then exports it via `uv export --frozen` and vendors the win_amd64 wheel into the bundle automatically (`build_release.py:109-142`) — no build change needed beyond the dependency line.

**Version verification:**
```bash
pip index versions cryptography   # 49.0.0 latest (verified 2026-07-22)
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `cryptography` | PyPI | published 2026-06-12 (v49) | seam: unknown | (PyCA — github.com/pyca/cryptography) | **SUS** (only `unknown-downloads` + `no-repository` metadata quirk) | **Approved** — canonical PyCA library, one of the most-downloaded packages on PyPI; the SUS verdict is a false positive from the seam being unable to fetch download stats. Planner should still gate the install behind one `checkpoint:human-verify` per the SUS protocol. |
| `pynacl` (alt) | PyPI | published 2026-01-01 | seam: unknown | github.com/pyca/pynacl | **SUS** (`unknown-downloads`) | Approved as fallback only if `cryptography` is not chosen; same PyCA provenance. |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** `cryptography`, `pynacl` — both are PyCA reference libraries flagged only because the legitimacy seam could not retrieve download counts (`weeklyDownloads: null`). They are verified via official PyCA GitHub + PyPI. Per protocol the planner inserts a `checkpoint:human-verify` before `uv add cryptography`; this is a formality here.

> `cryptography` was discovered from training knowledge and confirmed on the PyPI registry (wheel filenames enumerated). Registry existence alone is not `[VERIFIED]`; treat the *choice* as `[ASSUMED]` pending the planner's human-verify checkpoint, but note it is the industry-standard Ed25519 provider.

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────── APP PROCESS (has cryptography) ──────────────────────────┐
 startup / manual   │                                                                                     │
 «Проверить обн.»──▶│  update.check_for_update()                                                          │
                    │    │  ├─ engine.dialect != sqlite ─────────────────▶ NO-OP (UPD-06)                 │
                    │    │  ├─ GET api.github.com/repos/viktorplus/myorishop/releases/latest (httpx)       │
                    │    │  │     └─ offline / any error ────────────────▶ silent no-op (UPD-01)           │
                    │    │  └─ compare int(remote N from SIGNED manifest) > int(local N)  (UPD-05)         │
                    │    ▼                                                                                 │
                    │  notify-and-confirm surface (version + release body notes)  (UPD-03)                │
                    │    │  «Позже» ─────────────────────────────────────▶ dismiss                        │
                    │    ▼ «Обновить и перезапустить»                                                      │
                    │  update.apply():                                                                     │
                    │    1. download archive + manifest.txt + manifest.txt.minisig                        │
                    │    2. ┌── HARD GATE (UPD-02) ─────────────────────────────────────┐                 │
                    │       │  a. Ed25519 verify manifest.txt.minisig vs app/minisign.pub│                 │
                    │       │  b. SHA-256(archive) == manifest.sha256                    │                 │
                    │       └── any failure ⇒ abort, nothing staged ────────────────────┘                 │
                    │    3. unpack archive ──▶ install_root/staged/                                        │
                    │    4. backup.create_backup() ──▶ data/backups/myorishop-<ts>.db   (UPD-04 anchor)    │
                    │    5. write data/pending.json {staged_dir, expected_version, db_backup_path}         │
                    └───────────────────────────────────┬─────────────────────────────────────────────────┘
                                                        │  (app keeps running; no self-kill needed)
                    ┌───────────────────────────────────▼──── LAUNCHER PROCESS (stdlib-only, SHIPPED) ────┐
                    │  run_once() every 2s: parse_pending (path-confined) ─ invalid ⇒ discard, keep running│
                    │  apply_update():  stop_app ─▶ os.replace(app→app.prev) ─▶ os.replace(staged→app)      │
                    │                   ─▶ migrate: alembic upgrade head ─▶ start_app ─▶ health_ok()?       │
                    │        success ⇒ rmtree(app.prev)                                                    │
                    │        ANY failure ⇒ MATCHED-PAIR ROLLBACK: restore app.prev + restore pre-update DB │
                    └──────────────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
app/
├── services/
│   └── update.py         # NEW: check + download + verify(SHA-256 & Ed25519) + stage + pending.json  (UPD-01/02/04/05/06)
├── routes/
│   └── settings.py       # EXTEND: GET update banner state, POST /settings/update/check, POST /settings/update/apply (UPD-03/07)
├── templates/pages/
│   └── settings.html     # EXTEND: «Проверить обновления» + notify-and-confirm block (UPD-03/07)
├── minisign.pub          # NEW (vendored by the OFFLINE operator — currently ABSENT, blocking prerequisite)
└── main.py               # EXTEND: one-shot startup update check in lifespan (UPD-01), mirroring _auto_sync_loop
launcher/
└── swap.py               # OPTIONAL: enforce pending.expected_version against the staged bundle's __version__
```

### Pattern 1: Verify-before-unpack (the hard gate, UPD-02)
**What:** Never extract attacker-influenced bytes until both checks pass.
**When to use:** Always, before any `zipfile.extractall`.
**Example:**
```python
# Source: minisign spec (jedisct1.github.io/minisign) + cryptography Ed25519 API
import base64, hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def _parse_pubkey(text: str) -> tuple[bytes, bytes]:
    # app/minisign.pub: line 1 = untrusted comment, line 2 = base64(alg||keyid||pk)
    key_line = [ln for ln in text.splitlines() if ln.strip()][-1]  # docs/RELEASE.md:50
    raw = base64.b64decode(key_line)
    assert raw[:2] == b"Ed"                       # signature algorithm marker
    return raw[2:10], raw[10:42]                  # (key_id, 32-byte ed25519 pubkey)

def verify_minisign(manifest_bytes: bytes, sig_text: str, pubkey_text: str) -> bool:
    key_id, pk = _parse_pubkey(pubkey_text)
    lines = sig_text.splitlines()
    sig_raw = base64.b64decode(lines[1])          # base64(alg||keyid||sig)
    alg, sig_key_id, signature = sig_raw[:2], sig_raw[2:10], sig_raw[10:74]
    if sig_key_id != key_id:                      # wrong key ⇒ reject
        return False
    # Algorithm-agnostic: 'ED' = prehashed BLAKE2b-512, 'Ed' = raw message.
    message = (hashlib.blake2b(manifest_bytes, digest_size=64).digest()
               if alg == b"ED" else manifest_bytes)
    try:
        Ed25519PublicKey.from_public_bytes(pk).verify(signature, message)
        return True
    except Exception:                             # cryptography.InvalidSignature etc.
        return False

def sha256_matches(archive_path, expected_hex: str) -> bool:
    import pathlib
    return hashlib.sha256(pathlib.Path(archive_path).read_bytes()).hexdigest() == expected_hex
```
Note: read the trusted `version=` and `sha256=` from the manifest **only after** `verify_minisign` returns True. Reuse `build_release._parse_manifest`-shape parsing (`build_release.py:323-332`) or `verify_manifest` (`build_release.py:335-345`) — but the SHA-256 check must run against the *manifest that was just signature-verified*.

### Pattern 2: Dialect no-op gate (UPD-06) — copy the shipped idiom verbatim
```python
# Source: app/services/backup.py:110 and app/services/sync_client.py:90
from app import db
if db.engine.dialect.name != "sqlite":
    return None   # central PostgreSQL server never self-updates
```

### Pattern 3: Startup one-shot check, offline-safe (UPD-01)
Mirror the lifespan integration of `_auto_sync_loop` (`app/main.py:100-128`) but as a **single** non-blocking task (not a loop — periodic re-check is explicitly deferred, REQUIREMENTS.md:33). Wrap the whole check in a broad `try/except: pass` so an offline start never blocks or logs (same posture as `_auto_sync_iteration`, `app/main.py:80-97`). Do NOT `await` it before `yield` — startup must never block on the network.

### Pattern 4: Integer anti-downgrade compare (UPD-05)
```python
# "1.<N>" — never string compare ("1.9" > "1.10" is True). STATE.md pitfall.
def _counter(v: str) -> int:      # v = "1.15" -> 15
    return int(v.split(".", 1)[1])
def is_strictly_newer(remote: str, local: str) -> bool:
    return _counter(remote) > _counter(local)
```
`local` = `app.__version__` (`app/__init__.py:5`); `remote` = the `version=` line from the **signature-verified** manifest, NOT the git `tag_name`.

### Pattern 5: pending.json IPC (reuse the shipped schema exactly)
The launcher's `parse_pending` requires **exactly** `{staged_dir, expected_version, db_backup_path}` (`launcher/swap.py:30,106-136`) and rejects any extra/missing key or any `..`/absolute path. The app must write those three keys, with `staged_dir` and `db_backup_path` **relative to `install_root`** (e.g. `"staged"` and `"data/backups/myorishop-<ts>.db"`) or `parse_pending` raises `ValueError` and the launcher discards the marker (`launcher/__main__.py:73-78`).

### Anti-Patterns to Avoid
- **Trusting the git tag for the version.** The tag is mutable; the anti-downgrade authority is `version=` inside the signed `manifest.txt` (`docs/RELEASE.md:14-18`). Use the tag only to *locate* the release.
- **Unpacking before verifying.** Any `extractall` before both checks pass defeats UPD-02.
- **Importing `app.*` from the launcher.** Locks `app\`, breaks the rename swap (`launcher/__init__.py:6-11`, WinError 32).
- **Self-killing the app to trigger the swap.** Unnecessary — the launcher's `apply_update` calls `stop_app()` itself (`launcher/swap.py:86`). The app only stages + writes the marker.
- **Storing the pre-update backup inside `app\`.** It must live under the sibling `data\backups\` (already the default, `app/config.py:86`) so the swap can't destroy it and the launcher can restore it (`launcher/adapters.py:129-141`).
- **Running `VACUUM INTO` / the update path on PostgreSQL.** Guard with the dialect gate first (UPD-06).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ed25519 signature verify | A pure-Python Ed25519 implementation | `cryptography` `Ed25519PublicKey.verify` | Constant-time, audited; hand-rolled EC crypto is a classic footgun (CLAUDE.md safety) |
| Stop/swap/migrate/restart/rollback | New swap logic | `launcher.swap.apply_update` (shipped) | Matched-pair rollback + `os.replace` sequencing already correct and unit-tested (`launcher/swap.py`) |
| Pre-update DB snapshot | New backup code | `backup.create_backup()` (shipped) | WAL-safe `VACUUM INTO`, delete-partial-on-failure (`app/services/backup.py:27-48`) |
| DB restore after failed migrate | New restore code | `adapters.backup_restore` (shipped) | Deletes stale `-wal`/`-shm` sidecars (else SQLite corrupts the restored file, `launcher/adapters.py:129-141`) |
| Marker parsing / path confinement | New JSON parser | `launcher.swap.parse_pending` (shipped) | Rejects `..`/absolute/extra-key markers (ASVS V12, `launcher/swap.py:106-153`) |
| Archive SHA-256 bind/verify | New checksum code | `build_release.write_manifest` / `verify_manifest` | Already the release-side contract (`build_release.py:300-345`) |
| Post-update liveness check | New health probe | `adapters.health_ok` (shipped) | Polls `127.0.0.1:8000`, any status = alive (`launcher/adapters.py:103-126`) |

**Key insight:** Phase 32 is ~80% wiring of shipped mechanisms plus one new verification service. The risk is concentrated entirely in the verify-before-unpack gate and the dialect no-op — everything else is proven code.

## Runtime State Inventory

*(This is not a rename/refactor phase, but the self-update touches installed/runtime state, so the relevant categories are answered explicitly.)*

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Operator SQLite DB `data/myorishop.db` + `-wal`/`-shm`; `data/backups/*.db` | Pre-update backup via `create_backup()`; DB restored as the matched pair on rollback. **Never** under `app\`. |
| Live service config | `data/.env` (secret_key, device_id, sync_token) lives in the sibling `data\` (`app/config.py:24,30-31`) | None — physically outside the swappable `app\` (PKG-03); the swap cannot reach it |
| OS-registered state | Start-Menu shortcut → `{app}\launcher\launcher.exe` (`build_release.py:286`); the launcher is the stable PID owner outside `app\` | None — the shortcut targets `launcher\`, which is never swapped |
| Secrets/env vars | `app/minisign.pub` (vendored **public** key, read-only in `app\`); the minisign **secret** key is offline-only (`.gitignore` blocks `*.key`) | `app/minisign.pub` must be present in the bundle before a release is verifiable — **currently ABSENT** (blocking, see Open Questions) |
| Build artifacts / installed packages | `cryptography` win_amd64 wheel must be vendored into `app\Lib\site-packages`; the whole `alembic\versions\` tree is bundled and count-checked (`build_release.py:210-221`) | Add `cryptography` to deps so `vendor_wheels` picks it up; bumping `__version__` requires a matching `v1.<N>` tag or the build fails (`build_release.py:365-381`) |

**Nothing found in category:** All five categories have explicit entries above.

## Common Pitfalls

### Pitfall 1: minisign default mode ambiguity (Ed vs ED)
**What goes wrong:** The verifier assumes legacy raw-message mode but the offline signer produced a prehashed (`ED`, BLAKE2b-512) signature (or vice-versa), so verification always fails.
**Why it happens:** `minisign -S` mode depends on the minisign version/flags; `docs/RELEASE.md:97` shows `minisign -S -m manifest.txt -t "..."` without pinning the mode.
**How to avoid:** Make the verifier **algorithm-agnostic** — read the 2-byte algorithm from the `.minisig` line and branch (`ED` ⇒ hash with `hashlib.blake2b(digest_size=64)`, `Ed` ⇒ raw). Shown in Pattern 1. Add a test that verifies a real `minisign`-produced signature in BOTH modes (CI has the binary — `tests/test_release_verify.py`).
**Warning signs:** Verification fails on a genuinely-valid release from the offline machine.

### Pitfall 2: String version comparison (the 9→10 boundary)
**What goes wrong:** `"1.9" < "1.10"` is False as strings, so `1.9` never offers `1.10`.
**Why it happens:** Lexicographic compare on `"1.<N>"`.
**How to avoid:** Compare `int(N)` (Pattern 4). STATE.md explicitly calls for a 9→10 boundary test.
**Warning signs:** An update stops being offered at a `.9`→`.10` rollover.

### Pitfall 3: Backup or staged dir written inside `app\`
**What goes wrong:** The over-the-top swap (`os.replace(app→app.prev)` then delete) destroys the only copy of the operator's ledger or the staged bytes.
**Why it happens:** CWD under packaging is `app\` (`launcher/adapters.py:56`), so a relative path lands inside the swappable dir — the exact wipe-risk `app/config.py:80-86` warns about.
**How to avoid:** Stage into `install_root/staged` and back up into `data/backups/` (both siblings of `app\`). `pending.json` paths are confined relative to `install_root` (`launcher/swap.py:139-153`).
**Warning signs:** `data\` shrinks after an update; rollback finds no backup.

### Pitfall 4: Startup check blocks or crashes offline launch
**What goes wrong:** The update check awaits a network call before `yield`, so a no-internet start hangs or errors.
**Why it happens:** Treating the check as blocking startup work.
**How to avoid:** Fire it as a non-blocking task after `yield` (or in a background task), wrapped in a broad guard — mirror `_auto_sync_iteration`'s posture (`app/main.py:80-97`). UPD-01 requires a *silent no-op* offline.
**Warning signs:** The app is slow or fails to open the browser when offline.

### Pitfall 5: GitHub API without a User-Agent / rate limits
**What goes wrong:** GitHub rejects requests lacking a `User-Agent`, or the unauthenticated 60-req/hour/IP limit is hit.
**Why it happens:** Missing header; over-frequent checks.
**How to avoid:** Send a `User-Agent: MyOriShop/<version>` header; check only on startup + manual (periodic re-check is deferred, REQUIREMENTS.md:33). `/releases/latest` already excludes drafts and prereleases. [CITED: docs.github.com REST releases]
**Warning signs:** `403` with `X-RateLimit-Remaining: 0`, or `403 Forbidden` with no rate-limit context.

### Pitfall 6: `expected_version` in `pending.json` is parsed but not enforced
**What goes wrong:** The launcher swaps whatever is in `staged\` regardless of whether it matches the version the app intended, so a stale/malicious `staged\` could be applied.
**Why it happens:** `apply_update` uses `stop/replace/migrate` but does not compare `pending.expected_version` to the staged bundle's `__version__` (`launcher/swap.py:60-103`).
**How to avoid:** OPTIONAL hardening — have the launcher (or the app just before writing the marker) assert the staged `app/__init__.py __version__` equals `expected_version`. Low effort; closes a defense-in-depth gap. Flag as a decision.
**Warning signs:** A `staged\` left over from an aborted run gets applied on next launch.

## Code Examples

### GitHub latest-release check (offline-safe)
```python
# Source: docs.github.com REST /repos/{owner}/{repo}/releases/latest + app/services/sync_client.py timeout idiom
import httpx
_REPO = "viktorplus/myorishop"   # from `git remote -v`
_TIMEOUT = httpx.Timeout(connect=3.0, read=10.0, write=10.0, pool=3.0)  # sync_client.py:233

def fetch_latest_release() -> dict | None:
    try:
        r = httpx.get(
            f"https://api.github.com/repos/{_REPO}/releases/latest",
            headers={"User-Agent": f"MyOriShop", "Accept": "application/vnd.github+json"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()   # -> tag_name, body (release notes), assets[].browser_download_url
    except httpx.HTTPError:
        return None       # offline / rate-limited / error ⇒ silent no-op (UPD-01)
```

### Writing the pending.json marker (matches the shipped schema)
```python
# Source: launcher/swap.py:30,106-136 (keys must be EXACTLY these three, paths relative to install_root)
import json
from pathlib import Path
def stage_pending(install_root: Path, staged_rel: str, version: str, backup_rel: str) -> None:
    marker = install_root / "data" / "pending.json"
    marker.write_text(json.dumps({
        "staged_dir": staged_rel,          # e.g. "staged"
        "expected_version": version,       # e.g. "1.16"
        "db_backup_path": backup_rel,      # e.g. "data/backups/myorishop-20260722-101500.db"
    }), encoding="utf-8")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Verify via `minisign` CLI (as CI does) | Pure-Python Ed25519 verify with `cryptography` on the operator box | This phase | No native binary shipped; smaller AV surface |
| Sign the whole archive | Sign a small `manifest.txt` binding version + archive SHA-256 | Phase 31 | Verify one tiny signature then a fast hash; version inside signed payload (`docs/RELEASE.md:14-18`) |
| `run.bat` kills stale server by port | Launcher owns the child PID, stops by handle | Phase 31 | Deterministic stop before rename (`launcher/adapters.py:28-83`) |

**Deprecated/outdated:**
- PyInstaller single-file exe self-update patterns — N/A; this project ships a Python **embeddable onedir** (`build_release.py` docstring), which is exactly what makes an over-the-top directory swap possible.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `cryptography` is the right Ed25519 provider (vs `PyNaCl`) | Standard Stack | Low — both are PyCA; swap is a one-line dep change |
| A2 | The offline signer's `minisign -S` mode (Ed vs ED) is not fixed | Pitfall 1 | Mitigated by an algorithm-agnostic verifier; if wrong, a valid release fails to verify |
| A3 | Unauthenticated GitHub API (60/hr) suffices for startup+manual checks | Pitfall 5 | Low for a single operator; a token would only be needed at high frequency |
| A4 | `install_root/staged` and `data/backups/...` are the correct relative marker paths | Pattern 5 | Medium — wrong paths make `parse_pending` reject the marker (fails safe: no swap) |
| A5 | The launcher needs no new code (expected_version enforcement optional) | Responsibility Map | Low — the shipped `apply_update` covers UPD-04; A6 is defense-in-depth only |
| A6 | `cryptography` abi3 wheel imports cleanly under the embeddable cp313 `._pth` | Standard Stack | Medium — must be smoke-tested in the bundle (the `._pth` adds `Lib\site-packages`, `build_release.py:46`) |

## Open Questions

1. **GitHub owner/repo for releases**
   - What we know: `git remote -v` → `github.com/viktorplus/myorishop`; existing tags `v1.0..v2.0`.
   - What's unclear: Is that repo **public** (so unauthenticated `/releases/latest` works), and is it where signed `v1.<N>` releases will be published?
   - Recommendation: Confirm with the operator; default to `viktorplus/myorishop` public. If private, a read-only token must be provisioned (adds a secret to `.env`).

2. **`app/minisign.pub` is absent (BLOCKING)**
   - What we know: The verify gate needs the vendored public key; it is not in the repo (`ls app/minisign.pub` → not present); `build_release` treats it as optional (`build_release.py:51,196-201`).
   - What's unclear: When will the operator run `minisign -G` and commit `app/minisign.pub` (`docs/RELEASE.md:22-60`)?
   - Recommendation: This is a prerequisite for any end-to-end test. The plan should include a `checkpoint:human-verify` that `app/minisign.pub` exists and its key line starts `RW` before the verify tests can pass unskipped.

3. **Post-update health-check definition**
   - What we know: `adapters.health_ok` treats *any* HTTP status on `/` as alive (`launcher/adapters.py:103-126`).
   - What's unclear: Is "any response" strong enough, or should the launcher assert the **new** version is actually running (e.g. a tiny unauthenticated `/version` or `/health` endpoint returning `__version__`)?
   - Recommendation: Consider adding a public `/health` route returning `{"version": APP_VERSION}` so the health check can confirm the swap actually took (stronger UPD-04 guarantee). User-owned decision.

4. **Two real signed releases needed to test e2e**
   - What we know: Phase 32 "cannot even be end-to-end tested until two real signed releases exist" (ROADMAP.md:317; STATE.md v4.0 decisions).
   - What's unclear: Which throwaway `v1.<N>`/`v1.<N+1>` tags to cut, and who runs the offline signing.
   - Recommendation: Plan a UAT that cuts two throwaway tags, signs both offline, and exercises the full round trip on a bare Windows box.

5. **Verify the global (trusted-comment) signature too?**
   - What we know: minisign's trusted comment is authenticated by a second global signature (spec).
   - What's unclear: Do we need to verify it, given the primary payload (`manifest.txt`) already carries version + SHA-256?
   - Recommendation: Verify the primary signature at minimum (sufficient for UPD-02); optionally verify the global signature for completeness. Low cost.

6. **`expected_version` enforcement in the launcher (Pitfall 6)**
   - Recommendation: Decide whether to add the (small) launcher-side or app-side assertion that the staged bundle's `__version__` equals `pending.expected_version`. Defense-in-depth; not required by UPD-04.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `httpx` | GitHub API + asset download | ✓ | 0.28.* | — |
| `hashlib.blake2b`/`sha256` (stdlib) | minisign prehashed + archive digest | ✓ | stdlib | — |
| `cryptography` | Ed25519 verify | ✗ (not yet a dep) | 49.0.0 target | none — must add (no stdlib Ed25519) |
| `app/minisign.pub` | verify gate | ✗ | — | none — operator must vendor it (OQ-2) |
| `alembic` | migrate on swap | ✓ | 1.18.* | — |
| `minisign` binary (operator box) | — | ✗ (by design) | — | pure-Python verify (this phase) |
| Internet / GitHub reachable | update check | runtime-variable | — | silent no-op offline (UPD-01) |

**Missing dependencies with no fallback:**
- `cryptography` (add to `pyproject.toml`) and `app/minisign.pub` (operator-vendored) — both block the verify path.

**Missing dependencies with fallback:**
- Internet at startup — falls back to a silent no-op (required behavior, not a failure).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* (`pyproject.toml:23`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `uv run pytest tests/test_update.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UPD-01 | Newer release detected; offline = no-op (fetch returns None) | unit (httpx mock via `respx`/monkeypatch) | `pytest tests/test_update.py::test_check_detects_newer -x` | ❌ Wave 0 |
| UPD-02 | SHA-256 mismatch aborts; bad Ed25519 aborts; valid passes | unit | `pytest tests/test_update.py::test_verify_gate -x` | ❌ Wave 0 |
| UPD-02 | Real minisign round-trip (Ed AND ED modes) verifies in pure Python | integration (skip-gated on `minisign` binary, like `test_release_verify.py`) | `pytest tests/test_update.py::test_minisign_pure_python_verify -x` | ❌ Wave 0 |
| UPD-03 | Confirm applies; «Позже» dismisses; notes rendered | integration (TestClient) | `pytest tests/test_update.py::test_confirm_and_defer -x` | ❌ Wave 0 |
| UPD-04 | Pre-update backup taken; migrate-fail ⇒ matched-pair rollback | unit (reuse `test_launcher.py` fake-callbacks pattern) | `pytest tests/test_update.py::test_apply_rolls_back -x` | ⚠ extend `tests/test_launcher.py` |
| UPD-05 | int compare; 9→10 boundary; downgrade refused; version from signed manifest | unit | `pytest tests/test_update.py::test_anti_downgrade -x` | ❌ Wave 0 |
| UPD-06 | PostgreSQL dialect ⇒ entire path no-op | unit (dialect-gate seam) | `pytest tests/test_update.py::test_server_noop -x` | ❌ Wave 0 |
| UPD-07 | Manual check route returns banner state | integration (TestClient) | `pytest tests/test_update.py::test_manual_check -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_update.py -x`
- **Per wave merge:** `uv run pytest` (full suite — 1185 currently green; note 4 pre-existing `test_sync_ui.py` failures are OUT OF SCOPE, see MEMORY `preexisting-sync-ui-test-failures`)
- **Phase gate:** Full suite green + CI `release-verify` job green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_update.py` — new RED scaffold covering UPD-01..07 (import update service INSIDE test bodies to keep collection green, mirroring `tests/test_release_verify.py`/`test_packaging.py`)
- [ ] Test fixtures: a fake GitHub `/releases/latest` JSON, a tmp minisign keypair (throwaway, skip-gated on the binary), a synthetic zip + manifest + `.minisig`
- [ ] Extend `tests/test_launcher.py` for the app-writes-marker → launcher-applies integration (the swap half is already covered)
- [ ] Dependency install: `uv add cryptography` (behind a `checkpoint:human-verify`)

## Security Domain

> `security_enforcement=true`, ASVS L1, `security_block_on=high` (`.planning/config.json`). This is the phase where fetched code is executed — verification is a hard gate.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | Verify-before-unpack gate; app/launcher process split; dialect no-op boundary |
| V2 Authentication | no | Update check is unauthenticated read of a public release; no credentials |
| V5 Input Validation | yes | GitHub JSON is untrusted — validate `tag_name`/`version` shape (`^1\.\d+$`), asset URLs are `https://github.com`/`objects.githubusercontent.com` only; never render raw server error bytes (T-29-07 idiom, `sync_client.py:172-216`) |
| V6 Cryptography | yes | Ed25519 verify via `cryptography` (never hand-rolled); SHA-256 + BLAKE2b-512 via stdlib; the public key is vendored, the secret key is offline-only |
| V10 Malicious Code / Integrity | yes | **Signature + checksum before unpack** (UPD-02); anti-downgrade from signed manifest (UPD-05); matched-pair rollback (UPD-04) |
| V12 File & Resources | yes | `pending.json` path confinement (shipped, `launcher/swap.py:139-153`); staged unpack confined to `install_root/staged`; zip-slip guard on `extractall` |

### Known Threat Patterns for a self-updating client

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious/forged update artifact | Tampering / Elevation | Ed25519 verify of the signed manifest against vendored `app/minisign.pub` BEFORE unpack (UPD-02); abort on failure |
| Downgrade to a vulnerable version | Tampering | Integer `"1.<N>"` compare from the signed manifest; refuse ≤ current (UPD-05) |
| Man-in-the-middle on download | Tampering / Info Disclosure | HTTPS to GitHub; the signature+checksum make transport tampering detectable regardless |
| Mutable-tag substitution | Tampering | Trust the `version=` inside the signed manifest, never the git tag (`docs/RELEASE.md:14-18`) |
| Zip-slip on unpack | Tampering | Validate each archive member path stays under `staged\` before extract |
| Path traversal via `pending.json` | Tampering | `parse_pending` rejects `..`/absolute/extra keys (shipped, `launcher/swap.py:106-153`) |
| Signing-key exfiltration | Info Disclosure | Secret key offline-only, never in CI/repo (`.gitignore *.key`, `docs/RELEASE.md`, T-31-02) — inherited, not re-solved here |
| Half-applied migration / data loss | Denial of Service | Pre-update `VACUUM INTO` backup + matched-pair rollback (UPD-04, `launcher/swap.py:94-101`) |
| Server (PostgreSQL) tries to self-update | Denial of Service | Hard dialect no-op (UPD-06) |
| DoS via update check blocking offline launch | Denial of Service | Non-blocking, broad-guarded startup check (UPD-01) |

**Expected threat IDs:** the roadmap notes plans carry a threat model `T-32-01..10` (ASVS L1). The mitigations above map directly onto those; `/gsd-secure-phase 32` will formalize them.

## Project Constraints (from CLAUDE.md)

- **Locked stack:** Python 3.13 / FastAPI / SQLAlchemy 2.0 / SQLite / HTMX server-rendered — no SPA, no new frontend toolchain. Update UI is server-rendered HTMX in `pages/settings.html`.
- **Offline-first, vendored assets:** `app/minisign.pub` and the `cryptography` wheel are vendored into the bundle; no CDN, no runtime pip.
- **Portable ORM only:** the dialect gate uses `engine.dialect.name` (already the project idiom); no SQLite-specific SQL added. `VACUUM INTO` is reused only inside the existing sqlite-gated `create_backup`.
- **Integer scheme:** version is the `"1.<N>"` integer counter (not semver); money is integer cents (untouched here).
- **Don't hand-roll crypto:** Ed25519 delegated to `cryptography`; only the (documented, tiny) minisign envelope is parsed in-house.
- **Smallest safe change / patch existing:** reuse `create_backup`, `apply_update`, `parse_pending`, `verify_manifest`, `health_ok`, `_auto_sync_loop` shape verbatim; add one service + one route group + one template block + one dependency.
- **GSD workflow:** all edits through the GSD execute-phase flow; sequential main-tree execution with a full-suite post-wave gate (MEMORY `execute-phase-sequential-mode`).
- **Communication:** verification/UAT copy in Russian; code/comments/commits in English.

## Sources

### Primary (HIGH confidence — read at file:line this session)
- `launcher/swap.py`, `launcher/__main__.py`, `launcher/adapters.py`, `launcher/__init__.py` — swap state machine, marker parse, Windows adapters, no-`app.*` rule
- `build_release.py` — manifest/SHA-256/tag↔version, wheel vendoring, `._pth` fix, onedir zip
- `app/services/backup.py` — `create_backup` VACUUM INTO, dialect gate
- `app/services/sync_client.py` — background-loop / offline-safe / dialect-role idioms
- `app/main.py` — lifespan + `_auto_sync_loop` shape
- `app/config.py` — `MYORISHOP_DATA_DIR` sibling data-dir, backup_dir wipe-risk note
- `app/__init__.py`, `app/routes/__init__.py` — `__version__` → `APP_VERSION` global
- `app/routes/settings.py`, `app/services/settings.py`, `app/templates/pages/settings.html` — settings surface host
- `docs/RELEASE.md` — sign-manifest-not-archive, offline key, `RW` pubkey marker
- `tests/test_release_verify.py`, `tests/conftest.py` — minisign invocation + skip-gate + fixture patterns
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/config.json` — requirements, decisions, flags

### Secondary (MEDIUM confidence)
- jedisct1.github.io/minisign — signature/public-key byte layout, Ed/ED prehashed BLAKE2b-512, trusted-comment global signature
- PyPI JSON API — `cryptography` 49.0.0 + `cp311-abi3-win_amd64` wheel; `pynacl` 1.6.2
- docs.github.com REST — `/repos/{owner}/{repo}/releases/latest` shape, User-Agent + rate-limit behavior

### Tertiary (LOW confidence)
- minisign `-S` default mode (Ed vs ED) — resolved by making the verifier algorithm-agnostic rather than relying on the default

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every reused library is installed/read; the one new dep (`cryptography`) is registry-verified with a compatible wheel
- Architecture: HIGH — the swap/backup/marker/rollback mechanisms are shipped code read at file:line
- Verification primitive: MEDIUM-HIGH — minisign format is well-specified; the Ed vs ED default is the only soft spot, mitigated by an agnostic verifier
- Pitfalls: HIGH — grounded in the project's own comments (wipe-risk, string-compare, no-`app.*`, WAL sidecars)

**Research date:** 2026-07-22
**Valid until:** 2026-08-21 (30 days; stable — the reused mechanisms are frozen and `cryptography` is a mature library)
</content>
</invoke>
