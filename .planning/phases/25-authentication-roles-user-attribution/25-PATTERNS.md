# Phase 25: Authentication, Roles & User Attribution - Pattern Map

**Mapped:** 2026-07-18
**Files analyzed:** 26 new/modified files
**Analogs found:** 25 / 26 (one greenfield: the `contextvars`/auth-guard security module — no per-request-context precedent exists in this codebase)

> No `25-CONTEXT.md` exists. File list derived from `25-RESEARCH.md` (Recommended Project Structure, lines 143-163; Runtime State Inventory; Validation Architecture Wave-0 gaps) and `25-UI-SPEC.md` (Screens & Components; Template structure, lines 170-183). Every analog below was read in full or in the cited range — no invented paths.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/models.py` (add `User`; add `author_id` on Operation/CashMovement/Sale; add `ROLES`) | model | — | `app/models.py::Batch` + `WRITEOFF_REASONS`/`CASH_CATEGORIES` | exact (same file) |
| `alembic/versions/0017_users_and_author_id.py` | migration | batch | `alembic/versions/0008_batches.py` | exact |
| `app/services/auth.py` (Argon2id hash/verify/rehash) | service | transform | `app/services/finance.py` (RU-message service tier) | role-match |
| `app/services/users.py` (create/list/deactivate/reset) | service | CRUD | `app/services/warehouses.py` | exact |
| `app/services/security.py` (auth_guard, require_role, current_user, CSRF, contextvars) | middleware/guard | request-response | — (no analog) | none |
| `app/routes/auth.py` (login/logout/setup) | route | request-response | `app/routes/warehouses.py` (POST + 422/303) | role-match |
| `app/routes/users.py` (admin user CRUD) | route | CRUD | `app/routes/warehouses.py` | exact |
| `app/config.py` (+ secret_key, + device_id) | config | — | `app/config.py::Settings` | exact (same file) |
| `app/main.py` (SessionMiddleware, app-level dep, exc handler) | config/wiring | — | `app/main.py` | exact (same file) |
| `app/routes/__init__.py` (context processor) | config/wiring | — | `app/routes/__init__.py::templates` | exact (same file) |
| `app/services/ledger.py::record_operation` (stamp author_id) | service | CRUD | `app/services/ledger.py` (self) | exact (same file) |
| `app/services/finance.py::record_cash_movement` (stamp author_id) | service | CRUD | `app/services/finance.py` (self) | exact (same file) |
| `app/services/operations.py::history_view` (author join + filter) | service | CRUD-read | `history_view` customer/category filter (self) | exact (same file) |
| `app/services/reports.py::sales_profit_report` (author filter) | service | CRUD-read | `sales_profit_report` (self) | exact (same file) |
| `app/templates/auth_base.html` | template | — | `app/templates/base.html` | role-match (standalone chrome) |
| `app/templates/pages/login.html`, `pages/setup.html`, `pages/users.html` | template | — | `app/templates/pages/warehouse_form.html` | role-match |
| `app/templates/partials/login_form.html`, `user_rows.html`, `user_reset.html` | template | — | `partials/history_rows.html` / `warehouse_form.html` | role-match |
| `app/templates/base.html` + `mobile_base.html` (CSRF hx-headers, role menu, logout) | template | — | `app/templates/base.html::nav` | exact (same file) |
| `app/templates/partials/history_rows.html` (author `<select>`) | template | — | `history_rows.html` type/sort filter-bar | exact (same file) |
| `app/templates/pages/reports_sales.html` (author `<select>`) | template | — | `history_rows.html` filter select | role-match |
| `tests/conftest.py` (authenticated `client` fixture) | test | — | `tests/conftest.py::client` | exact (same file) |
| `tests/test_pragmas.py` (trigger-survival regression) | test | — | `tests/test_pragmas.py` + `app/db.py::APPEND_ONLY_TRIGGERS` | exact (same file) |
| `tests/test_auth.py`, `test_users.py`, `test_roles.py`, `test_attribution.py` | test | — | `tests/conftest.py` fixtures | role-match |

---

## Pattern Assignments

### `app/models.py` — `User` model + `author_id` columns (model)

**Analog:** `app/models.py::Operation` (lines 322-355) for column style; `Batch.is_legacy` (line 262) for the `Integer` soft-flag; `WRITEOFF_REASONS` (lines 50-57) / `CASH_CATEGORIES` (lines 70-82) for the RU-label allow-list dict.

**Column convention to mirror** (from `Operation`, lines 328, 351-354):
```python
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
device_id: Mapped[str] = mapped_column(String(36), nullable=False)
created_at: Mapped[str] = mapped_column(String(32), nullable=False)  # UTC ISO text
created_by: Mapped[str] = mapped_column(String(100), nullable=False)
```
- UUID `String(36)` PK with `default=new_id` (callable, no parens) — every table uses this; there is **no** integer PK despite CLAUDE.md's aspirational note.
- Timestamps are ISO text `String(32)` with `default=utcnow_iso` / `onupdate=utcnow_iso` — `new_id`/`utcnow_iso` live in `app/core.py` (lines 15, 20).
- Soft-disable = `Integer` flag defaulting to 1, mirroring `Batch.is_legacy: Mapped[int] = mapped_column(Integer, nullable=False, default=0)`.

**`author_id` on Operation/CashMovement/Sale** — mirror the existing bare nullable FK `batch_id` (lines 342-350):
```python
# ORM ForeignKey gives insert ordering + PostgreSQL portability; the DB column
# stays bare (migration adds it native — see 0008 precedent).
author_id: Mapped[str | None] = mapped_column(
    ForeignKey("users.id", name="fk_operations_author_id_users"), index=True
)
```

**`ROLES` allow-list** — mirror `WRITEOFF_REASONS` shape (latin key → RU label), place near other module-level constants:
```python
ROLES = {"administrator": "Администратор", "operator": "Оператор"}
```

---

### `alembic/versions/0017_users_and_author_id.py` (migration)

**Analog:** `alembic/versions/0008_batches.py` (read in full).

**Critical pattern — native `op.add_column`, NEVER `batch_alter_table`** (0008 lines 81-88):
```python
# NATIVE add-column (NO batch — preserves the operations_no_update /
# operations_no_delete triggers from migration 0001). BARE column, no
# DB-level FK (0004 sale_id precedent).
op.add_column(
    "operations",
    sa.Column("batch_id", sa.String(36), nullable=True),
)
```
Apply verbatim shape for `author_id` on `operations`, `cash_movements`, `sales`. Do the same for `create_table("users", ...)` using the 0008 `create_table` block (lines 54-78): explicit `sa.Column`s, `sa.PrimaryKeyConstraint("id", name=op.f("pk_users"))`, and `sa.UniqueConstraint("login", name=op.f("uq_users_login"))`.

**Immutability rule (0008 header, lines 29-31):** the migration file must **never import app modules** (only stdlib + sqlalchemy + alembic). Frozen literals only. `revision`/`down_revision` block at lines 39-43.

**`downgrade()`** — drop index then column, native (0008 lines 119-123).

---

### `app/services/users.py` (service, CRUD)

**Analog:** `app/services/warehouses.py::add_warehouse` / `update_warehouse` (lines 109-147).

**Validate → gate → single-commit, returning `(obj|None, errors)`** (warehouses lines 109-123):
```python
NAME_REQUIRED_ERROR = "Укажите название склада."  # RU, HTML-free, module-level

