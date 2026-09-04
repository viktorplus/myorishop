# Requirements — Milestone v5.0 Corrections, Dates & Currency

**Milestone goal:** Let the operator repair and correctly date their own data — reverse a wrong operation from История, record an operation with the date it actually happened, and fix product and customer cards from the phone.

**Defined:** 2026-09-04
**Source:** `.planning/research/SUMMARY.md` (four parallel researchers + synthesis), `.planning/OPEN-WORK-AUDIT-2026-09-04.md`, live-usage audits 2026-08-09 / 2026-08-13, and three operator decisions taken 2026-09-04 (recorded below).

**REQ-ID numbering:** `DATE-*` and `REV-*` are new prefixes. `SYNC-*` continues from SYNC-09 (v3.0), `MOB-*` from MOB-01 (v2.0), `CUR-*` from CUR-02 (quick task 260810-2g3).

---

## Operator decisions taken at scoping (2026-09-04)

| # | Question | Decision | Consequence |
|---|---|---|---|
| 1 | How to reverse a mis-entered **sale** | **Sales are excluded from storno.** The operator corrects a wrong sale through the existing «Возврат» flow. | Cheapest and safest — no second undo path double-handling cash, no two caps that can disagree. Accepted cost: the returns report, the customer's spend statistics and the «Возврат» cash category will contain an event that never happened. Revisit if it proves to be the operator's most common mistake. |
| 2 | How far back may an operation be dated | **No limit, plus a marker.** Any past date is accepted; rows where the business date differs from the entry date are marked «задним числом» and filterable in История. Future dates rejected. | Serves the milestone's actual purpose — the operator can always repair their own data. No clamp to fight when a genuinely old document surfaces. |
| 3 | Mobile customer editing scope | **Amended twice by the operator, 2026-09-04.** Originally "synced columns only"; then "+ phone and email"; finally **the full profile including every contact kind** — phones, emails, telegram, social. Mobile reaches parity with the desktop customer form. | The original objection was weaker than presented. It rested on `CustomerContact` not being a sync kind — true (zero occurrences in `merge.py`) — but the **mobile UI is server-only** (locked in v3.0: "mobile is server-only; there is no offline mobile install"), so a mobile edit writes straight to the server and involves no client→server sync at all. The desktop/server contact divergence is pre-existing and unaffected by this milestone. No wire-format change and no `FORMAT_VERSION` bump is required. The second amendment also **removes** the delete-by-omission hazard rather than guarding against it: rendering all four `CONTACT_KINDS` makes the full-replacement contract correct by construction, which is exactly what PITFALLS.md #17 prescribes ("pass `contacts=None` unless all four `CONTACT_KINDS` render"). Cost: a larger mobile form with repeatable multi-value fields. |

Decisions **not** put to the operator (unanimous research recommendation, taken as default, each reversible):

- All four new ledger columns land in **one** migration — one dual-dialect trigger rewrite, one five-artifact lockstep, one fleet skew window instead of two. Cost: `reverses_*_id` sits unused until Phase 34.
- A reversal **inherits the origin's business date verbatim**; its `created_at` is today. Not operator-editable in v5.0.
- Lock dates / closed accounting periods are **out of scope as an anti-feature** — they protect a statutory close this business does not have.

---

## v5.0 Requirements

### Sync hardening (pre-work — blocks the migration)

These land before any schema change reaches a client. They are not polish: without them the milestone's own migration opens a permanent, silent data-loss window.

- [x] **SYNC-10**: A push carrying a schema version the receiver does not understand is rejected with a clear Russian message, not accepted with fields silently dropped. `POST /api/sync/push` gains the same `schema_version` gate the offline upload path already has (`app/routes/offline.py:233-243`), reusing `offline.schema_version_ok` + `current_schema_version`.
- [x] **SYNC-11**: A rejected push leaves the client's rows unsynced, so nothing is lost and the next successful push re-sends them. `synced_at` stays NULL on a gate rejection.
- [x] **SYNC-12**: A cash movement pushed by a client that predates a column's introduction lands correctly instead of bricking that client's sync. Settles whether an explicit `None` in the insert dict defeats `server_default` — the same defect class that may already affect `CashMovement.currency` (`app/models.py:526`).
- [x] **SYNC-13**: The append-only triggers are proven live against a database built by `alembic upgrade head`, not only one built by `create_all`, so a future batch-recreate that drops them cannot pass the suite.

