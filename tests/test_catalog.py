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
from sqlalchemy import select, text

from alembic import command
from app.config import settings
from app.core import utcnow_iso
from app.models import OPERATION_TYPES, Operation
from app.services.catalog import (
    category_options,
    create_product,
    list_products,
    price_history,
    products_by_category,
    restore_product,
    soft_delete_product,
    update_product,
)
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


def test_create_product_rejects_negative_price(session):
    """WR-04: a negative amount has no domain meaning for a price field and
    must be rejected with PRICE_ERROR, not stored as negative cents."""
    product, errors = create_product(
        session,
        code="1234",
        name="Помада",
        category="",
        cost_raw="-12,50",
        sale_raw="",
        catalog_raw="",
    )
    assert product is None
    assert "cost" in errors
    assert session.scalar(text("SELECT COUNT(*) FROM products")) == 0


def test_create_product_threshold_fields_empty_means_none(session):
    """D-05: empty threshold raw strings -> NULL columns ('use global default')."""
    product, errors = create_product(
        session,
        code="1234",
        name="Помада",
        category="",
        **EMPTY_MONEY,
        low_stock_threshold_raw="",
        stale_days_raw="",
    )
    assert errors == {}
    assert product is not None
    assert product.low_stock_threshold is None
    assert product.stale_days is None


def test_create_product_threshold_zero_is_stored_as_zero_not_none(session):
    """Pitfall 3 (service level): an explicit "0" is stored as int 0, never None."""
    product, errors = create_product(
        session,
        code="1234",
        name="Помада",
        category="",
        **EMPTY_MONEY,
        low_stock_threshold_raw="0",
        stale_days_raw="0",
    )
    assert errors == {}
    assert product is not None
    assert product.low_stock_threshold == 0
    assert product.stale_days == 0


def test_create_product_rejects_invalid_threshold(session):
    """T-06-01: non-digit and negative threshold values are rejected, not clamped."""
    product, errors = create_product(
        session,
        code="1234",
        name="Помада",
        category="",
        **EMPTY_MONEY,
        low_stock_threshold_raw="abc",
        stale_days_raw="-1",
    )
    assert product is None
    assert "low_stock_threshold" in errors
    assert "stale_days" in errors
    assert session.scalar(text("SELECT COUNT(*) FROM products")) == 0


def test_create_product_rejects_threshold_above_int32_bound(session):
    """WR-03: a digit string that fits SQLite INTEGER but overflows a future
    PostgreSQL 4-byte INTEGER column must be rejected, not silently stored."""
    product, errors = create_product(
        session,
        code="1234",
        name="Помада",
        category="",
        **EMPTY_MONEY,
        low_stock_threshold_raw="2147483648",  # 2^31, one past the int32 max
        stale_days_raw="0",
    )
    assert product is None
    assert "low_stock_threshold" in errors
    assert session.scalar(text("SELECT COUNT(*) FROM products")) == 0


def test_duplicate_active_code_blocked_by_db_index(session, product):
    """WR-04: uq_products_code_active is the DB backstop, not just app code."""
    import sqlalchemy as sa

    from app.core import new_id
    from app.models import Product

    session.add(Product(id=new_id(), code="TEST-001", name="Дубль", quantity=0))
    with pytest.raises(sa.exc.IntegrityError):
        session.commit()
    session.rollback()


def test_create_duplicate_code_race_returns_ru_error_not_500(session, monkeypatch):
    """WR-04: when the SELECT check misses (double-submit race), the partial
    unique index fires at flush and must be translated into the RU error."""
    import sqlalchemy as sa

    from app.services import catalog as catalog_service

    first, errors = create_product(
        session, code="1234", name="Первый", category="", **EMPTY_MONEY
    )
    assert errors == {}

    # Blind the duplicate check to simulate the second tab of a race.
    monkeypatch.setattr(
        catalog_service,
        "select",
        lambda *entities: sa.select(*entities).where(sa.false()),
    )
    second, errors = create_product(
        session, code="1234", name="Второй", category="", **EMPTY_MONEY
    )
    assert second is None
    assert "Код уже используется другим товаром" in errors["code"]
    # Rollback left exactly one product and one audit op.
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


