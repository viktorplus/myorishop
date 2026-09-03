---
phase: 32-in-app-secure-self-update
plan: 02
subsystem: infra
tags: [cryptography, ed25519, minisign, supply-chain, self-update, security]

# Dependency graph
requires:
  - phase: 31-packaging-launcher-signed-release-pipeline
    provides: "signed-release pipeline (minisign roundtrip, VENDORED_APP_ASSETS), launcher swap; T-31-02 secret-key-stays-offline posture"
  - phase: 32-in-app-secure-self-update (plan 01)
    provides: "Wave-0 RED scaffold pinning minisign_verify / update service surfaces"
provides:
  - "cryptography (PyCA 49.0.0) as a project dependency — the Ed25519 provider for the Wave 2/3 verify gate"
  - "app/minisign.pub — the vendored Ed25519 PUBLIC key trust anchor for release-manifest verification"
  - "Confirmed repo-public posture (no read-only token fallback needed)"
affects: [32-03, 32-04, 32-05, minisign_verify, update-service, build_release]

# Tech tracking
tech-stack:
  added: [cryptography==49.0.0 (PyCA)]
  patterns: ["Blocking-human supply-chain checkpoint gates the one new install (T-32-SC)", "Only the PUBLIC minisign key is vendored; secret key stays offline (T-31-02/T-32-07)"]

key-files:
  created: [app/minisign.pub]
  modified: [pyproject.toml, uv.lock]

key-decisions:
  - "cryptography (PyCA) 49.0.0 is the Ed25519 provider — stdlib has none; human-approved supply-chain checkpoint (verified PyCA provenance + correct cp311-abi3-win_amd64 wheel on pypi.org)"
  - "Repo github.com/viktorplus/myorishop kept PUBLIC — unauthenticated /releases/latest works, so NO read-only GitHub token fallback is provisioned into .env (one fewer secret)"
  - "Only the PUBLIC key (app/minisign.pub, RW-prefixed) enters the repo; the secret key stays offline at the operator's password-protected store, .gitignore blocks *.key (T-31-02/T-32-07)"

patterns-established:
  - "Supply-chain gate: a [SUS]-flagged install is never auto-approved — a blocking-human checkpoint verifies PyCA provenance on pypi.org before uv add"
  - "Trust anchor vendoring: the client ships only the RW public half; the secret signing key never enters repo/CI"

requirements-completed: [UPD-02]

# Metrics
duration: ~5min
completed: 2026-07-22
---

# Phase 32 Plan 02: Verify-Gate Prerequisites Summary

**Added the PyCA `cryptography` 49.0.0 Ed25519 provider and vendored the `RW`-prefixed `app/minisign.pub` trust anchor — the two human-owned prerequisites that unblock the Wave 2/3 release-verify gate.**

## Performance

- **Duration:** ~5 min (automation half; both blocking-human checkpoints resolved by the operator beforehand)
- **Started:** 2026-07-22T20:10:19Z
- **Completed:** 2026-07-22T20:15:00Z
- **Tasks:** 2
- **Files modified:** 3 (pyproject.toml, uv.lock, app/minisign.pub)

## Accomplishments
- `cryptography==49.0.0` (PyCA) added to `[project].dependencies`; `Ed25519PublicKey` imports cleanly on this runtime (proves the win_amd64 abi3 wheel works on the embeddable cp313 target).
- `app/minisign.pub` vendored and verified: its last non-empty line starts with `RW` (minisign public-key marker) — the sole trust anchor the verify gate checks every release manifest against.
- Repo-public posture confirmed and recorded: no read-only token fallback needed.
- Test collection re-verified after the dependency change (1213 tests collected, no import breakage).

## Task Commits

Each task was committed atomically:

1. **Task 1: Supply-chain gate — approve + install `cryptography`** - `07a2186` (feat)
2. **Task 2: Vendor app/minisign.pub + confirm repo public** - `0199411` (feat)

## Files Created/Modified
- `pyproject.toml` - Added `cryptography>=49.0.0` to `[project].dependencies`.
- `uv.lock` - Locked cryptography 49.0.0 and its resolved graph.
- `app/minisign.pub` - Vendored Ed25519 PUBLIC key (RW key line: `RWToyp3x80Zr...`); trust anchor for release verification (UPD-02).

## Decisions Made
- **cryptography (PyCA) 49.0.0 as the Ed25519 provider** — human-approved via the blocking-human supply-chain checkpoint (T-32-SC): verified on pypi.org as the PyCA package, exact name, correct `cp311-abi3-win_amd64` wheel, not a typosquat.
- **Repo kept PUBLIC (no token fallback)** — unauthenticated `/releases/latest` works, so no read-only GitHub token is added to `.env`.
- **Public key only** — the secret signing key stays offline (operator's password-protected store); `.gitignore` blocks `*.key`/`minisign.key` (T-31-02/T-32-07). Executor never touched, read, or committed any secret key.

## Deviations from Plan

None - plan executed exactly as written. Both blocking-human checkpoints were resolved by the operator via the orchestrator; this executor ran only the sanctioned automation half of each task.

## Issues Encountered
None. `uv add cryptography` emitted a non-fatal hardlink-fallback warning (cache/target on different filesystems) — cosmetic, install succeeded.

## User Setup Required
None outstanding for this plan — the operator already performed the offline `minisign -G` keygen (docs/RELEASE.md Section 1) and confirmed repo visibility. The secret key remains an operator-held offline asset (never in repo).

## Next Phase Readiness
- Wave 2 (32-03) can now import `cryptography.hazmat.primitives.asymmetric.ed25519` and read `app/minisign.pub` to build `minisign_verify.py` / the `update.py` check-half.
- The real-release verify path is unblocked once two signed releases exist (Phase 31 pipeline); synthetic-key unit tests do not depend on the vendored key.

## Self-Check: PASSED

- Files verified present: pyproject.toml, uv.lock, app/minisign.pub, 32-02-SUMMARY.md
- Commits verified: 07a2186 (Task 1), 0199411 (Task 2)
- app/minisign.pub last non-empty line starts with `RW` (trust-anchor marker confirmed)

---
*Phase: 32-in-app-secure-self-update*
*Completed: 2026-07-22*
