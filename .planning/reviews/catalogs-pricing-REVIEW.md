---
phase: catalogs-pricing
reviewed: 2026-07-13T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - alembic/versions/0010_dictionary_catalogs.py
  - alembic/versions/0011_catalog_prices.py
  - app/config.py
  - app/main.py
  - app/models.py
  - app/routes/catalogs.py
  - app/routes/products.py
  - app/services/catalogs.py
  - app/services/pricing.py
  - app/templates/base.html
  - app/templates/pages/catalog_detail.html
  - app/templates/pages/catalogs.html
  - app/templates/pages/product_form.html
  - app/templates/partials/product_price_autofill.html
  - scripts/import_catalogs.py
  - scripts/import_prices.py
  - tests/test_catalog.py
  - tests/test_catalogs_feature.py
  - tests/test_pricing_feature.py
findings:
  critical: 0
  warning: 5
  info: 3
  total: 8
status: issues_found
---

# catalogs-pricing: Code Review Report

**Reviewed:** 2026-07-13
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Reviewed the catalogs-pricing feature branch: two Alembic migrations, the
`catalogs`/`pricing` services, the `/catalogs` and product-form price-autofill
routes, four templates, and the two xlsx/json import scripts.

Overall the security-sensitive surfaces hold up well. Path traversal on the
PDF-serving route is not exploitable (URL codes are regex-constrained to
`\d{4}-\d{1,2}` and the served filename always comes from a trusted folder
scan, plus a belt-and-braces containment check). No raw/SQLite-specific SQL,
no `|safe`/XSS sink (Jinja2 autoescaping is on and only numeric labels are
interpolated unescaped), and money stays integer-cents end to end — the xlsx
importer routes floats through the Decimal-based `to_cents`, so no float
corruption. I verified empirically that `bulk_save_objects` does apply the
Python `default=utcnow_iso`, so the NOT NULL `created_at`/`updated_at` columns
in `catalog_prices` are populated and the price import does not crash.

No blockers. The findings are correctness gaps in the messy-filename parsing
(the PDF scanner and the xlsx importer parse filenames by two different,
non-equivalent algorithms, and the PDF one is fragile), a silent key-join risk
between the two import sources, and some maintainability/portability notes.

## Warnings

### WR-01: `_file_key` folds ALL filename digits, so a digit-bearing suffix corrupts the catalog number

**File:** `app/services/catalogs.py:59-68`
**Issue:** `_file_key` does `"".join(re.findall(r"\d+", stem))` then takes the
first 4 digits as year and *all remaining digits* as the number. Any digit in
a filename suffix is swallowed into the number. The import-prices docstring
explicitly calls out duplicate copies named like `01-2026_ (1).xlsx`; the same
`… (1).pdf` / `…v2.pdf` pattern for a PDF would parse to a bogus catalog. Example:
`2026-04 (1).pdf` -> digits `2026041` -> `(2026, 41)` instead of `(2026, 4)`.
This diverges from `scripts/import_prices.py:parse_catalog`, which robustly uses
only the first two digit groups. The two sources that must agree on `(year,
number)` use different, non-equivalent parsers.
**Fix:** Parse the PDF filename with the same two-group logic as
`parse_catalog`, e.g.:
```python
def _file_key(filename: str) -> tuple[int, int] | None:
    nums = re.findall(r"\d+", Path(filename).stem)
    if len(nums) >= 2:
        a, b = int(nums[0]), int(nums[1])
        return (a, b) if len(nums[0]) == 4 else (b, a)
    # single 7-digit "2025005" no-separator form:
    if len(nums) == 1 and len(nums[0]) >= 5:
        return int(nums[0][:4]), int(nums[0][4:])
    return None
```

### WR-02: PDF scanner and xlsx importer disagree on YY-MM filenames -> a catalog can have prices but no PDF (or vice versa)

**File:** `app/services/catalogs.py:59-68`
**Issue:** `_file_key` rejects any stem with fewer than 5 digits, so a
`YY-MM` PDF such as `25-11.pdf` returns `None` and the PDF silently vanishes
from `/catalogs`. But `scripts/import_prices.py:parse_catalog` *does* accept
`25-11` (the `a > 17` YY-MM branch, exercised by `test_import_filename_parsing`).
The result is asymmetric: an issue whose xlsx used `YY-MM` gets prices imported
but no browsable/linkable PDF, and the product-card catalog links
(`catalogs_for_code`) drop it too. Today's files all use `YYYY-…`, so this is
latent, but the two code paths for the same concept should not diverge.
**Fix:** Share one filename->`(year, number)` parser between the service and
the import script (extract `parse_catalog` into `app/services/catalogs.py` and
call it from both), so PDF and xlsx filename handling can never drift.

### WR-03: `scan_catalog_files` silently drops a colliding PDF, and which one wins is nondeterministic

