---
phase: 33-back-dated-operations
fixed_at: 2026-09-05T00:00:00Z
review_path: .planning/phases/33-back-dated-operations/33-REVIEW.md
iteration: 3
fix_scope: critical_warning
findings_in_scope: 8
fixed: 7
skipped: 1
status: partial
suite: 1812 passed, 16 skipped, 0 failed
version: 1.124 -> 1.132
---

# Phase 33: Code Review Fix Report

**Fixed at:** 2026-09-05
**Source review:** `.planning/phases/33-back-dated-operations/33-REVIEW.md` (iteration 3)
**Iteration:** 3
**Base commit:** `1adc3c8` → **head after fixes:** `9589df8`

---

## Iteration 1 recap (do not lose this)

Iteration 1 ran with `fix_scope: critical_warning` — 9 findings in scope, **7 fixed,
1 partial, 1 skipped**, `1.101 → 1.110`, head `12c1611`, report committed as `208bf45`.

| Prior finding | Outcome in iteration 1 |
|---|---|
| CR-01 wire `business_date` + `format_ru_date` | fixed (`a471ca6`, `1d3bd4d`) |
| WR-02 `push_schema_ok` TypeError | fixed (`3d73b07`) |
| WR-03 409 echo | fixed (`df7f337`) |
| WR-04 naive `created_at` in `_is_backdated` | fixed (`9fc0b19`) |
| WR-06 `isascii()` in `register_receipt` | fixed (`781b8b7`) |
| WR-07 `StopIteration` in `register_sale` | fixed (`e918fa7`) |
| WR-08 downgrade trigger DDL asserted | fixed (`99522b1`) |
| WR-05 dated-filter trade-off | **partial** (`12c1611`) — documentation only, behaviour deliberately unchanged; re-raised in iteration 2 as WR-09 and again in iteration 3 as WR-06 |
| WR-01 `parse_op_date` past bound | **skipped** — needs an operator decision (floor value + a third RU string). **Escalated to CR-01 in iteration 3 and FIXED there** — see below |

IN-01..IN-06 were declared out of scope in iteration 1.

---

## Iteration 2 recap (do not lose this)

Iteration 2 ran with `fix_scope: all` — 18 findings in scope (CR-01, WR-01..WR-09,
IN-01..IN-08), **13 fixed, 1 partial, 4 skipped**, `1.110 → 1.124`, base `db12d31`,
head `43c2925`, suite **1784 passed / 16 skipped / 0 failed**.

| Prior finding | Outcome in iteration 2 |
|---|---|
| CR-01 `iso_to_local` raised on a wire `created_at`; naive read in the OS zone | fixed (`8f6ee9e`) — wire gate `_is_iso_timestamp` + never-raises display; 28 tests |
| WR-02 schema gate's two halves cancel | fixed (`a892a73`) — **documentation only**, `isinstance` branch deliberately KEPT as a crash backstop |
| WR-03 date gate missed `Batch.expiry` | fixed (`c2df0b6`) — 9 tests |
| WR-04 CSV column 1 outside `_csv_safe` | fixed (`9e86506`) — 5 date cells wrapped; `op.created_by` explicitly declined, **re-raised and fixed in iteration 3 as WR-04** |
| WR-05 `register_return` None guard | fixed (`9517ed1`) — lookup also moved inside `if debit:` |
| WR-06 `register_transfer` None guard | fixed (`16254c6`) |
| WR-07 revision-id tripwire glob | fixed (`1571fd0`) — `*.py`, floor 27 |
| WR-08 `.filter-bar` `flex-wrap` | fixed (`bd6d0b1`) — **still unverified in a browser** |
| IN-01 `local_day_bounds_utc` caller list | fixed (`dd6b9fd`) |
| IN-02 `POST /m/transfers/step/dest` dropped a date | fixed (`9c891ef`) — a tripwire on a DEAD route; **the reachable path stayed broken and is iteration 3's WR-03** |
| IN-04 invalid `op_date` blanked the date input | fixed (`30d19e9`) — `core.date_input_value` + the `op_date_value` Jinja global, 11 templates, 13 tests |
| IN-05 unbounded `getattr` in the Alembic helper | fixed (`54ffbc6`) |
| IN-07 `\d` matched non-ASCII digits | fixed (`254305c`) |
| IN-08 reversal ORM FK vs migration 0027 | **partial** (`43c2925`) — documented in `models.py` only; **re-raised as iteration 3's WR-07 and FIXED there** |
| WR-01 `parse_op_date` past bound | **skipped** — operator decision |
| WR-09 «Только в день операции» straddle | **skipped** — operator decision |
| IN-03 no DB-level date shape constraint | **skipped** — needs revision `0028` against a live production database |
| IN-06 four near-identical period resolvers | **skipped** — refactor-mode work needing an explicit scope |

