# Phase 18: Two-Price Model Consolidation (ДЦ/ПЦ) - Context

**Gathered:** 2026-07-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Every price the operator sees or edits anywhere in the app is one of exactly two — **ДЦ** (cost/distributor = `Product.cost_cents`) or **ПЦ** (sale/catalog = `Product.sale_cents`). `Product.catalog_cents` is eliminated. A colour cue (yellow below / blue above) marks any typed price that deviates from the catalog reference. ДЦ/ПЦ stay editable from the product card, the goods receipt, and the sale form; the dictionary redirects to the product card.

**Explicitly NOT in this phase:** `Product.min_sale_cents` is a guardrail threshold, not a displayed price — it is not removed, not renamed, not migrated. The PRICE-01 below-minimum sale warning (shipped v1.1, Phase 7) must keep working unchanged (success criterion 5 is its regression guard).

</domain>

<decisions>
## Implementation Decisions

### catalog_cents elimination (PROD-05)

- **D-01: Discard the values, drop the column in this phase.** `Product.catalog_cents` is dropped via a single Alembic migration. Its 6 live values are NOT migrated anywhere. Grounded in live-DB evidence (7 active products, alembic head `0013`):
  - **0 backfill candidates** — there is no product where `sale_cents IS NULL AND catalog_cents IS NOT NULL`. Any `backfill-if-NULL` clause is a provable no-op; write it only as a defensive guard, not as a migration step.
  - **6 of 6 disagree**, always in the same direction (`cost < sale < catalog`, e.g. code `32021`: 45000 / 69000 / 89000). `catalog_cents` is the Oriflame list price; `sale_cents` is what the operator actually charges (17–30% below list). The disagreement is meaningful business data, not drift.
  - The column is stale by construction: code `42125` holds `catalog_cents=42000` against a live `CatalogPrice.consumer_cents=158000`. The real catalog price is served from the `catalog_prices` table, never from this write-once copy.
- **D-02: Never overwrite `sale_cents` from `catalog_cents`.** That was considered and rejected — it would re-price the live shop upward 17–30% (690→890) and silently change every future prefill and profit figure.
- **D-03: Use native `op.drop_column("products", "catalog_cents")` — NOT `batch_alter_table`.** `render_as_batch=True` (`alembic/env.py:48,72`) only affects autogenerate rendering. SQLite 3.45.1 supports native DROP COLUMN, and `catalog_cents` appears in no index/trigger/view. Batch mode would drop and recreate `products` along with its partial unique index `uq_products_code_active` (`sqlite_where`) — an avoidable footgun. Precedent for native drop: `alembic/versions/0008_batches.py:121`.
- **D-04: Historical ledger payloads keep `catalog_cents` forever — that is fine and untouched.** 8 receipt operations carry `payload.catalog_cents`. The ledger is append-only and DB-trigger-enforced (`app/db.py:22-43`, `RAISE(ABORT, 'operations ledger is append-only')`), so criterion 4 holds by construction. Consequences:
  - **Drop the «Каталог» column from the receipt history view** (`app/templates/partials/receipt_rows.html:19,31`). The receipt's defining money (`unit_cost_cents`→ДЦ, `unit_price_cents`→ПЦ) still renders; `payload.catalog_cents` simply rests unread. This satisfies criterion 1 (no third price surfaces anywhere).
  - **Keep the `catalog_cents` label branch in `app/templates/partials/price_history.html:22`.** It costs one line, renders for 0 live rows (there are **0** `price_change` ops targeting `catalog_cents`, so it cannot violate criterion 1), and removing it would let the `{% else %}` fallback one day show a raw `catalog_cents` string to the operator.

### Colour cue reference price (PROD-06)

- **D-05: The reference is the code's single `CatalogPrice` row. Pairing: `consultant_cents` → ДЦ, `consumer_cents` → ПЦ.** Same rule at every entry point. This pairing is already consistent across `app/models.py:268-270`, `app/routes/products.py:147-160`, and quick-task 260714-fix — do not invent a new mapping.
- **D-06: "Catalog current at the operation's date" is NOT implementable — do not plan for it.** `catalog_prices` holds 6856 rows across 6856 distinct codes: **zero** codes carry more than one catalog, and `import_master_pricelist.py` guarantees that shape by keying its `collected` dict on code alone (~line 123). There is no per-period history and no effective-date column to resolve against.
- **D-07: "No catalog row → no cue + a muted hint" is the MAIN path, not an edge case.** 6 of 7 live products have no `CatalogPrice` row at all. Ship it as deliberate, visible behaviour — a silently absent cue would read as "your price matches the reference", which is worse than saying nothing.
- **D-08: Do NOT reuse `latest_price_for_code` unmodified** (`app/services/pricing.py:24-32`). It filters `consumer_cents.is_not(None)`, so a code with a ДЦ but no ПЦ returns `None` and its **ДЦ cue is starved despite a valid reference existing** (1 such code today). The cue needs a lookup that does not gate ДЦ on ПЦ's presence.
- **D-09: Accept the honest caveat rather than hiding it.** Each code's single row is its *last catalog appearance* (live data spans 2015 → 2026), so "the reference" means "the price when this code was last in a catalogue" — years stale for discontinued codes — and each re-import wipes and redefines it. Name this in the UI wording; do not pretend the reference is current.

