---
quick_id: 260721-ebn
type: execute
autonomous: true
files_modified:
  - app/services/sync_client.py
  - tests/test_sync_client.py
must_haves:
  truths:
    - "A pull page containing a Dictionary record whose `code` already exists locally under a DIFFERENT `id` (independently-imported catalog on each side) no longer raises sqlite3.IntegrityError / psycopg.errors.UniqueViolation — the sync completes with status='ok' (or 'partial' only for an unrelated reason)."
    - "In that case the LOCAL dictionary row (matched by code) is UPDATED with the server's name/catalogs/rubric/updated_at (server wins on master data, D-14), while its local `id` and `code` are left untouched — no duplicate row is created."
    - "A genuinely NEW dictionary code (not present locally under any id) is still inserted as before, using the server's id verbatim."
    - "All other reference kinds (warehouse/product/customer/batch/sale) keep the existing by-id partition/upsert behavior unchanged — this fix is scoped to the 'dictionary' kind only."
  artifacts:
    - path: "app/services/sync_client.py"
      provides: "_apply_pull_page special-cases kind=='dictionary' to partition/upsert by code instead of id"
  key_links:
    - from: "app/services/sync_client.py::_apply_pull_page"
      to: "Dictionary.code"
      via: "code-keyed partition + update, bypassing merge._partition_new's by-id logic for this one kind"
      pattern: "kind == \"dictionary\""
---

<objective>
Root cause (confirmed live against the deployed server via a real sync run): the local Dictionary table (Oriflame code -> name/rubric reference data, CAT-02/CAT-06) was populated by an independent local run of `scripts/import_master_pricelist.py`, and the server's Dictionary table was populated by an independent run of the SAME script on the server. Both runs generate fresh random UUIDs per row, so the SAME product `code` ends up with a DIFFERENT `id` on each side. `Dictionary.code` carries a DB-level `UNIQUE` constraint (app/models.py:289).

`_apply_pull_page` (app/services/sync_client.py) treats every reference kind identically: partition incoming rows into "new" vs "existing" by UUID `id` (`merge._partition_new`), insert the new ones verbatim. For `dictionary`, a server row is reported "new" (its id isn't present locally) and the insert crashes on `UNIQUE constraint failed: dictionary.code` (SQLite) / `UniqueViolation` (PostgreSQL) — because a DIFFERENT row with the same code already exists locally. This aborts the whole pull page (caught by `run_sync_once`'s broad `except Exception`, WR-01), degrading the manual sync button to `status='partial'` forever for any client whose local dictionary import predates being wired to a server (exactly this project's case, per `.planning/quick/260714-2w6-update-dictionary-pricelist/`).

Dictionary is push-exempt already (`collect_push_records` always emits an empty list for it — server is the sole source of truth, client only ever pulls it), so this is a CLIENT-ONLY fix: `_apply_pull_page` in app/services/sync_client.py needs a `dictionary`-specific branch that partitions/upserts by `code` instead of `id`, leaving `merge.py`'s shared by-id logic (used by the SERVER's ingest of product/batch/sale/etc.) completely untouched.

Output: dictionary pull no longer crashes when the local and server dictionaries were seeded independently; the local row's helper fields (name/catalogs/rubric) converge to the server's version on every sync, keyed by `code`.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@app/services/sync_client.py
@app/services/merge.py
@app/models.py
@tests/test_sync_client.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Partition/upsert the dictionary pull kind by code instead of id</name>
  <files>app/services/sync_client.py, tests/test_sync_client.py</files>
  <behavior>
    - Pull page carries a dictionary record whose `code` already exists locally under a different `id`, with different `name` -> sync status is NOT degraded by this row (no IntegrityError), and afterward exactly one local Dictionary row has that `code`, with its ORIGINAL local `id` preserved and `name` equal to the server's value (server wins on master data, mirroring the existing Product/Batch precedent).
    - Pull page carries a dictionary record whose `code` does NOT exist locally at all -> a new Dictionary row is inserted using the server's `id`, `code`, `name`, `catalogs`, `rubric` verbatim (unchanged existing behavior for genuinely new codes).
    - A pull page mixing a dictionary code-collision row together with unrelated new product/warehouse rows still applies all of them in the same page (no unrelated regression).
  </behavior>
  <action>
In app/services/sync_client.py, modify `_apply_pull_page`: inside the `for kind in merge._REFERENCE_INSERT_ORDER:` loop, add a branch for `kind == "dictionary"` that replaces the generic by-id partition/upsert with a by-code equivalent, BEFORE the generic `new_rows, _ = merge._partition_new(...)` line runs for that kind (early-continue after handling it, so the generic id-based path never executes for dictionary):

