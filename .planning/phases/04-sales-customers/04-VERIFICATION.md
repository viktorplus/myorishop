---
phase: 04-sales-customers
verified: 2026-07-09T20:05:49Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/5
  gaps_closed:
    - "SAL-01: GET /sales/lookup autofill of «Название» from a typed product code — was unconditionally broken (bare code/name/price query params never bound the bracketed code[]/name[]/price[] keys hx-include=\"closest tr\" actually sends), found by human UAT (04-UAT.md Test 2), root-caused in .planning/debug/sale-lookup-name-not-filling.md, fixed by plan 04-06 (Query(alias=\"code[]\"/\"name[]\"/\"price[]\") on app/routes/sales.py::sale_lookup), and confirmed closed by direct code read + 2 passing regression tests reproducing both the fill-when-empty and no-clobber-when-typed request shapes"
  gaps_remaining: []
  regressions: []
---

# Phase 4: Sales & Customers Verification Report

**Phase Goal:** Operator can sell products — optionally to a known customer — with stock decremented, oversells warned, and profit data frozen correctly at sale time
**Verified:** 2026-07-09T20:05:49Z
**Status:** passed
**Re-verification:** Yes — after gap closure (plan 04-06, closing the SAL-01 `/sales/lookup` bracketed-param binding bug found by UAT)

## Note on ROADMAP `Mode: mvp` tag

Carried forward from the initial verification: ROADMAP.md tags this phase `**Mode:** mvp`, but the phase goal text is not in user-story format (`gsd-tools query user-story.validate` returns `false`). This verification proceeds as standard goal-backward verification against ROADMAP Success Criteria and PLAN must-haves, as before. Informational only — does not affect the functional verdict.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can register a sale by product code with quantity; stock decreases and the sale is saved to history | VERIFIED | Unchanged since prior verification. `app/services/sales.py::register_sale` writes N `sale` ops (`qty_delta=-qty`) + a `Sale` header in one transaction; `test_stock_decrements_for_basket_sale` passes. **Plus (new):** the per-line code-lookup autofill (`GET /sales/lookup`) that makes entering a code by hand practical is now confirmed working for every case, not just when a price is empty — see gap-closure evidence below |
| 2 | Operator can override the sale price on any sale line | VERIFIED | Unchanged. `register_sale` requires an entered price, stores it as `unit_price_cents`; `test_price_override_uses_entered_price` passes |
| 3 | Operator can create and edit customer profiles and link a sale to a customer | VERIFIED | Unchanged. `app/services/customers.py` CRUD + `app/routes/sales.py` customer routes; `test_web_sale_links_selected_customer` passes; human-confirmed in 04-UAT.md Test 4 (pass) |
| 4 | Selling more than is in stock triggers a warning with explicit confirm-to-proceed | VERIFIED | Unchanged. Aggregate oversell check, zero writes until `confirm=="1"`; `test_oversell_blocks_without_confirm`, `test_oversell_confirm_writes_negative_stock` pass; human-confirmed in 04-UAT.md Test 3 (pass) |
| 5 | Each sale line snapshots unit cost and sale price at sale time, and a customer's purchase history shows what/when/at what price | VERIFIED | Unchanged. `unit_cost_cents`/`unit_price_cents` frozen at INSERT; `test_snapshot_frozen_after_price_change`, `test_purchase_history_frozen` pass |

**Score:** 5/5 truths verified

### Gap Closure Verification (SAL-01 — `/sales/lookup` bracketed-param binding)

This is the specific item this re-verification exists to confirm. Verified directly in the current codebase, not from SUMMARY.md claims:

