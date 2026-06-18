# Pearson — H-1B demo case files

Three complete, **synthetic** H-1B immigration case files that drive a conformant intake system
end-to-end. All data is fictional — no real PII. Passports are clearly watermarked
**SPECIMEN** and use stylized (not real) national emblems, with a real (synthetic)
face in the photo box so the headshot-extraction beat works.

## Profiles (the demo cast)

| Slug | Beneficiary | Nat | Scenario | Material-change email (Act 2) → impact |
|------|-------------|-----|----------|----------------------------------------|
| `arjun-kumar`        | Arjun Kumar       | IND | Cap-subject new hire; F-1 OPT → H-1B; US STEM master's | **compensation change** → wage / new LCA |
| `yangben-zhengjian`  | Yangben Zhengjian | CHN | H-1B transfer / portability (currently in H-1B) | **worksite relocation** → new LCA + amended petition (*Matter of Simeio Solutions*) |
| `abigail-medina`     | Abigail Medina Perez | MEX | Foreign degree + credential eval; TN → H-1B | **promotion / role change** → specialty-occupation re-test |

Each case folder holds the documents a client would actually hand over. The **six
required** ones drive the I-129 — `passport.png` (valid ICAO 9303 TD3 MRZ + a face in
the photo box), `offer.pdf`, `lca.pdf`, `i94.pdf`, `degree.pdf`, `support-letter.pdf` —
plus `ground-truth.json` (every expected fact + the pre-authored material-change email
body under `material_change_email.body`). The editable HTML render-*sources* live under
**`_src/`** (a client never sends HTML; it's the generator's input the PDFs are
rendered from, kept versioned + diffable so the corpus regenerates without LibreOffice).

### Too-much intake — over-shared documents

A real client dumps everything they have, not a tidy six-doc packet. Each case therefore
also carries **extra documents the I-129 does not need** — the résumé is 2 pages, so the
corpus exercises multi-page intake too:

| Case | Over-shared extras |
|------|--------------------|
| `arjun-kumar`       | `resume.pdf` (2pp), `i20.pdf` (F-1/OPT record), `paystub.pdf` |
| `yangben-zhengjian` | `resume.pdf` (2pp), `i797-prior.pdf` (prior H-1B approval), `paystub.pdf` |
| `abigail-medina`    | `resume.pdf` (2pp), `transcript.pdf`, `tn-approval.pdf` |

These are listed under `ground-truth.json → extra_documents` with `required: false` — they
**never count against the accuracy check** (they corroborate at most). The demo beat is that
the system ingests the noisy pile gracefully: it extracts what's relevant and ignores the
rest. Regenerate just these with `python3 generator/generate_cases.py --extras-only`
(leaves the required PDFs + sourced passports untouched).

> The three Act-2 scenarios are exactly the change-fields an H-1B amendment analysis
> reasons about — **wage**, **worksite** (cites Simeio), **title** — so the cast
> demonstrates a change → impact → approve loop end-to-end.

## Regenerate

```sh
python3 generator/generate_cases.py   # needs: magick, soffice, python3, Noto fonts
```

The generator computes valid MRZ check digits (ICAO 9303), renders country-styled
passports (national colors, bilingual headers, stylized emblems, SPECIMEN
watermark, synthetic face), produces the PDFs (HTML → soffice), and writes
ground-truth.

## Validate

```sh
python validator/validate.py integrity   # MRZ check digits, ground-truth, PDF text layers
python validator/validate.py all    # the whole corpus
```

## Material-change fixtures (the "Act 2" data)

Each `ground-truth.json` carries a pre-authored material-change email under
`material_change_email.body` and the field it changes — the data for exercising a
change → impact analysis end to end. The three scenarios map to the fields an H-1B
amendment analysis reasons about:

| Case | Change | Petition impact |
|------|--------|-----------------|
| `arjun-kumar`       | compensation | wage / new LCA |
| `yangben-zhengjian` | worksite     | new LCA + amended petition (*Matter of Simeio Solutions*) |
| `abigail-medina`    | title / role | specialty-occupation re-test |
