---
phase: 05-stock-operations-history
reviewed: 2026-07-10T14:30:00Z
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
  - app/templates/partials/history_load_more.html
  - app/templates/partials/history_response.html
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
  critical: 0
  warning: 6
  info: 10
  total: 16
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-07-10T14:30:00Z
**Depth:** standard (targeted deep verification of the 05-09 `/history` pagination restructuring)
**Files Reviewed:** 34
**Status:** issues_found (no blockers)

## Summary

This is a re-review of Phase 5 after **05-09**, which restructured
`/history`'s "Показать ещё" pagination to fix the previous review's **CR-01**
(the pagination control lived inside `#history-tbody`, the same element the
type/product `<select>`s and the "Показать ещё" button's own click both swap
into, so the oob-before-main-swap ordering destroyed it on the very first
filter interaction).

**CR-01 is CONFIRMED RESOLVED.** Verification performed specifically on this
fix:

- Read `git show 3970586` (the 05-09 commit) against the prior structure to
  confirm `#load-more` no longer nests inside `#history-tbody`'s
  innerHTML/beforeend swap target — it now lives in a sibling `<tfoot>`.
- Ran the full existing suite — `31 passed`, including the new
  `test_web_history_load_more_survives_filter_change` regression test, which
  seeds 51 rows and asserts `#load-more` is absent from inside `<tbody>` and
  present in `<tfoot>` for both a filtered full page and a filtered HX
  response.
- Probed the raw HTTP response bytes for an HX `/history` request to confirm
  htmx's `getStartTag` tag-sniffing (`<tr>` is the first tag in the combined
  rows+oob payload, regardless of leading Jinja whitespace) will wrap the
  response as `<table><tbody>...</tbody></table>`, so oob-extraction and the
  main swap split correctly.
- Probed a **two-hop** pagination sequence (120 seeded write-offs,
  `page_size=50`, not covered by the new test, which only exercises page 0):
  page 0 response linked to `page=1`; the page 1 response correctly linked
  to `page=2`; the page 2 (final, 20 rows remaining) response correctly
  rendered an empty, buttonless `<tr id="load-more">` (`has_next` correctly
  `False`). Confirms the fix holds across *multiple* consecutive
  interactions, not just the single filter-change case the new test covers.
