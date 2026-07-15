---
phase: 16
slug: manual-cash-movements-history
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-15
---

# Phase 16 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Manual cash movements (withdraw/deposit) + cash-movement history, desktop
> (`/finance`) and mobile (`/m/finance`) surfaces. Single local operator, no auth
> in v1 (CLAUDE.md).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| browser form → POST /finance/{withdraw,deposit} + /m/finance/{withdraw,deposit} | untrusted `amount` / `category` / `note` / `confirm` raw strings; the route parses only `Form("")` and delegates ALL validation to `record_manual_movement` (D-00c) | form strings |
| stored `note` / category label → history HTML (table + cards) | operator-authored `note` is untrusted-at-rest text rendered into the history rows/cards | stored text |
| browser query `bucket` / `page` → GET history | untrusted filter/page values; `bucket` flows through `CASH_BUCKETS.get` (parameterised `.in_`), `page` clamped server-side | query strings |
| client `confirm` flag → negative-balance override | `confirm == "1"` is an explicit operator override; the would-be balance is recomputed live at write time, never trusted from the client | form flag |
| model constants → write-path allow-list | `CASH_CATEGORIES` is the exact server-side allow-list `record_cash_movement` / `record_manual_movement` gate on | developer constants |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-16-01 | Tampering | amount parse (`to_cents`) | mitigate | Amount parsed ONLY via `app.core.to_cents` (`finance.py:123`), which rejects inf/nan/garbage/huge exponents and accepts the Russian comma (`core.py:39-46`); parsed `<= 0` also rejected (`finance.py:127-128`); any failure returns `(None, {"amount": ...})` with ZERO writes (`finance.py:131-132`) | closed |
| T-16-02 | Tampering / Elevation | category allow-list + direction | mitigate | Category must be in `CASH_BUCKETS["withdrawal"]`/`["deposit"]` (`finance.py:114-117`); system keys (`sale`/`return`) or unknown keys rejected server-side — defence-in-depth over `record_cash_movement`'s `CASH_CATEGORIES` guard (`finance.py:67-68`). WR-01 cross-direction guard rejects `deposit_*` on withdraw and `withdrawal_*` on deposit at both routers (`routes/finance.py:128-136,193-201`; `mobile_finance.py:136-144,199-207`, commit `b143ccb`) | closed |
| T-16-03 | Tampering | sign integrity | mitigate | Sign applied SERVER-SIDE by direction: `amount_cents = -parsed if is_withdrawal else parsed` (`finance.py:135`); a client cannot flip a withdrawal into a deposit nor submit a negative deposit | closed |
| T-16-04 | Tampering | mandatory-comment bypass (D-04) | mitigate | `withdrawal_other` / `deposit_correction` require a non-blank note in the service: `if category in _NOTE_REQUIRED_CATEGORIES and not note.strip(): return None, {"note": ...}` (`finance.py:30,138-139`), ZERO writes — not reliant on HTML `required` | closed |
| T-16-05 | Tampering | negative-balance gate (FIN-05) | mitigate + accept | Gate recomputes `compute_balance(session) + amount_cents < 0` LIVE at write (`finance.py:143`); `confirm != "1"` returns `{"negative_balance": {...}}` with ZERO writes; routes surface it at HTTP **200** (`routes/finance.py:156-163`; `mobile_finance.py:163-170`). `confirm == "1"` is an accepted-by-design explicit override (still a valid append-only row; balance stays truthful as a live SUM) | closed |
| T-16-06 | Tampering (stored XSS) | `note` / RU labels in history HTML | mitigate | Rendered via Jinja autoescape only — `{{ mv.note }}` / `{{ CASH_CATEGORIES.get(mv.category, mv.category) }}` (`cash_history_rows.html:48-49`; `cash_history_cards.html:26-28`); NO `\|safe` in any Phase 16 template (grep 0 across all `*finance*`/`*cash*` templates); autoescape not disabled anywhere | closed |
| T-16-07 | Tampering (SQLi) | bucket filter in `cash_history_view` | mitigate | `bucket` resolved via `CASH_BUCKETS.get(bucket)` → `CashMovement.category.in_(cats)` parameterised ORM (`finance.py:195-198`); unknown/tampered bucket → `None` → no filter; page clamped server-side (`finance.py:202`); routes pass the raw string straight to the service, never into SQL (`routes/finance.py:44-45`; `mobile_finance.py:45-46`); no raw/f-string SQL | closed |
| T-16-08 | Repudiation / Tampering | immutable ledger | accept (already mitigated) | `cash_movements` BEFORE UPDATE/DELETE triggers `RAISE(ABORT, 'cash ledger is append-only')` from migration 0013 (`alembic/versions/0013_cash_movements.py:37-48,80-81`); corrections are new rows. `CashMovement(...)` is constructed ONLY inside `record_cash_movement` (`finance.py:70`) — the single write path. No change this phase | closed |
| T-16-SC | Tampering | supply chain | accept (N/A) | Zero packages installed this phase (`tech-stack.added: []` in all four plan summaries) | closed |
| V2/V3/V4 | auth / session / access | — | accept (N/A) | Single local operator, no auth in v1 (CLAUDE.md project constraint) | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-16-01 | T-16-05 | `confirm == "1"` lets an operator drive the till balance negative on purpose; it is an explicit override, still an append-only row, and the balance remains truthful because it is a live SUM (never a cached column) | operator (plan-time disposition) | 2026-07-15 |
| AR-16-02 | T-16-08 | Ledger immutability is enforced at the DB level by the Phase 15 `cash_movements` UPDATE/DELETE ABORT triggers (migration 0013); Phase 16 adds only new-row corrections, never edits/deletes | operator (plan-time disposition) | 2026-07-15 |
| AR-16-03 | T-16-SC | No new third-party packages were introduced this phase — constants, service functions, routes, and templates only | operator (plan-time disposition) | 2026-07-15 |
| AR-16-04 | V2/V3/V4 | No authentication/session/access-control machinery in v1 — single local operator on localhost, no multi-tenant boundary (CLAUDE.md) | operator (plan-time disposition) | 2026-07-15 |

