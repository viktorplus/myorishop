---
status: diagnosed
trigger: "sale-lookup-name-not-filling: In the sale form basket row, typing a price then quickly typing a known product code does not autofill the product name field at all (the debounced lookup that should populate \"Название\" from the \"Код\" input appears to not be firing / not filling the name)."
created: 2026-07-09T00:00:00Z
updated: 2026-07-09T00:01:00Z
---

## Current Focus

hypothesis: CONFIRMED — /sales/lookup query-param names (code, name, price) do not match the sale_row.html basket input name attributes (code[], name[], price[]), so hx-include="closest tr" (plus the triggering code[] input itself) sends bracketed keys the FastAPI route never binds. code arrives as "" server-side -> lookup_prefill(session, "") returns None -> route returns 204 -> htmx no-ops (per documented convention) -> name field is NEVER filled, in any scenario (not specific to typing price first).
test: TestClient GET /sales/lookup with bracketed query keys (code[]=..., name[]=..., price[]=...) as hx-include actually produces, vs unbracketed (code=..., name=..., price=...).
expecting: bracketed request -> 204 (bug reproduced); unbracketed request -> 200 with name-wrap HTML containing the looked-up name.
next_action: none — root cause confirmed with direct evidence; investigation complete for find_root_cause_only mode.

## Symptoms

expected: The in-flight lookup response does not clobber the price the operator already typed (oob-swap guard holds) — implies baseline behavior (lookup by code autofills the name field ~300ms after typing) works, and typing a price first must not get wiped by that lookup response.
actual: "не подставляется имя товара после ввода цены - ввода кода." Name-fill does not happen at all when operator types a price first, then types a code.
errors: None reported (manual UAT, no dev tools inspected yet)
reproduction: Phase 4 UAT Test 2 (.planning/phases/04-sales-customers/04-UAT.md) — on /sales/new, in a basket row: type into "Цена продажи" first, then type a known product code (e.g. "32021") into "Код", observe "Название" never populates.
started: Discovered during manual UAT of Phase 4 (sales-customers), already executed and code-reviewed earlier. Regression/gap found only now during human browser testing.

## Eliminated

- hypothesis: The client-side hx-on::before-swap / hx-on::oob-before-swap guards in sale_form.html incorrectly block the primary name swap when the price field is already non-empty.
  evidence: Read app/templates/partials/sale_form.html lines 31-32. The before-swap guard checks event.detail.target.id.startsWith('name') AND the CURRENT (pre-swap) name input's own value.trim() — it never inspects the price field. The oob-before-swap guard checks event.detail.target.id.startsWith('price') — scoped only to the price OOB target. These guards are correctly scoped to their own swap targets and mirror the working receipt_form.html precedent (lines 18-21). Confirmed via TestClient reproduction below that the server itself never even emits the primary name-wrap HTML when price is pre-filled and code is sent bracketed — so the client-side guard is never reached; the request fails before that.
  timestamp: 2026-07-09T00:01:00Z

