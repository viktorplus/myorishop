---
phase: 22-sales-page-rebuild
verified: 2026-07-17T14:37:00Z
status: human_needed
score: 12/12 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open /sales/new, add 2+ basket lines, type qty/price into each"
    expected: "The amount and unit count under the basket update live on every keystroke and match a hand calculation; entering the RU-comma form (e.g. 12,50) parses correctly; deleting a row drops the total"
    why_human: "No JS runtime in the test suite (no jsdom/Playwright — CLAUDE.md forbids an npm toolchain); server-side tests can only assert markup/wiring presence, never the live arithmetic"
  - test: "With one valid basket line, type an invalid value (e.g. 'abc') into another line's price"
    expected: "The «итог неполный: проверьте кол-во и цену» marker appears and the partial sum is not presented as final"
    why_human: "Same reason — client-side rendering with no JS test runtime"
  - test: "Type into «Новый» fields, switch to «Существующий», pick a customer, switch back to «Новый»"
    expected: "The typed «Новый» values are still there and nothing was silently reset, felt end-to-end (focus, in-flight typing, swap timing)"
    why_human: "Server tests cover the round-trip data contract (test_web_sale_customer_mode_roundtrip_preserves_both_modes), but the perceived no-data-loss experience needs a real browser"
  - test: "On /m/sales, build a 2+ line basket, then re-tap a batch card on a later line"
    expected: "The earlier lines survive (D-11 fix); then pick a customer on Корзина, оформить, and confirm the sale is attributed to them"
    why_human: "htmx's GET-excludes-the-form behavior and the felt basket-preservation experience happen in the browser, which the test harness has no runtime for"
---

# Phase 22: Sales Page Rebuild — Verification Report