| Check | Method | Result |
|-------|--------|--------|
| Route declares aliased query params | Read `app/routes/sales.py` lines 71-79 | `code: str = Query("", alias="code[]")`, `name: str = Query("", alias="name[]")`, `price: str = Query("", alias="price[]")` — confirmed present verbatim |
| Real DOM sends bracketed keys | Read `app/templates/partials/sale_row.html` lines 15, 27, 34 | `name="code[]"`, `name="name[]"`, `name="price[]"` with `hx-include="closest tr"` on the code input (line 19) — confirms the route now binds the exact keys the browser sends |
| Regression test: fill-when-empty | `uv run pytest tests/test_sales.py -k lookup -q` | `test_web_sale_lookup_prefills_price` — sends `code[]`/`name[]`/`price[]`, asserts 200 + name present + `hx-swap-oob="true"` present. PASSED |
| Regression test: no-clobber-when-typed (exact UAT Test 2 reproduction) | Same run | `test_web_sale_lookup_bracketed_params_price_prefilled_no_clobber` — sends `price[]="15,00"`, asserts 200 + name present + `hx-swap-oob="true"` absent. PASSED |
| Full suite, no regressions | `uv run pytest -q` | 149 passed (148 prior + 1 new regression test), 0 failed |
| Scope of change since prior verification | `git diff --stat` against the UAT commit (`fd28bfa`) | Only `app/routes/sales.py` (+4/-4) and `tests/test_sales.py` (+32/-2) changed — confirms no unrelated drift, the fix is isolated to the diagnosed root cause |
| Lint clean | `uv run ruff check app/routes/sales.py tests/test_sales.py` and full phase-04 file set | All checks passed (pre-existing `I001` import-order finding in `tests/test_sales.py`/`test_customers.py` confirmed already logged in `deferred-items.md` from Plan 04-01, unrelated to this fix) |

**Conclusion:** The root cause (bare `code`/`name`/`price` query param declarations never binding the bracketed `code[]`/`name[]`/`price[]` keys the real basket row sends via `hx-include="closest tr"`) is fixed with an explicit `Query(alias=...)` on all three params, mirroring the existing pattern already used by the sibling `POST /sales` route. This was previously misdiagnosed by the human tester as a timing/race condition ("type price, then quickly type code before debounce fires") but the debug session confirmed it was an unconditional, deterministic binding failure — code lookup never worked, regardless of timing. Because the fix and its verification are both purely HTTP-request-shape-based (not timing-dependent), the two new regression tests fully close this gap without requiring a further browser-timing check. No new human-verification item is introduced by this fix.

### Required Artifacts

