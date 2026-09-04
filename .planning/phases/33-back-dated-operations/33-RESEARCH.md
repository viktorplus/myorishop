# Phase 33: Back-Dated Operations — Research

**Researched:** 2026-09-04
**Repo state:** `fba02f2` (2026-09-04), branch `main`, alembic head `0026`
**Domain:** Alembic dual-dialect ledger migration + SQLite/PostgreSQL append-only triggers + SQLAlchemy 2.0 bulk-insert default semantics + htmx 2.0.10 client-side constraint validation
**Confidence:** HIGH (every finding below was executed or read at `file:line` in this repo; nothing is from training data)

**Scope of this pass — NARROW.** This is not a greenfield research pass. `.planning/ROADMAP.md:322` says *"Research flag: not needed"* for this phase, and 25 decisions are already LOCKED in `33-CONTEXT.md`. This document does exactly three things:

1. closes the blocking `needs verification` items V1–V4 + the D-13 htmx question by **running code** and **reading HEAD**;
2. supplies the `## Validation Architecture` the Nyquist gate requires;
3. audits every `file:line` the planner is about to copy verbatim out of CONTEXT.

Nothing here re-derives the approach. Where milestone research already settled something, it is cited, not restated.

---

## Summary

All four blocking verifications are **closed**, and two of them came back the *opposite* of what the milestone research assumed:

- **V1 is answered NO.** An explicit `None` in `session.execute(insert(model), rows)` does **not** beat a column default on SQLAlchemy 2.0.51. SQLAlchemy drops `None`-valued keys from the emitted column list and substitutes the Python `default=` (or omits the column so the DDL `server_default` fires). Proven end-to-end through the real `apply_merge`: a cash record with `currency` popped lands `'RUB'`, not NULL. **`CashMovement.currency` is therefore not a live bug**, and SYNC-12 becomes a *pinning test*, not a fix.
- **V2 is answered "drop, not reject".** An older-code receiver silently discards an unknown wire field and returns a success report. This confirms D-01's premise exactly — but it also means the SYNC-12/V2 test must assert **drop**, not the "reject-not-drop" phrasing carried in `.planning/ROADMAP.md:320`.
- **V4 is answered "safe, and both necessary and sufficient".** A backfill `UPDATE` of a column *not named* in the trigger's `WHEN` enumeration succeeds and covers 100% of rows; the identical `UPDATE` is `ABORT`ed the moment the trigger names the column. The LOCKED ordering (`add_column` → backfill → extend trigger) is exactly right, and migration `0024`→`0026` is the shipped precedent that already ran this order on s1.
- **D-13's htmx question splits by surface.** On the 8 desktop `<form hx-post>` surfaces the browser's own interactive validation fires before `submit`, so a `max` violation shows a **native bubble** — safe. On the mobile wizards the `hx-post` sits on a `<button type="submit">`, htmx `preventDefault()`s the click (`ht()` in `htmx.min.js`), so **neither** native nor htmx validation runs and the request goes out to be refused by the server's Russian error — also acceptable. The feared silent halt requires `hx-post` on the `<form>` *plus* a non-submit trigger, which no ledger surface has.

**One new, previously-unknown hazard was found and it changes what the migration must say.** `alembic downgrade 0026 → 0023` was executed against a scratch DB built by `alembic upgrade head`: it **silently destroyed both `cash_movements_no_update` and `cash_movements_no_delete`**, because `0024.downgrade()` uses `op.batch_alter_table(...).drop_column(...)`, which forces a SQLite table recreate. The new migration's `downgrade()` must therefore (a) never use batch mode, and (b) restore the pre-`0027` trigger DDL **before** dropping the columns — SQLite refuses to drop a column a live trigger references.

**Primary recommendation:** plan the migration's `downgrade()` as the exact mirror of the `upgrade()` ordering constraint (restore old triggers → `op.drop_column` plain), make all four new columns `nullable=True` with **no** `default=` and **no** `server_default=`, and make SYNC-13's proof a whitespace-normalised diff of `sqlite_master` triggers from an `alembic upgrade head` DB against `app/db.py::APPEND_ONLY_TRIGGERS` — one test that pins all five lockstep artifacts at once.

---

## User Constraints (from CONTEXT.md)

`.planning/phases/33-back-dated-operations/33-CONTEXT.md` is **authoritative and must be read in full** before planning. It is not duplicated here (a copy would drift). Summary of what is binding:

### Locked decisions — D-01 … D-25 (`33-CONTEXT.md:27-334`)

| ID | One-line | CONTEXT line |
|----|----------|--------------|
| D-01 | Push schema gate is ASYMMETRIC (refuse client-ahead only) | `:32-46` |
| D-02 | New `push_schema_ok` in `app/services/sync.py`; `offline.py` untouched | `:48-53` |
| D-03 | Keep the `""` escape hatch on both sides | `:55-60` |
| D-04 | Lexicographic revision ordering bought with a TEST, not a parser | `:62-68` |
| D-05 | Gate AFTER `parse_exchange`, on `batch.schema_version` | `:70-76` |
| D-06 | `409` + a fifth RU constant naming both versions | `:78-83` |
| D-07 | SYNC-11 needs a TEST, not code | `:85-88` |
| D-08 | Reuse `format_sync_message`; `#sync-badge` must NOT be suppressed | `:90-101` |
| D-09 | Auto-sync backs off to `MAX_INTERVAL_SECONDS` on `schema_mismatch` | `:103-113` |
| D-10 | Visible `<input type="date">`, last field before `.form-actions` | `:117-124` |
| D-11 | Mobile: date in the persistent shell form (3 wizards) / final step (2 wizards) | `:126-142` |
| D-12 | Two distinct RU errors under `errors["op_date"]`, raised in the SERVICE layer | `:144-150` |
| D-13 | `max="{{ today }}"` — conditional on the htmx check (**resolved below**) | `:152-163` |
| D-14 | Mobile error rendering is NOT uniform; handle per file | `:165-173` |
| D-15 | No `today` Jinja global; pass per-context or register a zero-arg callable | `:175-180` |
| D-16 | DATE-01 covers 6 desktop + 2 cash + 5 mobile wizards + 1 mobile возврат | `:184-205` |
| D-17 | `record_operation` gains a kwarg with a default; 9 real call sites of 12 | `:207-214` |
| D-18 | Both dates as a muted SECOND LINE in «Когда», only when they differ | `:218-230` |
| D-19 | PRIMARY date in «Когда» is the business date | `:232-242` |
| D-20 | «задним числом» filter is a FOURTH `<select name="dated">` | `:244-253` |
| D-21 | Mobile MIRRORS desktop | `:255-260` |
| D-22 | `_SORT_MAP`/`_DEFAULT_ORDER` NOT changed; no business-date sort this phase | `:262-268` |
| D-23 | CSV: «Когда» BECOMES the business date; «Внесено» appended LAST | `:272-292` |
| D-24 | Switch «Последняя приёмка», batch auto-name, identification labels | `:294-324` |
| D-25 | `stale_products` STAYS on `created_at`; the coupled template edit is CANCELLED | `:326-334` |

### Six LOCKED ordering constraints (`.planning/ROADMAP.md:309-316`)

Restated verbatim in ROADMAP; **a planner may not silently reorder them**. This research adds a *seventh*, derived constraint (see `## Newly discovered migration constraints`): the `downgrade()` must mirror the `upgrade()` ordering.

### Claude's Discretion (`33-CONTEXT.md:336-344`)

RU wording within the D-06/D-12 shapes; the third option label on the История select; date-field placement inside the mobile shell; test naming and placement.

### Deferred / OUT OF SCOPE (`33-CONTEXT.md:517-541`)

Sticky business date across a session; `stale_products` on the business date; the `<details>` disclosure; `.filter-bar { flex-wrap }`. **Also out of scope milestone-wide** (`.planning/REQUIREMENTS.md:109-110`): bumping Alembic to 1.19.x, and **any new dependency**.

---

## Project Constraints (from CLAUDE.md)

Directives extracted from `E:\dev\myorishop\CLAUDE.md` + the global `CLAUDE.md` that bind this phase's plans:

| # | Directive | Consequence for Phase 33 |
|---|-----------|--------------------------|
| PC-1 | GSD workflow enforcement — no direct repo edits outside a GSD command | Plans must be executed via `/gsd-execute-phase`, not ad-hoc |
| PC-2 | **Portable ORM only**; no SQLite-specific SQL (`INSERT OR REPLACE`, `strftime`) | `business_date_expr` must be `func.coalesce(...)`, never `substr()` in a query; the only dialect SQL allowed is inside the migration's `_SQLITE_DDL`/`_PG_DDL` branches |
| PC-3 | Money as integer minor units; never FLOAT | Unaffected this phase, but the CSV column reshuffle (D-23) must not touch amount cells |
| PC-4 | `render_as_batch=True` for SQLite (`alembic/env.py:57,85`) | **Live hazard** — see `## Newly discovered migration constraints`; batch mode is enabled and will recreate the table for any non-`add_column` op |
| PC-5 | Timezone-aware UTC timestamps everywhere; store UTC, display local | The backfill must convert through `ZoneInfo(settings.display_tz)`, never slice the ISO string |
| PC-6 | Additive-change default: never add a second mechanism for a job the project already solves | Reinforces D-02 (do not touch `offline.schema_version_ok`) and ordering constraint 6 (`business_date_bounds` is a *sibling* of `local_day_bounds_utc`, not an overload) |
| PC-7 | `needs verification` must be stated explicitly with the smallest way to check | Every unresolved item below carries its exact command |
| PC-8 | Never claim something works unless it was actually run | Every VERDICT below cites either executed output or `file:line` |
| PC-9 | Do not start/kill servers or containers | V13/V14 are recorded as deployment-time tasks, not attempted |
| PC-10 | Russian for operator-facing prose; English for code/identifiers/commits | D-06/D-12 strings in RU; column names, helpers, tests in English |

---

## Phase Requirements

| ID | Description (`.planning/REQUIREMENTS.md`) | Research support |
|----|-------------------------------------------|------------------|
| SYNC-10 | Push with an unknown schema version rejected with a RU message, not silently dropped | V2 proves the silent drop is real (`merge.py:189` keeps the key, `merge.py:460` projects it away, `apply_merge` returns success). Gate site verified at `app/routes/sync.py:111-114`; `current_schema_version` at `app/services/sync.py:225-235`; RU constants at `app/routes/sync.py:51-54` |
| SYNC-11 | A rejected push leaves rows unsynced | Verified: `synced_at` is stamped only after `raise_for_status()` — `app/services/sync_client.py:376` then `:384-393`; `last_sync_at` advances only for `ok`/`partial` at `app/routes/sync.py:269-273` and `app/services/sync_client.py:597-599`. D-07 stands: test only |
| SYNC-12 | A pre-column client's cash movement lands correctly | **V1 executed** — it already lands correctly (`'RUB'`, not NULL). SYNC-12 is a pinning test; no `_ledger_row` change needed |
| SYNC-13 | Triggers proven live against an `alembic upgrade head` DB | V3 confirmed (`tests/conftest.py:27` and `:294` both use `create_all`). Executed proof-of-concept: an `alembic upgrade head` DB's four triggers are whitespace-identical to `app/db.py::APPEND_ONLY_TRIGGERS` today — that comparison IS the test |
| DATE-01 | Date field on every ledger-writing surface | D-16 surface list audited — **zero drift**, all 14 template `file:line` refs exact |
| DATE-02 | Future date rejected in RU; any past date accepted | `parse_optional_expiry` idiom verified at `app/services/receipts.py:46-66`; `EXPIRY_ERROR` at `:43`; `CLOSE_DATE_ERROR` at `app/services/active_catalog.py:21` |
| DATE-03 | Every period-scoped figure buckets by the business date, in ONE pass | 14 `local_day_bounds_utc` call sites + 7 imports: **zero drift**. 9 must-switch predicates: 8 exact, 1 off-by-one (see drift table) |
| DATE-04 | Technical timestamp keeps audit / display order / sync selection | Pitfall-16 baseline confirmed: `business_date` occurs **0 times** anywhere in the repo, so the guard starts from a clean zero |
| DATE-05 | Both dates in История and the CSV exports | `history_rows.html:125,132-147,233,240` all exact; `export.py:135,137-147,156,211-212,216,219` all exact. **One coupled edit is missing from D-23 — see drift table row CD-9** |
| DATE-06 | «задним числом» marker + filter | D-20's premises verified: exactly ONE `type="checkbox"` in all templates (`pages/settings.html:28`); the three sibling selects at `history_rows.html:27-35,39-45,54-62` are exact; `.filter-bar` closes at `:64` |
| DATE-07 | Byte-identical past-period totals after the migration | Executed tz arithmetic below gives the exact fixture values that make this provable; see `## Validation Architecture` |
| DATE-08 | A pre-update client's row still appears, bucketed by entry date | V1 proves a `nullable`, default-less column receives NULL from `_ledger_row` (`INSERT INTO t (id) VALUES (?)` — the column is omitted), so read-time `COALESCE` is the only thing needed |

