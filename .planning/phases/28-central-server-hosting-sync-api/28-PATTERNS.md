# Phase 28: Central Server — Hosting & Sync API - Pattern Map

**Mapped:** 2026-07-19
**Files analyzed:** 14 new/modified
**Analogs found:** 11 / 14

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/routes/sync.py` | route | request-response (NDJSON) | `app/routes/users.py` (thin-route shape) + `app/main.py` router wiring | role-match |
| `app/services/devices.py` | service | CRUD + auth | `app/services/users.py` + `app/services/auth.py` | exact |
| `app/services/sync.py` | service | batch/transform | `app/services/merge.py` (pure, caller owns txn) | exact |
| `app/services/security.py` (EDIT) | middleware/guard | request-response | itself — `PUBLIC_PATHS` seam at `security.py:37,135-136` | exact (in-place) |
| `app/models.py` (EDIT: `DeviceToken`) | model | CRUD | `User` model, `app/models.py:506-529` | exact |
| `alembic/versions/0018_*.py` | migration | DDL, dialect-branched | `0001_initial_schema.py:110-116,144-156` + `0013_cash_movements.py:95-116` | exact |
| `alembic/versions/0019_device_tokens.py` | migration | DDL | `0017_users_and_author_id.py:41-54` | exact |
| `app/db.py` (EDIT: `APPEND_ONLY_TRIGGERS`) | config constant | — | itself, `app/db.py:22-43` | exact (in-place) |
| `app/routes/devices.py` + `templates/pages/devices.html` | route + template | CRUD | `app/routes/users.py` + `pages/users.html` / `partials/user_rows.html` | exact |
| `tests/test_devices.py` | test (unit) | — | `tests/test_auth.py` / service unit tests | role-match |
| `tests/test_sync_api.py` | test (integration) | — | `tests/conftest.py::anon_client` fixture | role-match |
| `tests/test_append_only_cursor.py` | test (unit) | — | `tests/test_pg_parity.py` trigger cases (SQLite variant) | partial |
| `tests/test_pg_parity.py` (EDIT) | test (integration) | — | itself, lines 144-192 | exact (in-place) |
| `app/services/rate_limit.py` | service (in-process state) | request-response | **none** | no analog |
| `deploy/{myorishop.service,Caddyfile,DEPLOY.md}` | config/docs | — | **none** | no analog |
| `app/main.py` (EDIT: `https_only`, sync router) | config | — | itself, lines 70-82, 114-138 | exact (in-place) |

## Pattern Assignments

### `app/services/security.py` — the `/api/sync/` bypass (highest-consequence edit)

**Analog:** itself. The seam already exists. Add a *separate* prefix constant next to `PUBLIC_PATHS` — do not widen `PUBLIC_PATHS` (it is exact-match by design, `security.py:37`).

Existing constant and guard (`app/services/security.py:37`, `:123-147`):

```python
PUBLIC_PATHS = {"/login", "/logout", "/setup"}

async def auth_guard(request: Request, session: Session = Depends(get_session)) -> None:
    issue_csrf(request)  # (1)
    if request.url.path in PUBLIC_PATHS:  # (2)
        return
    if count_users(session) == 0:  # (3) AUTH-04 first-run
        raise NotAuthenticated(redirect="/setup")
    user_id = request.session.get("user_id")  # (4)
    user = get_active_user(session, user_id) if user_id else None
    if user is None:
        request.session.pop("user_id", None)
        raise NotAuthenticated(redirect="/login")
    if request.method not in ("GET", "HEAD", "OPTIONS"):  # (5) AUTH-05
        await require_csrf(request)
    _current_user.set(user)  # (6)
    request.state.user = user
