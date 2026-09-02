"""Executable contract for rules 1-7 of `260902-eyv-SPEC.md` (office-inventory import).

Every test builds its own tiny CSV in `tmp_path`; the real
`reports/оприходование-офис-*.csv` is NEVER read here — it is untracked and
absent in CI. `scripts.import_inventory_receipt` is imported INSIDE the test
bodies (project RED-scaffold idiom, 30-01/31-01/32-01) so collection of the
whole suite stays green while these tests are red.
"""

import csv

import pytest

from app.core import new_id
from app.models import Batch, CatalogPrice, Operation, Product, Warehouse

HEADER = [
    "Полка",
    "Код",
    "Наименование (из справочника)",
    "Кол-во",
    "Срок годности",
    "Срок (как в записи)",
    "Комментарий",
    "Файл-источник",
    "Проверить",
]


def _write_csv(tmp_path, rows, name="опись.csv"):
    """Write a CSV shaped exactly like the real inventory export.

    `rows` are `(shelf, code, name, qty, expiry[, note])` tuples; the missing
    trailing columns («Срок (как в записи)», «Файл-источник», «Проверить») are
    filled with empty strings so the width matches the real file.
    """
    path = tmp_path / name
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";", lineterminator="\n")
        writer.writerow(HEADER)
        for row in rows:
            shelf, code, product_name, qty, expiry = row[:5]
            note = row[5] if len(row) > 5 else ""
            writer.writerow([shelf, code, product_name, qty, expiry, "", note, "", ""])
    return path


def _import(session, warehouse, path, *, apply=True):
    from scripts.import_inventory_receipt import read_rows, run_import

    return run_import(session, read_rows(path), warehouse, apply=apply)


def _ops(session, type_):
    return list(session.query(Operation).filter(Operation.type == type_).all())


def test_sentinel_and_empty_codes_are_skipped(tmp_path):
    """Rule 1: only rows with a real code are imported; `???` and empty are skipped."""
    from scripts.import_inventory_receipt import read_rows

    path = _write_csv(
        tmp_path,
        [
            ("47", "32503", "Туалетная вода venture", "2", ""),
            ("59", "???", "", "17", ""),
            ("59", "", "Без кода", "1", ""),
        ],
    )
    rows = read_rows(path)

    assert [row.line_no for row in rows] == [2, 3, 4]
    assert rows[0].skip_reason is None
    assert rows[1].skip_reason is not None
    assert rows[2].skip_reason is not None


def test_new_code_creates_card_batch_and_receipt(session, warehouse, tmp_path):
    """Rule 1/3: an unknown code creates card + batch through register_receipt."""
    path = _write_csv(
        tmp_path, [("47", "32503", "Туалетная вода venture", "2", "", "полка 47")]
    )

    summary = _import(session, warehouse, path)

    assert summary["error"] is None
    product = session.query(Product).filter(Product.code == "32503").one()
    assert product.quantity == 2
    batch = session.query(Batch).one()
    assert batch.warehouse_id == warehouse.id
    assert batch.location == "полка 47"
    assert batch.expiry is None
    assert batch.quantity == 2
    assert len(_ops(session, "receipt")) == 1
    assert summary["new_products"] == 1
    assert summary["new_batches"] == 1
    assert summary["topups"] == 0


def test_same_month_tops_up_the_existing_batch(session, warehouse, tmp_path):
    """Rule 2.1: same code + same year-month = one batch, quantities add up."""
    path = _write_csv(
        tmp_path,
        [
            ("59", "34301", "Тоник", "1", "2021-02-28", "полка 59"),
            ("59", "34301", "Тоник", "1", "2021-02-28", "полка 59"),
        ],
    )

    summary = _import(session, warehouse, path)

    batch = session.query(Batch).one()
    assert batch.quantity == 2
    receipts = _ops(session, "receipt")
    assert len(receipts) == 2
    assert {op.batch_id for op in receipts} == {batch.id}
    assert summary["new_batches"] == 1
    assert summary["topups"] == 1


def test_same_month_different_day_merges_into_one_batch(session, warehouse, tmp_path):
    """Rule 2.1: 2018-01-14 (as recorded) and 2018-01-31 (as listed) are one lot.

    The existing batch's expiry is normalised to the inventory's shape (last
    day of the month) — only for the batch the import actually touches.
    """
    from app.services.receipts import register_receipt

    result, errors = register_receipt(
        session,
        code="25264",
        name="Крем для век",
        qty_raw="5",
        cost_raw="",
        sale_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
        expiry_raw="2018-01-14",
        location_raw="полка 59",
    )
    assert errors == {}
    existing_id = result["batch"].id

    path = _write_csv(
        tmp_path, [("59", "25264", "Крем для век", "3", "2018-01-31", "полка 59")]
    )
    summary = _import(session, warehouse, path)

    batch = session.query(Batch).one()
    assert batch.id == existing_id
    assert batch.quantity == 8
    assert batch.expiry == "2018-01-31"
    assert summary["new_batches"] == 0
    assert summary["topups"] == 1


