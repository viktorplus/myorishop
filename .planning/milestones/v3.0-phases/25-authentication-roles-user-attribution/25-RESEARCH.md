# Phase 25: Authentication, Roles & User Attribution - Research

**Researched:** 2026-07-18
**Domain:** Web session auth, password hashing, RBAC, CSRF, per-user attribution retrofit onto a brownfield FastAPI + SQLAlchemy 2.0 + SQLite + HTMX app
**Confidence:** HIGH (codebase facts + library versions verified); MEDIUM on two design decisions flagged in the Assumptions Log (attribution-threading mechanism, device_id storage location)

> **Note:** No `25-CONTEXT.md` exists in the phase directory — this phase has not been through `/gsd-discuss-phase`. There are no locked user decisions to honor yet, so this research recommends approaches for the planner/discuss step to confirm. The MEDIUM-confidence design choices in the Assumptions Log should be surfaced to the user before they become locked plan decisions.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | Login required before any page (desktop + mobile) | Global router-level auth dependency + custom `NotAuthenticated` exception handler (Pattern 3) |
| AUTH-02 | Passwords stored only as Argon2id hashes | `argon2-cffi` `PasswordHasher` (Standard Stack); `password_hash` TEXT column |
| AUTH-03 | Session persists across refresh via signed cookie; logout ends it | Starlette `SessionMiddleware` (itsdangerous-signed); `request.session.clear()` on logout (Pattern 1) |
| AUTH-04 | First-run: guide initial-admin creation, no shipped default creds | Zero-users detection in the guard + `/setup` route (Pattern 4) |
| AUTH-05 | HTMX POST forms protected against CSRF | Synchronizer-token-in-session, injected via `hx-headers` on `<body>` + hidden field, validated centrally (Pattern 5) |
| USER-01 | User profile: display name, login, role | New `users` table (UUID PK, established convention) |
| USER-02 | Admin can create a user + assign role | Admin-gated user-management routes + service |
| USER-03 | Admin can deactivate (soft-disable); past ops stay attributed | `is_active` flag; guard rejects inactive on every request; ledger rows keep `author_id` |
| USER-04 | Admin can reset another user's password | Admin route re-hashes + writes `password_hash` |
| USER-05 | Every op + cash movement records author at the single `record_operation()` path | Add `author_id` param/context to `record_operation` + `record_cash_movement` (both are the sole write paths — verified) |
| USER-06 | History shows operating user + filter by user | `author_id` join to `users`; add user filter to `history_view` (mirrors existing customer/category filters) |
| ROLE-01 | Exactly two roles: administrator, operator | Python allow-list `ROLES` (mirrors `WRITEOFF_REASONS`/`CONTACT_KINDS` convention) + optional CHECK |
| ROLE-02 | Server-side guard on every route incl. export/backup; menu-hide never the boundary | Single app-level dependency covers all current + future routers (Pattern 3) |
| ROLE-03 | Operator can do receipts/sales/writeoffs/returns/corrections/cash; admin sections hidden + blocked | `require_role("administrator")` dependency on admin routers + template menu-hide |
| ROLE-04 | Admin has full access + every operator action | Role hierarchy: admin passes every operator guard |
| RPT-01 | Reports filterable by operator | Add `author_id` filter to `sales_profit_report` / reports routes (mirrors `_resolve_period` param pattern) |

**Pre-flight (roadmap-mandated, not a REQ ID):** per-install unique `device_id` replacing the static `"device-01"` default — see Runtime State Inventory + Assumptions Log A2.
</phase_requirements>

## Summary

The app is a mature brownfield FastAPI server-rendered (Jinja2 + vendored HTMX 2.0.10) inventory system with a rigorously enforced **single write path** discipline. Two functions — `app/services/ledger.py::record_operation` and `app/services/finance.py::record_cash_movement` — are the *only* code that inserts ledger rows, and both today stamp `created_by=settings.operator_name` and `device_id=settings.device_id` from a **global singleton** (`app/config.py::settings`). There is currently **no per-request user context and no auth of any kind** — every route is public, and every ledger row is attributed to the literal string `"operator"`. This phase adds the first security boundary.

The cleanest fit with this codebase's conventions is: (1) a `users` table following the established UUID-PK/ISO-timestamp pattern; (2) `argon2-cffi` for Argon2id hashing; (3) Starlette's built-in `SessionMiddleware` (itsdangerous-signed cookie) for offline-safe, refresh-surviving sessions; (4) **one app-level auth dependency** so a newly-added router cannot be left unprotected; (5) a synchronizer CSRF token stored in the session and injected globally via `<body hx-headers>`; and (6) attribution threaded into the two existing write paths by adding a nullable **bare** `author_id` column to `operations`/`cash_movements`/`sales` — using the exact "native `op.add_column`, no inline FK, never a batch table-rebuild" migration pattern that migration 0008 already documents (a batch rebuild would silently drop the append-only triggers).

