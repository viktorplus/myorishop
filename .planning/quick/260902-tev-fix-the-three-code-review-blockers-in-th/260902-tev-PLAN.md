---
phase: 260902-tev-fix-the-three-code-review-blockers-in-th
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/import_master_pricelist.py
  - scripts/import_prices.py
  - scripts/import_catalogs.py
  - tests/test_import_master_pricelist.py
  - tests/test_import_prices.py
  - tests/test_import_catalogs.py
autonomous: true
requirements: [CR-01, CR-02, CR-03]
branch: fix/260902-import-blockers

must_haves:
  truths:
    - "A master-price import whose «Последний каталог» column has drifted (every row unparsable) refuses to write, and every dictionary row that was stored is still stored."
    - "A wholesale dictionary replace that would leave fewer rows than are stored refuses unless the operator passes --force; the refusal names the two counts (stored -> about to write), names `scripts/import_catalogs.py --only-missing --file catalogs/products.json` as the step that restores the fuller справочник, and names --force as the escape hatch for a deliberate rebuild."
    - "The threshold is 0%, with no tolerance: on a clean install the table is empty when this importer runs, so the guard is silent on the happy path; the case it fires on is a re-run against a loaded server — 12 582 stored against the 6 856 the master price list covers."
    - "The operator sees «unparsable catalog: N» and the path of a VACUUM INTO snapshot BEFORE the first dictionary row is deleted; on PostgreSQL the snapshot is a printed no-op, not a crash."
    - "A snapshot that cannot be taken aborts the import: the exception propagates out of backup_before_replace and nothing is deleted."
    - "An export record whose consumer_cents / consultant_cents / points is a float, a string, a bool or negative is refused by record index and value; so is a non-string name and a name longer than 200 chars."
    - "An export record carrying a stored 0 or a None in those same fields still loads — the contract is >= 0, not > 0."
    - "A failure during any of the three accumulative-file writes leaves the previous file byte-identical on disk and no temp file beside it."
    - "The bytes the three writers produce are unchanged: LF one-record-per-line JSON, gzip for a .gz destination, CRLF with no trailing newline for rubric_overrides.json."
    - "Each of the three blockers is one commit, revertable on its own."
  artifacts:
    - path: "scripts/import_master_pricelist.py"
      provides: "DictionaryReplaceRefused + guarded apply_master_import(force=) + backup_before_replace + --force"
      contains: "class DictionaryReplaceRefused"
    - path: "scripts/import_prices.py"
      provides: "atomic_write helper + full 7-field validate_records"
      contains: "def atomic_write"
    - path: "scripts/import_catalogs.py"
      provides: "write_export routed through the shared atomic_write"
      contains: "from scripts.import_prices import atomic_write"
    - path: "tests/test_import_master_pricelist.py"
      provides: "CR-01 contract: empty-input refusal, shrink refusal with an actionable message, --force escape hatch, backup dialect gate, failed-snapshot abort, print-order tripwire"
    - path: "tests/test_import_prices.py"
      provides: "CR-02 malformed-money/name cases + CR-03 atomic_write contract and write_export/write_overrides rollback"
    - path: "tests/test_import_catalogs.py"
      provides: "CR-03 proof that write_export never opens its destination directly"
  key_links:
    - from: "scripts/import_master_pricelist.py::apply_master_import"
      to: "session.query(Dictionary).delete()"
      via: "DictionaryReplaceRefused raised BEFORE the delete"
      pattern: "raise DictionaryReplaceRefused"
    - from: "scripts/import_master_pricelist.py::backup_before_replace"
      to: "app.services.backup.create_backup"
      via: "engine.dialect.name == 'sqlite' gate; the exception is never swallowed"
      pattern: "create_backup\\("
    - from: "scripts/import_prices.py::write_export"
      to: "atomic_write"
      via: "serialize_export(merged) evaluated as the argument, before dest is touched"
      pattern: "atomic_write\\(dest, serialize_export"
    - from: "scripts/import_prices.py::write_overrides"
      to: "atomic_write"
      via: "newline='\\r\\n', no trailing newline"
      pattern: "atomic_write\\("
    - from: "scripts/import_catalogs.py::write_export"
      to: "scripts.import_prices.atomic_write"
      via: "cross-script import, the idiom import_master_pricelist.py:53 already uses"
      pattern: "atomic_write\\("
    - from: "scripts/import_prices.py::validate_records"
      to: "build_price_rows -> upsert_price_rows"
      via: "the .gz transport contract enforced before any DB touch"
      pattern: "consumer_cents"
