"""WH-01 executable contract: Warehouse model, migration 0007, service layer.

Naming convention (mirrors test_dictionary.py/test_catalog.py): route/e2e
tests are prefixed test_web_, everything else is service/schema level.
"""

import sqlite3
from contextlib import closing

from alembic.config import Config

from alembic import command
from app.config import settings
from app.core import new_id
from app.models import Batch, Operation, Product, Warehouse
from app.services.ledger import next_seq, record_operation
from app.services.warehouses import (
    NAME_REQUIRED_ERROR,
    WAREHOUSE_NOT_FOUND_ERROR,
    add_warehouse,
    list_warehouses,
    restore_warehouse,
    soft_delete_warehouse,
    update_warehouse,
)


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


def test_add_warehouse_creates_row(session):
    warehouse, errors = add_warehouse(
        session, name="  Главный склад  ", address="  ул. Ленина, 1  "
    )

    assert errors == {}
    assert warehouse is not None
    assert warehouse.name == "Главный склад"
    assert warehouse.address == "ул. Ленина, 1"
    assert len(warehouse.id) == 36


def test_add_warehouse_requires_name(session):
    warehouse, errors = add_warehouse(session, name="   ", address="")

    assert warehouse is None
    assert errors["name"] == NAME_REQUIRED_ERROR
    assert list_warehouses(session)["warehouses"] == []


def test_add_warehouse_allows_duplicate_names(session):
    first, errors_a = add_warehouse(session, name="Склад №1", address="")
    second, errors_b = add_warehouse(session, name="Склад №1", address="")

    assert errors_a == {}
    assert errors_b == {}
    assert first is not None
    assert second is not None
    assert first.id != second.id


def test_update_warehouse_edits_fields(session):
    warehouse, _ = add_warehouse(session, name="Старое имя", address="Старый адрес")

    updated, errors = update_warehouse(
        session, warehouse.id, name="Новое имя", address="Новый адрес"
    )

    assert errors == {}
    assert updated is not None
    assert updated.name == "Новое имя"
    assert updated.address == "Новый адрес"
    persisted = session.get(type(warehouse), warehouse.id)
    assert persisted.name == "Новое имя"
    assert persisted.address == "Новый адрес"


def test_update_warehouse_unknown_id_returns_error(session):
    updated, errors = update_warehouse(
        session, "00000000-0000-4000-8000-000000000099", name="X", address=""
    )

    assert updated is None
    assert errors == {"warehouse": WAREHOUSE_NOT_FOUND_ERROR}


def test_soft_delete_and_restore_roundtrip(session):
    # Two warehouses so neither is "last active" when one is soft-deleted.
    warehouse_a, _ = add_warehouse(session, name="Склад А", address="")
    add_warehouse(session, name="Склад Б", address="")

    deleted, warning = soft_delete_warehouse(session, warehouse_a.id, confirm=False)

    assert deleted is True
    assert warning == {}
    assert warehouse_a.deleted_at
    # D-14: the default list view now HIDES deleted rows.
    default_rows = list_warehouses(session)["warehouses"]
    assert warehouse_a.id not in [w.id for w in default_rows]
    # status="all" still reaches it (the resolved restore path).
    all_rows = list_warehouses(session, status="all")["warehouses"]
    assert warehouse_a.id in [w.id for w in all_rows]

    restore_warehouse(session, warehouse_a.id)

    assert warehouse_a.deleted_at is None


def test_list_warehouses_default_hides_deleted(session):
    active, _ = add_warehouse(session, name="Активный склад", address="")
    deleted, _ = add_warehouse(session, name="Удалённый склад", address="")
    soft_delete_warehouse(session, deleted.id, confirm=True)

    result = list_warehouses(session)

    ids = [w.id for w in result["warehouses"]]
    assert active.id in ids
    assert deleted.id not in ids


