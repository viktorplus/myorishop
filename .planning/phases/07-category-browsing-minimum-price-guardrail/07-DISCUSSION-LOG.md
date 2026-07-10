# Phase 7: Category Browsing & Minimum Price Guardrail - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 7-Category Browsing & Minimum Price Guardrail
**Areas discussed:** Category page content & grouping, Category page navigation & route, Minimum-price warning behavior, Minimum-price field on product card

---

## Category page content & grouping

| Option | Description | Selected |
|--------|-------------|----------|
| Только остаток (Код, Название, Остаток) | Mirrors `reports_stock.html`; fast to build; no price leakage | |
| Полные цены (Код, Название, Закупочная, Продажа, Каталог, Действия) | Mirrors `product_rows.html`; one page for stock + pricing | ✓ (base choice) |
| Остаток + цена продажи | Middle ground, no existing precedent | |

**Follow-up:** confirmed the full-pricing option should ALSO include the Остаток (quantity) column, since the page is a stock page, not just a pricing catalog — the /products catalog table doesn't show quantity, but this new page must.

**User's choice:** Full pricing + quantity: Код, Название, Остаток, Закупочная, Продажа, Каталог, Действия.
**Notes:** Category sorting (alphabetical) and the "Без категории" bucket for uncategorized products were resolved by the advisor research directly from existing code/success-criteria — not re-asked as open questions, since the reasoning (reuse existing category ordering; success criterion requires seeing ALL active products) was unambiguous.

---

## Category page navigation & route

| Option | Description | Selected |
|--------|-------------|----------|
| Новый пункт меню + свой маршрут | Discoverable; clean IA slot for future phases | ✓ |
| Вкладка внутри /products | Keeps nav compact; blurs CRUD vs. browse purpose | |
| Расширить /reports/stock | Zero nav change; overloads the report's single responsibility | |

**Follow-up:** chose the exact route to avoid colliding with the existing `/reports/stock` report.

**User's choice:** New top-level nav entry at route `/categories`.
**Notes:** `/stock` was rejected specifically because it's too close in meaning to the existing `/reports/stock` "Остатки склада" report.

---

## Minimum-price warning behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Один общий блок, общий confirm | Mirrors `sale_oversell.html` exactly; single round-trip even when combined with oversell | ✓ |
| Раздельные confirm-флаги | Two-stage resolution; no precedent in codebase; more state to test | |
| Предупреждение внутри строки | Per-line inline warning; needs new visual state in `sale_row.html` | |

**User's choice:** One combined block sharing the same `confirm=1` flag as the existing oversell check.
**Notes:** PROJECT.md explicitly requires "same pattern as oversell" — this was the closest match to that instruction and to the existing zero-writes-until-confirmed contract in `register_sale`.

---

## Minimum-price boundary comparison

| Option | Description | Selected |
|--------|-------------|----------|
| Равно = норма (strict less-than) | Mirrors existing oversell boundary (`requested > quantity`) | ✓ |
| Равно = предупреждать (less-than-or-equal) | Treats minimum as an absolute no-touch floor; no precedent | |

**User's choice:** Strict less-than — price exactly equal to the minimum passes silently.

---

## Minimum-price field on product card

| Option | Description | Selected |
|--------|-------------|----------|
| После «Цена продажи», перед «Цена по каталогу» | Reads as "sale price, and the floor under it" | ✓ |
| После «Цена по каталогу» | Keeps existing price trio untouched | |
| Рядом с low_stock_threshold/stale_days | Matches mechanism (nullable override) but implies a false global-default hint | |

**User's choice:** Immediately after "Цена продажи", before "Цена по каталогу". Label "Минимальная цена продажи (необязательно)" — no "(по умолчанию: N)" hint, since PRICE-01 has no global fallback (confirmed: unlike `low_stock_threshold`/`stale_days`, PROJECT.md describes no default).

---

## Claude's Discretion

- Exact database column name for the minimum price (suggested `min_sale_cents`).
- Exact route module file for `/categories` (new file vs. extending `products.py`).
- Exact partial filename for the new price-warning block.

## Deferred Ideas

None — discussion stayed within phase scope.
