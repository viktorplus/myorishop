---
phase: 27-shared-idempotent-merge-core
audited_at: 2026-07-19
auditor: gsd-security-auditor
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
threats_total: 9
threats_closed: 9
threats_open: 0
status: secured
---

# Phase 27 — Shared Idempotent Merge Core: Security Audit

Verification of every declared threat mitigation against the implemented code.
Method: for each `mitigate` threat, the declared mitigation pattern was located in
the cited implementation files (file:line evidence below); the `accept` threat is
recorded in the accepted-risk log. Implementation files were NOT modified. Starting
hypothesis was "every threat open" — each is closed only on located in-code evidence.

Files audited (read-only): `app/services/merge.py`, `app/services/ledger.py`,
`tests/test_merge.py`, `tests/test_merge_pg.py`, `.github/workflows/ci.yml`, plus
the cited DB backstops in `app/models.py` and `alembic/versions/`.

## Threat Verification

| Threat ID | Category | Disposition | Result | Evidence |
|-----------|----------|-------------|--------|----------|
| T-27-01 | Tampering | mitigate | CLOSED | `_upsert_reference` insert-only, existing UUID discarded; no session.delete/update in module (see detail) |
| T-27-02 | Spoofing / Tampering | mitigate | CLOSED | `_resolve_code_collisions`/`_suffix_code` rename loser, incumbent keeps code; partial unique index backstop; proven on PG (see detail) |
| T-27-03 | Tampering / DoS | mitigate | CLOSED | `parse_exchange` strict pre-DB validation, all paths raise ValueError before any DB touch (see detail) |
| T-27-04 | Tampering / Repudiation | mitigate | CLOSED | Verbatim insert + `recompute_derived` invariant assert + append-only triggers + live cash SUM (see detail) |
| T-27-05 | Tampering (injection) | mitigate | CLOSED | Bound-param ORM/Core only; purity grep gate == 0 (no dialects/raw/f-string SQL) (see detail) |
| T-27-06 | Integrity | mitigate | CLOSED | `synced_at` forced None on parse + `_ledger_row`; `apply_merge` never commits (see detail) |
| T-27-07 | Tampering | mitigate | CLOSED | Insert-if-new by UUID PK (replay no-op); UNIQUE(device_id, seq) backstop; deterministic rename (see detail) |
| T-27-08 | Tampering | mitigate | CLOSED | CI pg-parity step re-runs engine core on postgres:17 with `-x`; no dialect construct in engine (see detail) |
| T-27-SC | Tampering (supply chain) | accept | CLOSED (accepted) | No packages installed this phase; logged as accepted risk |

## Detail

### T-27-01 — client overwriting server reference data (mitigate) → CLOSED

Declared mitigation: row-level server-wins-on-existing in `_upsert_reference` — an
existing UUID is discarded (never field-merged, never `deleted_at`→NULL, never
session.delete/update from client input).

Verified in code:
- `app/services/merge.py:420-447` `_upsert_reference` — `_partition_new` splits rows
  into new vs already-present; only `new_rows` are inserted via
  `session.execute(insert(model), new_rows)` (`:446`); existing UUIDs are counted as
  `server_wins` and returned (`:447`), never updated or deleted. Insert-only.
- Inline tombstone carried verbatim, never flipped — `_reference_row` (`:303-316`)
  copies `deleted_at` unchanged; a server row is never reached (dropped by the
  set-difference before insert).
- Grep gate confirms insert-only: `merge.py` contains no `session.delete`, `.delete(`,
  UPDATE, or `.commit(` (0 matches).
- Proven by tests — `tests/test_merge.py:553` `test_server_wins_on_existing_reference`
  (existing UUID edit discarded, server row untouched, `reference_server_wins == 1`)
  and `tests/test_merge.py:605` `test_tombstone_inline` (new soft-deleted row inserts;
  existing server row never resurrected/deleted).

### T-27-02 — cross-device Product.code hijack (mitigate) → CLOSED

Declared mitigation: incumbent (server) row keeps the clean code; incoming loser
renamed with a deterministic UUID suffix and reported; backstop partial unique index
`uq_products_code_active`.

Verified in code:
- `app/services/merge.py:361-417` `_resolve_code_collisions` — probes an active
  incumbent (`Product.code == code, deleted_at IS NULL`, `:394-398`); the first
  claimant keeps the clean code (`:403-405`), every later claimant is renamed
  (`:406-408`) and a `product_code` `Conflict` is appended (`:409-417`). Incumbent
  is a different UUID (existing UUIDs already dropped by the set-difference).
- `app/services/merge.py:332-358` `_suffix_code` — marker `"~"` + a deterministic
  slice of the losing UUID hex, widened until unique; fits `String(20)`.
- DB backstop present and portable — `alembic/versions/0003_products_code_active_unique.py:29-36`
  creates `uq_products_code_active` unique index with `sqlite_where` AND
  `postgresql_where` = `deleted_at IS NULL` (both dialects); also declared in
  `app/models.py`.
