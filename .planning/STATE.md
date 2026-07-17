---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: UX Overhaul & Navigation Restructure
status: ready_to_plan
stopped_at: Phase 21 complete (5/5) — ready to discuss Phase 22
last_updated: 2026-07-17T09:38:56.239Z
last_activity: 2026-07-17 -- Phase 21 execution started
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 21
  completed_plans: 21
  percent: 43
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-15)

**Core value:** The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.
**Current focus:** Phase 22 — sales page rebuild

## Current Position

Phase: 22
Plan: Not started
Status: Ready to plan
Last activity: 2026-07-17

Progress: [░░░░░░░░░░] 0% (v2.0)

## Performance Metrics

**Velocity:**

- Total plans completed: 65 (v1.0-v1.3)
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1-17 | 59 | - | - |
| 19 | 1 | - | - |
| 21 | 5 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion. Per-plan v1.0-v1.3 timings archived with their milestones.*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table (v1.0-v1.3 milestone decisions archived there and in `.planning/RETROSPECTIVE.md`).

- **v2.0 roadmap (2026-07-15):** 46 requirements grouped into 7 phases (18-24) — Phase 18 (Two-Price Model: PROD-05/06/07), Phase 19 (Products Page Rebuild: PROD-01..04/08), Phase 20 (Warehouses & Batch-Split Transfers: WH-01..03/XFER-01), Phase 21 (Customer Profiles & Insights: CUST-01..08), Phase 22 (Sales Page Rebuild: SALE-01..07), Phase 23 (Dashboard & History Rebuild: DASH-01..05/HIST-01..04), Phase 24 (Navigation Restructure & Settings: NAV-01..08/RPT-01/MOB-01).
- **Price consolidation (PROD-05/06/07) sequenced first, as its own phase.** It is the only schema-affecting change in the milestone (`Product.catalog_cents` collapses into ПЦ; `min_sale_cents` stays — see Blockers/Concerns) and it is read by receipts, sales, product cards, the dictionary, and the stock-valuation reports. Every later phase builds UI on the final two-price shape — mirrors the v1.1 "riskiest ledger-schema work before the UI that reads it" ordering decision that held for 5 phases.
- **Navigation (NAV-01..08) sequenced last, not first.** NAV-01/02/03 nest Приход/Списание/Справочник under Товары and NAV-07 nests Перемещение under the product context — all soft-depend on those pages being in final shape (Phases 19/20), and NAV-08's final top-level tab set can only be settled once Главная is rebuilt (Phase 23). MOB-01 (mobile tab parity) reads the final desktop tab set, so it rides with NAV-08 rather than standing alone.
- **RPT-01 ("Назад к отчётам") and MOB-01 folded into Phase 24 rather than becoming standalone phases.** Both are single-requirement navigation items; per the anti-fragmentation rule they belong with the nav phase they are conceptually part of. RPT-01 also directly addresses the class of gap UAT found in Phase 17 (report pages shipped without entry/exit navigation).
- **CUST-01..08 (Phase 21) sequenced before SALE-01..07 (Phase 22).** SALE-05 requires the inline new-customer form to show "optional profile fields" — those fields must exist on the profile before the sale form can render them, otherwise the sale rebuild would ship against a profile shape it then has to redo.
- **DASH-01..05 and HIST-01..04 combined into one phase (23).** Both are read-only presentations over the existing ledger, and DASH-05's per-operation-type feed columns and HIST-01's per-operation-type column sets are the same mapping — building them apart would duplicate it. Most underlying data (period totals, stock valuation) is already computed by the Phase 6/17 reporting services.
- **XFER-01 grouped with the warehouse work (Phase 20), not the batch/product work.** It is warehouse-to-warehouse batch-split behavior; v1.1's Phase 10 set the precedent of pairing transfers with warehouse-domain work.
- **7 phases (above the 4-6 "standard" granularity band) is deliberate.** v1.2 and v1.3 each compressed ~12-13 requirements into 3 phases (~4.3 reqs/phase); at that established rate 46 requirements implies ~10 phases. 7 is already a compression, and each phase still owns one coherent page/capability with user-observable criteria. Compressing further would produce grab-bag phases mixing schema migration, service logic, and unrelated page rebuilds.

### Pending Todos

None yet.

### Coverage Gate Overrides

