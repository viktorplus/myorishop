---
phase: 9
slug: batch-tracking-ledger-integration
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-12
---

# Phase 9 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Verification mode: FORCE — every declared mitigation confirmed by a code/test
> match at its cited location; documentation and intent are NOT accepted as evidence.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| service caller → `record_operation` (`app/services/ledger.py`) | a `batch_id` reaching the single write path is untrusted (foreign / forged / exhausted / absent) | `batch_id`, `product_id`, `type_`, `qty_delta` |
| receipt form → `register_receipt` | stale/crafted POST may name a foreign batch or deleted warehouse | `warehouse_id`, `batch_choice`, `expiry`, `location`, `comment` |
| basket form → `register_sale` | positional untrusted arrays; lengths and batch ownership forgeable | `code[]`, `qty[]`, `price[]`, `batch_id[]`, `confirm` |
| writeoff/correction form → service | batch may be foreign/exhausted; `confirm` replayable | `batch_id`, `qty`, `mode`, `value`, `confirm` |
| return form → `register_return` | batch is server-resolved from the validated origin op, never client-supplied | `origin_op_id`, `qty` |
| `row` query param → hx attributes on `/sales/batch-pick` | echoed into htmx attributes | `row` |
| stored batch/product text → chooser / picker / history / return HTML | untrusted-at-rest text rendered back into HTML | `batch.name`, `comment`, `location`, `expiry`, `product.name`, `product.code` |
| migration → live append-only ledger | 0008/0009 must not drop the `operations_no_%` triggers or rewrite ledger rows | schema DDL |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-09-01 | Tampering | `record_operation` batch_id ownership | mitigate | `app/services/ledger.py:90-100` — `session.get(Batch, batch_id)` then `batch.product_id != product_id` → `ValueError`; a batch_id on an audit type is rejected outright (line 99-100), so the ownership guard covers every path a batch can attach to | closed |
| T-09-02 | Tampering / Info-integrity | migration 0008 on `operations` | mitigate | `alembic/versions/0008_batches.py:84-87` native `op.add_column` (no batch mode; 0 `batch_alter_table`); replay test `tests/test_batches.py:266-277` asserts both `operations_no_%` triggers survive (count==2) AND an `UPDATE operations` still ABORTs (`IntegrityError`, "append-only") | closed |
| T-09-03 | Tampering | legacy-batch quantity seed | mitigate | `alembic/versions/0008_batches.py:92-116` — seed reads `SELECT SUM(qty_delta) … GROUP BY product_id HAVING SUM(qty_delta) > 0` in plain SQL and inserts that `:qty`; `products.quantity` is never read | closed |
| T-09-04 | Tampering | receipt top-up `batch_choice` | mitigate | `app/services/receipts.py:225-234` re-validates `batch.product_id != product.id or batch.warehouse_id != warehouse_id` → rollback + reject; allow-list enforced (empty → error line 128-129, "new" branch line 133); `record_operation` re-checks ownership again at line 238 | closed |
| T-09-05 | Tampering / Input-validation | receipt `warehouse_id` + `expiry` | mitigate | `app/services/receipts.py:117-124` server-side active-warehouse re-check (zero-warehouse blocking re-enforced); `parse_optional_expiry` (`:43-62`, called `:133-134`) validates via `date.fromisoformat` | closed |
| T-09-06 | Tampering (XSS) | location/comment in receipt chooser | mitigate | `receipt_batch_chooser.html` — no `\|safe` (0 filter matches repo-wide); default Jinja autoescape active (`app/routes/__init__.py:9`, no `autoescape=False`) | closed |
| T-09-07 | Tampering | parallel `batch_id[]` array | mitigate | `app/services/sales.py:71-78` pads `batch_ids` with `""` to `len(codes)` BEFORE zip (blankness never resurrects a row); a short/missing array degrades to blank → rejected at `:158-159` «Выберите партию.», never a positional guess | closed |
| T-09-08 | Tampering | forged/foreign/exhausted `batch_id` | mitigate | `app/services/sales.py:156-164` rejects unresolvable or `batch.product_id != product.id`; per-batch oversell aggregated vs `Batch.quantity` at `:181-204` on every POST | closed |
| T-09-09 | Repudiation / Tampering | `confirm=1` sale replay | mitigate | `app/services/sales.py:181` — oversell recomputed server-side each POST; `confirm` is never persisted/trusted as state, it only exercises the pre-existing warn-but-allow override (documented business contract, AR-09-01) | closed |
| T-09-10 | Injection | `row` id in hx attributes | mitigate | `app/routes/sales.py:31` `_ROW_ID_RE = re.compile(r"[0-9a-fA-F-]{1,36}")`; `.fullmatch(row)` applied at both entry points `:179` and `:229` — restricts to hex+hyphen, blocks `<`/`"`/markup | closed |
| T-09-11 | Tampering (XSS) | batch comment/location in picker | mitigate | `batch_picker.html` — no `\|safe`; default autoescape (see T-09-06) | closed |
| T-09-12 | Tampering | writeoff/correction `batch_id` | mitigate | `app/services/writeoffs.py:86-88` and `app/services/corrections.py:72-74` — resolve batch, reject `None` / `batch.product_id != product.id` BEFORE any write | closed |
| T-09-13 | Tampering / integrity | correction count baseline | mitigate | `app/services/corrections.py:85` — `qty_delta = counted - batch.quantity` (picked batch, not `product.quantity`); a recount cannot corrupt a sibling batch | closed |
| T-09-14 | Repudiation / Tampering | correction/writeoff `confirm=1` replay | mitigate | `app/services/writeoffs.py:92` and `app/services/corrections.py:107` — over-removal recomputed vs current `Batch.quantity` each POST; `confirm` never trusted alone | closed |
| T-09-15 | Tampering (XSS) | batch text in picker | mitigate | shared `batch_picker.html` — no `\|safe`; default autoescape | closed |
| T-09-16 | Tampering / integrity | stock-affecting op without a batch | mitigate | `app/services/ledger.py:91-93` — D-12 mandatory guard: `type_ in STOCK_AFFECTING_TYPES` with `batch_id is None` → `ValueError`; the write-path backstop across all current/future callers | closed |
| T-09-17 | Tampering | return batch attribution | mitigate | `app/services/returns.py:116-118` signature takes only `origin_op_id`/`qty_raw` (no form batch); batch is server-resolved at `:150` via `_resolve_or_create_return_batch_id` from `origin.batch_id` or the legacy batch | closed |
| T-09-18 | Info-integrity | legacy /history attribution | mitigate | `app/services/operations.py:33-53` — `outerjoin(Batch, Operation.batch_id == Batch.id)` resolves NULL batch_id at READ time; read-only service, the append-only ledger is never rewritten | closed |
| T-09-19 | Tampering (XSS) | batch text in /history + return form | mitigate | `history_rows.html` and `return_form.html` — no `\|safe`; default autoescape | closed |
| T-09-06-01 | Tampering | `sale_lookup.html` OOB fragments | mitigate | `app/templates/partials/sale_lookup.html:21-33` — OOB price `<td>` and batch-wrap `<tr>` each wrapped in `<template>` (parse-context only); single-`batch_id[]`-per-line invariant asserted by `tests/test_sales.py::test_web_sale_lookup_oob_batch_row_is_template_wrapped` | closed |
| T-09-07-01 | Tampering | «Вернуть» link params | accept | `app/routes/returns.py:27-53` `_resolve_origin` re-resolves + validates the origin sale op entry-point-agnostically (`session.get(Operation, …)`, type/sale_id checks); `register_return` re-validates again (`returns.py:128-130`). Same URL shape as the two shipping siblings — no new trust surface (AR-09-02) | closed |
| T-09-07-02 | Info-disclosure | product name/code in /history | mitigate | `history_rows.html` «Код»/«Товар» cells — no `\|safe`; default autoescape | closed |
| T-09-08-01 | Tampering | client-side dirty flag on `#code` | accept | flag only clears a stale autofilled name client-side; the server authoritatively decides fill-vs-204 (`receipts.lookup_prefill` → route 204) and re-validates ALL writes in `register_receipt` — a spoofed `data-autofilled` cannot cause a write (AR-09-03) | closed |
| T-09-08-02 | Info-disclosure | name/comment in `name_input.html` + chooser | mitigate | `name_input.html` and `receipt_batch_chooser.html` — no `\|safe`; default autoescape | closed |
| T-09-09-01 | Tampering | migration 0009 | mitigate | `alembic/versions/0009_batch_name.py:41-46` native `op.add_column` on `batches` only; replay test `tests/test_batches.py:466-488` asserts the two `operations_no_%` triggers survive (count==2) — no move-and-copy rebuild touched the ledger | closed |
| T-09-09-02 | Info-disclosure | `batch.name` in chooser label | mitigate | `receipt_batch_chooser.html` top-up label renders `{{ batch.name }}` — no `\|safe`; default autoescape (the name embeds the untrusted product name) | closed |
| T-09-SC | Tampering (supply chain) | npm/pip/cargo installs | accept | ZERO packages installed this phase: `git log -- pyproject.toml uv.lock` shows the last touch was Phase 01 (`b909b1f`/`aabfe33`/`157ae69`); no phase-9 commit modifies dependency files. All 9 sub-plan summaries report `tech-stack: added: []` (AR-09-04) | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-09-01 | T-09-09, T-09-14 | The `confirm=1` oversell/over-removal override is a warn-but-allow UX safeguard inherited from the Phase 4 sale contract, not an authorization boundary — this v1 app has no auth (single local operator, CLAUDE.md). The server recomputes oversell fresh on every POST against the current `Batch.quantity` and never persists/trusts a "already confirmed" flag; a replayed `confirm=1` can only reproduce a decision the operator is entitled to make. Stock going negative is recoverable via a correction op. | gsd-security-auditor | 2026-07-12 |
| AR-09-02 | T-09-07-01 | The /history «Вернуть» link reuses the exact `/returns?sale_id=…&product_id=…&origin_op_id=…` URL already shipping in `recent_sales.html`/`purchase_history.html`. `GET /returns` re-resolves and validates the origin sale op entry-point-agnostically (`_resolve_origin`), and `register_return` re-validates before any write, so the new caller adds no trust surface. | gsd-security-auditor | 2026-07-12 |
| AR-09-03 | T-09-08-01 | The receipt-form `data-autofilled` dirty flag is purely client-side ergonomics (clear a stale machine-filled name before re-lookup). The server authoritatively answers fill-vs-204 in `lookup_prefill` and re-validates every field in `register_receipt`; a spoofed flag cannot produce a write. No server trust is placed in the flag. | gsd-security-auditor | 2026-07-12 |
| AR-09-04 | T-09-SC | Phase 9 installed zero new dependencies (verified against `pyproject.toml`/`uv.lock` git history and all 9 sub-plan `tech-stack: added: []` declarations). The RESEARCH Package Legitimacy Gate is satisfied vacuously — no supply-chain surface introduced. | gsd-security-auditor | 2026-07-12 |
| AR-09-05 | T-09-06-02 | Batch `comment`/`location` in the unchanged `batch_picker.html` continue to rely on default Jinja autoescape (never `\|safe`). No markup edit this phase touched that render path; confirmed 0 `\|safe` filters repo-wide. | gsd-security-auditor | 2026-07-12 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-12 | 30 | 30 | 0 | gsd-security-auditor |

