---
phase: 33-back-dated-operations
reviewed: 2026-09-05T00:00:00Z
depth: standard
iteration: 2
files_reviewed: 96
files_reviewed_list:
  - alembic/versions/0027_ledger_business_date_and_reversal_links.py
  - app/__init__.py
  - app/core.py
  - app/db.py
  - app/main.py
  - app/models.py
  - app/routes/__init__.py
  - app/routes/corrections.py
  - app/routes/customers.py
  - app/routes/finance.py
  - app/routes/history.py
  - app/routes/mobile_corrections.py
  - app/routes/mobile_finance.py
  - app/routes/mobile_history.py
  - app/routes/mobile_receipts.py
  - app/routes/mobile_returns.py
  - app/routes/mobile_sales.py
  - app/routes/mobile_transfers.py
  - app/routes/mobile_writeoff.py
  - app/routes/receipts.py
  - app/routes/reports.py
  - app/routes/returns.py
  - app/routes/sales.py
  - app/routes/sync.py
  - app/routes/transfers.py
  - app/routes/writeoffs.py
  - app/services/corrections.py
  - app/services/customers.py
  - app/services/dashboard.py
  - app/services/export.py
  - app/services/finance.py
  - app/services/finance_reports.py
  - app/services/ledger.py
  - app/services/operations.py
  - app/services/receipts.py
  - app/services/reports.py
  - app/services/returns.py
  - app/services/sales.py
  - app/services/sync.py
  - app/services/sync_client.py
  - app/services/transfers.py
  - app/services/warehouses.py
  - app/services/writeoffs.py
  - app/static/style.css
  - app/templates/mobile_pages/history.html
  - app/templates/mobile_pages/receipts.html
  - app/templates/mobile_pages/sales.html
  - app/templates/mobile_pages/writeoff.html
  - app/templates/mobile_partials/corrections_step_value.html
  - app/templates/mobile_partials/history_cards.html
  - app/templates/mobile_partials/receipts_step_confirm.html
  - app/templates/mobile_partials/return_confirm.html
  - app/templates/mobile_partials/sale_basket.html
  - app/templates/mobile_partials/transfers_step_dest.html
  - app/templates/mobile_partials/writeoff_step_reason.html
  - app/templates/partials/correction_form.html
  - app/templates/partials/customer_insights.html
  - app/templates/partials/deposit_form.html
  - app/templates/partials/history_rows.html
  - app/templates/partials/receipt_form.html
  - app/templates/partials/return_form.html
  - app/templates/partials/sale_form.html
  - app/templates/partials/transfer_form.html
  - app/templates/partials/warehouse_rows.html
  - app/templates/partials/withdraw_form.html
  - app/templates/partials/writeoff_form.html
  - tests/conftest.py
  - tests/test_append_only_cursor.py
  - tests/test_attribution.py
  - tests/test_autosync.py
  - tests/test_business_date.py
  - tests/test_corrections.py
  - tests/test_customers.py
  - tests/test_dashboard.py
  - tests/test_export.py
  - tests/test_finance.py
  - tests/test_finance_reports.py
  - tests/test_history.py
  - tests/test_merge.py
  - tests/test_migrations.py
  - tests/test_mobile_corrections.py
  - tests/test_mobile_history.py
  - tests/test_mobile_receipts.py
  - tests/test_mobile_returns.py
  - tests/test_mobile_sales.py
  - tests/test_mobile_transfers.py
  - tests/test_mobile_writeoff.py
  - tests/test_receipts.py
  - tests/test_reports.py
  - tests/test_returns.py
  - tests/test_sales.py
  - tests/test_sync_client.py
  - tests/test_sync_schema_gate.py
  - tests/test_transfers.py
  - tests/test_warehouses.py
  - tests/test_writeoffs.py
findings:
  critical: 1
  warning: 9
  info: 8
  total: 18
status: issues_found
---

# Phase 33: Code Review Report

**Reviewed:** 2026-09-05
**Depth:** standard
**Status:** issues_found
**Iteration:** 2 (re-review after `33-REVIEW-FIX.md`)

## Summary

### Verification of iteration 1

Seven of the eight fixes claimed in `33-REVIEW-FIX.md` were verified in the current
code and are **not** re-reported:

| Prior | Verified at | Verdict |
|---|---|---|
| CR-01 (wire `business_date`) | `merge.py:92-97,147-166,250-262`; `core.py:96-110` | genuinely fixed for `business_date` |
| WR-02 (`push_schema_ok` TypeError) | `sync.py:282-286`; `merge.py:280-286` | crash fixed; see WR-02 below for what the fix broke |
| WR-03 (409 echo) | `routes/sync.py:61-66,150-160` | fixed (residual nit → IN-07) |
| WR-04 (naive `created_at`) | `operations.py:145-155` | fixed inside `_is_backdated`; see CR-01 below for the layer it did not reach |
| WR-06 (`isascii()`) | `receipts.py:125` | fixed |
| WR-07 (`StopIteration`) | `sales.py:220-229` | fixed in `sales.py`; identical shape still live in `returns.py`/`transfers.py` → WR-05/WR-06 |
| WR-08 (downgrade DDL asserted) | `tests/test_migrations.py:107-128` | fixed |

