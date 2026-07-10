---
phase: 05-stock-operations-history
reviewed: 2026-07-10T12:40:00Z
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
  warning: 3
  info: 8
  total: 12
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-07-10T12:40:00Z
**Depth:** standard
**Files Reviewed:** 34
**Status:** issues_found

## Summary

This is a re-review of Phase 5 (write-off / sale-linked return / stock
correction / `/history` ledger browser) after the **05-08** gap-closure plan.

- **Old CR-01** (a plain, non-htmx GET to a filtered `/history` URL — e.g. a
  browser reload of a URL `hx-push-url` just wrote — returned a bare
  chrome-less `<tr>` fragment that a real browser drops per HTML5 parsing
  rules) is now **CONFIRMED FIXED**. `app/routes/history.py:34-46` now
  branches purely on `is_hx = bool(request.headers.get("HX-Request"))`; a
  filtered top-level GET renders the full `pages/history.html` chrome with
  the filter bar pre-selecting the active filter, exactly as the previous
  review's fix suggestion specified. `tests/test_history.py`'s
  `test_web_history_filtered_reload_returns_full_chrome` exercises this.

- Everything else the previous review flagged (old WR-01 through WR-04,
  IN-01 through IN-07) is **still present, unchanged** — 05-08 only touched
  the chrome-decision logic, not any of these. They are carried forward
  below under their (renumbered) findings.

- Re-tracing the "Показать ещё" pagination control end-to-end for this pass
  surfaced that the underlying defect is **more severe than previously
  assessed**. The prior review's WR-01 described only the "Показать ещё"
  button's own `beforeend` click leaving the control visually stuck between
  row batches — filed as a deferred Warning. Tracing the *other* two
  triggers that hit the same `#history-tbody` target (the type/product
  `<select>`s in `history_filters.html`, which use htmx's **default**
  `innerHTML` swap, not `beforeend`) shows that using **any filter** causes
  the `#load-more` control — out-of-band-swapped, but nested *inside* the
  very element `innerHTML` is about to overwrite — to be **permanently
  destroyed** the moment a filter is first touched. `has_next` may still be
  `True` server-side, but no button to reach it ever appears again for the
  rest of that page session (only a full, non-htmx page reload restores
  it). That is a materially worse outcome (silent, permanent loss of access
  to part of the audit trail) than "the button looks stuck in the wrong
  place," so this is escalated from Warning to **Critical** below (CR-01,
  replacing the now-resolved old CR-01 slot).

## Critical Issues

### CR-01: `/history` "Показать ещё" pagination is permanently destroyed by the first filter interaction (htmx oob nested inside its own swap target); the button-click ordering bug from the prior review is also still present

**File:** `app/templates/partials/history_rows.html:44-52`, `app/templates/partials/history_filters.html:8-28`, `app/routes/history.py:34-46`

**Issue:** The trailing `<tr id="load-more">` row is marked
`hx-swap-oob="true"` on every htmx response (`oob` is true whenever
`is_hx` is true), and it lives *inside* `#history-tbody` — the same
element used as the `hx-target` by both the type/product `<select>`s
(`history_filters.html:8-16`, `:20-28`) and the "Показать ещё" button
(`history_rows.html:47-49`). htmx strips `hx-swap-oob` elements out of the
response and swaps them into the DOM *before* the main target swap runs
("removed from the response before the remainder of the response is
swapped in via the target" — documented htmx behavior). Two distinct
failure modes follow, both rooted in the same nesting mistake:

1. **Filter select change (new finding, not caught by the prior review).**
   Neither `<select>` sets `hx-swap`, so htmx uses its default —
   `innerHTML` — on `#history-tbody`. Sequence: (a) the oob-extracted
   `#load-more` row is swapped into its current position inside
   `#history-tbody`; (b) the main swap then runs
   `#history-tbody.innerHTML = <new rows only>` (the load-more row was
   already stripped out of that content for step (a)), which wipes out
   *every* child of `#history-tbody`, including the row step (a) just
   placed. After the **first** filter interaction, `#load-more` no longer
   exists anywhere in the DOM. Any later response that tries to oob-swap a
   fresh `#load-more` (e.g. a filter that now matches >50 rows) has no
   matching id to swap into, so it silently no-ops. Result: "Показать ещё"
   never reappears for the rest of that page session, even when
   `has_next` is `True` server-side — the operator can no longer reach
   rows beyond the first 50 for that filter, with no error or indication
   anything is missing.
2. **"Показать ещё" click itself (carried over from the prior review's
   WR-01, confirmed still present and unfixed).** The button uses
   `hx-swap="beforeend"` on the same `#history-tbody` target. Because the
   oob swap repositions `#load-more` in place *before* the `beforeend`
   append runs, the newly-fetched rows land *after* the already-updated
   `#load-more` row rather than before it — the control visibly migrates
   to a fixed position between the first and second page of rows instead
   of staying at the bottom, and every subsequent batch stacks beneath it
   (compounding with each click).

Given the app's core value proposition (the operator can rely on stock and
sales figures being always correct and visible), silently and permanently
hiding part of the operation ledger behind a vanished "load more" control
is a real defect, not merely cosmetic — hence Critical rather than Warning.