```

Insert the new branch immediately after step (2) — before the user-count, session and CSRF checks.

**Docstring convention to copy:** every constant/function in this module carries a requirement ID (`AUTH-05`, `ROLE-02`) and a threat ID (`T-25-03-02`). Do the same for the bypass (`SYNC-09`).

---

### `app/services/devices.py` (service, CRUD + auth)

**Analog A — service shape:** `app/services/users.py`. Copy verbatim:
- Module docstring stating the fat-service rule + the CLAUDE.md safety line (`users.py:1-12` ends with *"a raw password is hashed via `auth.hash_password` before store and is never echoed back or logged"* — write the token-plaintext equivalent).
- RU message constants at module top (`users.py:22-28`).
- Keyword-only params + `(obj | None, errors)` return + **ZERO writes on validation failure** (`users.py:57-96`).
- Soft-disable, never hard-delete (`deactivate_user`, `users.py:99-115`) — `is_active = 0` + stamp `revoked_at`.
- `select()`-based lookups only, `session.commit()` inside the service (`users.py:37,54,76`).

**Analog B — constant-time compare:** reuse `compare_token`, do not re-import `hmac` (`app/services/auth.py`):

```python
def compare_token(a: str, b: str) -> bool:
    """Timing-safe string equality (wraps hmac.compare_digest)."""
```

`app/services/auth.py:1-11` also documents *why* Argon2 is used for passwords — the plan's SHA-256-for-tokens divergence (RESEARCH A1) should be justified in the new module's docstring in the same voice.

**Analog C — the dependency-factory shape:** `require_role` (`security.py:150-167`) returns a closure raising `HTTPException(403, RU_MESSAGE)`. `require_device` follows the same shape but is a plain dependency raising `HTTPException(401, ..., headers={"WWW-Authenticate": "Bearer"})`.

---

### `app/models.py` — `DeviceToken` (model, CRUD)

**Analog:** `User`, `app/models.py:506-529`.

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    login: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # a ROLES key
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # Argon2id PHC
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)
```

Conventions to carry: `String(36)` UUID PK with `default=new_id`; `is_active` as `Integer` 1/0 (not Boolean) with a comment; ISO-text timestamps via `default=utcnow_iso`; a class docstring explaining the soft-disable choice.

For the `user_id` link, copy the **bare-column + ORM-only ForeignKey** convention (`app/models.py`, `Operation.author_id`):

```python
    author_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", name="fk_operations_author_id_users"), index=True
    )
```

---

### `alembic/versions/0019_device_tokens.py` (migration, DDL)

**Analog:** `0017_users_and_author_id.py:41-54` — the most recent `create_table` and the `users` precedent.

```python
def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("login", sa.String(50), nullable=False),
        ...
        sa.Column("is_active", sa.Integer(), nullable=False),  # 1 active / 0 disabled
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("login", name=op.f("uq_users_login")),
    )
```

Copy: `op.f()` naming for every constraint/index; explicit `nullable=`; the WR-06 docstring line *"this file must never import application modules — stdlib + sqlalchemy + alembic.op only"* (`0017:26-27`); a real `downgrade()` that drops indexes before columns/tables (`0017:80-90`).

---

### `alembic/versions/0018_sync_cursor_trigger_relaxation.py` (migration, dialect-branched DDL)

**Analog:** `0001_initial_schema.py:110-116` (upgrade branch) and `:144-156` (downgrade branch), mirrored in `0013_cash_movements.py:95-116`. Quote verbatim — this is the sanctioned dialect-branch exception.

Upgrade branch (`0001_initial_schema.py:110-116`):

```python
    # FND-01: append-only enforcement at the DATABASE level (frozen DDL copy).
    if op.get_bind().dialect.name == "postgresql":
        for stmt in _PG_OPERATIONS_DDL:
            op.execute(stmt)
    else:  # sqlite — output byte-for-behavior identical to today (WR-06)
        for stmt in _APPEND_ONLY_TRIGGERS:
            op.execute(stmt)
```

DROP grammar difference — the CR-01 fix, already frozen (`0013_cash_movements.py:106-114`):