**Primary recommendation:** Add a `users` table + `argon2-cffi` + Starlette `SessionMiddleware`; enforce login via a single app-level dependency with a redirect-on-unauthenticated exception handler; thread the logged-in user into the two existing single write paths via a request-scoped `contextvars` value read inside `record_operation`/`record_cash_movement` (falling back to `settings` defaults for tests/fixtures), writing a new nullable bare `author_id` column added by native `op.add_column` migrations that never rebuild the append-only tables.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Password verification / hashing | Service (`app/services/auth.py` new) | — | Security-critical logic belongs in the fat-service tier, never a route (V5/V6 precedent: all validation in services) |
| Session issue / read / clear | Middleware (`SessionMiddleware`) + guard dependency | Route (`/login`, `/logout`) | Cookie signing is transport; the guard reads it per-request |
| Login enforcement (every route) | App-level dependency (`app/main.py`) | Exception handler | One registration point covers all current + future routers — the "can't forget" guarantee (ROLE-02) |
| Role gating (admin-only sections) | Router-level dependency (`require_role`) | Template menu-hide | Server-side block is the boundary; hide is cosmetic (ROLE-03) |
| CSRF token issue + validate | Middleware/dependency + Jinja context processor | Template (hidden field / `hx-headers`) | Token lives in the signed session; validation is central |
| User CRUD / deactivate / reset | Service + admin routes | Migration (`users` table) | Mirrors every existing entity's service+route split |
| Author attribution | The two single write paths (`record_operation`, `record_cash_movement`) | `contextvars` set by the guard | USER-05 explicitly names the single write path; do not duplicate it |
| History/report author display + filter | Read services (`operations.history_view`, `reports.*`) | Templates | Read-only joins, mirroring existing customer/category filters |
| `device_id` generation | Startup / config load | Local file (not the DB) | Per-install identity must not travel with a copied `.db` backup (see Assumptions A2) |

## Standard Stack

### Core (new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| argon2-cffi | 25.1.0 | Argon2id password hashing (`from argon2 import PasswordHasher`) | The canonical Python Argon2 binding (Hynek Schlawack); implements Argon2id, includes `verify()` and `check_needs_rehash()` for the rehash-on-login pattern. `requires-python >=3.8`. `[VERIFIED: PyPI argon2-cffi/json]` |
| itsdangerous | 2.2.0 | Cryptographic signing behind Starlette `SessionMiddleware` | Pallets project; the signing dependency Starlette's `SessionMiddleware` imports. Not currently in the lock — must be added. `requires-python >=3.8`, released 2024-04-16. `[VERIFIED: PyPI itsdangerous/json]` |

### Supporting (already present — reuse, do not add)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Starlette (`SessionMiddleware`) | 1.3.1 (bundled via FastAPI) | Signed-cookie session; offline; survives refresh | `from starlette.middleware.sessions import SessionMiddleware`. Already installed (transitive). `[VERIFIED: uv.lock starlette 1.3.1]` `[CITED: Starlette docs — SessionMiddleware; verify exact API against installed 1.3.1]` |
| pydantic-settings | 2.14.* | `secret_key` + `device_id` config from `.env` | Add a `secret_key` field to `app/config.py::Settings` (never hardcode). `[VERIFIED: pyproject.toml]` |
| FastAPI DI (`Depends`) | 0.139.* | Auth guard, role guard, current-user injection | The idiomatic guard mechanism already used everywhere (`Depends(get_session)`). `[VERIFIED: codebase]` |
| Jinja2 context processor | 3.1.* (via Starlette `Jinja2Templates`) | Inject `current_user` + `csrf_token` into every template | Register on the shared `app/routes/__init__.py::templates` instance. `[CITED: Starlette Jinja2Templates context_processors]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Starlette `SessionMiddleware` | `itsdangerous` signed cookie set/read by hand | More code, must reimplement expiry/signing; SessionMiddleware already wraps itsdangerous correctly. Choose SessionMiddleware. |
| `argon2-cffi` | `passlib[argon2]` | `passlib` is effectively unmaintained (last release 2020) and still wraps argon2-cffi under the hood — adds a stale layer. Use argon2-cffi directly. `[ASSUMED — passlib maintenance status]` |
| Server-authoritative session (stateless: user_id in cookie) | Server-side session store (DB/Redis) | A store enables instant remote logout but adds infra; not needed — the guard re-loads the user and re-checks `is_active` on **every** request, so deactivation (USER-03) takes effect on the next request with no store. Choose stateless. |
| Synchronizer CSRF token | `starlette-csrf` middleware (double-submit) | Extra third-party dep; the session already exists, so a synchronizer token is simpler and needs no new package. Choose synchronizer. `[ASSUMED]` |
| `contextvars` attribution | Explicit `author`/`current_user` param threaded through every service | Explicit is more visible but touches ~7 service functions + all their route callers (receipts, sales, writeoffs, returns, corrections, transfers, manual cash). `contextvars` is a smaller diff but has a threadpool-propagation caveat (see Pitfall 4). Recommend contextvars; confirm with user (A1). |

**Installation:**
```bash
uv add "argon2-cffi==25.1.*" "itsdangerous==2.2.*"
```

## Package Legitimacy Audit

Ran `gsd-tools query package-legitimacy check --ecosystem pypi argon2-cffi itsdangerous`.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| argon2-cffi | PyPI | 25.1.0 published 2025-06-03; project since 2015 | seam: unknown (PyPI JSON exposes none) | github.com/hynek/argon2-cffi (seam reported none — PyPI `project_urls` gap) | SUS* | **Approved** — planner adds `checkpoint:human-verify` before install |
| itsdangerous | PyPI | 2.2.0 published 2024-04-16 | seam: unknown | github.com/pallets/itsdangerous (confirmed by seam) | SUS* | **Approved** — planner adds `checkpoint:human-verify` before install |

**\*Why SUS is a false-positive here:** both packages were flagged solely for `unknown-downloads` (the PyPI JSON API does not expose weekly download counts to the seam) and, for argon2-cffi, `no-repository` (its `project_urls` did not surface a repo URL to the seam). Both are foundational, decades-established libraries: `itsdangerous` is a Pallets/Flask-team project and is *already* an indirect dependency of the installed Starlette; `argon2-cffi` is the reference Python Argon2 binding. These are not slopsquat risks. Per protocol the SUS verdict is retained and the planner **must** still gate each install behind a `checkpoint:human-verify` task — but this note records that the signal is a data-availability artifact, not a real risk indicator.

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** argon2-cffi, itsdangerous (see note above — planner inserts `checkpoint:human-verify` before each `uv add`).

## Architecture Patterns

### System Architecture Diagram

```
                          Browser (desktop /… and mobile /m/…)
                                     │  request + Cookie: session=<signed>
                                     ▼
      ┌──────────────────────────────────────────────────────────────┐
      │  Starlette SessionMiddleware  (reads/writes signed cookie)     │
      └──────────────────────────────────────────────────────────────┘
                                     │  request.session = {user_id, csrf}
                                     ▼
      ┌──────────────────────────────────────────────────────────────┐
      │  App-level dependency: auth_guard(request, session)            │
      │   1. public path? (/login, /logout, /setup, /static) → allow   │
      │   2. zero users in DB?  → redirect /setup   (first-run AUTH-04) │
      │   3. no session user_id → NotAuthenticated → redirect /login    │
      │      (or 401 if HX-Request)                (AUTH-01/ROLE-02)     │
      │   4. load User; not is_active → clear session → /login (USER-03)│
      │   5. unsafe method? validate CSRF token   (AUTH-05)             │
      │   6. set contextvars(current_user); request.state.user = user   │
      └──────────────────────────────────────────────────────────────┘
                     │ allowed                       │ admin-only router
                     ▼                               ▼
      ┌───────────────────────────┐   require_role("administrator")
      │  Route (thin) → Service    │   (users mgmt, warehouses,
      │                            │    dictionaries, settings)  ROLE-03/04
      └───────────────────────────┘
                     │ state change (receipt/sale/writeoff/…/cash)
                     ▼
      ┌──────────────────────────────────────────────────────────────┐
      │  SINGLE WRITE PATH                                             │
      │   ledger.record_operation(...)   finance.record_cash_movement │
      │   reads contextvars → author_id + created_by (display name)    │
      │   INSERT append-only row (author_id NEW bare column)           │
      └──────────────────────────────────────────────────────────────┘
                     │ read
                     ▼
      History / Reports:  JOIN operations.author_id → users.display_name
                          + filter by author_id     (USER-06 / RPT-01)
