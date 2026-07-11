---
phase: 08-warehouses
verified: 2026-07-11T07:59:23Z
status: human_needed
score: 11/11 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Start `uv run uvicorn app.main:app --port 8000`, open http://localhost:8000/warehouses. Confirm the seeded «Склад по умолчанию» row shows on first load with no setup step."
    expected: "Page loads with one active warehouse row already present, no empty state."
    why_human: "Visual first-load confirmation; automated tests build their own rows via the session/client fixtures and never assert against a real post-migration DB (per 08-02-SUMMARY.md's own note that the test engine uses Base.metadata.create_all, not the Alembic seed migration)."
  - test: "Add a warehouse with only a name (no address); confirm it appears in the list."
    expected: "New row appears with blank address cell, no page navigation."
    why_human: "Visual/interaction confirmation of an already-passing automated case; browser DOM behavior (htmx swap) not exercised by TestClient."
  - test: "Delete a NON-last warehouse; confirm native browser confirm dialog appears, then the row goes muted with a Восстановить button and no page navigation."
    expected: "hx-confirm dialog fires, row mutes in place, URL does not change."
    why_human: "hx-confirm is a client-side browser dialog; TestClient does not execute JS/htmx, so the confirm-then-swap UX can't be verified programmatically."
  - test: "Delete the LAST remaining active warehouse; confirm the inline «Это последний активный склад» warning renders with zero navigation, then click «Удалить всё равно» to complete the delete."
    expected: "Warning row appears inline under the target row; clicking through deletes it with no full-page reload."
    why_human: "Visual placement/behavior of the inline warning block and the two-step confirm flow in a real browser; automated tests only assert the response body contains the expected strings, not the rendered DOM interaction."
  - test: "Click Восстановить on a deleted row; confirm it returns to active styling with a Удалить button again."
    expected: "Row un-mutes, action button switches back from Восстановить to Удалить."
    why_human: "Visual style-state transition in the browser."
  - test: "Confirm the Склады nav link is visible and marked active on /warehouses from every other page in the app."
    expected: "Nav link present and highlighted correctly across all pages."
    why_human: "Cross-page visual nav-state check; automated coverage only checks GET / for the link's presence, not the active-class behavior from other pages or general visual placement."
---

# Phase 8: Warehouses Verification Report

