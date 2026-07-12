---
phase: 09-batch-tracking-ledger-integration
plan: 07
subsystem: history-ui
tags: [history, returns, templates, htmx, uat-gap-closure]
requires:
  - GET/POST /returns (entry-point-agnostic return routes, already shipping)
  - history_view read service (rows carry op/product/batch)
provides:
  - "/history «Код» column (scannable product code, own cell)"
  - "/history sale-row «Вернуть» link -> GET /returns targeting #return-slot"
affects:
  - app/templates/partials/history_rows.html
  - app/templates/pages/history.html
tech-stack:
  added: []
  patterns:
    - "Mirror the sibling sale-listing templates (recent_sales.html / purchase_history.html) for the «Код» column + «Вернуть» link + #return-slot rather than inventing new markup"
    - "return-slot lives OUTSIDE the table so a #history-tbody innerHTML/filter swap never wipes an in-progress return form"
key-files:
  created: []
  modified:
    - app/templates/partials/history_rows.html
    - app/templates/pages/history.html
    - tests/test_history.py
decisions:
  - "Removed the inline ({{ code }}) from the «Товар» cell so the code lives in exactly one place (its own «Код» column) — matches the two shipping sibling templates and the operator's request"
  - "Non-sale rows render an aligned muted «—» in the «Действие» column to keep the 10-column grid consistent"
metrics:
  duration: ~20m
  completed: 2026-07-12
  tasks: 2
  files-changed: 3
  tests: 11 (history file); 328 (full suite)
---

# Phase 9 Plan 07: /history «Код» column + «Вернуть» return action Summary

Template-only gap-closure for Phase 9 UAT test 6: /history now surfaces a dedicated, scannable «Код» column and a sale-row «Вернуть» link (same `/returns?sale_id=…&product_id=…&origin_op_id=…` shape as `recent_sales.html`) that renders the return form into a `#return-slot` outside the table — making legacy sales reachable and returnable from the one view not capped at 10 recent sales. No route or service code changed.

## What Was Built

**Task 1 — templates (`ab706c3`)**
- `app/templates/partials/history_rows.html`:
  - Added a dedicated `<td>{{ r.product.code }}</td>` between the «Тип» and «Товар» cells.
  - Removed the inline ` ({{ r.product.code }})` from the «Товар» cell (code now lives in one place); the D-15 muted batch second line was left byte-for-byte intact (W3 caution honored).
  - Added a trailing «Действие» `<td>`: sale rows (`r.op.type == "sale"`) render the neutral `hx-get="/returns?…"` «Вернуть» link targeting `#return-slot`; every other row renders `<span class="muted">—</span>`.
  - Empty-state `colspan` 8 → 10.
- `app/templates/pages/history.html`:
  - Added `<th>Код</th>` (between «Тип» and «Товар») and a trailing `<th>Действие</th>` — header is now 10 columns, matching the data rows cell-for-cell.
  - Added `<div id="return-slot"></div>` after `</table>` (outside the `#history-tbody` innerHTML-swap and `<tfoot>` `#load-more` boundaries), mirroring the sibling templates.

**Task 2 — regression tests (`cdd2178`)**
- Renamed `test_web_history_table_stays_8_columns` → `test_web_history_table_has_10_columns` and updated the assertion to `== 10`.
- `test_web_history_filters`: dropped the inline ` ({code})` from both «Товар»-cell assertions (now `<td>{name}` present / absent) and updated the docstring to reflect the code moving to its own column.
- Added `test_web_history_has_code_column_and_return_link`: asserts the `<td>{code}</td>` cell, the `/returns?sale_id=` + `origin_op_id=` link, the `>Вернуть<` text, and `id="return-slot"`.

## Verification

- `uv run pytest tests/test_history.py -q` → 11 passed (10 prior + 1 new).
- `uv run ruff check tests/test_history.py` → clean.
- `uv run pytest -q` (full suite) → 328 passed (327 prior + 1 new), 3 pre-existing unrelated SAWarnings in test_receipts/test_returns.
- Header/data column counts confirmed equal at 10: Когда, Тип, Код, Товар, Кол-во, Цена, Себестоимость, Причина, Кто, Действие.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Verification cwd corrected for worktree execution**
- **Found during:** Task 1 verify.
- **Issue:** The plan's `<automated>` verify command hardcodes `cd "E:/dev/myorishop"` (the MAIN repo path). This executor runs in an isolated worktree at `E:/dev/myorishop/.claude/worktrees/agent-ae67f1a10c0c982eb`. Running pytest from the main-repo cwd loaded the **main repo's** unedited `pages/history.html` (Jinja loader searchpath is relative `app/templates`, resolved against cwd), so the suite reported a false 10/10 pass while the worktree's actual edits were never exercised (confirmed: main-repo template had 8 header `<th>` and no `#return-slot`; worktree template had 10 + slot).
- **Fix:** Ran all verification (`pytest`, `ruff`) from the worktree root so the loader picked up the edited templates. From the worktree, the two pre-fix tests failed exactly as the plan predicted, then passed after the Task 2 test updates.
- **Files modified:** none (verification-invocation only).
- **Commit:** n/a (no code change).

## Threat Surface

No new trust surface. The «Вернуть» link reuses the exact `/returns?…` URL shape already shipping in `recent_sales.html`/`purchase_history.html`; GET /returns re-resolves and validates the origin sale op entry-point-agnostically (T-09-07-01, accept). Jinja autoescape kept on the new «Код»/«Товар» cells — never `|safe` (T-09-07-02, mitigated).

## Known Stubs

None.

## Self-Check: PASSED

- Files verified present: history_rows.html, history.html, test_history.py, 09-07-SUMMARY.md
- Commits verified: ab706c3 (templates), cdd2178 (tests), be609a0 (summary)
