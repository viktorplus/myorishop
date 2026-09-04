---
phase: 33-back-dated-operations
reviewed: 2026-09-04T12:00:00Z
depth: standard
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
  warning: 8
  info: 6
  total: 15
status: issues_found
---

# Phase 33: Code Review Report

**Reviewed:** 2026-09-04T12:00:00Z
**Depth:** standard
**Files Reviewed:** 96
**Status:** issues_found

## Summary

Phase 33 adds an operator-supplied business date to both append-only ledgers
(`operations`, `cash_movements`), a tz-correct backfill migration (0027), a
dual-dialect trigger rewrite, one shared write-side validator (`parse_op_date`),
one shared read-side expression (`business_date_expr`), and it switches the whole
period-scoped read family (reports, finance, dashboard, history, exports,
customer/warehouse aggregates) from `created_at` timestamps to date-only closed
bounds.

The write side and the migration are the strongest parts of the change. The
single-write-path invariant holds: all fourteen surfaces route through
`parse_op_date` → `record_operation` / `record_cash_movement`, and the two
multi-row writers (`sales.register_sale`, `returns.register_return`,
`transfers.register_transfer`, `receipts.register_receipt`) each resolve the
today-fallback exactly once and thread one string into every row they write, so
goods and money cannot land on different days. Migration 0027 orders
add-column → backfill → trigger-rewrite correctly, uses bound parameters only,
imports no app code, and its downgrade restores the guards before dropping the
columns. The read side is consistent: `local_day_bounds_utc` has no remaining
production caller, and every switched predicate uses the CLOSED `>=`/`<=` form.

The central defect is on the boundary the phase's own threat register never
looked at. `business_date` was added to two tables that the sync merge engine
inserts into **verbatim from the wire**, and it is rendered by `format_ru_date`,
which raises on anything that is not an ISO date. Nothing between the network
and that filter validates the value, and the append-only triggers make a poisoned
row impossible for the application to repair. `T-33-19` only proves the string
`business_date` does not *appear* in the three sync modules — which is exactly
why nobody checked what the sync path *carries*.

Secondary themes: `parse_op_date` bounds the future but not the past;
`push_schema_ok` (new this phase) crashes on a non-string header field and
reflects that field back to the caller; and the `dated` filter's documented
UTC-vs-local trade-off is only reasoned through in one of its two directions.

## Critical Issues

### CR-01: `business_date` is inserted verbatim from the sync wire and rendered by a raising filter, on a table that can never be repaired

**Severity:** BLOCKER
**Files:**
- `app/models.py:420` and `app/models.py:587` (the two new columns — nullable `String(10)`, no CHECK)
- `app/services/merge.py:451-462` (`_ledger_row` — `{column: data.get(column) for column in KIND_TO_FIELDS[kind]}`)
- `app/services/merge.py:203-222` (`parse_exchange` validates `id`, `seq` and every `*_cents` field — and nothing else)
- `app/core.py:89-99` (`format_ru_date`, the `| ru_date` filter, raises `ValueError`)
- `app/services/operations.py:107-115`, `app/templates/partials/history_rows.html:157`, `:282`, `app/templates/mobile_partials/history_cards.html:40`
- `app/services/export.py:174`, `:260`
- `app/services/warehouses.py:117-118` + `app/templates/partials/warehouse_rows.html:83`
- `app/services/customers.py:565-569` + `app/templates/partials/customer_insights.html`
- `app/routes/returns.py:66` + `app/templates/partials/return_form.html`

**Issue:**
`parse_exchange` type-checks money fields (`isinstance(value, int)`, bool excluded)
and `seq`, precisely because SQLite's dynamic typing would otherwise store a string
in an `Integer` column. The two `business_date` columns added by this phase get no
such check. `_ledger_row` copies every key the model declares straight into
`session.execute(insert(model), rows)`, so a pushed record carrying
`"business_date": "не дата"` (or `"2026/09/04"`, or `12345`, or a 4 KB string) is
stored as-is.

