# Project Research Summary

**Project:** MyOriShop - Kassa / Finansy module (v1.3 milestone)
**Domain:** Cash-balance / cash-flow ledger bolted onto an existing single-operator, offline warehouse-and-sales app
**Researched:** 2026-07-14
**Confidence:** HIGH

## Executive Summary

This is not a greenfield feature: it is a second append-only ledger grafted onto a codebase that already solved this exact class of problem for stock. The existing operations table plus record_operation() single-write-path pattern (UUID PK, device_id/seq, DB-level immutability triggers, SQL-side atomic cache increments with a rebuild_*() recompute/repair function) is the proven template. All four research files converge on one architectural verdict: do not reuse operations for cash. Instead create a sibling cash_movements table that copies the sync-ready, append-only shape but drops the stock-specific invariants (product_id NOT NULL, mandatory batch_id). No new runtime dependency is required; money stays Integer cents, balance is a live SUM() (no cache needed at this scale), and every UI interaction (warn-but-allow negative balance, category allow-list plus free-text other) should mirror patterns already shipped for oversell/min-price warnings and write-off reasons.

The recommended approach: one foundation phase creates the cash_movements schema, the finance.py service (single write path, mirrors ledger.py), and wires both sale auto-credit (sales.py) and return auto-debit (returns.py) in the same phase, since these must ship together, not sequentially, because a return without a symmetric debit silently corrupts the balance on day one. A second phase builds the manual-movement UI (bidirectional, credit and debit, not debit-only, to cover opening balance and typo-correction) plus the Finansy dashboard/history page. A third, lower-priority phase covers reports/CSV export if pulled into scope.

Key risks: (1) treating cash as just more operations rows, rejected by all four researchers for concrete, code-grounded reasons (FK/NOT-NULL invariants, report-query pollution); (2) shipping sale-credit without return-debit in the same phase, silently breaking the balance the first time a customer returns something; (3) a debit-only manual form with no opening-balance/correction path, which turns the very first negative-balance warning into a false alarm the operator learns to distrust; (4) reintroducing a stale-cache balance bug that the Product.quantity design already solved, so default to live SUM(), no cache until proven necessary. None of these require new libraries or infrastructure; they require following the codebase own established conventions exactly.

## Key Findings

### Recommended Stack

No new dependency. The existing FastAPI / SQLAlchemy 2.0 / SQLite (WAL, busy_timeout=5000) / Alembic / Jinja2 / HTMX stack fully covers this feature: a new mapped class, a new migration with append-only triggers (copied from alembic/versions/0001_initial_schema.py), and a couple of new routes/templates following the exact shape already used by writeoffs.py. Money stays Integer cents (no Decimal/Numeric, no money library); no accounting/double-entry library; no caching/locking library (SQLite WAL plus busy_timeout already handle single-writer concurrency); no charting or scheduling library (out of this milestone scope).

**Core technologies (reused, unchanged):**
- SQLAlchemy 2.0.51 - new CashMovement mapped class, same declarative style as Operation/Batch
- Alembic 1.18.5 - one new migration adding cash_movements plus its own BEFORE UPDATE/DELETE ... RAISE(ABORT, ...) triggers
- SQLite WAL plus busy_timeout (already configured in app/db.py) - no new PRAGMA needed; unlimited readers, one writer, already the correct config for balance read often, written on every sale
- FastAPI plus Jinja2 plus HTMX 2.0.10 (vendored) - new Finansy section using only hx-get/hx-post/hx-target/hx-swap, already exercised throughout the app

### Expected Features

**Must have (table stakes, v1.3 launch):**
- Current cash balance display (live SUM of the ledger)
- Auto-credit on every sale (hook into register_sale(), single write path)
- Auto-debit on sale-linked return - not explicitly in PROJECT.md stated list but flagged as a hard gap: without it the balance drifts from reality the first time a return happens
- Manual withdrawal with mandatory category (supplier / salary / other) plus comment
- Movement history (reuse existing list/pagination/filter infrastructure from Phase 14)
- Insufficient-balance warning on withdrawal - warn-and-allow-override, matching the app existing oversell/min-price convention, never a hard block
- Separate Finansy UI nav section

**Should have (pull into v1.3 or immediate follow-up, recommended, not just nice later):**
- Manual balance correction / opening-balance entry (bidirectional manual-movement form, credit plus debit) - without it, balance starts wrong on day one for any operator with existing cash on hand, and a mistyped entry has no fix path (append-only trigger blocks UPDATE/DELETE)
- Cash flow reports (period in/out by category) - reuse existing Reports period-filter helper
- CSV export of cash movements - reuse existing export.py BOM/semicolon/formula-escape convention

