---
phase: 16-manual-cash-movements-history
verified: 2026-07-15T10:15:00Z
status: human_needed
score: 18/18 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run the app, open http://localhost:8000/finance. Withdraw «Оплата поставщику» 15,00; try a withdrawal larger than the balance; deposit «Начальный остаток» 100; filter «Тип» → Снятие; page through history."
    expected: "Balance drops after withdraw and the row appears in history; over-balance withdrawal shows «Баланс уйдёт в минус» + «Снять всё равно»; deposit raises balance; «Тип» filter shows only withdrawals; paging preserves the active filter."
    why_human: "Visual/interactive HTMX swap behaviour (oob balance refresh, warn dismiss, numbered pagination link state) cannot be confirmed by grep; needs a rendered browser session."
  - test: "Open http://localhost:8000/m/finance (or on a phone). Withdraw and deposit; trigger an over-balance withdrawal; scroll the card history, use «Тип» filter, tap «Показать ещё»."
    expected: "Withdraw/deposit persist and the balance updates; over-balance withdrawal shows the warning + «Снять всё равно»; history renders as cards with a «Тип» filter and «Показать ещё» appends the next page (no numbered bar)."
    why_human: "Mobile card-list rendering, load-more append behaviour, and touch layout are visual concerns not verifiable programmatically."
---

# Phase 16: manual-cash-movements-history Verification Report

**Phase Goal:** Operator can manually withdraw (categorized) or deposit funds, with a warn-but-allow negative-balance check, and browse all movements in a paginated/filterable history.
**Verified:** 2026-07-15T10:15:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-01 honoured: manual movements modeled by extending CASH_CATEGORIES, no type column/migration; direction in amount sign, kind in category prefix | ✓ VERIFIED | `app/models.py:69-100` — 7 manual keys appended to CASH_CATEGORIES; no `type` column added to CashMovement; direction derived from bucket at `finance.py:114-135` |
| 2 | 5 withdrawal + 2 deposit categories exist as CASH_CATEGORIES keys with RU labels | ✓ VERIFIED | `models.py:73-80` — withdrawal_supplier/salary/rent/utilities/other + deposit_opening/correction with exact RU labels |
| 3 | 4 coarse buckets (Продажа/Возврат/Снятие/Внесение) derivable via single grouping map | ✓ VERIFIED | `models.py:88-108` CASH_BUCKETS + CASH_BUCKET_LABELS; used via `.in_()` at `finance.py:195-198` |
| 4 | CASH_CATEGORIES + bucket-label map render as Jinja globals (no UndefinedError) | ✓ VERIFIED | `app/routes/__init__.py:27-28` env.globals assignments; consumed in `cash_history_rows.html:26,48` |
| 5 | record_manual_movement wraps single write path, server-applied sign, D-04 comment rule, D-05 negative gate, cash_history_view mirrors history_view | ✓ VERIFIED | `finance.py:87-162` (wrapper) + `174-211` (read); delegates to `record_cash_movement` at :151 |
| 6 | Withdrawal writes one negative row (server sign), deposit one positive row | ✓ VERIFIED | `finance.py:135` `amount_cents = -parsed if is_withdrawal else parsed`; tests pass |
| 7 | Zero/blank/non-integer/negative amount, unknown category, blank mandatory comment → ZERO writes + RU error | ✓ VERIFIED | `finance.py:116-139` validation returns `(None, errors)` before any write; 75 finance tests green |
| 8 | Withdrawal driving balance negative with confirm!='1' → negative_balance warn, ZERO writes; confirm=='1' writes | ✓ VERIFIED | `finance.py:143-147` live `compute_balance(session)+amount_cents<0` gate |
| 9 | cash_history_view returns paginated, bucket-filtered, newest-first page over all movements | ✓ VERIFIED | `finance.py:192-211` — order desc, `.in_(cats)` filter, server clamp, count/total_pages |
| 10 | Desktop /finance: two inline forms + «Тип»-filterable paginated history (D-06/D-07) | ✓ VERIFIED | `routes/finance.py:63-231`; `pages/finance.html`; `cash_history_rows.html` |
| 11 | On /finance operator can withdraw (mandatory category+comment); balance drops | ✓ VERIFIED | POST /finance/withdraw `finance.py:112-175` + oob balance refresh `_movement_success:96-109` |
| 12 | On /finance operator can deposit; balance rises | ✓ VERIFIED | POST /finance/deposit `finance.py:178-231` |
| 13 | Negative withdrawal re-renders form (HTTP 200) with warn + «Снять всё равно», writes nothing until confirmed | ✓ VERIFIED | `finance.py:156-163` returns 200; `cash_negative_balance.html` confirm control |
| 14 | /finance shows paginated «Тип»-filterable history of every movement | ✓ VERIFIED | GET /finance/history `finance.py:75-93`; bucket select + pagination include in template |
| 15 | Mobile /m/finance parity: two shared forms + paginated «Тип»-filterable history | ✓ VERIFIED | `routes/mobile_finance.py` reuses shared partials with finance_base='/m/finance' |
| 16 | On /m/finance operator can withdraw/deposit reusing shared forms; balance updates | ✓ VERIFIED | `mobile_finance.py:121-237` + oob balance refresh `_movement_success:56-74` |
| 17 | Mobile negative-balance warn «Баланс уйдёт в минус» + «Снять всё равно», writes nothing until confirmed | ✓ VERIFIED | `mobile_finance.py:163-170` returns 200; shared `cash_negative_balance.html` |
| 18 | Mobile «Финансы» shows card-list history with «Тип» filter + «Показать ещё» load-more (not numbered) | ✓ VERIFIED | `cash_history_cards.html` + `cash_history_load_more.html:9-12`; 0 numbered-pagination refs on mobile |

