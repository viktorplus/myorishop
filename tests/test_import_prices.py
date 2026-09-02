"""Executable contract for scripts/import_prices.py (quick task 260902-g1q).

The 118 MB `catalogs/price_lists/` archive is deliberately kept out of git and
out of the Docker image, so the JSON export is the ONLY transport that can
carry the price history to the server. That makes four things load-bearing:

1. the export round-trips with no loss — including a leading-zero code that
   must stay a string and a row with NULL name/points;
2. the export is ACCUMULATIVE — a row that lives only in the target file
   survives (SPEC «выгрузка накопительная, а не замещающая»);
3. ``--only-missing`` filters by CODE and never deletes or updates, so the
   server's master-price rows cannot be duplicated or shadowed;
4. openpyxl is imported lazily — it is a dev dependency and the image is built
   with `uv sync --frozen --no-dev`, so a module-level import would make this
   script unimportable exactly where --from-export has to run.

The importer is NEVER run against the operator's data/myorishop.db: everything
below is synthetic data on the `session` fixture or a tmp_path file.
"""

import ast
import json
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import CatalogPrice
from scripts.import_prices import (
    EXPORT_KEYS,
    MAX_NAME,
    atomic_write,
    build_price_rows,
    build_shade_overrides,
    collect_from_archive,
    collect_prices_from_sheets,
    collect_shade_candidates,
    current_name,
    display_name,
    export_prices,
    insert_missing_price_rows,
    is_shade_row,
    load_export,
    merge_overrides,
    merge_price_export,
    parse_catalog,
    pick_full_name,
    price_list_files,
    restore_full_name,
    serialize_export,
    shade_text,
    split_series_type,
    upsert_price_rows,
    validate_records,
    write_export,
    write_overrides,
)

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "import_prices.py"
MASTER_SCRIPT = (
    Path(__file__).resolve().parent.parent / "scripts" / "import_master_pricelist.py"
)

# "0305" is a real leading-zero code: it must survive as a string, never as 305.
ZERO_ROW = {
    "code": "0305",
    "year": 2026,
    "number": 1,
    "name": None,
    "consumer_cents": 59900,
    "consultant_cents": 39900,
    "points": None,
}
PLAIN_ROW = {
    "code": "46413",
    "year": 2025,
    "number": 17,
    "name": "ШАМПУНЬ ДЛЯ ВОЛОС",
    "consumer_cents": 49900,
    "consultant_cents": 29900,
    "points": 3,
}


def _tuples(records):
    return {tuple(r[k] for k in sorted(EXPORT_KEYS)) for r in records}


def _seed(session, *records):
    session.bulk_save_objects(build_price_rows(list(records)))
    session.commit()


def test_export_prices_projects_seven_fields_in_constraint_order(session):
    _seed(session, PLAIN_ROW, ZERO_ROW)

    records = export_prices(session)

    assert [r["code"] for r in records] == ["46413", "0305"], "ordered by (year, number, code)"
    assert all(set(r) == set(EXPORT_KEYS) for r in records)
    assert records[1]["code"] == "0305", "a leading-zero code stays a string"
    assert records[1]["name"] is None and records[1]["points"] is None


def test_serialize_export_is_valid_json_one_record_per_line():
    text = serialize_export([PLAIN_ROW, ZERO_ROW])

    assert json.loads(text) == [PLAIN_ROW, ZERO_ROW]
    assert len(text.strip().splitlines()) == 4, "[ + one line per record + ]"
    assert serialize_export([]) == "[]\n"


@pytest.mark.parametrize(
    "payload",
    [
        {"not": "a list"},
        [["not", "an", "object"]],
        [{k: v for k, v in PLAIN_ROW.items() if k != "points"}],
        [{**PLAIN_ROW, "code": 46413}],
        [{**PLAIN_ROW, "year": "2025"}],
        [{**PLAIN_ROW, "number": True}],
        # 260902-tev / CR-02: the four money and name fields the .gz transport
        # carried unchecked. A float lands in an INTEGER money column (SQLite
        # stores REAL, PostgreSQL aborts the transaction); a string reaches
        # format_cents() through reference_prices_for_code() and 500s the page.
        [{**PLAIN_ROW, "consumer_cents": 599.5}],
        [{**PLAIN_ROW, "consultant_cents": "не указано"}],
        [{**PLAIN_ROW, "points": "3"}],
        [{**PLAIN_ROW, "points": True}],  # bool is an int subclass
        [{**PLAIN_ROW, "consumer_cents": -1}],
        [{**PLAIN_ROW, "name": 46413}],
        [{**PLAIN_ROW, "name": "х" * (MAX_NAME + 1)}],  # CatalogPrice.name is String(200)
    ],
)
def test_load_export_refuses_malformed_input(tmp_path, payload):
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        load_export(path)

    assert str(exc.value), "the failure must name what is wrong"


