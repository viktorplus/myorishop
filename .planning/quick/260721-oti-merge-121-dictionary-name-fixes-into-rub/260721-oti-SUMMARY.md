---
quick_id: 260721-oti
type: execute
subsystem: dictionary
tags: [dictionary, rubric-overrides, data-fix, s1-deploy]
requires: []
provides:
  - "app/services/rubric_overrides.json with 121 corrected product names"
  - "local + s1 dictionary tables carrying the corrected names"
affects:
  - app/services/rubric_overrides.json
key-files:
  created: []
  modified:
    - app/services/rubric_overrides.json
decisions:
  - "Server update required an image rebuild (up -d --build), not just git pull + re-import — the app code (incl. rubric_overrides.json) is COPY-baked into the image, not volume-mounted."
metrics:
  tasks: 3
  files_changed: 1
  completed: 2026-07-21
---

# Quick Task 260721-oti: Merge 121 Dictionary Name Fixes into rubric_overrides Summary

Merged 121 web-verified corrected product names (name field only) into
`app/services/rubric_overrides.json`, re-imported the справочник locally and on s1,
so both the local SQLite and the s1 PostgreSQL `dictionary` tables now carry the
corrected display names. No code logic changed.

## Tasks Completed

### Task 1 — Merge 121 corrected names (name field only)
- Updated ONLY the `name` field of 121 codes in `rubric_overrides.json` from
  `reports/dictionary_refresh_results.json` via a throwaway snippet (scratchpad).
- Asserted: 1784 entries preserved, all 121 fix codes present, exactly 121 names
  changed, `conf`/`rubric` untouched, key order preserved, no trailing newline.
- Diff is exactly 121 added / 121 removed, every changed line a `"name"` line.
- **Committed atomically: `5940b3f`** — `data(dict): merge 121 corrected product names into rubric_overrides`.

### Task 2 — Local re-import + spot-check
- Ran `uv run python scripts/import_master_pricelist.py` (called the script directly,
  not the `.bat` which ends in a blocking `pause`).
- Importer full-replaced both helper tables: `Dictionary: 6856 -> 6856`,
  `CatalogPrice: 6856 -> 6856`, no error.
- Verified against the local DB via the app's own session/model
  (`from app.db import SessionLocal`, `from app.models import Dictionary` — both
  import paths resolved as the plan assumed; `Dictionary` has `code`/`name` columns).
- **Mismatch count = 0** — all 121 corrected names present in the local `dictionary` table.

### Task 3 — Push to origin + deploy to s1 (over SSH)
- **Step A:** `git push origin main` succeeded: `3fcc186..5940b3f  main -> main`.
- **Step B:** Deployed to s1 over SSH (SSH was available and non-interactive).
  - Server `git pull` brought in `5940b3f`.
  - First importer run (per plan's §4 command) full-replaced the dictionary but a
    server spot-check still showed the OLD short shade-only names (e.g. 48667 →
    «Чёрный оникс»), because the running `ori-app` container had the OLD
    `rubric_overrides.json` baked into its image (see Deviations).
  - Applied the DEPLOY.s1.md «Обновление работающего сервера» procedure:
    `docker compose -f docker-compose.prod.yml up -d --build` to rebuild the image
    with the new overrides, then re-ran the containerized importer
    (`uv run --with openpyxl`). Full-replace `Dictionary: 6856 -> 6856`, no error.
  - **Server spot-check now correct:**
    - 20387 → «Тональная основа Very Me «Йогуртовый микс» — Ванильный»
    - 21142 → «Губная помада 100% цвета — Прозрачный беж»
    - 48667 → «Гель-лак для ногтей — Чёрный оникс»
  - Live site healthy after rebuild: `https://ori.viktorplus.com/` → HTTP 303
    (redirect to /login, the expected auth-boundary response per DEPLOY.s1.md §6).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking deploy defect] Server needed an image rebuild, not just git pull**
- **Found during:** Task 3, Step B.
- **Issue:** The plan's Task 3 command came from DEPLOY.s1.md §4 (the first-time-load
  recipe: `git pull` + containerized importer). That is insufficient for an *update*:
  the app code, including `app/services/rubric_overrides.json`, is `COPY`-baked into
  the `ori-app` image (not volume-mounted). After `git pull`, the host files were
  updated but the *running* container still loaded the OLD overrides via
  `rubrics._load_overrides()` at import time — so `resolve_name` returned the stale
  short shade-only names and the server importer wrote them into `dictionary`. First
  server spot-check confirmed the defect (48667 → «Чёрный оникс» instead of the full
  «Гель-лак для ногтей — Чёрный оникс»).
- **Fix:** Ran the documented DEPLOY.s1.md «Обновление работающего сервера» procedure
  — `docker compose -f docker-compose.prod.yml up -d --build` to rebuild the image with
  the new file, waited for `ori-app` health, then re-ran the containerized importer.
  Server DB now shows the corrected full names.
- **Files modified:** none (deploy-procedure only).
- **Commit:** n/a (server-side operation).

## Verification Results

- Task 1 automated verify: OK (1784 entries, all 121 names merged); numstat 121/121.
- Task 2 automated verify: OK (local dictionary mismatch count = 0).
- Task 3: origin has `5940b3f`; s1 re-imported the corrected справочник over SSH after
  the image rebuild; three spot-check codes show corrected names on the server;
  live site returns HTTP 303. No human-needed fallback was required — the full deploy
  completed over SSH.

## Self-Check: PASSED

- FOUND: app/services/rubric_overrides.json (modified, committed in 5940b3f)
- FOUND: commit 5940b3f in git log (pushed to origin/main)
- Local dictionary table: 121/121 corrected names (mismatch 0)
- s1 dictionary table: spot-check 3/3 corrected names after rebuild