**File:** `app/services/catalogs.py:71-81`
**Issue:** `mapping.setdefault(key, pdf.name)` keeps the *first* PDF for a given
`(year, number)` in `folder.glob("*.pdf")` order, which is filesystem-dependent.
`2025-01.pdf` and `2025001.pdf` both normalize to `(2025, 1)`; if both exist,
one is served and the other is silently ignored, and the choice is not stable
across machines. No warning is surfaced.
**Fix:** Detect collisions explicitly and either prefer a canonical form or log
the duplicate, e.g. sort the glob deterministically and warn when a key already
exists instead of silently keeping the first.

### WR-04: Catalog price join depends on exact code-string equality across two independent imports

**File:** `app/templates/pages/catalog_detail.html:26-31`, `app/routes/catalogs.py:47-58`, `scripts/import_catalogs.py:62-71`, `scripts/import_prices.py:140`
**Issue:** The detail page maps prices by `prices.get(entry.code)`, matching
`Dictionary.code` (keys from `products.json`, stored as `str(code).strip()`)
against `CatalogPrice.code` (from an xlsx numeric cell, stored as
`str(code).strip()`, e.g. `str(46413)`). If the JSON side ever carries a
leading zero or other formatting (`"046413"`) while the xlsx numeric cell
yields `"46413"` (or vice versa), the join silently fails and the product shows
`—` even though a price exists. The two import paths normalize codes
independently with no shared canonical form, and there is no test covering a
formatting mismatch.
**Fix:** Normalize codes to a single canonical form at both import points
(e.g. strip leading zeros, or `.lstrip("0")`-tolerant compare), or store codes
zero-padded consistently. At minimum add a test asserting the join holds for a
leading-zero code.

### WR-05: `parse_catalog` YY-MM heuristic cannot represent 2017 and silently skips ambiguous names

**File:** `scripts/import_prices.py:38-53`
**Issue:** The `a > 17` / `b > 17` heuristic assumes catalog numbers never
exceed 17. A `YY-MM` file for year 2017 (`17-05.xlsx`) hits `a == 17` (not
`> 17`), then `b == 5` (not `> 17`), and returns `None` — the file is skipped
and its prices are dropped with only an aggregate "Skipped" line. The same
happens for any `MM-YY`/`YY-MM` pair where both numbers are ≤ 17. All current
files use a 4-digit year so this is latent, but it is silent data loss the day
a 2-digit-year file appears.
**Fix:** Disambiguate on an explicit separator/position convention rather than
magnitude, or require a 4-digit year in the import contract and *fail loudly*
(non-zero exit / explicit per-file message) for any filename that cannot be
parsed unambiguously, instead of silently skipping.

## Info

### IN-01: Migrations 0010/0011 bypass the project's `render_as_batch` convention

**File:** `alembic/versions/0010_dictionary_catalogs.py:28-34`, `alembic/versions/0011_catalog_prices.py:29-54`
**Issue:** CLAUDE.md mandates `render_as_batch=True` for SQLite migrations.
These use native `op.add_column` / `op.create_table` / `op.drop_column`. It is
documented in-file and works on the local SQLite 3.50 (native `DROP COLUMN`
needs ≥ 3.35), so this is intentional, but it is a deviation worth flagging:
the 0010 downgrade would fail on an older SQLite, and mixing batch/native
styles across the migration history is a maintenance footgun.
**Fix:** Either keep the documented native form (acceptable given the pinned
runtime) or wrap the `drop_column` in `op.batch_alter_table` for consistency
with the rest of the history.

### IN-02: `import_prices` drops rows and prices with no per-row diagnostic

**File:** `scripts/import_prices.py:83-151`
**Issue:** Rows are silently skipped when the code cell is non-numeric, when a
price cell is text rather than a number (`_cents` returns `None` for any
non-`int/float`), or when `consumer` is missing. Only aggregate counts are
printed. For a warehouse operator, a price that quietly fails to import is hard
to notice and audit.
**Fix:** Track and print a small sample of skipped `(file, sheet, row, code)`
for text-typed or zero prices so missing prices are diagnosable.

### IN-03: Membership queries load the whole Dictionary table into Python each request

**File:** `app/services/catalogs.py:84-93, 149-158`
**Issue:** `_membership_counts` and `products_in_catalog` `select(Dictionary)`
every row and filter the JSON `catalogs` list in Python on each `/catalogs`
render. Correct and portable, but it re-scans the full table (and the disk
folder) per request. Performance is out of scope for this review; noting as a
maintainability marker for when the dictionary grows or PostgreSQL JSON
querying becomes available.
**Fix:** No action required now; revisit with a JSON containment query
(`json_each` / PostgreSQL `?`/`@>`) if the dictionary grows large.

---

_Reviewed: 2026-07-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
