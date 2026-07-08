# Walking Skeleton — MyOriShop

**Phase:** 1
**Generated:** 2026-07-08

## Capability Proven End-to-End

The operator launches the app with run.bat, opens http://127.0.0.1:8000 offline, and records a stock correction for the seeded demo product through an HTMX form — the change lands as an immutable, audited row in the append-only operations ledger, and both the cached and ledger-recomputed stock update on screen without a page reload.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | FastAPI 0.139 + Jinja2 server-rendered pages + HTMX 2.0.10 (vendored) | Locked user decision (D-15/D-03); zero build step, fully offline, beginner-maintainable |
| Runtime / packaging | Python 3.13 via uv (fallback 3.12.13), deps in pyproject.toml; no Docker/PyInstaller | Locked (D-01/D-04); uv is the single env tool; run.bat is the v1 deployment story |
| Data layer | SQLite (WAL, foreign_keys=ON, busy_timeout via per-connection listener) + sync SQLAlchemy 2.0 Session, plain `def` endpoints | Locked (D-12/D-14); single local writer; portable to PostgreSQL later (ORM-only SQL) |
| Schema conventions | UUID4 TEXT PKs everywhere; money as Integer `*_cents`; timestamps UTC ISO-8601 TEXT; soft deletes (`deleted_at`) | Locked (D-05/D-06/D-07/D-10); sync-ready — no autoincrement collisions, lexicographic time ordering |
| Source of truth for stock | Append-only `operations` ledger (BEFORE UPDATE/DELETE triggers RAISE(ABORT)); `products.quantity` is a recomputable cached projection | Locked (D-08/D-09); FND-01 — every later phase writes ONLY via `app.services.ledger.record_operation` |
| Migrations | Alembic from day one, `render_as_batch=True`, naming convention on MetaData; migration 0001 is the schema source of truth (no create_all outside test fixtures) | Locked (D-13); SQLite ALTER limits; batch migrations of `operations` must recreate the triggers |
| Auth / identity | None in v1; single operator name + fixed device_id from pydantic-settings, stamped as `created_by` on every operation | Locked (D-17); FND-03 audit trail without auth machinery |
| Deployment target | Local Windows: run.bat → `uv run alembic upgrade head` → `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000` (single worker) + browser open | Locked (D-02); loopback-only, offline after first dependency install |
| Directory layout | Thin routes / fat services: `app/routes/`, `app/services/`, `app/models.py` (single file), `app/templates/{pages,partials}/`, `app/static/`, `tests/`, `alembic/` | Locked (D-11); routes parse forms + render; all business writes in services |
| UI language | Operator-facing text Russian; code/comments/commits English | User's global convention |

## Stack Touched in Phase 1

- [x] Project scaffold (uv project, pyproject.toml, ruff, pytest) — Plan 01-01
- [x] Routing — `GET /` page + `POST /ops` HTMX partial — Plan 01-03
- [x] Database — real write (record_operation → operations insert + projection update) AND real read (ledger_view, compute_stock) — Plans 01-02/01-03
- [x] UI — correction form wired via hx-post/hx-target/hx-swap to /ops — Plan 01-03
- [x] Deployment — run.bat documented local full-stack run command — Plan 01-03

## Out of Scope (Deferred to Later Slices)

- Product catalog CRUD, code→name dictionary, search/autocomplete (Phase 2)
- Goods receipts and automated VACUUM INTO backups (Phase 3)
- Sales, price override, oversell warning, cost snapshots, customers (Phase 4)
- Write-offs, returns, corrections UI beyond the skeleton form, full history browsing (Phase 5)
- Reports and CSV export (Phase 6)
- Sync engine / CRDTs / multi-device device_id negotiation (v2 — schema stays sync-ready only)
- Editing/deleting ledger rows — never; corrections are new operations rows
- `synced_at` updates — blocked by triggers in v1; v2 relaxes with a WHEN-clause migration

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2: operator maintains the catalog and finds any product in seconds (writes still via services; prices as `_cents` history rows)
- Phase 3: operator books goods receipts through `record_operation(type_="receipt")`; automated WAL-safe backups
- Phase 4: sales with price override + customer linking (`payload` may promote `customer_id` to a real column via migration — decide at Phase 4 planning)
- Phase 5: write-off / return / correction UI + full history over the same ledger
- Phase 6: reports and CSV export as read-only projections of the ledger
