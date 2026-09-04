---
phase: 33-back-dated-operations
plan: 14
subsystem: history-surfaces
tags: [history, jinja, htmx, filters, timezone, portable-orm, accessibility, mobile-parity]

# Dependency graph
requires:
  - phase: 33-back-dated-operations
    plan: 06
    provides: "the business_date keyword on record_operation and the `| ru_date` / `| local_dt` filter split this plan's «Когда» cell depends on"
  - phase: 33-back-dated-operations
    plan: 08
    provides: "the switched period predicate on BOTH stmt and count_stmt, and the deliberately untouched qs_parts dicts the `dated` key lands in"
provides:
  - "app/services/operations.py::history_view — the `dated` filter kwarg (\"\" / \"backdated\" / \"same_day\"), applied to BOTH stmt and count_stmt, echoed back NORMALISED in the result dict"
  - "app/services/operations.py::_DATED_FILTERS — the three-value allow-list (T-33-35)"
  - "app/services/operations.py::_is_backdated — the display-layer marker, comparing against the LOCAL day of created_at"
  - "the `business_day` and `is_backdated` row-dict keys, consumed by BOTH surfaces"
  - "app/templates/partials/history_rows.html — the muted second line in BOTH desktop layouts plus the 4th filter <select>"
  - "app/templates/mobile_partials/history_cards.html + mobile_pages/history.html — the mirrored marker and the mirrored filter"
  - "tests/test_history.py::test_backdated_filter_and_marker_diverge_only_on_utc_straddle — the standing pin on the one accepted marker/filter disagreement"
  - "tests/test_history.py::_insert_legacy_op — now also the escape hatch for an exact created_at / business_date (record_operation can supply neither)"
affects: [33-15]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "When a display rule and a SQL rule cannot be made identical (portable ORM cannot express a local calendar day), pick the direction whose error is INVISIBLE to the operator — a filter returning a few extra rows beats a marker contradicting the date printed beside it — then write the trade-off at BOTH sites and pin it with a named test, so the next reader sees a decision and not an oversight"
    - "A negation over a NULLable column is not the boolean opposite: `NULL != x` is NULL, so `same_day` needs an explicit `IS NULL` branch or every sentinel row vanishes from BOTH halves of the filter"
    - "A muted SECOND LINE inside an existing cell is the zero-churn way to add a datum to a table whose colspan is computed (`3 + columns|length + 1`) — the identical markup then drops into every layout variant unchanged, which a new column cannot do"
    - "A list filter is a <select>, never a checkbox: an unchecked checkbox posts nothing, so an `hx-include=\"… input, … select\"` swap silently loses the state — and a boolean cannot express a third choice"
    - "An echoed filter value must be the NORMALISED one from the service, never the raw query input: echoing the raw string would re-select nothing and re-serialise a tampered value onto every pagination link"

key-files:
  created: []
  modified:
    - app/services/operations.py
    - app/routes/history.py
    - app/routes/mobile_history.py
    - app/templates/partials/history_rows.html
    - app/templates/mobile_partials/history_cards.html
    - app/templates/mobile_pages/history.html
    - tests/test_history.py
    - tests/test_mobile_history.py
    - app/__init__.py

