// app/static/price-cue.js — PROD-06 / D-10
// One delegated listener: covers desktop, mobile, and HTMX-added basket rows
// with no re-initialisation (D-12: never a round-trip per keystroke — swapping
// a focused input destroys focus AND caret, and sale_row.html's price[] inputs
// have no id for htmx to restore focus to).
//
// D-13: this is NOT client-side money math. The cue is advisory — it never
// parses for submission, computes, or persists. parse_optional_cents
// (app/services/catalog.py:106) stays the sole authority and the server
// re-renders the authoritative cue on every response. Parity with core.py:28
// to_cents is a one-liner: strip + comma→dot; space-separated thousands are
// rejected by both. Float math can flip the cue ONLY exactly at the equality
// boundary (12,505 → 1250 client vs 1251 server) — harmless for a hint, and
// the server re-render is the tiebreaker.
document.addEventListener("input", function (event) {
  const field = event.target;
  const ref = field.dataset ? field.dataset.refCents : null;
  if (!ref) return;                       // no reference → no cue (D-07: the MAIN path)
  const cents = Math.round(parseFloat(field.value.trim().replace(",", ".")) * 100);
  field.classList.remove("price-below", "price-above");
  if (!Number.isFinite(cents) || cents === Number(ref)) return;  // equal → neither (criterion 3)
  field.classList.add(cents < Number(ref) ? "price-below" : "price-above");
});