*Accepted risks do not resurface in future audit runs.*

---

## Unregistered Flags

None. Plan 03 `16-03-SUMMARY.md` carries a `## Threat Flags` section that reads
"None — no new trust boundary beyond the plan's `<threat_model>`". Plans 01, 02,
and 04 introduced no new attack surface (`tech-stack.added: []`, no `## Threat
Flags` entries). No new attack surface appeared during implementation that lacks
a threat mapping.

---

## Code Review Follow-Through

Phase 16 went through `16-REVIEW.md` (0 critical, 1 warning, 3 info). Of direct
security relevance:

- **WR-01** (warning): the deposit route ignored the service's `negative_balance`
  result branch, so a crafted `withdrawal_*` category POSTed to the deposit
  endpoint (or a `deposit_*` to withdraw) could diverge endpoint semantics from
  the recorded movement direction. **Fixed** (commit `b143ccb`): both the desktop
  and mobile withdraw/deposit routes now reject a cross-direction category at the
  boundary before the service call (`routes/finance.py:128-136,193-201`;
  `mobile_finance.py:136-144,199-207`). This is verified as part of T-16-02.
- **IN-01/IN-02/IN-03** (info): a redundant `compute_balance` call in the gate,
  an unvalidated `bucket` echoed into the render context (cosmetic — autoescape
  prevents XSS; rows are still correctly unfiltered), and a duplicated
  `SAVE_FAILED_ERROR` constant. None are security blockers; carried as advisory.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-15 | 10 | 10 | 0 | gsd-security-auditor |

Evidence method: grep + read of each cited file:line. Service-tier mitigations
(`record_manual_movement`, `cash_history_view`) verified in `app/services/finance.py`;
route enforcement in `app/routes/finance.py` + `app/routes/mobile_finance.py`;
XSS in the four history/form templates; immutability triggers in
`alembic/versions/0013_cash_movements.py`.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Every `mitigate` threat verified by file:line evidence in implemented code
- [x] Accepted risks documented in Accepted Risks Log
- [x] No unregistered attack surface (SUMMARY `## Threat Flags` = None)
- [x] Implementation files unmodified (audit is read-only)
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-15
