---
phase: 21-customer-profiles-purchase-insights
verified: 2026-07-17T12:00:00Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
---

# Phase 21: Customer Profiles & Purchase Insights Verification Report

**Phase Goal:** A customer profile holds every way to reach the person and shows what they
actually buy, so the operator can act on it.
**Verified:** 2026-07-17
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A customer_contacts table + customers.address column exist and migration replays cleanly | ✓ VERIFIED | `alembic/versions/0015_customer_contacts.py` replays 0001→0015 on a throwaway DB (`DB_PATH=data/_verifycheck.db uv run alembic upgrade head` exits 0); `PRAGMA table_info` confirms `customer_contacts` columns and `customers.address` |
| 2 | Customer profile supports multiple phone/Telegram/email/social values (CUST-01..04) | ✓ VERIFIED | `app/services/customers.py::contacts_by_kind`/`_replace_contacts`; `tests/test_customers.py::test_contacts_phone/telegram/email/social_multiple_values_persist` all pass; end-to-end via `test_web_customer_create_with_contacts` |
| 3 | Customer profile supports a physical address (CUST-05) | ✓ VERIFIED | `Customer.address` column, `create_customer`/`update_customer` `address` kwarg, `test_create_customer_stores_address`/`test_update_customer_changes_address` pass |
| 4 | Customer profile shows date of most recent order (CUST-06) | ✓ VERIFIED | `last_order_date()` pure function reading `purchase_history[0]`, rendered in `customer_insights.html` (`Последний заказ:`); `test_web_customer_detail_insights_renders_all_blocks` passes |
| 5 | Customer profile shows spend totals for month/quarter/year (CUST-07) | ✓ VERIFIED | `spend_totals`/`spend_view` net-of-returns, double-coalesced to never return `None`; rendered as 3 tiles in `customer_insights.html`; `test_spend_totals_month_quarter_year_with_injected_today`, `test_spend_net_of_returns_subtracts`, `test_spend_empty_customer_returns_zero_not_none` all pass |
| 6 | Customer profile shows favorite products ranked by frequency then quantity (CUST-08) | ✓ VERIFIED | `favorite_products()` uses `count(DISTINCT sale_id)` for frequency, `qty` secondary, `Product.name` tiebreak; rendered in `favorite_products.html`; `test_favorite_products_ranked_by_frequency_then_qty`, `test_favorites_batch_split_counts_once` (locks the batch-split-counts-once semantic) pass |
| 7 | Operator can add/remove contact rows on the form without a page reload | ✓ VERIFIED | `GET /customers/contact-row?kind=` HTMX endpoint + client-side `hx-on:click` remove in `contact_row.html`; `test_web_contact_row_returns_blank_row_for_each_kind` passes |
| 8 | Submitting the new-customer form with contacts creates customer + contacts in one save | ✓ VERIFIED | `test_web_customer_create_with_contacts` (2 phone/1 telegram/1 email/1 social + address, asserted by count) passes |
| 9 | Re-saving a customer replaces contacts, never duplicates | ✓ VERIFIED | `test_contacts_replace_does_not_duplicate`, `test_web_customer_update_replaces_contacts` pass |
| 10 | A validation error re-echoes typed contact values and address | ✓ VERIFIED | `test_web_customer_create_invalid_re_echoes_contacts` asserts submitted phone values + address text present in 422 body |
| 11 | Unknown kind on GET /customers/contact-row returns 404, renders nothing | ✓ VERIFIED | `test_web_contact_row_rejects_unknown_kind` (`?kind=fax`, `?kind=<script>` → 404, no body leakage) |
| 12 | Zero-order profile renders 0,00 tiles and dashes, never crashes or shows `None` | ✓ VERIFIED | `test_web_customer_detail_empty_profile_renders_zeros` asserts `0,00` ×3, `Покупок пока нет.` ×2, zero occurrences of `None` |
| 13 | A social link containing HTML/`javascript:` renders as escaped plain text, never a clickable href | ✓ VERIFIED | `test_web_contacts_social_renders_escaped_not_as_href` — asserts `&lt;script&gt;` present, raw `<script>` absent, `href="javascript:` absent, both on detail and edit pages; `test_customer_templates_never_use_safe_filter` mechanically bans `\|safe` across all 6 Phase 21 templates |

