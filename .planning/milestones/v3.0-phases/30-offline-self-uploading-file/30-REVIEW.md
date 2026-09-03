---
phase: 30-offline-self-uploading-file
reviewed: 2026-07-20T16:03:07Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - app/main.py
  - app/routes/export.py
  - app/routes/offline.py
  - app/services/merge.py
  - app/services/offline.py
  - app/services/security.py
  - app/services/sync_client.py
  - app/templates/offline/result.html
  - app/templates/offline/self_upload.html
  - app/templates/pages/export.html
  - tests/test_merge.py
  - tests/test_offline.py
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues_found
---

# Phase 30: Code Review Report

**Reviewed:** 2026-07-20T16:03:07Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 30 adds an untrusted-file ingest path: a self-contained HTML export that logs
in, previews, and self-uploads an NDJSON bundle to the server. The security spine is
largely sound: the `/api/offline/` auth-guard bypass is an exact-prefix match
(`security.py:65,184`) that correctly leaves the session-guarded `/offline/export`
outside it; the CORS `Access-Control-Allow-Origin` header is scoped to the login
responses only (`offline.py:66`) and never applied app-wide or to `/upload`; the
itsdangerous token carries a dedicated salt + scope claim + short TTL and is verified
with the serializer's own HMAC-timed check (`offline.py:47-58`); the SHA-256 integrity
gate and the schema-version gate both run BEFORE any DB write in `offline_upload`
(`offline.py:191-232`); and the export route never stamps `synced_at` (D-07 holds:
`offline.py:110-111`, `collect_push_records` is read-only).

However, the single most security-critical line of the phase, neutralizing the
`</script>` HTML-parser breakout before embedding untrusted NDJSON into the
self-uploading file, is **case-sensitive** and bypassable, which is a script-injection
BLOCKER. Two further correctness/robustness defects (Unicode line-boundary
over-splitting in the digest round-trip, and an un-graceful 500 on a parseable-but-
poisoned batch) and low-severity items round out the findings.

## Critical Issues

### CR-01: `</script>` breakout neutralization is case-sensitive → HTML/script injection

**File:** `app/routes/offline.py:124` (paired with `app/templates/offline/self_upload.html:114`)
**Issue:**
The export embeds attacker-influenced NDJSON (product names, customer names, notes, etc.)
into a raw-text `<script type="application/x-ndjson">` block rendered with `{{ embedded | safe }}`,
so Jinja2 autoescaping is disabled and the ONLY protection is this manual replace:

```python
embedded = body.replace("</script", "<\\/script")
```

HTML end-tag matching for a `script` raw-text element is **case-insensitive**: the parser
ends the element at `</script`, `</SCRIPT`, `</Script`, etc. (followed by whitespace, `/`,
or `>`). The replace only rewrites the exact lowercase byte sequence `</script`, so a record
field containing `</SCRIPT>` or `</Script>` (unchanged by `json.dumps(ensure_ascii=False)`)
passes through verbatim, closes the script block early, and the remainder is parsed as live
HTML. On the self-upload page that executes in the same document where the operator types
their login + password, i.e. credential theft / arbitrary DOM injection. In the v3
multi-operator model such a field can arrive from another device via sync and then be
exported, so it is not purely self-inflicted. The round-trip test (`test_offline.py:511`)
only exercises the lowercase `</script>` case, so the gap is untested.

**Fix:** Make the neutralization case-insensitive (and reverse it identically in the JS at
`self_upload.html:150`):

```python
import re
# Escape any case variant of the raw-text end-tag prefix.
embedded = re.sub(r"</script", lambda m: "<\\/" + m.group(0)[2:], body, flags=re.IGNORECASE)
```

A simpler, equally safe alternative is to escape every `<` (`body.replace("<", "\\u003c")`)
and reverse `<` back to `<` in the browser before parsing, with no case edge cases at all.
Add a regression test with a mixed-case `</SCRIPT>` payload.

## Warnings

### WR-01: `payload.splitlines()` over-splits on Unicode line boundaries → false "corrupted" rejection

**File:** `app/routes/offline.py:204` (and the digest contract in `app/services/merge.py:528-539`)
**Issue:**
The route canonicalizes newlines with `payload.splitlines()` and the comment claims it
"strips CRLF and LF alike". But `str.splitlines()` also splits on `\v`, `\f`, `\x1c`, `\x1d`,
`\x1e`, `\x85`, and, critically, U+2028 (LINE SEPARATOR) / U+2029 (PARAGRAPH SEPARATOR).
`json.dumps(..., ensure_ascii=False)` (used by `serialize_exchange`, `merge.py:565`) does
**not** escape U+2028/U+2029, so a record field containing one of those characters is emitted
as a raw byte inside its JSON line. On the server, `splitlines()` then splits that single
record into two "lines", which both corrupts the SHA-256 recomputation (`payload_digest`
re-joins with `\n`, dropping the original separator) and breaks `parse_exchange`. Result: a
legitimate bundle containing such a character is permanently un-uploadable (always lands on
the "Файл повреждён" page), with no way for the operator to recover it.

