# Phase 33: Back-Dated Operations - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

The operator can record an operation with the date it actually happened, and every
period-scoped figure in the app buckets by that business date — while the technical
timestamp keeps all three of its existing jobs (audit trail, display order, sync
selection), and while the milestone's own schema change cannot open a silent
data-loss window across the self-updating client fleet.

**Delivers:** SYNC-10..13 (sync-skew hardening, FIRST) → one migration adding all four
nullable ledger columns with a timezone-correct backfill and one dual-dialect trigger
rewrite → `business_date_bounds` + `business_date_expr` helpers → every period-scoped
reader switched in ONE pass → a date input on every ledger-writing surface → both dates
plus the «задним числом» marker and filter in История and the CSV exports.

**Not this phase:** writing `reverses_*_id` (Phase 34 — the columns ship here unused but
trigger-guarded), the storno control itself (Phase 34), the `| cents` → `| money(...)`
currency sweep (Phase 34), mobile card editing (Phase 35).

</domain>

<decisions>
## Implementation Decisions

### Sync-skew hardening (SYNC-10/11) — lands BEFORE the migration

- **D-01: The `POST /api/sync/push` schema gate is ASYMMETRIC, not exact-match.**
  Refuse only when the client is AHEAD of the receiver (`client_schema <= server_schema`
  passes). Rationale: the data loss is one-directional — `merge._ledger_row`
  (`app/services/merge.py:460`) projects the incoming batch through the RECEIVER's
  columns, so only a client-ahead push loses a field behind a 200 while
  `sync_client.py:384-393` stamps `synced_at`. A behind-client push already fails loudly
  and all-or-nothing, so refusing it buys nothing and would cut the whole fleet off for
  an unbounded window — clients check for updates ONCE at startup
  (`app/main.py:118-136`) and the operator applies the update by hand, while s1 changes
  only on a manual `up -d --build`. Accepting the behind client is also what makes
  DATE-08 a live property rather than a fixture-only branch: its rows land with
  `business_date IS NULL` and bucket via the read-time COALESCE.
  Rejected: exact-match reuse of `offline.schema_version_ok`; unknown-field detection as
  the whole gate; and D-01 + an unknown-field belt (option C) — a second mechanism for
  one job, against the additive-change rule in CLAUDE.md.

- **D-02: New sibling `push_schema_ok(client_schema, server_schema)` in
  `app/services/sync.py`, directly under `current_schema_version`
  (`app/services/sync.py:225-235`). `app/services/offline.py:61-71` is NOT modified** —
  the offline bundle's exact-match 409 copy is locked by 30-UI-SPEC and rendered at
  `app/templates/offline/result.html:26-29`. The push route must not import the offline
  module; `app/routes/sync.py:37-41` already imports from `sync.py`.

- **D-03: Keep the `""` escape hatch on BOTH sides** (`if not server_schema or not
  client_schema: return True`). This is load-bearing, not cosmetic: the entire test suite
  builds its schema with `Base.metadata.create_all` (`tests/conftest.py:23-30`, server DB
  at `:292-297`), so `current_schema_version` returns `""` on both sides in every existing
  sync test. Drop the hatch and the suite goes red wholesale. The gate's own tests must
  therefore inject `schema_version` explicitly or monkeypatch `current_schema_version`.

- **D-04: The lexicographic ordering is bought with a TEST, not a parser.** All 26
  revisions are fixed-width numeric (`alembic/versions/0001_initial_schema.py` …
  `0026_cash_movements_trigger_guards_currency.py`, `revision = "0026"`,
  `down_revision = "0025"`), but nothing enforces it. Add a test asserting every
  `revision` / `down_revision` literal under `alembic/versions/` matches `^\d{4}$` — same
  tripwire shape as `test_trigger_column_list_matches_schema`. This phase's migration is
  `0027` (no `0027*` file exists today).

- **D-05: Gate AFTER `parse_exchange`, on `batch.schema_version`** (`app/routes/sync.py`
  around `:111-114`; the value is already extracted at `app/services/merge.py:229-234`) —
  two lines instead of the eight the offline path needs, because `app/routes/offline.py:222-235`
  only peeks the raw header line since it needs the digest first. **Named trade-off to write
  as a code comment:** if a future schema bump adds a new record *kind*, `parse_exchange`
  raises first and an ahead-client gets `400 MALFORMED_BATCH_ERROR` instead of the 409 — a
  worse *message*, but not a loss, because any non-2xx returns before the `synced_at` stamp.

- **D-06: `409` + a fifth RU constant beside the four at `app/routes/sync.py:51-54`**, naming
  BOTH versions like the offline page does (`result.html:29`, autoescaped, T-30-08). Because
  the gate is asymmetric the instruction is never ambiguous — only a client-ahead push is ever
  refused, so the message says «Обновите сервер».
  Shape: `SCHEMA_AHEAD_ERROR = "Несовместимая версия данных: клиент {client}, сервер {server}. Обновите сервер."`

