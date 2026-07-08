# Stack Research

**Domain:** Local-first warehouse inventory & sales app (single operator, browser UI at localhost, Windows, future PostgreSQL server sync)
**Researched:** 2026-07-08
**Confidence:** HIGH (all versions verified against PyPI / GitHub / unpkg registry metadata on 2026-07-08)

## Verdict on the User's Chosen Stack

**Python + FastAPI + SQLAlchemy + SQLite + HTMX (server-rendered) is validated.** This is the current mainstream "simple Python web app" stack for exactly this use case: one user, local machine, browser UI, no build toolchain, clean upgrade path to PostgreSQL. No changes recommended to the core choices — only specific versions, supporting libraries, and a few "do not use" guardrails below.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.13.x (3.12+ OK) | Language/runtime | Current stable line; every library below supports it. FastAPI requires >=3.10. Confidence: HIGH |
| FastAPI | 0.139.0 | Web framework, routing, validation | User's choice, validated: minimal boilerplate, first-class form/validation support via Pydantic v2, huge docs/community. Confidence: HIGH |
| Uvicorn | 0.51.0 | ASGI server (runs the app) | The standard server for FastAPI; works fine on Windows. Install with `uvicorn[standard]` extras. Confidence: HIGH |
| SQLAlchemy | 2.0.51 | ORM / database layer | User's choice, validated. Use the **2.0 declarative style** (`Mapped[]` / `mapped_column()`) — same models will run on PostgreSQL later with only a connection-string change. Confidence: HIGH |
| SQLite | bundled with Python (`sqlite3`) | Local database | Zero-install, single file (trivial backups = copy the file), perfect for 1 operator. Enable WAL mode + `foreign_keys=ON` via an SQLAlchemy connect event. Confidence: HIGH |
| Jinja2 | 3.1.6 | HTML templating | The standard for server-rendered FastAPI (`fastapi.templating.Jinja2Templates` wraps it). Confidence: HIGH |
| htmx | **2.0.10 (stable)** | Frontend interactivity (search, autocomplete, partial updates) | User's choice, validated. **Vendor the file locally** (`app/static/htmx.min.js`) — the app must work offline, so no CDN. Do NOT use the 4.0 beta (see below). Confidence: HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Alembic | 1.18.5 | Database migrations | From day one — schema WILL change. Configure `render_as_batch=True` in `env.py` (SQLite can't `ALTER` most things without batch mode). Confidence: HIGH |
| python-multipart | 0.0.32 | HTML form parsing | Required by FastAPI for any `Form(...)` endpoint — and an HTMX app is all forms. Confidence: HIGH |
| pydantic-settings | 2.14.2 | Config from `.env` (DB path, port) | Small, standard, keeps secrets/paths out of code. Confidence: HIGH |
| jinja2-fragments | 1.12.0 | Render a single Jinja2 `{% block %}` for HTMX partial responses | Optional but recommended once HTMX partials multiply — avoids one-file-per-fragment template sprawl. Its `Jinja2Blocks` is a drop-in replacement for FastAPI's `Jinja2Templates`. Confidence: HIGH (version), MEDIUM (necessity — can start without it) |
| pytest | 9.1.1 | Test runner | Standard; simplest test workflow for a beginner. Confidence: HIGH |
| httpx | 0.28.1 | Required by FastAPI's `TestClient` | Test dependency only; lets tests call endpoints without a running server. Confidence: HIGH |
| Pico.css (classless) | 2.x, vendored | Styling with zero build step | Optional: drop one CSS file into `/static`, semantic HTML looks decent immediately. No npm, no Tailwind build. Confidence: MEDIUM |