**Fix:** Split only on the newline styles the digest contract actually promises, e.g.
`lines = payload.replace("\r\n", "\n").replace("\r", "\n").split("\n")`, and update both the
route comment and `payload_digest`'s docstring. Alternatively, have `serialize_exchange` emit
`ensure_ascii=True` (or explicitly escape U+2028/U+2029) so no exotic line char ever reaches
the wire.

### WR-02: parseable-but-poisoned batch raises IntegrityError out of the route → HTTP 500, not the documented RU result page

**File:** `app/routes/offline.py:246-248`
**Issue:**
The module docstring (`offline.py:19-22`) and the `offline_upload` docstring
(`offline.py:188-189`) both state "Every rejection lands on a fixed RU result page". A record
that passes the integrity + schema + `parse_exchange` gates but references a missing FK parent
raises `IntegrityError` from `apply_merge`, which is deliberately not caught
(`with session.begin(): apply_merge(...)`). The exception propagates to FastAPI and the operator
receives a bare HTTP 500, not the "Файл повреждён" page, contradicting the stated contract and
giving a confusing dead-end on the untrusted internet PC. `test_upload_all_or_nothing`
(`test_offline.py:249`) asserts the raise propagates, so this is intentional for roll-back proof,
but the UX/contract mismatch remains.

**Fix:** Wrap the merge in a targeted handler that still guarantees rollback but renders the
result page, e.g.:

```python
from sqlalchemy.exc import IntegrityError
session.rollback()
try:
    with session.begin():
        report = apply_merge(session, batch, server_now=utcnow_iso())
except IntegrityError:
    session.rollback()
    return _result(request, "corrupted", status=422)
```

(and adjust the all-or-nothing test to assert the 4xx result page + zero rows instead of a raw raise).

### WR-03: upload token is accepted after the user is deactivated

**File:** `app/routes/offline.py:191-193`, `app/services/offline.py:47-58`
**Issue:**
`verify_offline_token` validates the signature, TTL, and scope but the route ignores the returned
`sub` claim, i.e. it never re-checks that the user still exists and `is_active == 1`. A token minted
just before an admin deactivates/deletes the account remains usable for the full `OFFLINE_TOKEN_TTL`
(300s) window to ingest data. Blast radius is small (single-operator, 5-minute window, server-wins
merge), but it diverges from the login gate which does enforce `is_active` (`offline.py:162-166`).

**Fix:** In `offline_upload`, use the claim to revalidate the user before merging:

```python
claim = offline_service.verify_offline_token(token)  # already called in the try
user = session.get(User, claim.get("sub"))
if user is None or user.is_active != 1:
    return _result(request, "expired", status=401)
```

## Info

### IN-01: dead `wrong_password` state in the result template

**File:** `app/templates/offline/result.html:20-22`
**Issue:** `result.html` renders a `wrong_password` branch, but login is a separate JSON endpoint
(`/api/offline/login`) that never renders this template; no route ever passes `state="wrong_password"`.
Dead branch.
**Fix:** Remove the unused branch, or add a comment noting it is reserved, to avoid implying a code path
that cannot occur.

### IN-02: login timing side-channel for user existence

**File:** `app/routes/offline.py:161-169`
**Issue:** The guard `user is None or not verify_password(...) or user.is_active != 1` short-circuits, so
an unknown login skips the (deliberately slow) password hash entirely. The response body is a single
generic message (good), but the response *time* differs measurably between an unknown login and a known
one with a wrong password, a mild enumeration oracle, despite the "no enumeration oracle" comment.
**Fix:** Perform a dummy `verify_password` against a constant hash when the user is missing to equalize
timing, or accept the risk explicitly (rate limiting already blunts bulk probing).

### IN-03: JS shows "wrong password" for any non-200/429 login response

**File:** `app/templates/offline/self_upload.html:199-203`
**Issue:** The client-side `else` branch maps every non-200, non-429 status (including a 500 server
error) to "Неверный логин или пароль", which can mislead the operator during a genuine server fault.
**Fix:** Add a branch for `resp.status >= 500` that shows a generic "server error, try later" message,
distinct from the credential error.

---

_Reviewed: 2026-07-20T16:03:07Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