---

## Summary — iteration 3

- Findings in scope: **8** (CR-01, WR-01..WR-07). The five IN-* items were out of
  scope for this pass by instruction.
- Fixed: **7**
- Skipped: **1** (WR-06)

Three of the seven were findings earlier iterations had deferred (CR-01 was
iteration 1+2's WR-01; WR-04 was declined in iteration 2; WR-07 was iteration 2's
partial IN-08). All three are now closed.

### Verification actually run (not inferred)

- **Full suite, at the final HEAD `9589df8`, with a clean working tree:**
  **1812 passed, 16 skipped, 0 failed** (466 s / 7m46s).
  Iteration 2's baseline was 1784 passed; the delta is **exactly the 28 tests
  added here** (CR-01 8, WR-01 4, WR-02 8, WR-03 4, WR-04 2, WR-05 1, WR-07 1).
- **The 4 known-flaky `tests/test_sync_ui.py` failures named in the brief DID NOT
  REPRODUCE**, exactly as in iterations 1 and 2. Nothing here touches
  `sync_client._run_lock` or the lifespan auto-sync thread, so their absence is
  an ordering/environment artefact, not a repair.
- **One earlier full-suite run is reported as INVALID and is not the number
  above.** A first run finished `1 failed, 1811 passed` on
  `test_release_verify.py::test_build_asserts_tag_matches_version`. That failure
  was self-inflicted, not a regression: I edited `app/__init__.py` (1.131 → 1.132)
  while that run was executing, and the test compares `app.__version__` (cached
  from the module imported at collection time) against
  `build_release._read_version()` (which re-reads the file from disk). The whole
  suite was re-run afterwards against an untouched tree; it passes there.
- **`ruff check` on all 22 touched `.py` files: 3 errors, and all 3 are
  pre-existing.** Measured by extracting the base-commit (`1adc3c8`) versions of
  the offending files and running ruff against them, not inferred:
  - `app/routes/__init__.py` I001 (import block unsorted) and E402 — both present
    at `1adc3c8`;
  - `tests/test_export.py:333` E501 (102-char docstring) — present at `1adc3c8`.
  One NEW error was introduced and then fixed inside this iteration: WR-01's
  rationale comment sat between two imports and tripped I001 in
  `app/services/finance.py`; commit `9589df8` moved the rationale into the
  function docstring. Project-wide `ruff check` / `ruff format --check` are not
  gates this repo passes today and were not touched.
- Every fix was re-read after editing and its own test modules run green before
  the commit.
- **WR-07's claim was verified by execution, not asserted**: the new test compiles
  `CreateTable` for both ledger tables against the SQLite dialect and asserts no
  `REFERENCES` clause on either reversal column — the inverse of the same probe
  iteration 2 used to prove the divergence existed.

### Pending human checks (NOT verified here)

1. **WR-08 from iteration 2 (`.filter-bar` `flex-wrap`)** — still open, still
   unverified. There is no browser in this environment. **Open `/history` at
   1024 px and confirm there is no horizontal scrollbar and no clipped fourth
   `<select>`.**
