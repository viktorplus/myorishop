---
phase: 26-postgresql-portability-append-only-parity
audited_at: 2026-07-19
auditor: gsd-security-auditor
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
threats_total: 4
threats_closed: 4
threats_open: 0
status: secured
---

# Phase 26 — PostgreSQL Portability & Append-Only Parity: Security Audit

Verification of every declared threat mitigation against the implemented code.
Method: for each `mitigate` threat, the declared mitigation pattern was located in
the cited implementation files (file:line evidence below); the `accept` threat is
recorded in the accepted-risk log. Implementation files were NOT modified.

## Threat Verification

| Threat ID | Category | Disposition | Result | Evidence |
|-----------|----------|-------------|--------|----------|
| T-26-01 | Tampering / Repudiation | mitigate | CLOSED | PG PL/pgSQL trigger functions + BEFORE UPDATE/DELETE triggers on BOTH ledgers; downgrade drops cleanly; CI asserts rejection (see detail) |
| T-26-02 | Information Disclosure | mitigate | CLOSED | No credential literal in config/CI beyond throwaway ephemeral; URL from env; `.env` gitignored (see detail) |
| T-26-03 | Tampering (injection) | mitigate | CLOSED | Static literal DDL; `%`-escaped Alembic URL; test seeds literal + single bound param (see detail) |
| T-26-SC | Tampering (supply chain) | accept | CLOSED (accepted) | `psycopg[binary]==3.3.*` pinned, legitimate official adapter — logged as accepted risk |

## Detail

### T-26-01 — operations + cash_movements UPDATE/DELETE on PostgreSQL (mitigate) → CLOSED

Declared mitigation: PL/pgSQL `BEFORE UPDATE/DELETE … RAISE EXCEPTION` trigger
functions on BOTH tables, DB-enforced and caller-independent (SRV-02), proven by
`tests/test_pg_parity.py` in the CI pg-parity job.

Verified in code:
- operations PG DDL — `alembic/versions/0001_initial_schema.py:57-65`
  (`_PG_OPERATIONS_DDL`: `CREATE OR REPLACE FUNCTION operations_append_only()` +
  `operations_no_update` BEFORE UPDATE + `operations_no_delete` BEFORE DELETE,
  `RAISE EXCEPTION 'operations ledger is append-only'`), emitted under the
  `dialect.name == "postgresql"` branch at `:111-113`.
- cash_movements PG DDL — `alembic/versions/0013_cash_movements.py:57-65`
  (`_PG_CASH_APPEND_ONLY_DDL`: `cash_movements_append_only()` +
  `cash_movements_no_update`/`_no_delete`, `RAISE EXCEPTION 'cash ledger is
  append-only'`), emitted at `:97-99`.
- Clean downgrade (CR-01 fix, commit 7bba10b) — `0001_initial_schema.py:145-150`
  and `0013_cash_movements.py:106-111` use the mandatory PG form
  `DROP TRIGGER IF EXISTS … ON <table>` plus `DROP FUNCTION IF EXISTS …()` under
  the postgresql branch, SQLite keeps the ON-less form.
- CI proof asserts rejection AND blocks — `tests/test_pg_parity.py`:
  `test_operations_update_rejected` (:144), `test_operations_delete_rejected`
  (:161), `test_cash_movements_immutable` (:176, both UPDATE and DELETE), each via
  `pytest.raises(Exception, match="append-only")`. The CI job runs
  `uv run pytest tests/test_pg_parity.py -x` with `DATABASE_URL` set to the
  postgres:17 service — `.github/workflows/ci.yml:40-43`; a failing assertion
  returns a nonzero exit and fails the job.

Advisory (not a mitigation gap — does not open the threat):
- The GitHub Actions pg-parity run being GREEN against real PostgreSQL is a
  deferred end-of-phase human-check (26-03-SUMMARY "Deferred Verification"); the
  mitigation code and the CI job that would prove it are both present.
- The PG downgrade path (CR-01 fix) is not exercised by CI (the parity suite never
  calls `command.downgrade`); it was `ast.parse`-verified only. The forward
  (upgrade) SRV-02 control — the mitigation this threat targets — IS covered.

