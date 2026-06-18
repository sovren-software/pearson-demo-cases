# Contributing to Pearson

Thanks for helping grow the corpus. There are **two ways to contribute**:

- **⚖️ Legal review (no code).** You're an immigration attorney or paralegal and you can tell us whether a contradiction, a verdict, a severity, or a deadline is *legally correct* — or whether a synthetic document looks realistic. **This is the contribution we most need.** Start with **[REVIEW-GUIDE.md](REVIEW-GUIDE.md)** and open a "Legal review" issue. You do not need any of the engineering steps below.
- **🛠️ Corpus / code.** You're adding or editing cases, the generator, or the validator. Follow the rest of this file.

The one rule for the code track: **every case ships with a machine-checkable answer key, and `validator/validate.py all` must stay green.**

## Ground rules

- **Synthetic only.** No real PII — ever. Names, employers, addresses, passport numbers, and EINs are fictional. Passport images stay watermarked SPECIMEN with stylized (non-official) emblems.
- **One defect per adversarial case.** An adversarial fixture injects exactly one contradiction and must trip exactly its named gate — no more, no less ("right-pass discipline").
- **The folder name is meaningful.** Persona folders are `given-family` slugs. Adversarial folders are named after the **gate** they prove. Incomplete folders are named after the **missing artifact**.
- **Keep the manifest in sync.** Add your case to [`CASES.yaml`](CASES.yaml), and put `base_persona` (scenario corpora) / `persona` (happy) in the case's `ground-truth.json`.

## Add a document case (happy / adversarial / incomplete)

1. Define the case in `generator/generate_cases.py` (the `PROFILES`, `ADVERSARIAL`, or `INCOMPLETE` lists). Adversarial/incomplete cases declare a `base` persona, the `defect`, and the `expected_gates`.
2. Regenerate:
   ```sh
   python3 generator/generate_cases.py   # needs imagemagick, libreoffice, Noto fonts
   ```
3. Add the case to `CASES.yaml`.
4. Validate:
   ```sh
   python3 validator/validate.py all
   ```

## Add a fixture case (materiality / status-clock)

These corpora are hand-authored `cases.json` (no document rendering). Add an entry with a complete `expect` block (the oracle) and an accurate `legal_basis`, then run the validator. For materiality, set `rule_ids`, `change`, `material`, and `primary_kind`; for status-clock, set `periods`, `travel`, and the expected clock values.

## Add a persona

Add the profile to `generator/generate_cases.py` (`given`, `surname`, `nationality`, `scenario`, the document fields), regenerate, and add it to the `personas:` block in `CASES.yaml`. Use a `given-family` kebab slug.

## The validator is the gate

`validator/validate.py` re-implements every detection gate in pure-stdlib Python and runs the full battery against each case. If you change a gate's semantics, update both the corpus and the validator — and prove it: a case must pass only on its *own* gate. CI (and reviewers) run `python3 validator/validate.py all`; keep it at `0 failed`.