Still open and re-stated against current line numbers: **WR-01** (skipped, needs an
operator decision) and the behavioural half of the prior **WR-05** (now WR-09), plus
**IN-01..IN-06** which were declared out of scope.

### New this iteration

The central new finding is that the CR-01 remediation was applied one column too
narrowly. The fix hardened `format_ru_date` (`| ru_date`) and added a wire gate for
`business_date`, and the WR-04 fix added a naive/unparseable guard inside
`_is_backdated` — with an in-code comment stating plainly that a merged
`created_at` "is not guaranteed to" be well-formed. But `created_at` itself is still
merged verbatim with no validation, and its display filter `iso_to_local`
(`| local_dt`) still **raises** and still reads a naive value in the **machine's OS
zone**. That filter renders on `/history`, `/m/history`, both CSV dumps and eight
other surfaces, two lines away from the code that was hardened. That is CR-01.

Three further new findings are the same "fixed here, not there" pattern: the date
gate covers `business_date` but not `Batch.expiry` on the same wire (WR-03); the
`StopIteration` fix landed in `sales.py` but the same unguarded dereference is live
in `returns.py` and `transfers.py` (WR-05, WR-06); and the WR-02 fix's two halves
cancel each other so the composed system fails OPEN while the docstring claims
fail-closed (WR-02).

Findings that would contradict an explicit phase decision are **not** raised: the
`created_at`-keeps-display-order rule (D-22), the read-side UTC-prefix fallback vs the
tz-correct backfill (D-24/`business_date_expr`), «Когда» becoming the business date in
CSV (D-23), `stale_products` staying on `created_at` (D-25), and the two-idiom mobile
date placement (D-11) are all correct as decided.

---

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: `| local_dt` still raises on a wire-supplied `created_at`, and reads a naive one in the OS zone — the exact defect the CR-01/WR-04 fixes closed one layer away

**Severity:** BLOCKER

**Files:**
- `app/core.py:113-116` (`iso_to_local` — no `try`, `astimezone()` on a possibly naive value)
- `app/routes/__init__.py:201-203` (the `local_dt` filter registration)
- `app/services/merge.py:90` (`_LEDGER_REQUIRED` — `created_at` checked for `is not None` and nothing else)
- `app/services/merge.py:503-514` (`_ledger_row` copies it verbatim into the bulk INSERT)
- `app/templates/partials/history_rows.html:158`, `:160`, `:283`, `:285`
- `app/templates/mobile_partials/history_cards.html:40`, `:42`
- `app/services/export.py:185`, `:265`
- plus `pages/home.html:61`, `partials/purchase_history.html:22`, `recent_sales.html:26`, `receipt_rows.html:24`, `cash_history_rows.html:45`, `ledger_rows.html:23`, `price_history.html:17`, `mobile_partials/cash_history_cards.html:26`

**Issue:**

The iteration-1 fixes established two rules and then applied each to only one of the
two ledger timestamp columns:

1. `format_ru_date` was made total — *"display code must not blow up on stored data …
   the ledger is append-only: a single unparseable value … would otherwise turn every
   one of those pages into a permanent 500 that the application cannot repair"*
   (`app/core.py:96-103`).
2. `_is_backdated` was given both a naive branch and an unparseable branch
   (`app/services/operations.py:145-155`), with the comment *"a row MERGED from
   another client is not guaranteed to [carry an offset]: `merge._LEDGER_REQUIRED`
   only checks `created_at is not None`"* and *"A timestamp this function cannot parse
   must not 500 /history — the ledger is append-only, so such a row cannot be
   repaired."*

Both statements are true. Neither was applied to `iso_to_local`, which is the filter
that renders **the same column, on the same rows, on the same pages**:

```python
# app/core.py:113-116 — unchanged this phase
def iso_to_local(iso_str: str, tz_name: str) -> str:
    moment = datetime.fromisoformat(iso_str)          # ValueError on junk
    return moment.astimezone(ZoneInfo(tz_name)).strftime("%d.%m.%Y %H:%M")
```

Executed (this machine, `Europe/Moscow` target):

```
iso_to_local("не дата", "Europe/Moscow")            -> ValueError: Invalid isoformat string
iso_to_local("2026-08-31T21:30:00", "Europe/Moscow") -> "31.08.2026 22:30"
```

The second line is the WR-04 bug, unfixed: the correct answer under
`0027._local_business_date`'s own rule (naive is UTC) is `01.09.2026 00:30`. The value
printed is whatever the **server's OS zone** produces — so the muted subline
`задним числом · внесено {{ r.op.created_at | local_dt }}`
(`history_rows.html:158`) can contradict the business date printed directly above it,
and `_is_backdated` and the timestamp beside it can disagree about which day the row
was entered.