def test_list_warehouses_status_all_and_deleted(session):
    active, _ = add_warehouse(session, name="Активный склад", address="")
    deleted, _ = add_warehouse(session, name="Удалённый склад", address="")
    soft_delete_warehouse(session, deleted.id, confirm=True)

    all_result = list_warehouses(session, status="all")
    deleted_result = list_warehouses(session, status="deleted")

    all_ids = [w.id for w in all_result["warehouses"]]
    assert active.id in all_ids
    assert deleted.id in all_ids
    deleted_ids = [w.id for w in deleted_result["warehouses"]]
    assert deleted_ids == [deleted.id]


def test_list_warehouses_filters_by_name_and_address(session):
    add_warehouse(session, name="Главный склад", address="ул. Ленина, 1")
    add_warehouse(session, name="Запасной склад", address="ул. Мира, 5")

    by_name = list_warehouses(session, name="главн")["warehouses"]
    assert [w.name for w in by_name] == ["Главный склад"]

    by_address = list_warehouses(session, address="ленина")["warehouses"]
    assert [w.name for w in by_address] == ["Главный склад"]


def test_list_warehouses_sort_name_asc_desc(session):
    add_warehouse(session, name="Бета склад", address="")
    add_warehouse(session, name="Альфа склад", address="")

    asc = list_warehouses(session, status="all", sort="name_asc")["warehouses"]
    assert [w.name for w in asc] == ["Альфа склад", "Бета склад"]

    desc = list_warehouses(session, status="all", sort="name_desc")["warehouses"]
    assert [w.name for w in desc] == ["Бета склад", "Альфа склад"]


def test_soft_delete_warehouse_blocked_when_stock_positive(session, batch):
    batch.quantity = 5
    session.commit()

    deleted, warning = soft_delete_warehouse(session, batch.warehouse_id, confirm=False)

    assert deleted is False
    assert warning == {"stock": 5}
    warehouse = session.get(Warehouse, batch.warehouse_id)
    assert warehouse.deleted_at is None


def test_soft_delete_warehouse_stock_guard_runs_before_last_active_guard(session, batch):
    # `batch`'s `warehouse` fixture is the ONLY warehouse in this session AND
    # carries stock — the non-overridable stock guard (checked first) must
    # win over the existing last-active guard.
    batch.quantity = 3
    session.commit()

    deleted, warning = soft_delete_warehouse(session, batch.warehouse_id, confirm=False)

    assert deleted is False
    assert "stock" in warning
    assert "warehouse" not in warning


def test_delete_last_active_warehouse_warns_then_allows(session):
    only, _ = add_warehouse(session, name="Единственный склад", address="")

    deleted, warning = soft_delete_warehouse(session, only.id, confirm=False)

    assert deleted is False
    assert warning == {"warehouse": only}
    assert only.deleted_at is None  # zero writes on the blocked path

    deleted, warning = soft_delete_warehouse(session, only.id, confirm=True)

    assert deleted is True
    assert warning == {}
    assert only.deleted_at is not None


def test_restore_warehouse_is_idempotent_when_already_active(session):
    warehouse, _ = add_warehouse(session, name="Активный склад", address="")

    restore_warehouse(session, warehouse.id)

    assert warehouse.deleted_at is None


# --- D-03: item_count (distinct products with stock > 0) ---


def test_list_warehouses_item_count_counts_distinct_products_with_stock(session, warehouse):
    product_a = Product(id=new_id(), code="A-001", name="Товар A", quantity=0)
    product_b = Product(id=new_id(), code="B-001", name="Товар B", quantity=0)
    product_c = Product(id=new_id(), code="C-001", name="Товар C", quantity=0)
    session.add_all([product_a, product_b, product_c])
    session.add_all(
        [
            Batch(
                id=new_id(),
                product_id=product_a.id,
                warehouse_id=warehouse.id,
                quantity=3,
            ),
            Batch(
                id=new_id(),
                product_id=product_b.id,
                warehouse_id=warehouse.id,
                quantity=2,
            ),
            Batch(
                id=new_id(),
                product_id=product_c.id,
                warehouse_id=warehouse.id,
                quantity=0,
            ),
        ]
    )
    session.commit()

    rows = list_warehouses(session)["warehouses"]

    row = next(w for w in rows if w.id == warehouse.id)
    assert row.item_count == 2


