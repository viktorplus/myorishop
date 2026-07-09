# Phase 5: Stock Operations & History - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-09
**Phase:** 5-stock-operations-history
**Areas discussed:** Write-off reason, Return sale-linking, Correction input mode, History browsing

---

## Write-off — reason capture (OPS-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Category + note (hybrid) | Required category from list + optional free-text note; ready-made grouping for RPT-03 | ✓ |
| Categories only | Dropdown, no free text; fast but no detail | |
| Free text | Single field; simple but hard to group in reports | |

**User's choice:** Category + comment (hybrid).
**Notes:** Category set proposed (брак/просрочка/потеря/личное/подарок/прочее → Latin codes). Stored in `payload`; codes Latin, labels RU. Feeds Phase 6 RPT-03 grouping.

---

## Return — sale linking (OPS-02)

| Option | Description | Selected |
|--------|-------------|----------|
| From the sale line | Start from recent sale / customer history; `sale_id` + price/cost copied from line; partial return; cap at sold qty | ✓ |
| Code form + sale search | Enter code, then search original sale; more flexible, weaker qty control | |
| By code, no link | Simple return, `sale_id` optional; violates OPS-02 intent | |

**User's choice:** From the sale line (recommended).
**Notes:** Return copies the frozen `unit_price_cents`/`unit_cost_cents` snapshot from the original sale line (profit symmetry, preserves SAL-05). Partial returns allowed; returned qty ≤ remaining returnable. `Operation.sale_id` already exists — no schema change.

---

## Correction — input mode (OPS-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Counted quantity (absolute) | Enter counted stock; system writes delta as correction; natural for stocktakes | |
| Delta (+/−) | Enter difference directly (existing draft); sign-error prone | |
| Both modes | Toggle between counted/delta | ✓ |

**User's choice:** Both modes (diverged from the single-mode recommendation).
**Notes:** Always written as a `correction` operation, never a direct edit. Recommended UI default = counted quantity; delta as secondary toggle. Replaces the walking-skeleton `POST /ops`. Optional reason/note + mode in `payload`.

---

## History browsing (OPS-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated /history | All products, newest first, type/product filters, pagination; single audit place | ✓ |
| Extend home | Reuse home ledger; but home is single-product + form, mixes roles | |
| Per-product on card | History on product card; useful but not "full history" | |

**User's choice:** Dedicated /history with filters (recommended).
**Notes:** Type + product filters this phase; date-range deferred to Phase 6 reports. Pagination/limit required. Extend `ledger_rows.html`; add nav link. Per-product card view optional.

---

## Claude's Discretion

- Route/template structure and URLs for write-off, return, correction, history.
- Migration 0005 only if a genuinely new column/index is justified — none expected (types + `sale_id` + `payload` already exist).
- RU UI text, empty-states, confirmation wording, form layouts.
- Whether write-off shows an oversell-style warn/confirm (recommended: yes, reuse Phase 4 pattern).
- Default correction input mode (recommended: counted quantity); pagination mechanism/page size.
- Exact `payload` key shapes; optional per-product history on the product card.

## Deferred Ideas

- Write-off/sales/profit/stock reports + CSV export — Phase 6 (RPT-01..04, BCK-02).
- Date-range filtering on history — folded into Phase 6 period reporting.
- Per-product history view on product card — optional, not required by OPS-04.
- Purchase-frequency reminders / interested-customer lists — CST-V2-01/02.
- Multi-currency, multi-operator sync, user roles — out of scope per PROJECT.md.
