# Phase 16: Manual Cash Movements & History - Context

**Gathered:** 2026-07-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Add an operator-driven WRITE path to the `cash_movements` ledger (manual
withdrawals with a mandatory category, manual deposits for opening balance /
correction) plus a READ view — a paginated, type-filterable history of every
cash movement (auto sale-credits, auto return-debits, and manual entries) — on
the «Финансы» page (desktop AND mobile).

**In scope:** extend `CASH_CATEGORIES` with manual keys; a thin manual-entry
service on top of `finance.record_cash_movement` (still the single write path);
withdrawal form (amount + category + comment) with negative-balance
warn-but-allow; deposit form (amount + reason + comment); a paginated/filtered
cash-movement history reusing the `/history` infra; wiring into both `/finance`
and `/m/finance`.

**Out of scope (later):** a separate `type` DB column / reporting schema, date-
range history filter, CSV export, profit & stock-valuation dashboard (Phase 17).

Requirements delivered: FIN-03, FIN-04, FIN-05, FIN-07.
</domain>

<decisions>
## Implementation Decisions

### Carrying forward from Phase 15 (locked — do not re-litigate)
- `finance.record_cash_movement` is the SINGLE write path for `cash_movements`
  (D-00b/D-00c). Routes NEVER write cash directly.
- Append-only ledger: no UPDATE/DELETE; corrections are new rows.
- Money is signed Integer cents; render via `app.core.format_cents`; NO currency
  symbol (single currency v1). Balance = live `SUM(amount_cents)` (D-00b).
- «Финансы» pages already exist on desktop (`/finance`) and mobile
  (`/m/finance`), balance-only today; nav present in `base.html` + mobile hub.

### Schema / data model — extend `category`, no new column (Option A)
- **D-01:** Model manual movements by EXTENDING `CASH_CATEGORIES` — NO new
  `type` column, no migration for one. `amount_cents` sign encodes direction
  (withdrawal negative, deposit positive; sale positive, return negative). The
  free-text comment lives in the existing `note` column. Chosen over a separate
  `type` column for minimal change; the app has one operator and reporting
  (Phase 17) can group by category.
- **D-01a:** Use category keys that make the 4 coarse buckets trivially
  derivable for the history filter — prefixed keys, e.g. `withdrawal_supplier`,
  `withdrawal_salary`, `withdrawal_rent`, `withdrawal_utilities`,
  `withdrawal_other`, `deposit_opening`, `deposit_correction`. Existing `sale` /
  `return` keys unchanged. Exact spelling = planner's discretion, but grouping
  into Продажа / Возврат / Снятие / Внесение MUST be trivial (prefix or a small
  grouping map).
- **D-01b:** RU labels via the existing `CASH_CATEGORIES` dict (same pattern as
  `OPERATION_TYPE_LABELS`). Withdrawal labels: Оплата поставщику / Зарплата /
  Аренда / Коммунальные / Прочее. Deposit labels: Начальный остаток /
  Корректировка.

### Manual entry — write path & sign
- **D-02:** Manual movements go through a thin manual-entry service function
  that wraps `finance.record_cash_movement` — it validates the category,
  applies the sign by direction, enforces the comment rule (D-04) and the
  warn-but-allow gate (D-05). The route layer still never writes cash directly.
- **D-02a:** Operator always enters a POSITIVE amount; the service applies the
  sign (снятие → negative, внесение → positive). Deposits can never be negative;
  withdrawals can never be positive. Reject zero/blank/non-integer amounts
  server-side, zero writes.

### Comment requirement
- **D-04:** `note` is mandatory ONLY for `withdrawal_other` («прочее») and
  `deposit_correction` («корректировка»); optional for the other categories.
  Enforced server-side (never trust the client). Empty/whitespace comment on
  those two → form re-renders with an error, ZERO writes.

### Negative-balance warn-but-allow (FIN-05)
- **D-05:** Reuse the sales oversell / min-price `confirm` pattern
  (`app/services/sales.py`). A withdrawal that would drive
  `compute_balance` < 0 with `confirm != "1"` → re-render the снятие form with a
  warning + a confirm control, ZERO writes. `confirm == "1"` → proceed and
  write. Applies to withdrawals ONLY (deposits only increase); non-negative
  withdrawals and all deposits never warn.

### Manual-entry UI
- **D-06:** TWO separate inline forms on the «Финансы» page, below the balance:
  «Снять деньги» (amount + category select + comment) and «Внести деньги»
  (amount + reason select Остаток/Коррекция + comment). Warn-but-allow logic
  lives only in the снятие POST. Server-rendered HTMX, consistent with existing
  forms (`writeoff_form`, `sale_form`).
- **D-06a:** Both `/finance` (desktop) and `/m/finance` (mobile) get manual
  entry + history — parity with Phase 15. Exact mobile layout (single scroll vs
  a dedicated mobile history subpage) = planner / UI-SPEC discretion following
  existing mobile patterns.

### History (FIN-07)
- **D-07:** Reuse the `/history` pattern end-to-end: `app/services/pagination.py`
  (`LIST_PAGE_SIZE`=20, `page_window`, `paginate`), a finance read service
  mirroring `operations.history_view`, a header-row «Тип» filter + HTMX
  swappable rows partial mirroring `partials/history_rows.html`, and `extra_qs`
  to preserve the active filter across pages.
