# Phase 16: Manual Cash Movements & History - Pattern Map

**Mapped:** 2026-07-15
**Files analyzed:** 9 (2 new symbols in existing service, 1 model edit, 1 globals edit, 2 route edits, 2 page-template edits, ~5 new partials, 1 test edit)
**Analogs found:** 9 / 9 (100% — reuse-heavy phase, every symbol has a direct in-repo analog)

This is a REUSE-HEAVY phase. No new files at the module level except templates/partials; the two new service functions live INSIDE `app/services/finance.py`. Every pattern below is copied from a specific existing file read this session.

---

## File Classification

| New/Modified File | Symbol | Role | Data Flow | Closest Analog | Match |
|-------------------|--------|------|-----------|----------------|-------|
| `app/models.py` (EDIT) | `CASH_CATEGORIES` extend + new `CASH_BUCKETS` / `CASH_BUCKET_LABELS` | model constants | transform (label/bucket map) | `OPERATION_TYPE_LABELS` / `WRITEOFF_REASONS` / `OPERATION_TYPES` (same file, lines 34–79) | exact |
| `app/services/finance.py` (ADD fn) | `record_manual_movement(...)` | service (write wrapper) | CRUD / request-response validate-gate | `writeoffs.register_writeoff` (confirm gate + `(result, errors)`) | exact |
| `app/services/finance.py` (ADD fn) | `cash_history_view(...)` | service (read) | CRUD read / filter-sort-paginate | `operations.history_view` | exact (simpler — no joins) |
| `app/routes/__init__.py` (EDIT) | Jinja globals | config | — | existing `WRITEOFF_REASONS`/`OPERATION_TYPE_LABELS` globals (lines 17–18) | exact |
| `app/routes/finance.py` (EDIT) | POST withdraw/deposit + GET history | route (thin) | request-response + read | `routes/writeoffs.py` (POST 3-branch) + `routes/history.py` (GET read) | exact |
| `app/routes/mobile_finance.py` (EDIT) | POST withdraw/deposit + GET history | route (thin, mobile) | request-response + read | `routes/mobile_finance.py` current + `routes/mobile_history.py` (cards+load-more) | exact |
| `app/templates/pages/finance.html` (EDIT) | balance + 2 forms + history block | template (desktop page) | SSR | current `pages/finance.html` + `pages/writeoff_form.html` shell | exact |
| `app/templates/mobile_pages/finance.html` (EDIT) | balance + 2 forms + history | template (mobile page) | SSR | current mobile finance + `mobile_pages/history.html` | exact |
| NEW `partials/withdraw_form.html` (+ `deposit_form.html`) | SHARED forms | template partial | SSR/HTMX | `partials/writeoff_form.html` (`form.stacked-form`, wrap+oob) | role-match |
| NEW `partials/cash_negative_balance.html` | warn-but-allow | template partial | SSR/HTMX | `partials/writeoff_oversell.html` | exact |
| NEW `partials/cash_history_rows.html` | desktop rows (table + numbered pagination) | template partial | SSR/HTMX | `partials/history_rows.html` + `partials/pagination.html` (reused unchanged) | exact |
| NEW `mobile_partials/cash_history_cards.html` + `cash_history_load_more.html` | mobile cards + load-more | template partial | SSR/HTMX | `mobile_partials/history_cards.html` + `history_load_more.html` | exact |
| `tests/test_finance.py` (EDIT) | FIN-03/04/05/07 cases | test | — | existing `tests/test_finance.py` (fixtures `session`,`client`,`mobile_client_factory`,`stocked_product`) | exact |

---

## Pattern Assignments

### `app/models.py` — extend `CASH_CATEGORIES` + add bucket maps (model constants, transform)

**Analog:** `OPERATION_TYPE_LABELS` / `WRITEOFF_REASONS` in the same file. Current state to EXTEND (lines 49–79):

```python
WRITEOFF_REASONS = {
    "damaged": "Брак", "expired": "Просрочка", "lost": "Потеря",
    "personal": "Личное использование", "gift": "Подарок", "other": "Прочее",
}
# Phase 15 — EXTEND this (currently only sale/return):
CASH_CATEGORIES = {
    "sale": "Продажа",
    "return": "Возврат",
}
```

