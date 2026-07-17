// app/static/sale-total.js — SALE-02 / D-08 / D-09
// One delegated listener: covers desktop basket rows, HTMX-added rows, and
// the mobile basket's accumulator inputs with no re-initialisation — the
// same architecture as app/static/price-cue.js (one top-level
// document.addEventListener("input", ...), no init function, no
// DOMContentLoaded, no per-element binding, cheapest early-return guard
// first).
//
// ADVISORY ONLY: register_sale (app/services/sales.py:282) is the sole
// authority on the charged amount. Nothing computed here is submitted —
// #sale-total carries no name= and no form control (T-22-03), so the
// browser's money math is structurally incapable of reaching the server.
//
// Deliberate no-float divergence from price-cue.js: price-cue.js:19 may use
// Math.round(parseFloat(...)) because it only COMPARES against a reference
// and the server re-stamps data-ref-cents authoritatively on every render.
// sale-total.js DISPLAYS a computed sum with no server-rendered fallback, so
// any float rounding drift would be visible to the operator. Every parse
// here is string -> integer cents with ZERO float arithmetic anywhere
// (CLAUDE.md "never use FLOAT for money").
//
// Accept-set divergence from the server's to_cents (app/core.py:28), bounded
// and deliberate (22-RESEARCH.md Pattern 2, verified by execution):
//   accepted here AND by server: "7", "12,50", "12.50", ".5", "5.", "12.505"
//   accepted by server, marked "неполный" here: "1e3", "1_000", "１２", "+12.5"
//   rejected by BOTH: "1 000", "12abc", "", "inf", "nan", "12,5,0"
// Byte-exact JS parity with Decimal(str) (exponents, PEP-515 underscores,
// signs, Unicode digit scripts) is not achievable in a regex and must not be
// attempted. A false "неполный" on an accepted-by-server-only value is
// harmless on an advisory display (an operator never types an exponent into
// a price field); a wrong number would not be.

// Money regex omits the sign on purpose: services/sales.py:157 rejects a
// negative sale price outright, so a negative is correctly "incomplete",
// not a negative subtotal.
const MONEY_RE = /^(?:\d+(?:[.,]\d+)?|[.,]\d+)$/;

// Qty class is written [0-9], NOT \d. This is not because \d would behave
// differently in JavaScript — \d IS exactly [0-9] there, with or without
// the u flag; the Unicode-wide behavior is Python's re module on str, not
// JS — but because [0-9] states the ASCII-only contract on its face for a
// reader comparing this line against the server's isascii() guard
// (services/sales.py:136-139).
const QTY_RE = /^[0-9]+$/;

function moneyToCents(text) {
  const t = String(text).trim();
  if (!MONEY_RE.test(t)) return null;
  const parts = t.replace(",", ".").split(".");
  const whole = parts[0] === "" ? 0 : Number(parts[0]);
  const frac = ((parts[1] || "") + "000").slice(0, 3);
  let cents = whole * 100 + Number(frac.slice(0, 2));
  // ROUND_HALF_UP mirror (core.py:44) — ties away from zero: 12,505 -> 1251.
  if (Number(frac[2]) >= 5) cents += 1;
  return Number.isSafeInteger(cents) ? cents : null;
}

function qtyToInt(text) {
  const t = String(text).trim();
  if (!QTY_RE.test(t)) return null;
  const n = Number(t);
  return Number.isSafeInteger(n) && n > 0 ? n : null; // sales.py:138 `qty <= 0`
}

// Mirror of core.py:49 format_cents — sign prefix, comma separator, 2 fraction digits.
function formatCents(cents) {
  const sign = cents < 0 ? "-" : "";
  const a = Math.abs(cents);
  return sign + Math.trunc(a / 100) + "," + String(a % 100).padStart(2, "0");
}

function recalcSaleTotal() {
  const box = document.getElementById("sale-total");
  if (!box) return; // not on a sale surface — the script loads on every page via the shell

  let cents = 0;
  let units = 0;
  let incomplete = false;

  const rows =
    box.dataset.rows === "mobile"
      ? document.querySelectorAll("#wizard-basket .mobile-card")
      : document.querySelectorAll("#basket-rows tr");

  for (const row of rows) {
    const codeEl = row.querySelector('[name="code[]"], [name="code_acc[]"]');
    const qtyEl = row.querySelector('[name="qty[]"], [name="qty_acc[]"]');
    const priceEl = row.querySelector('[name="price[]"], [name="price_acc[]"]');
    if (!qtyEl || !priceEl) continue; // skips sale_row.html's batch-wrap <tr>

    // Row-counting mirrors the server's non_blank_lines filter
    // (services/sales.py:90-94): a row counts only if ANY of code/qty/price
    // is non-blank — the always-present empty last row is skipped silently
    // and must NOT trigger the marker.
    const anyFilled = [codeEl, qtyEl, priceEl].some((el) => el && el.value.trim());
    if (!anyFilled) continue;

    const q = qtyToInt(qtyEl.value);
    const p = moneyToCents(priceEl.value);
    if (q === null || p === null) {
      incomplete = true; // D-09: skip this row's contribution, never drop the marker silently
      continue;
    }
    cents += q * p;
    units += q;
  }

  // .textContent only — never innerHTML (customer_picker.html:1-12 house rule;
  // also an XSS vector if product names ever entered the string).
  box.querySelector("#sale-total-amount").textContent = formatCents(cents);
  box.querySelector("#sale-total-units").textContent = String(units);
  box.querySelector("#sale-total-warning").hidden = !incomplete;
}

// THREE recompute triggers — the single likeliest silent bug in SALE-02
// (22-RESEARCH.md Pitfall 2, verified both extra paths):
// 1. Typing path.
document.addEventListener("input", function (event) {
  const field = event.target;
  const name = field.getAttribute && field.getAttribute("name");
  if (
    name === "qty[]" ||
    name === "price[]" ||
    name === "code[]" ||
    name === "qty_acc[]" ||
    name === "price_acc[]" ||
    name === "code_acc[]"
  ) {
    recalcSaleTotal();
  }
});
// 2. The 422/oversell re-render re-echoes the operator's values into fresh
//    DOM and fires NO input event.
document.body.addEventListener("htmx:afterSettle", recalcSaleTotal);
// 3. Exposed so both delete buttons can call it; a plain DOM .remove() fires
//    neither an input NOR an htmx event.
window.recalcSaleTotal = recalcSaleTotal;
