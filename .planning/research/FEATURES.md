# Feature Research

**Domain:** Cash balance / cash-flow tracking ("Касса") module for a single-operator local retail-reseller app — not an accounting system
**Researched:** 2026-07-14
**Confidence:** MEDIUM-HIGH (domain is well-established practitioner consensus; PROJECT.md scope itself is HIGH-confidence first-party source)

> Supersedes the v1.1-era FEATURES.md (2026-07-10, multi-warehouse/batch-tracking domain). This file covers only the v1.3 milestone: Финансы / Касса (cash balance tracking). Prior milestone findings remain valid history in git; see PROJECT.md "Validated" section for what already shipped.

## Feature Landscape

### Table Stakes (Users Expect These)

Features a "Касса"/petty-cash module is broken without — all are already implied by the v1.3 target features in PROJECT.md, made explicit here with complexity.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Current cash balance display | The single reason the module exists — operator must see "how much cash do I have right now" at a glance | LOW | Sum of all cash-ledger entries (in − out). If Касса reuses the existing append-only `record_operation()` ledger with new operation types, balance is a `SUM()` query, no new stored-balance column needed (avoids cache-consistency bugs) |
| Auto-credit on every sale | PROJECT.md target feature; matches how every real petty-cash/POS tool works — revenue is captured automatically, never re-typed | LOW-MEDIUM | Hook into the existing `register_sale()` service (single ledger write path per project's own Key Decision) — do not create a second, parallel write path |
| Auto-debit on sale-linked return | **Gap found, not in PROJECT.md's stated target list.** A sale-linked return already exists (Phase 5, OPS-01..04) and refunds the customer — if Касса doesn't mirror it as a cash-out, the balance silently drifts from physical reality the first time a return happens | LOW-MEDIUM | Same hook point as auto-credit; wire into the existing return-registration path, not a new manual step |
| Manual withdrawal with mandatory reason | PROJECT.md target feature: "pay supplier order / salary / other" + free-text comment | LOW | Simple form: category select (3 fixed values) + required comment when "other" (and recommended even for the other two, for traceability) |
| Movement history (chronological ledger) | Universal expectation for any cash-tracking tool — "show me what happened and when" | LOW-MEDIUM | Reuse the existing `/history` list-page pattern (Phase 5) already built for operations — pagination/filter/sort infrastructure from Phase 14 (`pagination.py`) applies directly |
| Insufficient-balance guard on withdrawal | The app has an established UX pattern for this exact situation: oversell warns but allows override (Phase 4 SAL-05), min-price warns but allows override (Phase 7 PRICE-01) | LOW | Extend the same "warn, allow override" convention to withdrawals exceeding current balance — do NOT silently block (operator may legitimately need to record a withdrawal that puts cash negative, e.g. cash was topped up from a personal wallet) |
| Separate "Финансы" UI section | PROJECT.md explicit requirement | LOW | New top-level nav entry + its own routes/templates, following the existing section pattern (Catalog, Warehouses, Reports, etc.) |

### Differentiators (Valuable, Not Required for v1.3 Scope)

Real capabilities seen in petty-cash and POS-till tools, worth flagging for a *future* milestone rather than building now — none are requested in the current PROJECT.md target list.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Manual balance correction/adjustment entry | Reconciles the ledger-computed balance with what's physically counted in the cash box (miscounts, undocumented historical cash, rounding drift) | LOW-MEDIUM | Same pattern as existing stock "correction" operation (Phase 5 OPS-04) — a signed adjustment entry with a mandatory comment, never a direct edit of past entries. **See Gaps section — likely needed at Касса launch, not just "nice later."** |
| Cash flow reports (period cash-in/out, by category) | Natural extension once the ledger exists; mirrors the existing Reports module (Phase 6) which already does day/week/month/custom-period aggregation | MEDIUM | Reuse the existing shared period-filter + local-day-boundary helper (Key Decision, Phase 6) rather than writing new date-math |
| CSV export of cash movements | Consistent with existing data-export pattern (BCK-02, Phase 6) — Excel-compatible CSV, BOM, `;` delimiter, formula-injection escaping already solved once | LOW-MEDIUM | Add as a fourth export file alongside products/sales/customers, reusing the existing CSV-writer helper, not a new implementation |
| Structured link: withdrawal → specific goods receipt/supplier order | Lets a "pay supplier" withdrawal reference *which* receipt it's paying for (partial/deferred payment tracking) rather than free text | MEDIUM | Would require a nullable FK from the cash-out entry to a receipt/operation ID, plus UI to pick one — real value only once goods are commonly received on credit/deferred payment, which isn't a stated v1.3 need |
| Shift/period reconciliation (expected vs physically counted) | Standard POS-till practice: compare ledger-computed balance to a manual physical count, surface the delta ("shortage/overage") | MEDIUM | Genuinely valuable for catching data-entry mistakes, but the value is highest with multiple cashiers/shifts. With 1 operator it mostly duplicates the "manual correction" entry above. Low urgency now |
| Multiple cash accounts/tills (e.g. cash box vs bank account) | Real businesses often split "cash on hand" from "money in the bank" | MEDIUM-HIGH | Explicitly out of scope for this milestone — see Anti-Features |
| Scheduled/recurring expenses (e.g. auto-log monthly rent) | Reduces repetitive manual entry for predictable recurring costs | MEDIUM-HIGH | Requires a background scheduler (APScheduler or similar) that does not exist anywhere in the current stack — disproportionate complexity for a convenience feature; operator can log it manually in seconds |
| Budget categories / spending limits per category | Lets the operator cap "how much can go to X per month" and get warned | MEDIUM | This is a personal-finance-app feature, not a cash-box-tracking feature; no signal in PROJECT.md that budgeting is a goal |

### Anti-Features (Commonly Requested, Often Problematic)

The instinct with any "money" feature is to reach for real accounting patterns. Resist it — this is a cash-box counter for one operator, not a bookkeeping system.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Full double-entry bookkeeping (debits/credits, chart of accounts, trial balance) | "Proper" accounting systems all work this way | Massive conceptual and implementation overhead for a single till with 3 expense categories; the project is explicitly beginner-friendly and local-first | Simple signed append-only ledger: each entry is `+amount` (sale/credit) or `-amount` (withdrawal/debit), balance = running sum |
| Tax reporting / VAT / tax categories | "Might as well capture it while we're tracking money" | No tax requirement stated anywhere in PROJECT.md; adds jurisdiction-specific complexity that doesn't belong in a warehouse-inventory tool | Nothing — if ever needed, export the CSV and hand it to an accountant/external tool |
| Invoicing / payment processing / payment gateway integration | Feels like a natural companion to "cash movements" | Already explicitly out of scope project-wide ("Invoicing/payments... not needed for core value") | Nothing — Касса only tracks cash already changing hands via existing sale/withdrawal flows |
| Bank reconciliation / bank statement import | Businesses do reconcile books against bank statements | This module tracks a *physical* cash box, not a bank account; no bank integration exists or is planned | Nothing — if a bank account is ever tracked, that's a separate "account" concept, not this feature |
| Multi-currency in Касса | Could seem needed once multi-country sync (v2.0) lands | Already deferred project-wide to v2.0 (CUR-V2-01); adding it here now creates a parallel currency model to retrofit later | Single-currency ledger now; extend when CUR-V2-01 is actually scoped |
| Multi-till / multi-cash-account structure | "What if there are two registers someday?" | No stated need; single operator, single physical location in v1.3 scope | Ship single-till now; the append-only ledger design doesn't block adding a `till_id` column later if genuinely needed |
| User roles / manager-approval workflow for withdrawals | Standard in multi-employee petty-cash tools | Project constraint: 1 operator, no auth complexity in v1 (explicit constraint in PROJECT.md and CLAUDE.md) | Nothing — the single operator is trusted by construction |
| Editable/deletable cash entries | "Let me just fix a typo directly" | Breaks the append-only audit-log invariant the whole app is built on (Key Decision: ledger rows are never UPDATE/DELETE'd) | Reversal/correction entry with a comment — same pattern as existing stock corrections |
| Receipt photo capture / OCR | Common in expense-tracking apps | No camera/OCR infrastructure anywhere in this stack; this app is manual, fast-entry by design (no barcode scanner either, by explicit prior decision) | Free-text comment field is enough for a single trusted operator |

## Feature Dependencies

```
Auto-credit on sale (table stakes)
    └──requires──> register_sale() service already exists (Phase 4) — hook, don't duplicate

Auto-debit on sale-linked return (table stakes, gap-flagged)
    └──requires──> return-registration path already exists (Phase 5) — hook, don't duplicate

Manual withdrawal entry (table stakes)
    └──requires──> category enum (pay supplier / salary / other) + comment field

Movement history view (table stakes)
    └──requires──> both of the above writing to one shared cash-ledger table/operation-type

Current balance display (table stakes)
    └──requires──> Movement history ledger (balance = SUM of entries, not a separately maintained counter)

Insufficient-balance guard (table stakes)
    └──requires──> Current balance display (need the number to compare against)
    └──mirrors──> existing oversell-warning and min-price-warning UX pattern (Phase 4/7)

Cash flow reports (differentiator)
    └──requires──> Movement history ledger + existing period-filter helper (Phase 6)

CSV export of cash movements (differentiator)
    └──requires──> Movement history ledger + existing CSV export helper (Phase 6)

Manual balance correction (differentiator, likely needed at launch — see Gaps)
    └──requires──> Movement history ledger
    └──mirrors──> existing stock "correction" operation pattern (Phase 5 OPS-04)

Structured link: withdrawal → goods receipt (differentiator)
    └──requires──> Manual withdrawal entry + existing goods-receipt operation IDs (Phase 3)

Shift reconciliation (differentiator)
    └──requires──> Manual balance correction (functionally overlaps for a single-operator app)

Multiple cash accounts/tills (future) ──conflicts──> current single-balance design
    (would require a till_id dimension on every ledger entry and every report — a schema
     decision, so if ever wanted it should be decided before, not after, the balance
     column/query shape is fixed)
```

### Dependency Notes

- **Auto-credit and auto-debit both require the *same* single write path.** The project's own Key Decision ("`record_operation()` as the single ledger write path... makes append-only + stock-cache consistency and future sync conflict resolution tractable") applies directly to cash: Касса should almost certainly be new operation types appended to the *same* ledger table the app already has, not a second parallel `cash_movements` table. That's an architecture call, but it directly shapes which features are "free" (history, reports reuse existing infra) versus which require new plumbing (a second ledger would need its own history view, its own pagination, its own CSV export).
- **Balance must never be a separately maintained/cached column that can drift.** Compute it from the ledger (`SUM`), exactly like the project already avoids float/cache-consistency bugs elsewhere (money stored as integer minor units per STACK.md).
- **Manual balance correction enhances all of the above** by giving the operator an escape hatch when the computed balance and physical cash disagree — without it, any data-entry mistake (or the very first day of using Касса, when a real cash balance already exists in the drawer) has no clean recovery path other than a fake "withdrawal" or "sale" abusing the wrong category.
- **Multiple cash accounts/tills conflicts with the current single-balance design** if bolted on later without planning — worth a one-line schema note (e.g. keep a nullable `till_id`/`account_id` slot even if unused in v1.3) only if the team wants to keep that door open cheaply; not a requirement for this milestone.

## MVP Definition

### Launch With (v1.3 — matches PROJECT.md target features, refined)

- [ ] Auto-credit balance from every sale — table stakes, explicit PROJECT.md requirement
- [ ] Auto-debit balance from every sale-linked return — **gap not in PROJECT.md's stated list; without it the balance is wrong the first time a return happens**
- [ ] Manual withdrawal with mandatory category (pay supplier order / salary / other) + comment — explicit PROJECT.md requirement
- [ ] Movement history view (filterable/sortable, reusing existing list-page infrastructure) — explicit PROJECT.md requirement
- [ ] Current balance display — explicit PROJECT.md requirement
- [ ] Insufficient-balance warning on withdrawal (warn, allow override) — matches existing app-wide UX convention
- [ ] Separate "Финансы" UI section — explicit PROJECT.md requirement

### Add After Validation (v1.3.x or immediate follow-up)

- [ ] Manual balance correction/adjustment entry — trigger: as soon as the module ships against a business that already has cash on hand (balance starts at 0 otherwise, which is wrong from day one)
- [ ] Cash flow reports (period in/out, by category) — trigger: once a few weeks of movement history exist and the operator wants trend visibility, same as existing Reports module
- [ ] CSV export of cash movements — trigger: once the operator wants to hand data to an accountant/backup, matching the existing full-data-export pattern

### Future Consideration (v2+)

- [ ] Structured link: withdrawal → specific goods receipt/supplier order — defer: no deferred-payment/credit-purchase pattern exists yet in the app to link against
- [ ] Multiple cash accounts/tills — defer: no second till/location need stated; would be a schema decision better made deliberately, not incidentally
- [ ] Shift/period reconciliation (expected vs counted) — defer: value is highest with multiple cashiers/shifts; single operator gets most of the benefit from the simpler manual-correction entry
- [ ] Scheduled/recurring expenses — defer: needs a background scheduler not present anywhere in the stack; disproportionate for the convenience gained
- [ ] Budget categories/spending limits — defer: no signal this is a goal; it's a personal-finance feature, not a cash-box tracker

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|----------------------|----------|
| Auto-credit on sale | HIGH | LOW | P1 |
| Auto-debit on sale-linked return | HIGH | LOW | P1 |
| Manual withdrawal + mandatory reason | HIGH | LOW | P1 |
| Movement history view | HIGH | LOW | P1 |
| Current balance display | HIGH | LOW | P1 |
| Insufficient-balance warning | MEDIUM | LOW | P1 |
| "Финансы" UI section | HIGH | LOW | P1 |
| Manual balance correction | HIGH | LOW-MEDIUM | P1 (recommend pulling into v1.3, see Gaps) |
| Cash flow reports | MEDIUM | MEDIUM | P2 |
| CSV export of cash movements | MEDIUM | LOW-MEDIUM | P2 |
| Structured link to goods receipt | LOW-MEDIUM | MEDIUM | P3 |
| Shift/period reconciliation | LOW (single operator) | MEDIUM | P3 |
| Multiple cash accounts/tills | LOW | MEDIUM-HIGH | P3 |
| Scheduled/recurring expenses | LOW | MEDIUM-HIGH | P3 |
| Budget categories/limits | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v1.3 launch
- P2: Should have, add once v1.3 core is validated
- P3: Nice to have, defer to v2+ or drop

## Competitor Feature Analysis

Not a market-facing product (single-operator internal tool), so this compares against the *category* of tool rather than named competitors — small-business petty-cash apps and POS till-management features, per the practitioner sources below.

| Feature | Petty-cash apps (Pleo, Zoho Expense, Weel, etc.) | POS till management (Lightspeed, Shopify POS, etc.) | Our Approach |
|---------|----------------------------------------------------|--------------------------------------------------------|--------------|
| Balance visibility | Real-time balance, always shown | Running total per shift/drawer | Real-time balance from ledger `SUM`, always shown |
| Cash in/out entry | Manual entry + receipt photo/OCR + categories | Auto from sales; manual "cash drop/loan" entries | Auto from sales/returns; manual entry with fixed categories, no OCR (not needed, single trusted operator) |
| Categorization | Free-form customizable categories | Minimal (drop/loan/paid-in/paid-out) | Fixed 3-category set (supplier/salary/other) + comment — matches PROJECT.md scope, avoids unbounded category sprawl |
| Approval workflow | Multi-user approval chains | Manager approves cashier's count | Not applicable — single trusted operator, no auth layer |
| Reconciliation | N/A (not till-based) | End-of-shift count vs expected, shortage/overage report | Deferred to v2+ (manual correction entry covers the single-operator case for now) |
| Multi-account | Often supports multiple wallets/cards | Multiple registers/drawers | Single balance only, by design |

## Sources

- `.planning/PROJECT.md` — first-party project scope, target features, existing architecture/Key Decisions (Confidence: HIGH)
- Web search: "simple petty cash management app features small business cash in cash out categories" — [haeywa petty cash app](https://play.google.com/store/apps/details?id=com.dotnovaai.haeywa&hl=en_US), [Weel: Top 5 Petty Cash Management Software](https://letsweel.com/resources/the-weelhouse/articles/the-best-petty-cash-management-software), [Pleo petty cash](https://www.pleo.io/en/petty-cash), [Zoho Expense petty cash](https://www.zoho.com/us/expense/petty-cash-management/) (Confidence: MEDIUM — cross-checked across multiple independent listings, consistent pattern: real-time balance, categorized in/out, approval workflows for multi-user tools)
- Web search: "POS cash drawer reconciliation shift closing count till features small retail" — [Fit Small Business: POS Reconciliation](https://fitsmallbusiness.com/pos-reconciliation/), [Shopify: Balancing a Cash Drawer](https://www.shopify.com/blog/balancing-a-cash-drawer), [KORONA POS: Count the Till](https://koronapos.com/blog/count-the-till-cash-handling/), [POS Highway: Cash Drawer Management](https://www.poshighway.com/blog/cash-drawer-management-cycle-counts-reconcilation-activation-and-closing/) (Confidence: MEDIUM — cross-checked, confirms reconciliation/shift-count value scales with multiple cashiers, which doesn't apply to this single-operator app)

---
*Feature research for: Касса/Финансы module, MyOriShop v1.3*
*Researched: 2026-07-14*