- **D-07a:** The «Тип» filter offers the 4 coarse buckets Продажа / Возврат /
  Снятие / Внесение (derived from category groups per D-01a). NO product filter
  (N/A for cash). Default sort: date descending. Placement: on the «Финансы»
  page, below the balance and the entry forms (ROADMAP criterion 4).
- **D-07b:** Each row shows: date, тип/категория label, comment (`note`), and the
  signed amount via `format_cents`. Manual vs auto is visible from the
  тип/категория label (sale/return are auto; снятие/внесение are manual) — no
  separate flag column needed.

### Claude's Discretion
- Exact category-key spelling; service/function names (follow
  `finance.py`/`ledger.py`/`operations.py`); route paths; template structure;
  whether desktop and mobile share partials.
- Whether the history read filters in SQL or Python-slices via `paginate` —
  follow whatever `operations.history_view` does.
- Mobile layout specifics (single page vs subpage) per existing mobile patterns.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements / roadmap
- `.planning/ROADMAP.md` §Phase 16 — goal, depends-on (Phase 15), success criteria.
- `.planning/REQUIREMENTS.md` — FIN-03, FIN-04, FIN-05, FIN-07 wording.
- `.planning/phases/15-cash-ledger-foundation/15-CONTEXT.md` — locked decisions
  D-00a…D-04 (cash_movements shape, single write path, format/label rules).

### The single write path & data model (extend, don't fork)
- `app/services/finance.py` — `record_cash_movement(category, amount_cents,
  sale_id, note, commit)` write path + `compute_balance` (live SUM) for the
  negative-balance check.
- `app/models.py` §`CASH_CATEGORIES` (currently `{sale, return}` — EXTEND) and
  §`CashMovement` (fields: `category`, signed `amount_cents`, `note`, `sale_id`,
  audit cols); §`OPERATION_TYPE_LABELS` — the latin-key→RU-label dict pattern to
  mirror for the new categories.

### History reuse (mirror these verbatim)
- `app/services/pagination.py` — `LIST_PAGE_SIZE`, `page_window`, `paginate`.
- `app/services/operations.py` §`history_view` / `filter_products` — the
  paginated/filtered/sorted read shape to copy for the cash history.
- `app/routes/history.py` — the thin route: HX-detection, `page_window`,
  `extra_qs` filter re-serialization, full-page vs partial render.
- `app/templates/partials/history_rows.html` — the swappable rows+filter+
  pagination block to mirror.

### Warn-but-allow pattern (FIN-05)
- `app/services/sales.py` §`register_sale` — the `confirm` / oversell
  warn-with-zero-writes → re-confirm flow to copy for negative-balance.

### Finance surfaces to extend
- `app/routes/finance.py`, `app/routes/mobile_finance.py` — read-only today; add
  POST handlers (manual entry) + the history read.
- `app/templates/pages/finance.html`, `app/templates/mobile_pages/finance.html` —
  balance-only today; add the two forms + history block.
- `app/core.py` §`format_cents` — money display filter (reuse verbatim).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `finance.record_cash_movement` — extend usage (manual categories) rather than
  add a second writer; `compute_balance` gives the pre-write balance for D-05.
- `pagination.paginate` / `page_window` — the whole history pagination, no
  hand-rolled math (D-07).
- `operations.history_view` + `partials/history_rows.html` + `history.py` route
  — a near drop-in template for the cash history (swap product filter → none,
  operation types → cash coarse buckets).
- `sales.py` `confirm` gate — the warn-but-allow flow, copy for negative balance.
- `core.format_cents` / `new_id` / `utcnow_iso` — money/id/timestamp helpers.

### Established Patterns
- Single-write-path invariant: only `finance.py` writes `cash_movements`;
  routes read/validate + call the service.
- Latin-key → RU-label dicts (`CASH_CATEGORIES`, `OPERATION_TYPE_LABELS`) drive
  history column labels — extend the dict, don't hardcode labels in templates.
- Server-side validation with zero-write on failure; warn-but-allow via a
  `confirm="1"` re-POST.
- One swappable HTMX `*_rows.html` partial per list page + `extra_qs` state.

### Integration Points
- `CASH_CATEGORIES` in `app/models.py` — add manual keys + labels.
- `finance.py` — add manual-entry service fn (sign + validation + warn gate).
- `finance.py`/`mobile_finance.py` routes — add POST (entry) + history read;
  templates gain the forms + history block.
</code_context>

<specifics>
## Specific Ideas

- Withdrawal categories (fixed by ROADMAP): Оплата поставщику / Зарплата /
  Аренда / Коммунальные / Прочее.
- Deposit reasons: Начальный остаток / Корректировка (a 2-item select, not free
  text).
- Comment mandatory only for «Прочее» and «Корректировка».
- History «Тип» filter buckets: Продажа / Возврат / Снятие / Внесение.
- Two forms («Снять деньги» / «Внести деньги») below the balance; history below
  the forms; same on desktop and mobile.
</specifics>

<deferred>
## Deferred Ideas

- **Date-range filter on cash history** — useful for reconciliation; needs a
  date-picker (not present in `/history`). Possible follow-up, not this phase.
- **Separate `type` DB column (Option B)** — revisit only if Phase 17 reporting
  makes category-prefix grouping awkward.
- **Reports / CSV export / profit & stock-valuation dashboard** → Phase 17.

*Discussion otherwise stayed within phase scope.*

</deferred>

---

*Phase: 16-manual-cash-movements-history*
*Context gathered: 2026-07-15*
