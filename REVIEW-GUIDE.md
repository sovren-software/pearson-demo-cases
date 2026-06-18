# Legal review guide

**For immigration attorneys and paralegals.** This repository is a library of fictional H‑1B cases used to test immigration software. The software's job is to read case documents and catch problems — a wage below the prevailing wage, a name that doesn't match the passport, a worksite outside the certified LCA area, a passport that expires before the job starts, and so on.

Here's the catch: **the software is only as good as the legal judgment baked into it.** Every "this is an error," every "this change requires an amendment," and every deadline calculation in this repo is a claim about immigration law that an engineer or an AI wrote down. We need practicing attorneys to check those claims.

**You don't need to write code, run anything, or use the command line.** If you can read a case and tell us what a competent immigration attorney would actually do, you can make this better.

> You can also point an AI assistant (ChatGPT, Claude, Codex, etc.) at this repository and ask it to walk you through a case or to turn your notes into a properly formatted issue. The repo is organized so an assistant can explain any case to you in plain English.

---

## How a case is laid out (60-second orientation)

Open any folder under [`cases/`](cases). A single case looks like a real client's document packet:

```
cases/h1b-adversarial/wage-below-prevailing/
├── passport.png          a passport data page (watermarked SPECIMEN)
├── offer.pdf             the employer's offer letter
├── lca.pdf              the certified Labor Condition Application (ETA-9035)
├── i94.pdf              the I-94 arrival/departure record
├── degree.pdf           the degree / credential evaluation
├── support-letter.pdf   the employer support letter
└── ground-truth.json    ← the ANSWER KEY: what we say is true about this case
```

The PDFs are exactly what you'd review in practice — open them. **`ground-truth.json`** is the part we need you to scrutinize: it's our written assertion of what the documents say, what (if anything) is *wrong* with the case, and *what a system should flag*. It's plain text; an AI assistant can read it aloud to you in normal English.

The five corpora are summarized in the [README](README.md#whats-in-the-box) and indexed in [`CASES.yaml`](CASES.yaml).

---

## What to review (pick any one — all are useful)

### 1. The contradiction cases — *are these real errors, characterized correctly?*
📁 [`cases/h1b-adversarial/`](cases/h1b-adversarial) · spec: [`VALIDATION-SPEC.md`](cases/h1b-adversarial/VALIDATION-SPEC.md)

Each of these 8 cases has **exactly one injected problem**, and we claim a competent system should catch it — with a **severity** (does it draw a *denial*, an *RFE*, or fully *block* filing?). For each, please tell us:

- **Is it really a problem?** (e.g., we treat an offered wage below the LCA prevailing wage as a *denial* ground — agree?)
- **Is the severity right?** Denial vs RFE vs blocker matters a lot to a firm.
- **Is our explanation (the `why` field) legally sound,** and the regulatory basis correct?

### 2. The change-impact cases — *when something changes mid-case, what's required?*
📁 [`cases/h1b-materiality/`](cases/h1b-materiality) · [`cases.json`](cases/h1b-materiality/cases.json)

A petition field changes after filing (a raise, a promotion, a worksite move, a name correction). For each change we assert a verdict — **amendment required**, **notice obligation**, **no action (stale)**, or **constraint violated**. This is the most law-heavy corpus, and **it has a field with your name on it**: every case carries an `attorney` entry that is currently *empty (pending review)* — that is literally where your redline goes.

- Is each verdict correct? Watch the **boundary pairs** especially: the *same* change (e.g., a title change) can require an amendment **after** filing but nothing **before** filing — we test both; tell us if we drew the line in the wrong place.
- **Rules 10–14 are explicitly AI-drafted and unconfirmed** — they most need a real attorney's sign-off (soften to a notice? a non-issue? keep as amendment?).

### 3. The deadline-math cases — *is the six-year clock right?*
📁 [`cases/h1b-statusclock/`](cases/h1b-statusclock) · [`cases.json`](cases/h1b-statusclock/cases.json)

H/L‑1 maximum-stay, day **recapture** for time spent abroad, and the one-year-absence **reset**. **These answers were computed by hand and are explicitly *pending attorney validation*.** Each case lists the periods, the travel, and our computed max-out date — please check the arithmetic and the rules behind it.

### 4. Document realism — *do these look like the real thing?*
📁 the happy cases in [`cases/h1b/`](cases/h1b)

Open the offer letters, LCAs, I‑797s, I‑94s. Would a real one read like this? **This is high-value and easy** — an attorney already caught that our offer letters printed the SOC/O\*NET code (rare in practice), and we removed it. What else looks off — phrasing, fields, formatting, what's present or missing?

### 5. Coverage gaps — *what failure modes are we missing entirely?*
What common, RFE‑drawing problems does this corpus **not** yet contain (maintenance-of-status gaps, specialty-occupation sufficiency, beneficiary-qualification mismatches, employer ability-to-pay, etc.)? A list of "you should add a case for X" is extremely useful.

---

## How to send feedback (easiest first)

You do **not** need a technical background for any of these.

1. **Open a GitHub issue (recommended).** Go to the **Issues** tab → **New issue** → **"⚖️ Legal review / case correction"** and fill in the short form. That's it. (Tip: have ChatGPT/Codex draft the issue from your notes — paste the case folder name and your comments.)
2. **Comment on a specific case** by opening an issue that names the case folder and quotes the line you disagree with.
3. **Suggest the exact fix** if you're comfortable: in `ground-truth.json` / `cases.json`, the values to change are the verdict, the severity, the `why`/`legal_basis`, and — for materiality — the `attorney` field.

We'll encode your correction, flip the relevant `attorney` field from *pending* to *confirmed*, and credit you (or keep you anonymous — your call).

---

## A good piece of feedback looks like

> **Case:** `cases/h1b-adversarial/soc-code-mismatch`
> **Your read:** The mismatch between the LCA SOC and the petition occupation is correctly an RFE, not a denial — agreed. But the `why` should note that the controlling question is whether the LCA *corresponds* to the position (8 CFR 214.2(h)(4)(iii)), and that a clearly clerical SOC transposition is often curable by RFE response rather than fatal. Severity "rfe" is right.

Short, specific, points at the file. Citations welcome but optional — your practical judgment is the thing we can't get anywhere else.

---

## Important

All cases here are **fictional and synthetic** — no real people, employers, or filings. Nothing in this repository is legal advice, and reviewing it does **not** create an attorney–client relationship. You're helping us make a *testing tool* legally accurate, not advising on a real matter. Thank you — this is the contribution that makes the project trustworthy.