---

## Resolved Verifications

Every verdict below is either **executed** (command + real output shown) or read at `file:line` in `fba02f2`.

### V1 — does an explicit `None` beat `server_default` in `session.execute(insert(model), rows)`?

**Method.** Two executed probes. (a) The 6-line inverted merge test drafted at `.planning/research/ARCHITECTURE.md:281-285`, run through the *real* `merge.parse_exchange` → `merge.apply_merge` against a `create_all`+`APPEND_ONLY_TRIGGERS` SQLite DB. (b) A four-column variant matrix isolating `default=` / `server_default=` / both / neither, with SQLAlchemy's emitted SQL captured via a `before_cursor_execute` listener.

**Executed output (a) — the inverted merge test:**

```
V1a: control — a cash record WITH currency present
  landed currency = 'RUB'

V1b: THE TEST — record.pop('currency') (a pre-0024 client's payload)
  wire data has 'currency'?  False
  _ledger_row projection: 'currency' in row = True
  _ledger_row projection: row['currency'] = None
  RESULT: INSERTED, currency = 'RUB'
```

**Executed output (b) — the variant matrix and the emitted SQL:**

```
executemany -> all keys present, values None (the _ledger_row shape)
  a(py-def)='RUB'  b(srv-def)='RUB'  c(both)='RUB'  d(none)='X'  e(nullable+def)='2000-01-01'
executemany -> keys ABSENT entirely
  a(py-def)='RUB'  b(srv-def)='RUB'  c(both)='RUB'  d(none)='X'  e(nullable+def)='2000-01-01'

Emitted SQL for the executemany-with-Nones case
  SQL: INSERT INTO t (id, a, c, d, e) VALUES (?, ?, ?, ?, ?)
  params: ('r6', 'RUB', 'RUB', 'X', '2000-01-01') | executemany: False

--- NOT NULL, no default, explicit None ---   RAISED IntegrityError: NOT NULL constraint failed: t.f
--- nullable, no default, explicit None ---   g = None
  SQL: INSERT INTO t (id) VALUES (?) | params: ('n1',)
```

**Mechanism (visible in the emitted SQL).** SQLAlchemy 2.0.51 **removes every `None`-valued key from the INSERT column list**, then: a column with a Python-side `default=` has the default *materialised into the bound params* (`a`, `c`, `e` → `'RUB'`, `'RUB'`, `'2000-01-01'`); a column with only `server_default=` is *omitted from the statement entirely* (`b` is absent from `INSERT INTO t (id, a, c, d, e)`) so the DDL DEFAULT fires; a column with neither is also omitted and therefore takes the DDL's implicit NULL — which raises `NOT NULL constraint failed` if the column is `nullable=False`.

**VERDICT (V1):**
- **NO.** An explicit `None` does **not** defeat `default=` or `server_default=` on SQLAlchemy 2.0.51 (`pyproject.toml` pins `sqlalchemy==2.0.*`; installed 2.0.51).
- **`CashMovement.currency` (`app/models.py:526-529`) is NOT a live bug.** A pre-0024 client's cash movement lands `'RUB'`. Nothing in `merge._ledger_row` needs repair.
- **The four new columns must still be `nullable=True`** — but the reason is now *positive*, not defensive: a `nullable=False` column with **no** default is the only shape that raises, and it would roll back the whole push (all-or-nothing, `app/routes/sync.py:121`). Give the four columns `nullable=True`, **no `default=` and no `server_default=`** — that is the only combination that lets a pre-update client's row land as NULL, which is what DATE-08 needs.
- **Do not add a `server_default` to the new columns "for safety".** Besides defeating DATE-08's NULL sentinel, a `server_default` that is a `ClauseElement` (`sa.text(...)`, `sa.func.now()`) forces a SQLite table recreate in batch mode and would destroy all four triggers — see `## Newly discovered migration constraints`.

### V2 — what does an older-*code* receiver do with an unknown wire field?

**Method.** Read `merge.parse_exchange` and `merge._ledger_row`, then executed the case by pushing a `cash_movement` record carrying a `business_date` key that the receiver's schema does not have. The receiver's field set is derived from the model mapper at `app/services/merge.py:80-83`, so "older code" == "a model without the column" == today's HEAD.

**Evidence at `file:line`:**

- `app/services/merge.py:189` — `data = {key: value for key, value in obj.items() if key != "kind"}`. **No unknown-key check anywhere in `parse_exchange`**; the loop validates format version, kind membership, id, ledger-required fields, money types and `synced_at` — never the *presence* of extra keys.
- `app/services/merge.py:460` — `row = {column: data.get(column) for column in KIND_TO_FIELDS[kind]}`. The projection is over the **receiver's** columns; anything else is dropped.
- `app/routes/sync.py:112` returns `400 MALFORMED_BATCH_ERROR` only on `ValueError` from `parse_exchange`; an unknown field never raises one.

**Executed output:**

```
V2: an OLDER-CODE receiver meets an unknown wire field
  receiver's KIND_TO_FIELDS['cash_movement'] = ['amount_cents','author_id','category','created_at',
     'created_by','currency','device_id','id','note','sale_id','seq','synced_at']
  parse_exchange kept the unknown key?  True
  _ledger_row kept the unknown key?     False
  RESULT: ACCEPTED, cash_inserted = 1
  -> the unknown field was SILENTLY DROPPED behind a success
```

**VERDICT (V2):** **Silently DROPS, behind a 200.** D-01's premise (`33-CONTEXT.md:32-46`) is confirmed exactly: the loss is one-directional and unrecoverable, because `sync_client.py:384-393` then stamps `synced_at` on rows whose new field never landed.

> ⚠ **Correction for the planner.** `.planning/ROADMAP.md:320` and `33-CONTEXT.md:554-556` both phrase the V2 check as *"assert reject-not-drop"*. That expectation is **false**. The test must assert **drop** — i.e. `report.cash_inserted == 1` and the column absent from the stored row — and then assert that `push_schema_ok` (SYNC-10) is what converts that drop into a 409. A test written to the ROADMAP phrasing will fail for the wrong reason and invite someone to "fix" `merge.py`, which is not the plan.

### V3 — does the test suite build schema via `create_all`?

**Already answered in CONTEXT; confirmed here, with the exact collision surface the new test must avoid.**

| Fixture | Line | Build method |
|---------|------|--------------|
| `engine(tmp_path)` | `tests/conftest.py:22-32` | `build_engine()` → `Base.metadata.create_all(engine)` at `:27`, then `for statement in APPEND_ONLY_TRIGGERS` at `:29` |
| `sync_driver_pair` server DB | `tests/conftest.py:293-298` | `build_engine(str(tmp_path / "server.db"))` at `:293`, `Base.metadata.create_all(server_engine)` at `:294`, triggers at `:296` |

**Existing fixture names in `tests/conftest.py` a new fixture must not shadow:** `engine` (:23), `session` (:36), `product` (:43), `warehouse` (:57), `batch` (:66), `stocked_product` (:80), `customer` (:118), `client` (:133), `anon_client` (:191), `device_client` (:221), `sync_driver_pair` (:262), `login` (:349), `past_sale` (:367), `mobile_client_factory` (:435).

**VERDICT (V3):** confirmed. Neither existing DB is migration-proving. SYNC-13's new fixture should be named distinctly (suggested: `alembic_engine` / `migrated_engine`) and must **not** be added to `conftest.py`'s `engine` chain — every one of the 14 fixtures above transitively depends on `engine`, and re-pointing it at Alembic would change the whole suite's build path.

**And a second consequence, already noted at `33-CONTEXT.md:492-495`:** because both DBs lack an `alembic_version` table, `current_schema_version` (`app/services/sync.py:225-235`) returns `""` in every existing sync test. D-03's `""` escape hatch is load-bearing; the gate's own tests must inject `schema_version` explicitly or monkeypatch `current_schema_version`.

### V4 — does the backfill `UPDATE` trip the pre-rewrite trigger, and does it cover every row?

**Method.** Read the trigger DDL, then executed the backfill against a live SQLite DB carrying the shipped `APPEND_ONLY_TRIGGERS`.

**What the trigger actually fires on** (`app/db.py:64-79`, mirrored by `alembic/versions/0026_...py:42-58` for SQLite and `:63-76` for PostgreSQL):

```sql
CREATE TRIGGER cash_movements_no_update
BEFORE UPDATE ON cash_movements
FOR EACH ROW WHEN
     NEW.id           IS NOT OLD.id
  OR NEW.category     IS NOT OLD.category
  ...
BEGIN SELECT RAISE(ABORT, 'cash ledger is append-only'); END
```

It is **not** `UPDATE OF <cols>` and it is **not** "any UPDATE". It is a **value-based `WHEN` over an explicit column enumeration**: the trigger body runs only if one of the enumerated columns actually changes value. A column absent from the enumeration is invisible to the guard — which is precisely Pitfall 1's fail-open, and equally precisely why the backfill is safe before the rewrite.

**Executed output:**

```
V4: does an UPDATE of a column NOT named in the trigger fire it?
  RESULT: backfill UPDATE SUCCEEDED, rows updated = 3
  coverage: 3/3 rows have business_date set

V4b: and once the trigger DOES name it, is the same UPDATE blocked?
  RESULT: UPDATE BLOCKED — IntegrityError (sqlite3.IntegrityError) cash ledger is append-only
  [SQL: UPDATE cash_movements SET business_date = '2020-01-01']
```

**Shipped precedent.** `alembic/versions/0024_cash_movement_currency.py:45-47` backfills `cash_movements.currency` with a bare `op.execute("UPDATE ...")`, and the trigger only learned about `currency` two revisions later in `0026`. That exact order has already run on s1 without incident.

**VERDICT (V4):**
- The backfill **does not** trip the pre-rewrite trigger, on **either** dialect (the PostgreSQL branch uses the same enumerated `WHEN (...)` shape, `0026:63-76`).
- It **does** cover every row (3/3 in the probe; the `UPDATE` is unfiltered).
- LOCKED ordering constraint 3 is therefore both **necessary** (reversed, the backfill aborts mid-upgrade) and **sufficient** (nothing else blocks it).
- ⚠ **PostgreSQL was not exercised locally** — no PG instance is available on this machine and starting one is forbidden by CLAUDE.md. This is provable in CI via the existing `tests/test_pg_parity.py` harness; see `## Validation Architecture` row VA-3.