Note: Pydantic 2.13.4 is installed automatically as a FastAPI dependency — don't pin it separately.

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | 0.11.28 | Package/env manager: `uv init`, `uv add`, `uv run`. One tool replaces pip+venv; fast; the current community default. Works great on Windows. |
| Ruff | 0.15.20 | Linter + formatter in one (`ruff check`, `ruff format`). Replaces flake8+black+isort — one tool for a beginner. |
| A `run.bat` launcher | Local "packaging" for v1 | Two lines: `uv run uvicorn app.main:app --port 8000` + open browser. This IS the Windows deployment story for v1 (see What NOT to Use: PyInstaller). |

## Installation

```bash
# One-time: install uv (Windows PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Project setup
uv init myorishop --python 3.13
cd myorishop

# Core
uv add "fastapi==0.139.*" "uvicorn[standard]" sqlalchemy alembic jinja2 python-multipart pydantic-settings

# Optional (HTMX partials helper)
uv add jinja2-fragments

# Dev dependencies
uv add --dev pytest httpx ruff

# htmx: download once and commit to the repo (offline requirement)
# https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js  ->  app/static/htmx.min.js

# Run
uv run uvicorn app.main:app --reload
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| FastAPI | Django | If you wanted built-in admin UI + auth + ORM in one box. Rejected: much bigger learning surface for a beginner, and its ORM/migrations lock you into Django patterns. |
| FastAPI | Flask | Nearly as simple, but FastAPI gives free validation, better docs momentum, and typed patterns worth learning. No reason to switch. |
| SQLAlchemy 2.0 | SQLModel | SQLModel (same author as FastAPI) merges Pydantic + SQLAlchemy models. Tempting for beginners, but it lags SQLAlchemy releases, has thinner docs for non-trivial queries, and you'd still learn SQLAlchemy underneath. Plain SQLAlchemy 2.0 is the safer investment. |
| Sync SQLAlchemy `Session` | Async SQLAlchemy + aiosqlite | Only worth it at high concurrency with a network DB. Single user + local SQLite gains nothing and doubles concept load (async sessions, greenlets). Use regular `def` endpoints — FastAPI runs them in a threadpool automatically. |
| htmx | Alpine.js sprinkles | Add Alpine later only if you need pure client-side state (e.g., a complex multi-line sale form). Start without it. |
| uv | pip + venv | Fine if uv ever misbehaves; everything here works with plain pip too. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| React / Vue / any SPA | Node toolchain, build step, separate API layer, state management — triples the learning surface for zero benefit at this scale | HTMX + Jinja2 server-rendered |
| **htmx 4.0 (currently 4.0.0-beta5, 2026-06-26)** | Beta, with breaking changes vs 2.x; ecosystem/docs still on 2.x | htmx 2.0.10 stable; migrate to 4 later if ever needed |
| htmx from a CDN `<script src>` | App must work with no internet | Vendored `app/static/htmx.min.js` |
| aiosqlite / `async_sessionmaker` | Needless async complexity for a single-user SQLite app (see Alternatives) | Sync `Session` + `def` endpoints |
| PyInstaller / cx_Freeze for v1 | Freezing FastAPI+Uvicorn into an .exe is notoriously fiddly (hidden imports, uvloop/watchfiles hooks); a rabbit hole for a beginner | `run.bat` + uv; revisit real packaging in a later milestone if distribution is needed |
| Docker | Overhead with no payoff for one local Windows user | uv-managed venv |
| `FLOAT`/`REAL` columns for money | SQLite has no true DECIMAL; floats corrupt profit math | Store prices as `Integer` minor units (cents/kopecks) or `Numeric` rendered carefully; integers are simplest and port cleanly to PostgreSQL |
| SQLite-specific SQL (e.g., `INSERT OR REPLACE`, `strftime` in queries) | Breaks the future PostgreSQL migration | Portable SQLAlchemy Core/ORM constructs only |
| Tailwind CSS | Requires an npm build pipeline (standalone CLI exists but is still an extra moving part) | Pico.css classless or plain CSS |
| SQLAlchemy 1.x tutorials / `declarative_base()` legacy style | The web is full of outdated 1.x examples; mixing styles confuses beginners | 2.0 style: `DeclarativeBase`, `Mapped[]`, `mapped_column()`, `select()` |

## Stack Patterns by Variant

**For the future PostgreSQL sync milestone (design for it now, build later):**
- Keep every query portable (ORM only, no raw SQLite SQL) — then PostgreSQL is a connection-string change (`postgresql+psycopg://...`) plus the same Alembic history.
- Give business entities (products, operations, sales) a `uuid` column (stored as 36-char text in SQLite, `UUID` in PostgreSQL) alongside the integer PK — integer autoincrement IDs collide across devices during sync; UUIDs don't.
- The append-only operation/event log table (already a project decision) is the sync foundation — never UPDATE/DELETE its rows.
- Use timezone-aware UTC timestamps (`datetime.now(timezone.utc)`) everywhere; SQLite stores them as text, PostgreSQL as `timestamptz`.

