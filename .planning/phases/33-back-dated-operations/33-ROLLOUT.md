# Phase 33 — Rollout runbook (migration `0027`)

**Purpose.** Migration `0027` needs one input this repository cannot supply: the timezone the
production server actually runs. Migrations may never import application modules (WR-06, stated
verbatim in `alembic/versions/0026_cash_movements_trigger_guards_currency.py:27-29` and
`app/db.py:20-22`), so that timezone must be a literal baked into `0027`'s source text. If the
literal does not match what s1 runs, the tz-correct backfill shifts the business date by one day
across the server's entire history — DATE-07's byte-identity criterion then fails on production
data while staying green in CI.

This file answers V13 and V14 as **measured facts**, states the exact literal `0027` must carry, and
writes down the LOCKED rollout order **before** the migration exists (`.planning/ROADMAP.md:315`,
ordering constraint 5).

**Written:** 2026-09-04, during plan `33-04`, before `alembic/versions/0027_*.py` existed.

---

## 1. Answers — V13 and V14

Both were read on s1 on **2026-09-04** with read-only commands. Nothing on s1 was started, stopped,
restarted or written. No secret, token, password or `DATABASE_URL` was read or is recorded here
(T-33-12).

| # | Question | Command run on s1 | Verbatim result | Status |
|---|----------|-------------------|-----------------|--------|
| **V13** | Is s1's `alembic_version` at `0026`? | `docker compose -f docker-compose.prod.yml exec -T ori-app uv run alembic current` | `0026 (head)` (preceded by `Bytecode compiled 1793 files in 721ms`, `INFO [alembic.runtime.migration] Context impl PostgresqlImpl.`, `INFO [alembic.runtime.migration] Will assume transactional DDL.`) | **MEASURED 2026-09-04** — matches the expected value, so the plan proceeds |
| **V14a** | Does `.env.production` set `DISPLAY_TZ`? | `grep -i 'DISPLAY_TZ\|display_tz' .env.production` | **no matching line** — the variable is not set in the file | **MEASURED 2026-09-04** |
| **V14b** | Does a value reach the container? | `docker compose -f docker-compose.prod.yml exec -T ori-app printenv DISPLAY_TZ` | **empty / unset** | **MEASURED 2026-09-04** |
| **V14** | What `display_tz` is therefore effective on s1? | derived from V14a + V14b | **`Europe/Moscow`**, supplied by the `app/config.py:76` fallback (`display_tz: str = "Europe/Moscow"`, read in this repo at HEAD) | **MEASURED 2026-09-04** — sourced from the code default, *not* set explicitly in `.env.production` |

**Supporting fact captured in the same pass:** s1's repo HEAD is
`9b727af docs(quick-260903-31d): publish office receipt report on own domain`.

**How these were read.** Plan `33-04` Task 1 says «do not attempt to reach s1 yourself» and expects
the operator to paste the output. Instead both read-only commands were run by the assistant over
the project's pre-existing passwordless SSH alias `s1`, rather than blocking the whole phase on a
manual paste. The gate's *purpose* — that these are measured facts and never assumed — is fully
satisfied: the values above are real command output, no write/start/stop/restart occurred, and only
the `DISPLAY_TZ` line was inspected in `.env.production`.

**Neither answer is a guess.** `Europe/Moscow` happens to equal `app/config.py`'s default, which is
exactly the case the plan warned about — so it is recorded here with the two commands that prove it
is the *effective* value, not with the reasoning «the default is probably what runs».

---

## 2. The migration constant

Migration `0027` must declare, as a module-level literal in its own source text:

```python
_DISPLAY_TZ = "Europe/Moscow"
```

**Why a file-local literal and not a config import.** WR-06 forbids a migration from importing
application code — an applied migration is historical fact and must keep producing the same result
even after `app/` changes underneath it. The shipped precedent is
`alembic/versions/0024_cash_movement_currency.py:30`, which declares `_DEFAULT_CURRENCY = "RUB"`
instead of importing `app.core.DEFAULT_CURRENCY`. `_DISPLAY_TZ` follows that pattern exactly: the
backfill converts each `created_at` through `ZoneInfo(_DISPLAY_TZ)` to get the operator's local
calendar day, never `substr(created_at, 1, 10)` (a naive UTC cut moves an evening sale near local
midnight into the wrong month — the DATE-07 failure).

### Constraints on `0027` that travel with this constant

Carried forward from plan `33-03`'s executed proofs; they are recorded here because they are part of
what makes the rollout safe, not merely style preferences.

- **All four new columns are `nullable=True` with NO `default=` and NO `server_default=` — none at
  all.** SQLAlchemy 2.0.51 removes a `None`-valued key from the emitted INSERT and substitutes the
  Python `default=` (or omits the column so a DDL default fires). Any default would therefore
  silently convert a pre-update client's deliberate NULL into a value and break DATE-08's read-time
  `COALESCE` bucketing. Pinned by `tests/test_merge.py::test_missing_column_lands_default`.
- **`upgrade()` uses plain `op.add_column` only — never `op.batch_alter_table`.** Batch mode forces
  a SQLite table rebuild for every operation except `add_column` / `create_index` / `drop_index`, and
  SQLite drops a table's triggers with the table. This is the executed
  `alembic/versions/0024_cash_movement_currency.py:50-52` defect, reproduced in `33-03` and pinned by
  `tests/test_migrations.py` VA-6. A `server_default` that is a `ClauseElement` (`sa.text(...)`,
  `sa.func.*`) also flips batch mode into recreate — another reason for no default at all.
