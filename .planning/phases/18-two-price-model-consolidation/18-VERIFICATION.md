---
phase: 18-two-price-model-consolidation
verified: 2026-07-16T11:58:07Z
status: human_needed
score: 5/5 roadmap truths verified (server-side); 1 requires by-eye colour sign-off
overrides_applied: 0
human_verification:
  - test: "Criterion 3 visual colour sign-off — product card, receipt (desktop+mobile), sale (desktop+mobile)"
    expected: "Typing ДЦ/ПЦ below the code's CatalogPrice reference shows amber border #b45309/#fef9e7; above shows blue border #2563eb/#eff6ff (never #e8effd, the existing search-match tint); exactly equal shows neither. No cue ever appears on «Минимальная цена продажи». A code with no CatalogPrice row shows the muted «нет справочной цены» hint and no colour. The cue still fires after an HTMX OOB autofill swap on #cost/#sale."
    why_human: "TestClient does not execute JavaScript — price-cue.js's classList toggle and the resulting border/background colours can only be confirmed by eye in a real browser. Server-side, data-ref-cents presence/absence and the CSS class definitions are already asserted by the automated suite (711 passed)."
  - test: "Confirm the operator is not expecting a text badge next to the colour cue"
    expected: "No text/icon badge (e.g. «ниже справочной») renders next to the field — only a coloured border + background tint. This is a known, intentional deviation from the original design note (D-14 said 'border + tint + short text badge'); the code review (WR-03) found no badge was ever implemented, and the fix corrected the code comment rather than adding one, explicitly noting the cue does NOT meet WCAG 1.4.1 (Use of Color) as shipped. If the operator needs the accessibility text badge, that is a follow-up, not a shipped regression."
    why_human: "This is a design-intent question (is colour-only acceptable to the operator/business), not something a grep or test can decide."
---

# Phase 18: Two-Price Model Consolidation (ДЦ/ПЦ) Verification Report

**Phase Goal:** Every price the operator sees or edits anywhere in the app is one of exactly two — ДЦ (cost/distributor) or ПЦ (sale/catalog) — and can be corrected from wherever it is noticed.
**Verified:** 2026-07-16T11:58:07Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator sees exactly two price fields — ДЦ/ПЦ — on product card, dictionary entry, receipt, sale (desktop+mobile); no third/fourth price field anywhere | ✓ VERIFIED | `products.catalog_cents` column absent from live DB schema (`PRAGMA table_info(products)` — only `cost_cents`/`sale_cents`/`min_sale_cents`); `grep -rn catalog_cents app/ tests/ scripts/ alembic/` returns only intentional historical/comment references (D-04 ledger payload, `price_history.html:22` fallback label, migration file itself); `product_form.html` has exactly ДЦ (`:69`)/ПЦ (`:77`) named inputs, catalog input deleted, `min_sale` regrouped as a guardrail with no `data-ref-cents`; `catalog_detail.html` shows ПЦ/ДЦ columns read-only; `app/routes/mobile_receipts.py` has zero `catalog` references (Pitfall 1 fully resolved); CSV export (`export.py`) and list views (`categories.html`, `product_rows.html`, `receipt_rows.html`) have no catalog column |
| 2 | Operator can edit ДЦ or ПЦ from any of the four entry points, and the change is saved from where it was made | ✓ VERIFIED | Product card: standard form POST to `/products/{id}`. Receipt: `services/receipts.py:169-196` writes back to `Product.cost_cents`/`sale_cents` with one `price_change` op per changed field, PD-8 "empty never clears" intact (D-15 regression preserved — code unchanged from prior milestone). Sale: confirmed **no** `product.cost_cents =` / `product.sale_cents =` write exists anywhere in `services/sales.py` (grep empty) — price stays scoped to the operation (D-15/D-16). Dictionary (`catalog_detail.html:37`): «изменить цену» → `/products/new?code={code}`, which redirects to the existing product's edit form or prefills a new one (`routes/products.py:170-199`, D-18) |
| 3 | Typing ДЦ/ПЦ below reference shows yellow; above shows blue; matching shows neither | ✓ VERIFIED (server-side) / ? HUMAN NEEDED (visual) | `price-cue.js` delegated listener present, computes cents client-side (parity with `to_cents`), toggles `.price-below`/`.price-above`; `style.css:299-300` defines `#b45309`/`#fef9e7` (below) and `#2563eb`/`#eff6ff` (above), confirmed distinct from the pre-existing `#e8effd` selection/match token; `data-ref-cents` verified rendered (guarded `is not none`, WR-01 fixed) on product card ДЦ/ПЦ, receipt ДЦ/ПЦ (desktop+mobile, static+OOB via shared `receipt_price_inputs.html`), and every sale ПЦ input (`sale_row.html`, `sale_lookup.html`, `sale_batch_pick.html`, mobile `sale_step_qty_price.html`); `min_sale` input carries no `data-ref-cents` anywhere. Actual colour rendering requires a browser — TestClient runs no JS — so this is deferred to human sign-off (harvested from 18-08 Task 3, see Human Verification below) |
| 4 | Stock/sales/profit figures recorded before consolidation still display as recorded — no historical money data lost or re-interpreted | ✓ VERIFIED | Live-DB canary: `SELECT count(*) FROM operations WHERE type='receipt' AND payload LIKE '%catalog_cents%'` = **8** (matches pre-migration count exactly — no historical payload lost). Ledger append-only triggers untouched (`app/db.py`). Migration `0014` is a native `op.drop_column` on `products` only, never touches `operations`. `price_history.html:22`'s `catalog_cents` label branch intentionally kept (renders for 0 live rows, D-04) |
| 5 | Selling below configured minimum still shows the warn-but-allow warning (PRICE-01 regression guard) | ✓ VERIFIED | All 9 named PRICE-01 guard tests pass, byte-for-byte unmodified (`git log` shows no edits to these test bodies across phase commits); `services/sales.py`'s `below_minimum` check logic unchanged; ran `pytest tests/test_sales.py tests/test_mobile_sales.py -k "negative_price_rejected or below_minimum or price_below_minimum"` — 9 passed |