**Score:** 18/18 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | Extended CASH_CATEGORIES + CASH_BUCKETS + CASH_BUCKET_LABELS | ✓ VERIFIED | All 9 keys, buckets, labels present (:69-108) |
| `app/routes/__init__.py` | CASH_CATEGORIES + CASH_BUCKET_LABELS as globals | ✓ VERIFIED | env.globals set (:27-28) |
| `app/services/finance.py` | record_manual_movement + cash_history_view | ✓ VERIFIED | Both present and wired (:87, :174) |
| `app/routes/finance.py` | POST withdraw/deposit, GET history, full-page GET | ✓ VERIFIED | All 4 handlers present; router registered `main.py:72` |
| `app/routes/mobile_finance.py` | Mobile POST/GET reusing service+forms | ✓ VERIFIED | All handlers present; router registered `main.py:83` |
| `partials/withdraw_form.html` | Shared снятие form + conditional warn | ✓ VERIFIED | finance_base-parameterised (2 refs), negative_balance include |
| `partials/deposit_form.html` | Shared внесение form | ✓ VERIFIED | finance_base-parameterised |
| `partials/cash_negative_balance.html` | Warn + confirm control | ✓ VERIFIED | «Снять всё равно» hx-vals confirm=1 |
| `partials/cash_history_rows.html` | Desktop table + bucket filter + numbered pagination | ✓ VERIFIED | id, select, pagination include |
| `mobile_partials/cash_history_cards.html` | Card stack per movement | ✓ VERIFIED | Present |
| `mobile_partials/cash_history_load_more.html` | «Показать ещё» has_next sentinel | ✓ VERIFIED | oob + has_next + page+1 |
| `tests/test_finance.py` | Service + desktop + mobile tests | ✓ VERIFIED | 75 tests pass incl. WR-01 fix tests |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| routes/__init__ | models CASH_CATEGORIES/LABELS | env.globals | ✓ WIRED | :27-28 |
| record_manual_movement | record_cash_movement | delegated insert | ✓ WIRED | `finance.py:151` |
| negative gate | compute_balance | live SUM | ✓ WIRED | `finance.py:143,145` |
| cash_history_view | CASH_BUCKETS | `.get(bucket)` → `.in_()` | ✓ WIRED | `finance.py:195-198` |
| routes/finance | record_manual_movement | POST withdraw/deposit | ✓ WIRED | :138,203 |
| routes/finance history | cash_history_view + page_window | numbered pagination | ✓ WIRED | :45-46 |
| mobile_pages/finance | shared withdraw/deposit forms | finance_base='/m/finance' | ✓ WIRED | shared partials reused |
| mobile_finance | record_manual_movement + cash_history_view | reused service | ✓ WIRED | :146,209,46 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| cash_history_rows.html | `rows` | `cash_history_view` → `select(CashMovement)` ORM query | Yes — real DB scan | ✓ FLOWING |
| cash_balance.html | `balance_cents` | `compute_balance` live `SUM(amount_cents)` | Yes | ✓ FLOWING |
| cash_history_cards.html | `rows` | `cash_history_view` (same service) | Yes | ✓ FLOWING |
| withdraw/deposit write | `amount_cents` | `to_cents` parse + server sign → `record_cash_movement` insert | Yes — real insert | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full finance test suite | `uv run pytest tests/test_finance.py -q` | 75 passed, 1 warning in 12.70s | ✓ PASS |
| No `\|safe` in finance templates | grep across 5 render templates | none found | ✓ PASS |
| No numbered pagination on mobile | grep pagination.html in 3 mobile files | 0 | ✓ PASS |
| WR-01 cross-direction guard tests | grep 4 reject-category test names | all 4 present (:1041-1085) | ✓ PASS |
| finance_base parameterisation | grep in 3 shared partials | 2 refs each (no hardcoded /finance) | ✓ PASS |

