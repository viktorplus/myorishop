"""RCP-01/RCP-02 executable contract: goods receipt slice (Plans 03-01/03-02).

Covers the receipt transaction (D-01: one entry = one receipt op with
qty_delta > 0), the save-and-next form loop (D-02: fresh form + focus
hook after success), the recent-receipts list (D-04: last 10, newest
first, hx-swap-oob refresh), product auto-creation for unknown codes
(D-05: product_created + receipt in ONE transaction), price snapshots
on the op (D-06: unit_cost/unit_price columns + payload.catalog_cents)
and optional prices (PD-8: empty string -> NULL, card untouched).

Plan 03-02 adds (RCP-02): the /receipts/lookup pre-fill (D-03: product
card fills name + EMPTY price fields, dictionary fills name only, 204
otherwise; PD-10: per-field oob fills skip operator-typed values) and
card price sync inside register_receipt (D-07: one price_change op per
CHANGED non-empty field; PD-9: a typed name never renames an existing
product).

Naming convention (used by -k filters): route/e2e tests are prefixed
test_web_, everything else is service level. "recent"/"nav" select the
03-01 Task 3 slice; "lookup"/"price_sync" select the 03-02 slice.
"""

from sqlalchemy import select

from app.core import new_id
from app.models import Batch, CatalogPrice, Operation, Product, Warehouse
from app.services import catalog
from app.services.catalog import create_product, soft_delete_product
from app.services.dictionary import add_entry
from app.services.ledger import compute_stock, record_operation
from app.services.receipts import (
    lookup_prefill,
    parse_optional_expiry,
    recent_receipts,
    register_receipt,
)

EMPTY_MONEY = {"cost_raw": "", "sale_raw": "", "catalog_raw": ""}
# Plan 09-02: the default new-batch path used by every previously batch-less
# service-level receipt test (warehouse_id supplied per test via the fixture).
NEW_BATCH = {"batch_choice": "new"}


# --- Service level (D-01 / D-05 / D-06 / PD-8) ---


def test_register_receipt_increases_stock_for_existing_product(session, product, warehouse):
    """D-01/D-06: one receipt op, qty_delta > 0, prices snapshotted on the op."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="что угодно",
        qty_raw="5",
        cost_raw="10",
        sale_raw="12,50",
        catalog_raw="15",
        warehouse_id=warehouse.id,
        batch_choice="new",
    )
    assert errors == {}
    assert result

    assert product.quantity == 5
    assert compute_stock(session, product.id) == 5

    ops = session.scalars(select(Operation).where(Operation.type == "receipt")).all()
    assert len(ops) == 1
    op = ops[0]
    assert op.qty_delta == 5
    assert op.unit_cost_cents == 1000
    assert op.unit_price_cents == 1250
    assert op.payload["catalog_cents"] == 1500
    assert len(op.id) == 36
    # NOTE: no assertions about the product card's price fields — card
    # price sync is Plan 03-02 scope.


def test_register_receipt_autocreates_product_for_unknown_code(session, warehouse):
    """D-05: unknown code -> new product card + product_created op, atomically."""
    result, errors = register_receipt(
        session,
        code="9999",
        name="Губная помада",
        qty_raw="3",
        cost_raw="5",
        sale_raw="",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
    )
    assert errors == {}
    assert result

    created = session.scalars(select(Product).where(Product.code == "9999")).one()
    assert created.name == "Губная помада"
    assert created.name_lc == "губная помада"
    assert created.quantity == 3
    assert created.cost_cents == 500
    assert created.sale_cents is None

    ops = session.scalars(select(Operation)).all()
    assert len(ops) == 2
    by_type = {op.type: op for op in ops}
    assert by_type["product_created"].qty_delta == 0
    assert by_type["product_created"].payload == {"code": "9999", "name": "Губная помада"}
    assert by_type["receipt"].qty_delta == 3


def test_register_receipt_requires_code_name_and_positive_int_qty(session, product, warehouse):
    """Blank code/name and non-positive-int quantity -> RU errors, zero writes."""
    cases = [
        ({"code": "  ", "name": "Крем", "qty_raw": "1"}, "code", "Укажите код товара."),
        ({"code": "TEST-001", "name": "  ", "qty_raw": "1"}, "name", "Укажите название."),
    ]
    for qty_raw in ("", "0", "-2", "abc", "1.5"):
        cases.append(
            (
                {"code": "TEST-001", "name": "Крем", "qty_raw": qty_raw},
                "quantity",
                "Укажите количество — целое число больше нуля.",
            )
        )

    products_before = len(session.scalars(select(Product)).all())
    for kwargs, field, message in cases:
        result, errors = register_receipt(
            session, **kwargs, **EMPTY_MONEY, warehouse_id=warehouse.id, **NEW_BATCH
        )
        assert result is None, kwargs
        assert errors[field] == message, kwargs

    assert session.scalars(select(Operation)).all() == []
    assert len(session.scalars(select(Product)).all()) == products_before


def test_register_receipt_rejects_bad_money(session, product, warehouse):
    """Garbage money -> the shared catalog PRICE_ERROR text, nothing written."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="1",
        cost_raw="abc",
        sale_raw="",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
    )
    assert result is None
    assert errors["cost"] == catalog.PRICE_ERROR
    assert session.scalars(select(Operation)).all() == []


