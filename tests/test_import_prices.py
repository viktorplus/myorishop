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
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import CatalogPrice
from scripts.import_prices import (
    EXPORT_KEYS,
    build_price_rows,
    export_prices,
    insert_missing_price_rows,
    load_export,
    merge_price_export,
    serialize_export,
    write_export,
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


def test_openpyxl_is_not_imported_at_module_level():
    """The image is built with `uv sync --frozen --no-dev` — openpyxl is dev-only."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    top_level = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            top_level.append(node.module or "")

    assert not any("openpyxl" in name for name in top_level), top_level
