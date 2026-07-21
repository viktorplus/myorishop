"""Wipe ONLY business/transactional data back to a clean baseline (quick task
260721-fu0).

Run: uv run python scripts/reset_business_data.py

Dialect-aware (works unmodified against local SQLite AND the deployed
PostgreSQL server — auto-detected from app.config.settings.database_url).
Wipes products/batches/customers/customer_contacts/sales/operations/
cash_movements ONLY. NEVER touches warehouses, users, device_tokens,
dictionary, catalog_prices, active_catalog, or sync_state.

This is deliberately narrower than scripts/reset_demo_data.py (which deletes
the SQLite FILE and re-migrates, wiping literally everything including users
and the dictionary, and only works locally) — see the quick task's PLAN.md
objective for the full rationale.

SAFETY: there is NO --yes/--force flag anywhere in this script. It refuses to
run unless the operator types the exact confirmation phrase at an interactive
prompt; running it non-interactively (stdin not a tty) aborts immediately,
before touching the database at all.

This script imports app.db freely (unlike reset_demo_data.py) — it wipes
tables in place rather than deleting a file, so there is no file-lock hazard.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import APPEND_ONLY_TRIGGERS, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Batch,
    CashMovement,
    Customer,
    CustomerContact,
    Operation,
    Product,
    Sale,
)

# Children-before-parents delete order (matches the FK graph — see
# app/models.py). warehouses/users/device_tokens/dictionary/catalog_prices/
# active_catalog/sync_state are NEVER touched by this script.
_WIPE_ORDER = (CashMovement, Operation, CustomerContact, Sale, Batch, Customer, Product)

_TRIGGER_NAMES = (
    "operations_no_update",
    "operations_no_delete",
    "cash_movements_no_update",
    "cash_movements_no_delete",
)

CONFIRM_PHRASE = "УДАЛИТЬ"


def wipe_business_data(session: Session, engine: Engine) -> dict[str, int]:
    """Delete every row from _WIPE_ORDER's tables; return {table_name: rows_deleted}.

    Bypasses the append-only triggers on operations/cash_movements for the
    duration of this call ONLY, then restores them before returning — the
    live app's UPDATE/DELETE guarantee on those two tables is unaffected once
    this function returns, on EITHER dialect. Idempotent: safe to call again
    on an already-empty database.
    """
    dialect = engine.dialect.name
    if dialect not in ("sqlite", "postgresql"):
        raise RuntimeError(f"unsupported dialect: {dialect!r}")

    if dialect == "sqlite":
        for name in _TRIGGER_NAMES:
            session.execute(text(f"DROP TRIGGER IF EXISTS {name}"))
    else:  # postgresql
        session.execute(text("ALTER TABLE operations DISABLE TRIGGER ALL"))
        session.execute(text("ALTER TABLE cash_movements DISABLE TRIGGER ALL"))

    counts: dict[str, int] = {}
    try:
        for model in _WIPE_ORDER:
            result = session.execute(model.__table__.delete())
            counts[model.__tablename__] = result.rowcount
    finally:
        # Restored under all conditions, including a mid-wipe exception — the
        # append-only guarantee must never be left disabled.
        if dialect == "sqlite":
            for ddl in APPEND_ONLY_TRIGGERS:
                session.execute(text(ddl))
        else:  # postgresql
            session.execute(text("ALTER TABLE operations ENABLE TRIGGER ALL"))
            session.execute(text("ALTER TABLE cash_movements ENABLE TRIGGER ALL"))
    session.commit()
    return counts


def _target_label(engine: Engine) -> str:
    """Human-readable target identity, PASSWORD-REDACTED (never print engine.url raw)."""
    if engine.dialect.name == "postgresql":
        return f"PostgreSQL: {engine.url.host}/{engine.url.database}"
    return f"SQLite file: {settings.db_path}"


def main() -> None:
    session = SessionLocal()
    try:
        print(f"Целевая база: {_target_label(engine)}")

        # No --yes/--force flag exists anywhere — non-interactive stdin aborts
        # immediately, BEFORE any database query, so a piped/CI invocation can
        # never hang or accidentally proceed.
        if not sys.stdin.isatty():
            print("Отказ: подтверждение требует интерактивного терминала.")
            sys.exit(1)

        print("Будет удалено (текущее количество строк):")
        for model in _WIPE_ORDER:
            count = session.scalar(select(func.count()).select_from(model.__table__))
            print(f"  {model.__tablename__}: {count}")

        answer = input(f'Введите "{CONFIRM_PHRASE}" чтобы продолжить: ')
        if answer.strip() != CONFIRM_PHRASE:
            print("Отменено.")
            sys.exit(1)

        counts = wipe_business_data(session, engine)
        print("Удалено:")
        for table, n in counts.items():
            print(f"  {table}: {n}")
        print("Готово. Таблицы warehouses/users/device_tokens/dictionary/"
              "catalog_prices/sync_state не затронуты.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