def test_register_receipt_soft_deleted_code_creates_new_product(session, warehouse):
    """Pitfall 5: a soft-deleted product's code auto-creates a NEW card."""
    old, errors = create_product(
        session, code="DEAD-01", name="Старый товар", category="", **EMPTY_MONEY
    )
    assert errors == {}
    old_id = old.id
    soft_delete_product(session, old_id)

    result, errors = register_receipt(
        session,
        code="DEAD-01",
        name="Новый товар",
        qty_raw="4",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
    )
    assert errors == {}
    assert result

    fresh = session.scalars(
        select(Product).where(Product.code == "DEAD-01", Product.deleted_at.is_(None))
    ).one()
    assert fresh.id != old_id
    assert fresh.quantity == 4


def test_register_receipt_empty_prices_are_null(session, product, warehouse):
    """PD-8 / A3: empty price strings -> NULL op columns and NULL payload price."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="2",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
    )
    assert errors == {}
    assert result

    op = session.scalars(select(Operation).where(Operation.type == "receipt")).one()
    assert op.unit_cost_cents is None
    assert op.unit_price_cents is None
    assert op.payload["catalog_cents"] is None


# --- Plan 09-02: batch birth path (D-01/D-02, LOT-03, WH-02, LOT-04) ---

EXPIRY_ERROR = "Укажите срок годности в формате ГГГГ-ММ-ДД."


def test_parse_optional_expiry_empty_valid_and_malformed():
    """LOT-03/V5: empty -> None; valid ISO normalizes; malformed -> RU error."""
    errors: dict[str, str] = {}
    assert parse_optional_expiry("", errors, "expiry") is None
    assert errors == {}
    assert parse_optional_expiry(" 2026-05-01 ", errors, "expiry") == "2026-05-01"
    assert errors == {}
    assert parse_optional_expiry("2026-13-40", errors, "expiry") is None
    assert errors["expiry"] == EXPIRY_ERROR


def test_register_receipt_new_batch_stores_location_expiry_and_price(
    session, product, warehouse
):
    """WH-02/LOT-03/D-02: new batch keeps location+expiry+comment and snapshots the sale price."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="6",
        cost_raw="",
        sale_raw="12,50",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
        expiry_raw="2026-05-01",
        location_raw="стеллаж А3",
        comment_raw="первая партия",
    )
    assert errors == {}
    assert result
    batch = result["batch"]
    assert batch.location == "стеллаж А3"  # WH-02
    assert batch.expiry == "2026-05-01"  # LOT-03
    assert batch.comment == "первая партия"  # LOT-04
    assert batch.warehouse_id == warehouse.id
    # D-02: price snapshots the entered «Цена продажи» — no separate batch price input.
    assert batch.price_cents == 1250
    assert batch.quantity == 6
    assert batch.is_legacy == 0

    op = session.scalars(select(Operation).where(Operation.type == "receipt")).one()
    assert op.batch_id == batch.id


