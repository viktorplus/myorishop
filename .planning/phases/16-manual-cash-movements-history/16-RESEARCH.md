# Phase 16: Manual Cash Movements & History - Research

**Researched:** 2026-07-15
**Domain:** Internal reuse — extend an existing append-only cash ledger (FastAPI + SQLAlchemy 2.0 + HTMX/Jinja2) with a manual write path and a paginated/filterable read view.
**Confidence:** HIGH (every claim below is grounded in the current repo source, read this session)

## Summary

Phase 16 adds two capabilities on top of the Phase 15 cash ledger: (1) an operator-driven WRITE path — manual withdrawals (mandatory category) and manual deposits (opening balance / correction) — routed through the existing single write path `finance.record_cash_movement`, and (2) a READ view — a paginated, type-filterable history of every cash movement (auto sale-credits, auto return-debits, manual entries) — on both `/finance` (desktop) and `/m/finance` (mobile).

This is a **reuse-heavy phase with zero new external dependencies.** Every pattern already exists in the codebase and must be mirrored verbatim: the single-write-path service invariant (`finance.py`), the latin-key→RU-label dict (`CASH_CATEGORIES` / `OPERATION_TYPE_LABELS`), the warn-but-allow `confirm == "1"` gate (`writeoffs.register_writeoff` / `sales.register_sale`), the shared pagination helper (`pagination.page_window` / `paginate` + `partials/pagination.html`), and the swappable `#*-rows` HTMX partial pattern (`operations.history_view` + `partials/history_rows.html` + `routes/history.py`). The research below records the exact current signatures, constants, and control flow so the planner can write concrete, correct plans without re-deriving them.

**Primary recommendation:** Add a thin `finance.record_manual_movement(...)` service wrapper (sign + validation + comment rule + negative-balance gate) and a `finance` read service (`cash_history_view(...)`) that mirrors `operations.history_view` but is SIMPLER (no Product/Batch joins; the «Тип» filter maps 4 coarse buckets → category-key sets via a prefix/grouping map). Wire POST handlers + the history read into `routes/finance.py` and `routes/mobile_finance.py`. Register `CASH_CATEGORIES` (and a bucket→label map) as Jinja globals. No new packages; extend `tests/test_finance.py`.

<user_constraints>
## User Constraints (from 16-CONTEXT.md)

### Locked Decisions (do not re-litigate)
- **Carried from Phase 15:** `finance.record_cash_movement` is the SINGLE write path for `cash_movements`; routes NEVER write cash directly. Append-only ledger — no UPDATE/DELETE; corrections are new rows. Money is signed Integer cents; render via `app.core.format_cents`; NO currency symbol. Balance = live `SUM(amount_cents)`. «Финансы» pages already exist on desktop and mobile (balance-only today); nav already present.
- **D-01:** Model manual movements by EXTENDING `CASH_CATEGORIES` — NO new `type` column, no migration. `amount_cents` sign encodes direction (withdrawal negative, deposit positive). Free-text comment lives in the existing `note` column.
- **D-01a:** Use prefixed category keys so the 4 coarse buckets are trivially derivable, e.g. `withdrawal_supplier`, `withdrawal_salary`, `withdrawal_rent`, `withdrawal_utilities`, `withdrawal_other`, `deposit_opening`, `deposit_correction`. Existing `sale`/`return` keys unchanged. Exact spelling = planner's discretion, but grouping into Продажа / Возврат / Снятие / Внесение MUST be trivial (prefix or a small grouping map).
- **D-01b:** RU labels via the existing `CASH_CATEGORIES` dict (same pattern as `OPERATION_TYPE_LABELS`). Withdrawal labels: Оплата поставщику / Зарплата / Аренда / Коммунальные / Прочее. Deposit labels: Начальный остаток / Корректировка.
- **D-02:** Manual movements go through a thin manual-entry service function wrapping `finance.record_cash_movement` — validates category, applies sign by direction, enforces the comment rule (D-04) and the warn-but-allow gate (D-05). Route layer never writes cash directly.
- **D-02a:** Operator always enters a POSITIVE amount; the service applies the sign (снятие → negative, внесение → positive). Deposits can never be negative; withdrawals never positive. Reject zero/blank/non-integer amounts server-side, ZERO writes.
- **D-04:** `note` is mandatory ONLY for `withdrawal_other` («прочее») and `deposit_correction` («корректировка»); optional for the others. Enforced server-side. Empty/whitespace on those two → re-render with error, ZERO writes.
- **D-05:** Reuse the sales/writeoff `confirm` pattern. A withdrawal that would drive `compute_balance` < 0 with `confirm != "1"` → re-render the снятие form with a warning + confirm control, ZERO writes. `confirm == "1"` → proceed and write. Withdrawals ONLY (deposits only increase); non-negative withdrawals and all deposits never warn.
- **D-06:** TWO separate inline forms below the balance: «Снять деньги» (amount + category select + comment) and «Внести деньги» (amount + reason select Остаток/Коррекция + comment). Warn-but-allow lives only in the снятие POST. Server-rendered HTMX, consistent with `writeoff_form`/`sale_form`.
- **D-06a:** Both `/finance` and `/m/finance` get manual entry + history — parity with Phase 15.
- **D-07:** Reuse `/history` end-to-end: `pagination.py` (`LIST_PAGE_SIZE`=20, `page_window`, `paginate`), a finance read service mirroring `operations.history_view`, a header-row «Тип» filter + HTMX swappable rows partial mirroring `partials/history_rows.html`, and `extra_qs` to preserve the active filter across pages.
- **D-07a:** The «Тип» filter offers the 4 coarse buckets Продажа / Возврат / Снятие / Внесение. NO product filter. Default sort: date descending. Placement: on «Финансы», below the balance and the entry forms.
- **D-07b:** Each row shows: date, тип/категория label, comment (`note`), signed amount via `format_cents`. Manual vs auto is visible from the label — no separate flag column.