1. Collect the incoming `code` values from `rows` (skip/guard any row missing a code — should not happen from a valid ExchangeBatch, but do not crash on it; log nothing, just skip inserting/updating that one malformed row and move on, consistent with the crash-should-never-happen posture of this pull driver).
2. Query existing local `Dictionary.code -> Dictionary.id` for those codes in one chunked `SELECT id, code FROM dictionary WHERE code IN (...)` (reuse the `merge._IN_CHUNK` constant for the chunk size, matching `_partition_new`'s existing chunking pattern).
3. For rows whose code has NO existing local match: insert via `merge._reference_row("dictionary", row)` exactly as today (Dictionary is not in `_CACHED_QUANTITY_KINDS`, so `_reference_row` returns the columns verbatim — no special-casing needed there).
4. For rows whose code DOES have an existing local match: build an UPDATE keyed by the LOCAL id (`update(Dictionary).where(Dictionary.code == row["code"]).values(**values)` is simplest and avoids needing the id lookup result at all — code is UNIQUE so this targets exactly one row), setting every column in `merge.KIND_TO_FIELDS["dictionary"] - {"id", "code"}` from the server's row (name, catalogs, name_lc, rubric, created_at, updated_at) — server wins on master data, matching the existing generic branch's `update_fields = merge.KIND_TO_FIELDS[kind] - {"id", "quantity"}` pattern (dictionary has no `quantity` column, so exclude `code` instead since it's the match key, not `id`, that must be excluded — actually `id` must ALSO be excluded so the server's differing id is never written over the local row's PK; exclude BOTH `id` and `code`).
5. Increment the shared `applied` counter for both inserted and updated dictionary rows, same as the generic path does.
6. `continue` to the next kind after handling dictionary (skip the existing generic new_rows/existing_rows block entirely for this kind).

Do not touch `app/services/merge.py` — `merge._partition_new`, `merge.KIND_TO_MODEL`, `merge.KIND_TO_FIELDS`, `merge._REFERENCE_INSERT_ORDER` all stay exactly as-is; this fix lives entirely inside `_apply_pull_page`'s loop body in app/services/sync_client.py, which is client-pull-only code never exercised by the server's `apply_merge` (server never receives dictionary rows — `collect_push_records` always emits `"dictionary": []`).

Add tests to tests/test_sync_client.py (near `test_pull_applies_server_update`/`test_pull_inserts_new_server_rows`, using the existing `sync_driver_pair` fixture — see those two tests for the exact pattern of seeding `pair.server_session` and asserting post-sync state via `session`):
- `test_pull_dictionary_code_conflict_updates_local_row`: seed a local `Dictionary(id=local_id, code="47518", name="Старое имя", ...)`, seed a server-side `Dictionary(id=different_server_id, code="47518", name="Новое имя", ...)`, run `sync_client.run_sync_once`, assert `result.status == "ok"` (NOT "partial" — this is the regression this fix closes), assert exactly one row in local `Dictionary` with `code="47518"`, its `id` is STILL `local_id` (unchanged), and its `name` is now `"Новое имя"` (server won).
- `test_pull_dictionary_new_code_still_inserts`: seed only a server-side `Dictionary` row with a code absent locally, run sync, assert it is inserted locally with the server's id and fields verbatim (mirrors `test_pull_inserts_new_server_rows` but for dictionary specifically).
  </action>
  <verify>
    <automated>uv run pytest tests/test_sync_client.py -q</automated>
  </verify>
  <done>Both new tests pass; the full tests/test_sync_client.py suite passes with no regressions; a dictionary code-collision pull page no longer raises an IntegrityError and no longer degrades sync status to 'partial'/'error'.</done>
</task>

</tasks>

<threat_model>
## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-260721-01 | Tampering | Dictionary rows pulled from the sync server and upserted by code | accept | The server is the same trusted, already-authenticated sync peer (Bearer device token) every other pulled reference kind (product/warehouse/customer/batch/sale) already trusts under the existing D-14 server-wins upsert; this change only widens the MATCH KEY from id to code for one kind, it does not introduce a new trust boundary. |
</threat_model>

<verification>
- `uv run pytest tests/test_sync_client.py -q` passes (all existing + 2 new tests).
- Manual spot check against the real deployed server: run `sync_client.run_sync_once` (or click «Синхронизировать» in the UI) on a client whose local dictionary predates server pairing — status should reach `ok` (or `partial`/`offline` only for reasons unrelated to dictionary), not crash.
</verification>

<success_criteria>
- Dictionary pull no longer crashes on a code collision between independently-imported local and server dictionaries.
- Local dictionary rows converge to the server's name/catalogs/rubric on every sync (server wins), keyed by code, without ever duplicating a code or reassigning a local row's id.
- No other reference kind's merge/pull behavior changes.
</success_criteria>

<output>
Create `.planning/quick/260721-ebn-fix-dictionary-pull-crashing-on-code-bas/260721-ebn-SUMMARY.md` when done
</output>