```

### Recommended Project Structure (additive — follows existing layout)
```
app/
├── config.py            # + secret_key, + device_id generation/load
├── main.py              # + SessionMiddleware, + app-level auth dependency, + exception handler
├── models.py            # + User model; + author_id on Operation/CashMovement/Sale
├── routes/
│   ├── __init__.py      # + context processor (current_user, csrf_token) on `templates`
│   ├── auth.py          # NEW: GET/POST /login, POST /logout, GET/POST /setup
│   └── users.py         # NEW: admin-only user CRUD/deactivate/reset  (ROLE-04)
├── services/
│   ├── auth.py          # NEW: PasswordHasher wrapper, authenticate(), verify+rehash
│   ├── users.py         # NEW: create/list/deactivate/reset-password, ROLES allow-list
│   └── security.py      # NEW: auth_guard, require_role, current_user, CSRF, contextvars
├── ledger.py / finance.py  # record_operation/record_cash_movement read author from context
└── templates/
    ├── base.html            # + hx-headers CSRF on <body>, + user/logout in nav, + menu-hide
    ├── mobile_base.html     # same
    └── pages/login.html, pages/setup.html, pages/users.html   # NEW
alembic/versions/0017_users_and_author_id.py   # NEW (native add_column, NO batch rebuild)
```

### Pattern 1: Signed-cookie session (offline, survives refresh, logout)
**What:** Starlette `SessionMiddleware` stores a signed `dict` in the cookie; store only `user_id` (+ `csrf`). No server-side store.
**When to use:** Every request. Login writes `request.session["user_id"]`; logout calls `request.session.clear()`.
```python
# app/main.py  — Source: Starlette docs (SessionMiddleware); verify against starlette 1.3.1
from starlette.middleware.sessions import SessionMiddleware
from app.config import settings
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,   # from .env, never hardcoded
    https_only=False,                 # local http:// desktop; set True if ever served over TLS
    same_site="lax",
)
```
```python
# app/routes/auth.py (login success)
request.session["user_id"] = user.id
# logout:
request.session.clear()
```
Deactivation/invalidation: because the guard re-loads the user and checks `is_active` on every request, a deactivated user's still-valid cookie is rejected immediately (USER-03) — no session store needed.

### Pattern 2: Argon2id hashing with rehash-on-login
```python
# app/services/auth.py — Source: argon2-cffi docs
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_ph = PasswordHasher()  # library defaults are Argon2id and OWASP-reasonable

def hash_password(raw: str) -> str:
    return _ph.hash(raw)              # PHC-encoded string, store in users.password_hash TEXT

def verify_password(session, user, raw: str) -> bool:
    try:
        _ph.verify(user.password_hash, raw)
    except (VerifyMismatchError, InvalidHashError):
        return False
    # rehash-on-login: params may be upgraded later
    if _ph.check_needs_rehash(user.password_hash):
        user.password_hash = _ph.hash(raw)
        session.commit()
    return True
```
Store the full PHC encoded hash (includes algorithm, params, salt) in a portable `String(255)` TEXT column — no separate salt column. `[CITED: argon2-cffi PasswordHasher]`

### Pattern 3: One app-level guard covering EVERY router (AUTH-04 / ROLE-02)
**What:** Register the login guard once on the whole app so a router added in a future phase is protected by default (the "can't forget" guarantee). Exempt only an explicit public allowlist.
```python
# app/main.py
app = FastAPI(title="MyOriShop", lifespan=lifespan, dependencies=[Depends(auth_guard)])
# StaticFiles is a MOUNT, not a router — app-level `dependencies=` do NOT apply to it,
# so /static stays public automatically (CSS/JS/htmx load on the login page). [VERIFIED: codebase — app.mount]
```
```python
# app/services/security.py
PUBLIC_PATHS = {"/login", "/logout", "/setup"}   # login/logout/first-run only

