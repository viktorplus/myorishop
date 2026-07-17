---
phase: 21-customer-profiles-purchase-insights
plan: 04
subsystem: ui
tags: [fastapi, jinja2, htmx, form-arrays, customer-profiles]

# Dependency graph
requires:
  - phase: 21-customer-profiles-purchase-insights (Plan 02)
    provides: contacts/address write+read path on create_customer/update_customer, contacts_by_kind
affects: [21-05-customer-detail]
provides:
  - "partials/contact_row.html + .contact-row CSS: one repeatable, client-side-removable contact row"
  - "GET /customers/contact-row?kind= (allow-list validated, 404 on unknown kind, declared above /customers/{customer_id})"
  - "customer_form.html: four repeatable contact sections (phone/telegram/email/social) + address field"
  - "customer_create/customer_update: phone[]/telegram[]/email[]/social[]/address form-array binding into create_customer/update_customer's contacts+address kwargs"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Form-array contact rows (D-03 resolution): rows become DB rows only on final submit — no per-row server CRUD endpoint exists, mirroring sale_row.html's code[]/qty[] contract"
    - "_contact_rows() shared padding helper: every CONTACT_KINDS key holds >=1 row (blank fallback), used identically by customer_new, customer_edit, and both POST handlers' 422 re-echo branches"
    - "422 re-echo builds 'contacts' from the SUBMITTED arrays, never from contacts_by_kind — the operator's unsaved edits must win over stored values"

key-files:
  created:
    - app/templates/partials/contact_row.html
  modified:
    - app/routes/customers.py
    - app/templates/pages/customer_form.html
    - app/static/style.css
    - tests/test_customers.py

key-decisions:
  - "GET /customers/contact-row declared above GET /customers/{customer_id} (route-order comment extended, not duplicated) — the parameterized route would otherwise swallow it"
  - "kind query param validated against CONTACT_KINDS before rendering; 404 (not a fresh-id fallback like sale_row) since kind has no sensible default"
  - "Contact rows carry no id= attribute (no lookup/focus hook/swap target exists for them, unlike sale_row's per-row ids)"
  - "Docstring text in contact_row.html rephrased to avoid the literal substring 'safe' so the plan's own grep -c \"safe\" == 0 acceptance criterion holds (same self-grep pitfall Plan 03 hit)"

requirements-completed: [CUST-01, CUST-02, CUST-03, CUST-04, CUST-05]

# Metrics
duration: ~20min
completed: 2026-07-17
---

# Phase 21 Plan 04: Customer Contact Form Edit Surface Summary

**Four repeatable contact sections (phone/Telegram/email/social) plus an address field on `customer_form.html`, backed by an HTMX `GET /customers/contact-row` endpoint and form-array binding on both `customer_create`/`customer_update` — contacts persist only on final submit, with zero per-row server CRUD.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-17
- **Tasks:** 3/3 completed
- **Files modified:** 4 (1 created)

## Accomplishments
- `contact_row.html` (new) renders one `.contact-row` — an array-named `{{ kind }}[]` input plus a client-side-only «Удалить» remove button — with no per-row id, no anchor tags, and autoescape-only rendering (no `|safe` anywhere)
- `GET /customers/contact-row?kind=` appends a blank row over HTMX for any of the four `CONTACT_KINDS`; an unknown/malicious `kind` 404s before anything is rendered, and the route is declared above `/customers/{customer_id}` so the literal path always wins
- `customer_form.html` gained four structurally identical contact sections (Телефоны/Telegram/Email/Соцсети, each with its own per-kind «Добавить …» button) plus a single-valued `Адрес` field, inserted between the untouched identity fields and `.form-actions`
- `customer_create`/`customer_update` bind `phone[]`/`telegram[]`/`email[]`/`social[]`/`address` and hand them straight to `create_customer`/`update_customer`'s existing `contacts`/`address` contract (Plan 02) — proving contacts survive the **new-customer** path where no `customer.id` exists at render time (the phase's Pitfall 2 guard)
- A 422 on either POST re-echoes every typed contact value and the address via a shared `_contact_rows()` padding helper, built from the submitted arrays (not stored values), so nothing the operator typed is silently dropped
- Full 799-test suite green (Wave 3 merge gate); `ruff check`/`ruff format --check` clean on every file this plan touched

## Task Commits

Each task was committed atomically:

1. **Task 1: contact_row.html partial + .contact-row CSS + GET /customers/contact-row** - `a970394` (feat)
2. **Task 2: customer_form.html — four contact sections + address field** - `30cd889` (feat)
3. **Task 3: Form-array binding on customer_create / customer_update** - `a2c8e5b` (feat)

