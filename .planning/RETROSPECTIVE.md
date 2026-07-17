# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-07-10
**Phases:** 6 | **Plans:** 31 | **Timeline:** 2026-07-08 → 2026-07-10 (3 days)

### What Was Built
- Foundation: append-only operations ledger enforced at the DB level (triggers reject UPDATE/DELETE), sync-ready schema (UUID4 TEXT PKs, integer cents, UTC ISO timestamps), HTMX walking skeleton, `run.bat` one-click launcher
- Catalog: product cards with price history, code→name dictionary with auto-fill, Cyrillic-safe instant search
- Goods receipt with dictionary/card auto-fill, plus automated VACUUM INTO backups (pruned, restore proven)
- Sales: multi-line basket, price override, oversell warn-then-confirm, frozen cost/price snapshots, customer CRUD with purchase history
- Stock operations: write-off, sale-linked return (frozen price/cost), stock correction, full paginated/filterable `/history` audit trail
- Reports (sales/profit, stock, low-stock, write-offs, top/stale products) and three hardened CSV exports

### What Worked
- One single write path (`record_operation()`) enforced from Phase 1 onward — every later phase (returns, corrections, reports) built on the same choke point instead of inventing new write logic, which is exactly what made the append-only ledger trustworthy end to end.
- Wave-0 "RED" test contracts (Phase 1, Phase 5) that fixed the route/service interface in failing tests before any implementation existed — later waves had a hard contract to build against instead of a moving target.
- Reusing one helper across multiple features paid off repeatedly: `_PRICE_FIELDS` (Phase 3), the sale oversell warn-but-allow pattern (reused verbatim for write-offs in Phase 5), and `local_day_bounds_utc`/period-filter helper reused unchanged across all four Phase 6 reports.
- The effective-threshold pattern (`is not None`, never bare `or`) was established once in Phase 6 and applied consistently across low-stock and stale-days — an explicit operator-set zero stayed meaningful instead of silently falling back to the default.

### What Was Inefficient
- Phase 5 grew from 5 planned waves to 9 plans — four extra gap-closure plans (05-06..05-09) were needed after code review/verification surfaced real bugs: a missing nav link, a 404-vs-422 htmx-swap discard bug, an `HX-Request`-header routing bug, and a pagination control that a filter change could permanently destroy. These were genuine defects, not scope creep, but they landed late (post-verification) rather than being caught during initial implementation.
- Phase 4 needed one gap-closure plan (04-06) because `GET /sales/lookup` used bare, unaliased query param names instead of `Query(alias=...)` for list-of-line lookups — an interface mismatch that UAT caught rather than automated tests.
- The REQUIREMENTS.md traceability table for OPS-02/03/04 was left stamped "In Progress" (referencing a wave state) after the plans actually completed — caught and corrected only at milestone close, not at phase transition. Worth checking traceability status matches actual phase completion during `/gsd-transition`, not just at the end.

### Patterns Established
- Single ledger write path (`record_operation()`) with the `IN-01` soft-deleted-product guard living inside it — one guard covers all present and future operation types.
- Frozen-at-write-time snapshots (price/cost on sale lines, price/cost on sale-linked returns) so historical reports stay correct even after catalog prices change later.
- Effective-threshold-with-explicit-`is not None`-fallback for any per-product-override-with-global-default field.
- Shared period-filter + local-day-boundary helper for any report bucketed by day/week/month/custom range.
- CSV export hardening: BOM-once + `;` delimiter + apostrophe-escape of formula-injection-prefixed cells, with zero client-supplied filename/path parameters.

### Key Lessons
1. A Wave-0 RED test contract at the start of a multi-wave phase (Phase 1, Phase 5) catches interface drift before implementation — worth doing again for any phase with 3+ waves touching shared routes.
2. Bugs caught by code review/verification instead of the original implementation plan (Phase 4's query-param aliasing, Phase 5's htmx-swap and pagination bugs) tend to cluster around HTMX partial-swap semantics (`HX-Request` header, OOB swaps, `hx-vals` array serialization) — worth a dedicated htmx-behavior checklist in future UI-heavy phases.
3. Update REQUIREMENTS.md traceability status at each phase transition, not just at milestone close — a stale "In Progress" note survived four phase completions before being caught.

