---
phase: 21-customer-profiles-purchase-insights
plan: 02
subsystem: database
tags: [sqlalchemy, sqlite, pytest, customer-profiles, service-layer]

# Dependency graph
requires:
  - phase: 21-customer-profiles-purchase-insights (Plan 01)
    provides: CustomerContact model, CONTACT_KINDS allow-list, Customer.address column, migration 0015
provides:
  - "address (D-02/CUST-05) write/read path on create_customer/update_customer"
  - "contacts (D-01/CUST-01..04) write/read path: _validate_contacts, _replace_contacts, contacts_by_kind"
  - "ADDRESS_TOO_LONG_ERROR, CONTACT_VALUE_TOO_LONG_ERROR RU error constants"
affects: [21-03-purchase-insights, 21-04-customer-form, 21-05-customer-detail]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "contacts: dict[str, list[str]] | None two-state contract (None = untouched, dict = full replace) mirrors the existing address: str = \"\" load-bearing-default pattern that keeps app/routes/sales.py's quick-create call unmodified"
    - "Unknown allow-list value (contact kind) raises ValueError rather than an errors-dict entry when the value is not operator-reachable (route binds fixed Form params) — mirrors ledger.py record_operation's treatment of an unknown operation type"
    - "Same-second insertion-order tie-break: _replace_contacts stamps each row with a monotonically increasing microsecond-precision created_at instead of relying on the column's one-second-resolution utcnow_iso() default, because new_id() (random UUID4) cannot serve as an insertion-order tie-break"

key-files:
  created: []
  modified:
    - app/services/customers.py
    - tests/test_customers.py

key-decisions:
  - "_replace_contacts explicitly stamps created_at with microsecond offsets per inserted row (Rule 1 bug fix) — the plan's documented ORDER BY (created_at, id) does not preserve submitted order on its own, since id is a random UUID4, not a sequence; without this fix contacts_by_kind returns rows in random order whenever a save's rows land in the same second, which is routine (not the exception)"
  - "contacts_by_kind issues exactly one SELECT and buckets in Python (CONTACT_KINDS order) — no relationship()/lazy loader exists in this codebase, so N+1 avoidance is entirely on this function's design"
  - "app/routes/sales.py and app/services/export.py left untouched, per plan scope"

patterns-established:
  - "Two-state None-vs-dict argument contract for a full-replace child collection, keeping an existing unrelated caller (sales.py quick-create) working via a keyword-only default"

requirements-completed: [CUST-01, CUST-02, CUST-03, CUST-04, CUST-05]

# Metrics
duration: ~25min
completed: 2026-07-17
---

# Phase 21 Plan 02: Customer Contacts + Address Service Layer Summary

**Contact validation/full-replace persistence and address wiring in `app/services/customers.py`, closing CUST-01..05 at the service level with 15 new tests, all inside the existing single-commit `create_customer`/`update_customer` transaction.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-07-17
- **Tasks:** 3/3 completed
- **Files modified:** 2

