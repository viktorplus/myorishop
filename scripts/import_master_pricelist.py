"""Full-replace import of the master price list into dictionary + catalog_prices.

Run: uv run python scripts/import_master_pricelist.py [--file catalogs/oriflame_prices_with_calculations_fixed.xlsx]
     uv run python scripts/import_master_pricelist.py --only-missing   (additive, deletes nothing)

Source file shape: one sheet "Прайс-лист" with header columns
Код, Название, ДЦ, ПЦ, Последний каталог. Unlike scripts/import_catalogs.py
(products.json: many catalogs per code) + scripts/import_prices.py (many xlsx
files: full per-catalog price history), this script imports ONE authoritative
recent export where every code carries just its single latest catalog issue
("Последний каталог") and current ДЦ/ПЦ prices.

Both the dictionary and catalog_prices tables are fully replaced on each run
(delete-all + bulk insert inside one transaction) — they are pure helper
tables (D-24), never touching Product/Batch/Operation/Sale/ledger rows.
Dictionary.catalogs becomes a single-element list (this collapses the prior
"history of many catalogs" down to just the latest one).

Quick task 260902-1d1 added the override-only branch: a справочник code can
exist as a real product and appear in NO price list (the 34 «НЕТ В
СПРАВОЧНИКЕ» codes of the «Офис» inventory). Those codes come from
RUBRIC_OVERRIDES with a name and a rubric but никогда a price, so they land
in dictionary with ``catalogs == []`` and get no catalog_prices row at all.
``--only-missing`` is the non-destructive way to backfill them into a live
database: it inserts the codes that are not there yet and deletes nothing.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl  # noqa: E402

from app.core import new_id, to_cents  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import CatalogPrice, Dictionary  # noqa: E402
from app.services.catalogs import to_json_code  # noqa: E402
from app.services.rubrics import RUBRIC_OVERRIDES, resolve_name, resolve_rubric  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = "catalogs/oriflame_prices_with_calculations_fixed.xlsx"
SHEET_NAME = "Прайс-лист"
EXPECTED_HEADERS = ["Код", "Название", "ДЦ", "ПЦ", "Последний каталог"]


def parse_last_catalog(value) -> tuple[int, int] | None:
    """"17-2021" -> (2021, 17); handles YYYY-MM, MM-YYYY and YY-MM shapes.

    Mirrors the exact disambiguation heuristic of parse_catalog() in
    scripts/import_prices.py, applied to the "Последний каталог" cell value
    instead of a filename.
    """
    nums = re.findall(r"\d+", str(value).strip())
    if len(nums) < 2:
        return None
    a, b = int(nums[0]), int(nums[1])
    if len(nums[0]) == 4:  # YYYY-MM
        return a, b
    if len(nums[1]) == 4:  # MM-YYYY
        return b, a
    if a > 17:  # YY-MM (a is the year, catalogs never exceed 17)
        return 2000 + a, b
    if b > 17:  # MM-YY
        return 2000 + b, a
    return None


def _cents(value) -> int | None:
    """Positive number -> integer cents; anything else (incl. blank) -> None."""
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    try:
        return to_cents(str(value))
    except ValueError:
        return None


def collect_price_rows(src: Path) -> tuple[dict[str, dict], dict[str, int]]:
    """Read the price-list sheet into {code: row-data} + skip statistics."""
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    if SHEET_NAME not in wb.sheetnames:
        sys.exit(f"Sheet {SHEET_NAME!r} not found in {src} (sheets: {wb.sheetnames})")
    ws = wb[SHEET_NAME]

    header_row = next(ws.iter_rows(values_only=True, max_row=1))
    colmap: dict[str, int] = {}
    for j, cell in enumerate(header_row):
        name = str(cell).strip() if cell is not None else ""
        if name in EXPECTED_HEADERS and name not in colmap:
            colmap[name] = j
    missing = [h for h in EXPECTED_HEADERS if h not in colmap]
    if missing:
        sys.exit(f"Missing expected column(s) {missing} in {src} sheet {SHEET_NAME!r}")

    total_rows = 0
    skipped_missing_code = 0
    skipped_bad_catalog = 0
    collected: dict[str, dict] = {}

    rows = ws.iter_rows(min_row=2, values_only=True)
    for row in rows:
        total_rows += 1
        code_cell = row[colmap["Код"]] if colmap["Код"] < len(row) else None
        if code_cell is None or str(code_cell).strip() == "":
            skipped_missing_code += 1
            continue
        code = str(code_cell).strip()

        cat = parse_last_catalog(row[colmap["Последний каталог"]] if colmap["Последний каталог"] < len(row) else None)
        if cat is None:
            skipped_bad_catalog += 1
            continue
        year, number = cat

        name_cell = row[colmap["Название"]] if colmap["Название"] < len(row) else None
        name = str(name_cell).strip()[:200] if name_cell is not None and str(name_cell).strip() else None

        consultant_cents = _cents(row[colmap["ДЦ"]] if colmap["ДЦ"] < len(row) else None)
        consumer_cents = _cents(row[colmap["ПЦ"]] if colmap["ПЦ"] < len(row) else None)

        collected[code] = {
            "name": name,
            "year": year,
            "number": number,
            "consumer_cents": consumer_cents,
            "consultant_cents": consultant_cents,
        }
    wb.close()

    stats = {
        "total_rows": total_rows,
        "skipped_missing_code": skipped_missing_code,
        "skipped_bad_catalog": skipped_bad_catalog,
    }
    return collected, stats


def override_only_rows(collected_codes: set[str]) -> dict[str, dict]:
    """RUBRIC_OVERRIDES entries whose code is in no price list.

    These are справочник codes that exist as a real product but appear in no
    price list at all — they get a name and a rubric, but никогда a price.
    """
    return {
        code: entry
        for code, entry in RUBRIC_OVERRIDES.items()
        if code not in collected_codes
    }


def _priceless_dictionary_row(code: str) -> Dictionary:
    """A Dictionary row for an override-only code: name, rubric, no catalog."""
    # resolve_name returns the override name for a code we have one for.
    name = resolve_name(code, code)[:200]
    return Dictionary(
        id=new_id(),
        code=code,
        name=name,
        name_lc=name.lower(),
        catalogs=[],
        rubric=resolve_rubric(code, name),
    )


def build_dictionary_rows(collected: dict[str, dict]) -> list[Dictionary]:
    """One row per price-list code, plus one per override-only code."""
    # CAT-06: assign the rubric and (for bad shade-only names) the corrected
    # full name, both resolved from the code via app.services.rubrics.
    # name_lc is the lowercased shadow column the name filter matches on
    # (LIST-02); set it here or bulk-imported rows are invisible to search.
    dict_rows = []
    for code, data in collected.items():
        name = resolve_name(code, data["name"] or code)[:200]
        dict_rows.append(
            Dictionary(
                id=new_id(),
                code=code,
                name=name,
                name_lc=name.lower(),
                catalogs=[to_json_code(data["year"], data["number"])],
                rubric=resolve_rubric(code, data["name"] or code),
            )
        )
    # 260902-1d1: codes that have an override but no price-list row still
    # belong in the справочник — with an empty catalogs list and no price.
    dict_rows.extend(
        _priceless_dictionary_row(code)
        for code in sorted(override_only_rows(set(collected)))
    )
    return dict_rows


def build_catalog_price_rows(collected: dict[str, dict]) -> list[CatalogPrice]:
    """One row per price-list code — override-only codes never get one."""
    return [
        CatalogPrice(
            id=new_id(),
            year=data["year"],
            number=data["number"],
            code=code,
            name=data["name"],
            consumer_cents=data["consumer_cents"],
            consultant_cents=data["consultant_cents"],
            points=None,
        )
        for code, data in collected.items()
    ]


def insert_missing_dictionary_rows(session, extra: dict[str, dict]) -> list[str]:
    """Additive backfill: insert only the `extra` codes not in dictionary yet.

    Never deletes, never updates an existing row, never writes a CatalogPrice.
    The caller commits. Returns the inserted codes.
    """
    existing = {code for (code,) in session.query(Dictionary.code).all()}
    inserted: list[str] = []
    for code in sorted(extra):
        if code in existing:
            continue
        session.add(_priceless_dictionary_row(code))
        inserted.append(code)
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Full-replace import of the master price list")
    parser.add_argument("--file", default=DEFAULT_FILE, help="path to the master price list xlsx")
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="additive: insert only the missing override-only codes; delete nothing",
    )
    args = parser.parse_args()

    src = Path(args.file)
    if not src.is_absolute():
        src = PROJECT_ROOT / src
    if not src.is_file():
        sys.exit(f"Source file not found: {src}")

    collected, stats = collect_price_rows(src)
    total_rows = stats["total_rows"]
    skipped_missing_code = stats["skipped_missing_code"]
    skipped_bad_catalog = stats["skipped_bad_catalog"]
    extra = override_only_rows(set(collected))

    if args.only_missing:
        with SessionLocal() as session:
            before_dict = session.query(Dictionary).count()
            inserted = insert_missing_dictionary_rows(session, extra)
            session.commit()
            after_dict = session.query(Dictionary).count()
        print(f"Source: {src}")
        print("Mode: --only-missing (additive, nothing deleted)")
        print(f"Rows read from price list: {len(collected)}")
        print(f"Override-only codes (no price): {len(extra)}")
        print(f"Inserted: {len(inserted)} (skipped, already present: {len(extra) - len(inserted)})")
        print(f"Dictionary: {before_dict} -> {after_dict}")
        return

    with SessionLocal() as session:
        before_dict = session.query(Dictionary).count()
        before_cp = session.query(CatalogPrice).count()

        session.query(Dictionary).delete()
        session.query(CatalogPrice).delete()

        session.bulk_save_objects(build_dictionary_rows(collected))
        session.bulk_save_objects(build_catalog_price_rows(collected))
        session.commit()

        after_dict = session.query(Dictionary).count()
        after_cp = session.query(CatalogPrice).count()
        rubric_filled = (
            session.query(Dictionary).filter(Dictionary.rubric.isnot(None)).count()
        )
        rubric_other = (
            session.query(Dictionary).filter(Dictionary.rubric == "Прочее").count()
        )

    print(f"Source: {src}")
    print(f"Sheet: {SHEET_NAME}")
    print(f"Data rows scanned: {total_rows}")
    print(f"Rows imported: {len(collected)}")
    print(
        "Rows skipped: "
        f"{skipped_missing_code + skipped_bad_catalog} "
        f"(missing code: {skipped_missing_code}, unparsable catalog: {skipped_bad_catalog})"
    )
    print(f"Dictionary rows from overrides only (no price): {len(extra)}")
    print(f"Dictionary: {before_dict} -> {after_dict}")
    print(f"CatalogPrice: {before_cp} -> {after_cp}")
    print(f"Rubric assigned: {rubric_filled}/{after_dict} (Прочее: {rubric_other})")


if __name__ == "__main__":
    main()