def add_warehouse(session, *, name, address) -> tuple[Warehouse | None, dict[str, str]]:
    name = name.strip()
    errors: dict[str, str] = {}
    if not name:
        errors["name"] = NAME_REQUIRED_ERROR
    if errors:
        return None, errors
    warehouse = Warehouse(id=new_id(), name=name, address=address or None)
    session.add(warehouse)
    session.commit()
    return warehouse, {}
```
Mirror for `create_user` (validate login/display_name/password/role against `ROLES`; duplicate-login → `errors["login"]`), `deactivate_user`/`reactivate_user` (set `is_active`), `reset_password` (write `password_hash` via `app/services/auth.py`), `list_users`. RU error strings from `25-UI-SPEC.md` Copywriting Contract (lines 138-142). `list_users` follows the `select()` read shape used across warehouses/operations services.

---

### `app/services/auth.py` (service, transform)

**Analog:** `app/services/finance.py` (module-level RU error constants, lines 24-27; validation-in-service discipline). The Argon2 mechanics come from `25-RESEARCH.md` Pattern 2 (lines 187-209), not the codebase (greenfield crypto).

**Mirror the fat-service convention:** all security logic here, never in a route. Store the full PHC string in `users.password_hash` (`String(255)`), no separate salt column. Use `argon2.PasswordHasher` + `check_needs_rehash` rehash-on-login. Compare tokens with `hmac.compare_digest` (RESEARCH "Don't Hand-Roll", lines 317-325).

---

### `app/services/security.py` (guard/middleware) — NO ANALOG

Greenfield: the codebase has **no per-request user context, no auth, no `contextvars`**. Build from `25-RESEARCH.md` Patterns 3 (app-level guard, lines 211-247), 6 (context processor, lines 266-282), 7 (`contextvars` attribution, lines 284-302). The only codebase anchor is the FastAPI DI idiom already used everywhere: `session: Session = Depends(get_session)` (see `app/db.py::get_session`, lines 70-73). **Pitfall 4 (contextvars → threadpool propagation) is unproven — gate behind the mandatory `tests/test_attribution.py` proof.**

---

### `app/routes/auth.py` + `app/routes/users.py` (routes)

**Analog:** `app/routes/warehouses.py` (read in full; lines 100-159) and the thin `app/routes/settings.py`.

**POST → service → 422-re-render-or-303-redirect** (warehouses lines 106-123):
```python
@router.post("/warehouses")
def warehouse_add(request, name: str = Form(""), address: str = Form(""),
                  session: Session = Depends(get_session)):
    _, errors = add_warehouse(session, name=name, address=address)
    if errors:
        context = {"warehouse": None, "errors": errors,
                   "form": {"name": name, "address": address}}
        return templates.TemplateResponse(request, "pages/warehouse_form.html",
                                          context, status_code=422)
    return RedirectResponse("/warehouses", status_code=303)
