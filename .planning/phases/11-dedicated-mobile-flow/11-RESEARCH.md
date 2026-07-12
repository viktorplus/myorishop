# Phase 11: Dedicated Mobile Flow - Research

**Researched:** 2026-07-12
**Domain:** Server-rendered multi-step wizard UI (FastAPI + Jinja2 + htmx 2.0.10), viewport-based routing, no client-side framework
**Confidence:** MEDIUM-HIGH (architecture/stack/pitfalls: HIGH, grounded directly in this repo's own code and history; viewport-redirect scope: MEDIUM, one genuine open design question flagged below)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Entry point / routing**
- **D-01:** Mobile flow lives under a dedicated URL namespace (`/m/...`), separate routes from the desktop pages.
- **D-02:** On first landing from a phone-width viewport, the operator is auto-redirected into `/m/...`. Desktop viewports are routed to the existing desktop pages unchanged.

**Mobile navigation**
- **D-03:** `/m/` is a home screen with large operation tiles (search, receipt, sale, write-off/return/correction, history, transfer, expiry report) — no persistent bottom tab bar or hamburger menu.
- **D-04:** Each operation screen provides a "Back" control that returns to the mobile home screen (`/m/`).

**Operation step structure**
- **D-05:** Sale, write-off, return, and correction flows are step-by-step wizards — one screen per step (find product → pick batch, when the product has more than one → enter quantity/price → confirm) — not a single scrollable form. One action per screen, thumb-operable.
- **D-06:** Same min-price/oversell warn-but-allow guardrails as desktop apply at the relevant wizard step.

**Batch-selection step**
- **D-07:** Mobile batch picker shows one large full-width tappable card per batch, with price, expiry date, remaining quantity, and comment all visible at once (no truncation, no expand-to-see-more). Tapping the card selects the batch.

### Claude's Discretion

- Exact tile layout/grid on the `/m/` home screen (icons, ordering, grouping).
- History browsing UI on mobile (filter set may be simplified vs. desktop `history.html`; scope not specifically discussed, no objection raised to reducing filters for a narrow screen).
- Transfer and expiry-report mobile screen layouts (not specifically discussed — build as simplified, single-purpose mobile screens per phase goal, consistent with D-05/D-07 patterns for wizards and batch display).
- Viewport-width breakpoint used to decide "phone-width" for the auto-redirect.

> **Note (this research pass):** all four discretion items above have since been **resolved** by the approved `11-UI-SPEC.md` (tile grid/order, history's single-filter design, transfer/expiry card layouts, and the 600px breakpoint). The one item UI-SPEC explicitly left open — "the exact redirect MECHANISM... is an implementation decision... flag for RESEARCH.md/planner" — is resolved below in Architecture Patterns / Pitfall 2.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | A dedicated mobile flow — simpler, single-purpose screens/steps for core operations (search, receipts, sales, write-offs/returns/corrections, history, transfer, expiry report) — rather than adapting the same dense desktop pages via CSS alone; the existing desktop layout stays unchanged | Architecture Patterns (route namespace, mobile base layout, wizard hidden-field state pattern, service reuse map), Don't Hand-Roll (which existing service functions to call unmodified), Common Pitfalls (OOB `<template>` wrapping, redirect scope, htmx-config duplication, batch ownership re-validation), Validation Architecture (test map + manual-only UAT gates for viewport behavior) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Extracted directives the planner must honor (same authority as locked CONTEXT.md decisions):

- **Stack is fixed:** FastAPI 0.139.x, SQLAlchemy 2.0.x (2.0 declarative style, sync `Session`, no async), SQLite (WAL + `foreign_keys=ON`, already configured), Jinja2 3.1.x, htmx **2.0.10 stable only** — never the 4.0 beta.
- **No SPA / no new JS framework.** No React/Vue/Alpine. This phase must use vendored htmx idioms only, exactly as the UI-SPEC's Interaction Contract already states.
- **htmx must be vendored**, never loaded from a CDN (`app/static/htmx.min.js`, already present — reuse the same `<script src="/static/htmx.min.js" defer>` tag, do not add a second copy or a different version).
- **No Docker, no PyInstaller/cx_Freeze.** Not relevant to this phase's scope but binding project-wide.
- **Portable ORM only** — no raw SQLite-specific SQL (`INSERT OR REPLACE`, `strftime`, etc.). Any new mobile-only query must use the same SQLAlchemy Core/ORM constructs as existing services.
- **Money stored as integer minor units (cents)**, never float. Reuse the existing `| cents` Jinja filter — never re-implement formatting.
- **Do not add auth/session machinery in v1** — "single local user... no auth complexity needed in v1." This directly rules out a server-side session store as the wizard state-carrying mechanism (see Architecture Patterns below).
- **UUID business-entity IDs, append-only ledger** — unchanged; mobile writes go through the same `record_operation` write path, never a new one.
- Ruff (`line-length = 100`, `target-version = "py313"`) and pytest are the lint/test tools; no new tooling to introduce.

## Summary

Phase 11 adds a second, parallel presentation layer (`/m/...`) on top of an already-complete desktop feature set. There is **no new business logic** in this phase — every operation (receipt, sale, write-off, correction, transfer, return, history, expiry report) already has a fully-worked, guardrail-enforcing service function in `app/services/*.py` (`register_sale`, `register_writeoff`, `register_correction`, `register_transfer`, `register_receipt`, `register_return`, `history_view`, `expiring_batches`, `open_batches`, `search_products`). The entire phase is: new routes that call these same functions, new Jinja2 templates that render mobile-shaped HTML, and one small piece of genuinely new client-side behavior (the viewport-width auto-redirect).

The single hardest technical decision UI-SPEC left open is **how the wizard carries state between htmx-swapped steps**, and **how the viewport redirect is implemented and scoped**. Both are resolved here by extending patterns the app already uses everywhere: hidden-field carry-forward (already the app's universal pattern for surviving 422/warn re-renders) for wizard state, and a client-side `matchMedia` redirect (not User-Agent sniffing) for the viewport check — because the UI-SPEC's breakpoint is explicitly a **viewport-width** threshold (600px), which only `matchMedia`/CSS media queries can express precisely; User-Agent and even the modern `Sec-CH-UA-Mobile` client hint answer "what device is this" (and the latter is Chromium-only), not "how wide is the viewport right now."

**Primary recommendation:** Build `/m/...` as new, flat `app/routes/mobile_*.py` router files (mirroring the existing one-file-per-feature convention, full paths declared per-route, no `APIRouter(prefix=...)`) that import and call the existing `app/services/*.py` functions unchanged; render a new `app/templates/mobile_base.html` + `app/templates/mobile_pages/` + `app/templates/mobile_partials/` template tree; carry wizard state as hidden `<input>` fields inside one persistent `<form>` per operation (no server-side session); and gate the auto-redirect with a single inline `matchMedia` script in `base.html`'s `<head>`, scoped to `/` only (see Pitfall 2 for why "every desktop entry point" is unsafe).

## Architectural Responsibility Map

This project's FastAPI app renders server-side HTML directly (no separate SSR-vs-API split) — "Frontend Server (SSR)" and "API/Backend" are the same physical tier here.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Viewport-width detection & auto-redirect (D-02) | Browser/Client | — | Viewport width in pixels is never sent to the server (no HTTP header carries it); only client-side JS (`matchMedia`) can evaluate it reliably against a CSS-style breakpoint |
| `/m/...` route namespace & rendering (D-01) | API/Backend (FastAPI+Jinja2, combined tier) | — | New thin routes, same process, same app instance — not a separate service |
| Wizard step-to-step state carry-forward (D-05) | Browser/Client (state physically lives in the loaded HTML form's hidden inputs) | API/Backend (re-renders each step from posted state) | No session store exists or should be added (CLAUDE.md); the DOM is the only place multi-step state can live without new infrastructure |
| Guardrail logic — min price, oversell, over-removal (D-06) | API/Backend | Database/Storage | 100% reused from existing `app/services/*.py`; zero new logic |
| Batch/basket card rendering (D-07) | API/Backend (SSR) | Browser/Client (htmx swaps the fragment) | Jinja2 renders server-side; htmx only swaps the resulting HTML into the DOM |
| Persistence (stock, batches, operations ledger) | Database/Storage | — | SQLite via SQLAlchemy 2.0, unchanged models/migrations — this phase touches zero schema |

## Standard Stack

### Core

No new dependencies this phase — 100% reuse of the stack already pinned in `pyproject.toml` (verified by reading the file directly, 2026-07-12).

| Library | Version | Purpose | Why Standard (this project) |
|---------|---------|---------|------------------------------|
| FastAPI | 0.139.* [VERIFIED: pyproject.toml] | Routing for new `/m/...` endpoints | Already the app's only web framework; new routers follow the exact shape of `app/routes/sales.py` etc. |
| Jinja2 | 3.1.* [VERIFIED: pyproject.toml] | `mobile_base.html` + mobile page/partial templates | Already wired via `app/routes/__init__.py`'s shared `Jinja2Templates` instance and filters (`cents`, `ru_date`, `local_dt`) — reused unchanged |
| htmx (vendored) | 2.0.10 [VERIFIED: app/static/htmx.min.js present in repo, CLAUDE.md pins this exact version] | Wizard step swaps, batch-card selection, basket updates | Already vendored at `app/static/htmx.min.js`; mobile templates load the exact same `<script src="/static/htmx.min.js" defer>` — no second copy |
| SQLAlchemy | 2.0.* [VERIFIED: pyproject.toml] | No new models/queries — mobile routes call existing service functions | Zero schema changes this phase |

### Supporting

No new supporting libraries. Mobile screens extend `app/static/style.css` with the four new CSS classes already specified in `11-UI-SPEC.md` (`.mobile-shell`, `.mobile-tile-grid`, `.mobile-tile`, `.mobile-card`, `.mobile-actions`, `.mobile-back`, `.mobile-step-indicator`) — no CSS framework, no build step, consistent with the project's classless/Pico-flavored plain-CSS approach.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Client-side `matchMedia` redirect | Server-side User-Agent sniffing (classic UA string or `Sec-CH-UA-Mobile` client hint) | Rejected — see Pitfall 1. UA-based detection answers "what device" not "how wide is the viewport," and `Sec-CH-UA-Mobile` is Chromium-only (no Safari/Firefox support), requiring a UA-string fallback anyway. Neither can express the UI-SPEC's exact 600px viewport-width threshold. |
| Hidden-field wizard state (in the DOM, inside one persistent `<form>`) | Server-side wizard session (dict keyed by a generated session id, in-memory or DB-backed) | Rejected as the default — would be genuinely new infrastructure (a session concept) that CLAUDE.md explicitly defers for v1 ("do not add auth machinery... single local user"), and this project already has zero cookie/session middleware anywhere (`grep` for `SessionMiddleware`/`itsdangerous`/`set_cookie` across `app/` returns nothing). Hidden-field carry-forward is not a fallback — it is literally the pattern the desktop forms already use for the exact same problem (surviving 422/warn re-renders with the operator's picks intact). |
| Flat `app/routes/mobile_*.py` files | A nested `app/routes/mobile/` package with an aggregating `__init__.py` | Either works; flat files were chosen to match the project's existing convention exactly (every desktop feature is one flat file in `app/routes/`, no sub-packages anywhere in the routes tree) — do not introduce a new organizational pattern for one phase. |

**Installation:** none — no new packages.

**Version verification:** all versions above were confirmed directly from `pyproject.toml` and the presence of the vendored `app/static/htmx.min.js` file in this repository, not via registry lookup (no new packages to look up).

## Package Legitimacy Audit

**Not applicable — this phase installs zero new external packages.** Every capability is built from the already-verified, already-installed stack (FastAPI, Jinja2, SQLAlchemy, vendored htmx 2.0.10). The Package Legitimacy Gate is required only "whenever this phase installs external packages"; skip the registry-check steps entirely and proceed with the existing dependency set.

## Architecture Patterns

### System Architecture Diagram

```
Phone-width browser                Desktop-width browser
        |                                    |
        v                                    v
  GET /  (base.html)                   GET /  (base.html)
        |                                    |
  inline <script> in <head>:                 |
  matchMedia('(max-width:599px)')            |
        |                                    |
   match? --yes--> location.replace('/m/')   |  no redirect
        |                                    |
        v                                    v
   GET /m/  (mobile_base.html)          existing desktop pages
        |                               (base.html, unchanged)
        v
  Home tile grid (8 tiles)
        |
        +--> /m/search -----------------> app.services.catalog.search_products (reused)
        |
        +--> /m/receipts (wizard) ------> app.services.receipts.register_receipt (reused)
        |
        +--> /m/sales (wizard, basket) -> app.services.sales.register_sale (reused)
        |         |
        |         +-- step: Товар -----> app.services.sales.lookup_prefill (reused)
        |         +-- step: Партия ----> app.services.batches.open_batches (reused)
        |         +-- step: Кол-во/Цена -> zero write yet (form state only)
        |         +-- step: Корзина ---> POST accumulates code[]/qty[]/price[]/batch_id[]
        |                                 identical shape to desktop's basket arrays
        |
        +--> /m/writeoff (wizard) ------> app.services.writeoffs.register_writeoff (reused)
        +--> /m/corrections (wizard) ---> app.services.corrections.register_correction (reused)
        +--> /m/transfers (wizard) -----> app.services.transfers.register_transfer (reused)
        +--> /m/history ----------------> app.services.operations.history_view (reused)
        +--> /m/reports/expiry ---------> app.services.batches.expiring_batches (reused)
        +--> (from a History card) -----> app.services.returns.register_return (reused)

  Every write ultimately funnels through the SAME single write path:
  app.services.ledger.record_operation (unchanged, append-only)
```

A reader can trace any operation end-to-end: browser taps a tile -> route calls the existing service function -> service calls `record_operation` -> SQLite. Only the routes and templates in the middle are new.

### Recommended Project Structure

```
app/
├── routes/
│   ├── mobile_home.py         # GET /m/  (D-03: 8-tile grid)
│   ├── mobile_search.py       # GET /m/search  (reuses catalog.search_products)
│   ├── mobile_receipts.py     # GET/POST /m/receipts/...  (wizard)
│   ├── mobile_sales.py        # GET/POST /m/sales/...  (wizard, basket)
│   ├── mobile_writeoff.py     # GET/POST /m/writeoff/...  (wizard)
│   ├── mobile_corrections.py  # GET/POST /m/corrections/...  (wizard)
│   ├── mobile_transfers.py    # GET/POST /m/transfers/...  (wizard)
│   ├── mobile_returns.py      # GET/POST /m/returns/... entry-from-history only, no tile
│   ├── mobile_history.py      # GET /m/history
│   └── mobile_reports.py      # GET /m/reports/expiry
├── templates/
│   ├── mobile_base.html       # NEW base layout (D-04: no <nav>, just «← Главная» + title)
│   ├── mobile_pages/          # full-page GET responses (home.html, search.html, ...)
│   └── mobile_partials/       # htmx-swapped step fragments (wizard steps, batch/basket cards)
└── static/
    └── style.css               # extended in place (additive classes only, see UI-SPEC)
```

Each new router file follows the exact per-route full-path style already used everywhere (`@router.get("/sales/new")`, no `APIRouter(prefix=...)`) — e.g. `@router.get("/m/sales")`, `@router.post("/m/sales")`, `@router.get("/m/sales/step/batch")`.

### Pattern 1: Wizard step state via a single persistent `<form>` + hidden-field carry-forward

**What:** One `<form>` per operation wizard wraps every step. Fields already answered are re-rendered as `<input type="hidden">` on every step response (outside the region htmx swaps); fields for the *current* step are visible inputs inside the swapped region. "Далее"/"Назад"/batch-card-tap are `hx-post` (or `hx-get`) requests that target only the step-content region (`hx-target="#wizard-step" hx-swap="innerHTML"`); htmx's documented default behavior includes all values from the closest enclosing `<form>` on every request automatically, so no manual `hx-include` is needed for the accumulated fields to ride along.

**When to use:** Every D-05 wizard (receipt, sale, write-off, correction, transfer). The final step's "Далее"/primary-CTA button is the *real* write request — same endpoint shape (`code`, `qty`, `price`, `batch_id`, `confirm`, etc.) the matching desktop POST already accepts, calling the same service function.

**Example (illustrative — synthesized from this project's own hidden-field-carry-forward convention, e.g. `app/routes/sales.py::_build_lines` / `sale_row.html`, generalized to a step wizard):**
```python
# app/routes/mobile_sales.py
@router.post("/m/sales/step/qty-price")
def mobile_sale_step_qty_price(
    request: Request,
    code: str = Form(""),
    batch_id: str = Form(""),
    # accumulated basket so far, same array shape register_sale already accepts
    code_acc: list[str] = Form([], alias="code[]"),
    qty_acc: list[str] = Form([], alias="qty[]"),
    price_acc: list[str] = Form([], alias="price[]"),
    batch_acc: list[str] = Form([], alias="batch_id[]"),
    session: Session = Depends(get_session),
):
    # ...resolve product/batch (same ownership re-validation as desktop, T-09-08)...
    context = {
        "code": code, "batch_id": batch_id,
        # every already-collected line is re-echoed as hidden inputs by the template
        "code_acc": code_acc, "qty_acc": qty_acc,
        "price_acc": price_acc, "batch_acc": batch_acc,
    }
    return templates.TemplateResponse(
        request, "mobile_partials/sale_step_qty_price.html", context
    )
```
```html
{# mobile_partials/sale_step_qty_price.html #}
{# accumulated lines ride along untouched, outside the swapped region #}
{% for c in code_acc %}<input type="hidden" name="code[]" value="{{ c }}">{% endfor %}
{# ...same for qty_acc/price_acc/batch_acc... #}
<label>Количество<input name="qty" inputmode="decimal" required></label>
<label>Цена<input name="price" inputmode="decimal"></label>
<button hx-post="/m/sales/step/basket" hx-target="#wizard-step" hx-include="closest form">Далее</button>
```

### Pattern 2: Viewport-width auto-redirect (client-side `matchMedia`, not UA sniffing)

**What:** A small, synchronous, inline `<script>` placed at the very top of `base.html`'s `<head>` (before the stylesheet, before htmx loads) checks `window.matchMedia('(max-width: 599px)').matches` and, only when true **and** the current path is exactly `/`, calls `location.replace('/m/')`.

**When to use:** Once, in `base.html` only (never in `mobile_base.html` — there is no requirement, and no UI-SPEC decision, to bounce a desktop-width visitor away from `/m/...`, so adding a reverse check would be unrequested scope and a needless redirect-loop risk).

**Why client-side, not server-side UA sniffing** [CITED: developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Browser_detection_using_the_user_agent; developer.chrome.com/docs/privacy-security/user-agent-client-hints; wicg.github.io/ua-client-hints]: the UI-SPEC's breakpoint (`600px`) is a **viewport-width** threshold, not a device classification. `matchMedia` evaluates the exact same media-query engine the CSS already uses, so JS and CSS agree by construction. Server-side alternatives were considered and rejected:
- Classic `User-Agent` string sniffing — fragile, spoofable, and fundamentally answers "what device/browser" not "how many CSS pixels wide is the viewport right now" (a desktop browser resized to 400px would be missed; a large-screen Android tablet in a UA-sniffing regex might be falsely caught).
- `Sec-CH-UA-Mobile` client hint — Chromium-only (Chrome/Edge/Opera; **not implemented in Safari or Firefox**), so it would require a classic-UA fallback anyway, and it too only signals "is this a mobile OS," not viewport width.

**Example (illustrative — no external doc mandates this exact snippet; synthesized from the matchMedia consensus above plus this project's existing "no external CDN, inline vendored JS only" convention):**
```html
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script>
    // D-02: viewport-width redirect, root landing only (Pitfall 2 — do NOT
    // extend this to every desktop path, or desktop-only pages with no
    // mobile equivalent become unreachable from a phone-width browser).
    if (window.location.pathname === "/" &&
        window.matchMedia("(max-width: 599px)").matches) {
      window.location.replace("/m/");
    }
  </script>
  ...
```

### Pattern 3: Guardrail warn-but-allow, reused verbatim

**What:** Every wizard's final confirmation step reuses the exact same `confirm` Form field + zero-write-until-confirmed contract the desktop routes already implement (`register_sale(..., confirm=confirm)`, `register_writeoff(..., confirm=confirm)`, etc.). The mobile confirmation screen's danger button ("Продать всё равно" / "Списать всё равно" / etc.) re-submits the SAME accumulated hidden fields plus `confirm=1` to the same final-step endpoint.

**When to use:** Sale (price-floor + oversell), write-off (over-removal), correction (over-removal), transfer (over-transfer) — every case already listed in `11-UI-SPEC.md`'s per-operation warning tables.

### Anti-Patterns to Avoid

- **Reimplementing stock/price/guardrail math in a mobile route:** every number this phase displays or validates (remaining quantity, min-price check, oversell check) already has a service function. A mobile route that hand-rolls "is qty > available" duplicates logic that can drift from the desktop version — always call the existing `register_*`/`open_batches`/`expiring_batches` functions.
- **A second copy of htmx or a different version for mobile:** CLAUDE.md pins htmx 2.0.10 vendored; do not add a CDN script tag or a different bundle for `/m/...` pages "to save bytes."
- **Server-side wizard session as the first idea:** tempting because it "feels cleaner," but it is new infrastructure this project has deliberately avoided (see Alternatives Considered). Hidden-field carry-forward is the established pattern, not a workaround.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Resolving open batches for a product | A new mobile-only batch query | `app.services.batches.open_batches(session, product_id, warehouse_id=None)` | Already encodes the D-07 sort order (earliest expiry first, NULL last, tie-broken by receipt date) and the `quantity > 0` filter |
| Expiring-batches list | A new mobile-only expiry query | `app.services.batches.expiring_batches(session)` | Already joins Product+Warehouse and orders by expiry (LOT-06) |
| Product/code search | A new mobile-only LIKE query | `app.services.catalog.search_products(session, q)` (or `search_view`) | Already Cyrillic-safe (Python-side `.lower()`, not SQL `lower()`), already escapes `%`/`_`/`\` via `_escape_like`, already ranks exact-code > code-prefix > name-substring, already caps at 20 rows |
| History listing/pagination | A new mobile-only ledger query | `app.services.operations.history_view(session, type_filter=..., product_id=..., page=..., page_size=...)` | Already does the has-next-sentinel pagination (fetch page_size+1) and the LEFT OUTER JOIN for pre-batch-era operations |
| Sale registration, oversell/price-floor checks | A mobile-only "simplified" sale writer | `app.services.sales.register_sale(session, customer_id=, codes=, qtys=, prices=, batch_ids=, confirm=)` | Already accepts the exact array shape (`code[]`/`qty[]`/`price[]`/`batch_id[]`) a mobile basket wizard naturally accumulates — zero adaptation needed at the write boundary |
| Write-off / correction / transfer / return registration | Mobile-only write functions | `register_writeoff`, `register_correction`, `register_transfer`, `register_return` (all in `app/services/`) | Same reasoning — these already implement D-06's guardrails |
| Batch ownership re-validation on a client-supplied `batch_id` | Trusting the posted `batch_id` directly | The `candidate.product_id == product.id` check already used in `sales.py::sale_batch_pick`, `writeoffs.py::writeoff_batch_pick`, `transfers.py::transfers_batch_pick` | Prevents a tampered `batch_id` from one product being attributed to a different product's operation (T-09-08 precedent) |
| Money/date formatting | New mobile-only filters | The existing `| cents` and `| ru_date` Jinja filters (registered once in `app/routes/__init__.py`, already global to every template) | Consistent formatting everywhere; already handles `None` |

**Key insight:** this phase has zero net-new domain logic. Every "Don't Hand-Roll" row above is not a generic library recommendation — it is a literal, already-imported function in this repository. The planner's tasks should be phrased as "call `X` from `Y`", not "implement X for mobile."

## Common Pitfalls

### Pitfall 1: OOB htmx fragments whose top-level element can't stand alone in the DOM

**What goes wrong:** An out-of-band (`hx-swap-oob`) fragment whose root element is one of `<tr>`, `<td>`, `<th>`, `<thead>`, `<tbody>`, `<tfoot>`, `<colgroup>`, `<caption>`, `<col>`, `<li>`, or `<option>` gets silently mis-parsed by the browser when it arrives outside its required parent context (e.g. a `<tr>` with no enclosing `<table>`) — the browser "repairs" the malformed fragment by folding it into an unrelated nearby element instead of routing it to its OOB target.

**Why it happens:** This is documented htmx behavior [CITED: htmx.org/attributes/hx-swap-oob — "Troublesome Tables"], and this exact bug already bit this project once: Phase 9 Plan 06 had to wrap an OOB `<tr id="batch-wrap-...">` in `<template>...</template>` inside `sale_lookup.html`/`sale_batch_pick.html` after the browser silently folded an unwrapped OOB `<tr>` into the open basket row, producing two `batch_id[]` hidden inputs per line and rejecting every batched sale with «Выберите партию.» (see `.planning/phases/09-batch-tracking-ledger-integration/09-06-SUMMARY.md`).

**How to avoid:** Mobile batch/basket selection uses `<div class="mobile-card">` (per D-07/UI-SPEC), not `<table>` rows, so this *specific* manifestation is unlikely to recur for the batch-card UI itself. It remains directly relevant wherever a mobile step OOB-refreshes a **sibling** hint while the main region advances — e.g. a "Остаток в партии" hint or an auto-filled price field elsewhere on the page (the same idiom desktop's `sale_lookup.html`/`correction_batch_pick.html` already use). Any such OOB fragment whose root tag is in the list above must be `<template>`-wrapped exactly like the existing fix.

**Warning signs:** a form field that "sometimes" duplicates, a hidden input that appears twice after a swap, a 422 that says a required field is missing when the operator visibly filled it in.

### Pitfall 2: Scoping the auto-redirect too broadly blocks reachability of desktop-only pages

**What goes wrong:** The UI-SPEC's Interaction Contract says "landing on `/` (or any desktop entry point) from a viewport under 600px sends the operator into `/m/...`." Read literally and implemented as "redirect on **every** desktop route, every time, whenever the viewport is under 600px," this makes several existing desktop-only pages **permanently unreachable** from a phone-width browser — `/products` (full list, not the mobile "search-only" screen), `/categories`, `/warehouses` (management), `/customers`, `/dictionary`, `/backup`, `/export`, and the non-expiry reports (`/reports/sales`, `/reports/products`, `/reports/writeoffs`) have **no mobile equivalent this phase** (only 8 tiles/operations are in scope per D-03). If the redirect fires on every navigation to any of these, an operator using a phone can never reach them at all.

**Why it happens:** "First landing" and "any desktop entry point" are two different scopes, and the UI-SPEC deliberately deferred the exact mechanism to this research pass.

**How to avoid:** Scope the redirect script to fire only when `window.location.pathname === "/"` (the literal, singular "first landing" case — matching this app's existing convention where `/` is the one canonical entry point, per `app/routes/home.py`). This preserves D-02's stated behavior (phone-width operators land on the mobile home by default) while keeping every desktop-only management/report page reachable via direct navigation or a bookmark. This scope choice is `[ASSUMED]` — see Assumptions Log A1 — and should be confirmed with the user or reconfirmed during plan review, since "or any desktop entry point" in the UI-SPEC could also be read as intentional.

**Warning signs (manual UAT):** on a phone-width browser, try to reach `/customers` or `/backup` directly — if it silently bounces to `/m/`, the redirect is scoped too broadly.

### Pitfall 3: `mobile_base.html` needs its own `<meta name="htmx-config">`, or 422 validation responses vanish

**What goes wrong:** `base.html` carries a project-specific htmx response-handling override:
```html
<meta name="htmx-config"
      content='{"responseHandling":[{"code":"204","swap":false},{"code":"[23]..","swap":true},{"code":"422","swap":true},{"code":"[45]..","swap":false,"error":true}]}'>
```
This exists because **htmx 2.x does not swap 4xx responses by default** — without this override, every 422 (validation error, oversell warning, etc.) a wizard step returns would be silently discarded instead of rendered. `mobile_base.html` is explicitly a *new, separate* file (not an `{% extends "base.html" %}`), so this `<meta>` tag will NOT be inherited unless it is copied into `mobile_base.html` too.

**Why it happens:** Easy to forget when writing a brand-new base template from scratch, since the desktop app "just works" and this config is easy to overlook as boilerplate rather than load-bearing.

**How to avoid:** Copy the exact same `<meta name="htmx-config">` tag into `mobile_base.html`. Add a regression test asserting the tag is present (mirrors how `test_smoke.py::test_home_page_renders` already asserts `/static/htmx.min.js` is present).

**Warning signs:** a wizard step's error/warning message ("Цена ниже минимальной", oversell, etc.) never appears on mobile even though the desktop equivalent works and the server logs show a 422 was returned.

### Pitfall 4: Missing the `<meta name="viewport">` tag in `mobile_base.html`

**What goes wrong:** Without `<meta name="viewport" content="width=device-width, initial-scale=1">`, mobile browsers render the page at a simulated desktop width (traditionally ~980px) and then scale it down — every `.mobile-card`/44px-touch-target/single-column layout in the UI-SPEC would render tiny and the whole "phone-width, thumb-operable" premise breaks, even though the HTML/CSS is otherwise correct.

**Why it happens:** `base.html` already has this tag; `mobile_base.html` is a brand-new file being written from scratch and it's easy to omit boilerplate that "isn't part of the visible design."

**How to avoid:** Copy the exact tag from `base.html` verbatim into `mobile_base.html`.

### Pitfall 5: Forgetting the `confirm` field breaks D-06's zero-write guarantee

**What goes wrong:** If a mobile wizard's final-step endpoint omits or mishandles the `confirm` parameter when calling `register_sale`/`register_writeoff`/`register_correction`/`register_transfer`, either (a) the warn-but-allow screen never appears (silent writes past a guardrail — a real data-integrity regression) or (b) the danger button never actually completes the operation (stuck warning loop).

**How to avoid:** Every final-step POST handler must thread `confirm` through to the service call exactly like the matching desktop route does (`app/routes/sales.py::sale_create`, `app/routes/writeoffs.py::writeoff_create`, etc.) — copy the `if result and (result.get("oversell") or result.get("below_minimum")):` branch pattern verbatim.

### Pitfall 6: Empty-batch state must still block forward wizard progress

**What goes wrong:** Desktop enforces "no batch, no sale/write-off/correction/transfer" (D-12 in prior phases) at the write boundary. A mobile wizard that lets the operator tap "Далее" past an empty batch-selection step (because "there's nothing to select, so just skip it") silently produces an operation attributable to no batch, which desktop never allows.

**How to avoid:** When `open_batches()` returns empty for the looked-up product, render the UI-SPEC's `«Нет партий с остатком.»` empty state AND omit/disable the forward control on that step, mirroring desktop's existing block.

## Code Examples

### Reusing an existing write service unchanged, from a new mobile route

```python
# Source: app/services/sales.py (existing, unmodified) — register_sale already
# accepts exactly the array shape a mobile basket wizard accumulates.
from app.services.sales import register_sale

@router.post("/m/sales")
def mobile_sale_create(
    request: Request,
    code: list[str] = Form([], alias="code[]"),
    qty: list[str] = Form([], alias="qty[]"),
    price: list[str] = Form([], alias="price[]"),
    batch_id: list[str] = Form([], alias="batch_id[]"),
    customer_id: str = Form(""),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    result, errors = register_sale(
        session, customer_id=customer_id, codes=code, qtys=qty,
        prices=price, batch_ids=batch_id, confirm=confirm,
    )
    # ...same oversell/below_minimum/errors branching as app/routes/sales.py::sale_create,
    # rendering mobile_partials/sale_confirmation.html instead of the desktop partial...
```

### `<template>`-wrapped OOB fragment (the established fix, for any new OOB hint)

```html
{# Source: app/templates/partials/sale_lookup.html (Phase 9 Plan 06 fix) #}
{% if picked is not none %}
<template>
  <td id="price-{{ row_id }}" hx-swap-oob="true">
    <input name="price[]" value="{{ fill_price_cents | cents }}">
  </td>
</template>
{% endif %}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Classic `User-Agent` string parsing for device detection | `window.matchMedia()` for viewport/feature checks; `Sec-CH-UA-*` client hints for genuine device/browser classification (Chromium-only) | Client Hints introduced ~2020 (Chrome 89+), still not adopted by Firefox/Safari as of this research | Neither replaces `matchMedia` for a viewport-width breakpoint — this project's 600px threshold is best expressed directly as a media query, both in CSS and in the one piece of redirect JS |

**Deprecated/outdated:** htmx 1.x's undocumented/inconsistent OOB-table handling — htmx 2.0.10 (this project's pinned version) documents the `<template>`-wrapping requirement explicitly; no change needed to the already-applied Phase 9 fix.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The D-02 auto-redirect should be scoped to `window.location.pathname === "/"` only (not every desktop entry point) | Architecture Patterns / Pattern 2, Pitfall 2 | If the user actually intended a broader redirect scope, desktop-only pages (customers, dictionary, backup, export, warehouses, non-expiry reports) would need either a mobile equivalent added later or an explicit "escape hatch" affordance — neither exists in the current UI-SPEC. Low risk of silent failure (it's a UX scoping choice, not a data-integrity risk), but should be confirmed before planning locks it in. |
| A2 | Wizard step-to-step state should be carried via hidden fields inside one persistent `<form>` per operation, not a server-side session | Architecture Patterns / Pattern 1, Alternatives Considered | If a future requirement needs cross-device or cross-tab wizard resumption, hidden-field state (tied to one loaded page) won't support it — but no such requirement exists in CONTEXT.md/UI-SPEC, and CLAUDE.md explicitly defers session infrastructure for v1. |
| A3 | New mobile route files should be flat (`app/routes/mobile_sales.py` etc.), matching the existing one-file-per-feature convention, rather than a nested `app/routes/mobile/` package | Architecture Patterns / Recommended Project Structure | Low risk — purely organizational; either would work, flat matches the codebase's existing 100% convention. |

## Open Questions

1. **Does "any desktop entry point" in the UI-SPEC mean the redirect should fire on every desktop route, not just `/`?**
   - What we know: `11-UI-SPEC.md`'s Interaction Contract literally says "landing on `/` (or any desktop entry point)."
   - What's unclear: whether that phrase means "any of the app's several top-level desktop pages a user might land on directly (bookmark, browser history)" or is just loosely restating "/" as "the" desktop entry point.
   - Recommendation: scope to `/` only per Pitfall 2's reasoning (preserves reachability of desktop-only pages with no mobile equivalent); flag for the planner/discuss-phase to confirm with the user before implementation if there's any doubt.

2. **Should there be a manual "escape hatch" link from `/m/...` back to the full desktop site, for the 8+ desktop-only pages this phase doesn't cover on mobile?**
   - What we know: D-03 explicitly forbids a persistent nav bar/hamburger on `/m/...`, and no CONTEXT.md/UI-SPEC decision mentions a desktop-escape link.
   - What's unclear: whether an operator on a phone who needs `/customers` or `/backup` is expected to type the URL manually, or whether some minimal affordance should exist.
   - Recommendation: out of this phase's explicit scope (UI-SPEC's screen list has no such link); leave as-is unless the user raises it in discuss-phase — do not invent a new nav affordance UI-SPEC didn't approve.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* [VERIFIED: pyproject.toml] with `httpx`-backed `fastapi.testclient.TestClient` (existing `client` fixture in `tests/conftest.py`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| Quick run command | `uv run pytest tests/test_mobile_*.py -x -q` (new mobile test files, once created) |
| Full suite command | `uv run pytest -q` |

**Client-side behavior cannot be automated with this stack:** `TestClient` makes HTTP requests only — it has no JS engine, so `matchMedia`/`location.replace` redirect behavior (D-02) **cannot** be asserted by pytest. This is a manual-only UAT gate, already flagged as item 1-2 in `11-UI-SPEC.md`'s "Manual UAT gates" list. Automated tests can only assert the redirect *script text* is present in `base.html`'s response (a weak proxy), not that it actually redirects a real narrow-viewport browser.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| UI-01 | `/m/` home renders all 8 tiles with correct hrefs | unit/integration | `uv run pytest tests/test_mobile_home.py -x -q` | ❌ Wave 0 |
| UI-01 | Each wizard's final step calls the SAME service function as its desktop counterpart and produces the same DB effect (e.g. a mobile sale creates the same `Operation` rows as a desktop sale) | integration | `uv run pytest tests/test_mobile_sales.py -x -q` (mirror `tests/test_sales.py`'s assertions against `/m/sales`) | ❌ Wave 0 |
| UI-01 | Guardrails (price-floor, oversell, over-removal) fire identically on mobile, zero-write until `confirm=1` | integration | `uv run pytest tests/test_mobile_sales.py -k oversell -q`, same pattern for writeoff/correction/transfer | ❌ Wave 0 |
| UI-01 | Batch-selection step blocks forward progress when a product has zero open batches | unit/integration | `uv run pytest tests/test_mobile_sales.py -k empty_batches -q` | ❌ Wave 0 |
| UI-01 | `/m/history` renders one filter (тип операции) and card rows with all 4 lines, matching History section of UI-SPEC | integration | `uv run pytest tests/test_mobile_history.py -x -q` | ❌ Wave 0 |
| UI-01 | `/m/reports/expiry` renders the read-only card list | integration | `uv run pytest tests/test_mobile_reports.py -x -q` | ❌ Wave 0 |
| UI-01 | Viewport-width auto-redirect fires only from a phone-width browser landing on `/` | manual-only | — | n/a (JS behavior, see note above) |
| UI-01 | Desktop pages remain pixel-for-pixel unchanged at desktop widths | manual-only + regression | Full existing desktop suite (`test_sales.py`, `test_writeoffs.py`, `test_corrections.py`, `test_transfers.py`, `test_receipts.py`, `test_history.py`, `test_reports.py`) must stay 100% green, unmodified, as the automated proxy | ✅ already exists |

### Sampling Rate

- **Per task commit:** the relevant `tests/test_mobile_*.py -x -q` file (or the closest existing desktop-equivalent file if the mobile file doesn't exist yet for that task).
- **Per wave merge:** `uv run pytest -q` (full suite — this also guards that desktop tests stay green, i.e. the "purely additive" phase boundary held).
- **Phase gate:** full suite green + the manual UAT gates already enumerated in `11-UI-SPEC.md`'s Interaction Contract (6 items) before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `tests/test_mobile_home.py` — covers UI-01 (home tile grid)
- [ ] `tests/test_mobile_search.py` — covers UI-01 (search screen)
- [ ] `tests/test_mobile_receipts.py` — covers UI-01 (receipt wizard)
- [ ] `tests/test_mobile_sales.py` — covers UI-01 (sale wizard + basket + guardrails)
- [ ] `tests/test_mobile_writeoff.py` — covers UI-01 (write-off wizard + guardrail)
- [ ] `tests/test_mobile_corrections.py` — covers UI-01 (correction wizard + guardrail)
- [ ] `tests/test_mobile_transfers.py` — covers UI-01 (transfer wizard + guardrail)
- [ ] `tests/test_mobile_returns.py` — covers UI-01 (return flow, entry from history)
- [ ] `tests/test_mobile_history.py` — covers UI-01 (history card list + single filter)
- [ ] `tests/test_mobile_reports.py` — covers UI-01 (expiry report card list)
- [ ] Framework install: none — `tests/conftest.py`'s existing `client`/`session`/`product`/`warehouse`/`batch`/`customer`/`stocked_product` fixtures are directly reusable for every new mobile test file (verified by reading `tests/conftest.py`).

## Security Domain

ASVS Level 1, `security_block_on: high` per `.planning/config.json`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Single local operator, no auth this phase (CLAUDE.md: "no auth complexity needed in v1") — unchanged by this phase |
| V3 Session Management | No | This phase deliberately introduces no server-side session (Pattern 1/Alternatives Considered) |
| V4 Access Control | No | No roles/permissions exist in the app |
| V5 Input Validation | Yes | Reuse existing service-layer parsers (`catalog.parse_optional_cents`, `catalog.parse_optional_int`) and the `register_*` functions' own validation; Jinja autoescape for all untrusted stored text (batch comment/location — never `\| safe`, matching the existing `batch_picker.html` comment); the `_escape_like()` pattern from `catalog.py` if `/m/search` builds any manual LIKE clause (prefer reusing `search_products` directly, which already does this) |
| V6 Cryptography | No | Not applicable to this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Reflected script injection via an unescaped id interpolated into a JS-evaluated `hx-on::load`/`hx-vals` attribute | Tampering | Format-validate any client-echoed id against the exact shape `new_id()` produces before interpolating it unescaped (the existing `_ROW_ID_RE = re.compile(r"[0-9a-fA-F-]{1,36}")` pattern in `app/routes/sales.py` — reuse verbatim if a mobile wizard also echoes row/step ids into JS attributes) |
| SQL LIKE-wildcard injection via unescaped `%`/`_`/`\` in a search query | Tampering | Reuse `app.services.catalog.search_products` (already applies `_escape_like`) rather than writing a new LIKE clause for `/m/search` |
| Client-supplied `batch_id` attributed to the wrong product (IDOR-style tampering) | Tampering / Elevation of Privilege | Re-validate `candidate.product_id == product.id` before trusting any client-supplied `batch_id`, exactly as every existing batch-pick endpoint already does (T-09-08 precedent) — every new mobile batch-pick endpoint must repeat this check |
| CSRF | Tampering | Not mitigated anywhere in this app today (no auth/session to ride), and this phase does not change that posture — consistent with the app's existing single-local-operator threat model, not a phase-specific gap |

## Sources

### Primary (HIGH confidence)
- This repository, read directly: `app/main.py`, `app/routes/__init__.py`, `app/routes/{home,sales,writeoffs,transfers}.py`, `app/services/{sales,writeoffs,transfers,batches,operations,catalog,corrections,returns,receipts}.py`, `app/templates/base.html`, `app/templates/partials/batch_picker.html`, `pyproject.toml`, `CLAUDE.md`, `.planning/phases/09-batch-tracking-ledger-integration/09-06-SUMMARY.md`, `.planning/phases/11-dedicated-mobile-flow/11-CONTEXT.md`, `.planning/phases/11-dedicated-mobile-flow/11-UI-SPEC.md`, `tests/conftest.py`

### Secondary (MEDIUM confidence)
- htmx.org — `hx-swap-oob` attribute documentation, "Troublesome Tables" `<template>`-wrapping guidance (via WebSearch, cross-checked against this project's own already-implemented, tested fix)
- developer.mozilla.org — Browser detection using the User-Agent string (UA sniffing pitfalls)
- developer.chrome.com/docs/privacy-security/user-agent-client-hints and wicg.github.io/ua-client-hints — `Sec-CH-UA-Mobile` support scope (Chromium-only)

### Tertiary (LOW confidence)
- General web consensus on `matchMedia` vs. UA sniffing (multiple blog/community sources returned by WebSearch, not a single authoritative doc) — corroborated across MDN + Chrome docs above, so treated as MEDIUM rather than LOW in the body text, but flagged here for transparency

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, versions confirmed by reading `pyproject.toml` directly
- Architecture: HIGH for service-reuse mapping (every function verified to exist in this repo by reading the source); MEDIUM for the wizard hidden-field pattern (a synthesized/recommended pattern, not copied from an official doc, though it directly extends an already-proven in-repo convention)
- Pitfalls: HIGH for Pitfalls 1/3/4/5/6 (directly grounded in this repo's own code/history); MEDIUM for Pitfall 2 (a genuine open scoping question, flagged as Assumption A1)

**Research date:** 2026-07-12
**Valid until:** 2026-08-11 (30 days — stable stack, no fast-moving dependencies; re-check if `11-UI-SPEC.md` is revised before planning)
