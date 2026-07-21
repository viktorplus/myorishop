---
quick_id: 260721-egc
type: execute
autonomous: true
files_modified:
  - app/routes/__init__.py
  - app/templates/base.html
  - app/static/style.css
  - tests/test_sync_ui.py
must_haves:
  truths:
    - "On an instance whose sync_server_url is empty (the central-server role, or any client that has never been paired), the header no longer shows the «Синхронизировать» trigger, the sync-inflight indicator, or the #sync-status/#sync-badge spans — that widget is meaningless there (this instance is never itself a sync CLIENT)."
    - "On an instance whose sync_server_url IS set (a paired client, e.g. the local Windows install), the header still shows the full sync trigger + status exactly as before — zero behavior change for the normal client role."
    - "An instance whose database_url resolves to PostgreSQL (the deployed central server, per SRV-01/SRV-02) renders its top <nav> with a visually distinct style (a dark server-mode background) so an operator can tell at a glance whether they are looking at the server or a local SQLite client; a SQLite-backed instance (every local client, incl. the test suite) renders the nav exactly as before (unchanged default style)."
  artifacts:
    - path: "app/routes/__init__.py"
      provides: "_sync_status_context exposes sync_configured (bool(sync_server_url)) and is_server_db (database_url startswith postgresql) to every template"
    - path: "app/templates/base.html"
      provides: "The sync trigger/indicator/status block is wrapped in {% if sync_configured %}; <nav> carries a conditional server-mode class"
    - path: "app/static/style.css"
      provides: "nav.server-mode rule (dark background + light text) distinct from the default nav style"
---

<objective>
Two related header/nav UX fixes surfaced live while testing sync against the deployed server (ori.viktorplus.com, PostgreSQL) from the local Windows client (SQLite):

1. The header's «Синхронизировать» button + status line (`partials/sync_status.html`, wired in `base.html`) is shown unconditionally to every logged-in user on every instance. On the central server itself, `sync_server_url` is (correctly, per SRV-03) never configured — the server is never a sync CLIENT of anything — so the button always renders "Синхронизация не настроена" / "Ещё не синхронизировано" forever, which reads as broken/confusing to an admin who is actually looking at the server's own dashboard. The fix is to only show this widget when `sync_server_url` is actually set (i.e. this instance is paired as a client).

2. There is currently no visual way to tell, at a glance, whether the page in front of you is the deployed central server (ori.viktorplus.com) or a local client (127.0.0.1:8000) — both render identically. Per `deploy/DEPLOY.s1.md` / `app/db.py` (SRV-01/SRV-02), the server is the ONLY role that ever runs on `DATABASE_URL=postgresql+psycopg://...`; every local client defaults to SQLite (`settings.database_url` starts with `sqlite:///`). This is an existing, always-true architectural signal — use it to give the top `<nav>` a distinct look (dark background) ONLY when the resolved dialect is PostgreSQL, so operators can never mistake one instance for the other.

Output: the header sync widget only appears on paired sync clients; the top nav is visually distinct (dark) on the PostgreSQL-backed server instance and unchanged everywhere else.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@app/routes/__init__.py
@app/templates/base.html
@app/static/style.css
@app/config.py
@app/db.py
@tests/test_sync_ui.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Hide the header sync widget when sync_server_url is not configured</name>
  <files>app/routes/__init__.py, app/templates/base.html, tests/test_sync_ui.py</files>
  <action>
In app/routes/__init__.py, `_sync_status_context` (around line 40) currently returns a dict with `sync_message`/`last_sync_line`/`unsynced` in both the success path and the `except Exception` fallback. Add a fourth key `"sync_configured": bool(_config_settings.sync_server_url)` to BOTH return dicts (the success path's `return {...}` and the `except Exception` fallback's `return {...}`) — `_config_settings` is already imported/used in this function (see the `format_sync_message(..., _config_settings.display_tz)` call). This makes `sync_configured` available on every template render (mirrors how `sync_message`/`last_sync_line`/`unsynced` already are), true only when the instance has a non-empty `sync_server_url`.

In app/templates/base.html, wrap the existing block from the `<a hx-post="/sync/run" ...>Синхронизировать</a>` line through the `{% include "partials/sync_status.html" %}` line (currently inside the `{% if current_user %}` block, all three: the trigger `<a>`, the `#sync-inflight` `<span>`, and the sync_status include) in an additional `{% if sync_configured %}...{% endif %}` — nest it INSIDE the existing `{% if current_user %}` (so it stays "logged-in users only" AND "only when this instance is a configured sync client"). Leave the surrounding logout link and everything else in that nav block untouched.

