# Phase 32: In-App Secure Self-Update - Pattern Map

**Mapped:** 2026-07-22
**Files analyzed:** 7 (2 new, 5 modified/extended) + 1 vendored asset (blocking prereq)
**Analogs found:** 7 / 7 (every mechanism this phase wires is shipped code, read at file:line)

> Grounding note: 32-RESEARCH.md already maps each new file to its shipped analog at file:line. This document confirms those analogs by reading the actual code and extracts the concrete excerpts the planner copies from. Where RESEARCH cited a symbol, it was verified present (all confirmed). The one genuinely-absent artifact is `app/minisign.pub` (see No Analog Found).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/services/update.py` (NEW) | service | request-response + file-I/O (check→download→verify→stage→marker) | `app/services/backup.py` + `app/services/sync_client.py` | role-match (compose two analogs) |
| minisign/Ed25519 verifier (NEW, inside `update.py` or `app/services/minisign_verify.py`) | utility | transform (bytes→bool) | `build_release.py:300-345` (manifest bind/verify) + `tests/test_release_verify.py` | partial (SHA-256 analog exists; Ed25519 is the one new primitive) |
| `app/routes/settings.py` (EXTEND) | route | request-response (HTMX partial) | `app/routes/settings.py:27-51` (existing `POST /settings/sync`) | exact (same file, same idiom) |
| `app/templates/pages/settings.html` (EXTEND) | component (template) | request-response | `pages/settings.html:23-48` (sync `<h2>`+form block) | exact (same file) |
| `app/main.py` lifespan (EXTEND) | config (app wiring) | event-driven (startup hook) | `app/main.py:100-128` (`_auto_sync_loop`/lifespan) | exact (same file) |
| `pending.json` producer (NEW, in `update.py`) | utility | file-I/O (IPC marker) | `launcher/swap.py:106-136` (`parse_pending` — the consumer contract) | exact (schema is a shipped hard contract) |
| `launcher/swap.py` (OPTIONAL extend) | service | event-driven | `launcher/swap.py:60-103` (`apply_update`) | exact (defense-in-depth only, A5/Pitfall 6) |
| `app/__init__.py` `__version__` (READ-only source) | config | — | `app/__init__.py:5` | exact (anti-downgrade compare source) |

## Pattern Assignments

### `app/services/update.py` (service, request-response + file-I/O)

This is the one substantial new file. It composes four shipped idioms: dialect no-op gate, offline-safe httpx fetch, VACUUM-INTO backup, and the pending.json marker. Verify-before-unpack is the security-critical new logic.

**Analog A — dialect no-op gate (UPD-06), copy verbatim.** `app/services/backup.py:110`:
```python
if engine.dialect.name != "sqlite":
    return None   # central PostgreSQL server never self-updates
```
Same idiom also at `app/services/sync_client.py:90` (`session.get_bind().dialect.name == "sqlite"` as the role signal). Run this FIRST in every public entry point (`check_for_update`, `apply`).

**Analog B — offline-safe httpx fetch (UPD-01), from `sync_client`.** Timeout constant `app/services/sync_client.py:233`:
```python
SYNC_TIMEOUT = httpx.Timeout(connect=3.0, read=10.0, write=10.0, pool=3.0)
```
Return-None-on-any-HTTPError posture, `app/services/sync_client.py:377-382`:
```python
except httpx.HTTPStatusError:
    return SyncResult(status="error", ...)
except httpx.HTTPError:
    # Offline / timeout / transport error: never raised out (SYNC-06).
    return SyncResult(status="offline", ...)
```
Mirror this for `fetch_latest_release() -> dict | None` — catch `httpx.HTTPError`, return `None` for a silent no-op (UPD-01). Add `headers={"User-Agent": "MyOriShop/<version>", "Accept": "application/vnd.github+json"}` (Pitfall 5).

**Analog C — pre-update backup (UPD-04 anchor), reuse the shipped function.** `app/services/backup.py:27-48` `create_backup(engine, backup_dir)` — WAL-safe `VACUUM INTO ?` with a bound parameter (never f-string, T-3-08) and delete-partial-on-failure. Call it AFTER verification passes and BEFORE writing the marker. Back up into `Path(settings.backup_dir)` (already the absolute sibling of `app\`, `app/config.py:86`) — never a relative path (Pitfall 3).

**Analog D — verify-before-unpack HARD GATE (UPD-02), extends `build_release.py`.** The SHA-256 half is shipped at `build_release.py:335-345`:
```python
def verify_manifest(archive_path, manifest_path) -> bool:
    expected = _parse_manifest(manifest_path).get("sha256")
    if not expected:
        return False
    actual = hashlib.sha256(Path(archive_path).read_bytes()).hexdigest()
    return actual == expected
