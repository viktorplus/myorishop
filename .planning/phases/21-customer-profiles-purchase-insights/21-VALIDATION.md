---
phase: 21
slug: customer-profiles-purchase-insights
status: bound
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-17
bound_at: 2026-07-17
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `21-RESEARCH.md` → `## Validation Architecture`.
> Task IDs bound to concrete plans/tasks by the planner on 2026-07-17.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["."]`) |
| **Quick run command** | `uv run pytest tests/test_customers.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~4.3s quick (19 tests) · full suite 754 tests |

**Conventions** (from `tests/test_customers.py:11-14`): route/e2e tests are prefixed `test_web_`; everything else is service-level. Fixtures `session`, `client`, `customer`, `stocked_product` already exist in `tests/conftest.py`. Seed sales via `register_sale` + `_only_batch(session, product)` as the existing history tests do.

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_customers.py -q`
- **After every plan wave:** Run `uv run pytest -q` + `uv run ruff check` + `uv run ruff format --check`
- **Before `/gsd-verify-work`:** Full suite green + `uv run alembic upgrade head` applied cleanly to a copy of a real 0014-era `.db`
- **Max feedback latency:** ~5 seconds (per-commit sample)

**Rationale for the rate:** the per-commit sample is one file because the phase's blast radius is one file's worth of surface — but `app/models.py` is imported by *everything*, so the CHECK-constraint pitfall (Pitfall 1) would take the whole suite red. That is why the full suite runs at wave merge and not only at the phase gate: a `models.py` mistake must not survive a wave.

**Wave merge gates (bound):** Wave 0 → task 21-01-01 runs `uv run pytest -q`. Wave 1 → 21-02-03. Wave 2 → 21-03-03. Wave 3 → 21-04-03. Wave 4 (phase gate) → 21-05-03.

---

## Per-Task Verification Map

> Task IDs bound by the planner (2026-07-17). Every row's Automated Command is mirrored verbatim
> into the named task's `<acceptance_criteria>` in its PLAN.md.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 21-02-03 | 21-02 | 1 | CUST-01 | — | N/A | integration | `uv run pytest tests/test_customers.py -k contacts_phone -x` | ✅ extend | ⬜ pending |
| 21-02-03 | 21-02 | 1 | CUST-02 | — | N/A | integration | `uv run pytest tests/test_customers.py -k contacts_telegram -x` | ✅ extend | ⬜ pending |
| 21-02-03 | 21-02 | 1 | CUST-03 | — | N/A | integration | `uv run pytest tests/test_customers.py -k contacts_email -x` | ✅ extend | ⬜ pending |
| 21-02-03 · 21-05-03 | 21-02 (storage) · 21-05 (render) | 1 · 4 | CUST-04 | T-21-XSS / T-21-01 | Social link value is escaped and NOT rendered as a raw `href` | integration | `uv run pytest tests/test_customers.py -k contacts_social -x` | ✅ extend | ⬜ pending |
| 21-02-02 | 21-02 | 1 | CUST-01..04 | V5 / T-21-09 | Blank rows discarded; `kind` allow-list rejects unknown kind | unit | `uv run pytest tests/test_customers.py -k contacts_validation -x` | ✅ extend | ⬜ pending |
| 21-02-02 | 21-02 | 1 | CUST-01..04 | — | Re-saving replaces (not duplicates) contacts | integration | `uv run pytest tests/test_customers.py -k contacts_replace -x` | ✅ extend | ⬜ pending |
| 21-04-03 | 21-04 | 3 | CUST-01..04 | — | Contacts survive the **new-customer** create path (Pitfall 2) | integration | `uv run pytest tests/test_customers.py -k web_customer_create_with_contacts -x` | ✅ extend | ⬜ pending |
| 21-02-01 | 21-02 | 1 | CUST-05 | V5 / T-21-04 | Address length-guarded before write | integration | `uv run pytest tests/test_customers.py -k address -x` | ✅ extend | ⬜ pending |
| 21-03-02 | 21-03 | 2 | CUST-06 | — | Last order date = most recent sale | unit | `uv run pytest tests/test_customers.py -k last_order -x` | ✅ extend | ⬜ pending |
| 21-03-02 | 21-03 | 2 | CUST-06 | — | Zero orders → no date, no crash | unit | `uv run pytest tests/test_customers.py -k last_order_empty -x` | ✅ extend | ⬜ pending |
| 21-03-01 | 21-03 | 2 | CUST-07 | — | Month/quarter/year totals with **injected** `today` (Pitfall 7) | unit | `uv run pytest tests/test_customers.py -k spend_totals -x` | ✅ extend | ⬜ pending |
| 21-03-01 | 21-03 | 2 | CUST-07 | — | Return subtracts from spend (D-06 net) | unit | `uv run pytest tests/test_customers.py -k spend_net_of_returns -x` | ✅ extend | ⬜ pending |
| 21-03-01 | 21-03 | 2 | CUST-07 | — | Sale outside the window excluded | unit | `uv run pytest tests/test_customers.py -k spend_window_excludes -x` | ✅ extend | ⬜ pending |
| 21-03-01 | 21-03 | 2 | CUST-07 | T-21-25 | **Zero orders → 0, not None** (Pitfall 4) | unit | `uv run pytest tests/test_customers.py -k spend_empty -x` | ✅ extend | ⬜ pending |
| 21-03-01 | 21-03 | 2 | CUST-07 | T-21-18 | NULL `unit_price_cents` line doesn't crash the sum (Pitfall 4) | unit | `uv run pytest tests/test_customers.py -k spend_null_price -x` | ✅ extend | ⬜ pending |
| 21-03-02 | 21-03 | 2 | CUST-08 | — | Favorites ranked by frequency, qty secondary | unit | `uv run pytest tests/test_customers.py -k favorite_products -x` | ✅ extend | ⬜ pending |
| 21-03-02 | 21-03 | 2 | CUST-08 | — | Batch-split purchase counts once (Pitfall 3) | unit | `uv run pytest tests/test_customers.py -k favorites_batch_split -x` | ✅ extend | ⬜ pending |
| 21-03-02 | 21-03 | 2 | CUST-08 | — | Capped at 10 (D-04a) | unit | `uv run pytest tests/test_customers.py -k favorites_limit -x` | ✅ extend | ⬜ pending |
| 21-03-02 | 21-03 | 2 | CUST-08 | T-21-17 | Scoped to THIS customer only | unit | `uv run pytest tests/test_customers.py -k favorites_scoped -x` | ✅ extend | ⬜ pending |
| 21-05-02 | 21-05 | 4 | CUST-06..08 | — | Detail page renders all insight blocks | e2e | `uv run pytest tests/test_customers.py -k web_customer_detail_insights -x` | ✅ extend | ⬜ pending |
| 21-03-03 | 21-03 | 2 | — (regression) | — | Frozen-price contract still holds | unit | `uv run pytest tests/test_customers.py -k frozen -x` | ✅ exists | ⬜ pending |
| 21-03-03 | 21-03 | 2 | — (portability) | T-21-15 / T-21-03 | Compiled PostgreSQL SQL contains no `strftime`; no id literal leaks (all values bound) | unit | `uv run pytest tests/test_customers.py -k portable -x` | ✅ extend | ⬜ pending |

### Rows added by the planner (not in the RESEARCH-derived contract)

These close landmines named by `21-PATTERNS.md` / `21-UI-SPEC.md` that the original map predates.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 21-01-03 | 21-01 | 0 | CUST-07 (Wave 0 fixture) | — | Past-dated sale seeding does not UPDATE the append-only ledger | infra | `uv run pytest tests/test_customers.py -k past_sale_fixture -x` | ✅ extend | ⬜ pending |
| 21-04-01 | 21-04 | 3 | CUST-01..04 | T-21-02 (V5) | `kind` allow-list gates the rendered `name` attribute; unknown kind → 404, nothing rendered | integration | `uv run pytest tests/test_customers.py -k web_contact_row -x` | ✅ extend | ⬜ pending |
| 21-05-01 | 21-05 | 4 | CUST-01..05 | T-21-01 | Contacts render as plain autoescaped text on the profile | e2e | `uv run pytest tests/test_customers.py -k web_customer_detail_contacts -x` | ✅ extend | ⬜ pending |
| 21-05-03 | 21-05 | 4 | CUST-06/07 | T-21-25 | Zero-order profile renders in full; the string `None` appears zero times | e2e | `uv run pytest tests/test_customers.py -k web_customer_detail_empty_profile -x` | ✅ extend | ⬜ pending |
| 21-05-03 | 21-05 | 4 | CUST-04 | T-21-22 | `\| safe` absent from all 6 Phase 21 templates | unit | `uv run pytest tests/test_customers.py -k safe_filter -x` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Portability guard (highest-leverage test in this phase):** compile the new statements against the PostgreSQL dialect and assert `"strftime" not in sql`. This mechanically enforces the CLAUDE.md portability rule that is otherwise only enforced by reviewer memory. Bound to **21-03-03**, which extends it to both statements (`_spend_stmt`, `_favorites_stmt`) under both dialects, and adds a bound-parameter assertion (the `customer_id` literal must not appear in compiled SQL — T-21-03).

---

## Wave 0 Requirements

- [x] `tests/conftest.py` — **fixture gap**: no existing fixture seeds a sale at a controlled *past* date, and every CUST-07 window test needs one. **Bound to task 21-01-03**: a `past_sale` factory fixture inserting a `Sale` + `Operation` pair with an explicit `created_at` directly via the session (safe — the append-only triggers block UPDATE/DELETE, never INSERT). Supports `type_="sale"`/`"return"`, a shared `sale` header (the batch-split shape 21-03-02 needs), and `unit_price_cents=None` (which 21-03-01's `spend_null_price` needs).
- [x] No new test files needed — `tests/test_customers.py` and `tests/conftest.py` already exist and cover the fixtures this phase needs (`session`, `client`, `customer`, `stocked_product`).
- [x] Framework install: none — pytest 9.1.x present and green (754 collected, 19 in scope).

---

## Manual-Only Verifications

| Behavior | Requirement | Bound To | Why Manual | Test Instructions |
|----------|-------------|----------|------------|-------------------|
| Migration 0015 applies to a real 0014-era database | CUST-01..05 | 21-01-02 `<human-check>` | No migration test harness exists in this repo | Copy a real 0014-era `.db`, run `uv run alembic upgrade head`, confirm exit 0 and that existing customer rows survive with contacts/address columns added |

**Partial automation added by the planner:** 21-01-02 additionally replays the *entire* migration chain (0001→0015) on a throwaway `DB_PATH=data/_migcheck.db`, exercises `downgrade -1` + `upgrade head`, and asserts the emitted `sqlite_master` DDL contains `CONSTRAINT ck_customer_contacts_kind_valid CHECK`. The operator's real `data/myorishop.db` is never touched by an automated check. This reduces the manual step to "does it apply to *real data*", which is the only part a fresh-DB replay cannot prove.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — all 15 tasks across plans 21-01..21-05 carry at least one `<automated>` command
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (past-dated sale fixture → 21-01-03)
- [x] No watch-mode flags
- [x] Feedback latency < 5s (per-commit sample is `tests/test_customers.py -q`, ~4.3s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** bound to plans 21-01..21-05 on 2026-07-17. Ready for execution.