def test_migration_0005_adds_threshold_columns(tmp_path, monkeypatch):
    """Migration 0005: fresh upgrade adds NULL low_stock_threshold/stale_days."""
    db_file = tmp_path / "fresh.db"
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "0004")

    now = "2026-07-10T00:00:00+00:00"
    with closing(sqlite3.connect(db_file)) as conn:
        conn.execute(
            "INSERT INTO products (id, code, name, quantity, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("00000000-0000-4000-8000-000000000005", "5555", "Порог-Тест", 0, now, now),
        )
        conn.commit()

    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db_file)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
        assert {"low_stock_threshold", "stale_days"} <= cols

        low_stock_threshold, stale_days = conn.execute(
            "SELECT low_stock_threshold, stale_days FROM products WHERE name = ?",
            ("Порог-Тест",),
        ).fetchone()
        assert low_stock_threshold is None
        assert stale_days is None


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


def test_products_by_category_groups_alphabetically_uncategorized_last(session):
    """D-03/D-04: named groups alphabetical, "Без категории" always last, never split."""
    create_product(session, code="B1", name="Духи", category="Парфюмерия", **EMPTY_MONEY)
    create_product(session, code="A1", name="Помада", category="Макияж", **EMPTY_MONEY)
    create_product(session, code="C1", name="Крем", category="Уход", **EMPTY_MONEY)
    create_product(session, code="U1", name="Товар Без Категории 1", category="", **EMPTY_MONEY)
    create_product(session, code="U2", name="Товар Без Категории 2", category="", **EMPTY_MONEY)

    groups = products_by_category(session)
    labels = [g["label"] for g in groups]
    assert labels == ["Макияж", "Парфюмерия", "Уход", "Без категории"]
    uncategorized = groups[-1]["products"]
    assert {p.code for p in uncategorized} == {"U1", "U2"}


def test_products_by_category_excludes_deleted(session):
    """D-05: a soft-deleted product never appears in any group."""
    kept, errors = create_product(
        session, code="K1", name="Остаётся", category="Уход", **EMPTY_MONEY
    )
    assert errors == {}
    gone, errors = create_product(
        session, code="G1", name="Удалён", category="Уход", **EMPTY_MONEY
    )
    assert errors == {}
    soft_delete_product(session, gone.id)

    groups = products_by_category(session)
    all_ids = {p.id for g in groups for p in g["products"]}
    assert kept.id in all_ids
    assert gone.id not in all_ids


def test_products_by_category_empty_catalog_returns_empty_list(session):
    """Zero active products -> []."""
    assert products_by_category(session) == []


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


# --- Plan 02-02: edit / price history / soft delete-restore (CAT-01 + CAT-04) ---


def test_update_price_records_price_change_with_old_and_new(session):
    """D-28 / Pitfall 7: old_cents snapshotted BEFORE mutation; one op per field."""
    product, errors = create_product(
        session,
        code="1234",
        name="Помада",
        category="",
        cost_raw="",
        sale_raw="150,50",
        catalog_raw="",
    )
    assert errors == {}
    updated, errors = update_product(
        session,
        product.id,
        code="1234",
        name="Помада",
        category="",
        cost_raw="",
        sale_raw="200",
        catalog_raw="",
    )
    assert errors == {}
    assert updated is not None
    ops = session.scalars(select(Operation).where(Operation.type == "price_change")).all()
    assert len(ops) == 1
    op = ops[0]
    assert op.qty_delta == 0
    # Snapshot-before-mutate: old is the PRE-update value, not the new one.
    assert op.payload == {"field": "sale_cents", "old_cents": 15050, "new_cents": 20000}
    session.expire_all()
    assert product.sale_cents == 20000