- **D-07: SYNC-11 needs a TEST, not code.** `synced_at` is stamped only after
  `raise_for_status()` (`app/services/sync_client.py:376,384-393`), so a 409 already leaves
  rows unsynced. Likewise `last_sync_at` already advances only for `ok`/`partial`
  (`app/routes/sync.py:269-273`, `app/services/sync_client.py:597-599`) — pin both with
  assertions, change nothing.

- **D-08: Operator-facing refusal reuses the shipped machinery.** Branch the existing
  `except httpx.HTTPStatusError` (`app/services/sync_client.py:377-379`) on
  `status_code == 409` → `SyncResult(status="schema_mismatch", ...)`, add one branch to
  `format_sync_message` (`:186-209`) with the string research already chose —
  **«Сервер ещё не обновлён — синхронизация отложена»** (`.planning/research/PITFALLS.md:130`).
  No new template, no new CSS token: `#sync-status`
  (`app/templates/partials/sync_status.html:15`) renders whatever the formatter returns.
  Keep the early return (no pull attempt) — a client-ahead refusal means the server's
  reference data is older, so pulling is pointless. The client must keep ignoring `detail`
  (T-29-07); it does by construction. **`#sync-badge` (`sync_status.html:16`) must NOT be
  suppressed** — the growing unsynced count is the correct visible pressure signal and is
  exactly what SYNC-11 guarantees is recoverable.

- **D-09: Auto-sync backs off to `MAX_INTERVAL_SECONDS` (3600) on `schema_mismatch`.**
  `_auto_sync_iteration` (`app/main.py:71-103`) reads the interval at the TOP of the
  iteration, so a permanent 409 would retry every 300 s
  (`DEFAULT_INTERVAL_SECONDS`, `app/services/sync_client.py:53`) forever, each time
  re-uploading the whole growing unsynced closure and burning a rate-limit token
  (`app/routes/sync.py:84-86`). Fix: after the tick, re-read `sync_state.last_status` and
  return `MAX_INTERVAL_SECONDS` (`sync_client.py:52`) when it is `schema_mismatch`.
  ~4 lines, no new column, no new setting, self-clearing on the next non-mismatch tick.
  Accepted cost: recovery is delayed up to an hour after s1 is rebuilt — mitigated because
  the manual «Синхронизировать» link (`app/templates/base.html:76`) shares the `_run_lock`
  but not the loop's sleep, so the operator can resync instantly.

### Date entry on the forms (DATE-01/02)

- **D-10: Visible `<input type="date" value="{{ today }}">` on every desktop surface,
  positioned as the LAST field before `.form-actions`, identically everywhere.**
  Rejected: a collapsed `<details>Указать другую дату` disclosure — `<details>` appears
  nowhere under `app/templates`, so it would be a brand-new UI idiom for a field the
  operator is expected to touch often (the locked operator decision removed any lower bound
  on back-dating), and a 422 on the date would point at an invisible field. Also rejected:
  visible on low-frequency forms + disclosure on the sale basket — two idioms for one
  concept. Matches `.planning/research/PITFALLS.md:700` («pre-filled **and visible**»).

- **D-11: On mobile, the date lives in the PERSISTENT `<form>` shell that wraps
  `#wizard-step`** for приход (`app/templates/mobile_pages/receipts.html:12`), продажа
  (`sales.html:11`) and списание (`writeoff.html:19`). That shell is never swapped by htmx
  and is auto-serialised on every non-GET, so the value survives every step swap AND the
  sale wizard's basket↔product round-trip with **zero** hidden-field threading, and
  «Шаг N из M» is untouched.
  **For корректировка and перемещение — which have no shell, only per-step `<form>`s
  (`corrections_step_product.html:14`, `transfers_step_product.html:12`) — the date goes on
  the FINAL step** (`corrections_step_value.html`, `transfers_step_dest.html`), whose
  screens are terminal with no accumulator round-trip. Accept this two-idiom split; do NOT
  manufacture a shell for those two — that refactor has its own blast radius.
  Rejected: date on the final screen of ALL five wizards — the sale basket is re-rendered
  from `_acc_context` (`app/routes/mobile_sales.py:39`) on every «Добавить товар», so a date
  typed there silently resets to today when a second item is added. Also rejected: a
  dedicated «Дата операции» wizard step — it rewrites **17** hardcoded «Шаг N из M» strings
  across 13 files plus 3 `step_label` literals in `app/routes/mobile_transfers.py:65,106,130`,
  and adds a mandatory tap forever to a field that is correct by default ~95% of the time.

- **D-12: Two distinct Russian errors, both under `errors["op_date"]`, raised in the
  SERVICE layer** (`.planning/research/ARCHITECTURE.md:167` — never the route), mirroring
  `parse_optional_expiry` (`app/services/receipts.py:46-65`) and the existing constants
  `EXPIRY_ERROR` (`receipts.py:43`) / `CLOSE_DATE_ERROR` (`active_catalog.py:21`):
  - `OP_DATE_FORMAT_ERROR = "Укажите дату в формате ГГГГ-ММ-ДД."`
  - `OP_DATE_FUTURE_ERROR = "Дата операции не может быть в будущем."`
  Malformed and future are different operator mistakes and must not share a message.

