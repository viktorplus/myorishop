# Phase 13: Mobile Wizard Context & Navigation - Research

**Researched:** 2026-07-13
**Domain:** Server-rendered HTMX wizard navigation & state carry-forward (FastAPI + Jinja2), fix-and-consistency over existing code
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use the exact format already shipped in `sale_step_batch.html`/`transfers_step_dest.html`: one line `**{{ code }}** — {{ name }}` (bold code, em dash, name), shown as plain text (not hidden-input-only) on every intermediate step of all 5 wizards.
- **D-02:** Add a `Склад: {{ warehouse_name }}` line once the warehouse/batch is known (i.e. once a batch has been picked, since batch determines warehouse in this app). Before that point in a wizard's flow, omit the warehouse line entirely — do not render a placeholder like "Склад: —".
- **D-03:** Apply this to every step currently missing it: all 3 correction steps (`corrections_step_batch.html`, `corrections_step_mode.html`, `corrections_step_value.html` — currently hidden-input-only), write-off qty/reason steps (`writeoff_step_qty.html`, `writeoff_step_reason.html` — currently hidden-input-only; `writeoff_step_batch.html` already has code+name partially, verify/align to D-01's exact format).
- **D-04:** Write-off wizard architecture today is NOT the fragment-swap-in-persistent-shell pattern used by sale/receipts/transfers — each step is its own full-page `{% extends "mobile_base.html" %}` template returned from a plain `<form method="post" action="...">` submit (full browser navigation, no htmx on the form itself). This is why "Назад" only works via `history.back()` (3 occurrences: `writeoff_step_batch.html`, `writeoff_step_qty.html`, `writeoff_step_reason.html`). Fixing UI-03 for write-off means migrating it to the receipts pattern: a persistent shell page (`mobile_pages/writeoff.html`, mirroring `mobile_pages/receipts.html`) with a `#wizard-step` div, steps as `hx-post` fragments (not full-page templates), and "Назад" buttons doing `hx-post` to the previous step's endpoint with `hx-include="closest form"` to carry all currently-filled fields back — exactly as `receipts_step_details.html`/`receipts_step_confirm.html` already do. This is more than a one-line onclick swap; it's a structural change to `app/routes/mobile_writeoff.py` and the write-off templates.
- **D-05:** Corrections wizard already uses `hx-post`-free simple links for "Назад" (`<a class="mobile-back" href="/m/corrections">`) on all 3 steps — but every one of them jumps to the wizard's start, not the immediately-previous step, silently discarding whatever the operator already entered (e.g. batch pick) on back-navigation. Since write-off is already being migrated to the receipts step-back pattern in this phase, apply the same fix to corrections: each step's "Назад" should `hx-post` back to the previous step's endpoint with `hx-include="closest form"`, preserving state, mirroring receipts/sale/transfers exactly. Scope: corrections' 3 steps only, same technique as D-04, no new capability.
- **D-06:** Sale, receipts, and transfers wizards' existing back-navigation is already correct (per-step, state-preserving) — no changes needed there beyond D-01/D-02's visible-text additions.
- **D-07:** `sale_basket.html` gets a `<p class="mobile-step-indicator">Корзина</p>` line (same CSS class as the numbered steps, but text reads "Корзина" instead of "Шаг X из Y") — the basket is a variable-length review screen, not a fixed step number, so no attempt to count it as e.g. "Шаг 3 из 3".
- **D-08:** Tapping "Продать"/"Принять" on `search_product_detail.html` navigates to the wizard's normal step 1 (`/m/sales` or `/m/receipts`) with the product code pre-filled in the code input — the operator sees the same step 1 they'd see on a normal wizard entry, just with the code already typed. No new "resume mid-wizard" entry point or step-skip logic needed in any wizard's routes.
- **D-09:** The "Продать" button is always shown, regardless of whether the product has any stock — the app already allows selling into negative stock with an oversell warning (existing pattern), so a zero-stock product must still be reachable via the quick action; hiding it would be inconsistent with that existing rule.

### Claude's Discretion

- Exact markup/CSS for the new visible code/name/warehouse lines (D-01/D-02) beyond matching the existing `sale_step_batch.html`/`transfers_step_dest.html` shape.
- Exact shape of the write-off shell-page migration (D-04) — route/template split, as long as the resulting "Назад" behavior matches receipts' `hx-post` + `hx-include="closest form"` pattern.
- Exact query-param/form-field mechanism for pre-filling the code on quick-action navigation (D-08) — e.g. `?code=...` on the GET, consumed the same way the code field is already populated on a normal wizard visit.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. Full mobile CRUD parity (warehouses/products/customers/dictionary/reports) remains out of scope per `.planning/REQUIREMENTS.md` (UI-V2-02, deferred to v2.0).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-02 | Every intermediate step of the sale, receipt, write-off, correction, and transfer mobile wizards displays the product code, name, and warehouse in visible text (not just hidden inputs) | Contract A markup (`_wizard_header.html` recommendation) in Architecture Patterns/Code Examples; Pitfall 1 (write-off `name` threading gap) and Pitfall 2 (corrections has no `name` service param — display-only) directly unblock this; warehouse-name lookup helper (`_warehouse_names`, Don't Hand-Roll) supplies the `Склад:` value. |
| UI-03 | All mobile wizards use the same explicit `hx-get`/`hx-post` "Назад" navigation pattern; the write-off wizard's `history.back()` steps are fixed to match | Pattern 1 (previous-step's-own-route redraw idiom) and Pattern 2 (`HX-Request` header-check for step-1 fragments) give the exact mechanism; Pitfall 4 (write-off step-1 fragment gap) and Pitfall 5 (corrections' 3 steps all pointing at step 1) enumerate every concrete fix needed; Open Question flags the one genuinely ambiguous edge (corrections step 2's own back-nav). |
| UI-04 | The mobile sale basket/review screen shows a step indicator consistent with the rest of the sale wizard | Code Examples / Recommended Project Structure confirm `sale_basket.html`'s current markup and the exact one-line addition (`<p class="mobile-step-indicator">Корзина</p>`) per D-07 — no route change needed, template-only. |
| UI-05 | Mobile search product-detail screen offers quick "Продать" / "Принять" actions that jump directly into the sale/receipt wizard for that product | `?code=` pre-fill Code Example shows the exact route signature change needed for `mobile_sales_page`/`mobile_receipt_new`; `search_product_detail.html`'s existing plain-link convention (verified, header comment) confirms D-08's plain `<a href>` approach requires no htmx; D-09's always-show requirement is confirmed compatible with the existing oversell-allowed pattern (Security Domain / PROJECT.md Key Decisions). |
</phase_requirements>

## Summary

This phase touches zero new libraries and zero new architectural concepts — it is a consistency
fix over 5 existing mobile wizards (sale, receipts, transfers, write-off, corrections) plus one
new pair of links on the search product-detail screen. All facts in this document are
`[VERIFIED: codebase]` — obtained by reading the actual route/template files in
`app/routes/mobile_*.py` and `app/templates/mobile_partials/*.html` /
`app/templates/mobile_pages/*.html`, not from external docs. No package installation, no version
research, no external registry lookups apply to this phase — the Package Legitimacy Audit section
is omitted for that reason (see note below).

The central technical finding: **two distinct wizard architectures currently coexist**, exactly as
`13-CONTEXT.md` D-04 states — (1) a persistent-shell `<form>` wrapping a `#wizard-step` (or
wizard-specific id) div that later steps swap via `hx-post`/`hx-get` (sale, receipts, transfers,
corrections), and (2) write-off's full-page-per-step architecture with plain `<form method="post">`
submits and `onclick="history.back()"`. Migrating write-off to architecture (1) is a real
structural change (route + 3 templates + the shell page), not a template tweak.

A second, more subtle finding not spelled out in `13-CONTEXT.md`: **every wizard's own step-1↔step-2
transition is currently a plain full-page reset** (a bare `<a href="...">` link, or a full
`GET`), even in the "already correct" wizards (receipts' step 2 "Назад" is
`<a class="button secondary" href="/m/receipts">`, discarding the typed code/warehouse). Only
transitions from step 3 onward use the `hx-post` + `hx-include="closest form"` pattern cited in
`13-UI-SPEC.md` Contract B. This matters because `13-CONTEXT.md` D-05 says "each step's Назад"
(all 3 corrections steps) should mirror "receipts... exactly" — but receipts itself does NOT do
this at its own step 2. This is flagged as an Open Question below since it changes route-count and
task scope for corrections' step-2 "Назад".

**Primary recommendation:** Extract a single reusable Jinja partial for the visible
code/name/warehouse header (Contract A markup) and include it from all 8 affected step templates
rather than duplicating the 2-line snippet 8 times; migrate write-off to the receipts persistent-shell
pattern verbatim (same route/template shapes, same `hx-include="closest form"` idiom); reuse the
`HX-Request` header check already established in `app/routes/mobile_search.py` to serve step-1 as a
bare fragment when reached via `hx-get`/`hx-post` "Назад", avoiding a new full-page-vs-fragment route
split.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Visible code/name/warehouse text (UI-02) | Frontend Server (SSR, Jinja2 template) | API/Backend (route must thread `name`/`warehouse_name` into context) | Pure server-rendered text; no client JS needed. The gap is in the route context dict, not the browser. |
| "Назад" step navigation (UI-03) | Frontend Server (SSR route + htmx attributes) | Browser (htmx issues the request) | Navigation is implemented as ordinary `hx-get`/`hx-post` to existing FastAPI routes — htmx is a thin client-side dispatcher, all state lives server-side in the posted form fields. |
| Sale basket step indicator (UI-04) | Frontend Server (Jinja2 template) | — | Static text line, zero logic. |
| Search → wizard quick actions (UI-05) | Frontend Server (Jinja2 template link) + API/Backend (GET query param) | Browser (plain `<a href>` navigation, no htmx) | Per `13-CONTEXT.md` code_context: this is an explicit plain top-level link (page-to-page jump), not an htmx partial swap. The `?code=` param is consumed server-side by the wizard's existing GET handler. |

## Standard Stack

No new packages. This phase uses only what's already installed: FastAPI 0.139.x, Jinja2 3.1.x,
htmx 2.0.10 (vendored, `app/static/htmx.min.js`), SQLAlchemy 2.0.x — all `[VERIFIED: codebase]`
via `pyproject.toml` and `app/templates/mobile_base.html`'s `<script src="/static/htmx.min.js">`.

**Installation:** none required.

## Package Legitimacy Audit

**Not applicable this phase** — no external packages are installed, upgraded, or introduced. All
work is template/route edits within the existing dependency set. This section is intentionally
omitted per the protocol's trigger condition ("whenever this phase installs external packages").

## Architecture Patterns

### System Architecture Diagram

```
Operator's phone (browser)
   │
   │  taps "Продать"/"Принять" on /m/search/product/{id}
   ▼
GET /m/sales?code=XXXX  or  GET /m/receipts?code=XXXX   (plain <a href>, full navigation)
   │
   ▼
mobile_pages/sales.html or receipts.html  (full page, persistent <form>, #wizard-step div)
   │  step 1 fragment pre-filled with ?code
   │
   │  operator fills step 1, taps "Далее"  ──hx-post──▶  step 2 route ──▶ returns step-2 fragment
   │                                                         (swapped into #wizard-step)
   │
   │  operator taps "Назад" on step 2/3/4  ──hx-post/hx-get──▶  PREVIOUS step's OWN route,
   │       (posts hx-include="closest form" — i.e. re-submits ITS OWN already-carried              │
   │        hidden fields to the route that originally rendered the step being returned to)          │
   │                                                         (re-renders that step fragment,
   │                                                          state preserved, swapped back in)
   │
   ▼
Final step "Далее"/submit  ──POST──▶  register_sale()/register_receipt()/register_writeoff()/
                                        register_correction()/register_transfer()
                                        (unchanged service layer — single source of truth,
                                         same write path as desktop)
   │
   ▼
Success fragment (saved=... context) OR oversell/error fragment (zero writes, re-render same step)
```

Data flow key insight: htmx never carries client-side wizard state — every "step" is a full
server round-trip that re-derives its render context from the POSTed/GET hidden fields. This is
why "Назад" done wrong (jumping to a route that doesn't accept/echo the same fields) silently
drops data — there is no client-side undo, only "resubmit what the DOM currently holds to a
route that knows how to redraw the target step."

### Recommended Project Structure

No new files/folders needed beyond what's listed in `13-CONTEXT.md`'s "Files needing the fixes."
One structural addition is recommended (see Don't Hand-Roll below): a shared partial for the
code/name/warehouse header.

```
app/templates/mobile_partials/
├── _wizard_header.html          # NEW (recommended): Contract A markup, {% include %}'d by all 8 step templates
├── corrections_step_batch.html  # existing — add header include, fix "Назад"
├── corrections_step_mode.html   # existing — add header include, fix "Назад"
├── corrections_step_value.html  # existing — add header include, fix "Назад"
├── writeoff_step_batch.html     # existing — align header format, migrate off history.back()
├── writeoff_step_qty.html       # existing — add header include, migrate off history.back()
├── writeoff_step_reason.html    # existing — add header include, migrate off history.back()
├── sale_basket.html             # existing — add step-indicator line only
└── search_product_detail.html   # existing — add "Продать"/"Принять" links
app/templates/mobile_pages/
└── writeoff.html                 # existing — becomes a persistent shell w/ #wizard-step (mirrors receipts.html)
app/routes/
├── mobile_writeoff.py             # existing — step handlers become fragment-returning (no more {% extends %} per-step), route accepts+threads `name`
├── mobile_corrections.py          # existing — "Назад" targets fixed; possibly a new step-1-as-fragment path (see Open Questions)
├── mobile_sales.py, mobile_receipts.py  # existing — GET handlers gain optional `code: str = ""` query param
└── mobile_search.py               # existing — no server logic change; template-only addition
```

### Pattern 1: The "previous step's own route redraws it" back-navigation idiom

**What:** Every correctly-implemented "Назад" button does NOT call a dedicated "go back" endpoint.
It calls the SAME route that originally rendered the step being returned to, POSTing/GETting the
current step's own already-carried hidden fields via `hx-include="closest form"` (or, for sale,
implicit inclusion since the whole wizard lives in one `<form id="sale-wizard-form">`).

**When to use:** Any step N → step N-1 transition where step N-1 is itself reachable via a route
that accepts the fields step N already carries forward as hidden inputs.

**Example (receipts, already correct — `[VERIFIED: codebase]` `receipts_step_details.html` line 43):**
```html
<!-- Source: app/templates/mobile_partials/receipts_step_details.html -->
<button type="button" class="secondary" hx-post="/m/receipts/step/batch" hx-include="closest form">Назад</button>
<button type="submit" hx-post="/m/receipts/step/confirm" hx-include="closest form">Далее</button>
```
The `/m/receipts/step/batch` route (`app/routes/mobile_receipts.py::mobile_receipt_step_batch`)
is the SAME route step 1 posts to move forward — it is dual-purpose (forward-render AND
backward-redraw) simply because it always re-derives its output from whatever fields it receives,
never from server-side session state.

**Example (write-off migration target — apply this exact shape):**
```html
<!-- Target for writeoff_step_qty.html "Назад", mirroring receipts_step_details.html -->
<button type="button" class="secondary" hx-post="/m/writeoff/step/batch" hx-include="closest form">Назад</button>
```
This requires `mobile_writeoff_step_batch` to stop returning a full-page `{% extends %}` template
and instead return a bare fragment (mirrors `writeoff_batch_wrap.html`'s existing bare-fragment
shape) — the route ALREADY exists and already re-derives its render purely from `code` +
freshly-requeried batches, so no service-layer change is needed, only the template's
`{% extends %}` needs removing and the enclosing shell/`#wizard-step` needs adding to
`mobile_pages/writeoff.html`.

### Pattern 2: `HX-Request` header check to serve one route as either full page or bare fragment

**What:** A single GET route detects whether the incoming request came from htmx
(`request.headers.get("HX-Request")` truthy) and returns either the full
`{% extends "mobile_base.html" %}` page or a bare fragment of just the inner content — same
context, two template choices.

**When to use:** Whenever a step-1 entry point needs to serve BOTH a cold-start full-page load
(bookmark, first visit) AND a "Назад"-triggered fragment swap into an existing shell — this is
exactly the gap corrections and write-off have today (their step-1 GET handlers only know how to
render the full page).

**Example — already shipped and working, `[VERIFIED: codebase]` `app/routes/mobile_search.py`:**
```python
# Source: app/routes/mobile_search.py::mobile_search
@router.get("/m/search")
def mobile_search(request: Request, q: str = "", session: Session = Depends(get_session)):
    context = search_view(session, q)
    # CR-01-precedent (history.py): only a genuine HX-Request gets the
    # rows-only fragment; a bookmarked/reloaded ?q=... URL still gets chrome.
    if bool(request.headers.get("HX-Request")):
        return templates.TemplateResponse(request, "mobile_partials/search_results.html", context)
    return templates.TemplateResponse(request, "mobile_pages/search.html", context)
```
**Recommended reuse:** Apply the identical `if bool(request.headers.get("HX-Request"))` branch to
`mobile_correction_start` (`GET /m/corrections`) and `mobile_writeoff_start` (`GET /m/writeoff`) so
a "Назад" button on step 2 can `hx-get="/m/corrections"` (or `/m/writeoff`) with the current `code`
value and receive back JUST the `#corrections-step-wrap` (or step-1 write-off) fragment, instead of
requiring a brand-new route. This is the cleanest way to resolve the Open Question below without
adding net-new endpoints.

### Anti-Patterns to Avoid

- **`onclick="history.back()"`:** Breaks whenever the operator did not arrive at the current step
  via browser history (e.g. deep link, refresh, or — after this phase's own `?code=` quick-action
  links — a fresh page load). It also cannot re-populate server-derived state (e.g. freshly
  requeried batch quantities), unlike a real GET/POST re-render. This is precisely why UI-03 exists.
- **Re-deriving "the previous step" from scratch with a brand-new dedicated back-route:** Every
  wizard in this codebase avoids this — always reuse the SAME route that forward-navigation already
  posts to. Introducing parallel "step N minus 1" endpoints duplicates logic that already exists
  and risks the two copies drifting (batch re-validation, name resolution, etc.).
- **Hand-rolling the code/name/warehouse header markup per-template:** See Don't Hand-Roll below —
  8 templates need the identical 2-line block; copy-pasting it 8 times invites drift on the next
  format change (already seen once: `writeoff_step_batch.html` "already shows code+name partially"
  per D-03, meaning it drifted from the canonical format even before this phase started).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Visible code/name/warehouse header repeated across 8 templates | A copy-pasted `<p><strong>{{ code }}</strong>...` block in each of the 8 files | One `{% include "mobile_partials/_wizard_header.html" %}` (new, tiny partial) | `batch_card_picker.html` already proves this codebase's convention of extracting shared multi-consumer fragments (`13-CONTEXT.md` code_context explicitly calls this pattern "Reusable Assets"); `writeoff_step_batch.html` already drifted from the canonical format once — a single include point makes future format changes a one-file edit. |
| Step-1-as-fragment for "Назад" targets | A brand-new `POST /m/corrections/step/product-back` / `POST /m/writeoff/step/product-back` endpoint | The existing `HX-Request` header check pattern already shipped in `mobile_search.py` | Avoids a parallel endpoint that must be kept in sync with the real step-1 GET handler's logic (lookup_prefill call, error handling) — one route, two response shapes, exactly like search already does. |
| Warehouse name lookup from a `batch_id`/`warehouse_id` | A raw SQL query or new service function | `app.services.batches.active_warehouses(session)` → build an `{id: name}` dict, exactly as `app/routes/mobile_transfers.py::_warehouse_names` already does | This helper function already exists and is already proven correct (used by transfers today); `Batch` has no ORM `relationship` to `Warehouse` (verified in `app/models.py`), so a raw `session.get(Warehouse, batch.warehouse_id).name` per-row is the only alternative and is less efficient than one dict built from `active_warehouses()`. |

**Key insight:** This phase's biggest hand-roll risk is template duplication, not business logic
duplication — the service layer (`register_writeoff`, `register_correction`, etc.) is explicitly
frozen (`PROJECT.md` Key Decision: "Mobile flow reuses existing services unchanged"). All the real
work is template/route wiring, which is exactly where duplication silently drifts (as already
happened once with `writeoff_step_batch.html`).

## Common Pitfalls

### Pitfall 1: `register_writeoff`'s `name` parameter is already there — the route just never passes it after step 1

**What goes wrong:** Assuming Contract A requires a service-layer change to support carrying
`name`. It does not.

**Why it happens:** `app/services/writeoffs.py::register_writeoff` already accepts a `name: str`
keyword argument (verified: `def register_writeoff(session, *, code, name, qty_raw, ...)`), and
`mobile_writeoff.py::mobile_writeoff_submit` already calls it with `name=""` hardcoded (line 174).
The gap is ENTIRELY in the route layer: `mobile_writeoff_step_qty` (Form params: `code`, `batch_id`
only) and `mobile_writeoff_step_reason` (Form params: `code`, `batch_id`, `qty` only) never declare
or thread a `name: str = Form("")` parameter, so it is lost after step 1's `code`→name lookup.

**How to avoid:** Add `name: str = Form("")` to `mobile_writeoff_step_qty` and
`mobile_writeoff_step_reason`'s signatures, add `<input type="hidden" name="name" value="{{ name }}">`
to `writeoff_step_batch.html`/`writeoff_step_qty.html` (carry-forward), and pass `name=name` into
the context dicts so the new header partial can render it. The final `register_writeoff` call in
`mobile_writeoff_submit` can then also stop hardcoding `name=""` and pass the real carried value
(cosmetic improvement, not required by any of UI-02/03's literal success criteria, but consistent
with sale/receipts/transfers which already thread `name` all the way to their final POST).

**Warning signs:** If a template shows `{{ name }}` as blank on step 3/4 even though step 1 found
a match, the route function's `Form(...)` parameter list is missing `name`.

### Pitfall 2: `register_correction` does NOT accept a `name` parameter at all

**What goes wrong:** Assuming corrections' name-threading mirrors write-off's (add a Form param,
pass it to the service call).

**Why it happens:** `app/services/corrections.py::register_correction`'s signature is
`(session, *, code, mode, value_raw, note, batch_id, confirm)` — no `name` parameter exists, and
none is needed since the service already re-resolves the product from `code` server-side.

**How to avoid:** For corrections, `name` is PURELY a display carry-forward (hidden field →
template header), never passed to `register_correction`. Do not add a `name` argument to the
service call — just thread the hidden field through `corrections_step_batch.html` →
`corrections_step_mode.html` → `corrections_step_value.html` (and the corresponding route Form
params), exactly the way `batch_qty` is already carried as a display-only opaque value today.

**Warning signs:** A `TypeError: register_correction() got an unexpected keyword argument 'name'`
at test time.

### Pitfall 3: Warehouse line must NEVER render before a batch is picked — a naive "show warehouse whenever known" implementation over-renders it on step 1

**What goes wrong:** Corrections/write-off step 1 (Товар) has no batch yet, so there is no
`warehouse_id` to resolve. If the new header partial is naively included on step 1 too (before a
`batch_id` exists), it must gracefully omit the warehouse line — but if the template author
copies the include onto step 1 "for consistency," they must ensure `warehouse_name` is simply
absent/`None` in that step's context (not an empty string), so the `{% if warehouse_name %}` guard
in Contract A correctly omits the line.

**How to avoid:** Per `13-CONTEXT.md` D-02 and D-03, the header partial is only added to the
INTERMEDIATE steps already listed (batch/mode/value for corrections; qty/reason for write-off) —
step 1 (Товар) is explicitly NOT in scope for D-03's file list, so this only matters if the header
partial is also reused on step 1 pages for the code/name half (which IS shown on write-off's step 1
already via `name-fill` div, just not in Contract A's exact format). Recommend keeping step 1's
existing name-echo (`writeoff_name_fill.html`, `corrections_name_echo.html`) untouched and unrelated
to the new `_wizard_header.html` partial, to avoid scope creep into files D-03 doesn't list.

**Warning signs:** `Склад: —` or `Склад: None` literally rendered on a step where no batch exists yet.

### Pitfall 4: `writeoff_step_batch.html`'s "Назад" (step 2 → step 1) has no established fragment target to swap into if migrated naively

**What goes wrong:** Assuming migrating write-off's step 2 "Назад" to `hx-post`/`hx-get` is a
simple copy of the Contract B snippet. Unlike receipts' step 3→2 and step 4→3 (which target routes
that ALREADY return bare fragments), write-off's own step 1 (`GET /m/writeoff` →
`mobile_writeoff_start`) currently ALWAYS returns the FULL `{% extends "mobile_base.html") %}`
page — there is no existing bare-fragment response for "step 1 content only."

**How to avoid:** Apply Pattern 2 (the `HX-Request` header check) to `mobile_writeoff_start`,
mirroring `mobile_search.py` exactly — extract the step-1 form body (code input + name-fill div)
into its own partial (or reuse the existing `{% block content %}` body conditionally), and return
that bare fragment when `HX-Request` is present, full page otherwise.

**Warning signs:** An `hx-swap="outerHTML"` (or `innerHTML`) into `#wizard-step` that lands a full
`<html><head>...` document inside the DOM — the exact CR-01 bug class already fixed once for
`corrections_not_found.html` (its header comment explicitly documents this failure mode).

### Pitfall 5: Corrections' step-2/3/4 "Назад" links point at `/m/corrections` (step 1) for ALL THREE steps, not at each one's immediate predecessor

**What goes wrong:** A shallow reading of "fix corrections' Назад" might treat all 3 as the SAME
bug (every one currently points at step 1) and fix them uniformly to `history.back()`-equivalent
"one step up" navigation without checking each step's actual immediate predecessor.

**Why it happens (confirmed via direct file read):**
- `corrections_step_batch.html` (step 2 "Партия") → `<a class="mobile-back" href="/m/corrections">` — this ACTUALLY IS the correct immediate predecessor (step 1), just implemented as a plain link instead of `hx-post`.
- `corrections_step_mode.html` (step 3 "Режим") → SAME `href="/m/corrections"` — this SKIPS step 2 entirely; the correct predecessor is `/m/corrections/step/batch`.
- `corrections_step_value.html` (step 4 "Значение") → SAME `href="/m/corrections"` — this SKIPS steps 2 AND 3; the correct predecessor is `/m/corrections/step/mode`.

**How to avoid:** Fix each step's target to its OWN immediate predecessor's route
(`/m/corrections/step/batch` for step 3's "Назад", `/m/corrections/step/mode` for step 4's
"Назад"), not a blanket "point everything one step back in an abstract counter" — the predecessor
ROUTE differs per step and must be looked up per-file, matching each step's actual forward-post target.

**Warning signs:** A regression test that fills mode+value then taps "Назад" from step 4 and
expects to land on step 3 (mode) with the picked mode still selected — if it lands on step 1
instead, this pitfall was not fixed.

## Open Question: Does corrections step 2's "Назад" (→ step 1) also need the `hx-post`+fragment fix, or is the plain-link pattern acceptable there (matching receipts' own step-2 precedent)?

**What we know:**
- `13-CONTEXT.md` D-05 literally reads: "each step's 'Назад' should `hx-post` back to the previous
  step's endpoint with `hx-include='closest form'`, preserving state, mirroring receipts/sale/transfers
  exactly" — applied to "corrections' 3 steps."
- But receipts' OWN step 2 "Назад" (`receipts_step_batch.html` line 53) is
  `<a class="button secondary" href="/m/receipts">Назад</a>` — a PLAIN link, NOT `hx-post` +
  `hx-include`. It discards the typed code/warehouse/prices on tap. This is the exact same shape
  corrections' step 2 currently has.
- `13-CONTEXT.md` D-06 says receipts' existing back-navigation "is already correct... no changes
  needed there" — meaning this plain-link step-2 behavior in receipts is implicitly accepted as
  correct/unchanged, even though it does NOT match the `hx-include="closest form"` pattern cited
  for receipts' OWN step 3/4.

**What's unclear:** Whether "mirroring receipts... exactly" (D-05) means corrections' step 2 should
ALSO stay a plain link (true parity with what receipts ACTUALLY does at its own step 2), or whether
ALL of corrections' 3 steps — including step 2 — must uniformly use the fragment pattern (true parity
with D-05's literal "each step" wording, which would make corrections MORE consistent than receipts
itself post-phase).

