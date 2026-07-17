---
phase: 21-customer-profiles-purchase-insights
plan: 05
subsystem: ui
tags: [fastapi, jinja2, htmx, xss-guard, customer-profiles, purchase-insights]

# Dependency graph
requires:
  - phase: 21-customer-profiles-purchase-insights (Plan 03)
    provides: spend_view/favorite_products/last_order_date read services (CUST-06/07/08)
  - phase: 21-customer-profiles-purchase-insights (Plan 04)
    provides: contacts_by_kind read path + contact edit surface proven end-to-end (CUST-01..05)
affects: []
provides:
  - "customer_detail.html final shape: Контакты -> Покупки -> Любимые товары -> История покупок"
  - "customer_detail route context: contacts, last_order_iso, spend, favorites"
  - "CONTACT_KINDS Jinja global (app/routes/__init__.py)"
  - "partials/customer_contacts.html, partials/customer_insights.html, partials/favorite_products.html"
  - "e2e proof: zero-order profile renders zeros/dashes never None; stored social XSS renders escaped and non-clickable; repo-wide | safe ban mechanically enforced"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Contact values render only as a label -> comma-joined-values <p> line, never a table and never an anchor — the phase's one security control (Contact Values Are NOT Clickable)"
    - "Money/date docstring self-grep pitfall (from Plans 03/04) recurred here: explanatory prose in a new template's own docstring can trip that same template's literal-grep acceptance criteria (safe/href/tel/mailto/title=/error/negative/pagination) — reworded around the banned substrings each time, same fix pattern as before"

key-files:
  created:
    - app/templates/partials/customer_contacts.html
    - app/templates/partials/customer_insights.html
    - app/templates/partials/favorite_products.html
  modified:
    - app/routes/__init__.py
    - app/routes/customers.py
    - app/templates/pages/customer_detail.html
    - tests/test_customers.py

key-decisions:
  - "Collapsed the 'Последний заказ:' <p> onto a single line (was split across a template line break) so the rendered zero-order dash state matches the UI-SPEC's verbatim copy 'Последний заказ: <span class=\"muted\">—</span>' exactly — found by the plan's own e2e assertion, not a pre-existing bug."
  - "Docstring explanatory text in all three new partials had to avoid literally containing the substrings the plan's own acceptance-criteria greps check for (safe, href/tel/mailto, title=, cents/100 or float, error/negative, pagination/показать ещё) — same self-grep pitfall documented in Plans 03/04, reworded each time to keep the identical rationale without the banned literal token."

requirements-completed: [CUST-01, CUST-02, CUST-03, CUST-04, CUST-05, CUST-06, CUST-07, CUST-08]

# Metrics
duration: ~50min
completed: 2026-07-17
---

# Phase 21 Plan 05: Customer Contacts + Purchase Insights Detail Page Summary

**The customer detail page now shows every recorded contact and address as plain autoescaped text, the last order date, three calendar-period spend tiles (net of returns), and a top-10 favorites table — with a zero-order profile rendering full-page zeros/dashes (never `None`) and a stored `<script>`/`javascript:` social link proven to render escaped and non-clickable end-to-end.**

## Performance

- **Duration:** ~50 min
- **Completed:** 2026-07-17
- **Tasks:** 3/3 completed
- **Files modified:** 7 (3 created)

## Accomplishments

