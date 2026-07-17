"""SALE-02/D-08/D-09: coverage for the live running total.

This suite asserts MARKUP and WIRING only — never arithmetic. The project's
test stack has no JS runtime (no jsdom/Playwright; CLAUDE.md forbids an npm
toolchain), so `sale-total.js`'s actual sum can only be checked by hand; see
`.planning/phases/22-sales-page-rebuild/22-VALIDATION.md` §Manual-Only
Verifications for that checklist. Do NOT "fix" the coverage gap by adding a
browser test runner; that is an explicit CLAUDE.md scope deviation (see this
plan's threat register, T-22-SC).
"""

import re

from app.services.batches import open_batches


def _only_batch(session, product):
    """The single open batch id seeded by the stocked_product fixture."""
    return open_batches(session, product.id)[0].id


def test_sale_total_element_renders_under_basket(client):
    """SALE-02: #sale-total renders under the basket with the empty-basket
    defaults and the advisory copy, directly above the existing basket hint."""
    response = client.get("/sales/new")
    assert response.status_code == 200
    body = response.text
    assert 'id="sale-total"' in body
    assert 'id="sale-total-amount"' in body
    assert 'id="sale-total-units"' in body
    assert 'id="sale-total-warning"' in body
    assert "Предварительный итог:" in body
    assert "шт." in body
    assert 'id="sale-total-amount">0,00<' in body
    assert 'id="sale-total-units">0<' in body

    total_index = body.index('id="sale-total"')
    hint_index = body.index("Если товара с таким кодом ещё нет")
    assert total_index < hint_index


def test_sale_total_has_no_name_attribute(client):
    """T-22-03 (security, not style): the browser's advisory money math must
    be structurally incapable of reaching the server. register_sale
    (services/sales.py:282) stays the sole authority."""
    response = client.get("/sales/new")
    match = re.search(r'<p id="sale-total"[^>]*>.*?</p>', response.text, re.DOTALL)
    assert match is not None, "expected a #sale-total element on /sales/new"
    element = match.group(0)
    opening_tag = element.split(">", 1)[0] + ">"
    assert "name=" not in opening_tag
    assert "<input" not in element
    assert "<select" not in element
    assert "<textarea" not in element


def test_sale_total_script_loaded_on_both_shells(client, mobile_client_factory):
    """22-PATTERNS.md Shared Pattern 7: mobile_base.html does not inherit
    from base.html, so the script tag must be duplicated verbatim on both."""
    from app.routes import mobile_sales

    desktop = client.get("/sales/new")
    assert desktop.status_code == 200
    assert '<script src="/static/sale-total.js" defer>' in desktop.text

    mobile_client = mobile_client_factory(mobile_sales.router)
    mobile = mobile_client.get("/m/sales")
    assert mobile.status_code == 200
    assert '<script src="/static/sale-total.js" defer>' in mobile.text


def test_sale_total_survives_422_rerender(client, session, stocked_product):
    """Pitfall 2a: a 422 re-render fires no `input` event, so if the element
    were dropped or the listener not re-triggered the total would go stale."""
    bid = _only_batch(session, stocked_product)
    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["0"],
            "price[]": ["15,00"],
            "batch_id[]": [bid],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 422
    assert 'id="sale-form-wrap"' in response.text
    assert 'id="sale-total"' in response.text


def test_sale_row_delete_hook_present(client):
    """Pitfall 2b: a plain DOM `.remove()` fires neither an `input` nor an
    htmx event, so the guarded window.recalcSaleTotal() call is the only
    trigger left when a basket row is deleted."""
    response = client.get("/sales/row")
    assert response.status_code == 200
    match = re.search(r"<button[^>]*>Удалить строку</button>", response.text)
    assert match is not None, "expected a «Удалить строку» button in the row partial"
    button_html = match.group(0)
    assert "window.recalcSaleTotal" in button_html


def test_sale_total_warning_hidden_by_default(client):
    """D-09: an incomplete total is a typing-in-progress state, not a fault —
    the marker is `.muted` and `hidden`, never `.error` (22-UI-SPEC.md Color
    rule 1)."""
    response = client.get("/sales/new")
    match = re.search(r'<span id="sale-total-warning"[^>]*>.*?</span>', response.text, re.DOTALL)
    assert match is not None, "expected #sale-total-warning on /sales/new"
    element = match.group(0)
    opening_tag = element.split(">", 1)[0] + ">"
    assert "hidden" in opening_tag
    assert "muted" in opening_tag
    assert "итог неполный" in element
    assert "error" not in opening_tag