**Score:** 13/13 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | `CONTACT_KINDS`, `CustomerContact`, `Customer.address` | ✓ VERIFIED | `CONTACT_KINDS = {"phone": "Телефон", "telegram": "Telegram", "email": "Email", "social": "Соцсеть"}` (line 115); `class CustomerContact` (line 362); `Customer.address: Mapped[str | None]` (line 356) |
| `alembic/versions/0015_customer_contacts.py` | Migration creating table + column | ✓ VERIFIED | Replays cleanly 0001→0015 on throwaway DB; correct constraint names; no app imports; no batch mode; no triggers |
| `app/services/customers.py` | Contact/address write+read path, spend/favorites/last-order reads | ✓ VERIFIED | `create_customer`, `update_customer`, `_validate_contacts`, `_replace_contacts`, `contacts_by_kind`, `spend_totals`, `spend_view`, `favorite_products`, `last_order_date` all present and match plan signatures |
| `app/routes/customers.py` | `GET /customers/contact-row`, form-array binding, extended `customer_detail` context | ✓ VERIFIED | Route declared above `/customers/{customer_id}` (line 128 vs 188); `phone[]`/`telegram[]`/`email[]`/`social[]`/`address` bound on both POST handlers; `customer_detail` context has `contacts`/`last_order_iso`/`spend`/`favorites` |
| `app/templates/partials/contact_row.html` | Repeatable contact row | ✓ VERIFIED | `.contact-row` div, array-named input, client-side remove, no id, no anchor, no `\|safe` |
| `app/templates/partials/customer_contacts.html` | Контакты section | ✓ VERIFIED | Per-kind label:values lines, empty-state `Контакты не указаны.`, autoescape-only |
| `app/templates/partials/customer_insights.html` | Покупки section | ✓ VERIFIED | Last-order line + `.metric-grid` 3 tiles + mandatory `С учётом возвратов.` line, no sign-coloring |
| `app/templates/partials/favorite_products.html` | Любимые товары table | ✓ VERIFIED | Table with Товар/Покупок,раз/Куплено,шт., `Покупок пока нет.` empty state, capped at 10, no pagination |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `contact_row.html` inputs | `customer_create`/`customer_update` | `name="{kind}[]"` bound by `Form([], alias="phone[]")` etc. | ✓ WIRED | Confirmed in `app/routes/customers.py` lines 149-152, 233-236 |
| `customer_create`/`customer_update` | `create_customer`/`update_customer` | `contacts=dict[str,list[str]]` kwarg | ✓ WIRED | Confirmed lines 159-166, 239-247 |
| `customer_detail` route | `spend_view`/`favorite_products`/`last_order_date`/`contacts_by_kind` | Direct function calls, `history` reused (no 7th query) | ✓ WIRED | Confirmed lines 193-203; `last_order_date(history)` reuses already-loaded list |
| `customer_insights.html` `spend.*.start_iso` | `app.core.format_ru_date` (`\| ru_date`) | `spend_view` returns `start.isoformat()` (str, not `date`) | ✓ WIRED | `test_spend_view_start_iso_is_a_string` and `test_web_customer_detail_insights_ru_date_captions_render` both pass — no `TypeError` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full customer test module | `uv run pytest tests/test_customers.py -q` | 73 passed | ✓ PASS |
| Full repo test suite (Wave-4/phase gate) | `uv run pytest -q` | 808 passed | ✓ PASS |
| Migration replays on throwaway DB | `DB_PATH=data/_verifycheck.db uv run alembic upgrade head` | exit 0, correct schema | ✓ PASS |
| Portability guard (no date functions, no literal leakage) | `pytest -k portable` | passed | ✓ PASS |
| Batch-split-counts-once semantic | `pytest -k favorites_batch_split` | passed | ✓ PASS |
| Zero-order profile renders zeros not None | `pytest -k web_customer_detail_empty_profile` | passed | ✓ PASS |
| Stored-XSS render guard | `pytest -k contacts_social` | passed (both storage + render halves) | ✓ PASS |
| Lint/format on touched files | `ruff check` / `ruff format --check` | clean | ✓ PASS |
| No debt markers in touched files | `grep -E "TBD\|FIXME\|XXX"` | 0 matches | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| CUST-01 | 21-01, 02, 04, 05 | Multiple phone numbers | ✓ SATISFIED | `test_contacts_phone_multiple_values_persist`, `test_web_customer_create_with_contacts` |
| CUST-02 | 21-01, 02, 04, 05 | Multiple Telegram handles | ✓ SATISFIED | `test_contacts_telegram_multiple_values_persist` |
| CUST-03 | 21-01, 02, 04, 05 | Multiple emails | ✓ SATISFIED | `test_contacts_email_multiple_values_persist` |
| CUST-04 | 21-01, 02, 04, 05 | Multiple social links, free-form | ✓ SATISFIED | `test_contacts_social_multiple_values_persist` (storage) + `test_web_contacts_social_renders_escaped_not_as_href` (render/XSS) |
| CUST-05 | 21-01, 02, 04, 05 | Physical address | ✓ SATISFIED | `test_create_customer_stores_address`, `test_web_customer_new_form...` address field |
| CUST-06 | 21-03, 05 | Most recent order date | ✓ SATISFIED | `last_order_date`, `test_last_order_returns_most_recent_created_at` |
| CUST-07 | 21-01, 03, 05 | Spend totals month/quarter/year | ✓ SATISFIED | `spend_totals`/`spend_view`, 6 dedicated tests, portability guard |
| CUST-08 | 21-03, 05 | Favorite products ranked | ✓ SATISFIED | `favorite_products`, 5 dedicated tests incl. batch-split semantic |