def test_different_month_creates_a_second_batch(session, warehouse, tmp_path):
    """Rule 2.1: a different year-month is a different lot."""
    path = _write_csv(
        tmp_path,
        [
            ("59", "34301", "Тоник", "1", "2021-02-28", "полка 59"),
            ("59", "34301", "Тоник", "1", "2021-08-31", "полка 59"),
        ],
    )

    summary = _import(session, warehouse, path)

    batches = session.query(Batch).all()
    assert len(batches) == 2
    assert sorted(b.quantity for b in batches) == [1, 1]
    product = session.query(Product).filter(Product.code == "34301").one()
    assert product.quantity == 2
    assert len(_ops(session, "product_created")) == 1
    assert summary["new_batches"] == 2
    assert summary["topups"] == 0


def test_empty_expiry_matches_only_empty_expiry(session, warehouse, tmp_path):
    """Rule 2.1: an empty expiry never merges with a dated lot."""
    path = _write_csv(
        tmp_path,
        [
            ("59", "18819", "Щётка", "1", "", "полка 59"),
            ("59", "18819", "Щётка", "1", "2020-10-31", "полка 59"),
            ("59", "18819", "Щётка", "1", "", "полка 59"),
        ],
    )

    summary = _import(session, warehouse, path)

    batches = session.query(Batch).all()
    assert len(batches) == 2
    empty = [b for b in batches if b.expiry is None]
    dated = [b for b in batches if b.expiry == "2020-10-31"]
    assert len(empty) == 1 and empty[0].quantity == 2
    assert len(dated) == 1 and dated[0].quantity == 1
    assert summary["new_batches"] == 2
    assert summary["topups"] == 1


def test_condition_marker_forces_a_new_batch_despite_matching_month(
    session, warehouse, tmp_path
):
    """Rule 2.2: a leftover in «Комментарий» is a condition marker — never a top-up."""
    path = _write_csv(
        tmp_path,
        [
            ("59", "34301", "Тоник", "1", "2021-02-28", "полка 59"),
            ("59", "34301", "Тоник", "1", "2021-02-28", "полка 59; упаковка повреждена"),
        ],
    )

    summary = _import(session, warehouse, path)

    batches = session.query(Batch).all()
    assert len(batches) == 2
    plain = [b for b in batches if not b.comment]
    marked = [b for b in batches if b.comment and "упаковка повреждена" in b.comment]
    assert len(plain) == 1
    assert len(marked) == 1
    assert marked[0].location == "полка 59"
    assert summary["new_batches"] == 2
    assert summary["topups"] == 0
    assert summary["condition_rows"] == 1


def test_two_rows_with_the_same_condition_share_one_new_batch(
    session, warehouse, tmp_path
):
    """Rule 2.2: identical code + month + marker go into ONE new batch."""
    path = _write_csv(
        tmp_path,
        [
            ("59", "34301", "Тоник", "1", "2021-02-28", "полка 59; пробник"),
            ("59", "34301", "Тоник", "2", "2021-02-28", "полка 59; пробник"),
        ],
    )

    summary = _import(session, warehouse, path)

    batch = session.query(Batch).one()
    assert batch.quantity == 3
    assert "пробник" in batch.comment
    assert summary["new_batches"] == 1
    assert summary["topups"] == 1
    assert summary["condition_rows"] == 2


def test_existing_batch_comment_does_not_block_topup(session, warehouse, tmp_path):
    """Rule 2.2: the marker comes from the CSV row, never from the stored batch."""
    from app.services.receipts import register_receipt

    result, errors = register_receipt(
        session,
        code="18819",
        name="Щётка",
        qty_raw="4",
        cost_raw="",
        sale_raw="",
        warehouse_id=warehouse.id,
        batch_choice="new",
        expiry_raw="",
        location_raw="полка 59",
        comment_raw="Срока на упаковке нет",
    )
    assert errors == {}
    existing_id = result["batch"].id

    path = _write_csv(tmp_path, [("59", "18819", "Щётка", "1", "", "полка 59")])
    summary = _import(session, warehouse, path)

    batch = session.query(Batch).one()
    assert batch.id == existing_id
    assert batch.quantity == 5
    assert "Срока на упаковке нет" in batch.comment
    assert summary["topups"] == 1
    assert summary["condition_rows"] == 0


def test_missing_catalog_price_leaves_prices_null(session, warehouse, tmp_path):
    """Rule 4: no catalog row = empty price fields, NULL in the database (not 0)."""
    path = _write_csv(tmp_path, [("47", "0001", "Барьер", "1", "", "полка 47")])

    summary = _import(session, warehouse, path)

    product = session.query(Product).filter(Product.code == "0001").one()
    batch = session.query(Batch).one()
    assert product.cost_cents is None
    assert product.sale_cents is None
    assert batch.price_cents is None
    assert batch.cost_cents is None
    assert summary["codes_without_price"] == 1