```python
def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # PG grammar requires `DROP TRIGGER name ON table`; the SQLite-only
        # form (no ON clause) raises a syntax error on PG (CR-01).
        op.execute("DROP TRIGGER IF EXISTS cash_movements_no_update ON cash_movements")
        op.execute("DROP TRIGGER IF EXISTS cash_movements_no_delete ON cash_movements")
        op.execute("DROP FUNCTION IF EXISTS cash_movements_append_only()")
    else:
        op.execute("DROP TRIGGER IF EXISTS cash_movements_no_update")
        op.execute("DROP TRIGGER IF EXISTS cash_movements_no_delete")
```

Note for `0018`: the PL/pgSQL **functions** `operations_append_only()` / `cash_movements_append_only()` are reused — do **not** emit `DROP FUNCTION`. DDL lives in module-level `_PG_DDL` / `_SQLITE_DDL` tuples of literal constants (never f-stringed), matching both analogs.

---

### `app/db.py` — `APPEND_ONLY_TRIGGERS` (config constant, must move with 0018)

**Analog:** itself, `app/db.py:16-43`. The docstring already names this phase:

```python
# Live source of the append-only trigger DDL (FND-01) for TEST FIXTURES.
# Migration 0001 carries its own FROZEN copy (WR-06: migrations must never
# import mutable app code). v1 blocks ALL updates (synced_at unused); the
# v2 sync milestone relaxes the UPDATE trigger with a WHEN clause in a NEW
# migration — never edit this constant's DDL semantics in place without
# also adding that migration.
APPEND_ONLY_TRIGGERS: tuple[str, ...] = (
    """
    CREATE TRIGGER operations_no_update
    BEFORE UPDATE ON operations
    BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END
    """,
    ...
)
```

Only the two `*_no_update` entries gain the `WHEN` clause; the two `*_no_delete` entries stay byte-identical. Update the comment to point at `0018` instead of "a NEW migration".

---

### `app/routes/sync.py` (route, request-response)

**Analog A — thin-route contract:** `app/routes/users.py:1-30`.

```python
"""Admin user-management routes (USER-01..04): thin over app/services/users.py.

Registered in app/main.py behind `require_role("administrator")` (ROLE-03), so
these handlers never re-check the role — the include_router dependency is the
server-side boundary. Every validation / creation / reset rule stays in the fat
user service (V5); these routes only wire HTTP → service → template swap
...
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.users import (...)

router = APIRouter()
```

Copy: bare `APIRouter()` with **no `prefix=`** (literal full paths on each decorator — the same convention the `/m/` mobile tree uses); `session: Session = Depends(get_session)` as the last parameter; **plain `def`, never `async def`** (`users.py:45,53,77` — CLAUDE.md sync-session rule); RU message constants at module top (`users.py:33-36`).

**Analog B — the engine contract:** `app/services/merge.py`. `apply_merge` (`merge.py:464-467`) documents *"PURE w.r.t. HTTP/disk and — critically — NEVER commits: the caller wraps the whole call…"*. The route owns `with session.begin():`. Signatures to call, unchanged:

```python
FORMAT_VERSION: int = 1
def parse_exchange(lines: Iterable[str]) -> ExchangeBatch
def apply_merge(session: Session, batch: ExchangeBatch, *, server_now: str) -> MergeReport
def serialize_exchange(records, *, schema_version, source_device_id, generated_at) -> Iterator[str]
```

**Analog C — router registration:** `app/main.py:99-138`. The sync router is added to the same `include_router` list. Note the file's leading comment block (`main.py:65-69`) explaining *why* the guard is app-level — the new registration needs a sibling comment explaining why `/api/sync/*` is exempt from it but not unguarded.

```python
app.include_router(
    users.router, dependencies=[Depends(require_role("administrator"))]
)
```

The admin device-management router uses this exact form. The **sync** router takes no `dependencies=` — `require_device` is declared per-route.

---

### `app/services/sync.py` (service, batch/transform)

**Analog:** `app/services/merge.py` — pure functions, no HTTP, no file I/O, caller owns the transaction. Copy the module-docstring style that enumerates the governing decision IDs (`merge.py:1-24`, listing DD-4 / DD-6) and the "PURE" contract sentence. Portable ORM only (`select()`, `insert()` from `sqlalchemy`) — no `sqlalchemy.dialects` import anywhere.

