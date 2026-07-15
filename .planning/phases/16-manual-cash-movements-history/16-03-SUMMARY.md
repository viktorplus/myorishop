---
phase: 16-manual-cash-movements-history
plan: 03
subsystem: finance
tags: [finance, htmx, jinja2, routes, templates, pagination, tdd, xss-mitigation]

# Dependency graph
requires:
  - phase: 16-manual-cash-movements-history (plan 01)
    provides: CASH_CATEGORIES, CASH_BUCKETS, CASH_BUCKET_LABELS (globals)
  - phase: 16-manual-cash-movements-history (plan 02)
    provides: record_manual_movement (single write wrapper), cash_history_view (paginated read), compute_balance
  - phase: 14-list-pagination
    provides: page_window + partials/pagination.html (numbered bar)
provides:
  - POST /finance/withdraw — thin route over record_manual_movement (warn 200 / errors 422 / success)
  - POST /finance/deposit — thin route over record_manual_movement (errors 422 / success, no negative branch)
  - GET /finance/history — HX rows partial vs full page, numbered pagination, bucket-preserving extra_qs
  - full-page GET /finance — balance + two forms + history block
  - Shared finance_base-parameterised partials (withdraw_form, deposit_form, cash_negative_balance) ready for Plan 04 mobile reuse
affects: [16-04-routes-templates-mobile]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Thin desktop routes delegating all cash validation to the Plan 02 service (routes never write cash — D-00c)"
    - "Shared finance_base-parameterised form partials (one markup, two surfaces) — mirrors UI-SPEC Q2"
    - "Success response composes fresh form + out-of-band #cash-balance + #cash-history-rows (mobile_history sibling-concat)"
    - "Desktop cash history = numbered page_window + partials/pagination.html with extra_qs bucket preservation (mirrors history.py)"

key-files:
  created:
    - app/templates/partials/cash_balance.html
    - app/templates/partials/withdraw_form.html
    - app/templates/partials/deposit_form.html
    - app/templates/partials/cash_negative_balance.html
    - app/templates/partials/cash_history_rows.html
  modified:
    - app/routes/finance.py
    - app/templates/pages/finance.html
    - tests/test_finance.py

key-decisions:
  - "Deposit route relabels the service's generic category error to «Выберите основание.» (UI-SPEC §D) — the «Основание» field wording differs from withdraw's «Категория»"
  - "negative-balance warn passes balance/amount into the partial via a {% with %} block so cash_negative_balance.html reads {{ balance | cents }} / {{ amount | cents }} verbatim per UI-SPEC §B"
  - "HX-vs-full-page detection on GET /finance/history mirrors history.py (HX-Request header) so the same route serves the swappable partial and the full page"

patterns-established:
  - "Manual cash forms shared desktop↔mobile via finance_base context var; wrap ids reused (pages never co-render)"
  - "Cash history rows partial simplified from history_rows.html: 4 columns, coarse-bucket filter, autoescaped note/label"

requirements-completed: [FIN-03, FIN-04, FIN-05, FIN-07]

# Metrics
duration: 18min
completed: 2026-07-15
---

# Phase 16 Plan 03: Desktop Manual Cash Movements & History Summary

**Desktop «Финансы» write + read surface: thin `POST /finance/withdraw` and `/finance/deposit` over `record_manual_movement` (negative-warn at HTTP 200, errors 422, success with out-of-band balance + history refresh), `GET /finance/history` with numbered bucket-preserving pagination, and a full-page `GET /finance` rendering the balance, two shared `finance_base`-parameterised forms, and an autoescaped, «Тип»-filterable history table.**

## Performance

- **Duration:** ~18 min
- **Tasks:** 2 (both TDD: RED test commit -> GREEN feat commit)
- **Files created:** 5 partials; **modified:** 3 (route, page, tests)

## Accomplishments
- `POST /finance/withdraw` is a THIN route: it parses `Form("")` strings, delegates every check to `record_manual_movement`, then branches exactly like `writeoffs.py` — `result.get("negative_balance")` -> re-render the снятие form at **HTTP 200** (htmx swaps 200; T-16-05) with a «Снять всё равно» confirm control and ZERO writes; `errors` -> 422 with the UI-SPEC RU message; success -> a composed response of a fresh empty form + out-of-band `#cash-balance` and `#cash-history-rows` refreshes. A defensive `try/except -> rollback -> 422` guard mirrors `writeoff_create`.
- `POST /finance/deposit` is the two-branch variant (errors 422 / success) — no negative branch (D-05, deposits only increase the balance) — and relabels a blank basis to «Выберите основание.» (UI-SPEC §D).
- `GET /finance/history` mirrors `history.py`: `cash_history_view` + `page_window`, `extra_qs` re-serializes the active `bucket` onto every pagination link, HX-Request returns the chrome-less `cash_history_rows.html`, a plain GET returns the full page.
- Five templates: `cash_balance.html` (oob-swappable), shared `withdraw_form.html`/`deposit_form.html` (parameterised by `finance_base`, no hardcoded `/finance`), the conditional `cash_negative_balance.html` warn (mirrors `writeoff_oversell.html`), and `cash_history_rows.html` (4-column table + `CASH_BUCKET_LABELS` «Тип» filter + shared `partials/pagination.html`). `note` and category labels render via Jinja autoescape only — **grep confirms 0 `|safe`** in every new template.