- **D-13: Add `max="{{ today }}"` to the date input — conditional on the htmx check
  below.** No `type="date"` in the repo carries `max`/`min` today (11 occurrences), but `max`
  itself is not a new idiom (`partials/return_form.html:35`,
  `mobile_partials/return_confirm.html:40`). The benefit is that the native mobile picker
  greys out future days — it *prevents* what the server can only *report*.
  **`needs verification` (blocking for this line only):** htmx 2.0.10 runs client-side
  constraint validation before a non-GET and halts with `htmx:validation:halted`. If it
  calls `checkValidity()` rather than `reportValidity()`, a `max` violation aborts the
  request with NO visible message — strictly worse than the server's Russian error.
  *Smallest check:* load `/receipts` in a browser, clear «Код», click «Сохранить приход»,
  observe whether a native validation bubble appears or the click is silently swallowed.
  If silent → drop `max`, rely on the server guard alone.

- **D-14: Mobile error rendering is NOT uniform and must be handled per file, not assumed.**
  Per-key `<p class="error">`: `receipts_step_confirm.html:19-21`,
  `transfers_step_dest.html:21-23,50,56`. A single `.error-block` looping ALL messages:
  `writeoff_step_reason.html:17-21`, `corrections_step_value.html:13-17`. Without a fix, the
  date error surfaces as a top-of-screen block on списание/корректировка instead of next to
  the field. Cheapest consistent fix: add the per-key branch under the date input in all five
  final steps and exclude `op_date` from the loop the way `receipts_step_confirm.html:20`
  excludes `form`. Desktop IS uniform (`pages/batch_form.html:42`,
  `partials/receipt_form.html:43`, `partials/withdraw_form.html:25`).

- **D-15: There is no `today` Jinja global** (`app/routes/__init__.py:193-231` lists them
  all) and registering one as a value would be **stale-per-process** (evaluated at import).
  Pass it per-context, or register a zero-arg callable. The local-today precedent is
  `datetime.now(ZoneInfo(settings.display_tz)).date()` (`app/services/receipts.py:209`,
  `app/routes/mobile_reports.py:21`, `app/services/customers.py:443,465`); config default
  `Europe/Moscow` at `app/config.py:76`.

### Scope of DATE-01 (surfaces)

- **D-16: DATE-01 covers EVERYTHING that writes to a ledger table, not literally
  «6 forms + 5 wizards».** The requirement text undercounts what exists in the code.
  Locked surface list:
  - **Desktop ledger forms (6):** `partials/receipt_form.html` (form `:23`),
    `partials/sale_form.html` (`#sale-form` `:40`), `partials/writeoff_form.html` (`:17`),
    `partials/correction_form.html` (`:21`), `partials/transfer_form.html` (`:19`),
    `partials/return_form.html` (`:28`, no page shell — rendered into `#return-form-wrap`
    by `app/routes/returns.py:99,102,132,142,160`).
  - **Cash forms (2, SHARED desktop↔mobile, parameterised by `finance_base`):**
    `partials/withdraw_form.html` (`:16`) and `partials/deposit_form.html` (`:10`), rendered
    from `pages/finance.html:30,33` AND `mobile_pages/finance.html:33,36`; routes
    `app/routes/finance.py:201,273` and `app/routes/mobile_finance.py`. Touched once each
    because the template is shared.
  - **Mobile wizards (5):** приход, продажа, списание (shell-form, D-11) + корректировка,
    перемещение (final step, D-11).
  - **Mobile возврат (1):** `mobile_partials/return_confirm.html` (form `:33`), rendered by
    `app/routes/mobile_returns.py:104,107,135,145,162` — a single screen, not a wizard.
    Without this it silently ships without a date field while its desktop twin has one.
  **Rationale for including cash:** DATE-03 puts the cash-flow report on the
  bucket-by-business-date list and the migration adds `cash_movements.business_date` — with
  no field on the cash forms that column would only ever be populated by the backfill and by
  Phase 34 reversals, which is incoherent.

- **D-17: `record_operation` gets a keyword with a default** (`app/services/ledger.py:37-49`,
  stamps `created_at=utcnow_iso()` at `:123`). It has **12** call sites —
  `corrections.py:120`, `returns.py:156`, `catalog.py:137,279,288`,
  `receipts.py:160,186,241`, `sales.py:287`, `transfers.py:176,184`, `writeoffs.py:105` — of
  which `catalog.py:137,279,288` are product-admin/import paths with no operator date form
  and stay on the default. So **9 real call sites**. `record_cash_movement`
  (`app/services/finance.py:48-57`) has **3** — `finance.py:188`, `sales.py:310`,
  `returns.py:174`.

### История rendering (DATE-05/06)

