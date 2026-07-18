---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Multi-Operator Sync, Central Server & Roles
status: executing
stopped_at: v3.0 roadmap created (Phases 25-30), STATE + REQUIREMENTS traceability updated, ready to plan Phase 25
last_updated: "2026-07-18T05:56:54.835Z"
last_activity: 2026-07-18
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 8
  completed_plans: 2
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-18)

**Core value:** The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.
**Current focus:** Phase 25 — authentication-roles-user-attribution

## Current Position

Phase: 25 (authentication-roles-user-attribution) — EXECUTING
Plan: 4 of 8
Status: Ready to execute
Last activity: 2026-07-18

Progress: [███░░░░░░░] 25%

**v3.0 phase map (Phases 25-30):**

1. Phase 25 — Authentication, Roles & User Attribution (AUTH/USER/ROLE + RPT-01, 16 reqs) — local, testable first
2. Phase 26 — PostgreSQL Portability & Append-Only Parity (SRV-01/02)
3. Phase 27 — Shared Idempotent Merge Core (SYNC-02/03/04/05) — **research flag** (server-authoritative Tier-B conflict policy + `Product.code` collision rule)
4. Phase 28 — Central Server: Hosting & Sync API (SRV-04, SYNC-09)
5. Phase 29 — Online Client Sync (SYNC-01/06/07/08, SRV-03)
6. Phase 30 — Offline Self-Uploading File (OFF-01..07) — **research flag** (self-contained-file mechanism + trust/version model)

## Performance Metrics

**Velocity:**

- Total plans completed: 86 (v1.0-v2.0)
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1-24 (v1.0-v2.0) | 86 | - | - |
| 25-30 (v3.0) | TBD | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion. Per-plan v1.0-v2.0 timings archived with their milestones.*
| Phase 25 P01 | ~10min | 2 tasks | 5 files |
| Phase 25 P02 | ~8min | 3 tasks | 3 files |
| Phase 25 P03 | ~18min | 3 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table (v1.0-v2.0 milestone decisions archived there and in `.planning/RETROSPECTIVE.md`).

**v3.0 roadmap-level decisions (2026-07-18):**

- **Dependency-ordered build:** identity/auth first (locally testable, unblocks attribution) → prove one model set on PostgreSQL → harden the shared merge engine in isolation → server + sync API → online client sync → offline self-uploading file last. The shared idempotent merge engine (Phase 27) is built and hardened before either transport (Phases 29/30) — both are thin callers of one engine.
- **Operator revisions override research where they disagree:** mobile is server-only (SRV-04, no offline mobile install); the offline path is upload-only via a self-contained self-uploading file to a server with no app installed (OFF-01..07, not peer import); Tier-B mutable master-data conflict resolution is server-authoritative (SYNC-05).
- **RPT-01 placed in Phase 25** (attribution phase) alongside USER-06 — same operator-filter pattern, cleanest coverage.
- **Device identity** (per-install unique `device_id`, replacing the static `device-01` default) is a Phase 25 pre-flight for all later sync.
- [Phase ?]: Phase 25: secret_key + per-install device_id persisted under gitignored data/ outside synced DB; env overrides win
- [Phase ?]: Phase 25: author_id added via native op.add_column (never batch_alter_table) so append-only triggers survive; pre-auth rows stay NULL (no backfill)
- [Phase ?]: Phase 25-03: security core is pure-Python and unit-tested with the plain session fixture before any app wiring; author_fields() falls back to settings.operator_name so existing tests stay green

### Pending Todos

None yet.

### Coverage Gate Overrides

- **Phase 8 (2026-07-11):** The globally-installed `gsd-tools` on PATH (an older `gsd-sdk` build) flagged D-03, D-07, D-08, D-10 as "uncovered" via its `decision-coverage-plan` check. Re-ran the project's own `$HOME/.claude/gsd-core/bin/gsd-tools.cjs gap-analysis` (the up-to-date tool) which confirmed all 11 items (WH-01 + D-01..D-10) are covered — the older global binary's matcher choked on compound citations like `(D-06/D-07)`. The semantic gsd-plan-checker agent also independently confirmed full coverage (Dimension 7: Context Compliance — PASS). No re-plan needed.

