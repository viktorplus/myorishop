---
quick_id: 260714-fix
slug: fix-catalog-sale-autofill
status: complete
---

## What happened

User clarified pricing terminology: ДЦ (consultant price) = себестоимость
(cost), ПЦ (consumer/catalog price) = цена продажи по умолчанию (default
sale price). The existing autofill only used ПЦ to fill "Цена по каталогу"
(a reference field), never "Цена продажи" — including an explicit D-02
decision in the goods-receipt flow that hard-excluded sale from catalog
autofill. User confirmed this should change in both places.

## Changes

- `app/routes/products.py::product_price_lookup` — added `sale` param and
  `fill_sale` (mirrors `fill_catalog`, both driven by `consumer_cents`,
  fill-only-if-empty).
- `app/templates/partials/product_price_autofill.html` — added the `sale`
  OOB fragment.
- `app/templates/pages/product_form.html` — added `#sale` to the autofill
  trigger's `hx-include`.
- `app/services/receipts.py::lookup_prefill` — catalog-source branch now
  returns `sale: consumer_cents` instead of always `None` (D-02 superseded).
- `app/routes/receipts.py::receipt_lookup` — catalog-source branch's
  `fill_fields` now includes `"sale"`.
- Mobile receipt wizard (`app/routes/mobile_receipts.py`) needed no code
  change — it already forwards whatever `lookup_prefill` returns via the
  existing `resolved_sale or sale.strip()` pattern.
- Updated/renamed 6 tests that encoded the old "sale never filled from
  catalog" behavior (`test_receipts.py` x4, `test_mobile_receipts.py` x1,
  `test_pricing_feature.py` x1) to assert the new fill behavior instead.

## Verified

- Manual `TestClient` checks: `/products/lookup-price`, `/receipts/lookup`,
  and `/m/receipts/step/batch` all now return `sale` filled with the
  catalog's consumer price when the field is empty.
- Full test suite: 563 passed.

## Changed files

- `app/routes/products.py`
- `app/templates/partials/product_price_autofill.html`
- `app/templates/pages/product_form.html`
- `app/services/receipts.py`
- `app/routes/receipts.py`
- `tests/test_receipts.py`
- `tests/test_mobile_receipts.py`
- `tests/test_pricing_feature.py`