### Back-dated operations

- [ ] **DATE-01**: On every operation-writing form — 6 desktop forms and 5 mobile wizards — the operator can set the date the operation actually happened, defaulting to today.
- [ ] **DATE-02**: A future date is rejected with a Russian message; any past date is accepted.
- [x] **DATE-03**: Every period-scoped figure — dashboard day/week/month totals, sales-profit report, cash-flow report, stock and write-off reports — buckets by the business date, switched in ONE pass so no two surfaces can disagree about the same week.
- [ ] **DATE-04**: The technical timestamp keeps its three existing jobs untouched: audit trail, display order, and sync selection. Changing an operation's business date never moves it in the sync queue or the audit record.
- [ ] **DATE-05**: История and the CSV exports show both dates whenever they differ, so the operator can always tell when something was entered versus when it happened.
- [ ] **DATE-06**: A row whose business date differs from its entry date is marked «задним числом» and can be filtered on that in История.
- [x] **DATE-07**: Existing operations keep reporting exactly as they do today. A fixed past period's sales-profit total is byte-identical before and after the migration — the backfill is timezone-correct, not a naive UTC-prefix cut.
- [ ] **DATE-08**: An operation arriving from a client that has not yet updated still appears in every report, bucketed by its entry date, rather than vanishing from the period.

### One-tap reversal (сторно)

- [ ] **REV-01**: From История, on both desktop and mobile, the operator can reverse a wrong receipt, write-off, correction, transfer or manual cash movement in one confirmed action.
- [ ] **REV-02**: The confirmation states what will be written before anything is written.
- [ ] **REV-03**: The reversal is a NEW compensating row of the same type with the opposite sign, written through the existing sanctioned write path. Nothing is edited or deleted; the ledger stays append-only.
- [ ] **REV-04**: Every existing report nets the reversal out automatically, including the per-line breakdowns — the write-off report's per-reason lines, not just its grand total.
- [ ] **REV-05**: A multi-row operation reverses as one unit or not at all — a transfer's two rows never half-reverse.
- [ ] **REV-06**: The reversal carries the **original** operation's business date, so the misstated period is actually repaired instead of a phantom movement appearing in the current one.
- [ ] **REV-07**: История shows both sides of the relationship: the original is marked «сторнирована», the compensating row reads «сторно операции X».
- [ ] **REV-08**: An operation can be reversed only once; the control is unavailable on an already-reversed row and on a reversal itself.
- [ ] **REV-09**: Reversing an operation whose stock has already moved on is refused before any write, with a Russian message saying why. Stock is never driven negative — this is a hard guard, not the warn-but-allow shape used for oversell.
- [ ] **REV-10**: A mistyped cash deposit or withdrawal can be reversed — today it has no undo at all.
- [ ] **REV-11**: Sales are explicitly out of scope for storno (operator decision 1); the История control does not offer it on a sale row, and the operator is pointed at «Возврат».

### Mobile card editing

- [ ] **MOB-02**: From the phone, the operator can edit a product card — minimum sale price, cost, sale price, category and low-stock threshold — instead of having to reach a desktop.
- [ ] **MOB-03**: From the phone, the operator can correct an existing customer's **complete** profile — name, surname, consultant number, address, and every contact kind: phones, emails, telegram and social profiles (operator amendment, 2026-09-04). Mobile customer editing reaches full parity with the desktop form.
- [ ] **MOB-04**: The mobile forms reuse the same services as the desktop ones, so a validation rule can never differ between the two.
- [ ] **MOB-05**: Saving from the phone never blanks a field the small screen did not show, and never deletes a contact the operator did not touch. `update_customer`'s documented contract is that a `contacts` dict **fully replaces** the set and "a dict that omits a kind clears that kind" (`app/services/customers.py:192-194`). Rendering **all four** `CONTACT_KINDS` satisfies that contract by construction — the trap is closed by completeness, not by a special partial-update path. Multi-value is preserved: a customer with three phones keeps all three, and the form can add and remove values within each kind.
- [ ] **MOB-06**: A mobile edit that touches no contact field leaves the customer's contacts byte-identical — pinned by a GET → POST-unchanged round-trip test, the single check that catches this whole family of defects.
- [ ] **MOB-07**: A rejected mobile edit redisplays what the operator typed with the error next to the offending field.
- [ ] **MOB-08**: The operator is not misled about where a contact lives. `CustomerContact` is not part of the sync exchange in either direction (zero occurrences in `app/services/merge.py`), and the mobile UI is server-only — so a phone edited on the phone updates the server and will not appear in the desktop client, and vice versa. This divergence is pre-existing, not introduced here; v5.0 states it honestly rather than fixing it (the fix is a wire-format change, deferred).