def test_update_two_prices_emits_two_ops(session):
    """PD-3: one price_change op PER changed field; None -> value keeps old_cents None."""
    product, errors = create_product(
        session,
        code="1234",
        name="Помада",
        category="",
        cost_raw="100",
        sale_raw="",
        catalog_raw="",
    )
    assert errors == {}
    updated, errors = update_product(
        session,
        product.id,
        code="1234",
        name="Помада",
        category="",
        cost_raw="120",
        sale_raw="",
        catalog_raw="80",
    )
    assert errors == {}
    assert updated is not None
    ops = session.scalars(select(Operation).where(Operation.type == "price_change")).all()
    assert len(ops) == 2
    by_field = {op.payload["field"]: op.payload for op in ops}
    assert by_field["cost_cents"] == {"field": "cost_cents", "old_cents": 10000, "new_cents": 12000}
    # Initial fill (None -> value) is still history: old_cents is None.
    expected = {"field": "catalog_cents", "old_cents": None, "new_cents": 8000}
    assert by_field["catalog_cents"] == expected


def test_update_unchanged_values_writes_no_ops(session):
    """No-op save: resubmitting identical values writes ZERO new operations."""
    product, errors = create_product(
        session,
        code="1234",
        name="Помада",
        category="Макияж",
        cost_raw="100",
        sale_raw="150,50",
        catalog_raw="",
    )
    assert errors == {}
    before = session.scalar(text("SELECT COUNT(*) FROM operations"))
    updated, errors = update_product(
        session,
        product.id,
        code="1234",
        name="Помада",
        category="Макияж",
        cost_raw="100",
        sale_raw="150,50",
        catalog_raw="",
    )
    assert errors == {}
    assert updated is not None
    assert session.scalar(text("SELECT COUNT(*) FROM operations")) == before


def test_update_non_price_fields_records_product_edited(session):
    """D-30 + D-27: one product_edited op with sorted changed fields; name_lc refreshed."""
    product, errors = create_product(
        session, code="1234", name="Губная Помада", category="Макияж", **EMPTY_MONEY
    )
    assert errors == {}
    updated, errors = update_product(
        session,
        product.id,
        code="1234",
        name="Тени Для Век",
        category="Глаза",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
    )
    assert errors == {}
    assert updated is not None
    ops = session.scalars(select(Operation).where(Operation.type == "product_edited")).all()
    assert len(ops) == 1
    assert ops[0].qty_delta == 0
    assert ops[0].payload == {"fields": ["category", "name"]}
    session.expire_all()
    assert product.name_lc == "тени для век"  # D-27: unconditional Python lower


def test_update_product_threshold_change_writes_product_edited_op(session):
    """D-04/D-05: a threshold-only edit writes exactly one product_edited op."""
    product, errors = create_product(
        session, code="1234", name="Помада", category="", **EMPTY_MONEY
    )
    assert errors == {}
    updated, errors = update_product(
        session,
        product.id,
        code="1234",
        name="Помада",
        category="",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
        low_stock_threshold_raw="",
        stale_days_raw="7",
    )
    assert errors == {}
    assert updated is not None
    ops = session.scalars(select(Operation).where(Operation.type == "product_edited")).all()
    assert len(ops) == 1
    assert ops[0].payload == {"fields": ["stale_days"]}
    session.expire_all()
    assert updated.stale_days == 7
    assert updated.low_stock_threshold is None


def test_update_rejects_duplicate_active_code_excluding_self(session):
    """D-19 on edit: uniqueness excludes the product itself."""
    a, errors = create_product(session, code="1111", name="Первый", category="", **EMPTY_MONEY)
    assert errors == {}
    b, errors = create_product(session, code="2222", name="Второй", category="", **EMPTY_MONEY)
    assert errors == {}
    before = session.scalar(text("SELECT COUNT(*) FROM operations"))

    result, errors = update_product(
        session,
        b.id,
        code="1111",
        name="Второй",
        category="",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
    )
    assert result is None
    assert "code" in errors
    assert session.scalar(text("SELECT COUNT(*) FROM operations")) == before

    ok, errors = update_product(
        session,
        b.id,
        code="2222",
        name="Второй",
        category="",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
    )
    assert errors == {}
    assert ok is not None


