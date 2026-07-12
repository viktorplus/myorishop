---
status: diagnosed
phase: 11-dedicated-mobile-flow
source: [11-VERIFICATION.md]
started: 2026-07-13T00:00:00Z
updated: 2026-07-13T02:20:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Phone-width auto-redirect from / to /m/
expected: Open the app in a real browser (or devtools responsive mode) at <600px viewport width and navigate to / — browser auto-redirects to /m/ (the mobile home tile grid)
result: pass

### 2. Redirect scope does not break desktop-only pages
expected: At a desktop-width viewport (>=600px), navigate to / and confirm no redirect occurs; separately, at a phone-width viewport, navigate directly to /customers, /backup, /dictionary, /warehouses, /categories, /export and confirm none of them silently bounce to /m/
result: pass

### 3. All 8 home tiles reach their mapped screens
expected: On a phone-width browser (or emulator), tap each of the 8 home tiles from /m/ and confirm each reaches its mapped screen — Продажа -> /m/sales, Приход -> /m/receipts, Поиск -> /m/search, Списание -> /m/writeoff, Корректировка -> /m/corrections, Перемещение -> /m/transfers, История -> /m/history, Сроки годности -> /m/reports/expiry
result: pass

### 4. Batch cards show all fields with no truncation at phone width
expected: At a batch-selection step (Sale/Write-off/Correction/Transfer) for a product with 2+ open batches, visually confirm every card shows price, expiry, remaining quantity, and comment with no truncation and no "expand to see more" interaction
result: issue
reported: "Bug A: batch card text is white-on-white — only readable on mouse hover (no hover exists on a real touch phone, so text is effectively invisible). Bug B: clicking 'Далее' on the batch step without selecting a batch advances to the qty/price step; clicking 'Назад' from there returns to the product step showing the code already filled in, but the batch-selection cards are gone — only the code field remains, no way to get back to batch selection without re-entering the code."
severity: blocker

### 5. Wizards feel thumb-operable, one action per screen
expected: Walk through each wizard (Sale, Receipt, Write-off, Correction, Transfer) on a real phone or emulator, confirming one action per screen, 44px+ tap targets, and thumb-operability
result: pass

### 6. Desktop pages remain visually unchanged
expected: At desktop width (>=600px), spot-check the category page, batch picker, transfer form, expiry report, and other pre-existing pages for pixel-for-pixel visual parity with pre-Phase-11 screenshots/memory
result: pass

## Summary

total: 6
passed: 5
issues: 1
pending: 0
skipped: 0
blocked: 0

## Previous Session (server was stale — see debug sessions for diagnosis)

- Test 1: issue (blocker) — /m/ 404. Root cause: stale server, no --reload, router wiring committed but not picked up. debug_session: .planning/debug/mobile-router-404.md
- Test 2: issue (major) — /transfers redirected to mobile at desktop width. Root cause inconclusive as code defect; leading hypothesis was stale mobile session. debug_session: .planning/debug/transfers-desktop-mobile-redirect.md
- Test 6: issue (major) — same as Test 2
- Tests 3, 4, 5: blocked (depended on /m/ working)
- Server has since been restarted (2026-07-13T01:30) and /m/, /m/sales, /transfers all verified returning HTTP 200 via curl. Re-testing all 6 from scratch below.

## Resolved (previous session — confirmed fixed on re-test, no code change needed)

- Test 1 (/m/ 404), Test 2 (/transfers redirect), Test 6 (transfer form redirect): all caused by a stale dev server process not picking up the mobile-router-wiring commit (run.bat has no --reload). Server restarted 2026-07-13T01:30; all three re-tested and now pass. debug_sessions: .planning/debug/mobile-router-404.md, .planning/debug/transfers-desktop-mobile-redirect.md

## Gaps

- truth: "Every batch card at the batch-selection step must show price, expiry, remaining quantity, and comment legibly at phone width, without requiring mouse hover"
  status: failed
  reason: "User reported: batch card text is white-on-white — only readable on mouse hover; no hover exists on a real touch phone, so the text is effectively invisible in normal use"
  severity: blocker
  test: 4
  root_cause: "app/static/style.css: .mobile-card (lines 270-274) overrides the base button rule's background to white but never overrides its color: #ffffff (set at line 146 on the generic button, a.button rule). Batch cards render as <button class=\"mobile-card\"> (app/templates/mobile_partials/batch_card_picker.html:40-48 and transfers_step_batch.html:20-37), so they inherit white text on a white background. Text only appears on :hover because button:hover (lines 154-158) darkens the background with no matching color change. The codebase's own button.secondary variant (lines 160-164) shows the correct pattern — pairing a light background override with a matching dark color override — which .mobile-card is missing. Affects both the Sale and Transfer wizards' batch steps."
  artifacts:
    - path: "app/static/style.css"
      issue: ".mobile-card rule (~line 270) missing a color override, inherits white text from base button rule"
  missing:
    - "Add an explicit color declaration to .mobile-card (e.g. matching button.secondary's #222) so it doesn't inherit the primary button's white text"
    - "Verify .mobile-card:hover and .mobile-card.selected states keep readable contrast once the base color is fixed"
  debug_session: .planning/debug/mobile-batch-card-white-on-white.md

- truth: "The batch-selection step (or a way back to it) must remain reachable via the wizard's Назад control without losing entered product context"
  status: failed
  reason: "User reported: clicking Далее on the batch step without selecting a batch advances to qty/price; clicking Назад from there returns to the product step with the code still filled in, but the batch cards are gone — only the code field remains, no way back to batch selection without re-entering the code"
  severity: major
  test: 4
  root_cause: "app/templates/mobile_partials/sale_step_qty_price.html (Назад button, lines 23-25) is wired to the same POST /m/sales/step/product with back=1 as the batch step's own Назад button, instead of routing back to GET /m/sales/step/batch (app/routes/mobile_sales.py:127-164), which already correctly re-runs open_batches and re-renders the batch cards fresh. The back==\"1\" branch in mobile_sale_step_product (mobile_sales.py:63-70) unconditionally re-renders step 1 regardless of which step the click came from, so step 3's Назад always skips step 2. 11-UI-SPEC.md:119 requires Назад to return to 'the previous step' — this is a genuine wiring bug, not an intentional design choice (confirmed by 11-04-SUMMARY.md Deviation #3, which self-documents this as an ad-hoc, unreviewed, untested addition)."
  artifacts:
    - path: "app/templates/mobile_partials/sale_step_qty_price.html"
      issue: "Назад button (lines 23-25) targets the wrong endpoint for its position in the wizard (step 3 -> step 1 instead of step 3 -> step 2)"
    - path: "app/routes/mobile_sales.py"
      issue: "mobile_sale_step_product's back==1 branch (lines 63-70) doesn't distinguish step-2-origin vs step-3-origin back navigation"
  missing:
    - "Wire the qty-price step's Назад to GET /m/sales/step/batch when a batch step was actually shown for the current code (not the dictionary-only path, which skips batch selection entirely)"
    - "Add a marker/flag so qty-price's Назад can distinguish 'came from batch step' vs 'came directly from product step' (dictionary-only match)"
  debug_session: .planning/debug/mobile-sale-back-nav-loses-batch-step.md
