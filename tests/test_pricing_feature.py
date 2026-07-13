"""CAT-05: per-catalog prices + product-form price autofill."""

import pytest

from app.core import new_id
from app.models import CatalogPrice
from app.services.pricing import (
    latest_price_for_code,
    price_history_for_code,
    prices_for_catalog,
)


def _price(code, year, number, consumer=None, consultant=None, points=None, name=None):
    return CatalogPrice(
        id=new_id(),
        code=code,
        year=year,
        number=number,
        consumer_cents=consumer,
        consultant_cents=consultant,
        points=points,
        name=name,
    )


@pytest.fixture()
def priced(session):
    session.add_all(
        [
            _price("100", 2025, 3, consumer=1000, consultant=600),
            _price("100", 2026, 1, consumer=1200, consultant=700),  # newest
            _price("100", 2025, 12, consumer=1100, consultant=650),
            _price("200", 2026, 1, consumer=500),  # no consultant price
        ]
    )
    session.commit()
    return session


# --- service ---------------------------------------------------------------


def test_latest_price_picks_newest_catalog(priced):
    latest = latest_price_for_code(priced, "100")
    assert (latest.year, latest.number) == (2026, 1)
    assert latest.consumer_cents == 1200
    assert latest.consultant_cents == 700


def test_latest_price_unknown_code_is_none(priced):
    assert latest_price_for_code(priced, "999") is None
    assert latest_price_for_code(priced, "") is None


def test_price_history_newest_first(priced):
    hist = price_history_for_code(priced, "100")
    assert [(p.year, p.number) for p in hist] == [(2026, 1), (2025, 12), (2025, 3)]


def test_prices_for_catalog_maps_by_code(priced):
    prices = prices_for_catalog(priced, 2026, 1)
    assert set(prices) == {"100", "200"}
    assert prices["200"].consumer_cents == 500


# --- autofill route --------------------------------------------------------


def test_price_autofill_fills_empty_fields(priced, client):
    r = client.get("/products/lookup-price", params={"code": "100", "cost": "", "catalog": ""})
    assert r.status_code == 200
    # catalog price 1200 cents -> "12,00"; consultant 700 -> "7,00"
    assert 'id="catalog"' in r.text and "12,00" in r.text
    assert 'id="cost"' in r.text and "7,00" in r.text
    assert 'hx-swap-oob="true"' in r.text


def test_price_autofill_never_overwrites_filled_fields(priced, client):
    r = client.get("/products/lookup-price", params={"code": "100", "cost": "5", "catalog": "9"})
    assert r.status_code == 204


def test_price_autofill_partial_when_no_consultant(priced, client):
    r = client.get("/products/lookup-price", params={"code": "200", "cost": "", "catalog": ""})
    assert r.status_code == 200
    assert 'id="catalog"' in r.text
    assert 'id="cost"' not in r.text  # code 200 has no consultant price


def test_price_autofill_unknown_code_is_noop(priced, client):
    r = client.get("/products/lookup-price", params={"code": "999", "cost": "", "catalog": ""})
    assert r.status_code == 204


# --- filename parsing (import script) --------------------------------------


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("01-2026.xlsx", (2026, 1)),
        ("03_2024.xlsx", (2024, 3)),
        ("2025-07.xlsx", (2025, 7)),
        ("25-11.xlsx", (2025, 11)),
        ("01-2025_calc.xlsx", (2025, 1)),
        ("01-2026_ (1).xlsx", (2026, 1)),
        ("17-2024-calc.xlsx", (2024, 17)),
    ],
)
def test_import_filename_parsing(filename, expected):
    from scripts.import_prices import parse_catalog

    assert parse_catalog(filename) == expected
