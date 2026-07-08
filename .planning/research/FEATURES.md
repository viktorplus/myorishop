# Feature Research

**Domain:** Warehouse inventory & sales tracking for a solo direct-sales reseller (Oriflame consultant)
**Researched:** 2026-07-08
**Confidence:** MEDIUM (cross-referenced web sources: direct-sales consultant tools, small-biz inventory tools, POS feature guides; no curated/official docs exist for this niche)

## Feature Landscape

Reference products analyzed:

- **Direct-sales consultant tools** (closest analogs): Pink Office, Direct Sidekick, QT Office, Mary Kay myCustomers+ — inventory + customers + invoices + reports for a single consultant.
- **Generic small-biz inventory tools**: Sortly (item tracking, no sales), inFlow (receiving/sales orders/reporting), Zoho Inventory (full order-to-fulfillment, noted as steep learning curve for small operators).
- **Micro-retail POS guides** (Shopify POS, retailcloud, MicroBiz): define what a "sale" transaction must support — price override, returns, stock auto-decrement, customer lookup.

Consistent pattern across all of them: the winning products for solo operators are the *simple* ones. Zoho-class breadth is explicitly cited as an adoption killer for single-user businesses; the direct-sales tools succeed by covering exactly: stock in, sell, customers, reports.

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Product catalog CRUD (code, name, category, prices, qty) | Core object of every inventory tool; all analogs have it | LOW | Most fields optional per spec; qty is derived from operations, not edited directly (see Anti-Features) |
| Fast search by code or name | Every analog (Sortly, inFlow, myCustomers+) leads with search; operator speed depends on it | LOW | SQLite LIKE + index is enough at this scale; autocomplete endpoint for HTMX |
| Goods receipt (stock in) with qty + cost + prices | "Receiving flow" is a named table-stakes feature in inFlow/Zoho; without it stock counts are fiction | LOW | Creates an operation record; updates product's current cost/sale/catalog price |
| Sale recording with auto stock decrement | Definitional: "POS updates stock automatically with every sale" (Shopify POS guide) | MEDIUM | Multi-line sale (several products in one sale) is worth doing in v1 — real purchases are baskets, not single items |
| Per-sale price override | Standard POS capability; direct sellers routinely discount for regulars | LOW | Default from product card, editable per line; store both default and actual price for discount reporting later |
| Oversell warning (selling more than in stock) | Explicit user requirement; standard POS validation | LOW | Warn-and-allow (with correction path), not hard block — real stock is sometimes right when the app is wrong |
| Returns | Named essential in every POS feature list; restores stock, reverses profit | MEDIUM | Simplest correct model: return references the original sale line → correct price/cost reversal for profit math |
| Write-off | Cosmetics expire/get damaged/become samples; every analog has "adjust out" with reason | LOW | Reason field (expired, damaged, gift/sample, personal use) — feeds write-off report |
| Stock correction (adjustment to counted value) | "Reconcile inventory if there are discrepancies" is a named POS essential; physical count will drift | LOW | Set-to-actual with auto-computed delta, logged as an operation with reason |
| Customer profile + purchase history | Core of myCustomers+/Pink Office; "who bought what, when, at what price" is the CRM minimum | MEDIUM | Optional customer on sale (walk-in sales allowed); history is a filtered view of sale lines |
| Reports: sales, profit, stock, write-offs for day/week/month/custom period | Pink Office ships 25+ reports; sales/profit/stock is the minimum any analog offers | MEDIUM | Profit requires cost captured per sale line at sale time (snapshot), not looked up later |
| Low-stock list | Present in every analog (myCustomers+ low-quantity alerts, Sortly min levels) | LOW | Per-product threshold with a sane default; a report/screen, not push notifications |
| Operation history / audit log | Explicit user requirement; also the architectural foundation for future sync | MEDIUM | Design decision, not just a feature: append-only operations table from day one; sales/receipts/write-offs ARE operations |
| Backup & data export | For a local-first app, data loss = business loss; spreadsheet-error literature shows why users fear this | LOW | One-click SQLite file backup + CSV export of products/sales. Frequently overlooked table stake for local apps |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable. These align with the Core Value: fast, reliable recording with correct stock and profit.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Pre-loaded code→name dictionary with autofill | Oriflame codes are short numerics the operator knows by heart; type code → name/prices fill in. This is *the* speed feature; generic tools can't do it | LOW | Separate reference table seeded once; receipt/sale forms autofill from it. Requires obtaining/entering the code list |
| Keyboard-first, minimal-click entry forms | Direct competitor to "just use Excel": entry must be faster than a spreadsheet row or the app loses | MEDIUM | Enter-to-advance, autofocus, autocomplete, stay-on-form after save for batch entry. UX work, not backend work |
| Profit-per-sale with cost snapshot | Pink Office markets "see your margins instantly"; solo sellers rarely know real profit | MEDIUM | Copy current cost onto each sale line at sale time. Must exist in v1 schema — retrofitting historical profit is impossible |
| Repurchase reminders ("customer may be running low") | myCustomers+'s flagship feature; drives repeat sales, the lifeblood of direct sales | HIGH | Needs purchase frequency inference per customer+product (median interval). Requires months of sales history to be useful → build after core loop is live |
| Interested-customers list on goods receipt | On receiving product X, show customers who bought X before → immediate outreach list. No generic tool has this | MEDIUM | Simple query over sales history triggered from receipt confirmation screen. Cheap once sales history exists |
| Stale-stock report ("not sold in N days") | Dead stock ties up a solo seller's limited cash; named user requirement, weakly served by generic tools | LOW | Query: products with stock > 0 and no sale in N days |
| Price change history | Oriflame catalog prices change every campaign (~3 weeks); history explains old margins | LOW | Append-only price log written on receipt/product edit; falls out of the operations-log design nearly free |
| Top products / active customers reports | Tells the operator what to reorder and who to nurture | LOW | Aggregations over existing sales data |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems for a solo, local-first, learning-developer v1.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Directly editable stock quantity on product card | "Fastest way to fix the number" | Breaks the operations ledger: stock no longer equals sum of operations, audit log lies, future sync impossible | Stock is always derived; fixes go through the stock-correction operation |
| Barcode scanning | Every inventory tool markets it | Needs hardware/camera integration; Oriflame codes are short and typed faster than scanned; adds a whole integration surface | Code autocomplete from the reference dictionary (already planned) |
| FIFO/batch (lot) costing | "Accurate" profit per batch | Significant schema + logic complexity (lot tracking, allocation); for one seller with small volumes the precision gain is noise | Snapshot current cost onto each sale line; revisit only if cost swings prove material |
| User auth, roles, permissions | In the original spec (admin/operator/viewer) | One user on localhost in year one; auth adds friction to every request and every feature | Defer to sync milestone (already a PROJECT.md decision); audit log records operations regardless |
| Cloud sync / multi-operator | In the original spec; "hardest part" per PROJECT.md | Conflict resolution is a project in itself; would dominate v1 effort | Local-first + append-only operation log now = sync-ready later without rework |
| Multi-currency | Original spec mentions multiple countries | Every price/report grows a currency dimension; pure overhead for one country | Single currency column-free v1 (already a PROJECT.md decision) |
| Invoicing & payment processing | Direct Sidekick/Pink Office have Stripe invoicing | Payments = compliance, receipts, refund flows; the user sells face-to-face for cash | Record the sale; money handling stays outside the app |
| Full accounting (expenses, mileage, tax) | Direct Sidekick sells this hard | Different domain with its own rules; scope explosion | Profit report from sales data only; accounting stays in whatever the user does today |
| Push/email notifications | "Alert me on low stock" | Requires background jobs/scheduling + delivery channel on a localhost app that isn't always running | Dashboard panels: low-stock list and due-reminders list shown on app open |
| Excel/CSV import of catalog & stock | Standard onboarding feature | No existing data to import (user decision); import validation is deceptively expensive | Manual entry via the fast receipt form; CSV *export* still provided for backup |
| Multi-warehouse / locations | inFlow/Zoho tier feature | One physical stock location; adds a dimension to every stock query and screen | Single implicit location; revisit at sync milestone if second country materializes |
| Real-time dashboards / charts everywhere | Demo appeal | Charting libs and live updates add complexity; operator needs numbers, not animations | Plain HTML tables with period filters; totals in bold |