### D-13 — does htmx 2.0.10 halt a `max`-violating submit silently?

**Method.** Read the **vendored** `app/static/htmx.min.js` (this is what actually ships — no CDN, per CLAUDE.md), plus the repo's `htmx-config` meta tags and the actual form markup of all 8 desktop ledger forms and the mobile wizards.

**Facts extracted from the vendored source:**

| Fact | Evidence |
|------|----------|
| Version is exactly 2.0.10 | `app/static/htmx.min.js` — `..., version:"2.0.10"}` in the config literal |
| htmx uses `checkValidity()`, not `reportValidity()` | `function an(e,t){const n=e;if(n.willValidate){ae(n,"htmx:validation:validate");if(!n.checkValidity()){...` |
| `reportValidity()` is gated on a config flag that **defaults to false** | same function: `...&&Q.config.reportValidityOfForms){n.reportValidity()}`; the default literal is `reportValidityOfForms:false` |
| The repo never overrides that flag | `app/templates/base.html:18-19`, `app/templates/mobile_base.html:12-13`, `app/templates/auth_base.html:12` set only `responseHandling` |
| htmx runs its own validation **only** when the hx-verb element IS a form, or `hx-validate="true"` | `...hx-validate")==="true";if(s.lastButtonClicked){l=l&&s.lastButtonClicked.formNoValidate!==true}if(t!=="get"){fn(n,o,i,Nt(e),l)}` |
| `hx-validate` appears **nowhere** in `app/templates` | `grep -rn "hx-validate" app/templates` → no matches |
| htmx `preventDefault()`s a click on a `button[type=submit]` that has a form | `function ht(e,t){if(e.type==="submit"&&t.tagName==="FORM"){return true}else if(e.type==="click"){const n=t.closest('input[type="submit"], button');if(n&&n.form&&n.type==="submit"){return true}...` |

**Applied to the actual markup:**

| Surface | Where `hx-post` lives | Submit control | What a `max` violation does |
|---------|----------------------|----------------|------------------------------|
| `partials/receipt_form.html:24`, `sale_form.html:41`, `writeoff_form.html:19`, `correction_form.html:23`, `transfer_form.html:21`, `return_form.html:28`, `withdraw_form.html:17`, `deposit_form.html:11` | on the **`<form>`** | native `<button type="submit">` (`:95`, `:89`, `:80`, `:102`, `:72`, `:39`, `:64`, `:54`) | Browser interactive validation runs **before** the `submit` event; `submit` never fires, so htmx never sees it. **Native bubble shown.** Safe. |
| Mobile приход/продажа/списание shells (`mobile_pages/receipts.html:12`, `sales.html:11`, `writeoff.html:19`) | on the **`<button>`** (e.g. `receipts_step_confirm.html:51`: `<button type="submit" hx-post="/m/receipts" hx-include="closest form">`) | that same button | htmx cancels the click's default action (`ht()` → `preventDefault`), so native validation never runs; and htmx's own validation is skipped because the hx-post element is a button, not a form. **`max` is inert; the request goes out and the server's RU error is what the operator sees.** |
| Mobile корректировка/перемещение final steps (`corrections_step_value.html`, `transfers_step_dest.html:28` `<form ... hx-post="/m/transfers">`) | on the **`<form>`** | native `<button type="submit">` | Same as desktop — **native bubble shown.** |

**VERDICT (D-13):** **`max="{{ today }}"` does NOT produce a silent halt on any surface this phase touches.** Add it. On the 8 desktop forms and the 2 mobile final-step forms the operator gets the browser's own message; on the 3 mobile shell wizards the attribute is simply inert and the server's `OP_DATE_FUTURE_ERROR` is the sole guard — which is the intended fallback anyway. The silent-halt failure mode requires `hx-post` on a `<form>` *combined with* a non-native-submit trigger, which no ledger surface has.

**Two supporting facts worth carrying into the plan:**
- The repo's two existing `max` attributes (`partials/return_form.html:35`, `mobile_partials/return_confirm.html:40`) sit on `<input type="text">`, where `max` has **no** constraint-validation effect at all. So Phase 33's date input will be the app's **first live `max` constraint** — nobody has seen this behaviour before, which is why D-13 flagged it.
- **Residual browser check (cheap, keep it as a plan task):** load `/receipts`, set the date input to tomorrow, click «Сохранить приход», confirm a native bubble appears and no request is issued (Network tab empty). Then repeat on `/m/receipts` step 4 and confirm the request IS issued and the RU error renders. This is the only part of D-13 that source reading cannot settle, because it depends on the browser's implementation of interactive validation.

### V15 — is Alembic still pinned where the plan expects?

- `pyproject.toml:6` pins **`alembic==1.18.*`**; the resolved environment reports **alembic 1.18.5**, sqlalchemy 2.0.51 (executed).
- `.planning/REQUIREMENTS.md:109` puts a 1.19.x bump explicitly **Out of Scope** for the whole milestone.

**VERDICT (V15):** the question as phrased ("is 1.19.1 still the newest") is **moot and was not checked** — the pin is `1.18.*`, so no upgrade can happen without editing the pin, and the answer cannot change the action. **Do not bump.** `[ASSUMED]`-free: the pin and installed version are executed facts; the upstream release state is deliberately unqueried.

---

## Conflicts with locked decisions

**No locked decision (D-01 … D-25) is contradicted by this research.** Three *stated premises* are factually wrong, and one *enumerated list* has a gap. In every case the decision itself survives; only the supporting sentence needs correcting so the planner does not propagate a false claim into a plan comment.

### CF-1 — `<details>` DOES appear in `app/templates` (D-10 rationale)

`33-CONTEXT.md:120-121` justifies rejecting a collapsed disclosure with *"`<details>` appears nowhere under `app/templates`, so it would be a brand-new UI idiom"*.

**Actual:** `<details>` appears in **two** templates:
- `app/templates/partials/product_rows.html:81` — `<details><summary>Партии ({{ product_batches | length }})</summary>` (batch list disclosure)
- `app/templates/partials/user_rows.html:39` — `<details><summary>Сбросить пароль</summary>`, with a comment at `:37-38` explicitly calling it *"native `<details>` reveal (no client JS, no extra GET route)"*

**Impact: none on the decision.** D-10 stands on its other, independently sufficient arguments — the operator touches the field often (no lower bound on back-dating), and a 422 on `op_date` pointing at a collapsed field is a real usability defect. **Action for the planner:** do not repeat the "nowhere in the codebase" claim in a code comment or plan rationale; it is false and a future reader will catch it.

### CF-2 — `merge._ledger_row` does NOT need fixing (SYNC-12 / `<code_context>` premise)

`33-CONTEXT.md:496-501` states *"`session.execute(insert(model), rows)` … appears to bypass both the Python `default=` and the DDL `server_default`. **This is load-bearing for D-01:** the asymmetric gate's «accept behind» promise is only true once SYNC-12 fixes `_ledger_row`."*

**Actual (V1, executed):** it bypasses neither. The accept-behind promise is **already true today**, with no code change.

**Impact: D-01 is unchanged and in fact strengthened** — the asymmetric gate can accept a behind client immediately, without waiting on a `_ledger_row` repair. **Action for the planner:** SYNC-12's plan must be re-shaped from *"fix `_ledger_row`"* to *"pin the current behaviour with a regression test"*. Do **not** write a defensive `{k: v for k, v in row.items() if v is not None}` filter into `_ledger_row` — that would be a second mechanism for a job SQLAlchemy already does (CLAUDE.md PC-6), and it would *break* DATE-08 by suppressing the deliberate NULL a pre-update client must produce.

### CF-3 — "assert reject-not-drop" is the wrong assertion (V2 phrasing)

`.planning/ROADMAP.md:320` and `33-CONTEXT.md:555-556`. See the V2 verdict above. **Action:** the test asserts **drop**, and SYNC-10's gate is what makes the drop unreachable in production.

### CF-4 — `dashboard.period_metrics`'s signature does NOT change

`33-CONTEXT.md:453-455` says `app/services/dashboard.py:95` is a call site *"whose signature changes `(start_iso, end_iso)` → `(start_day, end_day)`"*.

**Actual:** `app/services/dashboard.py:75-81` already reads
`def period_metrics(session: Session, start_day: date, end_day: date, tz_name: str, currency: str = DEFAULT_CURRENCY) -> dict:` — it **already** takes calendar days. Only the *body* at `:95` changes (`local_day_bounds_utc(...)` → `business_date_bounds(...)`), and its two downstream calls at `:96-97` (`sales_profit_report`, `cash_expense_total`) keep receiving the same two bound strings.

**Impact: none on any decision** — it makes the edit *smaller* than CONTEXT implies. **Action:** do not plan a signature change or a caller sweep for `period_metrics`; there are no callers to update.

---

## Call-site drift corrections

Audited against `fba02f2`. **Nine corrections out of ~120 references checked.** Everything not listed below was verified **exact**.

### Verified exact (no drift) — the planner may copy these verbatim

| Set | Count | Result |
|-----|-------|--------|
| `local_day_bounds_utc` call sites in `app/` | 14 | **All 14 exact.** `routes/reports.py:111,145,212`; `routes/finance.py:89,344,376`; `routes/mobile_finance.py:82,347,377`; `routes/history.py:103`; `routes/mobile_history.py:88`; `services/customers.py:446,468`; `services/dashboard.py:95` |
| Import lines to change | 7 | **All 7 exact.** `routes/reports.py:10`, `routes/finance.py:17`, `routes/mobile_finance.py:22`, `routes/history.py:11`, `routes/mobile_history.py:25`, `services/customers.py:17`, `services/dashboard.py:20` |
| `record_operation` call sites | 12 | **All 12 exact.** `catalog.py:137,279,288`; `corrections.py:120`; `receipts.py:160,186,241`; `returns.py:156`; `sales.py:287`; `transfers.py:176,184`; `writeoffs.py:105`. Definition at `ledger.py:37-49`, `created_at=utcnow_iso()` at `:123` |
| `record_cash_movement` call sites | 3 | **All 3 exact.** `finance.py:188`, `returns.py:174`, `sales.py:310`. Definition at `finance.py:48-57` |
| D-16 write-surface templates | 14 | **All exact** — 6 desktop forms, 2 cash forms, 3 mobile shells, 2 mobile final steps, 1 mobile возврат, plus their route render sites (`routes/returns.py:99,102,132,142,160`; `routes/mobile_returns.py:104,107,135,145,162`) |
| D-14 mobile error-render sites | 4 files | **All exact.** `receipts_step_confirm.html:19-21` (per-key, excludes `form` at `:20`); `transfers_step_dest.html:21-23,50,56`; `writeoff_step_reason.html:17-21` (loop-all); `corrections_step_value.html:13-17` (loop-all) |
| D-18/D-19/D-20 История refs | 8 | **All exact.** `history_rows.html:27-35`, `:39-45`, `:54-62`, `:118` (`colspan="10"`), `:125`, `:132-147`, `:233`, `:240` |
| D-23 CSV refs | 8 | **All exact.** `export.py:94-102`, `:135`, `:137-147`, `:156`, `:179`, `:185`, `:211-212`, `:216`, `:219` |
| MUST-NOT-switch `order_by` feeds | 8 of 9 | **Exact:** `finance.py:21`, `dashboard.py:156`, `sales.py:374`, `receipts.py:309`, `writeoffs.py:127`, `transfers.py:210`, `catalog.py:351`, `customers.py:352`. (`ledger.py` — see CD-5) |
| Other must-not refs | — | **Exact:** `merge.py:89`, `merge.py:456`; `sync.py:76`; `batches.py:55,71,97-98`; `active_catalog.py:21,36,66`; `dashboard.py:41,60-72`; `reports.py:224,236`; `reports_products.html:32` |
| D-24 borderline readers | — | **Exact:** `warehouses.py:100`; `warehouse_rows.html:29,71-74,75`; `customers.py:528-540`; `customer_insights.html:12`; `routes/returns.py:75,152`; `routes/mobile_returns.py:80,156`; `return_form.html:11`; `return_confirm.html:17` |
| Reusable assets | — | **Exact:** `sync.py:225-235`; `offline.py:61-71`; `sync_client.py:376,377-379,384-393,52,53,597-599`; `routes/sync.py:37-41,51-54,111-114,269-273`; `main.py:71-103,118-136`; `core.py:89-99,102-105,108`; `base.html:76`; `sync_status.html:15,16`; `result.html:26-29`; `mobile_sales.py:39`; `mobile_transfers.py:65,106,130`; `routes/__init__.py:227`; `reports.py:21` (`operation_currency_clause`); `style.css:72-77,188-193,363-368` |