def test_list_warehouses_item_count_two_batches_same_product_counts_once(session, warehouse):
    product = Product(id=new_id(), code="A-002", name="Товар A2", quantity=0)
    session.add(product)
    session.add_all(
        [
            Batch(
                id=new_id(),
                product_id=product.id,
                warehouse_id=warehouse.id,
                quantity=5,
                expiry="2026-08-01",
            ),
            Batch(
                id=new_id(),
                product_id=product.id,
                warehouse_id=warehouse.id,
                quantity=1,
                expiry="2026-12-01",
            ),
        ]
    )
    session.commit()

    rows = list_warehouses(session)["warehouses"]

    row = next(w for w in rows if w.id == warehouse.id)
    assert row.item_count == 1


def test_list_warehouses_item_count_zero_for_warehouse_with_no_batches(session):
    warehouse, _ = add_warehouse(session, name="Пустой склад", address="")

    rows = list_warehouses(session)["warehouses"]

    row = next(w for w in rows if w.id == warehouse.id)
    assert row.item_count == 0


# --- D-04: last_receipt (grouped outerjoin, receipt-type only) ---


def test_list_warehouses_last_receipt_date_uses_grouped_outerjoin(session, product, warehouse):
    batch = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0)
    session.add(batch)
    session.commit()

    earlier = Operation(
        id=new_id(),
        type="receipt",
        product_id=product.id,
        qty_delta=4,
        batch_id=batch.id,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at="2026-01-01T00:00:00Z",
        created_by=settings.operator_name,
    )
    session.add(earlier)
    session.commit()
    later = Operation(
        id=new_id(),
        type="receipt",
        product_id=product.id,
        qty_delta=6,
        batch_id=batch.id,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at="2026-02-01T00:00:00Z",
        created_by=settings.operator_name,
    )
    session.add(later)
    session.commit()

    rows = list_warehouses(session)["warehouses"]

    row = next(w for w in rows if w.id == warehouse.id)
    assert row.last_receipt == "2026-02-01T00:00:00Z"


def test_list_warehouses_last_receipt_none_when_never_received(session):
    warehouse, _ = add_warehouse(session, name="Никогда не получавший склад", address="")

    rows = list_warehouses(session)["warehouses"]

    row = next(w for w in rows if w.id == warehouse.id)
    assert row.last_receipt is None


def test_list_warehouses_last_receipt_ignores_transfer_only_stock(session, product, warehouse):
    batch = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=3)
    session.add(batch)
    session.commit()

    transfer_op = Operation(
        id=new_id(),
        type="transfer",
        product_id=product.id,
        qty_delta=3,
        batch_id=batch.id,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at="2026-03-01T00:00:00Z",
        created_by=settings.operator_name,
    )
    session.add(transfer_op)
    session.commit()

    rows = list_warehouses(session)["warehouses"]

    row = next(w for w in rows if w.id == warehouse.id)
    assert row.last_receipt is None


# --- Web slice (routes + templates, Plan 08-02) ---
#
# Note: tests/conftest.py's `engine` fixture builds schema via
# `Base.metadata.create_all` (per 08-VALIDATION.md Wave 0: "No new fixtures
# needed"), which does NOT run the Alembic seed migration. So the `client`
# fixture starts with ZERO warehouses, unlike a real post-migration DB —
# tests below create their own warehouses instead of relying on the
# migration-seeded "Склад по умолчанию" row.


def test_web_warehouses_page_renders(client):
    response = client.get("/warehouses")
    assert response.status_code == 200
    assert "Склады" in response.text
    assert "Добавить склад" in response.text
    # No warehouses exist yet in this test DB (create_all, no seed) -> empty state.
    assert "Складов пока нет" in response.text


