---
quick_id: 260813-ezt
type: execute
autonomous: true
files_modified:
  - app/templates/mobile_partials/batch_card_picker.html
  - app/templates/mobile_partials/transfers_step_batch.html
  - app/templates/mobile_partials/transfers_step_dest.html
  - app/templates/partials/sale_name_field.html
  - app/__init__.py
  - tests/test_mobile_corrections.py
  - tests/test_mobile_transfers.py
must_haves:
  truths:
    - "Tapping a batch card in the mobile Продажа/Корректировка/Списание/Перемещение wizards (and the desktop sale name-search debounce) sends its batch_id/code/name/row through hx-vals intact — the HTML attribute is never truncated at a JSON double quote, so the tapped batch actually gets selected instead of silently reverting to no selection."
    - "No template in the codebase renders a tojson-driven hx-vals attribute with double-quote HTML delimiters — every such attribute is single-quoted."
    - "The stale WR-02 comments that falsely claimed tojson escapes double quotes for HTML attributes are corrected to state the true rule (tojson escapes ' not \")."
  artifacts:
    - path: "app/templates/mobile_partials/batch_card_picker.html"
      provides: "single-quoted hx-vals with corrected WR-02 comment, shared by sale/correction/write-off wizards"
    - path: "app/templates/mobile_partials/transfers_step_batch.html"
      provides: "both hx-vals occurrences (batch-pick card + Назад button) single-quoted with corrected comments"
    - path: "app/templates/mobile_partials/transfers_step_dest.html"
      provides: "single-quoted hx-vals on the Назад button with corrected comment"
    - path: "app/templates/partials/sale_name_field.html"
      provides: "single-quoted hx-vals for the desktop name-search debounce row param"
    - path: "tests/test_mobile_corrections.py"
      provides: "regression test proving batch_id survives inside the single-quoted hx-vals attribute"
    - path: "tests/test_mobile_transfers.py"
      provides: "two regression tests covering transfers_step_batch.html (both spots) and transfers_step_dest.html"
  key_links:
    - from: "app/templates/mobile_partials/batch_card_picker.html"
      to: "/m/corrections/step/batch-pick, /m/sales/step/batch-pick, /m/writeoff/step/batch-pick"
      via: "hx-get card tap + single-quoted hx-vals carrying batch_id"
      pattern: "hx-vals='\\{\"batch_id\""
    - from: "tests/test_mobile_corrections.py"
      to: "app/templates/mobile_partials/batch_card_picker.html"
      via: "exact-string assertion on the rendered single-quoted hx-vals attribute containing the real batch id"
      pattern: "hx-vals=.\\{\"batch_id\""
---

