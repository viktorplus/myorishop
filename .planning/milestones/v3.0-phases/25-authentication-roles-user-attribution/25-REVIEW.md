---
phase: 25-authentication-roles-user-attribution
reviewed: 2026-07-18T00:00:00Z
depth: standard
files_reviewed: 34
files_reviewed_list:
  - app/config.py
  - app/device_id.py
  - app/models.py
  - alembic/versions/0017_users_and_author_id.py
  - app/main.py
  - app/routes/__init__.py
  - app/routes/auth.py
  - app/routes/history.py
  - app/routes/reports.py
  - app/routes/users.py
  - app/services/auth.py
  - app/services/finance.py
  - app/services/ledger.py
  - app/services/operations.py
  - app/services/reports.py
  - app/services/security.py
  - app/services/users.py
  - app/templates/auth_base.html
  - app/templates/base.html
  - app/templates/mobile_base.html
  - app/templates/pages/login.html
  - app/templates/pages/setup.html
  - app/templates/pages/users.html
  - app/templates/partials/history_rows.html
  - app/templates/partials/sales_report_results.html
  - app/templates/partials/user_reset.html
  - app/templates/partials/user_rows.html
  - tests/conftest.py
  - tests/test_attribution.py
  - tests/test_auth.py
  - tests/test_nav.py
  - tests/test_roles.py
  - tests/test_smoke.py
  - tests/test_users.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 25: Code Review Report

**Reviewed:** 2026-07-18
**Depth:** standard
**Files Reviewed:** 34
**Status:** issues_found

## Summary

This is a carefully built authentication / authorization / attribution slice. The
security-critical mechanisms are, for the most part, correctly implemented and
independently proven by the test suite:

- **Password hashing** uses `argon2-cffi`'s Argon2id defaults, salts per call,
  rehashes-on-verify, and `verify_password` never raises on a malformed/empty
  hash (`app/services/auth.py`). Verified by `tests/test_auth.py`.
- **Authorization** is a genuine server-side boundary: a single app-level
  `Depends(auth_guard)` (deny-by-default) plus `require_role("administrator")`
  on the four admin routers, read from `request.state.user` — not menu-hiding.
  `tests/test_roles.py` proves an operator gets 403 (with a *valid* CSRF token,
  so the 403 is the role gate, not the CSRF gate).
- **CSRF** is a synchronizer token in the signed session, compared with
  `hmac.compare_digest`, enforced on every unsafe method.
- **Attribution** is server-derived from a `ContextVar` (never client input),
  and the risky contextvars→threadpool hop is proven end-to-end in
  `tests/test_attribution.py`.
- **NULL-author tolerance** on history/report joins is correct (LEFT OUTER JOIN;
  pre-auth rows keep `created_by` and are never dropped from the unfiltered view).
- CLAUDE.md constraints are respected: integer-cents money, portable ORM, the
  append-only ledger is never UPDATE/DELETE'd (attribution columns are
  INSERT-time only, migration uses native `add_column`), UTC ISO timestamps, and
  no password/hash/secret is logged.

No blockers were found. The findings below are a login timing side-channel that
the code claims (in a comment) to have closed but has not, an authorization-scoping
question on the financial report, and one unhandled-error/robustness gap, plus
three minor items.

## Warnings

### WR-01: Login timing side-channel still leaks user existence (enumeration oracle claimed closed but open)

**File:** `app/routes/auth.py:59-63`
**Issue:** `login_submit` short-circuits when the login is unknown:

```python
user = session.scalar(select(User).where(User.login == login))
if user is not None and verify_password(session, user, password):
    ...
```

When `user is None` the expensive Argon2id verification is **skipped entirely**,
so the response returns almost immediately. When the login exists but the
password is wrong, a full Argon2id verify runs (deliberately ~100 ms+). The
inline comment asserts "no enumeration oracle" and the *message* oracle is indeed
closed (unknown login and wrong password share one message), but the **timing**
oracle is wide open and trivially measurable — an attacker can distinguish
"login exists" from "login does not exist" from response latency alone. Real-world
risk is low here (localhost, single offline operator), but the code documents a
guarantee it does not provide.

**Fix:** Always perform a constant-cost verification, even when the user is
missing, by verifying against a throwaway hash:

```python
from argon2 import PasswordHasher
_DUMMY_HASH = PasswordHasher().hash("timing-equalizer")

def login_submit(...):
    login = login.strip()
    user = session.scalar(select(User).where(User.login == login))
    if user is None:
        verify_password_raw(_DUMMY_HASH, password)  # burn the same time, ignore result
        # fall through to BAD_CREDENTIALS_ERROR
    elif verify_password(session, user, password):
        ...
```

