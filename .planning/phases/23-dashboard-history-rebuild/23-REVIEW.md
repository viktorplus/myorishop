---
phase: 23-dashboard-history-rebuild
reviewed: 2026-07-17T17:33:23Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - alembic/versions/0016_active_catalog.py
  - app/models.py
  - app/routes/catalogs.py
  - app/routes/history.py
  - app/routes/home.py
  - app/routes/mobile_history.py
  - app/routes/mobile_home.py
  - app/services/active_catalog.py
  - app/services/dashboard.py
  - app/services/operations.py
  - app/templates/mobile_pages/history.html
  - app/templates/mobile_pages/home.html
  - app/templates/mobile_partials/history_cards.html
  - app/templates/mobile_partials/history_pagination.html
  - app/templates/pages/catalogs.html
  - app/templates/pages/home.html
  - app/templates/partials/active_catalog_form.html
  - app/templates/partials/dashboard_tiles.html
  - app/templates/partials/history_rows.html
  - app/templates/partials/period_filter.html
  - tests/test_active_catalog.py
  - tests/test_dashboard.py
  - tests/test_history.py
  - tests/test_home.py
  - tests/test_mobile_history.py
  - tests/test_mobile_home.py
  - tests/test_smoke.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 23: Code Review Report

**Reviewed:** 2026-07-17T17:33:23Z
**Depth:** standard
**Files Reviewed:** 25 (routes, services, migration, templates, tests)
**Status:** issues_found

## Summary

Reviewed the DASH-01..05 (Главная rebuild) and HIST-01..04 (/history + /m/history filter parity) slice, plus the new `active_catalog` table/service/form. The write paths are correctly read-only (`dashboard_context`, `history_view`), joins are consistently `outerjoin` where the docstrings claim so (verified against the actual SQLAlchemy calls, not just the comments), money math (`profit_cents = gross + expense`, never subtraction) is correct, and templates only ever interpolate with Jinja's default autoescaping (no `|safe` on any untrusted field across the reviewed set). Test coverage for the new code is thorough and exercises the documented edge cases (empty catalog, closed catalog, half-open date ranges, per-type column narrowing).

No blockers found. Three warnings worth fixing before this ships: an unvalidated-echo inconsistency in `history_view`'s `type_filter`, a genuine singleton-race gap in `active_catalog`'s get-or-create, and a date-format validation gap that lets non-canonical ISO-8601 strings get persisted into a column an HTML `<input type="date">` expects in strict `YYYY-MM-DD` form.

## Warnings

### WR-01: `history_view` echoes an unvalidated `type_filter` back into the response

**File:** `app/services/operations.py:106-159`
**Issue:** The WHERE clause is correctly gated: `if type_filter and type_filter in OPERATION_TYPES:` (line 106) — an unrecognized value is ignored, matching the documented "unknown/tampered type_filter is ignored" contract (T-05-20). But the returned dict echoes the *raw, unvalidated* value:
```python
"type_filter": type_filter or "",   # line 154 — not gated by the OPERATION_TYPES check above
```
If a caller passes `?type=bogus`, the query correctly returns the unfiltered result set, but `result["type_filter"]` comes back as `"bogus"` instead of `""`. Downstream this:
- Makes `history_rows.html`'s `<select>` show neither "Все типы" nor any real option as `selected` (both the `{% if not type_filter %}` and `{% if t == type_filter %}` checks fail), a silent UI desync.
- Propagates `"bogus"` into `extra_qs` (`app/routes/history.py:129`), so every pagination link keeps re-sending the invalid value.
- Also affects `app/routes/mobile_history.py:113` the same way.

**Fix:** Gate the echoed value the same way the WHERE clause is gated:
```python
valid_type = type_filter if (type_filter and type_filter in OPERATION_TYPES) else None
...
"type_filter": valid_type or "",
"columns": HISTORY_TYPE_COLUMNS.get(valid_type),
```

### WR-02: `active_catalog` singleton has no concurrency guard — two near-simultaneous POSTs can create two rows

