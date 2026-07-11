"""WH-01 executable contract: Warehouse model, migration 0007, service layer.

Naming convention (mirrors test_dictionary.py/test_catalog.py): route/e2e
tests are prefixed test_web_, everything else is service/schema level.
"""

import sqlite3
from contextlib import closing

from alembic.config import Config

from alembic import command
from app.config import settings


def test_migration_0007_creates_and_seeds_default_warehouse(tmp_path, monkeypatch):
    """Migration 0007: fresh upgrade creates warehouses table + one seed row."""
    db_file = tmp_path / "fresh.db"
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "0006")
    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db_file)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(warehouses)")}
        assert cols == {"id", "name", "address", "created_at", "updated_at", "deleted_at"}

        rows = conn.execute(
            "SELECT id, name, address, deleted_at FROM warehouses"
        ).fetchall()
        assert rows == [
            ("00000000-0000-4000-8000-000000000010", "Склад по умолчанию", None, None)
        ]
