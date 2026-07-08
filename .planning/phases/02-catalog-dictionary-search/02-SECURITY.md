---
phase: 2
slug: catalog-dictionary-search
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-08
---

# Phase 2 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| browser forms → FastAPI routes | untrusted operator input (code/name/category/money strings, product_id path params) | form strings, low sensitivity |
| search box → GET /products/search | untrusted free-text query (Cyrillic, wildcards, HTML) | query string |
| browser → /dictionary POSTs, /dictionary/lookup GET | untrusted code/name strings; lookup echoes dictionary names into product form | form strings / HTML fragment |
| service layer → SQLite | all writes must stay parameterized ORM | SQL parameters |
| edit flow → operations ledger | price history must be tamper-proof once written | audit rows |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-2-01 | Tampering | product/dictionary POSTs, search q | mitigate | typed Form params (garbage → 422: products.py:88-90,149-151; dictionary.py:56-61,82-87); to_cents rejects non-finite (core.py:42-46); ORM-only (no raw SQL with user input); 404 on unknown id; RU validation messages | closed |
| T-2-02 | Tampering/DoS-lite | LIKE wildcard injection in search q | mitigate | `_escape_like` escapes `\ % _` (catalog.py:278-280), `escape="\\"` (catalog.py:295), `.contains(q_lc, autoescape=True)` (catalog.py:303), LIMIT 20 (catalog.py:294,306) | closed |
| T-2-03 | Tampering (XSS) | names/category/search echo rendered in templates | mitigate | Jinja2 autoescape on (routes/__init__.py:8); zero `\| safe` in templates; match segments split in Python, `<mark>` is literal template HTML (product_rows.html:22-23,35; name_input.html:5) | closed |
| T-2-04 | Repudiation/Tampering | operations ledger (audit rows, price history) | mitigate | append-only triggers block UPDATE/DELETE (alembic 0001:40-47; db.py:22-33); regression tests test_ledger.py:48,58; trigger-survival test_catalog.py:208-213; price history read-only SELECT | closed |
| T-2-05 | Tampering (CSRF) | all POST endpoints | accept | loopback-only bind `--host 127.0.0.1` (run.bat:10); single local operator, no auth in v1; delete gated by hx-confirm (product_form.html:86); revisit with AUTH-V2-01 | closed |
| T-2-06 | Tampering | stock manipulation via forms/lookup | mitigate | no form field maps to quantity; quantity assigned only inside record_operation (ledger.py:81) and rebuild_stock (no route exposure); GET /dictionary/lookup read-only (dictionary.py routes:27-40, service SELECT-only) | closed |
| T-2-SC | Tampering | supply chain | accept | zero new packages this phase — no phase-02 commit touches pyproject.toml/uv.lock (verified via git log) | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-2-01 | T-2-05 | CSRF: v1 binds to 127.0.0.1 only, single local operator, no auth surface; destructive actions gated by hx-confirm. Revisit with AUTH-V2-01 when multi-user sync lands | operator (plan-time disposition) | 2026-07-08 |
| AR-2-02 | T-2-SC | Supply chain: zero new packages installed in Phase 2 (dependency files untouched since Phase 1) | operator (plan-time disposition) | 2026-07-08 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-08 | 7 | 7 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-08