**Recommendation:** Fix step 3 ("Режим"→"Назад" to batch) and step 4 ("Значение"→"Назад" to mode)
unconditionally — these are unambiguous bugs (see Pitfall 5) matching `hx-post`/`hx-include`
verbatim, since both target routes already return bare fragments today. For step 2's "Назад" (→ step
1), recommend applying Pattern 2 (`HX-Request` header check on `GET /m/corrections`) for full
consistency with D-05's literal wording — this is a small, low-risk addition (mirrors an
already-shipped pattern) and closes the gap rather than leaving one wizard's first-step transition
inconsistent with its own other two transitions. If the planner/executor judges this out of the
locked-decision scope, the fallback (leaving step 2's plain link as-is, matching receipts' own
precedent) is also defensible — but should be an explicit, logged choice, not an oversight.
**This should be confirmed with the user or explicitly decided by the planner before execution**,
since it changes whether `mobile_correction_start` needs a route change at all.

## Code Examples

### Reusable header partial (recommended new file)

```html
{# Source: new file app/templates/mobile_partials/_wizard_header.html
   Consolidates Contract A (13-UI-SPEC.md) into one include point.
   Context: code (str, required), name (str|None), warehouse_name (str|None) #}
<p><strong>{{ code }}</strong>{% if name %} — {{ name }}{% endif %}</p>
{% if warehouse_name %}<p>Склад: {{ warehouse_name }}</p>{% endif %}
```
Included from each of the 5 affected step templates as:
```html
{% include "mobile_partials/_wizard_header.html" %}
```

