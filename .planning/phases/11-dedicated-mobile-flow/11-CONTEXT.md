# Phase 11: Dedicated Mobile Flow - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning

<domain>
## Phase Boundary

A dedicated, single-purpose mobile screen set — not a CSS reflow of the existing desktop templates — covering the complete final v1.1 operation set: search stock, receipt, sale, write-off/return/correction, history browsing, warehouse transfer, and the expiring-batches report. The existing desktop pages (`app/templates/pages/*.html`, `app/templates/base.html`, `app/static/style.css`) stay visually and functionally unchanged at desktop widths. This phase is purely additive.

</domain>

<decisions>
## Implementation Decisions

### Entry point / routing
- **D-01:** Mobile flow lives under a dedicated URL namespace (`/m/...`), separate routes from the desktop pages.
- **D-02:** On first landing from a phone-width viewport, the operator is auto-redirected into `/m/...`. Desktop viewports are routed to the existing desktop pages unchanged.

### Mobile navigation
- **D-03:** `/m/` is a home screen with large operation tiles (search, receipt, sale, write-off/return/correction, history, transfer, expiry report) — no persistent bottom tab bar or hamburger menu.
- **D-04:** Each operation screen provides a "Back" control that returns to the mobile home screen (`/m/`).

### Operation step structure
- **D-05:** Sale, write-off, return, and correction flows are step-by-step wizards — one screen per step (find product → pick batch, when the product has more than one → enter quantity/price → confirm) — not a single scrollable form. One action per screen, thumb-operable.
- **D-06:** Same min-price/oversell warn-but-allow guardrails as desktop apply at the relevant wizard step.

### Batch-selection step
- **D-07:** Mobile batch picker shows one large full-width tappable card per batch, with price, expiry date, remaining quantity, and comment all visible at once (no truncation, no expand-to-see-more). Tapping the card selects the batch.

### Claude's Discretion
- Exact tile layout/grid on the `/m/` home screen (icons, ordering, grouping).
- History browsing UI on mobile (filter set may be simplified vs. desktop `history.html`; scope not specifically discussed, no objection raised to reducing filters for a narrow screen).
- Transfer and expiry-report mobile screen layouts (not specifically discussed — build as simplified, single-purpose mobile screens per phase goal, consistent with D-05/D-07 patterns for wizards and batch display).
- Viewport-width breakpoint used to decide "phone-width" for the auto-redirect.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 11: Dedicated Mobile Flow" — goal, success criteria, depends-on
- `.planning/REQUIREMENTS.md` §UI-01 — requirement text and revision note explaining why Phase 11 exists and is sequenced last

### Existing desktop flows this phase must cover (read for behavior parity, not template reuse)
- `app/templates/pages/receipt_form.html` — desktop receipt flow
- `app/templates/pages/sale_form.html` — desktop sale flow
- `app/templates/pages/writeoff_form.html` — desktop write-off flow
- `app/templates/pages/correction_form.html` — desktop correction flow
- `app/templates/pages/transfer_form.html` — desktop transfer flow (Phase 10)
- `app/templates/pages/reports_expiry.html` — desktop expiring-batches report (Phase 10)
- `app/templates/pages/history.html` — desktop history browsing
- `app/templates/partials/batch_picker.html` — desktop batch-selection UI (fields to carry into the mobile card: price, expiry, remaining quantity, comment)
- `app/templates/base.html` — shared layout/nav; must remain unchanged for desktop widths

No external specs beyond ROADMAP.md/REQUIREMENTS.md — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/static/style.css` — single shared stylesheet (Pico.css-based per project stack); mobile screens can extend it rather than introducing a new CSS framework.
- `app/static/htmx.min.js` — vendored htmx 2.0.10, already used for all partial-swap interactions; mobile wizard steps can reuse the same htmx patterns (e.g. `batch_picker.html`'s swap approach) for step-to-step navigation.
- Backend routes/services for receipt, sale, write-off, correction, transfer, and expiry-report logic already exist (Phases 3-10) — mobile screens are new templates/routes calling into the same underlying services, not new business logic.

### Established Patterns
- `app/templates/base.html` renders a single shared `<nav>` for all desktop pages; mobile needs its own base/layout (no 12-link horizontal nav) rather than reusing `base.html` as-is.
- Guardrails (min-price floor, oversell warn-but-allow) are enforced today in the desktop sale/write-off/correction routes — mobile wizard steps must call the same guardrail logic, not reimplement it.

### Integration Points
- New `/m/...` routes sit alongside existing desktop routes in the FastAPI app, sharing the same SQLAlchemy models/services.
- Viewport-based redirect logic is the one genuinely new piece of routing behavior this phase introduces (desktop routing is unaffected).

</code_context>

<specifics>
## Specific Ideas

- Mobile batch cards must show every field the desktop batch picker shows (price, expiry, remaining quantity, comment) — nothing hidden behind a tap or scroll, since the whole point of the simplified mobile picker is showing the full picture on one card.
- Wizard steps should be "one action per screen" — explicitly contrasted against a single long scrollable form, because that would just be the CSS-reflow approach the phase goal explicitly rejects.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 11-Dedicated Mobile Flow*
*Context gathered: 2026-07-12*