**Score:** 5/5 truths hold on code evidence; truth 3's colour rendering additionally needs a human by-eye pass (deferred per project's `end-of-phase` human-verify convention, not a code gap).

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|---|---|---|---|
| **PROD-05** | Pricing reduced to exactly ДЦ/ПЦ; `catalog_cents` removed; `min_sale_cents` exempt | ✓ SATISFIED | `products.catalog_cents` dropped from live DB (alembic head `0014` confirmed), ORM (`app/models.py:150-160` — only `cost_cents`/`sale_cents`/`min_sale_cents`), all app code (36-site removal surface fully swept, verified via grep), CSV export, and all list/detail templates. `_PRICE_FIELDS = ("cost_cents", "sale_cents", "min_sale_cents")` (`services/catalog.py:159`). REQUIREMENTS.md's checkbox still shows unchecked/"Pending" — this is a stale tracking artifact, not a code gap (see Anti-Patterns/Info below) |
| **PROD-06** | Colour cue: below=yellow, above=blue, at any entry point | ✓ SATISFIED (server-side); visual confirmation pending | `reference_prices_for_code` (D-08/D-22 fix, `services/pricing.py:35-46`) returns ДЦ/ПЦ independently, never gating one on the other; `price-cue.js` + CSS tokens shipped; `data-ref-cents` wired on every priced input across card/receipt/sale, desktop+mobile (verified above). Colour-by-eye is the one item routed to human verification |
| **PROD-07** | ДЦ/ПЦ editable at any stage, saved from wherever made | ✓ SATISFIED | Same evidence as Truth 2 above — receipt write-back (D-15, pre-existing, confirmed unregressed), sale explicitly scoped/non-writing (D-16, confirmed via grep), dictionary redirect to product card (D-18, confirmed in `catalog_detail.html`+`routes/products.py`). REQUIREMENTS.md's checkbox shows "Pending" — stale tracking artifact, not a code gap |

