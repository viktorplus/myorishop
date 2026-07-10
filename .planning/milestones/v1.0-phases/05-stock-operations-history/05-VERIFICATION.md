---
phase: 05-stock-operations-history
verified: 2026-07-10T15:10:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/4
  gaps_closed:
    - "History is paginated (50/page + «Показать ещё») and never loads the whole ledger unbounded, and the operator can reliably page through it (OPS-04, D-15 must-have from 05-05-PLAN.md) — new CR-01 (pagination control destroyed by first filter interaction, due to `#load-more` being nested inside `#history-tbody`) closed by 05-09: `#load-more` moved into a standalone `<tfoot>` row, a DOM sibling of `#history-tbody`, no longer touched by the filter selects' default innerHTML swap or the button's own beforeend swap. Confirmed independently in this pass by reading the actual current `app/routes/history.py`, `app/templates/partials/history_rows.html`, `app/templates/partials/history_load_more.html`, `app/templates/partials/history_response.html`, and `app/templates/pages/history.html` — not by trusting 05-09-SUMMARY.md's claims — and by an independent pytest run of `tests/test_history.py` (5/5 passed, including the new `test_web_history_load_more_survives_filter_change` regression test seeded with 51 filtered rows) plus the full 167-test regression suite (up from the 166-passed baseline, as predicted)."
  gaps_remaining: []
  regressions: []
---

# Phase 5: Stock Operations & History Verification Report

**Phase Goal:** Operator can handle every non-sale stock movement (write-off, return, correction) and see the complete operation trail
**Verified:** 2026-07-10T15:10:00Z
**Status:** passed
**Re-verification:** Yes — fourth pass. First pass found OPS-01 unreachable via nav (closed by 05-06) plus warning-level reliability issues (closed by 05-07). Second pass found CR-01 (old), a chrome-less-fragment bug on `/history` (closed by 05-08). Third pass confirmed old CR-01 closed but found a new, more severe pagination-destruction defect (new CR-01) — the `#load-more` control nested inside the filter selects' innerHTML swap target, permanently destroyed after the first filter interaction. This fourth pass independently confirms new CR-01 is now closed by plan 05-09.

## Process Note

