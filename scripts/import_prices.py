"""Import per-catalog prices from the xlsx price lists into catalog_prices.

Run: uv run python scripts/import_prices.py [--dir catalogs]
     uv run python scripts/import_prices.py --export catalogs/catalog_prices.json
     uv run python scripts/import_prices.py --from-export catalogs/catalog_prices.json \
         --only-missing

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

Whole-ruble prices are converted to integer cents. On the xlsx path the table
is fully replaced on each run (it is derived purely from these files), so the
import is idempotent. Helper data only — no product/stock/ledger rows are
touched.

Quick task 260902-g1q added the JSON transport, because the 118 MB
`catalogs/price_lists/` archive is deliberately kept out of git and out of the
Docker image — the server has no price lists and never will:

  ``--export FILE``       dumps catalog_prices into a compact JSON array (one
                          record per line). The export is ACCUMULATIVE, never
                          replacing: rows already in the target file that this
                          database does not have are kept, so the file can only
                          grow.
  ``--from-export FILE``  loads that file instead of parsing xlsx.
  ``--only-missing``      (only with --from-export) inserts only rows whose
                          CODE is absent from catalog_prices.

⚠ ``--from-export`` WITHOUT ``--only-missing`` deletes every existing row
before inserting — never point it at a live server, where it would erase the
prices that came from the master price list.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core import new_id, to_cents  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import CatalogPrice  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# The exact shape of one exported row — the 7 model fields that carry data.
EXPORT_KEYS = frozenset(
    {"code", "year", "number", "name", "consumer_cents", "consultant_cents", "points"}
)


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


def collect_from_xlsx(files) -> tuple[dict[tuple[int, int, str], dict], list[str]]:
    """Walk the workbooks -> {(year, number, code): row-data} + skipped files.

    openpyxl is imported HERE, not at module level, on purpose: it is a dev
    dependency and the Dockerfile builds with `uv sync --frozen --no-dev`, so a
    top-level import would make this whole script unimportable inside the
    production image — which is exactly where --from-export has to run.
    """
    import openpyxl

    # Deduplicate by (year, number, code): duplicate files (01-2026 vs
    # 01-2026_ (1)) and repeated rows collapse to one; last write wins.
    collected: dict[tuple[int, int, str], dict] = {}
    skipped_files: list[str] = []
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
    return collected, skipped_files


def export_prices(session) -> list[dict]:
    """Every catalog_prices row projected onto the 7 exported fields.

    Sorted by (year, number, code) — the UNIQUE-constraint order, so a
    re-export is byte-stable and diffs cleanly.
    """
    records = [
        {
            "code": row.code,
            "year": row.year,
            "number": row.number,
            "name": row.name,
            "consumer_cents": row.consumer_cents,
            "consultant_cents": row.consultant_cents,
            "points": row.points,
        }
        for row in session.scalars(select(CatalogPrice))
    ]
    return sorted(records, key=_price_key)


def _price_key(record: dict) -> tuple[int, int, str]:
    return (record["year"], record["number"], record["code"])


def serialize_export(records: list[dict]) -> str:
    """Valid JSON array with ONE record per line (15 798 rows, no indent bloat)."""
    body = ",\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in records)
    return f"[\n{body}\n]\n" if records else "[]\n"


def validate_records(records, source) -> list[dict]:
    """Refuse malformed input loudly, naming the offending record index."""
    if not isinstance(records, list):
        sys.exit(f"Export file is not a JSON array: {source}")
    for i, record in enumerate(records):
        if not isinstance(record, dict):
            sys.exit(f"{source}: record {i} is not an object")
        if set(record) != set(EXPORT_KEYS):
            missing = sorted(set(EXPORT_KEYS) - set(record))
            extra = sorted(set(record) - set(EXPORT_KEYS))
            sys.exit(f"{source}: record {i} has wrong keys (missing={missing}, extra={extra})")
        if not isinstance(record["code"], str):
            sys.exit(f"{source}: record {i} has a non-string code {record['code']!r}")
        for field in ("year", "number"):
            value = record[field]
            if not isinstance(value, int) or isinstance(value, bool):
                sys.exit(f"{source}: record {i} has a non-integer {field} {value!r}")
    return records


def load_export(path: Path) -> list[dict]:
    """Read + validate an --export file. Exits on anything malformed."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"Export file is not valid JSON: {path} ({exc})")
    return validate_records(raw, path)


def build_price_rows(records: list[dict]) -> list[CatalogPrice]:
    """Model objects carrying every exported field verbatim — no coercion."""
    return [
        CatalogPrice(
            id=new_id(),
            year=r["year"],
            number=r["number"],
            code=r["code"],
            name=r["name"],
            consumer_cents=r["consumer_cents"],
            consultant_cents=r["consultant_cents"],
            points=r["points"],
        )
        for r in records
    ]


