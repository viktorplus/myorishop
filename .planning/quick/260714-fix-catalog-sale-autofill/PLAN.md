---
quick_id: 260714-fix
slug: fix-catalog-sale-autofill
date: 2026-07-14
---

Catalog consumer price (ПЦ) should also autofill "Цена продажи" (default sale
price), not just "Цена по каталогу" — ПЦ is the shop's default sale price
per user clarification, ДЦ (consultant) remains cost-only.

## Scope

1. Product-add/edit form (`app/routes/products.py`, `product_price_autofill.html`,
   `product_form.html`): `/products/lookup-price` also fills `sale` from
   `consumer_cents` when empty.
2. Goods receipt (`app/services/receipts.py::lookup_prefill`, catalog-source
   branch) + desktop route (`app/routes/receipts.py`): supersede D-02 —
   `sale` now also fills from `consumer_cents` on the catalog-only branch,
   same as cost/catalog. Mobile receipt wizard already forwards whatever
   `lookup_prefill` returns, so it picks this up automatically.
3. Update the tests that previously asserted "sale is never filled from
   CatalogPrice" (D-02 regression guards) to assert the new behavior.