- **D-18: Both dates render as a muted SECOND LINE inside the «Когда» cell, only when they
  differ** — the D-15 precedent already documented in the same file for batch attribution in
  the «Товар» cell (`app/templates/partials/history_rows.html:132-147`).
  This is chosen specifically because it needs **zero colspan churn**: `colspan="10"` (`:118`)
  and `3 + columns|length + 1` (`:233`) stay untouched, and the identical shape works in both
  the generic 10-column layout (`:125`) and the per-type narrowed layout (`:240`). Rows whose
  dates match — and every `business_date IS NULL` row from an un-upgraded client — render
  byte-identically to today.
  Rejected: a new «Дата операции» column (~8 edit sites in one template, colspan arithmetic
  in both layouts, and it fights the whole purpose of the narrowed views, which exist to
  *drop* columns — `HISTORY_TYPE_COLUMNS`, `app/services/operations.py:41-49`). Rejected:
  a colour badge as the marker — no badge token exists and colour-as-sole-cue already
  produced a WCAG 1.4.1 scar (`app/static/style.css:363-368`, 18-REVIEW WR-03).

- **D-19: The PRIMARY date in «Когда» is the business date; the entry timestamp is the muted
  subline.** Decisive argument: the date-range filter selects rows by
  `coalesce(business_date, substr(created_at,1,10))`, so a row entered today for 15.08 would
  otherwise appear under an August filter while displaying a September date — the list would
  look broken. Concretely:
  - equal, or `business_date IS NULL` → unchanged single line
    `{{ r.op.created_at | local_dt }}` → `04.09.2026 15:22` (`app/core.py:102-105`)
  - differing → line 1 `{{ r.business_day | ru_date }}` → `15.08.2026` (day-only,
    `app/core.py:89-99`); line 2
    `<span class="muted">задним числом · внесено {{ r.op.created_at | local_dt }}</span>`.
    That one line carries DATE-05 and DATE-06 together.

- **D-20: The «задним числом» filter is a FOURTH `<select name="dated">`** in `.filter-bar`
  («Все / Только задним числом / Только в день операции»), copying the byte-identical HTMX
  attribute set of the three siblings (`history_rows.html:27-35`, `:39-45`, `:54-62`).
  Rejected: a checkbox — `type="checkbox"` appears exactly ONCE across every desktop and
  mobile template (`app/templates/pages/settings.html:28`, a settings form, never a list
  filter), so it would be the app's first list-filter checkbox; a boolean cannot express
  «Только в день операции»; and an unchecked checkbox posts nothing, so the
  `hx-include="#history-rows input, #history-rows select"` idiom silently drops the state.
  Rejected: extra options on the «Сортировать по» select — conflates sorting with filtering
  against a deliberate allow-list (`app/services/operations.py:29-32`).

- **D-21: Mobile MIRRORS desktop, it does not diverge.**
  `app/templates/mobile_partials/history_cards.html:31` is already a muted
  `dd.mm.yyyy HH:MM · Тип` header line; the second date belongs on a sibling muted `<p>`
  right under it. A card layout has no colspan to break, so the argument that justified
  divergence elsewhere (the CR-01 pagination scar) does not apply here. The same two row-dict
  keys feed both surfaces.

- **D-22: `_SORT_MAP` and `_DEFAULT_ORDER` (`app/services/operations.py:29-32`) are NOT
  changed, and no business-date sort option is added in this phase.** Resolves a direct
  conflict between two research passes: one proposed
  `(business_date desc, created_at desc, seq desc)`, the other proposed leaving it.
  **DATE-04 settles it** — the technical timestamp keeps all three of its jobs *including
  display order*. Pitfall 15's «any sort entry must end in `created_at desc, seq desc`» is
  therefore not triggered this phase.

### Readers, exports and the borderline set (DATE-03/05)

- **D-23: CSV — «Когда» BECOMES the business date; a new «Внесено» column is APPENDED LAST.**
  Applies to `stream_sales_csv` (`app/services/export.py:137-147,156`) and
  `stream_cash_movements_csv` (`:216,219`) only — those are the sole exports touching a
  `business_date`-bearing table. `stream_products_csv` has no date column at all (`:94-102`)
  and `stream_customers_csv`'s «Создан» is `Customer.created_at` (`:179,185`), a table that
  gains no `business_date`; **both are out of scope entirely.**
  Rationale: «Когда» in a single-operator RU warehouse export reads as «когда это случилось»,
  and once back-dating ships the row set of `cash_movements.csv` is chosen by the business
  date (`export.py:211-212` is on the LOCKED must-switch list) — under the additive
  alternative the file's headline date column would routinely contradict the file's own
  period, which is exactly what DATE-03 exists to prevent. Column POSITIONS 1..N do not
  shift, so existing formulas over `Код`/`Цена`/`Сумма` keep working. Accepted cost: column
  1's value type changes from `dd.mm.yyyy HH:MM` to `dd.mm.yyyy`; for pre-migration rows the
  calendar date is unchanged and only `HH:MM` moves, reappearing verbatim in «Внесено».
  Rejected: keeping «Когда» technical and appending «Дата операции»; inserting a new FIRST
  column (shifts everything, strictly dominated); a single column (violates DATE-05).
  **Coupled edit that must not be missed:** `export.py:135` (`ORDER BY Operation.created_at`)
  becomes `(business_date_expr(Operation), Operation.created_at, Operation.seq)`, or the dump
  reads as unsorted by its own first column. DATE-05 applies to `sales.csv` even though it is
  a full dump with no period filter (`app/routes/export.py:36-38`) — it is an `Operation`
  dump and will contain back-dated rows.

