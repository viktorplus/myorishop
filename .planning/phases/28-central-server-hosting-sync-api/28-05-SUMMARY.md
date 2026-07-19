---
phase: 28-central-server-hosting-sync-api
plan: 05
subsystem: admin-ui
tags: [device-token, sync, admin-surface, show-once, revoke, htmx, role-gate]
requires: [SYNC-09, device-token-service, "28-02", "28-04"]
provides: [SYNC-09-admin-surface, /settings/devices]
affects: [app/routes/devices.py, app/main.py, app/templates, tests]
tech-stack:
  added: []
  patterns:
    - "thin route over fat service (users.py precedent): validation stays in the service"
    - "HX-Request page-vs-partial dispatch + outerHTML swap of a single #devices-table block"
    - "server-side admin gate via include_router(dependencies=[require_role]) — handlers never re-check"
    - "show-once secret: plaintext lives only in the single mint response context, never at rest"
key-files:
  created:
    - app/routes/devices.py
    - app/templates/pages/devices.html
    - app/templates/partials/device_rows.html
    - tests/test_devices_ui.py
  modified:
    - app/main.py
    - app/templates/pages/settings.html
decisions:
  - "No new design tokens or CSS classes (locked phase decision, no UI-SPEC): the page mirrors /settings/users verbatim — stacked-form, #-table outerHTML swap, danger button, empty-state muted, error/notice preamble"
  - "devices.html does NOT scope its own hx-headers wrapper (unlike the historical users.html) — base.html already carries the CSRF token on <body>"
  - "The minted plaintext travels only in the mint response context (grep-asserted: no request.session, no logging); the show-once regression test proves it is absent on reload"
metrics:
  duration: ~13min
  tasks: 3
  files: 6
  completed: 2026-07-19
---

# Phase 28 Plan 05: Device-Token Admin Surface (SYNC-09) Summary

The administrator surface for the SYNC-09 token lifecycle: `/settings/devices` lets an admin mint a device token (plaintext shown exactly once), review every token with its status and last-used time, and revoke a lost device instantly — the only mitigation for a stolen token, since there is no expiry by decision. The page reuses the `/settings/users` patterns and the Phase 25 design system verbatim: no new design tokens, no new CSS classes, no new interaction model.

## What Was Built

`app/routes/devices.py` is a thin router (three routes, all plain `def`, no `prefix=`, literal full paths) over the fat `app/services/devices.py`: `GET /settings/devices` does the `HX-Request` page-vs-partial dispatch, `POST /settings/devices` mints and re-renders the `#devices-table` partial with the plaintext + copy-now warning in the success context, and `POST /settings/devices/{token_id}/revoke` soft-disables and re-renders. Registered in `app/main.py` immediately after the users router behind `require_role("administrator")`, so handlers never re-check the role — the include_router dependency is the server-side boundary.

`app/templates/pages/devices.html` is the page shell (create form: «Название устройства» + «Идентификатор устройства», hidden `csrf_token` fallback, no scoped `hx-headers` — base.html carries it). `app/templates/partials/device_rows.html` is the single swappable `#devices-table` block, mirroring `user_rows.html`: notice/errors preamble, the `{% if new_token_plaintext %}` show-once `<code>` block with its copy-now warning, columns «Название / Устройство / Статус / Последнее использование / Действия», a `danger` revoke button with an `hx-confirm` for active tokens and nothing (never a delete control) for revoked ones. The stored digest and lookup prefix are never rendered. `settings.html` gains one `field` block linking to `/settings/devices`.

### Task-by-task

| Task | What | Commit |
|------|------|--------|
| 1 | `app/routes/devices.py` (3 admin routes, RU notice constants, `_rows_context`) + admin-gated registration in `app/main.py` | `a4b1c6d` |
| 2 | `pages/devices.html` + `partials/device_rows.html` (show-once block, revoke-only) + settings-index link | `e720f7d` |
| 3 | `tests/test_devices_ui.py` — 10 SYNC-09 admin-surface tests | `d03adfe` |

## Key Decisions

- **No new design tokens (locked phase decision).** The page is a structural clone of `/settings/users` — every class used (`stacked-form`, `field`, `form-actions`, `danger`, `empty-state muted`, `error`) already appears in the users page/partial. No UI-SPEC was authored for this phase by decision.
- **No scoped `hx-headers` on the page.** `users.html` still wraps its content in a `<div hx-headers=...>` for historical reasons (its CSRF line predates the base-chrome one). `base.html` now carries the CSRF token on `<body>`, so `devices.html` relies on that inherited header and adds only the hidden `csrf_token` field for the non-HTMX fallback.
- **Show-once is enforced at the source, not by hiding.** The plaintext is placed only into the mint response context — never into the session, a redirect, a query string, or a log line. The `test_plaintext_not_shown_on_reload` regression test extracts the exact minted string and asserts its absence from a subsequent GET.

