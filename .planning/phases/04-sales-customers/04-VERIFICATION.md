---
phase: 04-sales-customers
verified: 2026-07-09T16:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Add a basket line via «Добавить строку» without clicking into the new row"
    expected: "Focus lands on the new row's «Код» field automatically (no click required)"
    why_human: "DOM focus behavior after an htmx swap is not observable via TestClient/pytest — requires a real browser"
  - test: "Type a sale price, then quickly type a known product code in the same row (before the 300ms lookup debounce fires)"
    expected: "The in-flight lookup response does not clobber the price the operator already typed (oob-swap guard holds)"
    why_human: "In-flight HTMX swap race condition; requires real browser timing, not reproducible via TestClient"
  - test: "Oversell a line (qty > stock), observe the warning, click «Продать всё равно»"
    expected: "Warning shows zero committed sale ops; confirm re-POSTs the same basket and writes, allowing Product.quantity to go negative; «Вернуться к корзине» dismisses with no write"
    why_human: "Full HTMX warn-then-confirm cycle with live DOM state and the form= association across elements — end-to-end browser behavior beyond what TestClient's single-request model can exercise"
  - test: "In the sale form: type a customer name in the picker, select a row, verify the chip appears with «Убрать»; then quick-create a new customer inline without leaving the sale"
    expected: "Selecting a picker row (client-side dataset-read JS) flips the header to the chip state with the correct hidden customer_id; quick-create renders a chip from the server response; «Убрать» reverts to search state"
    why_human: "Client-side-only picker-row selection (reads element .dataset via JS, no server round-trip) is not exercised by TestClient, which only sees HTTP request/response pairs, not DOM/JS behavior"
---

# Phase 4: Sales & Customers Verification Report

**Phase Goal:** Operator can sell products — optionally to a known customer — with stock decremented, oversells warned, and profit data frozen correctly at sale time
**Verified:** 2026-07-09T16:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Note on ROADMAP `Mode: mvp` tag

ROADMAP.md tags this phase `**Mode:** mvp`, but the phase goal text ("Operator can sell products — optionally to a known customer — with stock decremented, oversells warned, and profit data frozen correctly at sale time") is **not** in the required user-story format (`As a [role], I want to [capability], so that [outcome].`). Confirmed programmatically:

```
gsd-tools query user-story.validate --story "<goal text>" --pick valid
→ false
```

