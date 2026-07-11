---
status: testing
phase: 08-warehouses
source: [08-VERIFICATION.md]
started: 2026-07-11T08:00:00Z
updated: 2026-07-11T08:00:00Z
---

## Current Test

number: 1
name: Seeded default warehouse shows on first load
expected: |
  Page loads with one active warehouse row already present, no empty state.
awaiting: user response

## Tests

### 1. Seeded default warehouse shows on first load
expected: Start `uv run uvicorn app.main:app --port 8000`, open http://localhost:8000/warehouses. Confirm the seeded «Склад по умолчанию» row shows on first load with no setup step. Page loads with one active warehouse row already present, no empty state.
result: [pending]

### 2. Add warehouse with name only (no address)
expected: Add a warehouse with only a name (no address); confirm it appears in the list. New row appears with blank address cell, no page navigation.
result: [pending]

### 3. Delete a non-last warehouse (native confirm dialog)
expected: Delete a NON-last warehouse; confirm native browser confirm dialog appears, then the row goes muted with a Восстановить button and no page navigation.
result: [pending]

### 4. Delete the last active warehouse (inline warn-then-confirm)
expected: Delete the LAST remaining active warehouse; confirm the inline «Это последний активный склад» warning renders with zero navigation, then click «Удалить всё равно» to complete the delete.
result: [pending]

### 5. Restore a deleted warehouse
expected: Click Восстановить on a deleted row; confirm it returns to active styling with a Удалить button again.
result: [pending]

### 6. Nav link visible and active across pages
expected: Confirm the Склады nav link is visible and marked active on /warehouses from every other page in the app.
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
