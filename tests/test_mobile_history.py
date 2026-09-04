"""Phase 11 Plan 08 tests: mobile history card list (GET /m/history).

Extended Phase 23 Plan 05 (HIST-01..04, D-10): full filter parity with
desktop (product/category/customer/date-range) and numbered
page_window/paginate pagination, replacing the legacy load-more mechanism.

Uses mobile_client_factory (Plan 01 foundation) to test app.routes.mobile_history
in isolation, without app.main registration (that happens in Plan 09).
"""

from app.config import settings
from app.core import format_ru_date, iso_to_local, new_id
from app.models import Batch, Product, Warehouse
from app.routes import mobile_history
from app.services.batches import open_batches
from app.services.ledger import record_operation


def _client(mobile_client_factory):
    return mobile_client_factory(mobile_history.router)


def _batch_id(session, product):
    batches = open_batches(session, product.id)
    return batches[0].id if batches else None


def test_empty_history_shows_unfiltered_empty_state(mobile_client_factory, session):
    client = _client(mobile_client_factory)

    response = client.get("/m/history")

    assert response.status_code == 200
    assert "Операций пока нет." in response.text


def test_receipt_operation_shows_one_card_with_type_label(
    mobile_client_factory, session, stocked_product
):
    client = _client(mobile_client_factory)

    response = client.get("/m/history")

    assert response.status_code == 200
    assert stocked_product.name in response.text
    assert stocked_product.code in response.text
    assert "Приход" in response.text  # OPERATION_TYPE_LABELS["receipt"]


def test_type_filter_narrows_results_and_shows_filtered_empty_state(
    mobile_client_factory, session, stocked_product
):
    client = _client(mobile_client_factory)
    record_operation(
        session,
        type_="correction",
        product_id=stocked_product.id,
        qty_delta=1,
        batch_id=_batch_id(session, stocked_product),
    )

    matching = client.get("/m/history", params={"type": "correction"})
    assert matching.status_code == 200
    # Scoped to the card's own "· <type label>" line — the always-populated
    # filter <select> also lists every RU type label as an <option>, so a
    # bare substring check would false-positive on that dropdown text
    # (mirrors desktop's test_web_history_filters docstring precedent).
    assert "· Корректировка</p>" in matching.text
    assert "· Приход</p>" not in matching.text

    empty = client.get("/m/history", params={"type": "writeoff"})
    assert empty.status_code == 200
    assert "Нет операций по выбранным фильтрам." in empty.text


def test_sale_row_shows_return_link_and_non_sale_row_does_not(
    mobile_client_factory, session, stocked_product
):
    client = _client(mobile_client_factory)
    record_operation(
        session,
        type_="sale",
        product_id=stocked_product.id,
        qty_delta=-1,
        batch_id=_batch_id(session, stocked_product),
    )

    response = client.get("/m/history", params={"type": "sale"})
    assert response.status_code == 200
    assert "/m/returns?sale_id=" in response.text
    assert "origin_op_id=" in response.text
    assert ">Вернуть<" in response.text

    receipt_only = client.get("/m/history", params={"type": "receipt"})
    assert receipt_only.status_code == 200
    assert ">Вернуть<" not in receipt_only.text


def test_product_filter_param_is_present_on_route_signature():
    """D-10 supersedes the Phase-11 CONTEXT discretion that dropped `product`
    from mobile's route signature (23-CONTEXT.md): the dashboard feed's deep
    link (/m/history?type=X&product=Y) requires `product` to exist as a query
    param again, even though mobile still has no visible Товар filter
    control (23-UI-SPEC.md Copywriting Contract — deep-link only)."""
    import inspect

    signature = inspect.signature(mobile_history.mobile_history_page)
    assert "product" in signature.parameters


def test_product_filter_narrows_results(mobile_client_factory, session, stocked_product):
    """D-10: the reinstated `product` param narrows results even with no
    visible Товар control on mobile."""
    client = _client(mobile_client_factory)
    other = Product(id=new_id(), code="OTH-001", name="Другой товар", quantity=0)
    session.add(other)
    other_warehouse = Warehouse(id=new_id(), name="Другой склад")
    session.add(other_warehouse)
    session.commit()
    other_batch = Batch(
        id=new_id(), product_id=other.id, warehouse_id=other_warehouse.id, quantity=0
    )
    session.add(other_batch)
    session.commit()
    record_operation(
        session,
        type_="receipt",
        product_id=other.id,
        qty_delta=5,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=other_batch.id,
    )

    response = client.get("/m/history", params={"product": stocked_product.id})

    assert response.status_code == 200
    assert stocked_product.code in response.text
    assert other.code not in response.text


def test_paging_returns_additional_cards_when_has_next(
    mobile_client_factory, session, stocked_product
):
    client = _client(mobile_client_factory)
    batch_id = _batch_id(session, stocked_product)
    for _ in range(51):
        record_operation(
            session,
            type_="writeoff",
            product_id=stocked_product.id,
            qty_delta=-1,
            batch_id=batch_id,
        )

    # D-10/HIST-04: numbered pagination bar replaces the old "page=1"
    # load-more-link substring assertion.
    first_page = client.get("/m/history", params={"type": "writeoff"})
    assert first_page.status_code == 200
    assert 'class="pagination"' in first_page.text

    second_page = client.get(
        "/m/history",
        params={"type": "writeoff", "page": 1},
        headers={"HX-Request": "true"},
    )
    assert second_page.status_code == 200
    assert "Списание" in second_page.text