**SQLite engine setup (do this on day one):**
- On every connection (SQLAlchemy `connect` event): `PRAGMA journal_mode=WAL;` and `PRAGMA foreign_keys=ON;` — WAL prevents reader/writer lockups, and SQLite does NOT enforce foreign keys by default.
- Backups = copy the `.db` file while app is closed, or `sqlite3 .backup` — worth a one-click "Backup" button early.

**If the app later needs auth (sync milestone):**
- Add session-cookie auth then (e.g., itsdangerous-signed cookies or fastapi-users). Do not add auth machinery in v1 — single local user.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| fastapi 0.139.0 | pydantic 2.13.4 | FastAPI >=0.100 is Pydantic-v2 only; never install Pydantic v1 |
| fastapi 0.139.0 | Python >=3.10 | 3.13 fully supported |
| alembic 1.18.5 | sqlalchemy 2.0.51 | Fully compatible; use `render_as_batch=True` for SQLite |
| pytest 9.1.1 | Python >=3.10 | TestClient needs `httpx` installed |
| htmx 2.0.10 | any backend | Pure static JS file; no server-side coupling |
| jinja2-fragments 1.12.0 | fastapi/starlette Jinja2Templates | Drop-in `Jinja2Blocks` subclass |

## Sources

- https://pypi.org/pypi/fastapi/json — version 0.139.0, requires-python >=3.10 (verified 2026-07-08, HIGH)
- https://pypi.org/pypi/sqlalchemy/json — 2.0.51 latest stable (HIGH)
- https://pypi.org/pypi/alembic/json — 1.18.5 (HIGH)
- https://pypi.org/pypi/uvicorn/json — 0.51.0 (HIGH)
- https://pypi.org/pypi/jinja2/json — 3.1.6 (HIGH)
- https://pypi.org/pypi/pydantic/json, /pydantic-settings/json — 2.13.4 / 2.14.2 (HIGH)
- https://pypi.org/pypi/python-multipart/json — 0.0.32 (HIGH)
- https://pypi.org/pypi/pytest/json, /httpx/json — 9.1.1 / 0.28.1 (HIGH)
- https://pypi.org/pypi/ruff/json, /uv/json — 0.15.20 / 0.11.28 (HIGH)
- https://unpkg.com/htmx.org/package.json — htmx stable line 2.0.10 (HIGH)
- https://api.github.com/repos/bigskysoftware/htmx/releases/latest — 4.0.0-beta5 published 2026-06-26, confirming 4.x is NOT stable (HIGH)
- https://pypi.org/pypi/jinja2-fragments/json — 1.12.0, FastAPI/Starlette support confirmed (HIGH)
- Ecosystem judgments (sync-vs-async for SQLite, PyInstaller pitfalls, WAL/foreign_keys pragmas, UUID-for-sync pattern) — practitioner consensus from official SQLAlchemy/FastAPI/SQLite docs knowledge (MEDIUM-HIGH)

---
*Stack research for: local-first FastAPI + HTMX + SQLite inventory app (MyOriShop)*
*Researched: 2026-07-08*