## Deviations from Plan

None — plan executed exactly as written. No architectural changes, no checkpoints, no auth gates, no new packages.

One adjustment worth noting (not a deviation from behavior): the Jinja/HTML comments in the new templates were reworded to avoid containing the literal substrings `|safe`, `token_hash`, `token_prefix`, and `hx-headers`, because the plan's acceptance criteria assert `grep -c` returns 0 for those tokens across the whole file (comments included). The security intent of each comment is preserved.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_devices_ui.py -q` | **10 passed** |
| `uv run pytest -q` (full SQLite suite) | **1076 passed, 11 skipped** (was 1043 at 28-02) |
| `uv run ruff check app/routes/devices.py app/main.py tests/test_devices_ui.py` | clean |
| `grep -c "async def" app/routes/devices.py` | 0 |
| `grep -Ec "print\(|logging|logger" app/routes/devices.py` | 0 |
| `grep -c "request.session" app/routes/devices.py` | 0 |
| `grep -c "|safe" app/templates/partials/device_rows.html` | 0 |
| `grep -Ec "token_hash|token_prefix" app/templates/partials/device_rows.html` | 0 |
| `grep -c "hx-headers" app/templates/pages/devices.html` | 0 |
| `grep -c 'id="devices-table"' app/templates/partials/device_rows.html` | 1 |

Note: `uv run ruff check app` (whole tree) reports 2 pre-existing E501s in `app/routes/products.py:133` and `app/routes/transfers.py:64` — untouched by this plan, already logged in `deferred-items.md` (from 28-03). All files this plan created/modified are ruff-clean.

## Success Criteria

- [x] An administrator can mint, review and revoke device tokens from `/settings/devices`, reachable from the settings index
- [x] The plaintext is displayed exactly once and is provably unrecoverable afterwards (`test_plaintext_not_shown_on_reload`)
- [x] An operator is refused with 403 on every route of the surface — GET, POST create, POST revoke (`test_operator_cannot_reach_devices_page`)
- [x] The page introduces no new design tokens and no new interaction model

## Threat Model Coverage

| Threat ID | Disposition | How covered |
|-----------|-------------|-------------|
| T-28-01 (stolen token, no expiry) | mitigate | This page IS the mitigation: per-token revoke + «Последнее использование» staleness column — `test_revoke_marks_row_revoked_not_deleted`. Residual risk (manual/reactive revocation) accepted |
| T-28-24 (operator self-minting a token) | mitigate | `include_router(dependencies=[require_role("administrator")])`; `test_operator_cannot_reach_devices_page` asserts 403 on ALL THREE routes |
| T-28-07 (plaintext in session/logs/URL/later render) | mitigate | plaintext only in the mint response context (grep-asserted: no `request.session`, no logging); `test_plaintext_not_shown_on_reload` |
| T-28-25 (stored credential leaking via UI) | mitigate | templates never render the digest/prefix (grep-asserted); `test_stored_hash_never_rendered` |
| T-28-06 (CSRF on mint/revoke POSTs) | mitigate | both POSTs use the untouched auth_guard CSRF path (not under `/api/sync/`); base.html header + hidden `csrf_token` fallback |
| T-28-26 (XSS via device label) | mitigate | Jinja autoescape only; `|safe` grep-asserted 0 in the rows partial |
| T-28-18 (deleting a compromised token to destroy evidence) | mitigate | revoke-only — no delete control in either template; revoked rows stay visible |
| T-28-SC (supply chain) | accept | zero new packages, no CDN, no JS beyond vendored htmx 2.0.10 |

## Known Stubs

None.

## Threat Flags

None. This plan adds one admin surface whose full STRIDE surface is already enumerated in the plan's `<threat_model>` and covered above; it introduces no new network endpoint, auth path, or schema change beyond the already-registered device-token store.

## Self-Check: PASSED

- FOUND: `app/routes/devices.py`
- FOUND: `app/templates/pages/devices.html`
- FOUND: `app/templates/partials/device_rows.html`
- FOUND: `tests/test_devices_ui.py`
- FOUND: commit `a4b1c6d`
- FOUND: commit `e720f7d`
- FOUND: commit `d03adfe`
