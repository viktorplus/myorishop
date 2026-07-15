---
status: diagnosed
trigger: "UAT Phase 17 Test 2 gap: user reported 'все хорошо но ненащел точку входа на эту страницу начиная с главной' (CSV export works, but no navigation entry point found from the main page)"
created: 2026-07-15T00:00:00Z
updated: 2026-07-15T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED (revised from initial) — the link to /finance/report is NOT missing from the codebase; it exists in 3 separate places (desktop /finance dashboard, desktop /reports landing page, mobile /m/finance dashboard), but in every case it is a plain inline `<p><a>` text link buried inside a dense page, one navigation hop below the top-level nav, with a label ("Отчёт по кассе за период" / "Движения кассы") that never says "export"/"CSV"/"скачать" — a discoverability/prominence gap, not a missing-link gap.
test: n/a — root cause confirmed via full template read of all reachable paths from main page (desktop nav, mobile home tile grid, finance dashboards, reports landing page) plus CSS check confirming no hiding/visibility bug.
expecting: n/a
next_action: n/a — diagnosis complete, goal is find_root_cause_only, returning report.

## Symptoms

expected: A CSV export/report page (/finance/report and /m/finance/report) should be reachable via a visible navigation link starting from the main page of the app.
actual: User could not find an entry point to the report page starting from the main page.
errors: None reported
reproduction: Test 2 in UAT (.planning/phases/17-financial-reports-export-dashboard-analytics/17-UAT.md) — starting from the app's home/main page, try to navigate to the finance report/export page without typing the URL directly.
started: Discovered during UAT of Phase 17

## Eliminated

- hypothesis: "/finance link is missing from the desktop top nav entirely"
  evidence: app/templates/base.html line 39 has `<a href="/finance">Финансы</a>` unconditionally rendered in the shared nav (inherited by every desktop page including home.html).
  timestamp: 2026-07-15

- hypothesis: "/m/finance link is missing from the mobile home tile grid"
  evidence: app/templates/mobile_pages/home.html line 14 has `<a class="mobile-tile" href="/m/finance">Финансы</a>` unconditionally rendered in the main mobile tile grid.
  timestamp: 2026-07-15

- hypothesis: "link exists on desktop but not on mobile (or vice versa)"
  evidence: Both pages/finance.html (line 10) and mobile_pages/finance.html (line 15) contain an unconditional `<a href="/finance/report">` / `<a href="/m/finance/report">` link. Symmetric on both surfaces.
  timestamp: 2026-07-15

- hypothesis: "link is present in markup but CSS hides it or makes it visually identical to plain text"
  evidence: app/static/style.css line 37-39: generic `a { color: #2563eb; }` (blue) applies globally; no `display:none`/`visibility:hidden`/`opacity:0` rule targets this link or its container. The link renders as a normal visible blue hyperlink.
  timestamp: 2026-07-15

## Evidence

- timestamp: 2026-07-15
  checked: app/templates/base.html (desktop shared nav, inherited by home.html)
  found: Top-level nav includes `<a href="/finance">Финансы</a>` (line 39) but NO direct top-level nav item for `/finance/report`.
  implication: /finance (dashboard) is one click from Главная; /finance/report requires a second hop through the dashboard page.

- timestamp: 2026-07-15
  checked: app/templates/pages/finance.html (desktop /finance dashboard)
  found: Line 10: `<p><a href="/finance/report">Отчёт по кассе за период</a></p>` — a single plain-text paragraph link, positioned between the `#finance-metrics` tiles block (above) and a large `<h1>Баланс кассы</h1>` section with balance + withdraw/deposit forms + history (below). Not styled as a button/CTA (no `class="button"` per style.css lines 168-179), just a normal inline `<a>`.
  implication: Link exists and works, but has low visual weight compared to surrounding page elements (H1 headings, forms, tile grid) — easy to scan past on a dense dashboard page. Label text does not use "export"/"CSV"/"скачать" wording that would match the tester's mental model of "CSV export" from the UAT script.

- timestamp: 2026-07-15
  checked: app/templates/mobile_pages/finance.html (mobile /m/finance dashboard)
  found: Line 15, structurally identical to desktop: `<p><a href="/m/finance/report">Отчёт по кассе за период</a></p>` sandwiched between metrics tiles and `<h1>Баланс кассы</h1>`. Same low-prominence placement mirrored on mobile.
  implication: Same discoverability gap exists on both surfaces — this is not a desktop/mobile asymmetry, it's a consistent placement pattern across both.

