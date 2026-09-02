"""Import the per-catalog price history from the price-list archive.

Run: uv run --with xlrd python scripts/import_prices.py [--dir catalogs/price_lists]
     uv run python scripts/import_prices.py --export catalogs/catalog_prices.json.gz
     uv run python scripts/import_prices.py --from-export catalogs/catalog_prices.json.gz

Each workbook is a catalog issue whose filename encodes month + year in one of
several formats (01-2026, 03_2024, 2025-07, 25-11, with _calc/(1) suffixes).
BOTH extensions are read — the archive is 118 `.xls` plus 115 `.xlsx` — through
``read_workbook_sheets()``, which xlrd handles for the old format. Inside, the
real price sheets carry a header row with `КОД` and `ПЦ`; tester sheets
(`ПРОДУКТ`/`ЦЕНА`) and the empty `КАЛЬКУЛЯТОР` template are skipped.

Extracted columns (Oriflame layout):
  * ПЦ -> consumer_cents   (catalog / retail price)
  * ОП -> consultant_cents (consultant / purchase price)
  * ББ -> points           (catalog bonus points)
  * НАИМЕНОВАНИЕ -> name    (short, upper-case source name; the pretty name
                            stays in the dictionary, imported separately)

Whole-ruble prices are converted to integer cents. Helper data only — no
product/stock/ledger rows are touched.

Ownership rule (quick task 260902-m9g), and the load-bearing one: a source owns
the ``(year, number, code)`` triples it itself carries, NOT the whole table. No
path here empties catalog_prices any more. Before this task three code paths
did, so whichever importer ran last erased the other's work and the table held
a 15 798-row snapshot of the master price list instead of a 230 000-row price
history. ``upsert_price_rows()`` is the ONE writer, and an incoming ``None``
never overwrites a stored value — that is what keeps the master price list
(which has no ББ column) from nulling the bonus points the archive supplies.

Quick task 260902-g1q added the JSON transport, because the 118 MB
`catalogs/price_lists/` archive is deliberately kept out of git and out of the
Docker image — the server has no price lists and never will:

  ``--export FILE``       dumps catalog_prices into a compact JSON array (one
                          record per line). The export is ACCUMULATIVE, never
                          replacing: rows already in the target file that this
                          database does not have are kept, so the file can only
                          grow.
  ``--from-export FILE``  loads that file instead of parsing the archive, and
                          upserts it — the server's own rows are never touched.
  ``--only-missing``      (only with --from-export) inserts only rows whose
                          CODE is absent from catalog_prices. Still meaningful,
                          but no longer a safety mechanism: the plain path is
                          non-destructive too.

A ``FILE`` ending in ``.gz`` is gzipped transparently on both sides (41.7 MB of
JSON becomes ~4.7 MB) — `catalogs/catalog_prices.json.gz` is the transport that
actually reaches the server.

Second job — ``--restore-shades`` (quick task 260902-k2i)
--------------------------------------------------------
This module owns the price-list archive, so it also owns the ONE other thing
those files know and the database does not: in an Oriflame price list the
product type is written once, in the first row of a series, and every following
row is a bare shade («- ФАРФОРОВЫЙ»). The dictionary import took those rows
literally, so 33155 reads «Фарфоровый» — a colour with no object.

``--restore-shades`` walks BOTH ``*.xls`` and ``*.xlsx``, inherits the series
type onto its shade rows, and appends the recovered full names to
``app/services/rubric_overrides.json``. It opens NO database: it reads the
archive plus ``catalogs/products.json`` and writes one file. It is a dry run
unless ``--apply`` is given. Applying those names to an existing dictionary row
is the job of ``scripts/import_catalogs.py --restore-shade-names``.
"""

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update  # noqa: E402