### T-26-02 — DATABASE_URL / CI Postgres credentials (mitigate) → CLOSED

Declared mitigation: app URL only from env via `settings.database_url`; config.py
holds only the non-secret `sqlite:///` default; CI uses a throwaway non-secret
password on an ephemeral container; no repo secret / production credential committed.

Verified in code:
- `app/config.py:30` — `database_url: str = ""` (empty default); `:65-66` fills
  `sqlite:///{db_path}` only when empty. No host/user/password literal present.
- `app/db.py:89` and `alembic/env.py:22` — both consumers read
  `settings.database_url` (single source of truth); a PG URL arrives only via env.
- `.github/workflows/ci.yml:12-18` — `POSTGRES_PASSWORD: postgres` documented as a
  throwaway non-secret for an ephemeral container; `:42`
  `DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/postgres`
  targets the local ephemeral service. No `secrets.*` reference.
- `.env` is gitignored — `.gitignore:16`; `git ls-files` shows no tracked `.env`.
- `.env.example` (tracked) contains no `DATABASE_URL` and no real secret values
  (SECRET_KEY/DEVICE_ID left empty with "never commit real secrets" guidance).

Repo-wide scan for `scheme://user:pass@host` literals returned only the documented
throwaway CI credential and placeholder examples (`u:p@h`, `USER:PASSWORD@HOST`) in
planning docs — no production credential committed.

### T-26-03 — migration trigger DDL / env.py URL handling / CI SQL (mitigate) → CLOSED

Declared mitigation: trigger DDL is static literal SQL with fixed message strings
(no injection surface); URL flows through SQLAlchemy config with no shell
interpolation of untrusted input; parity test uses bound params / literal seeds;
WR-02 `%` escaping on the Alembic URL.

Verified in code:
- Static literal DDL — `_APPEND_ONLY_TRIGGERS`/`_PG_OPERATIONS_DDL`
  (`0001_initial_schema.py:38-65`) and
  `_CASH_APPEND_ONLY_TRIGGERS`/`_PG_CASH_APPEND_ONLY_DDL`
  (`0013_cash_movements.py:37-65`) are module-constant tuples; no external input
  is interpolated; `downgrade()` DROP statements are hardcoded literals.
- WR-02 `%` escaping (commit 233f4ce) — `alembic/env.py:22`
  `config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))`;
  URL parsed with `make_url(...)` at `:29` (no shell/string interpolation).
- Parity test SQL — `tests/test_pg_parity.py`: seeds `_SEED_*` (:42-72) are constant
  string literals; the only bound parameter is `to_regclass(:t)` (:98); UPDATE/DELETE
  statements use hardcoded ids. No f-string of external/variable data into SQL text.

### T-26-SC — psycopg[binary] install (accept) → CLOSED (accepted risk)

Disposition = accept. Verified `pyproject.toml:11` pins
`"psycopg[binary]==3.3.*"` — the official PostgreSQL adapter
(github.com/psycopg/psycopg), the SQLAlchemy-documented `postgresql+psycopg://`
driver, consistent with 26-RESEARCH "Package Legitimacy Audit" verdict = OK/Approved
(3.3.4 on PyPI). Recorded below as an accepted risk; no blocking human checkpoint
required.

## Accepted Risks Log

| ID | Risk | Rationale | Owner | Recorded |
|----|------|-----------|-------|----------|
| T-26-SC | Adding `psycopg[binary]` to the dependency closure (supply-chain surface) | Official PostgreSQL adapter, SQLAlchemy-documented `postgresql+psycopg://` driver, version pinned `==3.3.*` (3.3.4 verified on PyPI); RESEARCH Package Legitimacy Audit = OK/Approved | Phase 26 owner | 2026-07-19 |

## Unregistered Flags

None. Phase 26 SUMMARY files contain no `## Threat Flags` section; 26-01-SUMMARY
("Threat Surface") and 26-03-SUMMARY ("Threat Model") both explicitly declare no
new security surface introduced beyond the plan's `<threat_model>`.

## Verdict

SECURED — 4/4 threats resolved (3 mitigated with in-code evidence, 1 accepted and
logged). No open (BLOCKER) threats. `block_on: high` gate is satisfied.