### Colour cue mechanism (PROD-06 / criterion 3)

- **D-10: One delegated listener in a new `app/static/price-cue.js` (~15 lines).** A single `document.addEventListener('input')` reading `data-ref-cents` off the field. Delegation covers desktop + mobile + HTMX-added basket rows with no re-initialisation, and keeps the rule in one place.
- **D-11: This is NOT the app's first hand-written JS** — that objection does not apply. `hx-on:` appears 42 times across templates (including conditional swap-suppression logic at `product_form.html:19`), and `base.html:6-14` already carries an inline viewport-redirect script. Alpine.js's deferred caveat is **not** triggered: there is no client-side *state* here, only a stateless read-compare-toggle.
- **D-12: Never use an HTMX round-trip per keystroke.** Swapping a focused `<input type="text">` destroys focus AND caret position while the operator is mid-typing; the basket's `price[]` inputs (`sale_row.html:35`) have no `id`, so htmx cannot even attempt focus restore; and it fires N requests per keystroke on an N-row basket. This repo has already been bitten by swaps clobbering in-flight typing — the `hx-on::before-swap` guard at `product_form.html:15-19` (Pitfall 5) exists for exactly that reason.
- **D-13: The "no client-side money math" convention is NOT violated.** The cue is advisory: it never parses, computes, or submits money. `parse_optional_cents` (`app/services/catalog.py:106`) stays the sole authority and the server re-renders the authoritative cue on every response. Client/server parse parity is a one-liner, not a reimplementation: `core.py:28` `to_cents` does `.strip().replace(",", ".")` and rejects space-separated thousands, so `parseFloat(v.replace(',','.'))` accepts exactly what the server accepts. Float math can flip the cue only exactly at the equality boundary (`12,505` → 1250 client vs 1251 server) — harmless for an advisory hint; the server re-render is the tiebreaker. Note this in a code comment.
- **D-14: Visual form — coloured border + soft background tint + short text badge** («ниже справочной» / «выше справочной»), reusing the existing `.muted` idiom. Colour alone fails WCAG 1.4.1 (Use of Color), and yellow-on-white is too low-contrast to read as a border by itself. Concrete values: *below* = amber border `#b45309` on `#fef9e7` fill; *above* = accent-blue border `#2563eb` on `#eff6ff` fill. **Collision to avoid: `#e8effd` is already the search-match `mark` highlight (`app/static/style.css:252-255`)** — the blue cue must not reuse that tint.

### Price write-back semantics (PROD-07)

- **D-15: Asymmetric by entry point — receipt writes back to the card, sale stays scoped to the sale.** This is the domain-correct rule and is already the shipped behaviour:
  - A **receipt** is a restock event establishing a new standing ДЦ/ПЦ → it writes back to the product card. **Already implemented** (`app/services/receipts.py:169-196`, decision D-07 of the earlier milestone) with one `price_change` op per changed field and the PD-8 "empty never clears" rule. No new work; do not regress it.
  - A **sale** is a negotiation with one customer → the price stays on the operation. `Batch.price_cents` stays frozen. Nothing writes back to `Product`.
- **D-16: Reject "sale writes back to the card".** It would turn a one-off discount into the product's permanent ПЦ, and its interaction with `min_sale_cents` is genuinely bad: writing a below-minimum sale price back to `sale_cents` leaves the card prefilling below its own floor, tripping the PRICE-01 warning on every subsequent sale and pushing the operator to reflex-click the `confirm=1` bypass — which **also clears the oversell check** (`app/services/sales.py:181`, one flag clears both). That actively erodes criterion 5.
- **D-17: Close the discoverability gap with wording, not machinery.** Extend the existing prefill-hint pattern (`app/routes/sales.py:152-157`, "Цена подставлена из карточки товара — можно изменить") to state the scope: **"— изменение сохранится только в этой продаже"**. A per-line "сохранить в карточку" checkbox was considered and rejected as basket clutter.
- **D-18: The dictionary entry point redirects to the product card — it does not become editable.** "Editing the price in the dictionary" is not implementable as written: the `Dictionary` table has **no price columns at all** (code→name only, `app/models.py:235-256`). The ДЦ/ПЦ shown there come from `CatalogPrice`, which is not "our price" but a published historical fact ("what Oriflame charged in catalog 07/26"), served by an explicitly read-only route (`app/routes/catalogs.py:4`). The importer does `session.query(CatalogPrice).delete()` then bulk-inserts (`scripts/import_master_pricelist.py:136-137`), so **any hand edit is silently destroyed on the next re-import** — a direct hit on the core value "without losing any data". Implementation: the dictionary/catalog row shows ДЦ/ПЦ read-only and offers **«изменить цену»**, which opens the *product card* for that code (creating it if it does not exist).