def test_web_quick_deleted_warehouse_hidden_by_default_reachable_via_status_filter(
    client, session
):
    # Two active warehouses so the one being deleted is not the last active one.
    add_warehouse(session, name="Склад А", address="")
    target, _ = add_warehouse(session, name="Склад на удаление", address="")

    # Zero stock, not last-active -> this is now a terminal-success delete
    # (Plan 20-02: POST /warehouses/{id}/delete redirect-after-success shape).
    response = client.post(f"/warehouses/{target.id}/delete")

    assert response.status_code == 200
    assert "HX-Redirect" in response.headers
    assert response.headers["HX-Redirect"] == "/warehouses"

    default_view = client.get("/warehouses")
    assert "Склад на удаление" not in default_view.text

    deleted_view = client.get("/warehouses", params={"status": "deleted"})
    assert "Склад на удаление" in deleted_view.text
    assert "Восстановить" in deleted_view.text


def test_web_warehouses_status_all_shows_active_and_deleted(client, session):
    add_warehouse(session, name="Активный склад", address="")
    deleted, _ = add_warehouse(session, name="Удалённый склад", address="")
    soft_delete_warehouse(session, deleted.id, confirm=True)

    response = client.get("/warehouses", params={"status": "all"})

    assert response.status_code == 200
    assert "Активный склад" in response.text
    assert "Удалённый склад" in response.text
    assert "Восстановить" in response.text


def test_web_warehouses_sort_name_desc(client, session):
    add_warehouse(session, name="Альфа склад", address="")
    add_warehouse(session, name="Бета склад", address="")

    response = client.get("/warehouses", params={"sort": "name_desc"})

    assert response.status_code == 200
    assert response.text.index("Бета склад") < response.text.index("Альфа склад")


def test_web_warehouses_filter_by_name(client, session):
    add_warehouse(session, name="Главный склад", address="")
    add_warehouse(session, name="Запасной склад", address="")

    response = client.get("/warehouses", params={"name": "главн"})

    assert response.status_code == 200
    assert "Главный склад" in response.text
    assert "Запасной склад" not in response.text


