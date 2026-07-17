# Phase 22: Sales Page Rebuild - Context

**Gathered:** 2026-07-17
**Status:** Ready for planning

<domain>
## Phase Boundary

The sale form (desktop `app/routes/sales.py` + mobile `app/routes/mobile_sales.py`) gets an explicit new/existing/anonymous customer selector at the top, a live running total under the basket table, and the recent-sales list gains a customer-name column. The basket table shape (code/name/qty/price) already exists and is not restructured — only the customer-selection UI, the total, and the recent-sales column are new work.

**Explicitly NOT in this phase:** No changes to `Customer`/`CustomerContact` schema (Phase 21 territory, already shipped). No new "anonymous" `Customer` DB row — walk-in stays `customer_id = NULL`, unchanged from today. No new profile fields (phone/Telegram/email/social/address) on the sale form's inline new-customer flow — those stay card-only (Phase 21 `customer_form.html`). No basket table restructuring — SALE-01's code/name/qty/price shape is already shipped.

</domain>

<decisions>
## Implementation Decisions

### Customer selector (SALE-03)

- **D-01: Explicit 3-way radio ("Новый" / "Существующий" / "Аноним"), each option HTMX-loads its own block** (`hx-get` per radio change, server renders the block) — not a client-side show/hide of blocks that are all already in the DOM. Chosen over pure client-side toggling because it mirrors the app's dominant pattern of server-rendered partial swaps rather than introducing a new all-client-JS interaction for this control (the live-total area is the one place client-only JS was explicitly chosen — see D-06 — but the selector itself follows the existing HTMX convention).
- **D-02: Default selection on form open is "Существующий"** (existing customer search/picker), not anonymous. Matches operator's stated workflow — most sales are to a known customer.
- **D-03: Switching the radio must not clobber data already entered in another mode.** If the operator types into the new-customer fields, picks an existing customer, then switches back, that mode's state must still be there — the HTMX swap that loads a different mode's block must preserve the other modes' already-filled state (not re-fetch/reset them). Implementation detail (which mode's HTML stays in the DOM vs. re-rendered) is Claude's discretion, but the behavior contract is: no silent data loss on radio switch.
- **D-04 (scope): Mobile sale wizard (`app/routes/mobile_sales.py`) gets the SAME 3-way customer selector in this phase — full desktop/mobile parity.** Mobile currently has NO customer picker at all (`customer_id=""` hardcoded, per the wizard's old "D-04: no mobile customer picker this phase" note — that deferred decision is now superseded). This is a real scope expansion beyond what REQUIREMENTS.md's SALE-03..07 wording states literally (unlike PROD-05 in Phase 18, SALE-03..07 don't say "desktop and mobile" explicitly) — operator confirmed explicitly when asked. Treat this as in-scope, not a gap to flag later.

### Anonymous sale (SALE-06)

- **D-05: Keep `customer_id = NULL` as-is — no new "Аноним" row in `customers`.** The "Аноним" radio option simply results in no `customer_id` being set on submit, identical to today's walk-in behavior. No migration, no seed data, no new service logic for a system customer profile.
- **D-06: Recent-sales list (SALE-07) shows "Розница" (muted style) in the customer column for any sale with `customer_id IS NULL`.** Not a blank/em-dash — an explicit muted label so the operator can tell "no customer recorded" apart from "data missing".

### New-customer inline fields (SALE-05)

- **D-07: The inline new-customer form on the sale page keeps exactly the 3 fields it has today — Имя / Фамилия / Номер консультанта.** None of Phase 21's new profile fields (phone/Telegram/email/social/address, all `CustomerContact` multi-value rows) are added to the sale-form inline flow. Operator explicitly rejected adding even a single phone+address shortcut. Full profile completion happens later on the customer's own card (`customer_form.html`), not at sale time. This applies to both desktop `sale_customer.html` and whatever mobile customer-selector partial D-04 introduces — same 3 fields only.
- **D-10: «Новый» mode creates the customer via the existing explicit «Добавить покупателя» button, NOT on sale submit — plus a 422 guard against the silent-walk-in bug.** Operator confirmed 2026-07-17 after research surfaced the defect: `sale_create` (`app/routes/sales.py:390-398`) reads **only** `customer_id` and never looks at `name`/`surname`/`consultant_number`, so filling the 3 fields and pressing «Оформить продажу» today silently writes a walk-in sale with no customer attached. Contract: keep `POST /sales/customer` (`sales.py:343`, already shipped and covered by `test_web_customer_quick_create_returns_chip`) as the sole creation path; `register_sale`'s signature is untouched. **Add the guard:** when `customer_mode == "new"` AND `customer_id` is empty AND any of the 3 fields is non-blank, `sale_create` returns 422 with a Russian error («Сначала нажмите «Добавить покупателя»») instead of silently writing a walk-in. Rejected: creating the customer inside `sale_create` — changes the endpoint's contract and pulls in duplicate-handling and basket-error-rollback logic for no operator-visible gain.

### Live running total (SALE-02)

- **D-08: Client-side JS, no HTMX round trip** — one delegated `document.addEventListener('input', ...)` (same architecture as `app/static/price-cue.js` from Phase 18), reading all basket rows' `qty[]`/`price[]` values, parsing with the SAME accept-set as the server's `to_cents` (`app/core.py:28` — comma-decimal, no space-thousands), summing to a running total (amount) and unit count. Rejected: server-side debounced HTMX recompute — unnecessary round trips on a 5-10 row basket where the total is purely advisory display, and this repo already has the client-JS-mirrors-server-parse precedent (Phase 18 D-13).
- **D-09: If any basket row has an invalid/incomplete qty or price, show an "итог неполный" (incomplete total) marker** alongside the running total, rather than silently excluding that row's contribution from the sum. Keeps the operator from mistaking a partial sum for the real total mid-entry.
- The total is advisory-only, same convention as the colour cue: the server remains the sole authority on the actual charged amount (`_build_lines` / `register_sale` in `app/services/sales.py`), computed authoritatively on submit. No client-side money math feeds into what gets saved.

### Defects found during research — in scope (added 2026-07-17)

- **D-11: Fix the mobile batch-card `hx-include` gap in this phase.** Operator confirmed 2026-07-17. `app/templates/mobile_partials/batch_card_picker.html:48-54` fires `hx-get` with no `hx-include`, and htmx only auto-includes the enclosing form on **non-GET** requests — so tapping a batch card in the mobile wizard drops the accumulated basket (verified empirically: `code_acc` hidden inputs absent from the response). Every sibling wizard (`writeoff`, `receipts`, `corrections`) already passes `hx-include="closest form"`; the sale wizard is the outlier. Pre-existing defect, but it sits exactly on D-04's blast radius. **It is a shared partial across 4 wizards** — pair the one-attribute change with a full `test_mobile_*` pass to prove no sibling regressed.
- **D-12: The verified chip-loss bug is SALE-03/04's to fix, not a separate concern.** A 422/oversell re-render silently drops the selected-customer chip while still submitting `customer_id` (verified: `customer_id survives in hidden input: True` / `chip text present: False`). Cause: `sale_create`'s error branches (`app/routes/sales.py:417, 435, 447`) pass only `{"customer_id": ...}`, but `sale_customer.html:17` renders the chip on `{% if selected %}`, never set on that path. The UI says "no customer" while the DB says otherwise. The rebuilt customer header MUST NOT re-ship this — a shared customer-context builder that populates `selected` on every render path (including error branches) is the recommended fix.

### Claude's Discretion

- Exact Russian wording/labels for the 3 radio options and the "итог неполный" marker.
- Which mode's HTML stays live in the DOM vs. gets re-fetched on radio switch, as long as D-03's no-data-loss contract holds.
- Whether the mobile customer selector (D-04) reuses the desktop `sale_customer.html` partial structure or gets its own mobile-styled equivalent — desktop/mobile already have separate route/template trees throughout the app (established pattern), so a mobile-specific partial is expected, not a deviation. **Resolved 2026-07-17 (research recommendation, within discretion): own mobile partial.** `customer_picker.html`'s `hx-on:click` hard-codes four desktop element ids; reuse would require parameterising all four and risks id collisions. A mobile-styled card list matches the established `mobile_partials/` tree and the `.mobile-card` idiom.
- Exact markup/placement of the live-total display (amount + unit count) directly under the basket table.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and scope
- `.planning/REQUIREMENTS.md` §Sales — SALE-01..07 (lines 50-58).
- `.planning/ROADMAP.md` §"Phase 22: Sales Page Rebuild" — goal, 5 success criteria, depends-on note (Phase 18 for ПЦ on the sale line, Phase 21 for extended profile fields — the latter explicitly NOT surfaced inline per D-07).
- `.planning/PROJECT.md` §Key Decisions — house conventions (single ledger write path, `record_operation`, integer cents, `Mapped[]`/`mapped_column()` SQLAlchemy 2.0 style).

### Prior art this phase extends (not replaces)
- `app/templates/partials/sale_form.html`, `sale_row.html` — the already-shipped code/name/qty/price basket table (SALE-01) and its HTMX guards (`before-swap`/`oob-before-swap` focus/typing protections) — do not regress these when adding the live-total listener.
- `app/templates/partials/sale_customer.html` — current combined search+quick-create block; D-01 restructures this into 3 explicit radio-driven states.
- `app/templates/partials/recent_sales.html` — current columns (Когда/Код/Название/Кол-во/Цена/Сумма/Действие); D-06 adds a customer column.
- `app/routes/mobile_sales.py` — the wizard's `customer_id=""` hardcode (line ~346) that D-04 supersedes.
- `app/services/customers.py::search_customers` — existing name/surname/consultant_number search, already reusable for the "Существующий" mode's autocomplete (SALE-04) with no changes needed to the search itself.
- `app/models.py` `Sale`/`Customer` — `Sale.customer_id` nullable (D-04 model comment: "walk-in sale is valid"); D-05 keeps this contract unchanged.

### Precedent patterns to follow
- `app/static/price-cue.js` (Phase 18) — the delegated-listener, client-side-advisory-only JS pattern D-08 mirrors exactly, including the "server is the tiebreaker" principle.
- `app/core.py:28` `to_cents` — canonical RU-comma money parser; the live-total JS must mirror its accept-set, same as price-cue.js already does.
- `.planning/phases/18-two-price-model-consolidation/18-CONTEXT.md` D-12/D-13 — "never use an HTMX round-trip per keystroke" and "no client-side money math is violated because it's advisory-only" — both principles apply directly to D-08/D-09.
- `.planning/phases/21-customer-profiles-purchase-insights/21-CONTEXT.md` — confirms the full extended-profile field set that D-07 deliberately excludes from the sale form.

### Money and ledger rules
- `CLAUDE.md` §"What NOT to Use" — integer minor units only; portable SQLAlchemy Core/ORM constructs only.
- `app/services/sales.py::register_sale` / `_build_lines` — remains the sole authoritative total/price computation on submit; D-08's client total never substitutes for it.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/customers.py::search_customers` — existing search by name/surname/consultant_number, reusable unchanged for SALE-04's autocomplete.
- `app/routes/sales.py::sale_customer_search`, `sale_customer_create` — existing endpoints for the picker and quick-create; D-01's radio restructuring wraps these, doesn't replace them.
- `app/static/price-cue.js` — direct structural precedent for the new live-total script (D-08).
- `app/templates/partials/customer_picker.html` — existing picker-row rendering with match highlighting, reusable inside the "Существующий" radio block.

### Established Patterns
- Server-rendered Jinja2 + HTMX 2.0.10 (vendored, offline). No SPA, no build step.
- Desktop and mobile are separate route/template trees (`app/routes/mobile_*.py`, `app/templates/mobile_pages/`, `app/templates/mobile_partials/`) — D-04's mobile customer selector follows this established separation, not a shared template.
- Money as integer cents; client-side money math is advisory-only, server is authoritative (Phase 18 precedent, reused by D-08/D-09).
- `hx-on::before-swap` / `hx-on::oob-before-swap` guards protect in-flight operator typing from being clobbered by concurrent lookup responses — any new radio-switch HTMX interaction (D-01) must not reintroduce a typing-clobber regression that D-03 explicitly rules out.

### Integration Points
- `app/routes/sales.py` — new endpoint(s) for the radio-driven mode switch (D-01), extended `sale_create` to read whichever mode was active on submit.
- `app/routes/mobile_sales.py` — extended per D-04 to add the same 3-way selector to the wizard flow; `register_sale`'s existing `customer_id` param becomes populated instead of always `""`.
- `app/templates/partials/sale_customer.html` — restructured into 3 radio-driven sub-blocks per D-01/D-07.
- `app/templates/partials/recent_sales.html` — new customer column (D-06), needs a join to `Customer` where `customer_id` is not null.
- `app/static/` — new `sale-total.js` (or similar) for D-08, wired into `sale_form.html` and its mobile basket equivalent (`mobile_partials/sale_basket.html`).
- `tests/test_sales.py` (and mobile sales tests, if present) — new coverage for the 3-way selector, NULL-customer submission, and total-display markup presence.

</code_context>

<specifics>
## Specific Ideas

- The operator's framing of the anonymous case: keep it exactly as simple as today (`customer_id = NULL`), just make the *choice* explicit in the UI rather than implicit ("don't search, don't fill anything = walk-in").
- The live total is meant purely as an at-a-glance running check while filling the basket — same "advisory, not authoritative" spirit as Phase 18's colour cue, reusing the same JS architecture (`price-cue.js`) rather than inventing a new mechanism.
- Mobile parity for the customer selector was a genuine scope surprise caught during discussion — REQUIREMENTS.md's SALE-03..07 wording doesn't say "desktop and mobile" the way PROD-05 did, but the operator wants full parity, not a mobile gap.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope (with one confirmed scope *expansion*, not creep: mobile customer-selector parity, D-04, explicitly confirmed by the operator as in-scope for this phase rather than deferred).

</deferred>

---

*Phase: 22-Sales Page Rebuild*
*Context gathered: 2026-07-17*
