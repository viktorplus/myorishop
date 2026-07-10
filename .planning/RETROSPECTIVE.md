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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | not tracked | 6 | First milestone — established single-write-path ledger discipline and Wave-0 RED contracts |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | not tracked in state files | not tracked | not tracked |

### Top Lessons (Verified Across Milestones)

1. Single write path + Wave-0 RED contracts (v1.0) — carry forward to v1.1.
