---
phase: 24-navigation-restructure-settings
verified: 2026-07-17T23:30:00Z
status: gaps_found
score: 5/6 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Every secondary action is reachable from the page it belongs to — on desktop and mobile alike (phase goal, D-11)"
    status: failed
    reason: "Removing the old mobile home tile grid (D-10) deleted the only mobile navigation path to /m/search (Поиск), /m/corrections (Корректировка), and /m/transfers (Перемещение). The D-11-mandated replacement — the new mobile Товары toolbar — only ships Приход/Списание/Категории/Справочник/Каталоги; Перемещение is omitted even though 24-CONTEXT.md D-11 explicitly names it. Поиск and Корректировка have no D-decision authorizing their removal at all. All three routes still return 200 by direct URL, but no rendered link in the shipped mobile UI (tabbar, /m/, /m/products toolbar, /m/products cards, /m/customers, /m/finance) points to any of them. Confirmed by reading mobile_base.html, mobile_partials/products_toolbar.html, mobile_pages/products.html, mobile_pages/home.html, mobile_pages/customers.html, mobile_pages/finance.html, and tests/test_mobile_wiring.py (test_every_mobile_tile_path_is_reachable only asserts 200-by-direct-URL, never rendered-link presence). Matches code review finding CR-01 (24-REVIEW.md), which remains open — no follow-up plan or commit addresses it."
    artifacts:
      - path: "app/templates/mobile_partials/products_toolbar.html"
        issue: "D-11 mobile toolbar mirror omits Перемещение from the Действия group despite D-11 explicitly listing it"
      - path: "app/templates/mobile_pages/products.html"
        issue: "Mobile product cards have no per-row action (no mirror of desktop product_rows.html's «Переместить» link)"
      - path: "app/templates/mobile_pages/home.html"
        issue: "10-tile grid removed (D-10, correct) but no replacement link added anywhere for Поиск or Корректировка"
    missing:
      - "Add a Перемещение entry to mobile_partials/products_toolbar.html's Действия group (href=\"/m/transfers\"), per D-11's explicit wording"
      - "Either add a discoverable mobile entry point for Поиск and Корректировка, or record an explicit operator-approved D-decision in 24-CONTEXT.md that these two are intentionally desktop-only (matching the rigor already applied to D-12 for Настройки)"
      - "Add a rendered-link assertion test (not just direct-URL 200 checks) so this class of regression fails CI next time — see 24-REVIEW.md WR-01 for a concrete example"
human_verification: []
---

# Phase 24: Navigation Restructure & Settings Verification Report

**Phase Goal:** The top-level nav shows only first-class pages, and every secondary action is reachable from the page it belongs to — on desktop and mobile alike.
**Verified:** 2026-07-17T23:30:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Top-level desktop nav shows exactly 8 items: Главная, Товары, Продажи, Покупатели, История, Отчёты, Финансы, Настройки | ✓ VERIFIED | `app/templates/base.html:35-42` — exactly these 8 `<a>` tags, no others |
| 2 | Operator reaches Приход, Списание, Справочник from Товары page; Перемещение from product context (desktop) | ✓ VERIFIED | `app/templates/partials/products_toolbar.html` (Приход/Списание/Категории/Справочник/Каталоги, always-visible toolbar); `app/templates/partials/product_rows.html:64` — `<a href="/transfers?code={{ product.code }}">Переместить</a>` per row |
| 3 | Operator reaches Склады и Резервные копии from /settings; Экспорт from /backup | ✓ VERIFIED | `app/templates/pages/settings.html:4-14` (Склады, Резервные копии, Экспорт кассы links + summaries); `app/templates/pages/backup.html:16-19` (3 CSV export links embedded, D-07) |
| 4 | Every report detail page has a "Назад к отчётам" link to /reports | ✓ VERIFIED | `grep` confirms identical `<p><a href="/reports">← Назад к отчётам</a></p>` at line 3 of all 5: reports_sales.html, reports_writeoffs.html, reports_stock.html, reports_expiry.html, reports_products.html |
| 5 | Mobile navigation offers the same main tabs as desktop (7, excluding Настройки) | ✓ VERIFIED | `app/templates/mobile_base.html:31-39` — `nav.mobile-tabbar` with exactly Главная/Товары/Продажи/Покупатели/История/Отчёты/Финансы; `tests/test_mobile_wiring.py::test_mobile_home_lists_seven_tabbar_hrefs` passes and asserts `"Настройки" not in response.text` |
| 6 | Every secondary action is reachable from the page it belongs to — on desktop **and mobile alike** (phase goal wording, D-11) | ✗ FAILED | Mobile has no rendered path to `/m/search` (Поиск), `/m/corrections` (Корректировка), or `/m/transfers` (Перемещение) anywhere — see Gap below and code review CR-01 |