```
- `Form("")` params, thin route, all logic in the service.
- Error → 422 re-render preserving entered values; success → 303 (or, for HX per `25-UI-SPEC` Interaction Contract lines 189-195, **204 + `HX-Redirect`**).
- `templates` imported from `app.routes` (`from app.routes import templates`).
- HX dual-response branch (`request.headers.get("HX-Request")`) as in `warehouses_page` (lines 94-97).
- Admin-only routes get the `require_role("administrator")` dependency (from `app/services/security.py`); the `users.py` router registers under `/settings/users` per `25-UI-SPEC` A-UI-2.

**Router boilerplate** (settings.py lines 9-17): `router = APIRouter()`, `@router.get(...)`, one context dict, one `templates.TemplateResponse(request, "pages/...", context)`.

---

### `app/config.py` (config) — add `secret_key`, per-install `device_id`

**Analog:** `app/config.py::Settings` (read in full, lines 9-32).
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    device_id: str = "device-01"   # <-- must become per-install unique (A2)
    operator_name: str = "operator"  # <-- becomes fallback-only default
```
Add `secret_key: str` (no hardcoded default that leaks; load from `.env`). Persist a per-install `device_id` (RESEARCH A2 / Pitfall 6 — outside the synced DB). Keep the existing `env_file=".env"` pattern; do not print secrets (CLAUDE.md safety).

---

### `app/main.py` (wiring)

**Analog:** `app/main.py` (self, read in full).
- App is constructed at line 56: `app = FastAPI(title="MyOriShop", lifespan=lifespan)` — add `dependencies=[Depends(auth_guard)]` here (RESEARCH Pattern 3, line 215).
- `app.mount("/static", ...)` (line 57) is a MOUNT — app-level `dependencies=` do **not** apply, so `/static` stays public automatically.
- 33 `app.include_router(...)` calls (lines 58-89) — do NOT add per-router guards; the single app-level dependency is the ROLE-02 guarantee.
- Add `SessionMiddleware` and the `NotAuthenticated` exception handler (RESEARCH Pattern 1 lines 168-178, Pattern 3 lines 238-246).

---

### `app/routes/__init__.py` (context processor)

**Analog:** `app/routes/__init__.py` (self, read in full, lines 1-40).

The shared `templates = Jinja2Templates(directory="app/templates")` (line 15) is where filters and globals are registered (lines 22-39). Extend it with a `context_processors=[_auth_context]` (RESEARCH Pattern 6, lines 266-274) to inject `current_user` + `csrf_token` into every template — mirroring how `WRITEOFF_REASONS`/`CASH_CATEGORIES`/`CONTACT_KINDS` are exposed globally so no route re-passes them. Verify the `context_processors` kwarg against installed starlette 1.3.1 (RESEARCH A6).

