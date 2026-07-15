# Requirements: MyOriShop — Финансы / Касса (v1.3)

**Defined:** 2026-07-14
**Core Value:** The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.

## v1 Requirements

Requirements for milestone v1.3. Each maps to roadmap phases.

### Финансы

- [ ] **FIN-01**: Касса автоматически пополняется на сумму каждой продажи
- [ ] **FIN-02**: Касса автоматически списывается при возврате товара (симметрично автопополнению при продаже)
- [x] **FIN-03**: Оператор может списать средства из кассы с обязательным выбором категории (оплата поставщику / зарплата / аренда / коммунальные / прочее) и комментарием
- [x] **FIN-04**: Оператор может вручную пополнить кассу (начальный остаток / корректировка ошибки) с комментарием
- [x] **FIN-05**: Списание, уводящее баланс кассы в минус, показывает предупреждение, но допускает подтверждение (тот же паттерн, что у оверселла/минимальной цены)
- [ ] **FIN-06**: Отдельный раздел UI «Финансы» с текущим балансом кассы
- [x] **FIN-07**: История движений кассы с пагинацией/фильтрацией (как у других списков — Phase 14)
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
| FIN-01 | Phase 15 | Pending |
| FIN-02 | Phase 15 | Pending |
| FIN-03 | Phase 16 | Complete |
| FIN-04 | Phase 16 | Complete |
| FIN-05 | Phase 16 | Complete |
| FIN-06 | Phase 15 | Pending |
| FIN-07 | Phase 16 | Complete |
| FIN-08 | Phase 17 | Pending |
| FIN-09 | Phase 17 | Pending |
| FIN-10 | Phase 17 | Pending |
| FIN-11 | Phase 17 | Pending |
| FIN-12 | Phase 17 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12 (Phase 15: 3, Phase 16: 4, Phase 17: 5)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-14*
*Last updated: 2026-07-14 — roadmap created (3 phases: 15 Cash Ledger Foundation, 16 Manual Cash Movements & History, 17 Financial Reports/Export & Dashboard Analytics). FIN-10/11/12 (profit + stock valuation) grouped into Phase 17 alongside FIN-08/09 rather than Phase 16, since both are read-only period/point-in-time aggregation queries reusing existing report infrastructure, distinct in nature from Phase 16's write-path/manual-entry UI work.*