The first line is a permanent, unrepairable 500. `created_at` reaches the DB the same
way `business_date` did before the CR-01 gate:

```python
# app/services/merge.py:233-236
if kind in _LEDGER_KINDS:
    for required in _LEDGER_REQUIRED:          # ("device_id","seq","created_at","created_by")
        if data.get(required) is None:         # <- presence only, no shape check
            raise ValueError(...)
```

`_ledger_row` then copies it into `session.execute(insert(model), rows)`. Once
stored, `operations_no_update` / `operations_no_delete` (`app/db.py:48-100`,
`0027:122-167`) make the row unrepairable by the application, and `reverses_op_id`
ships unused until Phase 34. One poisoned row takes down **all** rows on `/history`,
`/m/history`, `/`, the customer purchase-history tab, and both CSV dumps
(`export.py:185`, `:265` — neither has a `try`).

Preconditions are identical to the ones the accepted CR-01 finding rested on: a valid
device token and a push. The same reachability argument that justified fixing
`business_date` applies verbatim here, and is quoted in the code.

There is a second-order consequence worth stating, because it is the one that cannot
be undone. Migration 0027's backfill falls back to `created_at[:10]`
(`0027:307-310`) — so a row that was merged with `created_at = "не дата"` **before**
0027 ran now carries `business_date = "не дата"`, and the new CR-01 parse gate will
reject the entire NDJSON batch containing it with `400 MALFORMED_BATCH_ERROR`
(`routes/sync.py:123-126`) on every future push, forever. Validating `created_at` at
the same boundary closes the intake; it does not repair an already-backfilled row, so
the follow-up revision in IN-03 should cover both columns.

**Fix:** apply the two rules already written down, to the sibling column. Both parts:

```python
# app/core.py — mirror format_ru_date's NEVER-RAISES contract and 0027's naive rule
def iso_to_local(iso_str: str | None, tz_name: str) -> str:
    """Convert a UTC ISO-8601 string to local display time: '08.07.2026 15:00'.

    NEVER RAISES (CR-01, 33-REVIEW iteration 2) — same rule as `format_ru_date`.
    A naive value is read as UTC, never as the machine's OS zone: identical to
    `alembic/versions/0027…::_local_business_date` and
    `operations._is_backdated`, which this filter is rendered beside.
    """
    if not iso_str:
        return ""
    try:
        moment = datetime.fromisoformat(iso_str)
    except (TypeError, ValueError):
        return str(iso_str)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(ZoneInfo(tz_name)).strftime("%d.%m.%Y %H:%M")
```

```python
# app/services/merge.py — beside _DATE_FIELDS; created_at is a TIMESTAMP, not a date,
# so it needs its own check rather than an entry in _DATE_FIELDS.
_TIMESTAMP_FIELDS: frozenset[str] = frozenset({"created_at"})

def _is_iso_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True

# ...inside the `if kind in _LEDGER_KINDS:` block, after the seq check:
for ts_key in _TIMESTAMP_FIELDS & KIND_TO_FIELDS.get(kind, frozenset()):
    if not _is_iso_timestamp(data.get(ts_key)):
        raise ValueError(f"timestamp field {ts_key!r} must be an ISO-8601 string")
```

Regression tests to add beside `tests/test_history.py:743-781` (which already builds
the fixture shape): assert `iso_to_local` returns rather than raises on
`"не дата"`; assert `iso_to_local("2026-08-31T21:30:00", "Europe/Moscow") ==
"01.09.2026 00:30"` (this one is only discriminating off a UTC host — assert the
correct answer either way, as `test_is_backdated_reads_a_naive_created_at_as_utc`
does); and assert `parse_exchange` refuses a ledger record whose `created_at` is
`"не дата"`, `12345`, `None`-adjacent junk or a bare date.

---

## Warnings

### WR-01: `parse_op_date` still bounds the future but not the past (unfixed from iteration 1)

**Severity:** WARNING
**File:** `app/services/ledger.py:62-73`; the 14 date inputs all carry `max=` and none carries `min=` (`partials/receipt_form.html:109-110`, `sale_form.html:106-107`, `writeoff_form.html:96-97`, `correction_form.html:112-113`, `transfer_form.html:82-83`, `return_form.html:62-63`, `withdraw_form.html:86-87`, `deposit_form.html:72-73`, `mobile_pages/{receipts,sales,writeoff}.html`, `mobile_partials/{corrections_step_value,transfers_step_dest,return_confirm}.html`)

**Issue:** unchanged since iteration 1, deliberately skipped there pending an operator
decision. Verified still live:

```python
if parsed.isoformat() > local_today_iso(settings.display_tz):
    errors[key] = OP_DATE_FUTURE_ERROR
    return None
return parsed.isoformat()
```

