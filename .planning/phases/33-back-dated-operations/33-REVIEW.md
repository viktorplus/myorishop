---
phase: 33-back-dated-operations
reviewed: 2026-09-05T00:00:00Z
depth: standard
iteration: 3
files_reviewed: 98
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
  warning: 7
  info: 5
  total: 13
status: issues_found
---

# Phase 33: Code Review Report

**Reviewed:** 2026-09-05
**Depth:** standard (static read of every listed file; no commands executed — see Process notes)
**Files Reviewed:** 98
**Status:** issues_found
**Iteration:** 3 (prior fixes recorded in `33-REVIEW-FIX.md` were verified against current source and are NOT re-reported)

## Summary

Phase 33 threads an operator-supplied business date through 14 write surfaces, adds
`operations.business_date` / `cash_movements.business_date` plus two unused reversal
columns (migration `0027`), and switches every period-scoped reader from `created_at`
to `business_date_expr(...)`. The write path is genuinely tight: **every** call site
that reaches `record_operation(business_date=…)` or
`record_cash_movement(business_date=…)` goes through `ledger.parse_op_date`, and
`merge.parse_exchange` gates the wire with `_is_iso_date` / `_is_iso_timestamp`.
I could find no unvalidated path into either column. The predicate/bounds pairing
(`business_date_expr` + `business_date_bounds`, closed range) is consistently applied
in `history_view`, `sales_profit_report`, `writeoff_report`, `top_selling_products`,
`cash_expense_total`, `cash_flow_report`, `customers._spend_stmt`,
`warehouses.list_view` and both CSV exports, and both halves of each paginated query
(`stmt` + `count_stmt`) move together.

**Verified as actually fixed** (spot-checked against source, not against the fix report):
`core.iso_to_local` / `core.format_ru_date` no longer raise and read naive values as
UTC (`app/core.py:144-173`); `core.date_input_value` + the `op_date_value` Jinja
global are wired into all 11 echoing templates; `push_schema_ok` is total;
`_REVISION_ID_RE` uses `[0-9]{4}`; `returns.register_return` and
`transfers.register_transfer` guard the warehouse lookups; `tests/conftest.py`'s
Alembic dispatch is allow-listed; `tests/test_migrations.py` globs `*.py` and asserts
the downgraded trigger state.

What the phase did **not** finish is coverage symmetry. Three defects share one shape:
a date the operator can now enter is written, but a reader that should honour it does
not (cash history), a reader that should follow the phase's own naive/malformed rule
does not (`stale_products`), or a navigation path silently replaces it with today
(the two mobile wizards whose date lives on the final step). Separately, the single
highest-risk item — `parse_op_date` bounding the future but not the past — has now
been deferred twice and remains the only defect in this phase that writes permanently
uncorrectable data into an append-only ledger; it is escalated to Critical here with a
fix that requires no operator decision.

## Critical Issues

### CR-01: `parse_op_date` bounds the future but not the past — a year typo writes an unrecoverable ledger row

**Severity:** BLOCKER
**File:** `app/services/ledger.py:62-73` (check at `:70`); no `min=` on any of the 14 date inputs
**Status:** carried from iterations 1 and 2, deferred both times pending an operator decision. Escalated because the consequence is permanent data corruption, not a UX rough edge.

**Issue:** the only bound is
```python
if parsed.isoformat() > local_today_iso(settings.display_tz):
```
`"0226-09-04" > "2026-09-05"` is `False`, so a mistyped year is **accepted**. The row
is then written to an append-only table guarded by `operations_no_update` /
`cash_movements_no_update` (`app/db.py:48-100`), so the application can never repair
it — and сторно does not exist until Phase 34. The row simultaneously:

* vanishes from every period report (`business_date_expr(...) >= start` fails for all
  realistic bounds — `sales_profit_report`, `writeoff_report`, `cash_expense_total`,
  `cash_flow_report`, `customers._spend_stmt`, the dashboard tiles);
* corrupts `warehouses.list_view`'s `MAX(business_date_expr(Operation))` («Последняя
  приёмка») and `customers.last_order_date`'s `MAX(...)` only in the *other* direction
  — those take a MAX, so a `0226` row is invisible there while a mistyped **future**-
  looking-but-past value is not;
* still counts in `Product.quantity` / `Batch.quantity`, so stock and reports disagree
  with no visible cue.