## Task Commits

Each task committed atomically (TDD: test -> feat):

1. **Task 1 RED: failing desktop withdraw/deposit web tests** - `40a2a77` (test)
2. **Task 1 GREEN: withdraw/deposit POST routes + shared forms** - `13f8116` (feat)
3. **Task 2 RED: failing desktop cash-history web tests** - `6aabfce` (test)
4. **Task 2 GREEN: GET /finance/history + history block + oob refresh** - `47e677b` (feat)

## Files Created/Modified
- `app/routes/finance.py` - Extended from a read-only balance route to POST withdraw/deposit + GET history + a history-aware full-page GET; added `_history_context` and `_movement_success` helpers; imports `record_manual_movement`, `cash_history_view`, `page_window`, `urlencode`. Routes never write cash directly.
- `app/templates/pages/finance.html` - Balance partial + «Снять деньги»/«Внести деньги» forms + «История движений» block.
- `app/templates/partials/{cash_balance,withdraw_form,deposit_form,cash_negative_balance,cash_history_rows}.html` - New (see Accomplishments).
- `tests/test_finance.py` - Added 14 desktop web tests (`test_web_withdraw_*`, `test_web_deposit_*`, `test_web_negative_*`, `test_web_cash_history_*`, `test_web_finance_page_*`).

## Decisions Made
- The negative-balance partial receives `balance`/`amount` via a `{% with %}` wrapper around the include (the service returns them under `result["negative_balance"]`), keeping the partial's body identical to UI-SPEC §B (`{{ balance | cents }}, снимаете {{ amount | cents }}`).
- Deposit category error is relabeled in the route (not the service) to «Выберите основание.» so the shared service message «Выберите категорию.» stays correct for withdraw.

## Deviations from Plan

**1. [Test authoring only] `test_web_cash_history_hx_returns_partial_only` distinguishes filtered rows by amount, not label.**
- **Found during:** Task 2 GREEN.
- **Issue:** The «Тип» filter `<select>` always renders all four bucket labels (including «Продажа») as `<option>`s, so an initial assertion `"Продажа" not in text` failed even though the sale *row* was correctly filtered out.
- **Fix:** Assert on row amounts (`"-30,00" in`, `"125,00" not in`) instead of the ambiguous label. Implementation was correct; only the test assertion was refined.
- **Files modified:** tests/test_finance.py
- **Commit:** `47e677b` (part of Task 2 GREEN)

No source-code deviation from the plan's `<action>` steps; routes stay thin and all validation remains in the Plan 02 service.

## Issues Encountered
- Comments in the new templates literally contained the token `|safe` (e.g. «never |safe»), which tripped the acceptance grep `grep -c "|safe" ... == 0`. Reworded to «the safe filter is never applied» — no functional change; grep now returns 0 for all three checked templates.

## User Setup Required
None - no external service configuration required. Manual browser verification (`run.bat` -> `http://localhost:8000/finance`) is listed in the plan's `<human-check>` and deferred to end-of-phase per config (`human_verify_mode: end-of-phase`).

## Next Phase Readiness
- Desktop `/finance` delivers all four ROADMAP criteria: withdraw (mandatory category + comment), deposit, negative-balance warn-but-allow, and a paginated «Тип»-filterable history.
- Plan 04 (mobile) can reuse `withdraw_form.html` / `deposit_form.html` / `cash_negative_balance.html` verbatim by passing `finance_base="/m/finance"`, and forks only the history presentation (mobile card stack + load-more, per UI-SPEC Q2).
- Full suite green: 619 passed; `test_finance.py` 56/56; ruff clean on `app/routes/finance.py`; 0 `|safe` in new templates.

## Threat Flags

None — no new trust boundary beyond the plan's `<threat_model>`. T-16-05 (warn at 200) and T-16-06 (autoescaped note/label) are mitigated and asserted by tests.

## Self-Check: PASSED

- FOUND: app/routes/finance.py (POST /finance/withdraw, /finance/deposit, GET /finance/history)
- FOUND: app/templates/partials/cash_balance.html, withdraw_form.html, deposit_form.html, cash_negative_balance.html, cash_history_rows.html
- FOUND: app/templates/pages/finance.html (forms + history block)
- FOUND commits: 40a2a77, 13f8116, 6aabfce, 47e677b
- 56/56 test_finance.py pass; 619/619 full suite pass; ruff clean; 0 `|safe` in new templates.

---
*Phase: 16-manual-cash-movements-history*
*Completed: 2026-07-15*
