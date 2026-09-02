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
    build_price_rows,
    build_shade_overrides,
    collect_shade_candidates,
    current_name,
    display_name,
    export_prices,
    insert_missing_price_rows,
    is_shade_row,
    load_export,
    merge_overrides,
    merge_price_export,
    pick_full_name,
    price_list_files,
    restore_full_name,
    serialize_export,
    shade_text,
    split_series_type,
    write_export,
    write_overrides,
)

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "import_prices.py"

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
    ],
)
def test_load_export_refuses_malformed_input(tmp_path, payload):
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        load_export(path)

    assert str(exc.value), "the failure must name what is wrong"


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
