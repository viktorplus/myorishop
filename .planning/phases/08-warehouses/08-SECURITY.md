---
phase: 8
slug: warehouses
status: verified
threats_open: 0
asvs_level: default (not explicitly set by project)
created: 2026-07-11
---

# Phase 8 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| `app/services/warehouses.py` (called by routes) | HTTP form input reaches `add_warehouse`/`update_warehouse` | `name`, `address` strings |
| Browser -> POST /warehouses, /warehouses/{id}, /warehouses/{id}/delete, /warehouses/{id}/restore | Untrusted form input from the browser | `name`, `address`, `confirm` |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-08-01 | Tampering | `add_warehouse`/`update_warehouse` (`app/services/warehouses.py`) | mitigate | `app/services/warehouses.py:34-44,54-64` — `.strip()` + blank check on `name`, returns `(None, errors)` before any `session.add`/`commit`; confirmed by passing test `test_add_warehouse_requires_name` | closed |
| T-08-02 | Tampering | `alembic/versions/0007_warehouses.py` | mitigate | `grep -c "import app.models\|import app.core\|from app"` returns 0; `DEFAULT_WAREHOUSE_ID`/`_SEED_CREATED_AT` (lines 32-33) are frozen literals consumed only by the local `op.bulk_insert` — WR-06 compliant | closed |
| T-08-03 | Repudiation | `soft_delete_warehouse`'s `confirm=True` bypass of the last-active-warehouse warning | accept | No auth exists in v1 (CLAUDE.md constraint) — `confirm` is not an authorization boundary; soft-delete is fully reversible via `restore_warehouse` (`app/services/warehouses.py:67-73`) | closed |
| T-08-04 | Tampering / Information Disclosure | `partials/warehouse_rows.html` rendering `w.name`/`w.address` | mitigate | 0 matches for `\|safe` in the template; `app/routes/__init__.py:9` builds `Jinja2Templates` with no `autoescape=False` override, so default HTML autoescaping is active | closed |
| T-08-05 | Elevation of Privilege | all `/warehouses` routes are unauthenticated | accept | No auth exists anywhere in this v1 single-local-operator app (CLAUDE.md/PROJECT.md decision); consistent with every other router | closed |
| T-08-06 | Repudiation | `confirm=1` re-POST bypassing the last-active-warehouse warning via a scripted request | accept | Same warn-but-allow UX pattern as T-08-03 at the route layer; reversible via `POST /warehouses/{id}/restore` | closed |
| T-08-SC | Tampering (supply chain) | npm/pip/cargo installs | N/A | No new dependency introduced — `git log --oneline -- pyproject.toml` shows no phase-8 commits touching it | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-08-01 | T-08-03, T-08-06 | Deleting (or force-deleting via `confirm=1`) the last active warehouse is a UX safeguard, not a security control: this v1 app has no authentication anywhere (single local operator, per CLAUDE.md/PROJECT.md), so there is no privilege boundary for `confirm` to bypass; soft-delete is fully reversible via `restore_warehouse` — no data loss even in the worst case | gsd-security-auditor | 2026-07-11 |
| AR-08-02 | T-08-05 | All `/warehouses` routes are unauthenticated. Accepted because no auth mechanism exists anywhere in this v1 codebase — a documented project-level decision, not a phase-8-specific gap. Revisit when multi-operator sync ships (CLAUDE.md roadmap notes on session-cookie auth) | gsd-security-auditor | 2026-07-11 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-11 | 7 | 7 | 0 | gsd-security-auditor |

**Notes:** No `## Threat Flags` section in either 08-01-SUMMARY.md or 08-02-SUMMARY.md. Independent review of routes/templates/service/migration diffs found no additional attack surface beyond the register above — all form input flows through validated service functions or autoescaped templates; all DB access is parameterized ORM. One non-blocking, pre-existing observation: `Warehouse.name`/`Warehouse.address` (`String(200)`/`String(300)`) are not length-enforced at the SQLite storage layer or in service validation — matches the pre-existing `Product`/`Dictionary` pattern elsewhere, not a phase-8 regression.

Full verification run: `uv run pytest tests/test_warehouses.py -q` → 15 passed.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-11