- **D-24: Borderline readers — SWITCH these three to the business date:**
  - **«Последняя приёмка» per warehouse** — `app/services/warehouses.py:100`
    (`func.max(Operation.created_at)`, receipts only), labelled «Последняя приёмка» at
    `app/templates/partials/warehouse_rows.html:29`. «When did goods last arrive here» is a
    business fact. `MAX()` over ISO date strings stays correct.
    **This overrides `.planning/research/ARCHITECTURE.md:195`, which said to leave it** —
    that was open operator decision #5 and it is now decided the other way.
    *Coupled edits:* `warehouse_rows.html:75` `| local_dt` → `| ru_date`, AND the comment at
    `warehouse_rows.html:71-74` — which explicitly instructs «this is a full ISO timestamp,
    use `local_dt` not `ru_date`» — must be rewritten, or it becomes actively misleading.
  - **Batch auto-name «{товар} — {дата}»** — `app/services/receipts.py:209-210`. A receipt
    back-dated to 01.09 must not create a batch named «Крем — 04.09.2026» contradicting its
    own receipt line in История. *Ordering constraint for the planner:* the business date
    must be resolved and threaded into `receipts.py` **before** line 209 builds the name —
    passing it only to `record_operation` is not enough. **Existing batch names are snapshots
    and must NOT be migrated** (the snapshot rule is already established by the comment at
    `receipts.py:203-208`).
  - **Identification labels** — «Последний заказ» (`app/services/customers.py:528-540`,
    rendered at `app/templates/partials/customer_insights.html:12`) and «Возврат из продажи
    от …» (`app/routes/returns.py:75,152`; `app/routes/mobile_returns.py:80,156`; rendered at
    `partials/return_form.html:11`, `mobile_partials/return_confirm.html:17`). One date is
    enough on these — they are not DATE-05 both-dates surfaces.
    **Implementation constraint (resolves a real coupling):** `last_order_date` currently
    returns `history[0]["op"].created_at`, relying on `purchase_history`'s
    `created_at DESC, seq DESC` ordering (`customers.py:352`) to make `history[0]` the
    latest. Since D-22 keeps that ordering, switching only the displayed field would show the
    business date of the latest-*entered* row, not the latest purchase. Therefore
    **`last_order_date` is recomputed as `MAX(business_date_expr(...))` over the customer's
    sale rows** — a self-contained change that leaves `purchase_history`'s ordering
    untouched. The return label is the cheap case: `origin.business_date or
    origin.created_at[:10]` + `| ru_date`.

- **D-25: `stale_products` STAYS on `created_at`** — `app/services/reports.py:224`
  (`func.max(Operation.created_at)`) is explicitly NOT switched, and the coupled template
  edit at `app/templates/pages/reports_products.html:32` (`| local_dt` → `| ru_date`) is
  therefore **cancelled — do not make it.** The pre-existing type asymmetry between
  `reports.py:224` (ISO timestamp) and `reports.py:236` (`today_local`, a local date) is
  accepted as-is: it is pre-existing, not introduced by this phase, and is not in scope here.
  Note: `top_selling_products` (`reports.py:201-202`) is a different case — it is
  period-scoped by its own signature (`reports.py:186-188`) and therefore falls under the
  LOCKED DATE-03 list automatically. It switches.

### Claude's Discretion

- The exact wording of the two RU date errors and the 409 message, within the shapes given
  in D-06/D-12.
- Whether the fourth История select's third option reads «Только в день операции» or a
  shorter synonym.
- Placement of the date field inside the mobile shell `<form>` (visible on every step is a
  consequence of the shell, not a separate choice).
- Test naming and file placement, subject to the existing conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition and requirements

- `.planning/ROADMAP.md` § «Phase 33: Back-Dated Operations» — goal, the 5 success criteria,
  the **6 LOCKED ordering constraints** (SYNC-10..13 first; all four columns in ONE
  migration; `add_column` → backfill → THEN extend the trigger; the five-artifact lockstep as
  ONE commit; rollout order server→client; `business_date` gets its own period-bounds
  helper), the owned pitfalls, and the carried `needs verification` list V1–V4, V13–V15.
- `.planning/REQUIREMENTS.md` — SYNC-10..13, DATE-01..08 verbatim; the three operator
  decisions taken at scoping; the explicit Out-of-Scope list.

### Research (v5.0)

