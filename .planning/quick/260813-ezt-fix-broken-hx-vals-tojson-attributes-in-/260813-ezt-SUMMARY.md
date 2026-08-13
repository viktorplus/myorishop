---
quick_id: 260813-ezt
type: execute
subsystem: mobile-partials, sale-templates
tags: [bugfix, hx-vals, tojson, htmx, mobile-wizards]
dependency-graph:
  requires: []
  provides: [single-quoted-tojson-hx-vals-pattern]
  affects: [mobile-sale-wizard, mobile-correction-wizard, mobile-writeoff-wizard, mobile-transfer-wizard, desktop-sale-name-search]
tech-stack:
  added: []
  patterns: ["hx-vals='{{ ... | tojson }}' single-quoted, never double-quoted"]
key-files:
  created: []
  modified:
    - app/templates/mobile_partials/batch_card_picker.html
    - app/templates/mobile_partials/transfers_step_batch.html
    - app/templates/mobile_partials/transfers_step_dest.html
    - app/templates/partials/sale_name_field.html
    - app/__init__.py
    - tests/test_mobile_corrections.py
    - tests/test_mobile_transfers.py
decisions: []
metrics:
  duration: ~25min
  completed: 2026-08-13
---

# Quick Task 260813-ezt: Fix broken hx-vals tojson attributes Summary

Five `hx-vals="{{ ... | tojson }}"` HTML attributes were double-quoted around a tojson expression, which always emits JSON's mandatory double-quoted keys/values — the browser's HTML parser truncated each attribute at the payload's first `"`, silently dropping `batch_id`/`code`/`name`/`row` before they ever reached the server. Fixed by switching all five attributes from double to single quotes (no logic change), correcting two stale comments that falsely claimed tojson escapes double quotes, and adding three regression tests that pin the exact rendered attribute shape.

## What Was Built

- **`app/templates/mobile_partials/batch_card_picker.html`**: single-quoted `hx-vals` on the batch card tap (shared by sale/correction/write-off wizards); WR-02 comment corrected to state tojson always emits double-quoted JSON so the attribute must be single-quoted, and that tojson escapes single quotes in the data to their unicode escape.
- **`app/templates/mobile_partials/transfers_step_batch.html`**: both `hx-vals` occurrences single-quoted — the batch-pick card and the «Назад» button; both stale comments corrected with the same rule, and the still-accurate hx-vals-vs-hx-include rationale on the «Назад» button preserved verbatim.
- **`app/templates/mobile_partials/transfers_step_dest.html`**: the «Назад» button's `hx-vals` single-quoted; comment corrected.
- **`app/templates/partials/sale_name_field.html`**: the desktop sale name-search debounce row param's `hx-vals` single-quoted (no stale comment existed here — quote-delimiter change only).
- **`app/__init__.py`**: `__version__` bumped `"1.28"` → `"1.29"`.
- **`tests/test_mobile_corrections.py`**: new test `test_mobile_correction_batch_step_hx_vals_batch_id_survives_html_attribute` asserts the exact single-quoted rendered attribute `hx-vals='{"batch_id": "...", "code": "..."}'` and guards `'hx-vals="{' not in response.text`.
- **`tests/test_mobile_transfers.py`**: two new tests — `test_transfers_step_batch_hx_vals_batch_id_survives_html_attribute` (covers both fixed spots in `transfers_step_batch.html` in one response) and `test_transfers_step_dest_hx_vals_back_button_is_single_quoted` (covers `transfers_step_dest.html`'s fifth fixed line).

## Task Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: single-quote the five hx-vals attributes, correct comments, bump version | `599b895` | batch_card_picker.html, transfers_step_batch.html, transfers_step_dest.html, sale_name_field.html, app/__init__.py |
| Task 2: add regression tests | `e574a00` | test_mobile_corrections.py, test_mobile_transfers.py |

## Verification

Task 1 gate — `uv run pytest tests/test_mobile_corrections.py tests/test_mobile_transfers.py tests/test_mobile_sales.py tests/test_sales.py -q`:
```
139 passed, 1 warning in 53.65s
```

Full suite gate — `uv run pytest tests/ -q --junitxml=reports/quick-260813-ezt.xml`:
```
FAILED tests/test_sync_ui.py::test_sync_run_returns_oob_partial - assert 'Син...
FAILED tests/test_sync_ui.py::test_offline_run_returns_200_ru - assert 'Нет с...
FAILED tests/test_sync_ui.py::test_not_configured_run_is_a_noop - assert 'Син...
FAILED tests/test_sync_ui.py::test_lock_hit_returns_locked_partial - assert F...
4 failed, 1241 passed, 13 skipped, 3 warnings in 400.75s (0:06:40)
```

The 4 failures are the documented pre-existing `tests/test_sync_ui.py` condition (`sync_client._run_lock` held by the lifespan auto-sync thread across full-suite ordering — see project memory `preexisting-sync-ui-test-failures`), unrelated to this change. Confirmed unrelated by running `tests/test_sync_ui.py` in isolation (only 2 failed there — the failure set is timing/ordering-dependent, not deterministic content related to hx-vals/templates) and by inspection: none of the failing assertions touch templates, hx-vals, or any file this plan modified.

Targeted new-test run — `uv run pytest tests/test_mobile_corrections.py tests/test_mobile_transfers.py -q -k "hx_vals"`:
```
3 passed, 34 deselected, 1 warning in 2.43s
```

## Deviations from Plan

None — plan executed exactly as written. The tojson alphabetical key-ordering assumption in the plan's test assertions (`batch_id` before `code`, `code` before `name`) was confirmed correct by the passing test run — no adjustment needed.

## Known Stubs

None.

## Threat Flags

None — this is a delimiter-only fix (double quote to single quote) on existing hx-vals attributes; no new network endpoints, auth paths, file access patterns, or schema changes. Per the plan's threat model, T-quick-260813-01 (mitigate) is closed by the fix itself; T-quick-260813-02 (accept, information disclosure) required no code change since the same values were already rendered elsewhere on each page.

## Self-Check

- FOUND: app/templates/mobile_partials/batch_card_picker.html
- FOUND: app/templates/mobile_partials/transfers_step_batch.html
- FOUND: app/templates/mobile_partials/transfers_step_dest.html
- FOUND: app/templates/partials/sale_name_field.html
- FOUND: app/__init__.py (`__version__ = "1.29"`)
- FOUND: tests/test_mobile_corrections.py (new test present)
- FOUND: tests/test_mobile_transfers.py (two new tests present)
- FOUND commit 599b895 in git log
- FOUND commit e574a00 in git log

## Self-Check: PASSED