The read path then hits it:

```python
# app/services/operations.py:107-115
if op.business_date is None:
    return False
local_day = datetime.fromisoformat(op.created_at).astimezone(tz).date().isoformat()
return op.business_date != local_day        # "не дата" != "2026-09-04" -> True
```

`is_backdated=True` routes the row into the branch that renders
`{{ r.business_day | ru_date }}` → `date.fromisoformat("не дата")` → `ValueError`
→ HTTP 500. The same value also reaches `format_ru_date` unguarded in both CSV
exports (`export.py:174`, `:260`), in the warehouse list (`MAX()` over ISO strings
happily returns `"не дата"`, which sorts above every real date), in the customer
detail tile (`last_order_date` is a `MAX()` over the same expression), and in the
return form's origin line.

Two properties turn a bad row into a permanent outage rather than a bad cell:

1. `operations_no_update` / `operations_no_delete` (`app/db.py:48-100`,
   `alembic/versions/0027…py:122-167`) mean the application cannot UPDATE or
   DELETE the row. There is no сторно path either — `reverses_op_id` ships unused
   until Phase 34. Repair requires dropping the trigger by hand in `sqlite3`/`psql`.
2. `/history`, `/m/history`, `/warehouses`, the customer detail page and both CSV
   dumps break for **all** rows, not just the poisoned one.

Preconditions: a valid device token (`require_device`) and a push. That is not an
anonymous-internet vulnerability, but it is exactly the fleet-of-clients scenario
this column was designed for — and it does not require malice: a client whose
`display_tz` or clock produces an unexpected string, a hand-built offline bundle,
or a future format change all reach the same place. `sales.csv`/`cash_movements.csv`
have no `try` at all; `/history` has none either.

**Fix:** validate at the parse boundary (where the money check already lives) and
harden the display filter. Both, not one:

```python
# app/services/merge.py — beside the _money_fields loop in parse_exchange
_DATE_FIELDS: frozenset[str] = frozenset({"business_date"})

for date_key in _DATE_FIELDS & KIND_TO_FIELDS.get(kind, frozenset()):
    value = data.get(date_key)
    if value is None:
        continue
    if not isinstance(value, str):
        raise ValueError(f"date field {date_key!r} must be an ISO yyyy-mm-dd string")
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"date field {date_key!r} must be an ISO yyyy-mm-dd string") from exc
```

```python
# app/core.py::format_ru_date — display code must not 500 on stored data
def format_ru_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return date.fromisoformat(iso).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return str(iso)          # render it, never crash the page
```

Add a regression test alongside `tests/test_business_date.py:601-628` (which
already inserts a merge-shaped row bypassing `record_operation`): push
`business_date="не дата"` through `parse_exchange` and assert it is refused, and
assert `format_ru_date` on a junk value returns rather than raises.

## Warnings

### WR-01: `parse_op_date` bounds the future but not the past

**File:** `app/services/ledger.py:62-73`; forms at
`app/templates/partials/receipt_form.html:110`, `correction_form.html:113`,
`sale_form.html:107`, `transfer_form.html:83`, `writeoff_form.html:97`,
`withdraw_form.html:87`, `deposit_form.html:73`,
`mobile_partials/transfers_step_dest.html:99`, `mobile_pages/*.html`

**Issue:** the validator refuses `> today` and accepts everything else, and every
`<input type="date">` carries `max=` but no `min=`. A single mis-typed year
(`0226-09-04`, trivially produced by typing into the year segment of a native date
picker) is accepted, written, and then invisible to every period report — while the
ledger's append-only triggers make it uncorrectable until Phase 34 ships сторно.
The docstring reasons at length about the upper boundary and never mentions the
lower one.

**Fix:** add a floor to the single validator and a matching `min=` to the inputs:

```python
# app/services/ledger.py
OP_DATE_TOO_OLD_ERROR = "Дата операции слишком давняя."
_OP_DATE_FLOOR_DAYS = 3650          # ~10 years; pick with the operator

...
if parsed.isoformat() > local_today_iso(settings.display_tz):
    errors[key] = OP_DATE_FUTURE_ERROR
    return None
if (date.fromisoformat(local_today_iso(settings.display_tz)) - parsed).days > _OP_DATE_FLOOR_DAYS:
    errors[key] = OP_DATE_TOO_OLD_ERROR
    return None
```

### WR-02: `push_schema_ok` raises `TypeError` (raw 500) on a non-string `schema_version`

**Files:** `app/services/sync.py:273-275`, `app/routes/sync.py:136-143`,
`app/services/merge.py:231`

**Issue:** `parse_exchange` stores `header.get("schema_version") or ""` with no type
check, so a pushed header `{"kind":"header","format_version":1,"schema_version":5}`
yields an `int`. `push_schema_ok` then evaluates `5 <= "0027"` →
`TypeError: '<=' not supported between instances of 'int' and 'str'`, which nothing
catches: the route's `try` blocks cover only `parse_exchange` (step 4). The result
is an unhandled 500 from a route whose whole design note is "never echo, never
crash". A JSON list or dict produces the same crash.

**Fix:** coerce/validate at the parse boundary and make the predicate total:

```python
# app/services/merge.py:231
raw_schema = header.get("schema_version")
schema_version = raw_schema if isinstance(raw_schema, str) else ""
```

```python
# app/services/sync.py::push_schema_ok
if not isinstance(client_schema, str) or not isinstance(server_schema, str):
    return False            # an untyped/absent version is not "acceptable"
if not client_schema or not server_schema:
    return True
return client_schema <= server_schema
```

### WR-03: the 409 schema-gate detail reflects client-controlled bytes, contradicting its own comment

**File:** `app/routes/sync.py:134-143` (comment at `:134-135`, format at `:140-142`)

**Issue:** the in-code claim is "only the two Alembic revision ids are interpolated
into the detail — never submitted bytes". `batch.schema_version` **is** submitted
bytes: it comes straight from the pushed NDJSON header, unvalidated (WR-02), and
unbounded in length within the 32 MB body cap. The response is JSON so this is not
XSS, but it is an untrusted-echo policy violation and a response-amplification
vector, and — worse — the comment will stop the next reader from checking.

**Fix:** echo only the server's own revision, or truncate and character-class the
client half:

```python
client_shown = batch.schema_version if re.fullmatch(r"\d{4}", batch.schema_version or "") else "?"
raise HTTPException(
    status_code=409,
    detail=SCHEMA_AHEAD_ERROR.format(client=client_shown, server=server_schema),
)
```
Update the comment to say what the code actually does.

### WR-04: `_is_backdated` reads a naive `created_at` as server-local time, not UTC

**File:** `app/services/operations.py:114`

**Issue:**

```python
local_day = datetime.fromisoformat(op.created_at).astimezone(tz).date().isoformat()
```

`astimezone()` on a **naive** datetime interprets it in the *machine's* local zone.
Locally written rows always carry an offset (`utcnow_iso`), but a row merged from
another client is not guaranteed to (`_LEDGER_REQUIRED` only checks `created_at is
not None`). Migration 0027 hit the same input and handled it explicitly:

```python
# alembic/versions/0027…py:311-314
if moment.tzinfo is None:
    moment = moment.replace(tzinfo=UTC)
```

The two rules must agree — the backfill's whole correctness argument is that
`business_date == local_day(created_at)` for every historical row. As written, on a
server whose OS zone is not `display_tz`, a naive `created_at` produces a wrong
`local_day` and therefore a spurious (or missing) «задним числом» marker.

**Fix:** apply the migration's own rule:

```python
moment = datetime.fromisoformat(op.created_at)
if moment.tzinfo is None:
    moment = moment.replace(tzinfo=UTC)
local_day = moment.astimezone(tz).date().isoformat()
```

### WR-05: «Только в день операции» silently omits normal rows entered in the UTC-straddle window

**File:** `app/services/operations.py:265-285` (with the trade-off note at `:73-105`)

