---
phase: 05-stock-operations-history
verified: 2026-07-10T00:45:00Z
status: gaps_found
score: 3/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/4
  gaps_closed:
    - "Operator can write off stock with a reason, and stock decreases accordingly (OPS-01) — nav link to /writeoff added in base.html and home.html (05-06), confirmed by grep and by passing test_web_writeoff_reachable_from_nav"
  gaps_remaining: []
  regressions: []
gaps:
  - truth: "Operator can browse the full operation history showing what happened, when, and how much (OPS-04)"
    status: failed
    reason: >
      A newly-surfaced defect (05-REVIEW.md CR-01, confirmed independently in
      this verification pass) breaks ordinary browsing of /history. The route
      (app/routes/history.py:32-45) decides chrome vs. rows-only partial using
      `is_hx or is_filtered`, where `is_filtered = bool(type) or bool(product)`.
      Any plain, non-htmx top-level navigation that carries a type/product
      filter — exactly what happens when a browser reloads, bookmarks, or a
      user shares a URL that htmx's `hx-push-url` just wrote into the address
      bar after selecting a filter — receives a response containing only bare
      `<tr>` elements, with no enclosing `<table>`/`<tbody>`, no `<html>`/
      `<head>`/`<body>`, and no site nav. Verified empirically in this
      verification pass with a direct TestClient probe (no HX-Request header,
      `type=writeoff`): response is 200 with body starting `\n<tr>...`, and
      `"<html" in body`, `"<table" in body`, `"<nav" in body` are all False.
      Per the HTML5 tree-construction algorithm, a `<tr>` start tag processed
      in the "in body" insertion mode (i.e. outside a table context, exactly
      what a bare top-level document is) is a parse error and the token is
      dropped — a real browser renders an essentially blank page with no nav,
      leaving the operator unable to navigate onward except by manually
      editing the URL. This is reachable through ordinary use of the feature
      the phase built (select a filter, then reload/bookmark/share), not an
      obscure edge case. The existing tests do not catch it because
      `test_web_history_filters` (tests/test_history.py:63-77) only asserts
      substring presence in response text and never checks for enclosing
      chrome — exactly the blind spot 05-REVIEW.md's CR-01 identifies. No plan
      in this phase (05-01 through 05-07) touches this logic; it was
      introduced by 05-05 and has never been fixed.
    artifacts:
      - path: "app/routes/history.py"
        issue: "Lines 32-42: `is_hx or is_filtered` returns the chrome-less rows-only partial for a non-htmx, filtered top-level GET"
      - path: "app/templates/partials/history_rows.html"
        issue: "Contains bare <tr> markup with no enclosing <table>; correct only when swapped into an existing page by htmx, not when served as a standalone document"
    missing:
      - "Drop the `is_filtered` condition from the chrome decision in app/routes/history.py — only an actual HX-Request (is_hx) should receive the rows-only partial; a plain top-level GET (filtered or not) must always render the full pages/history.html with nav and filter bar, pre-selecting the current filter values"
      - "Add a regression test that performs a GET to /history with a filter param and NO HX-Request header, then asserts the response contains <html>/<nav>/<table> (not just row content) — the current test suite has no such assertion anywhere"
deferred: []
---

# Phase 5: Stock Operations & History Verification Report

**Phase Goal:** Operator can handle every non-sale stock movement (write-off, return, correction) and see the complete operation trail
**Verified:** 2026-07-10T00:45:00Z
**Status:** gaps_found
**Re-verification:** Yes — after gap-closure plans 05-06 (OPS-01 nav) and 05-07 (CR-02/CR-03/WR-03 error handling), following a fresh code review (05-REVIEW.md) that confirmed those fixes but surfaced a new Critical finding (CR-01) on `/history`.

## Process Note