**File:** `app/services/active_catalog.py:40-72`
**Issue:** `set_active_catalog` does a classic check-then-act: `get_active_catalog(session)` (SELECT ... LIMIT 1) then, if `None`, `session.add(ActiveCatalog(...))`. There is no unique constraint on the table (by design, per the model/migration docstrings) and no transaction-level locking. Two overlapping requests to `POST /catalogs/active` (e.g., a double-click, or two browser tabs on `/catalogs`) can both observe "no row yet" and both insert a new row, breaking the "singleton by convention" invariant that `get_active_catalog`'s `ORDER BY created_at LIMIT 1` (line 35-37) and `catalog_status`/`dashboard_context` implicitly depend on — the second row becomes silently invisible to every reader forever (not a crash, but silent data loss of one of the two writes with no error surfaced to the operator).
**Fix:** At minimum, document this as an accepted single-operator limitation (it may already be implicitly accepted, but the docstring doesn't call out the race explicitly — only the "no DB constraint" convention). If low effort is acceptable, add a partial unique index (e.g., `sqlite_where=text("1=1")`, effectively a full unique-on-empty-key trick is awkward in SQLite) or simplify by using a fixed, well-known PK (e.g., a singleton constant `id`) instead of `new_id()`, which would make `INSERT ... ON CONFLICT` style upserts trivial and eliminate the race entirely:
```python
_SINGLETON_ID = "00000000-0000-0000-0000-000000000000"
```

### WR-03: `close_date` validation accepts non-canonical ISO-8601 strings and stores them verbatim

**File:** `app/services/active_catalog.py:55-59, 69`
**Issue:** Validation only checks parseability:
```python
try:
    date.fromisoformat(close_date)
except ValueError:
    errors["close_date"] = CLOSE_DATE_ERROR
...
row.close_date = close_date or None   # stores the RAW input string, not date.isoformat()
```
Since Python 3.11, `date.fromisoformat()` accepts more than strict `YYYY-MM-DD` — e.g. `date.fromisoformat("20260831")` (basic format, no separators) succeeds and returns a valid `date`. If a caller POSTs `close_date=20260831` (e.g., via `curl`/a non-browser client — there is no auth gate blocking this), the raw 8-character string is stored verbatim in the `String(10)` column. On re-render, `<input type="date" value="{{ active.close_date or '' }}">` (`app/templates/partials/active_catalog_form.html:14`) will not be recognized by the browser as a valid date (HTML5 date inputs require canonical `YYYY-MM-DD`), so the field silently renders blank on reload even though a value is stored — the operator will believe the close date wasn't saved. `catalog_status()` (`app/services/dashboard.py:64-66`) still computes `days_left` correctly since it also calls the lenient `date.fromisoformat`, so the dashboard countdown itself isn't broken, but the round-trip through the edit form is.
**Fix:** Normalize before storing:
```python
if close_date:
    try:
        parsed = date.fromisoformat(close_date)
    except ValueError:
        errors["close_date"] = CLOSE_DATE_ERROR
    else:
        close_date = parsed.isoformat()  # canonical YYYY-MM-DD
```

## Info

### IN-01: Misleading "mirrors history_cards.html" comment on the mobile dashboard feed

**File:** `app/templates/mobile_pages/home.html:78-93`
**Issue:** The comment above `FEED_FIELDS` says "Per-type field presence mirrors history_cards.html's own `columns` narrowing." In fact `FEED_FIELDS` diverges from `HISTORY_TYPE_COLUMNS` (`app/services/operations.py:32-39`) in several places — e.g. `correction` is `("qty",)` in the feed vs `("expiry", "qty", "reason")` in history; `writeoff`/`sale`/`return` drop `reason`/`price`/`warehouse` entirely. The feed actually mirrors desktop's `pages/home.html` hard-coded table (which has the same reduced field set), not `history_cards.html`. This isn't a functional bug — the reduced feed columns are a deliberate simplification consistent between desktop/mobile dashboards — but the comment will mislead a future maintainer who edits `HISTORY_TYPE_COLUMNS` expecting the dashboard feed to follow along.
**Fix:** Reword the comment to say it mirrors `pages/home.html`'s own reduced field set, not `history_cards.html`'s `HISTORY_TYPE_COLUMNS`.

### IN-02: `_resolve_history_period` is duplicated verbatim (minus the presets) between desktop and mobile routes

**File:** `app/routes/history.py:23-80`, `app/routes/mobile_history.py:37-65`
**Issue:** Both routes independently implement date-range parsing/validation with the same error strings (`INVALID_DATE_ERROR`, `INVERTED_RANGE_ERROR` are literally re-declared as separate module-level constants in each file) and the same malformed/inverted-range fallback logic. The docstrings acknowledge this is intentional ("this codebase has no shared route-helper module"), so this is a pre-existing codebase convention rather than a new regression — flagging for visibility since any future change to the RU error copy or the fallback behavior must now be applied in two places, and it's easy to update one and miss the other.
**Fix:** No action required this phase; consider a shared `app/routes/_history_period.py` helper in a future cleanup pass if a third consumer appears.

### IN-03: No-JS form fallback for `/catalogs/active` returns a bare fragment, not a full page

**File:** `app/routes/catalogs.py:69-88`, `app/templates/partials/active_catalog_form.html`
**Issue:** The template comment claims the `method="post" action="/catalogs/active"` pair exists "for no-JS progressive enhancement," but the route always returns `partials/active_catalog_form.html` (a bare `<form>` fragment, not extending `base.html`) regardless of whether the request came from htmx or a plain browser POST. A user with JavaScript/htmx disabled who submits the form would see only the bare form fragment as the entire page body (no `<html>`/`<head>`/nav), not a real "no-JS fallback" experience. This mirrors an existing codebase-wide convention (`finance_withdraw`, per the docstring) so it isn't a regression introduced by this phase, but the "progressive enhancement" claim in the comment overstates what actually happens for a no-JS client.
**Fix:** No action required this phase (matches established convention); if genuine no-JS support is ever required, `catalogs_active` would need `is_hx` branching to redirect/render the full `/catalogs` page on a non-HX POST.

---

_Reviewed: 2026-07-17T17:33:23Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