## Accomplishments
- `address` (D-02/CUST-05) round-trips through `create_customer`/`update_customer` as a keyword-only `str = ""` argument; blanks normalize to `None`, an overlong value (>300 chars) is rejected with the exact UI-SPEC RU copy before any write, and `app/routes/sales.py`'s quick-create call site needed zero changes
- `_validate_contacts` and `_replace_contacts` (D-01/CUST-01..04) implement the full contact write path: unknown kinds raise `ValueError` (programmer error, not a form error — matches `ledger.py`'s `record_operation` precedent), blank rows are silently discarded, an overlong value is rejected per-kind, and re-saving replaces rather than duplicates — a delete-all-then-reinsert inside the caller's single transaction, legal because `customer_contacts` has no append-only trigger
- `contacts_by_kind` (public read) always returns all four `CONTACT_KINDS` keys (empty lists included) in a stable `CONTACT_KINDS` order, via exactly one `SELECT`
- Fixed a same-second ordering bug found during Task 3: `_replace_contacts` now stamps each inserted row with a monotonically increasing microsecond offset so `contacts_by_kind`'s submitted-order guarantee actually holds (see Deviations)

## Task Commits

Each task was committed atomically:

1. **Task 1: Address column wiring + WR-05 length guards (CUST-05)** - `954ad94` (feat)
2. **Task 2: Contact validation + full-replace persistence (CUST-01..04)** - `ec153b7` (feat)
3. **Task 3: contacts_by_kind read + per-kind persistence contract (CUST-01..04)** - `3199179` (feat, includes the Rule 1 ordering fix)

_Worktree mode: STATE.md/ROADMAP.md are updated centrally by the orchestrator after merge — no separate plan-metadata commit was made here._

## Files Created/Modified
- `app/services/customers.py` - `ADDRESS_TOO_LONG_ERROR`, `CONTACT_VALUE_TOO_LONG_ERROR`, `_ADDRESS_MAX_LEN`, `_CONTACT_VALUE_MAX_LEN` constants; `_validate_lengths` gains `address`; `_validate_contacts`, `_replace_contacts`, `contacts_by_kind` added; `create_customer`/`update_customer` gain `address: str = ""` and `contacts: dict[str, list[str]] | None = None` keyword-only arguments
- `tests/test_customers.py` - 15 new service-level tests: 4 address (`test_create_customer_stores_address`, `test_update_customer_changes_address`, `test_customer_address_blank_stores_none`, `test_customer_address_too_long_rejected`), 3 contacts_validation (`test_contacts_validation_discards_blank_rows`, `test_contacts_validation_rejects_unknown_kind`, `test_contacts_validation_value_too_long`), 2 contacts_replace (`test_contacts_replace_does_not_duplicate`, `test_contacts_replace_none_leaves_contacts_untouched`), 6 read-path (`test_contacts_phone_multiple_values_persist`, `test_contacts_telegram_multiple_values_persist`, `test_contacts_email_multiple_values_persist`, `test_contacts_social_multiple_values_persist`, `test_contacts_by_kind_returns_all_kinds_for_bare_customer`, `test_contacts_all_kinds_are_independent`)

## Decisions Made
- `_replace_contacts` stamps `created_at` explicitly with microsecond-precision offsets instead of relying on the column's default `utcnow_iso()` (one-second resolution) — required for `contacts_by_kind`'s `ORDER BY (created_at, id)` to actually preserve the caller's submitted order (see Deviations)
- Kept the plan's specified `ORDER BY (CustomerContact.created_at, CustomerContact.id)` shape unchanged in `contacts_by_kind` — the fix lives entirely in how `_replace_contacts` populates `created_at`, not in the read query
- `app/routes/sales.py` and `app/services/export.py` left untouched, per plan scope

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_replace_contacts` did not preserve submitted contact order**
- **Found during:** Task 3, running `test_contacts_phone_multiple_values_persist` / `test_contacts_email_multiple_values_persist` / `test_contacts_social_multiple_values_persist`
- **Issue:** The plan specifies `contacts_by_kind` order rows by `(CustomerContact.created_at, CustomerContact.id)`, with `id` as "the stable tie-break" for same-second ties (which the plan itself calls "routine" since a full-replace inserts every row of one save inside the same second). But `CustomerContact.id` is generated by `new_id()` — a random `uuid.uuid4()`, not a sequence — so ordering by `id` on a tie does NOT reproduce the order values were submitted in; it reproduces a random order. Running the read-path tests confirmed this: 3-phone and 2-value tests failed, returning insertion-unrelated orderings. This directly contradicts the plan's own acceptance criteria ("three phones save and read back **in submitted order**") and `must_haves.truths` ("Saving a customer with three phone numbers stores three CustomerContact rows...").
- **Fix:** `_replace_contacts` now stamps each inserted row's `created_at` explicitly with `base_time + timedelta(microseconds=offset)`, incrementing `offset` per row across the whole call (not reset per kind), instead of leaving it to the column's `default=utcnow_iso` (second resolution). This keeps every row's timestamp monotonically increasing in insertion order, so the existing `(created_at, id)` ORDER BY in `contacts_by_kind` now naturally returns submitted order without touching the read side. `id` is still the tie-break for the (now vanishingly unlikely) case of two truly identical timestamps, exactly as the plan describes.
- **Files modified:** `app/services/customers.py`
- **Verification:** All 4 read-path tests (`contacts_phone`, `contacts_telegram`, `contacts_email`, `contacts_social`) pass; full 770-test suite green.
- **Committed in:** `3199179` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for the plan's own explicitly stated acceptance criteria and `must_haves.truths` to hold. No scope creep — fix is contained to `_replace_contacts`'s row construction, no schema/architecture change.

## Issues Encountered
None beyond the deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `app/services/customers.py` now exposes the full CUST-01..05 write/read contract (`create_customer`/`update_customer` with `address`/`contacts` kwargs, `contacts_by_kind`) for Plan 04 (customer form) and Plan 05 (customer detail page) to build HTML against
- `app/routes/sales.py`'s quick-create call and `app/services/export.py` remain untouched, as the plan required
- Full 770/770 test suite is green (Wave 1 merge gate); `ruff check`/`ruff format --check` clean on both files this plan touched

---
*Phase: 21-customer-profiles-purchase-insights*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created/modified files exist on disk and all task commit hashes (`954ad94`, `ec153b7`, `3199179`) are present in git log.