**Phase Goal:** Operators can organize stock across more than one physical warehouse
**Verified:** 2026-07-11T07:59:23Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can create, edit, and soft-delete/restore a warehouse from a warehouse management page (ROADMAP SC1) | ✓ VERIFIED | `app/routes/warehouses.py` defines GET/POST `/warehouses`, POST `/warehouses/{id}`, `/delete`, `/restore`, all wired to `app/services/warehouses.py`; `tests/test_warehouses.py::test_web_add_and_edit_rows`, `test_web_deleted_warehouse_stays_visible_with_restore` pass |
| 2 | All existing v1.0 stock is automatically attributed to a seeded default warehouse after migration, with no data loss (ROADMAP SC2) | ✓ VERIFIED | `alembic/versions/0007_warehouses.py` creates a standalone `warehouses` table (no FK to/from existing tables) and seeds exactly one row (`DEFAULT_WAREHOUSE_ID = 00000000-0000-4000-8000-000000000010`, "Склад по умолчанию"); migration only adds a new table, never touches existing ones; `alembic heads` confirms 0007 is current head reached via `0006 -> 0007`; `test_migration_0007_creates_and_seeds_default_warehouse` passes |
| 3 | A soft-deleted warehouse no longer appears as a selectable option elsewhere in the app, but its operation history is preserved (ROADMAP SC3) | ✓ VERIFIED | `deleted_at` is set, never a hard delete (`soft_delete_warehouse`/`restore_warehouse` in `app/services/warehouses.py`); `list_warehouses` is the only query function against `Warehouse` and is used solely by the `/warehouses` management page itself; no other route/template in the codebase references `Warehouse` (grep across `app/` finds matches only in the 7 warehouse-specific files), so no other "selectable option" surface exists yet to leak deleted rows into — this criterion is structurally satisfied pending Phase 9's `Batch.warehouse_id` wiring |
| 4 | A Warehouse row can be created with a required name and optional address (D-04) | ✓ VERIFIED | `add_warehouse` validates non-blank `name`, allows `address` optional; `test_add_warehouse_creates_row`, `test_add_warehouse_requires_name` pass |
| 5 | Soft-deleting a warehouse sets `deleted_at` without removing the row; restoring clears it; row never excluded from `list_warehouses` (D-05/D-09) | ✓ VERIFIED | `grep -c "deleted_at.is_(None)" app/services/warehouses.py` = 1 (only in the active-count guard, confirming `list_warehouses` has no filter); `test_soft_delete_and_restore_roundtrip` passes |
| 6 | Soft-deleting the LAST remaining active warehouse is blocked with a warning until `confirm=1`; zero writes before confirmation (D-06) | ✓ VERIFIED | `soft_delete_warehouse` computes `active_count` before any write and returns `(False, {"warehouse": w})` with no `session.commit()` reached; `test_delete_last_active_warehouse_warns_then_allows` and `test_web_delete_last_active_warehouse_warns_then_confirm_deletes` pass |
| 7 | The nav bar exposes a Склады link to /warehouses from every page | ✓ VERIFIED | `app/templates/base.html` line 21: `<a href="/warehouses"...>Склады</a>`, positioned after Категории, rendered by every page via `{% extends "base.html" %}`; `test_web_nav_has_warehouses_link` passes |
| 8 | Router registered and reachable | ✓ VERIFIED | `app/main.py` imports `warehouses` and calls `app.include_router(warehouses.router)` |
| 9 | Deleted warehouse stays visible in the list with a Восстановить button (D-09, SC3) | ✓ VERIFIED | `warehouse_rows.html` branches `{% if not w.deleted_at %}Удалить{% else %}Восстановить{% endif %}`; `test_web_deleted_warehouse_stays_visible_with_restore` passes |
| 10 | No HX-Redirect anywhere in the warehouse routes (D-08 single-page CRUD) | ✓ VERIFIED | `grep -c "HX-Redirect" app/routes/warehouses.py` = 0 |
| 11 | Full existing test suite unaffected | ✓ VERIFIED | `uv run pytest -q` → 262 passed, 0 failed |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | `class Warehouse(Base)` with id/name/address/created_at/updated_at/deleted_at | ✓ VERIFIED | Lines 119-137, matches Product's soft-delete shape exactly |
| `alembic/versions/0007_warehouses.py` | warehouses table + seeded default row, `revision = "0007"`, `down_revision = "0006"` | ✓ VERIFIED | Confirmed via file read + `alembic heads` = 0007 |
| `app/services/warehouses.py` | CRUD + warn-but-allow service functions | ✓ VERIFIED | `list_warehouses`, `add_warehouse`, `update_warehouse`, `restore_warehouse`, `soft_delete_warehouse` all present and substantive (real DB queries, no stubs) |
| `app/routes/warehouses.py` | page + add/update/delete/restore routes | ✓ VERIFIED | All 5 routes present, each calls into the service layer and re-renders the rows partial |
| `app/templates/pages/warehouses.html` | warehouse management page | ✓ VERIFIED | Contains "Склады" h1, inline add form, includes rows partial |
| `app/templates/partials/warehouse_rows.html` | rows partial, swap target for every POST | ✓ VERIFIED | Contains `id="warehouse-rows"` and `warning_id`-driven inline warn block |
| `tests/test_warehouses.py` | migration + service + web-layer tests | ✓ VERIFIED | 15 tests, all passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/services/warehouses.py` | `app/models.py` | `select(Warehouse)` / `session.get(Warehouse, ...)` | ✓ WIRED | Confirmed by reading the file; real ORM queries, not stubs |
| `alembic/versions/0007_warehouses.py` | `warehouses` table | `op.bulk_insert` seed row | ✓ WIRED | `DEFAULT_WAREHOUSE_ID` literal inserted; migration test confirms the row exists post-upgrade |
| `app/templates/base.html` | `app/routes/warehouses.py` | `href="/warehouses"` | ✓ WIRED | Nav link present at line 21 |
| `app/main.py` | `app/routes/warehouses.py` | `app.include_router(warehouses.router)` | ✓ WIRED | Confirmed at line 44; import at line 22 |
| `app/routes/warehouses.py` | `app/services/warehouses.py` | `from app.services.warehouses import ...` | ✓ WIRED | All 5 service functions imported and called by name in each route handler |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `warehouses.html` / `warehouse_rows.html` | `warehouses` (context var) | `list_warehouses(session)` → `session.scalars(select(Warehouse))` | Yes — real DB query, no hardcoded/static return | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Warehouse tests pass (migration + service + web) | `uv run pytest tests/test_warehouses.py -q` | 15 passed | ✓ PASS |
| Full suite unaffected | `uv run pytest -q` | 262 passed, 0 failed | ✓ PASS |
| Migration chain reaches new head | `uv run alembic heads` | `0007 (head)` | ✓ PASS |
| Lint clean on modified Python files | `uv run ruff check app/models.py app/services/warehouses.py app/routes/warehouses.py alembic/versions/0007_warehouses.py` | All checks passed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|--------------|--------|----------|
| WH-01 | 08-01, 08-02 | User can create and manage multiple warehouses | ✓ SATISFIED | Full CRUD + soft-delete/restore backend and UI verified above; REQUIREMENTS.md traceability table already marks WH-01 "Complete", matching codebase evidence |

No orphaned requirements — REQUIREMENTS.md maps only WH-01 to Phase 8, and both plans declare `requirements: [WH-01]`.

### Anti-Patterns Found

None. Grep for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER|not yet implemented|coming soon` across all phase-modified files (`app/models.py`, `app/services/warehouses.py`, `app/routes/warehouses.py`, `app/templates/pages/warehouses.html`, `app/templates/partials/warehouse_rows.html`, `alembic/versions/0007_warehouses.py`) returned no matches.

### Human Verification Required

See frontmatter `human_verification` list. The plan's own Task 2 `<verify><human-check>` block (six-step manual UAT: seeded row on first load, add-without-address, delete-non-last with native confirm, delete-last-active warn-then-confirm, restore, nav link across pages) was explicitly **not run** by the executor — 08-02-SUMMARY.md states this directly: "Manual UAT ... was NOT run by this automated executor — recommend running it before considering Phase 8 fully closed." All automated truths pass, but this deferred human-check block means the phase cannot be marked `passed` outright.

### Gaps Summary

No code-level gaps found. All 11 observable truths (3 roadmap success criteria + 8 plan-level truths) are verified against the actual codebase: models, migration, service layer, routes, templates, nav, and router registration all exist, are substantive, and are wired together correctly. The full test suite (262 tests) passes with zero failures, and the new `tests/test_warehouses.py` (15 tests) covers migration, service, and web layers.

The only open item is the plan's own deferred manual UAT (Task 2 human-check), which the executor explicitly skipped per its own SUMMARY. This is a status-determining item per the escalation-gate protocol (Step 9: any harvested human-check item forces `human_needed`, even at a full automated score) — not a defect, but a required sign-off before the phase is considered fully closed.

---

*Verified: 2026-07-11T07:59:23Z*
*Verifier: Claude (gsd-verifier)*