def test_register_receipt_topup_freezes_batch_price(session, product, warehouse):
    """D-02: a top-up increases the chosen batch quantity but never rewrites its frozen price."""
    first, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="4",
        cost_raw="",
        sale_raw="10,00",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
    )
    assert errors == {}
    batch = first["batch"]
    assert batch.price_cents == 1000
    assert batch.quantity == 4

    # Top up the SAME batch with a different typed sale price.
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="3",
        cost_raw="",
        sale_raw="99,00",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice=batch.id,
    )
    assert errors == {}
    assert result
    session.refresh(batch)
    assert batch.quantity == 7  # 4 + 3 attributed to the chosen batch
    assert batch.price_cents == 1000  # frozen — NOT rewritten to 9900


def test_register_receipt_rejects_foreign_product_batch(session, product, warehouse):
    """Pitfall 10 / T-09-04: another product's batch -> rejected, zero writes."""
    other = Product(id=new_id(), code="OTHER-1", name="Другой", quantity=0)
    session.add(other)
    session.commit()
    foreign = Batch(
        id=new_id(), product_id=other.id, warehouse_id=warehouse.id, quantity=0
    )
    session.add(foreign)
    session.commit()

    ops_before = len(session.scalars(select(Operation)).all())
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="2",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice=foreign.id,
    )
    assert result is None
    assert "batch_choice" in errors
    assert len(session.scalars(select(Operation)).all()) == ops_before


def test_register_receipt_rejects_foreign_warehouse_batch(session, product, warehouse):
    """Pitfall 10: a batch of the same product but a different warehouse -> rejected."""
    other_wh = Warehouse(id=new_id(), name="Другой склад")
    session.add(other_wh)
    session.commit()
    other_batch = Batch(
        id=new_id(), product_id=product.id, warehouse_id=other_wh.id, quantity=0
    )
    session.add(other_batch)
    session.commit()

    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="2",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice=other_batch.id,
    )
    assert result is None
    assert "batch_choice" in errors
    assert session.scalars(select(Operation)).all() == []


def test_register_receipt_malformed_expiry_error(session, product, warehouse):
    """LOT-03: a malformed expiry on the new-batch path -> RU error, zero writes."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="2",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
        expiry_raw="2026-13-40",
    )
    assert result is None
    assert errors["expiry"] == EXPIRY_ERROR
    assert session.scalars(select(Operation)).all() == []


def test_register_receipt_zero_warehouses_rejected_server_side(session, product):
    """D-02 / T-09-05: no active warehouses -> blocking error even if a stale form posts a wh id."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="2",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
        warehouse_id="00000000-0000-4000-8000-000000000010",
        batch_choice="new",
    )
    assert result is None
    assert "warehouse" in errors
    assert session.scalars(select(Operation)).all() == []


# --- Web slice (routes + templates) ---


def test_web_receipt_page_renders_form(client):
    """/receipts/new: RU title, field set per UI-SPEC, auto-create notice."""
    response = client.get("/receipts/new")
    assert response.status_code == 200
    assert "Приход товара" in response.text
    assert "Сохранить приход" in response.text
    assert 'id="code"' in response.text
    assert "autofocus" in response.text
    assert 'name="qty"' in response.text
    assert 'inputmode="numeric"' in response.text
    assert 'inputmode="decimal"' in response.text
    assert "Закупочная цена" in response.text
    assert "Цена продажи" in response.text
    assert "Цена по каталогу" in response.text
    assert "(необязательно)" in response.text
    notice = "Если товара с таким кодом ещё нет — карточка будет создана автоматически."
    assert notice in response.text


def test_web_receipt_post_success_returns_fresh_form(client, warehouse):
    """D-02: success -> 200 fresh form partial + success line + focus hook."""
    response = client.post(
        "/receipts",
        data={
            "code": "9999",
            "name": "Крем",
            "qty": "2",
            "cost": "",
            "sale": "",
            "catalog": "",
            "warehouse_id": warehouse.id,
            "batch_choice": "new",
        },
    )
    assert response.status_code == 200
    assert "Приход сохранён: Крем — 2 шт." in response.text
    assert 'id="receipt-form-wrap"' in response.text
    assert "getElementById('code').focus()" in response.text
    assert "<html" not in response.text  # partial only, never a full page
    assert 'value="9999"' not in response.text  # form cleared for the next item


