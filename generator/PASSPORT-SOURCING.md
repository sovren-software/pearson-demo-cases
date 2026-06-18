# Passport images for the H-1B demo corpus — sourcing & adaptation

Accurate, high-quality passport images are critical for the Pearson corpus (the passport
read is the strongest cold-demo beat). This is the playbook for getting them.

## Principle: a person has ONE passport

The demo corpus reuses three identities (`arjun-kumar` IND, `yangben-zhengjian` CHN,
`abigail-medina` MEX). The 6 adversarial cases derive from those same three people —
so they **reuse the base person's blessed passport image**, they do not get a new
one. The generator enforces this:

- Happy-path profiles carry `"real_passport": True`. `render_passport()` **never
  overwrites a sourced image** for them (the curated scans the demo depends on).
- `build_adversarial()` **copies the base person's real passport** for any case that
  doesn't alter the passport itself. Only `passport-expired-before-period` and
  `mrz-checkdigit-corrupt` (which change the passport) render a synthetic SPECIMEN.

Source a *new* passport image only for a genuinely **new, distinct** beneficiary.

## Where to source a specimen (new beneficiary)

In priority order (full data page **with the MRZ**, ≥1000px short edge, even
lighting, low skew, a CC0/CC-BY/CC-BY-SA license — record the attribution):

1. **Wikimedia Commons** — `Category:Passport data pages`, then
   `Category:Passports of <Country>`, then the country's "X passport" Wikipedia
   article. Best practical source; per-file licenses vary — check each.
   - **India** — `File:Indian_Passport_Bio_Page_2021.jpg` (2706×3841, CC BY-SA)
   - **China** — `File:Data_Page_of_PRC_Ordinary_Passport...2014.png` (1561×2136, CC BY-SA; anonymized real → overwrite identity)
   - **Mexico** — `File:Hoja_de_datos_del_pasaporte_biométrico_mexicano.jpg` (2152×1154, **CC0**)
2. **ICAO Doc 9303 Part 3** — the fully-synthetic "Utopia / ANNA MARIA ERIKSSON"
   specimen; use it as the MRZ check-digit golden fixture + a generic layout.
3. **PRADO** (EU Council) — security-feature *reference* only; its public images are
   cropped close-ups, not full-page MRZ scans, and reuse terms are restrictive.
4. **IDV/OCR vendor galleries** (Regula, Mindee, ID Analyzer, …) — last resort;
   assume proprietary unless a license says otherwise.

## Adapting a specimen to a synthetic identity

The established IDV/document-AI method (MIDV-2020 / SIDTD / Dynamsoft **SynthMRZ**):

1. **Inpaint** the old name/DOB/number/MRZ regions (LaMa / `simple-lama-inpainting`
   or `lama-cleaner`) — do **not** paint a white box (the #1 obvious-paste tell).
2. **Overlay** the new visible fields in a matched typeface, near-black `#1a1a1a`,
   sized to the surrounding text; add a subtle blur/noise pass to share the grain.
3. **Render the MRZ in OCR-B** (OFL-licensed `OCRB-Regular.ttf`) at the bottom band,
   from a valid ICAO-9303 TD3 string. Our generator already computes valid TD3 check
   digits (7-3-1 + composite over positions 1–10,14–20,22–43); cross-check against
   the `mrz` PyPI lib (`mrz.generator.td3.TD3CodeGenerator`) as an oracle.
4. **Burn a diagonal `SPECIMEN — TEST DATA, NOT A VALID DOCUMENT` overprint** (~40%
   opacity, 30–45°) as the final layer.
5. **Record provenance** — source URL + license + "synthetic / SPECIMEN / fictional
   identity, for reader testing" in this file or a sibling manifest.

## Appropriateness boundary

Use only government / ICAO / EU-published **specimens** or clearly-anonymized
**template** images, adapted to **fictional** case identities, always marked
SPECIMEN. Never use a real individual's passport image as-is. The use is
*reading/testing our own extractor* — never producing usable travel documents.

## Open follow-on

`passport-expired-before-period` and `mrz-checkdigit-corrupt` currently use the synthetic SPECIMEN
(it correctly shows the defect). The higher-fidelity version is an **edited variant
of the base real image** — abigail's image with the expiry field + MRZ changed;
arjun's image with one MRZ check digit flipped — built with the inpaint+OCR-B
pipeline above. Tooling needed: `simple-lama-inpainting`, an OFL OCR-B font, and the
`mrz` lib. Tracked as the next step.

## Sources

Wikimedia Commons `Category:Passport_data_pages` · ICAO Doc 9303 Part 3 ·
MIDV-2020 (arxiv 2107.00396) · SIDTD (Nature s41597-024-04160-9) · SynthMRZ
(github.com/tony-xlh/SynthMRZ, dynamsoft.com SynthMRZ) · `mrz` PyPI · ICAO-9303
check digits (idcheck.dev/icao-9303-check-digits).
