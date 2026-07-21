---
quick_id: 260720-wqc
type: execute
autonomous: true
files_modified:
  - app/templates/partials/dictionary_rows.html
  - app/routes/dictionary.py
  - app/templates/partials/dictionary_lookup.html
  - app/templates/pages/product_form.html
  - tests/test_dictionary.py
must_haves:
  truths:
    - "The /dictionary list shows a read-only «Категория» column per row, rendering Dictionary.rubric (or an em dash '—' when NULL) — no filter, no sort, no input."
    - "Typing a known dictionary code into the product form's Код field, when Категория is empty, auto-fills Категория from that entry's rubric without leaving the field or submitting."
    - "An operator-entered Категория value is never overwritten by the autofill — same 'never overwrite non-empty input' rule already applied to Название (Pitfall 5)."
    - "Category autofill is independent of name autofill: if Название already has a value (typed or previously autofilled) but Категория is still empty, Категория still fills when the looked-up code carries a rubric."
    - "When the looked-up code has no rubric (NULL) or the code is unknown, Категория is left untouched — same no-op/204 behavior as today."
  artifacts:
    - path: "app/templates/partials/dictionary_rows.html"
      provides: "Read-only Категория column in the dictionary list table"
    - path: "app/templates/partials/dictionary_lookup.html"
      provides: "New response partial combining the existing direct-swap name fragment with an out-of-band category fragment"
      min_lines: 5
    - path: "app/routes/dictionary.py"
      provides: "dictionary_lookup route computing fill_name/fill_category independently and rendering the combined partial"
    - path: "app/templates/pages/product_form.html"
      provides: "Updated hx-include on #code so the current category value reaches the lookup request"
  key_links:
    - from: "app/templates/pages/product_form.html"
      to: "/dictionary/lookup"
      via: "hx-get on #code with hx-include=\"[name='name'], [name='category']\""
      pattern: "hx-include=\"\\[name='name'\\], \\[name='category'\\]\""
    - from: "app/routes/dictionary.py::dictionary_lookup"
      to: "app/templates/partials/dictionary_lookup.html"
      via: "TemplateResponse render (replaces the old direct partials/name_input.html render)"
      pattern: "dictionary_lookup\\.html"
    - from: "app/templates/partials/dictionary_lookup.html"
      to: "#category input on product_form.html"
      via: "hx-swap-oob=\"true\" replace-by-id"
      pattern: "id=\"category\""
---

<objective>
Two small, purely additive UI changes to the dictionary/product-form flow:

1. Show the dictionary's rubric as a read-only «Категория» column on the /dictionary list.
2. Auto-fill Product.category from the matched Dictionary entry's rubric on the product form's code lookup, using the exact same "never overwrite a non-empty operator value" rule already used for the name autofill.

Purpose: The rubric data already exists in the dictionary (CAT-06) but is invisible in the UI and unused for product creation — this surfaces it and saves the operator a manual category pick when the code is already classified.
Output: A rubric column on /dictionary; a category autofill wired into the existing /dictionary/lookup code-input flow on the product form.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@app/models.py
@app/routes/dictionary.py
@app/services/dictionary.py
@app/templates/partials/dictionary_rows.html
@app/templates/partials/name_input.html
@app/templates/partials/product_price_autofill.html
@app/templates/pages/product_form.html
@tests/test_dictionary.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Show read-only Категория column on the /dictionary list</name>
  <files>app/templates/partials/dictionary_rows.html, tests/test_dictionary.py</files>
  <action>
In app/templates/partials/dictionary_rows.html, add a read-only «Категория» column to the entries table. list_entries() in app/services/dictionary.py already returns Dictionary ORM objects with the rubric attribute populated — no service change is needed.

In the first header row (currently Код / Название / empty action header), insert a new "Категория" header cell between "Название" and the trailing empty action `<th></th>`. In the second header row (the filter-row with the code/name filter inputs), insert a matching empty `<th></th>` in the same column position to keep both header rows aligned to the now 4-column layout — do NOT add a filter input or sort option for rubric (per scope: display only, no filter, no sort).