- timestamp: 2026-07-15
  checked: app/templates/pages/reports_landing.html (desktop /reports, reached via nav "Отчёты")
  found: Line 5: single comma/middle-dot-separated line of 6 links including `<a href="/finance/report">Движения кассы</a>` (labeled "cash movements", not "report" or "export"), alongside Продажи и прибыль, Остатки склада, Списания, Топ и залежавшиеся товары, Сроки годности.
  implication: A SECOND working path to /finance/report exists via the "Отчёты" nav item — but it uses yet another label ("Движения кассы") different from the one used on the finance dashboard ("Отчёт по кассе за период"), and it's visually just one link among 6 in a single dense paragraph, no visual separation.
  found_also: There is no mobile equivalent of reports_landing.html (no mobile_pages/reports_landing.html) — mobile users only have the /m/finance dashboard path to reach /m/finance/report.

- timestamp: 2026-07-15
  checked: app/templates/mobile_base.html (mobile shared shell)
  found: Unlike base.html, mobile_base.html has NO persistent nav bar — only a `{% block back %}<a class="mobile-back" href="/m/">← Главная</a>{% endblock %}` back-link. All mobile navigation is driven entirely through the tile grid on mobile_pages/home.html; there is no secondary/global nav surface on mobile at all.
  implication: On mobile there is exactly one route into the finance area (the "Финансы" tile) and from there the tester must locate the small in-page text link — no alternate path like desktop's /reports landing page exists on mobile.

- timestamp: 2026-07-15
  checked: app/static/style.css (global link/nav/button styles, lines 1-50, 160-201, 290-340)
  found: Plain `<a>` tags get `color: #2563eb` (blue, distinguishable from body `#222`), no underline removal outside `nav a`. `.mobile-tile` (line 296-300) gets full button/card treatment: `font-size:16px; font-weight:600; text-decoration:none` in a bordered/padded grid tile. The report link uses neither `.mobile-tile` nor `.button` classes — it is a bare inline text link.
  implication: The link is technically visible (not hidden via CSS) but has categorically lower visual prominence than every other primary navigation affordance in the app (nav items, mobile tiles, `.button` CTAs all get distinct box/weight treatment; this link gets none).

## Resolution

root_cause: |
  The navigation entry point to /finance/report and /m/finance/report is NOT absent from the
  codebase — it exists in three places (desktop pages/finance.html, desktop pages/reports_landing.html,
  mobile mobile_pages/finance.html). The root cause of the UAT gap is a DISCOVERABILITY/PLACEMENT
  problem, not a missing link:

  1. No top-level nav item (desktop `<nav>` in base.html, or mobile tile grid in mobile_pages/home.html)
     points directly at /finance/report or /m/finance/report. Both entry points require a second hop
     through an intermediate page (/finance dashboard or /reports landing).
  2. On both the desktop /finance dashboard and the mobile /m/finance dashboard, the report link is a
     single plain inline `<p><a>` (app/templates/pages/finance.html:10,
     app/templates/mobile_pages/finance.html:15) with no `.button`/`.mobile-tile` styling, positioned
     between the metrics-tiles block and a visually heavier `<h1>Баланс кассы</h1>` section with forms —
     making it easy to visually skip on a page already dense with metrics, balance, two forms, and history.
  3. The link's label text ("Отчёт по кассе за период" on the finance dashboard, "Движения кассы" on the
     reports landing page) never uses "export"/"CSV"/"скачать" wording, so a tester scanning for a
     "CSV export" entry point (per the UAT script's own phrasing) has a label mismatch working against them.
  4. Mobile has no secondary nav surface at all (mobile_base.html has no persistent nav, only a back link),
     so mobile users have exactly one path in (the "Финансы" tile) — unlike desktop, which has two paths
     (via "Финансы" nav item, and via "Отчёты" nav item) but both suffer the same low-prominence,
     inconsistent-labeling issue.
fix: (not applied — goal is find_root_cause_only)
verification: (not applicable — no fix applied)
files_changed: []