---

<objective>
Close the three code-review blockers found in `.planning/quick/260902-m9g-xls-xlsx-catalog-prices/260902-m9g-REVIEW.md`
(CR-01, CR-02, CR-03) — and nothing else.

Purpose: all three are the same class of defect the m9g task was written to close for
`catalog_prices`, left open next door. A degraded parse can still silently wipe the
`dictionary` table (CR-01); the `.gz` file that ships the whole price history to s1 is
validated on 3 of its 7 fields (CR-02); and three accumulative files are truncated
before their replacement content is computed (CR-03).

The overriding requirement is the operator's: safe, with a way back. That means two
levels of rollback — git level (one atomic commit per blocker, so any one can be
reverted alone) and data level (no destructive operation without a recoverable snapshot
or an untouched original).

Output: three commits on the already-checked-out branch `fix/260902-import-blockers`.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
</execution_context>

<context>
@.planning/quick/260902-m9g-xls-xlsx-catalog-prices/260902-m9g-REVIEW.md
@CLAUDE.md
@scripts/import_master_pricelist.py
@scripts/import_prices.py
@scripts/import_catalogs.py
@tests/test_import_master_pricelist.py
@tests/test_import_prices.py
@tests/test_import_catalogs.py
@app/services/backup.py
@deploy/DEPLOY.s1.md
</context>

<execution_rules>
- Branch `fix/260902-import-blockers` is already checked out. Do NOT create or switch branches.
- ONE commit per task, in task order. Never combine two blockers in one commit — the
  per-blocker separation IS the rollback requirement.
- Test-first inside every task: write the new test(s), run them, SEE them fail for the
  stated reason, then write the fix, then see them pass.
- Do NOT bump `app/__init__.py` `__version__`. These commits touch `scripts/` and
  `tests/` only — nothing the running app serves — and the update mechanism shipped in
  Phase 32 pins that value as its anti-downgrade baseline.
- OUT OF SCOPE, do not touch: `merge_price_export`, `merge_dictionary_export`,
  `upsert_price_rows`, `insert_missing_price_rows`, every parsing function, and every
  WARNING/INFO finding of the review (WR-01..09, IN-01..09).
- Additive mode per CLAUDE.md: reuse what exists, no new modules, no new dependencies,
  no new config knobs beyond the single `--force` flag CR-01 requires.
- KNOWN PRE-EXISTING FAILURES: 4 tests in `tests/test_sync_ui.py` fail deterministically
  in the local full suite (`sync_client._run_lock` is held by the lifespan auto-sync
  thread). They are NOT a regression from this work and must NOT be "fixed" here. The
  full-suite gate is green iff the only failures are those 4.
