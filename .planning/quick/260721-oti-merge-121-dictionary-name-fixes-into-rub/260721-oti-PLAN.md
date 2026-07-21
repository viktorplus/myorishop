---
quick_id: 260721-oti
type: execute
wave: 1
depends_on: []
autonomous: false          # Task 3 has an SSH/human-needed fallback for the s1 deploy
files_modified:
  - app/services/rubric_overrides.json
requirements:
  - DICT-NAME-FIX-260721-oti
must_haves:
  truths:
    - "All 121 corrected product names appear in app/services/rubric_overrides.json (name field only)."
    - "The local DB dictionary table shows the corrected names after re-import."
    - "The corrected справочник is deployed to s1 (or exact manual deploy commands are handed to the operator)."
  artifacts:
    - path: "app/services/rubric_overrides.json"
      provides: "Merged override names (1784 entries, 121 name fields updated)"
      contains: "\"name\""
  key_links:
    - from: "app/services/rubric_overrides.json"
      to: "app/services/rubrics.py::resolve_name"
      via: "RUBRIC_OVERRIDES lookup by code"
      pattern: "resolve_name"
    - from: "scripts/import_master_pricelist.py"
      to: "dictionary table"
      via: "resolve_name(code, name) during full-replace import"
      pattern: "resolve_name"
---

<objective>
Merge the 121 corrected product names from `reports/dictionary_refresh_results.json`
into `app/services/rubric_overrides.json` (updating ONLY the `name` field of each
matching code), then re-import the справочник locally and on the s1 server so the
`dictionary` table carries the corrected names.

Purpose: `rubrics.resolve_name(code, name)` returns the override `name` during import,
so overwriting these 121 override names is the single source-of-truth change that makes
the corrected names flow into both the local SQLite DB and the s1 PostgreSQL DB on the
next full-replace import. No code logic changes.

Output: an updated `rubric_overrides.json` (committed + pushed), a re-imported local
dictionary table, and a deployed/re-imported s1 dictionary table (or exact manual
commands handed to the operator if SSH is unavailable from this environment).
</objective>

<context>
@.planning/STATE.md
@./CLAUDE.md
@reports/dictionary_refresh_results.json
@app/services/rubric_overrides.json
@app/services/rubrics.py
@scripts/import_master_pricelist.py
@deploy/DEPLOY.s1.md

Verified before planning:
- `rubric_overrides.json` = `{code: {"conf", "name", "rubric"}}`, 1784 entries.
- `dictionary_refresh_results.json` = flat `{code: new_name}`, 121 entries.
- All 121 codes already exist in the overrides; every new name DIFFERS from the current
  name → 121 real changes, 0 no-ops, 0 missing codes.
- `json.dumps(d, indent=1, ensure_ascii=False)` with NO trailing newline reproduces the
  current file byte-for-byte → a name-only merge produces a clean 121-line diff.
- `resolve_name(code, name)` returns the override `name` when present, so the importer
  applies the corrected names automatically on its next run.
- `import_master_pricelist.py` full-replaces `dictionary` + `catalog_prices` in one
  idempotent, re-runnable transaction. Local DB: `data/myorishop.db`.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Merge 121 corrected names into rubric_overrides.json (name field only)</name>
  <files>app/services/rubric_overrides.json</files>
  <action>
Update ONLY the `name` field of the 121 matching codes in
`app/services/rubric_overrides.json` from `reports/dictionary_refresh_results.json`.
Do NOT touch `conf` or `rubric` on any entry, and do NOT add or remove any entry.

Do this with a throwaway Python snippet (write it under the scratchpad dir, or run it as
an inline `python -c` / `uv run python -c`). The snippet must: `json.load` both files;
iterate the 121 items of the fixes dict; assert every fix code is already a key in the
overrides dict; set `d[code]["name"] = new_name` and count how many actually changed;
assert the changed count == 121; then write the file back with
`json.dumps(d, indent=1, ensure_ascii=False)` and NO trailing newline (this exactly
matches the file's current formatting — confirmed byte-for-byte on unchanged entries, so
the resulting git diff is exactly 121 changed name lines and nothing else). Load with
`encoding="utf-8"` and write with `encoding="utf-8"`.