<objective>
Fix a live production bug (confirmed on ori.viktorplus.com/m/corrections, app version 1.28): five templates embed `{{ ... | tojson }}` inside a DOUBLE-quoted `hx-vals` HTML attribute. Jinja's `tojson` filter (`jinja2.utils.htmlsafe_json_dumps`) escapes `<`, `>`, `&`, `'` — but json.dumps always renders object keys/values in double quotes, so tojson output ALWAYS contains literal `"` characters. The filter's own docstring says exactly this: "The exception is in HTML attributes that are double quoted; either use single quotes or the `|forceescape` filter." Because these five attributes are double-quoted, the browser's HTML parser terminates each `hx-vals` at the payload's first `"`, collapsing it to the literal string `{` — batch_id (and code/name/row) never reach the server. On mobile this means a tapped batch card never actually gets selected: the pick request fires with an empty `batch_id`, the card never highlights, and «Далее» stays disabled. Same breakage hits the desktop sale name-search debounce row param.

Regression was introduced in commit ea0778f ("fix(11): WR-02 use tojson for hx-vals JSON instead of manual string interpolation", 2026-07-13), which replaced manual `'{"batch_id": "..."}'` single-quoted interpolation with `"{{ ... | tojson }}"` double-quoted — backwards from what tojson requires.

The fix (delimiter-only, no logic change): switch each of the five HTML attributes from double to single quotes. The Jinja expression's own single-quoted dict-key literals inside `{{ }}` are unaffected — Jinja tokenizes `{{ }}` blocks before the surrounding HTML text matters, so `hx-vals='{{ {'batch_id': b.id} | tojson }}'` is valid, correctly-rendering template source. tojson escapes any `'` in the data as `\u0027`, so a single-quoted attribute can never be broken by the data itself.

Purpose: restore mobile batch selection (sale/correction/write-off/transfer wizards) and the desktop sale name-search row param, which have been silently broken since 2026-07-13.
Output: five corrected `hx-vals` attributes, two corrected stale comments, three new regression tests pinning the exact rendered attribute shape, `__version__` bumped to "1.29".
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@app/templates/mobile_partials/batch_card_picker.html
@app/templates/mobile_partials/transfers_step_batch.html
@app/templates/mobile_partials/transfers_step_dest.html
@app/templates/partials/sale_name_field.html
@app/__init__.py
@tests/test_mobile_corrections.py
@tests/test_mobile_transfers.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Single-quote the five tojson-driven hx-vals attributes; correct the stale WR-02 comments; bump version</name>
  <files>app/templates/mobile_partials/batch_card_picker.html, app/templates/mobile_partials/transfers_step_batch.html, app/templates/mobile_partials/transfers_step_dest.html, app/templates/partials/sale_name_field.html, app/__init__.py</files>
  <action>
Change the attribute delimiter only (double quote to single quote) at each of the five spots below. Do NOT touch the dict contents, filter chain, or any other markup — this is a quote-character-only fix plus comment-text correction.

1. `app/templates/mobile_partials/batch_card_picker.html` line 52: `hx-vals="{{ ({'batch_id': b.id, 'code': code | default(''), 'row': row_id} if row_id else {'batch_id': b.id, 'code': code | default('')}) | tojson }}"` becomes the same expression wrapped in single quotes: `hx-vals='{{ ({'batch_id': b.id, 'code': code | default(''), 'row': row_id} if row_id else {'batch_id': b.id, 'code': code | default('')}) | tojson }}'`. Also rewrite the WR-02 comment on lines 49-51 (currently: "WR-02: tojson (not manual string concatenation) correctly escapes a double quote inside code/row_id for both JSON and this HTML attribute — manual concatenation broke on a quote character.") to state the real rule instead: tojson always emits JSON's mandatory double-quoted keys/values, so this attribute MUST be single-quoted or the HTML parser truncates it at the first `"`; tojson escapes any `'` in the data as `\u0027`, so a single-quoted attribute can never be broken by the data itself. Keep the "WR-02" label as the comment's identifying tag.

2. `app/templates/mobile_partials/transfers_step_batch.html` line 26 (the batch-pick card): `hx-vals="{{ {'batch_id': b.id, 'code': code, 'name': name} | tojson }}"` becomes `hx-vals='{{ {'batch_id': b.id, 'code': code, 'name': name} | tojson }}'`. Rewrite the WR-02 comment on lines 24-25 (currently: "WR-02: tojson correctly escapes a double quote inside code for both JSON and this HTML attribute.") with the same corrected rule as step 1.

3. Same file, line 51 (the «Назад» button): `hx-vals="{{ {'code': code} | tojson }}"` becomes `hx-vals='{{ {'code': code} | tojson }}'`. The comment on lines 45-48 has two parts: the false "WR-02: tojson correctly escapes a double quote inside code for both JSON and this HTML attribute." claim (replace with the corrected rule from step 1) AND the still-accurate explanation of why hx-vals-not-hx-include is used here ("hx-vals (not hx-include) since this partial has no wrapping <form> of its own — matches this same file's batch-pick cards' own technique for carrying code forward (13-04)."), which must be kept verbatim.

4. `app/templates/mobile_partials/transfers_step_dest.html` line 86: `hx-vals="{{ {'code': code} | tojson }}"` becomes `hx-vals='{{ {'code': code} | tojson }}'`. Rewrite the WR-02 comment on lines 82-83 (currently: "WR-02: tojson correctly escapes a double quote inside code for both JSON and this HTML attribute.") with the corrected rule from step 1.

5. `app/templates/partials/sale_name_field.html` line 15: `hx-vals="{{ {'row': row} | tojson }}"` becomes `hx-vals='{{ {'row': row} | tojson }}'`. This file has no stale WR-02 comment — quote-delimiter change only, no comment edit needed.

Finally, bump `app/__init__.py`'s `__version__` from `"1.28"` to `"1.29"` (project versioning scheme: the trailing counter increments on the commit that completes this quick task's fix).
  </action>
  <verify>
    <automated>uv run pytest tests/test_mobile_corrections.py tests/test_mobile_transfers.py tests/test_mobile_sales.py tests/test_sales.py -q</automated>
  </verify>
  <done>All five hx-vals attributes render single-quoted with their JSON payload intact; both stale WR-02 comments state the corrected rule (tojson escapes ' not "); the hx-include-vs-hx-vals explanation in transfers_step_batch.html's second comment is preserved; __version__ is "1.29"; no pre-existing test regresses.</done>
</task>

<task type="auto">
  <name>Task 2: Add regression tests pinning the fixed attribute shape and guarding against the double-quoted break returning</name>
  <files>tests/test_mobile_corrections.py, tests/test_mobile_transfers.py</files>
  <action>
Add three regression tests reusing each file's existing fixtures/idioms (`mobile_client_factory`, `_seed_batch`/`_source_batch` helpers, `mobile_corrections`/`mobile_transfers` router imports already present) — do not create new test files or new fixtures. Each new test gets a one-line docstring naming this quick task (quick-260813-ezt) and the root cause (tojson escapes `'` not `"`, so a double-quoted hx-vals attribute silently truncates and drops batch_id) so a future reader understands why the exact-string assertion exists.

In `tests/test_mobile_corrections.py`, add a test after `test_mobile_correction_batch_step_lists_open_batches` named `test_mobile_correction_batch_step_hx_vals_batch_id_survives_html_attribute`: seed a batch via `_seed_batch(session, product, warehouse, 5)`, POST `/m/corrections/step/batch` with `data={"code": product.code}` via `mobile_client_factory(mobile_corrections.router)`, assert status 200, then assert the exact rendered single-quoted attribute is present: `assert f'hx-vals=\'{{"batch_id": "{batch.id}", "code": "{product.code}"}}\'' in response.text` (tojson sorts keys alphabetically, so `batch_id` precedes `code`). Also assert the guard: `assert 'hx-vals="{' not in response.text` — no double-quoted hx-vals attribute carrying a JSON payload may ever render again.

In `tests/test_mobile_transfers.py`, add two tests after `test_transfers_batch_pick_carries_name_into_dest_step`:

a) `test_transfers_step_batch_hx_vals_batch_id_survives_html_attribute`: get `source = _source_batch(session, stocked_product)`, POST `/m/transfers/step/batch` with `data={"code": stocked_product.code}` via `mobile_client_factory(mobile_transfers.router)`, assert status 200, then assert `assert f'hx-vals=\'{{"batch_id": "{source.id}", "code": "{stocked_product.code}", "name":' in response.text` — deliberately left open before the Cyrillic name value, since tojson escapes non-ASCII to `\uXXXX` (matches the established pattern already used in `test_transfers_batch_pick_carries_name_into_dest_step`, which asserts on `'"name":' in batch_response.text` rather than literal Cyrillic text). Also assert `assert 'hx-vals="{' not in response.text` — this one response renders BOTH the batch-pick card (line 26) and the «Назад» button (line 51) of transfers_step_batch.html, so this single guard covers both fixed spots in that file.