### Claude's Discretion
- Exact category-key spelling; service/function names (follow `finance.py`/`ledger.py`/`operations.py`); route paths; template structure; whether desktop and mobile share partials.
- Whether the history read filters in SQL or Python-slices via `paginate` — follow whatever `operations.history_view` does (it filters + paginates in SQL via `.where`/`.limit`/`.offset`).
- Mobile layout specifics (single page vs subpage) per existing mobile patterns.

### Deferred Ideas (OUT OF SCOPE)
- Date-range filter on cash history.
- Separate `type` DB column (Option B).
- Reports / CSV export / profit & stock-valuation dashboard → Phase 17.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FIN-03 | Оператор может списать средства из кассы с обязательным выбором категории (оплата поставщику / зарплата / аренда / коммунальные / прочее) и комментарием | Extend `CASH_CATEGORIES` with `withdrawal_*` keys (D-01a/D-01b); manual-entry service applies negative sign (D-02a) via `finance.record_cash_movement(category=..., amount_cents=-N, note=...)`; server-side category allow-list already enforced inside `record_cash_movement` (`if category not in CASH_CATEGORIES: raise ValueError`). Mandatory-comment for `withdrawal_other` (D-04). |
| FIN-04 | Оператор может вручную пополнить кассу (начальный остаток / корректировка ошибки) с комментарием | `deposit_opening` / `deposit_correction` keys; positive sign; mandatory comment for `deposit_correction` (D-04). |
| FIN-05 | Списание в минус показывает предупреждение, но допускает подтверждение (паттерн оверселла) | Mirror `writeoffs.register_writeoff` / `sales.register_sale` `confirm != "1"` warn-with-zero-writes flow. Pre-write balance from `finance.compute_balance(session)`; new balance = `compute_balance + amount_cents` (amount negative). Warn partial mirrors `partials/writeoff_oversell.html`. |
| FIN-07 | История движений кассы с пагинацией/фильтрацией (как у других списков — Phase 14) | New `cash_history_view` mirroring `operations.history_view`; `pagination.page_window`; swappable `#cash-history-rows` partial mirroring `partials/history_rows.html`; «Тип» filter = 4 buckets; `extra_qs` preserves filter across pages. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Manual cash write (sign, validation, comment rule, negative gate) | API / Backend — `app/services/finance.py` (new `record_manual_movement`) | — | Single-write-path invariant (D-00b/D-02): only `finance.py` inserts `cash_movements` rows. Sign + allow-list + gate are business logic, never client-trusted. |
| HTTP form handling (parse strings, re-render on error/warn) | API / Backend — `app/routes/finance.py` + `app/routes/mobile_finance.py` | — | Thin routes: parse `Form(...)` strings, call service, branch on `(result, errors)` / warn dict, render partial. Mirrors `routes/writeoffs.py`. |
| Cash balance (pre-write check + display) | API / Backend — `finance.compute_balance` (live SUM) | — | D-00b: no cached balance column; always recomputed. |
| Cash history read (filter/sort/paginate) | API / Backend — `finance.cash_history_view` (new) | — | Read-only; mirrors `operations.history_view`. Portable ORM only. |
| Category → RU label / bucket mapping | API/Backend model constants (`CASH_CATEGORIES` + bucket map in `models.py`) exposed as Jinja globals | Template rendering | Latin-key→RU-label dict pattern (D-01b); labels never hardcoded in templates. |
| Form + history rendering (HTMX partials) | Frontend Server (Jinja2 SSR) — `templates/pages/finance.html`, `templates/mobile_pages/finance.html`, new partials | Browser (htmx swaps) | Server-rendered HTMX, consistent with `writeoff_form`/`sale_form`/`history_rows`. |
| DB immutability (append-only) | Database / Storage — `cash_movements` triggers (migration 0013, already shipped Phase 15) | — | No schema change this phase (D-01: no new column). Triggers already block UPDATE/DELETE. |

## Standard Stack

No new packages. The phase uses the already-installed project stack verbatim (see `pyproject.toml`). Confirmed installed versions:

| Library | Version (installed) | Purpose | Why Standard |
|---------|--------------------|---------|--------------|
| FastAPI | 0.139.* | Routing, `Form(...)` parsing | Existing app framework [VERIFIED: pyproject.toml] |
| SQLAlchemy | 2.0.* | ORM (`select`, `func.sum`, `.where`, `.limit/.offset`) | Existing data layer; portable ORM only [VERIFIED: pyproject.toml] |
| Jinja2 | 3.1.* | Server-rendered templates + partials | Existing template engine [VERIFIED: pyproject.toml] |
| htmx | 2.0.10 (vendored `app/static/htmx.min.js`) | Partial swaps, `hx-post`, `hx-vals`, oob | Existing UI interactivity; offline-vendored [VERIFIED: CLAUDE.md] |
| pytest | 9.1.* | Test runner | Existing suite [VERIFIED: pyproject.toml] |
| httpx | 0.28.* (dev) | `TestClient` transport | Existing test dep [VERIFIED: pyproject.toml] |
| Ruff | 0.15.* (dev) | Lint/format (E,F,I,UP,B; line-length 100) | Existing lint config [VERIFIED: pyproject.toml] |

**Installation:** None. `uv run pytest` and `uv run ruff check` operate on the existing environment.

## Package Legitimacy Audit

**Not applicable — this phase installs zero external packages.** All work reuses in-repo modules and the already-locked stack. No registry lookup required.

## Architecture Patterns

### System Data-Flow Diagram

```
                          ┌─────────────────────────────────────────────┐
  Operator (browser)      │  Финансы page (/finance or /m/finance)      │
  submits a form  ───────►│  «Снять деньги»  |  «Внести деньги»  | Hist │
                          └───────────────┬─────────────────────────────┘
                                          │ hx-post (form) / hx-get (filter,page)
                                          ▼
      ┌───────────────────────────────────────────────────────────────┐
      │ routes/finance.py  (+ routes/mobile_finance.py)                │
      │  - parse Form strings (amount, category/reason, note, confirm) │
      │  - POST withdraw / POST deposit  → call service                │
      │  - GET history (type bucket, page) → call read service         │
      │  - branch: (result, errors) | warn-dict | success             │
      │    ROUTES NEVER WRITE cash (D-00c)                             │
      └───────────────┬───────────────────────────────┬───────────────┘
             write     │                       read     │
                       ▼                                ▼
      ┌────────────────────────────────┐   ┌──────────────────────────────┐
      │ finance.record_manual_movement │   │ finance.cash_history_view    │
      │  (NEW, thin wrapper)           │   │  (NEW, mirrors history_view) │
      │  1 validate category (allow)   │   │  - bucket→category-set filter│
      │  2 parse amount → positive int │   │  - order created_at/seq desc │
      │  3 apply sign by direction     │   │  - .limit/.offset paginate   │
      │  4 comment rule (D-04)         │   │  returns {rows,page,total,   │
      │  5 negative-balance gate (D-05)│   │           total_pages,filter}│
      │     compute_balance()+amount<0 │   └───────────────┬──────────────┘
      │  6 record_cash_movement(...)   │                   │
      └───────────────┬────────────────┘                   │
                      ▼ (single write path)                 ▼
      ┌───────────────────────────────────────────────────────────────┐
      │ finance.record_cash_movement (EXISTING single write path)     │
      │  append 1 immutable CashMovement row (audit-stamped, seq++)    │
      └───────────────┬───────────────────────────────────────────────┘
                      ▼
      ┌───────────────────────────────────────────────────────────────┐
      │ cash_movements table (append-only; UPDATE/DELETE → triggers    │
      │  RAISE(ABORT,'…append-only…'))  — migration 0013, shipped P15  │
      └───────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| File | Change | Responsibility |
|------|--------|----------------|
| `app/models.py` | EDIT `CASH_CATEGORIES` dict (add 7 manual keys + RU labels); add a bucket-grouping map (e.g. `CASH_BUCKETS`) | Source of truth for category→label and category→bucket. |
| `app/routes/__init__.py` | EDIT | Register `CASH_CATEGORIES` (+ bucket labels) as `templates.env.globals` (currently only `WRITEOFF_REASONS`/`OPERATION_TYPE_LABELS` are globals). |
| `app/services/finance.py` | ADD `record_manual_movement(...)` and `cash_history_view(...)` | Manual write wrapper (sign/validate/comment/gate) + read service. `record_cash_movement`/`compute_balance` UNCHANGED. |
| `app/routes/finance.py` | EDIT (add POST handlers + history read; keep GET) | Desktop thin route. |
| `app/routes/mobile_finance.py` | EDIT (add POST handlers + history read; keep GET) | Mobile thin route. |
| `app/templates/pages/finance.html` | EDIT | Balance + two forms + history block (desktop). |
| `app/templates/mobile_pages/finance.html` | EDIT | Balance + two forms + history block (mobile). |
| New partials | ADD | Withdraw form, deposit form, negative-balance warn, cash-history-rows (+ reuse `partials/pagination.html` unchanged). |
| `tests/test_finance.py` | EDIT (extend) | Service + web tests for FIN-03/04/05/07. |

### Pattern 1: Single-write-path manual wrapper (D-02)
**What:** A new `finance` service function is the ONLY caller that decides the sign and validates the manual entry; it delegates the actual insert to the existing `record_cash_movement`.
**When to use:** Every manual withdrawal/deposit.
**Example (mirrors the existing `record_cash_movement` contract):**
```python
# Source: app/services/finance.py (existing signature to wrap)
def record_cash_movement(
    session: Session, *, category: str, amount_cents: int,
    sale_id: str | None = None, note: str | None = None, commit: bool = True,
) -> CashMovement: ...
# Guards: `if category not in CASH_CATEGORIES: raise ValueError(...)` — so
# extending CASH_CATEGORIES is REQUIRED before manual keys can be written.