## Feature Dependencies

```
Operations log (append-only)
    └──underpins──> Goods receipt / Sale / Write-off / Return / Correction
                        └──derives──> Current stock levels
                                          └──enables──> Oversell warning, Low-stock list

Product catalog ──requires──> (nothing; foundation)
Reference dictionary (code→name) ──enhances──> Receipt form, Sale form (autofill)

Sale recording ──requires──> Product catalog + stock on hand (receipts first)
Sale w/ cost snapshot ──enables──> Profit reports
Return ──requires──> Sale (references original sale line)

Customer profiles ──enhances──> Sale recording (optional link)
Customer purchase history ──requires──> Sales linked to customers
Repurchase reminders ──requires──> Purchase history + frequency inference (needs months of data)
Interested-customers-on-receipt ──requires──> Purchase history + Goods receipt flow

Reports (sales/profit/stock/write-offs/top/stale) ──require──> Operations log populated
Price change history ──requires──> Operations log (receipt/edit events)
Backup/export ──requires──> Stable schema (any time after core entities exist)
```

### Dependency Notes

- **Everything requires the operations log:** it is the load-bearing decision. Sales, receipts, write-offs, returns, and corrections should *be* rows in an append-only operations structure; stock and reports derive from it. This also delivers the audit log for free and keeps the future-sync door open (PROJECT.md decision).
- **Profit reports require cost snapshot at sale time:** the schema must copy cost onto the sale line in v1 even though profit reports could ship later. Retrofitting is impossible — history without snapshots can never yield correct profit.
- **Repurchase reminders require history depth:** frequency inference on <2–3 purchases per customer/product produces garbage reminders. Ship the core loop first; reminders become useful only after real usage accumulates. This makes them a natural late phase.
- **Return references sale:** modeling returns as free-standing "stock in" operations loses the price/cost linkage and silently corrupts profit reports. Cheap to do right the first time, painful to fix.
- **Interested-customers is cheap once sales history exists:** it is a single query bolted onto the receipt confirmation screen — good early differentiator for low cost, but only after customers + sales are live.