def insert_missing_price_rows(session, records: list[dict]) -> list[dict]:
    """Additive backfill filtered by CODE. Never deletes, updates or commits.

    The filter is code-level, not (year, number, code)-level, on purpose: a
    code the server already knows came from the master price list with its own
    (year, number), and adding this file's history rows for the same code would
    shadow it in every "latest price" lookup.
    """
    existing = {code for code in session.scalars(select(CatalogPrice.code).distinct())}
    fresh = [r for r in records if r["code"] not in existing]
    if fresh:
        session.bulk_save_objects(build_price_rows(fresh))
    return fresh


def merge_price_export(
    previous: list[dict], fresh: list[dict]
) -> tuple[list[dict], dict[str, int]]:
    """Accumulate `fresh` on top of `previous` — the file only ever grows.

    SPEC 260902-g1q: the export is накопительный, not замещающий. A row that
    exists in the file but not in this database is KEPT (keyed by the
    (year, number, code) UNIQUE tuple), so exporting from a machine with a
    thinner price history can never impoverish the accumulated file.
    """
    merged = {_price_key(r): r for r in previous}
    before = len(merged)
    added = updated = 0
    for record in fresh:
        key = _price_key(record)
        if key not in merged:
            added += 1
        elif merged[key] != record:
            updated += 1
        merged[key] = record
    ordered = [merged[key] for key in sorted(merged)]
    stats = {
        "before": before,
        "added": added,
        "updated": updated,
        "after": len(ordered),
    }
    return ordered, stats


def write_export(dest: Path, fresh: list[dict]) -> dict[str, int]:
    """Merge `fresh` into whatever `dest` already holds and rewrite the file."""
    previous = load_export(dest) if dest.is_file() else []
    merged, stats = merge_price_export(previous, fresh)
    if stats["after"] < stats["before"]:  # unreachable by construction; a hard guard
        sys.exit(f"Refusing to write: the export would drop rows ({stats})")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Explicit LF so a re-export on Windows and on Linux produce identical bytes.
    with dest.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(serialize_export(merged))
    stats["codes"] = len({r["code"] for r in merged})
    return stats


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _run_export(dest: Path) -> None:
    with SessionLocal() as session:
        fresh = export_prices(session)
    stats = write_export(dest, fresh)
    print(f"Export: {dest}")
    print(
        f"Было: {stats['before']}  добавлено: {stats['added']}  "
        f"обновлено: {stats['updated']}  стало: {stats['after']}"
    )
    print(f"Rows: {stats['after']}  codes: {stats['codes']}  size: {dest.stat().st_size} bytes")


def _run_from_export(src: Path, only_missing: bool) -> None:
    records = load_export(src)
    print(f"Source: {src}  ({len(records)} rows, {len({r['code'] for r in records})} codes)")
    with SessionLocal() as session:
        before = session.query(CatalogPrice).count()
        if only_missing:
            inserted = insert_missing_price_rows(session, records)
            session.commit()
            after = session.query(CatalogPrice).count()
            print("Mode: --only-missing (additive, nothing deleted)")
            print(
                f"Inserted: {len(inserted)} "
                f"(skipped, code already present: {len(records) - len(inserted)})"
            )
            print(f"CatalogPrice: {before} -> {after}")
            return
        deleted = session.query(CatalogPrice).delete()
        session.bulk_save_objects(build_price_rows(records))
        session.commit()
    print(f"Rows: replaced {deleted} -> inserted {len(records)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import catalog prices from xlsx")
    parser.add_argument("--dir", default="catalogs", help="folder with the xlsx files")
    parser.add_argument(
        "--export", metavar="FILE", help="dump catalog_prices to JSON (accumulative) and exit"
    )
    parser.add_argument(
        "--from-export", metavar="FILE", help="load prices from an --export file instead of xlsx"
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="additive: insert only rows whose code is absent (requires --from-export)",
    )
    args = parser.parse_args()

    # Foot-gun guards, before any DB access: --only-missing must never silently
    # degrade into the destructive xlsx full replace.
    if args.export and args.from_export:
        sys.exit("--export cannot be combined with --from-export")
    if args.only_missing and not args.from_export:
        sys.exit("--only-missing works only with --from-export; the xlsx path is a full replace")

    if args.export:
        _run_export(_resolve(args.export))
        return

    if args.from_export:
        src = _resolve(args.from_export)
        if not src.is_file():
            sys.exit(f"Export file not found: {src}")
        _run_from_export(src, args.only_missing)
        return

    folder = _resolve(args.dir)
    files = sorted(folder.glob("*.xlsx"))
    if not files:
        sys.exit(f"No xlsx files in {folder}")

    collected, skipped_files = collect_from_xlsx(files)

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
