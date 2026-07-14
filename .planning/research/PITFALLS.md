# Pitfalls Research

**Domain:** Adding a cash-balance/cash-flow ledger ("Касса") module to an existing single-operator, offline, SQLite/FastAPI/HTMX warehouse-and-sales app with an append-only stock ledger
**Researched:** 2026-07-14
**Confidence:** HIGH for architecture-grounded pitfalls (read directly from `app/services/ledger.py`, `sales.py`, `returns.py`, `writeoffs.py`, `receipts.py`, `reports.py`, `db.py`, `models.py`); MEDIUM for general financial-ledger/small-business practitioner findings (web search, no official spec exists for "how to bolt cash tracking onto an existing app")

## Critical Pitfalls

### Pitfall 1: Bolting cash movements onto the existing `operations` table

**What goes wrong:**
The temptation is to add `cash_in`/`cash_out` as two more members of `OPERATION_TYPES` and reuse `record_operation()`, since it's already "the single write path." This breaks on contact: `Operation.product_id` is a `NOT NULL` FK, and `record_operation` requires `STOCK_AFFECTING_TYPES` to carry a mandatory, product-owned `batch_id` (D-12 guard) — but a cash withdrawal for "зарплата" has no product and no batch. You'd either force a dummy "cash" product/batch (data-model lie) or special-case the guard (weakens the D-12 invariant for every future stock type too). It also pollutes `reports.py`, which filters `Operation.type == "sale"` / `"writeoff"` directly against this same table for revenue/profit math (`app/services/reports.py:38,102,158,187`) — new row types with `qty_delta` semantics that don't mean "units of stock" corrupt those SUM queries if anyone forgets to add a `type` filter.

**Why it happens:**
The codebase's existing "one ledger table" story is compelling and the docstrings ("record_operation is the ONLY sanctioned write path") read as a project-wide rule, not a stock-specific one.

**How to avoid:**
Create a **separate** append-only ledger table (e.g. `cash_movements`), mirroring the *pattern* of `ledger.py` (own single write-path function, e.g. `record_cash_movement()`) but not the *table*. Give it its own DB-level immutability triggers (copy the `operations_no_update`/`operations_no_delete` pattern in `app/db.py`), its own `id`/`created_at`/`created_by`/`device_id`/`seq` columns, and a nullable `sale_id` FK to link auto-credit rows back to `Sale` — but no `product_id`/`batch_id` requirement.

**Warning signs:**
Any PR that adds a value to `OPERATION_TYPES` for cash, or that makes `Operation.product_id` nullable "just for cash rows."

**Phase to address:**
The phase that introduces the cash schema (first phase of the milestone) — this is a foundational data-model decision, expensive to reverse once real financial rows exist.

---

### Pitfall 2: Auto-credit wired into `sales.py` but not symmetrically into `returns.py`

**What goes wrong:**
`register_sale()` (`app/services/sales.py`) and `register_return()` (`app/services/returns.py`) are two separate service modules with separate write paths. If the cash auto-credit is added only inside `register_sale`'s commit block, a sale-linked return (already a shipped feature, OPS-02) silently leaves the cash balance permanently inflated by however much was returned — the balance stops reflecting reality the very first time a customer returns anything.

**Why it happens:**
Returns are architecturally a *second* write path that happens to reuse the same `sale_id`/`product_id` shape as sales but lives in a different file (`returns.py`) written in a different phase (Phase 5). It's easy to treat "wire up cash" as a `sales.py`-only task because that's where "Касса пополняется автоматически с каждой продажи" naturally points a developer's attention.

**How to avoid:**
Treat cash-in and cash-out as symmetric obligations from day one, the same way the codebase already treats price/cost freezing symmetrically (D-07: "price/cost symmetry — copy the origin sale op's FROZEN unit_price_cents/unit_cost_cents"). Add the return's cash debit in the exact same commit as the `return` operation write inside `register_return`, not as an afterthought bolted onto `sales.py`.

