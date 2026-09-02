"""Import the reference dictionary + catalog membership from products.json.

Run: uv run python scripts/import_catalogs.py [--file catalogs/products.json]
     uv run python scripts/import_catalogs.py --only-missing
     uv run python scripts/import_catalogs.py --export catalogs/products.json

Source file shape (produced from the Oriflame catalogs):

    { "46413": { "name": "...", "catalogs": ["01_25", "01_26", ...] }, ... }

For every code this upserts a Dictionary row (code -> name) and stores the
catalog membership in the Dictionary.catalogs JSON column. On the DEFAULT path
the JSON file is authoritative: existing rows have their name and catalogs
overwritten so re-running the import is idempotent. No product/stock/ledger
rows are touched (the dictionary is a helper table, D-24).

Every row this script writes now also carries `rubric` (CAT-06) and `name_lc`
(the lowercase shadow column the name filter matches on, LIST-02) — before
quick task 260902-g1q both were left NULL, which made every bulk-imported row
invisible to the /dictionary name search and category-less.

``--only-missing`` inserts ONLY the codes the target database does not have and
does not read from or write to a single existing row. It is the ONLY mode
allowed against a live server: the default path overwrites names, and a name
edited by hand on the server is newer than the machine-imported local one
(«побеждает последнее написание»).

``--export FILE`` dumps the current dictionary back into this script's own
format — it is what restores/refreshes `catalogs/products.json`, the file the
full справочник is transported in. The export is ACCUMULATIVE, never
replacing: codes already in the target file that the database no longer has are
kept, so the file can only grow and a thinned-out local database can never
impoverish it.

Prices are NOT in products.json — only names and catalog membership. Per-catalog
prices are imported separately from the xlsx price lists by
scripts/import_prices.py (into the catalog_prices table).
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core import new_id  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Dictionary  # noqa: E402
from app.services.catalogs import parse_json_code  # noqa: E402
from app.services.rubrics import resolve_name, resolve_rubric  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = "catalogs/products.json"


def _sort_key(json_code: str) -> tuple[int, int]:
    """Order catalog codes chronologically; unparsable codes sort last."""
    parsed = parse_json_code(json_code)
    return parsed if parsed is not None else (9999, 99)


def build_dictionary_row(code: str, name: str, catalogs: list[str]) -> Dictionary:
    """One dictionary row with rubric + name_lc filled, like the master importer.

    CAT-06: the rubric is resolved from the code (web override) or from the RAW
    input name — exactly what build_dictionary_rows() in
    scripts/import_master_pricelist.py does for a priced row.
    LIST-02: name_lc is the lowercase shadow column the name filter matches on
    (SQLite lower()/LIKE cannot fold Cyrillic); without it a bulk-imported row
    is invisible to the /dictionary search.
    """
    display = resolve_name(code, name)[:200]
    return Dictionary(
        id=new_id(),
        code=code,
        name=display,
        name_lc=display.lower(),
        catalogs=catalogs,
        rubric=resolve_rubric(code, name),
    )


def apply_dictionary_import(
    session, data: dict, *, only_missing: bool = False
) -> dict[str, int]:
    """Upsert the products.json mapping into `dictionary`. Never commits.

    Default: the file is authoritative — an existing code has its name,
    name_lc, rubric and catalogs refreshed.
    ``only_missing=True``: an existing code is counted as `present` and its row
    is not read from, not written to, not touched at all — the additive mode
    used against a live server.
    The caller owns the transaction (mirrors insert_missing_dictionary_rows in
    scripts/import_master_pricelist.py).
    """
    counts = {"created": 0, "updated": 0, "skipped": 0, "present": 0}
    # Load existing rows once, keyed by code, to avoid N lookups.
    existing = {row.code: row for row in session.scalars(select(Dictionary))}
    for raw_code, payload in data.items():
        code = str(raw_code).strip()
        name = (payload.get("name") or "").strip()
        if not code or not name:
            counts["skipped"] += 1
            continue
        row = existing.get(code)
        if row is not None and only_missing:
            counts["present"] += 1
            continue
        catalogs = sorted(payload.get("catalogs") or [], key=_sort_key)
        if row is None:
            session.add(build_dictionary_row(code, name, catalogs))
            counts["created"] += 1
        else:
            display = resolve_name(code, name)[:200]
            row.name = display
            row.name_lc = display.lower()
            row.rubric = resolve_rubric(code, name)
            row.catalogs = catalogs
            counts["updated"] += 1
    return counts


def export_dictionary(session) -> dict[str, dict]:
    """Dump `dictionary` back into this script's own file format.

    Only `name` and `catalogs` are exported: `rubric` and `name_lc` are
    recomputed on import from the code and the name, so the round trip loses
    nothing and the file stays the documented products.json shape.
    """
    rows = {row.code: row for row in session.scalars(select(Dictionary))}
    return {
        code: {"name": rows[code].name, "catalogs": list(rows[code].catalogs or [])}
        for code in sorted(rows)
    }


def read_previous_export(path: Path) -> dict[str, dict]:
    """The mapping already in the target file, or {} when there is none."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"Existing export is not valid JSON, refusing to overwrite it: {path} ({exc})")
    if not isinstance(data, dict):
        sys.exit(f"Existing export is not a JSON object, refusing to overwrite it: {path}")
    return {str(code): payload for code, payload in data.items()}