def test_web_receipt_post_validation_422_preserves_input(client, product, warehouse):
    """Validation failure -> 422 partial with RU error and echoed input."""
    response = client.post(
        "/receipts",
        data={
            "code": "TEST-001",
            "name": "Тестовый товар",
            "qty": "0",
            "cost": "",
            "sale": "",
            "catalog": "",
            "warehouse_id": warehouse.id,
            "batch_choice": "new",
        },
    )
    assert response.status_code == 422
    assert "Укажите количество — целое число больше нуля." in response.text
    assert 'value="TEST-001"' in response.text
    assert 'value="Тестовый товар"' in response.text


def test_web_receipt_unexpected_error_shows_block(client, monkeypatch):
    """Server failure -> 422 with the UI-SPEC error block, never a raw 500."""
    import app.routes.receipts as receipts_routes

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(receipts_routes, "register_receipt", boom)
    response = client.post(
        "/receipts",
        data={"code": "9999", "name": "Крем", "qty": "2", "cost": "", "sale": "", "catalog": ""},
    )
    assert response.status_code == 422
    assert "Не удалось сохранить. Проверьте данные и попробуйте ещё раз." in response.text


def test_web_receipt_survives_unexpected_error(client, session, product, warehouse, monkeypatch):
    """CR-01: an unexpected exception that leaves the Session needing a
    rollback() must not crash via an unhandled PendingRollbackError when the
    except block re-queries the (now-tainted) session for the error context.

    A failed flush (duplicate primary key) is what genuinely poisons a
    SQLAlchemy Session — mirroring returns.py's CR-03 regression test."""
    from sqlalchemy.exc import IntegrityError

    import app.routes.receipts as receipts_routes

    def _boom(*args, **kwargs):
        # Taint the session with a failed flush, mirroring a session left
        # needing rollback() after register_receipt's own commit fails for a
        # reason other than the IntegrityError it already handles.
        session.add(Product(id=product.id, code="DUP", name="dup", quantity=0))
        try:
            session.flush()
        except IntegrityError:
            pass
        raise RuntimeError("boom")

    monkeypatch.setattr(receipts_routes, "register_receipt", _boom)
    response = client.post(
        "/receipts",
        data={
            "code": "9999",
            "name": "Крем",
            "qty": "2",
            "cost": "",
            "sale": "",
            "catalog": "",
            "warehouse_id": warehouse.id,
            "batch_choice": "new",
        },
    )
    assert response.status_code == 422
    assert "Не удалось сохранить" in response.text


# --- Recent receipts + nav (Task 3 slice — D-04) ---


def test_recent_receipts_newest_first_capped_at_ten(session, product):
    """D-04: last 10 receipt ops, newest first (created_at desc, seq desc)."""
    warehouse = Warehouse(id=new_id(), name="Склад")
    session.add(warehouse)
    session.flush()
    batch = Batch(
        id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0
    )
    session.add(batch)
    session.flush()
    for i in range(12):
        record_operation(
            session,
            type_="receipt",
            product_id=product.id,
            qty_delta=i + 1,
            payload={"catalog_cents": None},
            batch_id=batch.id,
        )

    rows = recent_receipts(session)
    assert len(rows) == 10
    assert set(rows[0].keys()) == {"op", "product"}
    # Newest first: the last recorded op has the highest seq.
    assert rows[0]["op"].seq == 12
    assert rows[0]["op"].qty_delta == 12
    assert rows[0]["product"].id == product.id


def test_web_recent_receipts_empty_state(client):
    """No receipts yet -> heading + RU empty-state copy."""
    response = client.get("/receipts/new")
    assert response.status_code == 200
    assert "Последние приходы" in response.text
    empty_state = "Приходов пока нет. Введите код товара, чтобы оприходовать первую позицию."
    assert empty_state in response.text


