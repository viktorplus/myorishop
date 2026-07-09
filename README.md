# MyOriShop

Local warehouse inventory and sales tracking for a single Oriflame reseller.
FastAPI + SQLAlchemy + SQLite + HTMX, server-rendered, fully offline after setup.

## Prerequisites

- Windows
- Internet is needed once for setup (installs uv + dependencies); after that the app runs fully offline

## Setup (one time)

Double-click `install.bat` — it installs [uv](https://docs.astral.sh/uv/) (via winget) if missing, then runs `uv sync` and applies database migrations.

Or manually:

```bat
uv sync
uv run alembic upgrade head
```

## Run

Double-click `run.bat`, or run:

```bat
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000 (run.bat opens the browser automatically).
The app binds to loopback only and works without internet.

## Demo data (for manual testing)

- Double-click `seed_demo_data.bat` to fill the database with sample products, customers, and sales.
- Double-click `reset_demo_data.bat` to wipe it back to empty (the operations ledger is append-only, so this deletes the DB file and re-applies migrations rather than deleting rows).

Re-running the seed script without a reset in between refuses to run (pass `--force` to seed on top of existing data anyway).

## Test

```bat
uv run pytest
```

## Lint

```bat
uv run ruff check .
```