This is the second verification pass for Phase 5. The first pass
(superseded, see `re_verification` frontmatter) found one blocking gap:
OPS-01 (write-off) had no UI navigation entry point. Plan 05-06 closed that
gap; plan 05-07 separately closed three warning-level reliability issues
(CR-02, CR-03, WR-03) found by the first code review. A second code review
(05-REVIEW.md) confirmed all of those fixes are real and landed, but while
re-reading `/history` end-to-end it found a new, more serious defect
(CR-01) that the first review and the first verification pass both missed.
This report independently reproduces that defect (not just citing the
review) before scoring it.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can write off stock with a reason, and stock decreases accordingly (OPS-01) | ✓ VERIFIED | `register_writeoff` writes a `writeoff` op and decrements stock (tests/test_writeoffs.py, 4+ tests GREEN). **Previously-failed gap now closed**: `app/templates/base.html:22` has `<a href="/writeoff">Списание</a>` in the persistent nav bar, and `app/templates/pages/home.html:11` links it too. `tests/test_writeoffs.py::test_web_writeoff_reachable_from_nav` asserts `'href="/writeoff"' in response.text` on `GET /` and passes. |
| 2 | Operator can register a return linked to the original sale, and stock increases accordingly (OPS-02) | ✓ VERIFIED | Entry point wired from `recent_sales.html`/`purchase_history.html`. `register_return` copies frozen price/cost from the origin sale op, caps at returnable qty, increases stock (tests/test_returns.py GREEN). **Previously-flagged warnings now closed**: `GET /returns` origin-not-found now returns `status_code=422` (was 404, silently discarded by base.html's htmx `responseHandling` allow-list) — confirmed at `app/routes/returns.py:91` and by passing `test_web_return_origin_not_found_uses_422`. The exception handler now calls `session.rollback()` before re-querying (`app/routes/returns.py:114`), confirmed by passing `test_web_return_survives_unexpected_error`. |
| 3 | Operator can correct stock quantity, and the adjustment is recorded as an operation rather than a direct edit (OPS-03) | ✓ VERIFIED | `/corrections` reachable from home.html. `register_correction` writes a `correction` op via `record_operation`, never a direct quantity UPDATE; count and delta modes tested; zero-net input rejected with no write (tests/test_corrections.py GREEN). Exception handler now also calls `session.rollback()` (`app/routes/corrections.py:80`, WR-03 fix). Note (Warning, not blocking): `/corrections` still has no persistent top-nav entry (only reachable from home.html, and unreachable there if zero active products exist) — WR-02 in 05-REVIEW.md, unfixed, not blocking under normal (non-empty-catalog) operation. |
| 4 | Operator can browse the full operation history showing what happened, when, and how much (OPS-04) | ✗ FAILED | `/history` is reachable via nav and renders correctly for unfiltered top-level navigation and for genuine htmx-driven filter/pagination interactions. **But** a plain (non-htmx) top-level navigation carrying a type/product filter — i.e. reloading, bookmarking, or sharing a URL that `hx-push-url` just wrote to the address bar after the operator picked a filter — returns a bare `<tr>`-only fragment with no `<table>`/`<html>`/nav wrapper. Reproduced independently in this pass via TestClient (`GET /history?type=writeoff`, no `HX-Request` header → 200, `<html`/`<table`/`<nav` all absent from body). Per HTML5 parsing rules a real browser drops the stray `<tr>`, rendering an essentially blank, unnavigable page. This is an ordinary, easily-reachable interaction, not an edge case, and directly undermines "operator can browse the full operation history." See Gap above. |

**Score:** 3/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | `WRITEOFF_REASONS` + `OPERATION_TYPE_LABELS` constants | ✓ VERIFIED | Both present, registered as Jinja globals |
| `app/services/writeoffs.py` | `register_writeoff()` + `recent_writeoffs()` | ✓ VERIFIED | Validation, allow-list, oversell warn-but-allow, single write path |
| `app/routes/writeoffs.py` | `GET /writeoff`, `GET /writeoff/lookup`, `POST /writeoff` | ✓ VERIFIED | Route works and is now reachable via nav (gap closed) |
| `app/templates/base.html` | Nav entries for Phase 5 features | ⚠️ PARTIAL | «Списание»/«История» present; «Корректировка» still absent from persistent nav (WR-02, warning, not blocking) |
| `app/services/returns.py` | `returnable_qty()` + `register_return()` | ✓ VERIFIED | Frozen price/cost copy, cap enforcement tested |
| `app/routes/returns.py` | `GET /returns`, `POST /returns` | ✓ VERIFIED | 422 status + rollback-before-requery both confirmed in source and by passing regression tests |
| `app/services/corrections.py` | `register_correction()` + `lookup_prefill()` | ✓ VERIFIED | Count/delta modes, zero-net rejection, no direct quantity edit |
| `app/routes/corrections.py` | `GET /corrections`, `POST /corrections`; old `POST /ops` removed | ✓ VERIFIED | rollback-before-requery added (WR-03) |
| `app/services/operations.py` | `history_view()` + `filter_products()` | ✓ VERIFIED | Paginated, filtered, fetch-one-extra sentinel confirmed |
| `app/routes/history.py` | `GET /history` (full page + rows partial), correct chrome decision | ✗ DEFECTIVE | Chrome-decision logic (`is_hx or is_filtered`) is wrong — see Gap. Route exists and works for the unfiltered/htmx cases but fails the filtered+non-htmx case |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/templates/base.html` / `home.html` | `/writeoff` | nav link | ✓ WIRED | Confirmed present in both files; regression test passes |
| `app/routes/returns.py` | origin sale `Operation` | `session.get` → frozen copy, 422 on not-found | ✓ WIRED | Confirmed; `test_web_return_origin_not_found_uses_422` passes |
| `app/routes/returns.py` / `corrections.py` / `writeoffs.py` | `session.rollback()` | except-block first statement | ✓ WIRED | All three confirmed present before any further session use |
| `app/routes/history.py` | `pages/history.html` (full chrome) | `is_hx or is_filtered` branch | ✗ MISWIRED | Non-htmx + filtered request incorrectly routed to the chrome-less partial instead of the full page — this is the CR-01 defect |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `history_rows.html` | `rows` | `history_view()` → real DB query, paginated | Yes | ✓ FLOWING (data is correct; delivery wrapper is the defect, not the data) |
| `writeoff_form.html` (recent list) | `writeoffs` | `recent_writeoffs()` → real query | Yes | ✓ FLOWING |
| `return_form.html` | `product`, `sold`, `remaining`, `unit_price_cents` | `_origin_context()` → real queries + frozen origin fields | Yes | ✓ FLOWING |
| `correction_form.html` | `current_qty` | `lookup_prefill()` → real `Product.quantity` read | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Write-off nav link present | `uv run pytest tests/test_writeoffs.py -k reachable_from_nav -v` (verified via full-suite run below) | included in 165 passed | ✓ PASS |
| Return 422 on origin-not-found | `uv run pytest tests/test_returns.py -v` (included in full suite) | included in 165 passed | ✓ PASS |
| Return survives unexpected error (rollback) | `uv run pytest tests/test_returns.py -v` | included in 165 passed | ✓ PASS |
| Full regression suite | `uv run pytest -q` | **165 passed**, 2 warnings (1 deprecation, 1 SAWarning unrelated to Phase 5 logic) | ✓ PASS |
| `/history?type=writeoff` non-htmx request produces valid standalone HTML | Direct TestClient probe: `client.get("/history?type=writeoff")` (no HX-Request header), assert `<html>`/`<table>`/`<nav>` present | 200 OK, but `<html>`: False, `<table>`: False, `<nav>`: False — body is bare `<tr>` fragment | ✗ FAIL — confirms CR-01 |
| No TBD/FIXME/XXX in Phase 5 files | grep across routes/history.py, returns.py, corrections.py, writeoffs.py, base.html, home.html, history_rows.html | 0 matches | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files exist in this repo; this project's verification gate is its pytest suite plus the direct TestClient probe run above.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|--------------|--------|----------|
| OPS-01 | 05-01, 05-02, 05-06 | User can write off stock with a reason | ✓ SATISFIED | Service/route correct and tested; nav link added by 05-06 and confirmed by regression test |
| OPS-02 | 05-01, 05-03, 05-07 | User can register a return linked to the original sale; stock increases accordingly | ✓ SATISFIED | Entry point wired, tested, correct math; 422/rollback fixes from 05-07 confirmed |
| OPS-03 | 05-01, 05-04 | User can correct stock quantity (adjustment recorded as an operation, not a direct edit) | ✓ SATISFIED | `register_correction` uses `record_operation`; rollback fix (05-07) confirmed; WR-02 nav gap is a warning, not blocking |
| OPS-04 | 05-01, 05-05 | User can view the full operation history (what, when, how much) | ✗ BLOCKED | `/history` works for the unfiltered and htmx-driven cases, but a realistic, ordinary interaction (reload/bookmark/share of a filtered URL) returns a broken, chrome-less page — see Gap |

No orphaned requirements — REQUIREMENTS.md maps exactly OPS-01..04 to Phase 5, matching all seven plans' `requirements:` frontmatter (05-06 → OPS-01, 05-07 → OPS-02).

**Documentation inconsistency (Info, carried over):** REQUIREMENTS.md's traceability table (lines 93-96) still marks OPS-02/03/04 as "In Progress" even though the checkbox list above it marks all four complete. Not updated across any of Waves 2-7. Cosmetic only.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/routes/history.py:32-42` | — | `is_hx or is_filtered` chrome decision serves a chrome-less fragment to a plain top-level navigation carrying filter params (CR-01, new) | 🛑 Blocker | Breaks OPS-04 — see Gap |
| `app/templates/base.html` | nav | `/corrections` has no persistent top-nav entry, only reachable from `home.html` (and not reachable there with zero active products) (WR-02, carried over) | ⚠️ Warning | Inconsistent discoverability vs. `/writeoff`/`/history`; not blocking under normal (non-empty-catalog) operation |
| `app/templates/partials/history_rows.html:44-52` | — | "Показать ещё" pagination control (`hx-swap="beforeend"` + oob trailing row) gets stranded mid-list after first click (WR-01, carried over, explicitly deferred) | ⚠️ Warning | Cosmetic/UX only; does not prevent loading more rows |
| `app/templates/partials/writeoff_rows.html:28-30` | — | No guard against `r.op.payload` being `None`, unlike `history_rows.html` (WR-03 in new review numbering / carried over) | ℹ️ Info | Not currently reachable; latent risk |
| `app/services/operations.py:51-57` | — | `/history` product filter dropdown only lists active products (WR-04, carried over) | ℹ️ Info | Known limitation |
| Various (IN-01, IN-02, IN-03, IN-05, IN-06, IN-07 in 05-REVIEW.md) | — | Minor message-precision, dead-attribute, builtin-shadowing, and missing-validation issues | ℹ️ Info | Cosmetic/latent only, not blocking |

No `TBD`/`FIXME`/`XXX` debt markers found in any Phase 5 file.

### Human Verification Required

None required to resolve status — the CR-01 defect was reproduced directly with an automated TestClient probe in this verification pass (not inferred from the review alone), so no human click-through is needed to confirm it is real. Once fixed, a quick manual sanity check (pick a filter on `/history`, then hit browser reload) is reasonable but not blocking further automated verification.

### Gaps Summary

**One blocking gap remains, newly surfaced since the last verification pass:** `/history`'s chrome-decision logic (`is_hx or is_filtered` in `app/routes/history.py`) incorrectly serves the chrome-less rows-only partial to any plain (non-htmx) top-level navigation that carries a filter parameter — exactly what happens when an operator reloads, bookmarks, or shares a URL that htmx's `hx-push-url` wrote into the address bar after selecting a filter. This was independently reproduced in this verification pass (not just cited from 05-REVIEW.md): a TestClient GET to `/history?type=writeoff` without an `HX-Request` header returns 200 with a body containing no `<html>`, `<table>`, or `<nav>` — only bare `<tr>` elements, which a real browser drops per the HTML5 parsing algorithm, rendering an essentially blank, unnavigable page. This directly fails success criterion 4 ("Operator can browse the full operation history") and requirement OPS-04, under an ordinary and easily-reachable interaction. No plan across the phase (05-01 through 05-07) has addressed this; it was introduced in 05-05 and missed by the first code review and the first verification pass.

The two previously-tracked gaps are now closed and independently reconfirmed: OPS-01's missing nav link (05-06) and the returns 404-vs-422 / missing-rollback issues (05-07, CR-02/CR-03/WR-03). Full regression suite: 165 passed, no regressions detected from either gap-closure plan.

Two Warning-level items remain open by design (not blocking): WR-01 (pagination control placement) and WR-02 (`/corrections` lacks a persistent top-nav entry) — both explicitly deferred in prior passes, still present, still non-blocking to the tested happy paths.

**Fix scope for the remaining gap:** in `app/routes/history.py`, change the branch condition from `if is_hx or is_filtered:` to `if is_hx:`, and always populate `context["products"] = filter_products(session)` before falling through to the full-page template on any non-htmx request (filtered or not) — `history_filters.html` already supports pre-selecting the current filter values via `type_filter`/`product_id`, so no template changes are needed for correctness, only the route's branch condition. Recommended to pair this with a new regression test asserting `<html>`/`<nav>`/`<table>` presence on a non-htmx, filtered `GET /history` request, since the current suite has no such assertion anywhere.

---

*Verified: 2026-07-10T00:45:00Z*
*Verifier: Claude (gsd-verifier)*