**Warning signs:**
Grep for the new cash-write call and check it appears in *both* `sales.py` and `returns.py` before the phase is called done. A test that sells, fully returns, and asserts balance is back to its pre-sale value is the concrete regression guard.

**Phase to address:**
Same phase as Pitfall 1 (schema + auto-credit) — return-symmetry must ship in the same phase as sale auto-credit, not deferred to a later phase, or there will be a window where returns silently break the balance.

---

### Pitfall 3: Trying to "match" a return against the original cash-in row instead of deriving the debit independently

**What goes wrong:**
A naive design looks up the sale's original cash-in movement (by `sale_id`) and tries to reduce it, or asserts the return amount against it, then fails/logs a warning "cannot find matching cash-in movement" when the lookup comes up empty (e.g. legacy sales predating the cash feature, or a partial return where the "amounts don't match" because only part of the line was returned). This reconciliation logic is unnecessary and fragile.

**Why it happens:**
"Reverse a previous entry" is the natural mental model for a refund, borrowed from double-entry bookkeeping intuition, but this app already solved the equivalent problem for *stock* by never editing the original `sale` op and instead writing a fresh, independently-computed `return` op (D-06/D-07) whose amount comes from the **return's own** `qty * frozen unit_price_cents`, not from re-reading and adjusting the original sale row (which the `operations_no_update` trigger wouldn't even allow).

**How to avoid:**
Mirror `returns.py`'s existing approach exactly: `register_return` already copies `origin.unit_price_cents` (D-07, frozen at sale time) and computes `qty_delta`/amount purely from `qty * origin.unit_price_cents` for the returned quantity — no lookup or match against any prior movement is needed. Apply the identical rule to cash: the return's cash debit = `qty_returned * origin.unit_price_cents` (or, for a multi-line sale, sum only the returned line's own frozen price), written fresh, independent of whatever the original cash-in movement recorded. This sidesteps the "what if the original movement is missing or the amounts don't match" question entirely — there is nothing to match against.
This also means: don't seed the cash-in movement at the header level as a single lump `total_cents` row per `Sale` if you want partial per-line returns to net cleanly. Prefer one cash-in movement per sale `Operation` line (mirroring the ledger's existing per-line granularity) — or, if a single lump credit per sale is kept for simplicity, ensure the return debit is still computed independently line-by-line and never "diffs" the header's lump sum.

**Warning signs:**
Any code path that does `session.get(CashMovement, ...)` by `sale_id` and then errors/warns when it's `None`, or that tries to `sum(returns) <= original_credit` and blocks the return if not.

**Phase to address:**
Same phase as Pitfall 2 (return handling) — design the debit formula before writing any code, since retrofitting "independent computation" after a matching-based design ships is a rewrite, not a patch.

---

### Pitfall 4: Balance computed from a stale cache instead of a live SUM, or updated outside the writing transaction

**What goes wrong:**
The existing stock model already had this exact problem and solved it: `Product.quantity` is a cached projection, but it's *always* recomputable from `SUM(operations.qty_delta)` via `compute_stock()`, updated with a SQL-side atomic increment (`product.quantity = Product.quantity + qty_delta`) **inside the same transaction** as the ledger insert (`app/services/ledger.py:120-126`), and there's a `rebuild_stock()` repair/assertion function. A cash balance implemented as "just a cached integer column, updated in application code (`balance += amount`) in a separate step after the ledger write" reintroduces the exact class of bug (stale-read window, no atomicity, no recompute-and-verify path) that `record_operation`'s design was built to eliminate.

**Why it happens:**
It's tempting to treat "current balance" as a simple running total for display speed, without replicating the SQL-side-increment-in-the-same-transaction discipline, especially since the milestone description literally says "текущий баланс" (a display concept), inviting a naive `balance` column.

**How to avoid:**
Either (a) don't cache at all — at this scale (one operator, local SQLite, at most a few thousand cash rows a year) `SELECT COALESCE(SUM(amount_cents), 0) FROM cash_movements` is cheap and always correct, matching how `compute_stock()` is available as ground truth; or (b) if a cached balance is added for display speed, update it with the same SQL-side atomic increment pattern in the SAME transaction as the movement insert, and ship a `rebuild_cash_balance()` counterpart to `rebuild_stock()` from day one, not as a later "fix."

