# Feature Research

**Domain:** Small-business warehouse inventory + cash accounting (single operator, append-only ledger, offline-capable local client + central sync server)
**Researched:** 2026-09-04
**Confidence:** HIGH for reversal and two-date conventions (primary vendor docs: Microsoft Business Central, SAP, Odoo, Xero, ERPNext); HIGH for the code-state findings (read from this repo); MEDIUM for mobile-edit specifics (practitioner guidance, no single authority)

---

## ⚠️ Read this first: the currency phase is largely already shipped

`.planning/ROADMAP.md:327-350` (Phase 999.1) and `.planning/OPEN-WORK-AUDIT-2026-09-04.md:65-79` both describe per-warehouse currency as unstarted, quoting a code survey done **2026-08-09**. That survey was overtaken the next day. Verified by reading the current code:

| Backlog claim (stale) | Actual state (verified 2026-09-04) |
|---|---|
| "`Warehouse.currency` needs to be added" | `app/models.py:214-220` — shipped, `String(3)`, `DEFAULT_CURRENCY` server default, migration `0023_warehouse_currency.py` |
| "`reports.py` / `dashboard.py` / `finance.py` contain zero `warehouse`" | `app/services/reports.py:21-38` — `operation_currency_clause()` exists as a documented LOCKED decision; `sales_profit_report(..., currency=DEFAULT_CURRENCY)` at `:41-46` |
| "`format_cents` renders `12,50` with no currency symbol anywhere" | `app/core.py:56-86` — `CURRENCIES` (RUB ₽ / UAH ₴ / EUR €), `currency_symbol()`, `format_money(cents, currency)` all shipped; `format_cents` deliberately kept as the bare-number filter |
| "a basket can mix warehouses → would mix currencies; mixing must be blocked" | `register_sale` rejects a mixed-currency basket with a Russian message and **zero writes** (quick task `260810-2g3`, commit `faff73d`) |
| "`needs verification`: new-schema client pushing to an old-schema server" | Closed — commit `669b4ff`, "sync fails loudly against an under-migrated server DB" |

Source of truth: `.planning/quick/260810-2g3-currency-correctness-part-2-per-currency/260810-2g3-SUMMARY.md` (status `complete`, 11 commits, 45 files, +1627/−197, `__version__` 1.17 → 1.28, 2026-08-10) plus part 1 at commit `cdcec66`. Migrations `0023`, `0024` (`cash_movements.currency`), `0025` (`batches.cost_cents`), `0026` (append-only trigger guard for the new column) are all on disk.

**Implication for the milestone:** currency is not a phase-sized feature any more. What remains is a *coverage and verification* tail (itemised in section C below), which is roughly one plan, not one phase. This should be settled before requirements are written, or the milestone will re-specify shipped behaviour. The four-phase order in `PROJECT.md:41-46` was built on the stale picture.

Back-dated operations and reversal are genuinely unbuilt: a repo-wide search for `business_date|occurred_at|storno|сторно|reversal|reversed_operation_id` returns **zero hits in `app/`** — only planning documents.

---

## Feature Landscape

### A. Reversal / storno

#### What the established convention actually is

Three distinct operations, which every mature system keeps distinct and which the operator must not be asked to distinguish by choosing the right tool:

| Operation | Definition | What the ledger looks like afterwards | Where it is used |
|---|---|---|---|
| **Reversal (сторно)** | A new entry, equal and opposite to the original. Business Central: *"A reverse entry is the same as the original entry, but has an opposite sign in the Amount field."* | Two rows, netting to zero, both permanently visible, linked | The whole entry was a mistake |
| **Correction** | A new entry that moves the value to what it should have been (partial, different amount) | Two rows, netting to the correct value | The entry was right in kind, wrong in amount |
| **Void** | The record is kept but its amount is forced to zero | One row, zeroed, still listed | Systems without an append-only ledger (QuickBooks) |
| **Deletion** | The row is removed | Nothing — the row survives only in a separate audit log | Universally discouraged; impossible here (DB triggers ABORT UPDATE/DELETE) |

The Russian convention the operator already knows is **«красное сторно»**: the compensating entry carries the same accounts with a negative (historically red-ink) amount, posted in the current period. That maps exactly onto this project's append-only ledger — same operation type, negative `qty_delta`.

Guards that real systems enforce, and what each is for:

- **Reverse once, never a reversal of a reversal.** Business Central: *"An entry can only be reversed one time."*
- **Whole document only.** SAP `FB08` and BC's `Reverse Transaction` both operate on the entire document; partial undo is a correction, a different transaction.
- **Availability check before the write.** SYSPRO on job receipts: *"the basic principle which applies when reversing a job receipt is that the stock must be available in the warehouse."* SAP S/4 goods-receipt reversal fails when the stock has been issued or sold. BC's `Undo Receipt` is blocked once the quantity is invoiced/consumed. The system does **not** unwind the downstream transactions to make room — it refuses and tells the user to reverse the downstream document first (SAP: put the sales-order line back in backorder).
- **Reason code.** SAP requires a reversal reason, and the reason additionally governs whether an alternative posting date may be used. Odoo's credit-note wizard has a **Reason** field and a **Reversal date** field.
- **Permission gate + explicit confirmation.** BC: choose `Reverse`, then *"Choose Yes to confirm the reversal."*
- **Period lock.** SAP/Odoo/Xero refuse a reversal into a closed period. This exists to protect filed accounts — see anti-features.