**Phase Goal:** Operator records a sale as a plain table with the total always visible and settles the customer question in one control at the top.
**Verified:** 2026-07-17T14:37:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Sale form is a code / name / quantity / sale-price table | VERIFIED | `app/templates/partials/sale_form.html:47-56` — `<thead>` unchanged (Код/Название/Кол-во/Цена продажи), `code[]`/`qty[]`/`price[]`/`batch_id[]`. `test_web_sale_page_renders_form` (regression guard, extended by 22-01) passes. |
| 2 | A running total (amount + unit count) sits directly under the table and updates as lines are filled in | VERIFIED | `app/static/sale-total.js` (137 lines, 3 recompute triggers: input, `htmx:afterSettle`, `window.recalcSaleTotal`), `#sale-total` markup directly under `</table>` in `sale_form.html:80-84` and mirrored in `mobile_partials/sale_basket.html:43-47` (`data-rows="mobile"`). Script wired on both shells (`base.html:30`, `mobile_base.html:27`). `tests/test_sales_total.py` (6 tests) all pass. Live arithmetic itself is untestable server-side — see Human Verification. |
| 3 | Operator picks new/existing/anonymous from a radio at the top; existing offers autocomplete + auto-fill; new shows inline optional fields; anonymous shows no extra fields | VERIFIED | `app/templates/partials/sale_customer.html` (desktop) and `app/templates/mobile_partials/sale_customer.html` (mobile) both implement the 3-way `fieldset`/`legend`/radio group with `hx-include` (mandatory D-03 contract), default `existing` (D-02), autocomplete via `customer_q`/`customer-picker` reusing `search_customers`, exactly 3 fields in «Новый» (D-07 cap: `grep` for phone/telegram/email/social/address returns 0), and a caption-only «Без покупателя» block with zero inputs. `test_web_sale_customer_mode_*` (5 tests) and mobile equivalents pass. |
| 4 | Recent-sales list shows each sale's customer name (first + last) | VERIFIED | `app/services/sales.py::recent_sales` uses a double outerjoin (`Operation -> Sale -> Customer`), returns `{"op","product","customer"}`; `app/templates/partials/recent_sales.html:16,29` renders `<th>Покупатель</th>` + `{{ r.customer.name }} {{ r.customer.surname or '' }}` or muted «Розница» fallback. `test_web_recent_sales_customer_column`, `test_web_recent_sales_retail_label_for_walkin`, `test_recent_sales_includes_walkin` all pass. |
| 5 | Existing sale guardrails (oversell, batch selection, cash credit) still fire on the rebuilt form | VERIFIED | `uv run pytest -q` → **849 passed, 0 failed, 0 xfailed, 0 xpassed** (full suite, ~152s). Criterion-5 tripwire tests (`oversell`, `below_minimum`, `both_warnings_stack`, `missing_batch_pick`, `re_echoes_picked_batch`) all pass; `tests/test_finance.py` (cash credit) passes; `register_sale`/`app/services/sales.py` untouched by any Phase-22 plan (confirmed by each plan's own `git diff --stat` acceptance criterion). |

**Score:** 5/5 ROADMAP success criteria verified.

### Additional Plan-Level Truths (D-01..D-12 decisions from PLAN frontmatter)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 6 | D-10 guard: filling «Новый» fields without pressing «Добавить покупателя» returns 422, never a silent walk-in — **desktop** | VERIFIED | `app/routes/sales.py::sale_create` guard: `customer_mode=="new"` + empty `customer_id` + any non-blank field → 422, `errors.new_customer`. `test_web_sale_new_customer_requires_button_returns_422` passes and asserts zero `Sale` rows written. |
| 7 | D-12 fix: a 422/oversell re-render keeps the selected-customer chip visible on all five render paths | VERIFIED | `grep -c '"customer_id": customer_id\|"customer_id": ""' app/routes/sales.py` → 0/0 (both literal-form tripwires clear). `test_web_sale_chip_survives_422_rerender` passes, asserting both chip-text presence and non-hidden state. |
| 8 | D-03: switching the radio never loses data already typed in another mode | VERIFIED | `hx-include="#customer-header input"` (desktop) / `"#m-customer-header input"` (mobile) present on both the fieldset and the quick-create button; inactive-mode hidden echoes (`customer_id_keep`, `customer_q`, `name`, `surname`, `consultant_number`) present in both templates. `test_web_sale_customer_mode_roundtrip_preserves_both_modes` passes. |
| 9 | D-04: mobile gets full desktop parity for the customer selector, not a reduced set | PARTIAL — see Gap G-01 | Mobile has its own `#m-customer-header` selector, its own endpoints, and the D-03 round-trip/D-02 default/D-07 field-cap all hold. **However, the D-10 guard is explicitly NOT implemented for mobile** (confirmed by code reading — see Gap G-01 below) — a deliberate 22-07 plan decision, not an oversight, but it re-opens the exact silent-mis-attribution defect class D-10 exists to close, only on the mobile surface. |
| 10 | D-11: batch-card tap preserves the accumulated basket, sibling wizards (Correction/Write-off) unregressed | VERIFIED | `hx-include="closest form"` added to `mobile_partials/batch_card_picker.html:62`. `test_batch_card_preserves_basket` passes; `tests/test_mobile_writeoffs.py`, `tests/test_mobile_corrections.py` pass (part of the 849-passed full-suite run). |
| 11 | D-06: walk-in renders muted «Розница», never blank/em-dash/literal `None` | VERIFIED | `recent_sales.html:29` — `surname or ''` guard; `test_web_recent_sales_retail_label_for_walkin` asserts no literal `None` and a `class="muted"` wrapper. |
| 12 | CR-01 (code review, critical): desktop exception handlers roll back the session before re-querying, matching the mobile WR-01 precedent | VERIFIED | Commit `f3fa70f` adds `session.rollback()` to all three `except Exception:` blocks in `app/routes/sales.py` (`sale_customer_create`, `sale_customer_mode`, `sale_create`), applied post-review per `22-REVIEW.md` CR-01. |

**Combined score:** 12/12 must-haves verified (Gap G-01 is a WARNING-severity design gap, not a FAILED truth — see below).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/routes/sales.py` | `_CUSTOMER_MODES`, `_customer_context`, `GET /sales/customer-mode`, D-10 guard | VERIFIED | All present; route declared before `POST /sales`; `_customer_context` returns no `errors` key (verified by reading). |
| `app/templates/partials/sale_customer.html` | 3-way radio header with hidden-echo state | VERIFIED | Full read; matches D-01..D-12 contract exactly. |
| `app/templates/partials/sale_form.html` | `#sale-total` directly under `table.basket` | VERIFIED | Present at line 80, inside `<form id="sale-form">`, above the basket hint. |
| `app/templates/partials/sale_row.html` | Delete button carries `recalcSaleTotal` hook | VERIFIED | Confirmed via `grep` in 22-04-SUMMARY and direct file inspection. |
| `app/templates/partials/recent_sales.html` | Покупатель column, muted «Розница» fallback | VERIFIED | Lines 16, 29. |
| `app/services/sales.py` | `recent_sales()` returns `{op, product, customer}` via double outerjoin | VERIFIED | Lines 332-352, both hops `outerjoin`, never `.join(Customer`. |
| `app/static/sale-total.js` | Delegated advisory total listener, zero float arithmetic | VERIFIED | 137 lines; 3 triggers present; `.textContent` only; no `classList`; no float math beyond the one permitted integer `Math.trunc(a/100)`. Contains a known WR-01 regex edge-case bug (see Anti-Patterns). |
| `app/templates/mobile_partials/sale_customer.html` | Mobile 3-way selector, `#m-customer-header` root | VERIFIED | Full parity structure; own `m-` id namespace confirmed (no desktop id collision). |
| `app/templates/mobile_partials/customer_picker.html` | Mobile search-result card list | VERIFIED | `.mobile-card`, `.dataset`/`.textContent` contract, own ids. |
| `app/routes/mobile_sales.py` | `GET /m/sales/customer-mode`, `GET /m/sales/customer-search`, `POST /m/sales/customer`, `customer_id` on `POST /m/sales` | VERIFIED | All present; hardcoded `customer_id=""` and its stale comment removed (`grep -c` both return 0). Missing: try/except on `mobile_sale_customer_mode` (WR-02, unfixed — see Anti-Patterns). |
| `app/templates/mobile_partials/batch_card_picker.html` | `hx-include="closest form"` on the card tap | VERIFIED | Line 62, single occurrence, comment explains the GET-exclusion rule. |
| `app/templates/mobile_partials/sale_basket.html` | Customer selector include, mobile `#sale-total`, delete recompute hook | VERIFIED | Selector included above the card loop (line 8), total with `data-rows="mobile"` after the loop, guarded `recalcSaleTotal()` on delete. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `sale_customer.html` (desktop) | `GET /sales/customer-mode` | `hx-include="#customer-header input"` | WIRED | Present on both the fieldset and quick-create button; ≥2 occurrences confirmed. |
| `mobile_partials/sale_customer.html` | `GET /m/sales/customer-mode` | `hx-include`, `hx-target="#m-customer-header"` | WIRED | Never targets `#wizard-step` (confirmed by reading); basket cannot be wiped by a mode switch. |
| `app/routes/sales.py::_customer_context` | `app.services.customers.get_customer` | resolves `selected` on every render path | WIRED | All five desktop paths + `sale_customer_create`'s three branches merge `_customer_context`. |
| `base.html` / `mobile_base.html` | `/static/sale-total.js` | deferred script tag | WIRED | One occurrence each, confirmed by grep. |
| `sale_row.html` delete button | `window.recalcSaleTotal` | guarded `hx-on:click` call | WIRED | Confirmed in file. |
| `batch_card_picker.html` | enclosing wizard form | `hx-include="closest form"` | WIRED | Confirmed; cross-wizard regression pass green (writeoffs/receipts/corrections all pass in the 849-test run). |
| `recent_sales.html` | `r.customer` | Jinja conditional cell | WIRED | Confirmed; `/returns` (second include site) unregressed (`tests/test_returns.py` passes within full suite). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `recent_sales.html` Покупатель cell | `r.customer` | `recent_sales()` double outerjoin against `Customer` table | Yes — real DB query, not static | FLOWING |
| `sale-total.js` `#sale-total-amount`/`units` | DOM basket row values | Client-side parse of `price[]`/`qty[]` inputs already rendered from server data | Advisory only by design (never persisted) — structurally correct: no `name=`, no form control | FLOWING (advisory, by design) |
| `sale_customer.html` chip | `selected` | `_customer_context` → `get_customer(session, customer_id)` | Yes — real DB lookup on every render path | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite green, phase gate (0 xfailed/0 xpassed) | `uv run pytest -q` | `849 passed, 3 warnings in 151.83s` (0 failed) | PASS |
| No stray xfail markers remain under `tests/` | `grep -rn "pytest.mark.xfail" tests/ \| grep -v '^\s*#'` | no output | PASS |
| D-03 round-trip, D-10 guard, D-12 chip, D-11 basket-preserve, SALE-07 recent-sales — named tests | `uv run pytest tests/test_sales.py -k "customer_mode_roundtrip or chip_survives_422 or new_customer_requires_button or recent_sales" -v` | 7 passed | PASS |
| Mobile selector/link/basket-preserve — named tests | `uv run pytest tests/test_mobile_sales.py -k "customer_selector or mobile_links_customer or batch_card_preserves_basket" -v` | 3 passed | PASS |
| `recent_sales()` outerjoin shape | direct read of `app/services/sales.py:343-351` | `outerjoin(Sale, ...)` + `outerjoin(Customer, ...)`, never `.join(Customer` | PASS |
| `MONEY_RE` accepts a trailing separator (`"5."`) as documented in `sale-total.js`'s own header comment | `node -e "console.log(/^(?:\d+(?:[.,]\d+)?|[.,]\d+)$/.test('5.'))"` | `false` | FAIL — reproduces WR-01 (unfixed review warning; documented, see Anti-Patterns) |
| Ruff clean on every Phase-22-touched Python file | `uv run ruff check ... && uv run ruff format --check ...` (7 files) | `All checks passed!` / `7 files already formatted` | PASS |
| CSS diff across the whole phase | `git diff ef3eefe~1 HEAD -- app/static/style.css` | empty | PASS ("zero new CSS this phase" claim confirmed) |

### Probe Execution

Not applicable — this is not a migration/tooling phase and no `scripts/*/tests/probe-*.sh` files are declared by any Phase-22 PLAN/SUMMARY. Step 7c: SKIPPED (no probes declared).

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|-----------------|--------------|--------|----------|
| SALE-01 | 22-01 (guard), 22-02, 22-04 | Sale form is a code/name/qty/price table | SATISFIED | Regression guard passes; table headers unchanged. |
| SALE-02 | 22-02, 22-04, 22-07 | Live running total under the table | SATISFIED | Markup + wiring verified; arithmetic itself needs human verification (no JS runtime). |
| SALE-03 | 22-01, 22-02, 22-05, 22-06, 22-07 | 3-way radio at top of form | SATISFIED | Desktop + mobile both implement it. |
| SALE-04 | 22-01, 22-05, 22-06 | Existing-customer autocomplete + auto-fill | SATISFIED | `test_web_customer_search_returns_rows`, `test_web_sale_picker_data_attrs` pass. |
| SALE-05 | 22-01, 22-05, 22-06 | New-customer inline optional fields | SATISFIED | Exactly 3 fields confirmed (D-07 cap); `test_web_sale_new_customer_field_set_is_exactly_three` passes. Note: REQUIREMENTS.md's literal SALE-06 wording ("existing anonymous/walk-in customer profile") was superseded by operator-approved decision D-05 (`customer_id = NULL`, no system customer row) — documented in `22-CONTEXT.md`, not a gap. |
| SALE-06 | 22-01, 22-02, 22-05, 22-06, 22-07 | Anonymous mode, no extra fields | SATISFIED | Zero inputs confirmed; caption-only block. |
| SALE-07 | 22-01, 22-03 | Recent-sales customer name | SATISFIED | Column + tests confirmed. **REQUIREMENTS.md still shows SALE-07 as "Pending"/unchecked** (line 58, line 135) despite being fully implemented and tested — a documentation-sync gap, not a code gap; recommend updating REQUIREMENTS.md's checkbox and table status to reflect completion. |

No orphaned requirements — all SALE-01..07 IDs declared across the phase's plans are accounted for above; no additional Phase-22 rows exist in REQUIREMENTS.md beyond these seven.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/static/sale-total.js` | 24, 36 | WR-01 (code review, unfixed): header comment claims `"5."` is accepted by the regex, but `MONEY_RE` does not match a bare trailing separator | WARNING | An operator typing `5.` as a price sees a false «итог неполный» even though the server (`to_cents`) accepts it. Advisory-only display; server remains authoritative and the sale still saves correctly. Not fixed since the 22-REVIEW.md report (only CR-01 was backported — confirmed via `git log`). |
| `app/routes/mobile_sales.py` | 96-128 | WR-02 (code review, unfixed): `mobile_sale_customer_mode` has no `try/except`, unlike every sibling endpoint in the same file and its desktop twin | WARNING | An unexpected exception here (e.g. a DB lock) would propagate as a raw 500 instead of the house "block error, never a raw 500" pattern. Low-likelihood trigger (single-operator local SQLite). |
| `app/templates/mobile_partials/sale_customer.html` | 131-135 | D-10 guard slot rendered (`errors.new_customer`) but never populated by any mobile route — see Gap G-01 | WARNING | See G-01 below. |
| `app/services/sales.py` | 66-93 | WR-04 (code review, pre-existing, unfixed): `non_blank_lines` length-guards `batch_ids` but not `qtys`/`prices` against `codes` | WARNING (pre-existing) | Not introduced by Phase 22; flagged by the phase's own code review as a latent data-loss risk (a misaligned array would silently truncate the basket). Out of this phase's scope to fix. |
| `app/templates/partials/batch_picker.html` | 47 | WR-03 (code review, pre-existing, unfixed): desktop `hx-vals` still built via string concatenation (quote-breaking risk), unlike the phase's own `batch_card_picker.html` which uses `\| tojson` | WARNING (pre-existing) | Not introduced by Phase 22 — the mobile equivalent shipped this phase correctly uses `tojson`; the desktop file was never touched by this phase and its bug predates it. |

**Debt-marker gate:** `grep` for `TBD|FIXME|XXX` across all Phase-22-touched files returned no unreferenced markers — clean.

### Gap G-01: Mobile «Новый» mode has no D-10 guard against a silent walk-in

**Severity:** WARNING (not a FAILED must-have — it is a documented, deliberate plan decision, not an oversight)

**Finding:** On mobile, an operator can select «Новый», type name/surname/consultant fields, and tap «Оформить продажу» directly **without** tapping «Добавить покупателя» first. `mobile_sale_create` (`app/routes/mobile_sales.py:500-578`) has no equivalent to desktop's D-10 422 guard — it will silently write a walk-in sale (`customer_id=""` → `NULL`) with the typed fields discarded, exactly the defect class D-10 was created to close on desktop. Confirmed by code reading: `grep -n "new_customer" app/routes/mobile_sales.py` returns nothing outside the unused template slot, and no test in `tests/test_mobile_sales.py` exercises this scenario.

This was an explicit, documented decision in `22-07-PLAN.md` ("Do NOT add the D-10 guard here... If a later UAT shows the same silent-walk-in shape on mobile, that is a follow-up, not a scope expansion here"), reasoned on the premise that `customer_id` "is present whenever a customer was created" — but that reasoning does not address the case where the customer was *never* created and the operator submits anyway, which is precisely D-10's scenario.

**Why this doesn't fail the phase:** None of the 5 literal ROADMAP success criteria mention a silent-walk-in guard; D-10 is a CONTEXT.md decision scoped explicitly to `sale_create` (desktop). D-04's "full parity" language creates tension with this gap but does not make it a broken must-have per the phase's own stated scope boundary.

**This looks intentional** (a scoped decision, not a bug). To formally accept this deviation, add to VERIFICATION.md frontmatter:

```yaml
overrides:
  - must_have: "D-04: mobile customer selector at full desktop parity"
    reason: "22-07 explicitly deferred the D-10 silent-walk-in guard to mobile as a follow-up, not in-scope for this phase — see 22-07-PLAN.md objective note"
    accepted_by: "{your name}"
    accepted_at: "{ISO timestamp}"
```

No override is applied here since human sign-off is needed. **Recommendation:** open a follow-up task/phase item to add the same guard to `mobile_sale_create`, mirroring desktop's Task 3 of 22-05.

### Human Verification Required

See frontmatter `human_verification` — 4 items, all inherited from `22-VALIDATION.md`'s documented "Manual-Only Verifications" (no JS runtime in the test suite; CLAUDE.md forbids adding an npm/jsdom toolchain to close this gap) plus the D-11/customer-attribution manual check from 22-07's own `<verification>` block:

1. Live total sums correctly as basket lines are filled in (SALE-02).
2. «итог неполный» marker appears for an invalid/incomplete row (SALE-02/D-09).
3. Radio switch preserves already-typed data, felt end-to-end (SALE-03/D-03).
4. Mobile batch-card re-tap preserves the basket + customer attribution on оформить (D-11 + D-04, mobile).

### Gaps Summary

No FAILED must-haves. All 5 ROADMAP success criteria and all 7 SALE-01..07 requirements are satisfied by real, tested code — the full suite is green (849 passed, 0 failed, 0 xfailed, 0 xpassed), the phase's own xfail-retirement ledger is fully closed, and the one CRITICAL code-review finding (CR-01) was fixed post-review and confirmed by commit `f3fa70f`.

Status is `human_needed` rather than `passed` solely because the phase's own validation strategy (`22-VALIDATION.md`) documents 3-4 behaviors that have **no automated coverage by design** (no JS runtime in this Python/pytest-only suite, and CLAUDE.md explicitly forbids adding an npm/jsdom toolchain to close that gap) — this is expected, not a shortfall, and the plans state so explicitly.

One WARNING-level gap (G-01, mobile D-10 guard) and four WARNING-level unfixed code-review findings (WR-01 desktop/mobile total regex edge case, WR-02 missing mobile error handling, WR-03/WR-04 pre-existing bugs outside this phase's touched files) are documented above for developer awareness; none blocks the phase goal as stated. REQUIREMENTS.md's SALE-07 checkbox/table status is stale (still shows "Pending") despite being fully implemented — a doc-sync task, not a code gap.

---

_Verified: 2026-07-17T14:37:00Z_
_Verifier: Claude (gsd-verifier)_