### Building the warehouse-id → name map (mirrors existing transfers helper)

```python
# Source: app/routes/mobile_transfers.py::_warehouse_names (existing, verified)
def _warehouse_names(session: Session) -> dict[str, str]:
    """id -> name map so the batch-step card can show its own «Склад:» line."""
    return {w.id: w.name for w in active_warehouses(session)}
```
Reuse this exact helper (or an equivalent one-liner) in `mobile_writeoff.py` and
`mobile_corrections.py` to resolve `warehouse_name` from a picked `Batch.warehouse_id` for
Contract A's warehouse line.

### `?code=` pre-fill on wizard entry (new — needed for D-08/UI-05)

```python
# Target shape for app/routes/mobile_sales.py::mobile_sales_page
@router.get("/m/sales")
def mobile_sales_page(request: Request, code: str = ""):
    context = {
        "code": code,
        "error": None,
        "saved": None,
        **_acc_context([], [], [], []),
    }
    return templates.TemplateResponse(request, "mobile_pages/sales.html", context)
```
Same shape for `mobile_receipts.py::mobile_receipt_new` — add `code: str = ""` and pass it as
`"code": code` instead of the current hardcoded `"code": ""`. No lookup/prefill call is required
here — the existing debounced `hx-post`/`hx-trigger="input changed delay:300ms"` on the code field
already runs the name lookup once the field has a value, whether typed by the operator or
pre-filled by `value="{{ code }}"`.