- Confirmed `<tfoot>` after `<tbody>` is valid HTML5 (the modern content
  model permits `tfoot` as the table's last child) and that an oob
  outerHTML replace-by-ID works correctly even though the oob fragment's own
  parsing context (synthetic `<table><tbody>` wrapper, since the whole
  response's first tag is `<tr>`) differs from the live target's real
  parent (`<tfoot>`) — this is standard, well-supported contextual fragment
  parsing behavior, not something this codebase needs to special-case.

**No new htmx wiring defect of the CR-01 class was introduced.** The
findings below are pre-existing carry-forward items from the prior review
(unchanged files, re-verified as still present) plus a few new lower-severity
observations surfaced by this pass — none rise to Critical.

## Warnings

### WR-01: `/corrections` has no persistent nav entry point, and is fully unreachable with zero products (carried over, unchanged)

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
`history_rows.html:29`, which defensively checks
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

### WR-04: `is_hx` header check accepts any non-empty string, including the literal `"false"` (new finding)

**File:** `app/routes/history.py:41`
**Issue:** `is_hx = bool(request.headers.get("HX-Request"))` treats *any*
non-empty header value as "genuine htmx request," including a hand-crafted
`HX-Request: false`. Real htmx always sends the literal string `"true"`, so
this is unreachable through normal UI use — but the entire purpose of this
line (per the CR-01/D-14/D-15 comment directly above it, both the original
and the 05-09 addendum) is to reliably distinguish genuine htmx traffic
from anything else requesting `/history` with query params. A client that
sends `HX-Request: false` (a test tool, a proxy, a future JS helper, or a
misconfigured integration) would incorrectly receive the chrome-less
`history_response.html` fragment instead of the full page — reproducing
the exact "browser drops a bare fragment" failure class this branch exists
to prevent, just via a different trigger than the one already fixed.
**Fix:**
```python
is_hx = request.headers.get("HX-Request", "").lower() == "true"
```

### WR-05: `<tfoot>` is repurposed to anchor a pagination control, not to hold a footer summary (new finding, 05-09)

**File:** `app/templates/pages/history.html:23-27`, `app/templates/partials/history_load_more.html`
**Issue:** `<tfoot>` is a table-footer sectioning element with defined
semantics (column totals/summaries); some assistive technology and print
stylesheets treat it specially (e.g. repeating on every printed page, or
being announced differently by screen readers than an ordinary body row).
Using it purely as an out-of-band DOM anchor for a "Показать ещё" button —
which is what the 05-09 fix does to solve the CR-01 nesting bug — is a
semantic misuse of the element, even though it correctly achieves the
"structural sibling of `#history-tbody`, never touched by its swaps" goal
the fix needed. A plain `<div id="load-more">` placed immediately after the
closing `</table>` tag would achieve the identical DOM-sibling isolation
without borrowing footer semantics for what is really a pagination control,
not a summary row.
**Fix:** Low priority — functionally correct as shipped. Consider for a
follow-up accessibility pass:
```html
</table>
<div id="load-more">
  {% with oob = False %}{% include "partials/history_load_more.html" %}{% endwith %}
</div>
```
with `history_load_more.html`'s root element changed from `<tr>`/`<td
colspan="8">` to a plain block element.

### WR-06: Offset-based `/history` pagination can skip or duplicate rows under concurrent writes (new finding)

**File:** `app/services/operations.py:29-48`
**Issue:** `history_view` pages with `LIMIT page_size+1 OFFSET
page*page_size` over `ORDER BY created_at DESC, seq DESC`. If a new
operation is recorded (a sale, write-off, receipt, correction, etc.)
between two "Показать ещё" clicks, every row at or above the current offset
boundary shifts down by one — the next page fetch either re-shows a row
already seen (duplicate) or skips a row entirely (never shown). Not a
data-loss issue (the ledger itself is untouched), but it can make the
on-screen history page silently misleading during ordinary concurrent
operator activity (the exact scenario this app is built around — the
operator keeps working while `/history` might be left open in another
view).
**Fix:** Not urgent for v1 (short, focused browsing sessions), but worth a
follow-up: switch to keyset/cursor pagination keyed on the last row's
`(created_at, seq)` instead of a numeric `OFFSET`.

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

### IN-08: Inconsistent empty-note storage between corrections and write-offs (carried over, unchanged)

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

### IN-09: Unvalidated `type`/`product` query params echoed verbatim into the pagination URL (new finding)

**File:** `app/routes/history.py:21,46`, `app/templates/partials/history_load_more.html:14`
**Issue:** `history_view` returns `"type_filter": type_filter or ""` using
the raw, unvalidated query value even when it isn't a member of
`OPERATION_TYPES` (the allow-list is applied only to the `WHERE` clause,
not to the echoed-back value). This raw value is then embedded into the
"Показать ещё" button's `hx-get` URL on every response. Harmless today —
Jinja's autoescaping neutralizes HTML/attribute injection, and the value is
silently ignored server-side on the next request — but it's inconsistent
with the rest of the codebase's "never trust unvalidated input past the
boundary" convention (V5, applied to `reason_code`/`mode` elsewhere).
**Fix:** Normalize `type_filter` to `""` in `history_view` when it isn't a
member of `OPERATION_TYPES`, before returning it, instead of only using the
allow-list to build the `WHERE` clause.

### IN-10: Pre-existing `ruff` import-order violation in a required-reading test file (new finding)

**File:** `tests/test_writeoffs.py:17-21`
**Issue:** `uv run ruff check tests/test_writeoffs.py` reports `I001`
(unsorted import block) — the `from app.services.writeoffs import
register_writeoff  # noqa: F401` "RED by design" contract import is placed
before the `sqlalchemy`/`app.models`/`app.services.ledger` imports,
breaking isort grouping. The 05-09 commit fixed the identical pattern in
`tests/test_history.py` specifically to satisfy that plan's ruff-clean
gate; the same pattern remains unfixed here (and in `test_customers.py`/
`test_sales.py` elsewhere in the suite, outside this review's file list).
Not a functional issue — the `# noqa: F401` already suppresses the
unused-import warning — but worth a follow-up sweep if a repo-wide
ruff-clean gate is ever enforced.
**Fix:** `uv run ruff check --fix tests/test_writeoffs.py` (verify the
reordering doesn't change the "RED by design" collection-failure intent
before committing).

---

_Reviewed: 2026-07-10T14:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