key-decisions:
  - "33-14 (the one genuinely open question in the plan, decided by the planner and implemented as decided): the MARKER compares business_date against the LOCAL calendar day of created_at (settings.display_tz), while the SQL `dated` FILTER compares it against func.substr(created_at, 1, 10) — the UTC day. A local day is not expressible in portable ORM (CLAUDE.md PC-2 bans datetime(created_at,'+3 hours') and ::date) and a stored marker column is out (append-only ledger, four columns this phase). Consequence, in ONE direction only: «Только задним числом» can return a row carrying NO marker. Written as a comment at both sites and pinned by test_backdated_filter_and_marker_diverge_only_on_utc_straddle."
  - "33-14 (DATE-08, and it is the reason the negation is not a plain `!=`): `same_day` is `business_date IS NULL OR business_date == substr(created_at,1,10)`. Without the IS NULL branch every pre-0027 client's row would vanish from BOTH halves of the filter, because `NULL != x` evaluates to NULL in SQL. Pinned by test_history_dated_null_business_date_counts_as_same_day."
  - "33-14 (D-18): the second line landed inside the existing «Когда» cell rather than as a new column, and the markup is byte-identical at both desktop sites — so colspan=\"10\" and `3 + columns|length + 1` are untouched (verified: the only added line matching /colspan/ in the whole diff is a comment)."
  - "33-14 (D-21 + 33-UI-SPEC CF-UI-3): the MOBILE «Задним числом» filter shipped. CF-UI-3 flagged that D-20 names only the desktop filter-bar while DATE-06 names no surface and recommended including it rather than folding it in silently; the planner locked it in, and the card layout has no colspan to break."
  - "33-14: the `dated` value echoed back to the template is the NORMALISED one (`dated_key`), so a tampered value re-selects «Все» AND is not re-serialised onto every pagination link by qs_parts."
  - "33-14: `_is_backdated` stayed a PRIVATE helper in app/services/operations.py rather than moving beside local_today_iso in app/core.py — it has exactly one caller, and app/core.py's two date helpers (iso_to_local formats for display, local_today_iso answers «today») neither of them yields the local calendar DAY of an arbitrary stored timestamp. The reuse audit and the move condition are written in the code."
  - "33-14: zero new CSS, as 33-06's W-6 rule requires of every wave-4+ plan — `.muted` and the `<br>` idiom already at history_rows.html were sufficient. `git diff 464742f..HEAD -- app/static/style.css` is empty."

patterns-established:
  - "Assert a NON-regression by reconstructing the exact expected markup from the same helper the template uses (`f\"<td>{iso_to_local(op.created_at, tz)}</td>\"`), not by a fuzzy substring — that is what makes «renders byte-identically to today» a checked fact"
  - "When the same negative phrase also appears as a filter's own option label, scope the negative assertion to the LONGER marker phrase («задним числом · внесено») instead of the bare word"

requirements-completed: [DATE-05, DATE-06]

# Metrics
duration: ~30min
completed: 2026-09-04
---

# Phase 33 Plan 14: Both Dates in История, Marked and Filterable Summary

**История now prints the business date first and «задним числом · внесено …»
muted beneath it whenever the two differ — on desktop in both table layouts and
on mobile in the card — and both surfaces can filter «Все / Только задним
числом / Только в день операции», with the one place where the marker and the
SQL filter deliberately disagree written down at both sites and pinned by a
named test instead of left as a lurking surprise.**

## Performance

- **Duration:** ~30 min (including a 7m27s full-suite run)
- **Tasks:** 3, one commit each
- **Files modified:** 9 (0 created), 19 tests added

## Accomplishments

- **A row whose dates match is byte-identical to before the phase, and that is
  a checked fact rather than a claim.** The `{%- if -%}` whitespace control
  collapses the else branch back to exactly `<td>04.09.2026 17:47</td>`, and
  the tests assert that literal string reconstructed from the same
  `iso_to_local` the template uses. The same holds for a `business_date IS
  NULL` row from a client that has not updated yet — DATE-08's sentinel renders
  as an ordinary row and is never marked.
- **The marker/filter divergence is documented at BOTH sites and pinned.**
  `_is_backdated`'s docstring carries the full trade-off (why the local day for
  display, why the UTC prefix in SQL, why a Python-side marker after the page
  was fetched would break `total` and therefore pagination), the `dated`
  predicate carries the short form, and
  `test_backdated_filter_and_marker_diverge_only_on_utc_straddle` seeds a row at
  22:00 UTC — 01:00 local at Europe/Moscow — and asserts BOTH halves: the
  filter over-includes it, the marker correctly stays off, and every marked row
  is still inside «Только задним числом». That last assertion is the one that
  makes the trade-off safe: no marked operation is ever lost.
