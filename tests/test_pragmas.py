"""D-14: SQLite PRAGMAs must be applied per-connection via the event listener.

Assert on a live pooled connection — Pitfall 1: PRAGMAs "set once at startup"
do not survive pool checkouts unless the connect-event listener applies them.
"""


def test_pragmas_applied_on_pooled_connection(engine):
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