- `.planning/research/SUMMARY.md` — the consolidated picture, the risk ranking, the
  «Phase 0 Question» A/B/C pre-work table, and the consolidated `needs verification` list.
  **§Reconciled Disagreements** carries the backfill-method decision (tz-correct Python loop,
  NOT `substr(created_at,1,10)` as a *write-time* backfill) — that is a correctness rule, not
  a preference.
- `.planning/research/ARCHITECTURE.md` — §0 (the sync cursor is `synced_at IS NULL`, NOT
  `created_at`), §2.6 (tz-correct backfill + the byte-identity success criterion), §3.1
  (the explicit-`None`-vs-`server_default` question), §10 (dependency ordering), §12.
  **§195 is OVERRIDDEN by D-24** on «Последняя приёмка».
- `.planning/research/PITFALLS.md` — 1 (new column escapes the trigger), 2 (backfill
  deadlocks against its own new trigger), 3 (`batch_alter_table` drops all four triggers —
  `add_column` only), 4 (a new column silently dropped by an older-code server), 14
  (date-only column vs UTC-timestamp bounds — needs a `display_tz="America/New_York"` test),
  15 (ordering ties), 16 (`business_date` must appear nowhere in `sync.py`/`sync_client.py`/
  `routes/sync.py`), 20, 21. Also `:130` (the exact RU sync message reused in D-08) and
  `:700` («pre-filled and visible», the basis of D-10).
- `.planning/research/STACK.md` — the executed verification that `sa.Date` is disqualified
  twice over and that `String(10)` ISO text is the storage; the rejection list (babel,
  freezegun/time-machine, JS date pickers). **No new dependency is in scope.**
- `.planning/research/FEATURES.md` — D1–D8 feature framing. Note `:134,284` classify the
  «задним числом» marker/filter as D10/R14 «add after validation», which **disagrees with
  `REQUIREMENTS.md:46` (DATE-06) placing it in this phase. The requirement wins.**

### Shipped precedents this phase must copy, not reinvent

- `alembic/versions/0018_*.py` and `alembic/versions/0026_cash_movements_trigger_guards_currency.py` —
  the dual-dialect trigger-rewrite ritual, written twice. `0026` exists solely because the
  five-artifact lockstep was missed once for `cash_movements.currency`.
- `app/db.py::APPEND_ONLY_TRIGGERS` + both `IMMUTABLE_*_COLUMNS` frozensets +
  `tests/test_append_only_cursor.py`'s two constants — the lockstep artifacts.
  `test_trigger_column_list_matches_schema` is the tripwire; **do not "fix" it by editing one
  constant.**
- `app/services/reports.py::operation_currency_clause` — the OUTER-join + COALESCE discipline
  that `business_date_expr` mirrors.
- `app/core.py:108 local_day_bounds_utc` — the SHAPE `business_date_bounds` copies. It is
  **not** modified and **not** deleted (see code_context below).
- `app/services/receipts.py:46-65 parse_optional_expiry` — the service-layer date-parse +
  RU-error idiom D-12 mirrors.
- `app/routes/offline.py:228-243` + `app/templates/offline/result.html:26-29` — the 409
  schema-refusal precedent D-05/D-06 copy at the route layer.
- `app/templates/partials/history_rows.html:132-147` — the documented D-15 «muted second
  line, no extra column» precedent D-18 copies.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `app/services/sync.py:225-235 current_schema_version` — reads the live Alembic revision
  from the DB. The new `push_schema_ok` is its sibling in the same module.
- `app/services/offline.py:61-71 schema_version_ok` — the exact-match predicate. **Read it,
  do not modify it** (D-02).
- `app/services/sync_client.py:186-209 format_sync_message` — the shipped Russian result
  formatter; gains one branch (D-08). `#sync-status` / `#sync-badge` render whatever it
  returns (`app/templates/partials/sync_status.html:15,16`), so no template or CSS work.
- `app/core.py:89-99 format_ru_date` (`ru_date` filter) and `:102-105 iso_to_local`
  (`local_dt` filter) — the two render paths. Every reader switched from a timestamp to a
  date-only column MUST switch filter too, or `iso_to_local("2026-09-01")` produces a naive
  datetime and renders a bogus time (`| ru_date` is the correct filter for a `String(10)`).
- `app/templates/mobile_pages/{receipts,sales,writeoff}.html` — the persistent `<form>` shell
  htmx never swaps, which D-11 exploits. Its behaviour is already documented for `customer_id`
  at `app/templates/mobile_partials/sale_customer.html:29-38`.
- `.muted` (`app/static/style.css:304`) — no new CSS token is needed for D-18/D-19.

### Established Patterns

- **Two write choke points:** `record_operation` (`app/services/ledger.py:37-49`, stamps
  `created_at=utcnow_iso()` at `:123`) and `record_cash_movement`
  (`app/services/finance.py:48-57`). Nothing else may write a ledger row.
