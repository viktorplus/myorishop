"""Import per-catalog prices from the xlsx price lists into catalog_prices.

Run: uv run python scripts/import_prices.py [--dir catalogs]

Each xlsx is a catalog issue whose filename encodes month + year in one of
several formats (01-2026, 03_2024, 2025-07, 25-11, with _calc/(1) suffixes).
Inside, the real price sheets carry a header row with `КОД` and `ПЦ`; tester
sheets (`ПРОДУКТ`/`ЦЕНА`) and the empty `КАЛЬКУЛЯТОР` template are skipped.

Extracted columns (Oriflame layout):
  * ПЦ -> consumer_cents   (catalog / retail price)
  * ОП -> consultant_cents (consultant / purchase price)
  * ББ -> points           (catalog bonus points)
  * НАИМЕНОВАНИЕ -> name    (short, upper-case source name; the pretty name
                            stays in the dictionary, imported separately)

Whole-ruble prices are converted to integer cents. The table is fully
replaced on each run (it is derived purely from these files), so the import
is idempotent. Helper data only — no product/stock/ledger rows are touched.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl  # noqa: E402

from app.core import new_id, to_cents  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import CatalogPrice  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_catalog(filename: str) -> tuple[int, int] | None:
    """Filename -> (year, number); handles MM-YYYY, YYYY-MM and YY-MM shapes."""
    stem = re.sub(r"\.xlsx$", "", filename, flags=re.IGNORECASE)
    nums = re.findall(r"\d+", stem)
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


def _norm(value) -> str:
    return str(value).strip().upper() if value is not None else ""


def _find_header(rows) -> tuple[int, dict[str, int]] | None:
    """Locate the header row (КОД + ПЦ) and map roles to column indexes."""
    for i, row in enumerate(rows[:8]):
        cells = [_norm(c) for c in row]
        if "КОД" not in cells:
            continue
        colmap: dict[str, int] = {}
        for j, cell in enumerate(cells):
            if cell == "КОД" and "code" not in colmap:
                colmap["code"] = j
            elif cell == "ПЦ" and "consumer" not in colmap:
                colmap["consumer"] = j
            elif cell == "ОП" and "consultant" not in colmap:
                colmap["consultant"] = j
            elif cell == "ББ" and "points" not in colmap:
                colmap["points"] = j
            elif cell == "НАИМЕНОВАНИЕ" and "name" not in colmap:
                colmap["name"] = j
        if "code" in colmap and "consumer" in colmap:
            return i, colmap
    return None


def _is_code(value) -> bool:
    return value is not None and str(value).strip().isdigit() and 3 <= len(str(value).strip()) <= 7


def _cents(value) -> int | None:
    """Positive number -> integer cents; anything else -> None."""
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    try:
        return to_cents(str(value))
    except ValueError:
        return None


def _cell(row, colmap, role):
    idx = colmap.get(role)
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def main() -> None:
    parser = argparse.ArgumentParser(description="Import catalog prices from xlsx")
    parser.add_argument("--dir", default="catalogs", help="folder with the xlsx files")
    args = parser.parse_args()

    folder = Path(args.dir)
    if not folder.is_absolute():
        folder = PROJECT_ROOT / folder
    files = sorted(folder.glob("*.xlsx"))
    if not files:
        sys.exit(f"No xlsx files in {folder}")

    # Deduplicate by (year, number, code): duplicate files (01-2026 vs
    # 01-2026_ (1)) and repeated rows collapse to one; last write wins.
    collected: dict[tuple[int, int, str], dict] = {}
    skipped_files = []
    for path in files:
        cat = parse_catalog(path.name)
        if cat is None:
            skipped_files.append(path.name)
            continue
        year, number = cat
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=True))
            header = _find_header(rows)
            if header is None:
                continue
            start, colmap = header
            for row in rows[start + 1 :]:
                code = _cell(row, colmap, "code")
                if not _is_code(code):
                    continue
                consumer = _cents(_cell(row, colmap, "consumer"))
                if consumer is None:  # section header / blank row
                    continue
                code = str(code).strip()
                name = _cell(row, colmap, "name")
                name = str(name).strip()[:200] if name and str(name).strip() else None
                points = _cell(row, colmap, "points")
                collected[(year, number, code)] = {
                    "consumer_cents": consumer,
                    "consultant_cents": _cents(_cell(row, colmap, "consultant")),
                    "points": int(points)
                    if isinstance(points, (int, float)) and points > 0
                    else None,
                    "name": name,
                }
        wb.close()

    with SessionLocal() as session:
        deleted = session.query(CatalogPrice).delete()
        session.bulk_save_objects(
            [
                CatalogPrice(
                    id=new_id(),
                    year=year,
                    number=number,
                    code=code,
                    name=data["name"],
                    consumer_cents=data["consumer_cents"],
                    consultant_cents=data["consultant_cents"],
                    points=data["points"],
                )
                for (year, number, code), data in collected.items()
            ]
        )
        session.commit()

    catalogs = {(y, n) for (y, n, _c) in collected}
    codes = {c for (_y, _n, c) in collected}
    print(f"Files: {len(files)}  catalogs: {len(catalogs)}  codes: {len(codes)}")
    print(f"Rows: replaced {deleted} -> inserted {len(collected)}")
    if skipped_files:
        print(f"Skipped (unparsable filename): {skipped_files}")


if __name__ == "__main__":
    main()