def test_web_recent_receipts_lists_saved_receipt(client, warehouse):
    """After a save the table shows RU headers plus the saved name/quantity."""
    response = client.post(
        "/receipts",
        data={
            "code": "9999",
            "name": "Губная помада",
            "qty": "7",
            "cost": "",
            "sale": "",
            "catalog": "",
            "warehouse_id": warehouse.id,
            "batch_choice": "new",
        },
    )
    assert response.status_code == 200

    page = client.get("/receipts/new")
    assert page.status_code == 200
    for header in ("Когда", "Код", "Название", "Кол-во"):
        assert header in page.text
    assert "Губная помада" in page.text
    assert ">7<" in page.text


def test_web_recent_receipts_oob_row_in_post_response(client, warehouse):
    """D-04: the POST success response refreshes the list out-of-band."""
    response = client.post(
        "/receipts",
        data={
            "code": "9999",
            "name": "Крем для рук",
            "qty": "2",
            "cost": "",
            "sale": "",
            "catalog": "",
            "warehouse_id": warehouse.id,
            "batch_choice": "new",
        },
    )
    assert response.status_code == 200
    assert 'id="recent-receipts"' in response.text
    assert 'hx-swap-oob="true"' in response.text
    assert "Крем для рук" in response.text


def test_web_nav_has_receipts_link(client):
    """Nav gains the receipts entry: Приход -> /receipts/new."""
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/receipts/new"' in response.text
    assert "Приход" in response.text


# --- Plan 03-02: card price sync inside register_receipt (D-07 / PD-8 / PD-9) ---

CARD_HINT = "Данные подставлены из карточки товара — новые цены обновят карточку."
DICT_HINT = "Название подставлено из справочника — можно изменить."
CATALOG_FILL_HINT = "Цена и название подставлены из каталога — можно изменить."


def test_price_sync_updates_card_and_writes_ops(session, product, warehouse):
    """D-07: one price_change op per CHANGED field, old snapshotted BEFORE mutation."""
    product.cost_cents = 100
    product.sale_cents = None
    product.catalog_cents = 300
    session.commit()

    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Тестовый товар",
        qty_raw="1",
        cost_raw="2,00",
        sale_raw="5,00",
        catalog_raw="3,00",
        warehouse_id=warehouse.id,
        batch_choice="new",
    )
    assert errors == {}
    assert result

    assert product.cost_cents == 200
    assert product.sale_cents == 500
    assert product.catalog_cents == 300

    ops = session.scalars(select(Operation)).all()
    price_ops = {op.payload["field"]: op for op in ops if op.type == "price_change"}
    # catalog price unchanged (300 -> 300): NO price_change op for it.
    assert set(price_ops) == {"cost_cents", "sale_cents"}
    assert price_ops["cost_cents"].payload == {
        "field": "cost_cents",
        "old_cents": 100,
        "new_cents": 200,
    }
    assert price_ops["sale_cents"].payload == {
        "field": "sale_cents",
        "old_cents": None,
        "new_cents": 500,
    }
    receipt_ops = [op for op in ops if op.type == "receipt"]
    assert len(receipt_ops) == 1
    # 2 price_change + 1 receipt, all landed in the SAME committed transaction.
    assert len(ops) == 3


def test_price_sync_empty_fields_leave_card_untouched(session, product, warehouse):
    """PD-8: empty inputs never clear card prices; receipt op still written."""
    product.cost_cents = 100
    product.sale_cents = 250
    product.catalog_cents = 300
    session.commit()

    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Тестовый товар",
        qty_raw="2",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
    )
    assert errors == {}
    assert result

    assert product.cost_cents == 100
    assert product.sale_cents == 250
    assert product.catalog_cents == 300

    ops = session.scalars(select(Operation)).all()
    assert [op.type for op in ops] == ["receipt"]
    op = ops[0]
    assert op.unit_cost_cents is None
    assert op.unit_price_cents is None
    assert op.payload["catalog_cents"] is None


