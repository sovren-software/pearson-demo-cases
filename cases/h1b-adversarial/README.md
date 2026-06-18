# Pearson — H-1B adversarial (negative) case files

Eight **synthetic** H-1B packets, each a happy-path case (see `../h1b/`) with
**exactly one injected defect** that a serious intake system must catch. All data
is fictional — no real PII; passports are watermarked **SPECIMEN**.

Where `../h1b/` proves the **happy path** (clean docs extract correctly),
this tier proves the **validation gates** — the product's actual differentiator.
The spec (which gate each case must trip) is **`VALIDATION-SPEC.md`**.

## The eight cases

| Slug | Base | Defect | Trips gate | Cross-doc |
|------|------|--------|-----------|:--:|
| `wage-below-prevailing` | arjun-kumar | offered wage $120k < LCA prevailing $131,019 | `wage_below_prevailing` | ✓ |
| `identity-name-mismatch` | arjun-kumar | offer/support say "Kumarr"; passport/I-94 say "KUMAR" | `identity_name_mismatch` | ✓ |
| `soc-code-mismatch` | yangben-zhengjian | LCA SOC 15-1252 ≠ offer 15-1243 | `soc_code_mismatch` | ✓ |
| `worksite-outside-lca-area` | yangben-zhengjian | offer worksite Portland OR; LCA certifies Seattle WA | `worksite_outside_lca_area` | ✓ |
| `employer-name-mismatch` | arjun-kumar | offer "Northwind Analytics, Inc." vs LCA "Northwind Analytics LLC" (same EIN) | `employer_name_mismatch` | ✓ |
| `employer-ein-mismatch` | yangben-zhengjian | offer EIN 84-2910736 vs LCA EIN 82-7654321 (same name) | `employer_ein_mismatch` | ✓ |
| `passport-expired-before-period` | abigail-medina | passport expires 2026-09-30, before the 2026-10-15 start | `passport_expired_before_period` | — |
| `mrz-checkdigit-corrupt` | arjun-kumar | passport MRZ line-2 passport-number check digit flipped | `mrz_checkdigit_corrupt` | — |

Each case folder holds only the client-facing artifacts (`passport.png`,
`offer/lca/i94/degree/support-letter.pdf`) plus a `ground-truth.json` that adds two
keys — `defect` (the single injected flaw) and `expected_gates` (the gate that MUST
fire, with `evidence` carrying the exact contradicting values). The editable HTML
render-sources live under `_src/` (see the happy-path README).

## Status

All eight gates are **implemented + tested** against this corpus:
- `mrz_checkdigit_corrupt` — `extract::classify_passport_mrz` → `mrz-validation` gate.
- The seven cross-document gates — `validate::validate_cross_document` →
  `intake-validation` gates. Proven by `python validator/validate.py
  validate.py adversarial` (every fixture fires exactly its `expected_gates`). The two
  petitioner-consistency gates (`employer_name_mismatch`, `employer_ein_mismatch`)
  cover the offer-vs-LCA entity divergence.

See `VALIDATION-SPEC.md` for the gate catalog, the `validator/validate.py` reference implementation, and the
remaining checks (status-gap, degree-relatedness, etc.) for a follow-on tier.

## Regenerate

```sh
python3 generator/generate_cases.py --adversarial-only
```

`--adversarial-only` rebuilds just this tier; it does **not** touch the committed
happy-path fixtures (whose PDFs carry render timestamps). The corrupt MRZ is
produced by building a valid ICAO 9303 MRZ, then flipping `line2[9]` (the
passport-number check digit) — so the failure is detectable only by re-running the
check-digit algorithm, exactly as a real OCR error or tampered document would be.