- Proven by tests — `tests/test_merge.py:630` `test_product_code_collision_renamed`
  (incumbent keeps code, loser renamed keeping UUID, conflict reported) and the PG
  slice `tests/test_merge_pg.py:238` `test_code_collision_on_pg` (rename honoured
  against PostgreSQL's `postgresql_where` partial index).

### T-27-03 — parse_exchange malformed / type-confused NDJSON (mitigate) → CLOSED

Declared mitigation: strict per-line `json.loads` + schema validation rejecting
non-object lines, unsupported `format_version`, unknown kind, missing header, and
float money — all raise ValueError before any DB touch. (SIZE caps are a transport
concern for Phase 28/30, explicitly not owned here.)

Verified in code (`app/services/merge.py`, `parse_exchange` is pure — no DB/file/net):
- non-object / malformed line → ValueError — `:163-168`.
- unsupported `format_version` → ValueError — `:177-178`.
- unknown kind → ValueError — `:185-186`; duplicate header → `:183-184`.
- missing header → ValueError — `:174-175` and `:225-226`.
- missing non-empty string id → ValueError — `:191-193`; duplicate origin id
  (WR-02) → `:197-198`.
- missing ledger provenance / non-int seq → ValueError — `:202-207`.
- non-int money (float / string / bool, bool excluded explicitly) → ValueError —
  `:214-217`.
- Proven by tests — `tests/test_merge.py`: `test_malformed_line_rejected` (`:193`),
  `test_format_version_rejected` (`:186`), `test_unknown_kind_rejected` (`:202`),
  `test_missing_header_rejected` (`:209`), `test_duplicate_header_rejected` (`:216`),
  `test_record_missing_id_rejected` (`:223`), `test_ledger_missing_provenance_rejected`
  (`:230`), `test_float_money_rejected` (`:239`), `test_string_money_rejected` (`:775`),
  `test_bool_money_rejected` (`:783`).

### T-27-04 — forged ledger rows to inflate stock/cash (mitigate) → CLOSED

Declared mitigation: rows insert verbatim but Product/Batch.quantity recomputed via
`recompute_derived`; cash is a live SUM; invariant assert rejects an inconsistent
batch; append-only triggers block post-hoc edits; created_by/author_id origin preserved.

Verified in code:
- Verbatim ledger insert — `app/services/merge.py:450-461` `_ledger_row` (schema-restricted
  column dict, `synced_at` forced None); appended in `apply_merge` (`:508-519`).
- Derived stock recomputed, cache never trusted — `app/services/ledger.py:171-210`
  `recompute_derived`: recomputes each `Product.quantity` (`:186-187`) and
  `Batch.quantity` (`:191-195`) from the ledger; the wire `quantity` is dropped to 0
  first (`_reference_row`, `merge.py:314-315`). `apply_merge` calls it (`merge.py:522`).
- Invariant assert rejects inconsistency — `ledger.py:209-210`
  `raise ValueError(f"stock invariant violated ...")`; propagates through `apply_merge`
  (never caught) so the caller's transaction rolls back.
- Cash is a live SUM — no cash total stored; `finance.compute_balance` sums rows,
  proven by `tests/test_merge.py:448` `test_cash_balance_after_merge`.
- Append-only DB triggers (dual-dialect) block post-hoc edits —
  `alembic/versions/0001_initial_schema.py:40-47` (SQLite `operations_no_update`/`_no_delete`,
  `RAISE(ABORT, 'operations ledger is append-only')`) and `:61-63` (PG `RAISE EXCEPTION`);
  `alembic/versions/0013_cash_movements.py:39-46` / `:61-63` (`cash_movements_no_update`/`_no_delete`).
- Origin preserved (attribution not re-minted) — `tests/test_merge.py:396`
  `test_ledger_row_inserted_verbatim` asserts device_id/seq/author_id/created_by/created_at
  survive and `synced_at is None`.

### T-27-05 — SQL injection via record field values (mitigate) → CLOSED

Declared mitigation: portable ORM/Core, bound parameters only; no `sqlalchemy.dialects`,
no raw / f-stringed SQL.

Verified in code:
- Bound-param constructs only — `insert(model)` (`merge.py:299`, `:446`),
  `select(model.id).where(model.id.in_(chunk))` (`:279`),
  `Product.code == code` bound comparison (`:395-397`).
- Purity grep gate on `app/services/merge.py` == 0 matches for
  `sqlalchemy.dialects | on_conflict | INSERT OR | .commit( | .delete( | session.delete |
  text( | execute(f | f"…SELECT | f"…INSERT`. No dynamic SQL text anywhere in the engine.
- PG test seeds use literal constants / bound params only (`tests/test_merge_pg.py`
  module docstring rule + `_SEED_INCUMBENT` literal, `text(_SEED_INCUMBENT)` with no
  interpolated data).

### T-27-06 — wire synced_at trusted / half-applied batch (mitigate) → CLOSED

Declared mitigation: `synced_at` forced None on parse/ledger-row build; `apply_merge`
never commits mid-batch — caller owns the single all-or-nothing transaction.

Verified in code:
- `synced_at` never trusted from the wire — forced None in `parse_exchange`
  (`merge.py:219-221`) and again in `_ledger_row` (`:460`).
- `apply_merge` never commits — no `.commit(` anywhere in `merge.py` (grep == 0);
  docstring `:464-481` states the caller owns the transaction; stages run
  reference-upsert → ledger append → recompute with no commit.
- Proven by tests — `tests/test_merge.py:247` `test_synced_at_not_trusted` and
  `tests/test_merge.py:479` `test_bad_record_rolls_back` (a poisoned mid-batch record
  → caller rollback leaves 0 rows, product.quantity unchanged: all-or-nothing).

### T-27-07 — idempotency-key / seq forgery + non-deterministic rename (mitigate) → CLOSED

Declared mitigation: insert-if-new by UUID PK makes replay a no-op; UNIQUE(device_id, seq)
DB backstop; `_suffix_code` deterministic in UUID only.

Verified in code:
- Replay no-op — `_partition_new` (`merge.py:264-281`, chunked `WHERE id IN`) +
  `_insert_new` (`:284-300`) insert only ids not already present; re-run inserts 0.
- UNIQUE(device_id, seq) DB backstop — `app/models.py:337`
  `UniqueConstraint("device_id", "seq")` on `Operation`, and `app/models.py:476` on
  `CashMovement`.
- Deterministic rename — `_suffix_code` (`merge.py:332-358`) derives the marker from
  the UUID hex only, no random / no time; `_resolve_code_collisions` processes rows
  `sorted(..., key=lambda r: r["id"])` (`:389`) for order-stable resolution.
- Proven by tests — `tests/test_merge.py:377` `test_merge_twice_equals_once`
  (byte-identical snapshot, 0 second-apply inserts), `:424` `test_duplicate_uuid_skipped`,
  `:668` `test_collision_rename_is_deterministic`, `:794` `test_duplicate_ledger_uuid_rejected`.

### T-27-08 — dialect-specific construct silently forking client vs server (mitigate) → CLOSED

Declared mitigation: CI pg-parity job re-runs idempotency + collision core on
postgres:17; a divergence turns the job red and blocks (block_on: high); the engine
has no `sqlalchemy.dialects` / `on_conflict`.

Verified in code:
- CI step exists — `.github/workflows/ci.yml:45-48` "PostgreSQL merge portability
  (SYNC-02/04/05 one engine, both dialects)" runs
  `uv run pytest tests/test_merge_pg.py -x` with
  `DATABASE_URL: postgresql+psycopg://…@localhost:5432/postgres` against the
  `postgres:17` service (`:15`); `-x` makes any divergence fail the job.
- The PG slice exercises the real engine — `tests/test_merge_pg.py:112`
  `test_merge_idempotent_on_pg` and `:238` `test_code_collision_on_pg` (skipif-guarded
  on `settings.database_url.startswith("postgresql")`, `:39-42`).
- Engine has no dialect fork — purity grep == 0 for `sqlalchemy.dialects` / `on_conflict`
  in `merge.py`; the module docstring and `_partition_new` rely on a portable pre-select
  set-difference, not an upsert clause.
- Advisory (not a gap): the GitHub Actions pg-parity run being GREEN is recorded as
  already achieved (origin/ci/phase-27-pg-parity, run 29688176513, `test_merge_pg.py`
  2 passed on postgres:17). The mitigation this threat targets — the CI step and the
  dialect-free engine — is present in code regardless.

### T-27-SC — package installs / supply chain (accept) → CLOSED (accepted risk)

Disposition = accept. Verified no new dependency was introduced this phase:
- All four plan SUMMARYs declare `tech-stack.added: []` (27-01 line 22, 27-02 line 24,
  27-03 line 24, 27-04 line 20) — "stdlib json/dataclasses + already-installed
  SQLAlchemy; psycopg added in Phase 26".
- `app/services/merge.py` imports only stdlib (`json`, `dataclasses`, `collections.abc`),
  already-installed `sqlalchemy`, and internal `app.*` modules; `app/services/ledger.py`
  likewise imports only `sqlalchemy` + internal modules. No new registry surface.
Recorded below as an accepted risk; no blocking human checkpoint required.

## Accepted Risks Log

| ID | Risk | Rationale | Owner | Recorded |
|----|------|-----------|-------|----------|
| T-27-SC | Supply-chain surface from package installs during this phase | This phase installs NO packages: engine uses stdlib `json`/`dataclasses` + already-installed SQLAlchemy; `psycopg` was added and audited in Phase 26; CI `uv sync --dev` unchanged. All four 27-* SUMMARYs declare `added: []`. No new registry/dependency surface. | Phase 27 owner | 2026-07-19 |

## Unregistered Flags

None. No Phase 27 SUMMARY (27-01 through 27-04) contains a `## Threat Flags` section,
and each declares `tech-stack.added: []` and "no new packages" — no new attack surface
appeared during implementation beyond the plan `<threat_model>` register.

## Verdict

SECURED — 9/9 threats resolved (8 mitigated with in-code file:line evidence, 1 accepted
and logged). No open (BLOCKER) threats, no unregistered flags. `block_on: high` gate is
satisfied.