def test_web_nav_has_warehouses_link(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/warehouses"' in response.text
    assert "Склады" in response.text


# --- Dedicated add/edit/delete pages (Plan 20-02, WH-02/WH-03/D-01/D-02) ---


def test_web_warehouse_new_renders_add_form(client):
    response = client.get("/warehouses/new")

    assert response.status_code == 200
    assert "Новый склад" in response.text


def test_web_warehouse_edit_renders_existing_values(client, session):
    warehouse, _ = add_warehouse(session, name="Склад для правки", address="ул. Тестовая, 1")

    response = client.get(f"/warehouses/{warehouse.id}/edit")

    assert response.status_code == 200
    assert "Редактирование склада" in response.text
    assert "Склад для правки" in response.text
    assert "ул. Тестовая, 1" in response.text


def test_web_warehouse_edit_unknown_id_404s(client):
    response = client.get("/warehouses/00000000-0000-4000-8000-000000000099/edit")

    assert response.status_code == 404


def test_web_warehouse_edit_soft_deleted_id_404s(client, session):
    add_warehouse(session, name="Склад А", address="")
    target, _ = add_warehouse(session, name="Склад на удаление", address="")
    soft_delete_warehouse(session, target.id, confirm=True)

    response = client.get(f"/warehouses/{target.id}/edit")

    assert response.status_code == 404


def test_web_warehouse_update_soft_deleted_id_rejected(client, session):
    add_warehouse(session, name="Склад А", address="")
    target, _ = add_warehouse(session, name="Склад на удаление", address="")
    soft_delete_warehouse(session, target.id, confirm=True)

    response = client.post(
        f"/warehouses/{target.id}",
        data={"name": "Переименован после удаления", "address": ""},
        follow_redirects=False,
    )

    assert response.status_code == 404
    assert target.name == "Склад на удаление"


def test_web_warehouse_create_redirects_to_list(client):
    response = client.post(
        "/warehouses", data={"name": "Новый склад X", "address": ""}, follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/warehouses"


def test_web_warehouse_add_invalid_returns_422_form(client):
    response = client.post("/warehouses", data={"name": "  ", "address": ""})

    assert response.status_code == 422
    assert "Укажите название склада." in response.text
    assert "Новый склад" in response.text


def test_web_warehouse_update_redirects_to_list(client, session):
    warehouse, _ = add_warehouse(session, name="Старое имя", address="")

    response = client.post(
        f"/warehouses/{warehouse.id}",
        data={"name": "Новое имя", "address": "Новый адрес"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/warehouses"


def test_web_warehouse_delete_success_redirects(client, session):
    add_warehouse(session, name="Склад А", address="")
    target, _ = add_warehouse(session, name="Склад на удаление", address="")

    response = client.post(f"/warehouses/{target.id}/delete")

    assert response.status_code == 200
    assert response.headers["HX-Redirect"] == "/warehouses"


def test_web_warehouse_delete_stock_blocked_renders_in_wrap(client, session, batch):
    batch.quantity = 5
    session.commit()

    response = client.post(f"/warehouses/{batch.warehouse_id}/delete")

    assert response.status_code == 200
    assert "Нельзя удалить: на складе есть остаток" in response.text
    assert "HX-Redirect" not in response.headers
    assert "Удалить склад" in response.text


def test_web_warehouse_delete_last_active_warns_then_confirm_redirects(client, session):
    only, _ = add_warehouse(session, name="Единственный склад", address="")

    response = client.post(f"/warehouses/{only.id}/delete")

    assert response.status_code == 200
    assert "Это последний активный склад" in response.text
    assert "HX-Redirect" not in response.headers

    confirm_response = client.post(f"/warehouses/{only.id}/delete", data={"confirm": "1"})

    assert confirm_response.status_code == 200
    assert confirm_response.headers["HX-Redirect"] == "/warehouses"


# --- Plain picker restructure (Plan 20-03, WH-01/D-01) ---


def test_web_warehouses_page_shows_item_count_and_last_receipt_columns(client, session):
    warehouse, _ = add_warehouse(session, name="Склад с товаром", address="")
    product = Product(id=new_id(), code="WH3-001", name="Товар склада", quantity=0)
    session.add(product)
    session.commit()
    batch = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0)
    session.add(batch)
    session.commit()
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=1000,
        unit_price_cents=1500,
        batch_id=batch.id,
    )

    response = client.get("/warehouses")

    assert response.status_code == 200
    assert "Товаров" in response.text
    assert "Последняя приёмка" in response.text
    row = response.text.split("Склад с товаром")[1].split("</tr>")[0]
    assert '<td class="num">1</td>' in row
    assert "—" not in row


def test_web_warehouses_row_action_is_edit_link_not_inline_buttons(client, session):
    warehouse, _ = add_warehouse(session, name="Склад для проверки", address="")

    response = client.get("/warehouses")

    assert response.status_code == 200
    assert f'href="/warehouses/{warehouse.id}/edit"' in response.text
    row = response.text.split("Склад для проверки")[1].split("</tr>")[0]
    assert 'name="name"' not in row
    assert ">Удалить<" not in row
    assert ">Сохранить<" not in row


def test_web_warehouses_page_preserves_filter_sort_status_bar_after_restructure(client, session):
    """RESEARCH Pitfall 1: D-01's restructure must not strip Phase 14's list chrome."""
    add_warehouse(session, name="Склад для проверки чекбоксов", address="")

    response = client.get("/warehouses")

    assert response.status_code == 200
    assert 'class="filter-bar"' in response.text
    assert 'name="sort"' in response.text
    assert 'name="name"' in response.text
    assert 'name="address"' in response.text
    assert 'name="status"' in response.text
