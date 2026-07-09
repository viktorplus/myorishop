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

from app.models import Operation, Product
from app.services import catalog
from app.services.catalog import create_product, soft_delete_product
from app.services.dictionary import add_entry
from app.services.ledger import compute_stock, record_operation
from app.services.receipts import recent_receipts, register_receipt

EMPTY_MONEY = {"cost_raw": "", "sale_raw": "", "catalog_raw": ""}


# --- Service level (D-01 / D-05 / D-06 / PD-8) ---


def test_register_receipt_increases_stock_for_existing_product(session, product):
    """D-01/D-06: one receipt op, qty_delta > 0, prices snapshotted on the op."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="что угодно",
        qty_raw="5",
        cost_raw="10",
        sale_raw="12,50",
        catalog_raw="15",
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


def test_register_receipt_autocreates_product_for_unknown_code(session):
    """D-05: unknown code -> new product card + product_created op, atomically."""
    result, errors = register_receipt(
        session,
        code="9999",
        name="Губная помада",
        qty_raw="3",
        cost_raw="5",
        sale_raw="",
        catalog_raw="",
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


def test_register_receipt_requires_code_name_and_positive_int_qty(session, product):
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
        result, errors = register_receipt(session, **kwargs, **EMPTY_MONEY)
        assert result is None, kwargs
        assert errors[field] == message, kwargs

    assert session.scalars(select(Operation)).all() == []
    assert len(session.scalars(select(Product)).all()) == products_before


def test_register_receipt_rejects_bad_money(session, product):
    """Garbage money -> the shared catalog PRICE_ERROR text, nothing written."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="1",
        cost_raw="abc",
        sale_raw="",
        catalog_raw="",
    )
    assert result is None
    assert errors["cost"] == catalog.PRICE_ERROR
    assert session.scalars(select(Operation)).all() == []


def test_register_receipt_soft_deleted_code_creates_new_product(session):
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
    )
    assert errors == {}
    assert result

    fresh = session.scalars(
        select(Product).where(Product.code == "DEAD-01", Product.deleted_at.is_(None))
    ).one()
    assert fresh.id != old_id
    assert fresh.quantity == 4


def test_register_receipt_empty_prices_are_null(session, product):
    """PD-8 / A3: empty price strings -> NULL op columns and NULL payload price."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Крем",
        qty_raw="2",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
    )
    assert errors == {}
    assert result

    op = session.scalars(select(Operation).where(Operation.type == "receipt")).one()
    assert op.unit_cost_cents is None
    assert op.unit_price_cents is None
    assert op.payload["catalog_cents"] is None


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


def test_web_receipt_post_success_returns_fresh_form(client):
    """D-02: success -> 200 fresh form partial + success line + focus hook."""
    response = client.post(
        "/receipts",
        data={"code": "9999", "name": "Крем", "qty": "2", "cost": "", "sale": "", "catalog": ""},
    )
    assert response.status_code == 200
    assert "Приход сохранён: Крем — 2 шт." in response.text
    assert 'id="receipt-form-wrap"' in response.text
    assert "getElementById('code').focus()" in response.text
    assert "<html" not in response.text  # partial only, never a full page
    assert 'value="9999"' not in response.text  # form cleared for the next item


def test_web_receipt_post_validation_422_preserves_input(client, product):
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


# --- Recent receipts + nav (Task 3 slice — D-04) ---


def test_recent_receipts_newest_first_capped_at_ten(session, product):
    """D-04: last 10 receipt ops, newest first (created_at desc, seq desc)."""
    for i in range(12):
        record_operation(
            session,
            type_="receipt",
            product_id=product.id,
            qty_delta=i + 1,
            payload={"catalog_cents": None},
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


def test_web_recent_receipts_lists_saved_receipt(client):
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
        },
    )
    assert response.status_code == 200

    page = client.get("/receipts/new")
    assert page.status_code == 200
    for header in ("Когда", "Код", "Название", "Кол-во"):
        assert header in page.text
    assert "Губная помада" in page.text
    assert ">7<" in page.text


def test_web_recent_receipts_oob_row_in_post_response(client):
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


def test_price_sync_updates_card_and_writes_ops(session, product):
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


def test_price_sync_empty_fields_leave_card_untouched(session, product):
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


def test_price_sync_ignores_name_for_existing_product(session, product):
    """PD-9: a typed name never renames an existing product, no product_edited op."""
    result, errors = register_receipt(
        session,
        code="TEST-001",
        name="Другое имя",
        qty_raw="1",
        cost_raw="",
        sale_raw="",
        catalog_raw="",
    )
    assert errors == {}
    assert result

    session.refresh(product)
    assert product.name == "Тестовый товар"
    edited = session.scalars(
        select(Operation).where(Operation.type == "product_edited")
    ).all()
    assert edited == []


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
    """D-03 fallback: dictionary-only code fills the name, no oob fragments."""
    add_entry(session, code="4321", name="Тушь")
    response = client.get("/receipts/lookup", params={"code": "4321", "name": ""})
    assert response.status_code == 200
    assert "Тушь" in response.text
    assert DICT_HINT in response.text
    assert "hx-swap-oob" not in response.text


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
    include = "[name='name'],[name='cost'],[name='sale'],[name='catalog']"
    assert f'hx-include="{include}"' in response.text