2. **Iteration 2's CR-01 `created_at` intake gate against a REAL client push** —
   still open. Worth one live push from a real `0027` client before the client
   release tag, which is the same gate the phase's UAT is already blocked on.
3. **WR-01's two cash surfaces have not been LOOKED AT.** The marker is proven by
   four tests through the real routes, but nobody has seen the rendered table or
   the mobile cards. The desktop change adds a `<br>` + muted second line inside
   an existing `<td>` — the same markup `/history` already ships — so the risk is
   low, but the mobile card gains a second `<p class="muted">` line and that is a
   layout change on a 4-line card.
4. **WR-03's two wizards have not been TAPPED.** The round trips are pinned by
   tests that issue the exact requests the buttons issue, but the htmx wiring
   itself (does «Назад» really include the form? does the batch card's `hx-vals`
   really carry the new key?) was read, not observed. This is the one fix where a
   two-minute manual walk-through on a phone would add real information.
5. **WR-05 is a behaviour change on live data semantics.** A back-dated receipt
   now dates its `product_created`/`price_change` audit rows TODAY. If the
   operator has been relying on the old inheritance for anything, this changes
   what `/history` shows for those rows. It is the right default and the review
   asked for it, but it is a judgement worth confirming.

---

## Fixed Issues

### CR-01: `parse_op_date` bounded the future but not the past

**Commit:** `0e37369` — **requires human verification** (it introduces a new refusal path)
**Files:** `app/services/ledger.py`, `app/routes/__init__.py`, 11 templates,
`tests/test_business_date.py`, `33-UI-SPEC.md`

Deferred in iterations 1 and 2 as an operator decision; the review escalated it to
BLOCKER and separated the two questions that had been conflated. The deferral was
about picking a **business** floor («how far back may the operator book?»). The
year-typo class needs no business decision at all.

`OP_DATE_FLOOR = date(2000, 1, 1)` is a **sanity** floor, chosen precisely because
it can never refuse a legitimate entry — the oldest artefact this project knows of
is a 2013 price list. It catches every `"0226-09-04"` / `"0026-09-04"` shape that
the existing **lexicographic** future check lets through (`"0226-09-04" >
"2026-09-05"` is `False`). Such a row is written to an append-only table the
application can never repair, vanishes from every `business_date`-scoped report,
and still counts in `Product.quantity`.

Two details worth reading:

- **The floor is compared as a `date`, not as text, and is checked FIRST.** The
  text comparison is exactly what could not see the typo, so reusing it would have
  reproduced the bug.
- **`min=` is derived from the constant via one Jinja global**
  (`OP_DATE_FLOOR_ISO`), not hardcoded into 11 templates, so the browser hint and
  the server guard cannot drift. It is placed **before** `value=` in the tag so the
  `value="X" max="X"` adjacency that **14 existing route tests assert** stays
  intact — the first attempt split those onto separate lines and would have
  reddened all 14.
- The three mobile SHELL wizards deliberately get **no** `min=`: neither attribute
  fires there (`hx-post` sits on the button and htmx `preventDefault()`s the
  click), so adding one would make the hole look closed. A test asserts they do
  not gain it.

`33-UI-SPEC.md` § Copywriting Contract gained the third RU string and a
field-bounds row **in the same commit**, as the review required.

**Still open, deliberately:** the BUSINESS floor. When the operator answers «how
far back may I book?», that changes this constant's value, not its mechanism, and
not this copy. A test (`test_op_date_floor_is_a_sanity_bound_not_a_business_policy`)
is the tripwire for anyone raising the floor without asking.

**Tests added:** 8.

### WR-01: cash-movement history rendered `created_at` only

**Commit:** `89066b6`
**Files:** `app/core.py`, `app/services/operations.py`, `app/services/finance.py`,
`app/templates/partials/cash_history_rows.html`,
`app/templates/mobile_partials/cash_history_cards.html`, `tests/test_finance.py`,
`tests/test_history.py`, `33-UI-SPEC.md`