from app.core import new_id, to_cents  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import CatalogPrice  # noqa: E402
from app.services.rubrics import (  # noqa: E402
    RUBRICS,
    SHADE_DASHES,
    classify_rubric_by_name,
    is_shade_tail,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PRICE_DIR = "catalogs/price_lists"
DEFAULT_PRODUCTS = "catalogs/products.json"
OVERRIDES_PATH = PROJECT_ROOT / "app" / "services" / "rubric_overrides.json"

# Dictionary.name is String(200); a longer candidate is rejected, not truncated.
MAX_NAME = 200

# « <spaces> <dash(es)> <spaces> » — the separator between the product type and
# the shade inside one full price-list name.
_SERIES_SEPARATOR = re.compile(r"\s+[" + "".join(SHADE_DASHES) + r"]+\s+")

# The exact shape of one exported row — the 7 model fields that carry data.
EXPORT_KEYS = frozenset(
    {"code", "year", "number", "name", "consumer_cents", "consultant_cents", "points"}
)


def parse_catalog(filename: str) -> tuple[int, int] | None:
    """Filename -> (year, number); handles MM-YYYY, YYYY-MM and YY-MM shapes."""
    stem = re.sub(r"\.xlsx?$", "", filename, flags=re.IGNORECASE)
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


def _find_header(rows, require=("code", "consumer")) -> tuple[int, dict[str, int]] | None:
    """Locate the header row (КОД + ПЦ) and map roles to column indexes.

    ``require`` names the roles that must be present for the row to count as a
    header. The price import needs a price column (the default); the shade
    restoration needs only ("code", "name") — a sheet with names and no ПЦ
    still carries the series structure.
    """
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
        if all(role in colmap for role in require):
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


def collect_prices_from_sheets(sheets) -> dict[str, dict]:
    """One workbook's sheets -> {code: row-data}.

    Pure: it takes the plain row tuples the reader already produced, so the
    unit tests need neither openpyxl nor xlrd — the same split
    ``collect_shade_candidates`` / ``scan_shade_candidates`` uses below.
    Within one workbook the last write wins (repeated rows, repeated sheets).
    """
    collected: dict[str, dict] = {}
    for rows in sheets:
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
            name = _cell(row, colmap, "name")
            name = str(name).strip()[:200] if name and str(name).strip() else None
            points = _cell(row, colmap, "points")
            collected[str(code).strip()] = {
                "consumer_cents": consumer,
                "consultant_cents": _cents(_cell(row, colmap, "consultant")),
                "points": int(points) if isinstance(points, (int, float)) and points > 0 else None,
                "name": name,
            }
    return collected


def collect_from_archive(
    files,
) -> tuple[dict[tuple[int, int, str], dict], dict[str, list[str]]]:
    """Walk the archive -> {(year, number, code): row-data} + what it could not use.

    Reads BOTH extensions through the readers this module already owns; no new
    reader is written here. A corrupt workbook is expected (12-2013.xls is a
    truncated OLE2 file) and is NAMED in the report instead of aborting the
    walk — the same try/except ``scan_shade_candidates`` uses.

    The report has three lists: ``unparsable_name`` (the three
    oriflame_prices_*.xlsx), ``unreadable`` (12-2013.xls) and
    ``no_price_column`` — a workbook that yielded no price row at all.

    That last one is deliberately "yielded nothing", not "no sheet carries a
    ПЦ header": in 04-2024.xls and 05-2024.xls the real price sheet has ОП and
    ДЦ but NO ПЦ, while the empty КАЛЬКУЛЯТОР template beside it does carry a
    ПЦ header. Keying the report on the header would leave both files silently
    unreported even though they contribute nothing — the report exists to name
    exactly that.

    Deduplicates by (year, number, code): duplicate files (01-2026 vs
    01-2026_ (1)) collapse to one; last write wins.
    """
    collected: dict[tuple[int, int, str], dict] = {}
    report: dict[str, list[str]] = {
        "unparsable_name": [],
        "unreadable": [],
        "no_price_column": [],
    }
    for path in files:
        cat = parse_catalog(path.name)
        if cat is None:
            report["unparsable_name"].append(path.name)
            continue
        try:
            sheets = read_workbook_sheets(path)
        except Exception as exc:  # a corrupt workbook is expected (12-2013.xls)
            report["unreadable"].append(f"{path.name} ({exc.__class__.__name__})")
            continue
        priced = collect_prices_from_sheets(sheets)
        if not priced:
            report["no_price_column"].append(path.name)
            continue
        year, number = cat
        for code, data in priced.items():
            collected[(year, number, code)] = data
    return collected, report


# --------------------------------------------------------------------------
# --restore-shades: recover the series product type for bare-shade rows
# --------------------------------------------------------------------------


def _normalise_cell(value):
    """xlrd hands every number back as a float — 33155 arrives as 33155.0.

    Integral floats are folded back to int at the reading boundary so that
    `_is_code` and every other existing helper see exactly what the openpyxl
    path gives them.
    """
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def read_workbook_sheets(path: Path) -> list[list[tuple]]:
    """One workbook -> a list of sheets, each a list of row tuples.

    openpyxl AND xlrd are imported HERE, not at module level, for the same
    reason the price import does it: both are dev-only and the Dockerfile
    builds with `uv sync --frozen --no-dev`, so a top-level import would make
    this whole script unimportable inside the production image. xlrd is not a
    project dependency at all — it is reached ad hoc via `uv run --with xlrd`.
    """
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            return [
                [_normalise_row(row) for row in ws.iter_rows(values_only=True)]
                for ws in wb.worksheets
            ]
        finally:
            wb.close()
    if suffix == ".xls":
        import xlrd

        book = xlrd.open_workbook(path, on_demand=True)
        try:
            sheets = []
            for name in book.sheet_names():
                ws = book.sheet_by_name(name)
                sheets.append([_normalise_row(ws.row_values(i)) for i in range(ws.nrows)])
                book.unload_sheet(name)
            return sheets
        finally:
            book.release_resources()
    raise ValueError(f"Unsupported workbook type: {path.name}")


def _normalise_row(row) -> tuple:
    return tuple(_normalise_cell(cell) for cell in row)


def price_list_files(folder: Path) -> list[Path]:
    """Every readable workbook in the archive, both extensions, sorted."""
    if not folder.is_dir():
        return []
    return sorted(
        (
            p
            for p in folder.iterdir()
            if p.is_file()
            and p.suffix.lower() in (".xls", ".xlsx")
            and not p.name.startswith("~$")  # Excel lock file
        ),
        key=lambda p: p.name,
    )


def split_series_type(name: str) -> str:
    """SPEC rule 1: the product type is everything before the LAST « - »."""
    text = (name or "").strip()
    matches = list(_SERIES_SEPARATOR.finditer(text))
    if not matches:
        return text
    return text[: matches[-1].start()].strip()


def is_shade_row(name: str) -> bool:
    """SPEC rule 2: a row whose name starts with a dash is a shade of the series."""
    return (name or "").lstrip().startswith(SHADE_DASHES)


def shade_text(name: str) -> str:
    """«  - ФАРФОРОВЫЙ » -> « ФАРФОРОВЫЙ »."""
    return (name or "").lstrip().lstrip("".join(SHADE_DASHES) + " \t").strip()


def collect_shade_candidates(sheets) -> tuple[dict[str, Counter], int]:
    """Walk the sheets top to bottom, inheriting the series type onto shades.

    Returns ``{code: Counter[(type, shade)]}`` plus the number of shade rows
    dropped for lack of a current type — that count is the diagnostic which
    explains any deviation from the expected number of restored names.

    Pure: it takes plain row tuples, so the unit tests need neither xlrd nor
    openpyxl.
    """
    candidates: dict[str, Counter] = {}
    dropped = 0
    for rows in sheets:
        header = _find_header(rows, require=("code", "name"))
        if header is None:
            continue
        start, colmap = header
        current_type: str | None = None
        for row in rows[start + 1 :]:
            raw_name = _cell(row, colmap, "name")
            name = str(raw_name).strip() if raw_name is not None else ""
            if not name:
                continue  # a blank row changes nothing
            code = _cell(row, colmap, "code")
            if _is_code(code):
                if is_shade_row(name):
                    if current_type:
                        key = (current_type, shade_text(name))
                        candidates.setdefault(str(code).strip(), Counter())[key] += 1
                    else:
                        dropped += 1
                else:
                    current_type = split_series_type(name)
            elif not is_shade_row(name):
                # SPEC rule 3: «серия обрывается на следующем заголовке» — a
                # code-less title row («МАКИЯЖ») ends the series.
                current_type = None
    return candidates, dropped


def pick_full_name(counter: Counter) -> str:
    """SPEC: the LONGEST spelling of the type wins, ties go to the most frequent.

    The last tie-break is the (type, shade) pair itself, so the result does not
    depend on the order the archive happened to be read in.
    """
    (type_, shade), _count = max(
        counter.items(), key=lambda item: (len(item[0][0]), item[1], item[0])
    )
    return f"{type_} - {shade}"


def display_name(raw: str) -> str:
    """SPEC: the справочник's own sentence case — first letter up, rest down."""
    text = re.sub(r"\s+", " ", (raw or "").strip())
    return text[:1].upper() + text[1:].lower()


def restore_full_name(counter: Counter, current: str) -> str | None:
    """The restored name for `current`, or None when no variant fits it.

    SPEC detection rule, and the load-bearing one: the справочник name must
    equal the shade of AT LEAST ONE recorded variant — not of the single
    «best» one. Measuring against one best variant is the methodology error
    the SPEC calls out by name: the same code is a series header in one price
    list and a shade row in another, so the best variant's shade often is not
    the shade the справочник kept. (Any-variant gives the SPEC's 607; best-only
    gives 337.)

    Among the variants that DO carry this shade the normalisation rule then
    applies — the longest type wins, ties go to the most frequent. Restoring
    from a shade-matched variant is also what guarantees the new name ends with
    the old one, so no name can ever get shorter or lose its colour.
    """
    cur = (current or "").strip().lower()
    hits = Counter({key: n for key, n in counter.items() if key[1].strip().lower() == cur})
    if not hits:
        return None
    return display_name(pick_full_name(hits))


def current_name(code: str, products: dict[str, dict], existing: dict[str, dict]) -> str:
    """The name the справочник actually shows today — `resolve_name`'s rule.

    An override wins over products.json, so THAT is the name the predicate has
    to judge: a code whose override was already corrected by hand carries a
    product type and is out of reach; a code whose override is still the bare
    shade is exactly what this task exists to fix.
    """
    entry = existing.get(code)
    if entry:
        better = (entry.get("name") or "").strip()
        if better:
            return better
    return ((products.get(code) or {}).get("name") or "").strip()


def build_shade_overrides(
    candidates: dict[str, Counter], products: dict[str, dict], existing: dict[str, dict]
) -> tuple[dict[str, dict], dict[str, int]]:
    """The selection: which codes get their product type back, and under what name.

    A code qualifies only when the name the справочник shows TODAY (override
    first, else products.json) is nothing but the shade of the restored one.
    A name that already carries a product type cannot equal any variant's
    shade, so it is out of reach — that is the whole safety story.

    Most of the selected codes already HAVE an override entry whose name is
    that very bare shade (earlier quick tasks wrote them that way), and
    `resolve_name` makes the override win everywhere — so leaving them alone
    would silently undo the restoration on the next import. Their entry keeps
    its `conf` and its web-verified `rubric`; only the name is replaced.
    """
    stats = {
        "codes": len(candidates),
        "in_products": sum(1 for code in candidates if code in products),
        "not_in_products": 0,
        "no_shade_match": 0,
        "rejected_has_type": 0,
        "rejected_too_long": 0,
        "updated": 0,
        "appended": 0,
        "selected": 0,
    }
    fresh: dict[str, dict] = {}
    for code in sorted(candidates):
        current = current_name(code, products, existing)
        if not current:
            stats["not_in_products"] += 1
            continue
        restored = restore_full_name(candidates[code], current)
        if restored is None:
            stats["no_shade_match"] += 1
            continue
        if len(restored) > MAX_NAME:
            stats["rejected_too_long"] += 1
            continue
        if not is_shade_tail(current, restored):
            stats["rejected_has_type"] += 1
            continue
        prior = existing.get(code)
        if prior is not None and prior.get("rubric") in RUBRICS:
            # A web-verified rubric beats anything a name classifier can say.
            conf, rubric = prior.get("conf", "series"), prior["rubric"]
            stats["updated"] += 1
        else:
            # The rubric can never get WORSE than today's: an unclassifiable
            # restored name falls back to what the bare shade resolved to.
            conf = "series"
            rubric = classify_rubric_by_name(restored)
            if rubric == "Прочее":
                rubric = classify_rubric_by_name(current)
            stats["appended" if prior is None else "updated"] += 1
        fresh[code] = {"conf": conf, "name": restored, "rubric": rubric}
        stats["selected"] += 1
    return fresh, stats


def merge_overrides(existing: dict[str, dict], fresh: dict[str, dict]) -> dict[str, dict]:
    """Name-only merge — the same shape quick task 260721-oti used.

    Not one existing key MOVES, and not one existing `conf` or `rubric`
    changes: an entry that is being restored has ONLY its `name` replaced (and
    only ever by a strictly longer name ending in the same shade). A code that
    is genuinely new is appended in plain sorted order, after everything.
    """
    merged = {code: dict(entry) for code, entry in existing.items()}
    for code in sorted(fresh):
        if code in merged:
            merged[code]["name"] = fresh[code]["name"]
        else:
            merged[code] = fresh[code]
    return merged


def read_overrides(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_overrides(dest: Path, data: dict[str, dict]) -> None:
    """Reproduce the file's byte form: indent=1, CRLF, no trailing newline."""
    with dest.open("w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=1))


def scan_shade_candidates(files) -> tuple[dict[str, Counter], int, list[str]]:
    """Merge the per-file candidates of the whole archive; name what failed."""
    candidates: dict[str, Counter] = {}
    dropped = 0
    unreadable: list[str] = []
    for path in files:
        try:
            sheets = read_workbook_sheets(path)
        except Exception as exc:  # a corrupt workbook is expected (12-2013.xls)
            unreadable.append(f"{path.name} ({exc.__class__.__name__})")
            continue
        found, missed = collect_shade_candidates(sheets)
        for code, counter in found.items():
            candidates.setdefault(code, Counter()).update(counter)
        dropped += missed
    return candidates, dropped, unreadable


SAMPLE_CODES = ("32287", "33155", "33157", "33158", "33159")


def _run_restore_shades(price_dir: Path, products_path: Path, apply: bool, report) -> None:
    files = price_list_files(price_dir)
    if not files:
        sys.exit(f"No price lists (*.xls / *.xlsx) in {price_dir}")
    by_ext = Counter(p.suffix.lower() for p in files)
    breakdown = "  ".join(f"{ext}: {n}" for ext, n in sorted(by_ext.items()))
    print(f"Price lists: {len(files)}  {breakdown}")

    candidates, dropped, unreadable = scan_shade_candidates(files)
    if unreadable:
        print(f"Unreadable ({len(unreadable)}): {unreadable}")

    products = json.loads(products_path.read_text(encoding="utf-8"))
    existing = read_overrides(OVERRIDES_PATH)
    fresh, stats = build_shade_overrides(candidates, products, existing)

    print(f"Shade codes found: {stats['codes']}")
    print(f"  in products.json: {stats['in_products']}   absent: {stats['not_in_products']}")
    print(f"  rejected, name already carries a type: "
          f"{stats['no_shade_match'] + stats['rejected_has_type']}")
    print(f"  rejected, longer than {MAX_NAME} chars: {stats['rejected_too_long']}")
    print(f"  shade rows dropped for lack of a series type: {dropped}")
    print(f"SELECTED: {stats['selected']}  "
          f"(name-only update of an existing entry: {stats['updated']}, "
          f"appended as new: {stats['appended']})")
    print("Rubrics: " + ", ".join(f"{r}={n}" for r, n in Counter(
        e["rubric"] for e in fresh.values()).most_common()))
    for code in SAMPLE_CODES:
        print(f"  {code}: {fresh.get(code, {}).get('name', '— not selected —')}")

    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(fresh, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Report: {report}")

    merged = merge_overrides(existing, fresh)
    print(f"Overrides: {len(existing)} -> {len(merged)}")
    if not apply:
        print("DRY RUN — nothing written. Re-run with --apply.")
        return
    write_overrides(OVERRIDES_PATH, merged)
    print(f"Written: {OVERRIDES_PATH}")


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
        name = record["name"]
        if name is not None:
            if not isinstance(name, str):
                sys.exit(f"{source}: record {i} has a non-string name {name!r}")
            if len(name) > MAX_NAME:
                sys.exit(
                    f"{source}: record {i} has a name of {len(name)} chars, "
                    f"longer than the {MAX_NAME}-char column: {name[:40]!r}…"
                )
        # `>= 0`, not `> 0`, on purpose: the producers (`_cents` above and
        # import_master_pricelist._cents) only ever emit positive-or-None, but
        # export_prices() reads whatever the database holds, so a legitimate
        # re-export of a stored zero must not be rejected here.
        for field in ("consumer_cents", "consultant_cents", "points"):
            value = record[field]
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                sys.exit(f"{source}: record {i} has a non-integer {field} {value!r}")
    return records


def _open_export(path: Path, mode: str, *, encoding: str = "utf-8", newline: str | None = None):
    """Open an export file — `gzip.open` for a `.gz` suffix, `path.open` otherwise.

    `mode` is a TEXT mode ("rt" / "wt"): both backends accept it, and both
    accept `encoding` and `newline` with the same meaning, so BOTH keyword
    arguments are forwarded unchanged to whichever one is chosen. Neither
    branch may fall back to a platform-dependent default — `write_export`'s
    explicit LF has to hold on a plain `.json` exactly as it does on a `.gz`,
    or a re-export stops being byte-stable across platforms.
    """
    path = Path(path)
    if path.suffix.lower() == ".gz":
        return gzip.open(path, mode, encoding=encoding, newline=newline)
    return path.open(mode, encoding=encoding, newline=newline)


def load_export(path: Path) -> list[dict]:
    """Read + validate an --export file, `.gz` included. Exits on anything malformed.

    A truncated or corrupt gzip transport file must fail LOUDLY and by name,
    exactly like invalid JSON — 4.7 MB arriving over the wire is precisely
    where a silent traceback would be worst.
    """
    path = Path(path)
    try:
        with _open_export(path, "rt") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError as exc:
        sys.exit(f"Export file is not valid JSON: {path} ({exc})")
    except (gzip.BadGzipFile, EOFError) as exc:
        sys.exit(f"Export file is not a readable gzip: {path} ({exc.__class__.__name__}: {exc})")
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


# The four fields a source may carry for a triple it owns; `id`, `year`,
# `number` and `code` are the identity and never change.
MUTABLE_FIELDS = ("name", "consumer_cents", "consultant_cents", "points")


def upsert_price_rows(session, records: list[dict], chunk: int = 5000) -> dict[str, int]:
    """The ONE writer for catalog_prices: insert new triples, update changed ones.

    A source owns the (year, number, code) triples it itself carries and
    nothing else, so this never removes a row and never commits — everything
    happens inside the caller's single transaction.

    The merge rule is one rule with no mode flag: a field changes when the
    incoming value is not None and differs from the stored one. An incoming
    None NEVER overwrites a stored value, so the master price list (no ББ
    column at all) cannot null the bonus points the archive supplies, and the
    archive cannot impoverish the master snapshot either. It is symmetric on
    purpose — neither source may make the other poorer.

    Performance shape, and the trap to avoid: the existing triples are read in
    ONE query (a per-row SELECT over ~238 000 rows is unusably slow), and the
    model objects are built per chunk rather than up front — 223 000
    CatalogPrice instances materialised at once is hundreds of MB resident.
    """
    stats = {"inserted": 0, "updated": 0, "unchanged": 0}
    if not records:
        return stats

    stored = {
        (row.year, row.number, row.code): (
            row.id,
            row.name,
            row.consumer_cents,
            row.consultant_cents,
            row.points,
        )
        for row in session.execute(
            select(
                CatalogPrice.id,
                CatalogPrice.year,
                CatalogPrice.number,
                CatalogPrice.code,
                CatalogPrice.name,
                CatalogPrice.consumer_cents,
                CatalogPrice.consultant_cents,
                CatalogPrice.points,
            )
        )
    }

    fresh: list[dict] = []
    changed: list[dict] = []
    for record in records:
        current = stored.get(_price_key(record))
        if current is None:
            fresh.append(record)
            continue
        row_id, *values = current
        # Every mapping handed to one session.execute(update(...)) call must
        # carry the SAME key set or the executemany compile breaks — so build
        # the full merged mapping, not just the delta.
        merged = {}
        differs = False
        for field, old in zip(MUTABLE_FIELDS, values, strict=True):
            incoming = record.get(field)
            if incoming is not None and incoming != old:
                merged[field] = incoming
                differs = True
            else:
                merged[field] = old
        if differs:
            changed.append({"id": row_id, **merged})
        else:
            stats["unchanged"] += 1

    for start in range(0, len(fresh), chunk):
        batch = fresh[start : start + chunk]
        session.bulk_save_objects(build_price_rows(batch))
        stats["inserted"] += len(batch)
    for start in range(0, len(changed), chunk):
        batch = changed[start : start + chunk]
        session.execute(update(CatalogPrice), batch)
        stats["updated"] += len(batch)
    return stats


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
    with _open_export(dest, "wt", newline="\n") as handle:
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
        stats = upsert_price_rows(session, records)
        session.commit()
        after = session.query(CatalogPrice).count()
    print("Mode: upsert (a source owns its own (year, number, code) triples; nothing removed)")
    print(
        f"Inserted: {stats['inserted']}  updated: {stats['updated']}  "
        f"unchanged: {stats['unchanged']}"
    )
    print(f"CatalogPrice: {before} -> {after}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import catalog prices from the price lists")
    parser.add_argument(
        "--dir", default=DEFAULT_PRICE_DIR, help="folder with the xls/xlsx price lists"
    )
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
    parser.add_argument(
        "--restore-shades",
        action="store_true",
        help="recover the series product type for shade rows into rubric_overrides.json",
    )
    parser.add_argument(
        "--apply", action="store_true", help="actually write (requires --restore-shades)"
    )
    parser.add_argument("--products", default=DEFAULT_PRODUCTS, help="path to products.json")
    parser.add_argument("--report", metavar="FILE", help="dump the selected entries for review")
    args = parser.parse_args()

    # Foot-gun guards, before any DB access: --only-missing must never silently
    # degrade into the destructive xlsx full replace.
    if args.export and args.from_export:
        sys.exit("--export cannot be combined with --from-export")
    if args.only_missing and not args.from_export:
        sys.exit("--only-missing works only with --from-export; the archive path upserts by triple")
    if args.restore_shades and (args.export or args.from_export):
        sys.exit(
            "--restore-shades opens no database; "
            "it cannot be combined with --export or --from-export"
        )
    if args.apply and not args.restore_shades:
        sys.exit("--apply is meaningless without --restore-shades")

    if args.restore_shades:
        products = _resolve(args.products)
        if not products.is_file():
            sys.exit(f"products.json not found: {products}")
        _run_restore_shades(
            _resolve(args.dir),
            products,
            args.apply,
            _resolve(args.report) if args.report else None,
        )
        return

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
    files = price_list_files(folder)
    if not files:
        sys.exit(f"No price lists (*.xls / *.xlsx) in {folder}")

    collected, report = collect_from_archive(files)

    catalogs = {(y, n) for (y, n, _c) in collected}
    codes = {c for (_y, _n, c) in collected}
    print(f"Files: {len(files)}  catalogs: {len(catalogs)}  codes: {len(codes)}")
    print(f"Collected rows: {len(collected)}")
    for label, key in (
        ("Unparsable filename", "unparsable_name"),
        ("Unreadable", "unreadable"),
        ("No price column", "no_price_column"),
    ):
        if report[key]:
            print(f"{label} ({len(report[key])}): {report[key]}")

    # The failure that actually happened before this task: a --dir pointing at
    # a folder whose only workbook has an unparsable name collected 0 rows and
    # then emptied the table. Nothing is written on an empty walk.
    if not collected:
        sys.exit(f"Collected 0 price rows from {folder} — nothing written")

    with SessionLocal() as session:
        before = session.query(CatalogPrice).count()
        stats = upsert_price_rows(
            session,
            [
                {"year": year, "number": number, "code": code, **data}
                for (year, number, code), data in collected.items()
            ],
        )
        session.commit()
        after = session.query(CatalogPrice).count()
    print(
        f"Inserted: {stats['inserted']}  updated: {stats['updated']}  "
        f"unchanged: {stats['unchanged']}"
    )
    print(f"CatalogPrice: {before} -> {after}")


if __name__ == "__main__":
    main()
