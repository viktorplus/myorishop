# Phase 23: Dashboard & History Rebuild - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-17
**Phase:** 23-Dashboard & History Rebuild
**Areas discussed:** Active catalog + close date source, History type-first UX mechanics, Dashboard totals & operations feed, Mobile scope

---

## Active catalog + close date source

Advisor-mode research (gsd-advisor-researcher) produced a comparison table for this gray area, since no "active catalog" or close-date concept exists anywhere in the codebase (`Catalog`/`CatalogPrice` carry no date range; `scan_catalog_files()` derives only `(year, number)` from PDF filenames).

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid — number auto-derived from `scan_catalog_files()`, close date manual | Recommended by research: avoids re-typing the number, only concedes the genuinely unknowable close date | |
| Fully manual — both number and close date are separate operator fields | Direct control over both, no dependency on filename-derived state | ✓ |
| Formula — anchor start date + fixed cycle length, both computed | Zero operator upkeep, but risks silent drift if Oriflame cycles aren't strictly fixed-length | |

**User's choice:** Fully manual (both fields).
**Follow-up — where to edit:** Options were "inline on Главная," "on the existing `/catalogs` page," or "a new dedicated route." User picked the existing `/catalogs` page (Настройки doesn't exist until Phase 24, so a new small settings page was ruled out).
**Notes:** Operator prioritized direct control over both fields over minimizing re-typed data — explicitly against the research's own top recommendation.

---

## History: type-first operation-type selection mechanics

| Option | Description | Selected |
|--------|-------------|----------|
| Single `/history`, HTMX swaps rows AND columns in place | Recommended by research: extends the existing `history_rows.html` swap pattern, no URL/pagination disruption | ✓ |
| Separate routes per type (`/history/sale`, `/history/receipt`, ...) | Mirrors `/reports`'s landing-page precedent; cleaner templates but 6-9 near-duplicate routes | |
| Single table, CSS/JS hides columns client-side | Cheapest on paper; explicitly not recommended — violates the project's server-rendered-only convention | |

**User's choice:** Single `/history`, HTMX swaps rows and columns in place (research's recommendation).
**Follow-up — default/starting view before a type is picked:** Options were "today's existing generic 10-column view," "no default — a type picker with no combined view," or "remember the operator's last-picked type." User picked the existing generic view as the default, with type selection as an optional refinement rather than a mandatory first gate.
**Notes:** Research also flagged, as part of the same recommendation (not separately re-asked), that the customer filter should apply only to sale/return types and the category filter only where a product's category applies — the user did not object to this framing when it was presented.

---

## Dashboard: day/week/month totals — what counts as "expense"

| Option | Description | Selected |
|--------|-------------|----------|
| Cash-ledger definition, matching the Финансы page's `cash_expense_total` | Recommended by research: same word, same meaning app-wide | ✓ |
| Sales-triad / COGS-based ("expense" = cost of goods sold) | Arithmetically self-consistent (revenue − expense = profit) but a different meaning than Финансы's "expense" | |
| Four-number hybrid (gross profit, COGS, cash expense, net profit all shown separately) | Fully unambiguous but over-delivers beyond the phase's stated success criteria | |

**User's choice:** Cash-ledger definition (same as Финансы).
**Follow-up — profit tile, gross or net:** Options were "net profit (gross + cash expense, same formula as Финансы's `_metrics_context`)" or "gross profit shown with expense as an independent, arithmetically-unlinked number." User picked net profit, matching Финансы exactly.
**Notes:** Also surfaced by research as evidence-resolved (not re-asked): the recent-operations feed covers the same 6 stock-affecting operation types as History's type-first view, `limit=10` rows mirroring `recent_sales`, each row linkable into `/history?type=...&product=...`; DASH-04's stock valuation reuses `stock_valuation()` unchanged (whole-inventory, no per-warehouse split).

---

## Mobile Главная/История — scope for this phase

| Option | Description | Selected |
|--------|-------------|----------|
| Full data parity, mobile-native card/accordion presentation | Recommended by research: matches the established Phase 12-22 "same data, own simpler shape" pattern; also closes the mobile-history legacy-pagination gap | ✓ |
| Literal 1:1 copy of desktop (table/grid squeezed via CSS) | Not recommended — contradicts the v1.1 mobile-flow decision against CSS-only desktop adaptation | |
| Deliberately simplified mobile (reduced tiles, type-filter-only history, old load-more pagination) | Least new code, but conflicts with REQUIREMENTS.md wording, which carries no mobile carve-out | |

**User's choice:** Full data parity, mobile-native cards/accordion (research's recommendation).
**Notes:** User explicitly rejected both offered extremes (pixel-copy and cut-down), confirming the middle/recommended path.

---

## Claude's Discretion

- Exact Russian field labels/placeholder text for the catalog-number/close-date fields on `/catalogs`, and empty-state wording when no active catalog is configured.
- Exact card/accordion layout for mobile dashboard tiles and mobile per-type History cards.
- Whether the recent-operations feed is its own service function or a generalized `recent_sales` variant.
- Per-type sort option sets on the rebuilt History page.
- Whether non-applicable customer/category filters are hidden or shown disabled for a given type.

## Deferred Ideas

None — discussion stayed within phase scope across all 4 areas. No scope creep occurred.
