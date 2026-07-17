# Phase 21: Customer Profiles & Purchase Insights - Context

**Gathered:** 2026-07-17
**Status:** Ready for planning

<domain>
## Phase Boundary

A customer profile holds every way to reach the person — multiple phone numbers, multiple Telegram handles, multiple emails, multiple free-form social-profile links, and a single physical address — and shows purchase insights the operator can act on: last order date, spend totals for the current month/quarter/year, and the customer's top-10 favorite products ranked by purchase frequency.

**Explicitly NOT in this phase:** No changes to the sale form's customer picker/new-customer flow (SALE-03..06, Phase 22 — this phase only extends the `Customer` profile itself and its own form/detail pages). No anonymous/walk-in customer row (Phase 22, SALE-06). No structured/validated contact formats (phone number format validation, email format validation) — plain free-text values per the roadmap's Out of Scope note ("A structured multi-provider contacts schema... is unnecessary complexity for a single-operator local tool — plain repeatable text fields suffice").

</domain>

<decisions>
## Implementation Decisions

### Contact fields storage (CUST-01..04)

- **D-01: One generic child table, `CustomerContact(id, customer_id, kind, value, label?)`, with a `kind` discriminator** covering all four contact types (`phone`, `telegram`, `email`, `social`), guarded by a SQLite `CHECK (kind IN (...))` constraint (portable to PostgreSQL). Chosen over four separate tables (`CustomerPhone`/`CustomerTelegram`/`CustomerEmail`/`CustomerSocial` — rejected as 4x boilerplate for data that is structurally identical, a label+value pair, per requirements as written) and over JSON/list columns directly on `Customer` (rejected because deleting a single contact would require rewriting a whole array instead of one HTMX row-delete, breaking the app's existing per-row-partial CRUD pattern).
- **D-02: The physical address (CUST-05) is a plain nullable column directly on `Customer`**, independent of D-01 — the requirement wording is singular ("a physical address field"), not "multiple", so it does not belong in the `CustomerContact` table.
- Follow the codebase's existing FK convention: plain `mapped_column(ForeignKey(...))`, no ORM `relationship()`/`back_populates` (there are none anywhere in `app/models.py` today — confirmed by research).

### Contact fields edit UI (CUST-01..04)

- **D-03: Dynamic repeatable rows added via HTMX**, mirroring the exact pattern already shipped in `app/templates/partials/sale_form.html:74` (`hx-get="/sales/row" hx-target="#basket-rows" hx-swap="beforeend"`) and its row partial `sale_row.html` — an "Добавить строку" button appends a blank input row per contact kind; row removal is a client-side `hx-on:click` with no server round-trip. This repeats 4 times (phone/telegram/email/social) rather than the sale basket's once, but reuses one mental model already proven in this codebase rather than introducing a new UI convention (textarea-per-type was considered and rejected — no textarea exists anywhere in `app/templates` today).
- Each contact row maps to one `CustomerContact` row with its own id — add/delete are per-row HTMX operations, consistent with D-01's schema choice.

### Favorite products ranking (CUST-08)

- **D-04: One ranked list, sorted by purchase frequency** (count of distinct sale operations/lines for that product), with total quantity sold shown alongside as a secondary column — not a separate ranking and not a blended weighted score (a blended score was explicitly rejected: it would require inventing unweighted business rules nobody asked for and would be unexplainable to the operator, "why is this #1?").
- **D-04a: Show the top 10 products.**
- Query mirrors the existing `purchase_history` join (`app/services/customers.py:202-214`: `Operation` → `Sale` → `Product`, filtered `Sale.customer_id == customer_id, Operation.type == "sale"`), grouped by product with `func.count()` for frequency and `func.sum(-Operation.qty_delta)` for quantity — sale operations store `qty_delta` negated, confirmed against the existing pattern in `app/services/reports.py:47,110,153` and `app/services/returns.py:53`. Returns/write-offs are excluded from the ranking by keeping the `type == "sale"` filter, same as `purchase_history` already does.

### Spend periods (CUST-07)

- **D-05: Calendar-aligned period-to-date** — current calendar month, current calendar quarter, and current calendar year, each computed from its period start through today via the existing shared helper `local_day_bounds_utc(start_day, end_day, tz_name)` (`app/core.py:75`, the single reused date-math path for all period-based reports since Phase 6). This mirrors the month-preset convention the operator already sees on `/reports/sales` (`app/routes/reports.py`'s `_resolve_period`). Rolling 30/90/365-day windows and "last complete period" were both considered and rejected — rolling windows would silently drift from calendar months the operator is already trained to expect from the reports pages; "last complete period" excludes the customer's activity so far this period, the opposite of "what to act on now" per this phase's own goal.
- **D-06: Spend is net of returns.** The query sums both `sale` and `return` Operation rows for the customer with the SAME formula `-Operation.qty_delta * Operation.unit_price_cents` — a `return` row's `qty_delta` is the positive mirror of the original sale's negative `qty_delta`, at the same frozen `unit_price_cents` (confirmed via `app/services/returns.py`'s frozen-price-copy contract on `register_return`), so the formula nets out returned revenue automatically with zero extra branching. This is a **new** query in `app/services/customers.py`, distinct from `purchase_history()`, which stays `type == "sale"`-only (it displays what was bought, not net financial exposure) — a deliberate scope boundary, not an oversight.

### Claude's Discretion

- Exact Russian field labels/placeholders for each contact kind (e.g. "Телефон", "Telegram", "Email", "Соцсеть") and the per-section "Добавить строку" button copy.
- Whether `CustomerContact.label` (optional free-text sub-label, e.g. "рабочий"/"личный") ships in this phase or is left null-only for now — CUST-01..04 do not ask for labeled contacts, only for multiple values per kind.
- Exact `kind` CHECK-constraint literal values (`"phone"`, `"telegram"`, `"email"`, `"social"` or Russian equivalents) — internal implementation detail, not operator-facing.
- Layout of the new purchase-insights blocks (last order date, month/quarter/year spend, top-10 favorites) on `customer_detail.html` relative to the existing purchase-history section.
- How "last order date" (CUST-06) is computed — trivially derivable as `max(created_at)` over the existing `purchase_history` rows, or a small dedicated query; no gray area, just an implementation choice.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and scope
- `.planning/REQUIREMENTS.md` §Customers — CUST-01..08 (lines 60-70).
- `.planning/ROADMAP.md` §"Phase 21: Customer Profiles & Purchase Insights" — goal, 4 success criteria, depends-on note (nothing in this milestone; builds on shipped v1.0 customer/sale ledger).
- `.planning/ROADMAP.md` §Out of Scope — "New backend data model for social/contact fields beyond free-text lists" is explicitly rejected; plain repeatable text fields are sufficient (grounds D-01/D-03's simplicity).
- `.planning/PROJECT.md` §Key Decisions — house conventions (UUID string PKs, integer cents, single ledger write path `record_operation`, `Mapped[]`/`mapped_column()` SQLAlchemy 2.0 style).
- `CLAUDE.md` §"What NOT to Use" — no SQLite-specific SQL (portable ORM constructs only), integer minor units for money, no FLOAT/REAL for money.

### Prior art this phase extends (not replaces)
- `app/models.py` Customer class (lines 333-351) — current schema: name, surname, consultant_number, search_lc; no contact fields yet.
- `app/models.py` Batch class — the codebase's precedent for "one small child table per repeatable concept," partially followed by D-01 (collapsed to one shared table since all 4 contact kinds share an identical label+value shape, unlike Batch's genuinely distinct columns).
- `app/services/customers.py::purchase_history` (lines 202-214) — the join pattern (`Operation`→`Sale`→`Product`, `type == "sale"`) that D-04's favorites query and D-06's net-spend query both extend/mirror.
- `app/routes/customers.py` — thin-route convention; new contact-row and insights endpoints follow this file's existing shape.
- `app/templates/pages/customer_detail.html`, `customer_form.html` — current profile/edit templates to extend with contact rows, address field, and insights blocks.

### Precedent patterns to follow
- `app/templates/partials/sale_form.html:74` + `sale_row.html` — the HTMX repeatable-row add/remove mechanism D-03 mirrors for contact fields.
- `app/core.py:75` `local_day_bounds_utc` — the shared period-boundary helper D-05 must reuse unchanged (Phase 6 convention: "Single shared period-filter + local-day-boundary helper reused unchanged across all four period-based reports").
- `app/routes/reports.py` `_resolve_period` — the existing month-preset convention D-05's calendar-period choice mirrors.
- `app/services/reports.py::sales_profit_report` (line 20, `qty = -op.qty_delta` pattern) — the sign convention D-04/D-06 both reuse for turning stored `qty_delta` into a human-facing positive quantity/amount.
- `app/services/returns.py::register_return` — confirms the frozen-price-copy contract onto `return` operations that makes D-06's net-of-returns formula work without extra branching.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/customers.py::purchase_history` — join pattern to extend for both the favorites query (D-04) and the net-spend query (D-06).
- `app/templates/partials/sale_form.html` / `sale_row.html` — HTMX add/remove row mechanism to adapt for the 4 contact-kind sections (D-03).
- `app/core.py::local_day_bounds_utc` — period-boundary helper to reuse unchanged for D-05's month/quarter/year calculations.
- `app/routes/reports.py::_resolve_period` — existing month-preset convention to mirror for quarter/year period starts.

### Established Patterns
- No ORM `relationship()`/`back_populates` anywhere in `app/models.py` — every FK is a plain `mapped_column(ForeignKey(...))`, queried manually. `CustomerContact`'s FK to `Customer` must follow this.
- Money as integer cents; `qty_delta` is stored signed (negative for `sale`, positive for `return`) — always negate (`-qty_delta`) for a human-facing "how much" number, per the established pattern in `reports.py`/`returns.py`.
- Server-rendered Jinja2 + HTMX 2.0.10 (vendored, offline). No SPA, no build step, plain CSS in one stylesheet.
- Cyrillic-safe search via a Python-side `str.lower()` + `search_lc` shadow column (SQLite `LIKE` doesn't fold Cyrillic) — an existing `Customer` convention, not directly touched by this phase but worth knowing if contact search is ever added later.

### Integration Points
- `app/models.py` — add `CustomerContact` model (D-01) + `address` column on `Customer` (D-02); one new Alembic migration.
- `app/services/customers.py` — new functions: create/list/delete `CustomerContact` rows; `favorite_products()` (D-04); `spend_totals()` for month/quarter/year net of returns (D-05/D-06); last-order-date lookup (CUST-06, trivial).
- `app/routes/customers.py` — new endpoints for contact-row add/remove (mirroring `/sales/row`), extended `customer_form.html` POST handlers to accept contact arrays + address, extended `customer_detail` GET to pass insights context.
- `app/templates/pages/customer_form.html` — add 4 repeatable contact-row sections + address field.
- `app/templates/pages/customer_detail.html` — add purchase-insights blocks (last order date, month/quarter/year spend, top-10 favorites).

</code_context>

<specifics>
## Specific Ideas

- PROJECT.md's own v2.0 target-features framing matches the locked decisions exactly: "extended profile (multiple phones/Telegram/emails/social profiles/address) plus purchase stats and recommendations (last order date, spend by month/quarter/year, favorite products by frequency/quantity)."
- The operator confirmed spend should reflect money actually kept (net of returns), not gross sales — "how much money is left from this customer," not a raw sales total.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. No scope creep occurred across the 4 discussed areas (contact storage, contact UI, favorites ranking, spend periods).

</deferred>

---

*Phase: 21-Customer Profiles & Purchase Insights*
*Context gathered: 2026-07-17*