def merge_dictionary_export(
    previous: dict[str, dict], fresh: dict[str, dict]
) -> tuple[dict[str, dict], dict[str, int]]:
    """Accumulate `fresh` on top of `previous` — the file only ever grows.

    SPEC 260902-g1q: the export is накопительный, not замещающий. A code that
    exists in the file but not in this database is KEPT, so exporting from a
    machine with a thinner справочник can never impoverish the accumulated
    file. Codes from the database are added or refresh what is there.
    """
    merged = dict(previous)
    added = updated = 0
    for code, entry in fresh.items():
        if code not in merged:
            added += 1
        elif merged[code] != entry:
            updated += 1
        merged[code] = entry
    ordered = {code: merged[code] for code in sorted(merged)}
    stats = {
        "before": len(previous),
        "added": added,
        "updated": updated,
        "after": len(ordered),
    }
    return ordered, stats


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else PROJECT_ROOT / path


def write_export(dest: Path, fresh: dict[str, dict]) -> dict[str, int]:
    """Merge `fresh` into whatever `dest` already holds and rewrite the file."""
    previous = read_previous_export(dest)
    merged, stats = merge_dictionary_export(previous, fresh)
    if stats["after"] < stats["before"]:  # unreachable by construction; a hard guard
        sys.exit(f"Refusing to write: the export would drop codes ({stats})")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Explicit LF so a re-export on Windows and on Linux produce identical bytes.
    with dest.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(merged, ensure_ascii=False, indent=1))
        handle.write("\n")
    return stats


def _run_export(dest: Path) -> None:
    with SessionLocal() as session:
        fresh = export_dictionary(session)
    stats = write_export(dest, fresh)
    print(f"Export: {dest}")
    print(
        f"Было: {stats['before']}  добавлено: {stats['added']}  "
        f"обновлено: {stats['updated']}  стало: {stats['after']}"
    )
    print(f"Entries: {stats['after']}  size: {dest.stat().st_size} bytes")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import dictionary + catalogs")
    parser.add_argument("--file", default=DEFAULT_FILE, help="path to products.json")
    parser.add_argument(
        "--export",
        metavar="FILE",
        help="dump the dictionary into products.json format (accumulative) and exit",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="additive: insert only codes absent from the target; touch nothing existing",
    )
    args = parser.parse_args()

    if args.export:
        if args.only_missing:
            sys.exit("--export cannot be combined with --only-missing")
        if args.file != DEFAULT_FILE:
            sys.exit("--export cannot be combined with --file (it writes, it does not read)")
        _run_export(_resolve(args.export))
        return

    src = _resolve(args.file)
    if not src.is_file():
        sys.exit(f"Source file not found: {src}")

    data = json.loads(src.read_text(encoding="utf-8"))
    print(f"Source: {src}  ({len(data)} entries)")

    with SessionLocal() as session:
        before = session.query(Dictionary).count()
        counts = apply_dictionary_import(session, data, only_missing=args.only_missing)
        session.commit()
        after = session.query(Dictionary).count()

    print(
        f"Done. created={counts['created']} updated={counts['updated']} "
        f"skipped={counts['skipped']}"
    )
    if args.only_missing:
        print(
            "Mode: --only-missing (additive, nothing existing touched); "
            f"already present: {counts['present']}"
        )
        print(f"Dictionary: {before} -> {after}")


if __name__ == "__main__":
    main()
