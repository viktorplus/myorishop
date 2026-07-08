"""CAT-01 executable contract: product create/list slice (Plan 02-01).

Covers the catalog service create path (D-19/D-27/D-30), the IN-01
deleted-product guard in record_operation (D-20), migration 0002
(fresh DB + Cyrillic Python-side name_lc backfill) and the /products
web slice.

Naming convention (used by later -k filters): route/e2e tests are
prefixed test_web_, everything else is service/schema level.
"""

import sqlite3
from contextlib import closing

import pytest
from alembic.config import Config
from app.services.catalog import category_options, create_product, list_products
from sqlalchemy import select, text

from alembic import command
from app.config import settings
from app.core import utcnow_iso
from app.models import OPERATION_TYPES, Operation
from app.services.ledger import record_operation

EMPTY_MONEY = {"cost_raw": "", "sale_raw": "", "catalog_raw": ""}


def test_create_product_persists_all_fields_and_name_lc(session):
    """D-19/D-27: all CAT-01 fields stored; empty money -> NULL; Cyrillic name_lc."""
    product, errors = create_product(
        session,
        code="1234",
        name="Губная Помада",
        category="Макияж",
        cost_raw="100",
        sale_raw="150,50",
        catalog_raw="",
    )
    assert errors == {}
    assert product is not None
    assert product.code == "1234"
    assert product.name == "Губная Помада"
    assert product.category == "Макияж"
    assert product.cost_cents == 10000
    assert product.sale_cents == 15050
    assert product.catalog_cents is None
    assert product.quantity == 0
    # D-27: Python str.lower folds Cyrillic (SQL lower() cannot).
    assert product.name_lc == "губная помада"
    assert product in list_products(session)


def test_create_product_records_product_created_op(session):
    """D-30: create writes exactly one product_created op with qty_delta=0."""
    product, errors = create_product(
        session, code="1234", name="Губная Помада", category="", **EMPTY_MONEY
    )
    assert errors == {}
    ops = session.scalars(select(Operation)).all()
    assert len(ops) == 1
    op = ops[0]
    assert op.type == "product_created"
    assert op.qty_delta == 0
    assert op.product_id == product.id
    assert op.created_by == settings.operator_name  # FND-03
    assert op.payload["code"] == "1234"
    assert op.payload["name"] == "Губная Помада"


def test_create_product_rejects_duplicate_active_code(session):
    """D-19: code unique among non-deleted; failed create writes nothing."""
    first, errors = create_product(
        session, code="1234", name="Первый", category="", **EMPTY_MONEY
    )
    assert errors == {}
    second, errors = create_product(
        session, code="1234", name="Второй", category="", **EMPTY_MONEY
    )
    assert second is None
    assert "code" in errors
    assert session.scalar(text("SELECT COUNT(*) FROM products WHERE code = '1234'")) == 1
    assert session.scalar(text("SELECT COUNT(*) FROM operations")) == 1


def test_soft_deleted_code_can_be_reused(session, product):
    """D-19/D-20: uniqueness applies to ACTIVE products only."""
    product.deleted_at = utcnow_iso()
    session.commit()

    created, errors = create_product(
        session, code="TEST-001", name="Новый товар", category="", **EMPTY_MONEY
    )
    assert errors == {}
    assert created is not None
    assert created.code == "TEST-001"
    assert created.id != product.id


def test_record_operation_rejects_soft_deleted_product(session, product):
    """IN-01 / D-20: ANY operation on a soft-deleted product is rejected."""
    product.deleted_at = utcnow_iso()
    session.commit()

    with pytest.raises(ValueError, match="deleted"):
        record_operation(session, type_="correction", product_id=product.id, qty_delta=1)
    session.rollback()
    assert session.scalar(text("SELECT COUNT(*) FROM operations")) == 0


def test_operation_types_extended():
    """RESEARCH Finding 5: three new audit op types exist."""
    for op_type in ("price_change", "product_created", "product_edited"):
        assert op_type in OPERATION_TYPES