This is the fourth verification pass for Phase 5. All three prior gap-closure rounds are independently reconfirmed still-fixed in this pass by direct code inspection (not by citing prior SUMMARY.md files): OPS-01's nav link (05-06), the returns rollback/422 fixes (05-07), and the old `/history` chrome-decision bug (05-08). This pass's focus was the one remaining gap from the third verification pass — the new CR-01 pagination-destruction defect — closed by plan 05-09's structural fix (move `#load-more` into its own `<tfoot>`, a DOM sibling of `#history-tbody` rather than a descendant). Every file plan 05-09 claims to have created or modified was read directly from disk in this pass: `app/routes/history.py`, `app/templates/partials/history_rows.html`, `app/templates/partials/history_load_more.html` (new), `app/templates/partials/history_response.html` (new), and `app/templates/pages/history.html`. The full pytest suite was run independently by this verifier (not copy-pasted from 05-09-SUMMARY.md), confirming 167 passed (up from the 166-passed baseline recorded in the third-pass verification, exactly as the plan predicted for its one new test).

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can write off stock with a reason, and stock decreases accordingly (OPS-01) | ✓ VERIFIED | Regression-checked: `app/templates/base.html:22` still links `/writeoff`. Untouched by 05-09. Full suite green. |
| 2 | Operator can register a return linked to the original sale, and stock increases accordingly (OPS-02) | ✓ VERIFIED | Regression-checked: `app/routes/returns.py:114` still calls `session.rollback()` before re-query. Untouched by 05-09. |
| 3 | Operator can correct stock quantity, and the adjustment is recorded as an operation rather than a direct edit (OPS-03) | ✓ VERIFIED | Regression-checked: `app/routes/corrections.py:80` still calls `session.rollback()`. Untouched by 05-09. `/corrections` still lacks a persistent top-nav entry (carried-over Warning, non-blocking, explicitly out of scope for 05-09). |
| 4 | Operator can browse the full operation history showing what happened, when, and how much — including paging reliably through more than 50 matching operations under any filter (OPS-04) | ✓ VERIFIED | Both CR-01 defects now confirmed closed by direct source inspection: (a) old CR-01 (chrome decision) — `app/routes/history.py:41-52`, `is_hx` branch unchanged; (b) new CR-01 (pagination destruction) — `#load-more` is now defined only in `app/templates/partials/history_load_more.html`, rendered inside `<tfoot>` in `app/templates/pages/history.html:23-27` as a **sibling** of `<tbody id="history-tbody">` (line 20-22), and via `app/templates/partials/history_response.html` (includes `history_rows.html` + oob-wrapped `history_load_more.html`) for every genuine HX response (`app/routes/history.py:50`). `history_rows.html` no longer contains `id="load-more"` (grep confirms 0 occurrences) or reads an `oob` variable. Because `#load-more` is a structural sibling rather than a descendant of `#history-tbody`, the filter selects' default innerHTML swap on that tbody (unchanged in `history_filters.html`, still no `hx-swap` attribute) can no longer touch or destroy it — the root cause identified in the third-pass verification is structurally eliminated, not merely worked around. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | `WRITEOFF_REASONS` + `OPERATION_TYPE_LABELS` constants | ✓ VERIFIED | Unchanged since last pass |
| `app/services/writeoffs.py` | `register_writeoff()` + `recent_writeoffs()` | ✓ VERIFIED | Unchanged |
| `app/routes/writeoffs.py` | `GET /writeoff`, `GET /writeoff/lookup`, `POST /writeoff` | ✓ VERIFIED | Unchanged, reachable via nav |
| `app/templates/base.html` | Nav entries for Phase 5 features | ⚠️ PARTIAL | «Списание»/«История» present; «Корректировка» still absent from persistent nav (non-blocking Warning, carried over, out of scope for 05-09) |
| `app/services/returns.py` | `returnable_qty()` + `register_return()` | ✓ VERIFIED | Unchanged |
| `app/routes/returns.py` | `GET /returns`, `POST /returns` | ✓ VERIFIED | 422 + rollback-before-requery both still present |
| `app/services/corrections.py` | `register_correction()` + `lookup_prefill()` | ✓ VERIFIED | Unchanged |
| `app/routes/corrections.py` | `GET /corrections`, `POST /corrections`; old `POST /ops` removed | ✓ VERIFIED | rollback-before-requery still present |
| `app/services/operations.py` | `history_view()` + `filter_products()` | ✓ VERIFIED | Unchanged by 05-09 (route/template-only fix); paginated, filtered, fetch-one-extra sentinel logic correct |
| `app/routes/history.py` | `GET /history` (full page + rows partial), correct chrome decision | ✓ VERIFIED | `is_hx` branch renders `partials/history_response.html` for HX requests (line 50), `pages/history.html` otherwise (line 52). `"oob": is_hx` context key removed (grep confirms 0 occurrences), consistent with `history_response.html`/`pages/history.html` each hardcoding `oob` internally now. |
| `app/templates/partials/history_rows.html` | Data rows only, no load-more, no `oob` var | ✓ VERIFIED | Read directly: rows loop + empty-state row only (lines 13-40); `grep -c 'id="load-more"'` = 0 |
| `app/templates/partials/history_load_more.html` | NEW — standalone `#load-more` control | ✓ VERIFIED | Read directly: `<tr id="load-more"{% if oob %} hx-swap-oob="true"{% endif %}>` wrapping a conditional `<button>` when `has_next`; `grep -c 'id="load-more"'` = 1 |
| `app/templates/partials/history_response.html` | NEW — combined HX response (rows + oob load-more) | ✓ VERIFIED | Read directly: `{% include "partials/history_rows.html" %}` then `{% with oob = True %}{% include "partials/history_load_more.html" %}{% endwith %}` |
| `app/templates/pages/history.html` | `<tfoot>` sibling of `<tbody>` housing `#load-more` | ✓ VERIFIED | Read directly: `<tbody id="history-tbody">` (line 20-22) includes only `history_rows.html`; `<tfoot>` (line 23-27, sibling, not descendant) includes `history_load_more.html` with `oob = False` |
| `tests/test_history.py` | Regression test proving `#load-more` survives filter change on >50-row set | ✓ VERIFIED | `test_web_history_load_more_survives_filter_change` (lines 106-136): seeds 51 writeoff ops, asserts `id="load-more"` absent from `<tbody>` region and present in `<tfoot>` region for a plain filtered GET, and present with `hx-swap-oob` in the genuine HX-Request filtered response. Independently run: PASSED. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/templates/base.html` / `home.html` | `/writeoff` | nav link | ✓ WIRED | Confirmed present |
| `app/routes/returns.py` | origin sale `Operation` | `session.get` → frozen copy, 422 on not-found | ✓ WIRED | Confirmed present |
| `app/routes/returns.py` / `corrections.py` / `writeoffs.py` | `session.rollback()` | except-block first statement | ✓ WIRED | Confirmed present in all three |
| `app/routes/history.py` | `pages/history.html` (full chrome) | `is_hx` branch | ✓ WIRED | Non-htmx request always renders full chrome — old CR-01 fix reconfirmed |
| `app/routes/history.py` | `partials/history_response.html` (HX responses) | `is_hx` branch, line 50 | ✓ WIRED | Genuine HX requests now get the combined rows+load-more response |
| `app/templates/partials/history_filters.html` `<select>` | `#history-tbody` | default (`innerHTML`) htmx swap | ✓ WIRED (now safe) | Same unchanged markup as before, but `#load-more` is no longer a descendant of `#history-tbody`, so the innerHTML swap can no longer destroy it — new CR-01 root cause structurally eliminated |
| `app/templates/partials/history_load_more.html` `#load-more` | `<tfoot>` in `pages/history.html` | structural sibling of `#history-tbody`, `hx-swap-oob="true"` | ✓ WIRED | Confirmed: `<tfoot>` (lines 23-27) is a sibling of `<tbody id="history-tbody">` (lines 20-22), both children of `<table>` |
| `app/templates/partials/history_load_more.html` button | `#history-tbody` | `hx-target="#history-tbody" hx-swap="beforeend"` | ✓ WIRED | Button click appends next page's rows to tbody; no longer repositions the control (WR-01 from 05-REVIEW.md resolved as a side effect — the control lives in `<tfoot>`, entirely outside the beforeend target's content) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `history_rows.html` | `rows` | `history_view()` → real DB query, paginated, correct `has_next` sentinel | Yes | ✓ FLOWING |
| `history_load_more.html` | `has_next`, `type_filter`, `product_id`, `page` | `history_view()` result, passed through route `context` unchanged | Yes | ✓ FLOWING |
| `writeoff_form.html` (recent list) | `writeoffs` | `recent_writeoffs()` → real query | Yes | ✓ FLOWING |
| `return_form.html` | `product`, `sold`, `remaining`, `unit_price_cents` | `_origin_context()` → real queries + frozen origin fields | Yes | ✓ FLOWING |
| `correction_form.html` | `current_qty` | `lookup_prefill()` → real `Product.quantity` read | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `tests/test_history.py` full module, independently run | `uv run pytest tests/test_history.py -v` | 5 passed (`test_history_pagination`, `test_web_history_rows`, `test_web_history_filters`, `test_web_history_filtered_reload_returns_full_chrome`, `test_web_history_load_more_survives_filter_change`) | ✓ PASS |
| Full regression suite, independently run | `uv run pytest -q` | **167 passed**, 2 warnings (pre-existing, unrelated to Phase 5 logic) — up from the 166-passed baseline, exactly as predicted by 05-09-PLAN.md | ✓ PASS |
| `app/routes/history.py` / `tests/test_history.py` lint/format clean | `uv run ruff check app/routes/history.py tests/test_history.py app/templates` / `uv run ruff format --check app/routes/history.py tests/test_history.py` | All checks passed; 2 files already formatted | ✓ PASS |
| All 10 plan acceptance-criteria greps, independently re-run | `grep -c` on each pattern listed in 05-09-PLAN.md's `<acceptance_criteria>` | All 10 match exactly (0/1/0 as specified) — see table below | ✓ PASS |
| Nav links / rollback fixes still present (OPS-01/02/03 regression) | `grep` on `base.html`, `returns.py`, `corrections.py` | All previously-confirmed patterns still present | ✓ PASS |
| New CR-01 (pagination destruction) — structural code inspection | Read `history_rows.html` (no `#load-more`, no `oob`), `history_load_more.html` (new, standalone control), `history_response.html` (new, combines both), `pages/history.html` (`<tfoot>` sibling of `<tbody>`) | Confirms `#load-more` is now structurally isolated as a DOM sibling, never a descendant of `#history-tbody` — the exact fix scope recommended in the third-pass verification | ✓ PASS — confirms new CR-01 is closed |