### Corrections

| # | Claimed (CONTEXT / ROADMAP) | Actual at `fba02f2` | Severity |
|---|------------------------------|---------------------|----------|
| CD-1 | `reports.py:72-73` — sales-profit period predicate (the DATE-07 target) | **`reports.py:71-72`** (`:71` = `Operation.created_at >= start_iso`, `:72` = `< end_iso`; `:73` = `operation_currency_clause(currency)`) | off-by-one |
| CD-2 | `receipts.py:209-210` — batch auto-name; `receipts.py:209` — the local-today precedent (D-15) | **`receipts.py:208`** = `local_today = datetime.now(ZoneInfo(settings.display_tz)).date()`; **`:209`** = `batch_name = f"{product.name} — {format_ru_date(local_today.isoformat())}"`; **`:210`** = `batch = Batch(` | off-by-one; the D-24 "resolve the business date **before** line 209" ordering constraint actually means **before line 208** |
| CD-3 | `receipts.py:203-208` — the snapshot-rule comment D-24 cites | **`receipts.py:202-207`** | off-by-one |
| CD-4 | `receipts.py:46-65` — `parse_optional_expiry` | **`receipts.py:46-66`** (the second `return None` is at `:66`) | off-by-one |
| CD-5 | `ledger.py:234` in the must-not-switch list; `ledger.py:239` as the "recent N" feed | **`ledger.py:233`** = `.order_by(Product.created_at)` (a *Product* ordering, unrelated to the ledger); **`ledger.py:238`** = `.order_by(Operation.created_at.desc(), Operation.seq.desc())` — the actual recent-N feed. `:234` is `.limit(1)` | **wrong line** — the planner would guard the wrong statement |
| CD-6 | `operations.py:29-32` — `_SORT_MAP` and `_DEFAULT_ORDER` | `_SORT_MAP` spans **`:28-30`**, `_DEFAULT_ORDER` is **`:32`**. The cited span starts one line inside the dict literal | cosmetic |
| CD-7 | `routes/offline.py:228-243` (CONTEXT) / `:233-243` (REQUIREMENTS.md:34) — the 409 schema-refusal precedent | The schema gate is **`:232-243`**; **`:222-227`** is the raw-header peek; **`:228-230`** is the payload digest check | boundary drift |
| CD-8 | `style.css:304` — `.muted` | Selector `.muted {` is at **`:303`**; `:304` is `color: #6b7280;` | cosmetic |
| CD-9 | D-23 names **one** coupled `ORDER BY` edit: `export.py:135` for `sales.csv` | `stream_cash_movements_csv` has the **same** construct at **`export.py:214`** (`.order_by(CashMovement.created_at)`), and its `«Когда»` column at `:219` is on D-23's rewrite list. Under D-23's own argument ("the dump reads as unsorted by its own first column") this edit is required too, but it is **not enumerated anywhere** | **gap — the highest-value correction in this table** |
| CD-10 | `tests/test_reports.py:92` cited as the `local_day_bounds_utc` usage that keeps the helper alive | The file has **12** call sites (`:92,131,151,168,184,228,273,294,310,325,583,608`) | undercount; conclusion unchanged (the helper must not be deleted) |
| CD-11 | `routes/history.py:117-141` — the `qs_parts` re-serialization idiom | The comment block is `:117-126`; `qs_parts` itself is **`:129-142`**, `extra_qs` at **`:143`** | boundary drift |

**Test-side call sites of `local_day_bounds_utc` (which is why the helper must not be deleted) — verified totals:** `test_core.py` 4 dedicated tests (`:108,120,134,141`, calls at `:115,129,136,145,146,150`), `test_export.py:111,150,164,182,333`, `test_finance_reports.py` 12 sites (`:57,69,83,89,102,227,243,271,299,314,326,337`), `test_reports.py` 12 sites (see CD-10), `test_dashboard.py:211,215`, `test_attribution.py:228`, plus a docstring reference at `test_customers.py:623`. **Total: 36 test call sites across 6 files.**

---

## Newly discovered migration constraints

These were **not** in the milestone research and they change what the migration file must contain. All three are executed findings.

### NC-1 — `downgrade()` must be the MIRROR of `upgrade()`, and must never use batch mode

**Executed:** a scratch DB was built with `alembic upgrade head` (reaching `0026`), then downgraded:

```
$ DATABASE_URL=sqlite:///<scratch>/head.db uv run alembic downgrade 0023
INFO  Running downgrade 0026 -> 0025, cash_movements_no_update: guard the new currency column (CUR-02)
INFO  Running downgrade 0025 -> 0024, batches.cost_cents ...
INFO  Running downgrade 0024 -> 0023, cash_movements.currency ...

triggers after downgrade 0026->0023: ['operations_no_delete', 'operations_no_update']
```

**Both `cash_movements_no_update` and `cash_movements_no_delete` were silently destroyed.** The cause is `alembic/versions/0024_cash_movement_currency.py:51-52`, which drops the column inside `op.batch_alter_table(...)`. Alembic's `SQLiteImpl.requires_recreate_in_batch` (read from the installed `alembic.ddl.sqlite`, 1.18.5) returns `True` for **every** batch op except `add_column`, `create_index` and `drop_index` — so `drop_column` recreates the table and the triggers vanish with it. This is Pitfall 3, live and shipped, in HEAD.

**And the same function explains why the `upgrade()` side has been safe so far:** `add_column` returns `False` *unless* `col.server_default` is a `ClauseElement` (or a persisted `Computed`). `0024` added a NOT NULL column with the **string literal** `"RUB"` as `server_default`, so batch mode emitted a plain `ALTER TABLE ... ADD COLUMN` and the triggers survived. Confirmed by inspection of the alembic-built DB: all four triggers are present at head and are whitespace-identical to `app/db.py::APPEND_ONLY_TRIGGERS`.

**Rules the new `0027` must follow:**

1. `upgrade()`: use **`op.add_column(...)` directly** (LOCKED constraint 3 already says this). If a `server_default` is ever added, it must be a **plain string literal**, never `sa.text(...)`/`sa.func.*` — a `ClauseElement` default flips `requires_recreate_in_batch` to `True` and destroys all four triggers. (Per V1, the four columns should carry **no** default at all, so this is a guard-rail, not a plan.)
2. `downgrade()`: **restore the pre-`0027` trigger DDL FIRST, then `op.drop_column(...)` plain (never `batch_alter_table`).** The order is not optional — see NC-2.

### NC-2 — SQLite refuses to drop a column a live trigger references

**Executed:**

```
A) drop a trigger-referenced column WITHOUT restoring the trigger first:
   FAILED -> OperationalError error in trigger cm_no_update after drop column: no such column: NEW.business_date
B) restore the old trigger first, then drop:
   OK; triggers still present: ['cm_no_update']
```

Local SQLite is **3.45.1**, which supports native `ALTER TABLE ... DROP COLUMN`, and a native drop **preserves** triggers (verified separately). So the plain-`op.drop_column` route works — but only after the trigger has stopped naming the column.

**Therefore `0027.downgrade()` reads, in order:** ① drop + re-create `operations_no_update` and `cash_movements_no_update` with the `0026`-era enumeration (both `_SQLITE_DOWNGRADE_DDL` and `_PG_DOWNGRADE_DDL` halves, exactly the shape at `0026:81-116`) → ② `op.drop_column` × 4. Reversed, `alembic downgrade` aborts with `OperationalError` and leaves the schema half-migrated.

### NC-3 — the lockstep is currently intact, and the cheapest way to keep it is a trigger-SQL diff

**Executed** against the `alembic upgrade head` DB:

```
triggers present in the alembic-built DB: ['cash_movements_no_delete', 'cash_movements_no_update',
                                           'operations_no_delete', 'operations_no_update']
cash_movements_no_delete     alembic==app/db.py ? True
cash_movements_no_update     alembic==app/db.py ? True
operations_no_delete         alembic==app/db.py ? True
operations_no_update         alembic==app/db.py ? True
```

(comparison is `re.sub(r"\s+"," ",sql).strip()` on `SELECT sql FROM sqlite_master WHERE type='trigger'` vs each entry of `app/db.py::APPEND_ONLY_TRIGGERS`.)

**Gap in today's tripwires.** `tests/test_append_only_cursor.py` has two guards: `test_trigger_column_list_matches_schema` (`:246-258`) compares **models ↔ constants**, and `test_declared_constants_match_trigger_ddl` (`:261-290`) compares **constants ↔ `app/db.py` DDL**. **Nothing compares `app/db.py` ↔ the migrations.** That is the exact hole `0026` exists to patch after the fact. The trigger-SQL diff above closes it and simultaneously satisfies SYNC-13 — one test, all five artifacts.

**Sharp edge in the existing tripwire the planner must not trip.** `test_declared_constants_match_trigger_ddl:280,284` asserts `f"NEW.{column} " in ddl` — **with a trailing space**. The DDL in `app/db.py:37-85` is column-aligned with padding spaces. Adding `business_date` (13 chars) to `operations_no_update` and `reverses_movement_id` (20 chars) to `cash_movements_no_update` widens the alignment column; every existing line's padding must be re-flowed and **at least one space must remain after every column name**, or the tripwire goes red for a formatting reason and someone "fixes" it by weakening the assertion.

---

## Standard Stack

**No new dependency is in scope** (`.planning/REQUIREMENTS.md:110`; `.planning/research/STACK.md` rejects babel, freezegun/time-machine, JS date pickers, and disqualifies `sa.Date` twice over). Everything this phase needs is already installed and pinned.

| Component | Pinned | Resolved | Role in Phase 33 | Evidence |
|-----------|--------|----------|------------------|----------|
| SQLAlchemy | `2.0.*` | **2.0.51** | The `insert()`-default semantics V1 depends on | executed |
| Alembic | `1.18.*` | **1.18.5** | `0027`; `requires_recreate_in_batch` behaviour | executed; `pyproject.toml:6` |
| SQLite (stdlib) | — | **3.45.1** | native `DROP COLUMN`; trigger-reference refusal | executed |
| pytest | `9.1.*` | 9.1.1 | `[tool.pytest.ini_options] testpaths=["tests"] pythonpath=["."]` (`pyproject.toml:28-30`) | read |
| httpx | `0.28.*` | 0.28.1 | `TestClient`, sync driver tests | `pyproject.toml:10` |
| htmx (vendored) | — | **2.0.10** | D-13 | `app/static/htmx.min.js` |
| `zoneinfo` (stdlib) | — | — | the tz-correct backfill; `ZoneInfo(settings.display_tz)` | `app/core.py:9,120` |
| uv | — | — | `uv run alembic ...`, `uv run pytest` | executed |

