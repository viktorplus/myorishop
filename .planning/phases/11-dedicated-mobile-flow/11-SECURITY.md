# Security Audit — Phase 11: Dedicated Mobile Flow

**Audited:** 2026-07-13
**ASVS Level:** 1
**block_on:** high
**Threats:** 30 distinct IDs verified / 37 threat-model rows across 10 plans (T-11-CSRF recurs identically in Plans 02–09)
**Result:** SECURED — 0 open

Verification method: for each `mitigate` disposition, the cited code path was read directly (not inferred from comments) to confirm the declared control executes before any write/render. For each `accept` disposition, the stated rationale was sanity-checked against the actual code (no `|safe` audit, no CSRF anywhere in the app, no new dependencies added, etc.).

## Threat Verification

| Threat ID | Plan | Category | Disposition | Evidence |
|-----------|------|----------|-------------|----------|
| T-11-01 | 11-01 | Tampering | mitigate | `batch_card_picker.html` only renders the hidden `batch_id` echo (`app/templates/mobile_partials/batch_card_picker.html:37`); re-validation delegated to and confirmed present in every consumer (see T-11-10/13/16/19 below) |
| T-11-02 | 11-01 | Info Disclosure | mitigate | No `\|safe` anywhere in `app/templates/mobile_partials/batch_card_picker.html` (grep confirmed; comment matches only) — `b.comment`/`b.location` rendered via autoescape at lines 53-55 |
| T-11-03 | 11-01 | Tampering | accept | `app/templates/base.html:10-13` — redirect script reads only `window.location.pathname` and `matchMedia`; no user input, no server-echoed data |
| T-11-SC | 11-01 | Tampering (supply chain) | accept | `git diff` on `pyproject.toml` across the Phase 11 commit range shows only a Ruff lint-config line change — zero new runtime dependencies added |
| T-11-04 | 11-02 | Tampering | mitigate | `app/routes/mobile_search.py:22` calls `search_view(session, q)` unchanged; no new SQL/LIKE clause defined in the file |
| T-11-05 | 11-02 | Info Disclosure | accept | Per-warehouse batch quantity is already exposed on desktop via `/reports/expiry` (`app/templates/pages/reports_expiry.html:25,32` renders `row.warehouse.name`/`row.batch.quantity`) and via the receipt/sale/transfer/writeoff/correction wizards' own `open_batches` calls — no literal "/products page" breakdown exists, but the underlying claim (data already reachable by the same single local operator) holds; not a material gap |
| T-11-06 | 11-02 | Tampering (IDOR) | mitigate | `app/routes/mobile_search.py:38-40` — `session.get(Product, product_id)` returns `None` → `Response(status_code=404)`; file defines only `@router.get` routes, no write path |
| T-11-07 | 11-03 | Tampering | mitigate | `app/services/receipts.py:226-234` — posted `batch_choice` (when not `"new"`) is rejected via `batch.product_id != product.id or batch.warehouse_id != warehouse_id`, with `session.rollback()` and zero writes on reject |
| T-11-08 | 11-03 | Tampering | mitigate | `app/services/receipts.py:120-124` — `warehouse_id` checked against `active_warehouses(session)`, rejecting an inactive/stale id server-side |
| T-11-09 | 11-03 | Info Disclosure | mitigate | No `\|safe` in `receipts_step_batch.html`, `receipts_step_details.html`, or `receipts_step_confirm.html` (grep confirmed) |
| T-11-10 | 11-04 | Tampering/EoP | mitigate | `app/routes/mobile_sales.py:152-158` (`GET /m/sales/step/batch`) — `candidate.product_id == product.id` re-validated before trusting the pick |
| T-11-11 | 11-04 | Tampering | mitigate | `app/services/sales.py:156-164` — every basket line's `batch_id` is re-resolved and ownership-checked (`batch.product_id != product.id`) at the service layer before any write |
| T-11-12 | 11-04 | Repudiation | mitigate | `app/services/sales.py:181-234` — oversell/below-minimum computed and returned with zero writes when `confirm != "1"`; `session.add(header)` (first write) occurs only at line 236, after this gate |
| T-11-13 | 11-05 | Tampering/EoP | mitigate | `app/routes/mobile_writeoff.py:111-114` (`GET /m/writeoff/step/batch-pick`) — `candidate.product_id == product.id` re-validated |
| T-11-14 | 11-05 | Tampering | mitigate | `app/services/writeoffs.py:69-70` — `reason_code not in WRITEOFF_REASONS` server-side allow-list; template (`writeoff_step_reason.html:32`) iterates the `WRITEOFF_REASONS` Jinja global, never widening it |
| T-11-15 | 11-05 | Repudiation | mitigate | `app/services/writeoffs.py:92-102` — oversell gate returns zero-write result before `record_operation(..., commit=True)` at line 104 |
| T-11-16 | 11-06 | Tampering/EoP | mitigate | `app/routes/mobile_corrections.py:103-106` (`GET /m/corrections/step/batch-pick`) — `candidate.product_id == product.id` re-validated |
| T-11-17 | 11-06 | Tampering | mitigate | `app/services/corrections.py:55` — `mode not in ("count", "delta")` server-side allow-list |
| T-11-18 | 11-06 | Repudiation | mitigate | `app/services/corrections.py:107-117` — oversell gate returns zero-write result before `record_operation(...)` at line 119 |
| T-11-19 | 11-07 | Tampering/EoP | mitigate | `app/routes/mobile_transfers.py:73-82` (`_pick_batch`) — `candidate.product_id == product.id` re-validated, used by both `/m/transfers/step/batch-pick` and `POST /m/transfers` |
| T-11-20 | 11-07 | Tampering | mitigate | `app/services/transfers.py:85-90` — `dest_warehouse_id not in active_ids` and `dest_warehouse_id == source.warehouse_id` both rejected server-side |
| T-11-21 | 11-07 | Repudiation | mitigate | `app/services/transfers.py:95-105` — oversell gate returns zero-write result before `session.add(dest)`/`record_operation(...)` at lines 113-128 |
| T-11-22 | 11-08 | Tampering/EoP | mitigate | `app/routes/mobile_returns.py:34-57` (`_resolve_origin`) and services/returns.py:128-130 — both the route's own guard and the service's independent guard require `type == "sale"` and non-null `sale_id` |
| T-11-23 | 11-08 | Tampering | mitigate | `app/services/returns.py:141-145` — `qty > remaining` rejected before any write |
| T-11-24 | 11-08 | Info Disclosure | mitigate | No `\|safe` in `return_confirm.html` or `history_cards.html` (grep confirmed across all `mobile_partials/` and `mobile_pages/`) |
| T-11-25 | 11-09 | DoS (route collision) | mitigate | `uv run python -c "from app.main import app; print(len(app.routes))"` succeeds (31 routes); all 10 mobile routers registered in `app/main.py:68-77`, every mobile route confirmed under `/m/...` prefix |
| T-11-26 | 11-09 | Tampering | accept | Confirmed by direct verification of every individual endpoint's threat above (T-11-01 through T-11-24) — no aggregate gap found |
| T-11-CSRF | 11-02..11-09 | Tampering | accept | Global grep for `csrf`/`SessionMiddleware`/`CORSMiddleware`/`itsdangerous` across `app/` returns zero matches — confirms "unchanged app-wide posture" (no CSRF protection exists anywhere in the app, consistent with the single-local-operator, no-auth design) |
| T-11-10-01 | 11-10 | Tampering | mitigate | `sale_step_qty_price.html:29-32` — new «Назад» button targets `hx-get="/m/sales/step/batch"` only when `from_batch_step` is true, which is the same endpoint verified under T-11-10 (`candidate.product_id == product.id` unchanged) |
| T-11-10-02 | 11-10 | Info Disclosure | accept | `app/static/style.css:281-287` — CSS-only fix (`button.mobile-card { color: #222; }` + two hover rules); confirmed no template changes accompany it, autoescape posture unchanged |