Three of the 14 surfaces (the mobile приход / продажа / списание shells) document that
`max=` is **inert** on them — `hx-post` sits on the button and htmx `preventDefault()`s
the click — so on those surfaces the server-side check is the *only* guard, in both
directions.

**Why the previous "needs an operator decision" reasoning does not cover this case:**
the deferral was about picking a *business* floor (how far back may the operator
book?). The year-typo class needs no business decision at all — any floor before the
business existed catches it and can never refuse a legitimate entry.

**Fix:** land a decision-free sanity floor now, and leave the business floor as a
separate later change.

```python
# app/services/ledger.py
# A sanity floor, NOT a business policy: no MyOriShop data predates 2000, so this
# can never refuse a legitimate entry, while it catches every year typo
# ("0226-09-04", "0026-09-04") that lexicographic `>` lets through. The business
# floor ("how far back may the operator book?") is a separate, later decision.
OP_DATE_FLOOR = date(2000, 1, 1)
OP_DATE_TOO_OLD_ERROR = "Дата операции слишком старая — проверьте год."

    if parsed < OP_DATE_FLOOR:
        errors[key] = OP_DATE_TOO_OLD_ERROR
        return None
    if parsed.isoformat() > local_today_iso(settings.display_tz):
        errors[key] = OP_DATE_FUTURE_ERROR
        return None
```
and add `min="2000-01-01"` beside the existing `max="{{ today_iso() }}"` on the 11
echoing templates (it is a browser hint only — the server check above is the guard).
Note the third RU string is unavoidable and `33-UI-SPEC.md` § Copywriting Contract
must be updated in the same commit.

## Warnings

### WR-01: cash-movement history renders `created_at` only — a back-dated movement is invisible where the operator looks for it

**Severity:** WARNING
**Files:** `app/templates/partials/cash_history_rows.html:45`,
`app/templates/mobile_partials/cash_history_cards.html:26` (neither touched by this
phase) against `app/services/finance.py:112` (writes `business_date`),
`app/services/finance_reports.py:40-42,138-140` (reports bucket by it),
`app/services/export.py:253-276` (CSV column 1 is the business date)

**Issue:** the phase added «Дата операции» to `withdraw_form.html` and
`deposit_form.html`, made `cash_expense_total` / `cash_flow_report` /
`stream_cash_movements_csv` bucket by `business_date`, and gave `/history` both a
business-date primary column and a «Задним числом» filter. The cash ledger's own two
list surfaces got none of that. Executed consequence: the operator books a withdrawal
today with `op_date = 2026-08-15`; `/finance`'s list shows **05.09.2026**, the tiles
and `/finance/report` count it in **August**, and there is no marker and no filter
that can find it. The list and the report on the same page disagree, silently — the
exact failure the desktop `/history` «Когда» cell (`history_rows.html:155-162`) was
designed to prevent.

**Fix:** mirror the shipped `/history` shape in both cash templates — primary
`business_date | ru_date`, muted second line «внесено … » only when it differs from
the local day of `created_at`. The comparison helper already exists
(`operations._is_backdated`) but is `Operation`-typed; either generalise it to take
`(business_date, created_at)` or compute the flag in `finance.cash_history_view` and
return it per row (do **not** compute it in the template — the same reason
`history_view` computes it server-side: a template-side marker cannot be filtered or
counted). If the omission is deliberate, say so in `33-UI-SPEC.md` and in
`cash_history_view`'s docstring, because nothing in the code says it today.

### WR-02: `reports.stale_products` reads a naive `created_at` in the OS zone and has no parse guard

**Severity:** WARNING
**File:** `app/services/reports.py:300-322` (the defect is at `:310-314`)

**Issue:** this phase deliberately reviewed and annotated this function (the D-25
"stays on `created_at`" note at `:281-287` is new), and left the read itself in the
one shape the rest of the phase rejects:
```python
days_since = (today_local - datetime.fromisoformat(last_sale_iso).astimezone(
    ZoneInfo(settings.display_tz)).date()).days
```
Two problems, both proven reachable:

1. **Naive values are read in the machine's OS zone.** `merge._is_iso_timestamp`
   *deliberately accepts* a naive `created_at` («A NAIVE timestamp is deliberately
   ACCEPTED», `merge.py:205-207`), and `astimezone()` on a naive datetime assumes the
   **system** zone. `core.iso_to_local:171-173`, `operations._is_backdated:152-153`
   and `0027::_local_business_date:311-315` all apply the opposite rule (naive == UTC),
   and the CR-01 fix report states that rule is load-bearing precisely so the marker
   and the migration cannot disagree. On the s1 container (OS zone UTC,
   `display_tz=Europe/Moscow`) this function is off by up to a day for any merged
   naive row, while every sibling reader is correct.
2. **No `try`.** `datetime.fromisoformat` raises on a malformed value, and
   `33-REVIEW-FIX.md` § IN-03 states that a pre-0027 row may already carry a poisoned
   `created_at` that intake validation cannot retroactively repair. That is a raw 500
   on `/reports/products` with no recovery path — the exact scenario the CR-01
   "display never raises" rule exists for, applied everywhere except here.

**Fix:** route it through the same rule as its siblings.

```python
try:
    moment = datetime.fromisoformat(last_sale_iso)
except (TypeError, ValueError):
    # Same posture as core.iso_to_local / format_ru_date: an unrepairable
    # append-only row degrades one line, it never 500s the page.
    continue
if moment.tzinfo is None:
    moment = moment.replace(tzinfo=UTC)   # naive == UTC (0027, _is_backdated)
days_since = (today_local - moment.astimezone(ZoneInfo(settings.display_tz)).date()).days
```
Add one test per branch (naive input on a non-UTC host, unparseable input) — neither
shape is covered by `tests/test_reports.py` today.

### WR-03: the two mobile wizards whose date lives on the final step silently reset a typed back-date to today on «Назад»

**Severity:** WARNING
**Files:**
`app/routes/mobile_corrections.py:149-195` (`step/mode` and `step/value` neither accept
nor re-emit `op_date`), `app/templates/mobile_partials/corrections_step_value.html:68,75-77`;
`app/routes/mobile_transfers.py:181` (`_render_dest_step(...)` called with no `op_date`),
`app/templates/mobile_partials/transfers_step_dest.html:98,111-115`

**Issue:** iteration 2's IN-02 fix threaded `op_date` through
`POST /m/transfers/step/dest` — a route whose own docstring now states **«NO template
posts here … the only callers are tests»**. The *reachable* path was left broken, in
both wizards:

* **Корректировка.** Step 4's «Назад» posts to `/m/corrections/step/mode`
  (`corrections_step_value.html:75-77`, `hx-include="closest form"` — so `op_date` **is**
  sent). `mobile_correction_step_mode` does not declare it, `corrections_step_mode.html`
  does not re-emit it, and step 4 is then re-rendered by `step/value` with **no** `form`
  key at all, so `op_date_value(form.op_date if form is defined else '')` falls back to
  today (`corrections_step_value.html:68`).
* **Перемещение.** Step 3's «Назад» posts to `/m/transfers/step/batch`; tapping a batch
  card lands on `GET /m/transfers/step/batch-pick`, which calls `_render_dest_step`
  **without** `op_date` (`mobile_transfers.py:181`), so `op_date` is `""` and the
  template pre-fills today.

Why this is worse than an ordinary lost-form-value: value/note/qty come back **empty**,
so the operator sees they must retype them. The date comes back **plausible** — today's
date, correctly formatted. The operator confirms and the operation is booked on the
wrong day with no cue. This is the same class of defect IN-02 was raised for, and the
same wizard.

**Fix:** thread `op_date` end to end on the reachable path.
* `mobile_corrections.py`: add `op_date: str = Form("")` to `mobile_correction_step_mode`
  and `mobile_correction_step_value`; put `{"op_date": op_date}` into both contexts;
  add `<input type="hidden" name="op_date" value="{{ op_date }}">` to
  `corrections_step_mode.html` beside the existing `code`/`name`/`batch_id`/`batch_qty`
  hiddens; change `corrections_step_value.html:68` to prefer `form.op_date` and fall
  back to a flat `op_date` key.
* `mobile_transfers.py`: add `op_date: str = ""` to `transfers_step_batch_pick`, forward
  it into `_render_dest_step`, and add it to the «Назад» button's `hx-vals` in
  `transfers_step_dest.html:113` (`{'code': code, 'op_date': op_date} | tojson`, keeping
  the single-quoted attribute — see the memory note on `| tojson` quoting).