**Issue:** the docstring states the accepted cost in one direction only —
«Только задним числом» may return an unmarked row, "the converse never happens, so
no marked row is ever lost". The *other* filter has the mirror-image defect and it
is not stated: a row entered at 00:30 Europe/Moscow has
`business_date = 2026-09-05` and `substr(created_at,1,10) = 2026-09-04`, so

```python
Operation.business_date == entry_day_utc   # "2026-09-05" == "2026-09-04" -> False
```

excludes it from «Только в день операции» even though the UI renders it with **no**
marker, i.e. as an ordinary same-day row. At `Europe/Moscow` that is every row
entered between 00:00 and 03:00 local — a genuinely wrong answer to the operator's
question, not a cosmetic mismatch, and `tests/test_history.py::
test_backdated_filter_and_marker_diverge_only_on_utc_straddle` pins the behaviour
without contradicting the claim, because the claim only covers one side.

**Fix:** either state it (update the docstring and the UI copy so
«Только в день операции» reads as an approximation), or make the predicate exact by
comparing against a stored marker rather than a UTC-derived one. A minimal honest
fix is to widen `same_day` to also accept the neighbouring UTC day:

```python
dated_where = (
    or_(
        Operation.business_date.is_(None),
        Operation.business_date == entry_day_utc,
        # the local day may legitimately be entry_day_utc + 1 east of Greenwich
        Operation.business_date == func.substr(Operation.created_at, 1, 10),
    ),
)
```
— but note this changes the `backdated`/`same_day` complementarity, so pick the
approach with the operator and pin whichever is chosen.

### WR-06: `register_receipt`'s quantity guard is missing the `isascii()` check its four siblings have

**File:** `app/services/receipts.py:119`

**Issue:**

```python
qty = int(qty_text) if qty_text.isdigit() else 0
```

`"²".isdigit()` is `True` and `int("²")` raises `ValueError`. Every sibling service
was hardened for exactly this and says so in a comment —
`writeoffs.py:71`, `transfers.py:84`, `sales.py:148`, `returns.py:144` all read
`qty_text.isascii() and qty_text.isdigit()`. Receipts was left behind. Both receipt
routes wrap the call in `except Exception` (`routes/receipts.py:247`,
`mobile_receipts.py:276`), so the user-visible result is not a 500 — it is the wrong
message («Не удалось сохранить. Попробуйте ещё раз.» instead of the precise quantity
error) plus a spurious `logger.exception` stack trace for what is ordinary bad input.
This phase edited this function; the inconsistency is now the odd one out of five.

**Fix:**

```python
qty = int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0
```

### WR-07: `register_sale` can raise `StopIteration` on an unresolvable warehouse

**File:** `app/services/sales.py:215-220`

**Issue:**

```python
warehouse_ids = {line["batch"].warehouse_id for line in resolved}
warehouses = session.scalars(select(Warehouse).where(Warehouse.id.in_(warehouse_ids))).all()
basket_currencies = {warehouse.currency for warehouse in warehouses}
if len(basket_currencies) > 1:
    return None, {"basket": MIXED_CURRENCY_ERROR}
basket_currency = next(iter(basket_currencies))
```