- **Append-only triggers enumerate columns by name since 0018** — an unlisted column is
  freely mutable and the ledger fails OPEN, silently.
- **Portable ORM only** — no dialect-specific SQL; the SQLite branch uses `IS NOT`, the
  PostgreSQL branch `IS DISTINCT FROM`.
- **Inline errors redisplay what the operator typed**, service-layer RU constants, 422 on
  re-render, zero writes on refusal. Desktop is uniform; **mobile is not** (D-14).
- **HTMX filter idiom** — six identical attributes on every list filter, plus `qs_parts`
  re-serialization so pagination never loses state (`app/routes/history.py:117-141`, HIST-02).

### Integration Points

- **`local_day_bounds_utc` has 14 call sites in `app/`, and ALL 14 switch to
  `business_date_bounds`. Zero stay.** `app/routes/reports.py:111,145,212`;
  `app/routes/finance.py:89,344,376`; `app/routes/mobile_finance.py:82,347,377`;
  `app/routes/history.py:103`; `app/routes/mobile_history.py:88`;
  `app/services/customers.py:446,468`; `app/services/dashboard.py:95` (whose signature changes
  `(start_iso, end_iso)` → `(start_day, end_day)`). Seven import lines change too:
  `routes/reports.py:10`, `routes/finance.py:17`, `routes/mobile_finance.py:22`,
  `routes/history.py:11`, `routes/mobile_history.py:25`, `services/customers.py:17`,
  `services/dashboard.py:20`.
- **The helper itself must NOT be deleted** even though `app/` stops calling it. `tests/` uses
  it as the sanctioned way to BUILD `created_at` fixtures and to pin the half-open contract:
  `tests/test_core.py:108-150` (4 dedicated tests), `tests/test_export.py:111,150,164,182,333`,
  `tests/test_finance_reports.py:57-337` (12 sites), `tests/test_reports.py:92`,
  `tests/test_dashboard.py:211,215`, `tests/test_attribution.py:228`. Keeping it also honours
  the LOCKED «add a second, parallel helper beside it — do not modify or overload» rule
  (`.planning/research/PITFALLS.md:348`). Add one docstring line saying it is now the
  `created_at`-only helper.
- **⚠ Two different "14"s are in circulation and they are NOT the same set.**
  `.planning/ROADMAP.md:316` says «14 call sites» of `local_day_bounds_utc` (the list above,
  all switching). `.planning/research/SUMMARY.md:221` says «9 must-switch, ~14 must-not»,
  where the 9 are the service-layer `.where()` predicates
  (`.planning/research/ARCHITECTURE.md:175-186`) and the ~14 must-not are the `created_at`
  ordering/audit sites (`ARCHITECTURE.md:191-197`). **The full edit set is 9 service-layer
  predicates PLUS 14 bounds-producing call sites — not 14 total.** A planner skimming both
  documents will conflate them.
- **Service-layer predicates that MUST switch (the 9):** `reports.py:72-73` (sales-profit —
  the DATE-07 byte-identity target), `reports.py:145-146` (write-off report),
  `reports.py:201-202` (top-selling, period-scoped by its own signature `:186-188`),
  `finance_reports.py:33-34` (`cash_expense_total`), `finance_reports.py:126-127`
  (`cash_flow_report` — must move together with the line above or the reconciliation invariant
  documented at `finance_reports.py:115-118` breaks), `customers.py:415-416` (`_spend_stmt`),
  `operations.py:151-154` (`history_view` — **BOTH `stmt` and `count_stmt`**, or the count
  disagrees with the rows), `export.py:211-212` (the period-scoped CSV), plus `export.py:135`
  (`ORDER BY`, per D-23).
- **MUST NOT switch:** every `.order_by(created_at desc, seq desc)` «recent N» feed
  (`finance.py:21`, `dashboard.py:156`, `sales.py:374`, `receipts.py:309`, `writeoffs.py:127`,
  `transfers.py:210`, `catalog.py:351`, `customers.py:352`, `ledger.py:239`) — these answer
  «what did I just enter?», and switching would make a just-entered back-dated row vanish from
  the list the operator uses to confirm the entry landed. Also: `sync.py:68,76` and
  `merge.py:89,456` (sync cursor / required ledger field — one of `created_at`'s three LOCKED
  jobs); `export.py:185` and `:94-102`; `batches.py:97-98` (`expiring_batches` reads only
  `Batch.expiry`, its own unrelated shelf-life date — **confirmed untouched**);
  `batches.py:55,71,98` (`Batch.created_at` tiebreaker); `customers.py:93-115,321-333`
  (`CustomerContact.created_at`, a hand-built monotonic key); `active_catalog.py:36,66` and
  `dashboard.py:41,60-72`; `ledger.py:123,234`.
- **`tests/conftest.py:23-30` builds the schema with `Base.metadata.create_all`** (server DB at
  `:292-297`) — this is research item V3, and it is now ANSWERED: the trigger-liveness test is
  NOT migration-proving, so SYNC-13's added test must build via `alembic upgrade head`. It is
  also why D-03's `""` escape hatch is mandatory.