def test_validate_records_accepts_a_stored_zero_and_a_null():
    """The contract is >= 0, not > 0 — and None still means «this source has none».

    export_prices() reads whatever the database holds, so a legitimate
    re-export of a stored zero must not be rejected by the transport.
    """
    records = [
        {
            **PLAIN_ROW,
            "consumer_cents": 0,
            "points": 0,
            "consultant_cents": None,
            "name": None,
        }
    ]

    assert validate_records(records, "test") == records


def test_build_price_rows_carries_every_field_verbatim():
    rows = build_price_rows([ZERO_ROW])

    assert rows[0].code == "0305"
    assert rows[0].year == 2026 and rows[0].number == 1
    assert rows[0].name is None and rows[0].points is None
    assert rows[0].consumer_cents == 59900
    assert rows[0].consultant_cents == 39900


def test_insert_missing_price_rows_filters_by_code_and_is_idempotent(session):
    _seed(session, PLAIN_ROW)
    # The same code with a DIFFERENT (year, number) must still be skipped: the
    # server's master-price row for that code must not be shadowed.
    incoming = [
        {**PLAIN_ROW, "year": 2019, "number": 4, "consumer_cents": 19900},
        ZERO_ROW,
    ]

    inserted = insert_missing_price_rows(session, incoming)
    session.commit()

    assert [r["code"] for r in inserted] == ["0305"]
    assert session.scalar(select(func.count()).select_from(CatalogPrice)) == 2
    kept = session.scalar(select(CatalogPrice).where(CatalogPrice.code == "46413"))
    assert (kept.year, kept.number, kept.consumer_cents) == (2025, 17, 49900)

    # Second call inserts nothing and deletes nothing.
    assert insert_missing_price_rows(session, incoming) == []
    session.commit()
    assert session.scalar(select(func.count()).select_from(CatalogPrice)) == 2


def test_export_round_trips_through_the_file_with_no_loss(session, tmp_path):
    _seed(session, PLAIN_ROW, ZERO_ROW)
    path = tmp_path / "catalog_prices.json"
    path.write_text(serialize_export(export_prices(session)), encoding="utf-8")

    restored = load_export(path)
    session.query(CatalogPrice).delete()
    session.commit()
    insert_missing_price_rows(session, restored)
    session.commit()

    assert _tuples(export_prices(session)) == _tuples([PLAIN_ROW, ZERO_ROW])


def test_merge_export_keeps_rows_the_database_no_longer_has():
    """SPEC: выгрузка накопительная — the file can only grow."""
    merged, stats = merge_price_export([PLAIN_ROW], [ZERO_ROW])

    assert _tuples(merged) == _tuples([PLAIN_ROW, ZERO_ROW])
    assert stats == {"before": 1, "added": 1, "updated": 0, "after": 2}
    assert stats["after"] >= stats["before"]


def test_write_export_into_an_existing_file_preserves_a_foreign_row(tmp_path):
    """The file-level proof of the accumulative rule, end to end."""
    dest = tmp_path / "catalog_prices.json"
    dest.write_text(serialize_export([PLAIN_ROW]), encoding="utf-8")

    stats = write_export(dest, [{**PLAIN_ROW, "points": 9}, ZERO_ROW])

    on_disk = load_export(dest)
    assert stats == {"before": 1, "added": 1, "updated": 1, "after": 2, "codes": 2}
    assert [r["code"] for r in on_disk] == ["46413", "0305"]
    assert on_disk[0]["points"] == 9

    # A second export from a database that knows NOTHING cannot shrink the file.
    shrunk = write_export(dest, [])
    assert shrunk["after"] == 2 and shrunk["added"] == 0
    assert len(load_export(dest)) == 2