**Score:** 5/6 truths verified (5 roadmap Success Criteria all pass; the phase's own overarching goal statement — the "and mobile alike" clause — fails for 3 destinations)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/templates/base.html` | 8-item top nav | ✓ VERIFIED | Exactly 8 items, correct labels/hrefs/active-state |
| `app/templates/partials/products_toolbar.html` | Desktop Товары toolbar, 2 groups | ✓ VERIFIED | `.toolbar` > 2× `.toolbar-group` (Действия: Приход/Списание; Справочники: Категории/Справочник/Каталоги) |
| `app/templates/partials/product_rows.html` | Переместить row action | ✓ VERIFIED | Line 64, `href="/transfers?code={{ product.code }}"` |
| `app/routes/transfers.py` | `_resolve_transfer_lookup` + `?code=` prefill branch | ✓ VERIFIED WIRED | Function defined; `transfers_page` calls it when `code` present; unmatched code renders empty form (no 500, no echo) |
| `app/services/settings.py` | `settings_summary()` | ✓ VERIFIED WIRED | Composes `list_warehouses`/`list_backups`; used by `app/routes/settings.py` |
| `app/templates/pages/settings.html` | Настройки hub | ✓ VERIFIED | Склады + count, Резервные копии + last-backup date, Экспорт кассы link |
| `app/templates/pages/backup.html` | Embedded Экспорт section | ✓ VERIFIED | 3 CSV download links under `<h2>Экспорт</h2>` |
| `app/templates/pages/reports_*.html` (5 files) | Back-link | ✓ VERIFIED | All 5 confirmed |
| `app/templates/mobile_base.html` | `{% block tabbar %}` 7-tab nav | ✓ VERIFIED WIRED | Top-docked, sticky, `.active` state, excludes Настройки |
| `app/templates/mobile_partials/products_toolbar.html` | D-11 mobile toolbar mirror | ⚠️ STUB (partial) | Exists, renders 2 groups, but omits `Перемещение` — D-11 names it explicitly as an item that must live here |
| `app/templates/mobile_pages/home.html` | 10-tile grid removed | ✓ VERIFIED (removal) / ✗ regression (no replacement) | Grid gone (D-10 correct) but the grid was the sole nav path for 3 destinations, no replacement added |
| `app/templates/mobile_pages/products.html` | Mobile product list | ⚠️ ORPHANED action | No per-row action (no Перемещение mirror of desktop's `product_rows.html`) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `products_list.html` | `partials/products_toolbar.html` | `{% include %}` | ✓ WIRED | Confirmed via prior artifact check |
| `mobile_pages/products.html` | `mobile_partials/products_toolbar.html` | `{% include %}` | ✓ WIRED | `mobile_pages/products.html:5` |
| `partials/product_rows.html` | `app/routes/transfers.py` | `GET /transfers?code={{ product.code }}` | ✓ WIRED | Route accepts `code` query param and prefills |
| `app/routes/settings.py` | `app/services/settings.py` | `settings_summary(session, backup_dir)` | ✓ WIRED | Confirmed in service + route |
| `mobile_base.html` tabbar | `/m/products`, `/m/customers`, etc. | static `<a>` | ✓ WIRED | All 7 tab targets registered and return 200 (`test_every_preexisting_desktop_nav_route_still_returns_200`-style coverage for mobile) |
| Mobile UI (any page) | `/m/search`, `/m/corrections`, `/m/transfers` | rendered `<a>`/toolbar entry | ✗ NOT_WIRED | No such link exists in any shipped mobile template; routes are orphaned (reachable by direct URL only) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| NAV-01 | 24-01 | Приход nested under Товары | ✓ SATISFIED | Desktop toolbar |
| NAV-02 | 24-01 | Списание nested under Товары | ✓ SATISFIED | Desktop toolbar |
| NAV-03 | 24-01 | Справочник from Товары secondary menu | ✓ SATISFIED | Desktop toolbar |
| NAV-04 | 24-02 | Экспорт from Резервные копии page | ✓ SATISFIED | `backup.html` embedded CSV links |
| NAV-05 | 24-02 | Склады from Настройки | ✓ SATISFIED | `settings.html` |
| NAV-06 | 24-02 | Резервные копии from Настройки | ✓ SATISFIED | `settings.html` |
| NAV-07 | 24-04 | Перемещение as nested action from product context | ✓ SATISFIED (desktop) / ✗ not mirrored on mobile | `product_rows.html:64` (desktop). Requirement text doesn't name a platform, but the phase goal explicitly claims mobile parity — see gap above. |
| NAV-08 | 24-01 | Top nav reduced to first-class pages | ✓ SATISFIED | `base.html`, 8 items |
| RPT-01 | 24-03 | Back-link on every report detail page | ✓ SATISFIED | All 5 pages confirmed |
| MOB-01 | 24-05, 24-06 | Mobile nav offers same main tabs as desktop, excluding Настройки | ✓ SATISFIED (literal text) | 7-tab bar confirmed. Note: the phase's SUMMARY claims "MOB-01 is now fully satisfied" and treats this as fully closing mobile navigation — that framing overstates the outcome; MOB-01's literal wording (tab parity) is met, but it does not cover the D-11 secondary-action reachability the phase goal also promises. |

No orphaned requirements — every ID in REQUIREMENTS.md's Navigation/Reports/Mobile sections for Phase 24 is claimed by exactly one plan.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/templates/mobile_partials/products_toolbar.html` | 1-17 | Missing D-11-mandated item (Перемещение) | 🛑 Blocker | Drives the gap above |
| `app/templates/mobile_pages/products.html` | 9-14 | Bare `.mobile-card` divs, no action links | ⚠️ Warning | No mobile mirror of desktop's per-row Переместить action |
| `tests/test_mobile_products.py` | 1-27 | Toolbar hrefs never asserted (per code review WR-01) | ⚠️ Warning | This exact regression (missing Перемещение) would have been caught by an href-presence test; none exists |
| `app/templates/mobile_partials/products_toolbar.html` / `style.css:211-222` | — | Touch targets likely ≈42px, under the project's own 44px minimum (code review WR-02) | ⚠️ Warning | Not a must-have for this phase's stated success criteria; flagged for awareness only |
| `app/templates/base.html:41` | 41 | `/finance/report` (now reached via Настройки, D-08) still highlights Финансы as active, not Настройки (code review WR-03) | ⚠️ Warning | Minor "you are here" inconsistency, not a reachability failure |

No `TBD`/`FIXME`/`XXX` debt markers found in phase-modified files.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Desktop nav has exactly 8 items | grep count of `<a href=` inside `<nav>` in base.html | 8 matches, correct labels | ✓ PASS |
| All 5 report pages have identical back-link | grep across 5 files | 5/5 matches | ✓ PASS |
| Phase-relevant test suite passes | `uv run pytest tests/test_mobile_wiring.py tests/test_mobile_products.py tests/test_mobile_home.py tests/test_settings.py tests/test_reports.py tests/test_transfers.py -q` | 90 passed | ✓ PASS |
| No mobile template links to `/m/search`, `/m/corrections`, `/m/transfers` | grep across `app/templates/mobile_base.html`, `mobile_pages/*.html`, `mobile_partials/products_toolbar.html` | 0 outbound links found (routes only self-referenced from within their own flow) | ✗ FAIL — confirms CR-01 |

### Probe Execution

Not applicable — no `scripts/*/tests/probe-*.sh` files exist in this project and none are declared in the phase's PLAN/SUMMARY files. Skipped.

### Human Verification Required

None. The remaining gap (CR-01 / mobile reachability of Поиск, Корректировка, Перемещение) is fully verifiable by static template/route inspection — already done above — and does not require human judgment.

### Gaps Summary

5 of 5 ROADMAP.md Success Criteria pass literally as worded. However, the phase's own Goal statement is broader than the 5 enumerated criteria — it explicitly promises "every secondary action is reachable from the page it belongs to — on desktop **and mobile alike**." That promise is demonstrably false for three destinations:

- **Перемещение** (`/m/transfers`) — 24-CONTEXT.md's own D-11 decision explicitly lists this as an item that must be reachable from the mobile Товары toolbar (mirroring the desktop D-13 per-row action). The shipped `mobile_partials/products_toolbar.html` omits it.
- **Поиск** (`/m/search`) and **Корректировка** (`/m/corrections`) — no D-decision anywhere authorizes dropping these (unlike Настройки/Экспорт кассы, which D-12 explicitly and deliberately retires from mobile). They simply lost their only entry point when the old 10-tile home grid was deleted (D-10), and nothing replaced it.

This is not a cosmetic or discoverability nit — before this phase, all three were reachable from the mobile home grid; after this phase, they are reachable only by typing the URL directly. The routes still work (proven by `tests/test_mobile_wiring.py::test_every_mobile_tile_path_is_reachable`), but that test proves route registration, not UI reachability — it does not and cannot catch this regression, and none of the phase's other tests assert rendered-link presence for these three destinations.

This matches code review finding CR-01 (`24-REVIEW.md`) exactly, word for word in its root cause. No plan, commit, or CONTEXT.md addendum created after the review addresses it — it remains open.

**This looks like an execution gap, not an intentional deviation** — D-11 explicitly names Перемещение as in-scope for the mobile toolbar, so shipping without it contradicts the phase's own binding decision record rather than superseding it. No override is suggested; recommend a small closure plan (see `missing:` list in frontmatter) before this phase is considered complete.

---

_Verified: 2026-07-17T23:30:00Z_
_Verifier: Claude (gsd-verifier)_