### Cost Observations
- Model mix and per-session cost were not tracked in this project's state files — `needs verification` if that data matters for future milestones.
- Plan durations captured in STATE.md for the first 16 plans ranged 5-18 minutes each; later-phase durations were not recorded consistently — worth keeping the velocity table populated for every plan in the next milestone.

---

## Milestone: v2.0 — UX Overhaul & Navigation Restructure

**Shipped:** 2026-07-17
**Phases:** 7 (18-24) | **Plans:** 42 | **Timeline:** 2026-07-16 → 2026-07-17 (2 days)

### What Was Built
- Two-price model consolidation: `Product.catalog_cents` collapsed into ПЦ (`sale_cents`); a colour cue (amber below / blue above the catalog reference price) wired on every editable price input across product card, dictionary, receipt, and sale, desktop and mobile
- Products page rebuilt as a code-grouped stock list with a collapsed per-batch expiry/name breakout; redundant add-button removed, delete turned into a text link
- Warehouse CRUD moved to dedicated add/edit forms with item-count/last-receipt columns; batch-split transfers create a new destination batch under a different expiry/condition without corrupting the source
- Customer profiles gained repeatable multi-value contacts (phone/Telegram/email/social), address, most-recent-order date, spend totals net of returns, and frequency-ranked favorite products
- Sales page rebuilt as a plain code/name/qty/price table with a live JS running total and a single new/existing/anonymous customer radio control
- Главная rebuilt (date/catalog/revenue-profit-expense/stock/recent-ops feed); История rebuilt with type-first column narrowing plus filter/sort/pagination
- Navigation restructured to 8 first-class top-level pages, every secondary action nested under its owning page, a new Настройки hub, and full mobile tab parity

### What Worked
- Sequencing the one schema-affecting change (two-price consolidation, Phase 18) first, before any page rebuild that reads the price shape — zero rework was forced on Phases 19-24, the same "riskiest schema work before the UI that reads it" pattern that held for 5 phases in v1.1.
- Sequencing customer-profile work (Phase 21) before the sales-page rebuild (Phase 22) that needed the extended profile fields — avoided building the sale form's inline new-customer path against a profile shape that would immediately need redoing.
- Combining DASH-01..05 and HIST-01..04 into one phase (23) because they're the same per-operation-type column mapping applied to two different presentations — avoided duplicating that mapping across two phases.
- The re-verification cycle on Phase 24 caught a real mobile-reachability regression (removing the old mobile home tile grid had orphaned `/m/search`, `/m/corrections`, `/m/transfers`) that the phase's own goal statement ("on desktop and mobile alike") would otherwise have shipped broken — the verifier's first pass scored 5/6, gap-closure plan 24-07 closed it to 6/6.
- UAT files (18-UAT.md, 20-UAT.md) captured explicit operator sign-off on judgment calls that no test could decide — including accepting the D-14 colour-only WCAG 1.4.1 deviation as intentional rather than a shipped regression.

### What Was Inefficient
- Phase 22 (Sales Page Rebuild) shipped without ever getting a `22-UAT.md` — its own VALIDATION.md documented 4 manual-only behaviors (no JS runtime in the pytest-only suite), the VERIFICATION.md correctly flagged them as `human_needed`, but no UAT pass followed before milestone close. Phase 18 and Phase 20 both hit the same `human_needed` status and both got a completed UAT file within a day; Phase 22 didn't. Worth checking `human_needed` phases have a matching UAT file as a milestone-close gate, not just a phase-close nicety.
- REQUIREMENTS.md's checkboxes lagged actual completion for roughly half the milestone's requirements (PROD-05/07, WH-01/02/03, SALE-07, DASH-01/03/04/05, HIST-04, most of NAV-01..08) — every affected phase's own VERIFICATION.md independently caught and flagged this same lag. The traceability table was never re-edited after a phase shipped; worth a lightweight habit (or tooling) to flip the checkbox as part of a phase's own close-out, the same gap noted in the v1.0 retrospective for OPS-02/03/04.
- Repo-wide `ruff` debt (9 lint errors, ~50 files needing reformat) accumulated silently across the milestone — every phase's own plan-scoped verification correctly identified it as pre-existing and out of scope, but nobody scheduled the dedicated cleanup pass any of them recommended.