@pytest.mark.parametrize("package", ["openpyxl", "xlrd"])
def test_excel_readers_are_not_imported_at_module_level(package):
    """The image is built with `uv sync --frozen --no-dev`.

    openpyxl is dev-only and xlrd is not a project dependency AT ALL (it is
    reached ad hoc through `uv run --with xlrd`), so a module-level import of
    either would make this script unimportable exactly where --from-export has
    to run.
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    top_level = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            top_level.append(node.module or "")

    assert not any(package in name for name in top_level), top_level


# ---------------------------------------------------------------------------
# --restore-shades (quick task 260902-k2i)
#
# In an Oriflame price list the product type is written ONCE, in the first row
# of a series; every following row is a bare shade («- ФАРФОРОВЫЙ»). The rows
# below are the exact 33154-33159 series of the SPEC, verified by hand in
# 01-2018.xls and 01-2019.xlsx.
# ---------------------------------------------------------------------------

HEADER = ("КОД", "НАИМЕНОВАНИЕ", "ПЦ")
SERIES_TYPE = "УВЛАЖНЯЮЩАЯ ТОНАЛЬНАЯ ОСНОВА THE ONE AQUA BOOST"
SERIES_SHEET = [
    ("ПРАЙС-ЛИСТ 01-2018", None, None),
    HEADER,
    (33154, f"{SERIES_TYPE} - ВАНИЛЬНЫЙ", 599),
    (33155, "- ФАРФОРОВЫЙ", 599),
    (33156, "- БЕЖЕВЫЙ НЮД", 599),
    (33157, "- РОЗОВЫЙ НЮД", 599),
    (33158, "- СЛОНОВАЯ КОСТЬ", 599),
    (33159, "- ЕСТЕСТВЕННЫЙ БЕЖ", 599),
    (None, None, None),
]
ARCHIVE = Path(__file__).resolve().parent.parent / "catalogs" / "price_lists"


def test_split_series_type_cuts_at_the_last_separator():
    assert split_series_type(f"{SERIES_TYPE} - ВАНИЛЬНЫЙ") == SERIES_TYPE
    assert split_series_type("ТОНАЛЬНАЯ ОСНОВА") == "ТОНАЛЬНАЯ ОСНОВА", "no separator"
    assert split_series_type("ТУШЬ THE ONE - LASH - ЧЁРНЫЙ") == "ТУШЬ THE ONE - LASH"
    assert split_series_type("КРЕМ – ДНЕВНОЙ") == "КРЕМ", "en dash"
    assert split_series_type("КРЕМ — НОЧНОЙ") == "КРЕМ", "em dash"


def test_shade_row_detection_and_text():
    assert is_shade_row("- ФАРФОРОВЫЙ")
    assert is_shade_row("  – ВАНИЛЬ")
    assert not is_shade_row(SERIES_TYPE)
    assert shade_text(" -- ФАРФОРОВЫЙ ") == "ФАРФОРОВЫЙ"


def test_collect_shade_candidates_inherits_the_series_type():
    candidates, dropped = collect_shade_candidates([SERIES_SHEET])

    assert sorted(candidates) == ["33155", "33156", "33157", "33158", "33159"]
    assert "33154" not in candidates, "the header row is not a shade of itself"
    assert dropped == 0
    assert candidates["33155"] == Counter({(SERIES_TYPE, "ФАРФОРОВЫЙ"): 1})


def test_a_shade_with_no_series_type_is_dropped_and_counted():
    sheet = [
        HEADER,
        (33155, "- ФАРФОРОВЫЙ", 599),  # before any header row
        (33154, f"{SERIES_TYPE} - ВАНИЛЬНЫЙ", 599),
        (None, "МАКИЯЖ", None),  # a code-less title ends the series
        (33160, "- ЯРКИЙ", 599),
    ]

    candidates, dropped = collect_shade_candidates([sheet])

    assert candidates == {}
    assert dropped == 2


def test_longest_type_wins_over_the_most_frequent_spelling():
    short = [HEADER, (33154, "ТОН. ОСНОВА - ВАНИЛЬНЫЙ", 1), (33155, "- ФАРФОРОВЫЙ", 1)]
    long = [HEADER, (33154, "ТОНАЛЬНАЯ ОСНОВА - ВАНИЛЬНЫЙ", 1), (33155, "- ФАРФОРОВЫЙ", 1)]

    candidates, _ = collect_shade_candidates([short, short, short, long])

    assert pick_full_name(candidates["33155"]) == "ТОНАЛЬНАЯ ОСНОВА - ФАРФОРОВЫЙ"


def test_equal_length_types_fall_back_to_the_most_frequent_then_deterministically():
    counter = Counter({("ТУШЬ ЛАЙН", "ЧЁРНЫЙ"): 1, ("ТУШЬ ГЛЭМ", "ЧЁРНЫЙ"): 5})
    assert pick_full_name(counter) == "ТУШЬ ГЛЭМ - ЧЁРНЫЙ"

    tie = Counter({("ТУШЬ ЛАЙН", "ЧЁРНЫЙ"): 3, ("ТУШЬ ГЛЭМ", "ЧЁРНЫЙ"): 3})
    assert pick_full_name(tie) == pick_full_name(Counter(dict(reversed(tie.items()))))


def test_display_name_is_the_dictionarys_sentence_case():
    assert display_name(f"{SERIES_TYPE} - ФАРФОРОВЫЙ") == (
        "Увлажняющая тональная основа the one aqua boost - фарфоровый"
    )
    assert display_name("  ТУШЬ   THE\tONE  ") == "Тушь the one", "whitespace runs collapse"
    assert display_name("") == ""


def _products(**names):
    return {code: {"name": name, "catalogs": []} for code, name in names.items()}


def test_restore_full_name_matches_the_shade_of_any_variant_not_the_best_one():
    """The SPEC's load-bearing rule. Comparing against ONE «best» variant is the
    methodology error it forbids: the same code is a series header in one price
    list and a shade row in another."""
    counter = Counter(
        {
            # the LONGEST type, but a shade the справочник does not carry
            ("УЛЬТРАСТОЙКАЯ ТОНАЛЬНАЯ ОСНОВА THE ONE EVERLASTING", "ВАНИЛЬНЫЙ"): 4,
            ("ТОНАЛЬНАЯ ОСНОВА", "ФАРФОРОВЫЙ"): 1,
        }
    )
    # The «best» variant is the ВАНИЛЬНЫЙ one; the справочник says «Фарфоровый».
    assert pick_full_name(counter).endswith("ВАНИЛЬНЫЙ"), "precondition"

    assert restore_full_name(counter, "Фарфоровый") == "Тональная основа - фарфоровый"
    assert restore_full_name(counter, "Ванильный").endswith("everlasting - ванильный")
    assert restore_full_name(counter, "Медовый") is None, "no variant carries this shade"


def test_restore_full_name_takes_the_longest_type_among_the_matching_variants():
    counter = Counter(
        {
            ("ТОН. ОСНОВА", "ФАРФОРОВЫЙ"): 9,
            ("ТОНАЛЬНАЯ ОСНОВА", "ФАРФОРОВЫЙ"): 1,
        }
    )

    assert restore_full_name(counter, "фарфоровый") == "Тональная основа - фарфоровый"


def test_current_name_prefers_the_override_over_products_json():
    products = _products(**{"33155": "Фарфоровый"})
    assert current_name("33155", products, {}) == "Фарфоровый"
    assert current_name("33155", products, {"33155": {"name": "Исправлено"}}) == "Исправлено"
    assert current_name("33155", products, {"33155": {"name": "  "}}) == "Фарфоровый"
    assert current_name("нет", products, {}) == ""


def test_build_shade_overrides_selects_only_bare_shade_names():
    candidates, _ = collect_shade_candidates([SERIES_SHEET])
    products = _products(
        **{
            "33155": "Фарфоровый",
            # already carries a type -> equals no variant's shade -> untouched
            "33156": "Тональная основа бежевый нюд",
            "33157": "Розовый нюд",
        }
        # 33158 / 33159 are absent from products.json
    )

    fresh, stats = build_shade_overrides(candidates, products, existing={})

    assert sorted(fresh) == ["33155", "33157"]
    assert fresh["33155"] == {
        "conf": "series",
        "name": "Увлажняющая тональная основа the one aqua boost - фарфоровый",
        "rubric": "Макияж",
    }
    assert stats["selected"] == 2 and stats["appended"] == 2 and stats["updated"] == 0
    assert stats["no_shade_match"] == 1, "the name that already carries a type"
    assert stats["not_in_products"] == 2
    assert stats["codes"] == 5 and stats["in_products"] == 3


def test_an_existing_override_that_is_still_a_bare_shade_is_restored_in_place():
    """552 of the 607 are like this: an earlier task wrote the code into
    rubric_overrides.json WITH the bare shade as its name, and the override
    wins in resolve_name — so skipping them would undo the restoration."""
    candidates, _ = collect_shade_candidates([SERIES_SHEET])
    products = _products(**{"33155": "Фарфоровый"})
    existing = {"33155": {"conf": "high", "name": "Фарфоровый", "rubric": "Макияж"}}

    fresh, stats = build_shade_overrides(candidates, products, existing)

    assert fresh["33155"]["name"] == (
        "Увлажняющая тональная основа the one aqua boost - фарфоровый"
    )
    assert fresh["33155"]["conf"] == "high", "the entry keeps its own confidence"
    assert fresh["33155"]["rubric"] == "Макияж", "a web-verified rubric is never reclassified"
    assert stats["updated"] == 1 and stats["appended"] == 0


def test_an_existing_override_that_already_carries_a_type_is_left_alone():
    """The hand-corrected names (quick task 260721-oti) are out of reach."""
    candidates, _ = collect_shade_candidates([SERIES_SHEET])
    products = _products(**{"33155": "Фарфоровый"})
    existing = {
        "33155": {"conf": "high", "name": "Тональная основа фарфоровая", "rubric": "Макияж"}
    }

    fresh, stats = build_shade_overrides(candidates, products, existing)

    assert fresh == {}
    assert stats["selected"] == 0 and stats["no_shade_match"] == 1


def test_a_candidate_longer_than_200_chars_is_rejected_never_truncated():
    counter = Counter({("Т" * 250, "ФАРФОРОВЫЙ"): 1})
    candidates = {"33155": counter}

    fresh, stats = build_shade_overrides(
        candidates, _products(**{"33155": "Фарфоровый"}), existing={}
    )

    assert fresh == {}
    assert stats["rejected_too_long"] == 1


def test_the_rubric_can_never_get_worse_than_todays():
    """An unclassifiable restored name keeps the rubric the bare shade had."""
    unclassifiable = "ЗЗЗЗ ЫЫЫЫ ЭЭЭЭ ЮЮЮЮ ЪЪЪЪ ЩЩЩЩ"
    candidates = {"33155": Counter({(unclassifiable, "МЕДОВЫЙ"): 1})}

    fresh, _ = build_shade_overrides(
        candidates, _products(**{"33155": "Медовый"}), existing={}
    )

    assert fresh["33155"]["rubric"] == "Макияж", "fell back to the bare shade's rubric"


def test_merge_overrides_rewrites_only_the_name_and_never_moves_a_key():
    existing = {
        "999999": {"conf": "high", "name": "Первый", "rubric": "Прочее"},
        "111": {"conf": "medium", "name": "Второй", "rubric": "Украшения"},
    }
    fresh = {
        "222": {"conf": "series", "name": "Б", "rubric": "Макияж"},
        "111": {"conf": "series", "name": "Тушь - второй", "rubric": "Макияж"},
        "000": {"conf": "series", "name": "А", "rubric": "Макияж"},
    }

    merged = merge_overrides(existing, fresh)

    assert list(merged) == ["999999", "111", "000", "222"], "positions kept, new sorted last"
    assert merged["111"] == {
        "conf": "medium",  # untouched
        "name": "Тушь - второй",  # the ONLY field a restoration may change
        "rubric": "Украшения",  # untouched — web-verified beats a classifier
    }
    assert merged["999999"] == existing["999999"], "a code not being restored is identical"
    assert existing["111"]["name"] == "Второй", "the input dict is not mutated"


def test_write_overrides_reproduces_the_files_byte_form(tmp_path):
    dest = tmp_path / "rubric_overrides.json"

    write_overrides(dest, {"33155": {"conf": "series", "name": "Тушь", "rubric": "Макияж"}})

    raw = dest.read_bytes()
    assert raw.startswith(b'{\r\n "33155": {\r\n  "conf": "series",\r\n')
    assert raw.endswith(b"\r\n }\r\n}"), "CRLF, indent=1, NO trailing newline"
    assert "Тушь".encode() in raw, "ensure_ascii=False — Cyrillic stays readable"
    assert json.loads(raw.decode("utf-8"))["33155"]["rubric"] == "Макияж"


def test_price_list_files_takes_both_extensions_and_skips_lock_files(tmp_path):
    for name in ("01-2019.xlsx", "01-2018.xls", "~$01-2018.xls", "README.md", "x.csv"):
        (tmp_path / name).write_text("", encoding="utf-8")
    (tmp_path / "sub").mkdir()

    assert [p.name for p in price_list_files(tmp_path)] == ["01-2018.xls", "01-2019.xlsx"]
    assert price_list_files(tmp_path / "nowhere") == []


def test_the_two_real_price_lists_rebuild_the_33154_series():
    """The SPEC's hand-verified proof, against the real archive.

    Skips when xlrd is absent (it is NOT a project dependency — run it with
    `uv run --with xlrd pytest`) or when the gitignored archive is not on this
    machine. Reads ONLY the two named files, never the whole 118 MB folder.
    """
    pytest.importorskip("xlrd", reason="run with `uv run --with xlrd pytest`")
    from scripts.import_prices import read_workbook_sheets

    sheets = []
    for name in ("01-2018.xls", "01-2019.xlsx"):
        path = ARCHIVE / name
        if not path.is_file():
            pytest.skip(f"the price-list archive is not on this machine ({name})")
        sheets.extend(read_workbook_sheets(path))

    candidates, _dropped = collect_shade_candidates(sheets)

    expected = {
        "33155": "фарфоровый",
        "33156": "бежевый нюд",
        "33157": "розовый нюд",
        "33158": "слоновая кость",
        "33159": "естественный беж",
    }
    for code, shade in expected.items():
        assert code in candidates, f"{code} was not recovered from the real price lists"
        # Through the production path: the справочник holds the bare shade.
        name = restore_full_name(candidates[code], shade.capitalize())
        assert name is not None, code
        assert "тональная основа" in name, name
        assert name.endswith(f"- {shade}"), name


# ---------------------------------------------------------------------------
# Quick task 260902-m9g — a source owns its own (year, number, code) triples,
# never the whole table.
#
# `catalog_prices` was written by THREE table-wide deletes (the xlsx path, the
# --from-export path and the master price list), so whichever importer ran last
# erased the other's work and the table held a 15 798-row snapshot instead of a
# price history. The ownership key is the UniqueConstraint that already exists
# on (year, number, code); the tests below are its executable contract, plus the
# both-extension archive walk and the gzip transport.
# ---------------------------------------------------------------------------


def test_upsert_inserts_a_new_triple_and_leaves_a_foreign_row_untouched(session):
    """The rule in one sentence: a foreign triple is not this source's business."""
    _seed(session, PLAIN_ROW)

    stats = upsert_price_rows(session, [ZERO_ROW])
    session.commit()

    assert stats == {"inserted": 1, "updated": 0, "unchanged": 0}
    assert _tuples(export_prices(session)) == _tuples([PLAIN_ROW, ZERO_ROW])


