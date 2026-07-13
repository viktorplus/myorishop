# Phase 13: Mobile Wizard Context & Navigation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-13
**Phase:** 13-mobile-wizard-context-navigation
**Areas discussed:** Visible code/name/warehouse format, Write-off "Назад" retrofit, Sale basket step indicator, Search → wizard quick actions

---

## Visible code/name/warehouse format (UI-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Как уже сделано в sale/transfers | `**{{ code }}** — {{ name }}` line, warehouse line only once known | ✓ |
| Всегда три строки, склад с прочерком | Always render code/name/warehouse, "Склад: —" placeholder before known | |

**User's choice:** Mirror the existing `sale_step_batch.html`/`transfers_step_dest.html` format.
**Notes:** Warehouse line renders only once a batch is picked (batch determines warehouse); no placeholder before that.

---

## Write-off "Назад" retrofit (UI-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Как в receipts (одиночный товар) | Migrate write-off to persistent-shell + hx-post/hx-include back pattern | ✓ |
| Оставить history.back(), добавить fallback | Keep current mechanism with a minor safety net | |

**User's choice:** Mirror the receipts pattern.
**Notes:** Scouting revealed write-off currently uses a fundamentally different architecture (full-page-per-step, plain form POST) than receipts/sale/transfers (persistent shell + hx-post fragment swap) — this choice implies a structural migration, not a one-line button change. Captured as D-04 in CONTEXT.md.

---

## Corrections "Назад" (found during scouting, not in original 4 areas)

| Option | Description | Selected |
|--------|-------------|----------|
| Оставить как есть | UI-03 requirement text only names write-off; corrections' "back to wizard start" bug is a separate, unnamed issue | |
| Исправить тоже | Apply the same per-step hx-post/hx-include fix to corrections' 3 steps, since write-off is already being migrated | ✓ |

**User's choice:** Fix corrections too.
**Notes:** Corrections' 3 steps all link "Назад" straight to `/m/corrections` (wizard start) instead of the previous step, silently discarding entered state. Not explicitly named by UI-03's text but matches its intent ("all mobile wizards use the same explicit navigation pattern").

---

## Sale basket step indicator (UI-04)

| Option | Description | Selected |
|--------|-------------|----------|
| «Корзина» вместо номера шага | Text-only label, no step count, since basket length varies | ✓ |
| «Шаг 3 из 3 (Корзина)» фиксированно | Treat basket as a fixed final step number | |

**User's choice:** "Корзина" label, no step count.

---

## Search → wizard quick actions (UI-05)

| Option | Description | Selected |
|--------|-------------|----------|
| На шаг 1 с предзаполненным кодом | Land on the wizard's normal step 1, code pre-filled | ✓ |
| Сразу на шаг 2 (выбор партии) | Skip straight to batch selection | |

**User's choice:** Land on step 1 with the code pre-filled — no step-skip logic needed.

### Zero-stock "Продать" visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Скрыть кнопку | Hide "Продать" if the product has zero stock everywhere | |
| Показывать всегда | Always show it — app already allows oversell-with-warning | ✓ |

**User's choice:** Always show "Продать", consistent with the existing oversell-allowed pattern.

---

## Claude's Discretion

- Exact markup/CSS for the new visible code/name/warehouse lines beyond matching the existing shape.
- Exact shape of the write-off shell-page migration (route/template split), as long as back-navigation behavior matches receipts.
- Exact query-param/form-field mechanism for pre-filling the code on quick-action navigation.

## Deferred Ideas

None — discussion stayed within Phase 13 scope. Full mobile CRUD parity remains out of scope (UI-V2-02, v2.0).