### Label consolidation (PROD-05 / criterion 1)

- **D-19: Unify the price labels on ДЦ/ПЦ across every surface.** The same field is currently labelled inconsistently: `catalog_detail.html:21` says "Цена консультанта" while `product_form.html:110` says just "консультант" for the identical `CatalogPrice.consultant_cents`. Criterion 1 ("no third or fourth price field appears anywhere") is a *labelling* criterion as much as a schema one — two prices, two names, everywhere, desktop and mobile.

### Claude's Discretion

- Exact Russian wording of the cue badges and the muted "нет справочной цены" hint.
- Whether the ДЦ/ПЦ reference lookup lands as a new function in `app/services/pricing.py` or a fix to the existing one (D-08 only fixes the *behaviour*, not the location).
- Whether to correct the two misleading docstrings noted in Deferred while already editing those files.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Price-field inventory (read this first)
- `reports/2026-07-14-price-fields.md` — the operator-commissioned inventory of every price field: where each is stored, who writes it, exactly what is prefilled at sale time, and the four documented sources of confusion this phase resolves. **Untracked in git** (lives in `reports/`, not committed) — read it from disk, do not expect it in the history.

### Requirements and scope
- `.planning/REQUIREMENTS.md` §Products — PROD-05, PROD-06, PROD-07 (lines 35-37), including the `min_sale_cents` exemption clause.
- `.planning/ROADMAP.md` §"Phase 18: Two-Price Model Consolidation (ДЦ/ПЦ)" — goal, the 5 success criteria, and the operator's 2026-07-15 scope note.
- `.planning/PROJECT.md` — Key Decisions table; core value ("without losing any data").
- `.planning/STATE.md` §Blockers/Concerns — the resolved Phase 18 entry recording the `min_sale_cents` exemption and its rationale.
- `plan1.txt` (repo root, untracked) — the operator's original raw notes that PROD-05/06/07 were derived from. Source of the two-price wording and the yellow/blue cue rule: "ДЦ = дистрибьютерская цена = цена покупки = себестоимость. ПЦ = цена продажи = цена каталога… цена будет помечена цветом желтым если цена ниже рекомендуемой в справочнике или голубым если выше".

### Money and ledger rules
- `CLAUDE.md` §"What NOT to Use" — integer minor units only, never FLOAT/REAL for money; portable SQLAlchemy Core/ORM constructs only (no SQLite-specific SQL).
- `CLAUDE.md` §"Stack Patterns by Variant" — the append-only operation log is the sync foundation; never UPDATE/DELETE its rows.
- `app/db.py:22-43` — the DB triggers that enforce ledger immutability (`RAISE(ABORT, 'operations ledger is append-only')`).

