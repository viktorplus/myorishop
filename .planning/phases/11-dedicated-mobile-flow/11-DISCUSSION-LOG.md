# Phase 11: Dedicated Mobile Flow - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-12
**Phase:** 11-Dedicated Mobile Flow
**Areas discussed:** Entry point/routing, Mobile navigation, Operation step structure, Batch-selection screen

---

## Entry point / routing

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated `/m/...` URLs + auto-redirect by viewport | Separate routes, separate templates — desktop untouched; deep links to `/m/...` also work | ✓ |
| JS viewport-redirect without a URL namespace | Same URL serves mobile/desktop shell based on client-side width check | |
| Explicit "Mobile mode" link/banner on desktop | No auto-detection; operator opts in manually, optionally remembered via cookie | |

**User's choice:** Dedicated `/m/...` URLs with auto-redirect by viewport (recommended option).
**Notes:** None.

---

## Mobile navigation

| Option | Description | Selected |
|--------|-------------|----------|
| Home screen with operation tiles | `/m/` shows large tap targets for each operation; per-screen "Back" returns to home | ✓ |
| Persistent bottom tab bar | Always-visible 5-6 icon bar for switching operations without returning home | |
| Hamburger menu | Collapsible menu like desktop nav, adapted for touch | |

**User's choice:** Home screen with operation tiles (recommended option).
**Notes:** None.

---

## Operation step structure

| Option | Description | Selected |
|--------|-------------|----------|
| Step-by-step wizard, one screen per step | Find product → pick batch → enter qty/price → confirm; one action per screen | ✓ |
| Single scrollable form, simplified desktop layout | One page with all fields, secondary fields collapsed | |

**User's choice:** Step-by-step wizard with a dedicated screen per step (recommended option).
**Notes:** User's follow-up framing: single-screen scrollable form risks looking like the CSS-reflow approach the phase goal explicitly rejects.

---

## Batch-selection screen

| Option | Description | Selected |
|--------|-------------|----------|
| Full-width tap cards, all fields visible at once | Price, expiry, remaining qty, comment all shown per card; tap selects | ✓ |
| Compact list, comment hidden behind "more" | Price/expiry/qty visible in a compact row; comment/detail behind a tap | |

**User's choice:** Full-width tap cards with all fields visible (recommended option).
**Notes:** None.

---

## Claude's Discretion

- Exact tile layout/grid on the `/m/` home screen (icons, ordering, grouping)
- History browsing UI on mobile (filter set may be simplified vs. desktop)
- Transfer and expiry-report mobile screen layouts (not specifically discussed; build consistent with wizard/batch-card patterns above)
- Viewport-width breakpoint used for the phone-width auto-redirect

## Deferred Ideas

None — discussion stayed within phase scope.