## MVP Definition

### Launch With (v1)

Minimum viable product — validates the core value: "record receipts and sales fast; stock and profit always correct."

- [ ] Product catalog CRUD + fast search — foundation for everything
- [ ] Reference dictionary (code→name) with autofill — the speed differentiator, cheap
- [ ] Operations log (append-only) as the base for all stock movements — architectural table stake
- [ ] Goods receipt form — stock must exist before it can be sold
- [ ] Sale form: multi-line, price override, optional customer, cost snapshot, oversell warning — the core loop
- [ ] Write-off, return (sale-linked), stock correction — without these, stock drifts and trust dies
- [ ] Customer profiles + purchase history — required by the sale form's customer link
- [ ] Core reports: sales, profit, current stock, write-offs, low-stock, per period — the payoff that proves the app beats a notebook
- [ ] One-click backup (copy SQLite file) + CSV export — local-first apps without backup lose businesses

### Add After Validation (v1.x)

- [ ] Stale-stock report — trigger: a month of sales data exists
- [ ] Top products / active customers reports — trigger: enough data to rank
- [ ] Interested-customers list on receipt — trigger: customer-linked sales accumulating
- [ ] Price change history view — data captured from day one; UI when the user asks "why was margin different?"
- [ ] Repurchase reminders — trigger: 2–3 months of history; start with median-interval heuristic

### Future Consideration (v2+)

- [ ] Multi-operator sync via central server — deferred by decision; enabled by the operations log
- [ ] Auth/roles — only meaningful with sync
- [ ] Multi-currency — only meaningful with a second country
- [ ] Barcode scanning, Oriflame campaign catalog integration, batch/FIFO costing, notifications — best-practice extras; none blocks earlier phases

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Catalog + search + dictionary autofill | HIGH | LOW | P1 |
| Goods receipt | HIGH | LOW | P1 |
| Sale (multi-line, override, snapshot, warning) | HIGH | MEDIUM | P1 |
| Write-off / return / correction | HIGH | MEDIUM | P1 |
| Operations/audit log | HIGH | MEDIUM | P1 (architectural) |
| Customers + purchase history | HIGH | MEDIUM | P1 |
| Core reports (sales/profit/stock/write-offs/low-stock) | HIGH | MEDIUM | P1 |
| Backup + CSV export | HIGH | LOW | P1 |
| Stale-stock, top-products, active-customers reports | MEDIUM | LOW | P2 |
| Interested-customers on receipt | MEDIUM | MEDIUM | P2 |
| Price change history UI | MEDIUM | LOW | P2 |
| Repurchase reminders | HIGH | HIGH | P2 (late — needs data) |
| Sync, auth, multi-currency, barcodes | MEDIUM | HIGH | P3 |