Add one test per wizard that walks forward → «Назад» → forward and asserts the typed
date survives; the existing IN-02 tripwire test only covers the dead route.

### WR-04: `created_by` is the one free-text CSV cell that is not `_csv_safe`-wrapped, and it is wire-supplied

**Severity:** WARNING
**File:** `app/services/export.py:195` (`op.created_by`), secondary `:278`
(`movement.currency`), `:193` (`row_currency`)

**Issue:** `33-REVIEW-FIX.md` § WR-04 records this and explicitly declines to fix it
("pre-existing and unrelated"). It was neither carried into a finding nor tracked, so
it is raised here. `_INJECTION_PREFIXES` hardening (T-06-10) wraps every other
free-text cell in all three exports — product code/name/category, customer
name/surname/consultant number, batch comment, cash note, and now (WR-04's own fix)
five date cells. `op.created_by` is not wrapped, and it is **not** locally generated:
`merge._LEDGER_REQUIRED` (`merge.py:90`) carries it verbatim from a pushed NDJSON
record and `_ledger_row` bulk-inserts it, so a device with a valid Bearer token
controls its bytes; the append-only triggers then make it unrepairable. A value of
`=cmd|'/c calc'!A1` reaches `sales.csv` column 9 unescaped.

`movement.currency` and `row_currency` are the same shape one step weaker — validated
against `CURRENCIES` on the *local* write path (`finance.record_cash_movement:90-91`,
`warehouses._clean_currency`) but **not** by `parse_exchange`, which type-checks only
money, `seq`, dates and timestamps.

**Fix:** one-line each, output-identical for every well-formed value.
```python
_csv_safe(op.created_by or ""),          # export.py:195
_csv_safe(movement.currency or ""),      # export.py:278
_csv_safe(row_currency or DEFAULT_CURRENCY),  # export.py:193
```
Leave the `format_cents` columns unwrapped as they are — a negative amount legitimately
starts with `-`, exactly as the fix report reasoned. Add one test mirroring the
existing `=HYPERLINK` business-date test, driven through the real `/export/sales.csv`
route with a `created_by` that starts with `=`.

### WR-05: a back-dated receipt stamps the operator's date onto the `product_created` / `price_change` AUDIT rows

**Severity:** WARNING
**File:** `app/services/receipts.py:186-194` (`product_created`), `:213-221` (`price_change`)

**Issue:** `resolved_business_date` is passed to every `record_operation` call in
`register_receipt`, including the two audit types. Those rows are not goods movements —
`product_created` records *when the card was created* and `price_change` records *when
the price changed*, both of which really happened today. Every sibling service passes
the operator's date only to rows that represent the movement itself
(`writeoffs.py:118-127`, `corrections.py:136-152` write exactly one op;
`transfers.py:217-234` writes the two halves of one move;
`sales.py:321-357` the N sale lines plus their single cash movement).

Visible consequence: `/history` and `/m/history` bucket **all** types by
`business_date_expr` (`operations.py:280-286` — there is no type restriction), so
filtering the period to last month surfaces a «Товар создан» / «Цена изменена» row for a
card that was created today. `HISTORY_TYPE_COLUMNS` deliberately has no entry for the
three audit types, so they render in the generic view with no cue that their date was
inherited. D-25 reasoned explicitly about which *readers* stay on `created_at`; nothing
in the phase's artefacts decides that audit *writes* should carry the operator's date.

**Fix:** pass `business_date=None` for the two audit calls (so
`record_operation`'s Python-side fallback stamps the real local day) and keep
`resolved_business_date` on the `receipt` op at `:277-287` and on the batch auto-name at
`:246`. If inheritance was intentional, state the reason at both call sites and pin it
with a test — right now the code reads as "threaded everywhere because it was easy".

### WR-06: «Только в день операции» under-includes in the UTC-straddle window

**Severity:** WARNING
**File:** `app/services/operations.py:305-332` (the `same_day` branch at `:313-330`),
documented at `:96-116`
**Status:** carried from iterations 1 and 2 (as WR-05 then WR-09); still unresolved.

**Issue:** the `dated` filter compares `business_date` against
`substr(created_at, 1, 10)` (the **UTC** day) while `_is_backdated` compares it against
the **local** day. For a row entered at 00:30 local at `Europe/Moscow` the two disagree,
so a row the UI renders with **no** marker is nevertheless **excluded** from «Только в
день операции». The label promises a partition; the predicate delivers an
approximation. This is documented in the code and pinned by
`test_backdated_filter_and_marker_diverge_only_on_utc_straddle`, but documenting a wrong
answer does not make it right, and the shipped copy still over-promises.

**Fix (still needs one decision, and only one):** ask the operator which they want, then
apply exactly one of:
* **relabel** — change the option copy in `33-UI-SPEC.md` § Copywriting Contract and in
  both templates (`history_rows.html:79`, `mobile_pages/history.html:71`) to something
  the predicate can honour, e.g. «Без пометки»; or
* **make it exact** — store the marker. That means a fifth ledger column and revision
  `0028`, which the phase's own `add_column`-only discipline makes safe.
Do **not** close this by editing the docstring a third time.

### WR-07: `reverses_*_id` carry an ORM `ForeignKey` that migration 0027 does not create

**Severity:** WARNING
**Files:** `app/models.py:413-416`, `app/models.py:581-587` against
`alembic/versions/0027_ledger_business_date_and_reversal_links.py:343,346`
**Status:** carried from iteration 2 (IN-08); closed as "documentation only".

**Issue:** `Base.metadata.create_all` — the build path for **every** test fixture
(`tests/conftest.py:30`) — emits both reversal FKs, while `0027` adds bare
`sa.Column`s, and `app/db.py:121-131` sets `PRAGMA foreign_keys=ON`. The test suite
therefore enforces a constraint production does not have. The divergence is in the
false-RED direction, which is the safer one, but it is now a **latent trap for Phase 34
specifically**: the first test that pushes a reversal whose target row has not arrived
yet will raise `IntegrityError` in CI while the identical push succeeds on s1 — i.e. the
suite will "prove" a dangling-link behaviour that production does not have, or force a
Phase-34 author to weaken a test to make it pass.

**Fix:** decide before Phase 34 writes its first reversal, not after. Either
* drop the ORM `ForeignKey` on both columns (matching `0027`) and replace the
  merge insert-ordering it provided with an explicit entry in
  `merge._LEDGER_INSERT_ORDER` / the FK-closure collector; or
* add the real constraint in revision `0028` — permitted only via `op.create_foreign_key`
  on PostgreSQL; on SQLite it needs a table rebuild, which the module docstring's own
  Pitfall 3 says would drop all four append-only triggers. That makes option 1 the
  cheaper one unless PostgreSQL-only enforcement is acceptable.

## Info

### IN-01: `0027.upgrade()` skips rows whose `created_at` is falsy, contradicting `_local_business_date`'s own contract

**Severity:** INFO
**File:** `alembic/versions/0027_ledger_business_date_and_reversal_links.py:355-359`
against the docstring at `:304-305`

**Issue:** the helper promises «A malformed timestamp falls back to its leading 10
characters so no row is left NULL by a value this migration failed to parse», but the
caller filters with `if created_at`, so a row with an empty-string `created_at` is
skipped and keeps `business_date IS NULL`. Harmless in practice (the read-side COALESCE
covers it, and `created_at` is `NOT NULL`), but the two statements cannot both be true
and the next author will trust the docstring.

**Fix:** either drop the `if created_at` filter (the helper already handles `""` →
`""[:10]` → `""`, so tighten it to `return (created_at or "")[:10]`), or amend the
docstring to say empty values are deliberately left NULL. `0027` is live on s1 and must
not be edited — so this is a comment-only correction, or a note in `33-ROLLOUT.md`.

### IN-02: the wire timestamp gate covers ledger kinds only; `Sale.created_at` is the pull cursor and is unvalidated

**Severity:** INFO
**File:** `app/services/merge.py:300-304` (adjacent to the reviewed scope — changed by
iteration 2's CR-01 fix)

**Issue:** `_timestamp_fields(kind)` is written as a schema-derived intersection
(`_TIMESTAMP_FIELDS & KIND_TO_FIELDS[kind]`), which reads as "every kind that declares
the column", but the call site sits inside `if kind in _LEDGER_KINDS:`. So
`Sale.created_at` and `Customer.created_at` arrive unchecked. `Sale.created_at` is the
pull cursor column (`app/services/sync.py:76`) and `Customer.created_at` is rendered
into `customers.csv` via `iso_to_local`. Impact is bounded — `iso_to_local` no longer
raises, and the cursor comparison stays consistent even for junk — but this is
structurally the same gap WR-03 (iteration 2) closed for `Batch.expiry`: a gate
advertised as schema-tracking that silently is not.

**Fix:** hoist the timestamp loop out of the ledger branch (it is already an
intersection, so it is a no-op for kinds that do not declare the column), or narrow
`_timestamp_fields`' docstring to say the check is ledger-only and why.

### IN-03: no DB-level shape constraint on `business_date` / `created_at`

**Severity:** INFO
**Files:** `app/models.py:435,606`, `alembic/versions/0027…py`
**Status:** carried from iteration 2; correctly deferred.

The four blockers recorded in `33-REVIEW-FIX.md` (0027 is live; a SQLite `CHECK` needs
`batch_alter_table`, which drops all four triggers; the `GLOB` pattern is
SQLite-specific; PostgreSQL rejects the `ADD CHECK` outright if any existing row
violates it) all still hold and are all correct. **No action this iteration.** Next
step unchanged: one planned revision `0028` that repairs poisoned rows found on a real
s1 dump *and* adds the dual-dialect check, with V4 executed against that dump first.

### IN-04: four near-identical period resolvers

**Severity:** INFO
**Files:** `app/routes/reports.py:39-90`, `app/routes/history.py:24-81`,
`app/routes/mobile_history.py:37-65`, `app/services/dashboard.py:119-123`
**Status:** carried from iteration 2; refactor-mode work needing an explicit scope.

The Monday-start-week / calendar-month arithmetic is now copied four times and the
`_resolve_period` variant is imported cross-module by two mobile routers
(`mobile_finance.py:26`, `mobile_sales.py:21` set the precedent). Phase 34 touches
reports, so that is the natural moment to ask for the scope for a shared
`app/services/period.py`. Not a defect today; every copy is byte-identical and
documented as intentional.

### IN-05: the mandatory-comment error surfaces only on a second round trip

**Severity:** INFO
**File:** `app/services/finance.py:188-199`

`parse_op_date` writes into `errors`, then `if errors: return None, errors` at `:191`,
and only afterwards does `:198` check the mandatory comment for
`withdrawal_other` / `deposit_correction`. So a withdrawal submitted with both a bad
date and a blank comment reports the date, and the comment error only appears after the
operator fixes the date and resubmits. Pre-existing shape (the note check has always sat
after the error gate), but the phase added a *fourth* error to the batch that returns
early, making the two-round-trip path easier to hit.

**Fix:** move the note check above the `if errors:` gate and write into `errors` like
every other validation in the function, so all four surface in one 422.

---

## Process notes (limitations of this review — stated, not hidden)

* **No commands were executed.** This project's `CLAUDE.md` mandates invoking the
  `robust-console-commands` skill before every `Bash`/`PowerShell` call, and no
  Skill/SlashCommand tool is exposed in this agent context. Rather than bypass the
  policy, the entire review was done with read-only file tools. Consequences:
  * the diff against `1ea960f` was **not** computed — findings were derived from the
    current state of the listed files, so a small number of observations may touch
    pre-existing code (each such case is labelled as pre-existing in its finding);
  * **no tests were run.** The 1784-passed figure in `33-REVIEW-FIX.md` is taken on
    trust, not re-verified;
  * `ruff` was not run.
* **Not verifiable here, still open from iteration 2:** the `.filter-bar` `flex-wrap`
  change (`style.css:194-200`) needs a browser at 1024 px; the `created_at` intake gate
  needs one live push from a real `0027` client. Both remain pending human checks.
* **Deliberately not reported:** the `_movement_success` / mobile-history HX branches
  render templates via `get_template(...).render(...)`, bypassing the `_auth_context` /
  `_sync_status_context` processors; `mobile_writeoff_submit` returns a full
  `mobile_pages/writeoff.html` document into an `innerHTML` swap of `#wizard-step`; the
  shared `period_filter.html` preset links duplicate `from`/`to` between the `hx-get`
  URL and `hx-include`. All three are pre-existing, none was touched by Phase 33, and
  the last cannot be confirmed without a browser.

---

_Reviewed: 2026-09-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
