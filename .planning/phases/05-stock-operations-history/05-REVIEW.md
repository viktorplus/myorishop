---
phase: 05-stock-operations-history
reviewed: 2026-07-10T00:00:00Z
depth: standard
files_reviewed: 34
files_reviewed_list:
  - app/main.py
  - app/models.py
  - app/routes/__init__.py
  - app/routes/corrections.py
  - app/routes/history.py
  - app/routes/returns.py
  - app/routes/writeoffs.py
  - app/services/corrections.py
  - app/services/operations.py
  - app/services/returns.py
  - app/services/writeoffs.py
  - app/static/style.css
  - app/templates/base.html
  - app/templates/pages/correction_form.html
  - app/templates/pages/history.html
  - app/templates/pages/home.html
  - app/templates/pages/writeoff_form.html
  - app/templates/partials/correction_form.html
  - app/templates/partials/correction_lookup.html
  - app/templates/partials/history_filters.html
  - app/templates/partials/history_rows.html
  - app/templates/partials/purchase_history.html
  - app/templates/partials/recent_sales.html
  - app/templates/partials/return_form.html
  - app/templates/partials/writeoff_form.html
  - app/templates/partials/writeoff_lookup.html
  - app/templates/partials/writeoff_oversell.html
  - app/templates/partials/writeoff_rows.html
  - tests/test_corrections.py
  - tests/test_history.py
  - tests/test_ledger.py
  - tests/test_returns.py
  - tests/test_smoke.py
  - tests/test_writeoffs.py
findings:
  critical: 1
  warning: 4
  info: 7
  total: 12
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-07-10
**Depth:** standard
**Files Reviewed:** 34
**Status:** issues_found

## Summary

This is a re-review of Phase 5 (write-off / sale-linked return / stock
correction / `/history` ledger browser) after two gap-closure plans:

- **05-06** (nav-link fix) — verified **CLOSED**: `base.html`'s nav bar and
  `home.html` both now link to `/writeoff` (confirmed by grep + the new
  `test_web_writeoff_reachable_from_nav` test, and by direct read of both
  templates in this pass). The previous **CR-01** is resolved.
- **05-07** (session rollback + 422 status fix) — verified **CLOSED**:
  `GET /returns`'s origin-not-found branch now returns `status_code=422`
  (htmx-swappable per `base.html`'s `responseHandling` allow-list, not the
  previously-used `404` which was silently discarded), and all three write
  routes' bare `except Exception:` handlers (`corrections.py`,
  `returns.py`, `writeoffs.py`) now call `session.rollback()` before any
  further session use. The previous **CR-02**, **CR-03**, and **WR-03** are
  resolved. Full suite (165 tests) passes; the two new regression tests in
  `tests/test_returns.py` genuinely exercise both fixes.
- **WR-01** (history "Показать ещё" pagination control gets stranded after
  the first click) was explicitly deferred, not fixed — confirmed still
  present in `partials/history_rows.html` and carried forward below.

While re-reading the ledger/history code end-to-end for this pass, a new,
more serious defect surfaced that the previous review missed and that the
existing test suite does not catch (because `TestClient` only asserts on
response text, never on how a real browser parses that text): **a plain,
non-htmx navigation to a filtered `/history` URL — exactly what happens on
page reload, bookmark, or share of a link that `hx-push-url` just wrote
into the address bar — returns a bare `<tr>` fragment with no `<table>`,
`<tbody>`, `<html>`, or nav chrome at all.** Verified empirically against
the running app (see CR-01 below); per the HTML5 parsing algorithm a stray
`<tr>` outside a table context is a parse error and the token is dropped,
so the operator would see a blank page with no way to navigate back except
editing the URL by hand.

Several lower-severity robustness/consistency gaps (some carried over from
the previous review, some newly found) are listed under Warnings/Info.

## Critical Issues

### CR-01: Reloading/bookmarking a filtered `/history` URL renders a broken, chrome-less page

**File:** `app/routes/history.py:32-45`, `app/templates/partials/history_rows.html`
**Issue:** `history_page` decides between the full page and the rows-only
partial using `is_hx or is_filtered`, where `is_filtered = bool(type) or
bool(product)`. The intent (per the code comment) is that a plain,
non-htmx GET carrying filter params — e.g. the browser reloading a URL
that `hx-push-url="true"` just wrote to the address bar — should *still*
get the rows-only partial, to avoid "leaking" the full `<select>`'s
unselected option text. That reasoning doesn't hold: a `<select>` always
renders every `<option>` in its markup regardless of which one is
`selected` — that is normal, expected dropdown behaviour, not a leak. The
actual effect of the current code is that a real top-level browser
navigation to `/history?type=writeoff` (no `HX-Request` header) receives a
response containing only bare `<tr>` elements with no enclosing `<table>`/
`<tbody>`, no `<html>`/`<head>`/`<body>`, and no site nav. Verified
empirically:
```
GET /history?type=writeoff (no HX-Request header)
-> 200, body: '<tr>...</tr>\n<tr id="load-more">...</tr>'
-> '<html' in body: False, '<table' in body: False, '<nav' in body: False
```
Per the HTML5 tree-construction algorithm, a `<tr>` start tag encountered
in the "in body" insertion mode (i.e. not inside a table context, which is
exactly what a bare top-level document is) is a parse error and the token
is dropped — so a real browser would render an essentially blank page,
with the operator unable to navigate anywhere in the app without manually
editing the address bar. This is reachable in ordinary use: any user who
selects a history filter (which pushes the filtered URL via `hx-push-url`)
and then reloads, bookmarks, or shares that URL hits this.
**Fix:** Drop the `is_filtered` condition from the chrome decision — only
`is_hx` (an actual htmx request) should receive the rows-only partial. A
plain top-level GET, filtered or not, should always render the full page
with the filter bar and nav, with the current filter values pre-selected
in the `<select>`s (which `history_filters.html` already supports via
`type_filter`/`product_id`):
```python
# app/routes/history.py
if is_hx:
    return templates.TemplateResponse(request, "partials/history_rows.html", context)
context["products"] = filter_products(session)
return templates.TemplateResponse(request, "pages/history.html", context)
```