def test_update_rejects_soft_deleted_product(session, product):
    """D-20: editing a soft-deleted product is rejected up front, no writes."""
    product.deleted_at = utcnow_iso()
    session.commit()

    result, errors = update_product(
        session,
        product.id,
        code="TEST-001",
        name="Новое имя",
        category="",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
    )
    assert result is None
    assert errors
    assert session.scalar(text("SELECT COUNT(*) FROM operations")) == 0
    session.expire_all()
    assert product.name == "Тестовый товар"


def test_soft_delete_and_restore_roundtrip(session):
    """D-20 / IN-01: delete hides + blocks ops; restore brings the product back."""
    product, errors = create_product(
        session, code="1234", name="Помада", category="", **EMPTY_MONEY
    )
    assert errors == {}

    soft_delete_product(session, product.id)
    session.expire_all()
    assert isinstance(product.deleted_at, str)
    assert product.deleted_at
    assert product not in list_products(session)
    with pytest.raises(ValueError, match="deleted"):
        record_operation(session, type_="correction", product_id=product.id, qty_delta=1)
    session.rollback()

    restore_product(session, product.id)
    session.expire_all()
    assert product.deleted_at is None
    assert product in list_products(session)


def test_price_history_returns_only_price_changes_newest_first(session):
    """D-29 / Pitfall 8: only price_change ops, created_at DESC with seq tie-break."""
    product, errors = create_product(
        session,
        code="1234",
        name="Помада",
        category="",
        cost_raw="",
        sale_raw="100",
        catalog_raw="",
    )
    assert errors == {}
    # product_edited op (must NOT appear in history)
    update_product(
        session,
        product.id,
        code="1234",
        name="Помада Плюс",
        category="",
        cost_raw="",
        sale_raw="100",
        catalog_raw="",
    )
    # two price_change ops
    update_product(
        session,
        product.id,
        code="1234",
        name="Помада Плюс",
        category="",
        cost_raw="",
        sale_raw="150",
        catalog_raw="",
    )
    update_product(
        session,
        product.id,
        code="1234",
        name="Помада Плюс",
        category="",
        cost_raw="",
        sale_raw="200",
        catalog_raw="",
    )

    history = price_history(session, product.id)
    assert [op.type for op in history] == ["price_change", "price_change"]
    assert history[0].payload["new_cents"] == 20000
    assert history[1].payload["new_cents"] == 15000
    # Pitfall 8: same-second timestamps are tie-broken by seq DESC.
    assert history[0].seq > history[1].seq


def test_web_edit_page_shows_form_and_empty_history(client, session):
    """D-18: edit page pre-fills fields, shows История цен + empty state + delete."""
    product, errors = create_product(
        session,
        code="5555",
        name="Крем Для Рук",
        category="Уход",
        cost_raw="",
        sale_raw="99,90",
        catalog_raw="",
    )
    assert errors == {}

    page = client.get(f"/products/{product.id}/edit")
    assert page.status_code == 200
    assert "История цен" in page.text
    assert "Цены ещё не менялись." in page.text
    assert "5555" in page.text
    assert "Крем Для Рук" in page.text
    assert "Уход" in page.text
    assert "99,90" in page.text  # cents filter rendering of the sale input
    assert "Удалить товар" in page.text


