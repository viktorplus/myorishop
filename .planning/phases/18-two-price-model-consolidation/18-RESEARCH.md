# Phase 18: Two-Price Model Consolidation (ДЦ/ПЦ) - Research

**Researched:** 2026-07-16
**Domain:** Schema column removal + UI consolidation in a shipped FastAPI/SQLAlchemy/HTMX codebase
**Confidence:** HIGH (every claim below verified against this repo's code, its Alembic history, and the live `data/myorishop.db`)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**catalog_cents elimination (PROD-05)**

- **D-01: Discard the values, drop the column in this phase.** `Product.catalog_cents` is dropped via a single Alembic migration. Its 6 live values are NOT migrated anywhere. Grounded in live-DB evidence (7 active products, alembic head `0013`):
  - **0 backfill candidates** — there is no product where `sale_cents IS NULL AND catalog_cents IS NOT NULL`. Any `backfill-if-NULL` clause is a provable no-op; write it only as a defensive guard, not as a migration step.
  - **6 of 6 disagree**, always in the same direction (`cost < sale < catalog`, e.g. code `32021`: 45000 / 69000 / 89000). `catalog_cents` is the Oriflame list price; `sale_cents` is what the operator actually charges (17–30% below list). The disagreement is meaningful business data, not drift.
  - The column is stale by construction: code `42125` holds `catalog_cents=42000` against a live `CatalogPrice.consumer_cents=158000`. The real catalog price is served from the `catalog_prices` table, never from this write-once copy.
- **D-02: Never overwrite `sale_cents` from `catalog_cents`.** That was considered and rejected — it would re-price the live shop upward 17–30% (690→890) and silently change every future prefill and profit figure.
- **D-03: Use native `op.drop_column("products", "catalog_cents")` — NOT `batch_alter_table`.** `render_as_batch=True` (`alembic/env.py:48,72`) only affects autogenerate rendering. SQLite 3.45.1 supports native DROP COLUMN, and `catalog_cents` appears in no index/trigger/view. Batch mode would drop and recreate `products` along with its partial unique index `uq_products_code_active` (`sqlite_where`) — an avoidable footgun. Precedent for native drop: `alembic/versions/0008_batches.py:121`.
- **D-04: Historical ledger payloads keep `catalog_cents` forever — that is fine and untouched.** 8 receipt operations carry `payload.catalog_cents`. The ledger is append-only and DB-trigger-enforced (`app/db.py:22-43`, `RAISE(ABORT, 'operations ledger is append-only')`), so criterion 4 holds by construction. Consequences:
  - **Drop the «Каталог» column from the receipt history view** (`app/templates/partials/receipt_rows.html:19,31`). The receipt's defining money (`unit_cost_cents`→ДЦ, `unit_price_cents`→ПЦ) still renders; `payload.catalog_cents` simply rests unread. This satisfies criterion 1 (no third price surfaces anywhere).
  - **Keep the `catalog_cents` label branch in `app/templates/partials/price_history.html:22`.** It costs one line, renders for 0 live rows (there are **0** `price_change` ops targeting `catalog_cents`, so it cannot violate criterion 1), and removing it would let the `{% else %}` fallback one day show a raw `catalog_cents` string to the operator.

**Colour cue reference price (PROD-06)**

- **D-05: The reference is the code's single `CatalogPrice` row. Pairing: `consultant_cents` → ДЦ, `consumer_cents` → ПЦ.** Same rule at every entry point. This pairing is already consistent across `app/models.py:268-270`, `app/routes/products.py:147-160`, and quick-task 260714-fix — do not invent a new mapping.
- **D-06: "Catalog current at the operation's date" is NOT implementable — do not plan for it.** `catalog_prices` holds 6856 rows across 6856 distinct codes: **zero** codes carry more than one catalog, and `import_master_pricelist.py` guarantees that shape by keying its `collected` dict on code alone (~line 123). There is no per-period history and no effective-date column to resolve against.
- **D-07: "No catalog row → no cue + a muted hint" is the MAIN path, not an edge case.** 6 of 7 live products have no `CatalogPrice` row at all. Ship it as deliberate, visible behaviour — a silently absent cue would read as "your price matches the reference", which is worse than saying nothing.
- **D-08: Do NOT reuse `latest_price_for_code` unmodified** (`app/services/pricing.py:24-32`). It filters `consumer_cents.is_not(None)`, so a code with a ДЦ but no ПЦ returns `None` and its **ДЦ cue is starved despite a valid reference existing** (1 such code today). The cue needs a lookup that does not gate ДЦ on ПЦ's presence.
- **D-09: Accept the honest caveat rather than hiding it.** Each code's single row is its *last catalog appearance* (live data spans 2015 → 2026), so "the reference" means "the price when this code was last in a catalogue" — years stale for discontinued codes — and each re-import wipes and redefines it. Name this in the UI wording; do not pretend the reference is current.

**Colour cue mechanism (PROD-06 / criterion 3)**

- **D-10: One delegated listener in a new `app/static/price-cue.js` (~15 lines).** A single `document.addEventListener('input')` reading `data-ref-cents` off the field. Delegation covers desktop + mobile + HTMX-added basket rows with no re-initialisation, and keeps the rule in one place.
- **D-11: This is NOT the app's first hand-written JS** — that objection does not apply. `hx-on:` appears 42 times across templates (including conditional swap-suppression logic at `product_form.html:19`), and `base.html:6-14` already carries an inline viewport-redirect script. Alpine.js's deferred caveat is **not** triggered: there is no client-side *state* here, only a stateless read-compare-toggle.
- **D-12: Never use an HTMX round-trip per keystroke.** Swapping a focused `<input type="text">` destroys focus AND caret position while the operator is mid-typing; the basket's `price[]` inputs (`sale_row.html:35`) have no `id`, so htmx cannot even attempt focus restore; and it fires N requests per keystroke on an N-row basket. This repo has already been bitten by swaps clobbering in-flight typing — the `hx-on::before-swap` guard at `product_form.html:15-19` (Pitfall 5) exists for exactly that reason.
- **D-13: The "no client-side money math" convention is NOT violated.** The cue is advisory: it never parses, computes, or submits money. `parse_optional_cents` (`app/services/catalog.py:106`) stays the sole authority and the server re-renders the authoritative cue on every response. Client/server parse parity is a one-liner, not a reimplementation: `core.py:28` `to_cents` does `.strip().replace(",", ".")` and rejects space-separated thousands, so `parseFloat(v.replace(',','.'))` accepts exactly what the server accepts. Float math can flip the cue only exactly at the equality boundary (`12,505` → 1250 client vs 1251 server) — harmless for an advisory hint; the server re-render is the tiebreaker. Note this in a code comment.
- **D-14: Visual form — coloured border + soft background tint + short text badge** («ниже справочной» / «выше справочной»), reusing the existing `.muted` idiom. Colour alone fails WCAG 1.4.1 (Use of Color), and yellow-on-white is too low-contrast to read as a border by itself. Concrete values: *below* = amber border `#b45309` on `#fef9e7` fill; *above* = accent-blue border `#2563eb` on `#eff6ff` fill. **Collision to avoid: `#e8effd` is already the search-match `mark` highlight (`app/static/style.css:252-255`)** — the blue cue must not reuse that tint.

**Price write-back semantics (PROD-07)**

- **D-15: Asymmetric by entry point — receipt writes back to the card, sale stays scoped to the sale.** This is the domain-correct rule and is already the shipped behaviour:
  - A **receipt** is a restock event establishing a new standing ДЦ/ПЦ → it writes back to the product card. **Already implemented** (`app/services/receipts.py:169-196`, decision D-07 of the earlier milestone) with one `price_change` op per changed field and the PD-8 "empty never clears" rule. No new work; do not regress it.
  - A **sale** is a negotiation with one customer → the price stays on the operation. `Batch.price_cents` stays frozen. Nothing writes back to `Product`.
- **D-16: Reject "sale writes back to the card".** It would turn a one-off discount into the product's permanent ПЦ, and its interaction with `min_sale_cents` is genuinely bad: writing a below-minimum sale price back to `sale_cents` leaves the card prefilling below its own floor, tripping the PRICE-01 warning on every subsequent sale and pushing the operator to reflex-click the `confirm=1` bypass — which **also clears the oversell check** (`app/services/sales.py:181`, one flag clears both). That actively erodes criterion 5.
- **D-17: Close the discoverability gap with wording, not machinery.** Extend the existing prefill-hint pattern (`app/routes/sales.py:152-157`, "Цена подставлена из карточки товара — можно изменить") to state the scope: **"— изменение сохранится только в этой продаже"**. A per-line "сохранить в карточку" checkbox was considered and rejected as basket clutter.
- **D-18: The dictionary entry point redirects to the product card — it does not become editable.** "Editing the price in the dictionary" is not implementable as written: the `Dictionary` table has **no price columns at all** (code→name only, `app/models.py:235-256`). The ДЦ/ПЦ shown there come from `CatalogPrice`, which is not "our price" but a published historical fact ("what Oriflame charged in catalog 07/26"), served by an explicitly read-only route (`app/routes/catalogs.py:4`). The importer does `session.query(CatalogPrice).delete()` then bulk-inserts (`scripts/import_master_pricelist.py:136-137`), so **any hand edit is silently destroyed on the next re-import** — a direct hit on the core value "without losing any data". Implementation: the dictionary/catalog row shows ДЦ/ПЦ read-only and offers **«изменить цену»**, which opens the *product card* for that code (creating it if it does not exist).

**Label consolidation (PROD-05 / criterion 1)**

- **D-19: Unify the price labels on ДЦ/ПЦ across every surface.** The same field is currently labelled inconsistently: `catalog_detail.html:21` says "Цена консультанта" while `product_form.html:110` says just "консультант" for the identical `CatalogPrice.consultant_cents`. Criterion 1 ("no third or fourth price field appears anywhere") is a *labelling* criterion as much as a schema one — two prices, two names, everywhere, desktop and mobile.

### Claude's Discretion

- Exact Russian wording of the cue badges and the muted "нет справочной цены" hint.
- Whether the ДЦ/ПЦ reference lookup lands as a new function in `app/services/pricing.py` or a fix to the existing one (D-08 only fixes the *behaviour*, not the location).
- Whether to correct the two misleading docstrings noted in Deferred while already editing those files.

### Deferred Ideas (OUT OF SCOPE)

- **`Dictionary` code/name edits are wiped on re-import — same bug class as D-18.** `app/services/dictionary.py:63-82` lets the operator edit a dictionary entry's code/name via `POST /dictionary/{entry_id}`, but `import_master_pricelist.py` re-imports destructively, so those edits already vanish silently today. This is a pre-existing bug, out of scope for a price phase. → `deferred-items.md` candidate.
- **Two docstrings contradict the data.** `app/services/pricing.py:3-5` ("full per-catalog price history") and `CatalogPrice`'s docstring (`app/models.py:260-263`, "the full price history across every catalog issue") both describe a multi-catalog history that does not exist — the data is strictly one row per code. These docstrings are exactly what would mislead a future reader into believing D-06's date-accurate reference is available. Cheap to fix if a plan already touches those files (Claude's discretion); otherwise defer.
- **Sale → card price promotion as an explicit narrow action.** If the operator later wants to promote a sale price to the card, add a single "обновить цену в карточке" link on the sale confirmation — an explicit opt-in action, never a default. Not needed now; D-15 covers the common case.
- **`confirm=1` clears both the oversell check and the below-minimum check** (`app/services/sales.py:181`) — one flag, two guardrails. The UI presents the minimum as a hard barrier while it is in fact a bypassable warning. The 2026-07-14 report flagged this as "worth confirming it is intentional". Out of scope: criterion 5 freezes PRICE-01 behaviour unchanged for this phase. Revisit as its own decision.
- **"Обновить цены из последнего прайс-листа" button on the product card.** Suggested by the 2026-07-14 report: `Product` prices are filled once at autofill and then drift from `CatalogPrice` forever (code `42125`: 420 vs 1580). After this phase the drift is *visible* via the cue, which arguably makes a one-click resync the natural follow-up — but it is a new capability, not a consolidation. → Phase 19 (Products Page Rebuild) or backlog.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **PROD-05** | Product pricing reduced to exactly two fields — ДЦ (`cost_cents`) and ПЦ (`sale_cents`); every other product price field removed or consolidated. `min_sale_cents` explicitly exempt. | §Authoritative `catalog_cents` Removal Surface (36 code sites across 17 files, incl. the mobile wizard CONTEXT.md missed); §Alembic Migration Mechanics (native `0014` drop); §Label Consolidation Surface (D-19) |
| **PROD-06** | Entering a ДЦ or ПЦ differing from the dictionary's reference shows a colour cue: below = yellow, above = blue. | §The ДЦ/ПЦ Reference Lookup (exact signature + the D-08 starvation fix); §The `data-ref-cents` Input Surface (all 11 inputs); §Cue Styling (verified `#e8effd` collision is 6 sites, not 1) |
| **PROD-07** | ДЦ/ПЦ editable at any stage — product card, dictionary, receipt, sale — change saved from wherever made. | §Write-Back Semantics Verification (D-15 confirmed already shipped); §The D-17 Hint Surface (3 literal duplicates, not 1); §D-18 dictionary redirect (verified `Dictionary` has zero price columns) |
</phase_requirements>

## Summary

This phase is **not a research problem — it is an inventory problem.** The `/gsd-discuss-phase` session already produced 19 evidence-grounded decisions, and I independently re-verified every falsifiable claim in CONTEXT.md against this repo's code, its Alembic history, and the live `data/myorishop.db`. **All 8 live-DB claims reproduce exactly** (see §Live-DB Verification). CONTEXT.md is unusually reliable; the planner should treat D-01..D-19 as binding and not re-litigate them.

What the planner still needs, and what this document adds, is the **complete removal surface** — because CONTEXT.md's "~12 files" estimate is **materially incomplete**. The real surface is **36 code sites across 17 files**. The single largest omission is the **entire mobile receipt wizard**, which threads `catalog` through 5 endpoints in `app/routes/mobile_receipts.py` and 3 hidden/visible inputs across `receipts_step_details.html` / `receipts_step_batch.html` / `receipts_step_confirm.html`. CONTEXT.md's inventory does not mention mobile at all. `app/routes/receipts.py` (desktop, 8 sites) and `receipt_form.html`'s `hx-include` are likewise missing. A plan built only from CONTEXT.md's list would ship a mobile receipt wizard that 500s on a dropped attribute.

Three further corrections matter. (1) CONTEXT.md cites `0008_batches.py:121` as the native-drop precedent, but **`0002_catalog_dictionary.py:75` already contains `op.drop_column("products", "catalog_cents")` verbatim** — the exact statement `0014` needs, on the exact column, with a comment confirming native DROP COLUMN support. That is the precedent to cite. (2) CONTEXT.md says SQLite 3.45.1; the actual runtime is **3.50.4** (D-03 holds either way — both exceed the 3.35 threshold). (3) CONTEXT.md says `product_form.html:104-111` "goes away with the column" — **it must not.** That block renders `latest_price` (the `CatalogPrice` reference), not `catalog_cents`, and D-19 explicitly names line 110 as a relabel target. Only the input at `:79` goes; `:103-114` stays, gets the D-19 label and the D-09 caveat, and is the natural `data-ref-cents` source.

**Primary recommendation:** Sequence as (1) a native `0014` drop mirroring `0002`'s downgrade statement, (2) fix `latest_price_for_code` **in place** — it is starving ДЦ in 3 production callers today, not just the cue — then (3) sweep the 36-site surface desktop-and-mobile in one pass, and (4) add the cue last, since it is purely additive. Criterion 5 (PRICE-01) is **structurally independent** of `catalog_cents` — `sales.py:206-234` reads only `min_sale_cents` — so the regression risk is low, but its 9 guard tests must run green regardless.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Drop `catalog_cents` column | Database (Alembic `0014`) | — | Schema change; irreversible by D-01 |
| Parse/validate ДЦ/ПЦ input | API/Backend (`parse_optional_cents`) | — | D-13: server is the sole money authority; the client never computes money |
| Reference price lookup | API/Backend (`app/services/pricing.py`) | — | Reads `catalog_prices`; must not gate ДЦ on ПЦ (D-08) |
| Emit `data-ref-cents` | Frontend Server (Jinja2 templates) | — | Server-rendered; reference resolved server-side, attached as a data attribute |
| Live cue while typing | Browser/Client (`price-cue.js`) | — | D-10/D-12: keystroke-rate feedback; a round-trip would destroy focus/caret |
| Authoritative cue on load | Frontend Server (Jinja2) | Browser (re-computes on input) | D-13: server re-render is the tiebreaker at the equality boundary |
| Receipt → card write-back | API/Backend (`app/services/receipts.py:169-196`) | Database (ledger `price_change` ops) | D-15: already shipped; must not regress |
| Sale price scoping | API/Backend (`app/services/sales.py`) | — | D-15/D-16: stays on the operation; nothing writes to `Product` |
| PRICE-01 below-minimum warning | API/Backend (`app/services/sales.py:206-234`) | — | Criterion 5 regression guard; reads only `min_sale_cents` |
| Ledger immutability | Database (triggers, `app/db.py:22-43`) | — | D-04: criterion 4 holds by construction, not by application code |

## Standard Stack

**No new dependencies. This phase adds zero packages.**

The entire change is: one Alembic migration, edits to existing Python/Jinja2 files, one new ~15-line static JS file (`app/static/price-cue.js`), and CSS additions to the existing single stylesheet. Everything needed is already in `pyproject.toml`.

### Verified Runtime (probed on this machine, 2026-07-16)

| Component | Version | Verification | Relevance |
|-----------|---------|-------------|-----------|
| Python | 3.13.13 | `uv run python -c "import sys"` [VERIFIED: local runtime] | Matches `requires-python = ">=3.13"` |
| SQLAlchemy | 2.0.51 | `sqlalchemy.__version__` [VERIFIED: local runtime] | Matches `sqlalchemy==2.0.*` |
| SQLite | **3.50.4** | `sqlite3.sqlite_version` [VERIFIED: local runtime] | **Corrects CONTEXT.md's "3.45.1"**; native DROP COLUMN needs ≥ 3.35 — satisfied with wide margin |
| Alembic | 1.18.* | `pyproject.toml` [VERIFIED: repo] | D-03's native-drop path |
| pytest | 9.1.* | `pyproject.toml` [VERIFIED: repo] | `testpaths = ["tests"]`, `pythonpath = ["."]` |
| htmx | 2.0.10 vendored | `app/static/htmx.min.js` [VERIFIED: repo] | Offline; cue must not depend on a CDN |

### Alternatives Considered

Not applicable — CONTEXT.md D-01..D-19 already locked every design choice. Re-litigating them is explicitly out of scope for this research.

## Package Legitimacy Audit

**Not applicable — this phase installs no external packages.**

Per the Package Legitimacy Gate protocol, this section is required only when a phase installs external packages. The full dependency set for this work is already present in `pyproject.toml` and already installed. **No `checkpoint:human-verify` install gate is needed.** The only new file added to `app/static/` is hand-written first-party code (`price-cue.js`, D-10), not a vendored third-party asset — no supply-chain surface is introduced.

## Live-DB Verification

I re-ran every falsifiable claim in CONTEXT.md against `data/myorishop.db`. **All 8 reproduce exactly.** [VERIFIED: live database query, 2026-07-16]

| CONTEXT claim | Decision | Query result | Status |
|---|---|---|---|
| Alembic head is `0013` | D-01 | `0013` | ✅ exact |
| 7 active products | D-01 | `7` | ✅ exact |
| 0 backfill candidates (`sale_cents IS NULL AND catalog_cents IS NOT NULL`) | D-01 | `0` | ✅ exact |
| 6 live `catalog_cents` values | D-01 | `6` | ✅ exact |
| 6856 `catalog_prices` rows across 6856 distinct codes | D-06 | `6856` / `6856` | ✅ exact |
| Zero codes carry more than one catalog | D-06 | `0` | ✅ exact |
| 1 code with ДЦ but no ПЦ (starved cue) | D-08 | `1` | ✅ exact |
| 0 `price_change` ops targeting `catalog_cents` | D-04 | `0` | ✅ exact |
| 8 receipt ops carrying `payload.catalog_cents` | D-04 | `8` | ✅ exact |

**Implication for the planner:** D-01's "the backfill clause is a provable no-op", D-06's "date-accurate reference is not implementable", D-04's "keeping the `price_history.html:22` label cannot violate criterion 1 (0 rows render it)", and D-08's "1 code is starved today" are all **verified facts, not estimates.** Plan against them directly.

## Authoritative `catalog_cents` Removal Surface

CONTEXT.md estimated "~12 files, verify before editing". **The verified surface is 36 code sites across 17 files.** Below is the exhaustive inventory from `rg catalog_cents` scoped to `app/ tests/ scripts/ alembic/`, plus the `catalog` form-field name (which `catalog_cents` grep alone misses). [VERIFIED: ripgrep over repo, 2026-07-16]

### 🔴 Sites CONTEXT.md MISSED (the important part)

| File:line | What | Why it matters |
|---|---|---|
| `app/routes/mobile_receipts.py:106,163,201,234,264` | `catalog: str = Form("")` on **5 endpoints**; `resolved_catalog` (127-128), `final_catalog` (136), context keys (145,181,215,248), `catalog_raw=catalog` (264) | **Entire mobile wizard omitted from CONTEXT.md.** Threads `catalog` step→step |
| `app/templates/mobile_partials/receipts_step_details.html:26` | Visible `#receipt-catalog` input | Mobile's third price field — **criterion 1 violation if left** |
| `app/templates/mobile_partials/receipts_step_batch.html:15` | `<input type="hidden" name="catalog">` | Wizard state pass-through |
| `app/templates/mobile_partials/receipts_step_confirm.html:30` | `<input type="hidden" name="catalog">` | Wizard state pass-through |
| `app/routes/receipts.py:113,126,127,136,142,144,145,174,190,205` | Desktop receipt `catalog` param, `typed`/`fill_fields` dicts, context, `catalog_raw=catalog` | **Desktop receipt route omitted from CONTEXT.md** |
| `app/templates/partials/receipt_form.html:29` | `hx-include="…,[name='catalog'],…"` | Stale selector after input removal |
| `app/templates/partials/receipt_form.html:78-79` | `{% with field = "catalog", label = "Цена по каталогу" %}` + include | The desktop receipt's third price field |
| `alembic/versions/0002_catalog_dictionary.py:8,39,75` | Historical add/drop | **MUST NOT be edited** — WR-06 immutability rule (see §Alembic) |
| `tests/test_receipts.py:8,72,203,526,613,632,658,677,684` | 9 sites (CONTEXT said "~10 across two files" total) | `:613,632,658,677` **assign `product.catalog_cents`** → `AttributeError` on drop |
| `tests/test_export.py:230` | Asserts `"Каталог"` in CSV header | **Breaks when `export.py:98` column drops** |
| `app/services/receipts.py:6` | Docstring "payload carries catalog_cents" | Still true for history (D-04); reword, don't delete |

### ✅ Sites CONTEXT.md correctly identified

| File:line | What | Action |
|---|---|---|
| `app/models.py:153` | `catalog_cents: Mapped[int \| None]` | **Remove** (+ update the "three optional prices" comment → two + guardrail) |
| `app/services/catalog.py:106,125,156,211,236,261` | parse / create / update / `_PRICE_FIELDS` audit tuple | **Remove**; drop from `_PRICE_FIELDS` at :156 |
| `app/services/receipts.py:116,157,177,246,285` | parse / prefill / write-back / **ledger payload write** / lookup | **Stop writing**; `:246` payload write stops, history stays (D-04) |
| `app/services/export.py:98` | CSV column | **Remove** (+ `"Каталог"` header at :86) |
| `app/routes/products.py:155` | `"catalog_cents": latest.consumer_cents` | **Remove** (also `:133,148,154` — see §Autofill) |
| `app/templates/pages/product_form.html:79` | The `#catalog` input | **Remove** (**but `:103-114` STAYS** — see §product_form correction) |
| `app/templates/pages/categories.html:34` | List column | **Remove** |
| `app/templates/partials/product_rows.html:60` | List column | **Remove** |
| `app/templates/partials/receipt_rows.html:19,31` | History column | **Remove** per D-04 |
| `app/templates/partials/price_history.html:22` | Audit label branch | **KEEP** per D-04 (renders for 0 rows) |
| `app/templates/partials/product_price_autofill.html:6-7` | OOB `catalog` input | **Remove** (keep the `cost`/`sale` OOB inputs at :10,:14) |
| `tests/test_catalog.py:58,278,520,521` | 4 assertion sites | **Update**; `:278` asserts `catalog_cents` in reflected columns → invert to assert absence |

### ⚠️ Correction: `product_form.html:103-114` must NOT be removed

CONTEXT.md's Integration Points says `:104-111` is "the «сохранённая vs последняя из каталога» двойная строка … it goes away with the column." **Only half of that is right.** The verified content:

```jinja
{# line 77-81: the catalog_cents INPUT — this GOES #}
<div class="field">
  <label for="catalog">Цена по каталогу <span class="muted">(необязательно)</span></label>
  <input type="text" id="catalog" name="catalog" ... value="{% ... product.catalog_cents | cents %}">
</div>

{# line 103-114: the latest_price REFERENCE display — this STAYS #}
{% if latest_price is defined and latest_price %}
  {% if latest_price.consumer_cents is not none %}{{ latest_price.consumer_cents | cents }}{% endif %}
  {% if latest_price.consultant_cents is not none %}<span class="muted">· консультант {{ ... }}</span>{% endif %}
  <span class="muted">(каталог {{ latest_price.number }} · {{ latest_price.year }})</span>
{% endif %}
```

The `:103-114` block reads **`latest_price` (a `CatalogPrice` row)** — it never touches `catalog_cents`. It must stay because:
1. **D-19 explicitly names line 110** ("консультант") as the label-unification target. You cannot relabel a deleted block.
2. It already renders **both** `consumer_cents` and `consultant_cents` — exactly the ДЦ/ПЦ reference pair the cue needs. `app/routes/products.py:244` already supplies `latest_price` to this template, so **the product card's reference is already in context** — no new query needed there.
3. `(каталог {{ number }} · {{ year }})` is precisely where **D-09's honest caveat** ("the price when this code was last in a catalogue") belongs.

The "двойная строка" confusion CONTEXT.md refers to dissolves the moment the `:79` input disappears — one saved price vanishes, leaving one reference display. **Delete `:77-81`, keep and relabel `:103-114`.**

## Alembic Migration Mechanics

### Verified conventions [VERIFIED: `alembic/versions/` inspection]

| Property | Value |
|---|---|
| Current head | `0013` (file `0013_cash_movements.py`; **matches live DB `alembic_version`**) |
| Filename convention | `NNNN_snake_case_description.py`, zero-padded 4 digits |
| Revision ID convention | Bare zero-padded string: `revision = "0013"`, `down_revision = "0012"` |
| Boilerplate | `branch_labels = None`, `depends_on = None` on every file |
| Docstring convention | `"""<short title>\n\nRevision ID: NNNN\nRevises: NNNN\nCreate Date: YYYY-MM-DD\n\n<rationale + caveats>\n"""` |
| **WR-06 immutability rule** | **"this file must never import app modules"** — stated verbatim in `0001`, `0003`, `0013`. Migrations duplicate app constants as FROZEN copies; they never reference `app.*` |

**So `0014` must be:** `alembic/versions/0014_drop_product_catalog_cents.py`, `revision = "0014"`, `down_revision = "0013"`, and **must not import from `app.`** — it needs no imports beyond `sqlalchemy as sa` and `from alembic import op`.

### 🔴 Better precedent than CONTEXT.md cites

CONTEXT.md points to `0008_batches.py:121`. That line is `op.drop_column("operations", "batch_id")` — a *different* column, in `downgrade()`, preceded by an `op.drop_index`. **`0002_catalog_dictionary.py:75` is the exact statement `0014` needs, on the exact column:**

```python
def downgrade() -> None:          # 0002_catalog_dictionary.py:68-80
    ...
    # SQLite >= 3.35 supports native DROP COLUMN (local runtime is 3.50.4).
    op.drop_column("products", "name_lc")
    op.drop_column("products", "catalog_cents")     # <-- :75, verbatim what 0014 needs
    op.drop_column("products", "sale_cents")
    ...
```

Cite `0002:75` as primary precedent and `0008:121` as secondary. Note the in-repo comment already states **"local runtime is 3.50.4"**, independently corroborating my probe and correcting CONTEXT.md's "3.45.1".

### Why native, restated with verified evidence (supports D-03)

`0008_batches.py:11-17` carries this **verbatim** warning:

> *"CRITICAL — Alembic batch caveat (see 0001's frozen warning): a batch (move-and-copy) migration on `operations` DROPS its append-only triggers … `batch_id` is therefore added with a NATIVE op.add_column — NEVER an Alembic batch/move-and-copy rebuild."*

`0001:11-14` states the same rule. The repo has a **documented, twice-restated house rule against batch mode on ALTER**. D-03 is not a judgement call — it is the established convention. For `products` specifically the stake is `uq_products_code_active` (`0003`), a partial index using `sqlite_where=sa.text("deleted_at IS NULL")`; a move-and-copy rebuild is exactly the operation that risks losing that predicate. [VERIFIED: `alembic/versions/0003_products_code_active_unique.py`]

### Recommended `0014` shape

```python
"""drop products.catalog_cents (PROD-05)

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-16

Phase 18 (PROD-05, D-01): the two-price model keeps only ДЦ (cost_cents)
and ПЦ (sale_cents); min_sale_cents stays as a guardrail threshold, NOT a
displayed price. catalog_cents is a write-once stale copy of the Oriflame
list price — the live reference is served from catalog_prices — so its
values are DISCARDED, not migrated (D-01: 0 rows have sale_cents IS NULL
AND catalog_cents IS NOT NULL, so no backfill is possible or needed).

NATIVE op.drop_column, NOT batch_alter_table (D-03, and the house rule
frozen in 0001:11-14 / 0008:11-17): a move-and-copy rebuild of `products`
would recreate the partial unique index uq_products_code_active (0003,
sqlite_where="deleted_at IS NULL"). SQLite >= 3.35 supports native DROP
COLUMN (local runtime 3.50.4); catalog_cents is in no index/trigger/view.
Same statement already proven in 0002's downgrade (0002:75).

IRREVERSIBLE (D-01): downgrade re-adds the column as NULL-filled. The 6
discarded values are NOT recoverable from this migration. Pre-drop safety
net is app/services/backup.py's VACUUM INTO startup snapshot; historical
receipt payload.catalog_cents (8 ops) is untouched and stays readable.

Immutability rule (WR-06): this file must never import app modules.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("products", "catalog_cents")


def downgrade() -> None:
    # D-01: values were discarded on upgrade — the column returns EMPTY.
    # Nullable is what 0002:42 originally created, so the shape round-trips
    # even though the data does not.
    op.add_column("products", sa.Column("catalog_cents", sa.Integer(), nullable=True))
```

**On `downgrade()`:** D-01 makes the data loss deliberate. The correct downgrade restores the **schema shape** (nullable Integer, matching `0002:42`) with NULL values — it must not fabricate values from `sale_cents` (that would be D-02's rejected re-pricing, sneaking in through the back door). The docstring must say so explicitly; a silent NULL-filled downgrade is otherwise indistinguishable from a bug. `raise NotImplementedError` is the alternative, but it breaks the chain's replayability, which `0002`'s full-downgrade precedent maintains — prefer the shape-restoring version above.

## The ДЦ/ПЦ Reference Lookup (D-05 + D-08)

### Current state [VERIFIED: `app/services/pricing.py:14-32`]

```python
def latest_price_for_code(session: Session, code: str) -> CatalogPrice | None:
    """Most recent catalog price for a code (newest catalog first).
    "Newest" = highest (year, number). Only rows carrying a consumer price
    are considered, so the returned row always has consumer_cents set.
    """
    code = (code or "").strip()
    if not code:
        return None
    return session.scalars(
        select(CatalogPrice)
        .where(
            CatalogPrice.code == code,
            CatalogPrice.consumer_cents.is_not(None),   # <-- D-08: the starvation
        )
        .order_by(CatalogPrice.year.desc(), CatalogPrice.number.desc())
        .limit(1)
    ).first()
```

### 🔴 The D-08 bug is NOT cue-only — it is live in 3 production callers today

CONTEXT.md frames D-08 as "the ДЦ *cue* is starved". Verified: the same filter starves **the shipped autofill**, right now, before this phase touches anything. [VERIFIED: caller trace via ripgrep]

| Caller | Line | Current behaviour for the 1 starved code | Verdict |
|---|---|---|---|
| `app/routes/products.py:147` | Product-form autofill (CAT-05) | `latest` is `None` → `fill_cost` at `:149` is `False` → **ДЦ never autofills despite `consultant_cents` existing** | 🐛 live bug |
| `app/routes/products.py:244` | `latest_price` for the card's reference display | `None` → **the whole `:103-114` reference block silently vanishes** | 🐛 live bug |
| `app/services/receipts.py:289` | `lookup_prefill` catalog source | `latest` is `None` → falls to `entry is not None` only → **receipt ДЦ prefill starved** | 🐛 live bug |
| `tests/test_pricing_feature.py:45,52,53` | Unit tests | Assert current filtered behaviour | must be updated if fixed in place |

Look at `products.py:148-150` — the filter's effect is stark:

```python
latest = latest_price_for_code(session, code)          # None if consumer_cents IS NULL
fill_catalog = latest is not None and latest.consumer_cents is not None and not catalog.strip()
fill_cost    = latest is not None and latest.consultant_cents is not None and not cost.strip()   # unreachable
fill_sale    = latest is not None and latest.consumer_cents is not None and not sale.strip()
```

`fill_cost` guards `consultant_cents is not None` — the author clearly intended ДЦ to fill independently — but `latest` is already `None`, so the guard never gets the chance. **The intent is in the code; the filter defeats it.**

### Recommendation on the Claude's-Discretion call: **fix in place**

CONTEXT.md leaves "new function vs fix existing" to discretion. The evidence favours **fixing `latest_price_for_code` in place** (dropping the `consumer_cents.is_not(None)` filter):

- It repairs 3 live bugs, not just the cue. A new function leaves all 3 starved and adds a near-duplicate query — two functions differing by one `WHERE` clause, a maintenance trap.
- Every caller already null-checks each field independently (`products.py:148-150` above; `receipts.py:295-297` does `latest.consultant_cents if latest is not None else None` per field). **The callers are already written to tolerate a row with NULL fields** — they were built for the unfiltered contract.
- Blast radius is **one code** (verified: exactly 1 row has `consultant NOT NULL AND consumer NULL`). The change can only *add* a previously-missing autofill/reference, never remove or alter an existing one.
- The docstring's "the returned row always has consumer_cents set" becomes false and must be rewritten — which also resolves the Deferred docstring item for this file (`pricing.py:3-5`) while already editing it.

**Caveat the planner must weigh:** this is a **behaviour change beyond the phase's stated scope** — one code's receipt/product autofill starts filling ДЦ where it previously did not. It is a strict improvement and PROD-06 arguably requires it, but it is not literally in PROD-05/06/07 as written. If the planner prefers strict scope discipline, add a new `reference_prices_for_code` and log the 3 live bugs as a deferred item. **My recommendation is fix-in-place + update `test_pricing_feature.py`.** This is flagged as an Open Question (Q1) because it is a scope judgement, not a technical one.

### Required shape for the cue

The cue needs both fields **independently**, never gating one on the other:

```python
def reference_prices_for_code(session: Session, code: str) -> tuple[int | None, int | None]:
    """(ДЦ, ПЦ) reference for a code — (consultant_cents, consumer_cents).

    D-05: consultant_cents → ДЦ, consumer_cents → ПЦ. Each is returned
    INDEPENDENTLY (D-08): a code with a ДЦ but no ПЦ must still cue its ДЦ.
    (None, None) when the code appears in no imported catalog (D-07: the
    MAIN path — 6 of 7 live products have no catalog row).

    D-09: the single row per code is that code's LAST catalog appearance,
    not today's price. `catalog_prices` has exactly one row per code
    (6856 rows / 6856 codes) — there is no per-period history (D-06).
    """
```

Whether this is a thin wrapper over a fixed `latest_price_for_code` or the fixed function returning the row directly is style. **The load-bearing contract: ДЦ must not be gated on ПЦ's presence, and `(None, None)` must be a first-class, rendered outcome (D-07), not an error.**

## The `data-ref-cents` Input Surface

Exhaustive enumeration of every ДЦ/ПЦ input the cue must attach to. [VERIFIED: ripgrep `name="(cost|sale|catalog|price|min_sale)"` over `app/templates/**/*.html`]

### Desktop

| File:line | Input | Field | Cue? |
|---|---|---|---|
| `app/templates/pages/product_form.html:61` | `id="cost" name="cost"` | **ДЦ** | ✅ `data-ref-cents` = `latest_price.consultant_cents` |
| `app/templates/pages/product_form.html:67` | `id="sale" name="sale"` | **ПЦ** | ✅ `data-ref-cents` = `latest_price.consumer_cents` |
| `app/templates/pages/product_form.html:73` | `id="min_sale" name="min_sale"` | guardrail | ❌ **NO CUE — exempt (PROD-05 scope note)** |
| `app/templates/pages/product_form.html:79` | `id="catalog" name="catalog"` | — | 🗑️ **DELETE** |
| `app/templates/partials/receipt_price_inputs.html:7` | `id="{{field}}" name="{{field}}"` | generic | ✅ add optional `ref_cents` param — **one edit covers both receipt fields** |
| `app/templates/partials/receipt_form.html:71` | include → `cost` | **ДЦ** | ✅ pass `ref_cents` |
| `app/templates/partials/receipt_form.html:75` | include → `sale` | **ПЦ** | ✅ pass `ref_cents` |
| `app/templates/partials/receipt_form.html:78-79` | `field = "catalog"` | — | 🗑️ **DELETE** |
| `app/templates/partials/receipt_form.html:29` | `hx-include="…[name='catalog']…"` | — | 🗑️ **DELETE selector** |
| `app/templates/partials/sale_row.html:35` | `name="price[]"` (**no `id`** — D-12) | **ПЦ** | ✅ |
| `app/templates/partials/sale_lookup.html:22` | `name="price[]"` | **ПЦ** | ✅ |
| `app/templates/partials/sale_batch_pick.html:23` | `name="price[]"` | **ПЦ** | ✅ |
| `app/templates/partials/product_price_autofill.html:6-7` | OOB `#catalog` | — | 🗑️ **DELETE** |
| `app/templates/partials/product_price_autofill.html:10,14` | OOB `#cost`, `#sale` | ДЦ/ПЦ | ⚠️ **must carry `data-ref-cents` too** — OOB swap *replaces the element*, so a bare re-render silently strips the attribute (see Pitfall 2) |

### Mobile

| File:line | Input | Field | Cue? |
|---|---|---|---|
| `app/templates/mobile_partials/receipts_step_details.html:18` | `id="receipt-cost" name="cost"` | **ДЦ** | ✅ |
| `app/templates/mobile_partials/receipts_step_details.html:22` | `id="receipt-sale" name="sale"` | **ПЦ** | ✅ |
| `app/templates/mobile_partials/receipts_step_details.html:26` | `id="receipt-catalog" name="catalog"` | — | 🗑️ **DELETE** |
| `app/templates/mobile_partials/sale_step_qty_price.html:25` | `name="price"` | **ПЦ** | ✅ |
| `app/templates/mobile_partials/receipts_step_batch.html:13,14` | hidden `cost`, `sale` | state | ➖ no cue (hidden) |
| `app/templates/mobile_partials/receipts_step_batch.html:15` | hidden `catalog` | — | 🗑️ **DELETE** |
| `app/templates/mobile_partials/receipts_step_confirm.html:28,29` | hidden `cost`, `sale` | state | ➖ no cue (hidden) |
| `app/templates/mobile_partials/receipts_step_confirm.html:30` | hidden `catalog` | — | 🗑️ **DELETE** |

### 🔴 Mobile has **no product card at all**

`app/routes/` contains **no `mobile_products.py`**, and `app/templates/mobile_pages/` has **no `product_form.html`**. [VERIFIED: directory listing] Mobile pages are exactly: `corrections, finance, finance_report, history, home, receipts, reports_expiry, sales, search, transfers, writeoff`.

**Criterion 1 says "on the product card, the dictionary entry, the goods receipt, and the sale form (desktop and mobile)".** Taken literally that is unsatisfiable — **mobile has no product card and no dictionary page.** The mobile price surfaces are exactly two: the **receipt wizard** and the **sale wizard**. `mobile_partials/search_product_detail.html` is the closest thing to a mobile card and is read-only.

**Planner action:** interpret criterion 1 as *"every price surface that exists on each platform shows exactly two prices"*, and state that interpretation explicitly in the plan. Do **not** build a mobile product card — that is Phase 19 territory at best, and nothing in PROD-05/06/07 asks for it. This needs an explicit note so `/gsd-verify-work` does not read the criterion literally and fail the phase for a page that never existed. Flagged as Open Question Q2.

### Script tags

Both base templates are **standalone** — `mobile_base.html:9-11` states verbatim that it *"does not inherit from base.html via Jinja template inheritance, so this tag is NOT inherited … and must be duplicated here verbatim."* [VERIFIED: `app/templates/mobile_base.html:6-13`]

The `price-cue.js` tag must therefore be added **twice**, mirroring the existing vendored-htmx line in each:

- `app/templates/base.html:22` — `<script src="/static/htmx.min.js" defer></script>`
- `app/templates/mobile_base.html:16` — same line

`defer` is correct and safe: D-10's delegated `document.addEventListener('input')` binds after parse and catches events on elements added later by HTMX.

## Cue Styling

### ⚠️ The colour collision is wider than CONTEXT.md states

CONTEXT.md flags `#e8effd` as "the search-match `mark` highlight (`style.css:252-255`)". Verified: `#e8effd` is used at **6 sites**, and it is an established **"selection / match" semantic token**, not just one rule. [VERIFIED: `app/static/style.css`]

| Line | Rule | Role |
|---|---|---|
| `143` | (element background) | selection tint |
| `254` | `mark { background: #e8effd; }` | search match |
| `279` | `.batch-picker tr.selected-batch td` | selected batch — comment: *"existing mark/search tint, NOT a new color"* |
| `286` | `.name-search-list li button:hover/:focus-visible` | comment at `:283`: *"the existing mark/search tint (#e8effd) — no new color role"* |
| `309` | `.mobile-card.selected` | selected card |
| `321` | `button.mobile-card.selected:hover` | selected card |

Two comments in the stylesheet police this token explicitly. **D-14's rule stands and is more important than CONTEXT.md conveyed:** the blue cue fill must be `#eff6ff`, never `#e8effd` — otherwise "above reference" becomes visually identical to "selected/matched" across six existing surfaces.

`#2563eb` is the **established accent token** (`style.css:3` header comment: *"accent #2563eb, destructive #b91c1c"*; used at `:38` links, `:164` focus outline, `:172,174` buttons). D-14's blue border reuses it correctly — no new colour role. **`#b45309` / `#fef9e7` / `#eff6ff` are the only genuinely new tokens**; add them with a comment naming their role, matching the stylesheet's documented convention.

## Write-Back Semantics Verification (PROD-07)

### D-15 confirmed: the receipt→card write-back is already shipped

`app/routes/receipts.py:23` [VERIFIED]:
```python
CARD_FILL_HINT = "Данные подставлены из карточки товара — новые цены обновят карточку."
```
The receipt **already states its write-back scope**, as a named constant. This is the exact pattern D-17 asks the sale to mirror. **No new write-back work — D-15 is a "do not regress" constraint, not a build item.**

### 🔴 The D-17 hint has **3 literal duplicates**, not one location

CONTEXT.md points at `app/routes/sales.py:152-157` as "the existing prefill-hint pattern". Verified: the string `"Цена подставлена из карточки товара — можно изменить."` is **hard-coded inline at 3 sites**, and its batch-source sibling at **3 more**. [VERIFIED: ripgrep]

| File:line | String | D-17 target? |
|---|---|---|
| `app/routes/sales.py:128` | `"Цена подставлена из карточки товара — можно изменить."` | ✅ **yes** |
| `app/routes/sales.py:253` | same string | ✅ **yes** |
| `app/routes/mobile_sales.py:226` | same string | ✅ **yes** — mobile, CONTEXT.md did not mention it |
| `app/routes/sales.py:154` | `"Цена подставлена из партии — можно изменить."` | ⚠️ see below |
| `app/routes/sales.py:249` | same batch string | ⚠️ |
| `app/routes/mobile_sales.py:223` | same batch string | ⚠️ |

Note `sales.py:156` (the line CONTEXT.md's `152-157` range points to) sets `fill_price_cents = product.sale_cents` but **sets no hint** — the card hint for that path is at `:128`. Editing only the cited range would miss all three real sites.

**Two planner decisions:**
1. **Extract to constants** mirroring `receipts.py:23`'s `CARD_FILL_HINT`. Three inline duplicates of a string D-17 is about to lengthen is exactly how one gets updated and two do not — and criterion 2 is per-entry-point, so a missed mobile hint is a real gap.
2. **Does the batch-source hint also get the scope clause?** D-17 says the *sale* hint must state "изменение сохранится только в этой продаже". A batch-sourced price is **equally sale-scoped** (D-15: `Batch.price_cents` stays frozen, nothing writes back). Leaving the batch hint silent implies its price *might* write back — the exact confusion D-17 exists to kill. **Recommend: apply the scope clause to both hint families** (6 sites, 2 constants). Flagged as Open Question Q3.

### D-18 confirmed: `Dictionary` genuinely has no price columns

[VERIFIED] `app/templates/pages/dictionary.html` and `partials/dictionary_rows.html` contain **zero price columns** — grep for price labels returns nothing. `app/routes/catalogs.py:1-5` docstring states verbatim: *"Read-only: no writes here."* D-18's premise is exactly correct.

**Important mapping for the planner:** criterion 1's *"the dictionary entry"* does **not** map to `/dictionary`. The page that shows ДЦ/ПЦ is **`app/templates/pages/catalog_detail.html:20-21`** (the catalog-contents view, `/catalogs/{...}`), which renders `Цена по каталогу` / `Цена консультанта` from `prices_for_catalog`. That is D-18's and D-19's actual target surface. `/dictionary` shows code→name only and needs no price work at all.

## Label Consolidation Surface (D-19)

Every operator-visible price label, verified. Two prices, two names, everywhere.

| File:line | Current label | Underlying field | Target |
|---|---|---|---|
| `app/templates/pages/product_form.html:60` | «Закупочная цена» | `Product.cost_cents` | **ДЦ** |
| `app/templates/pages/product_form.html:66` | «Цена продажи» | `Product.sale_cents` | **ПЦ** |
| `app/templates/pages/product_form.html:72` | «Минимальная цена продажи» | `min_sale_cents` | **unchanged — exempt, and must NOT read as a third price** |
| `app/templates/pages/product_form.html:78` | «Цена по каталогу» | `Product.catalog_cents` | 🗑️ deleted |
| `app/templates/pages/product_form.html:107` | «Последняя цена по каталогу» | `latest_price` | reference display + **D-09 caveat** |
| `app/templates/pages/product_form.html:110` | «консультант» | `latest_price.consultant_cents` | **ДЦ** (D-19's named example) |
| `app/templates/pages/catalog_detail.html:20` | «Цена по каталогу» | `CatalogPrice.consumer_cents` | **ПЦ** |
| `app/templates/pages/catalog_detail.html:21` | «Цена консультанта» | `CatalogPrice.consultant_cents` | **ДЦ** (D-19's named example) |
| `app/templates/partials/receipt_form.html:78` | «Цена по каталогу» | receipt `catalog` | 🗑️ deleted |
| `app/services/export.py:86` | `"Каталог"` CSV header | `catalog_cents` | 🗑️ deleted (**breaks `test_export.py:230`**) |
| `app/templates/partials/receipt_rows.html:19` | «Каталог» column | `payload.catalog_cents` | 🗑️ deleted (D-04) |

**`min_sale_cents` labelling risk:** PROD-05 exempts the *field*, but criterion 1 is a labelling criterion (D-19) and *«Минимальная цена продажи»* reads as a **third price** on the card — the exact confusion the 2026-07-14 report documented. The field must stay and PRICE-01 must not change, but consider a label that reads as a guardrail rather than a price (e.g. framing it beside the existing «Порог "мало на складе"» threshold at `:84`, which is the same *kind* of setting). **This is presentation-only — zero logic change.** Flagged as Open Question Q4; it is the one place where the exemption and criterion 1 rub against each other.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Money parsing in JS | A cents parser mirroring `to_cents` | `parseFloat(v.replace(',','.'))` only (D-13) | `app/core.py:28` is the sole authority; the cue is advisory and never submits money |
| Per-keystroke reference check | `hx-trigger="keyup"` round-trip | `data-ref-cents` + one delegated listener (D-10/D-12) | Destroys focus/caret; `price[]` inputs have no `id` so htmx cannot restore focus |
| Cue re-init after HTMX swaps | `htmx:afterSwap` re-binding | Event delegation on `document` (D-10) | Delegation covers dynamically added basket rows with zero re-init |
| Column drop on SQLite | `batch_alter_table` | Native `op.drop_column` (D-03) | House rule frozen in `0001:11-14` / `0008:11-17`; protects `uq_products_code_active` |
| Preserving historical prices | A snapshot/archive table | Nothing — the ledger already does it (D-04) | `app/db.py:22-43` DB triggers make criterion 4 hold **by construction** |
| Reference price "as of date" | An effective-date resolver | Nothing — not implementable (D-06) | **Verified: 6856 rows / 6856 codes; zero codes have >1 row** |
| Sale→card write-back | Any promotion machinery | Wording only (D-17) | D-16: it would erode criterion 5 via the `confirm=1` bypass |

**Key insight:** criterion 4 ("no historical money data lost") requires **no work at all** — it is enforced by DB triggers on an append-only ledger. The risk is not losing history; it is a plan *adding* machinery to "protect" history and thereby touching the ledger.

## Common Pitfalls

### Pitfall 1: The mobile receipt wizard breaks silently
**What goes wrong:** `catalog` is dropped from `models.py`/`services`, but `app/routes/mobile_receipts.py` still declares `catalog: str = Form("")` on 5 endpoints and passes `catalog_raw=catalog` at `:264` into a signature that no longer accepts it → `TypeError` at runtime.
**Why it happens:** CONTEXT.md's inventory omits mobile entirely; the wizard threads `catalog` through **hidden** inputs (`receipts_step_batch.html:15`, `receipts_step_confirm.html:30`) so it is invisible in the UI and easy to miss by eye.
**How to avoid:** work from §Authoritative Removal Surface, not CONTEXT.md's list. Sweep desktop and mobile in the same task.
**Warning sign:** `rg catalog app/routes/mobile_receipts.py` returns anything after the sweep.

### Pitfall 2: OOB swaps strip `data-ref-cents`
**What goes wrong:** the cue works until the operator types a code; then `product_price_autofill.html` OOB-swaps `#cost`/`#sale` and the cue dies on exactly those fields.
**Why it happens:** `hx-swap-oob="true"` **replaces the whole element**. `product_price_autofill.html:10,14` re-render bare inputs; any attribute not in that template is gone. Same hazard for `receipt_price_inputs.html:5` (`oob=True` targeting `#{{field}}-wrap`).
**How to avoid:** every template that can OOB-render a price input must emit `data-ref-cents` too. Because `receipt_price_inputs.html` is the single source for both static and OOB renders (its `:1-4` docstring says so), adding an optional `ref_cents` param there covers both paths at once — the product-form autofill partial needs the same treatment separately.
**Warning sign:** cue works on page load, stops after a code lookup.

### Pitfall 3: `test_export.py:230` breaks — and it is a real contract question
**What goes wrong:** dropping `export.py:98` + the `"Каталог"` header at `:86` fails `test_export.py:230`, which asserts the header row.
**Why it happens:** the CSV header is an asserted contract.
**How to avoid:** update the test in the same task. **But decide deliberately:** the CSV is part of the app, and criterion 1 says no third price appears *anywhere* — so the column should go. Removing it is a **user-visible export-format change** (any spreadsheet the operator keeps loses a column). Worth a line in the phase summary; it is not silent.
**Warning sign:** treating this test as "just an assertion to fix" without noticing the format change.

### Pitfall 4: `_PRICE_FIELDS` and the append-only audit trail
**What goes wrong:** `catalog_cents` is left in `app/services/catalog.py:156`'s `_PRICE_FIELDS = ("cost_cents", "sale_cents", "catalog_cents", "min_sale_cents")` → the audit loop reads a dropped attribute → `AttributeError` on every product edit.
**Why it happens:** the tuple drives a `getattr` loop; it is data, not a reference the type checker catches.
**How to avoid:** drop it from the tuple. **Do not** remove `price_history.html:22`'s label branch (D-04) — the tuple governs *future writes*, the template governs *past reads*. They are deliberately asymmetric.
**Warning sign:** conflating "stop writing" with "stop reading".

### Pitfall 5: `latest_price_for_code` fix-in-place silently widens scope
**What goes wrong:** dropping the `consumer_cents.is_not(None)` filter changes behaviour in 3 production callers, not just the cue.
**Why it happens:** the function looks cue-specific; it is not (3 callers verified).
**How to avoid:** decide Q1 explicitly and record it. If fixing in place, update `tests/test_pricing_feature.py:45,52,53` and add a test for the ДЦ-without-ПЦ code. Blast radius is exactly 1 code (verified) and strictly additive.
**Warning sign:** `test_pricing_feature.py` passing unchanged after a fix-in-place — that means the filter is still there.

### Pitfall 6: Assuming `product_form.html:104-111` is dead code
**What goes wrong:** deleting the `latest_price` block per CONTEXT.md's Integration Points → the card loses its reference display, D-19's line-110 relabel target vanishes, and the cue's `data-ref-cents` source disappears from context.
**Why it happens:** CONTEXT.md's phrasing ("the двойная строка … goes away with the column") reads as "delete `:104-111`", but that block reads `latest_price`, never `catalog_cents`.
**How to avoid:** delete `:77-81` (the input) only. Keep, relabel (D-19), and extend (D-09 caveat) `:103-114`.
**Warning sign:** `latest_price` unreferenced in `product_form.html` while `products.py:244` still supplies it.

### Pitfall 7: `hx-include` selector left dangling
**What goes wrong:** `receipt_form.html:29` includes `[name='catalog']` in its lookup request. After the input is deleted the selector silently matches nothing — no error, but it is a landmine if a future field is ever named `catalog`.
**How to avoid:** remove the selector fragment in the same edit as the input.
**Warning sign:** `rg "name='catalog'" app/templates` returns anything post-sweep.

### Pitfall 8: The `min_sale` input attracts a cue it must not have
**What goes wrong:** a blanket "add `data-ref-cents` to every price input on the card" sweep hits `product_form.html:73`, cueing `min_sale` against the catalog reference — inventing a *third* cued price and directly violating criterion 1.
**Why it happens:** it is structurally identical to the other two inputs (same `type`, `inputmode`, `placeholder`).
**How to avoid:** `min_sale` is a guardrail, has no catalog counterpart, and gets **no** `data-ref-cents`. The cue attaches to exactly two fields per surface.
**Warning sign:** any cue rendering on the minimum-price field.

## Code Examples

### The delegated cue listener (D-10/D-12/D-13)

```javascript
// app/static/price-cue.js — PROD-06 / D-10
// One delegated listener: covers desktop, mobile, and HTMX-added basket rows
// with no re-initialisation (D-12: never a round-trip per keystroke — swapping
// a focused input destroys focus AND caret, and sale_row.html's price[] inputs
// have no id for htmx to restore focus to).
//
// D-13: this is NOT client-side money math. The cue is advisory — it never
// parses for submission, computes, or persists. parse_optional_cents
// (app/services/catalog.py:106) stays the sole authority and the server
// re-renders the authoritative cue on every response. Parity with core.py:28
// to_cents is a one-liner: strip + comma→dot; space-separated thousands are
// rejected by both. Float math can flip the cue ONLY exactly at the equality
// boundary (12,505 → 1250 client vs 1251 server) — harmless for a hint, and
// the server re-render is the tiebreaker.
document.addEventListener("input", function (event) {
  const field = event.target;
  const ref = field.dataset ? field.dataset.refCents : null;
  if (!ref) return;                       // no reference → no cue (D-07: the MAIN path)
  const cents = Math.round(parseFloat(field.value.trim().replace(",", ".")) * 100);
  field.classList.remove("price-below", "price-above");
  if (!Number.isFinite(cents) || cents === Number(ref)) return;  // equal → neither (criterion 3)
  field.classList.add(cents < Number(ref) ? "price-below" : "price-above");
});
```

### Cue styles (D-14) — the `#e8effd` collision avoided

```css
/* Price cue (PROD-06 / D-14): reference-deviation hint on ДЦ/ПЦ inputs.
   Border + tint + text badge — colour alone fails WCAG 1.4.1 (Use of Color),
   and yellow-on-white is too low-contrast to read as a border by itself.
   The blue fill is #eff6ff and deliberately NOT #e8effd — that tint is the
   established search-match/selection token (mark, .selected-batch,
   .name-search-list hover, .mobile-card.selected). #2563eb is the existing
   accent token, reused here — no new colour role for the border. */
.price-below { border-color: #b45309; background: #fef9e7; }
.price-above { border-color: #2563eb; background: #eff6ff; }
```

### Reference wiring on the product card (no new query needed)

```jinja
{# app/routes/products.py:244 ALREADY supplies latest_price to this template. #}
<input type="text" id="cost" name="cost" inputmode="decimal" placeholder="0,00"
       {% if latest_price and latest_price.consultant_cents is not none %}
       data-ref-cents="{{ latest_price.consultant_cents }}"{% endif %}
       value="...">
```

## State of the Art

| Old approach | Current approach | When changed | Impact |
|---|---|---|---|
| `Product.catalog_cents` as the card's catalog reference | `CatalogPrice` table is the live reference (`catalog_prices`, 6856 rows) | `0011_catalog_prices` (CAT-05) | `catalog_cents` became a **stale write-once copy** — code `42125`: 420 vs live 1580. D-01's justification |
| D-02 (original): "catalog price is not this shop's sale price" | **D-02 superseded**: catalog `consumer_cents` doubles as the default sale price at prefill | before this phase | `receipts.py:266-268` + `products.py:144-145` state this verbatim. ⚠️ **The 2026-07-14 report quotes the superseded comment** — trust the code, not the report, on this point |
| SQLite could not `DROP COLUMN` | Native `DROP COLUMN` since SQLite 3.35 (runtime **3.50.4**) | pre-dates this repo | D-03; already exploited in `0002:75` |

**Deprecated/outdated in the inputs to this phase:**
- **CONTEXT.md's "SQLite 3.45.1"** — actual runtime is **3.50.4** (D-03 unaffected).
- **CONTEXT.md's "~12 files"** — actual is **36 sites / 17 files**.
- **CONTEXT.md's "`0008_batches.py:121` precedent"** — `0002:75` is the exact statement.
- **`reports/2026-07-14-price-fields.md:66-68`** quotes *"sale is ALWAYS None on this branch"*; `receipts.py:266-268` now reads the opposite (*"D-02 superseded"*). The report predates the change. **The report is a good map of the confusion; it is not current on this detail.**

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest 9.1.* [VERIFIED: `pyproject.toml`] |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]`, `testpaths = ["tests"]`, `pythonpath = ["."]` |
| Quick run command | `uv run pytest tests/test_pricing_feature.py tests/test_export.py -q` (**6.4s measured**) |
| Full suite command | `uv run pytest -q` (**682 passed in 128s measured, exit 0**) |
| Baseline | **682 passing, 3 warnings, green** as of 2026-07-16 — any post-change count below 682 is a regression |
| Linter | `uv run ruff check` / `uv run ruff format` (line-length 100, target py313) |

**No Makefile and no CI config exist** [VERIFIED: `ls Makefile`, `ls .github` both empty] — `uv run pytest` is the project's actual and only test entry point. Do not invent a `make test`.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| PROD-05 | `catalog_cents` gone from the ORM/reflected schema | unit | `uv run pytest tests/test_catalog.py -q -k columns` | ✅ **invert** `test_catalog.py:278` |
| PROD-05 | Product create/update ignores a `catalog` field | unit | `uv run pytest tests/test_catalog.py -q` | ✅ update `:58,520,521` |
| PROD-05 | Receipt no longer writes `payload.catalog_cents` | unit | `uv run pytest tests/test_receipts.py -q` | ✅ update `:72,203,684` |
| PROD-05 | Receipt no longer touches `product.catalog_cents` | unit | `uv run pytest tests/test_receipts.py -q` | ✅ **rewrite** `:613,632,658,677` (assign a dropped attr) |
| PROD-05 | CSV export has no «Каталог» column | unit | `uv run pytest tests/test_export.py -q` | ✅ **invert** `:230` |
| PROD-05 | Mobile receipt wizard completes with no `catalog` | integration | `uv run pytest tests/test_mobile_receipts.py -q` | ✅ exists — **must stay green** |
| PROD-05 | Desktop receipt form completes with no `catalog` | integration | `uv run pytest tests/test_receipts.py -q` | ✅ exists |
| PROD-05 | No price surface renders a 3rd price | integration | `uv run pytest tests/test_smoke.py -q` | ❌ **Wave 0** — see below |
| PROD-06 | Reference returns ДЦ **and** ПЦ independently | unit | `uv run pytest tests/test_pricing_feature.py -q` | ⚠️ **Wave 0** — no test for ДЦ-without-ПЦ |
| PROD-06 | No catalog row → `(None, None)`, no cue (D-07) | unit | `uv run pytest tests/test_pricing_feature.py -q` | ⚠️ **Wave 0** |
| PROD-06 | `data-ref-cents` present on ДЦ/ПЦ, absent on `min_sale` | integration | `uv run pytest tests/test_pricing_feature.py -q` | ❌ **Wave 0** |
| PROD-06 | OOB autofill re-render preserves `data-ref-cents` | integration | `uv run pytest tests/test_catalog.py -q` | ❌ **Wave 0** (Pitfall 2) |
| PROD-06 | Yellow/blue/neither on below/above/equal | **manual** | — | ❌ browser-only (JS not executed by TestClient) |
| PROD-07 | Receipt writes ДЦ/ПЦ back to the card (D-15) | unit | `uv run pytest tests/test_receipts.py -q` | ✅ exists — **regression guard** |
| PROD-07 | Sale price does **not** write back (D-15/D-16) | unit | `uv run pytest tests/test_sales.py -q` | ⚠️ **Wave 0** if no explicit assertion |
| PROD-07 | Sale hint states sale-only scope (D-17) | integration | `uv run pytest tests/test_sales.py tests/test_mobile_sales.py -q` | ❌ **Wave 0** (3 sites) |
| PROD-07 | Catalog detail offers «изменить цену» → card (D-18) | integration | `uv run pytest tests/test_catalogs_feature.py -q` | ❌ **Wave 0** |

### 🔴 Criterion 4 — historical money data preserved (highest-stakes sample)

Criterion 4 is the one a `catalog_cents` drop could break silently, because **the drop is irreversible (D-01)**. It holds by construction (D-04: ledger append-only, trigger-enforced) — but "by construction" must be *sampled*, not assumed.

| Check | Command | Expected |
|---|---|---|
| **Ledger triggers still reject UPDATE/DELETE** | `uv run pytest tests/test_ledger.py -q` | green — the structural guarantee behind criterion 4 |
| **8 historical `payload.catalog_cents` receipt ops survive the migration** | `uv run pytest tests/test_receipts.py -q -k payload` + post-migration DB probe | `SELECT count(*) FROM operations WHERE type='receipt' AND payload LIKE '%catalog_cents%'` still returns **8** |
| **Recorded receipt money unchanged** | `uv run pytest tests/test_receipts.py tests/test_history.py -q` | `unit_cost_cents`/`unit_price_cents` render as recorded |
| **Profit figures unchanged** | `uv run pytest tests/test_reports.py tests/test_finance_reports.py -q` | green — profit never read `catalog_cents` |
| **`price_history.html:22` label branch intact** | `uv run pytest tests/test_catalog.py -q` | branch present (D-04: 0 rows render it, keep anyway) |
| **Migration round-trips** | `uv run alembic upgrade head && uv run alembic downgrade 0013 && uv run alembic upgrade head` | clean; downgrade re-adds the column **empty** (D-01) |
| **Pre-drop snapshot exists** | inspect `backups/` | `app/services/backup.py` `VACUUM INTO` snapshot taken before first `0014` run — **the only recovery path for the 6 discarded values** |

**The decisive sample:** the receipt-op payload count must be **8 before and 8 after**. That single number is criterion 4's canary — the 6 discarded `Product.catalog_cents` values are *intentionally* gone (D-01), while the 8 ledger payloads are *historical money that must survive*. Do not conflate them.

### 🔴 Criterion 5 — PRICE-01 regression guard

**Structurally independent of this phase.** `app/services/sales.py:206-234` reads **only** `min_sale_cents`; `catalog_cents` appears nowhere in `sales.py`. [VERIFIED] Risk is low — but it is a named criterion, so it gets an explicit sample.

**9 existing guard tests** [VERIFIED: `tests/test_sales.py`, `tests/test_mobile_sales.py`]:

| Test | File:line |
|---|---|
| `test_negative_price_rejected_without_min_sale_configured` | `test_sales.py:333` |
| `test_negative_price_rejected_with_min_sale_configured` | `test_sales.py:351` |
| `test_below_minimum_blocks_without_confirm` | `test_sales.py:443` |
| `test_below_minimum_confirm_writes` | `test_sales.py:462` |
| `test_below_minimum_boundary_equal_price_passes_silently` | `test_sales.py:483` |
| `test_min_sale_unset_never_warns_even_at_zero_entered_price` | `test_sales.py:502` |
| `test_oversell_and_below_minimum_both_reported_together` | `test_sales.py:519` |
| `test_web_sale_below_minimum_shows_warning_and_confirm_writes` | `test_sales.py:620` |
| `test_price_below_minimum_warns_zero_writes_then_confirm_writes` | `test_mobile_sales.py:509` |

**Command:** `uv run pytest tests/test_sales.py tests/test_mobile_sales.py -q`
**Gate:** all 9 green, **unmodified**. If a plan needs to *edit* any of these 9, that is a criterion-5 violation signal — stop and escalate. `min_sale_cents` is exempt from removal, so no PRICE-01 test should require changes.

### Sampling Rate

- **Per task commit:** the touched module's file(s), e.g. `uv run pytest tests/test_catalog.py -q` (seconds), plus `uv run ruff check`
- **Per wave merge:** `uv run pytest tests/test_sales.py tests/test_mobile_sales.py tests/test_receipts.py tests/test_mobile_receipts.py tests/test_catalog.py tests/test_export.py tests/test_pricing_feature.py -q`
- **Phase gate:** `uv run pytest -q` → **must report ≥ 682 passed** (baseline measured 2026-07-16), then `/gsd-verify-work`
- **Migration gate:** upgrade/downgrade/upgrade round-trip against a **copy** of `data/myorishop.db`, never the live file

### Wave 0 Gaps

- [ ] `tests/test_pricing_feature.py` — reference lookup returns ДЦ when ПЦ is NULL (**D-08's 1 live code**); returns `(None, None)` for an unknown code (D-07)
- [ ] `tests/test_pricing_feature.py` (or `test_catalog.py`) — `data-ref-cents` rendered on ДЦ/ПЦ inputs, **absent on `min_sale`** (Pitfall 8)
- [ ] `tests/test_catalog.py` — OOB autofill re-render preserves `data-ref-cents` (Pitfall 2)
- [ ] `tests/test_sales.py` — sale price does **not** mutate `Product.sale_cents` (D-15/D-16 explicit assertion)
- [ ] `tests/test_sales.py` + `tests/test_mobile_sales.py` — prefill hint carries the sale-only scope clause (D-17, **3 sites**)
- [ ] `tests/test_catalogs_feature.py` — catalog detail «изменить цену» links to the product card (D-18)
- [ ] **Manual browser check** — yellow below / blue above / neither at equality (criterion 3). TestClient does not execute JS, so the cue's *visual* behaviour cannot be automated with this stack. Assert `data-ref-cents` + the CSS classes server-side; verify colour by eye. **Recommend a `checkpoint:human-verify` task.**

No framework install needed — pytest and httpx are already dev dependencies.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| Python | everything | ✅ | 3.13.13 | — |
| SQLite | native DROP COLUMN (D-03) | ✅ | **3.50.4** (needs ≥ 3.35) | — |
| SQLAlchemy | ORM | ✅ | 2.0.51 | — |
| Alembic | `0014` | ✅ | 1.18.* | — |
| pytest | validation | ✅ | 9.1.* (682 green, 128s) | — |
| uv | runner | ✅ | — | plain `pip`/`venv` |
| Live DB | migration target | ✅ | `data/myorishop.db`, head `0013` | — |
| `backups/` snapshots | D-01 safety net | ✅ | `VACUUM INTO` on startup | — |
| htmx | UI | ✅ | 2.0.10 vendored, offline | — |
| Node/npm | — | ❌ | — | **not needed** — no build step, hand-written JS (D-10) |
| Browser | criterion 3 manual check | ✅ | — | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none material.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | Removing the «Каталог» CSV export column is desired, not a contract break | Pitfall 3 | Operator's spreadsheets lose a column unannounced. Criterion 1 implies removal, but export is not named in it |
| A2 | Fix-in-place on `latest_price_for_code` is acceptable scope | §Reference Lookup / Q1 | Widens behaviour to 3 callers beyond PROD-06. Strictly additive; blast radius = 1 verified code |
| A3 | Criterion 1's "desktop and mobile" means "surfaces that exist per platform" | §Input Surface / Q2 | Literal reading fails the phase for a mobile product card that has never existed |
| A4 | The batch-source prefill hint should also carry D-17's scope clause | §Write-Back / Q3 | D-17 names only the card hint; the batch hint's silence implies write-back |
| A5 | `min_sale_cents`'s *label* may be reworded (field/logic untouched) | §Label Consolidation / Q4 | PROD-05 exempts the field; D-19 unifies labels. Presentation-only either way |
| A6 | `downgrade()` restoring an empty column beats `NotImplementedError` | §Alembic | A downgrade silently yielding NULLs could mislead — mitigated by the docstring |
| A7 | The 8 historical `payload.catalog_cents` receipt ops need no UI at all | §Criterion 4 | D-04 says the data rests unread; if the operator ever needs it, it is queryable but not rendered |

**All 19 CONTEXT.md decisions are VERIFIED, not assumed** — every falsifiable claim reproduced against the live DB and the code (§Live-DB Verification). The assumptions above are **mine**, arising from gaps CONTEXT.md did not cover. A1–A5 are genuine judgement calls the planner (or the operator) should confirm; A6–A7 are low-risk.

## Open Questions (RESOLVED)

> **All five resolved 2026-07-16** — Q2/Q4/Q1 by operator decision, Q3/Q5 on this document's recommendation. Recorded as **D-20..D-24 in `18-CONTEXT.md`** and encoded in the plans. Resolution noted inline per question below.

1. **Fix `latest_price_for_code` in place, or add a new function?** (Claude's Discretion per CONTEXT.md)
   - **✅ RESOLVED → D-22: fix in place** (operator-confirmed). Drop the `consumer_cents.is_not(None)` filter; update `tests/test_pricing_feature.py:45,52,53`; add the ДЦ-without-ПЦ test; rewrite the now-false docstring. Encoded in plan **18-01**.
   - **What we know:** the `consumer_cents.is_not(None)` filter starves ДЦ in **3 live production callers** (`products.py:147`, `products.py:244`, `receipts.py:289`), not just the cue. All callers already null-check fields independently. Blast radius: exactly **1 code** (verified). Strictly additive.
   - **What's unclear:** whether repairing 3 pre-existing bugs is in scope for a consolidation phase.
   - **Recommendation:** **fix in place**; update `tests/test_pricing_feature.py:45,52,53`; add the ДЦ-without-ПЦ test; fix the `pricing.py:3-5` docstring while there (closes a Deferred item at zero cost). Note the autofill improvement in the phase summary so it is not a surprise.

2. **How is criterion 1's "desktop and mobile" satisfied where the surface does not exist?**
   - **✅ RESOLVED → D-20** (operator-decided): interpret as *"every price surface that EXISTS on each platform shows exactly two prices."* Do NOT build a mobile product card (Phase 19 territory). Interpretation stated in plan **18-08** `must_haves` so `/gsd-verify-work` does not fail criterion 1 literally.
   - **What we know:** **mobile has no product card and no dictionary page** (verified: no `mobile_products.py`, no `mobile_pages/product_form.html`). Mobile price surfaces are exactly two: receipt wizard, sale wizard.

3. **Does the batch-source prefill hint also get D-17's scope clause?**
   - **✅ RESOLVED → D-23: yes, both hint families** (on recommendation). Extract to 2 named constants mirroring `receipts.py:23`'s `CARD_FILL_HINT`; 6 sites. Encoded in plan **18-06**.
   - **What we know:** *"Цена подставлена из партии"* fires at `sales.py:154`, `sales.py:249`, `mobile_sales.py:223`. A batch price is equally sale-scoped (D-15: `Batch.price_cents` frozen, no write-back).

4. **May `min_sale_cents`'s label change, given PROD-05 exempts the field?**
   - **✅ RESOLVED → D-21: label/placement only** (operator-decided). Regroup as a guardrail setting beside the low-stock threshold; **zero logic change, no cue, no `data-ref-cents`**; PRICE-01 untouched. Encoded in plan **18-05** (relabel) + **18-07/18-08** (no-cue guards).
   - **What we know:** the field, its logic, and PRICE-01 are frozen (criterion 5). But *«Минимальная цена продажи»* sits directly under ДЦ/ПЦ on the card and **reads as a third price** — the exact confusion the 2026-07-14 report documented. D-19 makes criterion 1 a labelling criterion.

5. **Does the operator need the 6 `catalog_cents` values recorded anywhere before the drop?**
   - **✅ RESOLVED → D-24** (on recommendation): a fresh `VACUUM INTO` snapshot must exist immediately before the first `0014` run, and the 6 `(code, catalog_cents)` pairs go into the phase summary. Encoded as the `[BLOCKING]` pre-migration task in plan **18-04**.
   - **What we know:** D-01 discards them deliberately; `backups/` holds `VACUUM INTO` snapshots (17 exist), so they are recoverable from a snapshot but not from the migration.

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: high`. This phase is a **single-operator, localhost-only, offline** app (CLAUDE.md: *"1 operator in year one — no auth complexity needed in v1"*, *"Runs locally, UI in browser at localhost — no internet required for v1"*). No auth exists by project decision. Assessed against the phase's actual change surface: a column drop, a read-only lookup, price inputs, and a static JS file.

### Applicable ASVS Categories (Level 1)

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | **no** | No auth in v1 by project decision (single local operator). This phase adds no endpoint that changes that. |
| V3 Session Management | **no** | No sessions exist. |
| V4 Access Control | **no** | No users/roles. D-18's «изменить цену» link targets an **existing** product-card route — no new privileged surface. |
| V5 Input Validation | **yes** | `parse_optional_cents` (`app/services/catalog.py:106`) → `to_cents` (`app/core.py:28`) stays the **sole** authority (D-13). The cue never parses for submission. Removing the `catalog` field **shrinks** the input surface by 3 form params (desktop) + 5 (mobile). |
| V6 Cryptography | **no** | No secrets, keys, or crypto. Money is integer cents, never floats (CLAUDE.md). |
| V7 Error Handling & Logging | **partial** | Existing server-side `{% if errors.x %}` pattern unchanged. `0014` must not log the 6 discarded values. |
| V12 Files & Resources | **no** | `price-cue.js` is a first-party static file served by the existing `/static` mount. No upload, no new mount. |
| V13 API | **no** | No new endpoints. |

### Known Threat Patterns for FastAPI + Jinja2 + HTMX

| Pattern | STRIDE | Standard Mitigation | Status this phase |
|---|---|---|---|
| XSS via `data-ref-cents` | Tampering | Jinja2 autoescape (on by default in `Jinja2Templates`) | ✅ value is an `int` from the DB, never operator text. **Do not** render it via `\| safe` |
| XSS via cue badge text | Tampering | Autoescape; badge text is a **static Russian literal**, never interpolated input | ✅ by design (D-14) |
| SQL injection in the reference lookup | Tampering | SQLAlchemy Core/ORM `select()` with bound params — **never** f-string SQL | ✅ `pricing.py` already uses `select().where()`; keep it (also CLAUDE.md's portability rule) |
| Client-side money tampering | Tampering | Server re-validates every submission via `parse_optional_cents` | ✅ D-13 — the cue is advisory and **never submits** |
| Ledger tampering / history rewrite | Repudiation | DB triggers `RAISE(ABORT, 'operations ledger is append-only')` (`app/db.py:22-43`) | ✅ D-04 — `0014` touches `products` only, **never** `operations`. Guarded by `tests/test_ledger.py` |
| Irreversible data loss | Denial of Service | `VACUUM INTO` snapshot before migration (`app/services/backup.py`) | ⚠️ **D-01 is deliberate.** Confirm a fresh snapshot exists before the first `0014` run (Q5) |
| CSV injection in export | Tampering | `_csv_safe()` already wraps every exported cell (`app/services/export.py`) | ✅ removing the `catalog_cents` column **reduces** the exported surface |
| Supply-chain (slopsquatting) | Tampering | — | ✅ **N/A — zero packages added.** `price-cue.js` is hand-written first-party code, not a vendored asset |

**Verdict: no `high` findings — nothing to block on.** This phase **reduces** the input surface (8 fewer form params) and adds **no** package, endpoint, auth surface, or network call. The only security-adjacent item is D-01's deliberate, operator-approved data discard, whose control is the existing pre-migration backup (Open Question Q5). The one rule the planner must hold: `data-ref-cents` renders an **integer from the database** — if it ever renders operator-supplied text, autoescape must not be bypassed.

## Sources

### Primary (HIGH confidence) — this repository, verified 2026-07-16
- `data/myorishop.db` — live SQLite probe: head `0013`, 7 active products, 0 backfill candidates, 6 `catalog_cents`, 6856/6856 catalog rows/codes, 0 multi-catalog codes, 1 starved ДЦ code, 0 `price_change` ops on `catalog_cents`, 8 receipt payload ops. **All 9 CONTEXT.md claims reproduced exactly.**
- `alembic/versions/` — `0001` (WR-06 + batch caveat), `0002:39,75` (**exact `catalog_cents` add/drop precedent**), `0003` (`uq_products_code_active` partial index), `0008:11-17,121` (batch-mode trigger warning), `0013` (current head, revision-ID convention)
- `app/services/pricing.py:14-32` — `latest_price_for_code` and the D-08 filter
- `app/routes/products.py:130-161,244` — CAT-05 autofill; `fill_cost` unreachability; `latest_price` already in card context
- `app/services/receipts.py:261-299` — `lookup_prefill`; the *"D-02 superseded"* comment
- `app/services/sales.py:206-234` — PRICE-01; verified to read only `min_sale_cents`
- `app/routes/sales.py:128,154,249,253`, `app/routes/mobile_sales.py:223,226`, `app/routes/receipts.py:23` — the hint surface (3 + 3 sites)
- `app/routes/mobile_receipts.py:106-264` — **the mobile `catalog` surface CONTEXT.md missed**
- `app/templates/` — full price-input/label enumeration, desktop + mobile; `base.html:22` / `mobile_base.html:6-16` (standalone, no inheritance)
- `app/static/style.css:3,143,254,279,283,286,309,321` — `#e8effd` used at **6 sites**; `#2563eb` is the accent token
- `pyproject.toml` — pytest/ruff config; no Makefile, no CI
- Local runtime probe — Python 3.13.13, SQLite **3.50.4**, SQLAlchemy 2.0.51
- `uv run pytest -q` — **682 passed, 128s, exit 0** (baseline)
- `rg "hx-on"` — **exactly 42 occurrences** across 23 templates (**D-11 verified**)

### Secondary (MEDIUM confidence)
- `.planning/phases/18-two-price-model-consolidation/18-CONTEXT.md` — D-01..D-19 (binding; independently re-verified above)
- `.planning/ROADMAP.md` §Phase 18, `.planning/REQUIREMENTS.md` PROD-05/06/07
- `plan1.txt:20` — operator's raw two-price + cue wording
- `CLAUDE.md` — integer-cents money rule, portable-ORM rule, what-not-to-use

### Tertiary (LOW confidence — superseded)
- `reports/2026-07-14-price-fields.md` — accurate map of the confusion, but **`:66-68` quotes the superseded D-02 comment**; `receipts.py:266-268` now states the opposite. Trust the code.

### No external sources consulted
No package research, registry lookups, or web searches were required: this phase adds **no dependencies**, and the stack is settled by `CLAUDE.md`. Every claim above is grounded in this repository or its live database. **Zero `[ASSUMED]` package names appear in this document.**

## Metadata

**Confidence breakdown:**
- **Removal surface: HIGH** — exhaustive ripgrep over `app/ tests/ scripts/ alembic/`, cross-checked with a `catalog` form-field grep that `catalog_cents` alone misses. 36 sites / 17 files.
- **Alembic mechanics: HIGH** — conventions read from all 13 existing migrations; head confirmed against the live DB; the exact drop statement already exists at `0002:75`.
- **Reference lookup: HIGH** — full source read, all callers traced, starvation reproduced against live data (1 code).
- **Input surface: HIGH** — enumerated by ripgrep across both template trees; mobile's missing product card confirmed by directory listing.
- **Test surface: HIGH** — baseline measured (682/128s); PRICE-01's 9 guards located by name; commands verified by execution, not inferred.
- **Pitfalls: HIGH** — each derives from a verified code site, not from generic domain knowledge.
- **CONTEXT.md decisions: HIGH** — all 9 falsifiable live-DB claims reproduced exactly.
- **Open Questions: MEDIUM** — Q1–Q4 are scope/wording judgements needing planner or operator confirmation, not technical unknowns.

**Research date:** 2026-07-16
**Valid until:** 2026-08-15 (30 days — internal codebase research, no external dependencies; **invalidate immediately** if the price-list importer runs, `data/myorishop.db` gains products, or any migration past `0013` lands)
