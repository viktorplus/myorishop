"""Executable contract for the override-only branch of
scripts/import_master_pricelist.py (quick task 260902-1d1).

A справочник code can exist as a real product and still appear in NO price
list — the 34 codes of the «Офис» inventory of 2026-08-31 are exactly that.
Such a code has a name and a rubric (from RUBRIC_OVERRIDES) but никогда a
price, so the importer must be able to produce a dictionary row with
``catalogs == []`` and NO catalog_prices row at all.

These tests are the ONLY proof of that branch: the importer is never run
against the operator's data/myorishop.db (a full-replace run there would drop
~5658 dictionary rows). Everything below works on synthetic data, on the
`session` fixture, or read-only on the tracked master price list.
"""

from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import CatalogPrice, Dictionary
from app.services.rubrics import RUBRIC_OVERRIDES
from scripts.import_master_pricelist import (
    build_catalog_price_rows,
    build_dictionary_rows,
    collect_price_rows,
    insert_missing_dictionary_rows,
    override_only_rows,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MASTER = PROJECT_ROOT / "catalogs" / "oriflame_prices_with_calculations_fixed.xlsx"

# The 34 «НЕТ В СПРАВОЧНИКЕ» codes of the «Офис» inventory — the complete,
# intended override-only set. If the real-price-list gap test below reports
# MORE codes than these, do NOT relax it: an unrelated code would silently
# gain a priceless dictionary row on the next import.
EXPECTED_34 = {
    "0305", "1071", "1998", "2054", "2060", "2393", "4631", "4773", "4840",
    "4883", "5056", "6795", "7049", "9514", "11215", "12584", "12663",
    "12759", "14685", "14767", "15824", "16352", "16983", "17320", "17437",
    "18367", "20281", "20573", "26847", "28608", "33596", "38490", "42922",
    "103311",
}

# One synthetic price-list code that is NOT an override, with a name that
# needs no correction — stands in for "an ordinary priced product".
FAKE_CODE = "999999"
FAKE_ROW = {
    "name": "Тестовый шампунь для волос",
    "year": 2026,
    "number": 9,
    "consumer_cents": 59900,
    "consultant_cents": 39900,
}


def test_override_only_rows_keeps_codes_absent_from_the_price_list():
    """Everything in RUBRIC_OVERRIDES minus the codes the price list covers."""
    extra = override_only_rows({"111249"})

    assert "111249" not in extra, "a code present in the price list must be excluded"
    assert len(extra) == len(RUBRIC_OVERRIDES) - 1
    assert set(extra) == set(RUBRIC_OVERRIDES) - {"111249"}
    assert extra["0305"] == RUBRIC_OVERRIDES["0305"]


def test_build_dictionary_rows_adds_priceless_rows_for_override_only_codes():
    collected = {FAKE_CODE: dict(FAKE_ROW)}

    dict_rows = build_dictionary_rows(collected)
    by_code = {row.code: row for row in dict_rows}

    # Unchanged behaviour for a price-list code: single-element catalogs.
    priced = by_code[FAKE_CODE]
    assert priced.catalogs == ["09_26"]
    assert priced.name == FAKE_ROW["name"]
    assert priced.name_lc == FAKE_ROW["name"].lower()
    assert priced.rubric == "Уход за волосами"

    # New behaviour: every override code absent from `collected` is present
    # with a name, a rubric and NO catalog at all.
    priceless = by_code["0305"]
    assert priceless.catalogs == []
    assert priceless.name == "Не опознан (код 0305)"
    assert priceless.name_lc == "не опознан (код 0305)"
    assert priceless.rubric == "Прочее"
    assert len(dict_rows) == 1 + len(RUBRIC_OVERRIDES)


def test_build_catalog_price_rows_never_prices_an_override_only_code():
    collected = {FAKE_CODE: dict(FAKE_ROW)}

    price_rows = build_catalog_price_rows(collected)

    assert [row.code for row in price_rows] == [FAKE_CODE]
    assert not any(row.code in RUBRIC_OVERRIDES and row.code != FAKE_CODE for row in price_rows)
    assert price_rows[0].consumer_cents == FAKE_ROW["consumer_cents"]
    assert price_rows[0].consultant_cents == FAKE_ROW["consultant_cents"]


def test_priceless_dictionary_row_persists_without_any_catalog_price(session):
    """The rows survive a real insert+commit: dictionary yes, price no."""
    collected = {FAKE_CODE: dict(FAKE_ROW)}

    session.bulk_save_objects(build_dictionary_rows(collected))
    session.bulk_save_objects(build_catalog_price_rows(collected))
    session.commit()

    stored = session.scalar(select(Dictionary).where(Dictionary.code == "0305"))
    assert stored is not None
    assert stored.catalogs == []
    assert stored.name == "Не опознан (код 0305)"
    assert stored.rubric == "Прочее"

    prices_for_0305 = session.scalar(
        select(func.count()).select_from(CatalogPrice).where(CatalogPrice.code == "0305")
    )
    assert prices_for_0305 == 0

    prices_for_fake = session.scalar(
        select(func.count()).select_from(CatalogPrice).where(CatalogPrice.code == FAKE_CODE)
    )
    assert prices_for_fake == 1


def test_insert_missing_dictionary_rows_is_additive_and_idempotent(session):
    """Inserts only what is missing, never deletes, never writes a price."""
    existing = Dictionary(
        code="0305", name="Уже есть", name_lc="уже есть", catalogs=["01_26"]
    )
    session.add(existing)
    session.commit()

    extra = {code: RUBRIC_OVERRIDES[code] for code in ("0305", "1071", "1998")}

    inserted = insert_missing_dictionary_rows(session, extra)
    session.commit()

    assert sorted(inserted) == ["1071", "1998"], "an existing code must be skipped"
    assert session.scalar(select(func.count()).select_from(Dictionary)) == 3

    # The pre-existing row is untouched — no update, no overwrite.
    untouched = session.scalar(select(Dictionary).where(Dictionary.code == "0305"))
    assert untouched.name == "Уже есть"
    assert untouched.catalogs == ["01_26"]

    new_row = session.scalar(select(Dictionary).where(Dictionary.code == "1071"))
    assert new_row.catalogs == []
    assert new_row.name == RUBRIC_OVERRIDES["1071"]["name"]
    assert new_row.name_lc == RUBRIC_OVERRIDES["1071"]["name"].lower()
    assert new_row.rubric == RUBRIC_OVERRIDES["1071"]["rubric"]

    # Second call is a no-op.
    assert insert_missing_dictionary_rows(session, extra) == []
    session.commit()
    assert session.scalar(select(func.count()).select_from(Dictionary)) == 3
    assert session.scalar(select(func.count()).select_from(CatalogPrice)) == 0


@pytest.mark.skipif(not MASTER.is_file(), reason=f"master price list not available: {MASTER}")
def test_gap_against_the_real_price_list_is_exactly_the_34_inventory_codes():
    """Read-only gate against the tracked master price list.

    RED with extra codes means some unrelated override would gain a priceless
    dictionary row on the next import — report the extras, do not relax this.
    """
    collected, _stats = collect_price_rows(MASTER)

    gap = set(override_only_rows(set(collected)))

    unexpected = sorted(gap - EXPECTED_34)
    missing = sorted(EXPECTED_34 - gap)
    assert not unexpected, f"unexpected override-only codes: {unexpected}"
    assert not missing, f"expected codes found in the price list: {missing}"
    assert gap == EXPECTED_34