```
Manifest field parsing to reuse, `build_release.py:323-332` (`_parse_manifest`, `key=value` lines → dict). The manifest schema written by the release side, `build_release.py:313-314`: `version={version}\narchive={name}\nsha256={sha}\n`. Read `version=` and `sha256=` **only after** the Ed25519 signature verifies (RESEARCH Pattern 1 note). Ed25519 is the new primitive (see next file).

**Ordering (RESEARCH diagram lines 103-112):** dialect-gate → fetch → int-compare → download archive+manifest+.minisig → (a) Ed25519 verify manifest vs `app/minisign.pub` → (b) SHA-256(archive)==manifest.sha256 → any failure aborts with nothing staged → `zipfile.extractall` into `install_root/staged` (with zip-slip guard) → `create_backup()` → write `data/pending.json`.

**Anti-downgrade compare (UPD-05), RESEARCH Pattern 4.** `local = app.__version__` (`app/__init__.py:5`, currently `"1.15"`); `remote` = the `version=` from the signature-verified manifest, never `tag_name`. Integer compare `int(v.split(".",1)[1])` — string compare fails the 9→10 boundary (Pitfall 2).

---

### minisign/Ed25519 verifier (utility, transform) — THE one new primitive

**Analog:** `tests/test_release_verify.py` (minisign binary invocation + `shutil.which("minisign")` skip-gate) and `build_release.py` manifest logic. No existing Ed25519 code — this is new, delegated to `cryptography` (`Ed25519PublicKey.from_public_bytes(pk).verify(sig, msg)`), never hand-rolled (CLAUDE.md safety). Full envelope-parse skeleton is in RESEARCH Pattern 1 (lines 142-173): parse `app/minisign.pub` line 2 = base64(alg||keyid||pk); parse `.minisig` line 2 = base64(alg||keyid||sig[64]); branch `ED` (BLAKE2b-512 prehash, `hashlib.blake2b(digest_size=64)`) vs `Ed` (raw) — algorithm-agnostic (Pitfall 1). New dep `cryptography` 49.0.0 behind a `checkpoint:human-verify` (SUS false-positive, RESEARCH Package Audit).

**Skip-gate pattern to copy** from `tests/test_release_verify.py`: gate the real-minisign round-trip test on the binary's presence so CI (has minisign) runs it and the dev box skips — mirror for `tests/test_update.py::test_minisign_pure_python_verify`.

---

### `app/routes/settings.py` (route, request-response HTMX partial) — EXTEND

**Analog:** the existing `POST /settings/sync` in the SAME file, `app/routes/settings.py:27-51`:
```python
@router.post("/settings/sync")
def settings_save_sync(request: Request, auto_enabled: str = Form(""), ...):
    ...
    context = settings_summary(session, Path(settings.backup_dir))
    context["sync_saved"] = True
    return templates.TemplateResponse(request, "pages/settings.html", context)
```
Add `POST /settings/update/check`, `POST /settings/update/apply`, `POST /settings/update/dismiss` beside it (UPD-07/03). Per UI-SPEC these target a `#update-panel` partial (`hx-swap="innerHTML"`), so return a small partial template, NOT the whole page. Keep the thin-route rule (`settings.py:1-5` docstring): all logic in `app/services/update.py`, the route just calls the service and picks a context/partial. Always return **200** with a caption partial on a check failure — never a 5xx (UI-SPEC S2, mirrors sync's non-blocking posture). Admin-gating is already applied at the router include, `app/main.py:201-203` (`require_role("administrator")`) — no per-route guard needed. Untrusted GitHub fields (`body`, `tag_name`) render autoescaped, never `|safe` (UI-SPEC Accessibility & Security, T-29-07).

---

### `app/templates/pages/settings.html` (template) — EXTEND

**Analog:** the sync section in the SAME file, `pages/settings.html:23-48` — `<h2>` + `form.stacked-form` + `.field` + `.form-actions` + `<button>`, with CSRF carried by the base body `hx-headers` (`base.html:35`). Copy that idiom for the `«Обновление приложения»` section. Per UI-SPEC:
- Wrap the section in `{% if not is_server_db %}` (dialect no-op, UPD-06 — `is_server_db` is already in template context via `_sync_status_context`, `app/routes/__init__.py:92`).
- Manual check: `<form ... hx-post="/settings/update/check" hx-target="#update-panel" hx-swap="innerHTML" hx-indicator="#update-inflight">` button «Проверить обновления».
- `#update-panel` partial renders one of: up-to-date `.muted` caption, S1 amber notice (`background:#fef9e7;border:1px solid #b45309` — the shipped `.price-below` token pair, no new class), or offline `.muted` caption.
- Failure states use `.error-block` (UI-SPEC S3). Exact Russian copy is locked in 32-UI-SPEC.md Copywriting Contract — copy verbatim.

---

### `app/main.py` lifespan (config/wiring, event-driven startup) — EXTEND