---

### `app/routes/devices.py` + `templates/pages/devices.html` (route + template, CRUD)

**Analog:** `app/routes/users.py` end-to-end, plus `pages/users.html` / `partials/user_rows.html`.

HTMX page-vs-partial dispatch (`users.py:44-49`):

```python
@router.get("/settings/users")
def users_page(request: Request, session: Session = Depends(get_session)):
    context = _rows_context(session)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/user_rows.html", context)
    return templates.TemplateResponse(request, "pages/users.html", context)
```

Validation-failure re-render at **422** with a shared `_rows_context(session, errors=errors)` helper (`users.py:39-41, 64-71`). The one divergence: the minted token plaintext is rendered **once** into the response fragment and never re-fetchable — mirror the "password is never echoed back" comment (`users.py:117-119`) with its inverse rationale.

---

### `tests/test_sync_api.py` (test, integration)

**Analog:** `tests/conftest.py:190-217` — `anon_client`, the **only** fixture that leaves the real `auth_guard` active:

```python
@pytest.fixture()
def anon_client(engine, session, monkeypatch):
    """Unauthenticated TestClient with the REAL app-level guard active.
    ...
    """
    monkeypatch.setattr(settings, "backup_on_startup", False)

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
```

**This is the correct base for every token test.** The default `client` fixture (`conftest.py:132-187`) overrides `auth_guard` wholesale and would make the bypass untestable — RESEARCH's Wave-0 gap is confirmed against source. Two required negative tests both need `anon_client`: a session cookie must not reach `/api/sync/push`, and a Bearer token must not reach `/` or `/settings/users`.

Also copy: `monkeypatch.setattr(settings, "backup_on_startup", False)` — mandatory, or `TestClient(app)` runs the real lifespan and VACUUMs the developer's DB (`conftest.py:148-150`).

---

### `tests/test_append_only_cursor.py` (test, unit / SQLite)

**Analog:** `tests/test_pg_parity.py:144-158`, translated to the SQLite `engine`/`session` fixtures from `conftest.py:22-40` (which build the schema from `APPEND_ONLY_TRIGGERS`, not Alembic — `conftest.py:15,26-29`).

```python
def test_operations_update_rejected():
    """SRV-02: an UPDATE on operations is rejected by the append-only trigger."""
    ...
        with pytest.raises(Exception, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE operations SET qty_delta = 99 WHERE id = 'pg-op-upd'")
                )
```

The schema-derived guard test has a direct precedent in Phase 27's money-field guard — same `model.__mapper__.columns` technique.

---

### `tests/test_pg_parity.py` (EDIT — new PG relaxation cases)

**Analog:** itself. Copy the module contract verbatim (`test_pg_parity.py:33-37`, `:75-87`):

```python
pytestmark = pytest.mark.skipif(
    not settings.database_url.startswith("postgresql"),
    reason="PG parity — set DATABASE_URL to a postgresql+psycopg:// URL",
)

def _engine():
    return create_engine(settings.database_url)

def _upgrade_head():
    """Apply the whole migration chain to the PG target (env.py reads settings)."""
    command.upgrade(Config("alembic.ini"), "head")
```

Per-test shape: `_upgrade_head()` → `engine = _engine()` → `try: … finally: engine.dispose()`; literal-constant seeds naming every NOT NULL column with `ON CONFLICT DO NOTHING` (`:39-72`); assertions match the substring `append-only`, never an exception class (`:152`).

---

## Shared Patterns

### Guard/authorization
**Source:** `app/services/security.py:150-167` (`require_role`), `app/main.py:114-138` (registration)
**Apply to:** the admin device-management router (uses `require_role("administrator")`), and as the shape-analog for `require_device`.

```python
def require_role(role: str):
    def _role_guard(request: Request) -> None:
        user = getattr(request.state, "user", None)
        if user is None:
            raise HTTPException(status_code=403, detail=ACCESS_DENIED_ERROR)
        if user.role == "administrator":
            return  # admin passes every check (ROLE-04)
        if user.role != role:
            raise HTTPException(status_code=403, detail=ACCESS_DENIED_ERROR)
    return _role_guard
```

