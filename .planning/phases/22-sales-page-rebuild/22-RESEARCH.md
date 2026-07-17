# Phase 22: Sales Page Rebuild - Research

**Researched:** 2026-07-17
**Domain:** Brownfield UI rebuild on an existing offline FastAPI + Jinja2 + HTMX 2.0.10 server-rendered app
**Confidence:** HIGH (every claim below is read from or executed against this repo; zero new packages)

## Summary

This phase adds **no new technology**. Every requirement (SALE-01..07) is satisfied by patterns already shipped in this codebase: HTMX partial swaps, `hx-include`-driven server re-renders, a delegated client-side listener mirroring a server parser (`price-cue.js`), and a portable `outerjoin` (`export.py::stream_sales_csv`). The dependency set does not change — `pyproject.toml` is untouched.

The work concentrates in six files: `app/routes/sales.py`, `app/routes/mobile_sales.py`, `app/services/sales.py::recent_sales`, `app/templates/partials/sale_customer.html`, `app/templates/partials/recent_sales.html`, and a new `app/static/sale-total.js`. SALE-01 (the code/name/qty/price table) is **already shipped** — `sale_form.html:47-70` renders exactly that table; the phase must not regress it.

Two real defects were **verified empirically** during this research (temporary probe test, since removed) and both sit directly on this phase's critical path:
1. **A 422/oversell re-render silently drops the selected-customer chip while still submitting `customer_id`.** The operator sees the search box as if nobody is selected, but the hidden input still carries the id. This is the SALE-03/04 rebuild's problem to fix.
2. **The mobile wizard's batch-card tap (a `hx-get`) drops the accumulated basket arrays.** htmx only auto-includes the enclosing form's inputs on **non-GET** requests, and that card tap has no `hx-include`. This is the exact mechanism D-04's mobile customer selector must not repeat.

**Primary recommendation:** Implement the D-01 radio as a **stateful server round-trip**: the radio's `hx-get` carries `hx-include="#customer-header"`, the server re-renders the active mode's visible fields *and* re-emits the two inactive modes' values as hidden inputs. This is the only design that satisfies D-01 (server-rendered block per radio) and D-03 (no data loss on switch) simultaneously — `hx-preserve` is documented as unsuitable here.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Customer selector (SALE-03)**

