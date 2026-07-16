# Phase 18: Two-Price Model Consolidation (ДЦ/ПЦ) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-16
**Phase:** 18-Two-Price Model Consolidation (ДЦ/ПЦ)
**Areas discussed:** Fate of existing `catalog_cents` values, Colour cue reference price, Colour cue rendering mechanism, Price write-back semantics, Dictionary entry point (follow-up)

Mode: advisor (USER-PROFILE.md present), calibration tier `standard` (vendor philosophy: pragmatic). Four gray areas researched in parallel by `gsd-advisor-researcher` agents against the live codebase and database before any option was presented.

---

## Fate of existing `catalog_cents` values

| Option | Description | Selected |
|--------|-------------|----------|
| Discard + drop column now | ПЦ is `sale_cents` and always was. One `drop_column` migration + ~12 files cleaned. Sale prices unchanged, ledger untouched. Irreversible on a live one-file DB — 6 values gone (17 backups + startup snapshot as net). | ✓ |
| Discard from UI now, drop column later | Same work minus the migration; column sits untouched in the DB, fully reversible. Cost: model/DB drift, and "temporary" columns tend to become permanent. | |
| Overwrite `sale_cents := catalog_cents` | Would make the columns trivially agree — by re-pricing the live shop upward 17–30% (690→890) and corrupting every future prefill and profit figure. | |

**User's choice:** Discard and drop the column in this phase.
**Notes:** The live-DB query settled this rather than preference. 7 active products, alembic head `0013`: **zero** backfill candidates (no product has `sale_cents IS NULL` with a `catalog_cents` value), and **6 of 6** products where both exist *disagree*, always `cost < sale < catalog`. `catalog_cents` is the Oriflame list price, `sale_cents` is what the operator charges — the gap is real business data, not drift. Code `42125` (stored 42000 vs live catalog 158000) proves the column is stale by construction; the real catalog price is served from `catalog_prices`. Follow-on decisions taken with this: native `op.drop_column` rather than `batch_alter_table` (batch would recreate `products` and its partial unique index `uq_products_code_active`); drop the «Каталог» column from receipt history; keep the `price_history.html:22` label branch as a fallback guard (0 live rows, so criterion 1 is safe).

---

## Colour cue reference price

| Option | Description | Selected |
|--------|-------------|----------|
| The code's single `CatalogPrice` row | `consultant_cents`→ДЦ, `consumer_cents`→ПЦ. One rule at every entry point; matches the operator's "рекомендуемая в справочнике" framing. No row → no cue + muted hint (the majority case). | ✓ |
| Hybrid: catalog, else the card's own price | Cue would fire almost always, at the cost of one colour meaning two different references depending on where you are. | |
| The product card's own saved ДЦ/ПЦ | Self-referential at the product card — the field compares against itself, so the cue is dead exactly where PROD-06 requires it. | |

**User's choice:** The code's single catalog row.
**Notes:** "Catalog current at the operation's date" was investigated and dropped from the option set entirely — it is not implementable: `catalog_prices` holds 6856 rows across 6856 distinct codes (zero codes with more than one catalog), and the importer keys its `collected` dict on code alone, guaranteeing that shape. There is no per-period history and no effective-date column. Two traps surfaced for planning: `latest_price_for_code` filters `consumer_cents IS NOT NULL`, which starves the ДЦ cue for a code that has a ДЦ but no ПЦ (1 such code today); and 6 of 7 live products have no catalog row at all, making "no reference" the main path rather than an edge case.

---

## Colour cue rendering mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| One delegated listener in `app/static/price-cue.js` (~15 lines) | Single `input` listener reading `data-ref-cents`; covers desktop + mobile + HTMX-added rows with no re-init. Rule lives in one place. | ✓ |
| `hx-on:input` attribute per field | No new files; the idiom already appears 42× in the templates. Cost: identical logic duplicated into 5+ templates, free to drift apart. | |
| Cue on blur / after save | No JS at all, pure server render — but fails criterion 3 as written ("typing"), which would have to be formally relaxed. | |

**User's choice:** One delegated listener in a new static JS file.
**Notes:** Two premises of the original framing turned out to be false and were corrected before the question was asked. (1) This is not the app's first hand-written JS — `hx-on:` is used 42 times including conditional swap-suppression logic, and `base.html` carries an inline viewport script; the beginner-maintainer cost is near zero because it is the idiom the codebase already speaks. (2) The RU comma wrinkle is a one-liner, not a reimplementation: `core.py:28` `to_cents` does `.strip().replace(",", ".")` and rejects space-thousands, so `parseFloat(v.replace(',','.'))` accepts exactly the same set. A CSS-only option was excluded rather than padded into the table — CSS cannot compare a live input's typed value to a reference number. The HTMX-per-keystroke option was rejected on a hard technical ground: swapping a focused text input destroys focus and caret position mid-typing, the basket's `price[]` inputs have no `id` for htmx to restore focus to, and this repo already carries a guard (`product_form.html:15-19`, Pitfall 5) written because a swap once clobbered in-flight typing. Alpine.js's deferred caveat was checked and found not triggered — there is no client-side state here, only a stateless read-compare-toggle. Visual form settled as border + tint + text badge (colour alone fails WCAG 1.4.1), with `#e8effd` explicitly off-limits since it is already the search-match highlight.

