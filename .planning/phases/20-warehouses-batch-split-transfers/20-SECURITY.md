---
phase: 20
slug: warehouses-batch-split-transfers
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-17
---

# Phase 20 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

**Note on IDs:** `T-20-01` was assigned independently by two different plans
(20-01 and 20-05) to two *distinct* threats — a planning-time ID collision,
not a duplicate threat. Both are tracked below, disambiguated as
`T-20-01 (20-01)` and `T-20-01 (20-05)`.

---

## Trust Boundaries

| Boundary | Description |
|----------|--------------|
| Operator browser → `/warehouses` list query params | `name`/`address`/`status`/`sort`/`page`; pre-existing Phase 14 surface, unchanged input validation |
| Operator browser → `POST /warehouses/{id}`, `POST /warehouses/{id}/delete` | `warehouse_id` path param is client-controlled; must resolve via `session.get` with an explicit None-check (404) before any render or mutation |
| Operator browser → `POST /transfers`, `POST /writeoff` `batch_id` field | Client-submitted, untrusted — must be re-validated for product ownership before being echoed into any response |
| Operator browser → `POST /transfers` `dest_warehouse_id` = source's own warehouse | Valid input by design (D-05/D-09); gated by an override-required check in the service layer, not a trust-boundary violation |
| Operator phone → `POST /m/transfers`, `POST /m/transfers/step/dest` | Mirrors the desktop transfer boundary above |
| Caller → `register_transfer(new_expiry=, new_comment=)` | Free-text strings, untrusted; `.strip()`-then-check discipline only, no stricter validation (matches codebase-wide convention) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation / Rationale | Status |
|-----------|----------|-----------|-------------|--------------------------|--------|
| T-20-01 (20-01) | Information Disclosure | `list_warehouses` new aggregate queries | accept | Both new queries (`item_count`, `last_receipt`) are scoped by `Batch.warehouse_id.in_(warehouse_ids)`, where `warehouse_ids` is derived from the already-filtered/paginated `page_rows` — no client-supplied raw warehouse id reaches either query. Confirmed by direct read: `app/services/warehouses.py:68-95`. Non-sensitive operational metrics (no PII, no money). | closed |
| T-20-02 | Tampering | `GET/POST /warehouses/{id}[/edit\|/delete]` | mitigate | Every route resolves `warehouse_id` via `session.get(Warehouse, warehouse_id)` and 404s on `None` before rendering or mutating. Confirmed present at all three entry points: GET edit (`app/routes/warehouses.py:130-134`), POST delete (`app/routes/warehouses.py:173-175`), POST update (`app/routes/warehouses.py:147-149` + `app/services/warehouses.py:130-136`, which also now rejects soft-deleted warehouses per the WR-02 fix). Guard runs *before* any use of the resolved warehouse in all three routes — correct ordering. | closed |
| T-20-03 | Denial of Service (data loss) | `soft_delete_warehouse` stock/last-active guards | accept | Logic unchanged by this phase — only the rendering location moved (D-02). Confirmed unchanged: stock guard runs first and is non-overridable (`app/services/warehouses.py:179-185`), last-active warn-then-confirm only reached after the stock guard passes (`186-198`). Covered by existing service-level tests. | closed |
| T-20-04 | Tampering (stored XSS) | `w.name`/`w.address` in new read-only `<td>` cells | accept | Jinja2 autoescape only; no `\|safe` used. Confirmed: `app/templates/partials/warehouse_rows.html:64-65` render via plain `{{ w.name }}` / `{{ w.address or '' }}`; a project-wide grep for a functional `\|safe` filter across `app/templates/**` returned zero matches. | closed |
| T-20-05 | Tampering (stored XSS) | `new_comment` persisted onto `Batch.comment` | accept | Template-layer control (autoescape), unaffected by the service-layer change. Confirmed: `app/templates/partials/batch_picker.html:58` renders `{{ b.comment }}` with no `\|safe`; same zero-`\|safe` project-wide grep result as T-20-04. | closed |
| T-20-06 | Denial of Service (invalid data) | `new_expiry` accepted as free-text string, not date-validated | accept | Matches the existing `source.expiry` convention codebase-wide. Confirmed: `app/services/transfers.py:99` only `.strip()`s `new_expiry`, no date-format parsing/validation before use at line 134. | closed |
| T-20-01 (20-05) | Information Disclosure / Tampering | `transfers_create`'s `selected_batch` resolution | mitigate | Ported the 4-line ownership guard from `transfers_batch_pick` — rejects `candidate.product_id != product.id` before assigning `selected_batch`. Confirmed present at `app/routes/transfers.py:142-147`, and runs *before* `selected_batch` is echoed in the exception handler (line 169), oversell branch (line 186), and error branch (line 196). Closes the pre-flagged WR-01 debt. | closed |
| T-20-07 | Information Disclosure / Tampering | `writeoff_create`'s `selected_batch` resolution | mitigate | Ported the identical guard from `writeoff_batch_pick`. Confirmed present at `app/routes/writeoffs.py:129-134`, and runs *before* `selected_batch` is echoed in the exception handler (line 157), oversell branch (line 173), and error branch (line 183). | closed |
| T-20-08 | Tampering | `mobile_transfers.py::_pick_batch` | accept | Already correct — reference pattern other files copy from, not touched by this phase. Confirmed unchanged: `app/routes/mobile_transfers.py:76-85` re-queries the batch and checks `candidate.product_id == product.id` before returning it. | closed |
| T-20-09 | Tampering (stored/reflected XSS) | `new_expiry_value`/`new_comment_value` echoed into `value="..."` attributes | accept | Jinja2 autoescape handles HTML-attribute escaping automatically; no `\|safe` used. Confirmed: `app/templates/partials/transfer_batch_wrap.html:52,56` render both values via plain `{{ ... \| default('') }}`. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-20-01 | T-20-01 (20-01) | New warehouse-list aggregate queries are scoped to the already-paginated/filtered result set; no new client-controlled query parameter accepts a raw warehouse id; metrics are non-sensitive | operator (plan-time disposition) | 2026-07-16 |
| AR-20-02 | T-20-03 | `soft_delete_warehouse`'s stock/last-active guard logic is unchanged by this phase (only its rendering location moved); already covered by pre-existing service-level tests | operator (plan-time disposition) | 2026-07-16 |
| AR-20-03 | T-20-04 | `w.name`/`w.address` rendered via Jinja2 autoescape only, no `\|safe` anywhere in the template | operator (plan-time disposition) | 2026-07-16 |
| AR-20-04 | T-20-05 | `Batch.comment` rendering discipline (autoescape only) is a template-layer control unaffected by this phase's service-layer change | operator (plan-time disposition) | 2026-07-16 |
| AR-20-05 | T-20-06 | `new_expiry` free-text (no date validation) matches the existing `source.expiry`/receipt-form convention used everywhere else in this codebase | operator (plan-time disposition) | 2026-07-16 |
| AR-20-06 | T-20-08 | `mobile_transfers.py::_pick_batch` was already correct pre-phase and is the reference pattern other files were ported FROM in this phase (T-20-01/20-05, T-20-07) | operator (plan-time disposition) | 2026-07-16 |
| AR-20-07 | T-20-09 | Echoed override values rendered into `value="..."` attributes via Jinja2 autoescape only, no `\|safe` anywhere in the template family | operator (plan-time disposition) | 2026-07-16 |

