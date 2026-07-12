"""Phase 11 Plan 08 tests: mobile history card list (GET /m/history).

Uses mobile_client_factory (Plan 01 foundation) to test app.routes.mobile_history
in isolation, without app.main registration (that happens in Plan 09).
"""

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


def test_no_product_filter_param_on_route_signature():
    """UI-SPEC/CONTEXT discretion: mobile history drops the desktop product
    filter — the route must not accept/define a `product` query param."""
    import inspect

    signature = inspect.signature(mobile_history.mobile_history_page)
    assert "product" not in signature.parameters


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

    first_page = client.get("/m/history", params={"type": "writeoff"})
    assert first_page.status_code == 200
    assert "page=1" in first_page.text  # load-more control's next-page link

    second_page = client.get(
        "/m/history",
        params={"type": "writeoff", "page": 1},
        headers={"HX-Request": "true"},
    )
    assert second_page.status_code == 200
    assert "Списание" in second_page.text