**Storage type for `business_date`:** `String(10)` ISO text, matching `Batch.expiry` and `ActiveCatalog.close_date`. Already settled by execution in `.planning/research/STACK.md`; the two `reverses_*_id` columns are `String(36)` nullable with an ORM-only `ForeignKey` (the `sale_id`/`batch_id`/`author_id` precedent at `app/models.py:379-390,396-398`), no DB-level FK.

**Installation:** none. `uv sync` is already satisfied.

## Package Legitimacy Audit

**Not applicable — this phase installs no external packages.** No `uv add`, no `pip install`, no new entry in `pyproject.toml:5-27`. The package-legitimacy gate is vacuous here; there is nothing to verify against a registry. Every library named above is already a pinned, shipped dependency of this repo at `fba02f2`.

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

---

## Architecture Patterns

Only the two genuinely new artifacts are described. Everything else copies a shipped precedent listed in `33-CONTEXT.md:388-407`.

### Pattern 1: `business_date_bounds` — a SIBLING of `local_day_bounds_utc`, never an overload

**What.** A new helper in `app/core.py` that turns a local calendar range into **date-only ISO strings**, not UTC timestamps.

**Why it must be separate.** Executed proof of Pitfall 14 — comparing a date-only value against `local_day_bounds_utc`'s UTC-timestamp bounds:

```
Europe/Moscow      bounds=(2026-08-31T21:00:00+00:00, 2026-09-01T21:00:00+00:00)
                   date-only '2026-09-01' passes half-open? True      <- accidentally correct
America/New_York   bounds=(2026-09-01T04:00:00+00:00, 2026-09-02T04:00:00+00:00)
                   date-only '2026-09-01' passes half-open? False     <- row vanishes
UTC                bounds=(2026-09-01T00:00:00+00:00, 2026-09-02T00:00:00+00:00)
                   date-only '2026-09-01' passes half-open? False     <- row vanishes
```

> **Sharpening of Pitfall 14.** `.planning/research/PITFALLS.md` says the mistake is "off by a full day at any UTC− offset". The executed result is worse: it is broken at **every offset ≤ 0, including UTC itself**. It happens to work at `Europe/Moscow` (UTC+3) purely because `'2026-09-01' >= '2026-08-31T21:00:00+00:00'` and `'2026-09-01'` is a lexicographic prefix of `'2026-09-01T21:00:00+00:00'`. This is the single most convincing argument for LOCKED ordering constraint 6, and it belongs in the helper's docstring.

**Shape** (mirrors `app/core.py:108-126`, which is **not** modified and **not** deleted — 36 test call sites still use it as the sanctioned `created_at` fixture builder):

```python
def business_date_bounds(start_day: date, end_day: date) -> tuple[str, str]:
    """Date-only ISO bounds for the INCLUSIVE local range [start_day, end_day].

    The business date is already the operator's local calendar day, so no
    timezone conversion happens here — that is exactly why this is a separate
    helper from local_day_bounds_utc (app/core.py:108), which converts a local
    range into UTC *timestamp* bounds for the created_at column. Comparing a
    String(10) date against those timestamp bounds is a lexicographic accident
    that holds only at positive UTC offsets and silently drops rows at UTC+0
    and every negative offset (verified: 33-RESEARCH.md, Pattern 1).
    """
```

Note the contract difference the planner must not blur: `local_day_bounds_utc` returns a **half-open** `[start, end)` pair (the upper bound is midnight of the *next* day). `business_date_bounds` compares date strings, so it is naturally **closed** `[start_day, end_day]`. Whichever is chosen, every one of the 14 switched call sites must be updated consistently, and the helper's docstring must say which it is — this is the single easiest way to introduce a one-day off-by-one across nine reports at once.

**Anti-pattern to avoid:** adding a `date_only: bool` flag or a `column=` parameter to `local_day_bounds_utc`. `.planning/research/PITFALLS.md:348` locks this ("add a second, parallel helper beside it — do not modify or overload"), and CLAUDE.md PC-6 says the same.

### Pattern 2: `business_date_expr` — mirror `operation_currency_clause`'s COALESCE discipline

**Precedent to copy:** `app/services/reports.py:21` `operation_currency_clause`, whose docstring at `:22-40` documents the OUTER-join + COALESCE rule that lets a legacy `batch_id IS NULL` row bucket as RUB instead of vanishing.

**Shape:** `func.coalesce(Model.business_date, func.substr(Model.created_at, 1, 10))`.

Two constraints on this expression:

- **It must be a portable ORM construct.** `func.substr` renders as `substr(...)` on SQLite and `substr(...)` on PostgreSQL — both dialects have it, so this stays inside CLAUDE.md PC-2. Do **not** reach for `strftime`, `date_trunc`, `::date` or `SUBSTRING(... FROM ... FOR ...)`.
- **The read-time COALESCE is what makes DATE-08 a live property, not a fixture-only branch** (`33-CONTEXT.md:41-43`). It cannot be replaced by a backfill: rows arriving from an un-upgraded client *after* the migration have `business_date IS NULL` forever.

**The two-format asymmetry that makes this correct:** the fallback `substr(created_at,1,10)` is a **UTC** prefix, which is *not* the tz-correct local day — but for a row that a pre-update client wrote, there is no better information, and DATE-08 only requires that it "still appears in every report, bucketed by its entry date". The **backfill**, by contrast, has the row's full timestamp and MUST be tz-correct (see below). Do not let these two rules be unified into one.

### Pattern 3: the tz-correct backfill

`.planning/research/SUMMARY.md` §Reconciled Disagreements locks this as a correctness rule: a Python loop converting through `ZoneInfo(settings.display_tz)`, **not** `substr(created_at,1,10)` as a write-time backfill.

**Executed demonstration of why the two differ:**

```
Europe/Moscow      created_at=2026-08-31T21:30:00+00:00  tz-correct=2026-09-01  naive-substr=2026-08-31  differ=True
America/New_York   created_at=2026-09-01T02:00:00+00:00  tz-correct=2026-08-31  naive-substr=2026-09-01  differ=True
```

A single evening sale near local midnight lands in the wrong month with the naive cut. That is precisely the DATE-07 byte-identity failure.

**Migration-file constraint (WR-06, stated in `0026:27-29` and `app/db.py:20-22`):** *migrations must never import mutable app code.* So the backfill cannot `from app.config import settings`. It must read the timezone from the environment / a literal constant declared in the migration file itself, exactly the way `0024:30` declares `_DEFAULT_CURRENCY = "RUB"` rather than importing `app.core.DEFAULT_CURRENCY`. **This makes V14 (what `display_tz` s1 actually sets) a hard input to the migration's source text**, not a runtime lookup — see `## Deployment-time checks`.

---

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---------|-------------|-------------|-----|
| Stopping a `None` from overwriting a default in the merge insert | A `{k: v for k, v in row.items() if v is not None}` filter in `_ledger_row` | Nothing — SQLAlchemy 2.0.51 already does it (V1) | A filter is a second mechanism (PC-6) **and** it would break DATE-08 by suppressing the deliberate NULL |
| Enforcing lexicographic migration ordering | A revision-graph parser | The D-04 regex test (`^\d{4}$` over every `revision`/`down_revision` literal) | Locked at `33-CONTEXT.md:62-68`; a parser is a tool for a problem a 6-line test solves |
| Rejecting an incompatible push | A new exact-match predicate, or unknown-field detection | `push_schema_ok` as a sibling of `current_schema_version` (D-02) | `offline.schema_version_ok` is locked by 30-UI-SPEC and must not be touched |
| Re-running validation on the bulk sync path | Re-parsing dates in `merge.py` | Nothing — the ledger is replayed verbatim (DD-6, `merge.py:451-462`) | `business_date` must appear nowhere in the sync modules (Pitfall 16) |
| Making a date-only column comparable to timestamp bounds | Padding, casting, or `sa.Date` | `business_date_bounds` + `business_date_expr` | `sa.Date` is disqualified in `.planning/research/STACK.md`; padding is the Pitfall-14 bug with extra steps |
| Freezing time in the tz tests | `freezegun` / `time-machine` | Literal ISO fixture strings + an explicit `tz_name` argument | Rejected in `.planning/research/STACK.md`; every helper already takes `tz_name`/`today` as a parameter (`core.py:108`, `customers.py:426,451`, `dashboard.py:75-81`) |
| Restoring triggers after a batch recreate | A "re-create the triggers afterwards" helper | Never use `batch_alter_table` for anything but `add_column` (NC-1) | Alembic's own `requires_recreate_in_batch` is the source of truth; working around it invites the exact defect `0026` exists to patch |

---

## Common Pitfalls

Only pitfalls whose *concrete manifestation in this codebase* was newly pinned down are listed. The full catalogue stays in `.planning/research/PITFALLS.md` (owned set enumerated at `.planning/ROADMAP.md:318`).

### Pitfall A — the `downgrade()` that eats the cash ledger (new)

**What goes wrong.** `alembic downgrade` past `0027` leaves `cash_movements` (and, if the same mistake is repeated, `operations`) with **no** append-only triggers at all. Verified live on `0024` — see NC-1.
**Why it happens.** `alembic/env.py:57,85` enables `render_as_batch` for SQLite, and `SQLiteImpl.requires_recreate_in_batch` returns `True` for `drop_column`.
**How to avoid.** `downgrade()` = restore old trigger DDL → plain `op.drop_column`.
**Warning sign.** `SELECT name FROM sqlite_master WHERE type='trigger'` returns fewer than 4 rows after any migration step.

### Pitfall B — `ALTER TABLE ... DROP COLUMN` against a live trigger (new)

**What goes wrong.** `OperationalError: error in trigger cash_movements_no_update after drop column: no such column: NEW.business_date`, mid-downgrade, leaving the DB half-migrated.
**How to avoid.** Order the downgrade as in NC-2.
**Warning sign.** A downgrade that works on a fresh DB with no triggers but fails on a real one.

### Pitfall C — the tripwire's trailing-space assertion (new)

**What goes wrong.** `test_declared_constants_match_trigger_ddl` goes red after the trigger DDL is re-aligned, and the "obvious fix" is to relax the assertion — re-opening the fail-open hole.
**How to avoid.** Keep at least one space after every `NEW.<column>` token when re-flowing the alignment in `app/db.py:37-85` and in both migration DDL branches.

### Pitfall D — the one-day off-by-one from a half-open/closed mismatch (new)

**What goes wrong.** `local_day_bounds_utc` is documented half-open (`core.py:113-119`); a date-string comparison is naturally closed. Nine service predicates switch in one pass, and one of them keeps `<` where it now needs `<=`.
**How to avoid.** Fix the contract in `business_date_bounds`'s docstring first, then apply it mechanically. `## Validation Architecture` row VA-6 is the guard.

### Pitfall E — the two different "14"s (carried, still true)

`33-CONTEXT.md:464-471` warns that `.planning/ROADMAP.md:316`'s "14 call sites" and `.planning/research/SUMMARY.md:221`'s "9 must-switch, ~14 must-not" are **different sets**. Confirmed against HEAD: the full edit set is **9 service-layer predicates + 14 bounds-producing call sites + 7 import lines**, and the "~14 must-not" is a third, disjoint list. Do not conflate.

---

## Runtime State Inventory

This phase is a schema migration against a live fleet, so the rename/refactor inventory applies in its migration form.

