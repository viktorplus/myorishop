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

import ast
import types
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.core import new_id
from app.models import CatalogPrice, Dictionary
from app.services.rubrics import RUBRIC_OVERRIDES
from scripts.import_master_pricelist import (
    DictionaryReplaceRefused,
    apply_master_import,
    backup_before_replace,
    build_catalog_price_records,
    build_catalog_price_rows,
    build_dictionary_rows,
    collect_price_rows,
    insert_missing_dictionary_rows,
    override_only_rows,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MASTER = PROJECT_ROOT / "catalogs" / "oriflame_prices_with_calculations_fixed.xlsx"
SCRIPT = PROJECT_ROOT / "scripts" / "import_master_pricelist.py"

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


# ---------------------------------------------------------------------------
# Quick task 260902-m9g — the master import no longer annihilates the archive.
#
# `dictionary` is still replaced wholesale (that table has its own rules), but
# `catalog_prices` is only UPSERTED: this script owns the (year, number, code)
# triples it itself carries and nothing else. Before this task it deleted every
# row, so running it after the price-list archive walk erased 223 386 rows.
# ---------------------------------------------------------------------------

# A code that is neither FAKE_CODE nor an override — it must be gone from the
# dictionary after a full-replace import, while its price row survives.
FOREIGN_DICT_CODE = "888888"


def test_apply_master_import_replaces_the_dictionary_but_only_upserts_prices(session):
    session.add(
        Dictionary(
            id=new_id(),
            code=FOREIGN_DICT_CODE,
            name="Чужой код",
            name_lc="чужой код",
            catalogs=["01_26"],
        )
    )
    session.add(
        CatalogPrice(
            id=new_id(), year=2013, number=12, code="46413",
            name="ИЗ АРХИВА", consumer_cents=19900, consultant_cents=12900, points=2,
        )
    )
    session.commit()

    apply_master_import(session, {FAKE_CODE: dict(FAKE_ROW)})
    session.commit()

    archived = session.scalar(select(CatalogPrice).where(CatalogPrice.code == "46413"))
    assert archived is not None, "the archive row of a foreign triple must survive"
    assert (archived.year, archived.number, archived.points) == (2013, 12, 2)

    gone = session.scalar(select(Dictionary).where(Dictionary.code == FOREIGN_DICT_CODE))
    assert gone is None, "dictionary is still replaced wholesale"

    priced = session.scalar(
        select(func.count()).select_from(CatalogPrice).where(CatalogPrice.code == FAKE_CODE)
    )
    assert priced == 1


def test_apply_master_import_does_not_erase_the_bonus_points_of_its_own_triple(session):
    """The master price list carries no ББ at all — its NULL must not win."""
    session.add(
        CatalogPrice(
            id=new_id(),
            year=FAKE_ROW["year"],
            number=FAKE_ROW["number"],
            code=FAKE_CODE,
            name="ИЗ АРХИВА",
            consumer_cents=1,
            consultant_cents=None,
            points=17,
        )
    )
    session.commit()

    apply_master_import(session, {FAKE_CODE: dict(FAKE_ROW)})
    session.commit()

    row = session.scalar(select(CatalogPrice).where(CatalogPrice.code == FAKE_CODE))
    assert row.points == 17, "the archive's bonus points survive the master import"
    assert row.consumer_cents == FAKE_ROW["consumer_cents"], "the master price wins"
    assert row.consultant_cents == FAKE_ROW["consultant_cents"]
    assert session.scalar(select(func.count()).select_from(CatalogPrice)) == 1


def test_build_catalog_price_records_is_the_seven_key_export_shape():
    records = build_catalog_price_records({FAKE_CODE: dict(FAKE_ROW)})

    assert len(records) == 1
    assert set(records[0]) == {
        "code", "year", "number", "name", "consumer_cents", "consultant_cents", "points",
    }
    assert records[0]["code"] == FAKE_CODE
    assert records[0]["points"] is None, "the master price list has no ББ column"


# ---------------------------------------------------------------------------
# Quick task 260902-tev — CR-01: the wholesale `dictionary` replace is guarded,
# and the operator gets a snapshot plus the skip statistics BEFORE the delete.
#
# The input goes empty silently and plausibly: the headers are all in place, but
# every row is dropped by `skipped_bad_catalog` when the «Последний каталог»
# column changes shape in a new export. Before this task that turned a full
# replace into a wipe, and the statistics that would have shown it were printed
# after `session.commit()`.
# ---------------------------------------------------------------------------


def _seeded_dictionary_row(session, code: str) -> None:
    session.add(
        Dictionary(
            id=new_id(), code=code, name="Живая строка", name_lc="живая строка", catalogs=[]
        )
    )
    session.commit()


def test_apply_master_import_refuses_an_empty_price_list(session):
    """A degraded parse must not be able to empty the справочник."""
    _seeded_dictionary_row(session, "555555")
    before = session.scalar(select(func.count()).select_from(Dictionary))

    with pytest.raises(DictionaryReplaceRefused):
        apply_master_import(session, {})

    session.rollback()
    assert session.scalar(select(func.count()).select_from(Dictionary)) == before
    kept = session.scalar(select(Dictionary).where(Dictionary.code == "555555"))
    assert kept is not None, "the guard fires BEFORE the delete"


def test_apply_master_import_refuses_a_replace_that_would_shrink_the_dictionary(session):
    """The s1 case: 12 582 stored codes replaced by the 6 856 a price list covers."""
    # Never hardcode the override count — it grows. Ask the function itself.
    planned = len(build_dictionary_rows({FAKE_CODE: dict(FAKE_ROW)}))
    session.bulk_save_objects(
        [
            Dictionary(
                id=new_id(),
                code=f"77{i:05d}",
                name=f"Строка {i}",
                name_lc=f"строка {i}",
                catalogs=[],
            )
            for i in range(planned + 1)
        ]
    )
    session.commit()

    with pytest.raises(DictionaryReplaceRefused) as exc:
        apply_master_import(session, {FAKE_CODE: dict(FAKE_ROW)})

    session.rollback()
    assert session.scalar(select(func.count()).select_from(Dictionary)) == planned + 1

    # ACTIONABLE, not merely alarming: an operator who hits this must be able to
    # read the way out of the message instead of reaching for --force reflexively.
    message = str(exc.value)
    assert str(planned + 1) in message, message
    assert str(planned) in message, message
    assert "import_catalogs.py" in message, message
    assert "--force" in message, message


def test_force_allows_the_shrinking_replace(session):
    planned = len(build_dictionary_rows({FAKE_CODE: dict(FAKE_ROW)}))
    session.bulk_save_objects(
        [
            Dictionary(
                id=new_id(),
                code=f"77{i:05d}",
                name=f"Строка {i}",
                name_lc=f"строка {i}",
                catalogs=[],
            )
            for i in range(planned + 1)
        ]
    )
    session.commit()

    apply_master_import(session, {FAKE_CODE: dict(FAKE_ROW)}, force=True)
    session.commit()

    assert session.scalar(select(func.count()).select_from(Dictionary)) == planned


def test_backup_before_replace_takes_a_vacuum_snapshot(engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))

    snapshot = backup_before_replace(engine)

    assert snapshot is not None
    assert snapshot.is_file()
    assert snapshot.parent == tmp_path
    assert snapshot.match("myorishop-*.db")
    assert snapshot.stat().st_size > 0


