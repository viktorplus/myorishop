# Phase 21: Customer Profiles & Purchase Insights - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-17
**Phase:** 21-Customer Profiles & Purchase Insights
**Areas discussed:** Contact fields storage shape, Contact fields edit UI, Favorite products ranking, Spend period definition

---

## Contact fields storage shape

| Option | Description | Selected |
|--------|-------------|----------|
| Generic `CustomerContact(customer_id, kind, value)` table | One table, `kind` discriminator (phone/telegram/email/social) + CHECK constraint; one PK per record for HTMX row add/delete | ✓ |
| Four separate tables | `CustomerPhone`/`CustomerTelegram`/`CustomerEmail`/`CustomerSocial`, one model/migration/CRUD set per kind | |
| JSON/list columns on `Customer` | No new table; list-typed columns per kind, add-column-only migration | |

**User's choice:** Generic `CustomerContact` table (Option a).
**Notes:** Research confirmed the 4 contact kinds are structurally identical (label+value pairs), so a shared discriminated table avoids 4x boilerplate without losing per-row HTMX delete. CUST-05 (address) is singular in the requirements text, so it stays a plain column on `Customer` regardless of this choice.

---

## Contact fields edit UI

| Option | Description | Selected |
|--------|-------------|----------|
| Dynamic repeatable rows (HTMX) | Mirrors `sale_form.html`'s "Добавить строку" `hx-get`/`hx-swap="beforeend"` row-add + client-side row-remove | ✓ |
| Single field with lines (textarea) | One `<textarea>` per contact type, newline-separated values, server splits | |
| Fixed number of slots | e.g. 3 always-visible phone inputs, blanks ignored | |

**User's choice:** Dynamic repeatable rows (HTMX) (Option a).
**Notes:** Consistent with the storage decision — each row maps to one `CustomerContact` record. Reuses an existing, proven pattern rather than introducing a new UI convention (no textarea exists anywhere in the app's templates today).

---

## Favorite products ranking

| Option | Description | Selected |
|--------|-------------|----------|
| Single list by frequency | One ranking sorted by purchase-event count, quantity shown as secondary column | ✓ |
| Two separate lists | Top-N by frequency and top-N by quantity, shown side by side | |
| Blended weighted score | Single normalized frequency+quantity score | |

**User's choice:** Single list by frequency (Option a).
**Notes:** Follow-up question resolved list length — see below.

## Favorite products — list length (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Top 5 | Researcher's own recommendation | |
| Top 3 | Smallest footprint | |
| Top 10 | Fuller picture of preferences | ✓ |

**User's choice:** Top 10.
**Notes:** Operator wants a fuller picture than the researcher's default top-5 recommendation.

---

## Spend period definition

| Option | Description | Selected |
|--------|-------------|----------|
| Calendar period-to-date | Current month/quarter/year from period start to today, via existing `local_day_bounds_utc` | ✓ |
| Rolling window | Last 30/90/365 days from today | |
| Last complete period | Last finished calendar month/quarter/year, excluding the current in-progress one | |

**User's choice:** Calendar period-to-date (Option a).
**Notes:** Mirrors the existing `/reports/sales` month-preset convention. Follow-up on gross vs. net resolved below.

## Spend period — gross vs. net of returns (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Net of returns | Sum both `sale` and `return` operations with the same `-qty_delta * unit_price_cents` formula | ✓ |
| Gross revenue only | `sale` operations only, returns not subtracted | |

**User's choice:** Net of returns.
**Notes:** Operator wants "money actually kept from this customer," not a raw sales total. This is a new query, separate from the existing `purchase_history()` (which stays sale-only for its own display purpose).

---

## Claude's Discretion

- Exact Russian field labels/placeholders for each contact kind and per-section button copy.
- Whether `CustomerContact.label` (optional sub-label like "рабочий"/"личный") ships now or stays null-only.
- Exact `kind` CHECK-constraint literal values.
- Layout of the new purchase-insights blocks on `customer_detail.html` relative to the existing purchase-history section.
- Implementation detail of "last order date" (CUST-06) — trivial derivation, no gray area.

## Deferred Ideas

None — discussion stayed within phase scope.