| Category | Items found | Action required |
|----------|-------------|------------------|
| **Stored data** | `operations` and `cash_movements` on the s1 PostgreSQL DB and on every local SQLite client. Every existing row needs `business_date` populated by the tz-correct backfill. | **Data migration** (the backfill) **and** a code edit (`record_operation`/`record_cash_movement` kwargs) — these are two separate tasks and both must appear in the plan |
| **Live service config** | s1's `alembic_version` table (currently expected `0026`, **unverified** — V13) and s1's `.env.production` `display_tz` (**unverified** — V14, and it *parameterises the backfill*, so it must be read before the migration file is written) | Deployment-time checks, see below |
| **OS-registered state** | None for this phase. The Windows launcher / self-update path (`app/main.py:118-136`, Phase 31/32 artifacts) is untouched — no task names, plists or services embed a date column. | None — verified by inspection of the phase's file scope |
| **Secrets / env vars** | `DATABASE_URL` (`app/config.py:42`) and `display_tz` (`app/config.py:76`, default `Europe/Moscow`). Neither is renamed; `display_tz` is *read* by the backfill but through a migration-local constant, not an import (WR-06). | None renamed; V14 must be read before writing `0027` |
| **Build artifacts / installed packages** | None. No `pyproject.toml` change, so no reinstall. The vendored `app/static/htmx.min.js` is unchanged. | None |
| **Deployed client fleet** | Any client whose `alembic_version` is below `0026`. **Unknown** — this determines whether the D-01 accept-behind path is live traffic or theory. | Deployment-time check, see below |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (`pyproject.toml:24`, pinned `pytest==9.1.*`) |
| Config file | `pyproject.toml:28-30` — `[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["."]`. No `pytest.ini`/`setup.cfg`/`tox.ini` exists |
| Quick run command | `uv run pytest tests/test_append_only_cursor.py tests/test_core.py -x -q` |
| Full suite command | `uv run pytest -q` |
| PostgreSQL parity | `uv run pytest tests/test_pg_parity.py -q` with `DATABASE_URL=postgresql+psycopg://…`; skipped otherwise (existing harness, `.planning/ROADMAP.md:141` CI with `postgres:17`) |

> **Known pre-existing red.** Four `tests/test_sync_ui.py` tests fail deterministically in a local full-suite run (the lifespan auto-sync thread holds `sync_client._run_lock`). This predates every Phase-33 change. Do **not** attribute them to this phase, and do not "fix" them here.

### Phase requirements → test map

| Req | Behaviour proven | Type | Automated command | File exists? |
|-----|------------------|------|-------------------|--------------|
| VA-1 / SYNC-10 | A client-ahead push gets 409 + the RU constant; a client-behind push gets 200 and merges | integration | `uv run pytest tests/test_sync_schema_gate.py -x -q` | ❌ Wave 0 |
| VA-2 / SYNC-11 | After a 409, `Operation.synced_at IS NULL` for every row in the batch, and `sync_state.last_sync_at` did not advance | integration | `uv run pytest tests/test_sync_schema_gate.py::test_refused_push_leaves_rows_unsynced -x` | ❌ Wave 0 |
| VA-3 / SYNC-12 | A `cash_movement` record with `currency` popped merges and lands `'RUB'`; a record with `business_date` popped merges and lands `NULL` | unit | `uv run pytest tests/test_merge.py -k missing_column -x` | ⚠ extend existing `tests/test_merge.py` |
| VA-4 / SYNC-12 (V2) | A record carrying an **unknown** field merges, the field is dropped, and the report reports success — the exact loss SYNC-10 gates | unit | `uv run pytest tests/test_merge.py -k unknown_field_is_dropped -x` | ⚠ extend |
| VA-5 / SYNC-13 | The four triggers on an `alembic upgrade head` DB are whitespace-identical to `app/db.py::APPEND_ONLY_TRIGGERS` | integration | `uv run pytest tests/test_migrations.py::test_alembic_head_triggers_match_app_db -x` | ❌ Wave 0 |
| VA-6 / SYNC-13 | A full `upgrade head → downgrade -1 → upgrade head` round trip leaves exactly 4 triggers and the head column set | integration | `uv run pytest tests/test_migrations.py::test_downgrade_upgrade_roundtrip_preserves_triggers -x` | ❌ Wave 0 |
| VA-7 / D-04 | Every `revision`/`down_revision` literal under `alembic/versions/` matches `^\d{4}$` | unit | `uv run pytest tests/test_migrations.py::test_revision_ids_are_fixed_width -x` | ❌ Wave 0 |
| VA-8 / lockstep | `test_trigger_column_list_matches_schema` + `test_declared_constants_match_trigger_ddl` still green with the 4 new columns in both frozensets | unit | `uv run pytest tests/test_append_only_cursor.py -x -q` | ✅ exists (`:246`, `:261`) — extend the two constants at `:40-73` |
| VA-9 / DATE-07 | A fixed past period's `sales_profit_report` is **byte-identical** before and after the migration | integration | `uv run pytest tests/test_business_date.py::test_sales_profit_byte_identical_across_migration -x` | ❌ Wave 0 |
| VA-10 / Pitfall 14 | The same fixtures bucket correctly at `display_tz="America/New_York"` and at `"UTC"` | unit | `uv run pytest tests/test_business_date.py -k timezone -x` | ❌ Wave 0 |
| VA-11 / Pitfall 16 | `business_date` appears in **zero** of the three sync modules | unit | `uv run pytest tests/test_business_date.py::test_business_date_absent_from_sync_layer -x` | ❌ Wave 0 |
| VA-12 / DATE-08 | A row with `business_date IS NULL` still appears in every period report, bucketed by `substr(created_at,1,10)` | unit | `uv run pytest tests/test_business_date.py -k null_business_date -x` | ❌ Wave 0 |
| VA-13 / DATE-03 | Each of the 9 switched predicates returns the back-dated row under the business-date period and not under the entry-date period | unit | `uv run pytest tests/test_reports.py tests/test_finance_reports.py tests/test_customers.py tests/test_export.py tests/test_history.py -q` | ⚠ extend existing |
| VA-14 / DATE-02 | Future date → `OP_DATE_FUTURE_ERROR`; malformed → `OP_DATE_FORMAT_ERROR`; both under `errors["op_date"]`; zero writes | unit | `uv run pytest tests/test_receipts.py -k op_date -x` | ⚠ extend existing |
| VA-15 / DATE-01 | Every one of the 14 D-16 surfaces renders a `name="op_date"` input pre-filled with today | integration | `uv run pytest tests/test_business_date.py::test_every_write_surface_renders_op_date -x` | ❌ Wave 0 |
| VA-16 / DATE-05/06 | История renders one line when the dates match, two lines + «задним числом» when they differ, on desktop **and** mobile | integration | `uv run pytest tests/test_history.py -k dated -x` | ⚠ extend existing |
| VA-17 / D-22 | `_SORT_MAP` and `_DEFAULT_ORDER` are unchanged; a just-entered back-dated row is still first in every "recent N" feed | unit | `uv run pytest tests/test_history.py::test_recent_feeds_still_order_by_created_at -x` | ❌ Wave 0 |

### How the load-bearing tests are actually constructed

**VA-9 — the DATE-07 byte-identity proof.** The words "before and after the migration" cannot mean "run the suite twice"; it must be a single deterministic test. Shape:

1. Build a DB via `alembic upgrade <0027^>` (one before the new revision), seed a fixed set of sale operations with **literal** `created_at` values chosen to straddle local midnight, and record `before = sales_profit_report(session, *local_day_bounds_utc(DAY, DAY, TZ))`.
2. `alembic upgrade +1` on the **same** DB — the real migration, including the real backfill.
3. `after = sales_profit_report(session, *business_date_bounds(DAY, DAY))`.
4. `assert after == before` — the whole dict, not just the totals ("byte-identical" ⇒ compare the full return value including per-line breakdowns, which is what catches a per-row bucketing error that nets out in the grand total).

**Fixture values (executed, so they are known-good):** with `TZ="Europe/Moscow"`, `created_at="2026-08-31T21:30:00+00:00"` has tz-correct business date `2026-09-01` while `substr(created_at,1,10)` gives `2026-08-31`. Seed at least one such row, or the test passes against a naive backfill and proves nothing.

**VA-10 — the `display_tz="America/New_York"` test Pitfall 14 demands.** Executed baseline to assert against:

| tz | `local_day_bounds_utc(2026-09-01, 2026-09-01)` | date-only `'2026-09-01'` inside those bounds? |
|----|-----------------------------------------------|-----------------------------------------------|
| `Europe/Moscow` | `(2026-08-31T21:00:00+00:00, 2026-09-01T21:00:00+00:00)` | **True** (accidental) |
| `America/New_York` | `(2026-09-01T04:00:00+00:00, 2026-09-02T04:00:00+00:00)` | **False** |
| `UTC` | `(2026-09-01T00:00:00+00:00, 2026-09-02T00:00:00+00:00)` | **False** |

The test asserts the *third* column is irrelevant — i.e. that with `business_date_bounds` the row is found under all three timezones. Include `"UTC"` as well as `"America/New_York"`: the executed result shows plain UTC is also broken, so a UTC-only CI runner would otherwise be the thing that catches the bug in production instead of in the test.

Second half of VA-10: run the **backfill function itself** at both timezones and assert `tz-correct != naive-substr` for the two straddling fixtures listed under Pattern 3. That is what pins the SUMMARY.md "tz-correct, not a naive UTC-prefix cut" rule as a *test* rather than a comment.

**VA-5 / VA-6 — keeping the five-artifact lockstep honest.** The single cheapest complete guard, verified to pass at HEAD today:

```python
def _normalise(sql: str) -> str:
    return re.sub(r"\s+", " ", sql or "").strip()

def test_alembic_head_triggers_match_app_db(alembic_engine):
    """SYNC-13: the triggers a REAL migration chain builds must equal the ones
    tests/conftest.py installs from app/db.py::APPEND_ONLY_TRIGGERS.

    This is the ONLY check that spans app/db.py <-> the migrations. The two
    existing tripwires in tests/test_append_only_cursor.py compare
    models<->constants and constants<->app/db.py; migration drift (exactly what
    migration 0026 exists to patch after the fact) is invisible to both.
    """
    with alembic_engine.connect() as conn:
        built = {
            name: _normalise(sql)
            for name, sql in conn.exec_driver_sql(
                "SELECT name, sql FROM sqlite_master WHERE type='trigger'"
            )
        }
    declared = {
        re.search(r"CREATE TRIGGER (\w+)", t).group(1): _normalise(t)
        for t in APPEND_ONLY_TRIGGERS
    }
    assert built == declared
```

The `alembic_engine` fixture builds a fresh `tmp_path` SQLite DB by invoking Alembic programmatically with `DATABASE_URL` pointed at it — **not** by touching `tests/conftest.py::engine`, which 14 other fixtures depend on (V3).

VA-6 extends it to a round trip, which is the only thing that would have caught the live `0024.downgrade()` defect (NC-1):

```python
def test_downgrade_upgrade_roundtrip_preserves_triggers(alembic_engine):
    _alembic(alembic_engine, "downgrade", "-1")
    _alembic(alembic_engine, "upgrade", "head")
    assert _trigger_names(alembic_engine) == {
        "operations_no_update", "operations_no_delete",
        "cash_movements_no_update", "cash_movements_no_delete",
    }
```

**VA-11 — the Pitfall-16 guard as a runnable assertion.** Verified baseline: `business_date` currently appears **zero** times in the whole repo, so the guard starts clean.

