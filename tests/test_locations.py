"""Storage-place page (todo 2026-08-31): «где что лежит».

Pins the contracts the page depends on: the place is DERIVED from the batch
(location, else comment, else «Место не указано» — never a new column and
never a silently hidden batch), shelves sort naturally («полка 5» before
«полка 39»), emptied batches never appear, and the search folds Cyrillic in
Python (SQLite lower() cannot — D-27).
"""

import pytest
from sqlalchemy import select

from app.core import new_id
from app.models import Batch, Product, Warehouse
from app.routes import nav_section
from app.services.locations import (
    UNKNOWN_PLACE,
    batch_place,
    list_locations_view,
    place_sort_key,
)


def _warehouse(session, name="Офис"):
    warehouse = session.scalars(select(Warehouse).where(Warehouse.name == name)).first()
    if warehouse is None:
        warehouse = Warehouse(id=new_id(), name=name)
        session.add(warehouse)
        session.commit()
    return warehouse


def _stock(
    session,
    *,
    code,
    name,
    quantity=1,
    location=None,
    comment=None,
    expiry=None,
    warehouse_name="Офис",
):
    """One product with one batch holding `quantity` pieces.

    quantity is written straight onto the batch: it is a cached projection
    (D-11) and this view only READS it, so no ledger round-trip is needed to
    pin the read contract.
    """
    product = Product(id=new_id(), code=code, name=name, name_lc=name.lower(), quantity=quantity)
    session.add(product)
    session.commit()
    batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=_warehouse(session, warehouse_name).id,
        quantity=quantity,
        location=location,
        comment=comment,
        expiry=expiry,
    )
    session.add(batch)
    session.commit()
    return product, batch


# --- place derivation ---


def test_batch_place_prefers_location_then_comment_then_unknown(session):
    _, both = _stock(session, code="A1", name="Оба", location="полка 1", comment="полка 9")
    _, only_comment = _stock(session, code="A2", name="Комментарий", comment="полка 59")
    _, neither = _stock(session, code="A3", name="Пусто")
    _, blank = _stock(session, code="A4", name="Пробелы", location="   ", comment="  ")

    assert batch_place(both) == "полка 1"
    assert batch_place(only_comment) == "полка 59"
    assert batch_place(neither) == UNKNOWN_PLACE
    assert batch_place(blank) == UNKNOWN_PLACE


@pytest.mark.parametrize(
    "places, expected",
    [
        (["полка 39", "полка 5"], ["полка 5", "полка 39"]),
        (["полка 2", UNKNOWN_PLACE, "полка 1"], ["полка 1", "полка 2", UNKNOWN_PLACE]),
        (["полка 10", "полка 9", "полка 1"], ["полка 1", "полка 9", "полка 10"]),
    ],
)
def test_place_sort_key_is_natural_and_puts_unknown_last(places, expected):
    assert sorted(places, key=place_sort_key) == expected


# --- the two views ---


def test_default_view_lists_places_with_counts(session):
    _stock(session, code="B1", name="Первый", quantity=3, comment="полка 39")
    _stock(session, code="B2", name="Второй", quantity=2, comment="полка 39")
    _stock(session, code="B3", name="Третий", quantity=7, comment="полка 5")

    view = list_locations_view(session)

    assert view["mode"] == "places"
    assert [p["place"] for p in view["places_page"]] == ["полка 5", "полка 39"]
    shelf_39 = next(p for p in view["places_page"] if p["place"] == "полка 39")
    assert (shelf_39["batches"], shelf_39["quantity"]) == (2, 5)


def test_emptied_batch_is_not_listed(session):
    _stock(session, code="C1", name="Есть", quantity=4, comment="полка 1")
    _stock(session, code="C2", name="Кончился", quantity=0, comment="полка 2")

    view = list_locations_view(session)

    assert [p["place"] for p in view["places_page"]] == ["полка 1"]


def test_place_filter_shows_only_that_place(session):
    _stock(session, code="D1", name="Нужный", comment="полка 39")
    _stock(session, code="D2", name="Чужой", comment="полка 5")

    view = list_locations_view(session, place="полка 39")

    assert view["mode"] == "rows"
    assert [r["product"].code for r in view["rows"]] == ["D1"]
    # the picker still offers every place, not just the filtered one
    assert [p["place"] for p in view["places"]] == ["полка 5", "полка 39"]


def test_search_by_code_answers_where_it_lies(session):
    _stock(session, code="35532", name="Парфюмерная вода", comment="полка 39")
    _stock(session, code="30355", name="Другое", comment="полка 40")

    view = list_locations_view(session, q="35532")

    assert view["mode"] == "rows"
    assert [(r["product"].code, r["place"]) for r in view["rows"]] == [("35532", "полка 39")]


def test_search_by_cyrillic_name_is_case_insensitive(session):
    """D-27 regression: SQLite lower() folds ASCII only — the match is Python-side."""
    _stock(session, code="E1", name="Шейкер", comment="полка 87")

    view = list_locations_view(session, q="ШЕЙ")

    assert [r["product"].code for r in view["rows"]] == ["E1"]


def test_search_and_place_narrow_together(session):
    _stock(session, code="F1", name="Крем для рук", comment="полка 1")
    _stock(session, code="F2", name="Крем для лица", comment="полка 2")

    view = list_locations_view(session, q="крем", place="полка 2")

    assert [r["product"].code for r in view["rows"]] == ["F2"]


def test_out_of_range_page_reports_the_page_it_rendered(session):
    for i in range(25):
        _stock(session, code=f"G{i:02d}", name=f"Товар {i:02d}", comment="полка 1")

    view = list_locations_view(session, place="полка 1", page=99)

    assert view["total"] == 25
    assert view["total_pages"] == 2
    assert view["page"] == 1  # clamped, and the bar must highlight the rendered page
    assert len(view["rows"]) == 5


# --- page wiring ---


def test_locations_page_renders_places_and_is_linked_from_products(client, session):
    _stock(session, code="H1", name="Товар", quantity=6, comment="полка 59")

    page = client.get("/locations")
    assert page.status_code == 200
    assert "Места хранения" in page.text
    assert "полка 59" in page.text

    products = client.get("/products")
    assert 'href="/locations"' in products.text


def test_locations_search_returns_the_place(client, session):
    _stock(session, code="35532", name="Парфюмерная вода", comment="полка 39")

    page = client.get("/locations", params={"q": "35532"})

    assert page.status_code == 200
    assert "полка 39" in page.text


def test_hx_request_gets_the_fragment_only(client, session):
    _stock(session, code="I1", name="Товар", comment="полка 1")

    fragment = client.get("/locations", headers={"HX-Request": "true"})

    assert fragment.status_code == 200
    assert fragment.text.lstrip().startswith('<div id="location-rows">')
    assert "<!doctype html>" not in fragment.text.lower()  # no page chrome


def test_nav_section_highlights_products():
    assert nav_section("/locations") == "products"
