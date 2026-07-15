---
phase: 16
slug: manual-cash-movements-history
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-15
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* (+ httpx 0.28.* for FastAPI `TestClient`) |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| **Quick run command** | `uv run pytest tests/test_finance.py -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | quick ~3.5s pytest (~7s wall incl. uv startup, 14 tests today) · full ~98s (577 tests) |

*Lint (phase gate, not a test): `uv run ruff check` / `uv run ruff format`.*

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_finance.py -q`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd-verify-work`:** Full suite must be green AND `uv run ruff check` clean
- **Max feedback latency:** ~8 seconds (quick run, wall time incl. uv startup); full suite ~100s at wave boundaries

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | FIN-03 / FIN-04 / FIN-07 | T-16-02 / T-16-06 | Manual category allow-list + bucket maps are the exact server-side vocabulary; no orphan bucket key, no stray category | unit | `uv run pytest tests/test_finance.py -k "categories or buckets" -x` | ✅ | ⬜ pending |
| 16-01-02 | 01 | 1 | FIN-03 / FIN-04 / FIN-07 | T-16-06 | RU labels resolve as Jinja globals (autoescape rendering; no `UndefinedError`, no blank labels) | unit | `uv run pytest tests/test_finance.py -x` | ✅ | ⬜ pending |
| 16-02-01 | 02 | 2 | FIN-03 / FIN-04 / FIN-05 | T-16-01 / T-16-02 / T-16-03 / T-16-04 / T-16-05 | Server-side amount parse (`to_cents`), sign-by-direction, category allow-list, mandatory-comment rule, negative-balance gate — ZERO writes on any failure | unit (service) | `uv run pytest tests/test_finance.py -k "withdraw or deposit or negative" -x` | ✅ | ⬜ pending |
| 16-02-02 | 02 | 2 | FIN-07 | T-16-07 / T-16-08 | Bucket filter via parameterised `.in_()` (unknown bucket ignored); page clamped server-side; append-only view over the whole ledger | unit (service) | `uv run pytest tests/test_finance.py -k "cash_history" -x` | ✅ | ⬜ pending |
| 16-03-01 | 03 | 3 | FIN-03 / FIN-04 / FIN-05 | T-16-05 / T-16-01..04 (upstream) | Warn re-render returns HTTP 200 (not 422); route delegates ALL validation to the service, never writes cash directly | integration (web) | `uv run pytest tests/test_finance.py -k "web_withdraw or web_deposit or web_negative" -x` | ✅ | ⬜ pending |
| 16-03-02 | 03 | 3 | FIN-07 | T-16-06 / T-16-07 | `note`/labels rendered autoescaped (no `\|safe`); bucket/page passed straight to the service, never into SQL | integration (web) | `uv run pytest tests/test_finance.py -k "web_cash_history" -x` | ✅ | ⬜ pending |
| 16-04-01 | 04 | 4 | FIN-03 / FIN-04 / FIN-05 | T-16-05 / T-16-01..04 (upstream) | Mobile routes reuse the shared service + shared forms; identical 200/422/warn branching, no client-trusted validation | integration (web, mobile) | `uv run pytest tests/test_finance.py -k "mobile_withdraw or mobile_deposit or mobile_negative" -x` | ✅ | ⬜ pending |
| 16-04-02 | 04 | 4 | FIN-07 | T-16-06 / T-16-07 | Mobile cards autoescape `note`/labels (no `\|safe`); bucket/page via the service; no numbered bar (load-more only) | integration (web, mobile) | `uv run pytest tests/test_finance.py -k "mobile_cash_history" -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*File Exists ✅ = `tests/test_finance.py` exists today (Phase 15). Every Phase 16 task is `tdd="true"`, so each authors its own cases inline as the RED step — no separate Wave-0 stub pass is required.*

---

## Wave 0 Requirements

**Existing infrastructure covers all phase requirements.** No framework install, no new test file, no shared-fixture pass:

- `tests/test_finance.py` already exists (Phase 15 append-only / balance / credit / debit / page-render coverage). Each Phase 16 TDD task extends it in place with its own RED cases for FIN-03/04/05/07 (service + desktop web + mobile web).
- Reuse existing fixtures: `session`, `client`, `mobile_client_factory` (build `mobile_finance.router`), `stocked_product` (to seed sale-credit / return-debit rows into the history). No new `conftest.py` fixtures required.
- pytest 9.1.* + httpx 0.28.* already installed (`pyproject.toml` dev group) — nothing to install.

---

## Manual-Only Verifications

*(Every phase behavior also has automated coverage; these are visual-parity confirmations layered on top, run at end-of-phase — plans 16-03 / 16-04 `<human-check>`.)*

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Desktop `/finance` forms + warn + history visual/layout parity | FIN-03/04/05/07 | Visual layout, HTMX swap feel, and «Тип» filter/paging appearance are not asserted by API-level tests | Run `run.bat`, open `http://localhost:8000/finance`: withdraw «Оплата поставщику» 15,00 → balance drops and the row appears; withdrawal larger than the balance → «Баланс уйдёт в минус» + «Снять всё равно»; deposit «Начальный остаток» 100 → balance rises; «Тип» → Снятие shows only withdrawals; paging preserves the filter |
| Mobile `/m/finance` forms + warn + card history + «Показать ещё» visual parity | FIN-03/04/05/07 | Mobile card layout, touch targets, and load-more (vs numbered bar) are a visual/touch concern | Open `http://localhost:8000/m/finance` (or the phone): withdraw/deposit persist and the balance updates; over-balance withdrawal shows the warning + «Снять всё равно»; history shows cards with a «Тип» filter and «Показать ещё» loads the next page (not a numbered bar) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — no `<automated>` marked MISSING; test file + fixtures exist)
- [x] No watch-mode flags (all commands use `-x` / `-q`, no `--watch`)
- [x] Feedback latency < 10s (quick run ~8s wall)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-15