def auth_guard(request: Request, session: Session = Depends(get_session)):
    if request.url.path in PUBLIC_PATHS:
        return
    if count_users(session) == 0:
        raise NotAuthenticated(redirect="/setup")     # AUTH-04 first-run
    user_id = request.session.get("user_id")
    user = get_active_user(session, user_id) if user_id else None
    if user is None:
        raise NotAuthenticated(redirect="/login")      # AUTH-01
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        require_csrf(request)                           # AUTH-05
    _current_user.set(user)                             # contextvars for attribution
    request.state.user = user                           # for templates
```
```python
# app/main.py — redirect for HTML, 401 for HTMX partials
@app.exception_handler(NotAuthenticated)
async def _redirect_login(request: Request, exc: NotAuthenticated):
    if request.headers.get("HX-Request"):
        # 401 so HTMX does NOT swap a full login page into a fragment; the
        # htmx-config in base.html already marks 4xx as non-swapping/error.
        return Response(status_code=401, headers={"HX-Redirect": exc.redirect})
    return RedirectResponse(exc.redirect, status_code=303)
```
> **Why app-level dependency over per-`include_router`:** `main.py` currently calls `app.include_router(...)` 33 times. Adding `dependencies=[Depends(auth_guard)]` to each is 33 chances to forget one (and future phases add sync + mobile-server routers). A single app-level dependency is the ROLE-02 "every route" guarantee. `[VERIFIED: codebase — app/main.py lists 33 include_router calls]`

### Pattern 4: First-run bootstrap (AUTH-04)
Guard step 2 detects zero users and redirects to `/setup`. `/setup` GET renders an initial-admin form; `/setup` POST creates the first user with role `administrator` **only if `count_users(session) == 0`** (re-checked server-side to close the race/hole), then logs them in. No credentials are ever shipped or seeded by a migration. `/setup` is in `PUBLIC_PATHS` but self-closes once any user exists (POST returns 403/redirect to `/login` when users already exist).

### Pattern 5: CSRF synchronizer token for HTMX (AUTH-05)
**What:** A random token stored in `request.session["csrf"]` (issued on first request), injected into every page, and required on every unsafe request.
```html
{# base.html and mobile_base.html — one line covers EVERY hx POST on the page #}
<body hx-headers='{"X-CSRF-Token": "{{ csrf_token }}"}'>
{# non-htmx <form> posts also carry a hidden field: #}
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
```
```python
# require_csrf: accept either the header (htmx) or the form field (plain form),
# compare with hmac.compare_digest to request.session["csrf"]; 403 on mismatch.
```
`csrf_token` reaches every template via a context processor on the shared `templates` instance (Pattern 6) — no route re-passes it. Offline-safe (no external calls), compatible with vendored HTMX 2.0.10. `[ASSUMED — synchronizer-token pattern; standard but confirm token issuance/rotation policy with user]`

### Pattern 6: Inject current_user + csrf_token into every template
```python
# app/routes/__init__.py (extend the existing shared `templates`)
def _auth_context(request: Request) -> dict:
    return {
        "current_user": getattr(request.state, "user", None),
        "csrf_token": request.session.get("csrf") if "session" in request.scope else "",
    }
templates = Jinja2Templates(directory="app/templates", context_processors=[_auth_context])
```
Menu-hide then reads `current_user.role` in `base.html`/`mobile_base.html`:
```html
{% if current_user and current_user.role == "administrator" %}
  <a href="/settings" ...>Настройки</a>
{% endif %}
```
`[CITED: Starlette Jinja2Templates context_processors]` — verify the kwarg name against installed starlette 1.3.1.

### Pattern 7: Attribution at the single write path (USER-05)
`record_operation` and `record_cash_movement` currently read `settings.operator_name`/`settings.device_id`. Replace those reads with a helper that prefers the request-scoped user:
```python
# app/services/security.py
import contextvars
_current_user: contextvars.ContextVar = contextvars.ContextVar("current_user", default=None)

def author_fields() -> tuple[str | None, str]:
    u = _current_user.get()
    if u is None:                      # tests, fixtures, background tasks
        return None, settings.operator_name   # fallback keeps existing tests green
    return u.id, u.display_name
```
```python
# ledger.record_operation / finance.record_cash_movement (minimal edit)
author_id, created_by = author_fields()
op = Operation(..., author_id=author_id, created_by=created_by, device_id=settings.device_id, ...)
```
This keeps the single write path single (no duplication), touches only the two write functions, and leaves every service caller untouched. **Caveat:** contextvar propagation into FastAPI's threadpool — see Pitfall 4 (requires a test). `[ASSUMED — recommend, confirm mechanism with user (A1)]`

### Pattern 8: History + Reports by user (USER-06 / RPT-01)
- **Schema:** add nullable bare `author_id String(36)` to `operations`, `cash_movements`, `sales`. Keep `created_by` as the display-name snapshot (append-only, never rewritten).
- **History display:** `mobile_partials/history_cards.html` already renders `{{ r.op.created_by }}` — extend `history_view`'s select to LEFT OUTER JOIN `User` on `Operation.author_id` and surface the live display name (fallback to `created_by` text for pre-auth NULL rows). Add the equivalent column to the desktop history template.
- **Filter:** add an optional `author_id` kwarg to `history_view` and `sales_profit_report`, applied as `.where(Operation.author_id == author_id)` — mirrors the existing `customer`/`category`/period filters exactly. Pre-auth NULL-author rows simply don't match a user filter (acceptable — they predate auth; see Pitfall 2). A "filter by user" `<select>` is populated from `list_users()`.

### Anti-Patterns to Avoid
- **Menu-hiding as the security boundary** — ROLE-02 forbids it; always pair a template `{% if %}` with a server-side `require_role` dependency.
- **Per-`include_router` guards** — one forgotten router = a hole. Use the app-level dependency.
- **Backfilling `author_id` on historical rows via UPDATE** — the `operations_no_update`/`cash_movements_no_update` triggers ABORT it, and it would be a lie (those ops predate users). Leave NULL; render `created_by` text.
- **Alembic batch/move-and-copy migration on `operations`/`cash_movements`** — drops the append-only triggers silently (documented in migration 0008). Use native `op.add_column`.
- **Storing the password with a separate salt column or truncating the hash** — store the full PHC string in one TEXT column.
- **Hardcoding `secret_key`** — load from `.env` via pydantic-settings; a per-install random default is acceptable only if persisted (else every restart logs everyone out).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom PBKDF2/salt loop | `argon2-cffi` `PasswordHasher` | Timing-safe verify, correct Argon2id params, `check_needs_rehash` |
| Cookie signing/session | Hand-rolled HMAC cookie | Starlette `SessionMiddleware` (itsdangerous) | Tamper-proof signing, expiry, tested |
| Secret management | Constant in code | pydantic-settings `.env` | Keeps the signing key out of git (CLAUDE.md safety rule) |
| Timing-safe token compare | `==` on tokens | `hmac.compare_digest` | Avoids timing side-channels |
| Constant-time password check | `if hash == ...` | `PasswordHasher.verify` | Raises on mismatch, constant-time internally |

**Key insight:** Auth/crypto is exactly the domain where hand-rolling introduces subtle, exploitable bugs. Every primitive here is a thin call into a maintained, standard library — the phase's job is wiring, not cryptography.

## Runtime State Inventory

> This is a brownfield retrofit — the following runtime state matters.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `operations.created_by`, `cash_movements.created_by`, `sales.created_by` are all the literal string `"operator"` (from `settings.operator_name`) across every existing row. `operations.device_id`/`cash_movements.device_id` are all `"device-01"`. | **No migration of old rows** (append-only triggers forbid UPDATE, and it would be a lie). Add nullable `author_id` (NULL for all historical rows). New rows get real `author_id` + `created_by` snapshot. History renders `created_by` text for NULL-author rows. |
| Live service config | None — single local SQLite client, no external services registered with this string yet (sync/server arrive in Phases 28-30). | None. |
| OS-registered state | `run.bat` launcher (Windows) — starts uvicorn; no user identity embedded. No Task Scheduler / pm2 entries reference user identity. | None. |
| Secrets / env vars | `.env` consumed by `app/config.py::Settings` (currently `db_path`, `operator_name`, `device_id`, `display_tz`, backup/report settings). **A new `secret_key` must be added** and kept out of git. `operator_name` becomes a fallback-only default. `device_id` static default `"device-01"` must become per-install unique. | Add `secret_key` (random, persisted). Generate/persist a unique `device_id` (see A2). Ensure `.env` is gitignored (verify). |
| Build artifacts | `data/myorishop.db` (dev DB, gitignored) + `backups/*.db`. A dev DB already has zero users → first run will route to `/setup`. | None — schema advances via the new Alembic migration; `Base.metadata.create_all` + `APPEND_ONLY_TRIGGERS` in `tests/conftest.py` picks up the new `User` model and columns automatically for tests. |

**The canonical question — after every file is updated, what runtime systems still have the old string?** Only the append-only ledger rows themselves (`created_by="operator"`, `device_id="device-01"`), which are intentionally frozen and never rewritten. Nothing else caches user/device identity.

## Common Pitfalls

### Pitfall 1: Alembic batch migration silently drops the append-only triggers
**What goes wrong:** Adding `author_id` to `operations`/`cash_movements` via an Alembic **batch** (move-and-copy) operation recreates the table, dropping `operations_no_update`/`operations_no_delete` (and the cash equivalents) — the append-only guarantee vanishes with no error.
**Why it happens:** `render_as_batch=True` is set globally in `alembic/env.py`; SQLite table-rebuild does `CREATE new / copy / DROP old / RENAME`, and triggers are not recreated.
**How to avoid:** Add the column with a **native `op.add_column("operations", sa.Column("author_id", sa.String(36), nullable=True))`** — no `batch_alter_table`, no inline FK — exactly the pattern migration 0008 used for `batch_id` and 0004 for `sale_id`. The ORM `ForeignKey` on the model gives insert ordering + PostgreSQL portability; the SQLite column stays bare.
**Warning signs:** A migration touching `operations` that uses `with op.batch_alter_table("operations")`. `[VERIFIED: codebase — 0008_batches.py docstring + native add_column precedent]`

### Pitfall 2: Historical rows have no author — filter and display must tolerate NULL
**What goes wrong:** After adding `author_id`, all pre-auth rows are NULL. A user filter that inner-joins `users` drops every historical row; a template that assumes a `User` object `AttributeError`s.
**How to avoid:** LEFT OUTER JOIN `users` on `author_id` (mirrors the existing outerjoin discipline in `history_view`), fall back to the `created_by` text column for display, and treat a user filter as "match rows with this author_id" (NULL rows simply excluded, which is correct — they predate auth). Decide and document that pre-auth History shows the frozen `"operator"` string. `[VERIFIED: codebase — history_view uses outerjoin for Batch/Warehouse/Sale/Customer]`

### Pitfall 3: HTMX does not swap 4xx by default — auth redirects can silently vanish
**What goes wrong:** An expired/absent session on an HTMX POST returns a redirect or 401; HTMX 2 does **not** swap 4xx responses (the app's `htmx-config` marks `[45]..` as non-swapping error), so the user sees nothing.
**Why it happens:** `base.html` sets `htmx-config` `responseHandling` so 4xx/5xx don't swap.
**How to avoid:** For HX requests return **401 with an `HX-Redirect` header** (HTMX performs a full-page navigation to the login page) rather than a 303 body. For non-HX requests return a normal 303 redirect. `[VERIFIED: codebase — base.html htmx-config meta]`

### Pitfall 4: contextvars may not propagate into FastAPI's sync-endpoint threadpool
**What goes wrong:** The app's endpoints are sync `def` (run in a threadpool). A `ContextVar` set in the async guard dependency might not be visible inside `record_operation` running in the worker thread → author falls back to the default and attribution is silently wrong.
**Why it happens:** ContextVars are copied to a thread only if the runner copies the context; AnyIO's `run_in_threadpool` does copy the current context, but this must be proven, not assumed.
**How to avoid:** Add a focused test: log in as a known user, POST a sale/receipt through the real `TestClient`, and assert the persisted `Operation.author_id` equals that user's id. If propagation fails, fall back to Pattern's explicit-parameter alternative (thread `current_user` from the route into the service call). `[ASSUMED — needs verification; this is the single riskiest mechanism in the phase]`

### Pitfall 5: `secret_key` regenerated on every start logs everyone out
**What goes wrong:** A random `secret_key` generated at process start invalidates all existing session cookies on restart.
**How to avoid:** Persist the key (in `.env` or a generated local file) so it is stable across restarts; only generate once. `[ASSUMED]`

### Pitfall 6: A copied `.db` backup carries `device_id` if stored in the DB
**What goes wrong:** If `device_id` lives in a DB row and the operator copies `myorishop.db` to a second machine (the sanctioned backup = copy-the-file model), both installs share a `device_id` → per-device `seq` collisions once sync exists (UNIQUE(device_id, seq) is the loud backstop).
**How to avoid:** Persist `device_id` **outside** the synced DB — a small local file generated once on first run (or a `.env` value). This keeps identity tied to the install, not the data. `[VERIFIED: codebase — UNIQUE(device_id, seq) on operations/cash_movements; backup = VACUUM INTO / copy .db]` (design choice flagged A2).

## Code Examples

### Users table model (follows the exact established convention)
```python
# app/models.py — mirrors Product/Customer UUID-PK + ISO-timestamp convention (VERIFIED against models.py)
ROLES = {"administrator": "Администратор", "operator": "Оператор"}  # allow-list + RU labels,
                                                                    # same shape as WRITEOFF_REASONS/CONTACT_KINDS

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    login: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)   # a ROLES key
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # soft-disable (mirrors is_legacy)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)
```
> The codebase uses a **single UUID `String(36)` PK per table** (no separate integer PK), despite CLAUDE.md's aspirational "uuid alongside integer PK" note — follow the *actual* code. `[VERIFIED: models.py — every model]`

### Migration skeleton (native add_column, triggers untouched)
```python
# alembic/versions/0017_users_and_author_id.py — Source pattern: 0008_batches.py
def upgrade() -> None:
    op.create_table("users",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("login", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("login", name=op.f("uq_users_login")),
    )
    # BARE nullable columns — native ALTER, NO batch rebuild (keeps append-only triggers)
    op.add_column("operations", sa.Column("author_id", sa.String(36), nullable=True))
    op.add_column("cash_movements", sa.Column("author_id", sa.String(36), nullable=True))
    op.add_column("sales", sa.Column("author_id", sa.String(36), nullable=True))
```

### Test pattern — override the current user (reuse existing `client` fixture)
```python
# tests/conftest.py already overrides get_session and disables startup backup.
# For auth tests, seed a user + set the session cookie via a real POST /login,
# OR override the guard's current-user for role tests:
def override_current_user():   # pin an admin/operator without a real login round-trip
    return admin_user
app.dependency_overrides[current_user] = override_current_user
```
`[VERIFIED: tests/conftest.py — client fixture uses app.dependency_overrides + TestClient(app)]`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| bcrypt / PBKDF2 | Argon2id (memory-hard) | OWASP guidance ~2021+ | Argon2id is the current default recommendation for new apps |
| `passlib` wrapper | `argon2-cffi` directly | passlib last release 2020 | Avoid an unmaintained abstraction layer `[ASSUMED]` |
| Server-side session stores | Signed stateless cookie (re-check user per request) | — | No infra; deactivation enforced by per-request `is_active` reload |

**Deprecated/outdated:**
- `passlib` for new projects — effectively unmaintained; use `argon2-cffi`. `[ASSUMED — verify maintenance status before locking]`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `contextvars` set in the async guard propagate into sync-endpoint threadpool workers, so `record_operation` reads the right author | Pattern 7 / Pitfall 4 | Attribution silently wrong (author = fallback). **Mitigation:** mandatory end-to-end test; fall back to explicit param threading. Surface to user: contextvars vs explicit-param. |
| A2 | `device_id` should be persisted in a **local file outside the DB**, generated once, not a DB row | Runtime State Inventory / Pitfall 6 | If stored in the synced DB, a copied `.db` shares device_id → seq collisions when sync lands (Phases 28-30). Decide before writing. |
| A3 | Synchronizer CSRF token (session-stored, one per session) is sufficient; no rotation-per-request needed | Pattern 5 | Over- or under-engineered CSRF. Confirm token lifetime/rotation policy with user. |
| A4 | `passlib` is unmaintained; use `argon2-cffi` directly | Alternatives / State of the Art | Minor — both wrap the same primitive; verify before locking. |
| A5 | Argon2 library-default parameters are acceptable for this single-operator trusted-machine context | Pattern 2 | Params could be too weak/strong. REQUIREMENTS explicitly excludes password policies/2FA — defaults are appropriate; confirm. |
| A6 | Starlette `SessionMiddleware` and `Jinja2Templates(context_processors=...)` APIs are unchanged in the installed starlette 1.3.1 | Patterns 1 & 6 | API drift in a 1.x line. Verify against the installed version at plan/execute time. |
| A7 | Login is case-sensitive ASCII; no `login_lc` Cyrillic shadow needed (unlike `name_lc`) | Users table | If operators use Cyrillic/mixed-case logins, add a `login_lc` shadow (established pattern). Confirm. |

## Open Questions (RESOLVED)

> No `25-CONTEXT.md` / discuss-phase ran. Per autonomous planning (2026-07-18), the three
> open questions were LOCKED to the recommended options and made explicit in the plans.
> Resolutions recorded here so the research record matches what the plans committed to.

1. **Attribution mechanism: contextvars vs explicit parameter?** — **RESOLVED → contextvars.**
   - What we know: both work; contextvars is a ~2-function diff, explicit threading touches ~7 services + callers.
   - What's unclear: threadpool propagation of contextvars in this exact stack (A1).
   - **Decision:** implement contextvars, set by the auth guard, read inside the two write paths with a `settings.operator_name` fallback (keeps ~45 legacy tests green). Gated behind a mandatory threadpool-propagation proving test (Plan 25-07 Task 2); explicit-param threading documented as the fallback if the proof fails.

2. **`device_id` storage: local file vs `.env` vs DB row?** — **RESOLVED → local file, not in the DB.**
   - What we know: it must be per-install unique and must not travel with a copied `.db`.
   - **Decision:** generate a per-install UUID once into a local file (under the app data dir, e.g. `data/`), loaded by `app/config.py` — deliberately NOT a DB row, so a copied/restored `.db` backup does not clone the device identity (Plan 25-01).

3. **Where do warehouses/dictionaries/settings sit on the operator/admin line?** — **RESOLVED → enumerated admin router set.**
   - ROLE-03/04 name "user management, warehouses, dictionaries, settings" as admin-only.
   - **Decision:** admin-only routers = warehouses / dictionaries / settings / users, each guarded server-side with `require_role("administrator")`; operator routers (receipts, sales, write-offs/returns/corrections, cash movements, and operator-needed sub-actions like picking a warehouse during a receipt) explicitly excluded from the admin gate (Plan 25-05 Task 1).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | runtime | ✓ | 3.13 (pyproject `requires-python >=3.13`) | — |
| SQLAlchemy | ORM | ✓ | 2.0.* | — |
| FastAPI / Starlette | web + SessionMiddleware | ✓ | 0.139.* / 1.3.1 | — |
| Jinja2 | templates + context processor | ✓ | 3.1.* | — |
| pytest + httpx (TestClient) | tests | ✓ | 9.1.* / 0.28.* | — |
| argon2-cffi | Argon2id hashing | ✗ (must add) | 25.1.* target | none — required, `uv add` |
| itsdangerous | SessionMiddleware signing | ✗ (not in lock) | 2.2.* target | none — required, `uv add` |

**Missing dependencies with no fallback:** `argon2-cffi`, `itsdangerous` — both must be installed (`uv add`); both are hard requirements for AUTH-02/AUTH-03. Gate each behind a `checkpoint:human-verify` per the SUS audit note.

## Validation Architecture

> `workflow.nyquist_validation` is `true` in config — this section is included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* (+ httpx 0.28.* for `fastapi.testclient.TestClient`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `uv run pytest tests/test_auth.py -x` (new file) |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01/ROLE-02 | Unauthenticated GET of a protected route redirects to /login (303) or 401+HX-Redirect for HX | integration | `uv run pytest tests/test_auth.py -k guard_redirects` | ❌ Wave 0 |
| AUTH-01 | export/backup endpoints require login | integration | `... -k gated_export_backup` | ❌ Wave 0 |
| AUTH-02 | Password stored only as Argon2id PHC hash; verify + reject wrong | unit | `... -k password_hash` | ❌ Wave 0 |
| AUTH-03 | Login sets session; survives a second request; logout clears it | integration | `... -k session_persist_logout` | ❌ Wave 0 |
| AUTH-04 | Zero users → /setup; POST creates admin; /setup self-closes once a user exists | integration | `... -k first_run_setup` | ❌ Wave 0 |
| AUTH-05 | POST without CSRF token → 403; with token → OK | integration | `... -k csrf` | ❌ Wave 0 |
| USER-01/02/04 | Admin creates user, assigns role, resets password | integration | `... -k user_admin` | ❌ Wave 0 |
| USER-03 | Deactivated user cannot log in; existing session rejected next request; past ops keep author | integration | `... -k deactivate` | ❌ Wave 0 |
| USER-05 | Sale/receipt/cash op through TestClient persists `author_id` == logged-in user (contextvars proof — Pitfall 4) | integration | `... -k attribution` | ❌ Wave 0 |
| USER-06/RPT-01 | History + report show author and filter by author_id; NULL-author rows tolerated | integration | `... -k filter_by_user` | ❌ Wave 0 |
| ROLE-01 | Exactly two roles; unknown role rejected by service | unit | `... -k roles_allowlist` | ❌ Wave 0 |
| ROLE-03 | Operator blocked (403) from admin routers server-side; menu item hidden | integration | `... -k operator_blocked` | ❌ Wave 0 |
| ROLE-04 | Admin reaches every admin + operator action | integration | `... -k admin_full_access` | ❌ Wave 0 |
| (pre-flight) | Append-only triggers still present after the 0017 migration (regression) | integration | `uv run pytest tests/test_pragmas.py` | ✅ exists — extend |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_auth.py -x`
- **Per wave merge:** `uv run pytest` (full suite — the ~45 existing test files must stay green after the attribution retrofit and the app-level guard, which will require an authenticated `client` fixture)
- **Phase gate:** Full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_auth.py` — login/guard/csrf/first-run/session (AUTH-01..05)
- [ ] `tests/test_users.py` — user CRUD/deactivate/reset + roles allow-list (USER-01..04, ROLE-01)
- [ ] `tests/test_roles.py` — operator-blocked / admin-full server-side (ROLE-03/04)
- [ ] `tests/test_attribution.py` — author_id stamped at both write paths; history/report filter (USER-05/06, RPT-01)
- [ ] **Update `tests/conftest.py`** — the existing `client` fixture must now log in (or override `current_user`), or **every one of the ~45 existing test files breaks** once the app-level guard lands. This is the single highest-effort Wave-0 item.
- [ ] Extend `tests/test_pragmas.py` — assert append-only triggers survive migration 0017 (Pitfall 1 regression guard).

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: high`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Argon2id via `argon2-cffi`; no shipped default creds (AUTH-04); admin-only account creation (no self-registration — out of scope) |
| V3 Session Management | yes | Starlette `SessionMiddleware` signed cookie; `same_site=lax`; logout clears session; per-request `is_active` re-check invalidates deactivated users |
| V4 Access Control | yes | App-level auth dependency (deny-by-default, every route); `require_role` server-side on admin routers; menu-hide is cosmetic only (ROLE-02) |
| V5 Input Validation | yes | Existing service-tier validation discipline; role/login validated against `ROLES` allow-list; all RU error messages HTML-free (existing convention) |
| V6 Cryptography | yes | No hand-rolled crypto — `argon2-cffi` + itsdangerous; `secret_key` from `.env`, never hardcoded; `hmac.compare_digest` for token/CSRF comparison |

### Known Threat Patterns for FastAPI + HTMX + SQLite

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential theft from DB dump | Information Disclosure | Argon2id hashes only, never plaintext/reversible (AUTH-02) |
| Session forgery / tampering | Spoofing / Tampering | itsdangerous-signed cookie; `secret_key` secret + persisted |
| CSRF on state-changing HTMX POST | Tampering | Synchronizer token in session, `hx-headers` + hidden field, `compare_digest` (AUTH-05) |
| Missing guard on a new/forgotten router | Elevation of Privilege | Single app-level dependency (deny-by-default) covers future routers (ROLE-02) |
| Menu-hide mistaken for access control | Elevation of Privilege | Server-side `require_role` is the boundary; hide is cosmetic (ROLE-03) |
| Deactivated user retains access via valid cookie | Elevation of Privilege | Guard reloads user + checks `is_active` every request (USER-03) |
| First-run default-credential backdoor | Spoofing | No creds shipped; `/setup` self-closes after first admin (AUTH-04) |
| Attribution spoofing (client claims another author) | Repudiation | `author_id` derived server-side from the session, never from a form field (USER-05) |
| Open redirect on login `?next=` | Tampering | If a post-login redirect target is added, allow only same-origin relative paths |

## Sources

### Primary (HIGH confidence)
- Codebase (VERIFIED via Read/Grep): `app/main.py` (33 `include_router`, `app.mount` static), `app/services/ledger.py::record_operation`, `app/services/finance.py::record_cash_movement`, `app/models.py` (UUID-PK convention, `Operation`/`CashMovement`/`Sale` with `created_by`/`device_id`), `app/config.py` (`settings`, `device_id="device-01"`), `app/db.py` (`APPEND_ONLY_TRIGGERS`, PRAGMAs), `app/routes/__init__.py` (shared `templates`), `app/routes/{home,settings,export,backup,corrections,reports}.py`, `app/services/operations.py::history_view`, `alembic/env.py` (`render_as_batch=True`), `alembic/versions/0008_batches.py` (native-add-column + trigger-drop warning), `0013_cash_movements.py` (frozen trigger DDL), `tests/conftest.py` (`client`/`session`/`engine` fixtures, `dependency_overrides`), `app/templates/{base,mobile_base}.html` (nav, `htmx-config`), `pyproject.toml`, `uv.lock` (starlette 1.3.1, itsdangerous absent).
- PyPI JSON (VERIFIED): `argon2-cffi` 25.1.0 (requires-python >=3.8); `itsdangerous` 2.2.0 (2024-04-16, requires-python >=3.8).

### Secondary (MEDIUM confidence)
- Starlette docs — `SessionMiddleware`, `Jinja2Templates(context_processors=...)` (CITED; verify exact API against installed starlette 1.3.1, A6).
- argon2-cffi docs — `PasswordHasher.hash/verify/check_needs_rehash` (CITED).

### Tertiary (LOW confidence)
- `passlib` unmaintained status; synchronizer-token CSRF sufficiency; Argon2 default-parameter adequacy; contextvars threadpool propagation (all ASSUMED — see Assumptions Log).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified on PyPI; libraries are canonical.
- Architecture / codebase integration: HIGH — every "modify X" grounded in a file actually read (single write paths, migration pattern, guard placement, templates).
- Attribution mechanism (contextvars): MEDIUM — recommended but needs the threadpool-propagation proof (A1/Pitfall 4).
- device_id storage: MEDIUM — design decision flagged for user confirmation (A2).
- Pitfalls: HIGH — the top pitfall (batch migration drops triggers) is documented in the codebase's own migration 0008.

**Research date:** 2026-07-18
**Valid until:** 2026-08-17 (stable stack; re-verify starlette 1.3.1 API and library versions if planning slips)
