# Phase 15: Cash Ledger Foundation - Context

**Gathered:** 2026-07-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Introduce the cash till as a second append-only ledger. Every sale auto-credits
the till by the sale's total; every sale-linked return auto-debits it
symmetrically. A new «Финансы» nav section shows the current cash balance.

**In scope:** `cash_movements` schema + append-only triggers; `finance.py`
single-write-path service with a live-`SUM()` balance; auto-credit wired into
`register_sale`; auto-debit wired into `register_return`; a «Финансы» page that
displays the current balance; nav entry on desktop AND the mobile hub.

**Out of scope (later phases):** manual withdrawals/deposits, negative-balance
warn-but-allow, paginated/filterable movement history (Phase 16); reports, CSV
export, profit/stock-valuation dashboard (Phase 17).

Requirements delivered: FIN-01, FIN-02, FIN-06.
</domain>

<decisions>
## Implementation Decisions

### Locked by research (do not re-litigate)
- **D-00a:** Separate `cash_movements` table — NOT reusing `operations` (which
  has a NOT-NULL `product_id` FK and mandatory `batch_id`). Sync-ready shape
  copied from `Operation`: UUID PK, signed `amount_cents`, `device_id`/`seq`,
  `created_at`/`created_by`, nullable `sale_id` FK. Append-only BEFORE
  UPDATE/DELETE `RAISE(ABORT,…)` triggers mirroring `alembic/versions/0001_initial_schema.py`.
- **D-00b:** New `app/services/finance.py` — sibling to `ledger.py`, the SINGLE
  write path for `cash_movements`. Balance = live `SUM(amount_cents)` (no cache
  at this scale). Money stays Integer cents; no Decimal/money/accounting lib.
- **D-00c:** Wiring is at the SERVICE layer, inside the existing transactions —
  `register_sale` calls finance with `commit=False` before its trailing
  `session.commit()`; `register_return` does the symmetric debit inside its
  own commit. Never from the route layer (desktop + mobile callers both get it
  for free). Sale credit and return debit MUST ship together this phase.
- **D-00d:** Return debit is computed INDEPENDENTLY — `qty_returned ×` the
  origin sale op's frozen `unit_price_cents` (mirrors D-06/D-07 in
  `returns.py`), never reconciled against the prior credit row.

### «Финансы» page content
- **D-01:** Phase 15 shows the balance ONLY — one prominent current-balance
  figure, no movement list. Full history (with Phase 14 pagination/filter) lands
  in Phase 16, so no throwaway mini-list is built now.

### Navigation
- **D-02:** Entry appears in BOTH places: the desktop top nav (`base.html`,
  alongside Отчёты/Экспорт — Финансы is an analytical section) AND a tile in the
  mobile hub (`mobile_pages/home.html`, `<a class="mobile-tile" href="/m/…">`).
  A mobile-rendered balance page is therefore in scope this phase.

### Cash-record granularity
- **D-03:** ONE aggregated `cash_movement` per sale — `amount_cents` = the sale
  total (sum of line `price × qty`), linked via `sale_id`. A return likewise
  writes ONE debit movement. Keeps history readable and return matching simple;
  matches the research's nullable-`sale_id`-FK design.

### Balance label & format
- **D-04:** Heading «Баланс кассы». Render via `app.core.format_cents`
  (e.g. `12500` → `125,00`). Zero shows as `0,00`. NO currency symbol — single
  currency in v1, consistent with every other money surface in the app.

### Claude's Discretion
- Exact migration number/file name, trigger SQL text, `finance.py` function
  names (following `ledger.py`/`writeoffs.py` naming), route paths, and page
  template structure — follow existing conventions.
- Whether the desktop and mobile balance pages share a partial or each render
  their own — planner's call based on existing base-template patterns.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Research (in-repo, HIGH confidence — this phase needs no external research)
- `.planning/research/SUMMARY.md` — architectural verdict (separate
  `cash_movements` table, `finance.py` single write path, live-SUM balance,
  ship sale-credit + return-debit together). Phase 1 mapping = this phase.
- `.planning/research/ARCHITECTURE.md` — component/build-order design for the
  cash ledger.
- `.planning/research/PITFALLS.md` — the 8 codebase-grounded pitfalls
  (esp. #1 don't reuse `operations`, #2 ship debit with credit, #3 compute
  return debit independently, #4 no stale-cache balance).

### Codebase templates to mirror
- `app/services/ledger.py` — `record_operation` single-write-path pattern,
  `next_seq`, `compute_stock` (balance = live SUM analog), `rebuild_stock`.
- `app/models.py` — `Operation` mapped class shape to copy for `CashMovement`.
- `app/services/sales.py` §`register_sale` — the credit insertion point
  (stage `commit=False` before the trailing `session.commit()`).
- `app/services/returns.py` §`register_return` — the debit insertion point;
  frozen `unit_price_cents`/`unit_cost_cents` copy (D-06/D-07).
- `alembic/versions/0001_initial_schema.py` — append-only trigger template.
- `app/core.py` §`format_cents` — money display filter.
- `app/templates/base.html` (desktop nav) and
  `app/templates/mobile_pages/home.html` (mobile hub tiles) — nav insertion.
- `app/services/writeoffs.py` — closest service+route+template shape for the
  new Финансы route/page.

### Requirements / roadmap
- `.planning/ROADMAP.md` §Phase 15 — goal, depends-on, success criteria.
- `.planning/REQUIREMENTS.md` — FIN-01, FIN-02, FIN-06 wording.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/core.format_cents` / `to_cents` / `new_id` / `utcnow_iso` — money and
  id/timestamp helpers, reuse verbatim.
- `ledger.record_operation` — structural template for
  `finance.record_cash_movement` (append row + audit stamp + same transaction).
- `settings.device_id` / `settings.operator_name` — audit-field sources.

### Established Patterns
- Single-write-path invariant: cash rows must be written ONLY through
  `finance.py`, mirroring the "only `record_operation` touches operations" rule.
- `commit=False` staging + one `session.commit()` per logical write (WR-03) —
  the credit must be staged inside `register_sale`'s existing transaction so a
  rolled-back sale writes zero cash rows.
- Append-only ledger: no UPDATE/DELETE; corrections are new rows (Phase 16).

### Integration Points
- `register_sale` (`app/services/sales.py`) — after `total_cents` is computed,
  before the trailing `session.commit()`.
- `register_return` (`app/services/returns.py`) — inside the
  `record_operation(..., commit=True)` block; needs to become a staged
  multi-write so cash + stock commit together.
- Desktop nav `base.html`; mobile hub `mobile_pages/home.html`.
</code_context>

<specifics>
## Specific Ideas

- Balance heading text: «Баланс кассы».
- Money format exactly as everywhere else (`format_cents`), no ₽/currency glyph.
- In Phase 15 the balance can only move via sales (+) and capped returns (−),
  so it cannot go negative yet — negative-balance handling is deferred to
  Phase 16 with manual withdrawals.
</specifics>

<deferred>
## Deferred Ideas

- **Movement history list on the Финансы page** — full paginated/filterable
  history (reusing Phase 14 infra) → Phase 16 (FIN-07).
- **Manual withdrawals/deposits + negative-balance warn-but-allow** → Phase 16
  (FIN-03, FIN-04, FIN-05).
- **Reports, CSV export, profit & stock-valuation dashboard** → Phase 17
  (FIN-08…FIN-12).

*Discussion otherwise stayed within phase scope.*

</deferred>

---

*Phase: 15-cash-ledger-foundation*
*Context gathered: 2026-07-14*