No artifacts changed shape since the prior verification's artifact table (all 13 artifacts previously verified remain unchanged) except:

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/routes/sales.py` | `sale_lookup()` binds bracketed `code[]`/`name[]`/`price[]` via `Query(alias=...)` | VERIFIED | Confirmed at lines 71-79; `Query` added to the `fastapi` import (line 6) |
| `tests/test_sales.py` | Regression coverage for both bracketed-key lookup paths | VERIFIED | `test_web_sale_lookup_prefills_price` (updated) + `test_web_sale_lookup_bracketed_params_price_prefilled_no_clobber` (new), both present and passing |

All other Phase 4 artifacts (`app/models.py`, `app/services/ledger.py`, `alembic/versions/0004_sales_customers.py`, `app/services/sales.py`, `app/services/customers.py`, `app/routes/customers.py`, and all `app/templates/partials/*` / `pages/*` sale/customer templates) are unchanged since the prior VERIFICATION.md (confirmed via `git diff --stat` showing zero changes to any file outside `app/routes/sales.py` and `tests/test_sales.py`) and remain VERIFIED by inheritance from that prior full check.

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/templates/partials/sale_row.html` (code input) | `app/routes/sales.py::sale_lookup` | `hx-get="/sales/lookup"` + `hx-include="closest tr"` sending `code[]`/`name[]`/`price[]` | WIRED (was previously NOT_WIRED for real DOM requests — this is the closed gap) | Route now declares matching `Query(alias=...)` for all three; confirmed by regression tests using the literal bracketed param shape |
| All other key links from the prior verification (`register_sale`↔`record_operation`, `POST /sales`↔`sale_form.html`, oversell warn/confirm cycle, customer picker/search/create, `purchase_history` join) | — | — | WIRED (unchanged) | No files in these paths changed since prior verification; carried forward |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full phase+project test suite | `uv run pytest -q` | 149 passed, 0 failed | PASS |
| Bracketed-key lookup regression tests (both new/updated) | `uv run pytest tests/test_sales.py -k lookup -q` | 2 passed | PASS |
| Ruff clean on gap-closure files | `uv run ruff check app/routes/sales.py tests/test_sales.py` | 1 pre-existing, already-logged `I001` unrelated to this fix; 0 new findings | PASS |
| Ruff clean on full phase-04 core file set | `uv run ruff check app/services/sales.py app/services/customers.py app/routes/sales.py app/routes/customers.py app/models.py app/services/ledger.py alembic/versions/0004_sales_customers.py` | All checks passed | PASS |
| No unrelated drift since prior verification | `git diff --stat fd28bfa..HEAD -- app tests` | Only `app/routes/sales.py` and `tests/test_sales.py` changed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SAL-01 | 04-01, 04-02, 04-06 (gap closure) | Register a sale by code/qty; stock decreases, saved to history | SATISFIED | `register_sale`, `record_operation` sale ops, `test_stock_decrements_for_basket_sale`; per-line code-lookup autofill now fixed and regression-tested (see Gap Closure Verification above); REQUIREMENTS.md shows `[x]` and "Complete" |
| SAL-02 | 04-02 | Sale price can differ from standard price per line | SATISFIED | Unchanged; `test_price_override_uses_entered_price` |
| SAL-03 | 04-05 | Sale can optionally be linked to a customer | SATISFIED | REQUIREMENTS.md now shows `[x]` and "Complete" — the documentation-staleness gap noted in the prior VERIFICATION.md has been resolved |
| SAL-04 | 04-03 | Warn when selling more than in stock | SATISFIED | Unchanged; 3 oversell tests pass; human-confirmed in 04-UAT.md Test 3 |
| SAL-05 | 04-01, 04-02 | Snapshot unit cost + sale price at sale time | SATISFIED | Unchanged; `test_snapshot_frozen_after_price_change` |
| CST-01 | 04-04 | Create/edit customer profiles | SATISFIED | Unchanged; CRUD tests pass |
| CST-02 | 04-04 | View customer purchase history (what/when/price) | SATISFIED | Unchanged; `test_purchase_history_frozen` |

No orphaned requirements — all 7 phase-declared requirement IDs (SAL-01..05, CST-01, CST-02) appear in REQUIREMENTS.md's traceability table mapped to Phase 4, all marked `[x]` / "Complete".

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers found in `app/routes/sales.py`, `app/services/sales.py`, or `app/templates/partials/sale_row.html` | — | None |

No new anti-patterns introduced by plan 04-06. All 6 code-review findings from `04-REVIEW.md`/`04-REVIEW-FIX.md` remain fixed (unchanged since prior verification).

### Human Verification Required

None. The 4 items flagged in the prior verification were carried through a real UAT session (`04-UAT.md`): 3 passed (basket-row focus, oversell warn/confirm cycle, customer picker/quick-create), and 1 failed (the `/sales/lookup` autofill gap, SAL-01). That failure has now been root-caused, fixed, and closed with deterministic regression tests that reproduce the literal browser request shape — the failure was never actually a browser-timing race (that was the tester's working hypothesis going in), it was a static query-param binding mismatch, so no further browser-dependent confirmation is required to close it.

### Gaps Summary

No gaps. All 5 ROADMAP Success Criteria verified, all 7 phase requirements (SAL-01..05, CST-01, CST-02) satisfied and marked complete in REQUIREMENTS.md, full test suite green (149/149) with 2 new regression tests directly reproducing the closed UAT gap, ruff clean on all phase-04 core files, no anti-patterns, no orphaned requirements, and no outstanding human-verification items (the prior UAT round already exercised all 4 human-only behaviors, with the one failure now fixed and proven via deterministic tests rather than requiring a second browser round).

---

*Verified: 2026-07-09T20:05:49Z*
*Verifier: Claude (gsd-verifier)*
