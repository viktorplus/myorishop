---
phase: 32-in-app-secure-self-update
reviewed: 2026-07-22T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - app/services/minisign_verify.py
  - app/services/update.py
  - app/routes/health.py
  - app/routes/settings.py
  - app/services/security.py
  - app/services/settings.py
  - app/main.py
  - app/templates/pages/settings.html
  - app/templates/partials/update_panel.html
  - launcher/__main__.py
  - launcher/adapters.py
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
status: issues_found
---

# Phase 32: Code Review Report

**Reviewed:** 2026-07-22
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Adversarial review of the in-app secure self-update mechanism, focused on the
security-critical surfaces: Ed25519/minisign verification, the
verify-before-unpack gate, zip-slip protection, DB-backup-before-apply,
anti-downgrade logic, the public `/health` route, GitHub-notes XSS, and the
launcher swap/rollback + health version match.

**Trust chain assessment: the core security design is sound.** I traced the full
apply path and could NOT find a signature-bypass, downgrade, path-escape, or XSS
hole:

- `verify_minisign` correctly rejects on key-id mismatch, delegates the EC math
  to `cryptography`, and is fail-closed (`except Exception: return False`).
- `verify_release` verifies the signature BEFORE reading any manifest field,
  re-asserts the version shape + strict anti-downgrade, and only then downloads
  the archive and confirms its SHA-256 against the *signed* manifest — the
  verify-before-unpack ordering holds.