**Acceptance-criteria grep re-run detail:**

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| `id="load-more"` in `history_rows.html` | 0 | 0 | ✓ |
| `id="load-more"` in `history_load_more.html` | 1 | 1 | ✓ |
| `partials/history_rows.html` in `history_response.html` | 1 | 1 | ✓ |
| `partials/history_load_more.html` in `history_response.html` | 1 | 1 | ✓ |
| `<tfoot>` in `pages/history.html` | 1 | 1 | ✓ |
| `partials/history_load_more.html` in `pages/history.html` | 1 | 1 | ✓ |
| `partials/history_response.html` in `history.py` | 1 | 1 | ✓ |
| `partials/history_rows.html` in `history.py` | 0 | 0 | ✓ |
| `"oob": is_hx` in `history.py` | 0 | 0 | ✓ |
| `def test_web_history_load_more_survives_filter_change` in `test_history.py` | 1 | 1 | ✓ |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files exist in this repo; this project's verification gate is its pytest suite plus direct code/template inspection.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|--------------|--------|----------|
| OPS-01 | 05-01, 05-02, 05-06 | User can write off stock with a reason | ✓ SATISFIED | Regression-confirmed unchanged from prior pass |
| OPS-02 | 05-01, 05-03, 05-07 | User can register a return linked to the original sale; stock increases accordingly | ✓ SATISFIED | Regression-confirmed unchanged from prior pass |
| OPS-03 | 05-01, 05-04 | User can correct stock quantity (adjustment recorded as an operation, not a direct edit) | ✓ SATISFIED | Regression-confirmed unchanged from prior pass |
| OPS-04 | 05-01, 05-05, 05-08, 05-09 | User can view the full operation history (what, when, how much) | ✓ SATISFIED | Both CR-01 defects (chrome-decision, closed by 05-08; pagination-destruction, closed by 05-09) independently confirmed closed by direct source inspection and an independent test run in this pass |