- `CONTACT_KINDS` registered as a Jinja global (`app/routes/__init__.py`), alongside the existing `WRITEOFF_REASONS`/`CASH_CATEGORIES` pattern; the three pre-existing filters (`local_dt`, `cents`, `ru_date`) were left untouched.
- `customer_detail` route context extended with `contacts`, `last_order_iso` (derived from the already-loaded `history`, zero extra queries), `spend`, and `favorites` — zero date math in the route itself (`_period_starts` never called there).
- `partials/customer_contacts.html` (CUST-01..05): one `Label: value, value` line per contact kind that has at least one value, iterated in `CONTACT_KINDS` order (phone → telegram → email → social); the address renders on its own line; a bare profile shows `Контакты не указаны.`; every value is plain autoescaped text — no anchor, no `tel:`/`mailto:`/`https://`, no `| safe` anywhere.
- `partials/customer_insights.html` (CUST-06/07): last order date as one `<p>` line above three `.metric-grid` tiles (Потрачено за месяц/квартал/год), each with a `с {{ start_iso | ru_date }}` caption — `start_iso` is a `str` from `spend_view`, closing the real `TypeError` risk from a `date` object reaching `| ru_date`. The mandatory `С учётом возвратов.` line renders once, always visible, never a tooltip. Money renders only via `| cents`, never sign-colored.
- `partials/favorite_products.html` (CUST-08): top-10 ranked table (Товар / Покупок, раз / Куплено, шт.), empty state reuses `Покупок пока нет.` verbatim from the purchase-history partial so a zero-order profile says the same thing in both sections; no pagination, no links, no soft-delete special-casing.
- `customer_detail.html` final section order: Контакты → Покупки → Любимые товары → История покупок, matching the UI-SPEC's identity → reachability → value → drill-down rationale.
- 9 new e2e/mechanical tests: contacts render-all/omit-empty/empty-state (Task 1); insights render-all-blocks/section-order/`| ru_date` caption guard (Task 2); zero-order profile renders zeros not `None`, stored-XSS render guard on both detail and edit surfaces, and a repo-wide `| safe` ban across all 6 Phase 21 templates (Task 3).
- Full 808-test suite green — the Wave 4 / phase gate.

## Task Commits

Each task was committed atomically:

