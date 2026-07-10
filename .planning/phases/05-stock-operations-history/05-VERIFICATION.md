---
phase: 05-stock-operations-history
verified: 2026-07-10T14:30:00Z
status: gaps_found
score: 3/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/4
  gaps_closed:
    - "Operator can browse the full operation history showing what happened, when, and how much (OPS-04) — CR-01 (chrome-less fragment on non-htmx filtered GET) closed by 05-08: app/routes/history.py's chrome decision now keyed solely on `is_hx`; confirmed by reading the route, by an independent pytest run of tests/test_history.py (4/4 passed including the new test_web_history_filtered_reload_returns_full_chrome), and by the full 166-test regression suite."
  gaps_remaining: []
  regressions: []
gaps:
  - truth: "History is paginated (50/page + «Показать ещё») and never loads the whole ledger unbounded, and the operator can reliably page through it (OPS-04, D-15 must-have from 05-05-PLAN.md)"
    status: failed
    reason: >
      A new, more severe defect than the one closed by 05-08 exists in
      `/history`'s pagination control, independently confirmed in this
      verification pass by reading the actual template/route wiring (not
      merely citing 05-REVIEW.md, though that report — written after 05-08
      landed, and still the latest commit in the repo with no follow-up fix
      — first surfaced it and reasons through it correctly).

      `app/templates/partials/history_rows.html:44` renders the trailing
      "Показать ещё" control as `<tr id="load-more"{% if oob %}
      hx-swap-oob="true"{% endif %}>`, nested INSIDE `<tbody
      id="history-tbody">` (confirmed: this partial is included directly
      inside that tbody in both `pages/history.html:20-23`, oob=False, and
      as the raw HX response body, oob=True whenever `is_hx` is true —
      `app/routes/history.py:41`: `"oob": is_hx`). Both type/product
      `<select>` elements in `app/templates/partials/history_filters.html`
      (lines 8-16, 20-28) target `#history-tbody` and set NO `hx-swap`
      attribute, so htmx uses its documented default swap style —
      `innerHTML` — on that target (confirmed: `grep hx-swap=`
      history_filters.html returns zero matches for the two selects).

      Per htmx's documented out-of-band-swap behavior, `hx-swap-oob`
      elements are stripped out of the response and swapped into the DOM
      (in place, matched by id) BEFORE the remainder of the response is
      swapped into the declared target. For a filter `<select>` change this
      means: (1) the oob-extracted `#load-more` row is swapped back into its
      existing position inside `#history-tbody`; (2) the main swap then
      immediately runs `#history-tbody.innerHTML = <new data rows only>`
      (the load-more row was already stripped from that content for step 1)
      — which replaces every child of `#history-tbody`, including the row
      step 1 just placed. After the FIRST filter interaction on a page,
      `#load-more` no longer exists anywhere in the DOM. Any later response
      that tries to oob-swap a fresh `#load-more` (e.g. a filter that now
      matches more than `page_size=50` rows) has no matching id left to
      swap into, so it silently no-ops. Server-side `has_next` can still be
      `True` (`app/services/operations.py:41`, fetch-one-extra sentinel
      logic is correct and unaffected), but the button to reach page 2 of a
      filtered view never reappears for the rest of that page session —
      only a full non-htmx page reload restores it. This directly
      contradicts 05-05-PLAN.md's own must-have truth ("History is
      paginated ... and never loads the whole ledger unbounded") and
      undermines ROADMAP.md Success Criterion 4 ("Operator can browse the
      full operation history") for any product/type combination with more
      than 50 matching operations once any filter has been touched —
      exactly the kind of dataset growth this ledger-based app is designed
      to accumulate over time. The bug is a structural/markup nesting
      mistake (oob-swap target nested inside a same-element innerHTML swap
      target), not a runtime-variable or browser-version-dependent
      behavior, so it is deterministic and does not require live-browser
      confirmation to establish with high confidence — though a manual
      click-through is still recommended once fixed.

      This finding is not covered by any override, was not touched by plan
      05-08 (which fixed a separate, now-closed defect — the old CR-01
      chrome-decision bug), and no gap-closure plan has been created for it
      (`05-09-PLAN.md` does not exist; the latest commit in the repository,
      `dc9564a`, is the code-review report itself with no follow-up fix
      commit).
    artifacts:
      - path: "app/templates/partials/history_rows.html"
        issue: "Line 44: `<tr id=\"load-more\" hx-swap-oob=\"true\">` is nested inside `#history-tbody`, the same element both filter `<select>`s target with a default (innerHTML) swap"
      - path: "app/templates/partials/history_filters.html"
        issue: "Lines 8-16, 20-28: neither `<select>` sets `hx-swap`, so htmx's default `innerHTML` swap on `#history-tbody` wipes out the oob-placed `#load-more` row on every filter change"
      - path: "app/routes/history.py"
        issue: "Line 41: `oob` is set to `is_hx` on every htmx response including filter-change requests, not only genuine \"Показать ещё\" pagination requests, so every filter change triggers the same oob-nesting defect"
    missing:
      - "Move `#load-more` outside `#history-tbody` (e.g. into its own `<tfoot>` row) so neither the filter selects' innerHTML swap nor the button's beforeend append ever touches it; have the button target `#load-more` directly with `hx-target=\"#load-more\" hx-swap=\"outerHTML\"` instead of relying on `hx-swap-oob` + `beforeend` on the shared tbody target"
      - "Add a regression test that performs an HX-Request filter GET against a fixture seeded with more than 50 matching rows and asserts a `<button>` inside `id=\"load-more\"` is still present/reachable in that response — the current suite never exercises the >50-row filtered case, which is why this defect was not caught by any existing test"
deferred: []
---

# Phase 5: Stock Operations & History Verification Report

**Phase Goal:** Operator can handle every non-sale stock movement (write-off, return, correction) and see the complete operation trail
**Verified:** 2026-07-10T14:30:00Z
**Status:** gaps_found
**Re-verification:** Yes — third pass. First pass found OPS-01 unreachable via nav (closed by 05-06) plus warning-level reliability issues (closed by 05-07). Second pass found CR-01, a chrome-less-fragment bug on `/history` (closed by 05-08). This third pass independently confirms CR-01 is closed, but a fresh code review (`05-REVIEW.md`, committed after 05-08 with no follow-up fix) surfaced a new, more severe pagination-destruction defect on `/history` that this pass independently reproduces via code inspection and adds to the gap list.

## Process Note

This is the third verification pass for Phase 5. Two prior gap-closure rounds closed OPS-01's missing nav link (05-06), three reliability warnings (05-07), and the `/history` chrome-decision bug CR-01 (05-08) — all three are independently reconfirmed still-fixed in this pass (regression check: nav link present, `session.rollback()` present in returns/corrections, `is_hx`-only branch present in history.py, full 166-test suite green). However, while re-tracing `/history`'s pagination control end-to-end (prompted by `05-REVIEW.md`'s findings, but verified independently against the actual template/route source, not taken on the review's word alone), this pass confirms a new Critical defect: the "Показать ещё" load-more control is permanently destroyed by the first filter-select interaction on any page load, due to an htmx oob-swap-target-nesting mistake. This was not caught by any of the prior two verification passes because neither exercised the >50-row-per-filter pagination path. It has not yet been gap-closed by any plan.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can write off stock with a reason, and stock decreases accordingly (OPS-01) | ✓ VERIFIED | Regression-checked: `app/templates/base.html:22` and `app/templates/pages/home.html:11` both still link `/writeoff`; `register_writeoff` unchanged since last pass. Full suite green (166 passed). |
| 2 | Operator can register a return linked to the original sale, and stock increases accordingly (OPS-02) | ✓ VERIFIED | Regression-checked: `app/routes/returns.py` still returns 422 on origin-not-found (line 91/124/134) and calls `session.rollback()` before re-query (line 114). `register_return` unchanged. |
| 3 | Operator can correct stock quantity, and the adjustment is recorded as an operation rather than a direct edit (OPS-03) | ✓ VERIFIED | Regression-checked: `app/routes/corrections.py:80` still calls `session.rollback()`; `register_correction` unchanged, still writes via `record_operation`, never a direct quantity UPDATE. WR-02 (renumbered; formerly noted as "WR-02 nav gap", now tracked in `05-REVIEW.md` as WR-01) — `/corrections` still has no persistent top-nav entry — remains a non-blocking Warning, carried over unchanged. |
| 4 | Operator can browse the full operation history showing what happened, when, and how much (OPS-04) | ✗ FAILED | The previously-blocking chrome-decision bug (old CR-01) is now confirmed CLOSED: `app/routes/history.py:34-46` branches purely on `is_hx`; `tests/test_history.py::test_web_history_filtered_reload_returns_full_chrome` passes independently (`uv run pytest tests/test_history.py -v` → 4 passed). **But** a new, more severe defect (new CR-01, replacing the closed slot) breaks pagination: the "Показать ещё" control (`<tr id="load-more" hx-swap-oob="true">`, `history_rows.html:44`) is nested inside `#history-tbody`, the same element both filter `<select>`s (`history_filters.html`) target with htmx's default `innerHTML` swap (no `hx-swap` attribute set on either select — confirmed by grep). Per htmx's documented oob-before-main-swap ordering, the first filter interaction on any page permanently removes `#load-more` from the DOM for the rest of that page session — even though `has_next` may still be `True` server-side, no control remains to reach page 2+ of a filtered view. This directly contradicts 05-05-PLAN.md's own must-have ("History is paginated ... and never loads the whole ledger unbounded") and Success Criterion 4. See Gap below. |

**Score:** 3/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | `WRITEOFF_REASONS` + `OPERATION_TYPE_LABELS` constants | ✓ VERIFIED | Unchanged since last pass, still registered as Jinja globals |
| `app/services/writeoffs.py` | `register_writeoff()` + `recent_writeoffs()` | ✓ VERIFIED | Unchanged |
| `app/routes/writeoffs.py` | `GET /writeoff`, `GET /writeoff/lookup`, `POST /writeoff` | ✓ VERIFIED | Unchanged, reachable via nav |
| `app/templates/base.html` | Nav entries for Phase 5 features | ⚠️ PARTIAL | «Списание»/«История» present; «Корректировка» still absent from persistent nav (non-blocking Warning, carried over) |
| `app/services/returns.py` | `returnable_qty()` + `register_return()` | ✓ VERIFIED | Unchanged |
| `app/routes/returns.py` | `GET /returns`, `POST /returns` | ✓ VERIFIED | 422 + rollback-before-requery both still present |
| `app/services/corrections.py` | `register_correction()` + `lookup_prefill()` | ✓ VERIFIED | Unchanged |
| `app/routes/corrections.py` | `GET /corrections`, `POST /corrections`; old `POST /ops` removed | ✓ VERIFIED | rollback-before-requery still present |
| `app/services/operations.py` | `history_view()` + `filter_products()` | ✓ VERIFIED | Paginated, filtered, fetch-one-extra sentinel logic itself is correct (server-side `has_next` is accurate) |
| `app/routes/history.py` | `GET /history` (full page + rows partial), correct chrome decision | ✓ VERIFIED (chrome decision only) | `if is_hx:` branch confirmed correct — CR-01 (old) fully closed |
| `app/templates/partials/history_rows.html` | Rows partial + pagination control | ✗ DEFECTIVE | `#load-more` nested inside the filter selects' innerHTML swap target — see Gap (new CR-01) |
| `app/templates/partials/history_filters.html` | Type/product filter selects | ✗ DEFECTIVE (interaction with rows partial) | Default `innerHTML` swap on `#history-tbody` destroys the oob-placed load-more row on every filter change — see Gap |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/templates/base.html` / `home.html` | `/writeoff` | nav link | ✓ WIRED | Confirmed present in both files |
| `app/routes/returns.py` | origin sale `Operation` | `session.get` → frozen copy, 422 on not-found | ✓ WIRED | Confirmed present |
| `app/routes/returns.py` / `corrections.py` / `writeoffs.py` | `session.rollback()` | except-block first statement | ✓ WIRED | Confirmed present in all three |
| `app/routes/history.py` | `pages/history.html` (full chrome) | `is_hx` branch | ✓ WIRED | Non-htmx request (filtered or not) now always renders full chrome — CR-01 (old) fix confirmed |
| `app/templates/partials/history_filters.html` `<select>` | `#history-tbody` | default (`innerHTML`) htmx swap | ✗ MISWIRED | Wipes out the oob-nested `#load-more` row on every filter change — new CR-01 defect |
| `app/templates/partials/history_rows.html` `#load-more` button | `#history-tbody` | `hx-swap="beforeend"` | ⚠️ PARTIAL | Still functions for the "click without ever using a filter" path (control visibly migrates position — cosmetic WR, carried over, unchanged), but becomes permanently unreachable once any filter select has been used |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `history_rows.html` | `rows` | `history_view()` → real DB query, paginated, correct `has_next` sentinel | Yes | ✓ FLOWING (data itself is correct; the defect is the pagination CONTROL's DOM survival, not the data) |
| `writeoff_form.html` (recent list) | `writeoffs` | `recent_writeoffs()` → real query | Yes | ✓ FLOWING |
| `return_form.html` | `product`, `sold`, `remaining`, `unit_price_cents` | `_origin_context()` → real queries + frozen origin fields | Yes | ✓ FLOWING |
| `correction_form.html` | `current_qty` | `lookup_prefill()` → real `Product.quantity` read | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CR-01 (old, chrome decision) regression test passes standalone | `uv run pytest tests/test_history.py -v` | 4 passed (`test_history_pagination`, `test_web_history_rows`, `test_web_history_filters`, `test_web_history_filtered_reload_returns_full_chrome`) | ✓ PASS |
| Full regression suite | `uv run pytest -q` | **166 passed**, 2 warnings (pre-existing, unrelated to Phase 5 logic) | ✓ PASS |
| `app/routes/history.py` lint/format clean | `uv run ruff check app/routes/history.py` / `uv run ruff format --check app/routes/history.py` | Both clean | ✓ PASS |
| `tests/test_history.py` I001 (pre-existing, repo-wide pattern) | `uv run ruff check tests/test_history.py` | 1 finding, confirmed pre-existing at HEAD before 05-08 touched the file, and shared by 5 other test files repo-wide (`deferred-items.md`) | ℹ️ INFO, not blocking |
| Nav links / rollback fixes still present (OPS-01/02/03 regression) | `grep` on `base.html`, `home.html`, `returns.py`, `corrections.py` | All previously-confirmed patterns still present | ✓ PASS |
| New CR-01 (pagination destruction) — structural code inspection | Read `history_rows.html` (`#load-more` nesting + `oob` binding) + `history_filters.html` (no `hx-swap` on selects, default `innerHTML` target `#history-tbody`) + `history.py` (`oob: is_hx`) | Confirms the exact nesting/default-swap combination that, per documented htmx oob-before-main-swap semantics, destroys `#load-more` on first filter use | ✗ FAIL — confirms new CR-01 |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files exist in this repo; this project's verification gate is its pytest suite plus direct code/template inspection (the pagination defect is a client-side htmx DOM-swap-ordering issue that a Python TestClient cannot execute, since no JS runtime runs in that harness — confirmed via structural/markup analysis against htmx's documented, deterministic oob-swap-before-main-swap behavior instead).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|--------------|--------|----------|
| OPS-01 | 05-01, 05-02, 05-06 | User can write off stock with a reason | ✓ SATISFIED | Regression-confirmed unchanged from prior pass |
| OPS-02 | 05-01, 05-03, 05-07 | User can register a return linked to the original sale; stock increases accordingly | ✓ SATISFIED | Regression-confirmed unchanged from prior pass |
| OPS-03 | 05-01, 05-04 | User can correct stock quantity (adjustment recorded as an operation, not a direct edit) | ✓ SATISFIED | Regression-confirmed unchanged from prior pass |
| OPS-04 | 05-01, 05-05, 05-08 | User can view the full operation history (what, when, how much) | ✗ BLOCKED | Old CR-01 (chrome decision) closed by 05-08 and reconfirmed here; new CR-01 (pagination control destroyed by first filter interaction) is unresolved and blocks reliable access to more than 50 operations per filter — see Gap |

No orphaned requirements — REQUIREMENTS.md maps exactly OPS-01..04 to Phase 5, matching all eight plans' `requirements:` frontmatter (05-06 → OPS-01, 05-07 → OPS-02, 05-08 → OPS-04).

**Documentation inconsistency (Info, carried over, unchanged):** REQUIREMENTS.md's traceability table still marks OPS-02/03/04 as "In Progress" even though the checkbox list above it marks all four complete. Cosmetic only.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/templates/partials/history_rows.html:44` + `app/templates/partials/history_filters.html:8-28` | — | `#load-more` oob row nested inside the same `#history-tbody` element both filter selects target with a default `innerHTML` swap (new CR-01) | 🛑 Blocker | Permanently destroys pagination access beyond page 1 for any filter with >50 matching rows, after the first filter interaction — breaks OPS-04's "complete operation trail" — see Gap |
| `app/templates/base.html` | nav | `/corrections` has no persistent top-nav entry, only reachable from `home.html` (and not reachable there with zero active products) | ⚠️ Warning | Carried over unchanged, non-blocking under normal (non-empty-catalog) operation |
| `app/templates/partials/history_rows.html:47-49` | — | "Показать ещё" button-click-only ordering (control visibly migrates position after a raw click with no filter ever used) | ⚠️ Warning | Carried over, cosmetic-only when no filter is used; subsumed by the new Blocker above once any filter select is touched |
| `app/templates/partials/writeoff_rows.html:28-30` | — | No guard against `r.op.payload` being `None`, unlike `history_rows.html` | ℹ️ Info | Not currently reachable; latent risk, carried over |
| `app/services/operations.py:51-57` | — | `/history` product filter dropdown only lists active products | ℹ️ Info | Known limitation, carried over |
| Various (IN-01 through IN-05 in `05-REVIEW.md`) | — | Minor message-precision, dead-attribute, builtin-shadowing, duplicated-validation, UX-hint-reset issues | ℹ️ Info | Cosmetic/latent only, not blocking, carried over |

No `TBD`/`FIXME`/`XXX` debt markers found in any Phase 5 file (grep across all routes/templates/tests touched by this phase).

### Human Verification Required

None required to determine status — the new pagination-destruction defect is established with high confidence via deterministic, documented htmx oob-swap-ordering semantics against the actual template/route source (not a runtime-variable or browser-version-dependent behavior), so no click-through is needed to confirm it is real for the purpose of this verification's status determination. A manual sanity check (open `/history`, use a type/product filter, confirm "Показать ещё" is gone even when more than 50 matching rows exist) is recommended once a fix lands, as routine confirmation, but is not blocking further automated verification.

### Gaps Summary

**One blocking gap, newly surfaced since the last verification pass, replacing the now-closed old CR-01 slot:** `/history`'s "Показать ещё" pagination control (`app/templates/partials/history_rows.html:44`) is nested inside `#history-tbody`, the same element both type/product `<select>`s in `app/templates/partials/history_filters.html` target with htmx's default `innerHTML` swap. Per htmx's documented out-of-band-swap ordering (oob elements are extracted and swapped in-place BEFORE the remainder of the response is swapped into the declared target), the first filter interaction on any page permanently removes `#load-more` from the DOM for the rest of that page session — `has_next` can remain `True` server-side with no way left to reach it. This directly contradicts 05-05-PLAN.md's own must-have truth ("History is paginated ... and never loads the whole ledger unbounded") and undermines ROADMAP.md Success Criterion 4 for any filtered view exceeding 50 matching operations. This was surfaced by a fresh code review (`05-REVIEW.md`, the latest commit in the repository) after plan 05-08 closed the prior (unrelated) CR-01 chrome-decision defect, and independently confirmed in this verification pass by reading the actual template/route wiring rather than taking the review's word alone. No gap-closure plan exists for it yet.

The three previously-tracked gap-closure rounds remain closed and are reconfirmed in this pass: OPS-01's missing nav link (05-06), the returns 404-vs-422/missing-rollback issues (05-07), and the old `/history` chrome-decision bug (05-08). Full regression suite: 166 passed, no regressions detected.

Two Warning-level items remain open by design (not blocking): `/corrections` lacking a persistent top-nav entry, and the "Показать ещё" button's own click-ordering cosmetic migration when no filter has been used (now subsumed by the new Blocker once any filter is touched).

**Fix scope for the remaining gap:** move `#load-more` outside `#history-tbody` (e.g. into a `<tfoot>` row) so it is never touched by the filter selects' `innerHTML` swap or the button's own `beforeend` append; have the "Показать ещё" button target `#load-more` directly (`hx-target="#load-more" hx-swap="outerHTML"`) instead of relying on `hx-swap-oob` + a shared-target `beforeend`. Add a regression test seeding more than 50 matching rows for a filtered `HX-Request` GET and asserting the load-more `<button>` is still present in the response — the current suite has no test exercising the >50-row filtered case, which is why this was not caught earlier.

---

*Verified: 2026-07-10T14:30:00Z*
*Verifier: Claude (gsd-verifier)*