## State of the Art

Not applicable — no external ecosystem shifted since Phase 11 shipped these wizards; htmx 2.0.10 is
still the vendored/current stable line (per `CLAUDE.md`'s own dated verification, 2026-07-08).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Applying the `HX-Request` header-check pattern (Pattern 2) to `mobile_writeoff_start`/`mobile_correction_start` is the best resolution for step-1-as-fragment, rather than a dedicated new route | Architecture Patterns, Pitfall 4, Open Question | If the planner prefers a dedicated route instead, the shape changes slightly (extra endpoint) but the underlying data/logic is unaffected — low risk either way, purely a design preference |
| A2 | Corrections step 2's "Назад" needs the same fix as steps 3/4 (per literal D-05 wording) rather than staying a plain link (matching receipts' own step-2 precedent) | Open Question | If wrong, an unnecessary route change (`GET /m/corrections` gains an `HX-Request` branch) is added; if the planner instead scopes it out, the recommendation still leaves the phase's success criteria (UI-03) satisfied since D-05's stated end-state is ambiguous only on this one edge, not on the phase's overall test surface |

**If this table is empty:** N/A — see above, both entries are design-recommendation risk, not
factual-claim risk; every specific code/route/template fact cited in this document was verified by
directly reading the file (tagged `[VERIFIED: codebase]` throughout).

