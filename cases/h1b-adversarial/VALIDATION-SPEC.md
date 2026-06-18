# Pearson — H-1B intake validation spec (adversarial corpus)

This corpus is the **executable spec** for a conformant cross-document validation
layer — the differentiator vs extraction-only incumbents (Docketwise IQ, BAL
Cobalt, Parley all already read documents + detect missing ones; the moat is
**contradiction / consistency / sufficiency** reasoning).

Each adversarial case in this directory is a happy-path packet with **exactly one
injected defect** and an `expected_gates` block in its `ground-truth.json`.

> **Right-pass discipline.** A case PASSES only when the *named* gate fires — not
> merely when *some* gate fires or extraction simply "fails." This mirrors the
> right-pass discipline: a pass must be the *correct* pass. A case that fails for
> the wrong reason is a fail.

## Gate catalog (the 6 in this corpus)

| Gate | Category | Detects | Docs | Cross-doc | Severity | Affected form | Status |
|------|----------|---------|------|:--:|----------|---------------|--------|
| `mrz_checkdigit_corrupt` | document-integrity | passport MRZ fails an ICAO 9303 check digit → identity facts can't be validated | passport | — | rfe | I-129 Part 3 | **IMPLEMENTED** — MRZ check-digit validation |
| `wage_below_prevailing` | wage-compliance | offered wage < certified LCA prevailing wage | offer, lca | ✓ | denial | I-129 Part 5 + LCA | **IMPLEMENTED** (`validator/validate.py`) |
| `identity_name_mismatch` | identity-consistency | beneficiary name differs across passport/I-94 vs offer/support | passport, offer, i94 | ✓ | rfe | I-129 Part 3 | **IMPLEMENTED** (`validator/validate.py`) |
| `soc_code_mismatch` | lca-correspondence | LCA SOC ≠ offer/petition occupation | offer, lca | ✓ | rfe | I-129 + LCA | **IMPLEMENTED** (`validator/validate.py`) |
| `worksite_outside_lca_area` | lca-correspondence | petition worksite outside the LCA-certified area (Matter of Simeio) | offer, lca | ✓ | rfe | LCA + I-129 Part 5 | **IMPLEMENTED** (`validator/validate.py`) |
| `employer_name_mismatch` | petitioner-consistency | petitioner legal name on the LCA ≠ the offer letter (genuine entity divergence, e.g. Inc vs LLC — company-name normalization strips punctuation/casing but keeps words) | offer, lca | ✓ | rfe | I-129 Part 1 + LCA | **IMPLEMENTED** (`validator/validate.py`) |
| `employer_ein_mismatch` | petitioner-consistency | petitioner FEIN on the LCA ≠ the offer letter (digit-only compare, so `47-3829150` == `473829150`) | offer, lca | ✓ | rfe | I-129 Part 1 + LCA | **IMPLEMENTED** (`validator/validate.py`) |
| `passport_expired_before_period` | passport-validity | passport expires before the requested employment period | passport | — | blocker | passport | **IMPLEMENTED** (`validator/validate.py`) |

`IMPLEMENTED` = a real gate fires today. All eight gates are now built and tested
against this corpus (the corpus was the TDD target). The two petitioner-consistency
gates are part of this corpus; the extension closes their
document-fixture coverage gap (2026-06-12).

## The one implemented gate — `mrz-validation`

`passport_facts_from_mrz` already validates ICAO 9303 check digits via `mrtd` and
**rejects** a failing MRZ by returning *no facts* — correct, but previously
**silent** (the beneficiary-identity fields just stayed empty). This change
surfaces that rejection:

- `extract::classify_passport_mrz(mrz, src) -> PassportRead::{Validated|NeedsReview}`
  (pure, deterministic, unit-tested against the `mrz-checkdigit-corrupt` fixture).
- `extract_document_to_facts` raises an `mrz-validation` review gate
  (`required_role: immigration.attorney`) when a passport yields no validated
  facts — for every extraction consumer, at the chokepoint where facts are written.

## The cross-document layer (`validator/validate.py`)

A conformant validator implements these 5 cross-document checks (reference implementation: `validator/validate.py`). They
operate on `ValFact`s — each extracted fact tagged with its **source document
kind** — so the same predicate from `offer` vs `lca` (or `passport` vs `offer`) is
the contradiction signal. `validate_cross_document(&[ValFact])` returns one
`ValidationFinding` per inconsistency; `validate_and_gate(store, engagement, facts)`
raises one `intake-validation` review gate (`required_role: immigration.attorney`)
per finding. Wage + name needed two new extraction fields (`prevailing_wage`,
`beneficiary_full_name` on `EMPLOYMENT_FIELDS`); SOC/worksite/expiry use fields
already extracted.

Severity → routing: `blocker` (cannot proceed) > `denial` (statutory ground) >
`rfe` (deficiency) — a UI could sort the pending-reviews pill by this.

## Verification

- `python validator/validate.py adversarial` — runs the gate checks: happy-path
  raises nothing; each defect fires exactly its gate; two false-positive guards
  (same-area-different-formatting, zero prevailing wage).
- `python validator/validate.py adversarial` — deterministic
  regression over the committed corpus: every fixture's `expected_gates` fires
  (and only that gate); the MRZ fixture routes to its single-document gate.
- `e2e-demo` accumulates `ValFact`s from extraction and reports findings — the
  happy-path corpus must validate **clean** (the validators don't false-positive
  on real extracted data).

## Remaining (not in this tier)

The other 6 of the research top-12 — wage-level-vs-duties plausibility,
degree-relatedness, status-gap / maintenance-of-status, LCA certified+signed+dated,
foreign-degree evaluation present, employer-employee relationship — plus
modality-robustness fixtures (scans, skew, noise). Add as a follow-on tier.

## Grounding (sources)

- USCIS FY24 H-1B characteristics report (RFE volume); USCIS Policy Manual Vol 2
  Pt A Ch 4 (maintenance of status); USCIS I-129 checklist.
- DOL 20 CFR 655.731 (prevailing/actual wage); SOC/wage-level RFE guidance.
- *Matter of Simeio Solutions* (2015) — worksite outside the area of intended
  employment requires an amended LCA + petition.
- ICAO Doc 9303 — TD3 MRZ, 7-3-1 check-digit weighting.

Full research digest (top-12 checks, with the other 6 to add next — wage-level
plausibility, degree-relatedness, status-gap/maintenance, LCA-certified/signed,
foreign-degree evaluation, employer-employee relationship): candidate extensions to this corpus.

## Regenerate

```sh
python3 generator/generate_cases.py --adversarial-only   # 6 cases, happy-path untouched
```