### Probe Execution

Not applicable — this phase declares no probes; verification is via the pytest suite (run above).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FIN-03 | 16-01/02/03/04 | Categorized manual withdrawal with mandatory comment | ✓ SATISFIED | 5 withdrawal categories; D-04 comment rule (`finance.py:138`); withdraw routes + forms; REQUIREMENTS.md marks Complete |
| FIN-04 | 16-01/02/03/04 | Manual deposit (opening/correction) with comment | ✓ SATISFIED | 2 deposit reasons; deposit routes + forms; REQUIREMENTS.md Complete |
| FIN-05 | 16-02/03/04 | Negative-balance warn-but-allow | ✓ SATISFIED | Live gate `finance.py:143-147`; confirm=='1' override; warn template |
| FIN-07 | 16-01/02/03/04 | Cash-movement history with pagination/filter | ✓ SATISFIED | `cash_history_view` + desktop numbered + mobile load-more, «Тип» bucket filter |

No orphaned requirements: REQUIREMENTS.md maps exactly FIN-03/04/05/07 to Phase 16, all claimed by plans and all satisfied. (FIN-06 «Финансы» section is mapped to Phase 15, out of scope here.)

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TBD/FIXME/XXX in modified files; no stub returns; no hardcoded empty rendered data | ℹ️ Info | None — all data paths flow from real ORM queries |

Note: `except Exception` guards in the routes are the sanctioned UI-SPEC "block error, never a raw 500" pattern with `logger.exception` + rollback + 422 — not swallowed errors. Context-provided note: WR-01 warning was fixed in commit b143ccb (verified: 4 boundary-guard tests present and passing); 3 cosmetic info items remain open by design.

### Human Verification Required

#### 1. Desktop /finance interactive flow

**Test:** Run the app, open http://localhost:8000/finance. Withdraw «Оплата поставщику» 15,00; try a withdrawal larger than the balance; deposit «Начальный остаток» 100; filter «Тип» → Снятие; page through history.
**Expected:** Balance drops and row appears; over-balance withdrawal shows «Баланс уйдёт в минус» + «Снять всё равно»; deposit raises balance; filter shows only withdrawals; paging preserves the filter.
**Why human:** HTMX oob swap behaviour, warn dismiss, and pagination link state need a rendered browser session.

#### 2. Mobile /m/finance interactive flow

**Test:** Open http://localhost:8000/m/finance. Withdraw and deposit; trigger an over-balance withdrawal; use «Тип» filter and tap «Показать ещё».
**Expected:** Movements persist and balance updates; warning + «Снять всё равно» appears; history renders as cards with a «Тип» filter and «Показать ещё» appends the next page (no numbered bar).
**Why human:** Mobile card layout, load-more append, and touch UX are visual concerns.

### Gaps Summary

No gaps. All 18 must-have truths are verified against the codebase, all 12 artifacts exist / are substantive / are wired / have real data flowing, all 8 key links are connected, and all 4 requirements (FIN-03/04/05/07) are satisfied. The 75-test finance suite passes. Status is `human_needed` solely because both Plan 03 and Plan 04 carry deliberate end-of-phase `<human-check>` items for visual/interactive UI confirmation (desktop + mobile) that cannot be verified programmatically — these are not failures.

---

_Verified: 2026-07-15T10:15:00Z_
_Verifier: Claude (gsd-verifier)_
