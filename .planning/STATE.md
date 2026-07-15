---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Финансы / Касса
status: planning
stopped_at: Phase 17 context gathered
last_updated: "2026-07-15T13:04:39.693Z"
last_activity: 2026-07-15
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 8
  completed_plans: 8
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-15)

**Core value:** The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.
**Current focus:** Phase 17 — financial-reports, export & dashboard analytics

## Current Position

Phase: 17
Plan: Not started
Status: Ready to plan
Last activity: 2026-07-15

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 59
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | - | - |
| 2 | 4 | - | - |
| 05 | 9 | - | - |
| 06 | 6 | - | - |
| 07 | 4 | - | - |
| 09 | 9 | - | - |
| 10 | 3 | - | - |
| 12 | 4 | - | - |
| 13 | 6 | - | - |
| 14 | 7 | - | - |
| 16 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01 P01 | 8min | 2 tasks | 12 files |
| Phase 01 P02 | 5min | 2 tasks | 9 files |
| Phase 01 P03 | 7min | 3 tasks | 16 files |
| Phase 02 P01 | 16min | 3 tasks | 12 files |
| Phase 02 P02 | 17min | 3 tasks | 6 files |
| Phase 02 P03 | 6min | 2 tasks | 6 files |
| Phase 02 P04 | 9min | 2 tasks | 9 files |
| Phase 03 P01 | 8min | 3 tasks | 9 files |
| Phase 03 P02 | 10min | 3 tasks | 6 files |
| Phase 03 P03 | 9min | 3 tasks | 11 files |
| Phase 04 P06 | 8min | 1 tasks | 2 files |
| Phase 05 P01 | 12min | 2 tasks | 7 files |
| Phase 05 P02 | 13min | 3 tasks | 8 files |
| Phase 05 P03 | 10min | 3 tasks | 6 files |
| Phase 05 P04 | 13min | 3 tasks | 8 files |
| Phase 05 P05 | 18min | 3 tasks | 8 files |
| Phase 14 P01 | 15min | 3 tasks | 8 files |
| Phase 16 P01 | 5m | 2 tasks | 3 files |
| Phase 16 P02 | 12min | 2 tasks | 2 files |
| Phase 16 P03 | 18min | 2 tasks | 8 files |
| Phase 16 P04 | 20min | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table (v1.0/v1.1 milestone decisions archived there and in `.planning/RETROSPECTIVE.md`).

- **v1.3 roadmap (2026-07-14):** 12 requirements grouped into 3 phases — Phase 15 (Cash Ledger Foundation: FIN-01/02/06 — new sibling `cash_movements` ledger, auto-credit on sale, auto-debit on return, balance visible in a new «Финансы» section), Phase 16 (Manual Cash Movements & History: FIN-03/04/05/07 — bidirectional manual entry with mandatory category on withdrawal, warn-but-allow negative balance, paginated/filterable history), Phase 17 (Financial Reports, Export & Dashboard Analytics: FIN-08/09/10/11/12 — period cash-flow report, CSV export, gross/net profit and stock valuation on the dashboard).
- Sale-credit (FIN-01) and return-debit (FIN-02) kept in the same phase (15), not split across phases, per research Pitfall 2 — a return without its symmetric debit silently corrupts the balance the first time a customer returns something.
- FIN-06 (balance display) folded into Phase 15 rather than deferred to Phase 16 — makes the foundation phase's success criteria observable through the UI (mirrors the v1.0 Phase 1 "walking skeleton" pattern) instead of requiring a debug-only verification path.
- FIN-10/11/12 (gross profit, net profit, stock valuation — added after research via user follow-up) grouped into Phase 17 alongside FIN-08 (cash-flow report) and FIN-09 (CSV export) rather than into Phase 16's manual-movement UI — all five are read-only period/point-in-time aggregation queries reusing existing report infrastructure (`sales_profit_report`, the stock report shape, the export.py CSV convention), distinct in nature from Phase 16's write-path/form work. Net profit (FIN-11) also has a hard dependency on Phase 16's manual expense movements existing to subtract.
- 3 phases (not the 4-6 "standard" granularity default) mirrors the v1.2 precedent — 13 requirements also compressed to 3 phases under the same granularity setting — and follows the "don't pad small projects" rule for a contained, single-ledger integration milestone.
- [Phase ?]: D-01: manual cash movements extend CASH_CATEGORIES — no type column, no migration
- [Phase ?]: CASH_BUCKETS kept server-side only (not a Jinja global) — a filter map, never rendered
- [Phase ?]: Manual-entry sign tests pre-seed a covering balance so the D-05 negative gate does not fire; sign/comment verified independently
- [Phase ?]: [Phase 16-03]: Manual cash forms shared desktop-mobile via a finance_base context var (no hardcoded /finance); Plan 04 reuses withdraw_form/deposit_form/cash_negative_balance verbatim with finance_base=/m/finance
- [Phase ?]: [Phase 16-03]: negative-balance warn re-renders at HTTP 200 (not 422) so htmx swaps it; deposit route relabels the service category error to Vyberite osnovanie
- [Phase ?]: [Phase 16-04]: Mobile /m/finance reuses the shared withdraw/deposit forms + record_manual_movement service verbatim (finance_base=/m/finance); only the history presentation is forked — cards + Pokazat esche load-more (has_next sentinel), never the desktop numbered bar (UI-SPEC Q1)

### Pending Todos

None yet.

### Coverage Gate Overrides

- **Phase 8 (2026-07-11):** The globally-installed `gsd-tools` on PATH (an older `gsd-sdk` build) flagged D-03, D-07, D-08, D-10 as "uncovered" via its `decision-coverage-plan` check. Re-ran the project's own `$HOME/.claude/gsd-core/bin/gsd-tools.cjs gap-analysis` (the up-to-date tool) which confirmed all 11 items (WH-01 + D-01..D-10) are covered — the older global binary's matcher choked on compound citations like `(D-06/D-07)`. The semantic gsd-plan-checker agent also independently confirmed full coverage (Dimension 7: Context Compliance — PASS). No re-plan needed.

### Blockers/Concerns

- ℹ️ [Phase 16] Advisory (cosmetic, desktop only): a movement saved with an empty
  comment renders literal `None` in the `/finance` «Комментарий» column (mobile
  cards handle it correctly). Guard the desktop template cell with
  `{{ movement.note or "" }}` when next touching finance templates. Non-blocking.

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
| code_review | transfers.py/writeoffs.py: batch-ownership leak, unstripped qty echo (2 advisory, non-blocking) | acknowledged | 2026-07-13 (v1.1 close) |
| verification_gap | Phase 15: 15-VERIFICATION.md — manual browser check of `/finance` and `/m/finance` balance display through real sale/return forms | confirmed_working | 2026-07-14 (phase 15 execution), confirmed by operator 2026-07-15 |

## Session Continuity

Last session: 2026-07-15T13:04:39.672Z
Stopped at: Phase 17 context gathered
Resume file: .planning/phases/17-financial-reports-export-dashboard-analytics/17-CONTEXT.md

## Operator Next Steps

- Run `/gsd-plan-phase 17` to plan Phase 17: Financial Reports, Export & Dashboard Analytics