def test_web_edit_price_then_history_rendered(client, session):
    """CAT-04 e2e: price edit shows old and new values plus the operator name."""
    product, errors = create_product(
        session,
        code="6666",
        name="Тональный Крем",
        category="",
        cost_raw="",
        sale_raw="150,50",
        catalog_raw="",
    )
    assert errors == {}

    response = client.post(
        f"/products/{product.id}",
        data={
            "code": "6666",
            "name": "Тональный Крем",
            "category": "",
            "cost": "",
            "sale": "200",
            "catalog": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get(f"/products/{product.id}/edit")
    assert page.status_code == 200
    assert "150,50" in page.text  # old value in the history row
    assert "200,00" in page.text  # new value via cents filter
    assert settings.operator_name in page.text  # «Кто» column


def test_web_delete_hides_and_restore_returns(client, session):
    """D-20 / PD-4: delete via HX-Redirect hides product; restore brings it back."""
    product, errors = create_product(
        session, code="8888", name="Мицеллярная Вода", category="", **EMPTY_MONEY
    )
    assert errors == {}

    response = client.post(f"/products/{product.id}/delete")
    assert response.status_code == 200
    assert response.headers["HX-Redirect"] == "/products"

    listing = client.get("/products")
    assert "Мицеллярная Вода" not in listing.text

    edit = client.get(f"/products/{product.id}/edit")
    assert edit.status_code == 200
    assert "Товар удалён" in edit.text
    assert "Восстановить" in edit.text

    restore = client.post(f"/products/{product.id}/restore")
    assert restore.status_code == 200
    assert restore.headers["HX-Redirect"] == f"/products/{product.id}/edit"

    listing = client.get("/products")
    assert "Мицеллярная Вода" in listing.text


def test_web_edit_unknown_id_404(client):
    """Unknown product id on the edit page -> 404."""
    response = client.get("/products/does-not-exist/edit")
    assert response.status_code == 404


# --- Plan 07-01: /categories page (CAT-01) ---


def test_web_categories_page_lists_groups_with_edit_link(client, session):
    """CAT-01 e2e: groups render in order, "Без категории" last, edit links present."""
    create_product(session, code="B1", name="Духи", category="Парфюмерия", **EMPTY_MONEY)
    a1, errors = create_product(
        session, code="A1", name="Помада", category="Макияж", **EMPTY_MONEY
    )
    assert errors == {}
    create_product(session, code="U1", name="Товар Без Категории", category="", **EMPTY_MONEY)

    page = client.get("/categories")
    assert page.status_code == 200
    assert "Товары на складе" in page.text
    macijaz_pos = page.text.index("Макияж")
    parf_pos = page.text.index("Парфюмерия")
    bez_pos = page.text.index("Без категории")
    assert macijaz_pos < parf_pos < bez_pos
    assert f"/products/{a1.id}/edit" in page.text


def test_web_categories_page_hides_deleted_products(client, session):
    """D-05: a soft-deleted product's name never appears in the response."""
    kept, errors = create_product(
        session, code="K1", name="Остаётся Крем", category="Уход", **EMPTY_MONEY
    )
    assert errors == {}
    gone, errors = create_product(
        session, code="G1", name="Удалённый Товар", category="Уход", **EMPTY_MONEY
    )
    assert errors == {}
    soft_delete_product(session, gone.id)

    page = client.get("/categories")
    assert page.status_code == 200
    assert "Остаётся Крем" in page.text
    assert "Удалённый Товар" not in page.text


def test_web_categories_page_empty_state(client, session, product):
    """Zero active products -> empty-state block, no table."""
    soft_delete_product(session, product.id)

    page = client.get("/categories")
    assert page.status_code == 200
    assert "Товаров пока нет" in page.text
    assert "<table>" not in page.text


def test_web_nav_has_categories_link(client):
    """Nav bar exposes the new /categories link from every page."""
    page = client.get("/products")
    assert page.status_code == 200
    assert 'href="/categories"' in page.text
    assert "Категории" in page.text


# --- Plan 07-02: minimum sale price guardrail schema/capture (PRICE-01) ---


def test_migration_0006_adds_min_sale_cents_column(tmp_path, monkeypatch):
    """Migration 0006: fresh upgrade adds a NULL min_sale_cents column."""
    db_file = tmp_path / "fresh.db"
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "0005")

    now = "2026-07-10T00:00:00+00:00"
    with closing(sqlite3.connect(db_file)) as conn:
        conn.execute(
            "INSERT INTO products (id, code, name, quantity, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("00000000-0000-4000-8000-000000000006", "6666", "Мин-Цена-Тест", 0, now, now),
        )
        conn.commit()

    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db_file)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
        assert "min_sale_cents" in cols

        (min_sale_cents,) = conn.execute(
            "SELECT min_sale_cents FROM products WHERE name = ?",
            ("Мин-Цена-Тест",),
        ).fetchone()
        assert min_sale_cents is None