### Patterns Established
- Colour-deviation cue against a reference price (`data-ref-cents` + client-side `price-cue.js` classList toggle) as the house pattern for "this value differs from a known reference" — reusable for any future field with a canonical/reference value to compare against.
- Override-or-inherit ternary (never bare `or`) for batch-split transfers that may carry a new expiry/condition — same "explicit `is not None`, never collapse into a default" discipline the v1.0 retrospective established for thresholds.
- Multi-value contact fields (`customer_contacts` table, kind-grouped, full-replace-on-save) as the house pattern for any future "repeatable free-text values of several kinds" requirement.
- Type-first column narrowing (`HISTORY_TYPE_COLUMNS`-style per-type column map) as the house pattern for any future feed/list that spans heterogeneous row shapes.

### Key Lessons
1. A `human_needed` VERIFICATION.md status needs a tracked follow-up UAT file before milestone close, not just before phase close — Phase 22 shipped without one while Phase 18/20 (same status) both got one, and it was only caught by the full milestone audit, not by any single phase's own gate.
2. Stale REQUIREMENTS.md checkboxes are now a 3-milestone-running pattern (v1.0's OPS-02/03/04, and now roughly half of v2.0's 46 requirements) — each phase's own VERIFICATION.md catches its own instance, but nothing catches the aggregate until milestone audit. Worth a lightweight per-phase close-out step that flips the checkbox mechanically, not just a Notice in VERIFICATION.md.
3. Re-verification cycles (Phase 24: 5/6 → 6/6 after gap-closure plan 24-07) are cheap insurance when a phase's goal statement has a "both surfaces" or "and mobile alike" clause — the first verification pass is the natural place such a clause gets under-checked.

### Cost Observations
- Model mix and per-session cost were not tracked in this milestone's state files either — same `needs verification` gap noted in the v1.0 retrospective, still unresolved three milestones later.
- Full milestone timeline (2 days, 2026-07-16 → 2026-07-17) for 7 phases/42 plans is the fastest per-phase pace of any milestone to date (v1.0: 3 days/6 phases, v1.1: 3 days/5 phases, v1.2: 2 days/3 phases, v1.3: 2 days/3 phases) — worth watching whether that pace correlates with the Phase 22 UAT gap above, i.e. whether speed traded off against the human-verification follow-through.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | not tracked | 6 | First milestone — established single-write-path ledger discipline and Wave-0 RED contracts |
| v1.1-v1.3 | not tracked | 5, 3, 3 | Retrospective sections not written at these milestones' close — gap in this document, not in the milestones themselves (see their MILESTONES.md entries for delivered scope) |
| v2.0 | not tracked | 7 | Fastest pace to date (2 days/7 phases); full `/gsd-audit-milestone` run at close (status: tech_debt, no blockers) — first milestone since v1.0/v1.1 to run the full audit gate before archiving (v1.2 ran it, v1.3 explicitly skipped it) |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | not tracked in state files | not tracked | not tracked |
| v2.0 | 919 passing at close (0 failed) | not tracked | not tracked |

### Top Lessons (Verified Across Milestones)

1. Single write path + Wave-0 RED contracts (v1.0) — carried forward through v2.0 (`record_operation()` still the sole ledger write path; Wave-0 RED tests used again in Phase 21/22).
2. Stale REQUIREMENTS.md checkboxes recur every milestone (v1.0's OPS-02/03/04; v2.0's ~half of 46 requirements) — still unresolved as a process gap after 3+ milestones; needs tooling, not another reminder.
3. A `human_needed` VERIFICATION.md status needs a tracked UAT follow-up before milestone close, not just before phase close (v2.0, Phase 22) — new lesson, watch whether it recurs in v3.0.