A mistyped year is accepted: `"0226-09-04" > "2026-09-05"` is `False` because `'0' <
'2'`, so the value is written. The row is then invisible to every period report, and
the append-only triggers plus the absence of сторно (Phase 34) make it uncorrectable.
`date.fromisoformat` requires a 4-digit year, so the reachable range is
`0001-01-01 … today` — roughly 2000 years of accepted garbage.

**Fix:** unchanged from iteration 1 and still blocked on the same two decisions —
(a) what the oldest enterable date is, (b) the third RU error string, which
`33-UI-SPEC.md` § Copywriting Contract does not contain. **Recommended next step:**
put both questions to the operator in one pass, then land floor + string + `min=` as a
single change with the spec updated alongside. Do not ship the `min=` template half
alone: it is a browser hint on a field that is re-validated server-side precisely
because form values are untrusted, and shipping it would make the hole look closed.

### WR-02: the WR-02 fix's two halves cancel — the schema gate fails OPEN while its docstring claims fail-closed

**Severity:** WARNING
**Files:** `app/services/merge.py:280-286`, `app/services/sync.py:282-286`, `app/routes/sync.py:150-160`

**Issue:** the fix landed two changes that are individually sound and jointly
self-defeating.

```python
# merge.py:280-283 — runs FIRST
raw_schema = header.get("schema_version")
... schema_version=raw_schema if isinstance(raw_schema, str) else "", ...
```

```python
# sync.py:282-286 — runs SECOND, on the already-coerced value
if not isinstance(client_schema, str) or not isinstance(server_schema, str):
    return False            # <- unreachable from the only production caller
if not client_schema or not server_schema:
    return True             # <- this is the branch a non-string actually takes
```

`routes/sync.py:151` is the sole production caller of `push_schema_ok`, and it can
only ever be handed `batch.schema_version`, which `parse_exchange` has already
coerced. So the `isinstance` guard is dead code, and a header carrying
`"schema_version": 27` (or a list, or a dict) degrades to `""` → D-03 escape hatch →
**push accepted**. Meanwhile the docstring at `sync.py:273-280` asserts the opposite:

> A non-string version is not «acceptable» — it is refused (False), which is the
> fail-closed direction

That sentence is false for every path that exists. The consequence is small in
practice (our own client always sends a string from `current_schema_version`), but the
gate exists exactly to catch a client whose header is not what we assume, and a
reader — or a Phase 34 author adding a second caller — will trust the docstring.

**Fix:** pick one direction and make the code and the prose agree. The narrow,
behaviour-preserving option is to correct the prose and delete the dead branch:

```python
def push_schema_ok(client_schema: str, server_schema: str) -> bool:
    """...
    WR-02 (33-REVIEW): `parse_exchange` coerces a non-string wire
    `schema_version` to "" at the parse boundary (merge.py:280-283), so an
    UNTYPED version reaches this predicate as "" and is ACCEPTED via the D-03
    escape hatch — exactly like a header that omits the field. That is
    deliberate; this predicate is not the type gate.
    """
    if not client_schema or not server_schema:
        return True
    return client_schema <= server_schema
```

The fail-closed option is to stop coercing in `parse_exchange` and instead
`raise ValueError` on a non-string `schema_version` there, beside the money and date
checks — but that turns a malformed header into `400 MALFORMED_BATCH_ERROR`, so pick
it only if that is wanted. Whichever is chosen, update
`tests/test_sync_schema_gate.py`'s end-to-end assertion (which currently pins 200) and
its docstring so the pin states the composed behaviour, not the predicate's.

### WR-03: the new date gate covers `business_date` only — `Batch.expiry`, the other `String(10)` ISO date on the same wire, is still unvalidated

**Severity:** WARNING
**Files:** `app/services/merge.py:92-97` (`_DATE_FIELDS`), `app/models.py:264-266` (`Batch.expiry`), `app/services/merge.py:356-369` (`_reference_row` copies every mapper column verbatim), `app/templates/pages/reports_expiry.html:29` + `mobile_pages/reports_expiry.html:12`, `app/services/batches.py` (`expiring_batches`)

**Issue:** the CR-01 fix's own comment says:

```python
# app/services/merge.py:92-97
# CR-01 (33-REVIEW): date-typed wire columns. Named EXPLICITLY rather than
# derived from a `_date` suffix — ... Add the next date-only column here when
# one appears.
_DATE_FIELDS: frozenset[str] = frozenset({"business_date"})
```

The next date-only column has already appeared — it shipped in Phase 9.
`Batch.expiry` is `mapped_column(String(10))` holding ISO `yyyy-mm-dd`
(`models.py:264-266`), `batch` is one of the six reference kinds carried over the wire
(`merge.py:302-309`), and `_reference_row` copies every declared column straight from
the payload with no shape check. Consequences of a pushed `"expiry": "не дата"`:

- `expiring_batches` compares `Batch.expiry <= horizon` as a raw string, so the batch
  sorts arbitrarily into or out of the expiry report;
- `reports_expiry.html:29` and its mobile twin compare `row.batch.expiry < today` in
  Jinja, same lexicographic accident;
- `format_ru_date` renders it as-is — which is only *not* a 500 because of the CR-01
  fix, i.e. the second layer is doing the first layer's job for this column.

Batches are reference rows (upsertable, soft-deletable), so this is recoverable and
therefore not a BLOCKER — but the gate is advertised as schema-tracking and it is not.

**Fix:** one line, plus a test:

```python
# app/services/merge.py
_DATE_FIELDS: frozenset[str] = frozenset({"business_date", "expiry"})
```

`_date_fields()` already intersects with `KIND_TO_FIELDS[kind]`, so no other change is
needed. Add a `parse_exchange` refusal test for a `batch` record carrying
`"expiry": "2026/09/04"` alongside the existing `business_date` cases in
`tests/test_business_date.py`.

### WR-04: CSV column 1 can now carry free text and is the one cell in the file not passed through `_csv_safe`

**Severity:** WARNING
**Files:** `app/services/export.py:174`, `:260`; contract stated at `:20-23` and `:51-55`

**Issue:** the module docstring states the invariant:

> T-06-10: `_csv_safe` prefixes any free-text value starting with `=`, `+`, `-`, or
> `@` with a leading apostrophe so Excel never interprets it as a formula on open

Before this phase column 1 was `iso_to_local(...)`, which can only ever produce
`dd.mm.yyyy HH:MM` — genuinely not free text, so leaving it unwrapped was safe. This
phase changed it to `format_ru_date(...)`, and the CR-01 fix then made
`format_ru_date` return `str(iso)` verbatim on anything it does not recognise. Column
1 is therefore now a **pass-through of stored bytes**, and it is unwrapped in both
period-scoped exports:

```python
# app/services/export.py:174 and :260 — no _csv_safe
format_ru_date(op.business_date or op.created_at[:10]),
format_ru_date(movement.business_date or movement.created_at[:10]),
```

A stored `business_date` of `=HYPERLINK("http://x/"&A2,"click")` opens as a live
formula in the operator's spreadsheet. The CR-01 parse gate makes that unreachable
*today* — which is precisely the argument the CR-01 fix rejected when it hardened
`format_ru_date` as a second layer. The same reasoning applies to the second layer
here.

**Fix:** wrap it, exactly like every other free-text cell in the file:

```python
_csv_safe(format_ru_date(op.business_date or op.created_at[:10])),
```

A well-formed date never starts with `=`/`+`/`-`/`@`, so no existing output changes
by a single byte.

### WR-05: `register_return` dereferences `batch` and `warehouse` with no None guard — the precondition WR-07's own fix documented

**Severity:** WARNING
**File:** `app/services/returns.py:175-179`

**Issue:** WR-07 was fixed in `sales.py` with this justification, written into the code
at `sales.py:220-226`:

> The SELECT returns nothing when a picked batch points at a warehouse row that is
> absent, which is reachable on a merged DB: `Batch.warehouse_id`'s FK is ORM-only on
> the merge path and `PRAGMA foreign_keys` is set for SQLite connections only.

The identical dereference is live one module away, unguarded:

```python
# app/services/returns.py:175-179
batch_id = _resolve_or_create_return_batch_id(session, origin)
batch = session.get(Batch, batch_id)              # None if origin.batch_id dangles
warehouse = session.get(Warehouse, batch.warehouse_id)   # AttributeError
... currency=warehouse.currency,                  # AttributeError
```

Both lookups can return `None` under exactly the precondition quoted above.
`AttributeError` is not in the `except (ValueError,)` / `except IntegrityError`
handlers at `:215-222`, so it escapes `register_return`. Both routes wrap the call in
`except Exception` (`routes/returns.py:140`, `routes/mobile_returns.py`), so the user
sees `SAVE_FAILED_ERROR` rather than a 500 — but the operator gets the wrong message
and the server logs a `logger.exception` stack trace for what is a known data shape,
which is the same complaint WR-06 raised about `register_receipt`.

Note also that `warehouse` is resolved **unconditionally**, above the `if debit:`
guard at `:199`, so a return of a zero-price sale fails for a currency it never uses.

**Fix:**

```python
batch = session.get(Batch, batch_id)
warehouse = session.get(Warehouse, batch.warehouse_id) if batch is not None else None
if warehouse is None:
    session.rollback()
    return None, {"form": SAVE_FAILED_ERROR}
```

### WR-06: `register_transfer` dereferences `source_warehouse` with no None guard

**Severity:** WARNING
**File:** `app/services/transfers.py:122-125`

**Issue:** the same shape, same precondition:

```python
dest_warehouse = session.get(Warehouse, dest_warehouse_id)      # safe: checked against active_ids at :115
source_warehouse = session.get(Warehouse, source.warehouse_id)  # NOT checked — may be None
if dest_warehouse.currency != source_warehouse.currency:        # AttributeError
```