def test_upsert_updates_only_what_changed_and_a_repeat_reports_unchanged(session):
    _seed(session, PLAIN_ROW)
    cheaper = {**PLAIN_ROW, "consumer_cents": 44400}

    first = upsert_price_rows(session, [cheaper])
    session.commit()

    assert first == {"inserted": 0, "updated": 1, "unchanged": 0}
    row = session.scalar(select(CatalogPrice).where(CatalogPrice.code == "46413"))
    assert row.consumer_cents == 44400
    assert row.consultant_cents == PLAIN_ROW["consultant_cents"], "untouched field"
    assert row.name == PLAIN_ROW["name"] and row.points == PLAIN_ROW["points"]

    second = upsert_price_rows(session, [cheaper])
    session.commit()

    assert second == {"inserted": 0, "updated": 0, "unchanged": 1}
    assert session.scalar(select(func.count()).select_from(CatalogPrice)) == 1


def test_upsert_never_overwrites_a_known_value_with_none(session):
    """The master-price-list-after-archive case — the whole reason for the rule.

    The master price list carries no bonus points at all. Without this rule its
    NULL `points` would null the 233 346 points the archive supplies.
    """
    _seed(session, PLAIN_ROW)
    impoverished = {**PLAIN_ROW, "points": None, "name": None}

    stats = upsert_price_rows(session, [impoverished])
    session.commit()

    assert stats == {"inserted": 0, "updated": 0, "unchanged": 1}
    row = session.scalar(select(CatalogPrice).where(CatalogPrice.code == "46413"))
    assert row.points == 3, "an incoming None never impoverishes a stored value"
    assert row.name == PLAIN_ROW["name"]