## Warnings

### WR-01: `/history` "Показать ещё" control gets stuck in place after the first click (carried over, still unfixed — deferred by design)

**File:** `app/templates/partials/history_rows.html:44-52`, `app/routes/history.py`
**Issue:** The button uses `hx-target="#history-tbody" hx-swap="beforeend"`
while the response's trailing `<tr id="load-more">` is marked
`hx-swap-oob="true"`. htmx strips oob-marked elements from the response
before the main swap runs, so only the plain data rows get appended via
`beforeend` — i.e. after whatever is currently the last child of
`#history-tbody`, which is the in-place-updated (not moved) load-more row
itself. After the first click, the control is stranded above newly loaded
rows instead of below them, and every subsequent batch stacks beneath it.
Confirmed unchanged since the previous review; per `05-07-SUMMARY.md` this
was explicitly deferred, not addressed by the gap-closure plans.
**Fix:** Target the control row directly and insert new rows immediately
before it:
```html
<button ... hx-get="/history?...&page={{ page + 1 }}"
        hx-target="#load-more" hx-swap="beforebegin" hx-disabled-elt="this">Показать ещё</button>
```
(keep the oob-marked `<tr id="load-more">` in the response so it can
replace/remove itself once `has_next` becomes false).

### WR-02: `/corrections` has no persistent nav entry point, and is fully unreachable with zero products