def test_migration_0002_fresh_db_and_backfill(tmp_path, monkeypatch):
    """Migration 0002: fresh upgrade, Cyrillic Python backfill, triggers intact."""
    db_file = tmp_path / "fresh.db"
    # settings is a module-level singleton instantiated at import time —
    # patch the attribute, NOT the environment variable.
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "0001")

    now = "2026-07-08T00:00:00+00:00"
    with closing(sqlite3.connect(db_file)) as conn:
        conn.execute(
            "INSERT INTO products (id, code, name, quantity, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("00000000-0000-4000-8000-000000000002", "1234", "ДЕМО-Помада", 0, now, now),
        )
        conn.commit()

    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db_file)) as conn:
        # (a) new products columns present
        cols = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
        assert {"category", "cost_cents", "sale_cents", "catalog_cents", "name_lc"} <= cols

        # (b) Python-side backfill folded the Cyrillic name (NOT SQL lower()).
        (name_lc,) = conn.execute(
            "SELECT name_lc FROM products WHERE name = ?", ("ДЕМО-Помада",)
        ).fetchone()
        assert name_lc == "демо-помада"

        # (c) dictionary table with expected columns + unique index on code (PD-1)
        dict_cols = {row[1] for row in conn.execute("PRAGMA table_info(dictionary)")}
        assert dict_cols == {"id", "code", "name", "created_at", "updated_at"}
        unique_on_code = False
        for _seq, index_name, unique, *_rest in conn.execute("PRAGMA index_list(dictionary)"):
            columns = [r[2] for r in conn.execute(f'PRAGMA index_info("{index_name}")')]
            if unique and columns == ["code"]:
                unique_on_code = True
        assert unique_on_code, "dictionary.code must have a unique index"

        # (d) append-only triggers untouched (migration never touches operations)
        triggers = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")
        }
        assert {"operations_no_update", "operations_no_delete"} <= triggers

        # (e) search indexes created
        indexes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
        }
        assert {"ix_products_code", "ix_products_name_lc"} <= indexes


def test_category_options_distinct_active_only(session):
    """Datalist source: distinct non-empty categories of ACTIVE products, sorted."""
    create_product(session, code="A1", name="Духи", category="Ароматы", **EMPTY_MONEY)
    create_product(session, code="A2", name="Помада", category="Макияж", **EMPTY_MONEY)
    deleted, errors = create_product(
        session, code="A3", name="Крем", category="Уход", **EMPTY_MONEY
    )
    assert errors == {}
    deleted.deleted_at = utcnow_iso()
    session.commit()
    create_product(session, code="A4", name="Без категории", category="", **EMPTY_MONEY)

    assert category_options(session) == ["Ароматы", "Макияж"]


def test_web_products_page_lists_created_product(client, session):
    """CAT-01 e2e: POST /products creates, redirects; list shows the product."""
    response = client.post(
        "/products",
        data={
            "code": "7777",
            "name": "Тушь Для Ресниц",
            "category": "",
            "cost": "",
            "sale": "",
            "catalog": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    page = client.get("/products")
    assert page.status_code == 200
    assert "Тушь Для Ресниц" in page.text

    ops = session.scalars(
        select(Operation).where(Operation.type == "product_created")
    ).all()
    assert len(ops) == 1


def test_web_deleted_product_hidden_and_empty_state(client, session, product):
    """D-20 + UI-SPEC: deleted products hidden; empty state shown."""
    product.deleted_at = utcnow_iso()
    session.commit()

    page = client.get("/products")
    assert page.status_code == 200
    assert "Тестовый товар" not in page.text
    assert "Товаров пока нет" in page.text


def test_web_create_invalid_money_rerenders_with_error(client, session):
    """Invalid money -> 422 re-render with RU error; nothing persisted."""
    response = client.post(
        "/products",
        data={
            "code": "9999",
            "name": "Тест",
            "category": "",
            "cost": "abc",
            "sale": "",
            "catalog": "",
        },
    )
    assert response.status_code == 422
    assert "Неверный формат цены" in response.text
    assert session.scalar(text("SELECT COUNT(*) FROM products WHERE code = '9999'")) == 0
    assert session.scalar(text("SELECT COUNT(*) FROM operations")) == 0