**Orphaned requirements check:** REQUIREMENTS.md traceability table maps exactly CUST-01..08 to
Phase 21 (line 169: "21. Customer Profiles & Purchase Insights | CUST-01..08 | 8"). All 8 appear
in at least one plan's `requirements:` frontmatter. Zero orphaned.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/services/customers.py` | 149-151, 206-208 | Blank-name early return skips address/contact validation on the same submit (WR-01, flagged in `21-REVIEW.md`) | ⚠️ Warning | UX-only: when both name AND address/contacts are invalid, only the name error message shows this round; no data is written either way, and the re-echo of typed values (the phase's must-have) still works correctly regardless. Confirmed present in current code; not a phase-goal blocker. |
| `app/services/customers.py` | 426-471 | `spend_totals` and `spend_view` independently duplicate the period-window loop instead of `spend_view` composing on `spend_totals` (WR-02, flagged in `21-REVIEW.md`) | ⚠️ Warning | Maintainability only — no behavior divergence observed; both paths are tested and pass. |
| `app/templates/partials/favorite_products.html` | 22 | `{{ row.product.code }}` has no null guard, would render literal "(None)" for a code-less product (IN-01, flagged in `21-REVIEW.md`) | ℹ️ Info | Matches an existing codebase-wide convention gap (`purchase_history.html`, `top_selling_rows.html`, etc.) — not introduced fresh by this phase, low likelihood given products normally have codes |

No TBD/FIXME/XXX debt markers found in any Phase 21 file. No blockers.

### Human Verification Required

None. All must-haves are verified mechanically via passing automated tests, direct code
inspection, and a live migration replay against a throwaway database. No visual/UX judgment call
was left unresolved by the automated test suite (HTMX interactivity is covered by route-level
assertions on rendered HTML fragments, which is the established pattern for this codebase).

### Gaps Summary

No gaps. All 13 derived must-have truths (roadmap goal + PLAN.md frontmatter across all 5 plans)
are verified against the actual codebase, not just SUMMARY.md claims. The full 808-test suite
passes, the migration replays cleanly on a throwaway database, lint/format is clean on every
touched file, and no debt markers exist. A prior code-review pass (`21-REVIEW.md`, 2026-07-17)
already surfaced the three non-blocking findings listed above (WR-01, WR-02, IN-01); this
verification independently confirmed those three still exist in the current code and confirmed
none of them prevents the phase goal ("a customer profile holds every way to reach the person and
shows what they actually buy") from being observably true.

---

_Verified: 2026-07-17_
_Verifier: Claude (gsd-verifier)_