### Currency render coverage

The feature shipped 2026-08-10; this closes its adoption tail.

- [ ] **CUR-03**: Wherever an amount stands alone, the operator can see which currency it is in — measured against the full render surface, not eyeballed. История is the priority: three currencies interleave there today with no marker.
- [ ] **CUR-04**: A customer's spend totals and purchase history state their currency, or are scoped to one — today they are the most misleading numbers left in the app.
- [ ] **CUR-05**: No report can produce a total that mixes currencies. `writeoff_report`, `top_selling_products` and `stale_products` each get an explicit, recorded decision.
- [ ] **CUR-06**: A warehouse's currency cannot be changed once it holds stock, cash or history — changing it silently relabels every past figure that joins through it.
- [ ] **CUR-07**: A regression tripwire prevents the swept surfaces from drifting back to an unlabelled render.
- [ ] **CUR-08**: The per-warehouse currency feature gets the human browser check it never received.

---

## Future Requirements (deferred, not this milestone)

- [ ] «Сторно и повторить» — after reversing, re-open the entry form pre-filled. This is the operator's actual workflow ("I typed 15 instead of 5"), deferred only because it is worth building on top of a proven storno.
- [ ] Undo link in the post-save success message.
- [ ] Optional reversal reason, and a «сторнированные» filter in История.
- [ ] «Остаток на дату» — point-in-time stock. Genuinely valuable, own replay semantics, own phase.
- [ ] Mobile edit-in-wizard — highest mobile value, highest risk (wizard state; the CR-01 scar).
- [ ] Mobile CRUD parity beyond product/customer: warehouses, dictionary, full reports.
- [ ] `CustomerContact` in the sync wire format — required before a contact edited on one side (desktop client / server) appears on the other. Bumps `FORMAT_VERSION`. v5.0 states the divergence (MOB-08) rather than closing it.
- [ ] Field-level reference-data merge so a client's edit wins over the server's copy.
- [ ] Third role "report viewer" (AUTH-V2-01).
- [ ] Customer purchase-frequency analysis and "running low" reminders (CST-V2-01); likely-interested-customer suggestions on receipt (CST-V2-02).
- [ ] CSV export with warehouse/batch columns (EXP-V2-01).

## Out of Scope (explicit exclusions, with reasoning)

- **Deleting or editing a posted operation** — the append-only ledger is the project's foundation and the basis of sync conflict resolution. A reversal is a new row, always.
- **Lock dates / closed accounting periods** — they exist to protect filed statutory accounts and a month-end close, neither of which a single reseller has. Their only observable effect here would be locking the operator out of fixing their own data.
- **Automatic cascading reversal** — reversing an operation must never silently reverse others derived from it.
- **A dedicated `storno` operation type** — every existing `WHERE type == ...` filter would miss it and nothing would net out. The compensating row keeps the original's type.
- **Currency conversion, FX rates, an «все валюты» option** — settled at CUR-01: amounts in different currencies are never summed, so there is nothing to convert.
- **Storno of a sale** (operator decision 1) — the «Возврат» flow covers it.
- **Bumping Alembic to 1.19.x during this milestone** — CHECK-constraint autogeneration becomes default and would add diff noise across 26 existing migrations.
- **Any new dependency** — research verified by execution that the milestone needs none. babel, freezegun/time-machine, `sqlalchemy.Date` and every date library are explicitly rejected with reasons recorded in `.planning/research/STACK.md`.