No orphaned requirements — REQUIREMENTS.md maps exactly OPS-01..04 to Phase 5, matching all nine plans' `requirements:` frontmatter (05-06 → OPS-01, 05-07 → OPS-02, 05-08 → OPS-04, 05-09 → OPS-04).

**Documentation inconsistency (Info, carried over, unchanged):** REQUIREMENTS.md's traceability table (lines 93-96) still marks OPS-02/03/04 as "In Progress" even though the checkbox list above it (lines 33-36) marks all four complete. Cosmetic only, not touched by 05-09 (out of scope).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/templates/base.html` | nav | `/corrections` has no persistent top-nav entry, only reachable from `home.html` (and not reachable there with zero active products) | ⚠️ Warning | Carried over unchanged, non-blocking, explicitly out of scope for 05-09 per its plan text |
| `app/templates/partials/writeoff_rows.html:28-30` | — | No guard against `r.op.payload` being `None`, unlike `history_rows.html` | ℹ️ Info | Not currently reachable; latent risk, carried over |
| `app/services/operations.py:51-57` | — | `/history` product filter dropdown only lists active products | ℹ️ Info | Known limitation, carried over |
| Various (IN-01 through IN-08 in `05-REVIEW.md`) | — | Minor message-precision, dead-attribute, builtin-shadowing, duplicated-validation, UX-hint-reset issues | ℹ️ Info | Cosmetic/latent only, not blocking, carried over |

No `TBD`/`FIXME`/`XXX` debt markers found in any file touched by 05-09 (`app/templates/partials/history_rows.html`, `history_load_more.html`, `history_response.html`, `app/templates/pages/history.html`, `app/routes/history.py`, `tests/test_history.py`).

### Human Verification Required

None. The DOM restructuring (moving `#load-more` from a descendant of `#history-tbody` into a sibling `<tfoot>`) is a deterministic structural fix — htmx's oob-swap-before-main-swap ordering only causes destruction when the oob target is nested inside the main swap's target content, and this is no longer the case (verified by direct source inspection of all four templates plus the route). The new regression test exercises the exact real-browser request/response pair (a plain filtered page load and a genuine `HX-Request` filtered GET) against a 51-row seeded dataset and passes. A manual click-through (open `/history`, apply a filter matching >50 operations, click "Показать ещё" through multiple pages) remains a reasonable routine sanity check but is not required to establish confidence in this fix, consistent with the same reasoning applied when the defect was originally identified via structural analysis in the third-pass verification.

### Gaps Summary

No gaps. All four Phase 5 requirements (OPS-01 through OPS-04) are satisfied. The one remaining gap from the third verification pass — new CR-01, the `/history` pagination control destroyed by the first filter-select interaction — is now closed by plan 05-09's structural fix, independently confirmed in this pass by reading all five files 05-09 claims to have changed/created and by an independent pytest run (167 passed, up from the 166-passed baseline, matching the plan's own prediction exactly).

Two Info-level items and one Warning-level item remain open by design, unchanged and out of scope for this fix: `/corrections` lacking a persistent top-nav entry, the product filter dropdown listing only active products, and the various cosmetic/latent items catalogued in `05-REVIEW.md` (IN-01 through IN-08). None block Phase 5's goal achievement.

---

*Verified: 2026-07-10T15:10:00Z*
*Verifier: Claude (gsd-verifier)*