def compute_balance(session: Session) -> int:
    # live SUM(amount_cents), coalesced to 0. No WHERE, no cache.
    return session.scalar(select(func.coalesce(func.sum(CashMovement.amount_cents), 0)))
```
The new wrapper (planner names it) returns the same `(result, errors)` shape the routes already expect from `register_writeoff`/`register_sale` so the route branching is identical. Sign application: `amount_cents = +parsed` for deposit, `-parsed` for withdrawal (D-02a). Amount parsing: the entered value is a **quantity of money** — reuse `app.core.to_cents(str)` (accepts Russian comma, raises `ValueError` on invalid; already the sanctioned money parser). Reject `<= 0` after parse (blank/zero/negative) with a RU error, zero writes.

### Pattern 2: Warn-but-allow negative-balance gate (D-05, FIN-05)
**What:** Copy the writeoff/sale oversell flow exactly. Compute would-be balance BEFORE any write; if negative and `confirm != "1"`, return a warn dict with ZERO writes; `confirm == "1"` skips the check and writes.
**Example (mirrors `writeoffs.register_writeoff` lines 92–102):**
```python
# withdrawal amount_cents is already NEGATIVE here
if confirm != "1" and compute_balance(session) + amount_cents < 0:
    return ({"negative_balance": {"balance": compute_balance(session),
                                  "amount": -amount_cents}}, {})
# else: record_cash_movement(session, category=..., amount_cents=amount_cents,
#                            note=..., commit=True)
```
**Warn partial** mirrors `app/templates/partials/writeoff_oversell.html`: an `.error-block` with a `button.danger form="withdraw-form" hx-post=".../withdraw" hx-vals='{"confirm":"1"}'` re-POST and a client-only «Вернуться к форме» dismiss. Reuses existing CSS roles — no new colors. Deposits and non-negative withdrawals never enter this branch.

### Pattern 3: Cash history read + swappable rows partial (D-07, FIN-07)
**What:** A read service mirroring `operations.history_view`, but simpler — `cash_movements` has NO product/batch to join. The «Тип» filter is a **coarse bucket** (Продажа/Возврат/Снятие/Внесение) that maps to a SET of category keys, so the WHERE is `CashMovement.category.in_(bucket_categories)`, not `== filter`.
**Example (structure to copy from `operations.history_view`):**
```python
# Source: app/services/operations.py (shape to mirror)
_DEFAULT_ORDER = (CashMovement.created_at.desc(), CashMovement.seq.desc())