def test_backup_before_replace_is_a_printed_noop_on_postgresql(tmp_path, monkeypatch, capsys):
    """A server run must not crash on VACUUM INTO — and must not stay silent."""
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))
    postgres = types.SimpleNamespace(dialect=types.SimpleNamespace(name="postgresql"))

    assert backup_before_replace(postgres) is None

    assert list(tmp_path.iterdir()) == [], "nothing is written on a non-SQLite dialect"
    assert capsys.readouterr().out.strip(), "the skip must be reported, not silent"


def test_a_failed_snapshot_aborts_the_import(engine, session, tmp_path, monkeypatch):
    """A snapshot that cannot be taken must abort, never degrade to a warning.

    The behaviour is free today — the point of the test is to stop a future
    `except Exception: print(...)` from quietly demoting the last line of defence.
    """
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))

    def boom(*_args, **_kwargs):
        raise OSError("no space left on device")

    monkeypatch.setattr("scripts.import_master_pricelist.create_backup", boom)
    _seeded_dictionary_row(session, "555555")

    with pytest.raises(OSError):
        backup_before_replace(engine)

    assert session.scalar(select(Dictionary).where(Dictionary.code == "555555")) is not None


def _main_function(path: Path) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )


def test_the_operator_sees_the_statistics_and_the_backup_before_anything_is_written():
    """Print order as a tripwire: statistics after the commit are useless."""
    main = _main_function(SCRIPT)

    stats_line = min(
        node.lineno
        for node in ast.walk(main)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "Rows skipped" in node.value
    )
    backup_call = min(
        node.lineno
        for node in ast.walk(main)
        if isinstance(node, ast.Call) and "backup_before_replace" in ast.unparse(node)
    )
    session_block = max(
        node.lineno
        for node in ast.walk(main)
        if isinstance(node, ast.With) and "SessionLocal" in ast.unparse(node.items[0])
    )

    assert stats_line < session_block, "the skip statistics are printed after the write"
    assert backup_call < session_block, "the snapshot is taken after the write"