**Defer (v2+):**
- Structured link: withdrawal to specific goods receipt (deferred-payment tracking)
- Multiple cash accounts/tills, shift/period reconciliation, scheduled/recurring expenses, budget categories/limits
- Full double-entry bookkeeping, tax/VAT tracking, invoicing/payment-gateway integration, bank reconciliation, multi-currency, user roles/approval workflow, receipt photo/OCR - all explicit anti-features for a single-operator cash-box tracker

### Architecture Approach

A new app/services/finance.py module, sibling to ledger.py (not a submodule of it), owns the single write path for a new cash_movements table: record_cash_movement(), register_manual_debit() (validation mirrors writeoffs.register_writeoff), compute_balance() (live SUM, mirrors ledger.compute_stock), and a history view (mirrors operations.history_view, reusing pagination.py). sales.py register_sale() calls finance.py directly inside its existing transaction (one more commit=False call before the existing trailing session.commit()), never from the route layer, since there are already two callers (desktop plus mobile) that must both get the credit for free. The same discipline applies symmetrically to returns.py register_return().

**Major components:**
1. CashMovement model (app/models.py) - append-only row, UUID PK, signed amount_cents, category, nullable sale_id FK, device_id/seq/created_at/created_by (same sync-ready shape as Operation)
2. app/services/finance.py - single write path plus compute_balance() plus history view (new)
3. sales.py / returns.py - each gets exactly one new call into finance.py inside its existing commit block (modified, not rewritten)
4. app/routes/finance.py plus pages/finance.html plus partials/finance_history.html - thin routes, dashboard, bidirectional manual-movement form (new)
5. alembic/versions/00XX_cash_movements.py - new table plus two append-only triggers mirroring migration 0001 (new)

### Critical Pitfalls

1. **Bolting cash onto the operations table** - Operation.product_id is NOT NULL with a hard FK; forcing cash through it requires either a dummy product or relaxing an invariant every stock report/guard depends on. Avoid: dedicated cash_movements table with its own single-write-path function and triggers.
2. **Auto-credit wired into sales.py but not symmetrically into returns.py** - these are separate service modules; if the debit is not added to register_return in the same phase as the sale credit, returns silently inflate the balance forever. Ship both together; test: sell then fully return then assert balance returns to pre-sale value.
3. **Matching a return against the original credit row instead of computing independently** - mirror the existing D-06/D-07 pattern: the return debit equals qty_returned times origin frozen unit_price_cents, computed fresh, never looked up/reconciled against a prior movement.
4. **Cached balance updated outside the writing transaction** - either do not cache (live SUM, recommended at this scale) or use the exact SQL-side atomic-increment-in-same-transaction pattern Product.quantity already uses, plus a rebuild_cash_balance() repair function from day one.
5. **No opening balance / no correction path** - a debit-only manual form makes the first negative-balance warning a false alarm and leaves mistyped entries permanently unfixable (append-only trigger blocks edits). Ship a bidirectional (credit plus debit) manual-movement form with a Korrektirovka/opening-balance category from the start.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Cash ledger foundation (schema plus auto-credit/debit)
**Rationale:** This is the foundational, hardest-to-reverse data-model decision (Pitfall 1) and must ship the sale-credit/return-debit symmetry together (Pitfall 2/3): splitting these across phases leaves a window where returns silently break the balance.
**Delivers:** cash_movements table plus triggers, app/services/finance.py (record_cash_movement, compute_balance), sales.py auto-credit wiring, returns.py auto-debit wiring, unit tests proving atomicity (rolled-back sale gives zero cash rows) and return symmetry (sell then return then balance restored).
**Addresses:** Auto-credit on sale, auto-debit on return (table stakes plus gap)
**Avoids:** Pitfalls 1, 2, 3, 4 (schema shape plus live-SUM balance plus independent-computation debit)

### Phase 2: Finansy UI - balance, bidirectional manual movement, history
**Rationale:** Depends on Phase 1 ledger and write path existing; UI-level warn-and-allow validation and manual-entry design are a distinct, well-precedented concern (mirrors oversell/min-price and writeoffs UX exactly).
**Delivers:** app/routes/finance.py, pages/finance.html, partials/finance_history.html, nav link, bidirectional manual-movement form (credit for opening-balance/correction, debit for supplier/salary/other with mandatory category plus note), insufficient-balance warn-with-confirm guard, paginated/filterable history view.
**Uses:** pagination.py (Phase 14 infra), existing warn-but-allow UX contract from sales.py/writeoffs.py
**Implements:** finance.py service methods register_manual_debit/credit, history view mirroring operations.history_view

### Phase 3: Reports and export extension (optional, should-have)
**Rationale:** Lower priority (P2); adds value once a few weeks of movement history exist, but not blocking for launch.
**Delivers:** Cash flow report (period in/out by category, reusing existing period-filter helper) and/or CSV export of cash movements (reusing export.py BOM/semicolon/formula-escape convention).
**Addresses:** Cash flow reports, CSV export (differentiators)