def cash_history_view(session, *, bucket: str | None = None,
                      page: int = 0, page_size: int = LIST_PAGE_SIZE) -> dict:
    stmt = select(CashMovement).order_by(*_DEFAULT_ORDER)
    count_stmt = select(func.count()).select_from(CashMovement)
    cats = CASH_BUCKETS.get(bucket)            # unknown/tampered bucket → None → no filter
    if cats:
        stmt = stmt.where(CashMovement.category.in_(cats))
        count_stmt = count_stmt.where(CashMovement.category.in_(cats))
    total = session.scalar(count_stmt) or 0
    total_pages = max(1, -(-total // page_size))
    page = max(0, min(page, total_pages - 1))
    rows = list(session.scalars(stmt.limit(page_size).offset(page * page_size)))
    return {"rows": rows, "page": page, "total": total,
            "total_pages": total_pages, "bucket": bucket or ""}
```
**Route branching** copies `routes/history.py` verbatim: `is_hx = bool(request.headers.get("HX-Request"))`, `page_window(...)`, build `extra_qs = ("&" + urlencode({...})) if ... else ""`, pass `list_url`, `rows_target_id`, and render the rows partial on HX / the full page otherwise. **Rows partial** mirrors `partials/history_rows.html` but with only the columns from D-07b (Когда / Тип-категория / Комментарий / Сумма), the «Тип» `<select>` iterating the 4 buckets, and `{% include "partials/pagination.html" %}` unchanged.

### Pattern 4: Latin-key → RU-label dict + Jinja global
**What:** `CASH_CATEGORIES` is the label source. It must be exposed as a template global exactly like `OPERATION_TYPE_LABELS`.
**Current state (must fix):** `app/routes/__init__.py` registers `WRITEOFF_REASONS` and `OPERATION_TYPE_LABELS` as `templates.env.globals`, but **NOT** `CASH_CATEGORIES`. The manual forms + history rows need it (and a bucket-label map) as globals, so add:
```python
# app/routes/__init__.py — add alongside the existing two globals
templates.env.globals["CASH_CATEGORIES"] = CASH_CATEGORIES
templates.env.globals["CASH_BUCKET_LABELS"] = CASH_BUCKET_LABELS  # bucket key → RU
```

### Anti-Patterns to Avoid
- **Writing `cash_movements` from a route** — violates D-00c. All writes go through `finance.record_manual_movement` → `record_cash_movement`.
- **Adding a `type` column / migration** — D-01 forbids it; direction lives in the `amount_cents` sign, kind in the category prefix.
- **Hardcoding RU labels in templates** — use the `CASH_CATEGORIES` / bucket globals.
- **Filtering the «Тип» by exact category** — the filter is a coarse bucket → `category.in_(set)`. A single `== filter` cannot express «Снятие» (5 categories).
- **Trusting the client for sign/category/comment** — apply sign server-side; re-validate category against the allow-list; enforce the comment rule server-side (D-02a/D-04).
- **`|safe` on `note`** — `note` is untrusted operator text; autoescape only (see Security).
- **Returning 422 for the negative-balance warn** — the oversell/warn re-render returns **200** (see `writeoffs.py` — only true validation errors return 422). htmx swaps 200 and 422 (config present); a warn is a 200 with the intact form.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cash insert / audit stamping / seq | A second writer | `finance.record_cash_movement` | Single-write-path invariant; already stamps `device_id`/`seq`/`created_at`/`created_by` and validates category. |
| Balance | A cached column or manual loop | `finance.compute_balance` | Live SUM, already correct for the negative-balance gate. |
| Money parsing | `float()` / `int()` on the raw field | `app.core.to_cents` | Handles Russian comma, rejects `inf`/`nan`, ROUND_HALF_UP; the ONLY sanctioned money parser. |
| Money display | Manual formatting | `format_cents` (Jinja `cents` filter) | Signed, comma separator, no currency glyph — matches every surface. |
| Pagination math / window | Custom "1 2 … N" | `pagination.page_window` + `paginate` + `partials/pagination.html` | The shared Phase 14 contract; do not fork. |
| Warn-but-allow confirm flow | New modal/JS | Copy `writeoff_oversell.html` + `confirm=="1"` re-POST via `hx-vals` | Identical UX already shipped and tested. |
| IDs / timestamps | `uuid`/`datetime` inline | `app.core.new_id` / `utcnow_iso` | Sync-safe conventions (called inside `record_cash_movement` already). |

**Key insight:** In this codebase almost everything Phase 16 needs is a one-line reuse. The only genuinely new code is the manual-entry validation/sign/gate wrapper and the (simpler-than-`history_view`) cash read service. Building anything custom for money, pagination, or the confirm flow would diverge from locked invariants.

## Common Pitfalls

### Pitfall 1: Manual category not in `CASH_CATEGORIES` → ValueError
**What goes wrong:** `record_cash_movement` raises `ValueError(f"unknown cash category")` for any category not in the dict; a manual withdrawal with a new key that wasn't added to `CASH_CATEGORIES` blows up (or, if caught, silently rejects).
**Why:** The allow-list guard is the write-path's own safety net.
**How to avoid:** Extend `CASH_CATEGORIES` in the SAME plan/wave that introduces the manual write path; assert the new keys exist in a test.
**Warning signs:** `ValueError: unknown cash category` in logs; 422/500 on manual submit.

### Pitfall 2: `CASH_CATEGORIES` not exposed as a Jinja global
**What goes wrong:** The forms/history render blank labels or raise `UndefinedError` because `CASH_CATEGORIES`/bucket map aren't in `templates.env.globals` (only `WRITEOFF_REASONS`/`OPERATION_TYPE_LABELS` are today).
**How to avoid:** Add the globals in `app/routes/__init__.py` (Pattern 4).
**Warning signs:** Empty `<option>` text; Jinja `Undefined` errors.

### Pitfall 3: Filtering the «Тип» by a single category
**What goes wrong:** «Снятие» maps to 5 categories; a `== type_filter` WHERE returns nothing.
**How to avoid:** Bucket→category-set map + `category.in_(...)`. Ignore an unknown/tampered bucket (treat as no filter), mirroring `history_view`'s `if type_filter and type_filter in OPERATION_TYPES`.

### Pitfall 4: Sign confusion on the negative-balance check
**What goes wrong:** Adding a positive amount when the withdrawal is stored negative, or comparing the raw entered amount instead of the would-be balance.
**How to avoid:** Apply the sign FIRST (`amount_cents = -parsed` for withdrawals), then check `compute_balance(session) + amount_cents < 0`. Deposits (positive) never trip the gate.
**Warning signs:** Withdrawals never warn, or deposits incorrectly warn.

### Pitfall 5: Comment rule applied on the client only
**What goes wrong:** Mandatory comment for `withdrawal_other`/`deposit_correction` enforced by HTML `required` but not server-side → a crafted POST bypasses it.
**How to avoid:** Enforce in the service: `if category in {"withdrawal_other","deposit_correction"} and not note.strip(): errors["note"] = ...; return None, errors` — ZERO writes (mirrors the writeoff/sale validate-then-return pattern).

### Pitfall 6: htmx does not swap 4xx by default; warn ≠ error
**What goes wrong:** Returning 422 for the negative-balance warn (or forgetting the htmx-config) drops the response.
**How to avoid:** The htmx-config meta (`"422":{"swap":true}`) is already present in BOTH `base.html` and `mobile_base.html`. Return **200** for the warn re-render (like `writeoff_oversell`), **422** only for true validation errors (like the writeoff/sale routes). Mobile is a standalone base — the config is duplicated there, already correct.

### Pitfall 7: Mobile history uses a DIFFERENT pagination pattern than desktop
**What goes wrong:** Blindly mirroring desktop's page-number `partials/pagination.html` on mobile, or vice-versa, breaks parity with the existing mobile convention.
**Why:** `routes/history.py` (desktop) uses `page_window` + `partials/pagination.html` (numbered pages). `routes/mobile_history.py` (mobile) uses a `has_next` sentinel + `mobile_partials/history_cards.html` + `mobile_partials/history_load_more.html` (cards + «Показать ещё»), rendered via `templates.get_template(...).render()` + an oob-swapped load-more sibling.
**How to avoid:** Planner decides the mobile cash-history layout per D-06a/D-07 discretion — either (a) mirror `mobile_history` cards+load-more, or (b) reuse the desktop numbered bar on mobile. Pick ONE and state it in the plan/UI-SPEC; do not mix. The desktop cash history should use the numbered `page_window`/`pagination.html` path.

### Pitfall 8: Empty-basket / rollback semantics vs. cash
**What goes wrong:** Copying `register_sale`'s multi-write transaction machinery when a manual movement is a single row.
**How to avoid:** A manual movement is ONE `record_cash_movement(..., commit=True)` — no staged multi-write, no `session.rollback()` dance beyond the standard try/except in the route (mirror `routes/writeoffs.py`'s defensive `except Exception → 422 block` for a raw-500 guard).

## Code Examples

### Existing warn-but-allow route branch to copy (writeoffs)
```python
# Source: app/routes/writeoffs.py (POST /writeoff) — the exact branch order
result, errors = register_writeoff(...)          # service returns (result, errors)
if result and result.get("oversell"):            # WARN: 200, intact form + warning
    return templates.TemplateResponse(request, "partials/writeoff_form.html", ctx)  # 200
if errors:                                        # VALIDATION: 422
    return templates.TemplateResponse(request, "partials/writeoff_form.html", ctx, status_code=422)
# SUCCESS: 200 fresh form + oob rows
```
For cash: `withdraw` route → same three branches (`negative_balance` warn = 200, `errors` = 422, success = 200 with refreshed history oob or a targeted history re-render). `deposit` route → only `errors` (422) + success (no warn branch, D-05).

### Existing re-POST-with-confirm control to copy
```html
<!-- Source: app/templates/partials/writeoff_oversell.html -->
<button type="submit" class="danger" form="writeoff-form"
        hx-post="/writeoff" hx-vals='{"confirm": "1"}'
        hx-target="#writeoff-form-wrap" hx-swap="outerHTML"
        hx-disabled-elt="this">Списать всё равно</button>
```
Cash withdraw: same, retargeted to the withdraw form id + withdraw route.

### Existing pagination bar (reuse UNCHANGED)
```html
<!-- Source: app/templates/partials/pagination.html — expects ambient:
     list_url, page (0-based), total_pages, page_window, rows_target_id, extra_qs -->
{% include "partials/pagination.html" %}
```

### Money display / parse (reuse)
```python
# Source: app/core.py
from app.core import to_cents, format_cents   # parse "12,50"→1250 ; render 1250→"12,50"
# format_cents is registered as the Jinja `cents` filter in app/routes/__init__.py
```

## State of the Art

No external technology changes apply — this is an internal reuse phase on a locked stack. Relevant in-repo evolution the planner must respect:

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `/history` load-more («Показать ещё») + `tfoot` | Numbered `page_window` + `partials/pagination.html` | Phase 14 | Desktop cash history MUST use the numbered bar, not load-more. |
| Mobile `/m/history` | Still cards + `has_next` load-more (Phase 11) | Phase 11 | Mobile has NOT migrated to numbered pages — parity decision needed (Pitfall 7). |
| `CASH_CATEGORIES = {sale, return}` | Extended with 7 manual keys this phase | Phase 16 | The write-path allow-list gates on this dict. |

**Deprecated/outdated:** none relevant.

## Runtime State Inventory

> Not a rename/refactor/migration phase — this is additive feature work with **no schema change** (D-01: no new column, no migration). The `cash_movements` table + append-only triggers already exist (migration 0013, Phase 15). No stored data, live-service config, OS-registered state, secrets, or build artifacts are renamed or migrated. **None — verified by reading `app/models.py` (`CashMovement` unchanged), `16-CONTEXT.md` D-01 (no migration), and the absence of any new package in `pyproject.toml`.**

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* (+ httpx 0.28.* for `TestClient`) |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `uv run pytest tests/test_finance.py -x` |
| Full suite command | `uv run pytest` |
| Lint | `uv run ruff check` / `uv run ruff format` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FIN-03 | Withdrawal writes ONE negative row, correct category, balance decreases | service | `uv run pytest tests/test_finance.py -k withdraw -x` | ❌ Wave 0 (extend test_finance.py) |
| FIN-03 | Server applies negative sign to a positive entered amount (D-02a) | service | same | ❌ Wave 0 |
| FIN-03 | Zero/blank/non-integer amount → ZERO writes + error | service | same | ❌ Wave 0 |
| FIN-03 | Mandatory comment for `withdrawal_other` → ZERO writes when blank (D-04) | service | same | ❌ Wave 0 |
| FIN-03 | Unknown/tampered category rejected server-side (allow-list) | service | same | ❌ Wave 0 (contract test exists for `record_cash_movement`; add for wrapper) |
| FIN-04 | Deposit writes ONE positive row; `deposit_correction` requires comment | service | `uv run pytest tests/test_finance.py -k deposit -x` | ❌ Wave 0 |
| FIN-04 | Deposit can never be negative (sign always +) | service | same | ❌ Wave 0 |
| FIN-05 | Withdrawal driving balance <0 with `confirm!="1"` → warn, ZERO writes | service + web | `uv run pytest tests/test_finance.py -k negative -x` | ❌ Wave 0 |
| FIN-05 | Same withdrawal with `confirm=="1"` → writes, balance goes negative | service + web | same | ❌ Wave 0 |
| FIN-05 | Non-negative withdrawal + all deposits never warn | service | same | ❌ Wave 0 |
| FIN-05 | Warn re-render returns 200 (not 422); confirm control present | web | `uv run pytest tests/test_finance.py -k web_withdraw -x` | ❌ Wave 0 |
| FIN-07 | Cash history returns ≤ page_size rows + real total/total_pages | service | `uv run pytest tests/test_finance.py -k history -x` | ❌ Wave 0 |
| FIN-07 | «Тип» bucket filter narrows to the 4 buckets (Продажа/Возврат/Снятие/Внесение) across category sets | service | same | ❌ Wave 0 |
| FIN-07 | History shows sale credits, return debits, AND manual entries | service + web | same | ❌ Wave 0 |
| FIN-07 | Filter preserved across pages via `extra_qs` (HX request) | web | `uv run pytest tests/test_finance.py -k web_history -x` | ❌ Wave 0 |
| FIN-07 | Row renders date, тип/категория label, comment, signed amount | web | same | ❌ Wave 0 |
| FIN-03/04/07 | Mobile parity: `/m/finance` renders forms + history | web (mobile) | `uv run pytest tests/test_finance.py -k mobile -x` | ❌ Wave 0 (use `mobile_client_factory`) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_finance.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green + `uv run ruff check` clean before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_finance.py` — extend with the FIN-03/04/05/07 service + web + mobile cases above (file already exists; no new file needed).
- [ ] Reuse existing fixtures: `session`, `client`, `mobile_client_factory` (build `mobile_finance.router`), `stocked_product` (for seeding sale credits/return debits into the history). No new conftest fixtures required.
- [ ] No framework install needed — pytest/httpx already present.

*(Existing `tests/test_finance.py` covers Phase 15's append-only/balance/credit/debit/page-render behavior; Phase 16 adds the manual-entry and history cases alongside them.)*

## Security Domain

`security_enforcement` is enabled; `security_asvs_level` = 1. Single local operator (no auth in v1, per CLAUDE.md) — so V2/V3/V4 largely N/A, but input-validation and injection controls fully apply to the new write path and filter.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single local user, no auth in v1 (CLAUDE.md). |
| V3 Session Management | no | No sessions in v1. |
| V4 Access Control | no | Single operator; no roles until v2. |
| V5 Input Validation | **yes** | Server-side category allow-list (`if category not in CASH_CATEGORIES: raise`); `to_cents` money parse (rejects inf/nan/garbage); amount `> 0` check; mandatory-comment enforcement server-side (D-04); server applies the sign (never trust client sign); tampered «Тип» bucket ignored (treated as no filter, mirroring `history_view`). |
| V6 Cryptography | no | No secrets/crypto in this phase. |

### Known Threat Patterns for FastAPI + SQLAlchemy + Jinja/HTMX

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via filter/amount | Tampering | Parameterized ORM only (`select`, `.where(...in_(...))`); no raw/f-string SQL (portable-ORM invariant). |
| Stored XSS via `note` (untrusted operator text) rendered in history | Tampering | Jinja **autoescape only — NEVER `|safe`** on `note`/category label (same rule `history_rows.html` documents for product names/notes, T-05-18). |
| Sign/category tampering to force an invalid movement | Tampering / Elevation | Server applies sign by direction (D-02a); re-validate category against `CASH_CATEGORIES`; comment rule server-side (D-04). |
| Bypassing the mandatory-comment client `required` | Tampering | Enforce in the service, ZERO writes on failure. |
| Negative-balance protection bypass | Tampering | The gate is server-side (`compute_balance + amount < 0`); `confirm=="1"` is an explicit operator override, not a silent bypass (matches FIN-05 intent). |
| Immutable-ledger tampering (UPDATE/DELETE a movement) | Repudiation / Tampering | DB triggers `RAISE(ABORT,'…append-only…')` already block it (migration 0013); corrections are new rows. |

## Sources

### Primary (HIGH confidence — in-repo source read this session)
- `app/services/finance.py` — `record_cash_movement` signature + guard, `compute_balance` (live SUM), `next_seq`.
- `app/models.py` — `CASH_CATEGORIES` (`{sale, return}`), `CashMovement` columns (`category` String(20), `amount_cents` Integer signed, `note` String(300), nullable `sale_id` FK, `device_id`/`seq`/`created_at`/`created_by`), `OPERATION_TYPE_LABELS` pattern.
- `app/services/pagination.py` — `LIST_PAGE_SIZE=20`, `page_window`, `paginate`.
- `app/services/operations.py` — `history_view` (SQL filter/sort/paginate + return dict), `filter_products`.
- `app/routes/history.py` — HX-detection, `page_window`, `extra_qs`, full-page vs partial branching.
- `app/templates/partials/history_rows.html`, `partials/pagination.html` — swappable rows + shared pagination contract.
- `app/services/sales.py` (`register_sale`) + `app/services/writeoffs.py` (`register_writeoff`) — `confirm != "1"` warn-with-zero-writes flow; `(result, errors)` return shape.
- `app/routes/writeoffs.py`, `app/routes/sales.py` — three-branch route (warn 200 / errors 422 / success), defensive `except` guard.
- `app/templates/partials/writeoff_oversell.html`, `partials/writeoff_form.html` — warn control + form re-render.
- `app/routes/finance.py`, `app/routes/mobile_finance.py`, `templates/pages/finance.html`, `templates/mobile_pages/finance.html` — current read-only structure.
- `app/routes/__init__.py` — Jinja globals/filters registration (`cents`, `local_dt`, `ru_date`, `WRITEOFF_REASONS`, `OPERATION_TYPE_LABELS`; `CASH_CATEGORIES` NOT yet a global).
- `app/core.py` — `format_cents`, `to_cents`, `new_id`, `utcnow_iso`.
- `app/services/returns.py` — `register_return` return-debit path (context for history rows).
- `app/routes/mobile_history.py`, `templates/mobile_base.html`, `templates/mobile_pages/home.html`, `templates/base.html` — mobile history pattern + existing nav/tiles (already present).
- `tests/test_finance.py`, `tests/test_history.py`, `tests/conftest.py` — test patterns/fixtures.
- `pyproject.toml`, `.planning/config.json` — stack versions, nyquist/security flags.

### Secondary (MEDIUM)
- None — no external lookups required.

### Tertiary (LOW)
- None.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Entered amount is a money value parsed by `to_cents` (accepts «12,50»), not an integer-cents field | Pattern 1 | Low — if the UI collects whole units only, planner uses `to_cents`/`int` accordingly; either way parsing is server-side and rejects invalid. Confirm the input format in UI-SPEC. |
| A2 | Mobile cash-history layout is planner/UI-SPEC discretion (cards+load-more vs numbered bar) | Pitfall 7 | Low — CONTEXT D-06a/D-07 explicitly leave mobile layout to discretion; flagged, not decided. |

**All other claims are VERIFIED against in-repo source.** No external/registry claims were made.

## Open Questions

1. **Mobile history pagination style**
   - What we know: desktop uses numbered `page_window`; mobile `/m/history` uses cards + `has_next` load-more.
   - What's unclear: which to use for mobile cash history (D-06a/D-07 leave it to discretion).
   - Recommendation: planner/UI-SPEC picks ONE explicitly; simplest parity is to reuse the desktop numbered bar on mobile too (fewer new partials), but mirroring `mobile_history` keeps mobile-native feel. State the choice in the plan.

2. **Whether desktop and mobile share the history-rows / form partials**
   - What we know: some features share partials, some render their own (CONTEXT discretion).
   - Recommendation: share the withdraw/deposit form + cash-history-rows partials if the markup is identical; only fork if mobile needs a distinct card layout.

## Environment Availability

Skipped — no NEW external dependencies. The phase runs on the already-installed Python 3.13 / FastAPI / SQLAlchemy / pytest environment (`pyproject.toml`), with the `cash_movements` table + triggers already migrated (migration 0013, Phase 15). Nothing to probe.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; versions read from `pyproject.toml`.
- Architecture / patterns: HIGH — every pattern copied from a specific in-repo file read this session.
- Pitfalls: HIGH — derived directly from the existing writeoff/sale/history code and the two divergences (bucket filter, mobile pagination).
- Security: HIGH — controls map to existing V5 practices already enforced in `record_cash_movement` and the templates.

**Research date:** 2026-07-15
**Valid until:** stable — internal-reuse research; valid until the referenced source files change (no external drift). Re-verify signatures if `finance.py`/`models.py`/`operations.py` are edited before planning.