---

### `app/services/ledger.py::record_operation` + `finance.py::record_cash_movement` (single write path — stamp author_id)

**Analog:** the two functions themselves (`ledger.py` lines 36-129; `finance.py` lines 46-84).

**Current audit-stamp (ledger.py lines 114-118):**
```python
device_id=settings.device_id,
seq=next_seq(session, settings.device_id),
created_at=utcnow_iso(),
created_by=settings.operator_name,
```
**Minimal edit** (RESEARCH Pattern 7, lines 297-301): replace the `settings.operator_name` read with a helper that prefers the request-scoped user, and add `author_id`:
```python
author_id, created_by = author_fields()  # from app.services.security
op = Operation(..., author_id=author_id, created_by=created_by,
               device_id=settings.device_id, ...)
```
`author_fields()` falls back to `(None, settings.operator_name)` when no user is in context — this keeps every existing test and the `past_sale`/fixtures green. Apply the identical two-line change to `record_cash_movement` (finance.py lines 76-79). Do NOT duplicate the write path; do NOT touch the ~7 service callers.

---

### `app/services/operations.py::history_view` (author display + filter)

**Analog:** `history_view` itself (lines 43-139), specifically its customer/category filter blocks.

**Add a LEFT OUTER JOIN on `User`** mirroring the existing outerjoins (lines 84-98):
```python
.outerjoin(Sale, Operation.sale_id == Sale.id)
.outerjoin(Customer, Sale.customer_id == Customer.id)
# NEW, same pattern:  .outerjoin(User, Operation.author_id == User.id)
```
Outer join (never inner) so pre-auth NULL-author rows are not dropped (RESEARCH Pitfall 2). Fall back to the frozen `created_by` text for NULL rows.

**Add an `author_id` filter** mirroring the `customer`/`category` kwarg blocks (lines 113-132):
```python
if type_filter and type_filter in OPERATION_TYPES:
    stmt = stmt.where(Operation.type == type_filter)
    count_stmt = count_stmt.where(Operation.type == type_filter)
# NEW:  if author_id: stmt/count_stmt .where(Operation.author_id == author_id)
```
Additive kwarg, combines with AND, applied to both `stmt` and `count_stmt`. NULL-author rows simply don't match — correct, they predate auth.

---

### `app/services/reports.py::sales_profit_report` (author filter)

**Analog:** `sales_profit_report` itself (lines 20-64).

Add an optional `author_id` kwarg applied as an extra `.where(Operation.author_id == author_id)` inside the existing `.where(Operation.type == "sale", created_at >= ..., created_at < ...)` block (lines 37-41) — mirrors how the period bounds are already applied. Tolerates NULL author (pre-auth rows excluded when a user is selected).

---

### Templates

**`auth_base.html`** — Analog: `app/templates/base.html` (read in full). It is a **standalone** chrome (like `mobile_base.html`): copy the `<head>` (lines 3-31) including the `htmx-config` meta **verbatim** (lines 18-19 — 4xx non-swap / 422-swap is load-bearing for login errors), load `/static/style.css` + `/static/htmx.min.js`, put `<body hx-headers='{"X-CSRF-Token": "{{ csrf_token }}"}'>`, but OMIT the `<nav>` block (lines 34-43). Center a `.stacked-form` (max-width 480px).

**`pages/login.html` / `setup.html` / `users.html`** — Analog: `app/templates/pages/warehouse_form.html` (read in full). Reuse the `.stacked-form` + `.field` + `<label>` + `<p class="error">` + `.form-actions` idiom (lines 11-30). login/setup `{% extends "auth_base.html" %}`; users `{% extends "base.html" %}`.

**`partials/user_rows.html` / `user_reset.html`** — Analog: `partials/history_rows.html` table + swap idiom. Deactivate control uses `button.danger` + native `hx-confirm` (per `25-UI-SPEC` line 193, mirroring `product_form.html`).

**`base.html` + `mobile_base.html` edits** — Analog: `base.html::nav` (lines 34-43). Add `hx-headers` CSRF on `<body>` (line 32); wrap admin nav items in `{% if current_user and current_user.role == "administrator" %}` (RESEARCH Pattern 6, lines 276-281); add the logout POST control right-aligned. The «Настройки» link already exists at line 42 — gate it.