---

## Traceability

Filled by the roadmapper 2026-09-04. Every REQ-ID maps to **exactly one** phase — no orphans, no duplicates.

| REQ-ID | Phase | Status |
|--------|-------|--------|
| SYNC-10 | Phase 33 | Complete (33-01 server gate + 33-02 client half) |
| SYNC-11 | Phase 33 | Complete (33-01 VA-2 + 33-02 client-boundary test) |
| SYNC-12 | Phase 33 | Complete (33-03 VA-3 pinning test; no code change — SQLAlchemy already substitutes the default) |
| SYNC-13 | Phase 33 | Complete (33-03 alembic_engine + VA-5 trigger diff against an `alembic upgrade head` DB) |
| DATE-01 | Phase 33 | Not started |
| DATE-02 | Phase 33 | Not started |
| DATE-03 | Phase 33 | Not started |
| DATE-04 | Phase 33 | Not started |
| DATE-05 | Phase 33 | Not started |
| DATE-06 | Phase 33 | Not started |
| DATE-07 | Phase 33 | Not started |
| DATE-08 | Phase 33 | Not started |
| REV-01 | Phase 34 | Not started |
| REV-02 | Phase 34 | Not started |
| REV-03 | Phase 34 | Not started |
| REV-04 | Phase 34 | Not started |
| REV-05 | Phase 34 | Not started |
| REV-06 | Phase 34 | Not started |
| REV-07 | Phase 34 | Not started |
| REV-08 | Phase 34 | Not started |
| REV-09 | Phase 34 | Not started |
| REV-10 | Phase 34 | Not started |
| REV-11 | Phase 34 | Not started |
| CUR-03 | Phase 34 (currency plan) | Not started |
| CUR-04 | Phase 34 (currency plan) | Not started |
| CUR-05 | Phase 34 (currency plan) | Not started |
| CUR-06 | Phase 34 (currency plan) | Not started |
| CUR-07 | Phase 34 (currency plan) | Not started |
| CUR-08 | Phase 34 (currency plan) | Not started |
| MOB-02 | Phase 35 | Not started |
| MOB-03 | Phase 35 | Not started |
| MOB-04 | Phase 35 | Not started |
| MOB-05 | Phase 35 | Not started |
| MOB-06 | Phase 35 | Not started |
| MOB-07 | Phase 35 | Not started |
| MOB-08 | Phase 35 | Not started |

**Total: 36 requirements** — 4 sync hardening (SYNC-10..13), 8 back-dating (DATE-01..08), 11 reversal (REV-01..11), 7 mobile editing (MOB-02..08), 6 currency coverage (CUR-03..08).

> **Count correction, 2026-09-04 (roadmapper).** This section previously read "Total: 34 requirements" above the same five-group breakdown. The breakdown was and is correct; the sum was not — 4 + 8 + 11 + 7 + 6 = **36**. No REQ-ID was added, removed or renamed; only the arithmetic changed. Coverage is 36/36 mapped, each to exactly one phase.

**Phase mapping rationale:**

- **Phase 33** carries the sync hardening as its *first plans*, not a separate phase: SYNC-12's answer determines whether the four new ledger columns can ever be NOT NULL, and SYNC-10/11 must exist before any schema change reaches a self-updating client. Collapsing "Phase 0" into Phase 33 is explicitly authorised by `.planning/research/SUMMARY.md`, and PROJECT.md commits to 3 phases + 1 plan.
- **Phase 34** carries CUR-03..08 as a plan, not as a phase. The currency feature shipped 2026-08-10; the tail has no schema work and blocks nothing, but the reversal control, the currency marker and the business-date column all edit the same three История artifacts (`operations.py::history_view`, `history_rows.html`, `history_cards.html`), so it is sequenced adjacent to the reversal work to edit those files once — and before Phase 35, so the mobile product form ships with the final money render.
- **Phase 35** is last by the v1.1 UI-01 precedent: it renders money and writes ledger rows, so it inherits both upstream decisions. Building it earlier would mean redoing it.
