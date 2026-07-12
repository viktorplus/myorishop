---
phase: 09-batch-tracking-ledger-integration
reviewed: 2026-07-12T14:13:01Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - alembic/versions/0009_batch_name.py
  - app/models.py
  - app/routes/receipts.py
  - app/services/receipts.py
  - app/templates/pages/history.html
  - app/templates/partials/history_rows.html
  - app/templates/partials/name_input.html
  - app/templates/partials/receipt_batch_chooser.html
  - app/templates/partials/receipt_form.html
  - app/templates/partials/sale_batch_pick.html
  - app/templates/partials/sale_lookup.html
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 9 (gap-closure): Code Review Report

**Reviewed:** 2026-07-12T14:13:01Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Scoped adversarial review of the Phase 9 UAT gap-closure changes only (diff base
`0a68d41`, plans 09-06..09-09). The diff is small and mostly careful: a portable
native `add_column` migration for `batches.name`, an auto-generated snapshotted
batch label, a `<template>`-wrapped table-OOB fix for htmx, a code-clears-autofilled-name
interaction, and a new `Код`/`Действие` column pair on `/history` with a return slot.

No BLOCKER-class defects were found in the diff — no injection, no data loss, no
raw-500 regression, and the migration stays PostgreSQL-portable. Two WARNINGs
concern the new batch-name label: it is generated from a UTC date (inconsistent
with the project's established `display_tz` convention, producing an off-by-one
day near local midnight) and can overflow the `String(200)` column on PostgreSQL.
Two INFO items cover a stale column-count comment and a defensive-rendering nit.

## Warnings

### WR-01: Batch name label uses a UTC date, contradicting the project's display-timezone convention

**File:** `app/services/receipts.py:206`
**Issue:** The auto-generated batch label is built from a UTC date:
```python
batch_name = f"{product.name} — {format_ru_date(utcnow_iso()[:10])}"
```
`utcnow_iso()` is UTC (`app/core.py:25`), so `[:10]` is the UTC calendar date.
Everywhere else the app renders operator-facing dates/times in `settings.display_tz`
(default `Europe/Moscow`, UTC+3) — see the `local_dt` filter (`app/routes/__init__.py:11`)
and, most tellingly, `app/services/reports.py:194` which computes "today" as
`datetime.now(ZoneInfo(settings.display_tz)).date()`. Because Moscow is always
ahead of UTC, any batch created between 00:00–03:00 local time gets a label
showing *yesterday's* date, while that same batch's `created_at` renders as
*today* through `local_dt` on `/history`. The snapshot is stored, so the wrong
date is permanent. The inline comment ("single local operator, label only")
acknowledges UTC but does not address the cross-surface inconsistency.
**Fix:** Compute the label date in the display timezone, mirroring `reports.py`:
```python
from datetime import datetime
from zoneinfo import ZoneInfo
from app.config import settings

local_date = datetime.now(ZoneInfo(settings.display_tz)).date().isoformat()
batch_name = f"{product.name} — {format_ru_date(local_date)}"
```

### WR-02: Generated batch name can exceed `batches.name` String(200) — PostgreSQL truncation/overflow risk

**File:** `app/services/receipts.py:206` (column: `app/models.py:169`, migration `alembic/versions/0009_batch_name.py:44`)
**Issue:** `Product.name` is `String(200)` (`app/models.py:93`) and the label appends
`" — dd.mm.yyyy"` (13 characters), so a maximal product name yields ~213 characters
into `batches.name`, declared `String(200)`. SQLite ignores declared `VARCHAR`
lengths so this stores silently today, but the project explicitly targets a
future PostgreSQL migration with the same models/columns (CLAUDE.md: "portable
ORM only", "PostgreSQL is a connection-string change"). On PostgreSQL this raises
`value too long for type character varying(200)` and aborts the receipt commit —
turning a normal receipt into a failure for long-named products.
**Fix:** Truncate the product portion so the composed label fits, or widen the
column. Simplest, portable, no migration:
```python
suffix = f" — {format_ru_date(local_date)}"
batch_name = (product.name[: 200 - len(suffix)]) + suffix
```
(Alternatively bump `batches.name` to `String(255)` in the model + migration.)

## Info

### IN-01: Stale column-count comment in history_rows.html

**File:** `app/templates/partials/history_rows.html:1-2`
**Issue:** The header comment still reads "the /history table body — 8 columns
over EVERY operation type", but this gap-closure added the `Код` and `Действие`
columns (the empty-state `colspan` was correctly bumped to 10 on line 15, and the
`<th>` set in `history.html` is now 10). The comment now misdescribes the layout,
which can mislead the next editor into using the wrong `colspan`.
**Fix:** Update the comment to "10 columns" to match the header and the
`colspan="10"` empty state.

### IN-02: Return link emits literal `sale_id=None` when a sale op has a NULL sale_id

**File:** `app/templates/partials/history_rows.html:64`
**Issue:** `hx-get="/returns?sale_id={{ r.op.sale_id }}&..."` — Jinja2 renders a
Python `None` as the literal string `"None"` (no `finalize` is configured on the
env, `app/routes/__init__.py:9`). If any `type="sale"` op ever carried a NULL
`sale_id`, the URL would contain `sale_id=None`; the returns fallback then queries
`Operation.sale_id == "None"` (`app/routes/returns.py:41-46`), matching nothing.
Impact is currently only latent because sales always set `sale_id=header.id`
(`app/services/sales.py:262`) and the GET path prefers `origin_op_id`
(`returns.py:37-39`), which this link always supplies. Flagged as INFO because it
is a robustness/readability nit rather than an active bug.
**Fix:** Guard the param, e.g. `sale_id={{ r.op.sale_id or '' }}`, so a NULL
renders as an empty (correctly-ignored) query value instead of the string `None`.

---

_Reviewed: 2026-07-12T14:13:01Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
