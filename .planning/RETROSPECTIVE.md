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

## Milestone: v4.0 — Distribution & Delivery

**Shipped:** 2026-09-03
**Phases:** 2 (31, 32) | **Plans:** 13 (8 + 5) | **Tasks:** 29

> Note: v3.0 (phases 25-30) has no section here — it was never run through `/gsd-complete-milestone`, so it produced no retrospective and no archive. The gap is in this document and in `.planning/milestones/`, not in the milestone's delivery.

### What Was Built

A self-contained Windows distribution and the secure self-update on top of it: bundled Python 3.13 embeddable runtime in an onedir layout, an unsigned per-user Inno Setup installer, operator data moved to a physical sibling of the swappable `app\` directory, a stdlib-only out-of-tree launcher (stop → swap → migrate → health-check → restart, with matched-pair code+DB rollback), a tag-triggered GitHub Actions pipeline publishing a draft release signed with an OFFLINE minisign key, and an in-app notify-and-confirm updater that verifies SHA-256 + Ed25519 signature before it unpacks anything and is a hard no-op on the PostgreSQL server.

### What Worked

- **Physical layout as the safety mechanism (PKG-03).** Making operator data a *sibling* of the swappable directory means a directory swap cannot reach it — no careful code, no exclusion list, no bug surface. This is the single design decision the whole milestone rests on.
- **Wave-0 RED contracts again.** Both phases opened with executable acceptance tests (PKG-01..05, then 7 named UPD tests) written before any implementation module existed. Same pattern as v1.0/v2.0, still the cheapest way to keep a phase honest.
- **Reusing shipped mechanisms instead of inventing.** `backup.create_backup()` VACUUM INTO as the pre-update anchor, the `engine.dialect.name == "sqlite"` gate for the server no-op, the `_auto_sync_loop` background-loop shape, the `POST /settings/sync` thin-route shape for the update panel. Almost none of the update path is new machinery.
- **Forced phase ordering held.** Phase 32 genuinely could not be built or tested before Phase 31 existed, and the roadmap said so up front rather than discovering it mid-execution.

### What Was Inefficient

- **Three of Phase 31's eight plans were gap-closure waves.** The original four waves passed their tests and still produced an install that did not work: a fresh install created a schema-less DB and served HTTP 500 (`no such table: users`) because the launcher never ran `alembic upgrade head` (GAP-1), and the Start-Menu shortcut pointed at a file the installer did not ship (GAP-2). Both were found by looking at a real install, not by the suite.
- **A hand-built test fixture hid a total self-update failure behind 15 green tests (CR-01).** The swap/update tests staged a `staged\` directory assembled by hand instead of one produced by the real `build_release.py` archive; the shapes differed, so the tests proved nothing about the real path. The fix — build the fixture from the actual archive — is now a standing rule.
- **The rollback path needed three separate corrections after it was "done":** both swap renames had to move inside the rollback-guarded region, every directory rename had to clear its destination first (Windows `os.replace` refuses an existing directory, even an empty one), and the pending marker had to be quarantined instead of replayed every 2 seconds.
- **Nyquist validation was retrofitted.** Five coverage gaps in the self-update gate were closed by a post-hoc audit rather than being caught while the tests were being written.
- **No `/gsd-audit-milestone` was run.** v2.0 ran the full audit gate before archiving; v4.0 did not, and closed instead by acknowledging 27 open planning artifacts as deferred.

### Patterns Established

- **Test fixtures for a packaging/update path must be produced by the real build script.** A fixture assembled by hand tests the fixture, not the product.
- **Verify-before-unpack as a hard gate**, with the signature taken over an immutable signed manifest rather than a mutable git tag, and zip-slip confinement via `is_relative_to` on the unpack.
- **Version compare on the integer of the `1.<N>` scheme**, never string compare — and test the 9→10 boundary, where string compare silently inverts.
- **Two-stage build-in-CI / sign-offline-attach**, which is how "the pipeline publishes a signature" and "the secret key never leaves the operator's machine" can both be true.
- **`data\pending.json` as the app→launcher IPC contract**, path-confined and validated, so the privileged swap lives entirely outside the code being replaced.

### Key Lessons

1. **A green suite is not an install.** The two GAP waves and CR-01 all shared one cause: the tests exercised a model of the artifact rather than the artifact. For anything that ships as a *file the operator runs*, the acceptance evidence has to come from running that file.
2. **The v2.0 lesson recurred, unchanged.** "A `human_needed` VERIFICATION.md needs a tracked UAT follow-up before milestone close" was written down at the v2.0 close as something to watch in v3.0. v3.0 never closed at all; v4.0 shipped with two pending Phase-31 UAT scenarios plus phases 25 and 26 still `human_needed`. Three milestones on, this is a process defect, not a reminder problem.
3. **A "Distribution & Delivery" milestone that has never been installed or released is not delivered.** Every requirement is checked, every test is green, the pipeline is wired — and the two things that would prove it (a bare-Windows install, a real signed release) are exactly the two things still open.
4. **Windows filesystem semantics deserve their own tests.** `os.replace` on directories, destination clearing, and PID ownership each produced a real defect; none is discoverable by reading the Python docs casually.

### Cost Observations
- Model mix and per-session cost still not tracked in state files — the same `needs verification` gap noted at v1.0 and v2.0, now four milestones old.
- Timeline 2026-07-22 → 2026-09-03 (43 days) across 95 phase-31/32 commits, but the calendar is misleading: substantial unrelated work (dictionary/price-list imports, s1 deploys, 17 quick tasks) ran in the same window.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | not tracked | 6 | First milestone — established single-write-path ledger discipline and Wave-0 RED contracts |
| v1.1-v1.3 | not tracked | 5, 3, 3 | Retrospective sections not written at these milestones' close — gap in this document, not in the milestones themselves (see their MILESTONES.md entries for delivered scope) |
| v2.0 | not tracked | 7 | Fastest pace to date (2 days/7 phases); full `/gsd-audit-milestone` run at close (status: tech_debt, no blockers) — first milestone since v1.0/v1.1 to run the full audit gate before archiving (v1.2 ran it, v1.3 explicitly skipped it) |
| v3.0 | not tracked | 6 | Never closed — phases 25-30 all complete on disk, but no `/gsd-complete-milestone`, so no archive, no MILESTONES entry, no retrospective section |
| v4.0 | not tracked | 2 | First milestone whose deliverable is an artifact the operator installs rather than a page they open; 3 of 8 Phase-31 plans were gap-closure waves found by running the real install, not by the suite. No `/gsd-audit-milestone`; closed by acknowledging 27 open artifacts as deferred |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | not tracked in state files | not tracked | not tracked |
| v2.0 | 919 passing at close (0 failed) | not tracked | not tracked |
| v4.0 | not counted at close; 4 known-flaky `test_sync_ui.py` failures are pre-existing (lifespan auto-sync thread holds `sync_client._run_lock`), not a v4.0 regression | not tracked | `launcher/` is stdlib-only; `cryptography` 49.0.0 added for Ed25519 |

### Top Lessons (Verified Across Milestones)

1. Single write path + Wave-0 RED contracts (v1.0) — carried forward through v2.0 (`record_operation()` still the sole ledger write path; Wave-0 RED tests used again in Phase 21/22).
2. Stale REQUIREMENTS.md checkboxes recur every milestone (v1.0's OPS-02/03/04; v2.0's ~half of 46 requirements) — still unresolved as a process gap after 3+ milestones; needs tooling, not another reminder.
3. A `human_needed` VERIFICATION.md status needs a tracked UAT follow-up before milestone close, not just before phase close (v2.0, Phase 22) — **recurred in v4.0** (2 pending Phase-31 UAT scenarios; phases 25 and 26 still `human_needed`), and v3.0 never closed at all. Confirmed process defect across 3 milestones; needs a gate, not a note.
4. A green test suite does not prove the shipped artifact works (v4.0) — three Phase-31 gap-closure waves and CR-01 all came from fixtures/tests modelling the artifact instead of exercising it. Corollary: build packaging fixtures from the real build script's output.
