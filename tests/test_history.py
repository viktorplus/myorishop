"""OPS-04 executable contract for the /history browsing slice.

Interface contract for the Wave 5 history read service/route. Module path
and signature below are fixed — implement against them, do not rename.

This file is RED by design until app.services.operations lands: the module
import fails collection entirely (mirrors tests/test_sales.py from Phase 4).
Do NOT stub the service here.

Naming convention (used by -k filters, per 05-VALIDATION.md's
Requirements -> Test Map): route/e2e tests are prefixed test_web_;
everything else is service level. Selectors: rows, filters, pagination.
"""

from app.services.operations import history_view  # noqa: F401

from app.config import settings
from app.services.ledger import record_operation


def _seed_mixed_ops(session, product):
    """Seed a mix of op types on one product (receipt/writeoff/correction)."""
    record_operation(session, type_="writeoff", product_id=product.id, qty_delta=-1)
    record_operation(session, type_="correction", product_id=product.id, qty_delta=2)


# --- Service level ---


def test_history_pagination(session, stocked_product):
    """OPS-04/D-15: history_view returns <= page_size rows plus a has_next
    flag — a bounded page, never the whole ledger."""
    for _ in range(5):
        record_operation(session, type_="correction", product_id=stocked_product.id, qty_delta=1)
    # stocked_product already carries 1 receipt op from its fixture -> 6 rows total.

    first_page = history_view(session, page=0, page_size=3)
    assert len(first_page["rows"]) == 3
    assert first_page["has_next"] is True

    last_page = history_view(session, page=1, page_size=3)
    assert len(last_page["rows"]) <= 3
    assert last_page["has_next"] is False


# --- Web slice (routes + templates) ---


def test_web_history_rows(client, session, stocked_product):
    """OPS-04: GET /history returns all ops newest-first with product
    name/code, signed qty, reason, who, when, and RU type labels."""
    _seed_mixed_ops(session, stocked_product)

    response = client.get("/history")
    assert response.status_code == 200
    assert stocked_product.name in response.text
    assert stocked_product.code in response.text
    assert "Списание" in response.text  # OPERATION_TYPE_LABELS["writeoff"]
    assert "Корректировка" in response.text  # OPERATION_TYPE_LABELS["correction"]
    assert settings.operator_name in response.text


def test_web_history_filters(client, session, stocked_product, product):
    """OPS-04/D-14: the type filter and the product filter each narrow
    results (portable ORM, no raw SQL)."""
    _seed_mixed_ops(session, stocked_product)
    record_operation(session, type_="correction", product_id=product.id, qty_delta=1)

    type_response = client.get("/history", params={"type": "writeoff"})
    assert type_response.status_code == 200
    assert "Списание" in type_response.text
    assert "Корректировка" not in type_response.text

    product_response = client.get("/history", params={"product": stocked_product.id})
    assert product_response.status_code == 200
    assert stocked_product.code in product_response.text
    assert product.code not in product_response.text