`dest_warehouse_id` was verified to be in `active_ids` at `:113-116`, so
`dest_warehouse` is safe. `source.warehouse_id` was never verified against anything —
`source` is resolved by `session.get(Batch, batch_id)` and only its `product_id` is
checked (`:107-109`). Caught by the routes' `except Exception`, so the visible result
is the wrong RU message plus a spurious stack trace, not a 500.

**Fix:**

```python
source_warehouse = session.get(Warehouse, source.warehouse_id)
if source_warehouse is None:
    return None, {"batch": BATCH_REQUIRED_ERROR}
```

### WR-07: `test_revision_ids_are_fixed_width` cannot see the filenames it exists to catch

**Severity:** WARNING
**File:** `tests/test_migrations.py:145-146`

**Issue:** the test's own docstring names the failure it guards:

> the moment one revision is named `9` or `0027a` or `abc123`, the ordering silently
> stops meaning "newer than" … Nothing else in the repo enforces the shape, so this
> regex is the enforcement.

But the collection glob excludes exactly those files:

```python
paths = sorted(_VERSIONS_DIR.glob("[0-9]*.py"))
assert len(paths) >= 26, f"revision glob found only {len(paths)} files"
```

Alembic's default template names a revision file `<rev>_<slug>.py`, so
`alembic revision -m "..."` with an auto-generated hex id produces e.g.
`a1b2c3d4e5f6_add_thing.py` — which `[0-9]*.py` does not match, and which therefore
contributes nothing to `paths`. The `>= 26` floor still passes because the 27 legacy
files are all still there. The one case the test is written for is the one case it
silently skips, and `push_schema_ok`'s lexicographic comparison (`sync.py:266-271`)
rests entirely on it.

**Fix:** glob everything and let the regex do the work:

```python
paths = sorted(p for p in _VERSIONS_DIR.glob("*.py") if p.name != "__init__.py")
assert len(paths) >= 27, f"revision glob found only {len(paths)} files"
```

Every non-conforming filename then reaches the `re.fullmatch(r"\d{4}", ...)` assertion
and reddens, which is the stated intent. (Also prefer `[0-9]{4}` over `\d{4}` — see
IN-07.)

### WR-08: `.filter-bar` has no `flex-wrap` and this phase added a fourth `<select>` to it

**Severity:** WARNING
**Files:** `app/static/style.css:188-193`; `app/templates/partials/history_rows.html:24-82`

**Issue:**

```css
.filter-bar {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  margin-bottom: 24px;
}
```

No `flex-wrap`, so the default `nowrap` applies. D-20 added a fourth control to this
bar («Задним числом», `history_rows.html:71-81`) beside «Тип операции»,
«Сортировать по» («Сначала новые (по умолчанию)» is a wide option) and
«Пользователь». Four `<select>` elements plus 3×16 px gaps will exceed a 1024 px
content column, and with `nowrap` the overflow is clipped or forces a horizontal
scrollbar rather than wrapping — putting the phase's own new filter off-screen. The
sibling `.toolbar` rule at `:72-77` already sets wrapping, so this is an
inconsistency, not a new idiom.

`needs verification`: open `/history` at 1024 px and check for a horizontal scrollbar
or a clipped fourth select. This was flagged as a deferred item in `33-CONTEXT.md`
§ Deferred Ideas and was never checked.

**Fix:** one line, purely additive (no `.filter-bar` currently relies on nowrap):

```css
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-end;
  margin-bottom: 24px;
}
```

### WR-09: «Только в день операции» still under-includes rows in the UTC-straddle window (behavioural half of prior WR-05, unfixed)

**Severity:** WARNING
**Files:** `app/services/operations.py:96-116` (the new «ACCEPTED CONSEQUENCE — BOTH DIRECTIONS» block), `:313-330` (the `same_day` predicate)

**Issue:** iteration 1 closed the *documentation* half of this finding — the docstring
now states both directions accurately and the `history_view` branch points at it. The
*behaviour* is unchanged and is re-reported here so it stays on the ledger rather than
disappearing into a docstring:

```python
dated_where = (
    or_(
        Operation.business_date.is_(None),
        Operation.business_date == entry_day_utc,   # substr(created_at, 1, 10)
    ),
)
```

At `Europe/Moscow` every row entered between 00:00 and 03:00 local has
`business_date = D+1` and `substr(created_at,1,10) = D`, so the equality fails and the
row is **excluded** from «Только в день операции» — even though `_is_backdated`
renders it with no marker, i.e. as an ordinary same-day row. The operator asking
«show me only the ones entered on the day» gets a wrong answer, silently, for a
predictable 3-hour slice of every day's entries.

**Fix:** this is genuinely an operator/spec decision, not a local edit, and the fixer
was right not to pick unilaterally. The two options, unchanged:

- **Relabel** — change the option copy so it reads as an approximation. That is an
  edit to `33-UI-SPEC.md` § Copywriting Contract, which carries an explicit
  «Copy that must NOT be written» clause.
- **Widen the predicate** to also accept the neighbouring UTC day. This breaks the
  `backdated`/`same_day` complementarity (a row could satisfy both) and reddens
  `tests/test_history.py::test_backdated_filter_and_marker_diverge_only_on_utc_straddle`,
  which pins today's behaviour on purpose.

**Recommended next step:** ask the operator which of the two answers they want, in the
same pass as WR-01's floor question (both are copy + spec changes to the same phase's
UI-SPEC). Until then this stays open; do not close it by editing the docstring again.

---

## Info

### IN-01: `local_day_bounds_utc` has no production caller and the docstring does not say so

**File:** `app/core.py:119-135`

The docstring now correctly calls it "the `created_at`-only helper" and contrasts it
with `business_date_bounds`, but it never says the thing a reader needs: every `app/`
reference is a docstring cross-reference (`core.py:124,150,160`,
`export.py:233`), and the only live callers are `tests/test_core.py:108-150`,
`test_export.py:253`, `test_business_date.py:97,112` and `test_dashboard.py:231,235`.
It is retained deliberately (its docstring is load-bearing documentation and tests use
it to build `created_at` fixtures), so this is a note, not a removal request.

**Fix:** one sentence in the docstring — "As of Phase 33 this helper has NO caller
under `app/`; it is kept as fixture-building machinery for `tests/` and as the
documented contrast for `business_date_bounds`."

### IN-02: `POST /m/transfers/step/dest` is unreachable and would drop a typed date if it were wired up

**File:** `app/routes/mobile_transfers.py:184-209`

No template posts to this route — the dest step is entered only via
`GET /m/transfers/step/batch-pick` (`:164-181`) — and its only callers are three
tests. Already recorded in `33-12-SUMMARY.md:59`. It is also the one
`_render_dest_step` caller that does not accept or forward `op_date` (contrast
`:248-262`, `:267-280`, `:283-297`), so wiring it up later would silently reset a
typed back-date to today.

**Fix:** either delete the route, or add `op_date: str = Form("")` and thread it, so
the omission cannot become a bug when someone connects it.

### IN-03: `business_date` (and `created_at`) have no DB-level shape constraint

**Files:** `app/models.py:412` (`created_at`), `:420`, `:587` (`business_date`); `alembic/versions/0027…py:341-347`

`String(10)` / `String(32)` are not enforced by SQLite at all. A
`CHECK (business_date IS NULL OR business_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')`
would be the defence-in-depth backstop behind CR-01's parse gate that survives any
future write path. It cannot be added to 0027 (already applied on s1) and needs its
own revision — which is also the natural home for the `created_at` repair CR-01
identifies (a poisoned pre-0027 row cannot be fixed by intake validation alone).

### IN-04: an invalid `op_date` is echoed back into `<input type="date">`, which blanks it — and the resubmit then silently books today

**Files:** `app/templates/partials/receipt_form.html:110`, `sale_form.html:107`, `correction_form.html:113`, `transfer_form.html:83`, `writeoff_form.html:97`, `withdraw_form.html:87`, `deposit_form.html:73` (all `value="{{ form.op_date or today_iso() }}"`); `return_form.html:63`, `mobile_partials/return_confirm.html:65`, `transfers_step_dest.html:98` (all `value="{{ op_date | default(today_iso(), true) }}"`); `corrections_step_value.html:68`

Unchanged from iteration 1. On the `OP_DATE_FORMAT_ERROR` path the echoed string is by
definition not an ISO date, and a browser silently renders
`<input type="date" value="31.12.2026">` as **empty**. Re-submitting posts `""`, which
`parse_op_date` treats as «today» and writes with no error at all — the error message
and the resulting write disagree. `33-SECURITY.md` R2 already notes the "value is
normalised" claim is false; this is its user-visible consequence.

**Fix:** fall back to today whenever the field itself errored, so the input can never
render blank after a format error:

```jinja
value="{{ today_iso() if errors.op_date else (form.op_date or today_iso()) }}"
```

Apply the same shape to the four flat-`op_date` templates. Note the future-date path is
unaffected (a future date IS valid ISO and re-renders correctly).

### IN-05: unbounded `getattr` dispatch in the Alembic test helper

**File:** `tests/conftest.py:80`

```python
getattr(command, args[0])(config, *args[1:])
```

Will call any attribute of `alembic.command`. Test-only and low risk, but an explicit
allow-list is the same number of lines and fails loudly on a typo instead of raising
`TypeError` deep inside Alembic:

```python
{"upgrade": command.upgrade, "downgrade": command.downgrade}[args[0]](config, *args[1:])
```

### IN-06: four near-identical period resolvers