*Accepted risks do not resurface in future audit runs.*

---

## Code Review Follow-Through

Phase 20 went through `20-REVIEW.md` followed by `20-REVIEW-FIX.md` (3 findings in scope: CR-01 critical, WR-01, WR-02 warnings; all 3 fixed, 0 skipped). Of direct security/correctness relevance to this register:
- **WR-02**: `GET /warehouses/{id}/edit` did not guard against a soft-deleted warehouse; `warehouse_update` could silently re-save one. Fixed in commit `a3d6ef6` — both the GET route (`app/routes/warehouses.py:133`) and `update_warehouse` (`app/services/warehouses.py:135-136`) now reject soft-deleted warehouses. This hardens T-20-02's mitigation (an additional guard layer beyond the plan-time 404-on-unknown-id requirement) but was not itself a registered Phase 20 threat.
- **CR-01** and **WR-01** (destination-warehouse selection dropped on re-render; mobile dest-step missing error surfacing) are functional/UX fixes, not security-relevant to any threat in this register.

---

## Unregistered Flags

None. No `## Threat Flags` section was present in any of the seven Phase 20 SUMMARY.md files (20-01 through 20-07) — no new attack surface was flagged by the executor during implementation beyond the plan-time register.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-17 | 10 | 10 | 0 | gsd-security-auditor |

Verification method: direct read of `app/routes/warehouses.py`, `app/services/warehouses.py`, `app/routes/transfers.py`, `app/routes/writeoffs.py`, `app/routes/mobile_transfers.py`, `app/services/transfers.py`, and a project-wide grep for `\|safe` across `app/templates/**` (zero functional matches). All three `mitigate`-disposition threats (T-20-02, T-20-01 (20-05), T-20-07) verified with guard code present and confirmed to run *before* the guarded value is used (rendering or mutation), not after.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-17