**To add** (per D-01a/D-01b — prefixed keys so buckets derive by prefix; RU labels in the dict):
- withdrawal keys: `withdrawal_supplier` Оплата поставщику / `withdrawal_salary` Зарплата / `withdrawal_rent` Аренда / `withdrawal_utilities` Коммунальные / `withdrawal_other` Прочее.
- deposit keys: `deposit_opening` Начальный остаток / `deposit_correction` Корректировка.
- new `CASH_BUCKETS: dict[str, tuple[str, ...]]` mapping bucket key → category-key set, e.g. `{"sale": ("sale",), "return": ("return",), "withdrawal": (...5 keys...), "deposit": ("deposit_opening","deposit_correction")}`. Mirrors how `history_view` gates on `OPERATION_TYPES` membership.
- new `CASH_BUCKET_LABELS = {"sale":"Продажа","return":"Возврат","withdrawal":"Снятие","deposit":"Внесение"}`.

`CashMovement.category` is `String(20)` (line 343) — keep new keys ≤ 20 chars (all above fit). `note` is `String(300)` (line 347). Column is EXTEND-only; NO migration (D-01).

---

### `app/services/finance.py` — `record_manual_movement(...)` (service, write wrapper)

**Analog:** `writeoffs.register_writeoff` (validate → allow-list → confirm gate → single-write-path). The existing write path to WRAP (do NOT fork) — `finance.py` lines 29–76:

```python
def record_cash_movement(session, *, category, amount_cents,
                         sale_id=None, note=None, commit=True) -> CashMovement:
    if category not in CASH_CATEGORIES:            # allow-list backstop (V5)
        raise ValueError(f"unknown cash category: {category!r}")
    ...  # stamps id/device_id/seq/created_at/created_by, session.add, commit

def compute_balance(session) -> int:               # live SUM, no cache (D-00b)
    return session.scalar(select(func.coalesce(func.sum(CashMovement.amount_cents), 0)))
```

**Validate-then-return + confirm-gate shape to copy** from `writeoffs.register_writeoff` (lines 32–118):

```python
def register_writeoff(session, *, ..., confirm="") -> tuple[dict | None, dict[str, str]]:
    errors: dict[str, str] = {}
    ...  # per-field RU errors accumulate
    if reason_code not in WRITEOFF_REASONS:        # V5 server-side allow-list
        errors["reason"] = REASON_ERROR
    if errors:
        return None, errors                        # ZERO writes on validation fail
    ...
    if confirm != "1" and qty > batch.quantity:    # warn-but-allow, ZERO writes
        return ({"oversell": {...}}, {})
    try:
        op = record_operation(..., commit=True)
    except (IntegrityError, ValueError):
        session.rollback()
        return None, {"form": SAVE_FAILED_ERROR}
    return {"product": product, "operation": op}, {}
```

**`record_manual_movement` contract (planner writes):** same `(result, errors)` return so routes branch identically. Steps (D-02/D-02a/D-04/D-05):
1. Validate `category in CASH_CATEGORIES` AND matches the intended direction set (withdrawal vs deposit); else `errors["category"] = "Выберите категорию."`/"…основание."
2. Parse amount via `app.core.to_cents(str)` (core.py line 28 — accepts "12,50", raises `ValueError`, ROUND_HALF_UP). On `ValueError` or `≤ 0` → `errors["amount"] = "Введите сумму больше нуля."`, ZERO writes.
3. Apply sign server-side: `amount_cents = -parsed` (withdrawal) / `+parsed` (deposit). Never trust client sign (D-02a).
4. Comment rule (D-04): `if category in {"withdrawal_other","deposit_correction"} and not note.strip(): errors["note"] = "Укажите комментарий."` → return `None, errors`.
5. Negative-balance gate (D-05, withdrawal only): `if confirm != "1" and compute_balance(session) + amount_cents < 0: return ({"negative_balance": {"balance": compute_balance(session), "amount": -amount_cents}}, {})`. Deposits never enter this branch.
6. `record_cash_movement(session, category=..., amount_cents=amount_cents, note=note.strip() or None, commit=True)`; wrap in `try/except (IntegrityError, ValueError): session.rollback(); return None, {"form": ...}`.

Reuse `new_id`/`utcnow_iso` implicitly (already called inside `record_cash_movement`) — do NOT re-stamp.

---

### `app/services/finance.py` — `cash_history_view(...)` (service, read filter/sort/paginate)

**Analog:** `operations.history_view` (operations.py lines 23–78). Copy the count-then-clamp-then-slice shape; SIMPLER — `cash_movements` has NO Product/Batch join.

