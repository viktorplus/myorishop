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

## Catalogs & price lists

The **Каталоги** section (`/catalogs`) publishes the Oriflame catalog PDFs and,
for each catalog, lists its products with prices. Source data lives in the
`catalogs/` folder and is loaded into the database by two import scripts.

Place the source files in `catalogs/`:

- **PDF catalogs** — one file per issue (e.g. `2026-01.pdf`); mixed filename
  formats are tolerated.
- **`products.json`** — `code → { name, catalogs[] }`; fills the reference
  dictionary (name + catalog membership).
- **xlsx price lists** — one file per catalog issue (e.g. `01-2026.xlsx`); the
  `КОД`/`ПЦ`/`ОП`/`ББ` columns fill the per-catalog price history.

Load the data (both scripts are idempotent — safe to re-run after adding files):

```bat
uv run python scripts/import_catalogs.py   :: dictionary: names + catalog membership
uv run python scripts/import_prices.py      :: per-catalog prices (catalog_prices)
```

After import, adding a product auto-fills the name (from the dictionary) and the
catalog / purchase price (from the latest catalog) once its code is entered; the
operator can still override any suggested value.

## Test

```bat
uv run pytest
```

## Lint

```bat
uv run ruff check .
```