## Environment Availability

Skipped — this phase has no external tool/service dependencies beyond the already-running FastAPI
dev server and the project's existing SQLite database; nothing new to probe.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.x (`[VERIFIED: codebase]` `pyproject.toml` `[dependency-groups] dev`) |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| Quick run command | `uv run pytest tests/test_mobile_writeoff.py tests/test_mobile_corrections.py tests/test_mobile_sales.py tests/test_mobile_receipts.py tests/test_mobile_transfers.py tests/test_mobile_search.py -x` |
| Full suite command | `uv run pytest` |

Existing test files already cover each wizard's happy path via `mobile_client_factory` (verified in
`tests/test_mobile_writeoff.py`) but currently assert only text presence (e.g. `"Далее" in
response.text`), not `hx-post`/`hx-include` attribute values or absence of `history.back()` — new
assertions of that shape are needed for UI-03's regression coverage.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-02 | Every intermediate wizard step renders `{{ code }}`/`{{ name }}`/`Склад:` as visible `<p>` text (not just hidden inputs) | unit | `uv run pytest tests/test_mobile_writeoff.py -k header -x` | ❌ Wave 0 (new assertions needed in each `test_mobile_*.py`) |
| UI-03 | Write-off's 3 steps no longer contain `history.back()`; every "Назад" button's `hx-post`/`hx-get` target matches its immediate predecessor's route | unit | `uv run pytest tests/test_mobile_writeoff.py tests/test_mobile_corrections.py -k back -x` | ❌ Wave 0 |
| UI-04 | `sale_basket.html` contains `<p class="mobile-step-indicator">Корзина</p>` | unit | `uv run pytest tests/test_mobile_sales.py -k basket_step_indicator -x` | ❌ Wave 0 |
| UI-05 | `search_product_detail.html` renders "Продать"/"Принять" links to `/m/sales?code=`/`/m/receipts?code=`; both `/m/sales` and `/m/receipts` GET accept and echo `?code=` | unit + integration | `uv run pytest tests/test_mobile_search.py tests/test_mobile_sales.py tests/test_mobile_receipts.py -k code_prefill -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the relevant single `test_mobile_*.py` file's quick command above.
- **Per wave merge:** `uv run pytest tests/test_mobile_*.py`
- **Phase gate:** `uv run pytest` (full suite) green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] New assertions in `tests/test_mobile_corrections.py` — cover D-05's per-step back-target fix (REQ UI-03)
- [ ] New assertions in `tests/test_mobile_writeoff.py` — cover D-04's shell migration + absence of `history.back()` (REQ UI-03)
- [ ] New assertions in `tests/test_mobile_sales.py` — cover D-07 basket step-indicator (REQ UI-04) and D-08 `?code=` prefill (REQ UI-05)
- [ ] New assertions in `tests/test_mobile_receipts.py` — cover D-08 `?code=` prefill (REQ UI-05) and header format alignment (REQ UI-02)
- [ ] New assertions in `tests/test_mobile_search.py` — cover D-08/D-09 quick-action link presence, always rendered regardless of stock (REQ UI-05)
- [ ] New assertions in `tests/test_mobile_transfers.py` — cover header format alignment only (REQ UI-02; D-06 means no back-nav changes here)

*No new test framework/fixtures needed — `mobile_client_factory` (existing, `tests/conftest.py`) already supports every wizard's isolated router testing.*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Single-operator local app, no auth in v1 (per `CLAUDE.md`) |
| V3 Session Management | No | No server-side wizard session exists or is introduced — every step re-derives state from POSTed/GETed fields (stateless per-request), unchanged by this phase |
| V4 Access Control | No | No new roles/permissions surface |
| V5 Input Validation | Yes | Already-established pattern: every batch/warehouse id received from the client (`batch_id`, `code`) is re-validated server-side before trust (ownership check against `product_id`/`warehouse_id`) — this phase must NOT weaken that when threading `name`/`warehouse_name` into new template contexts. `name` is display-only carry-forward, never re-used to bypass a service's own `code`-based product re-resolution. |
| V6 Cryptography | No | Not touched by this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Reflected/stored XSS via product/batch name in the new header partial | Tampering/Information Disclosure | Jinja2 autoescaping (default, already relied on throughout every template read in this research — `product.name`/`oversell.product.name` are already rendered unescaped-safe via autoescape only, never `\|safe`); the new `_wizard_header.html` partial must follow the same convention — do not apply `\|safe` to `{{ name }}` or `{{ warehouse_name }}`. |
| Trusting a client-supplied `batch_id` to resolve `warehouse_name` without ownership re-validation | Tampering | Already-established pattern (`_pick_batch`/inline candidate checks in every wizard route) re-validates `candidate.product_id == product.id` before trusting a batch — the new warehouse-name lookup must be derived from the SAME already-validated `picked`/`candidate` batch object, never from a raw client-supplied `warehouse_id` field directly. |
| `?code=` query-param quick-action link used to inject arbitrary text into a form field | Tampering | Low risk — `code` pre-fills a text input that is validated identically to manually-typed input (existing `_find_product`/`lookup_prefill` server-side lookups apply regardless of how the field was populated); no new trust boundary is introduced since the value flows through the same `Form`/`Query` parameter validation any manual entry does. |

## Sources

### Primary (HIGH confidence — direct codebase reads, `[VERIFIED: codebase]`)
- `app/routes/mobile_writeoff.py`, `mobile_corrections.py`, `mobile_receipts.py`, `mobile_transfers.py`, `mobile_sales.py`, `mobile_search.py` — full read, all route signatures/context dicts
- `app/templates/mobile_partials/*.html` (all 5 wizards' step templates, `batch_card_picker.html`) — full read
- `app/templates/mobile_pages/{receipts,writeoff,corrections,sales,transfers,search}.html`, `mobile_base.html` — full read
- `app/services/batches.py`, `app/models.py` (`Batch`, `Warehouse`, `Product` classes) — full read, confirmed no ORM relationship from `Batch` to `Warehouse`
- `app/services/writeoffs.py`, `corrections.py`, `sales.py`, `transfers.py`, `receipts.py` — signature grep, confirmed `name` param present/absent per service
- `app/static/style.css` — grep for `.mobile-actions`/`.mobile-card`/`.mobile-step-indicator`/`a.button` (confirms `13-UI-SPEC.md`'s Design System table)
- `tests/test_mobile_writeoff.py` — read, confirms `mobile_client_factory` test convention and current assertion style
- `pyproject.toml` — confirms pytest 9.1.x, testpaths, no new deps needed
- `.planning/config.json` — confirms `nyquist_validation: true`, `security_enforcement: true` (Validation/Security sections required)

### Secondary (MEDIUM confidence)
- None — no web/docs lookups were needed for this phase; it is entirely internal-codebase research.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new stack, fully verified against `pyproject.toml`/existing vendored htmx
- Architecture: HIGH — every claim traced to a specific file/line read in this session
- Pitfalls: HIGH — each pitfall reproduced from actual route/template code, not inferred
- Open Question (corrections step-2 back-nav scope): MEDIUM — genuinely ambiguous in `13-CONTEXT.md`'s own wording vs. receipts' actual shipped behavior; flagged for planner/user confirmation

**Research date:** 2026-07-13
**Valid until:** No expiry concern — internal codebase research tied to the current commit; re-verify only if `app/routes/mobile_*.py` or `app/templates/mobile_*/` change again before planning executes.