**Fix:** Stop nesting the oob pagination control inside the element that
is also the `innerHTML`/`beforeend` swap target. Recommended: move
`#load-more` outside `#history-tbody` (e.g. its own `<tfoot>` row) so
neither swap ever touches it, and drop `hx-swap-oob` entirely in favor of
a same-element swap:
```html
<table>
  ...
  <tbody id="history-tbody">{# only data <tr>s, no load-more #}</tbody>
  <tfoot><tr id="load-more">...</tr></tfoot>
</table>
```
with the `<select>`s and the "Показать ещё" button both still targeting
`#history-tbody` (default `innerHTML` for filters is then safe — it only
ever touches data rows), and the button additionally targeting `#load-more`
directly (`hx-target="#load-more" hx-swap="outerHTML"`) to update/remove
itself without needing `hx-swap-oob` or `beforeend` at all. Add a
regression test that performs an `HX-Request` filter GET against a fixture
with >50 matching rows and asserts a `<button>` inside `id="load-more"` is
present in that response (the current suite never exercises the >50-row
filtered case).

## Warnings

### WR-01: `/corrections` has no persistent nav entry point, and is fully unreachable with zero products (carried over from prior review, unchanged)

**File:** `app/templates/base.html:17-26`, `app/templates/pages/home.html:5-16`

**Issue:** `base.html`'s nav bar links to `/`, `/products`, `/receipts/new`,
`/sales/new`, `/writeoff`, `/customers`, `/history`, `/dictionary`,
`/backup` — never `/corrections`. The only link to `/corrections` anywhere
in the rendered UI remains the inline paragraph in `home.html:11`, gated
behind `{% if product %}`. On a fresh install with zero active products,
`home.html` renders `<p>Нет товаров</p>` instead, and `/corrections`
becomes completely unreachable via the UI. `/writeoff` received the exact
same fix (nav entry + `test_web_writeoff_reachable_from_nav` regression
test) earlier in this phase; `/corrections` never got the equivalent
treatment, and still has no guarding test.

**Fix:**
```html
<a href="/corrections"{% if request.url.path.startswith("/corrections") %} class="active"{% endif %}>Корректировка</a>
```
plus a `test_web_corrections_reachable_from_nav` test mirroring the
write-off one.

### WR-02: `writeoff_rows.html` doesn't guard against a falsy/None `payload` (carried over, unchanged)

**File:** `app/templates/partials/writeoff_rows.html:28-30`
**Issue:** `{{ WRITEOFF_REASONS.get(r.op.payload.reason_code, r.op.payload.reason_code) }}`
assumes `r.op.payload` is always a populated dict, unlike
`history_rows.html:28`, which defensively checks
`r.op.type == "writeoff" and r.op.payload` first. Every write-off written
through today's single write path always populates `payload`, so this
isn't reachable yet — but it's an inconsistent defensive posture between
two templates rendering the same op type, and any future/legacy/synced row
with `payload IS NULL` would raise a Jinja `UndefinedError` on
`None.reason_code`, taking down the entire `/writeoff` page render.
**Fix:**
```html
{% if r.op.payload %}
{{ WRITEOFF_REASONS.get(r.op.payload.reason_code, r.op.payload.reason_code) }}{% if r.op.payload.note %} — {{ r.op.payload.note }}{% endif %}
{% else %}<span class="muted">—</span>{% endif %}
```

### WR-03: `/history` product filter dropdown only lists active products (carried over, unchanged)

**File:** `app/services/operations.py:51-57`
**Issue:** `filter_products()` filters on `Product.deleted_at.is_(None)`.
Operations recorded against a product that is later soft-deleted remain
visible in the unfiltered `/history` view (correct — the ledger join has
no deleted-filter), but the operator has no way to filter down to that
specific product's history once it's soft-deleted, since it no longer
appears as an `<option>` in the "Товар" select.
**Fix:** Either include soft-deleted products in the filter list (e.g.
labeled "Название (архив)"), or document this as a known limitation.

## Info

### IN-01: `corrections.py` "delta" mode silently reclassifies `-0` as a generic "nothing changed" error (carried over, unchanged)

**File:** `app/services/corrections.py:70-83`
**Issue:** Input `"-0"` passes the delta-mode format check
(`body = "0"`, `"0".isdigit()` is `True`), producing
`qty_delta = int("-0") == 0`, which falls into the `qty_delta == 0` branch
and returns `ZERO_NET_ERROR` instead of the more specific `DELTA_QTY_ERROR`.
Functionally harmless (the write is still correctly blocked) — message
precision only.
**Fix:** Not required to block ship; special-case `"-0"`/`"+0"` before the
generic zero-delta check if message precision matters.

### IN-02: `return_form.html` uses a `max` attribute on a `type="text"` input (carried over, unchanged)