```python
_DEFAULT_ORDER = (Operation.created_at.desc(), Operation.seq.desc())   # mirror with CashMovement
order_by = _SORT_MAP.get(sort, _DEFAULT_ORDER)
stmt = select(Operation, Product, Batch).join(...).order_by(*order_by)
count_stmt = select(func.count()).select_from(Operation).join(...)
if type_filter and type_filter in OPERATION_TYPES:          # unknown/tampered → no filter (T-05-20)
    stmt = stmt.where(Operation.type == type_filter)
    count_stmt = count_stmt.where(Operation.type == type_filter)
total = session.scalar(count_stmt) or 0
total_pages = max(1, -(-total // page_size))
page = max(0, min(page, total_pages - 1))                   # clamp server-side (T-14-04)
rows = session.execute(stmt.limit(page_size).offset(page * page_size)).all()
return {"rows": [...], "page": page, "total": total,
        "total_pages": total_pages, "type_filter": type_filter or "", ...}
```

**`cash_history_view` differences (D-07/D-07a):**
- `select(CashMovement)` only — no join, rows are bare `CashMovement`.
- The «Тип» param is a **coarse bucket**, not an exact category. Use `CASH_BUCKETS.get(bucket)` → tuple of category keys → `stmt.where(CashMovement.category.in_(cats))`. Unknown/tampered bucket → `None` → no filter (mirrors `if type_filter in OPERATION_TYPES`). This is Pitfall 3 — a `== bucket` filter CANNOT express «Снятие» (5 categories).
- Order: `(CashMovement.created_at.desc(), CashMovement.seq.desc())`.
- `LIST_PAGE_SIZE` from `app.services.pagination` (=20). `page_window`/`paginate` reused unchanged (pagination.py lines 6, 9, 31).
- Return dict key: `"bucket": bucket or ""` (instead of `type_filter`).

---

### `app/routes/__init__.py` — register Jinja globals (config)

**Analog:** existing globals block (lines 16–18). CASH_CATEGORIES is NOT yet a global (Pitfall 2). Add alongside:

```python
templates.env.globals["WRITEOFF_REASONS"] = WRITEOFF_REASONS          # existing
templates.env.globals["OPERATION_TYPE_LABELS"] = OPERATION_TYPE_LABELS # existing
# ADD:
templates.env.globals["CASH_CATEGORIES"] = CASH_CATEGORIES
templates.env.globals["CASH_BUCKET_LABELS"] = CASH_BUCKET_LABELS
```

`format_cents` is already the `cents` filter (line 12); `to_cents` is imported per-service, not a template helper.

---

### `app/routes/finance.py` — POST withdraw / POST deposit / GET history (thin route)

**Analog A — POST 3-branch** from `routes/writeoffs.py` `writeoff_create` (lines 99–189). Fields arrive as `Form("")` strings (Pydantic rejects "" for `int | None`); branch order:

```python
try:
    result, errors = register_writeoff(session, ..., confirm=confirm)
except Exception:                                  # noqa: BLE001 — block error, never raw 500
    session.rollback(); logger.exception(...)
    return templates.TemplateResponse(request, "partials/writeoff_form.html", ctx, status_code=422)
if result and result.get("oversell"):              # WARN: 200, intact form
    return templates.TemplateResponse(request, "partials/writeoff_form.html", ctx)          # 200
if errors:                                          # VALIDATION: 422
    return templates.TemplateResponse(request, "partials/writeoff_form.html", ctx, status_code=422)
# SUCCESS: 200 fresh form + include_oob_rows=True
return templates.TemplateResponse(request, "partials/writeoff_form.html", ctx)
```

