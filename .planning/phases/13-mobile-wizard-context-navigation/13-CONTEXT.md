# Phase 13: Mobile Wizard Context & Navigation - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Across the 5 mobile wizards (sale, receipt, write-off, correction, transfer), the operator always sees what they're working on (product code, name, warehouse) as visible on-screen text, can always navigate back reliably via a consistent explicit pattern, gets a step indicator on the sale basket/review screen matching the rest of that wizard, and can jump straight into the sale or receipt wizard from the mobile product-detail search screen. No new capabilities — this closes context/navigation gaps in wizards already shipped in Phase 11, further exposed by Phase 12's audit (D-07/D-12/D-13/D-14 in `12-CONTEXT.md` explicitly deferred this work here).

</domain>

<decisions>
## Implementation Decisions

### Visible code/name/warehouse (UI-02)
- **D-01:** Use the exact format already shipped in `sale_step_batch.html`/`transfers_step_dest.html`: one line `**{{ code }}** — {{ name }}` (bold code, em dash, name), shown as plain text (not hidden-input-only) on every intermediate step of all 5 wizards.
- **D-02:** Add a `Склад: {{ warehouse_name }}` line once the warehouse/batch is known (i.e. once a batch has been picked, since batch determines warehouse in this app). Before that point in a wizard's flow, omit the warehouse line entirely — do not render a placeholder like "Склад: —".
- **D-03:** Apply this to every step currently missing it: all 3 correction steps (`corrections_step_batch.html`, `corrections_step_mode.html`, `corrections_step_value.html` — currently hidden-input-only), write-off qty/reason steps (`writeoff_step_qty.html`, `writeoff_step_reason.html` — currently hidden-input-only; `writeoff_step_batch.html` already has code+name partially, verify/align to D-01's exact format).

### Write-off & correction "Назад" retrofit (UI-03)
- **D-04:** Write-off wizard architecture today is NOT the fragment-swap-in-persistent-shell pattern used by sale/receipts/transfers — each step is its own full-page `{% extends "mobile_base.html" %}` template returned from a plain `<form method="post" action="...">` submit (full browser navigation, no htmx on the form itself). This is why "Назад" only works via `history.back()` (3 occurrences: `writeoff_step_batch.html`, `writeoff_step_qty.html`, `writeoff_step_reason.html`). Fixing UI-03 for write-off means migrating it to the receipts pattern: a persistent shell page (`mobile_pages/writeoff.html`, mirroring `mobile_pages/receipts.html`) with a `#wizard-step` div, steps as `hx-post` fragments (not full-page templates), and "Назад" buttons doing `hx-post` to the previous step's endpoint with `hx-include="closest form"` to carry all currently-filled fields back — exactly as `receipts_step_details.html`/`receipts_step_confirm.html` already do. This is more than a one-line onclick swap; it's a structural change to `app/routes/mobile_writeoff.py` and the write-off templates.
- **D-05:** Corrections wizard already uses `hx-post`-free simple links for "Назад" (`<a class="mobile-back" href="/m/corrections">`) on all 3 steps — but every one of them jumps to the wizard's start, not the immediately-previous step, silently discarding whatever the operator already entered (e.g. batch pick) on back-navigation. Since write-off is already being migrated to the receipts step-back pattern in this phase, apply the same fix to corrections: each step's "Назад" should `hx-post` back to the previous step's endpoint with `hx-include="closest form"`, preserving state, mirroring receipts/sale/transfers exactly. Scope: corrections' 3 steps only, same technique as D-04, no new capability.
- **D-06:** Sale, receipts, and transfers wizards' existing back-navigation is already correct (per-step, state-preserving) — no changes needed there beyond D-01/D-02's visible-text additions.

### Sale basket step indicator (UI-04)
- **D-07:** `sale_basket.html` gets a `<p class="mobile-step-indicator">Корзина</p>` line (same CSS class as the numbered steps, but text reads "Корзина" instead of "Шаг X из Y") — the basket is a variable-length review screen, not a fixed step number, so no attempt to count it as e.g. "Шаг 3 из 3".

### Search → wizard quick actions (UI-05)
- **D-08:** Tapping "Продать"/"Принять" on `search_product_detail.html` navigates to the wizard's normal step 1 (`/m/sales` or `/m/receipts`) with the product code pre-filled in the code input — the operator sees the same step 1 they'd see on a normal wizard entry, just with the code already typed. No new "resume mid-wizard" entry point or step-skip logic needed in any wizard's routes.
- **D-09:** The "Продать" button is always shown, regardless of whether the product has any stock — the app already allows selling into negative stock with an oversell warning (existing pattern), so a zero-stock product must still be reachable via the quick action; hiding it would be inconsistent with that existing rule.

### Claude's Discretion
- Exact markup/CSS for the new visible code/name/warehouse lines (D-01/D-02) beyond matching the existing `sale_step_batch.html`/`transfers_step_dest.html` shape.
- Exact shape of the write-off shell-page migration (D-04) — route/template split, as long as the resulting "Назад" behavior matches receipts' `hx-post` + `hx-include="closest form"` pattern.
- Exact query-param/form-field mechanism for pre-filling the code on quick-action navigation (D-08) — e.g. `?code=...` on the GET, consumed the same way the code field is already populated on a normal wizard visit.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — UI-02, UI-03, UI-04, UI-05 (full requirement text)
- `.planning/ROADMAP.md` — Phase 13 section (goal, success criteria, dependency on Phase 11)
- `.planning/phases/12-code-name-autofill/12-CONTEXT.md` — D-06/D-07/D-12/D-13/D-14: explicitly deferred this phase's scope from Phase 12, including exact file/line pointers to the gaps Phase 12 left behind

### Reference pattern to mirror (already correct — copy, don't redesign)
- `app/templates/mobile_partials/sale_step_batch.html` — visible code/name line format (D-01) + correct per-step `hx-post` "Назад" (D-06 reference)
- `app/templates/mobile_partials/transfers_step_dest.html` — visible code/name line format (D-01), already fixed by Phase 12 D-14
- `app/templates/mobile_partials/receipts_step_details.html`, `receipts_step_confirm.html` — the exact `hx-post` + `hx-include="closest form"` back-navigation pattern to replicate for write-off (D-04) and corrections (D-05)
- `app/templates/mobile_pages/receipts.html`, `app/routes/mobile_receipts.py` — persistent-shell + `#wizard-step` fragment-swap architecture that write-off must migrate to (D-04)

### Files needing the fixes
- `app/templates/mobile_partials/corrections_step_batch.html`, `corrections_step_mode.html`, `corrections_step_value.html` — add visible code/name/warehouse (D-03), fix "Назад" to per-step hx-post (D-05)
- `app/templates/mobile_partials/writeoff_step_batch.html`, `writeoff_step_qty.html`, `writeoff_step_reason.html` — add visible code/name/warehouse (D-03), migrate off `history.back()` (D-04)
- `app/templates/mobile_pages/writeoff.html`, `app/routes/mobile_writeoff.py` — shell/route migration for D-04
- `app/templates/mobile_partials/sale_basket.html` — add step-indicator line (D-07)
- `app/templates/mobile_partials/search_product_detail.html`, `app/routes/mobile_search.py` — add "Продать"/"Принять" quick-action buttons (D-08/D-09)
- `app/routes/mobile_sales.py` (`/m/sales`), `app/routes/mobile_receipts.py` (`/m/receipts`) — GET entry points must accept a pre-fill code param (D-08)

### Project-level context
- `.planning/PROJECT.md` — Key Decisions table; v1.1 decision "mobile flow reuses existing services unchanged"; existing oversell-allowed-with-warning pattern (referenced by D-09)

No external ADRs/specs beyond the above — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `batch_card_picker.html` — shared batch-selection partial already used across sale/write-off/correction/transfer; already shows warehouse per batch card, useful reference for D-02's warehouse-line wording.
- `mobile-step-indicator` CSS class — already styled and used consistently across sale/receipts/write-off numbered steps; reuse unchanged for D-07's "Корзина" text.

### Established Patterns
- Two distinct wizard architectures currently coexist: (1) persistent-shell + `hx-post` fragment-swap (sale, receipts, transfers, corrections' rendering — though corrections' back-links don't yet follow the pattern) vs (2) full-page-per-step with plain form POST (write-off only). D-04 unifies write-off onto pattern (1).
- `hx-include="closest form"` is the established mechanism for carrying all wizard state backward/forward without re-deriving state server-side from scratch each step.

### Integration Points
- `search_product_detail.html` is reached via a plain top-level link (not HTMX) from `/m/search`, per its own header comment — quick-action buttons (D-08) should follow the same plain-navigation convention (a normal `<a href="...">`), not an HTMX partial swap, since this is a page-to-page jump into a different wizard entirely.

</code_context>

<specifics>
## Specific Ideas

No specific UI mockups given — user confirmed the researched/recommended option for all five gray areas discussed (D-01/D-02 format, D-04 write-off migration approach, D-05 extending the same fix to corrections, D-07 "Корзина" label, D-08/D-09 quick-action landing step + always-visible "Продать").

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Full mobile CRUD parity (warehouses/products/customers/dictionary/reports) remains out of scope per `.planning/REQUIREMENTS.md` (UI-V2-02, deferred to v2.0).

</deferred>

---

*Phase: 13-mobile-wizard-context-navigation*
*Context gathered: 2026-07-13*
