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

from app.config import settings
from app.services.ledger import record_operation
from app.services.operations import history_view  # noqa: F401


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
    results (portable ORM, no raw SQL).

    CR-01: since the fix, a filtered non-HX request renders the full page,
    whose filter-bar <select> unconditionally lists every RU type label /
    every active product as <option> text regardless of the active filter
    (that's normal <select> behavior, not a row match). So assertions must
    be scoped to the row markup (<td>...</td>) rather than a bare substring
    check, which would otherwise false-positive on the dropdown text.
    """
    _seed_mixed_ops(session, stocked_product)
    record_operation(session, type_="correction", product_id=product.id, qty_delta=1)

    type_response = client.get("/history", params={"type": "writeoff"})
    assert type_response.status_code == 200
    assert "<td>Списание</td>" in type_response.text
    assert "<td>Корректировка</td>" not in type_response.text

    product_response = client.get("/history", params={"product": stocked_product.id})
    assert product_response.status_code == 200
    assert f"<td>{stocked_product.name} ({stocked_product.code})</td>" in product_response.text
    assert f"<td>{product.name} ({product.code})</td>" not in product_response.text


def test_web_history_filtered_reload_returns_full_chrome(client, session, stocked_product):
    """CR-01/OPS-04: a plain (non-htmx) top-level GET to /history that
    carries a type filter must render the full page chrome — not the
    chrome-less rows-only partial a real browser would drop per HTML5
    parsing rules — while filtering still narrows the displayed rows
    correctly (scoped to <td> row markup — see test_web_history_filters
    docstring for why a bare substring check is insufficient once the
    always-populated filter-bar <select> is present)."""
    _seed_mixed_ops(session, stocked_product)

    response = client.get("/history", params={"type": "writeoff"})
    assert response.status_code == 200
    assert "<html" in response.text
    assert "<nav" in response.text
    assert "<table" in response.text
    assert "<td>Списание</td>" in response.text
    assert "<td>Корректировка</td>" not in response.text


def test_web_history_load_more_survives_filter_change(client, session, stocked_product):
    """CR-01 (new)/OPS-04: #load-more must survive a filter-select change on
    a >50-row filtered result set. The old bug nested <tr id="load-more"> INSIDE
    <tbody id="history-tbody">, the exact element the type/product <select>s
    target with htmx's default (unset -> innerHTML) swap; the oob-before-main
    ordering meant the main swap wiped the oob-placed control right after it
    landed, permanently stranding pagination past page 1 of any filtered
    view. The fix moves #load-more into its own <tfoot>, a DOM sibling of
    #history-tbody untouched by that tbody's innerHTML/beforeend swaps."""
    for _ in range(51):
        record_operation(session, type_="writeoff", product_id=stocked_product.id, qty_delta=-1)

    full_page = client.get("/history", params={"type": "writeoff"})
    assert full_page.status_code == 200
    tbody_start = full_page.text.index('<tbody id="history-tbody">')
    tbody_end = full_page.text.index("</tbody>", tbody_start)
    tbody_html = full_page.text[tbody_start:tbody_end]
    assert 'id="load-more"' not in tbody_html
    assert "<tfoot>" in full_page.text
    tfoot_start = full_page.text.index("<tfoot>")
    tfoot_html = full_page.text[tfoot_start:]
    assert 'id="load-more"' in tfoot_html
    assert "Показать ещё" in tfoot_html

    hx_response = client.get(
        "/history", params={"type": "writeoff"}, headers={"HX-Request": "true"}
    )
    assert hx_response.status_code == 200
    assert 'id="load-more"' in hx_response.text
    assert "hx-swap-oob" in hx_response.text
    assert "Показать ещё" in hx_response.text