1. **Task 1: customer_detail route context + CONTACT_KINDS global + Контакты section (CUST-01..05)** - `831b999` (feat)
2. **Task 2: Покупки + Любимые товары sections (CUST-06, CUST-07, CUST-08)** - `33de979` (feat)
3. **Task 3: Zero-order profile + stored-XSS e2e guards (the phase's two named bugs)** - `6e1ced8` (test)

_Worktree mode: STATE.md/ROADMAP.md are updated centrally by the orchestrator after merge — no separate plan-metadata commit was made here._

## Files Created/Modified

- `app/routes/__init__.py` — `CONTACT_KINDS` imported and registered as a Jinja global; the 3 existing filters left unchanged
- `app/routes/customers.py` — `customer_detail` context gains `contacts`, `last_order_iso`, `spend`, `favorites`; imports extended from `app.services.customers`
- `app/templates/partials/customer_contacts.html` (new) — Контакты section body: label → values list + address, RU empty state, plain autoescaped text only
- `app/templates/partials/customer_insights.html` (new) — Покупки section body: last order date + 3 spend tiles + mandatory net-of-returns line
- `app/templates/partials/favorite_products.html` (new) — Любимые товары ranked table, capped at 10, no pagination
- `app/templates/pages/customer_detail.html` — new sections `id="customer-contacts"`, `id="customer-insights"`, `id="customer-favorites"`; existing `id="customer-history"` moved last
- `tests/test_customers.py` — 9 new `test_web_`/mechanical tests across the three tasks; `re`, `datetime.UTC`/`datetime`, and `pathlib.Path` added to imports

## Decisions Made

- Kept Task 1/Task 2/Task 3 as three separate atomic commits exactly per the plan's task boundaries, even though the templates are tightly coupled (`customer_detail.html`'s final section order only exists after Task 2) — matches the precedent set by Plans 03/04's own atomic-commit splitting.
- The `Последний заказ:` line-break fix (found while writing Task 3's own zero-order assertion) was applied as a small in-place edit to the Task-2-created file and committed as part of Task 3's commit, documented below as a deviation rather than silently folded in.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `customer_insights.html`'s "Последний заказ:" line broke the UI-SPEC's verbatim zero-order copy**
- **Found during:** Task 3 — writing `test_web_customer_detail_empty_profile_renders_zeros`, which asserts the exact substring `Последний заказ: <span class="muted">—</span>` appears in the body.
- **Issue:** The Task 2 template wrote the `<p>` across two lines (`Последний заказ:` then a newline-indented `{% if %}...{% endif %}` on the next line), which Jinja renders with the literal newline and leading whitespace preserved between the label and the value — so the rendered output was `Последний заказ:\n  <span class="muted">—</span>` instead of the UI-SPEC's single-line copy, and the exact-substring assertion failed.
- **Fix:** Collapsed the `<p>` onto one line: `<p>Последний заказ: {% if last_order_iso %}...{% else %}<span class="muted">—</span>{% endif %}</p>`.
- **Files modified:** `app/templates/partials/customer_insights.html`
- **Verification:** `test_web_customer_detail_empty_profile_renders_zeros` and both other `-k web_customer_detail_insights` tests pass; full suite re-run green.
- **Committed in:** `6e1ced8` (Task 3 commit).

**2. [Rule 1 - Bug] Docstring explanatory text in all three new partials self-failed their own literal-grep acceptance criteria**
- **Found during:** Tasks 1-2 acceptance-criteria verification — the plan's own `grep -c "<a \|href=\|tel:\|mailto:"`, `grep -c "title="`, `grep -c "cents/100\|/ 100\|float"`, `grep -c "error\|b91c1c\|negative"`, and `grep -c "pagination\|показать ещё"` checks each returned 1-2 instead of the required 0, because my first-draft docstrings explained the security/formatting rules by naming the exact banned patterns in prose (e.g. "no `<a href>`, no `tel:`", "never a `title=` tooltip", "no pagination"). This is the identical self-grep pitfall Plans 03 and 04 documented hitting for `strftime`/`dateutil`/`date.today()`/`deleted_at` and the literal word "safe".
- **Fix:** Reworded all affected docstring passages to convey the same rationale without containing the literal banned substrings (e.g. "no clickable anchor of any kind" instead of naming `<a href>`/`tel:`/`mailto:`; "always visible plain text, never a hover-only hint" instead of `title=`; "no other arithmetic-to-string conversion" instead of `cents/100`/`float`; "below-zero total ... gets no special text color" instead of "negative"/"error"; "no further-navigation chrome of any kind" instead of "pagination").
- **Files modified:** `app/templates/partials/customer_contacts.html`, `app/templates/partials/customer_insights.html`, `app/templates/partials/favorite_products.html`
- **Verification:** All affected `grep -c` acceptance-criteria commands now return `0`; the actual rendered behavior (no anchors, no tooltips, no sign-coloring, no pagination chrome) was correct from the first draft — only the explanatory comments' wording changed.
- **Committed in:** `831b999` (Task 1, `customer_contacts.html`) and `33de979` (Task 2, `customer_insights.html`/`favorite_products.html`).

---

**Total deviations:** 2 auto-fixed (1 copy/rendering bug, 1 documentation-only correctness fix across 3 files). No scope creep — both fixes keep the plan's own acceptance criteria and the UI-SPEC's verbatim copy intact.

## Issues Encountered

None beyond the deviations above.

## Known Stubs

None — every context key the templates read (`contacts`, `last_order_iso`, `spend`, `favorites`) is wired to the real Plan 02/03 service functions; nothing renders from a hardcoded/mock value.

## Threat Flags

None — every threat this plan's `<threat_model>` names (T-21-01, T-21-22, T-21-23, T-21-24, T-21-25, T-21-17) is addressed by the implementation and mechanically verified: `test_web_contacts_social_renders_escaped_not_as_href` (T-21-01), `test_customer_templates_never_use_safe_filter` (T-21-22), the `cents/100|float` grep (T-21-23), `test_web_customer_detail_insights_ru_date_captions_render` (T-21-24), and `test_web_customer_detail_empty_profile_renders_zeros` (T-21-25). No new network endpoints, auth paths, or schema changes were introduced.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- CUST-01..08 (all 8 requirements of Phase 21) are now shipped end-to-end: contacts/address record + display, purchase insights (last order, spend tiles, favorites) all render on `customer_detail.html`.
- The phase's two named failure modes (the `| ru_date` `TypeError` on a `date` object, and `None` reaching a zero-order template) are both closed structurally and proven by e2e tests, not just by code review.
- Full 808/808 test suite is green (Wave 4 / phase gate); `ruff check`/`ruff format --check` clean on every file this plan touched. Whole-repo `ruff check` still shows the 2 pre-existing, out-of-scope line-length findings in `app/routes/dictionary.py`/`app/routes/products.py` already logged by Plan 03's deferred-items.md — left untouched per the executor's scope-boundary rule.
- No further service-layer or route work is anticipated for Phase 21 — this was the phase's final plan (Plan 05 of 5).

---
*Phase: 21-customer-profiles-purchase-insights*
*Completed: 2026-07-17*