def test_upsert_never_deletes(session):
    _seed(session, PLAIN_ROW, ZERO_ROW)

    stats = upsert_price_rows(session, [])
    session.commit()

    assert stats == {"inserted": 0, "updated": 0, "unchanged": 0}
    assert _tuples(export_prices(session)) == _tuples([PLAIN_ROW, ZERO_ROW])


def test_parse_catalog_reads_xls_filenames_too():
    """D1: the price path must take BOTH extensions, so the name parser must too."""
    assert parse_catalog("01-2018.xls") == (2018, 1)
    assert parse_catalog("2013-12.xls") == (2013, 12)
    assert parse_catalog("01-2019.xlsx") == (2019, 1)
    assert parse_catalog("oriflame_prices_with_calculations_fixed.xlsx") is None


PRICE_HEADER = ("КОД", "НАИМЕНОВАНИЕ", "ПЦ", "ОП", "ББ")
PRICE_SHEET = [
    ("ПРАЙС-ЛИСТ 01-2018", None, None, None, None),
    PRICE_HEADER,
    (33154, "ТОНАЛЬНАЯ ОСНОВА - ВАНИЛЬНЫЙ", 599, 399, 3),
    (None, "МАКИЯЖ", None, None, None),  # a code-less section header
    (33155, "- ФАРФОРОВЫЙ", None, 399, 3),  # no ПЦ -> not a price row
    (33156, "- БЕЖЕВЫЙ НЮД", 649, None, None),
]
NAMES_ONLY_SHEET = [
    ("КОД", "НАИМЕНОВАНИЕ"),
    (33154, "ТОНАЛЬНАЯ ОСНОВА - ВАНИЛЬНЫЙ"),
]
# The REAL shape of 04-2024.xls / 05-2024.xls: an empty КАЛЬКУЛЯТОР template
# that DOES carry a ПЦ header, next to the actual price sheet, which carries
# ОП and ДЦ but no ПЦ. The file yields nothing and must still be named.
CALCULATOR_SHEET = [
    ("КОД", "КОЛ-ВО", "СКИДКА", "НАИМЕНОВАНИЕ", "ББ", "ОП", "ДЦ", "ПЦ"),
    ("", "", "", "С У М М А", 0, 0, 0, 0),
    ("", "", " ", " ", " ", " ", " ", " "),
]
NO_CONSUMER_SHEET = [
    ("КОД", "СКИДКА", "СТР.", "АКЦИЯ", "НАИМЕНОВАНИЕ ", "ББ", "ОП", "ДЦ"),
    ("НОВИНКИ", "", "", "", "", "", "", ""),
    (47122, "", "17", "", "СКЛАДНАЯ КИСТЬ 3 В 1", 3, 96, 299),
]