**For cash:**
- `POST /finance/withdraw`: three branches — `result.get("negative_balance")` warn = **200** (intact form + `partials/cash_negative_balance.html`), `errors` = 422, success = 200 fresh form + oob-refreshed cash-history rows. Form fields: `amount=Form("")`, `category=Form("")`, `note=Form("")`, `confirm=Form("")`.
- `POST /finance/deposit`: only two branches — `errors` = 422, success = 200 (NO warn branch, D-05). Fields: `amount`, `category` (reason), `note`.
- Keep the defensive `except Exception → 422` guard + `session.rollback()` + `logger.exception` (Pitfall 8; do NOT copy `register_sale`'s multi-write machinery — a movement is ONE row).
- Success re-render carries refreshed history rows out-of-band (mirror `include_oob_rows` in `writeoff_form.html` lines 84–90).

**Analog B — GET history** from `routes/history.py` (lines 16–62). Copy verbatim: HX detection, `page_window`, `extra_qs`, full-page-vs-partial:

```python
is_hx = bool(request.headers.get("HX-Request"))
pw = page_window(result["page"], result["total_pages"])
qs_parts = {k: v for k, v in {"bucket": result["bucket"]}.items() if v}
extra_qs = ("&" + urlencode(qs_parts)) if qs_parts else ""
context = {..., "list_url": "/finance/history", "rows_target_id": "cash-history-rows",
           "extra_qs": extra_qs}
if is_hx:
    return templates.TemplateResponse(request, "partials/cash_history_rows.html", context)
return templates.TemplateResponse(request, "pages/finance.html", context)
```

Pass `finance_base="/finance"` into the page context (UI-SPEC Q2 — shared forms parameterized by route prefix). Also pass `balance_cents=compute_balance(session)` (current route line 18).

---

### `app/routes/mobile_finance.py` — POST + mobile history (thin route, mobile)

**Analog:** current `mobile_finance.py` (identical to desktop finance route) + `routes/mobile_history.py` (lines 22–54) for the cards+load-more mobile history (UI-SPEC Q1 — mobile uses cards + «Показать ещё», NOT numbered pages):

```python
result = history_view(session, type_filter=type or None, product_id=None, page=page)
context = {"rows": result["rows"],
           "has_next": result["page"] < result["total_pages"] - 1,   # derive sentinel locally
           "page": result["page"], "type_filter": result["type_filter"]}
is_hx = bool(request.headers.get("HX-Request"))
if is_hx:
    cards_html = templates.get_template("mobile_partials/history_cards.html").render(**context)
    load_more_html = templates.get_template("mobile_partials/history_load_more.html").render(oob=True, **context)
    return HTMLResponse(cards_html + load_more_html)
return templates.TemplateResponse(request, "mobile_pages/history.html", context)
```

Mobile POST handlers reuse the SAME `register_manual_movement` service + same 3-branch logic; render the SHARED `partials/withdraw_form.html`/`deposit_form.html` with `finance_base="/m/finance"`. Derive `has_next` locally from `total_pages` (mobile keeps the Phase 11 load-more sentinel; do NOT mix numbered pages — Pitfall 7).

---

### Templates

**`pages/finance.html` (EDIT)** — current is balance-only (2 lines). Extend to: `<h1>Баланс кассы</h1>` + balance `<p class="num"><strong>{{ balance_cents | cents }}</strong></p>` (keep UNCHANGED — UI-SPEC), then include withdraw form, deposit form, then cash-history block. Mirror `pages/writeoff_form.html` structure (extends `base.html`, `{% include %}` the form partial + rows partial).

**`partials/withdraw_form.html` / `deposit_form.html` (NEW, SHARED)** — copy `partials/writeoff_form.html` (lines 1–92): `#*-form-wrap` outer div, `<form class="stacked-form">`, `.field` blocks, `<select>` iterating a labels dict (lines 65–70 pattern), `hx-post`/`hx-target=#…-form-wrap`/`hx-swap="outerHTML"`/`hx-disabled-elt="find button"`, and the `include_oob_rows` tail (lines 84–90).
- Amount field: `<input type="text" name="amount" inputmode="decimal" placeholder="0,00">` (UI-SPEC Q3 — parsed by `to_cents`; identical to `sale_form`).
- Category/reason `<select name="category">` iterates the `withdrawal_*` (or `deposit_*`) subset of the `CASH_CATEGORIES` global; first `<option value="">` empty (mirror writeoff_form line 66).
- Comment `<input name="note">` — neutral label «Комментарий», NO "(необязательно)" hint (UI-SPEC D-04 resolution); error `<p class="error">` shown on submit only.
- Parameterize route: `hx-post="{{ finance_base }}/withdraw"` (Q2).

**`partials/cash_negative_balance.html` (NEW)** — copy `partials/writeoff_oversell.html` (lines 1–21) exactly, retargeted:
```html
<div class="error-block" id="withdraw-negative-warning">
  <p><strong>Баланс уйдёт в минус</strong></p>
  <p>Текущий баланс {{ balance | cents }}, снимаете {{ amount | cents }}.</p>
  <div class="form-actions">
    <button type="submit" class="danger" form="withdraw-form"
            hx-post="{{ finance_base }}/withdraw" hx-vals='{"confirm": "1"}'
            hx-target="#withdraw-form-wrap" hx-swap="outerHTML"
            hx-disabled-elt="this">Снять всё равно</button>
    <button type="button" class="secondary"
            hx-on:click="this.closest('#withdraw-negative-warning').remove()">Вернуться к форме</button>
  </div>
</div>
```

**`partials/cash_history_rows.html` (NEW, desktop)** — copy `partials/history_rows.html` (lines 1–132) but SIMPLER: `<div id="cash-history-rows">`, a header-row `<select name="bucket">` iterating `CASH_BUCKET_LABELS` (mirror the type `<select>` lines 39–47) with «Все типы» empty option, a 4-column table (Когда / Тип / Комментарий / Сумма — D-07b), rows show `{{ mv.created_at | local_dt }}`, `{{ CASH_CATEGORIES.get(mv.category, mv.category) }}`, `{{ mv.note }}` (autoescape ONLY, never `|safe`), `{{ mv.amount_cents | cents }}` (signed). Empty-state: «Движений пока нет.» / «Нет движений по выбранному типу.» (mirror lines 70–75). End with `{% include "partials/pagination.html" %}` UNCHANGED.

**`mobile_partials/cash_history_cards.html` + `cash_history_load_more.html` (NEW)** — copy `mobile_partials/history_cards.html` (lines 10–46) and `history_load_more.html` (lines 1–14). Cards show the 4 fields as `.mobile-card` stacks; load-more `hx-get="/m/finance/history?bucket={{ ... }}&page={{ page + 1 }}"` with `hx-target="#cash-history-cards" hx-swap="beforeend"` + `hx-swap-oob` sentinel.

**`mobile_pages/finance.html` (EDIT)** — copy structure of `mobile_pages/history.html` (lines 1–24): `{% block step_indicator %}{% endblock %}` (already present in current mobile finance), balance, shared forms, then bucket `<select>` + `<div id="cash-history-cards">` + load-more.

---

## Shared Patterns

### Single-write-path invariant (D-00c)
**Source:** `app/services/finance.py` `record_cash_movement` (lines 29–67).
**Apply to:** every write. Routes NEVER insert `cash_movements`; they call `record_manual_movement` → `record_cash_movement`. The `if category not in CASH_CATEGORIES: raise ValueError` guard (lines 50–51) is why `CASH_CATEGORIES` MUST be extended in the same wave (Pitfall 1).

### Warn-but-allow confirm gate (FIN-05)
**Source:** `writeoffs.register_writeoff` lines 92–102 (service) + `partials/writeoff_oversell.html` (template) + `routes/writeoffs.py` lines 155–164 (200 warn branch).
**Apply to:** withdraw only. Warn returns **200** (htmx swaps 200; the `"422":{"swap":true}` config in both `base.html`/`mobile_base.html` covers only true errors — Pitfall 6). `confirm=="1"` re-POST via `hx-vals`.

### Latin-key → RU-label dict + Jinja global
**Source:** `models.py` `OPERATION_TYPE_LABELS`/`WRITEOFF_REASONS` + `routes/__init__.py` globals + template usage `{{ DICT.get(key, key) }}` (history_rows.html line 80).
**Apply to:** category labels in both forms and history rows; bucket labels in the filter. Never hardcode RU in templates (Pitfall 2 / anti-pattern).

### Shared pagination (desktop)
**Source:** `pagination.page_window`/`paginate`/`LIST_PAGE_SIZE` + `partials/pagination.html` (reused UNCHANGED — expects ambient `list_url`, `page`, `total_pages`, `page_window`, `rows_target_id`, `extra_qs`).
**Apply to:** desktop cash history only. Mobile uses the `has_next` load-more sentinel instead (Pitfall 7).

### Money parse / display
**Source:** `app.core.to_cents` (core.py line 28, service-side parse) + `format_cents` (line 49, `cents` Jinja filter). **Apply to:** amount input parse (service) and every rendered amount (templates). Signed, no currency symbol.

### Autoescape-only on untrusted text (security V5)
**Source:** `history_rows.html` header comment (T-05-18). **Apply to:** `note` and category labels in cash history rows/cards — NEVER `|safe`.

---

## No Analog Found

None. Every symbol has a direct in-repo analog (this is why the phase is classified reuse-heavy). The only genuinely NEW logic is the composition inside `record_manual_movement` (sign application + direction/comment rules) and the bucket→category-set mapping in `cash_history_view` — both assembled from existing pieces, no novel technique.

---

## Metadata

**Analog search scope:** `app/services/`, `app/routes/`, `app/templates/partials/`, `app/templates/mobile_partials/`, `app/templates/pages/`, `app/templates/mobile_pages/`, `app/models.py`, `app/core.py`.
**Files scanned/read:** finance.py, writeoffs.py, operations.py, pagination.py, history.py, mobile_history.py, finance.py+mobile_finance.py routes, models.py (constants + CashMovement cols), core.py (helpers), routes/__init__.py, and 8 templates.
**Pattern extraction date:** 2026-07-15
</content>
</invoke>