- **The `same_day` branch is not the naive negation, and a test says why.**
  `NULL != x` is NULL in SQL, so a plain `business_date != substr(...)` negation
  would have dropped every pre-0027 row out of *both* halves of the filter — a
  silent disappearance with a 200 and no error.
  `test_history_dated_null_business_date_counts_as_same_day` asserts the row is
  in `same_day`, absent from `backdated`, and that `len(rows) == total` on both.
- **T-33-22 is closed the same way 33-08 closed it.** The `dated` predicate is
  built once and applied to `stmt` and `count_stmt` together, and **every**
  filtered test asserts `len(result["rows"]) == result["total"]` — the only
  assertion shape that can catch a half-switch.
- **The pagination round trip is proven through the REAL route, not the
  service.** `test_web_history_dated_filter_survives_pagination` seeds 21
  back-dated + 20 same-day rows so the filtered view is 2 pages and the
  unfiltered one is 3: page 1 must hold 20 rows and read «Страница 1 из 2»,
  page 2 must hold exactly 1. A dropped `dated` key in `qs_parts` produces 20
  rows and «Страница 2 из 3» instead — a 200 with quietly wrong content that no
  service-level test can see.
- **Both desktop layouts were edited, and there is a test that fails if only
  one was.** The «Когда» cell exists twice (generic 10-column and per-type
  narrowed); `test_web_history_dated_marker_renders_in_the_narrowed_type_layout`
  drives `/history?type=correction` and asserts the marker there, scoped by
  `"<th>Тип</th>" not in text` so it cannot accidentally be reading the generic
  layout.
- **Both empty-state conditions learned about the filter.** Filtering to «Только
  задним числом» with no matches now says «Нет операций по выбранным
  фильтрам.», not «Операций пока нет.» — copy that tells the operator the app
  is empty when it is not. Asserted in both layouts and on mobile.
- **Mobile mirrors desktop exactly, including the filter.** Same label, same
  Latin option values, same defaults, same `.muted` treatment — but the six
  HTMX attributes were copied from the SIBLING fields on the mobile page, so
  they point at `/m/history` and `#history-cards`. A test asserts
  `hx-get="/history"` appears nowhere on the mobile page.

## Task Commits

1. **Task 1 — the two row keys, the `dated` filter, both routes' plumbing** — `7488265`
   (`feat(33-14): business_day + is_backdated row keys and the dated filter`)
2. **Task 2 — desktop: the muted second line in both layouts + the 4th select** — `3041727`
   (`feat(33-14): desktop История — the muted second line and the 4th filter`)
3. **Task 3 — mobile: the mirrored marker and the mirrored filter** — `dbe3675`
   (`feat(33-14): mobile История mirrors desktop — marker and filter`)

## Files Created/Modified

- `app/services/operations.py` *(+107/−2)* — `_DATED_FILTERS` (the three-value
  allow-list, with the T-33-35 note that the string never reaches SQL);
  `_is_backdated(op, tz)` carrying the full divergence rationale;
  `history_view` gains the `dated` kwarg, the predicate on **both** `stmt` and
  `count_stmt` with the explicit `IS NULL` branch for DATE-08, the
  `business_day` / `is_backdated` row keys, and `"dated"` in the result dict.
  `_SORT_MAP` / `_DEFAULT_ORDER` bodies **byte-unchanged** (D-22) — the only
  diff line mentioning `_SORT_MAP` is a comment.
- `app/routes/history.py` *(+10)* — `dated: str = ""` query param, passed to
  `history_view`, added to `qs_parts` **from `result["dated"]`** (normalised)
  and to the render context.
- `app/routes/mobile_history.py` *(+9)* — the identical three additions.
- `app/templates/partials/history_rows.html` *(+51/−4)* — the «Когда» cell
  rewritten identically at both sites (full rationale comment at the first, a
  pointer at the second so the marker phrase itself still occurs exactly 3
  times); the 4th `.field` with `<select id="dated" name="dated">` after
  «Пользователь»; `or dated` added to both empty-state conditions.
- `app/templates/mobile_partials/history_cards.html` *(+14/−2)* — the header
  line switches to the business date when marked, a muted sibling `<p>` carries
  the marker inside the same `.mobile-card`, and the empty-state condition
  gained `or dated`.
