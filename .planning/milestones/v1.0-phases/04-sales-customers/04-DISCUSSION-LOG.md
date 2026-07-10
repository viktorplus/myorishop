# Phase 4: Sales & Customers - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-09
**Phase:** 4-Sales & Customers
**Areas discussed:** Sale entry flow, Customer linking, Oversell warning, Price/cost snapshot

---

## Sale Entry Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Одна строка (Рекомендую) | One sale = one product, "save & next" like receipts. Simpler, less code, consistent with Phase 3. | |
| Корзина | One sale = several products to one customer (catalog order). More natural for Oriflame, cleaner customer history, but noticeably more complex (order table, multi-line form). | ✓ |

**User's choice:** Корзина (basket / multi-line sale)
**Notes:** User accepted the added complexity for a more natural order model. Fast per-line entry preserved inside the basket; single commit finalizes the whole sale.

---

## Customer Linking

| Option | Description | Selected |
|--------|-------------|----------|
| Необязателен + создание в форме (Рекомендую) | Customer optional; search existing + quick-create inline in the sale form; separate /customers page for full CRUD. | ✓ |
| Только выбор из созданных | Customers created only on /customers; sale form only picks from the list. | |

**User's choice:** Optional customer + inline search/create (recommended)
**Notes:** —

---

## Oversell Warning (SAL-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Подтвердить + минус ок (Рекомендую) | Inline warning + "Продать всё равно" confirm; stock may go negative (ledger is source of truth, correction in Phase 5). | ✓ |
| Подтвердить, но не ниже нуля | Warn, but max sellable = current stock; negative forbidden. | |

**User's choice:** Warn + confirm-to-proceed, allow negative (recommended)
**Notes:** —

## Price & Cost Snapshot (SAL-02, SAL-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Снимок NULL, прибыль «?» (Рекомендую) | Sale price from card (editable per line); cost frozen from card at sale time; empty cost → NULL snapshot, profit shown as "unknown", sale not blocked. | ✓ |
| Требовать ввод себест. | If card cost empty, require entering cost before selling. More accurate profit, slower entry. | |

**User's choice:** NULL snapshot + profit "unknown" (recommended)
**Notes:** —

---

## Claude's Discretion

- Templates/partials structure, basket UI layout, RU empty-state and confirmation texts
- Migration numbering (0004+) and index choices; sale-header ↔ operation link mechanism (column vs payload vs sale_lines table)
- Where the oversell check runs (per-line vs finalize) — must warn+confirm before any negative write
- Customer purchase-history view layout (must satisfy CST-02)
- Recent-sales list as partial vs its own view

## Deferred Ideas

- CST-V2-01 purchase-frequency / "running low" reminders — later milestone
- CST-V2-02 interested-customers on receipt — later milestone
- Returns / write-offs / corrections / history browsing — Phase 5
- Reports + CSV export — Phase 6
- Multi-currency, multi-operator sync, user roles — out of scope (PROJECT.md)

## Process Note

Advisor mode active (USER-PROFILE.md present), calibration tier = standard (vendor_philosophy: pragmatic). External web research skipped by judgment: this is a well-understood local CRUD/HTMX domain built on established Phase 1–3 patterns — decisions depend on the operator's business preference and existing code, both already in hand. Recommendations were grounded directly instead of spawning research subagents.
