---
phase: 03-goods-receipt-backup
reviewed: 2026-07-09T06:33:22Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - app/config.py
  - app/main.py
  - app/routes/backup.py
  - app/routes/receipts.py
  - app/services/backup.py
  - app/services/receipts.py
  - app/templates/base.html
  - app/templates/pages/backup.html
  - app/templates/pages/receipt_form.html
  - app/templates/partials/backup_list.html
  - app/templates/partials/name_input.html
  - app/templates/partials/receipt_form.html
  - app/templates/partials/receipt_lookup.html
  - app/templates/partials/receipt_price_inputs.html
  - app/templates/partials/receipt_rows.html
  - tests/conftest.py
  - tests/test_backup.py
  - tests/test_receipts.py
findings:
  critical: 0
  warning: 6
  info: 5
  total: 11
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-07-09T06:33:22Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Reviewed the Phase 3 slice: goods receipts (RCP-01/RCP-02) and VACUUM INTO backups (BCK-01) — services, routes, templates, and tests. The implementation is careful in the areas the plan called out: single-write-path staging with one commit, parameterized `VACUUM INTO` target (no path interpolation), no client-supplied filenames on any backup endpoint, active-only product lookup, autoescaped templates, and both server-side and swap-time guards against overwriting operator input. All 112 tests pass (`uv run pytest`). Cross-references verified: `parse_optional_cents`/`DUPLICATE_CODE_ERROR` exist in `catalog.py`, `record_operation(commit=False)` supports the staged-transaction contract, `tzdata` is a declared dependency (Windows `ZoneInfo` works), and `restore.bat` referenced by the backup page exists and deletes stale `-wal`/`-shm` sidecars.

No Critical issues found. Six Warnings concern edge-case correctness and failure-path behavior: a Unicode-digit quantity parsing gap, retention misconfiguration that silently deletes every backup (including the one just created), a misleading error when pruning (not creation) fails, an unhandled startup-backup failure that aborts app launch with a raw traceback, a template guard that renders Jinja2 `Undefined` into the `cents` filter for permanent ledger rows missing a payload key, and absent CSRF/origin protection on state-changing endpoints that write to an append-only (unfixable) ledger.

## Warnings

### WR-01: `qty` parsed with `isdigit()` — Unicode digit characters crash `int()` and surface the wrong error

**File:** `app/services/receipts.py:58`
**Issue:** `qty = int(qty_text) if qty_text.isdigit() else 0` — `str.isdigit()` is True for characters like superscripts (`"²"`) and circled digits (`"①"`), for which `int()` raises `ValueError`. The exception escapes `register_receipt`, is swallowed by the route's blanket `except Exception` (`app/routes/receipts.py:96`), and the operator sees the generic "Не удалось сохранить" form-level error instead of the specific quantity error `QTY_ERROR`. The correct predicate for `int()`-safe input is `str.isdecimal()`.
**Fix:**
```python
qty = int(qty_text) if qty_text.isdecimal() else 0
```

### WR-02: `prune_backups` with `keep <= 0` deletes ALL backups — including the one just created — while the UI reports success

**File:** `app/services/backup.py:54` (also `app/config.py:23`, `app/routes/backup.py:47`)
**Issue:** `doomed = files[:-keep] if keep > 0 else files` — if `BACKUP_KEEP=0` (or negative) is set via `.env`, every backup file is deleted, including the snapshot created a moment earlier by `create_backup`. `backup_now` then renders "Резервная копия создана: {name}" for a file that no longer exists, and `startup_backup` likewise destroys its own snapshot on every launch. A one-character typo in `.env` silently disables the entire backup safety net of a data-safety-focused app.
**Fix:** Reject or clamp non-positive retention. Either validate in config:
```python
backup_keep: int = Field(default=30, ge=1)
```
or guard in the service:
```python
if keep < 1:
    raise ValueError(f"backup_keep must be >= 1, got {keep}")
```

### WR-03: `backup_now` reports "backup failed" when only pruning failed — backup actually exists

