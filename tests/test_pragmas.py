"""D-14: SQLite PRAGMAs must be applied per-connection via the event listener.

Assert on a live pooled connection — Pitfall 1: PRAGMAs "set once at startup"
do not survive pool checkouts unless the connect-event listener applies them.
"""

import pytest
from sqlalchemy.exc import IntegrityError

# The four append-only triggers guarding the two ledger tables (app.db).
APPEND_ONLY_TRIGGER_NAMES = frozenset(
    {
        "operations_no_update",
        "operations_no_delete",
        "cash_movements_no_update",
        "cash_movements_no_delete",
    }
)


def test_pragmas_applied_on_pooled_connection(engine):
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000


def test_append_only_triggers_survive_author_id_schema(engine):
    """Phase 25 Pitfall 1 regression: adding `author_id` (migration 0017) must
    NEVER use batch_alter_table on operations/cash_movements — a batch rebuild
    silently DROPS the four append-only triggers. The `engine` fixture mirrors
    the applied-migration schema (users table + author_id columns), so this
    proves the triggers still EXIST after the attribution schema is built.
    """
    with engine.connect() as connection:
        present = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )
        }
    assert APPEND_ONLY_TRIGGER_NAMES <= present, (
        f"missing append-only triggers: {APPEND_ONLY_TRIGGER_NAMES - present}"
    )


def test_operations_update_still_aborts_after_author_id(engine):
    """The operations_no_update trigger must be LIVE (not merely present) after
    author_id exists — an UPDATE touching author_id must still ABORT. Proves the
    append-only guarantee holds through the Phase 25 schema change.
    """
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO products (id, name, quantity, created_at, updated_at) "
            "VALUES ('p-1', 'Тест', 0, '2026-07-18T00:00:00+00:00', "
            "'2026-07-18T00:00:00+00:00')"
        )
        connection.exec_driver_sql(
            "INSERT INTO operations (id, type, product_id, qty_delta, device_id, "
            "seq, created_at, created_by) VALUES ('op-1', 'receipt', 'p-1', 1, "
            "'dev-1', 1, '2026-07-18T00:00:00+00:00', 'seed')"
        )

    with pytest.raises(IntegrityError, match="append-only"):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE operations SET author_id = 'u-1' WHERE id = 'op-1'"
            )