### Phase Ordering Rationale

- Schema-first ordering matches this codebase own established convention (schema then service then route then template, per ARCHITECTURE.md Build Order) and is non-negotiable because the table shape (Pitfall 1) is the hardest thing to change once real financial rows exist.
- Sale-credit and return-debit are grouped into the same phase specifically because PITFALLS.md identifies their separation as a critical, easy-to-miss regression (Pitfall 2): the roadmap must not schedule these as sequential, independently-closeable phases.
- The manual-movement UI is deliberately scoped bidirectional (not debit-only, despite the milestone description emphasizing debit) to close the opening-balance and correction gaps (Pitfalls 7/8) at the same time the debit form is built, rather than as a late patch.
- Reports/export is pushed to a later, explicitly optional phase since FEATURES.md scores it P2 and none of the P1 table-stakes features depend on it.

### Research Flags

Phases likely needing deeper research during planning:
- None flagged: this is an internal integration project; all four research files are grounded in direct codebase inspection (HIGH confidence), not ecosystem survey.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Directly mirrors ledger.py/Operation already-proven, in-repo pattern - no external research needed.
- **Phase 2:** Directly mirrors writeoffs.py validation shape and the existing oversell/min-price warn-and-allow UX - no external research needed.
- **Phase 3:** Directly mirrors reports.py period-filter helper and export.py CSV convention - no external research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new dependencies; conclusion rests on direct codebase inspection plus cross-checked practitioner sources on integer-cents money handling and SQLite WAL concurrency |
| Features | MEDIUM-HIGH | PROJECT.md scope is a HIGH-confidence first-party source; broader petty-cash/POS feature-landscape claims rest on MEDIUM-confidence web sources (multiple cross-checked listings) |
| Architecture | HIGH | Entirely derived from direct inspection of this repository existing services/models/migrations - a project-specific integration design, not a generic survey |
| Pitfalls | HIGH (architecture-grounded) / MEDIUM (general financial-ledger practitioner findings) | Codebase-specific pitfalls (1-8) read directly from ledger.py/sales.py/returns.py/db.py; Pitfall 9 cash-vs-profit confusion claim is corroborated by MEDIUM-confidence external sources |

**Overall confidence:** HIGH

### Gaps to Address

- Return auto-debit is not explicitly in PROJECT.md stated v1.3 target feature list (FEATURES.md/PITFALLS.md both flag it as a gap, not a stated requirement): confirm with the user/PROJECT.md owner before roadmap lock-in that it is in scope for v1.3 rather than a fast-follow; all four research files strongly recommend including it in the foundation phase regardless.
- Bidirectional manual-movement form (credit direction for opening balance/correction) is also not explicitly stated in PROJECT.md wording (the debit categories text reads debit-only): same treatment, flag explicitly in the roadmap/requirements rather than silently deciding scope during execution.
- Idempotency / duplicate-sale-submission risk (Pitfall 5) is a pre-existing app-wide gap that becomes financially visible with cash tracking: decide during roadmap planning whether this phase adds only a UI-level submit-guard (hx-disabled-elt) or whether a full idempotency-key mechanism is named as an explicit Future/Out-of-Scope item.
- Whether CSV export / reports scope includes cash movements is currently undecided: PITFALLS.md flags this must be a stated decision, not an oversight, whichever way it goes.

## Sources

### Primary (HIGH confidence)
- Direct inspection of this repository: app/models.py, app/services/ledger.py, app/services/sales.py, app/services/returns.py, app/services/writeoffs.py, app/services/operations.py, app/services/reports.py, app/routes/sales.py, app/routes/__init__.py, app/main.py, app/config.py, app/core.py, app/db.py, alembic/versions/0001_initial_schema.py, app/templates/base.html
- E:\dev\myorishop\CLAUDE.md - prior validated stack research (versions, integer-cents rule, WAL/busy_timeout rationale)
- .planning/PROJECT.md - v1.3 milestone scope, target features, existing architecture Key Decisions

### Secondary (MEDIUM confidence)
- SQLite concurrent writes and database is locked errors (tenthousandmeters.com) - WAL single-writer model, busy_timeout mitigation
- Precision Matters: cents vs floating point for money (hackerone.com) - integer-minor-units practitioner consensus
- Petty-cash/POS feature landscape: Pleo, Zoho Expense, Weel, Shopify POS, KORONA POS, Fit Small Business (multiple cross-checked listings)
- The Idempotent Ledger (medium.com), Formance - What Is a Ledger - idempotency and standalone-balance-field risks
- Accu-Tax, GrowthForce - cash-vs-profit confusion pattern

---
*Research completed: 2026-07-14*
*Ready for roadmap: yes*
