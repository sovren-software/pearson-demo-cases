# Pearson — H-1B materiality test corpus (the "legal brain" test)

The deterministic, legally-grounded test of Pearson's **impact engine** — the part that,
when an inbound email moves a petition field, computes *what it means*: an amended I-129,
a notice obligation, simple staleness, or a cross-document constraint violation.

Where the other tiers test **documents** (`../h1b-adversarial/` = contradictions,
`../h1b-incomplete/` = missing pieces), this tier tests **changes**. So it isn't
document folders — it's a single fixture file, `cases.json`, each case = a *change* + the
verdict the engine must return. Proven with no models, no network:

```sh
python validator/validate.py materiality
```

It drives the impact engine directly and asserts the right rule fires (and only it,
plus any named counterfactual constraint), the right `kind` / `affected_form` / `deadline`,
and the set-level `material` flag.

## What it covers

The 14 materiality rules in the materiality rule set (9 reviewed + 5 AI-drafted)
+ the counterfactual cross-document pass + two engine-safety boundaries:

| Fixture | Rule | Change → verdict |
|---------|:----:|------------------|
| `wage-decrease-amendment` | 1 | wage ↓ (still ≥ prevailing) → **amendment** |
| `wage-increase-stale` | 2 | wage ↑ → **stale** |
| `title-change-post-filing-amendment` | 3 | title changed, filed → **amendment** |
| `title-change-pre-filing-stale` | 4 | title changed, pre-filing → **stale** (same change, earlier stage) |
| `worksite-outside-lca-amendment` | 5 | worksite outside LCA area → **amendment** (Simeio) |
| `worksite-within-area-stale` | 6 | worksite within LCA area → **stale** |
| `home-address-ar11-notice` | 7 | home address → **notice** (AR-11, 10 days) — *not* an amendment |
| `name-correction-amendment` | 8 | beneficiary name corrected → **amendment** |
| `soc-code-change-amendment` | 9 | SOC code changed → **amendment** |
| `wage-cut-below-prevailing-counterfactual` | 1 | wage cut below prevailing → **amendment + constraint_violated** |
| `end-date-extension-amendment` | 10\* | end date extended → **amendment** (extension petition) |
| `fte-to-parttime-amendment` | 11\* | full-time → part-time → **amendment** |
| `hours-per-week-change-amendment` | 12\* | weekly hours changed → **amendment** |
| `employer-legal-name-change-amendment` | 13\* | petitioner legal name changed → **amendment** (successor-in-interest) |
| `employer-ein-change-amendment` | 14\* | petitioner FEIN changed → **amendment** (successor-in-interest) |
| `lca-number-correction-stale-fallback` | — | bound field with no rule → reverse-index **stale** (no silent drop) |
| `unbound-field-noop` | — | unbound field → **no impact** (no false positive) |

\* Rules **10–14 are AI-drafted (2026-06-11), attorney-review pending** — conservative
"surface-as-material" drafts of the triggers the packet flagged as missing. Each has a
nuance to resolve (see its fixture's `legal_basis`); the attorney may soften any to a notice
or staleness. They are the coverage expansion, not yet confirmed law.

Rules 3↔4 and 5↔6 are deliberate **boundary pairs**: the *same* change yields a different
verdict depending on stage (filed vs pre-filing) or geography (outside vs within the LCA
area). Those are the cases most likely to be legally wrong, so they each get an explicit
fixture.

## Scope

This corpus is the executable spec for an H-1B **materiality / change-impact** engine:
*given a detected change to a petition field, what is the correct verdict* — amendment
required, notice obligation, stale, or constraint violated. Each fixture's `expect`
block IS the contract. The reference validator (`python validator/validate.py
materiality`) checks the corpus is well-formed and internally consistent; implementing
the full verdict engine is left to the consumer — the `expect` values are the oracle.

Rules **10–14 are AI-drafted, attorney-review pending** — conservative
"surface-as-material" drafts; each carries a `legal_basis` and an `attorney` redline
field (empty = pending). Rules 3↔4 and 5↔6 are deliberate **boundary pairs** — the same
change yields a different verdict by filing stage or geography — the cases most likely to
be legally contentious.

## Regenerate

The materiality and status-clock corpora are hand-authored `cases.json` fixtures (no
document rendering). Edit `cases.json` directly to add a case; keep the `expect` block
and `legal_basis` accurate.