Add a test to tests/test_sync_ui.py (near `test_header_shows_sync_trigger_and_status`) named `test_header_hides_sync_trigger_when_not_configured`: using the same `client`/`_ctx_session` fixtures as the existing header test, `monkeypatch.setattr(settings, "sync_server_url", "")` before the request (mirrors the pattern already used in `test_not_configured_run_is_a_noop`), GET a logged-in page, and assert `"Синхронизировать"` is NOT in the response text and `'id="sync-status"'` is NOT in the response text. Also update/verify the existing `test_header_shows_sync_trigger_and_status` still passes as-is IF its fixture already sets a non-empty `sync_server_url` (check the `_ctx_session` fixture / any autouse fixture in tests/test_sync_ui.py — if `sync_server_url` is empty by default in tests, that existing test will need `monkeypatch.setattr(settings, "sync_server_url", "http://sync")` added so it keeps asserting the "shown" case correctly now that visibility is conditional; inspect the file first to see whether this is already the case via the `_ctx_session` fixture at line ~62 which already does exactly this monkeypatch).
  </action>
  <verify>
    <automated>uv run pytest tests/test_sync_ui.py -q</automated>
  </verify>
  <done>The sync trigger/status widget only renders when sync_server_url is non-empty; new test passes; existing tests/test_sync_ui.py suite has zero regressions.</done>
</task>

<task type="auto">
  <name>Task 2: Visually distinguish the PostgreSQL-backed server instance's nav</name>
  <files>app/routes/__init__.py, app/templates/base.html, app/static/style.css, tests/test_sync_ui.py</files>
  <action>
In app/routes/__init__.py, add `"is_server_db": _config_settings.database_url.startswith("postgresql")` to the SAME two `_sync_status_context` return dicts touched in Task 1 (success path + exception fallback — in the fallback it must still be computed from `_config_settings.database_url` directly, not skipped, since that read never touches the DB and cannot itself raise the exception this fallback guards against; keep it OUTSIDE the `try` body's DB-dependent lines by computing it once at the top of the function if simpler, then reusing the same value in both returns).

In app/templates/base.html, add `{% if is_server_db %} class="server-mode"{% endif %}` to the existing `<nav>` opening tag (the one at the top of base.html containing the Главная/Товары/Продажи/... links) — do not otherwise change the nav's structure or existing links.

In app/static/style.css, add a new rule immediately after the existing `nav { ... }` block (around line 28):
```css
/* Server-mode indicator (SRV-01/02): the PostgreSQL-backed central server gets
   a visually distinct dark nav so it can never be mistaken for a local SQLite
   client — both render this same base.html otherwise. */
nav.server-mode {
  background: #1e293b;
  border-bottom-color: #0f172a;
}

nav.server-mode a {
  color: #e2e8f0;
}

nav.server-mode a.active {
  color: #ffffff;
}
```
Do not modify the existing plain `nav { ... }` / `nav a { ... }` / `nav a.active { ... }` rules — this is an additive override that only applies when `.server-mode` is present.

Add a test to tests/test_sync_ui.py named `test_nav_server_mode_on_postgres_db_url`: `monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://u:p@host/db")`, GET a logged-in page, assert `'class="server-mode"'` appears in the response text. Add a companion `test_nav_default_mode_on_sqlite_db_url` asserting the class is ABSENT when `database_url` is left at its sqlite default (the normal test-suite condition — this should pass with no monkeypatch needed, confirming the default/unconfigured case stays unchanged).
  </action>
  <verify>
    <automated>uv run pytest tests/test_sync_ui.py -q</automated>
  </verify>
  <done>nav carries class="server-mode" only when database_url starts with postgresql; new tests pass; full tests/test_sync_ui.py suite passes with no regressions.</done>
</task>

</tasks>

<threat_model>
## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-260721-02 | Information Disclosure | `is_server_db` / `sync_configured` booleans rendered as a CSS class / conditional block | accept | Both are derived from server-side config already known to any user who can view page source (the nav links themselves differ by role already); neither leaks the DB URL, host, or token — only a boolean presence/absence of a class name. |
</threat_model>

<verification>
- `uv run pytest tests/test_sync_ui.py -q` passes (all existing + 4 new tests).
- Manual spot check: on the local client (SQLite, sync_server_url set) the header keeps showing «Синхронизировать» and the nav stays the default light style. On the deployed server (PostgreSQL, sync_server_url unset) the sync widget disappears from the header and the nav renders with the dark server-mode background.
</verification>

<success_criteria>
- The header sync widget is only visible on instances actually configured as a sync client.
- The nav is visually distinct (dark) on the PostgreSQL-backed server instance only.
- No other page behavior changes; SQLite-backed local clients are pixel-identical to before this change.
</success_criteria>

<output>
Create `.planning/quick/260721-egc-hide-header-sync-button-status-when-this/260721-egc-SUMMARY.md` when done
</output>