b) `test_transfers_step_dest_hx_vals_back_button_is_single_quoted`: reuse `source = _source_batch(session, stocked_product)`, POST `/m/transfers/step/dest` with `data={"code": stocked_product.code, "batch_id": source.id}`, assert status 200, then assert `assert f'hx-vals=\'{{"code": "{stocked_product.code}"}}\'' in response.text` and `assert 'hx-vals="{' not in response.text` — covers the fifth fixed line (transfers_step_dest.html:86).
  </action>
  <verify>
    <automated>uv run pytest -q</automated>
  </verify>
  <done>3 new regression tests pass; full suite is green except the 4 pre-existing tests/test_sync_ui.py failures (sync_client._run_lock held by the lifespan auto-sync thread — confirmed unrelated to this change, see .planning STATE.md/MEMORY known-condition note).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Server-rendered HTML -> browser DOM | The hx-vals payload (batch_id/code/name/row) consists entirely of values already known to and echoed by the current server response (a hidden input, visible product text, or a just-looked-up batch id) — not fresh untrusted user input. It crosses into the browser's HTML parser, which htmx then reads the attribute from. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-260813-01 | Tampering | hx-vals attribute delimiter in batch_card_picker.html, transfers_step_batch.html (x2), transfers_step_dest.html, sale_name_field.html | mitigate | Switch the attribute delimiter to single-quote so tojson's guaranteed double-quoted JSON output can never truncate the attribute early; tojson's own `'`-escaping (`\u0027`) makes the single-quoted attribute unbreakable by any value these five dicts carry. |
| T-quick-260813-02 | Information Disclosure | rendered hx-vals JSON (batch_id/code/name/row) | accept | Same server-echoed values are already rendered elsewhere on the same page (product code/name in visible text, batch_id in a hidden input) before this fix — the quote-delimiter change exposes nothing new. |

</threat_model>

<verification>
- `uv run pytest tests/test_mobile_corrections.py tests/test_mobile_transfers.py tests/test_mobile_sales.py tests/test_sales.py -q` passes after Task 1 (template fix alone — proves zero regressions from the quote-delimiter change before any new tests exist).
- `uv run pytest -q` (full suite) passes after Task 2 except the 4 known-unrelated `tests/test_sync_ui.py` failures (sync_client._run_lock held by the lifespan auto-sync thread — do not attribute these to this change).
- Read-check: no remaining double-quoted tojson-driven hx-vals attribute exists anywhere under `app/templates/` (all five identified spots fixed, no sixth spot missed).
</verification>

<success_criteria>
- All five hx-vals attributes identified in the bug diagnosis render single-quoted, carrying their JSON payload intact — batch_id survives into the pick request on every affected wizard (sale/correction/write-off/transfer) and the desktop sale name-search debounce keeps working.
- Both stale WR-02 comments state the correct rule (tojson escapes `'` not `"`); the still-true hx-include-vs-hx-vals rationale in transfers_step_batch.html is preserved.
- Three new regression tests in tests/test_mobile_corrections.py and tests/test_mobile_transfers.py assert the exact single-quoted rendered attribute shape and guard against the double-quoted break ever returning.
- `app/__init__.py` `__version__` is `"1.29"`.
- Full test suite green except the 4 known-unrelated tests/test_sync_ui.py failures.
</success_criteria>

<output>
Create `.planning/quick/260813-ezt-fix-broken-hx-vals-tojson-attributes-in-/260813-ezt-SUMMARY.md` when done
</output>