```python
SYNC_MODULES = (
    Path("app/services/sync.py"),
    Path("app/services/sync_client.py"),
    Path("app/routes/sync.py"),
)

def test_business_date_absent_from_sync_layer():
    """DATE-04 / Pitfall 16: the sync cursor must never follow the business date.

    The push cursor is `synced_at IS NULL` and the pull cursor covers reference
    kinds only (app/services/sync.py:58-77). If `business_date` ever appears in
    one of these three modules, someone has wired the ledger's *meaning* into
    its *transport* — which silently re-orders the sync queue.
    """
    offenders = {
        str(p): [
            f"{n}: {line.rstrip()}"
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if "business_date" in line
        ]
        for p in SYNC_MODULES
    }
    assert not any(offenders.values()), offenders
```

**VA-7 — the D-04 revision tripwire.**

```python
def test_revision_ids_are_fixed_width():
    """D-04: `current_schema_version` returns a bare revision string and the
    schema gate compares them; that comparison is only meaningful while every
    revision id is fixed-width numeric. Nothing enforces it but this test."""
    pattern = re.compile(r"^\d{4}$")
    for path in sorted(Path("alembic/versions").glob("[0-9]*.py")):
        src = path.read_text(encoding="utf-8")
        rev = re.search(r'^revision\s*=\s*"([^"]+)"', src, re.M).group(1)
        down = re.search(r'^down_revision\s*=\s*(None|"[^"]+")', src, re.M).group(1)
        assert pattern.match(rev), (path.name, rev)
        if down != "None":
            assert pattern.match(down.strip('"')), (path.name, down)
```

Baseline: 26 revision files, `0001` … `0026`, all fixed-width (read at `alembic/versions/`). No `0027*` exists yet.

### Sampling / coverage reasoning

**The 9 must-switch service-layer predicates — which need their own test:**

| Predicate | Own test? | Reason |
|-----------|-----------|--------|
| `reports.py:71-72` (sales-profit) | **YES** | It is the DATE-07 byte-identity target; VA-9 is dedicated to it |
| `reports.py:145-146` (write-off report) | **YES** | Grouped by `payload.reason_code`; a bucketing error nets out in the grand total and only shows in a per-reason line |
| `reports.py:201-202` (top-selling) | shared | `func.sum` + `.group_by` + `.limit()` — a period error changes the *ranking*; one assertion in the extended `test_reports.py` suffices |
| `finance_reports.py:33-34` (`cash_expense_total`) | **YES, paired** | Must move together with the next row or the reconciliation invariant documented at `finance_reports.py:115-118` breaks |
| `finance_reports.py:126-127` (`cash_flow_report`) | **YES, paired** | Same test asserts `cash_flow_report(...)["expense_total_cents"] == cash_expense_total(...)` for identical bounds — that single equality catches the "switched one, forgot the other" failure |
| `customers.py:415-416` (`_spend_stmt`) | shared | Covered transitively by `spend_totals` (`:446`) and `spend_view` (`:468`), which are its only two callers |
| `operations.py:151-154` (`history_view`) | **YES** | **Both `stmt` and `count_stmt`.** The assertion must be `len(result["rows"]) == result["total"]` for a filtered period — nothing else catches a count that disagrees with its own rows |
| `export.py:211-212` (period-scoped cash CSV) | **YES** | The row set is chosen by the business date while column 1 becomes the business date (D-23); an inconsistency here is exactly what D-23 exists to prevent |
| `export.py:135` (sales CSV `ORDER BY`) | shared | Assert the first column is non-decreasing down the file — cheap, and it also covers CD-9's missing `export.py:214` if the planner adds it |

**The 14 `local_day_bounds_utc` call sites — which need their own test:** none individually. They are pure parameter plumbing into the 9 predicates above; a route-level test per *surface family* (reports, finance, mobile finance, history, mobile history, customers, dashboard = 7 families) covers all 14 transitively. What **does** need its own explicit assertion is that `local_day_bounds_utc` itself still exists and still behaves — `tests/test_core.py:108-150`'s four dedicated tests must stay green untouched, because 36 test call sites across 6 files build `created_at` fixtures with it.

**Sampling rate:**
- **Per task commit:** `uv run pytest tests/test_append_only_cursor.py tests/test_migrations.py tests/test_business_date.py -x -q` (< 30 s).
- **Per wave merge:** `uv run pytest -q` (full suite), accepting the 4 known-red `test_sync_ui.py` cases.
- **Phase gate:** full suite green (modulo the 4 known) **plus** one PostgreSQL run of `tests/test_pg_parity.py` against the CI `postgres:17` service, because V4's PG half could not be exercised locally.

### Wave 0 gaps

- [ ] `tests/test_migrations.py` — new file; `alembic_engine` fixture + VA-5, VA-6, VA-7
- [ ] `tests/test_business_date.py` — new file; VA-9 … VA-12, VA-15, VA-17
- [ ] `tests/test_sync_schema_gate.py` — new file; VA-1, VA-2
- [ ] Extend `tests/test_merge.py` — VA-3, VA-4
- [ ] Extend the two constants in `tests/test_append_only_cursor.py:40-73` — VA-8 (**same commit as the migration**, LOCKED constraint 4)
- [ ] No framework install needed — pytest 9.1.1 and httpx 0.28.1 are already pinned

---

## Deployment-time checks

