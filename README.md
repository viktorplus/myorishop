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

## Test

```bat
uv run pytest
```

## Lint

```bat
uv run ruff check .
```