def test_pagination_bar_reflects_filtered_total(mobile_client_factory, session, stocked_product):
    """HIST-04/D-10: mobile История migrates onto the same numbered
    page_window/paginate mechanism as desktop — mirrors
    test_web_history_pagination_bar_reflects_filtered_total
    (tests/test_history.py)."""
    client = _client(mobile_client_factory)
    batch_id = _batch_id(session, stocked_product)
    for _ in range(25):
        record_operation(
            session,
            type_="writeoff",
            product_id=stocked_product.id,
            qty_delta=-1,
            batch_id=batch_id,
        )

    response = client.get(
        "/m/history",
        params={"type": "writeoff", "page": 1},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert 'class="pagination"' in response.text
    assert "Страница 2 из 2" in response.text


# --- Phase 33 (DATE-05/DATE-06, D-21): the mirrored marker and the mirrored filter ---
#
# VA-16, mobile half. VA-16 is satisfied only when BOTH halves pass — neither
# tests/test_history.py nor this file closes it alone.


def _correction(session, product, *, business_date=None):
    return record_operation(
        session,
        type_="correction",
        product_id=product.id,
        qty_delta=1,
        batch_id=_batch_id(session, product),
        business_date=business_date,
    )


def test_mobile_dated_card_is_one_line_when_the_two_dates_match(
    mobile_client_factory, session, stocked_product
):
    """D-21: a row entered and attributed to the same day renders EXACTLY the
    card it rendered before this phase — one muted header line, no sibling <p>."""
    client = _client(mobile_client_factory)
    op = _correction(session, stocked_product)

    response = client.get("/m/history", params={"type": "correction"})

    assert response.status_code == 200
    entered = iso_to_local(op.created_at, settings.display_tz)
    assert f'<p class="muted">{entered} · Корректировка</p>' in response.text
    # «Только задним числом» is always in the filter <select>; the marker itself
    # is the longer phrase, so this negative assertion is safe.
    assert "задним числом · внесено" not in response.text


def test_mobile_dated_card_shows_business_date_and_marker_when_they_differ(
    mobile_client_factory, session, stocked_product
):
    """D-21: mobile MIRRORS desktop — the business date takes over the header
    line and the entry timestamp becomes a muted sibling <p> inside the same
    .mobile-card. The marker is the RU words, never colour alone."""
    client = _client(mobile_client_factory)
    op = _correction(session, stocked_product, business_date="2026-07-10")

    response = client.get("/m/history", params={"type": "correction"})

    assert response.status_code == 200
    day = format_ru_date("2026-07-10")
    entered = iso_to_local(op.created_at, settings.display_tz)
    assert f'<p class="muted">{day} · Корректировка</p>' in response.text
    assert f'<p class="muted">задним числом · внесено {entered}</p>' in response.text
    # `| ru_date`, not `| local_dt`: a String(10) through local_dt would print a
    # fabricated 00:00 without raising.
    assert "10.07.2026 00:00" not in response.text


def test_mobile_dated_filter_narrows_cards_and_shows_the_filtered_empty_state(
    mobile_client_factory, session, stocked_product
):
    """DATE-06 on the surface the operator actually uses in the warehouse."""
    client = _client(mobile_client_factory)
    _correction(session, stocked_product, business_date="2026-07-10")
    _correction(session, stocked_product)

    backdated = client.get("/m/history", params={"dated": "backdated"})
    assert backdated.status_code == 200
    assert backdated.text.count('<div class="mobile-card">') == 1
    assert "задним числом · внесено" in backdated.text

    same_day = client.get("/m/history", params={"dated": "same_day"})
    assert same_day.status_code == 200
    assert "задним числом · внесено" not in same_day.text

    # Nothing back-dated among receipts -> the empty state must name the
    # filters, not claim the app is empty.
    empty = client.get("/m/history", params={"type": "receipt", "dated": "backdated"})
    assert empty.status_code == 200
    assert "Нет операций по выбранным фильтрам." in empty.text
    assert "Операций пока нет." not in empty.text


def test_mobile_dated_select_renders_and_reselects_the_active_option(
    mobile_client_factory, session, stocked_product
):
    """D-20/D-21: the mirrored 4th filter. Its HTMX attributes must point at
    /m/history and #history-cards — copied from THIS page's siblings, never from
    the desktop select.

    The re-selection is asserted on a full-page GET carrying the param, because
    that is the only path that re-renders the control: mobile's filters live in
    #history-filters, which htmx never swaps (hx-target is #history-cards), so
    after a swap the operator's choice survives in the DOM by construction and
    only a reload of the pushed URL can lose it.
    """
    client = _client(mobile_client_factory)

    default = client.get("/m/history")
    assert default.status_code == 200
    assert '<select id="dated" name="dated"' in default.text
    assert '<option value="" selected>Все</option>' in default.text
    assert 'hx-get="/m/history"' in default.text
    assert 'hx-target="#history-cards"' in default.text
    assert 'hx-get="/history"' not in default.text  # never the desktop target

    active = client.get("/m/history", params={"dated": "backdated"})
    assert '<option value="backdated" selected>Только задним числом</option>' in active.text

    same_day = client.get("/m/history", params={"dated": "same_day"})
    assert '<option value="same_day" selected>Только в день операции</option>' in same_day.text