- `_extract_guarded` confines every zip member under `staged/` before extraction
  (belt-and-suspenders with `extractall`'s own sanitizer); absolute/`..` members
  resolve outside root and raise.
- `launcher.swap.parse_pending` / `_confine` reject `..`, absolute paths, and
  out-of-root escapes; `apply_update` does a matched-pair (code + DB) rollback.
- `health_ok(expected_version=...)` requires an exact version match, so a
  stale/wrong staged dir triggers rollback.
- The template renders all GitHub-sourced text autoescaped, never `|safe`, so no
  XSS from release notes/versions.
- CSRF is enforced on the update POST routes via the app-level `auth_guard`
  (base body `hx-headers` carries the token), and the routes are admin-gated via
  `require_role("administrator")`.

No BLOCKERs found. The findings below are robustness / authenticity / quality
issues that should be addressed but do not constitute an exploitable break of
the update trust model.

## Warnings

### WR-01: Release notes are displayed from the UNSIGNED GitHub release body

**File:** `app/services/update.py:169`, rendered at `app/templates/partials/update_panel.html:27`
**Issue:** `verified_manifest_version` returns `(version, release.get("body"))`.
The `version` is read from the signature-verified manifest (correct), but
`notes` comes straight from the mutable GitHub release `body` — it is NOT covered
by the Ed25519 signature. The docstring in `settings.py:91`
("release notes are echoed AUTOESCAPED via the cached status (T-32-01)") implies
the notes are handled as trusted; they are authentic only against XSS (Jinja
autoescape), not against tampering. Anyone able to edit the GitHub release text
(a compromised GitHub account / token, without the signing key) can present
arbitrary "Что нового" copy to the operator on the update-confirm screen — a
social-engineering surface (e.g. fake instructions urging the operator to act).
No code execution results, so this is not a BLOCKER, but the notes should be
treated as untrusted, not implied-verified.
**Fix:** Either source the displayed notes from a field inside the signed
`manifest.txt` (e.g. a `notes=`/`notes_url=` line), or keep using the release
body but label it explicitly as unverified in the UI and in the docstring so the
authenticity boundary is honest. At minimum, correct the `settings.py:91`
comment, which currently overstates the guarantee.

### WR-02: `apply()` can raise `ValueError` post-extraction and leave `staged/` behind

**File:** `app/services/update.py:413-415`
**Issue:**
```python
backup_path = backup.create_backup(engine, Path(settings.backup_dir))
backup_rel = backup_path.relative_to(root)   # raises ValueError if outside root
stage_pending(root, "staged", version, backup_rel)
```
`Path.relative_to(root)` raises `ValueError` when `settings.backup_dir` is not
under the derived `root`. With the default layout (`backup_dir = _DATA_DIR/backups`,
`root = _DATA_DIR.parent`) this is fine, but a `BACKUP_DIR` env override pointing
outside the install root makes `relative_to` throw. That happens AFTER
`_extract_guarded` already wrote `staged/`, so the exception (caught in
`settings_update_apply` as `except Exception → outcome="rollback"`) surfaces the
reassuring "Восстановлена предыдущая версия" message even though nothing was
installed or rolled back, and a fully-extracted `staged/` dir is left on disk
(it is cleaned only on the *next* apply). The user is told a rollback happened
when it did not.
**Fix:** Guard the `relative_to` conversion and fail the apply cleanly with a
distinct outcome before extraction, or compute `backup_rel` defensively:
```python
try:
    backup_rel = backup_path.relative_to(root).as_posix()
except ValueError:
    # backup_dir is outside install_root — cannot stage a confinable marker
    raise UpdateVerificationError("backup path is outside the install root")
```
and/or move `create_backup` + the `relative_to` check ahead of
`_extract_guarded` so a failure stages nothing.

### WR-03: Trust-gate scaffolding duplicated across `verified_manifest_version` and `verify_release`

**File:** `app/services/update.py:137-171` and `app/services/update.py:282-329`
**Issue:** Asset extraction, the V5 host allowlist loop, the manifest+sig
download, and the `verify_minisign` call are implemented twice in two separate
functions. This is security-critical code where the two copies must stay
byte-for-byte in agreement (same allowlist, same "verify before reading any
field" ordering). Divergence during future edits (e.g. adding a host to one
allowlist, or relaxing one ordering) would silently weaken one path. Duplicated
security invariants are a maintenance hazard.
**Fix:** Extract a single private helper (e.g. `_download_verified_manifest(release) -> dict | None`)
that performs the allowlist + download + `verify_minisign` + `_parse_manifest`
once, and have both `verified_manifest_version` and `verify_release` call it, so
the trust gate exists in exactly one place.

## Info

### IN-01: `assert` used to validate the public-key algorithm marker

**File:** `app/services/minisign_verify.py:36`
**Issue:** `assert raw[:2] == b"Ed"` validates the pubkey algorithm marker. Python
`assert` statements are stripped under `python -O`, so this check would silently
vanish in an optimized interpreter. Impact is low: the input is the trusted
vendored `app/minisign.pub`, the surrounding `verify_minisign` is fail-closed,
and a malformed key would still fail the downstream signature check — but using
`assert` for validation is an anti-pattern.
**Fix:** Replace with an explicit guard: `if raw[:2] != b"Ed": raise ValueError("unsupported pubkey algorithm")`.

### IN-02: SHA-256 comparison is case-sensitive with no normalization

**File:** `app/services/minisign_verify.py:74-75`
**Issue:** `return actual == expected_hex` compares `hexdigest()` (lowercase)
directly against the manifest's `sha256=` value. If the release-build ever emits
uppercase hex, a legitimate update is silently rejected (fail-closed, so no
security risk, but a fragile coupling to the build's exact casing).
**Fix:** Normalize both sides: `return actual == expected_hex.strip().lower()`.

### IN-03: `_archive_url` selects the first `*.zip` by dict order

**File:** `app/services/update.py:274-279`
**Issue:** The archive asset is chosen as the first asset whose name ends in
`.zip`. If a release ever carries more than one zip (e.g. an installer plus the
onedir bundle), selection is arbitrary. A wrong pick fails the SHA-256 gate
(fail-closed, no wrong-code execution), but the update would silently never
install.
**Fix:** Read the exact archive filename from the signed manifest (e.g. an
`archive=` field) and look that asset up by name, rather than pattern-matching.

### IN-04: Public `/health` discloses the app version unauthenticated

**File:** `app/routes/health.py:20-22`, `app/services/security.py:39`
**Issue:** `/health` is in `PUBLIC_PATHS` and returns `__version__` to any
anonymous caller. On the local SQLite client this is localhost-only and is the
launcher's intended probe. On the internet-facing PostgreSQL server (behind
Caddy), the same route is reachable and leaks the running version without auth —
minor information disclosure that aids version-specific attacks. The launcher
never polls the server, so the server does not need this route public.
**Fix:** Acceptable as-is for the localhost client; if tightening is desired,
dialect-gate or network-gate `/health` on the server, or return only
`{"status": "ok"}` for unauthenticated callers and the version only to the
loopback probe.

### IN-05: "Идёт обновление…" is shown even when no launcher is watching the marker

**File:** `app/routes/settings.py:96-98`, `app/templates/partials/update_panel.html:29`
**Issue:** A successful `update.apply()` writes `data/pending.json` and returns
`state="staged"`, and the panel then shows "Идёт обновление. Приложение
перезапустится автоматически". Nothing actually swaps unless the packaged
launcher (`python -m launcher`) is the parent process consuming the marker. In a
`run.bat`/dev launch (SQLite, no launcher) the marker is written but never
consumed, so the operator is told a restart is imminent that will not happen; a
stale marker persists.
**Fix:** Out of scope for the packaged target, but consider gating the update
section (or the apply action) on a launcher-managed environment signal, or
softening the copy to "запланировано; перезапустите приложение" so a
launcher-less run is not misleading.

---

_Reviewed: 2026-07-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