</execution_rules>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: CR-01 — refuse a degraded master-price import, and snapshot before the wholesale replace</name>
  <files>scripts/import_master_pricelist.py, tests/test_import_master_pricelist.py</files>

  <behavior>
    New tests in `tests/test_import_master_pricelist.py`, appended after the existing
    260902-m9g section, under a new section comment naming quick task 260902-tev.
    Add `import ast` and a module constant `SCRIPT = PROJECT_ROOT / "scripts" / "import_master_pricelist.py"`.

    - `test_apply_master_import_refuses_an_empty_price_list`: seed one Dictionary row,
      call `apply_master_import(session, {})`, expect `DictionaryReplaceRefused`, then
      assert the seeded row is STILL there (the guard fires before the delete) and that
      `session.scalar(select(func.count()).select_from(Dictionary))` is unchanged.
    - `test_apply_master_import_refuses_a_replace_that_would_shrink_the_dictionary`:
      compute `planned = len(build_dictionary_rows({FAKE_CODE: dict(FAKE_ROW)}))` from the
      function itself (never hardcode the RUBRIC_OVERRIDES count — it grows), seed
      `planned + 1` synthetic rows with codes `f"77{i:05d}"`, expect
      `DictionaryReplaceRefused`, and assert the row count is still `planned + 1`.
      Assert the message is ACTIONABLE, not just alarming: it contains both counts
      (`str(planned + 1)` and `str(planned)`), the substring `import_catalogs.py`, and the
      substring `--force`. An operator who hits this must be able to read the way out of
      the error itself instead of reaching for `--force` reflexively.
    - `test_force_allows_the_shrinking_replace`: same seed, `force=True`, then commit and
      assert the count is exactly `planned` — the escape hatch works.
    - `test_backup_before_replace_takes_a_vacuum_snapshot(engine, tmp_path, monkeypatch)`:
      monkeypatch `app.config.settings.backup_dir` to `str(tmp_path)`, call
      `backup_before_replace(engine)`, assert the returned Path exists, is inside
      `tmp_path`, matches `myorishop-*.db`, and is a readable SQLite file (non-zero size).
    - `test_backup_before_replace_is_a_printed_noop_on_postgresql(tmp_path, monkeypatch, capsys)`:
      pass a stub with `dialect.name == "postgresql"` (a `types.SimpleNamespace`), assert
      the return is None, that `list(tmp_path.iterdir()) == []`, and that something was
      printed — a server run must not crash and must not stay silent.
    - `test_a_failed_snapshot_aborts_the_import(engine, session, tmp_path, monkeypatch)`:
      monkeypatch `scripts.import_master_pricelist.create_backup` to raise `OSError`, seed
      one Dictionary row, assert `backup_before_replace(engine)` propagates the `OSError`
      (`pytest.raises`), and assert the seeded row is still there. The behaviour is free
      today — the point of the test is to stop a future `except Exception: print(...)`
      from quietly demoting the last line of defence into a warning.
    - `test_the_operator_sees_the_statistics_and_the_backup_before_anything_is_written`:
      an ast tripwire over `SCRIPT`, in the style of the existing
      `test_excel_readers_are_not_imported_at_module_level`. Inside the `main` FunctionDef,
      take the lowest lineno of a string constant containing `Rows skipped`, the lowest
      lineno of a `Call` whose `ast.unparse` mentions `backup_before_replace`, and the
      HIGHEST lineno of a `With` whose first item unparses to something containing
      `SessionLocal`; assert both of the first two are strictly smaller than the third.
  </behavior>

  <action>
    Write the tests above FIRST and confirm they fail (`DictionaryReplaceRefused` and
    `backup_before_replace` do not exist yet; the ast tripwire fails on the current
    print order). Then make these four changes to `scripts/import_master_pricelist.py`,
    which are the review's CR-01 (a)(b)(c)(d):

    (b) Add a dedicated exception class `DictionaryReplaceRefused(RuntimeError)` at module
    level, right after the constants, mirroring `ShadeNameWouldShrink` in
    `scripts/import_catalogs.py:87` — same shape, same docstring register ("the last line
    of defence for the unattended server run"). Name it `Refused` rather than
    `WouldShrink` because it carries two distinct messages, one of which (empty input on
    an empty table) is not a shrink.

    Change the signature to `apply_master_import(session, collected, *, force: bool = False)`
    — keyword-only, so the two existing call sites in the tests keep working unchanged.
    Before `session.query(Dictionary).delete()`, in this order:
      1. `if not collected: raise DictionaryReplaceRefused(...)` — message: refusing to
         replace `dictionary` from an empty price list.
      2. build `rows = build_dictionary_rows(collected)` ONCE, read
         `before = session.query(Dictionary).count()` (the idiom already used in `main()`
         at lines 286/299 — keep the file consistent, do not introduce a second style),
         and `if len(rows) < before and not force: raise DictionaryReplaceRefused(...)`.
      3. Only then delete, `session.bulk_save_objects(rows)` (reuse the list already
         built — do not call `build_dictionary_rows` twice), and return
         `upsert_price_rows(...)` exactly as today.
    Both guards live INSIDE `apply_master_import` so every caller is protected, not only
    `main()`.

    THE THRESHOLD IS 0%, AND IT STAYS 0% — no tolerance band. Record the reason in the
    guard's own comment so the next reader does not re-open it: `deploy/DEPLOY.s1.md:73-121`
    documents the install order, and this importer runs FIRST (§4, line 82) while
    `import_catalogs.py --only-missing --file catalogs/products.json` runs after it
    (§4.1, line 117) — so on a clean install `dictionary` is EMPTY here, 0 -> 6 856 is
    growth, and the guard is silent on the happy path. The case it DOES fire on is a
    re-run of this importer against an already-loaded server, where
    `deploy/DEPLOY.s1.md:101-105` gives the numbers: the master price list covers 6 856
    codes while the full справочник holds 12 582. That is a 45% loss and it is precisely
    the destruction CR-01 exists to stop, today guarded by nothing but the prose warning
    at `deploy/DEPLOY.s1.md:94-97`. A 20% tolerance would not even catch that case (45%
    > 20%) — it would only weaken the small-drift case, so it buys nothing and costs
    protection.

    The shrink message must therefore be ACTIONABLE, not merely loud. It states the two
    counts in the form "stored N -> about to write M", names
    `scripts/import_catalogs.py --only-missing --file catalogs/products.json` as the step
    that restores the fuller справочник, and names `--force` last, as the escape hatch for
    a deliberate rebuild. The empty-input message keeps its own wording.

    (d) Add `backup_before_replace(engine) -> Path | None` next to the other helpers.
    It reads `engine.dialect.name`; when it is not `sqlite` it prints one line saying the
    VACUUM INTO snapshot is skipped on this dialect (the policy `.env.production.example:25`
    already states for `BACKUP_ON_STARTUP`) and returns None. Otherwise it calls
    `create_backup(engine, Path(settings.backup_dir))`, prints the returned path labelled
    as the rollback snapshot, and returns it. Import `create_backup` from
    `app.services.backup` and `settings` from `app.config`, in the existing
    `# noqa: E402` import block. Do NOT catch the exception `create_backup` raises — a
    failed snapshot must abort the import before anything is deleted, which is the whole
    point and is now pinned by a test. This helper takes the ENGINE and is called from
    `main()` before the session is opened, deliberately: `apply_master_import` is called
    directly by two existing unit tests on throwaway engines, and a filesystem side effect
    inside it would spray backups into the developer's real `data/backups/`.

    (a)(c) In `main()`:
      - add `--force` (`action="store_true"`) whose help text says it permits a replace
        that shrinks the dictionary; right after `parse_args`, add the foot-gun guard the
        module's siblings already use — `--force` with `--only-missing` is meaningless
        (that mode deletes nothing), so `sys.exit` with that sentence.
      - after `collect_price_rows(src)` and before the mode branch, add the sibling
        script's empty-input refusal (`scripts/import_prices.py:988`): `sys.exit` naming
        the source, the missing-code count and the unparsable-catalog count. NOTE, and
        state it in a comment: this guards BOTH modes on purpose — with a degraded parse
        `--only-missing` would insert a priceless «Не опознан» row for every override code
        that actually IS in the price list. It deletes nothing, but it is still junk, and
        fail-closed is the rule here.
      - move the pre-write half of the summary (`Source`, `Sheet`, `Data rows scanned`,
        `Rows imported`, `Rows skipped`, `Dictionary rows from overrides only`) to BEFORE
        the `with SessionLocal() as session:` block of the full-replace path, then call
        `backup_before_replace(engine)` (import `engine` alongside `SessionLocal` from
        `app.db`), then open the session. Leave the post-write half (`Dictionary: X -> Y`,
        `CatalogPrice: X -> Y`, the inserted/updated/unchanged line, `Rubric assigned`)
        where it is — those numbers do not exist until after the write. Pass
        `force=args.force` into `apply_master_import`.

    Keep every line under the 100-char ruff limit.
  </action>

  <verify>
    <automated>uv run pytest tests/test_import_master_pricelist.py -q</automated>
    <automated>uv run pytest -q</automated>
  </verify>

  <done>
    All new tests pass; the four existing `apply_master_import` / `build_dictionary_rows`
    tests still pass unchanged; the full suite is green except the 4 known
    `tests/test_sync_ui.py` failures. `uv run ruff check scripts/ tests/` reports nothing
    new for the touched files. Committed as ONE commit:
    `fix(import): refuse a degraded master-price import and snapshot before the replace (CR-01)`
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: CR-02 — validate all seven export fields, not three</name>
  <files>scripts/import_prices.py, tests/test_import_prices.py</files>

  <behavior>
    In `tests/test_import_prices.py`, extend the EXISTING parametrize list of
    `test_load_export_refuses_malformed_input` (line 111) with the unchecked shapes —
    same file, same test, next to its neighbours:
      - `{**PLAIN_ROW, "consumer_cents": 599.5}` — a float in an INTEGER money column
      - `{**PLAIN_ROW, "consultant_cents": "не указано"}` — a string that would reach
        `format_cents()` through `reference_prices_for_code()` and 500 the page
      - `{**PLAIN_ROW, "points": "3"}`
      - `{**PLAIN_ROW, "points": True}` — bool is an int subclass; it must not slip through
      - `{**PLAIN_ROW, "consumer_cents": -1}`
      - `{**PLAIN_ROW, "name": 46413}` — a non-string name
      - `{**PLAIN_ROW, "name": "х" * (MAX_NAME + 1)}` — longer than the String(200) column
    Add ONE new test, `test_validate_records_accepts_a_stored_zero_and_a_null`, calling
    `validate_records` directly with a record carrying `consumer_cents=0`, `points=0`,
    `consultant_cents=None`, `name=None`, asserting it returns the records and does NOT
    raise. That test is what pins `>= 0` against a future tightening to `> 0`.
    Add `MAX_NAME` and `validate_records` to the module's import list from
    `scripts.import_prices`.
  </behavior>

  <action>
    Write the test cases first and confirm each new parametrize case FAILS (today
    `validate_records` accepts all of them) while the zero/null test passes.

    Then extend `validate_records()` in `scripts/import_prices.py` (lines 640-657), after
    the existing `year`/`number` loop and in the SAME error style — `sys.exit` naming the
    source, the record index and the offending value with `!r`:
      - `name`: accept None; otherwise require `isinstance(value, str)` and
        `len(value) <= MAX_NAME` (the constant at line 97 — `CatalogPrice.name` is
        `String(200)`, and `IN-03` already flags the duplicated literal, so use the
        constant, never a new `200`). Two distinct messages: non-string vs too long.
      - `consumer_cents`, `consultant_cents`, `points` in one loop: accept None
        (`continue`); otherwise reject when `not isinstance(value, int)` or
        `isinstance(value, bool)` or `value < 0`.
    Add a one-line comment on the `>= 0` choice: the producers (`_cents()` at line 164 and
    `import_master_pricelist._cents` at line 83) only ever emit positive-or-None, but
    `export_prices()` reads whatever the database holds, so a legitimate re-export of a
    stored zero must not be rejected.

    This is the whole task — do not touch `build_price_rows`, `upsert_price_rows`, or
    `load_export`'s exception list (WR-07 is out of scope).
  </action>

  <verify>
    <automated>uv run pytest tests/test_import_prices.py -q</automated>
    <automated>uv run pytest -q</automated>
  </verify>

  <done>
    Every new parametrize case raises `SystemExit` with a message naming the record index
    and the value; the zero/null record still loads; the existing round-trip and gzip
    tests are unchanged and green; full suite green except the 4 known `test_sync_ui.py`
    failures. Committed as ONE commit:
    `fix(import): validate every money and name field in the price export (CR-02)`
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: CR-03 — one atomic_write helper, reused by all three truncating writers</name>
  <files>scripts/import_prices.py, scripts/import_catalogs.py, tests/test_import_prices.py, tests/test_import_catalogs.py</files>

  <behavior>
    In `tests/test_import_prices.py` (import `atomic_write`, and `gzip` if needed):
    - `test_atomic_write_keeps_the_gz_branch_and_the_explicit_newline(tmp_path)`: write a
      payload to a `.json.gz` destination and assert the first two bytes are `\x1f\x8b`
      and `load_export` reads it back; write to a `.json` destination with
      `newline="\r\n"` and assert the raw bytes contain CRLF and no lone LF; after both,
      assert no file matching `*.tmp*` is left in `tmp_path`.
    - `test_atomic_write_leaves_the_destination_untouched_when_the_write_fails(tmp_path)`:
      seed the destination with known bytes, call `atomic_write` with a payload that is
      not a string so `handle.write` raises inside the with-block, assert `TypeError`,
      then assert the destination's bytes are byte-identical to the seed and no `*.tmp*`
      file survives. That is the rollback, stated as a test.
    - `test_write_export_computes_the_payload_before_touching_the_destination(tmp_path, monkeypatch)`:
      the sharpest proof of the actual defect. Seed `dest` via
      `write_export(dest, [PLAIN_ROW])`, monkeypatch
      `scripts.import_prices.serialize_export` to raise `RuntimeError`, call
      `write_export(dest, [ZERO_ROW])` inside `pytest.raises(RuntimeError)`, then assert
      `load_export(dest)` still returns the original single row. Today this fails because
      `_open_export(dest, "wt")` has already truncated the file.
    - `test_write_overrides_never_opens_its_destination_directly(tmp_path, monkeypatch)`:
      wrap `scripts.import_prices._open_export` in a recording stub that appends the path
      it was handed and delegates to the real function; call `write_overrides`; then
      assert, IN THIS ORDER: first `assert recorded, "the writer never went through
      _open_export"` — without it the RED step dies on an IndexError and hides what
      actually broke; then that the recorded path is NOT `dest`; then that its name ends
      with the destination's own suffix (so the gzip branch cannot be lost); then that the
      resulting bytes still satisfy the existing CRLF / no-trailing-newline contract.

    In `tests/test_import_catalogs.py`:
    - `test_write_export_never_opens_its_destination_directly(tmp_path, monkeypatch)`: the
      same recording stub on `scripts.import_prices._open_export` (the helper resolves
      `_open_export` from its own module globals, so patching it there covers the
      cross-script caller). Same assertion order, starting with
      `assert recorded, "the writer never went through _open_export"`; then that the
      recorded path is not `dest`, and that the file content still round-trips through
      `read_previous_export` with the same key order.
  </behavior>

  <action>
    Write the five tests first and confirm the three that must be RED are RED (the helper
    does not exist; `write_export` truncates before serializing; both `write_overrides`
    and `import_catalogs.write_export` open their destination directly).

    Then add ONE helper to `scripts/import_prices.py`, directly next to `_open_export`
    (line 660) so the two live together, and add `import os` to the stdlib import block:

    `atomic_write(dest, payload, *, newline)` — makes `dest.parent`, writes `payload`
    through `_open_export(tmp, "wt", newline=newline)` into a sibling temp file in the
    SAME directory (same filesystem, so the rename is atomic), then `os.replace(tmp, dest)`;
    a `finally` clause unlinks the temp with `missing_ok=True`, which is both the
    error-path cleanup and a no-op after a successful replace. On any exception the
    destination is left exactly as it was — that is the rollback.

    THE TRAP, and the reason this is not the review's snippet verbatim: `_open_export`
    decides gzip-vs-plain from the SUFFIX, so a temp named `dest.name + ".tmp"` would turn
    `catalog_prices.json.gz` into a PLAIN-text write. The temp name must end in the
    destination's own suffix — build it as `dest.name + ".tmp" + dest.suffix`, giving
    `catalog_prices.json.gz.tmp.gz` and `products.json.tmp.json`. Say so in the docstring;
    the gz test above is its tripwire.

    Reuse it in the three current truncating writers, changing nothing else about them:
      - `import_prices.write_export` (lines 848-851): drop the now-duplicated
        `dest.parent.mkdir` and the `with _open_export(...)` block, and call
        `atomic_write(dest, serialize_export(merged), newline="\n")`. Evaluating
        `serialize_export(merged)` as the argument is what makes the ~42 MB string exist
        before anything touches `dest`. Leave the `stats["after"] < stats["before"]` guard
        and the `stats["codes"]` line untouched.
      - `import_prices.write_overrides` (lines 538-541): call `atomic_write` with
        `json.dumps(data, ensure_ascii=False, indent=1)` and `newline="\r\n"`. The file's
        byte form — CRLF, indent=1, NO trailing newline — must survive exactly;
        `test_write_overrides_reproduces_the_files_byte_form` is the existing net.
      - `import_catalogs.write_export` (lines 355-359): import the helper with
        `from scripts.import_prices import atomic_write  # noqa: E402`, placed with the
        other `# noqa: E402` imports — the same cross-script idiom
        `scripts/import_master_pricelist.py:53` already uses. Build the payload as
        `json.dumps(merged, ensure_ascii=False, indent=1) + "\n"` and pass it with
        `newline="\n"`; the trailing newline this writer emits today must stay.

    Do not change the merge functions, the shrink guards, or any caller-visible bytes.
  </action>

  <verify>
    <automated>uv run pytest tests/test_import_prices.py tests/test_import_catalogs.py -q</automated>
    <automated>uv run pytest -q</automated>
  </verify>

  <done>
    All five new tests pass; the three existing byte-form/accumulation tests
    (`test_write_overrides_reproduces_the_files_byte_form`,
    `test_write_export_into_an_existing_file_preserves_a_foreign_row`,
    `test_the_export_round_trips_through_a_gz_with_no_loss`, plus the import_catalogs
    twin) pass UNCHANGED — proof the bytes did not move; full suite green except the 4
    known `test_sync_ui.py` failures. Committed as ONE commit:
    `fix(import): write the three accumulative files atomically (CR-03)`
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| xlsx price list → `dictionary` | A silently reshaped export column turns a full replace into a wipe (CR-01) |
| `catalog_prices.json.gz` → server DB | The only transport that reaches s1; arrives over the wire and is written by an importer run unattended (CR-02) |
| process → accumulative files on disk | Files holding rows that exist in NO database; a truncated write is unrecoverable (CR-03) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-TEV-01 | Denial of Service (data loss) | `apply_master_import` wholesale replace | mitigate | Empty-input + 0%-threshold shrink guards raised inside the function before the delete; `--force` is the only bypass, and the message names the `import_catalogs.py --only-missing` recovery step first |
| T-TEV-02 | Denial of Service (data loss) | operator running the master import unattended | mitigate | `create_backup` VACUUM INTO snapshot taken and its path printed before the delete; a failed snapshot aborts the run, pinned by a test |
| T-TEV-03 | Tampering | `validate_records` on the `.gz` transport | mitigate | Reject non-int / bool / negative money and points and non-str / over-200 names by record index, before `build_price_rows` reaches the INTEGER columns |
| T-TEV-04 | Denial of Service (data loss) | `write_export` / `write_overrides` / `import_catalogs.write_export` | mitigate | Serialize first, write to a same-directory temp with the destination's suffix, `os.replace`; the original is untouched on any failure |
| T-TEV-05 | Elevation of Privilege | new CLI surface | accept | The only new flag is `--force` on a local, operator-run script; it loosens nothing that `python -c` could not already do |
| T-TEV-SC | Tampering | package installs | accept | Zero new dependencies — stdlib `os` only |
</threat_model>

<verification>
1. `uv run pytest -q` — green except exactly the 4 pre-existing `tests/test_sync_ui.py`
   failures (`sync_client._run_lock`). Any fifth failure is a regression from this work.
2. `uv run ruff check scripts/ tests/` — no NEW findings for the six touched files
   (the repo already carries pre-existing E501s elsewhere; compare, do not clean up).
3. `git log --oneline -3` — exactly three commits, one per blocker, in CR-01/02/03 order,
   each revertable on its own (`git revert <sha>` touches only that blocker's files).
4. Manual, no DB required: run
   `uv run python scripts/import_master_pricelist.py --file <a copy of the xlsx with the
   «Последний каталог» header renamed>` and confirm it exits naming the missing column
   without opening a session. This is the CR-01 scenario end to end and writes nothing.
</verification>

<success_criteria>
- Three commits on `fix/260902-import-blockers`, one per blocker, no cross-contamination.
- `apply_master_import` cannot wipe the справочник from an empty or degraded parse, and
  cannot shrink it at all without `--force`; both guards fire before the delete, for every
  caller; the shrink message carries the two counts, the recovery command and `--force`.
- A VACUUM INTO snapshot path is printed before the replace on SQLite; PostgreSQL prints a
  skip line and does not crash; a snapshot that fails aborts the import.
- The skip statistics are on screen before anything is deleted.
- All seven export fields are validated; `0` and `None` still load.
- All three accumulative writers are crash-safe, and their output bytes are unchanged.
- Full suite green except the 4 known `test_sync_ui.py` failures.
</success_criteria>

<output>
Create `.planning/quick/260902-tev-fix-the-three-code-review-blockers-in-th/260902-tev-SUMMARY.md`
when done, listing the three commit SHAs and, for each, the one-line revert command.
</output>