**File:** `app/templates/base.html:17-26`, `app/templates/pages/home.html:9-13`
**Issue:** The 05-06 gap-closure plan added `/writeoff` to both the
persistent top nav (`base.html`) and the home page, but `/corrections` was
only ever wired into `home.html`'s `{% if product %}` block — it never
got a top-nav entry, even though `/history` and `/writeoff` both did. Two
consequences: (1) inconsistent discoverability — every other primary
write action (`Приход`, `Продажи`, `Списание`, `История`) is reachable
from any page via the persistent nav, but a correction requires returning
to the home page first; (2) if the shop has zero active products (a
first-run/empty-database state, or after every product is soft-deleted),
`home.html` renders the `{% else %}Нет товаров{% endif %}` branch instead,
which contains no links at all — `/corrections` becomes completely
unreachable from the rendered UI in that state (the operator would have
to type the URL from memory). The previous review's CR-01 fix commentary
explicitly flagged this as worth considering ("consider whether
`/corrections` deserves the same top-level treatment") but it was not
acted on.
**Fix:** Add the same nav-bar pattern used for `/writeoff`/`/history`:
```html
<a href="/corrections"{% if request.url.path.startswith("/corrections") %} class="active"{% endif %}>Корректировка</a>
```

### WR-03: `writeoff_rows.html` doesn't guard against a falsy/None `payload` (carried over, still unfixed)

**File:** `app/templates/partials/writeoff_rows.html:28-30`
**Issue:** `{{ WRITEOFF_REASONS.get(r.op.payload.reason_code, r.op.payload.reason_code) }}`
assumes `r.op.payload` is always a populated dict. `history_rows.html`
(line 28) defensively checks `r.op.type == "writeoff" and r.op.payload`
first; this partial does not. Every write-off written through today's
single write path always populates `payload`, so this isn't reachable
yet — but it's an inconsistent defensive posture between two templates
rendering the same op type, and any future/legacy/synced row with
`payload IS NULL` would raise a Jinja `UndefinedError` on
`None.reason_code`, taking down the entire `/writeoff` page render.
**Fix:**
```html
{% if r.op.payload %}
{{ WRITEOFF_REASONS.get(r.op.payload.reason_code, r.op.payload.reason_code) }}{% if r.op.payload.note %} — {{ r.op.payload.note }}{% endif %}
{% else %}<span class="muted">—</span>{% endif %}
```

### WR-04: `/history` product filter dropdown only lists active products (carried over, still unfixed)

**File:** `app/services/operations.py:51-57`
**Issue:** `filter_products()` filters `Product.deleted_at.is_(None)`.
Operations recorded against a product that is later soft-deleted remain
visible in the unfiltered `/history` view (correct — the ledger join has
no deleted-filter), but the operator has no way to filter down to that
product's history once it's soft-deleted, since it no longer appears as
an `<option>` in the "Товар" select.
**Fix:** Either include soft-deleted products in the filter list (e.g.
marked "Название (архив)"), or document this as a known limitation.

## Info

### IN-01: `corrections.py` "delta" mode silently reclassifies `-0` as a generic "nothing changed" error (carried over)

**File:** `app/services/corrections.py:70-83`
**Issue:** Input `"-0"` passes the delta-mode format check
(`body = "0"`, `"0".isdigit()` is `True`), producing
`qty_delta = int("-0") == 0`. It falls into the `qty_delta == 0` branch
and returns `ZERO_NET_ERROR` instead of the more specific `DELTA_QTY_ERROR`
("must be a nonzero integer"). Functionally harmless (the write is still
correctly blocked) — message precision only.
**Fix:** Not required to block ship; special-case `"-0"`/`"+0"` before the
generic zero-delta check if message precision matters.

### IN-02: `return_form.html` uses a `max` attribute on a `type="text"` input (carried over)

**File:** `app/templates/partials/return_form.html:24`
**Issue:** `<input type="text" ... max="{{ remaining }}">` — the HTML
`max` attribute has no effect on `type="text"` inputs. Server-side
validation is correctly authoritative, so this is cosmetic only.
**Fix:** Remove the dead `max` attribute, or switch to `type="number"`
with equivalent `inputmode` handling if client-side capping is desired.

### IN-03: `history.py` route parameter `type` shadows the Python builtin (carried over)

**File:** `app/routes/history.py:16`
**Issue:** `def history_page(request, type: str = "", ...)` shadows the
builtin `type()` within the function body. No current bug (the builtin
isn't needed here), but it's a readability smell that could bite a future
edit.
**Fix:** Rename to `type_`/`op_type`; keep the wire query-string key `type`
via `Query(alias="type")` if needed.

### IN-04: `return_create` duplicates the origin/validity check `register_return` already performs (carried over)

**File:** `app/routes/returns.py:104-105`, `app/services/returns.py:72-74`
**Issue:** The route independently re-derives `origin_valid` by fetching
the same `Operation` and re-checking `type == "sale" and sale_id is not
None` before calling `register_return`, which performs the identical
check internally. Not a functional bug today, but the two copies could
drift out of sync if only one is updated.
**Fix:** Have `register_return` (or a shared helper) return enough
information for the route to build its error context without
re-implementing the validity check.

### IN-05: `/corrections`'s "current stock" hint always disappears after any submit, success or failure

**File:** `app/routes/corrections.py:82-114`, `app/templates/partials/correction_form.html:63-69`
**Issue:** `#current-qty-hint` (`Текущий остаток: {{ current_qty ... }}`)
is only ever populated by the `/corrections/lookup` GET (out-of-band swap
on typing a code). Every POST response — success, validation error, or
the exception path — sets `"current_qty": None` in its context, and
`#correction-form-wrap` (which contains the hint) is swapped `outerHTML`
on every POST. So as soon as the operator submits (even a rejected
submission, e.g. a bad quantity), the "Текущий остаток: N" hint they were
just looking at reverts to "—" and can only be restored by retyping the
code to re-trigger the lookup. Purely a UX regression-of-context, not a
correctness bug (the server still validates the real quantity), but it
undermines the counted-mode hint's whole purpose on the most common path
(a rejected input immediately followed by a correction attempt).
**Fix:** On the error-retention path, re-run `lookup_prefill`'s quantity
lookup for the currently-echoed `code` and populate `current_qty` from it
instead of hardcoding `None`.

### IN-06: `corrections.py` delta mode rejects a leading `+`, contradicting its own UI label

**File:** `app/services/corrections.py:70-76`, `app/templates/partials/correction_form.html:72`
**Issue:** The delta-mode input label reads "Изменение (+ или −)"
("Change (+ or −)"), implying a leading `+` is valid input syntax for a
positive delta. The validation only special-cases a leading `-`
(`body = s[1:] if s.startswith("-") else s`); a value like `"+3"` fails
`"+3".isdigit()` (the `+` isn't stripped) and is rejected with the generic
`DELTA_QTY_ERROR`, even though the label visually invites `+` notation.
**Fix:** Either strip a leading `+` the same way `-` is stripped, or
reword the label to clarify that positive deltas are entered as a bare
number (no `+` prefix).

### IN-07: `/history`'s `page` query param accepts negative values with no validation

**File:** `app/routes/history.py:14-21`, `app/services/operations.py:14-48`
**Issue:** `page: int = 0` has no lower-bound validation. A negative
`page` (e.g. `/history?page=-1`) produces a negative `OFFSET` in the
underlying query; verified empirically that SQLite silently treats a
negative `OFFSET` as `0`, so this doesn't crash — but it silently
re-serves page 0's content under a URL that looks like it should show
something else, rather than rejecting the input. Low severity (no crash,
no data exposure), purely a missing-input-validation gap.
**Fix:** Add `page: int = Query(0, ge=0)` to reject/clamp negative values
explicitly.

---

_Reviewed: 2026-07-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