**Warning signs:**
A `balance` field updated via ORM read-modify-write (`balance = balance.value + amount`) instead of `Model.balance + amount` in the UPDATE; a balance update committed in a different `session.commit()` than the movement row.

**Phase to address:**
The schema/write-path phase (Pitfall 1) — the balance-computation strategy is part of the same design decision as the table shape.

---

### Pitfall 5: No idempotency guard against a sale being processed (and cash auto-credited) twice

**What goes wrong:**
`register_sale()` has no idempotency key today — a double-click on submit, a retried HTMX request after a network blip on localhost, or (once multi-operator sync exists) a duplicate sync replay could in principle create two `Sale` headers with duplicate `sale` operations. For stock, a duplicate sale silently oversells by the same amount twice, which the existing oversell warning would at least flag on the *second* attempt if stock runs out — but a duplicate cash auto-credit has no equivalent guard, since cash "oversell" isn't checked at all (crediting cash never fails). Money gets invisibly duplicated with no warning path, unlike stock.

**Why it happens:**
The app was designed for a single trusted local operator with WAL + `busy_timeout=5000` serializing writes at the DB level — which prevents *corruption* from concurrent writes, but does nothing to prevent the *same logical action* (one basket) from being submitted twice as two separate, individually-valid transactions.

**How to avoid:**
This is a pre-existing gap in the whole app, not something the cash feature must fully solve — but the cash feature is where it becomes financially visible for the first time. At minimum: disable the sale-submit button/form during the HTMX request (standard `hx-disabled-elt` pattern) to close the double-click window, and document that duplicate-basket detection (e.g. an idempotency token per basket submission) is a gap worth closing before/alongside this milestone rather than silently inherited. Do not treat "cash auto-credit never fails" as a reason to skip this — the absence of a failure mode is exactly what makes duplicates invisible.

**Warning signs:**
Two `Sale` headers with identical `customer_id`, lines, and `created_at` within the same second; a balance that's "suspiciously exactly 2x" a spot-check total.

**Phase to address:**
Flag for the schema/auto-credit phase to at least add the UI-level submit-guard; a full idempotency-key mechanism can be deferred but should be an explicit, named deferral (Future/Out-of-Scope entry), not a silent gap.

---

### Pitfall 6: Negative-balance validation inconsistent with the app's established warn-but-allow pattern

**What goes wrong:**
Two wrong choices are equally tempting and equally bad: (a) hard-blocking any withdrawal that would take the balance negative (inconsistent with how this app treats every other "physically implausible" situation — oversell and below-minimum-price both warn-and-allow-with-confirm, never hard-block), or (b) allowing withdrawals with zero warning at all, which for real money is worse than for stock because a negative cash balance either means a data-entry mistake or a genuinely urgent real-world problem (cash box empty), and the operator should be told either way.

**Why it happens:**
"Money" instinctively feels like it should be stricter than "stock count," pulling toward a hard block; but this app has a strong, already-validated precedent (oversell in `sales.py`/`writeoffs.py`/`transfers.py`, below-minimum-price in `sales.py` PRICE-01) of warn-with-`confirm=1`-to-override, chosen specifically because a purely local single-operator tool should never trap the operator behind a check it can't override (e.g. a legitimate reason: cash was withdrawn in person before this app recorded the receipt).

**How to avoid:**
Reuse the exact same warn-but-allow UX contract already implemented for oversell/min-price: compute the check, and when `confirm != "1"` and the resulting balance would go negative, return a warning payload with ZERO writes; `confirm == "1"` skips the check and writes anyway (balance may go negative, exactly like stock may go negative). This keeps the whole app's validation vocabulary consistent for the operator instead of introducing a third, different pattern.