## Competitor Feature Analysis

| Feature | Direct-sales tools (Pink Office, Direct Sidekick, myCustomers+) | Generic inventory (Sortly, inFlow, Zoho) | Our Approach |
|---------|--------------|--------------|--------------|
| Inventory tracking | Real-time counts, low-stock alerts, import from company back office | Strong; barcode-first, multi-location | Operations-log-derived stock, low-stock list, no barcodes/locations |
| Sales recording | Invoices with payments (Stripe) | Sales orders/POS tiers | Plain sale records, no invoicing/payments |
| Customer CRM | Purchase history, birthdays, follow-up reminders | Weak or absent | Purchase history + frequency-based repurchase reminders (v1.x) |
| Company-specific product data | Import from Mary Kay InTouch etc. | None | Pre-seeded Oriflame code→name dictionary with autofill |
| Reports | 25+ reports (Pink Office); sales/inventory/expenses | Stock and order reports | Focused set: sales, profit, stock, write-offs, top, stale, low-stock |
| Profit calc | Margins per invoice | Costing at order level | Cost snapshot per sale line; average-cost simplicity, no FIFO |
| Accounting/tax | Core selling point (Direct Sidekick) | Absent | Deliberately out — profit from sales only |
| Offline/local | Cloud-only SaaS | Cloud-only SaaS | **Differentiator: fully local, no internet, no subscription** |

Notable gap in the market our constraints exploit: all direct-sales analogs are US-centric, subscription, cloud-only, and often tied to one company (Mary Kay). A local, free, Oriflame-code-aware tool has no direct competitor — but it also means the bar is set by *spreadsheets*, so entry speed is the metric that decides adoption.

## Sources

Confidence: MEDIUM overall — vendor marketing pages and comparison articles, cross-verified across 3+ independent sources per claim; no first-party/curated documentation exists for this niche. (Note: gsd-tools `research-plan` / `classify-confidence` / `research-store` seams were unavailable in this installation; built-in WebSearch used per fallback rules, confidence self-assessed.)

- Direct-sales consultant tools: [Pink Office](https://www.pinkoffice.com/), [Direct Sidekick](https://directsidekick.com/), [Direct Sidekick — Mary Kay inventory tracking](https://directsidekick.com/mary-kay-inventory-tracking/), [QT Office](https://www.qtoffice.com/home/), [Mary Kay myCustomers+ (App Store)](https://apps.apple.com/us/app/mycustomers/id1126501083), [Retail Dive on myCustomers+](https://www.retaildive.com/ex/mobilecommercedaily/mary-kay-uncaps-sales-via-beauty-consultant-geared-virtual-assistant-app)
- Small-biz inventory comparisons: [Cin7 — best inventory systems for small business](https://www.cin7.com/blog/best-inventory-management-systems-for-small-business/), [Softr — Zoho vs Sortly](https://www.softr.io/blog/zoho-inventory-vs-sortly), [SelectHub — Sortly vs Zoho](https://www.selecthub.com/inventory-management-software/sortly-vs-zoho-inventory/), [G2 — Sortly vs Zoho](https://www.g2.com/compare/sortly-vs-zoho-inventory)
- POS essentials (sale/return/override/adjustment semantics): [Shopify — POS features guide](https://www.shopify.com/blog/pos-features), [retailcloud — essential POS features](https://retailcloud.com/modern-retail-pos-features/), [Stax — POS for retail](https://staxpayments.com/blog/pos-systems-for-retail-store/), [Microsoft Dynamics — POS returns model](https://learn.microsoft.com/en-us/dynamics365/commerce/pos-returns)
- Adoption pitfalls / spreadsheet failure modes: [erplain — 5 inventory mistakes](https://www.erplain.com/en/blog-en/5-inventory-management-mistakes-small-businesses-often-make), [Sortly — common inventory mistakes](https://www.sortly.com/blog/common-inventory-mistakes-and-how-to-avoid-them/), [Rackbeat — spreadsheet inventory mistakes](https://rackbeat.com/en/5-common-mistakes-companies-make-with-spreadsheet-inventory-management-and-how-to-avoid-them/)
- Project context: `E:\dev\myorishop\.planning\PROJECT.md`, `E:\dev\myorishop\agent.md`

---
*Feature research for: solo direct-sales reseller inventory & sales tracking*
*Researched: 2026-07-08*