- **Phase 8 (2026-07-11):** The globally-installed `gsd-tools` on PATH (an older `gsd-sdk` build) flagged D-03, D-07, D-08, D-10 as "uncovered" via its `decision-coverage-plan` check. Re-ran the project's own `$HOME/.claude/gsd-core/bin/gsd-tools.cjs gap-analysis` (the up-to-date tool) which confirmed all 11 items (WH-01 + D-01..D-10) are covered — the older global binary's matcher choked on compound citations like `(D-06/D-07)`. The semantic gsd-plan-checker agent also independently confirmed full coverage (Dimension 7: Context Compliance — PASS). No re-plan needed.

### Blockers/Concerns

- ✅ [Phase 18] RESOLVED 2026-07-15 (operator decision). The two-price consolidation
  touches live money columns that shipped features read. Scope now explicit:
  `Product.catalog_cents` collapses into ПЦ (`sale_cents`); `Product.cost_cents`
  is ДЦ; `CatalogPrice.consumer_cents`/`consultant_cents` map to ПЦ/ДЦ (v1.2
  catalog autofill, quick-tasks 260714-2w6 / 260714-fix). **`Product.min_sale_cents`
  is NOT removed** — the operator confirmed it is a guardrail threshold (like the
  low-stock threshold), not a displayed price, so Phase 7's below-minimum sale
  warning (PRICE-01, shipped v1.1) must keep working unchanged. PROD-05 and the
  Phase 18 roadmap entry both carry this exemption; Phase 18 success criterion 5
  is the PRICE-01 regression guard.

- ℹ️ [Phase 16] Advisory (cosmetic, desktop only): a movement saved with an empty
  comment renders literal `None` in the `/finance` «Комментарий» column (mobile
  cards handle it correctly). Guard the desktop template cell with
  `{{ movement.note or "" }}` when next touching finance templates. Non-blocking.

- ℹ️ [v1.3 close] No `17-SECURITY.md` threat verification or `/gsd-audit-milestone`
  was run before v1.3 shipped (operator chose to skip both). v2.0 touches the same
  money paths; consider restoring the gate at this milestone's close.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260714-2w6 | Replace Dictionary + CatalogPrice with a single-catalog-per-code import from oriflame_prices_with_calculations_fixed.xlsx (ДЦ->consultant_cents, ПЦ->consumer_cents) | 2026-07-14 | 3f0a7e3 | [260714-2w6-update-dictionary-pricelist](./quick/260714-2w6-update-dictionary-pricelist/) |
| 260714-fix | Catalog consumer price (ПЦ) now also autofills "Цена продажи" on product form and goods receipt (D-02 in receipts.py superseded); ДЦ still cost-only | 2026-07-14 | 53c3c92 | [260714-fix-catalog-sale-autofill](./quick/260714-fix-catalog-sale-autofill/) |
| 260714-o1z | Kill stale server on port 8000 in run.bat before starting a new one (fixes /dictionary 500 caused by an old process serving stale code) | 2026-07-14 | 5014787 | [260714-o1z-kill-stale-server-port](./quick/260714-o1z-kill-stale-server-port/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| uat_gap | Phase 01: 01-UAT.md — offline run.bat launch + browser correction flow + restart persistence (1 pending scenario) | testing | 2026-07-10 (v1.0 close) |
| verification_gap | Phase 01: 01-VERIFICATION.md — same offline run.bat flow | human_needed | 2026-07-10 (v1.0 close) |
| code_review | transfers.py/writeoffs.py: batch-ownership leak, unstripped qty echo (2 advisory, non-blocking) | acknowledged | 2026-07-13 (v1.1 close) — **Phase 20 touches transfers.py; close them there** |
| verification_gap | Phase 15: 15-VERIFICATION.md — manual browser check of `/finance` and `/m/finance` balance display through real sale/return forms | confirmed_working | 2026-07-14 (phase 15 execution), confirmed by operator 2026-07-15 |
| doc_drift | `export.py`: `stream_customers_csv` docstring claims a *"Full customer profile dump"* — becomes false once Phase 21 ships address + contacts. Out of scope by design (contacts are 1-to-many and don't fit the flat CSV shape). If `address` is ever added it must go through the existing `_csv_safe`. | acknowledged | 2026-07-17 (phase 21 planning) — accepted debt, close in a future phase |

## Session Continuity

Last session: 2026-07-17T06:50:04.594Z
Stopped at: Phase 21 UI-SPEC approved
Resume file: .planning/phases/21-customer-profiles-purchase-insights/21-UI-SPEC.md

## Operator Next Steps

- Run `/gsd-plan-phase 20` to plan Phase 20: Warehouses & Batch-Split Transfers (WH-01..03, XFER-01)
- Every v2.0 phase is UI-bearing — `/gsd-ui-phase 20` is available before planning (config `ui_phase: true`)
