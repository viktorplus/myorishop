"""SYNC-02/04/05 PostgreSQL portability slice for the ONE merge engine.

Proves that ``app/services/merge.py`` — the single correctness core shared by
both later transports (Phase 28 online sync, Phase 30 offline self-upload) —
behaves IDENTICALLY on PostgreSQL (the server) and SQLite (the client). The
engine deliberately avoids dialect-specific upsert clauses (``on_conflict_*``) in
favour of a portable pre-select set-difference (``_partition_new``); the only way
to KNOW it stayed portable is to re-run its idempotency + Product.code-collision
core on a real PostgreSQL instance. This mirrors the Phase 26 harness in
``tests/test_pg_parity.py`` (skipif guard + ``_engine``/``_upgrade_head`` +
``sessionmaker`` + ``try/finally: engine.dispose()``).

The whole module SKIPS on SQLite (the local dev default) and RUNS only when
``DATABASE_URL`` targets a ``postgresql+psycopg://…`` server — ``settings``
is the single source of truth.

Seed rule (Security V5, T-27-05): only literal constant seed values / bound
parameters are used — no external or dynamic data is f-stringed into any SQL text
or record. Fixed UUIDs make the module re-runnable against a standing PG server:
ledger rows can never be DELETEd (append-only triggers), so a second run's
set-difference simply finds them present and inserts nothing (idempotency).
"""

import json

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.config import settings
from app.models import Batch, Operation, Product
from app.services.finance import compute_balance
from app.services.ledger import compute_batch_stock, compute_stock
from app.services.merge import FORMAT_VERSION, _suffix_code, apply_merge, parse_exchange

# Single source of truth: run only against a PostgreSQL target (mirror pg_parity).
pytestmark = pytest.mark.skipif(
    not settings.database_url.startswith("postgresql"),
    reason="PG merge portability — set DATABASE_URL to a postgresql+psycopg:// URL",
)

# --- Literal-constant fixtures (fixed UUIDs; never f-string dynamic data) ------

_TS = "2026-07-19T10:00:00+00:00"
_NOW = "2026-07-19T12:00:00+00:00"

# Idempotency slice ids (all <=36 chars for String(36) PKs).
_IDEM_PROD = "11111111-1111-1111-1111-111111110001"
_IDEM_WH = "22222222-2222-2222-2222-222222220001"
_IDEM_BATCH = "33333333-3333-3333-3333-333333330001"
_IDEM_OP = "44444444-4444-4444-4444-444444440001"
_IDEM_CASH = "55555555-5555-5555-5555-555555550001"
_IDEM_QTY = 10

# Collision slice ids + the shared active code.
_INCUMBENT_ID = "aaaaaaaa-0000-0000-0000-0000000000c1"
_LOSER_ID = "bbbbbbbb-1111-2222-3333-4444555566c1"
_LOSER_OP = "cccccccc-0000-0000-0000-0000000000c1"
_CODE = "PGCOL9"

# Idempotent incumbent seed: products carry no append-only trigger, but ON
# CONFLICT DO NOTHING keeps the harness re-runnable against a standing server.
_SEED_INCUMBENT = (
    "INSERT INTO products (id, code, name, quantity, created_at, updated_at) "
    "VALUES ('aaaaaaaa-0000-0000-0000-0000000000c1', 'PGCOL9', 'Инкумбент', 0, "
    "'2026-07-19T10:00:00+00:00', '2026-07-19T10:00:00+00:00') "
    "ON CONFLICT DO NOTHING"
)


def _engine():
    """Engine from the single-source-of-truth URL (postgresql+psycopg://…)."""
    return create_engine(settings.database_url)


def _upgrade_head():
    """Apply the whole migration chain to the PG target (env.py reads settings).

    Idempotent — ``head`` re-applied against an up-to-date DB is a no-op, so each
    test can call this to guarantee the schema exists without ordering coupling.
    """
    command.upgrade(Config("alembic.ini"), "head")


def _rec(kind: str, **fields) -> dict:
    """One NDJSON record dict: a literal ``kind`` + explicit literal fields."""
    return {"kind": kind, **fields}


def _ndjson(records: list[dict]) -> list[str]:
    """Return NDJSON lines (header first) built from literal-constant dicts only."""
    header = {
        "kind": "header",
        "format_version": FORMAT_VERSION,
        "schema_version": "0017",
        "source_device_id": "pg-device",
        "generated_at": _TS,
        "counts": {},
    }
    lines = [json.dumps(header, ensure_ascii=False)]
    lines.extend(json.dumps(rec, ensure_ascii=False) for rec in records)
    return lines


def _apply(session, records):
    """Parse literal records into a batch and apply_merge it (no commit inside)."""
    return apply_merge(session, parse_exchange(_ndjson(records)), server_now=_NOW)