Per the MVP-mode verification contract, a non-conforming goal under `mode: mvp` should be surfaced as a discrepancy rather than forced into MVP-mode framing (which would produce a low-quality "User Flow Coverage" table built from an ad-hoc-derived flow instead of the phase's own user story). This verification therefore proceeds as **standard goal-backward verification** against the ROADMAP Success Criteria and PLAN must-haves. If MVP framing is desired for this phase, run `/gsd mvp-phase 4` to reformat the goal, then re-verify.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can register a sale by product code with quantity; stock decreases and the sale is saved to history | VERIFIED | `app/services/sales.py::register_sale` writes N `sale` ops (`qty_delta=-qty`) + a `Sale` header in one transaction; `tests/test_sales.py::test_stock_decrements_for_basket_sale` passes (spot-checked directly, plus full suite) |
| 2 | Operator can override the sale price on any sale line | VERIFIED | `register_sale` requires an entered price and stores it as `unit_price_cents`, ignoring `Product.sale_cents` except as a lookup pre-fill; `test_price_override_uses_entered_price` passes |
| 3 | Operator can create and edit customer profiles (name, surname, consultant number) and link a sale to a customer | VERIFIED | `app/services/customers.py::create_customer/update_customer` (CRUD + `search_lc` shadow); `app/routes/sales.py::sale_customer_create` + `partials/sale_customer.html` link `customer_id` into the sale header; `test_web_sale_links_selected_customer` passes (spot-checked directly) |
| 4 | Selling more than is in stock triggers a warning with explicit confirm-to-proceed | VERIFIED | Aggregate oversell check in `register_sale` (sums qty per `product_id` before comparing to cached `Product.quantity`); zero writes until `confirm=="1"`; `partials/sale_oversell.html` renders «Продать всё равно»/«Вернуться к корзине»; `test_oversell_blocks_without_confirm`, `test_oversell_confirm_writes_negative_stock`, `test_oversell_aggregates_duplicate_lines` all pass (last one spot-checked directly) |
| 5 | Each sale line snapshots unit cost and sale price at sale time, and a customer's purchase history shows what/when/at what price | VERIFIED | `unit_cost_cents`/`unit_price_cents` frozen at INSERT via `record_operation`; `app/services/customers.py::purchase_history` joins `Operation→Sale→Product` and reads the FROZEN `unit_price_cents`; `test_snapshot_frozen_after_price_change`, `test_purchase_history_frozen` pass (latter spot-checked directly) |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | `Customer`, `Sale` models, `Operation.sale_id` | VERIFIED | All three present exactly as specified (lines 122-170) |
| `app/services/ledger.py` | `record_operation(..., sale_id=None)` kwarg | VERIFIED | Line 38, 78 — threaded into `Operation(...)` constructor |
| `alembic/versions/0004_sales_customers.py` | customers + sales tables, native `operations.sale_id` add-column | VERIFIED | Confirmed native `op.add_column` (no `batch_alter_table`); migration chain runs; append-only triggers preserved (`test_migration_0004_preserves_append_only_triggers`) |
| `app/services/sales.py` | `register_sale`, `lookup_prefill`, `recent_sales` | VERIFIED | All three present; single-write-path via `record_operation` only |
| `app/routes/sales.py` | `/sales/new`, `/sales/lookup`, `/sales/row`, `POST /sales`, `/sales/customer-search`, `POST /sales/customer` | VERIFIED | All six routes present, literal paths declared correctly |
| `app/templates/partials/sale_form.html` | basket form, oversell + customer-header insertion points wired | VERIFIED | Contains `id="sale-form-wrap"`, `id="sale-form"`, `hx-post="/sales"`, includes `sale_customer.html` and `sale_oversell.html` conditionally |
| `app/templates/partials/recent_sales.html` | oob-refreshable recent sales list | VERIFIED | Contains `id="recent-sales"` + `hx-swap-oob` |
| `app/templates/partials/sale_oversell.html` | oversell warning + confirm/cancel | VERIFIED | Contains «Товара не хватает на складе», «Продать всё равно», «Вернуться к корзине», `hx-vals='{"confirm": "1"}'` |
| `app/services/customers.py` | CRUD, `search_customers`, `purchase_history` | VERIFIED | All functions present; `purchase_history` joins on `Operation.sale_id == Sale.id` |
| `app/routes/customers.py` | `/customers` CRUD + detail | VERIFIED | All 7 routes present, literal-before-parameterized ordering respected |
| `app/templates/pages/customer_detail.html` | customer detail + purchase history | VERIFIED | Contains «История покупок»; `partials/purchase_history.html` renders frozen `unit_price_cents` |
| `app/templates/partials/sale_customer.html` | customer header: search + quick-create + chip | VERIFIED | Contains `name="customer_id"`, `hx-get="/sales/customer-search"`, quick-create `hx-post="/sales/customer"`, «Без покупателя (розница)» note |
| `app/templates/partials/customer_picker.html` | customer search rows for sale picker | VERIFIED | Contains `id="customer-picker"` (table-based per 04-05 decision), `<mark>` highlight, no `\|safe` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/services/sales.py` | `app/services/ledger.record_operation` | `record_operation(type_="sale", qty_delta=-qty, sale_id=header.id, commit=False)` | WIRED | Confirmed at lines 169-178 |
| `app/routes/sales.py` | `app/services/sales.register_sale` | `POST /sales` handler | WIRED | Confirmed at line 187 |
| `app/templates/partials/sale_form.html` | `POST /sales` | `hx-post="/sales"` | WIRED | Confirmed via grep |
| `app/services/sales.py` | `Product.quantity` | aggregate requested qty per product vs cached quantity | WIRED | Confirmed lines 130-148 |
| `app/templates/partials/sale_oversell.html` | `POST /sales` | `hx-vals='{"confirm":"1"}'` + `form="sale-form"` | WIRED | Confirmed via review + tests |
| `app/services/customers.py` | Sale + Operation + Product join | `Operation.sale_id == Sale.id` | WIRED | Confirmed line 154 |
| `app/services/customers.py` | `Customer.search_lc` | `search_lc.contains(q_lc, autoescape=True)` | WIRED | Confirmed line 128, Python-side lowering (Cyrillic-safe) |
| `app/routes/sales.py` | `app/services/customers.search_customers/create_customer` | `GET /sales/customer-search`, `POST /sales/customer` | WIRED | Confirmed lines 123-173 |
| `app/templates/partials/sale_customer.html` | `POST /sales` (finalize) | hidden `input name="customer_id"` `form="sale-form"` | WIRED | Confirmed per 04-05 SUMMARY + review |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full phase test suite | `uv run pytest -q` | 148 passed, 0 failed | PASS |
| Sale finalize links selected customer | `uv run pytest tests/test_sales.py::test_web_sale_links_selected_customer -v` | PASSED | PASS |
| Oversell aggregates duplicate lines before comparing to stock | `uv run pytest tests/test_sales.py::test_oversell_aggregates_duplicate_lines -v` | PASSED | PASS |
| Purchase history reads frozen price after card mutation | `uv run pytest tests/test_customers.py::test_purchase_history_frozen -v` | PASSED | PASS |
| Test enumeration for the phase (34 tests) | `uv run pytest tests/test_sales.py tests/test_customers.py --co -q` | 34 tests collected, all named per requirement (stock/oversell/customer_link/snapshot/crud/search/history/history_frozen/web_*) | PASS |
| Ruff clean on phase-modified files | `uv run ruff check app/services/sales.py app/services/customers.py app/routes/sales.py app/routes/customers.py app/models.py app/services/ledger.py alembic/versions/0004_sales_customers.py` | All checks passed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SAL-01 | 04-01, 04-02 | Register a sale by code/qty; stock decreases, saved to history | SATISFIED | `register_sale`, `record_operation` sale ops, `test_stock_decrements_for_basket_sale` |
| SAL-02 | 04-02 | Sale price can differ from standard price per line | SATISFIED | Entered price required and snapshotted as `unit_price_cents`; `test_price_override_uses_entered_price` |
| SAL-03 | 04-05 | Sale can optionally be linked to a customer | SATISFIED (code+tests) — **REQUIREMENTS.md not updated** | `sale_customer.html`/`customer_picker.html`/routes wired; `test_web_sale_links_selected_customer`, `test_customer_link_sets_header_customer_id`, `test_customer_link_walkin_customer_id_null` all pass. **Gap:** `.planning/REQUIREMENTS.md` still shows `[ ] SAL-03` and "Pending" in the Traceability table — SAL-01/02/05 (05e2014) and CST-01/02 (4c6f9ba) each got a dedicated "mark complete" commit, but no equivalent commit exists for SAL-03 after 04-05 merged |
| SAL-04 | 04-03 | Warn when selling more than in stock | SATISFIED | Aggregate oversell check + warn/confirm flow; 3 oversell tests pass |
| SAL-05 | 04-01, 04-02 | Snapshot unit cost + sale price at sale time | SATISFIED | `unit_cost_cents`/`unit_price_cents` frozen at INSERT; `test_snapshot_frozen_after_price_change`, `test_null_cost_allowed_sale_succeeds` |
| CST-01 | 04-04 | Create/edit customer profiles | SATISFIED | `create_customer`/`update_customer`/routes/templates; CRUD tests pass |
| CST-02 | 04-04 | View customer purchase history (what/when/price) | SATISFIED | `purchase_history` join reads frozen price; `test_purchase_history_returns_rows_for_customer`, `test_purchase_history_frozen` |

No orphaned requirements — all 7 phase-declared requirement IDs (SAL-01..05, CST-01, CST-02) appear in REQUIREMENTS.md's traceability table mapped to Phase 4.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers found in any phase-04 file | — | None |

A code review (`04-REVIEW.md`) found 1 critical (CR-01: reflected XSS via unvalidated `row` query param in an `hx-on::load` JS sink) and 5 warnings (unsafe `isdigit()` precondition, broad exception swallowing with no logging, missing explicit rollback on non-`IntegrityError` write failures, duplicated line-filtering logic, missing max-length guards on customer fields). All 6 were fixed per `04-REVIEW-FIX.md`, each with its own commit (fec18a2, 73e5a28, 729100e, b253026, 3ca887a, acbbffa), and verified present in the current codebase (e.g. `_ROW_ID_RE` validation in `app/routes/sales.py`, `_validate_lengths` in `app/services/customers.py`, the widened `except (IntegrityError, ValueError)` in `register_sale`). No unresolved findings remain.

### Human Verification Required

1. **Focus after adding a basket line**
   **Test:** Click «Добавить строку» to add a new row without clicking into it.
   **Expected:** Focus lands on the new row's «Код» field automatically.
   **Why human:** DOM focus behavior post-htmx-swap is not observable via TestClient.

2. **In-flight lookup does not clobber a typed price**
   **Test:** Type a price, then quickly type a known product code before the 300ms debounce fires.
   **Expected:** The lookup response's price pre-fill does not overwrite the already-typed price.
   **Why human:** Real browser timing/race condition, not reproducible in a synchronous test client.

3. **Oversell warn→confirm→write cycle end-to-end**
   **Test:** Enter a quantity exceeding stock, observe the warning, click «Продать всё равно»; separately, click «Вернуться к корзине».
   **Expected:** Warning shows 0 writes; confirm re-POSTs and writes (stock may go negative); cancel dismisses with zero writes.
   **Why human:** Full HTMX two-step confirm cycle with live DOM/`form=` association across page state — beyond what a single-request TestClient assertion proves.

4. **Customer picker client-side selection**
   **Test:** In the sale form, type a customer name, click a picker row; separately, use «Новый покупатель» to quick-create inline.
   **Expected:** Clicking a row flips the header to the chip state (populated from `data-*` attributes via JS, no server round-trip) with the correct hidden `customer_id`; quick-create renders a server-side chip; «Убрать» reverts to the search state.
   **Why human:** The picker-row selection is pure client-side JS (`.dataset` read, no HTTP call) — TestClient only exercises HTTP request/response pairs, not in-page JS behavior.

### Gaps Summary

No functional gaps block the phase goal — all 5 ROADMAP Success Criteria are verified in the codebase with passing automated tests (148/148, including targeted re-runs of 3 key tests), clean `ruff check`, and all 6 code-review findings fixed and confirmed present. Two non-blocking items are worth the developer's attention:

1. **REQUIREMENTS.md staleness (SAL-03):** the traceability table and checkbox for SAL-03 were not updated to "Complete" after 04-05 merged, unlike every other requirement in this phase which got a dedicated tracking commit. Functionally SAL-03 is fully implemented and tested — this is a documentation-only gap, easy to fix with a one-line edit + commit.
2. **ROADMAP `mode: mvp` / goal-format mismatch:** the phase is tagged `mode: mvp` but its goal text is not in user-story format, so MVP-mode "User Flow Coverage" framing was not applied (see note above). This is informational only — it does not affect the functional verification above.

The four human-verification items above are genuine browser/DOM/timing behaviors that cannot be proven by automated tests and were correctly deferred to end-of-phase UAT by the plans themselves (VALIDATION.md Manual-Only Verifications + 04-05's embedded human-check). Per the status decision tree, their presence routes this phase to `human_needed` rather than `passed`, even though every automatable truth is VERIFIED.

---

*Verified: 2026-07-09T16:00:00Z*
*Verifier: Claude (gsd-verifier)*
