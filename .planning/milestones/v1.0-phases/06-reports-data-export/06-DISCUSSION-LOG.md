# Phase 6: Reports & Data Export - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 6-Reports & Data Export
**Areas discussed:** Period selection & local-day boundaries, Report page structure, Low-stock & stale-product thresholds, CSV export scope & format

---

## Period selection & local-day boundaries

| Option | Description | Selected |
|--------|-------------|----------|
| Presets + editable fields | Preset buttons (Сегодня/Неделя/Месяц) pre-fill editable «с/по» date fields; one code path | ✓ |
| Mode toggle | Radio «Пресет / Произвольный» switching between two input modes | |
| Two date fields only | Minimal code, no preset buttons, JS shortcuts only | |

**User's choice:** Presets + editable fields (recommended option).
**Notes:** Technical constraint noted regardless of choice: `operations.created_at` is UTC; day/week/month boundaries must be computed via local midnight (`ZoneInfo(settings.display_tz)`) converted to UTC, not by slicing the UTC string directly.

---

## Report page structure

| Option | Description | Selected |
|--------|-------------|----------|
| One dashboard | All report sections on one long scrolling page | |
| Separate pages per report | Own route/template/nav-link per report, matching existing project convention | ✓ |
| Tabbed single page | One page, HTMX partial-swap between report sections | |

**User's choice:** Separate pages per report (recommended option).
**Notes:** Stock/low-stock report (RPT-02) doesn't need a period selector at all, which argues against mixing it into a shared-period dashboard/tab layout.

---

## Low-stock & stale-product thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed in settings | Single global threshold for all products via config/settings | |
| Configurable per product | New field(s) on the product card, per-product override | ✓ |
| Hardcoded in code | No configurability | |

**User's choice:** Configurable per product (deviates from the recommended "fixed in settings" option).

**Follow-up 1 — does "залежался" (stale) get the same per-product treatment, or stay global?**
- Options: "Global for all products" (recommended) vs "Also per product".
- **User's choice:** Also per product — both `low_stock_threshold` and `stale_days` are per-product fields.

**Follow-up 2 — fallback when a product has no threshold set:**
- Options: "Global default fallback applies" (recommended) vs "No threshold — product excluded from the report".
- **User's choice:** Global default fallback applies — effective threshold = per-product value if set, else the global default from settings.

**Notes:** Requires a schema migration (new nullable `products` columns) plus corresponding global fallback settings in `app/config.py`.

---

## CSV export scope & format

| Option | Description | Selected |
|--------|-------------|----------|
| Three files on /export | Separate download buttons for products/sales/customers, dedicated page mirroring `/backup` | ✓ |
| One ZIP archive | Single "Export all" button, three CSVs zipped together | |
| Buttons on existing pages | Export buttons scattered on `/products`, `/reports`, `/customers` instead of a dedicated page | |

**User's choice:** Three files on a dedicated `/export` page (recommended option).
**Notes:** Must use `utf-8-sig` (BOM) encoding so Cyrillic names render correctly when opened in Excel — locked as a hard technical requirement regardless of UI choice.

---

## Claude's Discretion

- Exact URLs/route names and template/partial structure for each report page.
- Migration number and exact column names for the per-product threshold fields.
- Names/keys of the new global fallback settings.
- Sales/profit report layout details (per-line vs per-product vs period-total profit display).
- Top-selling ranking metric (units vs revenue vs profit) and lookback window; whether "stale" uses the period selector or is independent (recommended: independent, based on `stale_days` recency).
- Exact CSV column sets per entity export.
- RU UI text, empty-state and confirmation wording.

## Deferred Ideas

- Date-range filtering directly on `/history` — stays deferred; period reporting lives in the new `/reports/*` pages instead of a `/history` upgrade (resolves Phase 5's D-14 note).
- Combined ZIP export, single-dashboard layout, global-only thresholds — considered, not chosen.
- Purchase-frequency reminders / interested-customer lists (CST-V2-01/02) — later milestone.
- Multi-currency, multi-operator sync, user roles — out of scope per PROJECT.md.
