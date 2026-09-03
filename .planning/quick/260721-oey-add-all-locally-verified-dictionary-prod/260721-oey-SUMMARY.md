---
quick_id: 260721-oey
title: Add all locally verified dictionary product names
status: complete
---

# Changed

- Added 13 names reconstructed from adjacent product-series rows in local historical Oriflame price lists.
- Updated coverage from 108 to 121 of 592 priority codes.
- Added codes: 20440, 30476-30478, 31434-31440, 32568, and 48667.
- Used only product types and lines explicitly present in the local source rows.

# Source evidence

- `catalogs/price_lists/10-2016.xls`: code 20440 inherits the product title from code 20437.
- `catalogs/price_lists/17-2017.xls` and `17-2016.xls`: codes 30476-30478 inherit the product title from code 30475.
- `catalogs/price_lists/17-2017.xls`: codes 31434-31440 inherit the product title from code 31433.
- `catalogs/price_lists/14-2016.xls`: code 32568 inherits the product title from code 32566.
- `catalogs/price_lists/07-2026.xlsx`: code 48667 inherits the product title from code 46874.

# Verification

- JSON parses successfully as UTF-8.
- 121 unique codes; no duplicates or blank replacement names.
- Every output code belongs to the low/medium priority set.
- Every output name differs from its input `current_name`.
- Numeric code ordering is preserved.
- 471 priority codes remain without a replacement.

# Notes

- No commit was created.