- **`CashMovement.currency` is `nullable=False` (`app/models.py:526-528`)** and
  `merge._ledger_row` (`:460`) builds `{column: data.get(column) ...}` — the key is always
  PRESENT, valued `None` — then `_insert_new` runs `session.execute(insert(model), rows)`
  (`merge.py:298-301`), which appears to bypass both the Python `default=` and the DDL
  `server_default`. **This is load-bearing for D-01:** the asymmetric gate's «accept behind»
  promise is only true once SYNC-12 fixes `_ledger_row`. SYNC-12 is ordered first anyway.

</code_context>

<specifics>
## Specific Ideas

- The «задним числом» subline copy should read as one line carrying both facts, e.g.
  `задним числом · внесено 04.09.2026 15:22` — not a bare badge plus a separate date.
- The 409 message names BOTH versions and tells the operator which side to update; because
  the gate is asymmetric it can always say «Обновите сервер» without ambiguity.
- The Russian sync-status string is not invented here — reuse
  «Сервер ещё не обновлён — синхронизация отложена» from `.planning/research/PITFALLS.md:130`.

</specifics>

<deferred>
## Deferred Ideas

- **Sticky business date across a session (research D11).** Offered during discussion as a
  cheap hedge — echoing `form.op_date` into the post-success re-render on the four
  save-and-next desktop forms (`partials/receipt_form.html:5`, `sale_form.html:5`,
  `writeoff_form.html:6`, `correction_form.html:8`, which all currently re-render blank with
  `focus_code`) rather than resetting to today. **Not taken** — the operator chose the plain
  option. Without it, entering ten receipts from one paper sheet dated last Tuesday means
  re-picking that date ten times. Revisit if that friction shows up in real use.
- **`stale_products` on the business date** — explicitly declined (D-25). The pre-existing
  type asymmetry at `reports.py:224` vs `:236` stays and is not this phase's problem.
- **Collapsed `<details>` date disclosure on the sale form** — rejected now (D-10), but named
  as the correct follow-up *if* the always-visible field measurably slows the sale flow.
- **`.filter-bar` needs `flex-wrap`** — `app/static/style.css:188-193` sets none (unlike
  `.toolbar` at `:72-77`), so the fourth select from D-20 may overflow at narrow desktop
  widths. A one-line fix, but it touches every `.filter-bar` page, so it is a separate
  decision. `needs verification`: open `/history` at 1024 px and look for a horizontal
  scrollbar.

### Reviewed Todos (not folded)

- `2026-08-31-price-lists-backfill.md` — matched at score 0.2 on the keyword «created» only;
  it concerns price-list backfill, not business dates. Reviewed and left out of scope.

</deferred>

<open_verification>
## `needs verification` carried into planning

Blocking (each *determines* what the migration says — from `.planning/ROADMAP.md:320`):

- **V1** — does an explicit `None` beat `server_default` in
  `session.execute(insert(model), rows)`? Also exposes the `CashMovement.currency` NOT NULL
  bug. *Check:* the 6-line inverted merge test drafted at
  `.planning/research/ARCHITECTURE.md:281-285` — build a cash record, `record.pop("currency")`,
  `apply_merge`, observe `IntegrityError` vs a landed `'RUB'`. **Load-bearing for D-01.**
- **V2** — what an older-*code* receiver does with an unknown wire field. *Check:*
  monkeypatch `merge.KIND_TO_FIELDS` to the pre-change set, apply a batch carrying the new
  key, assert reject-not-drop.
- **V3** — **ANSWERED during this discussion:** `tests/conftest.py:23-30` builds via
  `create_all`, so the trigger-liveness test is not migration-proving. SYNC-13 must add a test
  that builds via `alembic upgrade head`.

Phase-level:

- **V4** — does the backfill UPDATE trip the pre-rewrite trigger, and does it cover every row?
  *Check:* run against a copy of the s1 dump; assert rows-updated == rows-total.
- **D-13's htmx question** — does htmx 2.0.10 halt a `max`-violating submit silently?
  *Check:* browser, `/receipts`, clear «Код», click save, watch for a native bubble.

Pre-rollout:

- **V13** — is s1's `alembic_version` at `0026` today? *Check:*
  `docker compose -f docker-compose.prod.yml exec ori-app uv run alembic current` on s1.
- **V14** — what `display_tz` does s1's `.env.production` actually set? It **parameterises the
  backfill**. *Check:* read the file on s1.
- Is any deployed client's `alembic_version` below `0024`? Determines whether V1 is live risk
  or theory.

Advisory:

- **V15** — is alembic 1.19.1 still the newest? **Do not bump regardless.**
- Whether the operator maintains a spreadsheet over `sales.csv` / `cash_movements.csv` — the
  single input that would have flipped D-23; the operator chose option A without needing it,
  so this is now informational only.

</open_verification>

---

*Phase: 33-back-dated-operations*
*Context gathered: 2026-09-04*