Preserve existing key order — do NOT pass `sort_keys=True` (the dict already round-trips
in its current order; reordering would produce a noisy diff).

After the file is written, git-commit it atomically (this is a deploy-authorized task, so
commit is expected). Commit message: `data(dict): merge 121 corrected product names into rubric_overrides`.
  </action>
  <verify>
    <automated>python -c "import json; d=json.load(open('app/services/rubric_overrides.json',encoding='utf-8')); r=json.load(open('reports/dictionary_refresh_results.json',encoding='utf-8')); assert len(d)==1784, len(d); assert all(c in d for c in r); mism=[c for c in r if d[c]['name']!=r[c]]; assert not mism, mism; print('OK: 1784 entries, all 121 names merged')"</automated>
    <automated>git diff --numstat HEAD~1 -- app/services/rubric_overrides.json</automated>
  </verify>
  <done>
`rubric_overrides.json` still has 1784 entries and remains valid JSON; all 121 override
`name` fields equal the values in `dictionary_refresh_results.json`; no `conf`/`rubric`
field changed; the diff touches exactly 121 name lines (numstat shows 121 added / 121
removed); the change is committed.
  </done>
</task>

<task type="auto">
  <name>Task 2: Re-import the справочник locally and spot-check the corrected names</name>
  <files>data/myorishop.db</files>
  <action>
Run the full-replace importer against the local SQLite DB. Call the Python script
DIRECTLY (not `import_dictionary.bat`, which ends with a `pause` prompt that blocks a
non-interactive run):

`uv run python scripts/import_master_pricelist.py`

The script deletes and rebuilds `dictionary` + `catalog_prices` in one transaction,
applying `resolve_name`/`resolve_rubric` — so the 121 corrected override names land in
`dictionary.name`. It is idempotent; a re-run is safe. Confirm the printed summary shows
`Dictionary: N -> N` with a non-zero row count and no error.

Then verify against the DB: query the local `dictionary` table for every one of the 121
codes and assert each row's `name` equals the expected corrected name from
`reports/dictionary_refresh_results.json`. Use the app's own session + model
(`from app.db import SessionLocal`, `from app.models import Dictionary`) so the query hits
the same DB the app serves.
  </action>
  <verify>
    <automated>uv run python scripts/import_master_pricelist.py</automated>
    <automated>uv run python -c "import json; from app.db import SessionLocal; from app.models import Dictionary; r=json.load(open('reports/dictionary_refresh_results.json',encoding='utf-8')); s=SessionLocal(); rows={d.code:d.name for d in s.query(Dictionary).all()}; s.close(); mism=[c for c in r if rows.get(c)!=r[c]]; assert not mism, mism[:5]; print('OK: all 121 corrected names present in local dictionary table')"</automated>
  </verify>
  <done>
`import_master_pricelist.py` completes without error and reports a full-replace of the
dictionary; the local `dictionary` table returns the corrected `name` for all 121 codes
(mismatch count == 0). Spot examples to eyeball if desired: 20387 →
«Тональная основа Very Me «Йогуртовый микс» — Ванильный», 48667 → «Гель-лак для ногтей —
Чёрный оникс», 21142 → «Губная помада 100% цвета — Прозрачный беж».
  </done>
</task>

<task type="auto">
  <name>Task 3: Push to origin and deploy the re-import to s1 (SSH, with human-needed fallback)</name>
  <files></files>
  <action>
Deploying to the server was explicitly requested, which authorizes push + deploy.

Step A — push the Task 1 commit to origin:
Run `git push origin main` (the working branch is `main`). This should succeed
non-interactively with the configured credentials. If it fails, surface the exact error;
do not invent a workaround.