**Note on REQUIREMENTS.md tracking:** `.planning/REQUIREMENTS.md` lines 35/37 still show `[ ]`/"Pending" for PROD-05 and PROD-07 while PROD-06 shows `[x]`/"Complete" — this is inconsistent with the actual code state (all three are implemented and covered above) and is very likely a checklist that was not updated as part of phase close. Flagged as an info item for the human to reconcile, not a verification gap.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `alembic/versions/0014_drop_product_catalog_cents.py` | Native `op.drop_column` migration | ✓ VERIFIED | Exists; live DB confirmed at head `0014`; column confirmed absent via `PRAGMA table_info` |
| `app/models.py` | `Product` with exactly `cost_cents`/`sale_cents`/`min_sale_cents` | ✓ VERIFIED | No `catalog_cents` mapped column |
| `app/services/pricing.py::reference_prices_for_code` | ДЦ/ПЦ reference, independent lookup | ✓ VERIFIED | D-08/D-22 fix confirmed in place, docstring corrected |
| `app/static/price-cue.js` | Delegated input listener | ✓ VERIFIED | 23 lines, single `addEventListener('input', ...)`, reads `data-ref-cents`, toggles classes, never parses for submission |
| `app/static/style.css` (`.price-below`/`.price-above`) | Cue CSS tokens | ✓ VERIFIED | `#b45309`/`#fef9e7` and `#2563eb`/`#eff6ff` present; comment now honestly states no text badge and WCAG 1.4.1 is not met as shipped (post WR-03 fix) |
| `app/services/sales.py` (`SALE_CARD_FILL_HINT`/`SALE_BATCH_FILL_HINT`) | Sale-scope hint constants | ✓ VERIFIED | Both constants defined with the "сохранится только в этой продаже" clause, used at all 6 call sites across `sales.py`/`mobile_sales.py` |
| `app/routes/receipts.py` (`CARD_FILL_HINT`) | Receipt write-back hint | ✓ VERIFIED (pre-existing, unregressed) | `CARD_FILL_HINT` present, used |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `product_form.html` ДЦ/ПЦ inputs | `latest_price.consultant_cents`/`consumer_cents` | `data-ref-cents` | ✓ WIRED | Guarded `is not none`, never `\| safe` |
| `receipt_price_inputs.html` | `reference_prices_for_code` | `ref_cents` param (static + OOB, single source) | ✓ WIRED | WR-01 truthy-check bug fixed; one param covers both render paths (Pitfall 2 resolved) |
| Sale `price[]` inputs (row/lookup/batch-pick, desktop+mobile) | `reference_prices_for_code` (ПЦ only) | `ref_pc_cents` → `data-ref-cents` | ✓ WIRED | Independently resolved per line in `_build_lines`/`sale_lookup`/`sale_batch_pick` |
| `base.html` + `mobile_base.html` | `/static/price-cue.js` | `<script defer>` duplicated in both standalone bases | ✓ WIRED | Confirmed both bases load the script |
| `catalog_detail.html` «изменить цену» | Product card | `/products/new?code=` → redirect-or-prefill | ✓ WIRED | `routes/products.py:170-199` |
| Receipt `register_receipt` | `Product.cost_cents`/`sale_cents` | Direct write-back + `price_change` op | ✓ WIRED (pre-existing) | D-15 regression-checked, unchanged |
| Sale services | `Product` | (intentionally NOT wired) | ✓ CONFIRMED ABSENT | grep for `product.cost_cents =`/`product.sale_cents =` in `services/sales.py` returns nothing (D-15/D-16) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full regression suite | `uv run pytest -q` | 711 passed, 0 failed (126s) | ✓ PASS |
| PRICE-01 guard tests | `pytest tests/test_sales.py tests/test_mobile_sales.py -k "negative_price_rejected or below_minimum or price_below_minimum"` | 9 passed | ✓ PASS |
| Live DB at migration head | `PRAGMA table_info`, `alembic_version` query | head=`0014`, `catalog_cents` absent | ✓ PASS |
| Ledger payload canary (criterion 4) | `SELECT count(*) FROM operations WHERE type='receipt' AND payload LIKE '%catalog_cents%'` | 8 | ✓ PASS |
| Pre-migration backup exists (D-24 safety net) | directory listing of `backups/` | `myorishop_pre-0014_20260716_122204.db` present, contains all 6 discarded `(code, catalog_cents)` pairs recoverable | ✓ PASS |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `app/static/style.css` | 289-297 | Comment now correctly states the cue is border+tint only, no text badge, and WCAG 1.4.1 is NOT met — this documents a real gap vs. CONTEXT.md's D-14 ("border + tint + short text badge") but was a deliberate code-review-fix decision (WR-03), not an oversight | ⚠️ WARNING | Roadmap criterion 3 only requires colour (satisfied); the accessibility text-badge design point from CONTEXT.md D-14 was not shipped. Non-blocking for this phase's stated success criteria, but worth an explicit accept/reject decision |
| `.planning/phases/18-two-price-model-consolidation/18-04-SUMMARY.md` (D-24) | — | The 6 discarded `(code, catalog_cents)` pairs were never recorded in any phase summary (the executing worktree had no live-DB access) | ⚠️ WARNING | Not a data-loss issue — the pre-migration backup file (`backups/myorishop_pre-0014_20260716_122204.db`) still holds all 6 pairs, extracted during this verification: `32021`→89000, `31670`→75000, `42125`→42000, `33456`→49000, `50012`→56000, `70099`→25000. D-24's audit-trail intent is satisfiable retroactively from the backup; recommend pasting this list into the phase record for completeness |
| `.planning/REQUIREMENTS.md` | 35, 37 | PROD-05 and PROD-07 checkboxes/status still show unchecked/"Pending" despite being fully implemented | ℹ️ INFO | Stale tracking doc; not a code gap — recommend updating checkboxes |
| `app/templates/partials/receipt_lookup.html` | 15 | Dead `"catalog"` key in the `labels` dict (IN-01, reviewed, accepted as harmless) | ℹ️ INFO | `fill_fields` is permanently `("cost", "sale")`, so this key is never read; cosmetic only |
| `app/services/receipts.py` | 295 | `lookup_prefill` still returns an unused `"catalog"` dict key (IN-02, reviewed, accepted as harmless) | ℹ️ INFO | No caller reads it; cosmetic residue |

