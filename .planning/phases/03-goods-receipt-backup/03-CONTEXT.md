# Phase 3: Goods Receipt & Backup - Context

**Gathered:** 2026-07-08
**Status:** Ready for planning
**Mode:** Autonomous (recommended answers auto-accepted per user's full-auto directive)

<domain>
## Phase Boundary

Stock intake through the append-only ledger plus automated database backups. Operator registers goods receipts by product code (quantity, cost price, catalog price, sale price) with dictionary auto-fill; stock increases via ledger `receipt` operations. Before real daily data entry begins, the SQLite database gets automated WAL-safe backups (VACUUM INTO) with a verified restore path. No sales, write-offs, or reports yet (Phases 4–6).

</domain>

<decisions>
## Implementation Decisions

### Receipt Entry Flow
- **D-01:** One receipt entry = one product line = one ledger `receipt` operation (qty_delta > 0). No multi-line receipt documents in v1 — fast repeat entry replaces them.
- **D-02:** Page `/receipts/new`: fields code, name (auto-filled), quantity, cost price, catalog price, sale price. After successful save the form clears and focus returns to the code field ("save & add next" loop) — minimal clicks for a box of many items.
- **D-03:** Name auto-fills from the dictionary via the existing HTMX lookup pattern (GET /dictionary/lookup, 204 pattern, ~300ms debounce) — RCP-02. If the code matches an existing product, its current name/prices pre-fill the form.
- **D-04:** Recent receipts visible on the receipts page (last N entries partial) so the operator sees what was just entered.

### Unknown Product Handling
- **D-05:** Receipt for a code with no product card auto-creates the product (code, name from dictionary or typed, entered prices) in the same transaction — no separate "create product first" detour. Auto-creation records `product_created` op per Phase 2 conventions.

### Price Capture & Card Update
- **D-06:** The `receipt` operation snapshots entered unit_cost_cents and prices (payload carries catalog/sale prices) — success criterion 3.
- **D-07:** Entered prices also update the product card (cost/sale/catalog) via the existing `price_change` operations in the same transaction, so the card always reflects the latest intake prices while history is preserved (CAT-04 machinery reused).

### Backup & Restore (BCK-01)
- **D-08:** Backup method: `VACUUM INTO 'backups/myorishop-YYYYMMDD-HHMMSS.db'` — WAL-safe, produces a compact standalone copy.
- **D-09:** Automatic backup on app startup (before serving requests, skipped if DB missing/empty) + manual "Backup now" button on a simple /backup page showing existing backups.
- **D-10:** Retention: keep the most recent 30 backups; older ones deleted automatically after a successful new backup.
- **D-11:** Restore: documented procedure + `restore.bat`/script that copies a chosen backup over the live DB while the app is stopped. Restore must be verified at least once (automated test restoring a backup into a temp path and reading data back).

### Claude's Discretion
- Exact backup page layout, filename format details, empty-state texts
- Migration needs (likely none beyond possible indexes), template structure
- Whether recent-receipts list is a dedicated page or a partial under the form

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions
- `.planning/phases/01-foundation-ledger-core/01-CONTEXT.md` — ledger schema, money/UUID/UTC conventions, single write path
- `.planning/phases/02-catalog-dictionary-search/02-CONTEXT.md` — dictionary lookup 204 pattern, price_change ops, soft-delete rules

### Project docs
- `.planning/REQUIREMENTS.md` — RCP-01, RCP-02, BCK-01 definitions
- `.planning/ROADMAP.md` — Phase 3 success criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/ledger.py` — `record_operation` single write path; `OPERATION_TYPES` already includes `receipt` (`app/models.py:34`)
- `app/services/catalog.py` — product creation/price-change logic to reuse for auto-create and card updates
- `app/services/dictionary.py` + `GET /dictionary/lookup` — name auto-fill (RCP-02) ready to reuse
- `app/core.py` — to_cents (comma/dot), format_cents, utcnow_iso, new_id
- `tests/conftest.py` — tmp-path SQLite engine, session, TestClient fixtures

### Established Patterns
- Thin routes / fat services; typed Form inputs; HTMX partials; RU UI text; ruff + pytest gates
- All stock changes only through ledger service; frozen Alembic migrations style

### Integration Points
- New: `app/routes/receipts.py`, `app/services/receipts.py` (or extend catalog/ledger), templates page + partial, nav link in `base.html`
- New: backup service (VACUUM INTO via engine connection), startup hook in `app/main.py`, `/backup` route, `restore.bat`
- `backups/` directory git-ignored

</code_context>

<specifics>
## Specific Ideas

- Fast entry is the core value: save-and-next loop, focus management, money input accepts comma and dot
- UI text Russian; backups must work fully offline (local folder only)

</specifics>

<deferred>
## Deferred Ideas

- Multi-line receipt documents (batch header grouping lines) — revisit if single-line loop proves slow
- Scheduled/periodic backups while app runs (startup + manual is enough for one operator)
- Off-machine backup copies (cloud/USB sync) — v2 concern
- CSV export — Phase 6 (BCK-02)

</deferred>

---

*Phase: 3-Goods Receipt & Backup*
*Context gathered: 2026-07-08*