### Prior art this phase must not regress
- `app/services/sales.py:206-234` — the PRICE-01 below-minimum warning (criterion 5's regression guard) and its `confirm=1` bypass at `sales.py:181`.
- `app/services/receipts.py:169-196` — the shipped receipt→card write-back (D-07) and the PD-8 "empty never clears" rule that D-15 preserves.
- `.planning/milestones/v1.1-ROADMAP.md` — Phase 7 (PRICE-01) as originally scoped.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/pricing.py` (`latest_price_for_code`, `price_history_for_code`) — the code→catalog-price lookup the cue needs, **but see D-08**: its `consumer_cents IS NOT NULL` filter starves the ДЦ cue and must not be reused as-is.
- `app/templates/partials/product_price_autofill.html` + `/products/lookup-price` — the shipped `hx-swap-oob` pattern that rewrites price inputs by id after a code lookup (CAT-05). Precedent for server-driven field updates; it must keep working once `catalog_cents` is gone (it currently emits a `catalog` input).
- `app/core.py:28` `to_cents` — the canonical RU-comma money parser; the JS cue must mirror its accept-set exactly (D-13).
- `app/services/catalog.py:156` `_PRICE_FIELDS` — the price-change audit tuple; drop `catalog_cents` from it.
- `app/services/backup.py` — `VACUUM INTO` startup snapshot; 17 snapshots already exist in `backups/`. This is the safety net behind D-01's irreversible drop.

### Established Patterns
- Server-rendered Jinja2 + HTMX 2.0.10 (vendored, offline). No SPA, no build step, plain CSS in one stylesheet.
- Money is integer cents end-to-end; display via the `| cents` Jinja filter; inputs are `type="text" inputmode="decimal"` with `placeholder="0,00"`.
- Validation errors render server-side as `{% if errors.x %}<p class="error">…</p>{% endif %}` — one message per field.
- Desktop and mobile are separate route/template trees (`app/routes/mobile_*.py`); criterion 1 requires parity, so every price surface is touched twice.
- Alembic with `render_as_batch=True` for SQLite — but see D-03 for why this migration goes native.

### Integration Points
Full `catalog_cents` removal surface (~12 files, verify before editing):
- `app/models.py:153` (column definition; D-19 comment says "three optional prices" — update to two + the min guardrail)
- `app/services/catalog.py:106,125,156,211,236,261` (parse / create / update / audit tuple)
- `app/services/receipts.py:116,157,177,246,285` — **note line 246 writes `payload={"catalog_cents": …}` into the append-only ledger**; the write stops, the history stays (D-04)
- `app/services/export.py:98` (CSV export column)
- `app/routes/products.py:155` (`"catalog_cents": latest.consumer_cents if latest else None`)
- `app/templates/pages/product_form.html:79` (the input), `:104-111` (the "сохранённая vs последняя из каталога" двойная строка that exists only because the two drift — it goes away with the column)
- `app/templates/pages/categories.html:34`, `app/templates/partials/product_rows.html:60` (list columns)
- `app/templates/partials/receipt_rows.html:19,31` (history column — drop per D-04)
- `app/templates/partials/price_history.html:22` (audit label — **keep** per D-04)
- `app/templates/partials/product_price_autofill.html` (the OOB `catalog` input)
- `tests/test_catalog.py`, `tests/test_receipts.py` (~10 assertions)

New surface for the cue: `app/static/price-cue.js` (new file), a `<script>` tag in both base templates, `data-ref-cents` on every ДЦ/ПЦ input across the product card / receipt / sale (desktop + mobile), and cue styles in `app/static/style.css`.

</code_context>

<specifics>
## Specific Ideas

- The operator's own framing of the reference price is **"рекомендуемая в справочнике"** — the imported Oriflame price list is a *recommendation*, and their own price legitimately deviates from it. The cue is a glance-level "you're off the recommendation" hint, never a block. Nothing in this phase may turn it into a validation error.
- The mental model behind D-15 in the operator's words: at приход you are saying "this product now costs X and sells for Y" (standing price → card); at продажа you are negotiating with one customer (this sale only).
- `cost < sale < catalog` holds for 6/6 live products — the operator sells consistently below Oriflame list. Any design that assumes ПЦ ≈ catalog price is wrong for this shop.

</specifics>

<deferred>
## Deferred Ideas

- **`Dictionary` code/name edits are wiped on re-import — same bug class as D-18.** `app/services/dictionary.py:63-82` lets the operator edit a dictionary entry's code/name via `POST /dictionary/{entry_id}`, but `import_master_pricelist.py` re-imports destructively, so those edits already vanish silently today. This is a pre-existing bug, out of scope for a price phase. → `deferred-items.md` candidate.
- **Two docstrings contradict the data.** `app/services/pricing.py:3-5` ("full per-catalog price history") and `CatalogPrice`'s docstring (`app/models.py:260-263`, "the full price history across every catalog issue") both describe a multi-catalog history that does not exist — the data is strictly one row per code. These docstrings are exactly what would mislead a future reader into believing D-06's date-accurate reference is available. Cheap to fix if a plan already touches those files (Claude's discretion); otherwise defer.
- **Sale → card price promotion as an explicit narrow action.** If the operator later wants to promote a sale price to the card, add a single "обновить цену в карточке" link on the sale confirmation — an explicit opt-in action, never a default. Not needed now; D-15 covers the common case.
- **`confirm=1` clears both the oversell check and the below-minimum check** (`app/services/sales.py:181`) — one flag, two guardrails. The UI presents the minimum as a hard barrier while it is in fact a bypassable warning. The 2026-07-14 report flagged this as "worth confirming it is intentional". Out of scope: criterion 5 freezes PRICE-01 behaviour unchanged for this phase. Revisit as its own decision.
- **"Обновить цены из последнего прайс-листа" button on the product card.** Suggested by the 2026-07-14 report: `Product` prices are filled once at autofill and then drift from `CatalogPrice` forever (code `42125`: 420 vs 1580). After this phase the drift is *visible* via the cue, which arguably makes a one-click resync the natural follow-up — but it is a new capability, not a consolidation. → Phase 19 (Products Page Rebuild) or backlog.

</deferred>

---

*Phase: 18-Two-Price Model Consolidation (ДЦ/ПЦ)*
*Context gathered: 2026-07-16*