**Warning signs:**
A withdrawal route that returns a raw 4xx/500 or refuses the write entirely with no `confirm` escape hatch.

**Phase to address:**
The manual-debit phase.

---

### Pitfall 7: No opening/seed balance, so the very first negative-balance warning is a false alarm

**What goes wrong:**
The milestone's target features list auto-credit-on-sale and manual-debit-with-reason, but no "set starting balance" concept. If Финансы launches computing balance purely from `SUM(cash_movements.amount_cents)` starting at zero, then any real-world cash the operator already has on hand at go-live is invisible to the app. The very first supplier payment or salary withdrawal recorded — even though physically fine — will trip the negative-balance warning from Pitfall 6, teaching the operator to distrust or ignore the warning from day one.

**Why it happens:**
This mirrors a genuine architectural blind spot: the app has never modeled "initial state" for money the way it does for stock (every stock item starts at zero and is built up via receipts — there's no equivalent "cash receipt" concept to seed a starting cash balance, since receipts in this app only ever add *stock*, never cash — see Pitfall 9).

**How to avoid:**
Give the operator an explicit way to record a starting/adjustment cash-in movement (e.g. a "Внесение/корректировка" category available on the manual-movement form, or a dedicated one-time "opening balance" action) before relying on the negative-balance warning. This does not need its own UI flow — reusing the manual movement form with an `is_credit` direction and a "внесение наличных" category, mirroring how `WRITEOFF_REASONS` already models a category dict with an `"other"` free-text escape hatch, covers it.

**Warning signs:**
The requirements list only mentions debit categories ("оплата заказа поставщику, зарплата, прочее") — if the shipped UI genuinely has no way to add a manual *credit*, this is unaddressed.

**Phase to address:**
The manual-debit phase — build the movement form bidirectional (credit + debit) from the start rather than debit-only, even though the milestone description emphasizes debit.

---

### Pitfall 8: No correction/reversal path for a mistyped manual entry, colliding with the append-only trigger

**What goes wrong:**
`operations_no_update`/`operations_no_delete` (`app/db.py`) ABORT any UPDATE/DELETE at the SQLite trigger level — this is a deliberate, hard architectural guarantee, and any new cash table should copy it verbatim (Pitfall 1). But that means an operator who fat-fingers a withdrawal amount (e.g. types 5000 instead of 500) has **no way to fix it** unless the UI explicitly supports adding a compensating entry. If the shipped UI only exposes the three named debit categories from the requirements (supplier payment / salary / other) with no way to add a manual credit, the operator is stuck with a permanently wrong balance and no recourse except a raw SQL edit — which defeats the entire point of an immutable, trustworthy ledger.

**Why it happens:**
The stock side already solved this with a dedicated `correction` operation type (Phase 5) precisely because "the recorded number is wrong and needs fixing without editing history" is a known, expected need — but the v1.3 requirements as scoped don't mention an equivalent "cash correction" category, likely because the milestone description focuses on the two headline flows (auto-credit, manual debit) and doesn't explicitly call out reversals.

**How to avoid:**
Ship a manual-credit path (see Pitfall 7) with a "Корректировка" category from day one, so a wrong entry is always fixable by adding an offsetting movement with a note explaining why — never by editing/deleting the original row. Document this in the UI itself (e.g. helper text near the balance: "Ошибку нельзя удалить — добавьте корректирующую запись").

**Warning signs:**
Any support/debug request that ends in "can we just edit that row in the database" is a sign this path is missing in the UI.

**Phase to address:**
The manual-debit phase, same as Pitfall 7 (they're the same underlying gap: debit-only UI).

---

### Pitfall 9: UI conflates "cash balance" with "profit"/"revenue," and goods-receipt cost isn't auto-linked to a cash debit

**What goes wrong:**
Two distinct confusions:
1. `reports.py` already computes sales/profit reports (RPT-01..04) from the same `operations` table. A business owner glancing at a big "баланс кассы" number on the new Финансы page can easily read it as "profit," when it actually also contains money that must be reserved to restock inventory (cost of goods) and is reduced by non-COGS expenses (salary) that never touch the profit report. Confusing available cash with profit is one of the most common small-business financial mistakes in general (external sources below) — U.S. Bank found most business failures trace to cash-flow mismanagement, not unprofitability, and it stems exactly from this "I have money in the account, so I must be doing fine" confusion. This app now has two overlapping-but-different money views (Отчёты profit/revenue vs. Финансы cash balance) that must be labeled unambiguously or the owner will misread one for the other.
2. `receipts.py` (goods intake) records `unit_cost_cents` for stock but has zero connection to cash — the v1.3 spec treats "оплата заказа поставщику" as a manual withdrawal category, entirely decoupled from recording the receipt itself. This is intentional per the requirements, but if undocumented in the UI, an operator's natural mental model ("I sold something → cash went up automatically; I bought stock → shouldn't cash go down automatically too?") will be violated silently, leading them to either forget to record the manual payment (balance overstated) or worry the app is missing a feature.

**Why it happens:**
The milestone deliberately scopes cash tracking as an *aggregate* module bolted onto an existing product-centric app, not a full accounting/AP system — so the natural symmetry a user expects (every stock-affecting money event has a cash-affecting counterpart) is only half-built by design (sale → auto; receipt → manual, and only if the operator remembers).

**How to avoid:**
Label the Финансы balance explicitly as cash-on-hand ("Наличные в кассе"), distinct from the existing Отчёты "Выручка"/"Прибыль" labels, and consider a short explanatory line or link between the two pages. Add a one-line note on the receipt form near the cost field, or on the Финансы manual-debit form, clarifying that recording a receipt does NOT withdraw cash automatically — the operator must record a separate withdrawal if they paid at receipt time.

**Warning signs:**
User-facing copy that uses "баланс"/"касса"/"выручка"/"прибыль" interchangeably; support questions like "why doesn't my cash match my profit report."

**Phase to address:**
UI/history-and-balance-display phase (whichever phase builds the Финансы page and its copy) — this is a labeling/documentation fix, cheap to do right the first time, expensive to retrofit once the owner has already formed a wrong mental model.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|--------------------|-----------------|------------------|
| Cache the balance as a plain column updated by application-code `+=` instead of a SQL-side atomic increment | Slightly less code to write initially | Balance drift under any concurrent/retried write, no audit trail to explain drift (same failure mode the ledger-vs-standalone-balance-field research above warns against) | Never — the SQL-side-increment-in-same-transaction pattern already exists in `ledger.py`; copying it costs nothing extra |
| Skip the "opening balance" / manual-credit UI and ship debit-only for v1.3 | Matches the literal milestone wording faster | Every operator whose real cash box has starting money gets a false negative-balance warning on day one, and any mistyped debit is permanently unfixable | Only acceptable if explicitly flagged to the user as a known v1.3 gap and fast-followed — not silently deferred |
| Store the cash-movement "reason" as unconstrained free text only (no category allow-list) | Faster form to build | Loses the reportability the `WRITEOFF_REASONS` pattern already proved valuable (filterable categories in `/history`) — a future "expenses by category" report becomes a text-parsing problem | Never, given the app already has a working allow-list + "other" free-text pattern one file away (`writeoffs.py`) to copy |
| Skip a `rebuild_cash_balance()`/recompute-from-ledger repair function | Saves one function in the first phase | No way to detect or repair drift if a bug is ever found, unlike stock which has `rebuild_stock()` as a safety net | Acceptable only if the balance is never cached (computed live via SUM every read) — then there's nothing to rebuild |

## Integration Gotchas

Mistakes when wiring the new Финансы module into the existing sales/returns/receipts/reports code, not external services (this app has none — fully local/offline).

| Integration point | Common Mistake | Correct Approach |
|--------------------|-----------------|-------------------|
| `sales.py` (`register_sale`) | Wiring the cash credit as a second, separate `session.commit()` after the sale operations commit | Stage the cash-credit write inside the SAME try/commit block as the sale operations (WR-03 pattern: one commit closes the whole transaction) |
| `returns.py` (`register_return`) | Forgetting to add the symmetric debit at all (Pitfall 2), or computing it by looking up/matching the original credit (Pitfall 3) | Compute the debit independently from `qty_returned * origin.unit_price_cents`, write it in the same transaction as the `return` op |
| `writeoffs.py` / `corrections.py` / `transfers.py` | Assuming these need cash wiring too, since they're stock-affecting operation types | Per v1.3 scope, only `sale` (credit) and `return` (debit) touch cash automatically — write-off/correction/transfer are stock-only and must NOT silently create cash movements |
| `receipts.py` | Assuming goods receipt should auto-debit cash for the cost (natural symmetry expectation) | Per v1.3 scope this is explicitly a MANUAL category ("оплата заказа поставщику") — do not auto-wire it; document the gap in UI (Pitfall 9) |
| `reports.py` | Extending existing profit/revenue report queries to also sum cash movements from the operations table | Cash movements live in their own table (Pitfall 1) — a "Финансы" report is a separate query/page, not a modification to the existing `Operation.type == "sale"` filters |
| `/history` view (`operations.py`, `OPERATION_TYPE_LABELS`) | Trying to merge cash movements into the same history list/pagination as stock operations | Give Финансы its own history view (mirrors the existing `LIST-01..03` pagination/filter/sort pattern from `pagination.py`, applied to the new table) rather than injecting rows into the stock ledger's `/history` |
| CSV export (`export.py`, BCK-02) | Silently omitting cash movements from the existing three-file export, or bolting them onto an existing CSV without the same BOM/`;`-delimiter/formula-injection-escape treatment | If cash export is in scope, reuse the exact same CSV-safety convention (BOM-once, `;` delimiter, apostrophe-escape of formula-injection prefixes) already proven in `export.py`; if out of scope for v1.3, say so explicitly rather than leaving it ambiguous |

## Performance Traps

Low risk at this project's actual scale (one operator, local SQLite, hundreds to low thousands of cash rows/year), but worth naming so the design doesn't accidentally block growth.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Recomputing `SUM(amount_cents)` on every page load with no index | Финансы page feels slightly slower to load over years of accumulated rows | Index on the movement table's `created_at` (for period filters) — mirrors existing `Operation.product_id`/`created_at` indexing choices | Not before tens of thousands of rows on SQLite; unlikely to matter for a single-store operator within the app's realistic lifetime |
| Financial history page with no pagination | Page becomes slow/unwieldy after a year or two of daily movements | Reuse `app/services/pagination.py`, the same helper already applied uniformly to all six existing list pages (Phase 14, LIST-01..03) | Same threshold as the existing `/history` and `dictionary` pages that already needed it (thousands of rows) |

## Security Mistakes

This is a local, offline, single-operator app with no auth — "security" here means protecting the integrity guarantees the app already relies on, not network/auth hardening.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Adding an admin/debug route that directly UPDATEs a cash balance or movement row "just for fixing mistakes" | Defeats the append-only guarantee the whole ledger design (and this feature's trustworthiness) depends on; also would silently succeed only until the trigger is copied onto this table (Pitfall 1), then fail confusingly | Never add such a route; use compensating entries (Pitfall 8) instead, exactly like the rest of the app has no "edit a past sale" backdoor |
| Free-text reason/note field rendered unescaped anywhere (UI or future CSV export) | Reflected-content or formula-injection risk if ever exported to Excel/CSV, mirroring the exact risk the existing export already had to solve | Reuse the existing Jinja2 autoescape + CSV apostrophe-escape conventions already proven in `export.py`/templates — don't build a new unescaped path for this one feature |
| Trusting a client-submitted amount/category without server-side re-validation | A crafted form POST could submit a category not in the allow-list, or a negative "credit" amount used to secretly debit | Validate category against a server-side allow-list (mirror `WRITEOFF_REASONS`) and validate amount sign/positivity server-side, exactly like `sales.py` re-validates price sign (D-10/WR-04) rather than trusting the form |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|--------------|-------------------|
| Labeling the Финансы balance ambiguously (just "Баланс") next to the existing profit/revenue reports | Owner conflates cash-on-hand with profit, may over-withdraw believing all of it is profit (Pitfall 9) | Explicit label "Наличные в кассе" distinct from "Выручка"/"Прибыль", short explanatory copy or cross-link |
| Debit-only manual movement form (matches literal requirements wording) | No way to seed an opening balance or fix a mistake (Pitfall 7/8) | Bidirectional form (credit + debit) with a "Корректировка"/"Внесение" category from day one |
| Hard-blocking negative balance | Breaks the app's own established warn-and-override precedent (oversell, min-price), traps the operator in a state they can't record | Warn-with-`confirm=1`-override, identical to the existing oversell/min-price pattern (Pitfall 6) |
| No visible link between a sale's cash-in and the sale itself in the movement history | Owner sees a growing list of anonymous "приход" rows and can't tell which sale generated which credit, especially once returns start appearing as separate debit rows | Show the linked sale (customer/products) inline in the Финансы history row, reusing the existing `sale_id` FK, the same way `/history` already resolves op → product/batch context |
| Receipt form silent about cash (Pitfall 9) | Operator forgets to record the manual supplier-payment withdrawal, balance silently overstated | One-line note on the receipt form near the cost field pointing to the manual withdrawal flow |

## "Looks Done But Isn't" Checklist

- [ ] **Auto-credit on sale:** Often missing the symmetric debit on return — verify `returns.py`'s `register_return` writes a cash debit in the same transaction as the `return` op, computed independently (not matched against the original credit).
- [ ] **Current balance display:** Often backed by a cached field with no recompute-from-ledger safety net — verify a `compute_cash_balance()` (mirroring `compute_stock()`) exists and, if a cache is used, a `rebuild_cash_balance()` (mirroring `rebuild_stock()`) exists too.
- [ ] **Manual withdrawal reason:** Often free-text only, or category-only with no escape hatch — verify it mirrors `WRITEOFF_REASONS`: a server-validated category allow-list plus an optional free-text note, with "прочее" as the escape hatch.
- [ ] **Negative-balance handling:** Often either silently allowed with no warning or hard-blocked — verify it follows the existing warn-with-`confirm=1`-override pattern used by oversell/min-price.
- [ ] **Opening balance:** Often entirely absent — verify there's a way to record a starting/adjustment cash-in that isn't tied to a fake sale.
- [ ] **Audit fields on cash movements:** Often reinvented ad hoc — verify the new table reuses `created_by`/`device_id`/`seq`/`synced_at` exactly like `Operation`, not a bespoke "operator" text field, so v2 multi-operator sync doesn't require a schema rewrite.
- [ ] **Финансы history view:** Often built without pagination/filter/sort — verify it reuses `app/services/pagination.py`, matching every other list page (LIST-01..03).
- [ ] **Reports/CSV export scope:** Often silently left out — verify whether cash movements are (or explicitly are not) part of the existing profit reports and the three-file CSV export (BCK-02), and that this is a stated decision, not an oversight.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|----------------|-----------------|
| Cash reused the `operations` table (Pitfall 1) | HIGH | Requires a new migration to split cash rows into a dedicated table, backfilling from the polluted `operations` rows, and auditing every `reports.py` query that filters `Operation.type` to confirm no cash rows leaked into profit/revenue sums |
| Return didn't debit cash (Pitfall 2) | LOW–MEDIUM | Because the ledger is append-only, recovery is itself a compensating entry: a one-time backfill script that finds every `return` op lacking a matching cash debit and inserts the missing debit rows (never edits existing ones) |
| Duplicate cash credit from a double-submitted sale (Pitfall 5) | LOW | Insert a compensating manual debit with a "Корректировка" category and a note referencing the duplicate sale/op id — same recovery mechanism as Pitfall 8, no special tooling needed if the bidirectional manual-movement form (Pitfall 7) was built |
| Balance drifted from a non-atomic cache update (Pitfall 4) | LOW (if `rebuild_cash_balance()` exists) / MEDIUM (if it doesn't) | With the recompute function: call it to snap the cache back to `SUM(cash_movements.amount_cents)`. Without it: write the function first, then run it — same shape as the existing `rebuild_stock()` repair path |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|--------------------|----------------|
| 1. Cash bolted onto `operations` table | Schema/foundation phase | New migration creates a dedicated `cash_movements` table (or equivalent) with its own immutability triggers; `OPERATION_TYPES` unchanged; no new `NOT NULL` relaxation on `Operation.product_id` |
| 2. Return doesn't debit cash | Same schema/foundation phase (ship credit + debit together) | Test: sell → fully return → assert balance returns to pre-sale value |
| 3. Return "matches" against original credit | Same schema/foundation phase | Code review: return-debit computation reads only from the `return` op's own frozen price/qty, never queries prior cash movements |
| 4. Cache/balance drift | Same schema/foundation phase | Either no cache (live SUM), or a `rebuild_cash_balance()` exists and is exercised by a test that intentionally desyncs and repairs the cache |
| 5. No idempotency guard | Schema/foundation phase (UI guard) + explicit Future/Out-of-Scope note if full fix deferred | Submit button disabled during HTMX request; PROJECT.md/roadmap explicitly notes duplicate-basket detection as a known gap if not fully solved |
| 6. Negative-balance validation inconsistency | Manual-debit phase | Withdrawal form returns a warning + `confirm=1` override on negative-balance, verified against the same test shape as existing oversell tests |
| 7. No opening balance | Manual-debit phase | Manual movement form supports a credit direction with an "opening/adjustment" category, not debit-only |
| 8. No correction path for manual entries | Manual-debit phase (same as 7 — same underlying gap) | UI copy explicitly tells the operator to add a compensating entry rather than edit/delete; no admin route exists that UPDATEs a movement row |
| 9. Balance/profit conflation + receipt-cash expectation gap | UI/history-and-balance-display phase | Финансы page copy uses "Наличные в кассе" (not "Прибыль"/"Выручка"); receipt form has a note about manual supplier-payment withdrawal |

## Sources

- `app/services/ledger.py`, `sales.py`, `returns.py`, `writeoffs.py`, `receipts.py`, `reports.py`, `db.py`, `models.py` (this repository) — direct code reading, HIGH confidence, primary grounding for all architecture-specific pitfalls
- `.planning/PROJECT.md` — milestone scope, requirements, and prior Key Decisions (D-XX/WR-XX conventions), HIGH confidence
- [The Idempotent Ledger: Solving the Duplicate Event Problem in High-Throughput Financial Systems](https://medium.com/@adeyemi_malik/the-idempotent-ledger-solving-the-duplicate-event-problem-in-high-throughput-financial-systems-e41dfa390f25) — general idempotency/duplicate-write pitfalls in ledger design, MEDIUM confidence (practitioner blog, cross-checked against this app's own WAL/`operations_no_update` design)
- [Formance — What Is a Ledger? A Guide for Software Engineers](https://www.formance.com/blog/financial-operations/what-is-a-ledger) — "storing a running balance as a standalone field is error-prone" finding used in Pitfall 4, MEDIUM confidence
- [Accu-Tax — Cash Flow vs. Profit: The Mistake That Sinks Small Businesses](https://www.accutaxinc.net/cash-flow-vs-profit-the-mistake-that-sinks-small-businesses/) — small-business cash-vs-profit confusion pattern used in Pitfall 9, MEDIUM confidence
- [GrowthForce — Why Profits Don't Equal Cash Flow](https://www.growthforce.com/blog/why-profits-dont-equal-cash-flow) — corroborating source for Pitfall 9, MEDIUM confidence

---
*Pitfalls research for: Adding a Касса (cash-balance) module to MyOriShop's existing warehouse/sales app*
*Researched: 2026-07-14*
