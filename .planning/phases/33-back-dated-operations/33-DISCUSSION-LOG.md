# Phase 33: Back-Dated Operations - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-04
**Phase:** 33-back-dated-operations
**Mode:** advisor (USER-PROFILE.md present; `NON_TECHNICAL_OWNER` = false — `learning_style: hands-on`, `explanation_depth: concise`, `frustration_triggers: over-explanation`, no `jargon` signal; calibration tier `standard` → 2–4 options, resolved from `Vendor Philosophy: pragmatic`, no `preferences.vendor_philosophy` in `.planning/config.json`)
**Areas discussed:** Schema gate on push · Date field on the forms · История two-date rendering · CSV and borderline date readers
**Research:** 4 parallel `gsd-advisor-researcher` agents, one per selected gray area

---

## Area 1 — Schema-version gate on `POST /api/sync/push`

| Option | Description | Selected |
|--------|-------------|----------|
| A. Exact match | Reuse `offline.schema_version_ok` verbatim. Zero new code, 409 precedent transfers 1:1. Refuses the behind client too, so during the LOCKED rollout (server first) every not-yet-updated client stops syncing for an unbounded window — clients check for updates once at startup and the operator applies them by hand. DATE-08 becomes fixture-only. | |
| B. Asymmetric ordering gate | `client_schema <= server_schema` passes; refuse only when the client is AHEAD. Matches the one direction that loses data. A behind client keeps syncing, its rows land `business_date IS NULL` and bucket via COALESCE — DATE-08 satisfied literally. Couples to the `^\d{4}$` revision convention (bought with a test). | ✓ |
| C. B + unknown-field belt | B plus «does this batch carry a key absent from my `KIND_TO_FIELDS`?». Detects the actual loss condition rather than a proxy; survives a revision-id rename. Cost: two mechanisms for one job, against CLAUDE.md's additive-change rule. | |
| D. Unknown-field detection only | Direction-free and convention-free, but blind to a receiver whose DB is behind, leaves `schema_version` decorative on the online path while the offline path still gates on it — two answers to one question. | (not offered) |

**User's choice:** B — asymmetric.
**Notes:** Two follow-ups settled in the same pass. (1) Auto-sync backoff — a permanent 409 would otherwise retry every 300 s forever, re-uploading a growing closure and burning a rate-limit token each time; user chose to back off to `MAX_INTERVAL_SECONDS` (3600) on `schema_mismatch`, accepting up to an hour's recovery delay because the manual «Синхронизировать» link does not share the loop's sleep. (2) Research found SYNC-11 is already free in shipped code — `synced_at` is stamped only after `raise_for_status()` — so it needs a test, not code.

---

## Area 2 — Where the date field lives on the operation-writing forms

| Option | Description | Selected |
|--------|-------------|----------|
| D1 + M1/M2 | Desktop: visible `<input type="date">` pre-filled with today, last field before the actions, identical on every form. Mobile: in the persistent `<form>` shell for приход/продажа/списание (survives every step swap with zero hidden-field threading, «Шаг N из M» untouched); on the final step for корректировка/перемещение, which have no shell. | ✓ |
| D1 + M1/M2 + sticky date | The same, plus echoing the entered date back on the four save-and-next desktop forms instead of resetting to today — most of research's deferred D11 for one line per route. Scope extension. | |
| D2. Collapsed `<details>` | Field hidden behind «Указать другую дату», default today. Zero friction on the fast sale path. Cost: `<details>` appears nowhere under `app/templates` — a new UI idiom; a 422 would point at an invisible field. | |
| M3. Dedicated wizard step | (Presented in the research table, not offered as a choice.) Rewrites 17 hardcoded «Шаг N из M» strings across 13 files plus 3 `step_label` literals, and adds a mandatory tap forever to a field correct by default ~95% of the time. | |

**User's choice:** D1 + M1/M2, without the sticky-date extension.
**Notes:** Research disqualified «date on the final screen of all five wizards» outright — the sale basket is re-rendered from `_acc_context` on every «Добавить товар», so a date typed there silently resets to today when a second item is added. The two-idiom split (shell for three wizards, final step for two) was accepted rather than manufacturing a shell for корректировка/перемещение, which is a separate refactor with its own blast radius.

---

## Area 3 — История: two dates and the «задним числом» marker

| Option | Description | Selected |
|--------|-------------|----------|
| A + fourth `<select>` | Muted second line inside the «Когда» cell, only when the dates differ — the D-15 precedent already in the same file for batch attribution. Zero colspan churn; identical in both the generic and narrowed layouts; matching rows render byte-identically to today. Filter = a fourth select copying the three siblings' HTMX idiom. Mobile card mirrors. | ✓ |
| A + badge | The same, but the marker becomes a visible inline badge and the second line carries only «внесено …». Stronger visually; cost is a new CSS token and a repeat of the colour-as-sole-cue WCAG 1.4.1 scar. | |
| B. New «Дата операции» column | Scannable, maps 1:1 onto CSV. Cost: ~8 edit sites in one template, colspan arithmetic in both layouts, an 11-column generic view, and it fights the purpose of the narrowed views, which exist to drop columns. Mobile diverges regardless. | |