---

## Price write-back semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Asymmetric: receipt writes back, sale stays scoped | Receipt = restock event establishing a standing price → card. Sale = negotiation with one customer → this sale only. Already the shipped behaviour; adds only a scope hint in the prefill text. | ✓ |
| "Сохранить в карточку" checkbox on the sale | Operator decides discount-vs-new-price each time. Cost: a per-line checkbox in a multi-line basket is real clutter, and the default re-litigates the whole decision anyway. | |
| Sale writes back to the card too | Uniform rule, literal reading of PROD-07 — but a one-off discount becomes the product's standing price, and a below-minimum sale rewrites ПЦ below its own floor. | |

**User's choice:** Receipt writes back, sale stays scoped (the status quo).
**Notes:** Research corrected the premise: the receipt→card write-back is **already implemented** (`receipts.py:169-196`, D-07, with a `price_change` op per changed field and the PD-8 "empty never clears" rule) — so "operation-scoped only" would have been a *regression*, not the safe default. The append-only rule turned out not to discriminate between the options at all: ledger immutability is trigger-enforced at the DB level (`app/db.py:22-43`), so criterion 4 holds by construction under every option — the real hazard is forward drift, not historical corruption. That reframed the question as "which entry point owns a *standing* price?". The decisive argument against sale→card write-back is its interaction with criterion 5: writing a below-minimum sale price back to `sale_cents` leaves the card prefilling below its own floor, tripping the PRICE-01 warning on every subsequent sale and training the operator to reflex-click `confirm=1` — which also clears the oversell check (one flag, two guardrails). The only real gap in the chosen option is discoverability, closed with wording: the existing hint becomes "Цена подставлена из карточки товара — изменение сохранится только в этой продаже".

---

## Dictionary entry point (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| «Изменить цену» opens the product card | Dictionary row shows catalog ДЦ/ПЦ read-only (an Oriflame fact, not our price) + a link that opens the product card, creating it if absent. Editing stays possible; it just lands where the price survives. | ✓ |
| Make dictionary prices editable | Literal reading of PROD-07 — but requires rewriting the importer to upsert instead of DELETE+reload, or hand edits vanish at the next price-list update. Materially expands the phase. | |
| Dictionary read-only, no edit affordance | Honest and simple, but drops to three entry points and criterion 2 would need rewording. | |

**User's choice:** «Изменить цену» redirects to the product card.
**Notes:** Raised as a follow-up because research found PROD-07 is not implementable as written at this entry point: the `Dictionary` table has **no price columns at all** (code→name only). The prices shown there live in `CatalogPrice`, which is import-owned — `import_master_pricelist.py` does `DELETE` all rows then bulk-inserts, so any hand edit is silently destroyed on the next re-import, directly hitting the core value "without losing any data". The chosen redirect keeps criterion 2's spirit (correct the price from wherever you notice it) while landing the edit on the record this shop actually owns.

---

## Claude's Discretion

- Exact Russian wording of the cue badges and the "нет справочной цены" muted hint.
- Whether the ДЦ/ПЦ reference lookup becomes a new function in `app/services/pricing.py` or a fix to the existing `latest_price_for_code` (the decision fixes the behaviour, not the location).
- Whether to correct the two misleading docstrings (see Deferred) while already editing those files.

## Deferred Ideas

- `Dictionary` code/name edits (`app/services/dictionary.py:63-82`) are wiped by the destructive re-import — the same bug class as the dictionary price decision, pre-existing and out of scope here.
- `app/services/pricing.py:3-5` and `CatalogPrice`'s docstring (`app/models.py:260-263`) both claim a "full per-catalog price history" that does not exist (strictly one row per code). These are what would mislead a future reader into thinking a date-accurate reference is available.
- Sale → card price promotion as a single explicit "обновить цену в карточке" link on the sale confirmation — an opt-in action, never a default.
- `confirm=1` clears both the oversell check and the below-minimum check (`sales.py:181`); the UI presents the minimum as a hard barrier while it is a bypassable warning. Criterion 5 freezes PRICE-01 behaviour for this phase, so this needs its own decision later.
- "Обновить цены из последнего прайс-листа" button on the product card — after this phase the ДЦ/ПЦ-vs-catalog drift becomes *visible* via the cue, which makes a one-click resync the natural follow-up. New capability → Phase 19 or backlog.