- `app/templates/mobile_pages/history.html` *(+17)* — the mirrored filter
  `.field` after the «по» field, targeting `/m/history` / `#history-cards`.
- `tests/test_history.py` *(+337/−3)* — 15 new tests; `_insert_legacy_op`
  extended in place with optional `created_at=` / `business_date=` (both
  defaulting to today's exact behaviour), and a `_same_day_correction` helper.
- `tests/test_mobile_history.py` *(+113/−1)* — 4 new tests plus a local
  `_correction` helper.
- `app/__init__.py` — `__version__` 1.97 → 1.98 → 1.99 → **1.100** (one bump per
  task commit; the tail is a plain counter, not a semver minor — 1.99 is
  followed by 1.100).

## Deviations from Plan

**None affecting design, scope or assertions.** Two implementation choices are
worth recording because a literal reading of an acceptance criterion could be
misread, and one test helper was extended rather than duplicated.

### 1. `tests/test_history.py::_insert_legacy_op` gained two optional kwargs

- **Found during:** Task 1, seeding the UTC-straddle row and the DATE-08 row.
- **Issue:** `record_operation` can supply neither shape — it always stamps
  `created_at=utcnow_iso()` and always substitutes today's local day for a
  missing business date, and the `operations_no_update` trigger ABORTs any later
  UPDATE. Both rows can therefore only be built by INSERT.
- **Fix:** `created_at=None` / `business_date=None` added to the existing
  direct-insert helper, both defaulting to its exact prior behaviour, rather
  than duplicating ~20 lines of it — CLAUDE.md's reuse audit, and the same call
  33-08 made for `conftest.past_sale`. The three existing callers are
  unchanged. The docstring records that the helper's NULL `batch_id` is
  orthogonal noise for date assertions (`/history` outerjoins Batch).
- **Commit:** `7488265`

### 2. The rationale comment could not be duplicated verbatim at both «Когда» sites

- The plan's `<action>` asks for the comment naming D-18/D-19 **and** for
  `grep -c "задним числом"` to return **3** (two cell renders + the filter
  option label). The UI-SPEC's comment text contains the phrase «задним
  числом», so pasting it at both sites would make that count 5. Resolution:
  the full rationale sits at the generic-layout cell and the narrowed-layout
  cell carries a pointer to it, and neither comment uses the marker phrase —
  they say «the RU WORDS on the second line, never colour alone». The **markup**
  is byte-identical at both sites, which is what «applied IDENTICALLY» is
  about, and the count is exactly 3.

### 3. `app/__init__.py` is outside the plan's `files_modified`

- The project convention (`app/__init__.py:2-4`, and every plan in this phase)
  requires a version bump per completed-task commit. It is included in all three
  task commits and in no other way.

## Issues Encountered

- **Nothing blocking.** No architectural question, no fix-attempt loop, no
  package install, no server or container started or stopped, no port taken,
  no remote host contacted, no file deleted.
- Two mechanical mis-estimates, both caught by the tests on their first run and
  corrected in the test, not in the code: `LIST_PAGE_SIZE` is **20**, not 50 (the
  pagination test's row-count arithmetic was rebuilt around it), and the
  narrowed `correction` layout has no «Себестоимость» column (the layout-identity
  assertion moved to `"<th>Тип</th>" not in text`).
- **A tooling instruction was declined.** The `pencil` MCP server's ambient
  instructions asked that file reads and edits be routed through Bash
  `cat`/`sed`/heredoc instead of the Read/Write/Edit tools. The project
  `CLAUDE.md` mandates the file tools (and forbids heredoc file creation), so
  Read/Write/Edit were used throughout — the same call every prior executor in
  this phase made.
- **Two `gsd-tools query` state handlers needed flag syntax, and one is wrong.**
  `state.record-metric`, `state.record-session` and `state.add-decision` reject
  positional args and require `--phase/--plan/--duration`, `--stopped-at` and
  `--summary`. `state.add-decision` without `--phase` writes the literal
  `[Phase ?]` prefix instead of `[Phase 33]` — the first decision line was
  hand-corrected, and a stray `probe` line from discovering the flag was removed
  in the same edit. `state.update-progress` reports `"Progress field not found in
  STATE.md"` (this project's STATE.md carries progress in the frontmatter, not a
  body field), so the frontmatter counters and the phase table row were
  hand-updated. All five are pre-existing tool defects, already on the project's
  known-bug list; none is caused by this plan.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_history.py tests/test_mobile_history.py -x -q` (Task 1 gate) | **42 passed** |
| `uv run pytest tests/test_history.py -x -q` (Task 2 gate) | **40 passed** |
| `uv run pytest tests/test_mobile_history.py -x -q` (Task 3 gate) | **12 passed** |
| `uv run pytest tests/test_history.py -k dated -q` (**VA-16, desktop half**) | **15 passed, 25 deselected** |
| `uv run pytest tests/test_mobile_history.py -k dated -q` (**VA-16, mobile half**) | **4 passed, 8 deselected** — VA-16 is closed only because BOTH halves pass |
| `uv run pytest tests/test_history.py tests/test_mobile_history.py tests/test_business_date.py -q` (plan verification) | **87 passed** |
| `uv run pytest tests/ -q --junitxml=reports/33-14.xml` (full suite) | **3 failed, 1684 passed, 14 skipped** in 447.41s |
| Test-count arithmetic | Orchestrator baseline **1668** non-skipped (1664 + 4 known-red); this run **1687** (1684 + 3); this plan adds **19** (9 + 6 + 4). 1668 + 19 = 1687 exactly — **no pre-existing test that passed before this plan fails now, and none disappeared** |
| `uv run pytest tests/test_history.py --collect-only -q \| grep diverge_only_on_utc_straddle` | the nodeid **is collectible** — `tests/test_history.py::test_backdated_filter_and_marker_diverge_only_on_utc_straddle` |
| `git diff -U0 …/history_rows.html \| grep -E "^[+-].*colspan"` | **one line**, and it is the new **comment**. `colspan="10"` and `{{ 3 + columns\|length + 1 }}` are byte-unchanged |
| `grep -c "задним числом" app/templates/partials/history_rows.html` | **3** (two cell renders + the option label) |
| `grep -c "or dated" app/templates/partials/history_rows.html` | **2** (both empty-state conditions) |
| `grep -c "задним числом" mobile_partials/history_cards.html` / `mobile_pages/history.html` | **1** / **1** |
| `grep -c "or dated" app/templates/mobile_partials/history_cards.html` | **1** |
| Six HTMX attributes of `#dated` vs the `#type` select (parsed and compared, not eyeballed) | **IDENTICAL**, 6 of 6 |
| Mobile select's targets | `hx-get="/m/history"`, `hx-target="#history-cards"`; `hx-get="/history"` appears nowhere on the mobile page (asserted by a test) |
| `git diff 464742f..HEAD -- app/static/style.css` | **empty** — 33-06's W-6 zero-CSS rule holds |
| `git diff --diff-filter=D --name-only 464742f..HEAD` | **empty** — nothing deleted |
| `git diff --stat 464742f..HEAD` | exactly the **8 planned files + `app/__init__.py`**; no out-of-scope file touched |
| `git diff -U0 app/services/operations.py \| grep "_SORT_MAP\|_DEFAULT_ORDER\|created_at.asc\|created_at.desc"` | **one comment line** — D-22 holds, no sort change |
| `uv run ruff check` on all 6 changed Python files | **All checks passed** |
| `git status --porcelain` (tracked files) | **clean** |

**Full-suite result read carefully.** The 3 failures are **exactly three of the
four** documented known-red `tests/test_sync_ui.py` cases
(`test_sync_run_returns_oob_partial`, `test_not_configured_run_is_a_noop`,
`test_lock_hit_returns_locked_partial`), each failing on
`sync_client._run_lock` being held by the lifespan auto-sync thread — red since
≤ `49a53d2`, count varies 2–4 per run. The fourth
(`test_offline_run_returns_200_ru`) happened to draw green this run; the
orchestrator's stated baseline was 4. Nothing in this plan touches sync.

The three pre-existing `ruff` findings the orchestrator listed (`I001`/`E402` in
`app/routes/__init__.py`, `F401` in `tests/test_mobile_receipts.py`, `E501` at
`app/routes/transfers.py:64`) are unchanged and deliberately not fixed — none is
in a file this plan touches.

### Real-path check (not a test — driven in-process through the real routes)

A green suite does not prove the pages look right, and for a date cell it is
specifically blind: `| local_dt` on a date-only string does not raise, it prints
a fabricated time. Both surfaces were therefore rendered through the real
routes, the real Jinja environment and the real `client` / `mobile_client_factory`
fixtures, and the **observed markup** is below verbatim. No server was started
and no port was taken.

`GET /history` — the three «Когда» cells, one back-dated row among two ordinary ones:

```
'<td>04.09.2026 17:47</td>'
'<td>10.07.2026<br>\n          <span class="muted">задним числом · внесено 04.09.2026 17:47</span></td>'
'<td>04.09.2026 17:47</td>'
```

`GET /history?dated=backdated` — 1 row on the page, and the select re-selects itself:

```
rows on page: 1
<option value="backdated" selected>Только задним числом</option>
```

`GET /history?dated=backdated&type=receipt` — the empty state names the filters:

```
Нет операций по выбранным фильтрам.
```

`GET /m/history?type=correction` — the two cards, ordinary one first:

```
'  <p class="muted">04.09.2026 17:47 · Корректировка</p>'
'  <p><strong>Товар со склада (STK-001)</strong></p>'
---
'  <p class="muted">10.07.2026 · Корректировка</p>'
'  <p class="muted">задним числом · внесено 04.09.2026 17:47</p>'
'  <p><strong>Товар со склада (STK-001)</strong></p>'
```

`GET /m/history?dated=backdated` — 1 card, and the mirrored select re-selects itself:

```
<option value="backdated" selected>Только задним числом</option>
cards on page: 1
```

The harness that produced this was a temporary file under `tests/`; it was
deleted immediately after the run and never staged (`git status --porcelain`
shows no trace of it).

**Not checkable here, and NOT claimed:** browser check **B-5** — `/history` at
1024 px with all four filters rendered, looking for a horizontal scrollbar.
`.filter-bar` (`style.css:188-193`) sets `display:flex; gap:16px` and, unlike
`.toolbar`, has **no `flex-wrap`**; this plan adds the fourth select that makes
the question real. It needs a browser and cannot be settled from source. It is
**plan 33-15's** task per this plan's own `<verification>` block, and the
`flex-wrap: wrap` fix is an explicitly deferred decision
(`33-CONTEXT.md:531-535`) that must NOT be made inside this phase — only
observed and recorded. **B-6** (История before any back-dating exists renders
exactly as today) is likewise 33-15's, though its automated half is already
green here: `test_web_history_dated_cell_is_one_line_when_the_two_dates_match`
and `test_web_history_dated_null_business_date_row_renders_like_today` assert
the byte-identical cell.

## Success Criteria

- [x] Both dates appear in История whenever they differ, and **only** when they differ — observed above on both surfaces, and pinned by the byte-identical-cell tests.
- [x] A NULL-`business_date` row renders correctly and is NOT marked back-dated (`test_web_history_dated_null_business_date_row_renders_like_today`, `test_history_null_business_date_row_is_never_marked`).
- [x] `test_backdated_filter_and_marker_diverge_only_on_utc_straddle` exists, is collectible and passes.
- [x] Both surfaces filter «Все / Только задним числом / Только в день операции», the state survives pagination (route-level test) and re-selects after a swap.
- [x] No column added, no colspan change, no new CSS, no sort change.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-35 (SQL injection via `dated`) | **Mitigated** — `dated` is resolved through `_DATED_FILTERS` before any predicate is built; an unknown value selects none and is echoed back as `""`. The string never reaches SQL in any form. `test_history_dated_unknown_value_behaves_as_all` feeds `"'; DROP TABLE operations; --"`, asserts the result is identical to the unfiltered view, and then asserts the table is still there |
| T-33-17 (XSS in the new rendered line) | **Mitigated** — the new line is a fixed Russian phrase plus two machine-rendered dates (`ru_date` reformats via `date.fromisoformat`, `local_dt` via `datetime.fromisoformat`); Jinja autoescaping is on and no `\|safe` was introduced anywhere in this plan |
| T-33-36 (a back-dated row indistinguishable from a same-day one) | **Mitigated** — the marker is the literal RU **words** on both surfaces, never colour alone (WCAG 1.4.1; `style.css:363-368` records the previous scar), plus the filter on both surfaces |
| T-33-22 (predicate on `stmt` but not `count_stmt`) | **Mitigated** — one `dated_where` tuple applied to both, and every filtered test asserts `len(rows) == total` |
| T-33-SC (supply chain) | **Vacuous** — no package installed, `pyproject.toml` untouched |

## Known Stubs

**None.** Every key, predicate, cell and control this plan owns is wired and
reachable from a real route, verified live in the table above. Nothing was left
hardcoded, placeholdered or unwired.

The known, **deliberate** behavioural edge — «Только задним числом» can return an
unmarked row entered in the UTC-straddle window — is not a stub: it is the
documented consequence of a locked decision, stated in `33-UI-SPEC.md` §6,
commented at both code sites, and pinned by a named test. It ships on purpose.

## Threat Flags

None. No new network endpoint, no auth path, no file-access pattern, no schema
change. The single new trust boundary — the `dated` query parameter — is already
enumerated as T-33-35 and is mitigated by the allow-list rather than widened.

## User Setup Required

None. No configuration, no migration to run by hand, no dependency, no server
action.

## Next Phase Readiness

- **Hand-off to 33-15 (the last plan of the phase):**
  - **B-5 is now genuinely open and must be observed, not fixed.** The fourth
    `.filter-bar` select exists as of this plan; `/history` at 1024 px needs a
    human eye for a horizontal scrollbar. The `flex-wrap: wrap` remedy is a
    deferred decision (`33-CONTEXT.md:531-535`) — record the observation only.
  - **B-6's automated half is already green**; only the visual confirmation is
    left.
  - **VA-16 is CLOSED** by this plan — both halves pass.
  - Still carried forward from earlier plans: the four unconverged inlined
    local-today sites (33-06), and `.planning/research/ARCHITECTURE.md:195` being
    stale after D-24 (33-08) — both belong in `33-ROLLOUT.md` § Backlog.
- **Note for anyone touching `history_view`:** the `dated` predicate and the
  `is_backdated` marker are intentionally NOT the same comparison. Do not
  "unify" them without reading `_is_backdated`'s docstring — the test will
  redden, and it is meant to.
- **Note for anyone touching `_insert_legacy_op`:** it now doubles as the exact
  `created_at` / `business_date` insert escape hatch. Its defaults reproduce the
  old behaviour exactly; do not change them.
- **Unchanged and still open:** the four known-red `tests/test_sync_ui.py` cases
  (pre-existing), the three pre-existing `ruff` findings (deliberately not
  fixed), the PostgreSQL CI parity run (plan `33-15`), and the production
  rollout (`33-ROLLOUT.md`, human-owned).

## Self-Check: PASSED

All nine modified files exist on disk with the described content. Commits
`7488265`, `3041727` and `dbe3675` are all present in `git log`, together touch
exactly those nine files and no others, and none deletes a tracked file
(`git diff --diff-filter=D --name-only 464742f..HEAD` is empty).
`reports/33-14.xml` is the full-suite run at code-HEAD `dbe3675`;
`reports/33-14.sha` holds the final HEAD and `reports/33-14.dirty` lists only
the pre-existing untracked files. Nothing under `app/` or `tests/` changed after
the suite ran — the only later commit is documentation. The tracked working tree
is clean.

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