**Files:** `app/routes/reports.py:39-90`, `app/routes/history.py:24-81`, `app/routes/mobile_history.py:37-65`, plus `_metrics_context` duplicated between `app/routes/finance.py:78-108` and `app/routes/mobile_finance.py`, plus `app/services/dashboard.py:119-123`

The Monday-start-week / calendar-month boundary arithmetic now exists in five places,
each documented as intentional. This phase did not create the duplication, but it had
to touch four of the five to switch to `business_date_bounds` — which is exactly the
maintenance cost the duplication imposes. Worth scheduling a shared `period.py` helper
before the next phase touches period logic.

### IN-07: `_REVISION_ID_RE` uses `\d`, which matches non-ASCII digits, so the 409 detail can still echo attacker-chosen characters

**File:** `app/routes/sync.py:65`; same pattern at `tests/test_migrations.py:153,163`

```python
_REVISION_ID_RE = re.compile(r"\d{4}")
```

Python's `\d` is Unicode-aware by default, so `"١٢٣٤"` (Arabic-Indic) and `"١٢٣٤"`-class
strings `fullmatch`. The WR-03 fix's comment says the value is shown "only when it has
the exact shape of an Alembic revision id", and Alembic revision ids are ASCII. The
practical impact is tiny — `fullmatch` bounds the echo to exactly 4 characters, so
there is no amplification — but it is still an untrusted echo the comment says does
not happen.

**Fix:** `re.compile(r"[0-9]{4}")` in both files.

### IN-08: `reverses_*_id` carry an ORM `ForeignKey` that migration 0027 does not create, so test fixtures enforce a constraint production does not have

**Files:** `app/models.py:398-401`, `:562-567`; `alembic/versions/0027…py:47-51`, `:343`, `:346`

0027 adds both reversal-link columns as bare native columns and states the intent
explicitly:

> the bare native column means a reversal whose target has not arrived yet renders as a
> dangling link instead of rolling back an entire push

That is true on an Alembic-built database (production, s1). It is **false** on every
test fixture: `tests/conftest.py:30` builds schema with `Base.metadata.create_all`,
which emits the `REFERENCES operations(id)` clause from the ORM `ForeignKey`, and
`app/db.py:128` sets `PRAGMA foreign_keys=ON`. So a Phase-34 test that pushes a
reversal whose target has not arrived will raise `IntegrityError` in the suite while
succeeding in production — the opposite of the documented contract, and in the
direction that produces a false red rather than a false green (which is the better
direction, but still a divergence worth knowing before Phase 34 writes these columns).

This follows the pre-existing `sale_id`/`batch_id`/`author_id` precedent and is not a
defect this phase introduced; it is recorded so Phase 34 does not debug it from
scratch. Either drop the ORM `ForeignKey` on the two reversal columns (losing merge
insert-ordering) or add the FK in the follow-up revision — but pick one before
building a test around the dangling-link behaviour.

---

## Coverage notes (what was read deeply vs. lightly)

**Read in full and traced this iteration:** `app/core.py`, `app/db.py`,
`app/models.py` (the four new columns + `Batch.expiry`), `app/routes/__init__.py`,
`app/services/merge.py` (again — CR-01/WR-02/WR-03 all live there),
`app/services/sync.py`, `app/routes/sync.py`, `app/services/ledger.py`,
`operations.py`, `reports.py`, `export.py`, `finance.py`, `finance_reports.py`,
`receipts.py`, `sales.py`, `returns.py`, `transfers.py`, `writeoffs.py`,
`corrections.py`, `app/routes/history.py`, `mobile_history.py`, `returns.py`,
`transfers.py`, `mobile_transfers.py`, the full 0027 migration,
`tests/test_migrations.py`, `tests/conftest.py:1-120`, and the fixed regions of
`tests/test_history.py`.

**Read at the relevant hunks only:** `app/services/customers.py`
(`_spend_stmt`/`last_order_date`), `warehouses.py` (`last_receipt`), `dashboard.py`
(`period_metrics`), `sync_client.py` (`format_sync_message`, the 409 branch),
`app/main.py` (`_auto_sync_iteration` backoff), `app/routes/finance.py` (report + CSV
routes), `app/routes/sales.py` (POST path), and every `op_date` occurrence across
`app/routes/` and `app/templates/` via targeted grep.

**Scanned, not line-by-line audited:** the remaining `tests/*` files. WR-07 is the
only finding resting on test code, and it was read in full.

**Executed:** one thing only — `iso_to_local` was run against `"не дата"` and against a
naive timestamp to prove CR-01 rather than assert it. Output is quoted verbatim in
that finding. The suite was **NOT** run (`не запускал`). To confirm CR-01 end-to-end:
insert an `Operation` with `created_at="не дата"` via a merge-shaped bulk insert (the
fixture shape already exists at `tests/test_business_date.py:601-628`) and request
`/history` and `/export/sales.csv`.

---

_Reviewed: 2026-09-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Iteration: 2_