**File:** `app/routes/backup.py:45-52`
**Issue:** `create_backup` and `prune_backups` share one `try` block. If the backup succeeds but `prune_backups` raises (`old.unlink()` at `app/services/backup.py:56` has no error handling — on Windows a `PermissionError` is raised whenever another process holds a handle on an old backup file, e.g. an open copy or antivirus scan), the operator sees "Не удалось создать резервную копию..." even though the new backup was written successfully. The success message (and the operator's confidence in the fresh snapshot) is lost.
**Fix:** Separate the two failure domains:
```python
try:
    path = backup_service.create_backup(engine, Path(settings.backup_dir))
    message = f"Резервная копия создана: {path.name}."
except Exception:
    error = BACKUP_ERROR
else:
    try:
        backup_service.prune_backups(Path(settings.backup_dir), keep=settings.backup_keep)
    except OSError:
        pass  # or log; the backup itself succeeded
```
Additionally consider `old.unlink(missing_ok=True)` inside `prune_backups` and skipping (not aborting) on per-file `PermissionError` so one locked file doesn't block retention of the rest.

### WR-04: Startup backup failure aborts app launch with a raw traceback and no operator-facing message

**File:** `app/main.py:19` (and `app/services/backup.py:103`)
**Issue:** `lifespan` calls `startup_backup()` with no error handling. `_db_has_data` deliberately absorbs `SQLAlchemyError` ("must not crash startup"), but `create_backup` failures — backups directory not writable, disk full, `VACUUM INTO` interrupted — propagate out of `lifespan`, so uvicorn fails to start and the operator (a non-programmer, per project context) sees only a Python traceback in the console and a browser that cannot connect. The stated D-09 intent is "block until the backup finishes," not "refuse to start the app"; the inconsistency with `_db_has_data`'s crash-proofing suggests this path was not considered.
**Fix:** Decide the policy explicitly. If the app should still start, catch and log loudly:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        backup_service.startup_backup()
    except Exception:
        logging.exception("Startup backup FAILED — data is not backed up!")
    yield
```
If failing closed is intended, document it in the docstring and emit a clear one-line message before re-raising.

### WR-05: `receipt_rows.html` guard passes Jinja2 `Undefined` into the `cents` filter — a receipt op whose payload lacks `catalog_cents` 500s the page forever

**File:** `app/templates/partials/receipt_rows.html:31`
**Issue:** `{% if r.op.payload and r.op.payload.catalog_cents is not none %}` — when `payload` is a dict that does not contain the key `catalog_cents`, the attribute lookup yields Jinja2 `Undefined`, and `Undefined is not none` evaluates **True**. The branch is then taken and `{{ r.op.payload.catalog_cents | cents }}` calls `format_cents(Undefined)`, whose `cents < 0` comparison raises `UndefinedError` → 500 on both `/receipts/new` and every receipt POST. The operations ledger is append-only and permanent: a single receipt op ever written without that payload key (another device in v2 sync, a manual fix-up script, a future schema change) makes the receipts page permanently unloadable. The guard on line 31 was clearly *intended* to protect against exactly this shape of data but does not.
**Fix:**
```jinja
<td class="num">{% if r.op.payload and r.op.payload.get("catalog_cents") is not none %}{{ r.op.payload.get("catalog_cents") | cents }}{% endif %}</td>
```

### WR-06: No CSRF/origin protection on state-changing endpoints that write to a permanent append-only ledger

**File:** `app/routes/receipts.py:65`, `app/routes/backup.py:37`
**Issue:** `POST /receipts` and `POST /backup` accept form-encoded requests with no origin validation. Form-encoded POSTs are CORS "simple requests" — any web page open in the operator's browser while the app runs can fire `fetch("http://localhost:8000/receipts", {method: "POST", mode: "no-cors", body: new URLSearchParams({code: "X", name: "X", qty: "9999"})})` and it will execute. Normally CSRF on a localhost app is low-stakes, but here forged operations land in the append-only ledger protected by DB triggers — they can never be deleted, permanently corrupting stock counts and audit history. The v1 "no auth" decision covers login machinery, not request-origin hygiene, and the machine is not guaranteed offline (the browser is a general-purpose one).
**Fix:** Add a cheap middleware that rejects cross-site state changes — no auth needed:
```python
@app.middleware("http")
async def block_cross_site_writes(request, call_next):
    if request.method == "POST" and request.headers.get("sec-fetch-site", "none") not in ("same-origin", "none"):
        return PlainTextResponse("Forbidden", status_code=403)
    return await call_next(request)
```
(Also ensure `run.bat` binds uvicorn to `127.0.0.1`, not `0.0.0.0`.)

## Info

### IN-01: Cross-module import of private name `_PRICE_FIELDS`

**File:** `app/services/receipts.py:23`
**Issue:** `from app.services.catalog import _PRICE_FIELDS, ...` imports an underscore-private constant across module boundaries; the leading underscore signals "internal to catalog.py," so this import contradicts the convention and will trip linters later.
**Fix:** Rename to `PRICE_FIELDS` in `catalog.py` (it is now shared API) and update both usage sites.

### IN-02: Backup page copy hardcodes "30 копий" while retention is configurable

**File:** `app/templates/pages/backup.html:4`
**Issue:** "Хранятся последние 30 копий." is static text, but the actual retention is `settings.backup_keep` (env-overridable). If the operator changes `BACKUP_KEEP`, the page lies. (Note: `tests/test_backup.py:199` also asserts the literal "30".)
**Fix:** Render from settings: `Хранятся последние {{ backup_keep }} копий.` with `backup_keep` passed in the route context.

### IN-03: `list_backups` can 500 if a file disappears between `glob` and `stat`

**File:** `app/services/backup.py:53, 61-68`
**Issue:** Both `prune_backups` and `list_backups` call `p.stat()` on globbed paths; if the operator deletes a backup file in Explorer while the page loads, `FileNotFoundError` propagates to a 500. Low probability for a single user, but trivially cheap to harden.
**Fix:** Skip vanished files: wrap the per-file `stat()` in `try/except OSError: continue`, and use `old.unlink(missing_ok=True)` in `prune_backups`.

### IN-04: No upper bound on quantity — 20-digit input takes the generic-error path via `OverflowError`

**File:** `app/services/receipts.py:58`
**Issue:** `int(qty_text)` accepts arbitrarily large values; a fat-fingered `99999999999999999999` either lands as an absurd `qty_delta` or, past int64, raises `OverflowError` at the SQLite bind — caught by the route's blanket handler and shown as the misleading "Не удалось сохранить" instead of a quantity error.
**Fix:** Cap it in validation, e.g. `if qty <= 0 or qty > 1_000_000: errors["quantity"] = QTY_ERROR`.

### IN-05: Any `IntegrityError` at commit is reported as "duplicate code"

**File:** `app/services/receipts.py:139-141`
**Issue:** The `except IntegrityError` around the final commit assumes `uq_products_code_active` fired, but the same exception type covers any constraint (e.g. `UNIQUE(device_id, seq)` on operations). A non-duplicate integrity failure would show the misleading "Код уже используется другим товаром" message. Low likelihood single-user; worth a comment or a check of the constraint name in the exception message before mapping to that copy.
**Fix:** Inspect `exc.orig` for the constraint/table name and fall back to the generic save error otherwise.

---

_Reviewed: 2026-07-09T06:33:22Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
