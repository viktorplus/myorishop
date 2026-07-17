---
phase: 24
slug: navigation-restructure-settings
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-17
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| **Quick run command** | `uv run pytest tests/test_<module>.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~seconds (existing suite runs fast per prior-phase memory notes) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_<touched_module>.py -x`
- **After every plan wave:** Run `uv run pytest` (full suite — this phase touches shared chrome: `base.html`/`mobile_base.html`; isolated module runs won't catch cross-file breakage)
- **Before `/gsd-verify-work`:** Full suite must be green, with special attention to the ~13 nav-presence tests enumerated below (expected red until explicitly updated)
- **Max feedback latency:** ~30 seconds (targeted run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 24-XX-01 | TBD | TBD | NAV-01/02/03 | — | Приход/Списание/Справочник reachable from Товары toolbar | web/integration | `uv run pytest tests/test_receipts.py tests/test_writeoffs.py tests/test_dictionary.py -x` | ✅ existing tests to UPDATE | ⬜ pending |
| 24-XX-02 | TBD | TBD | NAV-04 | — | Экспорт reachable from /backup | web/integration | `uv run pytest tests/test_export.py tests/test_backup.py -x` | ✅ existing, `test_web_nav_has_export_link` to UPDATE | ⬜ pending |
| 24-XX-03 | TBD | TBD | NAV-05/06 | T-24-01 (V5 input validation) | Склады/Резервные копии reachable from /settings | web/integration | `uv run pytest tests/test_settings.py -x` | ❌ W0 — new file | ⬜ pending |
| 24-XX-04 | TBD | TBD | NAV-07/D-14 | T-24-01 (V5 input validation) | Перемещение per-row action + `?code=` pre-fill | web/integration | `uv run pytest tests/test_transfers.py -x` | ✅ existing file, new cases to ADD | ⬜ pending |
| 24-XX-05 | TBD | TBD | NAV-08 | — | Top nav is exactly 8 items | web/integration | `uv run pytest tests/test_smoke.py -k nav -x` | ❌ W0 — new assertion | ⬜ pending |
| 24-XX-06 | TBD | TBD | RPT-01 | — | Back-link on every report detail page | web/integration | `uv run pytest tests/test_reports.py -k back -x` | ❌ W0 — 5 new assertions | ⬜ pending |
| 24-XX-07 | TBD | TBD | MOB-01 | — | Mobile tab bar has 7 tabs, excludes Настройки; new mobile Товары/Покупатели routes | web/integration | `uv run pytest tests/test_mobile_wiring.py tests/test_mobile_home.py tests/test_mobile_products.py tests/test_mobile_customers.py -x` | ⚠️ existing to REPLACE, 2 new files (W0) | ⬜ pending |

*Task IDs are placeholders — the planner assigns real plan/task IDs; update this table's Task ID/Plan/Wave columns after planning (or leave as a requirement→test map; per-task status is authoritative only once plans exist).*

---

## Wave 0 Requirements

- [ ] `tests/test_settings.py` — new file, covers NAV-05/06/D-06 (`/settings` route existence, warehouse-count summary, last-backup-date summary, links present)
- [ ] `app/routes/mobile_products.py` + `tests/test_mobile_products.py` — new mobile Товары tab (MOB-01)
- [ ] `app/routes/mobile_customers.py` + `tests/test_mobile_customers.py` — new mobile Покупатели tab (MOB-01)
- [ ] Update (not delete) the 13 nav-presence tests enumerated in 24-RESEARCH.md Pitfall 3 to assert the new reachability paths: `tests/test_dictionary.py:321`, `tests/test_warehouses.py:453`, `tests/test_writeoffs.py:286`, `tests/test_receipts.py:584`, `tests/test_export.py:330`, `tests/test_backup.py:267`, `tests/test_finance_reports.py:570/580/606`, `tests/test_mobile_home.py:28/41`, `tests/test_mobile_wiring.py:38`
- [ ] New back-link assertions in `tests/test_reports.py` (5 report detail pages, RPT-01)
- [ ] New assertions for D-13/D-14 transfer per-row action + pre-fill in `tests/test_transfers.py` and wherever `product_rows.html` output is already asserted

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Top-docked mobile tab bar visual/ergonomic feel | MOB-01 / D-09 | Deliberate deviation from bottom-tab convention — needs a human thumb/eye check on a real phone-width viewport, not just DOM assertions | Open `/m` on a mobile-width browser or device, confirm the tab bar is fixed at the top, doesn't overlap page content, and all 7 tabs are reachable by touch |
| Товары toolbar two-group visual grouping | NAV-01..03 / D-04 | "Grouped by meaning" layout intent is a visual/UX judgment, not a DOM assertion | Open `/products`, confirm the toolbar visually separates "Действия" (Приход/Списание/Перемещение-related) from "Справочники" (Категории/Справочник/Каталоги) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