- hypothesis: /sales/lookup route logic (lookup_prefill / 204-vs-200 branching) has a bug for products with a price already set.
  evidence: Direct TestClient GET /sales/lookup?code=<real_code>&name=&price=15,00&row= (unbracketed, matching the route's declared param names) returned 200 with correct `<td id="name-wrap">...<input ... value="Товар со склада"></td>` and (correctly) NO oob price swap block, since fill_price=False when price is already non-empty. Server logic for the "price already typed" branch is correct.
  timestamp: 2026-07-09T00:01:00Z

## Evidence

- timestamp: 2026-07-09T00:00:30Z
  checked: app/templates/partials/sale_row.html (code input) and app/templates/partials/sale_form.html (guard handlers)
  found: The "Код" input has name="code[]" (array-form, required so the whole basket row posts correctly to POST /sales which expects list[str] = Form([], alias="code[]") etc. per app/routes/sales.py sale_create). It also carries hx-get="/sales/lookup" hx-include="closest tr" hx-vals='{"row": "..."}'. hx-include picks up every input in the row: code[], name[], qty[], price[] — all bracket-suffixed names.
  implication: Every GET request to /sales/lookup triggered from the code field serializes its params using the bracketed input names (code[]=..., name[]=..., price[]=...), NOT the bare names the FastAPI route expects.

- timestamp: 2026-07-09T00:00:45Z
  checked: app/routes/sales.py sale_lookup() route signature (lines 71-96)
  found: def sale_lookup(request, code: str = "", name: str = "", price: str = "", row: str = "", session=...). Declared query param names are bare (code, name, price) with no alias — unlike the POST /sales route below it, which explicitly uses Form([], alias="code[]") for the array fields.
  implication: FastAPI/Pydantic binds query params by exact name; a query string containing code[]=X does NOT populate the code parameter. code stays at its default "".

- timestamp: 2026-07-09T00:01:15Z
  checked: Ran two TestClient GET /sales/lookup requests against a real seeded stocked_product (via a throwaway scratch pytest file, deleted after use — not part of the deliverable): (1) params={"code": <code>, "name": "", "price": "15,00", "row": ""} (unbracketed) -> 200, body contains the correct name-wrap HTML with the product's name. (2) Same values sent as raw query string code[]=<code>&name[]=&price[]=15,00&row= (bracketed, exactly matching what hx-include="closest tr" actually serializes from the real DOM input name attributes) -> 204 No Content, empty body.
  implication: This is a direct, reproducible confirmation of the root cause. The real browser request (bracketed keys) always produces 204 regardless of whether price was typed first — the "price first" framing in the UAT reproduction is incidental; the underlying bug breaks the code-lookup name-autofill unconditionally, in every case, because the request never actually carries a usable `code` value server-side.

- timestamp: 2026-07-09T00:01:20Z
  checked: app/services/sales.py lookup_prefill(session, code)
  found: `code = code.strip(); if not code: return None` (line 201-203).
  implication: An empty code (as arrives when the query key is code[] instead of code) always returns None, and the route then returns Response(status_code=204). Per the project's own documented convention ("the SERVER decides fill vs no-op; htmx ignores 204" — sale_row.html comment, sales.py comment), htmx performs no swap at all on a 204 — this is why "Название" never gets populated, matching the reported symptom exactly ("does not get filled in... at all").

- timestamp: 2026-07-09T00:01:25Z
  checked: app/templates/partials/receipt_form.html (the precedent this pattern was adapted from) for comparison
  found: The receipt form's single-line inputs use bare names (name="code", name="name", name="cost", etc. — no array brackets), because /receipts POST is a single-line form, not a multi-row basket. hx-include="[name='name'],[name='cost'],[name='sale'],[name='catalog']" and the /receipts/lookup route's bare query params line up correctly there.
  implication: The bug is specific to how the receipts single-line lookup pattern was adapted to the sales basket's array-form inputs (code[]/name[]/qty[]/price[]) — the GET /sales/lookup route signature was never updated to accept the bracketed names (e.g. via Query(alias="code[]") or by reading raw query params), unlike the sibling POST /sales route which correctly uses alias="code[]" etc.

## Resolution

root_cause: |
  app/routes/sales.py `sale_lookup()` (GET /sales/lookup, lines 71-96) declares its query
  parameters as bare names: `code: str = ""`, `name: str = ""`, `price: str = ""`. But the
  basket row inputs that supply these values (app/templates/partials/sale_row.html) are
  array-form fields named `code[]`, `name[]`, `qty[]`, `price[]` — required so the row posts
  correctly to `POST /sales` (which declares `Form([], alias="code[]")` etc. in the same file).
  The code input's own `hx-include="closest tr"` (plus its own `name="code[]"` attribute as
  the triggering element) causes every /sales/lookup GET request to be sent with bracketed
  query keys (`code[]=...&name[]=...&price[]=...`), which FastAPI never binds to the route's
  bare `code`/`name`/`price` parameters. `code` therefore always arrives as `""` server-side.
  `lookup_prefill(session, "")` (app/services/sales.py:201-203) returns `None` for an empty
  code, so the route always answers `204 No Content`. Per this app's own documented
  htmx convention, a 204 response produces no swap at all — so "Название" is never populated,
  for ANY code lookup on the sales basket row, not only when a price is typed first. This is a
  total break of SAL lookup-by-code autofill on the /sales/new page, introduced when the
  receipts single-line lookup pattern (bare field names) was adapted to the sales basket's
  array-form field names without updating the GET /sales/lookup route signature to match.
fix: (not applied — find_root_cause_only mode)
verification: (not applicable — find_root_cause_only mode)
files_changed: []
