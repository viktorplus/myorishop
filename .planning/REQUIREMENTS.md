# Requirements: MyOriShop — Финансы / Касса (v1.3)

**Defined:** 2026-07-14
**Core Value:** The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.

## v1 Requirements

Requirements for milestone v1.3. Each maps to roadmap phases.

### Финансы

- [ ] **FIN-01**: Касса автоматически пополняется на сумму каждой продажи
- [ ] **FIN-02**: Касса автоматически списывается при возврате товара (симметрично автопополнению при продаже)
- [ ] **FIN-03**: Оператор может списать средства из кассы с обязательным выбором категории (оплата поставщику / зарплата / аренда / коммунальные / прочее) и комментарием
- [ ] **FIN-04**: Оператор может вручную пополнить кассу (начальный остаток / корректировка ошибки) с комментарием
- [ ] **FIN-05**: Списание, уводящее баланс кассы в минус, показывает предупреждение, но допускает подтверждение (тот же паттерн, что у оверселла/минимальной цены)
- [ ] **FIN-06**: Отдельный раздел UI «Финансы» с текущим балансом кассы
- [ ] **FIN-07**: История движений кассы с пагинацией/фильтрацией (как у других списков — Phase 14)
- [ ] **FIN-08**: Отчёт по движениям кассы за период (приход/расход по категориям)
- [ ] **FIN-09**: CSV-экспорт движений кассы
- [ ] **FIN-10**: Дашборд «Финансы» показывает валовую прибыль за период (цена продажи минус закупочная цена по продажам, переиспользуя существующий `sales_profit_report`)
- [ ] **FIN-11**: Дашборд «Финансы» показывает чистую прибыль = валовая прибыль минус расходы кассы за тот же период
- [ ] **FIN-12**: Дашборд «Финансы» показывает стоимость товара на складе: сумма по закупочным ценам и сумма по ценам продажи (по всем активным остаткам/партиям)

## v2 Requirements

Deferred to future release. Not in current roadmap.

### Финансы (расширенное)

- **FIN-V2-01**: Структурная привязка списания к конкретному приходу/поставке (не просто свободный текст)
- **FIN-V2-02**: Несколько касс/счетов, сменные/периодические закрытия смены
- **FIN-V2-03**: Плановые/повторяющиеся расходы, бюджетные лимиты по категориям

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Полноценная двойная бухгалтерия, налоговый учёт | Не нужно для кассы одного оператора локального магазина |
| Выставление счетов / интеграция с платёжными шлюзами | Не входит в core value приложения |
| Банковская сверка (bank reconciliation) | Касса — это наличные средства, банк вне охвата |
| Мультивалютность в кассе | Проект в целом однвалютный (см. Constraints в PROJECT.md) |
| Фото/OCR чеков | Избыточно для однооператорского локального инструмента |
| Роли/согласование расходов (approval workflow) | Один оператор — нет ролей до v2.0 (multi-operator sync) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FIN-01 | TBD | Pending |
| FIN-02 | TBD | Pending |
| FIN-03 | TBD | Pending |
| FIN-04 | TBD | Pending |
| FIN-05 | TBD | Pending |
| FIN-06 | TBD | Pending |
| FIN-07 | TBD | Pending |
| FIN-08 | TBD | Pending |
| FIN-09 | TBD | Pending |
| FIN-10 | TBD | Pending |
| FIN-11 | TBD | Pending |
| FIN-12 | TBD | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 0 (roadmap not yet created)
- Unmapped: 12 ⚠️ (expected — roadmapper fills this in next)

---
*Requirements defined: 2026-07-14*
*Last updated: 2026-07-14 after initial definition (research-informed: return auto-debit, bidirectional manual entry, and profit/stock-valuation dashboard additions came from research + user follow-up)*
