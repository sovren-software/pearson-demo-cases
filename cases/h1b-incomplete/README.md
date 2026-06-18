# Pearson — H-1B incomplete ("not-enough") case files

Four **synthetic** H-1B packets, each a happy-path case (see `../h1b/`) with
**exactly one required document or field MISSING** — the "not-enough" half of real
intake. A real client forgets the LCA, sends an offer letter with no salary, omits the
I-94. All data is fictional — no real PII; passports are watermarked **SPECIMEN**.

Where `../h1b/` proves the **happy path** and `../h1b-adversarial/` proves
the **contradiction** gates, this tier proves the **completeness** gates — the product
catching what the client *didn't* send, not just what's wrong with what they did.

## The four cases

| Slug | Base | Missing | Trips gate | Severity |
|------|------|---------|-----------|:--:|
| `missing-lca`     | yangben-zhengjian | no certified LCA (ETA-9035)        | `missing_required_document` | blocker |
| `missing-degree`  | abigail-medina    | no degree / credential evaluation  | `missing_required_document` | blocker |
| `missing-i94`     | arjun-kumar       | no I-94 record                     | `missing_required_document` | blocker |
| `missing-wage`    | arjun-kumar       | offer present but states **no salary** | `missing_required_field` | rfe |

The first three drop a whole document (a required KIND is absent from the packet). The
fourth keeps every document but the offer letter names no annualized salary, so the
required *field* (`annual_wage_usd`) can't be read — a present-but-incomplete document.

Each case folder holds the client-facing artifacts that ARE present (`passport.png` +
the remaining `offer/lca/i94/degree/support-letter.pdf`) plus a `ground-truth.json` that
adds:
- `documents_present` — the required-document kinds in the packet,
- `documents_missing` — the omitted document (empty for the missing-field case),
- `facts` — the flat fact set the present documents yield (the completeness check's input),
- `expected_gates` — the completeness gate that MUST fire, naming the `missing_kind` /
  `missing_field`.

The editable HTML render-sources live under `_src/` (see the happy-path README).

## Status

The completeness gates are **implemented + tested** against this corpus by
the completeness check (reference: `validator/validate.py`):

```sh
python validator/validate.py incomplete   # every fixture fires its gate
```

Required documents the check enforces (with the key field each must yield): passport
(`passport_number`), offer letter (`annual_wage_usd`), certified LCA (`prevailing_wage`),
I-94 (`current_nonimmigrant_status`), degree / credential evaluation (`beneficiary_degree`).

**Live-wiring note.** Completeness is *absence-based*, so — unlike the cross-document
contradiction gates (which need both sides present and are safe after every upload) — it
is **not** wired into the per-upload `validate_matter`: running it mid-upload would flag a
half-loaded matter. It is meant to fire at an explicit "intake complete?" checkpoint
(end-of-batch upload, or a reviewer action). That trigger is the deliberate follow-on; the
logic + corpus are ready for it.

## Regenerate

```sh
python3 generator/generate_cases.py --incomplete-only
```

`--incomplete-only` rebuilds just this tier; it does **not** touch the committed
happy-path or adversarial fixtures. The blessed real passport image is reused from the
base case (a person has one passport); the missing document is simply not rendered.
