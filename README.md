# Pearson — synthetic H-1B case files

[![validate](https://github.com/sovren-software/pearson-demo-cases/actions/workflows/validate.yml/badge.svg)](https://github.com/sovren-software/pearson-demo-cases/actions/workflows/validate.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**A high-quality, fully synthetic corpus of U.S. H-1B immigration cases — for building, testing, and benchmarking document-intake and case-integrity systems.**

Most legal-AI demos run on one tidy happy-path packet. Real intake is messy: clients over-share, contradict their own documents, forget the LCA, and send a passport that expires mid-petition. **Pearson** is the corpus that exercises all of it — clean cases, adversarial contradiction traps, incomplete packets, materiality/change-impact fixtures, and status-clock deadline math — each with a machine-checkable answer key and a runnable reference validator.

Inspired by the open-source legal-AI work at [mikeoss.com](https://mikeoss.com). Everything here is fictional; passports are watermarked **SPECIMEN**.

---

## What's in the box

**37 cases across 5 corpora**, plus a generator and a stdlib-only reference validator.

| Corpus | Cases | What it proves | Form |
|--------|:-----:|----------------|------|
| [`cases/h1b`](cases/h1b) | 3 | **Happy path** — clean documents extract into facts that fill the I-129 | full document packets |
| [`cases/h1b-adversarial`](cases/h1b-adversarial) | 8 | **Contradiction gates** — one injected defect per case (wage below prevailing, name/SOC/employer/EIN mismatch, worksite outside LCA, expired passport, corrupt MRZ) — the folder *is* the gate it must trip | full packets + `expected_gates` |
| [`cases/h1b-incomplete`](cases/h1b-incomplete) | 4 | **Completeness gates** — one required document or field is missing | partial packets |
| [`cases/h1b-materiality`](cases/h1b-materiality) | 17 | **Change → impact** — a petition field changes mid-case; what's the correct verdict (amendment / notice / stale / constraint-violated)? | `cases.json` fixtures |
| [`cases/h1b-statusclock`](cases/h1b-statusclock) | 5 | **Deadline math** — H/L-1 six-year max-out, day recapture, and clock reset | `cases.json` fixtures |

Three recurring personas anchor the document corpora — **Arjun Kumar** (IND), **Yangben Zhengjian** (CHN), and **Abigail Medina Pérez** (MEX) — each a distinct H-1B story (cap-subject new hire, transfer/portability, foreign-degree/TN conversion). See [`CASES.yaml`](CASES.yaml) for the full manifest: every case → its persona → the gate it proves.

---

## Quick start

```sh
# Validate the whole corpus (Python 3 stdlib only — no dependencies)
python3 validator/validate.py all
```

```
integrity:   17 passed, 0 failed, 0 skipped
adversarial:  8 passed, 0 failed, 0 skipped
incomplete:   4 passed, 0 failed, 0 skipped
statusclock:  5 passed, 0 failed, 0 skipped
materiality: 17 passed, 0 failed, 0 skipped
TOTAL: 51 passed, 0 failed, 0 skipped
```

```sh
python3 validator/validate.py adversarial    # just one corpus
```

The validator is a **clean-room reference implementation** of every detection gate — it reads each case's `ground-truth.json` (the facts a perfect extractor would read) and checks the documented gate fires, **and only it** (a case that trips for the wrong reason is a failure). It's the spec made executable.

---

## Each case, on disk

A document case (happy / adversarial / incomplete) is what a client would actually hand over:

```
cases/h1b-adversarial/wage-below-prevailing/
├── passport.png          # country-styled, valid ICAO 9303 TD3 MRZ + a face, watermarked SPECIMEN
├── offer.pdf             # employment offer letter
├── lca.pdf               # certified ETA-9035 Labor Condition Application
├── i94.pdf               # CBP I-94 arrival/departure record
├── degree.pdf            # degree / credential evaluation
├── support-letter.pdf    # employer support letter
├── _src/*.html           # the diffable HTML the PDFs render from (regen without a reader)
└── ground-truth.json     # the answer key (facts + defect + expected_gates)
```

`ground-truth.json` records the expected facts; adversarial cases add `defect` + `expected_gates` (the gate that must fire, with the contradicting `evidence`), and carry `base_persona` so the case links back to its persona. The materiality and status-clock corpora are single `cases.json` files keyed by scenario, with an `expect` block as the oracle.

---

## Regenerate

The document corpora are reproducible from source:

```sh
python3 generator/generate_cases.py    # needs: imagemagick, libreoffice, python3, Noto fonts
```

The generator computes valid ICAO-9303 MRZ check digits, renders country-styled SPECIMEN passports with a synthetic face, produces the PDFs (HTML → LibreOffice), and writes the ground truth. See [`generator/PASSPORT-SOURCING.md`](generator/PASSPORT-SOURCING.md) for how the passport images are sourced.

---

## Repository layout

```
pearson-demo-cases/
├── cases/            # the 5 case corpora (the data)
├── generator/        # reproducible synthetic-case generator
├── validator/        # validate.py — the stdlib reference validator
├── CASES.yaml        # manifest: personas, cases, gates, naming conventions
└── cases/h1b-adversarial/VALIDATION-SPEC.md   # the gate catalog (the spec)
```

---

## A note on the data

Every name, employer, address, passport, and case in this repository is **fictional and synthetic**. Passport images are watermarked **SPECIMEN** and use stylized, non-official national emblems. Any resemblance to a real person, employer, or case is coincidental. Nothing here is legal advice; the gate definitions encode common H-1B failure modes for testing software, not legal guidance.

---

## Contributing & license

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a case or persona and keep the validator green.

Licensed under the **[Apache License 2.0](LICENSE)**. © 2026 Sovren Software.
