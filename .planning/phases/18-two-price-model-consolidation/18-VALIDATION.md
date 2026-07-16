---
phase: 18
slug: two-price-model-consolidation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-16
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `18-RESEARCH.md` §Validation Architecture. Every command below was
> **measured by execution**, not inferred.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* [VERIFIED: `pyproject.toml`] |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]`, `testpaths = ["tests"]`, `pythonpath = ["."]` |
| **Quick run command** | `uv run pytest tests/test_pricing_feature.py tests/test_export.py -q` (**6.4s measured**) |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~128 seconds (full suite, measured 2026-07-16) |
| **Baseline** | **682 passed, 3 warnings, exit 0** — any post-change count below 682 is a regression |
| **Linter** | `uv run ruff check` / `uv run ruff format` (line-length 100, target py313) |

> **No Makefile and no CI config exist** [VERIFIED: `ls Makefile`, `ls .github` both empty].
> `uv run pytest` is the project's actual and only test entry point. **Do not invent `make test`.**

---

## Sampling Rate

- **After every task commit:** the touched module's test file, e.g. `uv run pytest tests/test_catalog.py -q` (seconds), plus `uv run ruff check`
- **After every plan wave:** `uv run pytest tests/test_sales.py tests/test_mobile_sales.py tests/test_receipts.py tests/test_mobile_receipts.py tests/test_catalog.py tests/test_export.py tests/test_pricing_feature.py -q`
- **Before `/gsd-verify-work`:** `uv run pytest -q` → must report **≥ 682 passed**
- **Migration gate:** upgrade/downgrade/upgrade round-trip against a **copy** of `data/myorishop.db`, **never the live file**
- **Max feedback latency:** ~10 seconds per task commit; 128 seconds at the phase gate

---

## Per-Task Verification Map

> Task IDs are assigned by the planner. This table is the **contract each plan's tasks must
> satisfy**; the planner fills the Task ID / Plan / Wave columns when writing PLAN.md files.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | PROD-05 | — | `catalog_cents` absent from ORM + reflected schema | unit | `uv run pytest tests/test_catalog.py -q -k columns` | ✅ **invert** `test_catalog.py:278` | ⬜ pending |
| TBD | TBD | TBD | PROD-05 | — | Product create/update ignores a `catalog` field | unit | `uv run pytest tests/test_catalog.py -q` | ✅ update `:58,520,521` | ⬜ pending |
| TBD | TBD | TBD | PROD-05 | T-18-LEDGER | Receipt no longer **writes** `payload.catalog_cents`; history stays readable (D-04) | unit | `uv run pytest tests/test_receipts.py -q` | ✅ update `:72,203,684` | ⬜ pending |
| TBD | TBD | TBD | PROD-05 | — | Receipt no longer touches `product.catalog_cents` | unit | `uv run pytest tests/test_receipts.py -q` | ✅ **rewrite** `:613,632,658,677` (assign a dropped attr) | ⬜ pending |
| TBD | TBD | TBD | PROD-05 | T-18-CSV | CSV export has no «Каталог» column (`_csv_safe` still wraps every cell) | unit | `uv run pytest tests/test_export.py -q` | ✅ **invert** `:230` | ⬜ pending |
| TBD | TBD | TBD | PROD-05 | — | **Mobile** receipt wizard completes with no `catalog` (Pitfall 1) | integration | `uv run pytest tests/test_mobile_receipts.py -q` | ✅ exists — **must stay green** | ⬜ pending |
| TBD | TBD | TBD | PROD-05 | — | Desktop receipt form completes with no `catalog` | integration | `uv run pytest tests/test_receipts.py -q` | ✅ exists | ⬜ pending |
| TBD | TBD | TBD | PROD-06 | — | Reference returns ДЦ **and** ПЦ independently (D-08/D-22) | unit | `uv run pytest tests/test_pricing_feature.py -q` | ⚠️ **W0** — no ДЦ-without-ПЦ test | ⬜ pending |
| TBD | TBD | TBD | PROD-06 | — | No catalog row → `(None, None)`, no cue + muted hint (D-07) | unit | `uv run pytest tests/test_pricing_feature.py -q` | ⚠️ **W0** | ⬜ pending |
| TBD | TBD | TBD | PROD-06 | T-18-XSS | `data-ref-cents` present on ДЦ/ПЦ, **absent on `min_sale`** (Pitfall 8, D-21); renders an **int from the DB**, never `\| safe` | integration | `uv run pytest tests/test_pricing_feature.py -q` | ❌ **W0** | ⬜ pending |
| TBD | TBD | TBD | PROD-06 | — | OOB autofill re-render **preserves** `data-ref-cents` (Pitfall 2) | integration | `uv run pytest tests/test_catalog.py -q` | ❌ **W0** | ⬜ pending |
| TBD | TBD | TBD | PROD-06 | — | Yellow below / blue above / neither at equality | **manual** | — | ❌ browser-only (TestClient runs no JS) | ⬜ pending |
| TBD | TBD | TBD | PROD-07 | — | Receipt writes ДЦ/ПЦ back to the card (D-15) | unit | `uv run pytest tests/test_receipts.py -q` | ✅ exists — **regression guard** | ⬜ pending |
| TBD | TBD | TBD | PROD-07 | — | Sale price does **not** write back to `Product` (D-15/D-16) | unit | `uv run pytest tests/test_sales.py -q` | ⚠️ **W0** if no explicit assertion | ⬜ pending |
| TBD | TBD | TBD | PROD-07 | — | Both hint families carry the sale-only scope clause (D-17/D-23, **6 sites / 2 constants**) | integration | `uv run pytest tests/test_sales.py tests/test_mobile_sales.py -q` | ❌ **W0** | ⬜ pending |
| TBD | TBD | TBD | PROD-07 | — | Catalog detail offers «изменить цену» → product card (D-18) | integration | `uv run pytest tests/test_catalogs_feature.py -q` | ❌ **W0** | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## 🔴 Criterion 4 — historical money data preserved (highest-stakes sample)

Criterion 4 is the one a `catalog_cents` drop could break **silently**, because the drop is
irreversible (D-01). It holds *by construction* (D-04: ledger append-only, trigger-enforced) —
but "by construction" must be **sampled, not assumed**.

| Check | Command | Expected |
|-------|---------|----------|
| Ledger triggers still reject UPDATE/DELETE | `uv run pytest tests/test_ledger.py -q` | green — the structural guarantee behind criterion 4 |
| **8 historical `payload.catalog_cents` receipt ops survive** | `uv run pytest tests/test_receipts.py -q -k payload` + post-migration DB probe | `SELECT count(*) FROM operations WHERE type='receipt' AND payload LIKE '%catalog_cents%'` still returns **8** |
| Recorded receipt money unchanged | `uv run pytest tests/test_receipts.py tests/test_history.py -q` | `unit_cost_cents` / `unit_price_cents` render as recorded |
| Profit figures unchanged | `uv run pytest tests/test_reports.py tests/test_finance_reports.py -q` | green — profit never read `catalog_cents` |
| `price_history.html:22` label branch intact | `uv run pytest tests/test_catalog.py -q` | branch present (D-04: 0 rows render it — **keep anyway**) |
| Migration round-trips | `uv run alembic upgrade head && uv run alembic downgrade 0013 && uv run alembic upgrade head` | clean; downgrade re-adds the column **empty** (D-01) |
| **Pre-drop snapshot exists** (D-24) | inspect `backups/` | fresh `VACUUM INTO` snapshot taken **before** the first `0014` run — the only recovery path for the 6 discarded values |

> **The decisive sample:** the receipt-op payload count must read **8 before and 8 after**.
> That single number is criterion 4's canary. The 6 discarded `Product.catalog_cents` values are
> *intentionally* gone (D-01); the 8 ledger payloads are *historical money that must survive*.
> **Do not conflate them.**

---

## 🔴 Criterion 5 — PRICE-01 regression guard

**Structurally independent of this phase** — `app/services/sales.py:206-234` reads **only**
`min_sale_cents`; `catalog_cents` appears nowhere in `sales.py` [VERIFIED]. Risk is low, but it
is a named criterion, so it gets an explicit sample.

**9 existing guard tests** [VERIFIED by name]:

| Test | File:line |
|------|-----------|
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

**Gate:** all 9 green, **unmodified**. If a plan needs to *edit* any of these 9, that is a
criterion-5 violation signal — **stop and escalate**. `min_sale_cents` is exempt from removal
(D-21 permits label/placement only), so no PRICE-01 test should require changes.

---

## Wave 0 Requirements

- [ ] `tests/test_pricing_feature.py` — reference lookup returns ДЦ when ПЦ is NULL (**D-08/D-22's 1 live code**); returns `(None, None)` for an unknown code (D-07)
- [ ] `tests/test_pricing_feature.py` (or `test_catalog.py`) — `data-ref-cents` rendered on ДЦ/ПЦ inputs, **absent on `min_sale`** (Pitfall 8)
- [ ] `tests/test_catalog.py` — OOB autofill re-render preserves `data-ref-cents` (Pitfall 2)
- [ ] `tests/test_sales.py` — sale price does **not** mutate `Product.sale_cents` (D-15/D-16 explicit assertion)
- [ ] `tests/test_sales.py` + `tests/test_mobile_sales.py` — both hint families carry the sale-only scope clause (D-17/D-23, 6 sites)
- [ ] `tests/test_catalogs_feature.py` — catalog detail «изменить цену» links to the product card (D-18)

**No framework install needed** — pytest and httpx are already dev dependencies.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cue renders **yellow below** / **blue above** / **neither at equality** while typing | PROD-06 (criterion 3) | TestClient does not execute JavaScript — the cue's *visual* behaviour cannot be automated with this stack. Server-side we assert `data-ref-cents` + the CSS classes; the colour itself is verified by eye. | Open the product card for a code **with** a `CatalogPrice` row. Type a ДЦ below `consultant_cents` → amber border `#b45309` on `#fef9e7` + «ниже справочной» badge. Type above → blue border `#2563eb` on `#eff6ff` + «выше справочной». Type exactly equal → no cue. Repeat on ПЦ against `consumer_cents`. Then repeat in the **receipt** and **sale** forms, desktop **and** mobile. Confirm the blue is **not** `#e8effd` (the existing search-match/selection tint used at 6 sites). Confirm **no cue** appears on «Минимальная цена продажи» (Pitfall 8). |
| Cue survives an HTMX OOB autofill | PROD-06 | Requires a real browser + a code lookup round-trip | Type a product code that triggers autofill. After the OOB swap replaces `#cost`/`#sale`, type in each again — the cue must still fire (Pitfall 2). |
| No catalog row → muted hint, no cue | PROD-06 (D-07) | Visual; this is the **MAIN path** — 6 of 7 live products have no catalog row | Open a product card for a code absent from `catalog_prices`. Expect a muted "нет справочной цены" hint and **no** colour on either field. |

> **Recommend a `checkpoint:human-verify` task** for the criterion-3 visual check.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 130s (full suite; ~10s per task commit)
- [ ] Full suite reports **≥ 682 passed** (baseline measured 2026-07-16)
- [ ] PRICE-01's 9 guard tests green and **unmodified**
- [ ] Receipt-op payload count reads **8 before and 8 after** the migration
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