def test_merge_idempotent_on_pg():
    """SYNC-02/04: merge-twice == once on PostgreSQL (portable set-difference).

    A first apply lands a reference product/warehouse/batch + an operation + a
    cash_movement; a second apply of the SAME batch inserts 0 rows and leaves
    derived stock/balance identical — proving the pre-select set-difference (not a
    dialect ``on_conflict``) holds on PG exactly as on SQLite.
    """
    _upgrade_head()
    engine = _engine()
    factory = sessionmaker(bind=engine)
    records = [
        _rec(
            "warehouse",
            id=_IDEM_WH,
            name="PG-Склад",
            address=None,
            created_at=_TS,
            updated_at=_TS,
            deleted_at=None,
        ),
        _rec(
            "product",
            id=_IDEM_PROD,
            code="PGIDEM1",
            name="PG-Товар",
            name_lc="pg-товар",
            category=None,
            cost_cents=None,
            sale_cents=None,
            min_sale_cents=None,
            low_stock_threshold=None,
            stale_days=None,
            quantity=0,
            created_at=_TS,
            updated_at=_TS,
            deleted_at=None,
        ),
        _rec(
            "batch",
            id=_IDEM_BATCH,
            product_id=_IDEM_PROD,
            warehouse_id=_IDEM_WH,
            expiry=None,
            price_cents=None,
            location=None,
            comment=None,
            name=None,
            quantity=0,
            is_legacy=0,
            created_at=_TS,
            updated_at=_TS,
        ),
        _rec(
            "operation",
            id=_IDEM_OP,
            type="receipt",
            product_id=_IDEM_PROD,
            qty_delta=_IDEM_QTY,
            unit_cost_cents=1000,
            unit_price_cents=None,
            payload=None,
            sale_id=None,
            batch_id=_IDEM_BATCH,
            author_id=None,
            device_id="pg-dev",
            seq=1001,
            created_at=_TS,
            created_by="operator",
            synced_at=None,
        ),
        _rec(
            "cash_movement",
            id=_IDEM_CASH,
            category="sale",
            amount_cents=5000,
            note=None,
            sale_id=None,
            author_id=None,
            device_id="pg-dev",
            seq=1001,
            created_at=_TS,
            created_by="operator",
            synced_at=None,
        ),
    ]
    try:
        with factory() as session:
            # First apply — rows land (fresh CI) or are already present (re-run).
            _apply(session, records)
            session.commit()

            product = session.get(Product, _IDEM_PROD)
            assert product is not None
            assert product.quantity == _IDEM_QTY == compute_stock(session, _IDEM_PROD)
            # Batch stock recomputed from the merged ledger.
            batch = session.get(Batch, _IDEM_BATCH)
            assert batch is not None
            assert batch.quantity == _IDEM_QTY == compute_batch_stock(session, batch)
            assert session.get(Operation, _IDEM_OP) is not None

            # Snapshot the derived state that a replay must not perturb.
            snap = (product.quantity, batch.quantity, compute_balance(session))

            # Second apply of the SAME batch — idempotent no-op on PG.
            report2 = _apply(session, records)
            session.commit()
            assert report2.operations_inserted == 0
            assert report2.cash_inserted == 0
            assert report2.operations_skipped == 1
            assert report2.cash_skipped == 1

            session.refresh(product)
            session.refresh(batch)
            assert (product.quantity, batch.quantity, compute_balance(session)) == snap
            # Exactly one row per origin UUID — the set-difference deduped on PG.
            assert (
                session.scalar(
                    select(Operation).where(Operation.id == _IDEM_OP)
                ).id
                == _IDEM_OP
            )
    finally:
        engine.dispose()


def test_code_collision_on_pg():
    """SYNC-05: Product.code collision renames the loser against PG's partial index.

    An active incumbent owns a fixed code; a NEW product (different UUID) carrying
    the same code is merged with a referencing operation. The incumbent keeps the
    code, the incoming loser is renamed deterministically (keeping its UUID so its
    operation stays valid), proving the collision path works against PostgreSQL's
    ``postgresql_where`` partial unique index ``uq_products_code_active``.
    """
    _upgrade_head()
    engine = _engine()
    factory = sessionmaker(bind=engine)
    records = [
        _rec(
            "product",
            id=_LOSER_ID,
            code=_CODE,
            name="Проигравший",
            name_lc="проигравший",
            category=None,
            cost_cents=None,
            sale_cents=None,
            min_sale_cents=None,
            low_stock_threshold=None,
            stale_days=None,
            quantity=0,
            created_at=_TS,
            updated_at=_TS,
            deleted_at=None,
        ),
        _rec(
            "operation",
            id=_LOSER_OP,
            type="receipt",
            product_id=_LOSER_ID,
            qty_delta=3,
            unit_cost_cents=1000,
            unit_price_cents=None,
            payload=None,
            sale_id=None,
            batch_id=None,
            author_id=None,
            device_id="pg-dev",
            seq=2001,
            created_at=_TS,
            created_by="operator",
            synced_at=None,
        ),
    ]
    try:
        with engine.begin() as conn:
            conn.execute(text(_SEED_INCUMBENT))
        with factory() as session:
            _apply(session, records)
            session.commit()

            # Incumbent keeps the clean code (server-dialect partial index honoured).
            incumbent = session.get(Product, _INCUMBENT_ID)
            assert incumbent is not None
            assert incumbent.code == _CODE
            assert incumbent.deleted_at is None

            # Loser inserted with a deterministic rename, ORIGINAL UUID preserved.
            loser = session.get(Product, _LOSER_ID)
            assert loser is not None
            assert loser.code == _suffix_code(_CODE, _LOSER_ID)
            assert loser.code != _CODE
            assert loser.code.startswith(_CODE)
            assert "~" in loser.code
            assert _LOSER_ID.replace("-", "")[:4] in loser.code
            assert len(loser.code) <= 20

            # The loser's operation inserted and references the preserved UUID.
            op_row = session.get(Operation, _LOSER_OP)
            assert op_row is not None
            assert op_row.product_id == _LOSER_ID
    finally:
        engine.dispose()
