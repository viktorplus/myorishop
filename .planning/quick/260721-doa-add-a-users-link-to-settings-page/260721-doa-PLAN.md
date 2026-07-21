---
quick_id: 260721-doa
type: execute
autonomous: true
files_modified:
  - app/templates/pages/settings.html
  - tests/test_users.py
must_haves:
  truths:
    - "The /settings page renders a «Пользователи» link pointing to /settings/users, in the same style/position group as the existing Склады/Резервные копии/Устройства links."
  artifacts:
    - path: "app/templates/pages/settings.html"
      provides: "A new .field block with a button-styled link to /settings/users, labeled «Пользователи»"
---

<objective>
The /settings/users route and page already exist (Phase 25, USER-01..04) and are gated behind `require_role("administrator")`, but no link to them was ever added to the main /settings page — an administrator has no way to discover user management from the UI nav. Add the missing link.

Output: /settings renders a "Пользователи" link/button to /settings/users, matching the existing field-block pattern used for Склады/Резервные копии/Устройства.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@app/templates/pages/settings.html
@app/routes/users.py
@app/routes/settings.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add Пользователи link to /settings</name>
  <files>app/templates/pages/settings.html, tests/test_users.py</files>
  <action>
In app/templates/pages/settings.html, add a new `<div class="field">` block containing `<a class="button" href="/settings/users">Пользователи</a>` — place it after the existing "Устройства" field block (after line 18, before the "Синхронизация" `<h2>`), matching the exact markup pattern of the other field blocks (button link, no extra description paragraph needed unless a short muted caption fits naturally — keep consistent with the "Склады"/"Экспорт кассы" blocks which have no caption for the latter).

Add or extend a test in tests/test_users.py (or wherever /settings page tests live — check test_settings.py first, use whichever file already covers GET /settings) asserting the response for GET /settings (as an authenticated administrator) contains `href="/settings/users"` and the text "Пользователи".
  </action>
  <verify>
    <automated>uv run pytest tests/test_users.py tests/test_settings.py -q</automated>
  </verify>
  <done>/settings renders a Пользователи link to /settings/users; new/updated test passes; no existing settings/users tests regress.</done>
</task>

</tasks>

<threat_model>
## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-260721-01 | Information Disclosure | New Пользователи link on /settings | accept | The link only surfaces an existing route already gated by require_role("administrator") (ROLE-03) at the router level — no new access is granted, only discoverability of an already-authorized page. |
</threat_model>

<verification>
- `uv run pytest tests/test_users.py tests/test_settings.py -q` passes.
- Manual spot check: log in as administrator, open /settings, confirm a "Пользователи" link/button is visible and navigates to /settings/users.
</verification>

<success_criteria>
- /settings page has a discoverable link to /settings/users.
- No regressions to existing settings/users routes or tests.
</success_criteria>

<output>
Create `.planning/quick/260721-doa-add-a-users-link-to-settings-page/260721-doa-SUMMARY.md` when done
</output>