def test_price_sync_ignores_name_for_existing_product(session, product, warehouse):
    """PD-9: a typed name never renames an existing product, no product_edited op."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Другое имя",
        qty_raw="1",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
    )
    assert errors == {}
    assert result

    session.refresh(product)
    assert product.name == "Тестовый товар"
    edited = session.scalars(
        select(Operation).where(Operation.type == "product_edited")
    ).all()
    assert edited == []


# --- Plan 12-01: lookup_prefill() source=="catalog" branch (D-01/D-02/D-03) ---


def _catalog_price(code, consumer=None, consultant=None):
    return CatalogPrice(
        id=new_id(),
        code=code,
        year=2026,
        number=1,
        consumer_cents=consumer,
        consultant_cents=consultant,
    )


def test_lookup_prefill_catalog_source_dictionary_name_only(session):
    """D-01: unknown code, Dictionary match only -> catalog source, prices all None."""
    add_entry(session, code="4321", name="Тушь")

    result = lookup_prefill(session, "4321")

    assert result == {
        "source": "catalog",
        "name": "Тушь",
        "prices": {"cost": None, "catalog": None, "sale": None},
    }


def test_lookup_prefill_catalog_source_price_only(session):
    """D-01: unknown code, CatalogPrice match only -> name None, cost/catalog filled."""
    session.add(_catalog_price("5555", consumer=1500, consultant=900))
    session.commit()

    result = lookup_prefill(session, "5555")

    assert result == {
        "source": "catalog",
        "name": None,
        "prices": {"cost": 900, "catalog": 1500, "sale": 1500},
    }


def test_lookup_prefill_catalog_source_combines_dictionary_and_price(session):
    """D-01: both a Dictionary entry AND a CatalogPrice row -> combined dict."""
    add_entry(session, code="6666", name="Помада")
    session.add(_catalog_price("6666", consumer=2000, consultant=1200))
    session.commit()

    result = lookup_prefill(session, "6666")

    assert result == {
        "source": "catalog",
        "name": "Помада",
        "prices": {"cost": 1200, "catalog": 2000, "sale": 2000},
    }


def test_lookup_prefill_unknown_code_returns_none(session):
    """No Product, no Dictionary, no CatalogPrice -> None, unchanged contract."""
    assert lookup_prefill(session, "0000") is None


def test_lookup_prefill_product_source_unaffected_by_catalog_branch(session, product):
    """D-03: an active Product code still returns source=="product", unaffected."""
    product.cost_cents = 1250
    session.commit()

    result = lookup_prefill(session, "TEST-001")

    assert result["source"] == "product"
    assert result["name"] == "Тестовый товар"
    assert result["prices"]["cost"] == 1250


def test_lookup_prefill_sale_filled_from_catalog_consumer_price(session):
    """D-02 superseded: sale is filled from the catalog's consumer price (ПЦ)
    on the catalog-source branch, same value as catalog."""
    add_entry(session, code="7777", name="Тональный крем")
    session.add(_catalog_price("7777", consumer=3000, consultant=1800))
    session.commit()

    result = lookup_prefill(session, "7777")

    assert result["source"] == "catalog"
    assert result["prices"]["sale"] == 3000


# --- Plan 03-02: GET /receipts/lookup pre-fill (D-03 / PD-10 / RCP-02) ---


def test_web_lookup_product_fills_name_and_prices(client, session, product):
    """D-03: existing product -> name main swap + oob fills for empty prices."""
    product.cost_cents = 1250
    session.commit()

    response = client.get(
        "/receipts/lookup",
        params={"code": "TEST-001", "name": "", "cost": "", "sale": "", "catalog": ""},
    )
    assert response.status_code == 200
    assert 'id="name-wrap"' in response.text
    assert "Тестовый товар" in response.text
    assert CARD_HINT in response.text
    assert 'id="cost-wrap"' in response.text
    assert 'hx-swap-oob="true"' in response.text
    assert 'value="12,50"' in response.text


def test_web_lookup_product_skips_typed_price_fields(client, session, product):
    """PD-10: price fields the operator already typed are excluded from the fill."""
    product.cost_cents = 1250
    session.commit()

    response = client.get(
        "/receipts/lookup",
        params={"code": "TEST-001", "name": "", "cost": "9", "sale": "", "catalog": ""},
    )
    assert response.status_code == 200
    assert 'id="name-wrap"' in response.text
    assert 'id="sale-wrap"' in response.text
    assert 'id="catalog-wrap"' in response.text
    assert 'id="cost-wrap"' not in response.text


def test_web_lookup_dictionary_fallback_name_only(client, session):
    """D-01 catalog source: dictionary-only code fills the name via the combined
    catalog branch (no removed "dictionary" source anymore). Blank cost/catalog
    OOB fragments DO render — fill_fields is computed from typed-emptiness only
    (Pitfall 1), independent of whether a real CatalogPrice value exists."""
    add_entry(session, code="4321", name="Тушь")
    response = client.get("/receipts/lookup", params={"code": "4321", "name": ""})
    assert response.status_code == 200
    assert "Тушь" in response.text
    assert CATALOG_FILL_HINT in response.text


def test_web_lookup_catalog_source_price_only_fills_cost_catalog_and_sale(client, session):
    """Unknown-to-Product code with a CatalogPrice match only: cost/catalog/sale
    OOB fragments carry the real consultant/consumer cents display values —
    sale is filled from the consumer price (ПЦ), same as catalog (D-02 superseded)."""
    session.add(
        CatalogPrice(
            id=new_id(),
            code="5555",
            year=2026,
            number=1,
            consumer_cents=1500,
            consultant_cents=900,
        )
    )
    session.commit()

    response = client.get(
        "/receipts/lookup",
        params={"code": "5555", "name": "", "cost": "", "sale": "", "catalog": ""},
    )
    assert response.status_code == 200
    assert 'id="cost-wrap"' in response.text
    assert 'value="9,00"' in response.text
    assert 'id="catalog-wrap"' in response.text
    assert 'value="15,00"' in response.text
    assert 'id="sale-wrap"' in response.text


def test_web_lookup_catalog_source_combines_dictionary_and_price(client, session):
    """Unknown-to-Product code matched by BOTH a Dictionary name and a
    CatalogPrice row: name text and both price OOB fragments appear together."""
    add_entry(session, code="6666", name="Помада")
    session.add(
        CatalogPrice(
            id=new_id(),
            code="6666",
            year=2026,
            number=1,
            consumer_cents=2000,
            consultant_cents=1200,
        )
    )
    session.commit()

    response = client.get(
        "/receipts/lookup",
        params={"code": "6666", "name": "", "cost": "", "sale": "", "catalog": ""},
    )
    assert response.status_code == 200
    assert "Помада" in response.text
    assert 'id="cost-wrap"' in response.text
    assert 'id="catalog-wrap"' in response.text


def test_web_lookup_catalog_source_skips_typed_cost(client, session):
    """Typed-cost-preserved regression for the catalog branch, mirroring
    test_web_lookup_product_skips_typed_price_fields: a price already typed
    by the operator is excluded from the fill."""
    session.add(
        CatalogPrice(
            id=new_id(),
            code="5555",
            year=2026,
            number=1,
            consumer_cents=1500,
            consultant_cents=900,
        )
    )
    session.commit()

    response = client.get(
        "/receipts/lookup",
        params={"code": "5555", "name": "", "cost": "9", "sale": "", "catalog": ""},
    )
    assert response.status_code == 200
    assert 'id="cost-wrap"' not in response.text
    assert 'id="catalog-wrap"' in response.text


def test_web_lookup_204_for_unknown_code(client):
    """Code known nowhere -> 204, empty body, htmx does nothing."""
    response = client.get("/receipts/lookup", params={"code": "0000", "name": ""})
    assert response.status_code == 204
    assert response.text == ""


def test_web_lookup_204_when_name_typed(client, product):
    """Pitfall 7: operator-typed name is never overwritten -> 204."""
    response = client.get(
        "/receipts/lookup", params={"code": "TEST-001", "name": "Своё"}
    )
    assert response.status_code == 204
    assert response.text == ""


def test_web_lookup_form_wiring(client):
    """The receipt code input triggers the debounced lookup with swap guards."""
    response = client.get("/receipts/new")
    assert response.status_code == 200
    assert 'hx-get="/receipts/lookup"' in response.text
    assert "delay:300ms" in response.text
    assert 'hx-target="#name-wrap"' in response.text
    assert 'hx-sync="this:replace"' in response.text
    include = "[name='name'],[name='cost'],[name='sale'],[name='catalog'],[name='warehouse_id']"
    assert f'hx-include="{include}"' in response.text


# --- Plan 09-02: warehouse select + /receipts/batches chooser (routes) ---


def test_web_receipt_form_warehouse_select_and_chooser(client, session, warehouse):
    """The receipt form gains a required «Склад» select and a #batch-chooser target."""
    response = client.get("/receipts/new")
    assert response.status_code == 200
    assert 'name="warehouse_id"' in response.text
    assert 'id="batch-chooser"' in response.text
    assert "[name='warehouse_id']" in response.text  # code input hx-include grew
    assert warehouse.name in response.text  # active warehouse rendered as an option


