# Phase 22: Sales Page Rebuild - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-17
**Phase:** 22-Sales Page Rebuild
**Areas discussed:** Переключатель покупателя, Анонимная продажа, Поля нового покупателя, Живой итог, Мобильный масштаб (surfaced mid-discussion)

---

## Переключатель покупателя (Customer selector)

| Option | Description | Selected |
|--------|-------------|----------|
| Radio сверху скрывает/показывает блоки (client-side JS) | 3 radio buttons at top; switching is pure client JS show/hide, no server round trip, mirrors existing "Убрать" button | |
| Radio с HTMX-подгрузкой каждого варианта | Radio change does hx-get, server renders the matching block | ✓ |

**User's choice:** Radio с HTMX-подгрузкой каждого варианта.

| Option | Description | Selected |
|--------|-------------|----------|
| Аноним/розница | Fastest path — most sales assumed to have no customer link | |
| Существующий | Shows search first — nudges operator to look up the customer | ✓ |

**User's choice:** Существующий (default on form open).

| Option | Description | Selected |
|--------|-------------|----------|
| Сбрасывать при каждом переключении | Simple, predictable — matches today's "Убрать" behavior | |
| Сохранять введённое при возврате назад | No data loss if operator clicks wrong radio | ✓ |

**User's choice:** Сохранять введённое при возврате назад — implementation must not clobber other modes' state via the HTMX swap.

**Notes:** Mid-discussion, a scope gap was surfaced: the mobile sale wizard (`mobile_sales.py`) currently has NO customer picker at all (`customer_id=""` hardcoded). REQUIREMENTS.md's SALE-03..07 wording doesn't explicitly say "desktop and mobile" (unlike PROD-05 in Phase 18). Asked separately — see "Мобильный масштаб" below.

---

## Анонимная продажа (Anonymous sale)

| Option | Description | Selected |
|--------|-------------|----------|
| Оставить NULL как есть | No DB/service changes; "Аноним" radio just leaves customer_id unset on submit, exactly like today | ✓ |
| Создать реальный системный профиль «Аноним» | A real seeded `Customer` row every anonymous sale links to; matches the requirement's literal wording but needs migration/edge-case handling | |

**User's choice:** Оставить NULL как есть.

| Option | Description | Selected |
|--------|-------------|----------|
| «Розница» текстом (muted) | Explicit label distinguishing "no customer" from "data missing" | ✓ |
| Пустая ячейка (—) | Matches other optional-field conventions elsewhere in the app | |

**User's choice:** «Розница» текстом (muted) for the recent-sales customer column when `customer_id IS NULL`.

---

## Поля нового покупателя (New-customer inline fields)

| Option | Description | Selected |
|--------|-------------|----------|
| Только текущие 3 (имя/фамилия/консультант) | No Phase 21 fields added inline — full profile filled later on the customer card | ✓ |
| + один телефон и адрес | Most-needed fields for retail, without exposing multi-value telegram/email/social | |
| Все поля Фазы 21 инлайн | Full field set, including repeatable HTMX rows for phone/telegram/email/social | |

**User's choice:** Только текущие 3 (имя/фамилия/номер консультанта). Explicitly rejected adding even a single phone+address shortcut.

---

## Живой итог (Live running total)

| Option | Description | Selected |
|--------|-------------|----------|
| Клиентский JS-слушатель (как price-cue.js) | Delegated `input` listener, parses qty×price across rows with the same accept-set as `to_cents`, no round trip | ✓ |
| Серверный пересчёт с дебаунсом (HTMX) | Authoritative parse, but a round trip on every keystroke across a 5-10 row basket | |

**User's choice:** Клиентский JS-слушатель (как price-cue.js).

| Option | Description | Selected |
|--------|-------------|----------|
| Тихо пропускать невалидные строки | Total silently reflects only complete rows | |
| Показывать метку «итог неполный» | Explicit marker so operator doesn't mistake a partial sum for the real total | ✓ |

**User's choice:** Показывать метку «итог неполный» when any row has invalid/incomplete qty or price.

---

## Мобильный масштаб (Mobile scope — surfaced mid-discussion, not a pre-selected area)

| Option | Description | Selected |
|--------|-------------|----------|
| Только десктоп, мобильное не трогать | SALE-01..06 shipped desktop-only, mobile wizard stays customer-less as today | |
| Добавить тот же переключатель и в мобильный мастер | Full desktop/mobile parity — same 3-way radio in the mobile wizard | ✓ |

**User's choice:** Добавить тот же переключатель и в мобильный мастер — confirmed as an intentional scope expansion, not creep, since it directly closes a gap in an existing requirement (SALE-03..07) rather than adding a new capability.

---

## Claude's Discretion

- Exact Russian wording/labels for the 3 radio options and the "итог неполный" marker.
- Which mode's HTML stays live in the DOM vs. gets re-fetched on radio switch, as long as no-data-loss on switch holds.
- Whether the mobile customer selector reuses the desktop `sale_customer.html` partial structure or gets its own mobile-styled equivalent.
- Exact markup/placement of the live-total display under the basket table.

## Deferred Ideas

None — discussion stayed within phase scope. The mobile customer-selector addition is a confirmed scope expansion (operator decision), not a deferred idea.