**Analog:** `_auto_sync_iteration` + `_auto_sync_loop` + `lifespan`, `app/main.py:65-128`. The broad-guard offline posture to copy, `app/main.py:80-97`:
```python
try:
    ...
except Exception:
    # offline / transport / transient DB error → silently skip.
    pass
```
lifespan integration, `app/main.py:112-128` — but per RESEARCH Pattern 3, the update check is a **single one-shot** non-blocking task, NOT a loop (periodic re-check is deferred). Do NOT `await` it before `yield` — an offline start must never block (UPD-01/Pitfall 4). Shape: `asyncio.create_task(...)` after `startup_backup()`, wrapped in the broad guard. Offload any blocking work with `anyio.to_thread.run_sync(..., abandon_on_cancel=False)` like `app/main.py:91-93`.

---

### `pending.json` producer (utility, file-I/O IPC) — NEW (in `update.py`)

**Analog / hard contract:** `launcher/swap.py:30,106-136` — `parse_pending` requires EXACTLY `{staged_dir, expected_version, db_backup_path}` (`_REQUIRED_KEYS`, `swap.py:30`) and rejects any extra/missing key, `..`, or absolute path (`_confine`, `swap.py:139-153`, ASVS V12). The producer must write those three keys, paths **relative to `install_root`** (`"staged"`, `"data/backups/myorishop-<ts>.db"`) or the launcher discards the marker. Writer skeleton is in RESEARCH lines 297-308. Write to `install_root/data/pending.json` (the sibling data dir, `app/config.py:24`).

---

### `launcher/swap.py` (service, event-driven) — OPTIONAL extend (defense-in-depth)

**Analog:** `apply_update`, `launcher/swap.py:60-103` — already does stop→`os.replace(app→app_prev)`→`os.replace(staged→app)`→`migrate`→`start_app`→`health_ok`→rollback. **No new code required for UPD-04** (A5). Pitfall 6 / OQ-6 flags an OPTIONAL assertion that the staged bundle's `__version__` equals `pending.expected_version` before swapping — planner decides. If added, it stays stdlib-only (never import `app.*` — WinError 32, `launcher/__init__.py:6-11`); read the staged `app/__init__.py` as text, not via import.

## Shared Patterns

### Dialect no-op gate (UPD-06)
**Source:** `app/services/backup.py:110`, `app/services/sync_client.py:90`
**Apply to:** every public entry in `update.py` (check + apply), the settings route handlers, and the settings template section render.
```python
if engine.dialect.name != "sqlite":
    return None   # central PostgreSQL server never self-updates
```

### Offline-safe / broad-guard posture (UPD-01)
**Source:** `app/services/sync_client.py:377-382`, `app/main.py:80-97`
**Apply to:** the GitHub fetch (return `None`), the startup task (swallow all), the manual-check route (return a 200 caption, never a 5xx).

### Matched-pair backup + rollback (UPD-04)
**Source:** `app/services/backup.py:27-48` (`create_backup`), `launcher/swap.py:86-101` (`apply_update` rollback), `launcher/adapters.py:129-141` (`backup_restore` — deletes `-wal`/`-shm`)
**Apply to:** `update.py` takes the pre-update backup; the shipped launcher performs the paired revert. Backup MUST land under `settings.backup_dir` (absolute sibling of `app\`, `app/config.py:86`) — never a relative path (Pitfall 3).

### Untrusted-input autoescape (V5)
**Source:** T-29-07 fixed-string-error idiom (`sync_client.py`), UI-SPEC Accessibility & Security
**Apply to:** all GitHub JSON (`body`, `tag_name`, `version`) — validate version shape `^1\.\d+$`, render autoescaped (never `|safe`), never echo raw server/error bytes into the panel.

### pending.json path confinement (V12)
**Source:** `launcher/swap.py:106-153`
**Apply to:** the marker producer — three exact keys, relative paths only.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/minisign.pub` | secret/asset (vendored PUBLIC key) | — | **ABSENT in the repo** (`ls app/minisign.pub` → not present, confirmed). BLOCKING prerequisite: the operator must run `minisign -G` offline and commit the pubkey (key line starts `RW`, `docs/RELEASE.md:22-60`) before the verify gate/tests can pass unskipped. Not a code analog — an operator-provisioned artifact. Gate with a `checkpoint:human-verify`. |
| Ed25519 signature verify | utility | transform | No Ed25519 code exists anywhere in the codebase; stdlib has none. New `cryptography` dep + ~30-line envelope parser (RESEARCH Pattern 1). The SHA-256 half has an analog (`build_release.verify_manifest`); the Ed25519 half does not. |

## Metadata

**Analog search scope:** `app/services/` (backup, sync_client), `app/routes/` (settings, __init__), `app/main.py`, `app/templates/` (settings.html, base.html), `launcher/` (swap, adapters), `build_release.py`, `app/__init__.py`, `app/config.py`
**Files scanned:** 11 read at file:line this session (all RESEARCH-cited analogs verified present; `app/minisign.pub` verified absent)
**Pattern extraction date:** 2026-07-22