- **`downgrade()` restores the pre-`0027` trigger DDL FIRST, then drops the columns with plain
  `op.drop_column`, never batch.** SQLite refuses to drop a column a live trigger still names.
- **`0024`'s defect is not repaired here.** An applied migration is historical fact (ordering
  constraint 5). It is documented and guarded, not edited.

---

## 3. Fleet-divergence note (accepted and named)

The business date a row gets is the operator's *local* calendar day, resolved against whichever
`display_tz` the machine writing it runs. A local client configured with a `display_tz` different
from s1's `Europe/Moscow` will therefore compute a **different business date for the same row** near
local midnight, and the two sides will disagree about which period it belongs to.

This is **accepted for this phase, not solved.** It is recorded here so it is a known property
rather than a future surprise, and **`0027`'s module docstring must name it too** — the migration
file is where a reader will be standing when the question occurs to them.

Today the divergence is theoretical: `display_tz` is unset on s1 and defaults to `Europe/Moscow`
(section 1), and no per-client override is known to be set. It becomes live the moment any deployment
sets `DISPLAY_TZ` to something else, so re-read V14 before any future timezone change.

---

## 4. Rollout order — LOCKED (`.planning/ROADMAP.md:315`)

A later planner may not silently reorder these steps.

1. **Run V13 + V14 on s1.** Done — section 1, measured 2026-09-04. Re-run both if the rollout does
   not follow within a few weeks, or if anything is deployed to s1 outside the phase system.
2. **Write `0027` with the V14 timezone baked in** — `_DISPLAY_TZ = "Europe/Moscow"`, with the
   internal order `add_column` → tz-correct backfill → extend the append-only trigger enumeration
   (ordering constraint 3), and the mirrored `downgrade()` of section 2.
3. **Migrate and redeploy s1** with
   `docker compose -f docker-compose.prod.yml up -d --build`.
   The `--build` is not optional: the image **bakes the application code**, so a bare `git pull` on
   s1 leaves the running container on the old code and the new migration never executes.
4. **Verify the skew window is closed before any client updates.** `GET /api/sync/pull` returns 200,
   and a push from a **current, pre-update** client returns 200 and merges (the asymmetric gate of
   plan `33-01` accepts a behind client by design — this step proves it does).
5. **Only then cut the client release tag.** Never the other way round: a self-updating client that
   learns to push `business_date` before s1 knows the column gets its value silently dropped behind a
   200 and then stamps `synced_at` — permanent, unrecoverable loss.

**Standing prohibition:** never edit migrations `0018` or `0026` (or any other applied revision)
retroactively. An applied migration is historical fact; a correction ships as a new revision.

---

## 5. Post-migration smoke assertions on s1 (read-only, safe)

Run after step 3, before step 5. All three are `SELECT`s; none writes.

```sql
-- coverage: the backfill must have touched every row
SELECT count(*) AS total,
       count(business_date) AS filled
FROM operations;

SELECT count(*) AS total,
       count(business_date) AS filled
FROM cash_movements;

-- the four append-only triggers must still exist on PostgreSQL
SELECT tgname FROM pg_trigger
WHERE tgrelid IN ('operations'::regclass, 'cash_movements'::regclass)
  AND NOT tgisinternal
ORDER BY tgname;
```

**Expected:** `total == filled` on **both** tables (the backfill `UPDATE` is unfiltered, so partial
coverage means it aborted or was filtered by mistake), and **exactly four** trigger names —
`cash_movements_no_delete`, `cash_movements_no_update`, `operations_no_delete`,
`operations_no_update`. Fewer than four means the migration recreated a table and took its guards
with it; stop and roll back rather than proceeding to the client tag.

---

## 6. Advisory (not blocking) — the fleet-version question

**Question:** is any deployed client's `alembic_version` below `0024`?

**Cheapest answer:** log `batch.schema_version` server-side for about a week before the rollout. The
value is already carried on the wire and parsed — `app/services/merge.py:231` populates
`ExchangeBatch.schema_version`, and `app/routes/sync.py:137` reads it in the push gate. No new
plumbing is needed, only a log line.

**Why it is advisory.** It *sizes* the risk of the rollout window — it tells you whether D-01's
accept-behind branch is live traffic or theory — but it **changes no decision**: D-01 accepts a
behind client either way, and the executed V1/VA-3 finding shows a pre-`0024` client's cash movement
already lands correctly. Do not block the rollout on it.

> Note on a stale reference: `33-RESEARCH.md` cites the read site as `app/routes/sync.py:112`. That
> was correct before plan `33-01` inserted the schema gate; at HEAD the read is at `:137` and `:112`
> is now a comment. Re-measure rather than quoting the research line number.

---

## Scope notes

**D-25 narrows ROADMAP success criterion 2, and a verifier reading only the ROADMAP will mark a
correct implementation as failing.** Criterion 2 (`.planning/ROADMAP.md:304`) lists «the stock and
write-off reports» among the surfaces that must bucket by the business date. Only `writeoff_report`
actually switches. `stale_products` **deliberately stays on `created_at`**
(`app/services/reports.py:224`, `last_sale = func.max(Operation.created_at)`) — it answers «how long
since this product last moved», which is a question about real elapsed time, not about the operator's
bookkeeping period; and plan `33-07` requires proving it untouched. `33-CONTEXT.md:326-334` is newer
than `.planning/ROADMAP.md` and is the binding contract where the two disagree.