What a *bad* implementation looks like, from a system that got it wrong: ERPNext `Cancel` sets `docstatus=2` and flips `is_cancelled=1` on the original entries rather than posting a compensating entry. Open issues [#11130] and [#47652] argue this is unacceptable once books are closed, and [#30547] complains that the reverse entry lands on the *original* date rather than the cancellation date. The project's append-only ledger already forecloses this failure mode — keep it that way.

#### Table stakes

| # | Feature | Why the operator will consider it broken without it | Complexity | Notes / dependency |
|---|---|---|---|---|
| R1 | A reversal control on each reversible row of История (desktop **and** mobile), reaching a confirmation step that states in words what will be written before anything happens | "One tap" without a preview is how a mis-tap becomes a second wrong operation. BC forces an explicit Yes | LOW | Depends on: История is currently display-only (`app/routes/history.py:84`, `history.html` renders no action controls) |
| R2 | The reversal is a **new compensating row** written through `record_operation` / `record_cash_movement`; the original is never edited or deleted | Non-negotiable project invariant (DB triggers ABORT UPDATE); also the audit convention | LOW | Reuses the sole sanctioned write path |
| R3 | Whole-operation, all-or-nothing. A composite operation reverses as one unit in one transaction — a transfer writes 2 ledger rows and both must go, a sale writes N rows + a cash movement | Half-reversed transfer = corrupted stock in two warehouses | MEDIUM | `record_operation(commit=False)` + one `session.commit()` is the shipped pattern (WR-03, `ledger.py:56-60`) |
| R4 | A **stored** link from the compensating row to the reversed row, rendered on both: the original gets a «сторнировано» badge and stops offering the control; the storno row reads «Сторно операции от 13.08 — приход 5 шт» and links back | Two unlabelled opposite rows in История is exactly today's problem restated. The whole point is that the relationship is stated | LOW–MEDIUM | `Operation.payload` (JSON, `models.py:374`) could hold it, but a dedicated nullable column mirroring `sale_id`/`batch_id` is queryable and is what the once-only guard needs to check cheaply. `CashMovement` has **no** payload column at all → needs a real column |
| R5 | Reverse-once guard, and a storno row can never itself be reversed | Two stornos of one receipt = phantom stock. BC's explicit rule | LOW | Needs the R4 link to be indexed/queryable |
| R6 | Availability guard with a specific, actionable Russian message and **zero writes** on refusal: «Нельзя сторнировать: из партии уже продано 3 шт, осталось 2 из 5» + what to do instead | Reversing a receipt whose stock has been sold would drive the batch negative and silently corrupt every valuation. Every ERP refuses this | MEDIUM | Exact precedent already in the codebase: `returns.py` computes `returnable_qty` and refuses *before any write* (`returns.py:140-146`), with RU messages |
| R7 | The compensating row nets to zero in every existing report **without any report being changed** — same operation `type`, opposite `qty_delta`, same frozen `unit_cost_cents`/`unit_price_cents` | If reversal needs each report to learn about it, "one tap" becomes a cross-cutting rewrite and one forgotten report double-counts forever | LOW (design choice, not code) | `SUM(qty_delta)` and every money sum net automatically. `needs verification`: any report that `COUNT`s operations rather than summing them would count the storno as a second event — audit `reports.py`, `dashboard.py`, `finance_reports.py` for COUNT/len usage |
| R8 | Cash movements are reversible at all | Today `app/routes/finance.py` exposes only `/finance/withdraw` and `/finance/deposit` — a mistyped deposit has no undo whatsoever. Worst case in the audit | LOW–MEDIUM | Opposite-signed movement, **same currency**, same category, linked. Needs a new column on `cash_movements` **and** that column added to the append-only trigger's column enumeration — migration `0026` exists precisely because this was missed once |
| R9 | Reversal is available to the `operator` role, not administrator-only | The operator is the person who makes the typos. An admin-only undo in a one-person shop means no undo | LOW | Roles shipped v3.0 |
| R10 | Reversing a cash movement may drive the balance negative — reuse the **existing** warn-but-allow gate (FIN-05), do not invent a second rule | Two different negative-balance behaviours in one app is a bug report waiting | LOW | Existing feature |

#### Differentiators

| # | Feature | Value proposition | Complexity | Notes |
|---|---|---|---|---|
| R11 | «Сторно и повторить» — after reversing, re-open the original entry form pre-filled with the original values so the corrected version can be re-entered immediately | This is the actual workflow ("I typed 15 instead of 5"). Odoo ships it as *Reverse and create invoice*; BC documents undo-then-redo as the standard sequence | MEDIUM | Pre-fill only; no coupling between the two writes |
| R12 | An undo affordance on the **just-written** operation — an «Отменить» link in the success message right after saving, for a short window | Catches the majority of mistakes with zero navigation into История. МойСклад uses exactly this (a green bar with an inline restore after deletion) | LOW | Same service call as R1; purely an extra entry point |
| R13 | Optional free-text reversal reason, stored and displayed on the storno row | SAP makes it mandatory; for one operator it is a note-to-self ("ошибся в количестве") that makes История readable in a month | LOW | Store in `payload` for operations |
| R14 | A «сторнированные» filter/marker on История | Lets the operator find their own corrections; helps when reconciling a physical count | LOW | Rides on the shipped HIST-02 filter machinery |

#### Anti-features

| # | Feature | Why requested | Why problematic | Alternative |
|---|---|---|---|---|
| R15 | Delete / hard-delete an operation | "It was never real, remove it" | Breaks the append-only invariant, breaks the UUID-keyed sync replay (a deleted row still exists on other devices), destroys the audit trail. QuickBooks keeps deleted transactions in the audit log for exactly this reason; ERPNext's mutate-the-original cancel is the design its own community files bugs against | Reversal (R1–R7) |
| R16 | Edit a posted operation in place | "Just fix the number" | DB triggers ABORT UPDATE; would also require rewriting the sync payload of an already-synced row | Reversal, then re-enter (R11) |
| R17 | Reversal time window / period lock / closed periods | Every ERP has one | Their purpose is protecting filed statutory accounts and an accountant's month-end close. Neither exists here. It would only ever manifest as the operator being locked out of fixing their own data, with no one able to unlock it. Xero's own known weakness is that anyone with settings access can move the lock date anyway, with no history | No time limit. R5 (once-only) + R6 (availability) are the real guards |
| R18 | Automatic cascading reversal of downstream operations | "Just undo everything that depended on it" | This is how systems corrupt stock — SAP explicitly makes the user restore availability manually first. Auto-unwinding an arbitrary chain in an append-only ledger is unbounded work with no safe stopping point | Refuse with the specific R6 message naming the blocking operation |
| R19 | A new `"storno"` entry in `OPERATION_TYPES` | Seems tidier than a negative row | Every report, every История type filter, the CSV export, the mobile per-type columns, and `merge.KIND_TO_FIELDS` would all have to learn a 10th type; anything that forgets it silently drops or double-counts stornos | Same type + negative `qty_delta` + a link column (R7) |
| R20 | Reversing a **sale** through the new storno mechanism | Symmetry — "reverse anything" | Returns already do this: capped by `returnable_qty`, linked via `sale_id`, price/cost copied frozen from the origin op, cash auto-debited symmetrically. A second undo path for sales is the "second mechanism for a job the project already solves" trap | See the open question below — this needs an operator decision, not a default |

**Open question for requirements (flag):** a mis-entered sale is *not* a return. Routing it through `register_return` gives arithmetically correct stock and cash, but it pollutes the returns report, the customer's purchase stats and the «Возврат» cash category with an event that never happened. Three options: (a) storno excludes sales, operator uses Возврат — cheapest, wrong data; (b) storno on a sale row routes into the existing return flow but tags the row as a correction so reports can exclude it — medium; (c) sales get a real storno writing negative `sale` ops + a negative `return`-category cash row — most correct, most work. Decide before writing REQ-IDs.

---

### B. Business date vs. technical timestamp

#### The standard model

Mature systems carry **three** dates and this project needs **two**:

| Date | Meaning | Who reads it |
|---|---|---|
| **Document date** | When the paper/event is dated | Due-date and payment-term calculations |
| **Posting date** | Which accounting period the entry lands in | **Every ledger report.** In Business Central the posting date is what writes G/L, Customer and *Item Ledger* entries; the document date only drives invoice due dates |
| **Entry timestamp** | When the row was physically created | Audit trail, immutable |

The bitemporal framing of the same thing: **valid time** (when it was true in the world) versus **transaction time** (when the system learned it). A back-dated entry has `valid_from` in the past and `created_at` now; the pair is what makes the record auditable.

How far back you may date is governed by lock dates, not by the field itself. Xero: once a lock date is set, users *"cannot add, change, or delete transactions with dates prior to or on the lock date."* Odoo has a tiered version (non-advisers / all users / tax) and silently rolls a confirmed draft forward to the first day after the lock date. Business Central calls it allowed posting dates.

**What goes wrong with only one date — the app's current condition:** a sale made yesterday and entered today lands in today's bucket, and every period-scoped surface (finance report, dashboard, cash flow, sales profit) inherits the drift. There is no way to reconstruct the truth afterwards, because the information was never captured.

**What goes wrong when back-dating is added carelessly** — worth stating because it is the single most-reported pain in Odoo/D365 forums: with FIFO/weighted-average costing, a back-dated receipt disrupts the chronological cost layers, forcing retroactive recalculation of every subsequent transaction's COGS. **This project is structurally immune and must stay that way:** batch selection is manual (automatic FEFO/FIFO is explicitly Out of Scope in `PROJECT.md:230`) and cost/price are frozen per operation row at write time. Nobody should later "improve" this into date-ordered costing.

#### Table stakes

| # | Feature | Why the operator will consider it broken without it | Complexity | Notes / dependency |
|---|---|---|---|---|
| D1 | Every operation-writing form — receipt, sale, write-off, correction, transfer, cash withdraw/deposit — has a date field defaulting to today, and leaving it untouched behaves exactly as today | Default-and-forget is the entire ergonomic premise; a required date on every form would slow down the common case | LOW per form, MEDIUM across 6 desktop forms + 5 mobile wizards | `record_operation` (`ledger.py:37-49`) takes no date argument today; same for `record_cash_movement` (`finance.py:48`) |
| D2 | **Every** period-scoped surface switches to the business date in the same phase: `sales_profit_report`, `writeoff_report`, `top_selling_products`, the dashboard's day/week/month tiles, `cash_flow_report`, `cash_expense_total`, `cash_history_view`, the История date filter, and both CSV exports | A half-migrated set of readers is strictly worse than today's consistent drift: the dashboard and the report would show different numbers for the same week, and the operator has no way to know which is right | MEDIUM–HIGH (breadth) | The shipped single shared period-filter + local-day-boundary helper (a v1.0 Key Decision) is the leverage point — change it once |
| D3 | The technical timestamp is untouched: still the audit trail, still the sort order, still the sync cursor. История's default sort stays entry-order | Re-ordering the ledger by business date would let a back-dated row insert itself *behind* the sync cursor and be skipped forever. This is the project's own stated risk (`ROADMAP.md:385`) | LOW (a rule, if held) | `Operation.created_at` + `seq` + `synced_at` + `ix_operations_unsynced` are all load-bearing |
| D4 | When the two dates differ, История shows both — «операция 13.08, введено 15.08» — and the CSV export carries both columns | Otherwise a back-dated row is indistinguishable from a normal one, and the operator cannot audit their own corrections a month later | LOW | Depends on D1 |
| D5 | Future dates are rejected | The fat-finger year (2027 for 2026) would silently remove the operation from every report with no error anywhere | LOW | Same guard everywhere; one helper |
| D6 | Date granularity is a calendar day (`yyyy-mm-dd`), not a datetime | Reports already bucket by local day; a time-of-day picker on a phone is friction with no consumer | LOW | Matches the shipped `Batch.expiry` convention (`String(10)`, ISO, sorts lexicographically = chronologically) |
| D7 | A storno carries the **same business date as the operation it reverses**, while its own technical timestamp is now | This is what makes "fix yesterday's mistake" actually fix yesterday's report. BC's rule: *"The reverse entry must have the same document number and posting date as the original entry."* SAP's today-dated alternative exists only to protect closed periods, which do not exist here | LOW | **Hard dependency: business date must ship before storno** — confirms the phase order in `PROJECT.md:41-46` |

#### Differentiators

| # | Feature | Value proposition | Complexity | Notes |
|---|---|---|---|---|
| D8 | A soft warning past a threshold — «Дата на 45 дней назад. Всё верно?» — warn-but-allow | Catches typos without ever locking the operator out. Uses the app's own established warn-but-allow idiom (oversell, below-min-price, negative cash) | LOW | Threshold as a setting is scope creep; hardcode |
| D9 | «Остаток на дату» — point-in-time stock, replayed as `SUM(qty_delta)` filtered by business date | Only becomes computable once a business date exists; the real use is reconciling a physical count taken days ago against the book | MEDIUM | Would legitimately differ from the cached current quantity. **Own phase, not a rider** |
| D10 | An «задним числом» marker/filter on История | Lets the operator review what they back-dated during a catch-up session | LOW | Rides on shipped HIST-02 |
| D11 | The date field remembers the last value within a session | The realistic use is entering a stack of last week's paperwork in one sitting; re-typing the date each time is the friction that makes people give up | LOW | Session-scoped only |

#### Anti-features

| # | Feature | Why requested | Why problematic | Alternative |
|---|---|---|---|---|
| D12 | Lock dates / closed periods / allowed-posting-date settings | Every accounting product has them | They protect a month-end close and filed accounts. There is no accountant, no close and no statutory filing here. The only observable effect would be locking the operator out of their own data, and (per Xero's own caveat) they can move the lock date anyway with no record | D5 (no future dates) + D8 (soft warning) |
| D13 | Separate document date **and** posting date | "That's how ERPs do it" | The second date has no consumer: no invoices, no payment terms, no due dates, no fiscal calendar | One business date |
| D14 | Letting the operator-supplied date overwrite `created_at` | "Simpler — one column" | Destroys the audit trail and the sync cursor simultaneously. Named as the top risk in the project's own backlog note | Separate column (D3) |
| D15 | Retroactive re-costing when a receipt is back-dated | "The valuation should be as of that date" | The classic backdating failure in FIFO systems. Does not apply here and must not be introduced — manual batch selection + per-row frozen cost is what keeps back-dating cheap and safe | Leave costing untouched; the business date affects **reporting periods only**, never stock arithmetic |
| D16 | Re-ordering the ledger by business date | "History should read chronologically" | `seq`/`created_at`/`synced_at` ordering is load-bearing for merge replay | Sort by entry order; *display* the business date (D4); optionally offer business-date sort as a view-only option |
| D17 | Back-dating changing the current stock number | Seems to follow from "record it as of yesterday" | Current stock is a net sum, order-independent — a back-dated receipt correctly adds to stock now. If it *also* changed history retroactively, the cached projection and `recompute_derived`'s invariant would diverge | Current stock is unaffected by definition; point-in-time stock is a separate report (D9) |

---

### C. Per-warehouse currency — residual work only

Shipped 2026-08-10 (see the banner at the top). What is verifiably **done**: the `Warehouse.currency` / `CashMovement.currency` / `Batch.cost_cents` schema with RUB backfill; `operation_currency_clause()` with an **outer** join + `COALESCE` so legacy batch-less rows bucket as RUB instead of silently vanishing; currency-scoped `sales_profit_report`, `/finance` (balance, history, cash flow, expense total, stock valuation rewritten onto a `Batch`+`Warehouse` join) and the dashboard; currency switchers on Главная, `/reports/sales` and `/finance`; mixed-currency baskets rejected with zero writes; cross-currency transfers requiring a destination-currency cost; a «Валюта» column on the CSV exports; the append-only trigger extended to guard the new column; and sync failing loudly against an under-migrated server.

#### The design questions the milestone still has to answer

**How do you present money that must never be summed?** The systems that support this (Dynamics 365 financial reporting, Clarizen) do it the same way: a **mandatory currency filter that resolves to exactly one currency**, so aggregation across currencies is not expressible. D365: *"if you don't specify a currency filter, the system includes transactions in all currencies"* — which is precisely the failure to avoid. This project already implemented the correct form (`currency=DEFAULT_CURRENCY` default, never "all"). The remaining rule is **there must be no «все валюты» option anywhere**, and every standalone amount must carry its symbol.

**How is "you may not mix currencies in one document" surfaced at entry time rather than at submit time?** The established answer is that currency lives on the **document header**, and the line pickers are then filtered to match — you cannot construct the invalid state. Currently `register_sale` catches it at submit (correctly, with zero writes and a Russian message). The entry-time version: pick/derive the warehouse first, display «Склад: Офис · ₴ UAH» in the basket header, and have the batch picker only offer batches from currency-compatible warehouses, keeping the submit-time check as the backstop.

#### Remaining items

| # | Item | Category | Complexity | Notes |
|---|---|---|---|---|
| C1 | Currency-aware money render on the surfaces that still print a bare `12,50`: История, product cards, batch cards, receipt forms, the sale basket, write-off and correction screens — desktop and mobile | **Table stakes** once a second currency exists | MEDIUM (breadth) | Only 13 templates currently reference `currency`/`format_money`; `format_money()` already exists, so this is mechanical. `needs verification`: exact per-surface list — audit every `format_cents` call site in templates |
| C2 | Currency scoping for `writeoff_report`, and confirm `top_selling_products` / `stale_products` expose no cross-currency money total | **Table stakes** if they sum money | LOW–MEDIUM | Verified: `reports.py:127,186,212` take no `currency` argument. `needs verification`: whether `writeoff_report` sums money or only quantities |
| C3 | Warehouse/currency dimension on the История filters | Differentiator | MEDIUM | История has no warehouse dimension |
| C4 | Entry-time mixing prevention (warehouse on the basket header + filtered batch picker) | Differentiator (submit-time guard already correct) | MEDIUM | `services/sales.py` has no warehouse concept. `needs verification`: whether a rejected basket is preserved on re-render or lost |
| C5 | Human visual check in a real browser of the currency selects and the new money renders, desktop and mobile | **Table stakes** (verification, not code) | LOW | Explicitly listed as *"Not verified: visual rendering in Chrome"* in the quick-task summary; the 20 live-HTTP scenarios that did pass are not a substitute |
| C6 | Mobile parity for the currency switchers beyond `/m/finance` and the mobile home | **Table stakes** | LOW–MEDIUM | `needs verification` per mobile surface |

#### Anti-features

| # | Feature | Why requested | Why problematic | Alternative |
|---|---|---|---|---|
| C7 | FX rates / conversion / base-currency roll-up | "I want one total" | Drags in a rate table, rate-dated valuation, and realised/unrealised FX gain–loss. BC's own docs note that its reversal feature *cannot be used at all* when an additional reporting currency is configured, because amounts are converted but not netted — conversion breaks reversal, the other headline feature of this milestone | Side-by-side currencies, one filter, no total |
| C8 | An «все валюты» option in any currency filter | "Just show me everything" | Reintroduces exactly the aggregation the design forbids, in the one place the operator will trust | Per-currency views only |
| C9 | Per-product or per-batch currency independent of the warehouse | Flexibility | Lets a single warehouse hold two currencies, which re-opens mixing on every screen the mixing guard was just added to | Currency belongs to the location |
| C10 | Automatic conversion on cross-currency transfer | "The cost should carry over" | There is no rate to convert with, and the carried-over number would be silently wrong | Already correct: the operator retypes the cost in the destination currency; refuse with zero writes if absent |

---

### D. Mobile editing of product and customer cards

The context is a phone in a warehouse: one hand, possibly gloves, standing up. Practitioner guidance for warehouse mobile apps converges on large touch targets in consistent positions, high contrast, guided single-purpose steps rather than open forms, and **on-device inline validation** so an error is caught at the field instead of escalating into data cleanup later. Mobile form-validation guidance adds a specific timing rule: validate immediately when the user is *correcting* a field already flagged, but wait until they leave the field before flagging a first-time entry.

Current state, verified: `app/routes/mobile_products.py` exposes exactly one route (`GET /m/products`); the mobile product card template declares itself read-only in its own header comment; `app/routes/mobile_customers.py` likewise exposes only `GET /m/customers`. A customer can be *created* mid-sale (`mobile_sales.py:159` calls the shared `create_customer`) but never corrected.

#### Table stakes

| # | Feature | Why the operator will consider it broken without it | Complexity | Notes / dependency |
|---|---|---|---|---|
| M1 | Mobile edit of a product card covering the same fields as desktop — name, category, ДЦ cost, ПЦ sale, min sale price, low-stock threshold — or an explicitly stated subset, never a silently different one | A form that omits the field the operator came to fix reads as broken. These are exactly the fields `/products/{id}/edit` exposes (`products.py:262,281`) | MEDIUM | Depends on the C1 money render being final |
| M2 | Mobile edit of a customer card — name, surname, phones/contacts, consultant number | Same reasoning; creation already exists on mobile, correction does not | MEDIUM | Extended profile shipped v2.0 (CUST-01..08); multi-value contacts make the form non-trivial on a phone |
| M3 | Both reuse the **same services and the same validation and the same Russian error strings** as desktop — no second validation path | A divergent mobile path is how the same input gets accepted on one device and rejected on the other, then syncs | LOW (as a rule, if held) | Established project pattern (mobile flow reuses `register_sale` etc., a v1.1 Key Decision); the shipped `/m/batches/{id}/edit` from quick task `260813-i28` is the exact route-pair precedent to copy |
| M4 | Entry points from where the operator is already looking: the mobile product card and the customer list row | An edit route with no link into it is invisible. This project has already shipped a gap-closure plan (17-05) for exactly this failure | LOW | |
| M5 | Field-level inline errors next to the offending field, preserving every other value the operator typed | A full-form reset on a phone means retyping everything; this project already has a data-loss scar here (CR-01: the mobile receipt wizard silently discarded typed prices on a Назад→Далее round trip) | LOW–MEDIUM | |
| M6 | Explicit Save with a visible confirmation that the change persisted, plus Отмена/Назад returning to the card unchanged | Warehouse UX rule: generous, consistently placed confirmation areas. Silent success on a phone is indistinguishable from failure | LOW | |
| M7 | Correct input types: `inputmode="decimal"` for money, `type=date` for dates, a select for category | Free-text numeric entry on a phone keyboard is the highest-error path there is | LOW | Category select already exists on desktop (quick task `260721-f39`) |
| M8 | Guardrails behave identically to desktop — below-min-price warn-but-allow, the ДЦ/ПЦ colour cue against the catalog reference | A guardrail that only fires on desktop is worse than none | LOW | Falls out of M3 if services are shared |

#### Differentiators

| # | Feature | Value proposition | Complexity | Notes |
|---|---|---|---|---|
| M9 | Edit a price from inside the mobile sale/receipt wizard and return to the same step | The real trigger is noticing a wrong price *while* selling. Standing at the shelf and losing the basket to go fix a card is the actual pain | MEDIUM–HIGH | Wizard state preservation is exactly where CR-01 bit before. Do not take this on lightly |
| M10 | Price/edit history on the mobile card | The ledger already writes `price_change`, `product_created`, `product_edited` rows — this is a read | LOW | |
| M11 | Mobile CRUD parity beyond product/customer (warehouses, dictionary, full reports) | | MEDIUM–HIGH | Already deferred in `PROJECT.md:222` — keep it deferred |

#### Anti-features

| # | Feature | Why requested | Why problematic | Alternative |
|---|---|---|---|---|
| M12 | A mobile-only "lite" service or validation path | "The phone form is simpler" | Guarantees eventual divergence between what desktop and mobile accept, on a synced multi-device system | Shared service (M3) |
| M13 | Tap-to-edit inline on the list row without an explicit save | Feels fast | A mis-tap writes to a price field with no confirmation, and there is no undo for reference data | Explicit edit route + Save (M6) |
| M14 | Auto-save on blur / optimistic UI | "Fewer taps" | Offline-capable client + append-only ledger + sync = silent partial writes that surface as conflicts later | Explicit Save, single request |
| M15 | Delete a product or customer from the phone | Parity with desktop's quick-delete | A destructive control one mis-tap from Edit, on the device most prone to mis-taps, with no undo. Desktop's guarded quick-delete is reachable | Edit only on mobile — **confirm with the operator**, this is an opinionated cut |
| M16 | A parallel mobile template tree duplicating the desktop field list | Independence | Two field lists drift the first time a field is added | Shared parameterised partials — the `finance_base` pattern from Phase 17 |

---

## Feature Dependencies

```
Back-dated operations (B)
    ├──required-by──> One-tap reversal (A)
    │                  (D7: the storno must carry the ORIGINAL's business date;
    │                   building storno first means reworking every storno row later)
    ├──enables──────> «Остаток на дату» point-in-time stock (D9, separate phase)
    └──touches──────> record_operation + record_cash_movement + the append-only
                      trigger column enumeration + every period-scoped report

Currency residual (C)
    ├──required-by──> One-tap reversal (A)
    │                  (C1: История must render each amount with its currency
    │                   before a storno row's sum means anything)
    └──required-by──> Mobile editing (D)
                       (M1: the mobile edit form displays prices)

One-tap reversal (A)
    ├──reuses───────> returns.py  (cap-before-write, zero-writes-on-error, RU messages)
    ├──reuses───────> record_operation(commit=False) + single commit  (atomic multi-row)
    ├──reuses───────> the FIN-05 warn-but-allow negative-cash gate
    └──conflicts────> returns.py, for SALES only  (R20 open question)

Mobile editing (D)
    ├──reuses───────> the desktop product/customer services unchanged
    ├──copies───────> the /m/batches/{id}/edit route-pair precedent (quick 260813-i28)
    └──independent──> of (A) and (B)

Sync (shipped)
    └──absorbs──────> new columns automatically via merge.KIND_TO_FIELDS
                      (derived from model columns), with the loud
                      under-migrated-server failure already in place (669b4ff)
```

### Dependency notes

- **Storno requires the business date.** A compensating row that cannot carry the original's date either lands in the wrong period or forces a rework of every storno row when back-dating ships. This is a hard ordering constraint, not a preference — and it matches the project's own "schema before its readers" rule (v2.0 sequenced price consolidation ahead of every page that read the price shape).
- **Storno requires the currency render, not the currency schema.** The schema is done; what storno needs is C1 (История showing amounts with their symbol). That is a much smaller gate than the roadmap assumed.
- **Both new schema changes hit the append-only triggers.** The triggers enumerate columns; migration `0026` exists solely because `cash_movements.currency` was added without extending the guard. Every new column on `operations` or `cash_movements` in this milestone must extend the trigger in the same migration, or the column is silently unprotected.
- **`CashMovement` has no `payload` column.** Operations can stash a reversal link in `payload` (JSON, `models.py:374`); cash cannot. A real nullable column is needed either way for the once-only guard to be a cheap indexed lookup — mirror the `sale_id`/`batch_id` shape (bare native column in the migration, ORM `ForeignKey` in the model for insert ordering + PostgreSQL portability).
- **Storno conflicts with returns on sales only.** Receipts, write-offs, transfers and cash have no existing undo and no conflict. See the R20 open question.
- **Mobile editing depends only on the money render.** It can be sequenced last, or in parallel with storno if C1 lands first — it shares no files with the ledger work.

---

## MVP Definition

### Launch with (this milestone)

- [ ] **Business date on every operation-writing form**, defaulting to today, date-only, no future dates (D1, D5, D6) — the enabling schema change
- [ ] **Every period-scoped surface reads the business date**, in one pass (D2) — a partial migration is worse than none
- [ ] **The technical timestamp untouched** as audit trail, sort order and sync cursor (D3) — the non-negotiable constraint
- [ ] **Both dates visible in История and CSV when they differ** (D4)
- [ ] **Currency render coverage on the remaining money surfaces**, desktop + mobile (C1), plus the writeoff-report scoping check (C2) and the never-done human browser check (C5, C6)
- [ ] **One-tap reversal for receipts, write-offs, transfers and cash movements**, with confirmation preview, stored link both ways, reverse-once guard, availability guard with an actionable message and zero writes, atomic multi-row reversal, and the storno carrying the original's business date (R1–R10, D7)
- [ ] **Mobile edit route pairs for product and customer cards**, same services, inline errors, explicit save, entry points from card and list (M1–M8)

### Add after validation

- [ ] «Сторно и повторить» (R11) — once the operator has used plain storno and confirmed the re-entry step is the friction
- [ ] Undo link in the post-save success message (R12) — cheap, but only worth it after the История control proves the semantics
- [ ] Soft warning past a back-dating threshold (D8) — tune the threshold from real usage
- [ ] Optional reversal reason (R13) and the «сторнированные» / «задним числом» filters (R14, D10)
- [ ] Entry-time currency mixing prevention on the basket header (C4)

### Future consideration

- [ ] «Остаток на дату» point-in-time stock report (D9) — genuinely valuable, but a new report with its own replay semantics; its own phase
- [ ] Mobile edit-in-wizard (M9) — highest value of the mobile differentiators, highest risk (wizard state, prior CR-01 scar)
- [ ] Mobile CRUD parity for warehouses/dictionary/reports (M11) — already deferred in PROJECT.md
- [ ] История warehouse/currency filter dimension (C3)

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Business date field on every write form (D1) | HIGH | MEDIUM | P1 |
| All period surfaces read the business date (D2) | HIGH | MEDIUM–HIGH | P1 |
| Technical timestamp preserved (D3) | HIGH (correctness) | LOW | P1 |
| Both dates shown when they differ (D4) | MEDIUM | LOW | P1 |
| No future dates (D5) | MEDIUM | LOW | P1 |
| Storno control + confirmation preview (R1) | HIGH | LOW | P1 |
| Compensating row via the sanctioned write path (R2, R7) | HIGH (correctness) | LOW | P1 |
| Atomic whole-operation reversal (R3) | HIGH | MEDIUM | P1 |
| Stored bidirectional link, rendered both ways (R4) | HIGH | LOW–MEDIUM | P1 |
| Reverse-once guard (R5) | HIGH | LOW | P1 |
| Availability guard, zero writes, actionable message (R6) | HIGH | MEDIUM | P1 |
| Cash movement reversal (R8) | HIGH | LOW–MEDIUM | P1 |
| Storno inherits the original's business date (D7) | HIGH | LOW | P1 |
| Currency render on remaining surfaces (C1) | HIGH (with 2+ currencies) | MEDIUM | P1 |
| Writeoff-report currency scoping (C2) | MEDIUM | LOW–MEDIUM | P1 |
| Human browser verification of currency UI (C5, C6) | HIGH (unknown risk) | LOW | P1 |
| Mobile product edit (M1) | HIGH | MEDIUM | P1 |
| Mobile customer edit (M2) | MEDIUM–HIGH | MEDIUM | P1 |
| Shared services / inline errors / explicit save (M3, M5, M6, M7) | HIGH | LOW | P1 |
| Mobile entry points from card and list (M4) | HIGH | LOW | P1 |
| «Сторно и повторить» (R11) | HIGH | MEDIUM | P2 |
| Post-save undo link (R12) | MEDIUM–HIGH | LOW | P2 |
| Soft back-dating warning (D8) | MEDIUM | LOW | P2 |
| Reversal reason (R13) | LOW–MEDIUM | LOW | P2 |
| Entry-time currency mixing prevention (C4) | MEDIUM | MEDIUM | P2 |
| Storno / back-dated filters (R14, D10) | LOW–MEDIUM | LOW | P2 |
| Sticky date within a session (D11) | MEDIUM | LOW | P2 |
| «Остаток на дату» (D9) | MEDIUM–HIGH | MEDIUM–HIGH | P3 |
| Mobile edit-in-wizard (M9) | MEDIUM–HIGH | HIGH | P3 |
| Price history on the mobile card (M10) | LOW | LOW | P3 |
| История currency/warehouse filter (C3) | LOW–MEDIUM | MEDIUM | P3 |

---

## Competitor Feature Analysis

| Feature | Business Central | SAP / Odoo | ERPNext (the counter-example) | Our approach |
|---------|------------------|-----------|-------------------------------|--------------|
| Undo a posted entry | `Reverse Transaction` writes an opposite-signed entry; `Undo Receipt` inserts a corrective line under the original | SAP `FB08` posts a reversal document with a mandatory reason; Odoo issues a credit note ("the only legal method for cancelling a validated invoice") with Reason + Reversal date | `Cancel` sets `docstatus=2` and mutates the original entries; community open issues call for real reversing entries | Compensating row of the **same type** with opposite `qty_delta`, written through `record_operation`; original never touched |
| Reverse twice | Explicitly prevented — "an entry can only be reversed one time" | Reversal document cannot itself be reversed | Amend chains (`INV-0032-1`) | Reverse-once guard; a storno row is not reversible |
| Reversing consumed stock | `Undo Receipt` blocked once invoiced/consumed | SAP: reverse the downstream document first (put the SO line back in backorder) | — | Refuse with an actionable Russian message naming the shortfall; never auto-unwind |
| Reversal date | Same posting date as the original | SAP: today, or an alternative date if the reason permits; Odoo: user-chosen reversal date | Reverse entries land on the original date (filed as a bug) | Same business date as the original (BC's rule) — safe because there are no closed periods |
| Backdating control | Allowed posting date range | Odoo tiered lock dates; Xero lock dates | — | **No lock dates.** No future dates + a soft warning past a threshold |
| Which date reports use | Posting date drives G/L, Customer and Item Ledger entries | Same | — | Business date drives every period report; technical timestamp drives audit, sort and sync |
| Multi-currency reporting | Additional reporting currency, converted — and reversal is unsupported when it is on | Odoo/D365 convert to a base currency; D365 offers a currency filter that prevents row aggregation; Clarizen sums only within a selected currency | — | One currency per warehouse, **no conversion anywhere**, mandatory single-currency filter, no "all currencies" option |
| Delete a transaction | Not for posted entries | Not permitted | Permitted with linked-document blocks | Impossible — DB triggers ABORT UPDATE/DELETE |

---

## Sources

**Reversal / correction / void / delete**
- [Undo a posting using a reversing entry — Microsoft Business Central](https://learn.microsoft.com/en-us/dynamics365/business-central/finance-how-reverse-journal-posting) — reverse entry = same entry with opposite sign; same document number and posting date; reverse-once rule; `Undo Receipt` corrective line; ACY/reversal incompatibility. HIGH
- [Credit notes and refunds — Odoo documentation](https://www.odoo.com/documentation/19.0/applications/finance/accounting/customer_invoices/credit_notes.html) — credit note as the only legal cancellation; Reason field; Reversal date; Reverse-and-create-invoice. HIGH
- [Document Reversal FB08 — Guru99](https://www.guru99.com/how-to-perform-document-reversal.html) and [SAP FI Document Reversal — TutorialsPoint](https://www.tutorialspoint.com/sap_fico/sap_fi_document_reversal.htm) — mandatory reversal reason; alternative posting date governed by the reason; reversal document header carries the original document number. MEDIUM–HIGH
- [Canceled Document should lead to reverse GL Entries, not deletion — frappe/erpnext #11130](https://github.com/frappe/erpnext/issues/11130), [Proper Reversal Entries — #47652](https://github.com/frappe/erpnext/issues/47652), [Cancelling creates a reverse entry on the original date — #30547](https://github.com/frappe/erpnext/issues/30547) — the counter-example: mutate-on-cancel and its consequences. MEDIUM
- [Void or delete transactions — QuickBooks](https://quickbooks.intuit.com/learn-support/en-us/help-article/list-management/void-delete-transactions-quickbooks-online/L5sZV8GYh_US_en_US) and [Use the audit log to re-enter deleted transactions](https://quickbooks.intuit.com/learn-support/en-us/help-article/audit-log/use-audit-log-enter-deleted-transactions/L8RHvqYB4_US_en_US) — void keeps the record at zero; deletion survives only in the audit log. HIGH
- [Reversing entries in accounting — PLANERGY](https://planergy.com/blog/reversing-entries/) — reversal vs correction and the audit-trail argument. MEDIUM
- [Как сделать сторно в 1С Бухгалтерия 8.3 — 1CBIT](https://www.1cbit.ru/blog/kak-sdelat-storno-v-1s-bukhgalteriya-8-3-8-2/) — «красное сторно»: the compensating entry with a negative amount, posted in the current period; «Сторно документа» as a named operation the operator already knows. MEDIUM
- [Отмена учета с помощью сторнирующей операции — Business Central (RU)](https://learn.microsoft.com/ru-ru/dynamics365/business-central/finance-how-reverse-journal-posting) — Russian terminology for the same mechanism. HIGH
- [Удаление и восстановление документов — МойСклад](https://support.moysklad.ru/hc/ru/articles/203055266) — the green inline restore bar immediately after a destructive action (precedent for R12). MEDIUM
- [Job Receipts — SYSPRO](https://help.syspro.com/syspro-7-update-1/imp01b.htm) — "the basic principle which applies when reversing a job receipt is that the stock must be available in the warehouse". MEDIUM–HIGH

**Business date / posting date / lock dates**
- [Updating document dates with posting dates — Business Central](https://learn.microsoft.com/en-us/dynamics365/business-central/across-link-doc-dates-to-posting-dates) and [Specify posting periods](https://learn.microsoft.com/en-us/dynamics365/business-central/finance-how-specify-posting-periods) — the document/posting date split and allowed posting dates. HIGH
- [Guide to Using Dates in Dynamics 365 Business Central — Stoneridge Software](https://stoneridgesoftware.com/guide-to-using-dates-in-dynamics-365-business-central/) — posting date is what writes G/L, Customer and Item Ledger entries; document date drives due dates. MEDIUM–HIGH
- [Lock Dates in Odoo 17 Accounting — Cybrosys](https://www.cybrosys.com/odoo/odoo-books/v17/accounting/lock-dates/) — tiered lock dates; a draft confirmed after the lock date rolls forward. MEDIUM
- [Understanding Lock Dates in Xero — Chargebee](https://www.chargebee.com/docs/billing/2.0/kb/accounting/xero-lock-dates) and [Lock Dates in Xero — Bookkeeping Tutor](https://www.bookkeepingtutor.com.au/blog/lock-dates-in-xero/) — lock dates prevent backdating; anyone with settings access can move them, with no history of the change. MEDIUM
- [How to allow backdated inventory transactions with real-time valuation — Odoo forum](https://www.odoo.com/forum/help-1/how-to-allow-backdated-inventory-transactions-with-real-time-valuation-288422) and [Inventory costing methods — Descartes Finale](https://www.finaleinventory.com/accounting-and-inventory-software/inventory-costing-methods) — why backdating breaks FIFO cost layers, and why lock dates are the standard mitigation. MEDIUM
- Bitemporal framing (valid time = when it was true, transaction time = when it was recorded; a retroactive entry has `created_at` now and `valid_from` in the past) — established data-modelling terminology, corroborated across the retrieved patent literature. MEDIUM

**Multi-currency without conversion**
- [Currency capabilities in financial reporting — Dynamics 365 Finance](https://learn.microsoft.com/en-us/dynamics365/finance/dev-itpro/financial-reporting-currency-capability) — without a currency filter all currencies are included; a currency filter prevents row aggregation. HIGH
- [Multi-Currency Support in Reports — Clarizen](https://success.clarizen.com/hc/en-us/articles/360012180233-Multi-Currency-Support-in-Reports) — sum only within the selected currency; "Matches Currency" filter. MEDIUM

**Mobile editing UX**
- [Inline Validation UX — Smart Interface Design Patterns](https://smart-interface-design-patterns.com/articles/inline-validation-ux/) and [Mobile Inline Form Validation — UXmatters](https://www.uxmatters.com/mt/archives/2012/09/mobile-inline-form-validation.php) — validate immediately while correcting a flagged field, defer while first filling one. MEDIUM
- [7 UX Design Best Practices for Warehouse Mobile Apps](https://medium.com/@stefan.karabin/7-ux-design-best-practices-for-warehouse-mobile-apps-b6e2a0a6940f) and [Microsoft Warehouse Management App](https://apps.apple.com/us/app/microsoft-warehouse-management/id6444014310) — large touch targets for gloved hands, high contrast, guided steps over open forms, generously sized confirmation areas. MEDIUM

**This repository (read directly, 2026-09-04 — HIGH)**
- `app/services/ledger.py:37-136` (`record_operation`: no date argument; single write path; `commit=False` staging), `:139-222` (`compute_stock`, `recompute_derived` invariant)
- `app/models.py:35-45` (`OPERATION_TYPES`), `:70-99` (`CASH_CATEGORIES`, `CASH_BUCKETS`), `:199-224` (`Warehouse.currency`, CUR-01), `:248-286` (`Batch.cost_cents`, CUR-02), `:348-393` (`Operation`: `payload` JSON, `sale_id`/`batch_id` insert-only link precedent, `ix_operations_unsynced`), `:493-538` (`CashMovement`: currency, no payload column)
- `app/core.py:49-86` (`format_cents`, `CURRENCIES`, `currency_symbol`, `format_money`)
- `app/services/reports.py:21-46` (`operation_currency_clause` LOCKED decision), `:127,186,212` (`writeoff_report`, `top_selling_products`, `stale_products` — no currency argument)
- `app/services/returns.py:4-12, 46-146` (cap-before-write, zero writes on error, frozen origin price/cost — the reversal precedent)
- `alembic/versions/` — migrations `0023`–`0026` present
- `.planning/quick/260810-2g3-currency-correctness-part-2-per-currency/260810-2g3-SUMMARY.md` — the shipped currency scope, its 5 locked decisions, and the explicitly unverified browser check

---

## Unverified items (`needs verification` before requirements are finalised)

1. **Whether currency should be a milestone phase at all.** Sections above show it is largely shipped; the roadmap and the 2026-09-04 audit disagree because both quote a 2026-08-09 code survey. Re-scope with the operator before writing REQ-IDs.
2. **`writeoff_report`** — does it sum money, or only quantities? If money, it can still produce a cross-currency total (`reports.py:127`).
3. **The full list of templates still rendering bare `format_cents`** — needed to size C1. Audit every `format_cents` call site across `templates/pages`, `templates/partials`, `templates/mobile_pages`, `templates/mobile_partials`.
4. **Whether a rejected mixed-currency basket preserves the operator's basket on re-render**, or loses it — determines whether C4 is table stakes or a differentiator.
5. **Whether any report `COUNT`s operations rather than summing `qty_delta`** — such a report would count a storno as a second event instead of netting it (affects R7).
6. **Mobile currency-switcher coverage** beyond `/m/finance` and the mobile home.
7. **R20 (sale reversal vs. return)** is an operator decision, not a research finding.
8. **How the storno of a *sale* interacts with the sale's cash movement and the customer's spend statistics** — not investigated in code; depends on the R20 answer.

---
*Feature research for: small-business warehouse inventory with an append-only ledger, single operator*
*Researched: 2026-09-04*
