---
phase: 05-stock-operations-history
verified: 2026-07-10T00:28:29Z
status: gaps_found
score: 3/4 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Operator can write off stock with a reason, and stock decreases accordingly"
    status: failed
    reason: >
      The /writeoff feature is fully implemented and tested at the service and
      route level (register_writeoff writes a writeoff op, stock decreases,
      reason allow-list enforced, oversell warn-but-allow works) — but there is
      NO navigation link to /writeoff anywhere in the rendered UI. base.html's
      nav bar lists Главная/Товары/Приход/Продажи/Покупатели/История/
      Справочник/Резервные копии — no «Списание». home.html links to
      /corrections and /history but not /writeoff. Grepping every template for
      "/writeoff" (excluding the write-off page/partials themselves) returns
      zero matches. An operator using the app through its UI (as opposed to
      typing a URL from memory) has no way to discover or reach this feature.
      This was a known gap acknowledged in 05-02-SUMMARY.md ("A future plan or
      the phase's UAT pass may want to add it") but was never closed in Waves
      3-5 or at phase completion. Confirmed independently by 05-REVIEW.md
      (CR-01, Critical) and by direct grep in this verification.
    artifacts:
      - path: "app/templates/base.html"
        issue: "Nav bar (lines 17-25) has no <a href=\"/writeoff\"> entry"
      - path: "app/templates/pages/home.html"
        issue: "Links only to /corrections and /history, not /writeoff"
    missing:
      - "Add a «Списание» nav link to /writeoff in app/templates/base.html (and/or home.html), consistent with how /corrections and /history were wired"
deferred: []
---

# Phase 5: Stock Operations & History Verification Report

**Phase Goal:** Operator can handle every non-sale stock movement (write-off, return, correction) and see the complete operation trail
**Verified:** 2026-07-10T00:28:29Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Process Note

ROADMAP.md marks this phase `Mode: mvp`, but the phase goal text ("Operator
can handle every non-sale stock movement...") does not match the strict User
Story format (`As a ..., I want to ..., so that ....`) required by the MVP
Mode Verification methodology (`gsd-tools query user-story.validate` returns
`valid: false`). All five phases in this project use `Mode: mvp` with the
same traditional goal-phrasing style, and ROADMAP.md already supplies a full,
structured `success_criteria` list for this phase — so standard goal-backward
verification (Step 2a: roadmap success criteria + Step 2b: PLAN frontmatter
must_haves) was used instead of the MVP User-Flow-Coverage table. This is
informational only and does not change the verification outcome; if strict
MVP-mode formatting is desired going forward, run `/gsd mvp-phase 5` to
reformat the goal.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can write off stock with a reason, and stock decreases accordingly (OPS-01) | ✗ FAILED | `register_writeoff` correctly writes a `writeoff` op and decrements `Product.quantity`/`compute_stock` (tests/test_writeoffs.py::test_stock_and_reason, 4/4 GREEN). But **no UI navigation path reaches `/writeoff`** — confirmed by grep across all templates and by 05-REVIEW.md CR-01. Operator cannot discover the feature through the running app. |
| 2 | Operator can register a return linked to the original sale, and stock increases accordingly (OPS-02) | ✓ VERIFIED | Entry point wired from `recent_sales.html`/`purchase_history.html` («Вернуть» hx-get to `/returns?sale_id=&product_id=&origin_op_id=`). `register_return` copies frozen `unit_price_cents`/`unit_cost_cents` from the origin sale op, caps at returnable qty, increases stock (tests/test_returns.py, 3/3 GREEN, asserts `stocked_product.quantity == 8 - 2 + 1`). See Warnings for two error-handling edge-case gaps (CR-02, CR-03) that do not block the happy path but are real reliability risks. |
| 3 | Operator can correct stock quantity, and the adjustment is recorded as an operation rather than a direct edit (OPS-03) | ✓ VERIFIED | `/corrections` reachable from home.html («Корректировка остатка»). `register_correction` writes a `correction` op via `record_operation` (never a direct `UPDATE` on `products.quantity`); count and delta modes both tested; zero-net input rejected with no write; old walking-skeleton `POST /ops` route confirmed removed (`tests/test_corrections.py::test_web_ops_replaced`, 4/4 GREEN). |
| 4 | Operator can browse the full operation history showing what happened, when, and how much (OPS-04) | ✓ VERIFIED | `/history` reachable via nav link «История» in base.html. `history_view()` returns newest-first, type/product-filterable, paginated (50/page) rows joined across all operation types with RU labels (tests/test_history.py, 3/3 GREEN, full suite 162 passed). See Warnings for a pagination-control placement bug (WR-01) that doesn't prevent browsing but produces a confusing "Показать ещё" position after the first click. |

**Score:** 3/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | `WRITEOFF_REASONS` + `OPERATION_TYPE_LABELS` constants | ✓ VERIFIED | Both present, correct keys, registered as Jinja globals (`app/routes/__init__.py:15-16`) |
| `app/services/writeoffs.py` | `register_writeoff()` + `recent_writeoffs()` | ✓ VERIFIED | Implements validation, allow-list, oversell warn-but-allow, single write path |
| `app/routes/writeoffs.py` | `GET /writeoff`, `GET /writeoff/lookup`, `POST /writeoff` | ✓ VERIFIED (route works) / ⚠️ ORPHANED (no nav entry point) | Functional but unreachable via UI — see Gap #1 |
| `app/services/returns.py` | `returnable_qty()` + `register_return()` | ✓ VERIFIED | Frozen price/cost copy from origin sale op confirmed; cap enforcement tested |
| `app/routes/returns.py` | `GET /returns`, `POST /returns` | ✓ VERIFIED (wired) | Reachable from recent-sales/purchase-history; see CR-02/CR-03 warnings for error-path robustness |
| `app/services/corrections.py` | `register_correction()` + `lookup_prefill()` | ✓ VERIFIED | Count/delta modes, zero-net rejection, no direct quantity edit |
| `app/routes/corrections.py` | `GET /corrections`, `POST /corrections`; old `POST /ops` removed | ✓ VERIFIED | `test_web_ops_replaced` confirms old route gone |
| `app/services/operations.py` | `history_view()` + `filter_products()` | ✓ VERIFIED | Paginated, filtered, fetch-one-extra sentinel confirmed in code and tests |
| `app/routes/history.py` | `GET /history` (full page + rows partial) | ✓ VERIFIED | Reachable via nav; branches HX/filtered vs full page |
| `app/templates/base.html` | Nav entries for all Phase 5 features | ✗ INCOMPLETE | «История» present; «Списание» (writeoff) absent — Gap #1 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/routes/__init__.py` | `app.models.WRITEOFF_REASONS`/`OPERATION_TYPE_LABELS` | `templates.env.globals[...]` | ✓ WIRED | Confirmed by direct grep (tool's automated key-link check mis-escaped the regex; manually verified) |
| `app/services/writeoffs.py` | `app.services.ledger.record_operation` | `record_operation(` call | ✓ WIRED | `app/services/writeoffs.py:95` |
| `app/routes/writeoffs.py` | `app.services.writeoffs.register_writeoff` | POST handler | ✓ WIRED | `app/routes/writeoffs.py:73` |
| `app/main.py` | `writeoffs.router`/`returns.router`/`corrections.router`/`history.router` | `include_router` | ✓ WIRED | All four confirmed in `app/main.py:44-47` |
| `app/services/returns.py` | origin sale `Operation` | `session.get(Operation, origin_op_id)` → frozen copy | ✓ WIRED | `app/routes/returns.py:104`, `app/services/returns.py` |
| `app/templates/partials/recent_sales.html` / `purchase_history.html` | `/returns` | «Вернуть» hx-get with sale_id+product_id | ✓ WIRED | Confirmed present in both templates |
| `app/templates/base.html` / `home.html` | `/writeoff` | nav link | ✗ NOT_WIRED | No link found anywhere — Gap #1 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `history_rows.html` | `rows` | `history_view()` → `select(Operation, Product).join(...)` real DB query, paginated | Yes | ✓ FLOWING |
| `writeoff_form.html` (recent list) | `writeoffs` | `recent_writeoffs()` → real query over `Operation` | Yes | ✓ FLOWING |
| `return_form.html` | `product`, `sold`, `remaining`, `unit_price_cents` | `_origin_context()` → real `sold_qty`/`returnable_qty` queries + origin op fields | Yes | ✓ FLOWING |
| `correction_form.html` | `current_qty` | `lookup_prefill()` → real `Product.quantity` read | Yes | ✓ FLOWING |

No hardcoded/empty data sources found in any Phase 5 read path.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Write-off decrements stock via service | `uv run pytest tests/test_writeoffs.py -v` | 4/4 passed | ✓ PASS |
| Return increases stock, freezes origin price | `uv run pytest tests/test_returns.py -v` | 3/3 passed | ✓ PASS |
| Correction writes op (not direct edit), old /ops route gone | `uv run pytest tests/test_corrections.py -v` | 4/4 passed | ✓ PASS |
| History pagination/filtering | `uv run pytest tests/test_history.py -v` | 3/3 passed | ✓ PASS |
| Full regression suite | `uv run pytest -q` | 162 passed | ✓ PASS |
| `/writeoff` reachable via UI navigation | `grep -rn "href=\"/writeoff" app/templates/` | 0 matches | ✗ FAIL |
| ruff clean on Phase 5 files | `uv run ruff check .` | 2 pre-existing errors, both in Phase-4 files (`tests/test_customers.py`, `tests/test_sales.py`), not touched by Phase 5 | ✓ PASS (Phase 5 scope) |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files exist in this repo and no PLAN/SUMMARY references probes; this project's verification gate is its pytest suite.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|--------------|--------|----------|
| OPS-01 | 05-01, 05-02 | User can write off stock with a reason | ✗ BLOCKED | Service/route/tests fully correct, but unreachable from the app UI (Gap #1) — an operator relying on the app's own navigation cannot use this feature |
| OPS-02 | 05-01, 05-03 | User can register a return linked to the original sale; stock increases accordingly | ✓ SATISFIED | Entry point wired, tested, correct math; error-path robustness gaps noted as warnings (not blocking) |
| OPS-03 | 05-01, 05-04 | User can correct stock quantity (adjustment recorded as an operation, not a direct edit) | ✓ SATISFIED | `register_correction` uses `record_operation`; old direct-edit-adjacent `/ops` route removed |
| OPS-04 | 05-01, 05-05 | User can view the full operation history (what, when, how much) | ✓ SATISFIED | `/history` reachable, filterable, paginated, tested; a pagination UX bug (WR-01) does not block browsing |

**No orphaned requirements** — REQUIREMENTS.md's traceability table maps exactly OPS-01..04 to Phase 5, matching every plan's `requirements:` frontmatter.

**Documentation inconsistency (Info):** REQUIREMENTS.md's own traceability table (lines 93-96) still marks OPS-02/03/04 as "In Progress (Wave 0 foundation landed...)" even though the checkbox list above it (lines 33-36) marks all four `[x]` complete and ROADMAP.md marks the phase `[x]` complete (2026-07-09). This table was not updated after Waves 2-5 landed — cosmetic, but worth a follow-up edit for traceability hygiene.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/templates/base.html`, `app/templates/pages/home.html` | nav / 9 | Missing `/writeoff` nav link (CR-01 in 05-REVIEW.md) | 🛑 Blocker | OPS-01 unreachable via UI — see Gap #1 |
| `app/routes/returns.py:88-92`, `app/templates/base.html:9-10` | — | `GET /returns` returns its "origin not found" error partial with `status_code=404`, but base.html's htmx `responseHandling` config only allow-lists `204`/`422` for swapping — every other 4xx/5xx (including 404) gets `swap:false,error:true`, so the RU error message is silently discarded and the operator sees nothing happen (CR-02) | ⚠️ Warning | Edge case only (stale/invalid return link); does not affect the tested happy path |
| `app/routes/returns.py:107-120`, `app/services/returns.py:91-110` | — | `POST /returns`'s exception handler re-queries the same SQLAlchemy session without `session.rollback()` first; per SQLAlchemy semantics an exception-tainted session raises `PendingRollbackError` on the next query, so an unexpected exception (e.g. `OperationalError`) could itself crash with an unhandled 500 instead of the graceful error page the `# noqa: BLE001` comment promises (CR-03) | ⚠️ Warning | Not exercised by current tests (which don't force this exception path); real risk under an unusual DB error |
| `app/routes/corrections.py`, `app/routes/writeoffs.py`, `app/routes/returns.py` | except blocks | Bare `except Exception` never calls `session.rollback()` (WR-03) — currently harmless for corrections/writeoffs (their error contexts don't re-query), but a systemic gap that caused CR-03 for returns | ⚠️ Warning | Latent risk for future edits to these error-context builders |
| `app/templates/partials/history_rows.html:44-52`, `app/routes/history.py` | — | "Показать ещё" pagination control (`hx-swap="beforeend"` + trailing `hx-swap-oob` row) gets left stranded mid-list after the first click instead of returning to the bottom (WR-01) — confirmed by reading the swap/target/oob wiring | ⚠️ Warning | Cosmetic/UX only; does not prevent loading more rows, just visually disorders them |
| `app/templates/partials/writeoff_rows.html:28-30` | — | No guard against `r.op.payload` being `None`, unlike `history_rows.html`'s equivalent check (WR-02) — not currently reachable since every write-off write path always populates payload | ℹ️ Info | Defensive-coding inconsistency; latent risk only |
| `app/services/operations.py:51-57` | — | `/history` product-filter dropdown only lists active (non-deleted) products, so a soft-deleted product's ops can't be filtered to directly (WR-04) | ℹ️ Info | Known limitation, not a regression |
| `app/services/corrections.py:70-83` | — | `"-0"` input in delta mode returns the generic `ZERO_NET_ERROR` instead of the more specific `DELTA_QTY_ERROR` (WR-05) | ℹ️ Info | Cosmetic message-precision issue only |
| `.planning/REQUIREMENTS.md:93-96` | — | Traceability table not updated to "Complete" for OPS-02/03/04 after Wave 2-5 landed | ℹ️ Info | Documentation hygiene only |

No `TBD`/`FIXME`/`XXX` debt markers found in any Phase 5 file (`app/services/writeoffs.py`, `returns.py`, `corrections.py`, `operations.py`, corresponding routes/templates).

### Human Verification Required

None required to resolve status — the missing nav link (Gap #1) and the htmx/session-rollback issues (CR-02, CR-03, WR-01) were all confirmed directly from source (grep/read), not inferred. Once Gap #1 is closed, a quick manual click-through of Главная → «Списание» (once added) is a reasonable sanity check but is not blocking further automated verification.

### Gaps Summary

One blocking gap: **OPS-01 (write-off) has no discoverable entry point in the running application.** The feature itself — service, route, templates, validation, oversell handling — is complete, correct, and fully covered by 4/4 passing tests. But it can only be reached by typing `/writeoff` into the browser's address bar; no link exists anywhere in `base.html`'s nav bar or `home.html`. This was explicitly flagged as a known, deliberately-deferred gap in `05-02-SUMMARY.md` ("A future plan or the phase's UAT pass may want to add it alongside the other nav entries added across Waves 3-5") but was never closed by 05-03/04/05, and the phase's own code review (05-REVIEW.md) independently confirmed it as Critical (CR-01). Given the phase goal is specifically about the *operator's* ability to handle these stock movements through the app, an unreachable page does not satisfy "operator can write off stock with a reason" in practice.

Three additional Warning-level issues from the code review (CR-02: swallowed 404 error message on `/returns`, CR-03: potential unhandled 500 from an unrolled-back session in `/returns`'s exception path, WR-01: pagination control placement bug on `/history`) do not block the phase goal today (their respective happy paths are tested and correct) but represent real reliability/UX gaps worth fixing before or shortly after this phase ships, especially CR-03 given the project's stated Core Value of "reliably record ... without losing any data."

**Fix scope for Gap #1:** add one `<a href="/writeoff">Списание</a>` line to `app/templates/base.html`'s nav (and optionally a link from `home.html`), matching the existing pattern used for `/history`, `/corrections`, etc. This is a trivial, low-risk, single-line change with no service-layer impact.

---

*Verified: 2026-07-10T00:28:29Z*
*Verifier: Claude (gsd-verifier)*