In the `{% for e in entries %}` loop in `<tbody>`, insert a new `<td>{{ e.rubric or "—" }}</td>` in the same column position, between the existing name `<td>` and the actions `<td>`. This cell is plain text output only — no `<input>`, no `form=` attribute, no hx- wiring (unlike the editable code/name cells beside it).

Add a new test to tests/test_dictionary.py named test_web_dictionary_shows_rubric_column: create one entry via add_entry(session, code=..., name=...), then set its .rubric attribute directly (e.g. entry.rubric = "Макияж") and session.commit() (add_entry itself has no rubric parameter — rubric is populated elsewhere by the CAT-06 import/classification service, so tests set it directly on the ORM object). GET /dictionary and assert the rubric value "Макияж" appears in the response text. Add a second entry with no rubric set (leave it NULL, matching add_entry's default) and assert the em dash "—" also appears in the response text for that row (the None fallback).
  </action>
  <verify>
    <automated>uv run pytest tests/test_dictionary.py -q</automated>
  </verify>
  <done>The /dictionary list renders a fourth "Категория" column showing each entry's rubric (or "—" when NULL), with no filter/sort control added for it; the new test_web_dictionary_shows_rubric_column test passes alongside all existing tests/test_dictionary.py tests.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Autofill Product.category from Dictionary.rubric on the product form</name>
  <files>app/routes/dictionary.py, app/templates/partials/dictionary_lookup.html, app/templates/pages/product_form.html, tests/test_dictionary.py</files>
  <behavior>
    - GET /dictionary/lookup?code=&lt;known-code-with-rubric&gt;&amp;name=&amp;category= (both empty) -> 200, response contains an out-of-band category input (hx-swap-oob="true", id="category") whose value is the entry's rubric, AND the existing name-wrap fragment fills the name too (both independent, both empty -> both fill).
    - GET /dictionary/lookup?code=&lt;known-code-with-rubric&gt;&amp;name=Уже+заполнено&amp;category= (name non-empty, category empty) -> 200, response contains the category OOB input filled from rubric, but the name fragment shows NO autofill hint ("Название подставлено из справочника" absent) — category fills independently of name being already set.
    - GET /dictionary/lookup?code=&lt;known-code-with-rubric&gt;&amp;name=&amp;category=Уже+заполнено (category non-empty) -> 200 with the name fragment filled, but NO category OOB input present in the response (id="category" absent) — an operator-entered category is never overwritten (mirrors Pitfall 5 for name).
    - GET /dictionary/lookup?code=&lt;known-code-no-rubric&gt;&amp;name=&amp;category= (entry exists but rubric is NULL) -> unaffected by this change: name still fills if empty (existing behavior), no category OOB fragment (nothing to fill).
    - GET /dictionary/lookup with both name and category already non-empty, or with an unknown code -> 204 empty response (unchanged contract, existing tests test_web_lookup_204_when_name_present / test_web_lookup_204_when_code_unknown must keep passing as-is since their fixture entries carry no rubric).
  </behavior>
  <action>
In app/routes/dictionary.py, modify the dictionary_lookup route: add a `category: str = ""` query parameter alongside the existing `code`/`name` parameters (same GET-query-param shape as `name`). Keep `entry = lookup(session, code)` and the `entry is None -> Response(status_code=204)` branch unchanged. Replace the remaining logic: compute `fill_name = not name.strip()` and `fill_category = bool(entry.rubric) and not category.strip()` — each field's fill decision is independent, matching Pitfall 5's "never overwrite a non-empty operator value" rule applied per-field rather than gating the whole response on name alone. If neither `fill_name` nor `fill_category` is true, return `Response(status_code=204)` (preserves the exact current no-op contract). Otherwise build the context dict with `name` (entry.name if fill_name else the echoed-back `name` param), `autofilled` (fill_name), `fill_category`, and `category` (entry.rubric if fill_category else the echoed-back `category` param), and render the new `partials/dictionary_lookup.html` template instead of `partials/name_input.html` directly.

Create app/templates/partials/dictionary_lookup.html as a thin wrapper: `{% include "partials/name_input.html" %}` first (unchanged — this keeps producing the exact `<div id="name-wrap">` fragment that `hx-target="#name-wrap" hx-swap="outerHTML"` on the product form's #code input already swaps in place, so that contract is byte-for-byte preserved), followed by, only when `fill_category` is true, an out-of-band category input mirroring the OOB pattern in app/templates/partials/product_price_autofill.html: an `<input type="text" id="category" name="category" list="cat-options" value="{{ category }}" hx-swap-oob="true">` — matching the id/name/list attributes of the static `#category` input in product_form.html exactly so the existing `<datalist id="cat-options">` wiring keeps resolving after the OOB replace. Do NOT add anything to app/templates/partials/name_input.html itself — it is also reused by app/routes/receipts.py's separate `/receipts/lookup` route (per its own PD-6 comment), which has no category field and must stay untouched.

In app/templates/pages/product_form.html, update the `#code` input's `hx-include` attribute from `"[name='name']"` to `"[name='name'], [name='category']"` so the debounced lookup request also carries the operator's current category value (required for the server-side empty-check above). Leave `hx-get`, `hx-trigger`, `hx-target="#name-wrap"`, `hx-swap="outerHTML"`, and `hx-sync` on that input unchanged — only the include list grows.

Update the existing test test_web_product_form_wired_for_autofill in tests/test_dictionary.py to assert the new hx-include value `"[name='name'], [name='category']"` in place of the old `"[name='name']"` assertion.

Add three new tests to tests/test_dictionary.py mirroring the <behavior> cases above: test_web_lookup_fills_category_when_empty (entry with rubric set via direct attribute assignment + commit, both name and category empty in the request -> 200, asserts `id="category"` and `hx-swap-oob="true"` and the rubric value all appear in response text); test_web_lookup_fills_category_only_when_name_already_present (same entry, name non-empty in the request, category empty -> 200, asserts the category OOB fragment is present but "Название подставлено из справочника" is absent); test_web_lookup_does_not_overwrite_existing_category (same entry, category non-empty in the request -> 200, asserts `id="category"` is absent from the response text, i.e. no OOB category fragment sent).
  </action>
  <verify>
    <automated>uv run pytest tests/test_dictionary.py -q</automated>
  </verify>
  <done>dictionary_lookup independently fills Категория from Dictionary.rubric and Название from Dictionary.name, each only when its own field is currently empty; product_form.html's #code lookup now includes the category field's value in its request; all new and existing tests/test_dictionary.py tests pass.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator-typed code/name/category (product form) -> GET /dictionary/lookup -> HTML fragment | Local single-operator app (no auth boundary crossed here beyond the existing app-wide session guard); the endpoint only echoes back either the operator's own just-typed values or existing Dictionary rows already readable via /dictionary. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-260720-01 | Tampering | dictionary_lookup query params (code/name/category) | accept | Values are either echoed back verbatim into the same form fields the operator typed them into (Jinja auto-escapes by default, no `\| safe`) or sourced from existing Dictionary rows already exposed on /dictionary — no new write path, no new data exposed beyond what /dictionary already lists. |
| T-quick-260720-02 | Information Disclosure | Dictionary.rubric now rendered in two places (list column + autofill) | accept | rubric is helper/reference data (D-24, CAT-06) already fully visible in the raw dictionary table via existing routes; surfacing it in the list and as a form default adds no new exposure. |
</threat_model>

<verification>
- `uv run pytest tests/test_dictionary.py -q` passes (all existing + new tests).
- Manual spot check: open /dictionary and confirm a «Категория» column renders per row (rubric value or —).
- Manual spot check: on /products/new, type a code known to have both a Dictionary entry and a rubric — confirm Название AND Категория both auto-fill; then edit Категория by hand and re-trigger the code lookup (e.g. backspace+retype a digit) — confirm the hand-edited Категория is not overwritten.
</verification>

<success_criteria>
- /dictionary lists a read-only Категория column reflecting Dictionary.rubric, with no filter/sort added.
- Typing a known code on the product form autofills Категория from the matched entry's rubric when Категория is empty, independently of whether Название also fills.
- An operator-entered Категория value is never overwritten by the autofill.
- No existing dictionary/name-autofill/receipts-lookup behavior changes.
</success_criteria>

<output>
Create `.planning/quick/260720-wqc-rubric/260720-wqc-SUMMARY.md` when done
</output>
