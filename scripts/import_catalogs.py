"""Import the reference dictionary + catalog membership from products.json.

Run: uv run python scripts/import_catalogs.py [--file catalogs/products.json]

Source file shape (produced from the Oriflame catalogs):

    { "46413": { "name": "...", "catalogs": ["01_25", "01_26", ...] }, ... }

For every code this upserts a Dictionary row (code -> name) and stores the
catalog membership in the new Dictionary.catalogs JSON column. The JSON file
is authoritative: existing rows have their name and catalogs overwritten so
re-running the import is idempotent. No product/stock/ledger rows are touched
(the dictionary is a helper table, D-24).

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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = "catalogs/products.json"


def _sort_key(json_code: str) -> tuple[int, int]:
    """Order catalog codes chronologically; unparsable codes sort last."""
    parsed = parse_json_code(json_code)
    return parsed if parsed is not None else (9999, 99)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import dictionary + catalogs")
    parser.add_argument("--file", default=DEFAULT_FILE, help="path to products.json")
    args = parser.parse_args()

    src = Path(args.file)
    if not src.is_absolute():
        src = PROJECT_ROOT / src
    if not src.is_file():
        sys.exit(f"Source file not found: {src}")

    data = json.loads(src.read_text(encoding="utf-8"))
    print(f"Source: {src}  ({len(data)} entries)")

    created = updated = skipped = 0
    with SessionLocal() as session:
        # Load existing rows once, keyed by code, to avoid N lookups.
        existing = {row.code: row for row in session.scalars(select(Dictionary))}
        for code, payload in data.items():
            code = str(code).strip()
            name = (payload.get("name") or "").strip()
            if not code or not name:
                skipped += 1
                continue
            catalogs = sorted(payload.get("catalogs") or [], key=_sort_key)
            row = existing.get(code)
            if row is None:
                session.add(Dictionary(id=new_id(), code=code, name=name, catalogs=catalogs))
                created += 1
            else:
                row.name = name
                row.catalogs = catalogs
                updated += 1
        session.commit()

    print(f"Done. created={created} updated={updated} skipped={skipped}")


if __name__ == "__main__":
    main()