def test_collect_prices_from_sheets_is_pure_and_maps_the_price_columns():
    collected = collect_prices_from_sheets([PRICE_SHEET])

    assert sorted(collected) == ["33154", "33156"]
    assert collected["33154"] == {
        "name": "ТОНАЛЬНАЯ ОСНОВА - ВАНИЛЬНЫЙ",
        "consumer_cents": 59900,
        "consultant_cents": 39900,
        "points": 3,
    }
    assert isinstance(collected["33154"]["points"], int)
    assert collected["33156"]["consultant_cents"] is None
    assert collected["33156"]["points"] is None
    assert "33155" not in collected, "a row without ПЦ is not a price row"
    assert collect_prices_from_sheets([NAMES_ONLY_SHEET]) == {}
    assert collect_prices_from_sheets([CALCULATOR_SHEET, NO_CONSUMER_SHEET]) == {}


def test_collect_from_archive_names_every_file_it_could_not_use(tmp_path, monkeypatch):
    """The corrupt 12-2013.xls must be NAMED, not fatal — the walk continues."""
    good = tmp_path / "01-2018.xls"
    corrupt = tmp_path / "12-2013.xls"
    nameless = tmp_path / "oriflame_prices_compact.xlsx"
    priceless = tmp_path / "04-2024.xls"

    def fake_reader(path):
        if path == corrupt:
            raise ValueError("File is truncated, or OLE2 MSAT is corrupt")
        if path == priceless:
            # The real 04-2024.xls shape: the empty КАЛЬКУЛЯТОР template DOES
            # carry a ПЦ header, so "no sheet has a price header" would miss
            # this file. What is reported is «yielded no price row at all».
            return [CALCULATOR_SHEET, NO_CONSUMER_SHEET]
        return [PRICE_SHEET]

    monkeypatch.setattr("scripts.import_prices.read_workbook_sheets", fake_reader)

    collected, report = collect_from_archive([good, corrupt, nameless, priceless])

    assert set(collected) == {(2018, 1, "33154"), (2018, 1, "33156")}
    assert collected[(2018, 1, "33154")]["consumer_cents"] == 59900
    assert report["unparsable_name"] == [nameless.name]
    assert report["no_price_column"] == [priceless.name]
    assert len(report["unreadable"]) == 1
    assert corrupt.name in report["unreadable"][0], report["unreadable"]


