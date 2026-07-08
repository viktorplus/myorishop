---
status: testing
phase: 01-foundation-ledger-core
source: [01-VERIFICATION.md]
started: 2026-07-08T13:40:00Z
updated: 2026-07-08T13:40:00Z
---

## Current Test

number: 1
name: Оффлайн-запуск run.bat
expected: |
  Отключить сеть. Двойной клик run.bat — открывается браузер на http://127.0.0.1:8000.
  Страница показывает «Демо-товар». Корректировка +3 добавляет строку журнала без перезагрузки страницы (HTMX).
  После закрытия и повторного запуска run.bat данные сохранены.
awaiting: user response

## Tests

### 1. Оффлайн-запуск run.bat
expected: Браузер открывает 127.0.0.1:8000 без сети; корректировка +3 добавляет строку без перезагрузки; после рестарта данные на месте
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
