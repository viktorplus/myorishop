# Phase 3: Goods Receipt & Backup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-08
**Phase:** 3-goods-receipt-backup
**Areas discussed:** Receipt entry flow, Unknown product handling, Price capture, Backup strategy
**Mode:** Autonomous — recommended options auto-selected per user's standing full-auto directive (no AskUserQuestion turns).

---

## Receipt Entry Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Single-line loop | One product per receipt entry; form clears and refocuses for fast repeat | ✓ |
| Multi-line document | Receipt header + N lines, submitted together | |

**Choice rationale:** Simplest ledger mapping (1 op per line), fastest for a beginner-maintained codebase; multi-line deferred.

---

## Unknown Product Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-create product | Create product card from receipt data in same transaction | ✓ |
| Reject with link | Require creating product first | |

**Choice rationale:** Fast entry is core value; prices are already in the form.

---

## Price Capture

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot + update card | Receipt op snapshots prices; card updated via price_change ops | ✓ |
| Snapshot only | Card prices unchanged by receipts | |

**Choice rationale:** Keeps card current with latest intake prices; reuses Phase 2 price-history machinery.

---

## Backup Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Startup + manual button, keep 30 | VACUUM INTO backups/ on app start + /backup page | ✓ |
| Scheduled while running | Background timer backups | |
| Manual only | Operator-triggered only | |

**Choice rationale:** WAL-safe, zero moving parts, satisfies BCK-01 including verified restore (test + restore.bat).

## Claude's Discretion

- Backup page layout, filename format, empty states
- Migration/index needs, template structure
- Recent-receipts list placement

## Deferred Ideas

- Multi-line receipt documents
- Periodic in-app scheduled backups
- Off-machine backup copies (cloud/USB) — v2
- CSV export — Phase 6
