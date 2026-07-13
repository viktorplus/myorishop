"""Catalog service (CAT-04): published PDF catalogs + product membership.

The catalog list is derived at request time by scanning the PDF folder
(settings.catalogs_dir) — there is NO catalog metadata table. Membership is
read from the Dictionary.catalogs JSON column (imported from
catalogs/products.json by scripts/import_catalogs.py).

Two code shapes exist and are bridged here:
  * JSON code   "MM_YY"   e.g. "01_26"  — stored in Dictionary.catalogs
  * URL code    "YYYY-MM" e.g. "2026-01" — used in /catalogs/{url_code} routes
Both map bijectively to a (year, number) pair, which is the internal key.
"""

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Dictionary

_JSON_CODE_RE = re.compile(r"^(\d{1,2})_(\d{2})$")  # MM_YY
_URL_CODE_RE = re.compile(r"^(\d{4})-(\d{1,2})$")  # YYYY-MM


def parse_json_code(code: str) -> tuple[int, int] | None:
    """ "01_26" -> (2026, 1); returns None on any unexpected shape."""
    m = _JSON_CODE_RE.match(code.strip())
    if not m:
        return None
    month, yy = int(m.group(1)), int(m.group(2))
    return 2000 + yy, month


def parse_url_code(code: str) -> tuple[int, int] | None:
    """ "2026-01" -> (2026, 1); returns None on any unexpected shape."""
    m = _URL_CODE_RE.match(code.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def to_json_code(year: int, number: int) -> str:
    """(2026, 1) -> "01_26" (the Dictionary.catalogs storage form)."""
    return f"{number:02d}_{year % 100:02d}"


def to_url_code(year: int, number: int) -> str:
    """(2026, 1) -> "2026-01" (the /catalogs route + display form)."""
    return f"{year}-{number:02d}"


def catalog_label(year: int, number: int) -> str:
    """Human label: (2026, 1) -> "Каталог 1 · 2026"."""
    return f"Каталог {number} · {year}"


def _file_key(filename: str) -> tuple[int, int] | None:
    """Normalize a PDF filename to (year, number) across the messy formats.

    Handles "2025-01.pdf", "2025005.pdf" and "2026-04_ru.pdf" uniformly:
    the first 4 digits are the year, the remaining digits are the number.
    """
    digits = "".join(re.findall(r"\d+", Path(filename).stem))
    if len(digits) < 5:
        return None
    return int(digits[:4]), int(digits[4:])


def scan_catalog_files() -> dict[tuple[int, int], str]:
    """Map (year, number) -> pdf filename for every PDF in the catalogs dir."""
    folder = Path(settings.catalogs_dir)
    mapping: dict[tuple[int, int], str] = {}
    if not folder.is_dir():
        return mapping
    for pdf in folder.glob("*.pdf"):
        key = _file_key(pdf.name)
        if key is not None:
            mapping.setdefault(key, pdf.name)
    return mapping


def _membership_counts(session: Session) -> dict[tuple[int, int], int]:
    """Tally how many dictionary codes reference each catalog (year, number)."""
    counts: dict[tuple[int, int], int] = {}
    rows = session.scalars(select(Dictionary.catalogs)).all()
    for cats in rows:
        for code in cats or []:
            key = parse_json_code(code)
            if key is not None:
                counts[key] = counts.get(key, 0) + 1
    return counts


def list_catalogs(session: Session) -> list[dict]:
    """All catalog PDFs, newest first, with product counts (CAT-04)."""
    files = scan_catalog_files()
    counts = _membership_counts(session)
    catalogs = [
        {
            "year": year,
            "number": number,
            "filename": filename,
            "url_code": to_url_code(year, number),
            "label": catalog_label(year, number),
            "product_count": counts.get((year, number), 0),
        }
        for (year, number), filename in files.items()
    ]
    catalogs.sort(key=lambda c: (c["year"], c["number"]), reverse=True)
    return catalogs


def get_catalog(url_code: str) -> dict | None:
    """Catalog descriptor by URL code (folder scan only), or None if no PDF."""
    key = parse_url_code(url_code)
    if key is None:
        return None
    filename = scan_catalog_files().get(key)
    if filename is None:
        return None
    year, number = key
    return {
        "year": year,
        "number": number,
        "filename": filename,
        "url_code": to_url_code(year, number),
        "label": catalog_label(year, number),
    }


def catalog_file_path(url_code: str) -> Path | None:
    """Absolute path of the PDF for a URL code, validated to stay in the dir.

    The filename comes from the trusted folder scan (never from user input),
    so path traversal is impossible; the containment check is belt-and-braces.
    """
    catalog = get_catalog(url_code)
    if catalog is None:
        return None
    folder = Path(settings.catalogs_dir).resolve()
    candidate = (folder / catalog["filename"]).resolve()
    if folder not in candidate.parents:
        return None
    return candidate if candidate.is_file() else None


def products_in_catalog(session: Session, url_code: str) -> list[Dictionary]:
    """Dictionary entries present in the given catalog, ordered by name."""
    key = parse_url_code(url_code)
    if key is None:
        return []
    json_code = to_json_code(*key)
    entries = session.scalars(select(Dictionary)).all()
    matched = [e for e in entries if json_code in (e.catalogs or [])]
    matched.sort(key=lambda e: e.name.lower())
    return matched


def catalogs_for_code(session: Session, code: str) -> list[dict]:
    """Catalogs a product code appears in, newest first (product-card view).

    Only catalogs with an actual PDF on disk are returned, so every entry is
    a working link. Reads membership from the Dictionary row for `code`.
    """
    code = (code or "").strip()
    if not code:
        return []
    entry = session.scalars(select(Dictionary).where(Dictionary.code == code)).first()
    if entry is None or not entry.catalogs:
        return []
    files = scan_catalog_files()
    result = []
    for json_code in entry.catalogs:
        key = parse_json_code(json_code)
        if key is None or key not in files:
            continue
        year, number = key
        result.append(
            {
                "year": year,
                "number": number,
                "url_code": to_url_code(year, number),
                "label": catalog_label(year, number),
            }
        )
    result.sort(key=lambda c: (c["year"], c["number"]), reverse=True)
    return result