Step B — deploy + re-import on s1. Per `deploy/DEPLOY.s1.md` §4 and «Обновление
работающего сервера», the server pulls the new commit then re-runs the containerized
importer (openpyxl is a dev-dep not baked into the image, so it is pulled ephemerally via
`uv run --with openpyxl`). ATTEMPT this over SSH from this environment:

  `ssh s1 "cd /opt/myorishop && git pull && docker compose -f docker-compose.prod.yml exec -T ori-app uv run --with openpyxl python scripts/import_master_pricelist.py"`

(Use `exec -T` for a non-interactive, non-TTY run — the importer needs no confirmation
prompt, unlike reset_business_data.py.)

FALLBACK (do NOT fail the task): SSH to s1 may be non-interactive / key-unavailable /
blocked from this environment. If the `ssh s1 ...` command errors, times out, or cannot
authenticate, STOP retrying and instead emit the exact manual command block below for the
operator to run, and mark this step human-needed (the verify has a `<human-check>` for
exactly this). Manual block to hand over verbatim:

  ssh s1
  cd /opt/myorishop
  git pull
  docker compose -f docker-compose.prod.yml exec ori-app uv run --with openpyxl python scripts/import_master_pricelist.py

Confirm (from SSH output if it ran, or ask the operator to confirm from the manual run)
that the server importer printed a full-replace of the dictionary and that
`https://ori.viktorplus.com/dictionary` shows a corrected name for a spot-check code
(e.g. 48667 → «Гель-лак для ногтей — Чёрный оникс»).
  </action>
  <verify>
    <automated>git push origin main</automated>
    <human-check>
On s1 (via the ssh command above, or the operator running the manual block): `git pull`
brought in the rubric_overrides commit, the containerized `import_master_pricelist.py`
completed with a full-replace and no error, and https://ori.viktorplus.com/dictionary
shows a corrected name for a spot-check code (e.g. 48667 → «Гель-лак для ногтей — Чёрный
оникс»). If SSH was unavailable from this environment, the exact manual command block was
handed to the operator.
    </human-check>
  </verify>
  <done>
The commit is pushed to origin. Either: (a) the s1 `git pull` + containerized re-import
ran successfully over SSH and a spot-check code shows its corrected name on
https://ori.viktorplus.com/dictionary; or (b) SSH was unavailable and the operator has
the exact manual deploy commands, with this step marked human-needed.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| local → git origin (public) | The committed data file becomes publicly readable. |
| this env → s1 (SSH) | Remote command execution / deploy on the production server. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-oti-01 | Information Disclosure | rubric_overrides.json pushed to origin | accept | File holds only non-secret Oriflame product display names; no PII, secrets, or credentials. Already a tracked, previously-public file. |
| T-oti-02 | Tampering | scripts/import_master_pricelist.py on s1 | accept | Idempotent, re-runnable full-replace of two helper tables only (D-24); never touches ledger/Product/Batch/Operation/Sale rows. A bad run is corrected by re-running. |
| T-oti-SC | Tampering | `uv run --with openpyxl` on s1 | accept | openpyxl is an existing project dev-dependency (documented stack), not a new/unaudited package; pulled ephemerally per the established DEPLOY.s1.md §4 procedure. No new installs introduced by this task. |
</threat_model>

<verification>
- `rubric_overrides.json`: 1784 entries, valid JSON, exactly 121 `name` fields changed, no `conf`/`rubric` changes (Task 1 verify).
- Local `dictionary` table: all 121 codes return the corrected name after re-import (Task 2 verify).
- Origin has the commit; s1 re-imported the corrected справочник, or the operator holds the exact manual deploy commands (Task 3 verify + human-check).
</verification>

<success_criteria>
- The 121 corrected names are merged into `app/services/rubric_overrides.json` (name field only, 1784 entries preserved) and committed.
- The local SQLite `dictionary` table shows all 121 corrected names after a full-replace import.
- The commit is pushed to origin and the s1 server is re-imported (or the operator has the exact manual deploy commands, step marked human-needed).
- No code logic and no master xlsx were modified — only the JSON data file plus running the importer.
</success_criteria>

<output>
Create `.planning/quick/260721-oti-merge-121-dictionary-name-fixes-into-rub/260721-oti-SUMMARY.md` when done.
</output>