**User's choice:** A + fourth select.
**Notes:** Also settled — the business date is the PRIMARY value in «Когда» with the entry timestamp muted beneath, because the period filter selects rows by business date and a `created_at` headline would make a filtered list look mis-sorted. A checkbox filter was rejected on evidence: `type="checkbox"` appears exactly once in the whole template tree (a settings form), a boolean cannot express «Только в день операции», and an unchecked checkbox posts nothing, so the `hx-include` idiom would silently drop the state.

**Conflict resolved by requirement, not by asking:** one research pass proposed changing `_DEFAULT_ORDER` to `(business_date desc, created_at desc, seq desc)`; another proposed leaving it. DATE-04 states the technical timestamp keeps all three of its jobs *including display order* — so the ordering is unchanged and no business-date sort option is added this phase.

---

## Area 4a — Scope of DATE-01 (which surfaces get a date field)

| Option | Description | Selected |
|--------|-------------|----------|
| Everything that writes to a ledger table | 6 desktop ledger forms + возврат + 2 cash forms (shared desktop/mobile template); mobile: 5 wizards + the возврат screen. The only reading coherent with DATE-03, which puts the cash-flow report on the bucket-by-business-date list. | ✓ |
| Literally 6 + 5 | Only the six desktop ledger forms and five mobile wizards. Less work, but `cash_movements.business_date` would only ever be populated by the backfill and by Phase 34 reversals. | |
| Ledger + cash, возврат deferred | Возврат left without a date field on the argument that a return is a genuinely new event happening today. | |

**User's choice:** everything that writes to a ledger table.
**Notes:** Raised because the requirement text «6 desktop forms and 5 mobile wizards» undercounts what exists in the code — research enumerated the real surface list and found three more.

---

## Area 4b — CSV column shape

| Option | Description | Selected |
|--------|-------------|----------|
| A. «Когда» becomes the business date, «Внесено» appended last | Keeps «Когда»'s plain-Russian meaning; column positions 1..N do not shift, so existing formulas over `Код`/`Цена`/`Сумма` keep working; column 1 agrees with the period that selected the rows. Cost: column 1's value type goes from `dd.mm.yyyy HH:MM` to `dd.mm.yyyy`. | ✓ |
| B. «Когда» stays technical, «Дата операции» appended last | Byte-identical column 1 for every pre-migration row. Cost: a period export's first date column would routinely contradict the file's own period — the exact disagreement DATE-03 exists to prevent. | |
| Ask the operator first | Research flagged «does the operator maintain a spreadsheet over these files?» as the single input that flips A→B. | |

**User's choice:** A.
**Notes:** Applies only to `stream_sales_csv` and `stream_cash_movements_csv` — `products.csv` has no date column and `customers.csv`'s «Создан» is `Customer.created_at`, a table that gains no `business_date`. Coupled edit recorded: `export.py:135`'s `ORDER BY` must switch too, or the dump reads as unsorted by its own first column.

---

## Area 4c — Borderline date readers (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| «Последняя приёмка» per warehouse | `warehouses.py:100`. Research recommends switching and explicitly contradicts `research/ARCHITECTURE.md:195` («leave it») — this was open operator decision #5. | ✓ |
| Batch auto-name «{товар} — {дата}» | `receipts.py:209`. Without it, a receipt back-dated to 01.09 creates a batch named for today, contradicting its own История row. | ✓ |
| `stale_products` «дней без продаж» | `reports.py:224`. Its comparison target at `:236` is already a local date, so the two sides are currently different types. | |
| Labels «Последний заказ» / «Возврат из продажи от …» | `customers.py:528-540`, `returns.py:75,152`. Pure identification labels. | ✓ |

**User's choice:** warehouse «Последняя приёмка», batch auto-name, and the two labels. `stale_products` left on `created_at`.
**Notes:** Declining `stale_products` cancels its coupled template edit (`reports_products.html:32` stays `| local_dt`) and leaves the pre-existing `reports.py:224` vs `:236` type asymmetry untouched — recorded as an explicit non-change rather than an oversight.

A real coupling was surfaced and resolved rather than shipped silently: «Последний заказ» reads `history[0]["op"].created_at`, relying on `purchase_history`'s `created_at DESC` ordering, which DATE-04 forbids changing. Switching only the displayed field would show the business date of the latest-*entered* row. Resolution recorded in CONTEXT D-24 — recompute `last_order_date` as `MAX(business_date_expr(...))` over the customer's sale rows, leaving `purchase_history` untouched. Flagged to the user as a fixed assumption open to correction.

---

## Claude's Discretion

- Exact wording of the two Russian date errors and the 409 message, within the shapes recorded in CONTEXT D-06/D-12.
- The third option's label on the new История select.
- Placement of the date input inside the mobile shell `<form>`.
- Test naming and file placement.

## Deferred Ideas

- Sticky business date across a session (research D11) — offered as a one-line-per-route hedge on the four save-and-next desktop forms, not taken.
- `stale_products` on the business date — explicitly declined.
- A collapsed `<details>` date disclosure on the sale form — rejected now, named as the correct follow-up if the always-visible field measurably slows the sale flow.
- `.filter-bar` `flex-wrap` — the fourth select may overflow at narrow desktop widths; a one-line fix that touches every `.filter-bar` page, so it is a separate decision.
- Todo `2026-08-31-price-lists-backfill.md` — reviewed (score 0.2, keyword «created» only), not folded.