def test_web_receipt_batches_chooser_lists_open_batches(client, session, product, warehouse):
    """GET /receipts/batches returns a «Пополнить партию» radio per open batch + «Новая партия»."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="5",
        cost_raw="",
        sale_raw="12,50",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
        location_raw="стеллаж А3",
    )
    assert errors == {}

    response = client.get(
        "/receipts/batches", params={"code": "TEST-001", "warehouse_id": warehouse.id}
    )
    assert response.status_code == 200
    assert "Пополнить партию" in response.text
    assert "Новая партия" in response.text
    assert "стеллаж А3" in response.text  # WH-02 location echoed in the radio


def test_web_receipt_batches_zero_warehouses_blocks_with_link(client):
    """No active warehouses -> blocking «Нет активных складов» hint + /warehouses link."""
    response = client.get(
        "/receipts/batches", params={"code": "TEST-001", "warehouse_id": "whatever"}
    )
    assert response.status_code == 200
    assert "Нет активных складов" in response.text
    assert 'href="/warehouses"' in response.text
    assert "Пополнить партию" not in response.text


# --- Plan 09-08: chooser clarity + name-autofill dirty-flag markers ---

BARE_LOAD_HINT = "Введите код товара и выберите склад"
TOPUP_HINT = "Выберите партию для пополнения"


def test_web_receipt_chooser_has_fieldset_legend(client, warehouse):
    """09-08: the batch radio group is a labelled <fieldset><legend>Партия</legend>."""
    response = client.get("/receipts/new")
    assert response.status_code == 200
    assert "<legend>Партия</legend>" in response.text


def test_web_receipt_chooser_bare_load_hint(client, warehouse):
    """09-08: bare load (no code) shows the «Введите код…» hint, not the top-up hint."""
    response = client.get("/receipts/new")
    assert response.status_code == 200
    assert BARE_LOAD_HINT in response.text
    assert TOPUP_HINT not in response.text


def test_web_receipt_chooser_topup_hint_with_open_batches(client, session, product, warehouse):
    """09-08: an existing product with an open batch shows the top-up hint and
    pre-checks no radio (D-01)."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="5",
        cost_raw="",
        sale_raw="12,50",
        catalog_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
    )
    assert errors == {}

    response = client.get(
        "/receipts/lookup",
        params={"code": "TEST-001", "name": "", "warehouse_id": warehouse.id},
    )
    assert response.status_code == 200
    assert TOPUP_HINT in response.text
    assert "checked" not in response.text  # D-01: no radio pre-checked with open batches


def test_web_receipt_name_input_has_autofill_markers(client, session, product):
    """09-08: the autofill fragment carries data-autofilled + autocomplete=off; the
    plain form include carries autocomplete=off but NOT the autofilled marker."""
    lookup = client.get(
        "/receipts/lookup", params={"code": "TEST-001", "name": ""}
    )
    assert lookup.status_code == 200
    assert 'data-autofilled="true"' in lookup.text
    assert 'autocomplete="off"' in lookup.text

    form = client.get("/receipts/new")
    assert form.status_code == 200
    assert 'autocomplete="off"' in form.text
    assert 'data-autofilled="true"' not in form.text
