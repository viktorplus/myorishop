---
phase: 21
slug: customer-profiles-purchase-insights
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-17
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `21-RESEARCH.md` → `## Validation Architecture`.

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

---

## Per-Task Verification Map

> Task IDs are assigned by the planner. Rows below are the **requirement-level** contract
> from RESEARCH.md; the planner/executor binds each to a concrete `{N}-{plan}-{task}` ID.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | CUST-01 | — | N/A | integration | `uv run pytest tests/test_customers.py -k contacts_phone -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-02 | — | N/A | integration | `uv run pytest tests/test_customers.py -k contacts_telegram -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-03 | — | N/A | integration | `uv run pytest tests/test_customers.py -k contacts_email -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-04 | T-21-XSS | Social link value is escaped and NOT rendered as a raw `href` | integration | `uv run pytest tests/test_customers.py -k contacts_social -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-01..04 | V5 | Blank rows discarded; `kind` allow-list rejects unknown kind | unit | `uv run pytest tests/test_customers.py -k contacts_validation -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-01..04 | — | Re-saving replaces (not duplicates) contacts | integration | `uv run pytest tests/test_customers.py -k contacts_replace -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-01..04 | — | Contacts survive the **new-customer** create path (Pitfall 2) | integration | `uv run pytest tests/test_customers.py -k web_customer_create_with_contacts -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-05 | V5 | Address length-guarded before write | integration | `uv run pytest tests/test_customers.py -k address -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-06 | — | Last order date = most recent sale | unit | `uv run pytest tests/test_customers.py -k last_order -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-06 | — | Zero orders → no date, no crash | unit | `uv run pytest tests/test_customers.py -k last_order_empty -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-07 | — | Month/quarter/year totals with **injected** `today` (Pitfall 7) | unit | `uv run pytest tests/test_customers.py -k spend_totals -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-07 | — | Return subtracts from spend (D-06 net) | unit | `uv run pytest tests/test_customers.py -k spend_net_of_returns -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-07 | — | Sale outside the window excluded | unit | `uv run pytest tests/test_customers.py -k spend_window_excludes -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-07 | — | **Zero orders → 0, not None** (Pitfall 4) | unit | `uv run pytest tests/test_customers.py -k spend_empty -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-07 | — | NULL `unit_price_cents` line doesn't crash the sum (Pitfall 4) | unit | `uv run pytest tests/test_customers.py -k spend_null_price -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-08 | — | Favorites ranked by frequency, qty secondary | unit | `uv run pytest tests/test_customers.py -k favorite_products -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-08 | — | Batch-split purchase counts once (Pitfall 3) | unit | `uv run pytest tests/test_customers.py -k favorites_batch_split -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-08 | — | Capped at 10 (D-04a) | unit | `uv run pytest tests/test_customers.py -k favorites_limit -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-08 | — | Scoped to THIS customer only | unit | `uv run pytest tests/test_customers.py -k favorites_scoped -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | CUST-06..08 | — | Detail page renders all insight blocks | e2e | `uv run pytest tests/test_customers.py -k web_customer_detail_insights -x` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | — (regression) | — | Frozen-price contract still holds | unit | `uv run pytest tests/test_customers.py -k frozen -x` | ✅ exists | ⬜ pending |
| TBD | TBD | TBD | — (portability) | — | Compiled PostgreSQL SQL contains no `strftime` | unit | `uv run pytest tests/test_customers.py -k portable -x` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Portability guard (highest-leverage test in this phase):** compile the new statements against the PostgreSQL dialect and assert `"strftime" not in sql`. This mechanically enforces the CLAUDE.md portability rule that is otherwise only enforced by reviewer memory.

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — **fixture gap**: no existing fixture seeds a sale at a controlled *past* date, and every CUST-07 window test needs one. Add a past-dated sale fixture (or a helper that backdates an operation's UTC timestamp) before Wave 1.
- [x] No new test files needed — `tests/test_customers.py` and `tests/conftest.py` already exist and cover the fixtures this phase needs (`session`, `client`, `customer`, `stocked_product`).
- [x] Framework install: none — pytest 9.1.x present and green (754 collected, 19 in scope).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Migration 0015 applies to a real 0014-era database | CUST-01..05 | No migration test harness exists in this repo | Copy a real 0014-era `.db`, run `uv run alembic upgrade head`, confirm exit 0 and that existing customer rows survive with contacts/address columns added |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (past-dated sale fixture)
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