### Error handling / RU messages
**Source:** `app/services/users.py:21-28`
**Apply to:** `devices.py` (service + route)
Module-level RU constants, HTML-free, referencing the UI-SPEC Copywriting Contract line numbers. Services return `(obj | None, errors_dict)`; routes translate that into a 422 re-render. HTTP-layer failures use `HTTPException(status_code, detail="…")` with a Russian `detail` (`security.py:117`, `:161`).

### Session / dependency wiring
**Source:** `app/db.py:93-96`
**Apply to:** every new route and dependency.

```python
def get_session():
    """FastAPI dependency: yield a session, closed automatically."""
    with SessionLocal() as session:
        yield session
```

### Dialect gating outside migrations
**Source:** `app/db.py:46-76` (`build_engine_from_url`), `alembic/env.py:83-90`
**Apply to:** the `startup_backup` PG guard (OQ-6).

```python
    engine = create_engine(url)
    if engine.dialect.name != "sqlite":
        return engine
```

```python
        # render_as_batch is SQLite-only; derive it from the live dialect.
        render_as_batch = connection.dialect.name == "sqlite"
```

**OQ-6 resolved by reading `app/services/backup.py:89-105`:** `startup_backup()` will **not** crash on PostgreSQL, but only by accident — it returns early at `if not Path(settings.db_path).exists()`, and `settings.db_path` still points at the SQLite file, which is absent on the VPS. If a stray file ever exists there, `create_backup` would run `VACUUM INTO` against the **PostgreSQL** engine (`db.engine`, resolved lazily at line 98) and raise on boot. Add an explicit dialect guard in the same `if not settings.backup_on_startup` gate block rather than relying on the file-missing accident.

### Docstring / traceability convention
**Source:** every module read (`security.py:1-20`, `users.py:1-12`, `merge.py:1-24`, `0017:1-28`)
**Apply to:** all new files. Each module opens with a docstring naming the requirement IDs it realizes, the RESEARCH pattern it implements, the rejected alternative and why, and — for anything touching secrets — an explicit CLAUDE.md safety line. Migrations additionally restate the WR-06 no-app-imports rule.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/services/rate_limit.py` | service | request-response | No rate-limiting precedent exists anywhere in the repo — the app has never had an internet-exposed endpoint. Nothing in `app/services/` holds cross-request in-process state, so there is no analog for the module-level bucket dict or its `threading.Lock` either |
| `deploy/myorishop.service` | config | — | No systemd/OS-registration artifact exists in the repo; `run.bat` is the only launcher precedent |
| `deploy/Caddyfile` | config | — | No reverse-proxy config exists; the app has never been internet-facing |
| `deploy/DEPLOY.md` | docs | — | No deployment runbook exists |

For `app/services/rate_limit.py`, RESEARCH Open Question 4 fixes the shape: a ~40-line stdlib token bucket
keyed by the non-secret `token_prefix` (`time.monotonic()` refill, module-level dict, `threading.Lock`
because FastAPI runs `def` endpoints in a threadpool). No third-party limiter — `slowapi`/Redis are
explicitly rejected as disproportionate at 1-3 devices, and 256-bit tokens make this DoS protection rather
than brute-force protection. Planned in 28-03.

For the three `deploy/` files, the planner should use RESEARCH.md's Code Examples section (systemd unit + Caddyfile, lines 589-615) directly. The one repo-anchored constraint: `ExecStartPre` must mirror `run.bat`'s `uv run alembic upgrade head`, and the uvicorn bind must stay `127.0.0.1` exactly as `run.bat` does.

## Metadata

**Analog search scope:** `app/`, `app/routes/`, `app/services/`, `app/templates/`, `alembic/`, `alembic/versions/`, `tests/`
**Files scanned:** 14 read in full or targeted; ~120 enumerated by listing
**Pattern extraction date:** 2026-07-19
