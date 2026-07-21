---
quick_id: 260721-doa
type: execute
one_liner: "Added a discoverable «Пользователи» link on /settings pointing to /settings/users"
key_files:
  modified:
    - app/templates/pages/settings.html
    - tests/test_settings.py
metrics:
  duration: ~5min
  tasks_completed: 1
  files_changed: 2
completed: 2026-07-21
---

# Quick Task 260721-doa: Add Users Link to Settings Page Summary

## What Was Done

The `/settings/users` route and page already existed (shipped in Phase 25, USER-01..04) and were gated behind `require_role("administrator")`, but no link to them was ever added to the main `/settings` page — an administrator had no way to discover user management from the UI nav.

Added a new `.field` block in `app/templates/pages/settings.html`, placed after the existing "Устройства" field block and before the "Синхронизация" `<h2>`, containing:

```html
<div class="field">
  <a class="button" href="/settings/users">Пользователи</a>
</div>
```

This matches the existing button-link pattern used for Склады/Резервные копии/Устройства (no extra caption paragraph, consistent with the "Экспорт кассы" block).

## Test Changes

The plan suggested `tests/test_users.py` but I checked `tests/test_settings.py` first per the plan's own guidance — it already owns `GET /settings` coverage (`test_web_settings_page_renders`), so I extended that existing test's assertions rather than adding a new test file/duplicate coverage:

```python
assert 'href="/settings/users"' in response.text
assert "Пользователи" in response.text
```

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written, with the file-location judgment call explicitly delegated to me by the plan text ("check test_settings.py first, use whichever file already covers GET /settings").

## Verification

```
uv run pytest tests/test_users.py tests/test_settings.py -q
```

Result: **26 passed**, 1 unrelated deprecation warning (httpx/starlette testclient), no regressions.

## Commits

- `1c56366` — feat(quick-260721-doa): add Пользователи link to /settings

## Self-Check: PASSED

- FOUND: app/templates/pages/settings.html (link present)
- FOUND: tests/test_settings.py (assertions present)
- FOUND: commit 1c56366 in git log