(Expose a hash-only `verify_password_raw(stored_hash, raw)` in `auth.py` so the
dummy path does not need a `User`/`session`.)

### WR-02: `/finance/report` (whole-business financial report) is operator-accessible server-side while the nav files it under the admin «Настройки» menu

**File:** `app/main.py:131` (finance router registration) and `app/templates/base.html:44,49`
**Issue:** `app.include_router(finance.router)` is registered with **no**
`require_role` dependency, so `GET /finance/report` (period cash-flow / profit
report, `app/routes/finance.py:299`) is reachable by any authenticated operator.
Yet `base.html` visually groups it under the admin-only «Настройки» section: the
«Финансы» link is de-activated for `/finance/report` (`:44`) and the «Настройки»
link is activated for it (`:49`), and «Настройки» itself is hidden from operators
(`:48`). An operator has no menu path to the report but can reach it by typing the
URL. The `main.py` ROLE-03 comment says only four sections are admin-only (which
would make this intentional), but an adversarial reading flags that a
whole-business financial/profit report is exposed to a role the UI treats as
lower-privilege. This is exactly the "nav-hiding is not authorization" class of gap.

**Fix:** Confirm the intended visibility of `/finance/report`. If it is meant to
be admin-only (as the nav grouping implies), gate the finance report routes
server-side — either split the report endpoints into their own router behind
`require_role("administrator")`, or add a route-level
`dependencies=[Depends(require_role("administrator"))]` on
`finance_report_page` / `finance_report_csv`. If it is genuinely operator-visible,
adjust the nav so it does not appear to live under «Настройки».

### WR-03: `create_user` unique-login check is SELECT-then-INSERT with no `IntegrityError` handling → user-facing 500 on the race

**File:** `app/services/users.py:76,86-96`
**Issue:** Login uniqueness is enforced with a pre-check
(`select(User).where(User.login == login)`) and then a plain
`session.add(user); session.commit()`. The DB `uq_users_login` constraint is the
real backstop (so data integrity is safe), but a duplicate that slips past the
pre-check (two admins creating the same login, or any double-submit that evades
the client-side `hx-disabled-elt`) raises an **unhandled** `IntegrityError`,
surfacing as a raw 500. Contrast `setup_submit` (`app/routes/auth.py:108`) and
`finance.record_manual_movement` (`app/services/finance.py:156-166`), which both
explicitly guard their write races.

**Fix:** Wrap the commit and convert the constraint violation into the same
validation error the pre-check returns:

```python
from sqlalchemy.exc import IntegrityError
...
session.add(user)
try:
    session.commit()
except IntegrityError:
    session.rollback()
    return None, {"login": LOGIN_TAKEN_ERROR}
return user, {}
```

## Info

### IN-01: `/logout` is CSRF-exempt (listed in `PUBLIC_PATHS`), allowing cross-site forced logout

**File:** `app/services/security.py:37,135-136,144-145`
**Issue:** `/logout` is a public path, so the guard early-returns before the
unsafe-method CSRF check. `POST /logout` therefore accepts a request with no
valid token, so a cross-site page can force-log-out a victim. Impact is limited
to annoyance (no data loss). Making logout public is defensible (a deactivated /
expired user can still clear their cookie), but the CSRF exemption is an
avoidable weakness.
**Fix:** Keep `/logout` reachable but still validate CSRF for it, e.g. handle
logout inside the guarded surface, or special-case `require_csrf` for `/logout`
while leaving `/login` and `/setup` exempt.

### IN-02: `user_reactivate` always returns HTTP 200, even when nothing was reactivated

**File:** `app/routes/users.py:96-104`
**Issue:** `reactivate_user` returns `False` for an unknown/already-active id, and
the route then renders the table with `notice=None` under a 200. Sibling
mutations (`deactivate`, `reset-password`) return 422 with an error on failure.
This is a minor UX/consistency gap, not a security issue (the row set is
re-rendered correctly either way).
**Fix:** Optionally return 422 with a "Пользователь не найден." error when
`reactivate_user` returns `False`, mirroring `deactivate`.

### IN-03: `verify_password` rehash commits a new hash even for accounts that login then refuses (deactivated)

**File:** `app/services/auth.py:49-51` combined with `app/routes/auth.py:63-70`
**Issue:** `login_submit` calls `verify_password` (which commits a rehash on a
successful verify) **before** checking `is_active`. A deactivated user supplying
the correct password triggers a hash upgrade + `session.commit()` even though the
login is then rejected. Harmless (the row is legitimately theirs and stays
deactivated), but it is a small side effect on a rejected login path.
**Fix:** Optional — check `is_active` before `verify_password`, or accept the
current ordering (which is deliberate to avoid a deactivation status oracle).

---

_Reviewed: 2026-07-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