**Threat Flags reconciliation:** All nine sub-plan summaries (09-01 … 09-09) declare
`## Threat Flags: None` / `tech-stack: added: []`. No new attack surface appeared
during implementation that lacks a threat mapping — **no unregistered flags**.

**XSS mitigation verification (T-09-06, -11, -15, -19, -06-02, -07-02, -08-02, -09-02):**
a repo-wide grep found **zero** actual `\|safe` filter expressions and **zero**
`{% autoescape false %}` blocks in `app/templates/` — every `\|safe` occurrence is
inside a `{# … #}` comment reminding "never `\|safe`". `Jinja2Templates` is built with
no `autoescape` override (`app/routes/__init__.py:9`), so default HTML autoescaping is
active on all `.html` templates. The XSS threats are closed by the framework default,
positively confirmed by the absence of every opt-out.

**Ledger integrity:** the mandatory D-12 batch guard (`STOCK_AFFECTING_TYPES`) and the
batch↔product ownership check both live in the single write path
(`record_operation`), so every current and future stock caller inherits them
(T-09-01, T-09-16). Both migrations use native `op.add_column`; replay tests prove the
append-only `operations_no_update`/`operations_no_delete` triggers survive and still
ABORT an `UPDATE` (T-09-02, T-09-09-01).

Suite health (per SUMMARY self-checks): `uv run pytest -q` → 328 passed after the
gap-closure wave; migration upgrade→downgrade cycles green for 0008 and 0009.

---

## Sign-Off

- [x] All 30 threats have a disposition (mitigate / accept / transfer)
- [x] Every `mitigate` threat verified by a code/test match at its cited location
- [x] Accepted risks documented in Accepted Risks Log (AR-09-01 … AR-09-05)
- [x] Threat Flags from all sub-plan summaries reconciled — no unregistered flags
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter
- [x] No implementation file modified (SECURITY.md is the only artifact written)

**Approval:** verified 2026-07-12