- **D-01: Explicit 3-way radio ("Новый" / "Существующий" / "Аноним"), each option HTMX-loads its own block** (`hx-get` per radio change, server renders the block) — not a client-side show/hide of blocks that are all already in the DOM. Chosen over pure client-side toggling because it mirrors the app's dominant pattern of server-rendered partial swaps rather than introducing a new all-client-JS interaction for this control (the live-total area is the one place client-only JS was explicitly chosen — see D-06 — but the selector itself follows the existing HTMX convention).
- **D-02: Default selection on form open is "Существующий"** (existing customer search/picker), not anonymous. Matches operator's stated workflow — most sales are to a known customer.
- **D-03: Switching the radio must not clobber data already entered in another mode.** If the operator types into the new-customer fields, picks an existing customer, then switches back, that mode's state must still be there — the HTMX swap that loads a different mode's block must preserve the other modes' already-filled state (not re-fetch/reset them). Implementation detail (which mode's HTML stays in the DOM vs. re-rendered) is Claude's discretion, but the behavior contract is: no silent data loss on radio switch.
- **D-04 (scope): Mobile sale wizard (`app/routes/mobile_sales.py`) gets the SAME 3-way customer selector in this phase — full desktop/mobile parity.** Mobile currently has NO customer picker at all (`customer_id=""` hardcoded, per the wizard's old "D-04: no mobile customer picker this phase" note — that deferred decision is now superseded). This is a real scope expansion beyond what REQUIREMENTS.md's SALE-03..07 wording states literally (unlike PROD-05 in Phase 18, SALE-03..07 don't say "desktop and mobile" explicitly) — operator confirmed explicitly when asked. Treat this as in-scope, not a gap to flag later.

**Anonymous sale (SALE-06)**

- **D-05: Keep `customer_id = NULL` as-is — no new "Аноним" row in `customers`.** The "Аноним" radio option simply results in no `customer_id` being set on submit, identical to today's walk-in behavior. No migration, no seed data, no new service logic for a system customer profile.
- **D-06: Recent-sales list (SALE-07) shows "Розница" (muted style) in the customer column for any sale with `customer_id IS NULL`.** Not a blank/em-dash — an explicit muted label so the operator can tell "no customer recorded" apart from "data missing".

**New-customer inline fields (SALE-05)**

- **D-07: The inline new-customer form on the sale page keeps exactly the 3 fields it has today — Имя / Фамилия / Номер консультанта.** None of Phase 21's new profile fields (phone/Telegram/email/social/address, all `CustomerContact` multi-value rows) are added to the sale-form inline flow. Operator explicitly rejected adding even a single phone+address shortcut. Full profile completion happens later on the customer's own card (`customer_form.html`), not at sale time. This applies to both desktop `sale_customer.html` and whatever mobile customer-selector partial D-04 introduces — same 3 fields only.

**Live running total (SALE-02)**

- **D-08: Client-side JS, no HTMX round trip** — one delegated `document.addEventListener('input', ...)` (same architecture as `app/static/price-cue.js` from Phase 18), reading all basket rows' `qty[]`/`price[]` values, parsing with the SAME accept-set as the server's `to_cents` (`app/core.py:28` — comma-decimal, no space-thousands), summing to a running total (amount) and unit count. Rejected: server-side debounced HTMX recompute — unnecessary round trips on a 5-10 row basket where the total is purely advisory display, and this repo already has the client-JS-mirrors-server-parse precedent (Phase 18 D-13).
- **D-09: If any basket row has an invalid/incomplete qty or price, show an "итог неполный" (incomplete total) marker** alongside the running total, rather than silently excluding that row's contribution from the sum. Keeps the operator from mistaking a partial sum for the real total mid-entry.
- The total is advisory-only, same convention as the colour cue: the server remains the sole authority on the actual charged amount (`_build_lines` / `register_sale` in `app/services/sales.py`), computed authoritatively on submit. No client-side money math feeds into what gets saved.

### Claude's Discretion

- Exact Russian wording/labels for the 3 radio options and the "итог неполный" marker.
- Which mode's HTML stays live in the DOM vs. gets re-fetched on radio switch, as long as D-03's no-data-loss contract holds.
- Whether the mobile customer selector (D-04) reuses the desktop `sale_customer.html` partial structure or gets its own mobile-styled equivalent — desktop/mobile already have separate route/template trees throughout the app (established pattern), so a mobile-specific partial is expected, not a deviation.
- Exact markup/placement of the live-total display (amount + unit count) directly under the basket table.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope (with one confirmed scope *expansion*, not creep: mobile customer-selector parity, D-04, explicitly confirmed by the operator as in-scope for this phase rather than deferred).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SALE-01 | Sale form is a code / name / quantity / sale-price table | **Already shipped** — `sale_form.html:47-70` renders `<table class="basket">` with exactly `Код / Название / Кол-во / Цена продажи` headers. Phase work = **regression guard only** (CONTEXT §Phase Boundary: "No basket table restructuring"). See §Common Pitfalls 1. |
| SALE-02 | Live running total (amount + unit count) under the table | New `app/static/sale-total.js`, architecture mirrored from `app/static/price-cue.js` (23 lines, delegated listener). Exact parse accept-set verified empirically — see §Architecture Pattern 2. Recompute hooks required on swap + row-delete — see §Common Pitfalls 2. |
| SALE-03 | New/existing/anonymous radio at top of sale form | Restructure `app/templates/partials/sale_customer.html` (65 lines today). New `GET /sales/customer-mode` endpoint. Stateful-echo design — see §Architecture Pattern 1. Mobile parity per D-04 — see §Architecture Pattern 3. |
| SALE-04 | Existing-customer autocomplete by consultant number / name / surname; auto-fills identifying fields | **Search backend needs zero changes** — `app/services/customers.py::search_customers` (:232) already matches all three via the `search_lc` shadow column; `customer_search_view` (:246) already returns `name_seg` + `consultant_seg` match highlighting. Endpoint `GET /sales/customer-search` (`sales.py:336`) and `customer_picker.html` reused. |
| SALE-05 | New-customer inline optional profile fields | D-07 pins this to the 3 existing fields. `POST /sales/customer` (`sales.py:343`) + `create_customer` (`customers.py:121`) reused unchanged — `create_customer`'s `address`/`contacts` params default so the sale-form call keeps working (see its docstring, :130-141). |
| SALE-06 | Anonymous records against walk-in with no extra fields | D-05: no schema change. `Sale.customer_id` is already `Mapped[str \| None]` (`models.py:409`) and `register_sale` already coerces `customer_id or None` (`sales.py:254`). Anonymous mode = render no fields, submit empty `customer_id`. Covered today by `test_customer_link_walkin_customer_id_null` (test_sales.py:255). |
| SALE-07 | Recent-sales list shows customer first + last name | `recent_sales` (`services/sales.py:333`) gains a double `outerjoin` mirroring `export.py:118-125` verbatim. `recent_sales.html` gains a column with D-06's muted "Розница". **Two callers** — see §Common Pitfalls 4. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

These are binding on every plan in this phase. All are already satisfied by the recommendations below.

| Directive | Source | Implication for Phase 22 |
|-----------|--------|--------------------------|
| No SPA / React / Vue; HTMX + Jinja2 server-rendered | §What NOT to Use | The D-01 radio and D-08 total stay in vanilla JS + HTMX. No build step. |
| htmx 2.0.10 stable, **vendored locally**, never a CDN | §Recommended Stack, §What NOT to Use | `app/static/htmx.min.js` — **verified** `version:"2.0.10"`. New `sale-total.js` must likewise be a local static file loaded via `<script src="/static/…" defer>` (mirrors `base.html:26`). |
| No `FLOAT`/`REAL` for money — integer minor units only | §What NOT to Use | The live total must sum **integer cents**, never JS floats. See §Don't Hand-Roll and §Architecture Pattern 2 — the recommended parser does string→int with zero float math. |
| No SQLite-specific SQL; portable SQLAlchemy Core/ORM only | §What NOT to Use | The SALE-07 join uses `select()/.outerjoin()` only — no `strftime`, no `INSERT OR REPLACE`. |
| SQLAlchemy 2.0 style (`Mapped[]`, `mapped_column()`, `select()`) | §Recommended Stack | No model changes this phase (D-05), so nothing new to declare. |
| No new dependencies without cause; `uv` manages env | §Development Tools | **Zero new packages.** `pyproject.toml` untouched. |
| Tailwind / npm build pipeline forbidden | §What NOT to Use | Radio + total styling reuses existing tokens in `app/static/style.css`. |
| Do not commit unless explicitly asked | global CLAUDE.md §Git | Executors stage but do not push beyond the GSD flow. |
| Communicate with the user in Russian | global CLAUDE.md §Language | UI copy is Russian (already true); code/comments English. |

**House conventions confirmed in-repo (not in CLAUDE.md but load-bearing):**
- Zero `relationship()`/`back_populates` in `app/` — FKs are joined manually in the service layer (`models.py:381-383` states this as a house rule). The SALE-07 join must follow this.
- Money rendered only via the `cents` Jinja filter (`app/routes/__init__.py:18` → `format_cents`).
- Untrusted stored text is Jinja-autoescaped, **never** `|safe`; client JS reads via `.dataset` and writes via `.textContent`, never building HTML strings (`customer_picker.html:1-12`).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Customer mode selection + block rendering (SALE-03) | Frontend Server (Jinja2 partial) | Browser (HTMX swap trigger) | D-01 mandates server-rendered blocks; the browser only fires `hx-get` and swaps. |
| Existing-customer autocomplete (SALE-04) | API/Backend (`search_customers`) | Frontend Server (`customer_picker.html`) | Cyrillic folding **cannot** happen in SQLite (`customers.py:5-7`) — it is Python-side, service tier. Never move to the browser. |
| Customer selection state across swaps (D-03) | Frontend Server (hidden-input echo) | Browser | htmx GET does not auto-include form values; state must round-trip through the server explicitly. |
| New-customer creation (SALE-05) | API/Backend (`create_customer`) | — | Validation + `search_lc` maintenance are service-tier (`customers.py:166`). |
| Live running total display (SALE-02) | Browser (`sale-total.js`) | — | D-08: advisory display only. Explicitly **not** an API concern. |
| Authoritative sale total / charged amount | API/Backend (`register_sale`) | — | `services/sales.py:282` `total_cents += qty * price_cents`. The browser total never feeds this. |
| Anonymous → `customer_id = NULL` (SALE-06) | API/Backend (`register_sale:254`) | Browser (submits empty) | Server coerces `customer_id or None`; browser cannot be trusted. |
| Recent-sales customer name (SALE-07) | Database/Storage (outerjoin) | Frontend Server (`recent_sales.html`) | One query, no N+1 — house rule (`customers.py:326-328`). |
| Oversell / batch / cash-credit guardrails (criterion 5) | API/Backend (`register_sale`) | — | Must remain untouched. See §Common Pitfalls 5. |

**Tier misassignment risk for this phase:** the tempting error is putting the live total's money math anywhere near the write path, or letting the browser decide `customer_id` semantics. Both are explicitly server-tier. The total is a *display* capability with no backend counterpart.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.139.* | Routing, `Form(...)` binding for the new mode endpoint | Already the app's framework `[VERIFIED: pyproject.toml:7]` |
| Jinja2 | 3.1.* | Server-rendered radio blocks + recent-sales column | Already the app's templating `[VERIFIED: pyproject.toml:8]` |
| htmx | 2.0.10 (vendored) | Radio-driven partial swap, autocomplete, oob refresh | `[VERIFIED: app/static/htmx.min.js contains version:"2.0.10"]` — matches CLAUDE.md's pinned stable line |
| SQLAlchemy | 2.0.* | `outerjoin` for the SALE-07 customer column | Already the app's ORM `[VERIFIED: pyproject.toml:11]` |
| Vanilla JS (no framework) | — | `sale-total.js` | Mirrors the shipped `price-cue.js` precedent exactly `[VERIFIED: app/static/price-cue.js]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.1.* | All new coverage | Existing runner `[VERIFIED: pyproject.toml:20]` |
| httpx | 0.28.* | Backs `TestClient` for web-level assertions | Existing dev dep `[VERIFIED: pyproject.toml:18]` |
| ruff | 0.15.* | Lint + format, `line-length = 100` | Existing `[VERIFIED: pyproject.toml:21, 29]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Stateful hidden-input echo (D-03) | `hx-preserve` on inactive blocks | **Rejected.** Docs: "You _must_ set an unchanging `id`" and "The response requires an element with the same `id`" — so the server must render the inactive block anyway, defeating D-01's per-mode fetch. Also documented: "Some elements cannot unfortunately be preserved properly, such as `<input type="text">` (focus and caret position are lost)". `[CITED: htmx.org/attributes/hx-preserve/]` |
| Stateful hidden-input echo (D-03) | Client-side show/hide of all 3 blocks | **Rejected by D-01** (locked). Would trivially satisfy D-03 but contradicts the locked decision. |
| Client-side total (D-08) | Server-side debounced HTMX recompute | **Rejected by D-08** (locked). Also would collide with the `oob-before-swap` typing guard (`sale_form.html:46`). |
| `sale-total.js` as a new file | Extending `price-cue.js` | **Recommend a new file.** `price-cue.js` is loaded on every page via `base.html:26`; the total logic is sale-only. A separate file mirrors the "standalone file, mirrors the htmx vendored-script line above" comment at `base.html:23-26`. Both files are ~25 lines; no bundler exists to merge them anyway. |

**Installation:**
```bash
# NONE. This phase adds zero packages.
# Verify the existing env instead:
uv run pytest -q
```

## Package Legitimacy Audit

**Not applicable — this phase installs no external packages.**

`pyproject.toml` is not modified. Every capability is delivered with dependencies already pinned and in use (`fastapi==0.139.*`, `jinja2==3.1.*`, `sqlalchemy==2.0.*`, vendored `htmx 2.0.10`). No registry lookup, slopsquatting exposure, or `postinstall` risk exists for this phase.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

> If any plan proposes adding a package, that is a scope deviation from CLAUDE.md §Development Tools and must be escalated, not silently installed.

## Architecture Patterns

### System Architecture Diagram

```
                         DESKTOP SALE FORM  (GET /sales/new)
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  #sale-form-wrap             │  ← swapped outerHTML on EVERY POST /sales
                    │                              │
   radio change ───►│  #customer-header            │  (lives OUTSIDE <form id="sale-form">;
   hx-get           │   ├─ radio: Новый/Существ./  │   inputs associate via form="sale-form")
   +hx-include      │   │        Аноним            │
        │           │   ├─ ACTIVE mode block       │
        │           │   └─ hidden echo of the      │
        │           │      2 INACTIVE modes        │
        │           │                              │
        ▼           │  <form id="sale-form">       │
  GET /sales/       │   └─ table.basket            │
  customer-mode     │       ├─ tr (code/name/qty/  │
        │           │       │    price)  ×N        │
        │           │       └─ tr batch-wrap ×N    │
        │           │   [NEW] #sale-total ◄────────┼──── sale-total.js (delegated)
        └──────────►│                              │      input | htmx:afterSettle | row-delete
     re-render      └──────────────┬───────────────┘
     active+hidden                 │ POST /sales (code[]/qty[]/price[]/batch_id[]/customer_id/confirm)
                                   ▼
                    ┌──────────────────────────────┐
                    │ sale_create (routes/sales.py)│
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │ register_sale (services)     │  ◄── SOLE money authority
                    │  ├─ per-line validate        │
                    │  ├─ batch owned? ────────────┼──► «Выберите партию.»  (guardrail)
                    │  ├─ oversell per BATCH ──────┼──► warn, ZERO writes   (guardrail)
                    │  ├─ below_minimum per line ──┼──► warn, ZERO writes   (guardrail)
                    │  ├─ record_operation ×N      │
                    │  └─ record_cash_movement ────┼──► cash credit         (guardrail)
                    └──────────────┬───────────────┘
                                   │ ONE commit
                                   ▼
                       Sale + N Operation + 1 CashMovement
                                   │
                                   ▼
                    recent_sales() ── outerjoin Sale ── outerjoin Customer
                                   │
                                   ▼
                    recent_sales.html  (oob refresh; [NEW] customer column)


                         MOBILE WIZARD  (GET /m/sales)
   <form id="sale-wizard-form">        ← persists across every step
     └─ #wizard-step                   ← innerHTML-swapped by EVERY step response
          Товар → Партия → Кол-во/Цена → Корзина ──POST /m/sales──► register_sale
                                            │
                                     [NEW] customer selector belongs HERE
                                     (same swap unit as the Оформить button)
```

### Recommended Project Structure

No new directories. Files touched:

```
app/
├── routes/
│   ├── sales.py               # + GET /sales/customer-mode; sale_create echoes mode state
│   └── mobile_sales.py        # + customer selector; :346 customer_id="" -> real value
├── services/
│   └── sales.py               # recent_sales(): + outerjoin Sale + Customer
├── static/
│   ├── price-cue.js           # UNCHANGED (precedent only)
│   └── sale-total.js          # NEW (SALE-02)
└── templates/
    ├── base.html              # + <script src="/static/sale-total.js" defer>
    ├── mobile_base.html       # + same script tag (mobile parity)
    ├── partials/
    │   ├── sale_customer.html # RESTRUCTURED into 3 radio-driven states
    │   ├── sale_form.html     # + #sale-total markup under table.basket
    │   ├── sale_row.html      # + recompute hook on the delete button
    │   └── recent_sales.html  # + Покупатель column (D-06 «Розница»)
    └── mobile_partials/
        ├── sale_customer.html # NEW (mobile-styled equivalent, D-04)
        └── sale_basket.html   # + selector include, total, recompute hook
tests/
├── test_sales.py              # desktop coverage
├── test_mobile_sales.py       # mobile coverage
└── test_sales_total.py        # NEW (see §Validation Architecture)
```

### Pattern 1: Stateful radio mode-swap (D-01 + D-03)

**What:** The radio's `hx-get` sends the *entire* current customer-header state; the server re-renders the chosen mode's visible fields and re-emits the other two modes' values as hidden inputs.

**When to use:** This is the ONLY reconciliation of D-01 (server fetches each block) with D-03 (switching preserves the other modes' data). Both are locked.

**Why the naive version fails — the load-bearing htmx rule:**

> "By default, an element that causes a request will include its value if it has one. If the element is a form it will include the values of all inputs within it. **Additionally, if the element causes a non-`GET` request, the values of all the inputs of the associated form will be included** (typically this is the nearest enclosing form, but could be different if e.g. `<button form="associated-form">` is used)."
> `[CITED: htmx.org/docs/#parameters]`

A radio with `hx-get` therefore sends **only its own value**. Without `hx-include`, the server cannot know what the operator typed, so the re-rendered block comes back empty → D-03 violated. `hx-include` is the documented remedy:

> "If you wish to include the values of other elements, you can use the `hx-include` attribute with a CSS selector of all the elements whose values you want to include in the request."
> `[CITED: htmx.org/docs/#parameters]`

**Example:**

```html
{# app/templates/partials/sale_customer.html — RESTRUCTURED (D-01/D-02/D-03/D-07)

   Root id="customer-header" stays the outerHTML swap target (unchanged
   contract from today's :13). Still lives OUTSIDE <form id="sale-form">;
   every input associates via form="sale-form".

   D-03: the two INACTIVE modes are re-emitted as hidden inputs below, and
   the radio's hx-include ships them back on the next switch — so a mode's
   state survives an arbitrary number of switches without ever being
   re-fetched or reset. #}
{% set mode = mode | default("existing") %}   {# D-02: default «Существующий» #}
<div id="customer-header" class="customer-header">

  {# The radio itself. hx-include is MANDATORY (htmx GET sends only its own
     value — docs §Parameters); without it the server cannot echo state back
     and D-03 breaks silently. #}
  <fieldset class="customer-mode"
            hx-get="/sales/customer-mode"
            hx-trigger="change"
            hx-include="#customer-header"
            hx-target="#customer-header"
            hx-swap="outerHTML"
            hx-sync="this:replace">
    <legend>Покупатель</legend>
    <label><input type="radio" name="customer_mode" value="new"
                  {% if mode == "new" %}checked{% endif %}> Новый</label>
    <label><input type="radio" name="customer_mode" value="existing"
                  {% if mode == "existing" %}checked{% endif %}> Существующий</label>
    <label><input type="radio" name="customer_mode" value="anon"
                  {% if mode == "anon" %}checked{% endif %}> Аноним</label>
  </fieldset>

  {# customer_id is the ONLY field register_sale reads (sales.py:396).
     Anonymous mode forces it empty -> register_sale's `customer_id or None`
     (services/sales.py:254) yields NULL. D-05: no «Аноним» customer row. #}
  <input type="hidden" id="customer-id-input" name="customer_id" form="sale-form"
         value="{{ customer_id if mode == 'existing' else '' }}">

  {% if mode == "existing" %}
    {# ACTIVE: search + picker + chip. Fixes the verified chip-loss bug —
       `selected` is now resolved server-side from customer_id on EVERY
       render, including the 422/oversell re-render. #}
    <div id="customer-selected" class="customer-chip"{% if not selected %} hidden{% endif %}>
      <span id="customer-chip-text">{% if selected %}Покупатель: {{ selected.name }} {{ selected.surname or '' }}{% endif %}</span>
      ...
    </div>
    <div id="customer-default"{% if selected %} hidden{% endif %}>
      <input type="search" id="customer-q" name="customer_q"
             value="{{ form.customer_q or '' }}"
             hx-get="/sales/customer-search" hx-trigger="input changed delay:300ms"
             hx-target="#customer-picker" hx-swap="outerHTML" hx-sync="this:replace">
      <div id="customer-picker" class="customer-picker"></div>
    </div>
  {% else %}
    {# INACTIVE echo — keeps «Существующий» state alive across switches (D-03) #}
    <input type="hidden" name="customer_id_keep" value="{{ customer_id or '' }}">
    <input type="hidden" name="customer_q" value="{{ form.customer_q or '' }}">
  {% endif %}

  {% if mode == "new" %}
    {# ACTIVE: D-07 — exactly 3 fields, no Phase-21 profile fields. #}
    <div class="customer-quick-create">
      <h2>Новый покупатель</h2>
      <input type="text" id="customer-name" name="name" value="{{ form.name or '' }}">
      <input type="text" id="customer-surname" name="surname" value="{{ form.surname or '' }}">
      <input type="text" id="customer-consultant" name="consultant_number"
             value="{{ form.consultant_number or '' }}">
      <button type="button" hx-post="/sales/customer"
              hx-include="#customer-header" hx-target="#customer-header"
              hx-swap="outerHTML" hx-disabled-elt="this">Добавить покупателя</button>
    </div>
  {% else %}
    {# INACTIVE echo — keeps «Новый» typed fields alive across switches (D-03) #}
    <input type="hidden" name="name" value="{{ form.name or '' }}">
    <input type="hidden" name="surname" value="{{ form.surname or '' }}">
    <input type="hidden" name="consultant_number" value="{{ form.consultant_number or '' }}">
  {% endif %}

  {# mode == "anon": no extra fields rendered at all (SALE-06 criterion 3). #}
</div>
```

```python
# app/routes/sales.py — NEW endpoint. Literal path, so it MUST stay declared
# before any parameterized /sales/{...} route (the file's :30-32 rule).

_CUSTOMER_MODES = ("new", "existing", "anon")   # allow-list, mirrors _SORT_MAP (customers.py:262)


def _customer_context(session: Session, mode: str, customer_id: str, form: dict) -> dict:
    """Shared context builder for every render of sale_customer.html.

    D-03: `form` carries ALL modes' values (active + echoed-inactive), so a
    mode switch never loses another mode's state. Called from
    sale_customer_mode, sale_customer_create, sale_new_page AND every
    sale_create branch — a single builder is what keeps the 422/oversell
    re-render from dropping the chip (the verified pre-existing bug).
    """
    # Untrusted client value -> allow-list, never echoed raw (T-14-18 precedent).
    mode = mode if mode in _CUSTOMER_MODES else "existing"
    selected = get_customer(session, customer_id) if (mode == "existing" and customer_id) else None
    # An id that no longer resolves degrades to "nothing selected" rather than
    # rendering a chip for a deleted customer (mirrors _build_lines' batch rule).
    return {
        "mode": mode,
        "customer_id": selected.id if selected else "",
        "selected": selected,
        "form": form,
        "errors": {},
    }


@router.get("/sales/customer-mode")
def sale_customer_mode(
    request: Request,
    customer_mode: str = "existing",
    customer_id: str = "",
    customer_id_keep: str = "",
    customer_q: str = "",
    name: str = "",
    surname: str = "",
    consultant_number: str = "",
    session: Session = Depends(get_session),
):
    """D-01: radio change -> server re-renders #customer-header for the new mode.

    D-03: every mode's state arrives via the radio's hx-include="#customer-header"
    and is echoed back — the two inactive modes as hidden inputs. Nothing is
    re-fetched or reset, so no switch can lose data.

    customer_id vs customer_id_keep: whichever mode is leaving supplies one of
    them (the visible hidden input, or the inactive echo). Coalesce, don't pick.
    """
    context = _customer_context(
        session,
        customer_mode,
        customer_id or customer_id_keep,
        {
            "customer_q": customer_q,
            "name": name,
            "surname": surname,
            "consultant_number": consultant_number,
        },
    )
    return templates.TemplateResponse(request, "partials/sale_customer.html", context)
```

**Anti-pattern to avoid:** giving the radio `hx-get` **without** `hx-include`. It looks correct in a single-mode manual test (the first switch works because the block is fresh) and silently violates D-03 only on the *second* switch back. This is the single most likely defect in the phase.

### Pattern 2: Client-side advisory total mirroring a server parser (D-08 + D-09)

**What:** One delegated listener, integer-cents string math, zero floats.

**The server's exact accept-set — verified by execution, not assumed:**

```
$ uv run python -c "from app.core import to_cents; ..."
'12,50'   -> 1250        '1 000'   -> ValueError
'12.50'   -> 1250        '12abc'   -> ValueError
'7'       -> 700         ''        -> ValueError
' 12,5 '  -> 1250        'inf'     -> ValueError
'+12.5'   -> 1250        'nan'     -> ValueError
'-5'      -> -500        'Infinity'-> ValueError
'12.505'  -> 1251        '12,5,0'  -> ValueError
'.5'      -> 50
'5.'      -> 500
'1_000'   -> 100000      # Decimal accepts PEP-515 underscores
'1e3'     -> 100000      # Decimal accepts exponents
'１２'     -> 1200        # Decimal accepts Unicode digits (fullwidth)
'٣'       -> 300         # Decimal accepts Arabic-Indic digits
```
`[VERIFIED: executed against app/core.py:28 in this session, 2026-07-17]`

**Consequence — CONTEXT.md's D-08 wording is incomplete.** D-08 describes `to_cents` as "comma-decimal, no space-thousands". That is right about spaces (`'1 000'` → ValueError ✓) but the accept-set is **wider** than D-08 implies: `Decimal(str)` also takes underscores, exponents, signs and Unicode digit scripts. Byte-exact JS parity is therefore not achievable in a one-liner, and **should not be attempted**.

**Recommended resolution (safe under D-09):** accept the strict common subset; anything else falls into D-09's "итог неполный" bucket. A false "incomplete" marker on `1e3` is harmless (advisory display, operator never types that); a *wrong number* would not be. Note the effective server domain for a sale price also **excludes negatives** — `services/sales.py:157` rejects `price_cents < 0` with `PRICE_ERROR` — so the JS regex correctly omits the sign.

**Qty parity is exact.** Server: `qty_text.isascii() and qty_text.isdigit()` then `int(...) > 0` (`services/sales.py:136-139`). The `isascii()` guard exists precisely to reject non-ASCII digits like `'²'` (WR-01 comment). JS `/^[0-9]+$/` + `> 0` is a byte-exact mirror.

**Example:**

```javascript
// app/static/sale-total.js — SALE-02 / D-08 / D-09
// One delegated listener: covers desktop basket rows, HTMX-added rows, and
// the mobile basket's hidden accumulator inputs with no re-initialisation
// (D-08, mirroring price-cue.js's architecture exactly).
//
// D-08/D-09: this total is ADVISORY. register_sale (app/services/sales.py:282)
// stays the sole authority on the charged amount. Nothing here is submitted.
//
// CLAUDE.md ("never use FLOAT for money"): parsing is string -> integer cents
// with NO float arithmetic anywhere, so unlike price-cue.js:19 there is zero
// rounding drift versus the server. price-cue.js can afford Math.round(
// parseFloat(...)) because it only compares; a displayed TOTAL cannot.
//
// Accept-set (verified against app/core.py:28 to_cents on 2026-07-17):
//   accepted here AND by server: "7", "12,50", "12.50", ".5", "5.", "12.505"
//   accepted by server, marked "неполный" here: "1e3", "1_000", "１２", "+12.5"
//   rejected by BOTH: "1 000", "12abc", "", "inf", "nan", "12,5,0"
// The narrow divergence is deliberate: an operator never types an exponent or
// a fullwidth digit, and D-09 makes a false "неполный" harmless while a wrong
// sum would not be. Negatives are omitted on purpose — services/sales.py:157
// rejects a negative sale price outright.
const MONEY_RE = /^(?:\d+(?:[.,]\d+)?|[.,]\d+)$/;
const QTY_RE = /^[0-9]+$/;   // exact mirror of isascii() and isdigit() (sales.py:137)

function moneyToCents(text) {
  const t = text.trim();
  if (!MONEY_RE.test(t)) return null;
  const parts = t.replace(",", ".").split(".");
  const whole = parts[0] === "" ? 0 : Number(parts[0]);
  const frac = ((parts[1] || "") + "000").slice(0, 3);
  let cents = whole * 100 + Number(frac.slice(0, 2));
  // ROUND_HALF_UP mirror (core.py:44) — ties away from zero: 12,505 -> 1251.
  if (Number(frac[2]) >= 5) cents += 1;
  return Number.isSafeInteger(cents) ? cents : null;
}

function qtyToInt(text) {
  const t = text.trim();
  if (!QTY_RE.test(t)) return null;
  const n = Number(t);
  return Number.isSafeInteger(n) && n > 0 ? n : null;   // sales.py:138 `qty <= 0`
}

function recalcSaleTotal() {
  const box = document.getElementById("sale-total");
  if (!box) return;                                 // not on a sale surface
  let cents = 0, units = 0, incomplete = false;
  for (const row of box.dataset.rows === "mobile"
       ? document.querySelectorAll("#wizard-basket .mobile-card")
       : document.querySelectorAll("#basket-rows tr")) {
    const codeEl = row.querySelector('[name="code[]"], [name="code_acc[]"]');
    const qtyEl = row.querySelector('[name="qty[]"], [name="qty_acc[]"]');
    const priceEl = row.querySelector('[name="price[]"], [name="price_acc[]"]');
    if (!qtyEl || !priceEl) continue;               // sale_row.html's batch-wrap <tr>
    // Row-counting mirrors non_blank_lines (services/sales.py:90-94): a row
    // counts if ANY of code/qty/price is non-blank. Same filter as the server,
    // so "неполный" appears exactly when the server would 422 that row.
    const anyFilled = [codeEl, qtyEl, priceEl].some(el => el && el.value.trim());
    if (!anyFilled) continue;
    const q = qtyToInt(qtyEl.value);
    const p = moneyToCents(priceEl.value);
    if (q === null || p === null) { incomplete = true; continue; }  // D-09
    cents += q * p;
    units += q;
  }
  // .textContent only — never innerHTML (customer_picker.html:1-12 house rule).
  box.querySelector("#sale-total-amount").textContent = formatCents(cents);
  box.querySelector("#sale-total-units").textContent = String(units);
  box.querySelector("#sale-total-warning").hidden = !incomplete;
}

// Mirror of core.py:49 format_cents — comma separator, 2 fraction digits.
function formatCents(c) {
  const sign = c < 0 ? "-" : "";
  const a = Math.abs(c);
  return sign + Math.trunc(a / 100) + "," + String(a % 100).padStart(2, "0");
}

document.addEventListener("input", function (e) {
  const n = e.target.getAttribute && e.target.getAttribute("name");
  if (n === "qty[]" || n === "price[]" || n === "code[]") recalcSaleTotal();
});
// See Pitfall 2: an htmx swap re-renders echoed values and fires NO input event.
document.body.addEventListener("htmx:afterSettle", recalcSaleTotal);
// See Pitfall 2: row delete is a plain DOM removal — no input, no htmx event.
window.recalcSaleTotal = recalcSaleTotal;
```

```html
{# app/templates/partials/sale_form.html — placed directly under table.basket
   (SALE-02 criterion 2), INSIDE <form id="sale-form"> so it travels with the
   #sale-form-wrap swap. #}
    </table>
    <p id="sale-total" class="sale-total">
      Итого: <strong id="sale-total-amount">0,00</strong> ·
      <span id="sale-total-units">0</span> шт.
      <span id="sale-total-warning" class="muted" hidden>итог неполный</span>
    </p>
```

### Pattern 3: Mobile selector placement (D-04)

**What:** Put the mobile customer selector on the **Корзина** screen, in the same `#wizard-step` innerHTML unit as the «Оформить продажу» button.

**Why this exact placement:** `mobile_pages/sales.html:11-15` shows `<form id="sale-wizard-form">` persists while `#wizard-step` is innerHTML-swapped by every step response. A selector placed on an *earlier* step would be destroyed by the next step's swap unless every subsequent step re-echoes its state as hidden inputs (the `code_acc[]` carry-forward pattern, `sale_step_product.html:13-16`) — four more echo points, four more chances to drop state.

On the Корзина screen there is **no carry-forward needed at all**: `sale_basket.html:41-43`'s «Оформить продажу» is `hx-post` — a **non-GET** request — so htmx includes the enclosing `#sale-wizard-form`'s inputs automatically `[CITED: htmx.org/docs/#parameters]`. That is exactly how `code_acc[]` reaches `mobile_sale_create` today. The selector's `customer_id` rides the same mechanism for free.

**Then the one-line unlock:**

```python
# app/routes/mobile_sales.py — mobile_sale_create signature gains the param
    customer_id: str = Form(""),        # D-04: supersedes the old hardcode
    ...
        result, errors = register_sale(
            session,
            customer_id=customer_id,    # was: "" — D-04: no mobile customer picker this phase
            codes=code_acc,
            ...
```

`[VERIFIED: app/routes/mobile_sales.py:346 currently reads `customer_id="",  # D-04: no mobile customer picker this phase`]`

**Caveat that makes or breaks it:** if the mobile selector's mode radio uses `hx-get` (mirroring desktop D-01), it hits the same GET-excludes-form rule — and worse, its swap target sits *inside* `#wizard-step` alongside the basket's hidden `code_acc[]` inputs. Scope the mode swap to its own `#m-customer-header` root (`hx-target="#m-customer-header" hx-swap="outerHTML"`), never to `#wizard-step`, or the basket arrays are wiped. See §Common Pitfalls 3.

### Pattern 4: Portable customer outerjoin (SALE-07 / D-06)

**What:** Extend `recent_sales` with the join `export.py` already proves.

**Example:**

```python
# app/services/sales.py — add Customer to the existing models import (:35)
from app.models import Batch, Customer, Operation, Product, Sale


def recent_sales(session: Session, limit: int = 10) -> list[dict]:
    """Last N sale ops joined to their products + buyer, newest first (mirrors D-04).

    SALE-07/D-06: the double outerjoin (NOT join) is load-bearing — Sale.customer_id
    is nullable (models.py:409, "walk-in sale is valid") and Operation.sale_id is
    nullable for legacy rows (models.py:318). An inner join would silently DROP
    every walk-in sale from the list instead of labelling it «Розница». Byte-for-byte
    the shape export.py:118-125 already ships.

    Portable ORM constructs only (CLAUDE.md): no raw SQL, no relationship() —
    the FK is joined manually here, per the house rule at models.py:381-383.
    """
    rows = session.execute(
        select(Operation, Product, Customer)
        .join(Product, Operation.product_id == Product.id)
        .outerjoin(Sale, Operation.sale_id == Sale.id)
        .outerjoin(Customer, Sale.customer_id == Customer.id)
        .where(Operation.type == "sale")
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
        .limit(limit)
    ).all()
    return [
        {"op": op, "product": product, "customer": customer}
        for op, product, customer in rows
    ]
```

```html
{# app/templates/partials/recent_sales.html — new column after «Название».
   Customer names are untrusted stored text (T-4-01): autoescape only, never |safe. #}
        <th>Покупатель</th>
...
        <td>{% if r.customer %}{{ r.customer.name }} {{ r.customer.surname or '' }}
            {% else %}<span class="muted">Розница</span>{% endif %}</td>
```

`.muted` already exists (`style.css:230`) — D-06 needs **no new CSS**.

### Anti-Patterns to Avoid

- **Radio `hx-get` without `hx-include`:** silently breaks D-03 on the second switch. See Pattern 1.
- **Inner `join` to `Customer` in `recent_sales`:** drops every walk-in sale from the list. Use `outerjoin` twice.
- **Floats in the total:** violates CLAUDE.md §What NOT to Use. Use the string→cents parser.
- **Rendering the total via `innerHTML`:** breaks the `.textContent`-only house rule (`customer_picker.html:1-12`) and would be an XSS vector if product names ever entered the string.
- **Targeting `#wizard-step` from the mobile mode radio:** wipes the `code_acc[]` basket. Target `#m-customer-header`.
- **Adding Phase-21 profile fields to the sale form:** D-07 explicitly forbids it; `create_customer`'s `contacts=None` default exists to keep this call site 3-field (`customers.py:135-141`).
- **Creating an "Аноним" `Customer` row:** D-05 forbids it. `customer_id = NULL` is the contract.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Customer search by name/surname/consultant number | A new query, or SQL `LOWER()`/`LIKE` | `customers.py:232 search_customers` | SQLite `lower()`/`LIKE` **cannot fold Cyrillic** (`customers.py:5-7`). The `search_lc` shadow column + Python `str.lower()` is the established fix. Rebuilding it in SQL produces a search that silently misses «Анна» vs «анна». |
| Match highlighting in the picker | Manual string slicing into HTML | `customers.py:246 customer_search_view` + `catalog.split_match` | Already returns `name_seg`/`consultant_seg` 3-tuples; `customer_picker.html:27` renders `<mark>` as literal template HTML, never `|safe`. Hand-rolling reintroduces an XSS vector. |
| Money parsing on the server | A new parser | `core.py:28 to_cents` | Sole sanctioned conversion point (`core.py:1-5`). Handles ROUND_HALF_UP and rejects inf/nan. |
| Money rendering | `f"{cents/100:.2f}"` | `cents` Jinja filter (`routes/__init__.py:18` → `core.py:49`) | Comma separator + no float. A float divide reintroduces the exact bug CLAUDE.md bans. |
| Customer creation + validation | Direct `session.add(Customer(...))` | `customers.py:121 create_customer` | Maintains `search_lc` (:166) — skip it and the new customer is **invisible to the autocomplete forever**. Also enforces the WR-05 max-length guards that mirror the declared column widths. |
| Sale totals / oversell / batch validation | Any recomputation | `services/sales.py:97 register_sale` | Single-write-path contract (`services/sales.py:22-26`). It is the sole authority; the D-08 total must never feed it. |
| Preserving typed values across an htmx swap | A custom JS state cache / `sessionStorage` | Server-side hidden-input echo (Pattern 1) | `hx-preserve` is documented as lossy for `<input type="text">` and still requires the element in the response `[CITED: htmx.org/attributes/hx-preserve/]`. A JS cache would be a fourth source of truth for customer state. |
| Batch pick / oversell / cash credit | Anything | Untouched `register_sale` | Criterion 5 is a pure regression guard. |

**Key insight:** every "new" capability in this phase already has a shipped counterpart one layer away — the customer search (Phase 4), the delegated-listener JS (Phase 18), the customer outerjoin (Phase 6 export). The phase is 90% wiring and 10% new code. The failure mode is not "missing library" but "re-implemented an existing helper slightly differently and diverged."

## Common Pitfalls

### Pitfall 1: Assuming SALE-01 is unbuilt and restructuring the basket table

**What goes wrong:** The requirement text "Sale form is a code / name / quantity / sale-price table" reads like greenfield work. An executor rebuilds `sale_form.html`'s table and destroys the HTMX guard web around it.
**Why it happens:** SALE-01 is listed as `[ ] Pending` in REQUIREMENTS.md:52 even though `sale_form.html:47-70` already renders exactly that table with headers `Код / Название / Кол-во / Цена продажи`. CONTEXT §Phase Boundary says so explicitly: "No basket table restructuring — SALE-01's code/name/qty/price shape is already shipped."
**How to avoid:** Treat SALE-01 as a **verification-only** requirement. The only edit to `sale_form.html`'s table region is inserting the `#sale-total` element after `</table>`; the only edit to `sale_row.html` is the delete-button recompute hook.
**Warning signs:** any diff that touches `<thead>` in `sale_form.html`, or that renames `code[]`/`qty[]`/`price[]`/`batch_id[]`.

### Pitfall 2: The total goes stale because two update paths fire no `input` event

**What goes wrong:** The total is correct while typing, then silently wrong after (a) a 422/oversell re-render, or (b) deleting a row.
**Why it happens:** Two verified gaps.
  - (a) `sale_create`'s 422/oversell branches re-render `#sale-form-wrap` with the operator's values echoed by `_build_lines` (`routes/sales.py:434-441`). The DOM changes; **no `input` event fires**. A delegated `input`-only listener (the `price-cue.js` shape) never recomputes. `price-cue.js` gets away with this because the *server* re-renders its cue authoritatively (`sale_row.html:41` stamps `data-ref-cents`); there is no server-rendered total to fall back on.
  - (b) `sale_row.html:49` deletes a row with `hx-on:click="this.closest('tr').remove(); ..."` — a plain DOM removal. No `input` event, and **no htmx swap event either**. Same on mobile: `sale_basket.html:30` `hx-on:click="this.closest('.mobile-card').remove()"`.
**How to avoid:** three triggers, not one — `input` (delegated), `htmx:afterSettle` (on `document.body`, covers path a), and an explicit call appended to both delete buttons (covers path b):
```html
{# sale_row.html:49 — append the recompute; guard for the script not being loaded #}
hx-on:click="this.closest('tr').remove();
             var w=document.getElementById('{{ batch_wrap_id }}'); if (w) w.remove();
             if (window.recalcSaleTotal) window.recalcSaleTotal()"
```
**Warning signs:** a total that only ever grows; a total that survives «Удалить строку» unchanged.

### Pitfall 3: An htmx GET silently drops the form it appears to be inside

**What goes wrong:** A mode radio or picker uses `hx-get`, and everything *else* in the enclosing form vanishes from the request — so the server re-renders a block with empty values and the operator's data is gone.
**Why it happens:** htmx auto-includes the enclosing form **only on non-GET** `[CITED: htmx.org/docs/#parameters]`. This is not hypothetical — it is a **live latent defect in this repo**:

`mobile_partials/batch_card_picker.html:48-54` fires `hx-get="{{ pick_url }}"` with only `hx-vals='{"batch_id":…, "code":…}'` and **no `hx-include`**, targeting `#batch-wrap` with `outerHTML`. For the sale wizard `pick_url` is `/m/sales/step/batch`, and `#batch-wrap` (`sale_step_batch.html:5-10`) is precisely where the four `*_acc[]` hidden inputs live. So the request omits the accumulators, `mobile_sale_step_batch` reads `code_acc: list[str] = Query([], ...)` as empty, and the re-rendered `#batch-wrap` contains **no accumulator inputs at all** — a multi-line mobile basket loses its earlier lines when the operator re-taps a batch card on a later line.

Verified in this session:
```
GET /m/sales/step/batch?code=TEST-001   (no acc params, as the browser sends it)
  STATUS: 200
  code_acc hidden input rendered: False
```
Every other mobile wizard back/forward control does this correctly with `hx-include="closest form"` (`writeoff_step_batch.html:20`, `receipts_step_batch.html:53`, `corrections_step_batch.html:24`). The sale wizard's card tap is the outlier.

**How to avoid:** For **new** work, put `hx-include="closest form"` (or an explicit selector) on every non-POST htmx control that needs sibling state. For the **pre-existing** defect: it is out of this phase's literal scope, but D-04 puts the mobile wizard's state-preservation squarely on the table and Pattern 3's placement means `customer_id` would ride the *same* `#wizard-step` DOM. **Recommend the planner add a small task** to add `hx-include="closest form"` to `batch_card_picker.html`'s tap (it is a shared partial — Sale/Write-off/Correction/Transfer all consume it, so the change needs a regression pass across `test_mobile_*`), or explicitly defer it with a written note. Do not let it be discovered as "the customer selector broke the basket."
**Warning signs:** any `hx-get`/`hx-delete` inside `#sale-wizard-form` without `hx-include`; a mobile basket that loses lines.

### Pitfall 4: `recent_sales` has two callers, and one of them is the returns page

**What goes wrong:** The SALE-07 column is added and `/returns` breaks or renders a ragged table.
**Why it happens:** `recent_sales` is imported by **both** `routes/sales.py:23` and `routes/returns.py:18` (used at `returns.py:157`), and `recent_sales.html` is included from **three** places: `pages/sale_form.html:8`, `partials/sale_form.html:84` (the oob refresh), and `partials/return_form.html:51`. Adding `"customer"` to the dict is backward-compatible; adding a `<th>`/`<td>` pair changes the table on the returns page too.
**How to avoid:** Add both `<th>` and `<td>` in the same edit (a `<th>`-only change yields a ragged table), and run `tests/test_returns.py` in the same wave. The extra column on `/returns` is consistent, not a bug — but confirm no test asserts an exact column count.
**Warning signs:** `test_returns.py` failures; a `<th>` count that differs from the `<td>` count.

### Pitfall 5: Regressing a guardrail while restructuring the customer header (criterion 5)

**What goes wrong:** Oversell / batch-required / cash-credit stops firing after the rebuild.
**Why it happens:** All three live in `register_sale` and are reached only if `sale_create` keeps passing the same arrays. The warning UI reaches back into the basket form by **id**, from outside it:
  - `sale_oversell.html:17-20`: `<button type="submit" form="sale-form" hx-post="/sales" hx-vals='{"confirm":"1"}' hx-target="#sale-form-wrap">`. This depends on the ids `sale-form` and `sale-form-wrap` surviving verbatim, and on the `form="sale-form"` association re-POSTing the basket **plus** the customer header's `customer_id` (which is also `form="sale-form"`).
  - `services/sales.py:431` checks **both** `oversell` **and** `below_minimum` keys — the comment at `routes/sales.py:425-430` explains why a below-minimum-only basket must not fall through.
  - The cash credit is `finance.record_cash_movement(..., commit=False)` inside `register_sale`'s single transaction (`services/sales.py:284-296`). Nothing in this phase should touch it.
**How to avoid:** Do not rename `#sale-form`, `#sale-form-wrap`, `#customer-header`, or `#customer-id-input`. Keep `form="sale-form"` on every customer-header input (including the new hidden echoes — **or** deliberately omit it on the echo-only inputs so they don't pollute the POST; either is fine, but be deliberate: `sale_create` ignores unknown form fields, so pollution is harmless but noisy).
**Warning signs:** `test_web_sale_oversell_shows_warning_and_confirm_writes` (test_sales.py:615), `test_web_sale_below_minimum_shows_warning_and_confirm_writes` (:648), `test_web_sale_both_warnings_stack_and_single_confirm_resolves_both` (:684) — these three are the criterion-5 tripwire and must stay green untouched.

### Pitfall 6: Reintroducing the typed-value clobber that the swap guards exist to prevent

**What goes wrong:** A lookup/mode response overwrites a value the operator is mid-way through typing.
**Why it happens:** `sale_form.html:45-46` carries two guards on `<form id="sale-form">`:
```
hx-on::before-swap="if (event.detail.target.id.startsWith('name') && …value.trim()) event.detail.shouldSwap = false"
hx-on::oob-before-swap="if (event.detail.target.id.startsWith('price') && …value.trim()) event.detail.shouldSwap = false"
```
These are **prefix** matches on `name*` / `price*`. The new-customer field `id="customer-name"` does **not** start with `name`, so it is unaffected — but any new element id beginning with `name` or `price` inside this form would be caught by a guard written for basket rows. Also note the guards are declared on `#sale-form`, while `#customer-header` sits **outside** that form (`sale_customer.html:1-6`) — so mode swaps targeting `#customer-header` do not pass through these guards at all. That is correct and should stay that way.
**How to avoid:** Do not give any new element an id starting with `name` or `price`. Keep `#customer-header` outside `<form id="sale-form">`. Do not "tidy" the guards — 18-REVIEW WR-02 documents an accepted limitation there that is deliberate (`sale_form.html:32-39`).
**Warning signs:** the colour cue stopping on basket rows; `test_sales_search.py` failures.

### Pitfall 7: The verified chip-loss bug re-shipping in the rebuild

**What goes wrong:** The operator picks «Анна Иванова», the basket 422s on a bad qty, and the form comes back showing the *search box* as if nobody is selected — yet the sale still gets attributed to Анна on the retry.
**Why it happens:** `sale_create`'s error branches pass only `{"customer_id": customer_id}` into the context (`routes/sales.py:417, 435, 447`). `sale_customer.html` renders the chip on `{% if selected %}` (:17) and `selected` is **never set** on that path → the chip is `hidden`, `#customer-default` is shown, but `#customer-id-input` still carries the id (:14-15).

Verified in this session (POST /sales with `qty[]=0` and a valid `customer_id`):
```
STATUS: 422
customer_id survives in hidden input: True
chip text 'Покупатель:' present:  False
customer name present:            False
chip block hidden:                True
```
This is a **silent mis-attribution surface**: the UI says "no customer", the database says otherwise.
**How to avoid:** route every render of `sale_customer.html` through the single `_customer_context()` builder in Pattern 1, which resolves `selected` from `customer_id` server-side on **every** path — `sale_new_page`, `sale_customer_mode`, `sale_customer_create`, and all four `sale_create` branches. This is why Pattern 1 puts the builder in the route module rather than inlining context dicts.
**Warning signs:** any `sale_create` branch whose context dict still hand-writes `"customer_id": customer_id` without `selected`/`mode`/`form`.

## Code Examples

All patterns above are drawn from shipped code in this repo. Consolidated references:

### Delegated advisory listener (the D-08 precedent, verbatim)
```javascript
// Source: app/static/price-cue.js:15-23 (Phase 18, shipped)
document.addEventListener("input", function (event) {
  const field = event.target;
  const ref = field.dataset ? field.dataset.refCents : null;
  if (!ref) return;                       // no reference → no cue (D-07: the MAIN path)
  const cents = Math.round(parseFloat(field.value.trim().replace(",", ".")) * 100);
  field.classList.remove("price-below", "price-above");
  if (!Number.isFinite(cents) || cents === Number(ref)) return;
  field.classList.add(cents < Number(ref) ? "price-below" : "price-above");
});
```
> Note the file's own header: "this is NOT client-side money math. The cue is advisory — it never parses for submission, computes, or persists." `sale-total.js` **does** compute, so it must be stricter — hence the integer-cents parser in Pattern 2 rather than this `parseFloat`.

### The customer outerjoin (the SALE-07 precedent, verbatim)
```python
# Source: app/services/export.py:118-125 (Phase 6, shipped)
query = (
    select(Operation, Product, Sale, Customer)
    .join(Product, Operation.product_id == Product.id)
    .outerjoin(Sale, Operation.sale_id == Sale.id)
    .outerjoin(Customer, Sale.customer_id == Customer.id)
    .where(Operation.type == "sale")
    .order_by(Operation.created_at)
)
```

### Safe client-side selection without building HTML (the SALE-04 precedent, verbatim)
```html
<!-- Source: app/templates/partials/customer_picker.html:21-28 (Phase 4, shipped) -->
<button type="button" class="secondary"
        data-id="{{ customer.id }}" data-name="{{ customer.name }}"
        data-surname="{{ customer.surname or '' }}"
        hx-on:click="document.getElementById('customer-id-input').value = this.dataset.id;
          document.getElementById('customer-chip-text').textContent = 'Покупатель: ' + this.dataset.name + (this.dataset.surname ? (' ' + this.dataset.surname) : '');
          document.getElementById('customer-selected').hidden = false;
          document.getElementById('customer-default').hidden = true;">
```
> `.dataset` in, `.textContent` out — never `innerHTML`, never `|safe`. Preserve this exactly when the picker moves inside the «Существующий» radio block. **However:** these handlers hard-code the ids `customer-id-input` / `customer-chip-text` / `customer-selected` / `customer-default`. If the mobile selector (D-04) reuses `customer_picker.html`, those ids collide across the two trees. Either keep the desktop ids and give mobile its own picker partial, or parameterise the ids the way `batch_card_picker.html:41-42` parameterises `batch_input_name`/`batch_target` with `| default(...)`.

### Untrusted client value → allow-list before echo (the mode-param precedent)
```python
# Source: app/routes/sales.py:36-40 (CR-01, shipped)
# CR-01: row_id is echoed unescaped into an hx-on::load JS-evaluated
# attribute (sale_row.html), so it must be constrained to the exact shape
# new_id() produces (a UUID4 string) before it is ever trusted.
_ROW_ID_RE = re.compile(r"[0-9a-fA-F-]{1,36}")
```
> `customer_mode` is echoed into `{% if mode == "new" %}` comparisons only (never into an attribute), so a tuple allow-list (`_CUSTOMER_MODES`) is the proportionate guard — mirroring `customers.py:262 _SORT_MAP`'s allow-list rather than this regex.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sale customer = combined search + always-visible quick-create + implicit walk-in | Explicit 3-way radio, one mode visible at a time | This phase (D-01) | `sale_customer.html` restructured; walk-in becomes an explicit choice, not an absence of choice |
| Mobile sale always walk-in (`customer_id=""`) | Mobile has full parity with desktop | This phase (D-04) | `mobile_sales.py:346` hardcode removed; supersedes the old Phase-11 "D-04: no mobile customer picker this phase" |
| No total until submit | Live advisory total under the basket | This phase (D-08) | New `sale-total.js`; server stays authoritative |
| Recent sales show product only | Recent sales show buyer, «Розница» when NULL | This phase (D-06) | `recent_sales` gains 2 outerjoins; Phase 23 DASH-05 will consume the same shape |

**Deprecated/outdated within this repo:**
- The Phase-11 note `# D-04: no mobile customer picker this phase` (`mobile_sales.py:346`) — **explicitly superseded** by Phase 22 D-04. Delete the comment along with the hardcode; leaving it will mislead the next reader.
- `htmx 4.0.0-beta5` exists upstream but CLAUDE.md §What NOT to Use pins 2.0.10 stable. Do not upgrade in this phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The «Новый» mode keeps the existing explicit «Добавить покупателя» button (creating the customer via `POST /sales/customer` *before* the sale POST), rather than creating the customer implicitly during `POST /sales` | Pattern 1, Open Q1 | If the operator expects to just fill 3 fields and hit «Оформить продажу», the sale saves with `customer_id=""` → walk-in, and the typed customer is **silently lost**. Medium-high UX risk; CONTEXT does not settle it. **Needs user confirmation.** |
| A2 | A false «итог неполный» on exotic-but-server-valid input (`1e3`, `1_000`, fullwidth `１２`) is acceptable | Pattern 2 | Operator sees "неполный" on a value the server would accept. Very low — these are not realistic manual entries, and D-09 makes the marker advisory. |
| A3 | Adding a Покупатель column to the shared `recent_sales.html` is desirable on `/returns` too, not just `/sales/new` | Pitfall 4 | A column the returns page didn't ask for. Low — it is consistent, and the alternative (a `{% if %}` flag) adds branching. Flagged for the planner to confirm. |
| A4 | The mobile selector belongs on the Корзина screen rather than as a 4th wizard step | Pattern 3 | If the operator expects to choose the buyer *first*, placement is wrong. Low-medium — CONTEXT leaves placement to Claude's discretion, but "Корзина" is the only step where no carry-forward is needed. |
| A5 | `batch_card_picker.html`'s missing `hx-include` is a real pre-existing basket-loss bug in the browser (verified server-side; the htmx GET behavior is documented but not exercised in a real browser here) | Pitfall 3 | If htmx behaves differently in practice, the recommended fix is a harmless no-op. Low. |

## Open Questions

1. **Does «Новый» mode create the customer on sale submit, or via the existing button? (drives A1)**
   - What we know: D-07 pins the field set to 3 and says "keeps exactly the 3 fields it has today", implying today's flow. `POST /sales/customer` (`sales.py:343`) + `test_web_customer_quick_create_returns_chip` (test_sales.py:756) already ship and work. `sale_create` (`sales.py:390-398`) reads **only** `customer_id` — it does not look at `name`/`surname`/`consultant_number` at all.
   - What's unclear: whether the operator considers "filled the 3 fields + pressed Оформить продажу" sufficient. With today's code that silently produces a **walk-in sale**.
   - Recommendation: **keep the explicit button** (smallest change, reuses tested endpoints, keeps `register_sale`'s signature untouched). But add a guard: if `customer_mode == "new"` and `customer_id` is empty and any of the 3 fields is non-blank, `sale_create` should return 422 with a Russian error ("Сначала нажмите «Добавить покупателя»") rather than silently writing a walk-in sale. **Confirm with the operator during planning.**

2. **Fix or defer the `batch_card_picker.html` `hx-include` gap? (drives Pitfall 3 / A5)**
   - What we know: verified that the endpoint renders no accumulator inputs when the acc params are absent, and that htmx does not send them on a GET. Every sibling wizard uses `hx-include="closest form"`; the sale card tap does not.
   - What's unclear: whether the operator has ever hit it (it needs a ≥2-line mobile basket plus a batch re-tap on a later line).
   - Recommendation: fix it in this phase — it is a 1-attribute change, it sits on D-04's exact blast radius, and it is far cheaper than debugging it after the customer selector lands nearby. It is a **shared** partial (Sale/Write-off/Correction/Transfer), so pair it with a full `test_mobile_*` run. If the planner prefers to keep scope tight, defer it explicitly with a written note rather than leaving it undiscovered.

3. **Does the mobile picker reuse `customer_picker.html` or get its own partial?**
   - What we know: CONTEXT marks this Claude's discretion and notes a mobile-specific partial is "expected, not a deviation". `customer_picker.html`'s `hx-on:click` hard-codes four desktop element ids.
   - What's unclear: nothing blocking.
   - Recommendation: **own mobile partial**. Reuse would require parameterising four ids (the `batch_card_picker.html` `| default(...)` pattern) and risks id collisions; a mobile-styled card list matches the established `mobile_partials/` tree and the `.mobile-card` idiom.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Everything | ✓ | 3.13 (`requires-python = ">=3.13"`) | — |
| uv | Test/run entry point | ✓ | Verified (`uv run pytest` executed successfully) | — |
| pytest | All new coverage | ✓ | 9.1.* — **808 tests pass, 169s** | — |
| httpx | `TestClient` | ✓ | 0.28.* | — |
| SQLite | Data layer | ✓ | bundled | — |
| htmx (vendored) | All UI interaction | ✓ | 2.0.10 (`version:"2.0.10"` in `app/static/htmx.min.js`) | — |
| ruff | Lint gate | ✓ | 0.15.*, `line-length = 100` | — |
| Internet | — | **Not required** | — | App is offline-by-design; nothing in this phase changes that |

**Missing dependencies with no fallback:** none
**Missing dependencies with fallback:** none

**Baseline captured this session:** `uv run pytest -q` → `808 passed, 3 warnings in 169.23s`. The 3 warnings are pre-existing `SAWarning`s in `test_returns.py` (identity-key conflicts at `test_returns.py:316`) — not introduced by this phase and not a gate.

> Note: bare `python -m pytest` **fails** (`ModuleNotFoundError: No module named 'sqlalchemy'`) — the deps live in the uv-managed `.venv`. Every command in this phase must be prefixed `uv run`.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* (`pyproject.toml:20`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `pythonpath = ["."]` |
| Quick run command | `uv run pytest tests/test_sales.py tests/test_mobile_sales.py tests/test_sales_search.py -q` (**23.65s measured, 87 tests**) |
| Full suite command | `uv run pytest -q` (**169.23s measured, 808 tests**) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SALE-01 | Basket table renders `Код/Название/Кол-во/Цена продажи` headers (regression) | web | `uv run pytest tests/test_sales.py::test_web_sale_page_renders_form -x` | ✅ (:570) — extend with header assertions |
| SALE-02 | `#sale-total` element present under `table.basket` with amount + unit slots | web | `uv run pytest tests/test_sales_total.py -x` | ❌ Wave 0 |
| SALE-02 | `sale-total.js` loaded on desktop **and** mobile shells | web | `uv run pytest tests/test_sales_total.py -k script -x` | ❌ Wave 0 |
| SALE-02 | 422 re-render still carries `#sale-total` (Pitfall 2a) | web | `uv run pytest tests/test_sales_total.py -k rerender -x` | ❌ Wave 0 |
| SALE-02 | Delete button carries the `recalcSaleTotal` hook (Pitfall 2b) | web | `uv run pytest tests/test_sales_total.py -k delete_hook -x` | ❌ Wave 0 |
| SALE-02/D-09 | Parse parity: JS accept-set vs `to_cents` documented boundaries | unit | `uv run pytest tests/test_core.py -k to_cents -x` | ✅ extend — pin `'1 000'`/`'12abc'` rejection + `'12.505'→1251` as the JS contract |
| SALE-02 | Live sum updates as lines are filled (browser behavior) | **manual-only** | — | Justification: no JS runtime in the suite (no jsdom/Playwright; CLAUDE.md forbids an npm toolchain). Server-side tests assert *markup + wiring presence*; the arithmetic is verified by UAT. Mitigation: the parser is pure and could be ported to a Python mirror test if drift is ever suspected. |
| SALE-03 | `GET /sales/new` renders the 3 radios, «Существующий» checked (D-02) | web | `uv run pytest tests/test_sales.py -k customer_mode_default -x` | ❌ Wave 0 |
| SALE-03 | `GET /sales/customer-mode?customer_mode=new` renders the 3-field block | web | `uv run pytest tests/test_sales.py -k customer_mode_new -x` | ❌ Wave 0 |
| SALE-03/D-03 | Switching to `new` then back to `existing` preserves both modes' values | web | `uv run pytest tests/test_sales.py -k customer_mode_roundtrip -x` | ❌ Wave 0 — **the phase's highest-risk test** |
| SALE-03 | Unknown `customer_mode` falls back to `existing`, never echoed raw | web | `uv run pytest tests/test_sales.py -k customer_mode_allowlist -x` | ❌ Wave 0 |
| SALE-04 | Autocomplete matches by name, surname, **and** consultant number | web | `uv run pytest tests/test_sales.py::test_web_customer_search_returns_rows -x` | ✅ (:749) — extend for surname + consultant_number |
| SALE-04 | Picking a match fills the chip and hides the search (markup contract) | web | `uv run pytest tests/test_sales.py -k picker_data_attrs -x` | ❌ Wave 0 |
| SALE-04 | **422 re-render keeps the chip visible** (Pitfall 7, verified bug) | web | `uv run pytest tests/test_sales.py -k chip_survives_422 -x` | ❌ Wave 0 — **regression test for a live defect** |
| SALE-05 | Inline new-customer has exactly 3 fields, no Phase-21 profile fields (D-07) | web | `uv run pytest tests/test_sales.py -k new_customer_field_set -x` | ❌ Wave 0 |
| SALE-05 | Quick-create returns a chip carrying the new id | web | `uv run pytest tests/test_sales.py::test_web_customer_quick_create_returns_chip -x` | ✅ (:756) |
| SALE-06 | Anonymous mode renders no extra fields | web | `uv run pytest tests/test_sales.py -k customer_mode_anon -x` | ❌ Wave 0 |
| SALE-06 | Anonymous submit writes `Sale.customer_id IS NULL` | unit | `uv run pytest tests/test_sales.py::test_customer_link_walkin_customer_id_null -x` | ✅ (:255) |
| SALE-07 | Recent sales renders buyer first+last name | web | `uv run pytest tests/test_sales.py -k recent_sales_customer_column -x` | ❌ Wave 0 |
| SALE-07/D-06 | Walk-in sale renders muted «Розница», not blank | web | `uv run pytest tests/test_sales.py -k recent_sales_retail_label -x` | ❌ Wave 0 |
| SALE-07 | `recent_sales` outerjoin does not drop walk-in rows | unit | `uv run pytest tests/test_sales.py -k recent_sales_includes_walkin -x` | ❌ Wave 0 — guards the inner-join anti-pattern |
| SALE-07 | `/returns` recent-sales include still renders (Pitfall 4) | web | `uv run pytest tests/test_returns.py -q` | ✅ existing suite |
| D-04 | Mobile Корзина renders the 3-way selector | web | `uv run pytest tests/test_mobile_sales.py -k customer_selector -x` | ❌ Wave 0 |
| D-04 | `POST /m/sales` with `customer_id` links the sale (hardcode gone) | web | `uv run pytest tests/test_mobile_sales.py -k mobile_links_customer -x` | ❌ Wave 0 |
| D-04 | `POST /m/sales` without `customer_id` still writes a walk-in | web | `uv run pytest tests/test_mobile_sales.py -k mobile_walkin -x` | ❌ Wave 0 |
| D-04 | Mobile selector swap does not wipe `code_acc[]` (Pitfall 3) | web | `uv run pytest tests/test_mobile_sales.py -k acc_survives -x` | ❌ Wave 0 |
| **Criterion 5** | Oversell warning still fires, confirm still writes | web | `uv run pytest tests/test_sales.py::test_web_sale_oversell_shows_warning_and_confirm_writes -x` | ✅ (:615) |
| **Criterion 5** | Below-minimum still fires, confirm still writes | web | `uv run pytest tests/test_sales.py::test_web_sale_below_minimum_shows_warning_and_confirm_writes -x` | ✅ (:648) |
| **Criterion 5** | Both warnings stack; one confirm resolves both | web | `uv run pytest tests/test_sales.py::test_web_sale_both_warnings_stack_and_single_confirm_resolves_both -x` | ✅ (:684) |
| **Criterion 5** | Batch selection required; missing pick → 422 | web | `uv run pytest tests/test_sales.py::test_web_sale_missing_batch_pick_returns_422 -x` | ✅ (:1081) |
| **Criterion 5** | Batch pick survives the 422 re-echo | web | `uv run pytest tests/test_sales.py::test_web_sale_422_re_echoes_picked_batch -x` | ✅ (:1041) |
| **Criterion 5** | Cash credit written for the basket | unit | `uv run pytest tests/test_finance.py -q` | ✅ existing suite |
| Regression | Colour cue still stamped on the rebuilt form (Phase 18) | web | `uv run pytest tests/test_sales.py -k data_ref_cents -q` | ✅ (:899, :933, :956) |
| Regression | Name→code search dropdown still wired | web | `uv run pytest tests/test_sales_search.py -q` | ✅ existing suite |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_sales.py tests/test_mobile_sales.py tests/test_sales_search.py -q` (~24s — comfortably under the 30s budget)
- **Per wave merge:** `uv run pytest -q` (~169s) **plus** `uv run ruff check . && uv run ruff format --check .`
- **Phase gate:** Full suite green (≥808 + new tests) before `/gsd-verify-work`; manual UAT for the two browser-only behaviors (live total arithmetic; radio-switch data preservation felt end-to-end).

### Wave 0 Gaps

- [ ] `tests/test_sales_total.py` — new file, covers SALE-02 markup/wiring (`#sale-total` present, script tag on both shells, 422 re-render carries it, delete hook present)
- [ ] `tests/test_sales.py` — extend for SALE-03 (4 tests incl. the D-03 round-trip), SALE-04 (chip-survives-422 + picker attrs), SALE-05 (field-set assertion), SALE-07 (3 tests)
- [ ] `tests/test_mobile_sales.py` — extend for D-04 (4 tests)
- [ ] `tests/test_core.py` — extend `to_cents` coverage to pin the accept-set boundaries the JS mirrors (`'1 000'`, `'12abc'` → ValueError; `'12.505'` → 1251)
- [ ] Framework install: **none needed** — pytest/httpx/TestClient already present and green
- [ ] Shared fixtures: **none needed** — `client`, `session`, `customer`, `stocked_product`, `mobile_client_factory` in `tests/conftest.py` already cover every case (`customer` seeds «Анна Иванова» / consultant `12345` with `search_lc` set, which is exactly what SALE-04's three-way autocomplete test needs)

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1` (`.planning/config.json`).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | **no** | Single local operator, no auth in v1 (CLAUDE.md §Constraints: "1 operator in year one — no auth complexity needed in v1"). This phase adds no auth surface. |
| V3 Session Management | **no** | No sessions exist. |
| V4 Access Control | **no** | No multi-user model; no per-record ownership beyond batch↔product, which `register_sale` already enforces server-side (`services/sales.py:178`). |
| V5 Input Validation | **yes** | Service-layer validation + Jinja autoescape. New surface: `customer_mode` → tuple allow-list (`_CUSTOMER_MODES`); `customer_id` → resolved via `get_customer`, unresolvable id degrades to "nothing selected"; the 3 new-customer fields → `create_customer`'s existing `_validate_lengths` (WR-05, `customers.py:48-59`). |
| V6 Cryptography | **no** | No new crypto. Ids stay `uuid.uuid4()` via `core.py:15 new_id`. |
| V7 Error Handling / Logging | **yes** (incidental) | The new mode endpoint must follow the house pattern: `except Exception: logger.exception(...)` then a Russian block error, **never a raw 500** (`routes/sales.py:358-361`, "UI-SPEC: block error, never a raw 500"). |

### Known Threat Patterns for FastAPI + Jinja2 + HTMX + SQLite

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stored XSS via customer name rendered in the recent-sales column or chip | Tampering / Elevation | Jinja autoescape, **never `|safe`**. Client-side: `.dataset` in, `.textContent` out — the shipped `customer_picker.html:1-12` / `sale_customer.html:7-12` contract (T-4-01/T-4-05). The new total writes via `.textContent` too. |
| XSS via a client value echoed into an `hx-on::*` JS-evaluated attribute | Tampering | The CR-01 precedent (`routes/sales.py:36-40`): constrain the shape before echoing. `customer_mode` never reaches an attribute — allow-list it (`_CUSTOMER_MODES`) and compare, never interpolate. |
| SQL injection | Tampering | SQLAlchemy Core/ORM bound params only; `search_customers` uses `.contains(q_lc, autoescape=True)` (`customers.py:241`) — `autoescape=True` neutralises `%`/`_` LIKE wildcards. No raw SQL added. |
| Untrusted `customer_id` forcing attribution to an arbitrary customer | Spoofing / Repudiation | Single-operator local app — not a meaningful threat boundary (the operator can already reach every customer). Still: resolve via `get_customer` and degrade to "nothing selected" on a miss, mirroring `_build_lines`' batch rule (`routes/sales.py:69-77`). FK `fk_sales_customer_id_customers` + `PRAGMA foreign_keys=ON` is the DB backstop. |
| Client-computed money reaching persistence | Tampering | Structural: `sale-total.js` writes to `.textContent` only and has **no** form input. `register_sale` recomputes from `price[]` (`services/sales.py:282`). Verify no plan ever adds a `name=` to the total element. |
| Mass-assignment via extra form fields on `POST /sales` | Tampering | FastAPI binds only declared `Form(...)` params (`routes/sales.py:390-398`); the echoed hidden inputs (`name`, `surname`, `customer_id_keep`) are simply ignored there. Do **not** "fix" this by adding `**kwargs`. |
| Ledger tampering | Repudiation | Untouched: append-only triggers (`APPEND_ONLY_TRIGGERS`, `app/db.py`) + single write path `record_operation`. This phase writes no new ledger code. |
| CSRF | Spoofing | Out of scope for v1 (localhost, single operator, no auth) — consistent with every shipped phase. Not a regression. |

**Net security posture:** this phase adds **one** new endpoint (`GET /sales/customer-mode`, read-only, no writes) and **one** new form param on an existing endpoint (`customer_id` on `POST /m/sales`, feeding an existing validated service arg). No new write path, no schema change, no new dependency, no new crypto. The only genuine new control needed is the `customer_mode` allow-list.

## Sources

### Primary (HIGH confidence)
- **This repository, read directly** — `app/core.py`, `app/models.py`, `app/routes/sales.py`, `app/routes/mobile_sales.py`, `app/routes/__init__.py`, `app/services/sales.py`, `app/services/customers.py`, `app/services/export.py`, `app/static/price-cue.js`, `app/static/style.css`, `app/templates/base.html`, `app/templates/pages/sale_form.html`, `app/templates/partials/{sale_form,sale_row,sale_customer,customer_picker,recent_sales,sale_oversell}.html`, `app/templates/mobile_pages/sales.html`, `app/templates/mobile_partials/{sale_basket,sale_step_product,sale_step_batch,batch_card_picker}.html`, `tests/conftest.py`, `tests/test_sales.py`, `tests/test_mobile_sales.py`, `tests/test_sales_search.py`, `pyproject.toml`, `.planning/config.json`
- **Executed in this session (empirical):**
  - `uv run python -c "from app.core import to_cents; ..."` → the 20-case accept-set table in Pattern 2
  - Temporary probe test (since removed) → confirmed the 422 chip-loss defect and the mobile acc-array drop
  - `uv run pytest -q` → `808 passed in 169.23s` (baseline)
  - `uv run pytest tests/test_sales.py tests/test_mobile_sales.py tests/test_sales_search.py -q` → `87 passed in 23.65s`
  - `head -c 300 app/static/htmx.min.js` + version grep → `version:"2.0.10"`
- `.planning/phases/22-sales-page-rebuild/22-CONTEXT.md` — D-01..D-09 (locked)
- `.planning/REQUIREMENTS.md` §Sales (:50-58), `.planning/ROADMAP.md` §Phase 22 (:196-210), `CLAUDE.md`

### Secondary (MEDIUM confidence)
- `htmx.org/docs/#parameters` — default parameter inclusion; the non-GET/enclosing-form rule; `hx-include` `[CITED]`
- `htmx.org/attributes/hx-preserve/` — id requirement, response requirement, `<input type="text">` caveat `[CITED]`

### Tertiary (LOW confidence)
- None. Every claim in this document is either read from this repo, executed in this session, or cited from official htmx documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — zero new packages; every version read from `pyproject.toml` and the vendored htmx file, and the whole suite runs green
- Architecture: **HIGH** — all four patterns are extensions of shipped, tested code in this repo; the one genuinely new mechanism (stateful radio echo) is grounded in cited htmx docs
- Pitfalls: **HIGH** — 5 of 7 are read directly from source comments/tests; 2 (Pitfall 3, Pitfall 7) were **verified empirically** this session
- Parse accept-set: **HIGH** — executed, not recalled. Note this **corrects** D-08's characterisation (see Pattern 2)
- Open Question 1 (new-customer submit semantics): **LOW** — CONTEXT does not settle it; needs operator confirmation before planning locks it

**Research date:** 2026-07-17
**Valid until:** 2026-08-16 (30 days — stable pinned stack, offline app, no fast-moving dependency). Invalidate earlier if `sale_form.html`, `sale_customer.html`, `services/sales.py::recent_sales`, or `mobile_sales.py` change outside this phase.