_Worktree mode: STATE.md/ROADMAP.md are updated centrally by the orchestrator after merge — no separate plan-metadata commit was made here._

## Files Created/Modified
- `app/templates/partials/contact_row.html` (new) - one `.contact-row` div: array-named text input + client-side «Удалить» button; no id, no anchors, no `|safe`
- `app/static/style.css` - `.contact-row` / `.contact-row input` rules (flex row, existing 8px token only)
- `app/routes/customers.py` - `GET /customers/contact-row` (kind allow-list, declared above `/customers/{customer_id}`); `_contact_rows()` helper; `customer_new`/`customer_edit` gain a `contacts` context key; `customer_create`/`customer_update` bind the four `*[]` arrays + `address` and pass them to the service; both 422 branches re-echo `address` and the submitted `contacts`
- `app/templates/pages/customer_form.html` - four repeatable contact sections + address field inserted between `consultant_number` and `.form-actions`; identity fields (lines 1-31) untouched
- `tests/test_customers.py` - 14 new route-level (`test_web_`) tests across the three tasks: blank row per kind, unknown-kind 404, route-order guard, new-form one-blank-row-per-kind, edit-form stored contacts + blank-row-for-empty-kind, create-with-contacts (Pitfall 2 guard), blank-row discard, update-replaces-not-appends, 422 re-echo, overlong-value rejection

## Decisions Made
- Followed the plan's "Locked-decision reinterpretation": form-array only, no `POST /customers/{id}/contacts` and no per-row DELETE endpoint exist — verified by `grep -c "customers/{customer_id}/contacts\|@router.delete"` returning 0
- `_contact_rows()` is the single shared padding rule used by all four context-building sites (`customer_new`, `customer_edit`, and both POST handlers' 422 branches), so the "always at least one row" guarantee cannot drift between them
- Contact rows carry no `id=` attribute — matches the plan's stated rationale (no lookup, no focus hook, no swap target for a section-labeled repeated group)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `contact_row.html`'s own docstring self-failed the plan's `grep -c "safe"` acceptance criterion**
- **Found during:** Task 1 acceptance-criteria verification
- **Issue:** My first draft of the partial's docstring block explicitly stated "Autoescape only, never `|safe`" (per the house convention cited in `purchase_history.html:1-3` and the task's own `<read_first>` instructions). The plan's own acceptance criteria run `grep -c "safe" app/templates/partials/contact_row.html` and require `0` — the docstring's own literal mention of the word "safe" made that grep return `1`, self-failing the check even though the template correctly never applies `|safe` to any value. This is the same self-grep pitfall Plan 03's Summary documents hitting for `strftime`/`dateutil`/`date.today()`/`deleted_at` in service-layer docstrings.
- **Fix:** Reworded the docstring to convey the identical guarantee ("Autoescape is on by default and is the only HTML-escaping mechanism used here — no escape-bypassing Jinja2 filter is ever applied to `value`") without containing the literal substring "safe".
- **Files modified:** `app/templates/partials/contact_row.html`
- **Verification:** `grep -c "safe" app/templates/partials/contact_row.html` returns `0`; all other Task 1 acceptance-criteria greps (`<a href`, `tel:`, `mailto:`, `id=`, `danger`, `hx-confirm`, `script src`) also return `0`; the three `-k web_contact_row` tests pass.
- **Committed in:** `a970394` (Task 1 commit — the docstring was authored and corrected before the commit, so no separate fix-up commit was needed)

---

**Total deviations:** 1 auto-fixed (documentation-only correctness fix, no behavior change)
**Impact on plan:** None on functionality — the template's actual escaping behavior was always correct; only the explanatory comment's wording changed so the plan's own literal-grep acceptance criterion passes as written. No scope creep.

## Issues Encountered
None beyond the deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `app/templates/pages/customer_form.html` and `app/routes/customers.py` now expose the full CUST-01..05 edit surface for the operator; `contacts_by_kind`/`create_customer`/`update_customer` (Plan 02) are exercised end-to-end through the web layer for the first time
- Plan 05 (customer detail page) can render the same `contacts_by_kind` read path this plan already proved works through the save path — no further service-layer changes anticipated
- Full 799/799 test suite is green (Wave 3 merge gate); `ruff check`/`ruff format --check` clean on every file this plan touched. Whole-repo `ruff check`/`ruff format --check` still show pre-existing, out-of-scope findings across files this plan never touched (already logged in `21-*-deferred-items.md` by Plan 03) — left untouched per the executor's scope-boundary rule.

---
*Phase: 21-customer-profiles-purchase-insights*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created/modified files exist on disk and all task commit hashes (`a970394`, `30cd889`, `a2c8e5b`) are present in git log.