**File:** `app/templates/partials/return_form.html:24`
**Issue:** `<input type="text" ... max="{{ remaining }}">` — the HTML `max`
attribute has no effect on `type="text"` inputs. Server-side validation
(`qty > remaining` in `services/returns.py`) is correctly authoritative, so
this is cosmetic/dead-markup only.
**Fix:** Remove the dead `max` attribute, or switch to `type="number"` with
equivalent `inputmode` handling if client-side capping is desired.

### IN-03: `history.py` route parameter `type` shadows the Python builtin (carried over, unchanged)

**File:** `app/routes/history.py:16`
**Issue:** `def history_page(request, type: str = "", ...)` shadows the
builtin `type()` within the function body. No current bug (the builtin
isn't needed there), but it's a footgun for a future edit.
**Fix:** Rename to `type_`/`op_type` internally; keep the wire
query-string key `type` via `Query(alias="type")` if the external contract
must stay unchanged.

### IN-04: `return_create` duplicates the origin/validity check `register_return` already performs (carried over, unchanged)

**File:** `app/routes/returns.py:104-105`, `app/services/returns.py:72-74`
**Issue:** The route independently re-derives `origin_valid` by fetching
the same `Operation` and re-checking `type == "sale" and sale_id is not
None` before calling `register_return`, which performs the identical check
internally. Not a functional bug today, but the two copies could drift out
of sync if only one side is updated later.
**Fix:** Have `register_return` (or a shared helper) surface enough
information for the route to build its error context without
re-implementing the validity check.

### IN-05: `/corrections`'s "current stock" hint always disappears after any submit, success or failure (carried over, unchanged)

**File:** `app/routes/corrections.py:82-114`, `app/templates/partials/correction_form.html:63-69`
**Issue:** `#current-qty-hint` is only ever populated by the
`/corrections/lookup` GET (an out-of-band swap triggered while typing a
code). Every POST response — success, validation error, or the exception
path — sets `"current_qty": None`, and `#correction-form-wrap` (which
contains the hint) is swapped `outerHTML` on every POST. So as soon as the
operator submits, even a rejected submission (e.g. a bad quantity), the
"Текущий остаток: N" hint they were just relying on reverts to "—" and can
only be restored by retyping the code. Purely a UX regression-of-context
(the server still validates against the real quantity), but it undermines
the counted-mode hint on the most common retry path.
**Fix:** On the error-retention path, re-run `lookup_prefill`'s quantity
lookup for the currently-echoed `code` and populate `current_qty` from it
instead of hardcoding `None`.

### IN-06: `corrections.py` delta mode rejects a leading `+`, contradicting its own UI label (carried over, unchanged)

**File:** `app/services/corrections.py:70-76`, `app/templates/partials/correction_form.html:72`
**Issue:** The delta-mode input label reads "Изменение (+ или −)"
("Change (+ or −)"), implying a leading `+` is valid input syntax for a
positive delta. Validation only special-cases a leading `-`
(`body = s[1:] if s.startswith("-") else s`); a value like `"+3"` fails
`"+3".isdigit()` (the `+` is never stripped) and is rejected with the
generic `DELTA_QTY_ERROR`, even though the label visually invites `+`
notation.
**Fix:** Either strip a leading `+` the same way `-` is stripped, or
reword the label to clarify that positive deltas are entered as a bare
number with no `+` prefix.

### IN-07: `/history`'s `page` query param accepts negative values with no validation (carried over, unchanged)

**File:** `app/routes/history.py:14-21`, `app/services/operations.py:14-48`
**Issue:** `page: int = 0` has no lower-bound validation. A negative
`page` (e.g. `/history?page=-1`) produces a negative `OFFSET` in the
underlying query; SQLite silently treats a negative `OFFSET` as `0`, so
this doesn't crash — it silently re-serves page 0's content under a URL
that looks like it should show something else, rather than rejecting the
input. Low severity (no crash, no data exposure), a missing-input-
validation gap only.
**Fix:** `page: int = Query(0, ge=0)` to reject/clamp negative values
explicitly.

### IN-08: Inconsistent empty-note storage between corrections and write-offs (new finding)

**File:** `app/services/corrections.py:91`, `app/services/writeoffs.py:100`
**Issue:** `corrections.py` stores `note.strip() or None` in the payload
(empty note → `None`), while `writeoffs.py` stores `note.strip()` as-is
(empty note → `""`). Both are handled correctly by the display templates
(`{% if payload.note %}` is falsy for both `None` and `""`), so this isn't
a live bug — but it's an unnecessary shape inconsistency between two
sibling single-write-path services, which could confuse a future reader
building an export or migration that assumes one canonical "empty"
representation for `payload.note`.
**Fix:** Standardize on one convention (recommend `None`, matching
`corrections.py`) in `writeoffs.py` too: `"note": note.strip() or None`.
This changes `tests/test_writeoffs.py::test_stock_and_reason`'s assertion
`op.payload == {"reason_code": "expired", "note": ""}` to expect `None`
instead — update the test alongside the fix.

---

_Reviewed: 2026-07-10T12:40:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