No `TBD`/`FIXME`/`XXX` markers found in any file modified by this phase.

## Human Verification Required

### 1. Criterion 3 — Colour cue visual sign-off

**Test:** Open the app (`run.bat`). On a product card for a code WITH a CatalogPrice row, type a ДЦ below `consultant_cents`, then above, then exactly equal; repeat for ПЦ against `consumer_cents`. Repeat on the desktop receipt form and desktop sale basket, then the mobile receipt wizard and mobile sale wizard (D-20: mobile's only two price surfaces). Confirm the blue is `#eff6ff` and never `#e8effd` (the existing search-match/selection tint). Confirm no cue ever appears on «Минимальная цена продажи». Confirm a code with no CatalogPrice row shows the muted «нет справочной цены» hint with no colour. After a code lookup that OOB-swaps `#cost`/`#sale` (or the sale basket's price cell), type again and confirm the cue still fires.
**Expected:** Amber border/tint below reference, blue border/tint above, no cue when equal or when no reference exists; no cue ever on min_sale; cue survives OOB swaps.
**Why human:** TestClient does not execute JavaScript — this is the only way to confirm the actual rendered colours and the client-side listener's live behaviour.

### 2. Text-badge expectation check

**Test:** Confirm whether the operator expects a visible text label (e.g. «ниже справочной») alongside the colour, per the original CONTEXT.md design note (D-14), or whether colour-only (as shipped) is acceptable.
**Expected:** Either accept the shipped colour-only cue, or file a follow-up to add the text badge (current code explicitly documents non-compliance with WCAG 1.4.1 as shipped).
**Why human:** This is a product/accessibility-policy decision, not a code-correctness question — roadmap criterion 3 as written only requires colour, so this does not block the phase, but the deviation from the CONTEXT.md decision should be a conscious choice.

## Gaps Summary

No blocking gaps found. All 5 ROADMAP success criteria and all 3 phase requirements (PROD-05/06/07) are backed by direct codebase evidence: the `catalog_cents` column and every application reference to it are removed (live DB confirmed at migration head `0014`); the two-price labelling is consistent everywhere; the reference-deviation cue is server-wired end-to-end across every price surface (product card, dictionary redirect, receipt, sale, desktop and mobile) with the correct CSS tokens and a working delegated JS listener; historical ledger data is provably intact (8/8 payload canary); and PRICE-01's 9 regression-guard tests are green and byte-for-byte unmodified. The full test suite passes (711/711).

The only outstanding items are (a) a human by-eye confirmation of the cue's actual rendered colours in a browser — unavoidable since the test stack runs no JavaScript — and (b) two non-blocking documentation gaps (the D-14 text badge was consciously not shipped per a code-review decision, and the D-24 audit-trail pairs were never pasted into a summary, though they remain fully recoverable from the pre-migration backup, and are reproduced above). REQUIREMENTS.md's checkbox states for PROD-05/PROD-07 are stale and should be updated to reflect completion.

---

_Verified: 2026-07-16T11:58:07Z_
_Verifier: Claude (gsd-verifier)_
