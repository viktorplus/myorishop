"""Phase 11 Plan 08 tests: mobile return flow (GET/POST /m/returns), entered
only from a history card's «Вернуть» action.

Uses mobile_client_factory (Plan 01 foundation) with BOTH mobile_history and
mobile_returns routers together — the return entry point is a link rendered
by the history card partial.
"""

from datetime import date, timedelta

from sqlalchemy import select

from app.config import settings
from app.core import local_today_iso, new_id, utcnow_iso
from app.models import CashMovement, Operation, Sale
from app.routes import mobile_history, mobile_returns
from app.services.batches import open_batches
from app.services.ledger import record_operation


def _client(mobile_client_factory):
    return mobile_client_factory(mobile_history.router, mobile_returns.router)


def _return_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "return")).all()


def _make_sale(
    session, product, qty, unit_price_cents=1500, unit_cost_cents=1000, business_date=None
):
    """Real BATCHED sale: one Sale header + one `sale` op through the single
    write path (mirrors tests/test_returns.py::_make_sale).

    Phase 33: `business_date` defaults to None — record_operation's own default,
    so the origin gets today's local day exactly as before. Pass it only when the
    test is about an origin sale that was itself back-dated (D-24)."""
    header = Sale(
        id=new_id(),
        customer_id=None,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(header)
    batches = open_batches(session, product.id)
    batch_id = batches[0].id if batches else None
    op = record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-qty,
        unit_cost_cents=unit_cost_cents,
        unit_price_cents=unit_price_cents,
        sale_id=header.id,
        batch_id=batch_id,
        business_date=business_date,
    )
    return header, op


def test_tapping_return_resolves_origin_and_shows_returnable_count(
    mobile_client_factory, session, stocked_product
):
    client = _client(mobile_client_factory)
    header, sale_op = _make_sale(session, stocked_product, qty=3)

    response = client.get(
        "/m/returns",
        params={
            "sale_id": header.id,
            "product_id": stocked_product.id,
            "origin_op_id": sale_op.id,
        },
    )

    assert response.status_code == 200
    assert "Доступно к возврату: 3 из 3." in response.text


def test_valid_return_writes_operation_and_shows_success_line(
    mobile_client_factory, session, stocked_product
):
    client = _client(mobile_client_factory)
    header, sale_op = _make_sale(session, stocked_product, qty=3)

    response = client.post(
        "/m/returns", data={"origin_op_id": sale_op.id, "qty": "2"}
    )

    assert response.status_code == 200
    assert f"Возврат оформлен: {stocked_product.name} — 2 шт." in response.text
    returns = _return_ops(session)
    assert len(returns) == 1
    assert returns[0].qty_delta == 2
    assert returns[0].sale_id == header.id


def test_over_cap_qty_returns_422_with_zero_writes(
    mobile_client_factory, session, stocked_product
):
    client = _client(mobile_client_factory)
    _header, sale_op = _make_sale(session, stocked_product, qty=3)

    response = client.post(
        "/m/returns", data={"origin_op_id": sale_op.id, "qty": "5"}
    )

    assert response.status_code == 422
    assert not _return_ops(session)


def test_unresolvable_origin_shows_not_found_message_with_no_form(
    mobile_client_factory, session
):
    client = _client(mobile_client_factory)

    response = client.get("/m/returns", params={"origin_op_id": "does-not-exist"})

    assert response.status_code == 422
    assert "Исходная продажа не найдена." in response.text
    assert "<form" not in response.text


# ---------------------------------------------------------------------------
# DATE-01/DATE-02/D-16/D-24: the business date on the mobile возврат screen
# ---------------------------------------------------------------------------


def _today_plus(days: int) -> str:
    """An ISO day offset from the operator's LOCAL today — the same definition
    parse_op_date's future check and the today_iso() Jinja global both use."""
    return (
        date.fromisoformat(local_today_iso(settings.display_tz)) + timedelta(days=days)
    ).isoformat()


def _return_cash(session):
    return session.scalars(select(CashMovement).where(CashMovement.category == "return")).all()


def test_mobile_return_renders_the_date_field_at_desktop_parity(
    mobile_client_factory, session, stocked_product
):
    """D-16: without this the возврат surface would ship dateless on mobile while
    its desktop twin has the field. Plain `.field`, no full-row modifier — the
    same deliberate compact-layout exception as desktop (surface 14 of 14)."""
    client = _client(mobile_client_factory)
    _header, sale_op = _make_sale(session, stocked_product, qty=3)

    response = client.get("/m/returns", params={"origin_op_id": sale_op.id})

    assert response.status_code == 200
    today = local_today_iso(settings.display_tz)
    assert "Дата операции" in response.text
    assert 'name="op_date"' in response.text
    assert f'value="{today}" max="{today}"' in response.text
    assert "op-date" not in response.text


def test_mobile_return_back_date_lands_on_the_ledger_row_and_the_refund(
    mobile_client_factory, session, stocked_product
):
    """DATE-01/DATE-03 through the real POST: returned goods and refunded money
    carry the same business date."""
    client = _client(mobile_client_factory)
    _header, sale_op = _make_sale(session, stocked_product, qty=3)
    back_date = _today_plus(-9)

    response = client.post(
        "/m/returns",
        data={"origin_op_id": sale_op.id, "qty": "2", "op_date": back_date},
    )

    assert response.status_code == 200
    returns = _return_ops(session)
    assert len(returns) == 1
    assert returns[0].business_date == back_date
    assert _return_cash(session)[0].business_date == back_date


def test_mobile_return_future_date_returns_422_with_the_per_key_error(
    mobile_client_factory, session, stocked_product
):
    """DATE-02/D-14: the refusal renders as a per-key <p class="error"> under the
    input — this file's own idiom — never as a whole-screen .error-block, and the
    typed date is still in the input so the operator can correct it."""
    client = _client(mobile_client_factory)
    _header, sale_op = _make_sale(session, stocked_product, qty=3)
    tomorrow = _today_plus(1)

    response = client.post(
        "/m/returns",
        data={"origin_op_id": sale_op.id, "qty": "1", "op_date": tomorrow},
    )

    message = "Дата операции не может быть в будущем."
    assert response.status_code == 422
    assert f'<p class="error">{message}</p>' in response.text
    assert f'<div class="error-block">{message}</div>' not in response.text
    assert f'value="{tomorrow}"' in response.text
    assert not _return_ops(session)


def test_mobile_return_label_names_the_origin_sales_business_date(
    mobile_client_factory, session, stocked_product
):
    """D-24 mirrored to mobile (D-21): «Возврат из продажи от …» identifies the
    origin by its BUSINESS date, dd.mm.yyyy, with no time part."""
    client = _client(mobile_client_factory)
    back_date = _today_plus(-45)
    _header, sale_op = _make_sale(session, stocked_product, qty=3, business_date=back_date)
    assert sale_op.created_at[:10] != back_date

    response = client.get("/m/returns", params={"origin_op_id": sale_op.id})

    assert response.status_code == 200
    expected = date.fromisoformat(back_date).strftime("%d.%m.%Y")
    assert f"Возврат из продажи от {expected} —" in response.text
    entered_today = date.fromisoformat(local_today_iso(settings.display_tz)).strftime("%d.%m.%Y")
    assert f"Возврат из продажи от {entered_today}" not in response.text