def test_existing_card_price_is_never_overwritten(session, warehouse, tmp_path):
    """Rule 4: prices travel only for brand-new cards; existing cards are untouched."""
    product = Product(
        id=new_id(),
        code="34301",
        name="Тоник",
        name_lc="тоник",
        cost_cents=100,
        sale_cents=200,
        quantity=0,
    )
    session.add(product)
    session.add(
        CatalogPrice(
            id=new_id(),
            year=2026,
            number=1,
            code="34301",
            consultant_cents=999,
            consumer_cents=1999,
        )
    )
    session.add(
        CatalogPrice(
            id=new_id(),
            year=2026,
            number=1,
            code="35408",
            consultant_cents=12345,
            consumer_cents=45600,
        )
    )
    session.commit()

    path = _write_csv(
        tmp_path,
        [
            ("59", "34301", "Тоник", "1", "", "полка 59"),
            ("59", "35408", "Тоник новый", "1", "", "полка 59"),
        ],
    )
    _import(session, warehouse, path)

    session.refresh(product)
    assert product.cost_cents == 100
    assert product.sale_cents == 200
    assert _ops(session, "price_change") == []

    fresh = session.query(Product).filter(Product.code == "35408").one()
    assert fresh.cost_cents == 12345
    assert fresh.sale_cents == 45600


def test_shelf_is_appended_to_comment_on_topup_without_duplicating(
    session, warehouse, tmp_path
):
    """Rule 3: the shelf is written into the batch comment on a top-up, once."""
    path = _write_csv(
        tmp_path,
        [
            ("47", "32503", "Вода", "1", "2021-02-28", "полка 47"),
            ("47", "32503", "Вода", "1", "2021-02-28", "полка 47"),
            ("47", "32503", "Вода", "1", "2021-02-28", "полка 47"),
        ],
    )

    _import(session, warehouse, path)

    batch = session.query(Batch).one()
    assert batch.location == "полка 47"
    parts = [part.strip() for part in (batch.comment or "").split(";")]
    assert parts.count("полка 47") == 1


def test_shelf_4_is_not_considered_present_in_shelf_47(session, warehouse, tmp_path):
    """Rule 3: «полка 4» is a different shelf from «полка 47» (no substring match)."""
    path = _write_csv(
        tmp_path,
        [
            ("47", "32503", "Вода", "1", "2021-02-28", "полка 47"),
            ("47", "32503", "Вода", "1", "2021-02-28", "полка 47"),
            ("4", "32503", "Вода", "1", "2021-02-28", "полка 4"),
        ],
    )

    _import(session, warehouse, path)

    batch = session.query(Batch).one()
    parts = [part.strip() for part in (batch.comment or "").split(";")]
    assert parts.count("полка 47") == 1
    assert parts.count("полка 4") == 1


def test_warehouse_lookup_is_case_insensitive_and_active_only(session):
    """Rule 7: find the destination warehouse by name, active only, any case."""
    from scripts.import_inventory_receipt import find_warehouse

    office = Warehouse(id=new_id(), name="офис")
    gone = Warehouse(
        id=new_id(), name="Старый склад", deleted_at="2026-01-01T00:00:00+00:00"
    )
    session.add_all([office, gone])
    session.commit()

    assert find_warehouse(session, "Офис").id == office.id
    assert find_warehouse(session, "  ОФИС  ").id == office.id
    assert find_warehouse(session, "Старый склад") is None
    assert find_warehouse(session, "Нет такого") is None


def test_dry_run_writes_nothing_and_predicts_intra_file_repeats(
    session, warehouse, tmp_path
):
    """Dry run is read-only and predicts exactly what --apply would do."""
    path = _write_csv(
        tmp_path,
        [
            ("59", "34301", "Тоник", "1", "2021-02-28", "полка 59"),
            ("59", "34301", "Тоник", "1", "2021-02-28", "полка 59"),
            ("59", "34301", "Тоник", "1", "2021-08-31", "полка 59"),
        ],
    )

    summary = _import(session, warehouse, path, apply=False)

    assert summary["new_products"] == 1
    assert summary["new_batches"] == 2
    assert summary["topups"] == 1
    assert summary["rows_written"] == 0
    assert session.query(Product).count() == 0
    assert session.query(Batch).count() == 0
    assert session.query(Operation).count() == 0


@pytest.mark.parametrize(
    ("note", "shelf", "expected"),
    [
        ("полка 59", "59", ("полка 59", "")),
        ("под зеркалом", "под зеркалом", ("под зеркалом", "")),
        ("полка 59; упаковка повреждена", "59", ("полка 59", "упаковка повреждена")),
        ("", "47", ("полка 47", "")),
        ("вскрыто", "47", ("полка 47", "вскрыто")),
    ],
)
def test_note_splits_into_placement_and_condition(note, shelf, expected):
    """Rule 2.2/3: «Комментарий» = placement + optional condition leftover."""
    from scripts.import_inventory_receipt import split_note

    assert split_note(note, shelf) == expected