### Blockers/Concerns

- ℹ️ [Phase 16] Advisory (cosmetic, desktop only): a movement saved with an empty
  comment renders literal `None` in the `/finance` «Комментарий» column (mobile
  cards handle it correctly). Guard the desktop template cell with
  `{{ movement.note or "" }}` when next touching finance templates. Non-blocking.

- ℹ️ [v2.0 close, 2026-07-18] Phase 22 (Sales Page Rebuild) shipped with 4 manual-only
  test cases (live basket-total arithmetic, incomplete-row marker, customer-mode
  radio round-trip, mobile basket preservation on batch re-tap) never confirmed in
  a live browser — no `22-UAT.md`, unlike the equivalent Phase 18/20 items which
  both have a completed UAT file. All 4 are backed by passing server-side tests;
  only the felt client-side JS behavior is unconfirmed. See
  `.planning/v2.0-MILESTONE-AUDIT.md` for the full breakdown. Recommend a short
  manual browser pass before relying heavily on the rebuilt sale form.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260714-2w6 | Replace Dictionary + CatalogPrice with a single-catalog-per-code import from oriflame_prices_with_calculations_fixed.xlsx (ДЦ->consultant_cents, ПЦ->consumer_cents) | 2026-07-14 | 3f0a7e3 | [260714-2w6-update-dictionary-pricelist](./quick/260714-2w6-update-dictionary-pricelist/) |
| 260714-fix | Catalog consumer price (ПЦ) now also autofills "Цена продажи" on product form and goods receipt (D-02 in receipts.py superseded); ДЦ still cost-only | 2026-07-14 | 53c3c92 | [260714-fix-catalog-sale-autofill](./quick/260714-fix-catalog-sale-autofill/) |
| 260714-o1z | Kill stale server on port 8000 in run.bat before starting a new one (fixes /dictionary 500 caused by an old process serving stale code) | 2026-07-14 | 5014787 | [260714-o1z-kill-stale-server-port](./quick/260714-o1z-kill-stale-server-port/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| uat_gap | Phase 01: 01-UAT.md — offline run.bat launch + browser correction flow + restart persistence (1 pending scenario) | testing | 2026-07-10 (v1.0 close) |
| verification_gap | Phase 01: 01-VERIFICATION.md — same offline run.bat flow | human_needed | 2026-07-10 (v1.0 close) |
| code_review | transfers.py/writeoffs.py: batch-ownership leak, unstripped qty echo (2 advisory) | resolved | 2026-07-13 (v1.1 close) — closed by Phase 20 (D-10/D-11, 20-05/20-06-SUMMARY.md, 2026-07-16) |
| verification_gap | Phase 15: 15-VERIFICATION.md — manual browser check of `/finance` and `/m/finance` balance display through real sale/return forms | confirmed_working | 2026-07-14 (phase 15 execution), confirmed by operator 2026-07-15 |
| doc_drift | `export.py`: `stream_customers_csv` docstring claims a *"Full customer profile dump"* — becomes false once Phase 21 ships address + contacts. Out of scope by design (contacts are 1-to-many and don't fit the flat CSV shape). If `address` is ever added it must go through the existing `_csv_safe`. | acknowledged | 2026-07-17 (phase 21 planning) — accepted debt, close in a future phase |
| uat_gap | Phase 22: no 22-UAT.md for 4 human_needed items (live basket-total math, incomplete-row marker, customer-mode round-trip, mobile basket preservation) — server-side tests all pass, only client-side JS behavior unconfirmed | testing | 2026-07-18 (v2.0 close) — see `.planning/v2.0-MILESTONE-AUDIT.md` |

## Session Continuity

Last session: 2026-07-18T05:56:34.178Z
Stopped at: v3.0 roadmap created (Phases 25-30), STATE + REQUIREMENTS traceability updated, ready to plan Phase 25
Resume file: None

## Operator Next Steps

- Plan the first v3.0 phase with `/gsd-plan-phase 25` (Authentication, Roles & User Attribution)
- Phases 27 and 30 are research-flagged — expect a `--research-phase` pass at their plan time
- Optional, non-blocking: a short manual browser pass on Phase 22's 4 unconfirmed items (see Blockers/Concerns above)
