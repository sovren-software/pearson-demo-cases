# Passport reference-image sourcing catalog

License-verified base images for the **adapt-real-specimen** path (source a published
specimen / anonymized / CC-or-PD image → adapt to a **fictional** identity → render a
valid ICAO-9303 MRZ → mark SPECIMEN). Every license below was read from the actual
Wikimedia Commons file page. **Boundary:** only government/ICAO specimens, anonymized
templates, or CC0/CC-BY/CC-BY-SA/PD images — never a real, identifiable live passport.

> License tiers: **CC0 / PD** = no obligation. **CC BY-SA** = share-alike — any derived
> SPECIMEN image must itself be published CC BY-SA with attribution + "changes made".
> (The repo already ships CC BY-SA-derived persona passports, so this is established
> practice; it just needs a per-image NOTICE.)

## Per-country bases

| Country | Best base | License | Resolution | Identity | Gen(s) | Notes |
|---|---|---|---|---|---|---|
| **India** | Indian_Passport_Bio_Page_2021.jpg | CC BY-SA 4.0 | 2706×3841 | anonymized (black-box redacted) | 2021 | needs inpaint of redaction boxes; + CC0 2025 ePassport (473×657, blank) for newest gen |
| **China** | Interior_of_PRC_Biometric_passport.jpeg | **PD (PRC-exempt)** | 3070×4296 | anonymized (blurred) + real face | post-2018 | upgrade over repo's CC BY-SA 2014; replace face + inpaint fields |
| **Mexico** | Hoja_de_datos_..._biométrico.jpg | **CC0** | 2152×1154 | **blank specimen** (no name, no face) | 2021 | cleanest — no inpaint; no MRZ in source (we render it). + 2016 (CC BY-SA, 5864×3880, real face) |
| **Canada** | — NONE — | Crown © (to 2074) | — | — | — | **no permissive data page exists → build fully-synthetic (ICAO generic)** |
| **South Korea** | Identity_Page_South_Korea_New_Passport.jpg | **PD (ROK gov)** | 593×843 | specimen, MRZ | pre-2021 green | low-res; + older 2003 specimen (PD); CC BY-SA 3006×3353 option encumbered |
| **Taiwan** | Republic_of_China_Passport_Data_Page.jpg | **PD (ROC-exempt)** | 669×466 | specimen | 2nd-gen chip | both Taiwan bases <700px → upscale or ICAO-composite |
| **Philippines** | Philippine_passport_(2016_edition)_data_page.jpg | **PD (PH gov)** | 1002×1401 | specimen, MRZ | 2016 | + 2009 maroon (PD, 1026×1430); P1 has fair-use→PD provenance history to flag |
| **Brazil** | Brazil_passport_data_page.jpg | **PD (BR gov)** | 1040×724 | specimen (sample serial AA000261), full MRZ | 2015 | only reusable BR MRZ page; 2019/2023 gens → synthetic |
| **United Kingdom** | Former_British_passport_biodata.jpg | CC BY-SA 4.0 | 600×423 | **specimen** ("UK SPECIMEN / ANGELA ZOE"), full MRZ | pre-2020 burgundy | low-res; **current blue (2020+) = Crown © + OGL-excluded → must be synthetic** |
| **Pakistan** | Data_Page_-_Polycarbonate_..._Pakistani_Passport.png | CC BY-SA 4.0 | **5901×3989** | **blank template** (empty fields, empty photo oval) | 2023+ e-passport | best base in set — blank + huge res; + MRP gen (CC BY-SA 3.0, 883×1249, redacted) |

## Hard constraints discovered

1. **Canada** — no permissively-licensed passport data page exists (Crown copyright to 2074). Canada must be **fully synthetic** (generic ICAO layout).
2. **UK current generation (post-2020 blue)** — Crown copyright; the Open Government Licence v3.0 *explicitly excludes* "identity documents such as the British Passport". Only the **pre-2020 burgundy specimen** is reusable; current-gen must be synthetic.
3. **License mix** — clean PD/CC0 bases: China, Mexico-CC0, Korea, Taiwan, Philippines, Brazil. Share-alike (CC BY-SA): India-2021, Mexico-2016, UK, Pakistan. Each derived image needs a per-image attribution + "changes made" notice in a NOTICE/this file.

## Fidelity tiers for adaptation effort

- **Blank templates — no inpainting (slam dunks):** Pakistan polycarbonate (5901×3989), Mexico CC0, India 2025. Overlay fictional fields + render MRZ directly.
- **Specimen with fields, no real face — light overlay:** Brazil, UK pre-2020, Philippines, Korea, Taiwan. Cover/overlay the sample fields (matched-color boxes) + fresh MRZ.
- **Real face / blurred fields — needs real inpainting (LaMa):** China interior, Mexico 2016, India 2021 (black boxes). Heaviest; only if we want those specific bases.

## ICAO generic fallback (for Canada, UK-current, and any low-res gap)

ICAO Doc 9303 Part 3 "Utopia" specimen — country code `UTO` (deliberately invalid):
```
P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<<
L898902C<3UTO6908061F9406236ZE184226B<<<<<14
```
Use as the layout + MRZ-format reference for fully-synthetic countries.