**`history_rows.html` author `<select>`** — Analog: the type/sort selects in the same file (lines 24-46). Copy the exact HTMX wiring:
```html
hx-get="/history" hx-trigger="change"
hx-include="#history-rows input, #history-rows select"
hx-target="#history-rows" hx-swap="outerHTML" hx-push-url="true"
```
Populate options from `list_users()`; add «Все пользователи» (empty value) first. **Autoescape only — never `|safe`** on `display_name`/`login`/`created_by` (line 12 warning is authoritative).

---

## Shared Patterns

### Single write path (attribution)
**Source:** `app/services/ledger.py::record_operation` (lines 104-118), `app/services/finance.py::record_cash_movement` (lines 70-80).
**Apply to:** attribution only. These are the ONLY two insert sites; `author_id` is derived server-side (contextvars), never from a form field (repudiation mitigation, USER-05).

### Validate → gate → `(obj|None, errors)` service return
**Source:** `app/services/warehouses.py::add_warehouse` (lines 109-123), `app/services/finance.py::record_manual_movement` (lines 87-124).
**Apply to:** every write in `app/services/users.py` and `app/services/auth.py`. RU, HTML-free error strings as module-level constants (finance.py lines 24-27).

### Thin route → 422-re-render / 303-redirect
**Source:** `app/routes/warehouses.py` (lines 106-159).
**Apply to:** `app/routes/auth.py`, `app/routes/users.py`. `Form("")` params, HX dual-response branch, `templates` from `app.routes`.

### Append-only trigger preservation (migration)
**Source:** `alembic/versions/0008_batches.py` (lines 81-88), `app/db.py::APPEND_ONLY_TRIGGERS` (lines 22-43).
**Apply to:** migration 0017 — native `op.add_column`, never `batch_alter_table`, on `operations`/`cash_movements`. Regression-guard in `tests/test_pragmas.py` (assert the 4 triggers survive 0017).

### UUID-PK / ISO-timestamp / RU-label-dict model conventions
**Source:** `app/models.py` (`Operation` lines 328-354; `Batch.is_legacy` line 262; `WRITEOFF_REASONS` lines 50-57), helpers `app/core.py` (`new_id` line 15, `utcnow_iso` line 20).
**Apply to:** the `User` model and the `ROLES` dict.

### RU-label globals via shared `templates`
**Source:** `app/routes/__init__.py` (lines 30-39).
**Apply to:** `current_user` + `csrf_token` via `context_processors`; `ROLES` via `templates.env.globals` (same mechanism as `WRITEOFF_REASONS`).

### Test fixture: authenticated `TestClient`
**Source:** `tests/conftest.py::client` (lines 129-157) — `app.dependency_overrides[get_session]`, `monkeypatch.setattr(settings, "backup_on_startup", False)`, `with TestClient(app)`.
**Apply to:** the updated `client` fixture must additionally seed a user + log in (or `app.dependency_overrides[current_user]`), or all ~45 existing test files break under the app-level guard. `Base.metadata.create_all` + `APPEND_ONLY_TRIGGERS` in the `engine` fixture (lines 19-29) auto-picks up the new `User` model / `author_id` columns.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/services/security.py` | middleware/guard | request-response | No per-request user context, auth guard, `contextvars`, CSRF, or exception-redirect pattern exists anywhere in the codebase. Build from `25-RESEARCH.md` Patterns 3/6/7. Only anchor: the `Depends(get_session)` DI idiom (`app/db.py` lines 70-73). The `contextvars`→threadpool propagation (Pitfall 4) is the single riskiest mechanism — mandatory `tests/test_attribution.py` proof before relying on it; explicit-param threading is the documented fallback. |

---

## Metadata

**Analog search scope:** `app/models.py`, `app/config.py`, `app/main.py`, `app/db.py`, `app/routes/{__init__,warehouses,settings}.py`, `app/services/{ledger,finance,warehouses,operations,reports}.py`, `app/templates/{base,partials/history_rows,pages/warehouse_form}.html`, `alembic/versions/0008_batches.py`, `tests/{conftest,test_pragmas}.py`, `app/core.py` (grep).
**Files scanned:** 18 read in full/targeted + directory listings of routes/services/templates/tests/alembic.
**Pattern extraction date:** 2026-07-18