Took the review's **first** option — generalise the marker — rather than growing a
second definition in `finance.py`. `operations._is_backdated(op, tz)` became public
`is_backdated(business_date, created_at, tz_name)`, and its naive==UTC / malformed
rules moved into `core.local_day_of`. That move was not invention: the old
function's own comment said to move it «beside `local_today_iso` if a second caller
ever appears», and WR-01 and WR-02 are the second and third callers.

The flag is computed in `cash_history_view`, not in the template, for the reason
`history_view` does the same: a template-side marker cannot be filtered or counted.
`rows` are now `{mv, business_day, is_backdated}` dicts, matching `/history`.

Migration `0027` keeps its own private copy of the rule ON PURPOSE — a migration
must not import application code that will keep changing under it.

**Deviation worth stating:** four existing assertions in `test_finance.py` read
`rows` as bare `CashMovement`s and were updated with the shape change. That is a
test-contract change, not a test weakening — the same four facts are asserted.

**Tests added:** 4 (service-level row contract including the DATE-08 NULL
sentinel; desktop marked; desktop unmarked; mobile both ways). Two existing
`_is_backdated` unit tests moved to the new signature, which let their
`SimpleNamespace` fake disappear entirely.

### WR-02: `reports.stale_products` read a naive `created_at` in the OS zone with no parse guard

**Commit:** `d7bcc8d`
**Files:** `app/services/reports.py`, `tests/test_reports.py`, `tests/test_core.py`

Routed through `core.local_day_of` so there is no fourth copy of the rule. Both
defects the review named were reachable: `astimezone()` on a naive value reads the
**machine's** zone (on s1 — OS zone UTC, `display_tz` Europe/Moscow — that is up to
a day of drift for any merged naive row, while every sibling reader was correct),
and the missing `try` made a poisoned pre-0027 row a permanent 500 on
`/reports/products`.

**D-25 is NOT reopened.** The function still answers «how long since this product
last MOVED» from `created_at`, never `business_date`. Only the way it reads that
column changed, and the docstring says so.

An unreadable row is **skipped**, not reported with a fabricated «дней без
продажи» — unlike the marker's 10-char fallback, an invented number here would be
worse than an absent row, because this list exists to be acted on. Stated at the
call site.

**Honest limitation, recorded in the test's own docstring:** the naive-vs-aware
equivalence test through `stale_products` is **vacuous on a host whose OS zone is
UTC**, because there the old code satisfied it by accident. That is why three
additional `core.local_day_of` unit tests were added: they pass the zone
explicitly and are host-independent.

**Tests added:** 8 (2 through `stale_products`, 6 on `core.local_day_of`).

### WR-03: both mobile wizards silently reset a typed back-date on «Назад»

**Commit:** `6f6abbe`
**Files:** `app/routes/mobile_corrections.py`, `app/routes/mobile_transfers.py`,
7 templates, `tests/test_mobile_corrections.py`, `tests/test_mobile_transfers.py`,
`33-UI-SPEC.md`

