"""Wipe the local database back to empty (undoes seed_demo_data.py).

Run: uv run python scripts/reset_demo_data.py

The operations ledger is append-only at the DB level (no UPDATE/DELETE,
by design - see app/models.py Operation), so "clearing" test data can't
mean selectively deleting rows. Instead this deletes the SQLite file
(+ WAL/SHM sidecars) and re-applies migrations, giving back the exact
same clean state as a fresh install (just the frozen demo product).

This script must NOT import app.db - importing it opens a SQLite engine
and would hold a lock on the very file we're about to delete.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic.config import main as alembic_main  # noqa: E402

from app.config import settings  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    db_path = Path(settings.db_path)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path

    removed = []
    for suffix in ("", "-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + suffix)
        if sidecar.exists():
            sidecar.unlink()
            removed.append(sidecar.name)

    if removed:
        print(f"Removed: {', '.join(removed)}")
    else:
        print("No database file found - already clean.")

    print("Re-applying migrations...")
    import os

    cwd = os.getcwd()
    os.chdir(PROJECT_ROOT)
    try:
        alembic_main(argv=["upgrade", "head"])
    finally:
        os.chdir(cwd)

    print("Done. Database reset to empty (just the frozen demo product).")


if __name__ == "__main__":
    main()