def test_the_export_round_trips_through_a_gz_with_no_loss(tmp_path):
    """41.7 MB of JSON becomes ~4.7 MB — the ONLY transport that reaches s1."""
    dest = tmp_path / "catalog_prices.json.gz"

    stats = write_export(dest, [PLAIN_ROW, ZERO_ROW])

    assert stats["after"] == 2 and stats["codes"] == 2
    assert dest.read_bytes()[:2] == b"\x1f\x8b", "the file is genuinely gzipped"
    assert _tuples(load_export(dest)) == _tuples([PLAIN_ROW, ZERO_ROW])

    # A second write into the same .gz is still ACCUMULATIVE, not replacing.
    again = write_export(dest, [{**ZERO_ROW, "points": 7}])

    assert again == {"before": 2, "added": 0, "updated": 1, "after": 2, "codes": 2}
    on_disk = load_export(dest)
    assert [r["code"] for r in on_disk] == ["46413", "0305"]
    assert on_disk[1]["points"] == 7


def _uncommented(path: Path) -> str:
    return "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
    )


def test_neither_importer_deletes_the_whole_price_table():
    """The tripwire for the defect this task exists to close.

    The needle is composed from parts on purpose: written as one literal it
    would also match this very file, and assembling it states the intent. For
    the same reason the two scripts must describe the ownership rule in PROSE —
    a docstring quoting the removed call verbatim would silently re-arm this
    gate against itself.
    """
    needle = ".query(" + "CatalogPrice" + ").delete()"

    for script in (SCRIPT, MASTER_SCRIPT):
        assert needle not in _uncommented(script), script.name