def test_create_product_min_sale_cents_empty_is_none(session):
    """D-06: empty min_sale raw -> NULL column (no floor set)."""
    product, errors = create_product(
        session,
        code="1234",
        name="Помада",
        category="",
        **EMPTY_MONEY,
        min_sale_raw="",
    )
    assert errors == {}
    assert product is not None
    assert product.min_sale_cents is None


def test_create_product_min_sale_cents_explicit_zero_is_stored_as_zero(session):
    """Pitfall 1 (service level): an explicit "0" is stored as int 0, never None."""
    product, errors = create_product(
        session,
        code="1234",
        name="Помада",
        category="",
        **EMPTY_MONEY,
        min_sale_raw="0",
    )
    assert errors == {}
    assert product is not None
    assert product.min_sale_cents == 0


def test_create_product_rejects_negative_min_sale_price(session):
    """WR-04 reused: a negative minimum price is rejected with PRICE_ERROR."""
    product, errors = create_product(
        session,
        code="1234",
        name="Помада",
        category="",
        **EMPTY_MONEY,
        min_sale_raw="-5",
    )
    assert product is None
    assert "min_sale" in errors
    assert session.scalar(text("SELECT COUNT(*) FROM products")) == 0


def test_update_min_sale_price_change_records_price_change_op(session):
    """T-07-05: a min-price-only edit joins _PRICE_FIELDS and is audited."""
    product, errors = create_product(
        session, code="1234", name="Помада", category="", **EMPTY_MONEY
    )
    assert errors == {}
    updated, errors = update_product(
        session,
        product.id,
        code="1234",
        name="Помада",
        category="",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
        min_sale_raw="99,90",
    )
    assert errors == {}
    assert updated is not None
    ops = session.scalars(select(Operation).where(Operation.type == "price_change")).all()
    assert len(ops) == 1
    assert ops[0].payload == {"field": "min_sale_cents", "old_cents": None, "new_cents": 9990}
    session.expire_all()
    assert product.min_sale_cents == 9990


# --- Plan 07-02: product-form min-price field, end-to-end round-trip (PRICE-01) ---


def test_web_create_product_with_min_sale_price_round_trips(client, session):
    """Success criterion 4: a set min_sale round-trips through save and reload."""
    from app.models import Product

    response = client.post(
        "/products",
        data={
            "code": "MIN-1",
            "name": "Крем С Минимальной Ценой",
            "category": "",
            "cost": "",
            "sale": "",
            "catalog": "",
            "min_sale": "12,50",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    created = session.scalars(select(Product).where(Product.code == "MIN-1")).first()
    assert created is not None
    assert created.min_sale_cents == 1250

    edit_page = client.get(f"/products/{created.id}/edit")
    assert edit_page.status_code == 200
    assert "12,50" in edit_page.text


def test_web_create_product_min_sale_explicit_zero_round_trips(client, session):
    """Success criterion 4: an explicit 0 minimum price is NOT NULL."""
    from app.models import Product

    response = client.post(
        "/products",
        data={
            "code": "MIN-2",
            "name": "Крем С Нулевой Ценой",
            "category": "",
            "cost": "",
            "sale": "",
            "catalog": "",
            "min_sale": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    created = session.scalars(select(Product).where(Product.code == "MIN-2")).first()
    assert created is not None
    assert created.min_sale_cents == 0

    edit_page = client.get(f"/products/{created.id}/edit")
    assert edit_page.status_code == 200
    assert "0,00" in edit_page.text


def test_web_create_product_invalid_min_sale_rerenders_422(client, session):
    """Invalid min_sale -> 422 re-render with PRICE_ERROR; nothing persisted."""
    response = client.post(
        "/products",
        data={
            "code": "MIN-3",
            "name": "Тест",
            "category": "",
            "cost": "",
            "sale": "",
            "catalog": "",
            "min_sale": "abc",
        },
    )
    assert response.status_code == 422
    assert "Неверный формат цены" in response.text
    assert session.scalar(text("SELECT COUNT(*) FROM products WHERE code = 'MIN-3'")) == 0