## Unregistered Flags

None. All 10 SUMMARY.md files (11-01 through 11-10) were checked for a `## Threat Flags` section — none exists in any of them (confirmed via grep), so there is no new attack surface flagged by the executor beyond the plan-time register.

## Notes / Observations (non-blocking)

- T-11-05's rationale text ("same data already visible on the desktop /products page") is imprecise — the desktop `/products` list itself does not show per-warehouse batch quantities. The equivalent data is genuinely visible elsewhere on desktop (`/reports/expiry`, and every batch-picking wizard step), so the underlying "no new exposure for a single local operator" claim still holds and is not treated as a gap. Recommend tightening the wording if this threat model is ever reused as a template.
- T-11-CSRF is listed identically in Plans 02 through 09. It was verified once, globally, rather than once per plan, since the code-level fact being checked (no CSRF machinery exists anywhere in `app/`) does not vary by plan.

## Accepted Risks Log

| Threat ID | Rationale | Re-verify if... |
|-----------|-----------|------------------|
| T-11-03 | Redirect script has zero injection surface (no user input) | `base.html`'s redirect script is ever changed to read a query param or cookie |
| T-11-SC | Zero new packages in Phase 11 | Any future phase adds a dependency touching this mobile surface |
| T-11-05 | Per-warehouse stock already reachable elsewhere by the same single operator | Multi-operator/auth is introduced (v2 roadmap item) |
| T-11-26 | Aggregate `/m/...` surface = sum of already-mitigated individual endpoints | A new `/m/...` route is added without its own threat entry |
| T-11-CSRF | No auth/session exists app-wide; consistent single-operator posture | Any auth/session mechanism is ever added |
| T-11-10-02 | Styling-only change, no template/data-flow change | The CSS fix is ever bundled with a template edit |

SECURITY.md: `.planning/phases/11-dedicated-mobile-flow/SECURITY.md`