`len(...) > 1` catches the mixed case but not the empty one. If the `SELECT` returns
nothing (a batch pointing at a warehouse row that is absent — possible on a merged
DB, since `Batch.warehouse_id`'s FK is ORM-only on the merge path and `PRAGMA
foreign_keys` is only set for SQLite connections), `next(iter(set()))` raises
`StopIteration` outside every `try` in this function. The desktop sale route has no
blanket `except Exception`, so this is a raw 500 mid-checkout.

**Fix:**

```python
if len(basket_currencies) > 1:
    return None, {"basket": MIXED_CURRENCY_ERROR}
if not basket_currencies:
    return None, {"basket": SAVE_ROLLBACK}
basket_currency = next(iter(basket_currencies))
```

### WR-08: the downgrade trigger DDL is asserted against nothing

**Files:** `tests/test_migrations.py:72-95`;
`alembic/versions/0027…py:213-289` (`_SQLITE_DOWNGRADE_DDL` / `_PG_DOWNGRADE_DDL`)

**Issue:** `test_alembic_head_triggers_match_app_db` compares the live triggers to
`APPEND_ONLY_TRIGGERS` **as a whole name → DDL map**, and its docstring explains
that comparing names alone would miss "a trigger present under the right name but
guarding the wrong column list". Its sibling then does exactly that:

```python
assert set(_live_triggers(alembic_engine)) == set(_TRIGGER_NAMES)   # names only
```

and it asserts *after* re-upgrading to head, so the state it inspects is produced by
`_SQLITE_DDL`, not by `_SQLITE_DOWNGRADE_DDL`. Consequence: the ~80 lines of
hand-copied downgrade DDL — the half that has to reproduce 0018's and 0026's exact
`WHEN` enumerations — are covered by no assertion at all. A typo there (a dropped
`OR NEW.currency`, say) leaves a downgraded DB with a silently weaker cash guard and
every test stays green. That is the same class of drift migration 0026 exists to fix.

**Fix:** snapshot the map at the downgraded revision, before re-upgrading:

```python
run_alembic(url, "downgrade", "-1")
downgraded = _live_triggers(alembic_engine)
assert set(downgraded) == set(_TRIGGER_NAMES)
assert "business_date" not in downgraded["operations_no_update"]
assert "NEW.currency" in downgraded["cash_movements_no_update"]   # 0026's guard survives
run_alembic(url, "upgrade", "head")
assert _live_triggers(alembic_engine) == {
    re.search(r"CREATE TRIGGER (\w+)", t).group(1): _normalise(t) for t in APPEND_ONLY_TRIGGERS
}
```

## Info

### IN-01: `local_day_bounds_utc` has no production caller left

**File:** `app/core.py:108-131`

Every `app/` reference is now a docstring cross-reference (`app/core.py:139,149`,
`app/services/export.py:233`); the only live callers are `tests/test_export.py:27,253`
and `tests/test_business_date.py:96,111`. It is retained deliberately (its docstring
is load-bearing documentation for the `business_date_bounds` contrast, and tests
build `created_at` fixtures with it), so this is a note, not a removal request —
but a reader will assume it is on a live path. Add one line to the docstring saying
it is now fixture/documentation-only.

### IN-02: `POST /m/transfers/step/dest` is unreachable

**File:** `app/routes/mobile_transfers.py:184-209`

No template posts to it (the dest step is entered only via
`GET /m/transfers/step/batch-pick`); the only callers are three tests. Already
recorded in `33-12-SUMMARY.md:59`. It is also the one `_render_dest_step` caller that
does not accept `op_date`, so if it were ever wired up it would silently reset a
typed back-date to today.

### IN-03: `business_date` has no DB-level format constraint

**Files:** `app/models.py:420`, `:587`;
`alembic/versions/0027…py:342-347`

`String(10)` is not enforced by SQLite at all, and a `CHECK (business_date IS NULL OR
business_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')` would be the
defence-in-depth backstop for CR-01 that survives any future write path. Worth
considering for the follow-up revision (it cannot be added to 0027 retroactively).

### IN-04: an invalid `op_date` is echoed back into `<input type="date">`, which blanks it

**Files:** `app/templates/partials/receipt_form.html:110`, `correction_form.html:113`,
`sale_form.html:107`, `transfer_form.html:83`, `writeoff_form.html:97`,
`withdraw_form.html:87`, `deposit_form.html:73`

`value="{{ form.op_date or today_iso() }}"` echoes the raw submitted string. On the
`OP_DATE_FORMAT_ERROR` path that string is by definition not an ISO date, and a
browser silently renders `<input type="date" value="31.12.2026">` as empty — so
re-submitting posts `""`, which means «today» and writes a row with no error at all.
The error message and the resulting write disagree. `33-SECURITY.md` R2 already notes
the "value is normalised" claim is false; this is its user-visible consequence.
Echo the value only when `parse_op_date` accepted it, or fall back to `today_iso()`
whenever `errors.op_date` is set.

### IN-05: unbounded `getattr` dispatch in the Alembic test helper

**File:** `tests/conftest.py:80`

`getattr(command, args[0])(config, *args[1:])` will call any attribute of
`alembic.command`. Test-only and low risk, but an explicit allow-list
(`{"upgrade": command.upgrade, "downgrade": command.downgrade}[args[0]]`) is the same
number of lines and fails loudly on a typo instead of raising `TypeError` deep inside
Alembic.

### IN-06: four near-identical period resolvers

**Files:** `app/routes/reports.py:39-90`, `app/routes/history.py:24-81`,
`app/routes/mobile_history.py:37-65`, plus `_metrics_context` duplicated between
`app/routes/finance.py:78-108` and `app/routes/mobile_finance.py`

The Monday-start-week / calendar-month boundary arithmetic now exists in five places
(including `app/services/dashboard.py:119-123`, which replicates it deliberately and
says so). Each copy is documented as intentional, and this phase did not create the
duplication — but it did have to touch four of the five to switch to
`business_date_bounds`, which is precisely the maintenance cost the duplication
imposes. Worth scheduling a shared `period.py` helper before the next phase touches
period logic.

---

## Coverage notes (what was read deeply vs. lightly)

**Read in full and traced:** `app/services/ledger.py`, `corrections.py`,
`operations.py`, `reports.py`, `finance_reports.py`, `finance.py`, `export.py`,
`sales.py`, `returns.py`, `receipts.py`, `writeoffs.py`, `transfers.py`,
`dashboard.py`, `sync.py`, `sync_client.py` (targeted), `app/core.py`,
`app/models.py`, `app/db.py`, `app/routes/__init__.py`, `sync.py`, `history.py`,
`mobile_history.py`, `reports.py`, `finance.py` (+ mobile twin, targeted),
`returns.py`, `corrections.py` (POST path), `receipts.py` / `mobile_receipts.py`
(POST path), `mobile_transfers.py`, and the full 0027 migration.
`app/services/merge.py` was read despite being outside the supplied file list,
because CR-01 could not be proven without it.

**Read at the relevant hunks only:** `app/services/customers.py` (the `_spend_stmt`
/ `last_order_date` block), `app/services/warehouses.py` (the `last_receipt`
aggregate), `app/main.py` (the auto-sync backoff), `app/static/style.css` (the single
`.field.op-date` rule), and the mobile route files that only thread `op_date` through
to an already-reviewed service (`mobile_sales.py`, `mobile_writeoff.py`,
`mobile_corrections.py`, `mobile_returns.py`, `mobile_finance.py`).

**Deprioritised (scanned, not line-by-line audited):** all 30 `tests/*` files except
`test_migrations.py`, `test_append_only_cursor.py`, `tests/conftest.py` and the first
200 lines of `test_business_date.py`, which were read in full because WR-08 and the
CR-01 gap are about what the suite does and does not assert. The remaining test files
were sampled via grep for the assertions the SUMMARY artifacts cite; no finding below
BLOCKER rests on them. `app/routes/customers.py` and `app/templates/mobile_pages/
history.html`, `writeoff.html`, `mobile_partials/writeoff_step_reason.html`,
`return_confirm.html`, `corrections_step_value.html`, `customer_insights.html`,
`deposit_form.html`, `withdraw_form.html` were checked only for the `op_date` /
`| ru_date` render shape (via grep + the two representative full reads of
`history_rows.html` and `sale_basket.html`), not audited as whole files.

**Not verified by execution:** nothing in this review was run. The suite was not
executed (`не запускал`); to confirm CR-01 the reproducer is
`uv run pytest tests/test_merge.py -q` after adding a record with
`"business_date": "не дата"` and then rendering `/history`.

---

_Reviewed: 2026-09-04T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