Three questions cannot be answered from this machine (CLAUDE.md PC-9 forbids touching the operator's live instance, and s1 is a remote host). Each is a **plan task**, not a research gap. All three must be answered **before** the migration is written or applied.

| # | Question | Exact command | Why it blocks |
|---|----------|---------------|---------------|
| **V13** | Is s1's `alembic_version` at `0026` today? | On s1: `docker compose -f docker-compose.prod.yml exec ori-app uv run alembic current` | If it is **below** `0026`, the new migration is not `0027` and the rollout applies more than one revision. If it is **above**, someone shipped outside the phase system and the whole plan is stale. Expected output: `0026 (head)` |
| **V14** | What `display_tz` does s1's `.env.production` actually set? | On s1: `grep -i '^DISPLAY_TZ' .env.production` (and `docker compose -f docker-compose.prod.yml exec ori-app printenv DISPLAY_TZ` to confirm it reaches the container) | **It parameterises the backfill.** The migration cannot `from app.config import settings` (WR-06, `0026:27-29`), so the timezone must be baked in as a literal constant the way `0024:30` bakes `_DEFAULT_CURRENCY`. If s1 is not `Europe/Moscow` (the `app/config.py:76` default), the backfill constant must match s1, and a client with a different `display_tz` will produce a *different* business date for the same row — a divergence that must be named in the migration's docstring even if it is accepted |
| **—** | Is any deployed client's `alembic_version` below `0024`? | On each client: `uv run alembic current`; or centrally, inspect the `device_tokens` / last-push `schema_version` header values the server has seen. The header is already carried at `merge.py:231` and read at `routes/sync.py:112` — **the cheapest answer is to log `batch.schema_version` on the server for one week before the rollout** | Determines whether D-01's accept-behind branch is live traffic or theory, and whether the V1 finding (a pre-0024 client's cash movement lands `'RUB'`) is exercising a real code path. It does **not** change any decision — D-01 accepts behind clients either way — but it sizes the risk of the rollout window |

**Rollout order (LOCKED, `.planning/ROADMAP.md:315`), restated with the checks slotted in:**

1. Run V13 + V14 on s1. → 2. Write `0027` with the V14 timezone baked in. → 3. Migrate + redeploy s1 (`docker compose -f docker-compose.prod.yml up -d --build` — note the image bakes app code, see the s1 image-baked-code gotcha). → 4. Verify `GET /api/sync/pull` returns 200 and a push from a *current* (pre-update) client returns 200 and merges. → 5. **Only then** cut the client release tag. → Never edit `0018`/`0026` retroactively.

**Post-migration smoke assertions on s1** (read-only, safe):

```sql
-- coverage: the backfill must have touched every row
SELECT count(*) AS total,
       count(business_date) AS filled
FROM operations;
SELECT count(*) AS total,
       count(business_date) AS filled
FROM cash_movements;

-- the four triggers must still exist on PostgreSQL
SELECT tgname FROM pg_trigger
WHERE tgrelid IN ('operations'::regclass, 'cash_movements'::regclass)
  AND NOT tgisinternal
ORDER BY tgname;
```

Expected: `total == filled` on both tables, and exactly four trigger names.

---

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | everything | ✓ | 3.13 (`requires-python = ">=3.13"`, `pyproject.toml:4`) | — |
| uv | `uv run alembic`, `uv run pytest` | ✓ | executed successfully | — |
| SQLAlchemy | V1, the ORM layer | ✓ | 2.0.51 | — |
| Alembic | `0027`, VA-5/6/7 | ✓ | 1.18.5 | — |
| SQLite | local DB, trigger tests | ✓ | 3.45.1 (native `DROP COLUMN` supported) | — |
| pytest / httpx | the whole test map | ✓ | 9.1.1 / 0.28.1 | — |
| **PostgreSQL** | the PG half of V4 and of the `_PG_DDL` trigger rewrite | **✗ locally** | — | **CI** — `tests/test_pg_parity.py` against the GitHub Actions `postgres:17` service (`.planning/ROADMAP.md:141`). Not a blocker, but the PG branch of the migration is **unproven until CI runs it** |
| **A browser** | the residual D-13 check (native validation bubble) | **✗ in this session** | — | Carry as a `checkpoint:human-verify` task in the plan |
| **s1 (remote)** | V13, V14, the fleet-version question | **✗ deliberately not touched** | — | Deployment-time checks above |

**Missing with no fallback:** none.
**Missing with fallback:** PostgreSQL (→ CI), browser (→ human check task), s1 (→ deployment-time task).

---

## Security Domain

`security_enforcement` is not disabled in `.planning/config.json`, so this section is included. Phase 33 adds one operator-supplied field and one HTTP refusal path; nothing else changes the attack surface.

### Applicable ASVS categories

| ASVS category | Applies | Standard control already in place |
|---------------|---------|-----------------------------------|
| V2 Authentication | no change | Argon2id + session cookie (Phase 25); `/api/sync/*` uses `require_device` Bearer (`app/routes/sync.py:70,141`) |
| V3 Session Management | no change | `SessionMiddleware` + CSRF via `base.html` `hx-headers` |
| V4 Access Control | no change | `auth_guard` + `require_role`; the sync prefix bypass is per-route, not app-level (`app/routes/sync.py:11-13`) |
| V5 Input Validation | **yes** | `op_date` is untrusted form input. Validate in the **service** layer with `date.fromisoformat`, exactly as `parse_optional_expiry` does (`app/services/receipts.py:59-66`) — never trust the browser's ISO guarantee, and never interpolate the value into SQL |
| V6 Cryptography | no change | `payload_digest` (SHA-256) untouched |
| V7 Error handling / logging | **yes** | The new 409 must return a **fixed RU constant** naming only the two version strings; it must never echo submitted bytes (the T-28-07/V7 rule already enforced at `app/routes/sync.py:113-114`) |

### Known threat patterns for this change

| Pattern | STRIDE | Mitigation in this phase |
|---------|--------|--------------------------|
| SQL injection via `op_date` | Tampering | The value never reaches SQL as text — it is parsed to a `date` in the service, re-serialised via `.isoformat()`, and passed only as a bound parameter. **The migration's backfill must likewise never f-string a value into SQL**; `0024:45-47` gets away with it only because the interpolated value is a module-level constant, and the same discipline applies to the timezone constant |
| Version-string reflection in the 409 body | Information disclosure | Both versions are Alembic revision ids (`0026`), not secrets — and `offline/result.html:28-29` already establishes the autoescape-never-`|safe` rule for exactly this pair of values (T-30-08) |
| Denial of service via a permanent 409 retry loop | DoS (self-inflicted) | **D-09 is the mitigation** — back off to `MAX_INTERVAL_SECONDS` (3600) on `schema_mismatch`, or a mismatched client re-uploads its whole growing unsynced closure every 300 s and burns a rate-limit token each time (`app/routes/sync.py:84-86`, `sync_client.py:52-53`) |
| Ledger tampering through the new columns | Tampering | The four columns **must** be added to both trigger enumerations in the same commit (LOCKED constraint 4). Until they are, they are freely mutable on an already-synced row — the ledger fails **open**, silently (`app/db.py:24-29`) |
| A back-dated row used to hide an operation from an audit period | Repudiation | Accepted by operator decision 2 (`.planning/REQUIREMENTS.md:17`): unbounded back-dating **plus** the mandatory «задним числом» marker and filter (DATE-06). `created_at` is never overwritten (DATE-04), so the audit trail is intact regardless |

---

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | The PostgreSQL trigger's enumerated `WHEN (...)` behaves like SQLite's for a backfill of an unnamed column | V4 | If PG fired on any UPDATE, `alembic upgrade head` would abort mid-upgrade **on the live server**. Mitigated by reading `0026:63-76` (same column enumeration, `IS DISTINCT FROM` instead of `IS NOT`) and by VA-3 in CI. **Verify in CI before the s1 rollout.** |
| A2 | The browser's interactive validation blocks the `submit` event on the 8 desktop forms, so the native bubble appears | D-13 | If a browser dispatched `submit` anyway, htmx's `an()` would run and halt silently. Cheap to disprove; carried as the residual browser check |
| A3 | s1's `alembic_version` is `0026` and its `display_tz` is `Europe/Moscow` | Deployment-time checks | The migration's baked timezone constant would be wrong and the backfill would produce off-by-one business dates on the server's whole history. **This is why V13/V14 are hard blockers, not advisories** |
| A4 | SQLAlchemy's `None`-drops-to-default behaviour is stable across the `2.0.*` pin | V1 | A patch release changing it would make `_ledger_row` write NULLs into `CashMovement.currency`. VA-3 pins it as a regression test, which is the correct mitigation |
| A5 | No deployed client is below `0024` | Runtime state inventory | Only affects risk sizing, not any decision. The server-side `schema_version` log named in the deployment checks answers it |

**Everything else in this document is `[VERIFIED]` by execution or `[CITED]` at `file:line` in `fba02f2`.**

---

## Open Questions (RESOLVED)

> All four questions below were closed during phase planning. Each carries an inline `RESOLVED:`
> line naming the plan that closes it and how. Nothing in this section is open.

1. **Should `business_date_bounds` be closed `[start, end]` or half-open `[start, end+1)`?**
   - *Known:* `local_day_bounds_utc` is explicitly half-open and its docstring (`app/core.py:113-119`) explains why (a row landing exactly on UTC midnight would double-count). A date-string comparison has no such hazard.
   - *Unclear:* which shape produces the smaller diff across the 14 call sites, all of which currently unpack `(start_iso, end_iso)` and use `>= start` / `< end`.
   - *Recommendation:* **closed** `[start_day, end_day]` with `>=` / `<=`, because it matches how the operator reads a date range and removes the `+1 day` arithmetic entirely. Whichever is chosen, state it in the docstring and make VA-13 assert the last day of the range is included — this is Pitfall D.
   - **RESOLVED:** `33-06` — the recommendation was taken. The contract is **closed** `[start_day, end_day]`, fixed in that plan's `<locked_planner_decision>` and stated in `business_date_bounds`'s docstring FIRST; every switched predicate turns `< end_iso` into `<= end_day`, and 33-06 / 33-07 each assert the last day of the range is included.

2. **Does `export.py:214` get the same `ORDER BY` treatment as `export.py:135`?** (CD-9)
   - *Known:* D-23 explicitly names `export.py:135` as a coupled edit that "must not be missed", by the argument that the dump would otherwise read as unsorted by its own first column. `stream_cash_movements_csv` has the identical construct at `:214` and its `«Когда»` column at `:219` is on the same rewrite list.
   - *Unclear:* whether the omission was deliberate.
   - *Recommendation:* make the same edit at `:214` and note it in the plan as "extending D-23's stated rule to the surface D-23 already put on the switch list". If the planner disagrees, record the reason — silently leaving it is the failure mode.
   - **RESOLVED:** `33-09` — the same `ORDER BY` edit IS made at `export.py:214`, on the reasoning recorded in that plan's `<planner_decision_cd9>` (extending D-23's stated rule to a surface D-23 had already put on the switch list). The omission was not treated as deliberate.

3. **Should the live `0024.downgrade()` trigger-destruction defect (NC-1) be fixed in this phase?**
   - *Known:* it is real and executed. But LOCKED constraint 5 forbids editing `0018`/`0026` retroactively, and by the same principle `0024` is historical fact. A fix would have to be a *new* migration, and downgrades are not part of the s1 rollout path.
   - *Unclear:* whether the operator ever runs `alembic downgrade` in practice.
   - *Recommendation:* **do not fix it here.** Scope-creep against a phase already carrying a fleet-wide migration. Do (a) make `0027.downgrade()` correct by construction (NC-1/NC-2), (b) add VA-6 so the round trip is pinned from now on, and (c) record the `0024` defect as a backlog item. Naming it in `0027`'s docstring is free and prevents the next author from copying `0024`'s shape.
   - **RESOLVED:** `33-05` — the recommendation was taken in full and the defect is NOT fixed in this phase. `0027.downgrade()` is correct by construction, VA-6 pins the upgrade→downgrade→upgrade round trip, and `0027`'s docstring names the `0024.downgrade()` `batch_alter_table` defect as real, known and deliberately out of scope (`33-05-PLAN.md` Task 3).

4. **Where does the `today` value come from for the 14 templates?** (D-15)
   - *Known:* there is no `today` Jinja global — the full globals/filters registration block is `app/routes/__init__.py:193-231` and contains none. Registering a *value* would be stale-per-process. The local-today precedent is `datetime.now(ZoneInfo(settings.display_tz)).date()` (`receipts.py:208`, `mobile_reports.py:21`, `customers.py:443,465`).
   - *Recommendation:* register a **zero-arg callable** global (`templates.env.globals["today"] = lambda: datetime.now(ZoneInfo(settings.display_tz)).date().isoformat()`) rather than threading a context key through ~20 route handlers. It is one line in the same block as the 12 existing globals, it cannot go stale, and it keeps the D-16 surface edits to "add the input" with no route changes. This is inside Claude's Discretion only insofar as D-15 says "pass it per-context, **or** register a zero-arg callable" — both are sanctioned.
   - **RESOLVED:** `33-06` Task 2 — the zero-arg callable was chosen. It is registered as the Jinja global `today_iso` in the existing block at `app/routes/__init__.py:193-231`, backed by the new `app/core.local_today_iso`, which is also what `parse_op_date` checks against so the pre-filled value and the server guard can never disagree. No per-context threading through ~20 route handlers.

---

## State of the Art

| Old belief (milestone research) | Corrected by this pass | Impact |
|---------------------------------|------------------------|--------|
| An explicit `None` defeats `server_default` in bulk insert | It does not, on SQLAlchemy 2.0.51 (V1) | SYNC-12 becomes a pinning test; `CashMovement.currency` is not a bug |
| An older receiver might reject an unknown field | It silently drops it (V2) | The test asserts drop; the gate is what refuses |
| Pitfall 14 is "off by a day at any UTC− offset" | Broken at **every** offset ≤ 0, including UTC | A UTC CI runner is not a safe place to skip the tz test |
| `batch_alter_table` is dangerous "in principle" (Pitfall 3) | It has already destroyed two triggers in a shipped `downgrade()` (NC-1) | The new migration's downgrade shape is now constrained, not merely advised |
| `<details>` is a brand-new idiom in this codebase (D-10 rationale) | It ships in two templates | Rationale corrected; decision unchanged |

**Deprecated / outdated in the upstream docs — not applicable.** No external library is being adopted or upgraded.

---

## Sources

### Primary — executed in this session (HIGH confidence)

- `uv run python` probe of `merge.parse_exchange` → `merge.apply_merge` with a popped `currency` and with an unknown `business_date` field (V1, V2)
- `uv run python` variant matrix over `default=` / `server_default=` / both / neither, with the emitted INSERT captured via `before_cursor_execute` (V1 mechanism)
- `uv run alembic upgrade head` into a scratch SQLite DB, then `sqlite_master` trigger diff against `app/db.py::APPEND_ONLY_TRIGGERS` (NC-3, VA-5 proof-of-concept)
- `uv run alembic downgrade 0023` on that DB → two triggers destroyed (NC-1)
- Direct `sqlite3` probes: backfill vs trigger enumeration (V4), native `DROP COLUMN` vs trigger reference (NC-2), SQLite 3.45.1
- `inspect.getsource(alembic.ddl.sqlite)` → `requires_recreate_in_batch` (NC-1 mechanism)
- `app/core.local_day_bounds_utc` + `zoneinfo` arithmetic at three timezones (Pitfall 14, Pattern 3 fixtures)
- `grep -rn "business_date" app/services/sync.py app/services/sync_client.py app/routes/sync.py` → zero matches (VA-11 baseline)

### Primary — read at `file:line` in `fba02f2` (HIGH confidence)

`app/services/merge.py`, `app/services/sync.py`, `app/routes/sync.py`, `app/services/sync_client.py`, `app/main.py`, `app/db.py`, `app/core.py`, `app/config.py`, `app/models.py`, `app/services/{reports,finance_reports,customers,operations,export,warehouses,receipts,ledger,finance,dashboard,batches,active_catalog,offline}.py`, `app/routes/{__init__,history,offline,returns,mobile_returns,mobile_sales,mobile_transfers}.py`, `alembic/env.py`, `alembic/versions/{0024,0026}*.py`, `tests/conftest.py`, `tests/test_append_only_cursor.py`, `app/static/htmx.min.js`, `pyproject.toml`, and 20 templates under `app/templates/`.

### Secondary — project documents (MEDIUM confidence, cited not restated)

`.planning/phases/33-back-dated-operations/33-CONTEXT.md`; `.planning/ROADMAP.md:296-325`; `.planning/REQUIREMENTS.md`; `.planning/research/{SUMMARY,ARCHITECTURE,PITFALLS,STACK,FEATURES}.md`; `CLAUDE.md`.

### Tertiary — not used

No WebSearch, no Context7, no external documentation was consulted. Every question in scope was answerable from this repo, which is why the milestone research marked this phase "research not needed".

---

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| V1 (insert defaults) | HIGH | Executed twice, mechanism confirmed in the emitted SQL |
| V2 (unknown field) | HIGH | Executed end-to-end plus read at three `file:line` |
| V3 (fixtures) | HIGH | Read; full fixture-name collision list enumerated |
| V4 (backfill vs trigger) | HIGH on SQLite, **MEDIUM on PostgreSQL** | PG not exercisable locally; provable in CI (A1) |
| D-13 (htmx) | HIGH on the source facts, **MEDIUM on browser behaviour** | Vendored source read in full; the native-validation half is A2 |
| NC-1/NC-2 (downgrade) | HIGH | Executed against a real Alembic chain |
| Call-site audit | HIGH | ~120 references checked line by line |
| Deployment checks | **N/A — deliberately unverified** | s1 is out of reach and out of bounds (PC-9) |

**Research date:** 2026-09-04
**Valid until:** 2026-10-04 for the executed library behaviour (stable pins). **Invalid the moment `alembic/versions/` gains a `0027*` file or `app/models.py` gains a ledger column** — the call-site line numbers in this document are pinned to `fba02f2` and will drift on the first edit.