**Scope beyond the review's list, and why.** The review named `step/mode` +
`step/value` for корректировка and `batch_pick` + the «Назад» `hx-vals` for
перемещение. That list could not have worked on its own: without step 2 carrying
`op_date`, nothing reaches `batch-pick` at all. And stopping one step short only
moves the same silent reset one tap further back. `op_date` is therefore threaded
through **every** step of both wizards — hidden input where the step has a
`<form>`, `hx-vals` where it does not (перемещение's step 2), single-quoted per the
standing `| tojson` note.

**Two tests were DELIBERATELY INVERTED, not deleted.**
`test_*_earlier_steps_never_emit_the_date` asserted the exact opposite of this
fix, and their docstrings even predicted it («a future edit that threads it as a
hidden field reddens this test»). Their reasoning had the failure mode backwards:
the risk was never a **stale** date, it was a silently **fabricated** one. They now
pin the half of D-11 that still holds — earlier steps carry the value and render
**no** date input, so there is still exactly one editable date per wizard. Each
inverted test says in its docstring what it used to assert and why that was wrong.
`33-UI-SPEC.md` rows 12–13, whose «terminal with no accumulator round-trip» claim
is what produced the defect, carry the correction inline.

**Tests added:** 4 (a forward → «Назад» → forward round trip per wizard, plus a
cold-entry-still-defaults-to-today guard per wizard); 2 inverted; 1 `hx-vals`
quoting assertion updated for the second key.

### WR-04: `created_by` was the last unescaped free-text CSV cell, and it is wire-supplied

**Commit:** `137e8f7`
**Files:** `app/services/export.py`, `tests/test_export.py`

Iteration 2 saw this and declined it as «pre-existing and unrelated». Defensible on
scope, but it was neither carried into a finding nor tracked anywhere, so the
review raised it again; closed here. `merge._LEDGER_REQUIRED` carries `created_by`
verbatim from a pushed NDJSON record and `_ledger_row` bulk-inserts it, so a device
holding a valid Bearer token controls those bytes and the append-only triggers then
make the row unrepairable.

`row_currency` and `movement.currency` were wrapped too: both are checked against
`CURRENCIES` on the **local** write path but not by `parse_exchange`, which
type-checks only money, `seq`, dates and timestamps.

All three are output-identical for every well-formed value. The `format_cents`
money columns stay unwrapped ON PURPOSE and now have a test saying so — a negative
amount legitimately starts with `-`, so wrapping those WOULD change real output.

**Tests added:** 2.

### WR-05: a back-dated receipt stamped the operator's date onto the audit rows

**Commit:** `5450a19` — **requires human verification** (a semantic change to what /history shows)
**Files:** `app/services/receipts.py`, `tests/test_receipts.py`

`business_date=None` on the two audit calls, so `record_operation` stamps the real
local day. `resolved_business_date` stays on the `receipt` op and on the D-24 batch
auto-name, which really do describe the movement.

The review's reading was confirmed against the phase's own artefacts:
`33-10-SUMMARY.md` records this as «`business_date=resolved_business_date` on all
three `record_operation` calls» — mechanical, with no decision behind it. D-25
reasoned about which **readers** stay on `created_at`; nothing decided it for audit
**writes**. Every sibling service already draws the line the same way.

**One existing test was DELIBERATELY INVERTED**, not deleted:
`test_backdated_receipt_stamps_business_date` asserted the date landed on «BOTH ops
it writes». Its docstring now says why that was wrong. `price_change` had **no**
coverage at all; it has a test now, which asserts the receipt row and the audit row
**together**, so the split itself is what is pinned rather than one side of it.

**Tests added:** 1; 1 inverted.

### WR-07: `reverses_*_id` carried an ORM `ForeignKey` migration 0027 does not create

**Commit:** `5cc8bea`
**Files:** `app/models.py`, `tests/test_migrations.py`

Iteration 2 closed this as documentation-only, reasoning that neither option was a
review fix. The review disagreed and asked for the decision to be taken **before**
Phase 34 writes its first reversal. Taken here, and it turned out to be
decision-free once one claim was checked rather than trusted:

**The «merge insert-ordering» the ForeignKey was documented as providing did not
exist.** `merge._LEDGER_INSERT_ORDER` and `_REFERENCE_INSERT_ORDER` are hardcoded
tuples of KINDS, not derived from ORM metadata — and this is a SELF-link, so both
rows land in the same bulk insert of the same kind and no kind ordering could ever
satisfy it. «PostgreSQL portability» was not real either: `0027` adds the column
bare on PostgreSQL too, so the ORM FK never matched production on **any** dialect.

So option 1 (drop the ORM FK) costs nothing and makes the two schema build paths
agree. Option 2 (add the real FK in `0028`) was rejected as the more expensive one:
on SQLite it needs a table rebuild, which `0027`'s own Pitfall 3 says would drop all
four append-only triggers.

Scoped to the two reversal columns only — `sale_id`/`batch_id`/`author_id` share the
shape but are pre-existing and deliberate, and were not touched.

**Test added:** 1, asserted against the **compiled** `CreateTable` DDL rather than
the model source, so a comment cannot satisfy it.

---

## Skipped Issues

### WR-06: «Только в день операции» under-includes in the UTC-straddle window

**File:** `app/services/operations.py:305-332`
**Reason:** **unchanged from iterations 1 and 2 — the review itself says «still
needs one decision, and only one», and I have no channel to ask the operator.**

Both remedies are decisions, not local edits:

- **Relabel** — «Только в день операции» is a row in the locked
  `33-UI-SPEC.md` § Copywriting Contract; replacing it (e.g. with «Без пометки»)
  is new operator-facing copy.
- **Make it exact** — a fifth ledger column and revision `0028`, which drags in the
  phase's LOCKED five-artifact lockstep and its server→client rollout ordering.

**A decision-free third option was looked for and does not exist.** Making the SQL
predicate compare against the LOCAL day needs either date arithmetic on an ISO text
timestamp (not expressible in portable ORM — `datetime(created_at, '+3 hours')` on
SQLite / `created_at::date` on PostgreSQL are both banned by CLAUDE.md PC-2) or a
Python-side computation after the page is fetched, which breaks `total` and the
pager — the exact defect `test_history_period_count_agrees_with_its_own_rows` pins.
That is why CR-01 could be escalated to a decision-free fix and this one cannot.

**The docstring was NOT edited**, per the review's explicit «do not close this by
editing the docstring a third time».

**Next step:** ask the operator which answer they want. It is now the ONLY finding
across three iterations still blocked on an operator decision — CR-01, the other
half of that pair, was closed this iteration.

---

## Process notes

- Ran in an isolated `git worktree` on a temp branch (`gsd-reviewfix/33-2465`),
  fast-forwarded into `main` on completion (`1adc3c8` → `9589df8`, `--ff-only`,
  clean). The recovery sentinel was written after `worktree add` and removed after
  `worktree remove`; the temp branch was deleted only after the fast-forward
  succeeded. **No orphan worktree, branch or sentinel remains** — verified with
  `git worktree list`. The unrelated pre-existing worktree
  (`.claude/worktrees/agent-a97d10bfdb502533b`) was left untouched.
- `git add` used explicit paths only — the 51 untracked files (`reports/`,
  `input/`, `AGENTS.md`, `plan1.txt`) were never staged.
- `__version__` bumped once per commit: **1.124 → 1.132** — 8 commits
  (`0e37369` CR-01, `89066b6` WR-01, `d7bcc8d` WR-02, `6f6abbe` WR-03,
  `137e8f7` WR-04, `5450a19` WR-05, `5cc8bea` WR-07, `9589df8` ruff cleanup).
- `sed -i` was not used on any repo file. All edits went through the Edit/Write
  tools; commit messages went through `git commit -F`.
- **One incident, recorded rather than hidden:** I edited `app/__init__.py` and
  `app/services/finance.py` while a full-suite run was in progress, which broke
  `test_release_verify.py::test_build_asserts_tag_matches_version` (it compares the
  cached `app.__version__` against a fresh read of the file from disk). Nothing was
  lost — all fixes were already committed — and the suite was re-run cleanly
  afterwards. The 1812-passed figure quoted above is from that clean re-run, at the
  final HEAD, with `git status --porcelain` empty of tracked changes.
- **Three test contracts were deliberately inverted this iteration** (two in WR-03,
  one in WR-05). Every one of them is a test that pinned the defective behaviour
  rather than a decision, each inverted test's docstring states what it used to
  assert and why that reasoning was wrong, and no test was deleted or weakened to
  make a fix pass.
- **The project's mandatory `robust-console-commands` skill could not be invoked** —
  no Skill/SlashCommand tool is exposed in this agent context. Console use was kept
  to single-purpose commands (`git`, `uv run pytest`, `uv run ruff`, `grep`).
  Flagging rather than silently bypassing, as in iteration 2.

---

_Fixed: 2026-09-05_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 3_