# ---------------------------------------------------------------------------
# Quick task 260902-tev — CR-03: the accumulative files are written atomically.
#
# `open("wt")` (and `gzip.open("wt")`) TRUNCATES at open time, and the ~42 MB
# payload was serialized after that. Anything failing in between (MemoryError,
# ENOSPC, an interrupted process, an unfinished deflate stream) left an empty or
# corrupt file where the previous content had just been destroyed — and these
# files hold rows that exist in NO database.
# ---------------------------------------------------------------------------


def test_atomic_write_keeps_the_gz_branch_and_the_explicit_newline(tmp_path):
    """The temp name must end in the destination's suffix, or .gz writes plain text."""
    gz_dest = tmp_path / "catalog_prices.json.gz"

    atomic_write(gz_dest, serialize_export([PLAIN_ROW]), newline="\n")

    assert gz_dest.read_bytes()[:2] == b"\x1f\x8b", "the .gz branch survived the temp file"
    assert _tuples(load_export(gz_dest)) == _tuples([PLAIN_ROW])

    crlf_dest = tmp_path / "rubric_overrides.json"
    atomic_write(crlf_dest, '{\n "a": 1\n}', newline="\r\n")

    raw = crlf_dest.read_bytes()
    assert b"\r\n" in raw, "the explicit newline is forwarded to the temp file"
    assert b"\n" not in raw.replace(b"\r\n", b""), "no lone LF survives"

    assert list(tmp_path.glob("*.tmp*")) == [], "no temp file is left behind"


def test_atomic_write_leaves_the_destination_untouched_when_the_write_fails(tmp_path):
    """The rollback, stated as a test: a failed write destroys nothing."""
    dest = tmp_path / "catalog_prices.json"
    seed = serialize_export([PLAIN_ROW]).encode("utf-8")
    dest.write_bytes(seed)

    with pytest.raises(TypeError):
        atomic_write(dest, 12345, newline="\n")  # handle.write() refuses a non-string

    assert dest.read_bytes() == seed, "the previous file is byte-identical"
    assert list(tmp_path.glob("*.tmp*")) == [], "no temp file is left behind"


def test_write_export_computes_the_payload_before_touching_the_destination(
    tmp_path, monkeypatch
):
    """The sharpest proof of the defect: serialization must precede truncation."""
    dest = tmp_path / "catalog_prices.json"
    write_export(dest, [PLAIN_ROW])

    def boom(_records):
        raise RuntimeError("MemoryError stand-in, 42 MB into the payload")

    monkeypatch.setattr("scripts.import_prices.serialize_export", boom)

    with pytest.raises(RuntimeError):
        write_export(dest, [ZERO_ROW])

    assert _tuples(load_export(dest)) == _tuples([PLAIN_ROW]), "the old file survived"


def _recording_open_export(monkeypatch):
    """Record every path `_open_export` is handed, and delegate to the real one."""
    from scripts import import_prices

    recorded = []
    real = import_prices._open_export

    def spy(path, mode, **kwargs):
        recorded.append(Path(path))
        return real(path, mode, **kwargs)

    monkeypatch.setattr("scripts.import_prices._open_export", spy)
    return recorded


def test_write_overrides_never_opens_its_destination_directly(tmp_path, monkeypatch):
    dest = tmp_path / "rubric_overrides.json"
    recorded = _recording_open_export(monkeypatch)

    write_overrides(dest, {"33155": {"conf": "series", "name": "Тушь", "rubric": "Макияж"}})

    assert recorded, "the writer never went through _open_export"
    assert recorded[0] != dest, "the destination itself must not be opened for writing"
    assert recorded[0].name.endswith(dest.suffix), "the gzip branch keys on the suffix"

    raw = dest.read_bytes()
    assert raw.startswith(b'{\r\n "33155": {\r\n  "conf": "series",\r\n')
    assert raw.endswith(b"\r\n }\r\n}"), "CRLF, indent=1, NO trailing newline"
