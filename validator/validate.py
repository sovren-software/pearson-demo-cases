#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate.py — reference validator for the pearson-demo-cases H-1B corpus.

This is the runnable, open-source contract for a cross-document
intake-validation layer. It is the *spec made executable*: a clean-room
re-implementation of every detection gate, run against the committed
synthetic corpus, with zero third-party dependencies (Python 3 stdlib only).

------------------------------------------------------------------------------
Where the facts come from
------------------------------------------------------------------------------
Each case ships a ``ground-truth.json`` that records the values a perfect
document-extraction pipeline *would* read out of that case's PDFs/PNG. In a
real system those facts come from OCR + LLM extraction over the documents; here
they are the oracle, so the validator can test the *detection logic* in
isolation from the (separately-tested) extraction layer.

For adversarial cases the injected defect's "before/after" values live in the
``expected_gates[0].evidence`` block — that block is the authoritative oracle
for what the gate must compare. We read the document fact blocks as the primary
source and treat ``evidence`` as the oracle when a value (e.g. the LCA-side
prevailing wage, or a mismatched surname) is recorded only there.

------------------------------------------------------------------------------
Right-pass discipline (the right gate must fire, and only it)
------------------------------------------------------------------------------
An adversarial case PASSES only when its OWN named gate fires *and no sibling
gate fires*. A case that trips for the wrong reason — or trips two gates — is a
FAIL, not a pass. This is the whole point of the corpus: a detector that
"fails" a packet for any reason is not the same as a detector that identifies
the *correct* defect. Every gate is therefore implemented as a pure predicate,
and for each case we run the full gate battery and assert exactly the expected
gate matched.

------------------------------------------------------------------------------
Usage
------------------------------------------------------------------------------
    python3 validator/validate.py [all|integrity|adversarial|incomplete|
                                   materiality|statusclock]

Default is ``all``. Exits 0 only if every case PASSED (SKIPs are tolerated and
reported but never assert a falsehood); exits 1 if anything FAILED.

The corpus dirs are globbed, never hardcoded — drop a new case folder in and it
is auto-discovered.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Paths — resolved relative to this file so the validator runs from anywhere.
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CASES = os.path.join(REPO, "cases")

# Per-corpus required document files (basenames). Extra `required:false`
# documents (resume/paystub/i20/etc.) are over-shared and intentionally ignored.
HAPPY_REQUIRED = ["passport.png", "offer.pdf", "lca.pdf", "i94.pdf", "degree.pdf",
                  "support-letter.pdf", "ground-truth.json"]
ADVERSARIAL_REQUIRED = ["passport.png", "offer.pdf", "lca.pdf", "ground-truth.json"]
INTAKE_REQUIRED = ["README.md", "case.json", "ground-truth.json",
                   "packet-for-lei-upload/LEI_CASE_001_JOHN_DOE_PACKET_COMBINED.pdf",
                   "packet-for-lei-upload/README_FOR_LEI_UPLOAD.pdf",
                   "attorney-only/ATTORNEY_ONLY_ANSWER_KEY.pdf"]
INTAKE_FORBIDDEN_UPLOAD_NAMES = ("lca", "support-letter", "support_letter",
                                 "i-129", "i129", "g-28", "g28")

# Map a logical document "kind" to the file that would carry it. Used by the
# incomplete tier to confirm a `documents_missing` entry is genuinely absent.
KIND_TO_FILE = {
    "passport": "passport.png",
    "offer": "offer.pdf",
    "lca": "lca.pdf",
    "i94": "i94.pdf",
    "degree": "degree.pdf",
    "support": "support-letter.pdf",
}


# ===========================================================================
# Result accounting
# ===========================================================================
class Results:
    """Collects per-case verdicts and renders the per-corpus summary."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def record(self, status: str, label: str, reason: str = "") -> None:
        tag = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP"}[status]
        line = f"  [{tag}] {label}"
        if reason:
            line += f" — {reason}"
        print(line)
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        else:
            self.skipped += 1

    def summary(self, corpus: str) -> None:
        print(f"  {corpus}: {self.passed} passed, {self.failed} failed, "
              f"{self.skipped} skipped")


# ===========================================================================
# Small helpers
# ===========================================================================
def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def case_dirs(corpus: str) -> list[str]:
    """Glob a per-case corpus dir for folders that contain a ground-truth.json."""
    pattern = os.path.join(CASES, corpus, "*", "ground-truth.json")
    return sorted(os.path.dirname(p) for p in glob.glob(pattern))


def digits_only(s) -> str:
    """Normalize an identifier to its digits (so `47-3829150` == `473829150`)."""
    return re.sub(r"\D", "", str(s or ""))


def norm_company(name) -> str:
    """
    Normalize a company name by stripping punctuation and casing but KEEPING the
    words. So `Northwind Analytics, Inc.` -> `northwind analytics inc`, which is
    still distinct from `Northwind Analytics LLC` -> `northwind analytics llc`.
    This is the deliberate `employer_name_mismatch` signal: an entity-suffix
    divergence (Inc vs LLC) is a real petitioner-consistency question.
    """
    cleaned = re.sub(r"[^\w\s]", " ", str(name or "").lower())
    return " ".join(cleaned.split())


def metro_of(address) -> str:
    """
    Reduce a worksite address to a coarse 'metro' key: the trailing
    `City, ST ZIP` tuple normalized to `city|st`. Two addresses in the same
    certified area of intended employment reduce to the same metro even if the
    suite/building/formatting differs (Matter of Simeio only cares about the
    area, not the street). Returns "" when no `City, ST` tail is parseable.
    """
    s = str(address or "")
    # Match "<City>, <2-letter state> [ZIP]" anywhere (use the LAST occurrence).
    matches = re.findall(r"([A-Za-z .'-]+?),\s*([A-Z]{2})\b", s)
    if not matches:
        return ""
    city, st = matches[-1]
    return f"{city.strip().lower()}|{st.lower()}"


def surname_of(full_name) -> str:
    """First whitespace token of an uppercase 'SURNAME GIVEN ...' name string."""
    toks = str(full_name or "").strip().split()
    return toks[0].upper() if toks else ""


def parse_date(s) -> date | None:
    try:
        return date.fromisoformat(str(s))
    except (ValueError, TypeError):
        return None


# ===========================================================================
# ICAO 9303 TD3 machine-readable-zone check digits
# ===========================================================================
def mrz_char_value(c: str) -> int:
    """ICAO 9303 char weighting: '<'=0, digits=themselves, A=10..Z=35."""
    if c == "<":
        return 0
    if c.isdigit():
        return int(c)
    return ord(c.upper()) - 55  # 'A' (65) -> 10 ... 'Z' (90) -> 35


def mrz_check_digit(field: str) -> int:
    """Compute the 7-3-1 weighted modulo-10 check digit over a field."""
    weights = (7, 3, 1)
    total = sum(mrz_char_value(ch) * weights[i % 3] for i, ch in enumerate(field))
    return total % 10


def mrz_td3_valid(line1: str, line2: str) -> tuple[bool, dict]:
    """
    Validate the five TD3 line-2 check digits per ICAO Doc 9303. Returns
    (all_valid, {field: (computed, claimed)}). line1 is accepted for signature
    symmetry but TD3's numeric check digits all live on line 2.

    TD3 line-2 layout (0-indexed):
        [0:9]   passport number      [9]  check digit
        [10:13] nationality
        [13:19] date of birth        [19] check digit          [20] sex
        [21:27] expiration date      [27] check digit
        [28:42] personal number      [42] check digit
        [43]    composite check digit over passport#+cd, dob+cd, expiry+cd,
                personal#+cd
    """
    line2 = (line2 or "").ljust(44, "<")
    checks = {
        "passport_number": (mrz_check_digit(line2[0:9]),  line2[9]),
        "date_of_birth":   (mrz_check_digit(line2[13:19]), line2[19]),
        "expiration":      (mrz_check_digit(line2[21:27]), line2[27]),
        "personal_number": (mrz_check_digit(line2[28:42]), line2[42]),
        "composite":       (mrz_check_digit(line2[0:10] + line2[13:20]
                                            + line2[21:28] + line2[28:43]),
                            line2[43]),
    }
    all_valid = all(str(computed) == claimed for computed, claimed in checks.values())
    detail = {k: (str(computed), claimed) for k, (computed, claimed) in checks.items()}
    return all_valid, detail


# ===========================================================================
# Adversarial gates — clean-room from VALIDATION-SPEC.md
# ---------------------------------------------------------------------------
# Each gate is a pure predicate ``fire(gt) -> bool`` over a case's
# ground-truth dict. It reads the document fact blocks as the primary source
# and the ``expected_gates[0].evidence`` block as the oracle for values that
# only exist there (LCA-side facts, mismatched surnames, corrupted MRZ index).
# A gate returning True means "this packet trips this gate."
# ===========================================================================
def _evidence(gt: dict) -> dict:
    gates = gt.get("expected_gates") or []
    return (gates[0].get("evidence") if gates else {}) or {}


def gate_wage_below_prevailing(gt: dict) -> bool:
    offer = gt.get("employment_from_offer_letter", {})
    ev = _evidence(gt)
    offered = ev.get("annual_wage_usd", offer.get("annual_wage_usd"))
    prevailing = ev.get("prevailing_wage")  # LCA-side, only in evidence
    if offered is None or prevailing is None:
        return False
    return float(offered) < float(prevailing)


def gate_identity_name_mismatch(gt: dict) -> bool:
    ev = _evidence(gt)
    # Surnames are the oracle (the offer fact block shows the *clean* name).
    passport_surname = ev.get("passport_surname")
    offer_surname = ev.get("offer_surname")
    if passport_surname is None or offer_surname is None:
        # Fall back to comparing passport vs offer full-name surnames if present.
        p = surname_of(gt.get("beneficiary_from_passport", {}).get("beneficiary_full_name"))
        o = surname_of(gt.get("employment_from_offer_letter", {}).get("beneficiary_full_name"))
        if not p or not o:
            return False
        return p != o
    return surname_of(passport_surname) != surname_of(offer_surname)


def gate_soc_code_mismatch(gt: dict) -> bool:
    offer = gt.get("employment_from_offer_letter", {})
    ev = _evidence(gt)
    offer_soc = ev.get("offer_soc_code", offer.get("soc_code"))
    lca_soc = ev.get("lca_soc_code")  # LCA-side, only in evidence
    if offer_soc is None or lca_soc is None:
        return False
    return str(offer_soc).strip() != str(lca_soc).strip()


def gate_worksite_outside_lca_area(gt: dict) -> bool:
    offer = gt.get("employment_from_offer_letter", {})
    ev = _evidence(gt)
    offer_ws = ev.get("offer_worksite", offer.get("worksite_address"))
    lca_ws = ev.get("lca_worksite")  # LCA-side, only in evidence
    if offer_ws is None or lca_ws is None:
        return False
    om, lm = metro_of(offer_ws), metro_of(lca_ws)
    if not om or not lm:
        return False
    return om != lm


def gate_employer_name_mismatch(gt: dict) -> bool:
    offer = gt.get("employment_from_offer_letter", {})
    ev = _evidence(gt)
    offer_name = ev.get("offer_petitioner_legal_name", offer.get("petitioner_legal_name"))
    lca_name = ev.get("lca_petitioner_legal_name")  # LCA-side, only in evidence
    if offer_name is None or lca_name is None:
        return False
    return norm_company(offer_name) != norm_company(lca_name)


def gate_employer_ein_mismatch(gt: dict) -> bool:
    offer = gt.get("employment_from_offer_letter", {})
    ev = _evidence(gt)
    offer_ein = ev.get("offer_petitioner_ein", offer.get("petitioner_ein"))
    lca_ein = ev.get("lca_petitioner_ein")  # LCA-side, only in evidence
    if not offer_ein or not lca_ein:
        return False
    return digits_only(offer_ein) != digits_only(lca_ein)


def gate_passport_expired_before_period(gt: dict) -> bool:
    passport = gt.get("beneficiary_from_passport", {})
    offer = gt.get("employment_from_offer_letter", {})
    ev = _evidence(gt)
    exp = parse_date(ev.get("passport_expiration", passport.get("passport_expiration")))
    start = parse_date(ev.get("requested_start_date", offer.get("requested_start_date")))
    if exp is None or start is None:
        return False
    return exp < start


def gate_mrz_checkdigit_corrupt(gt: dict) -> bool:
    mrz = gt.get("mrz", {})
    line1, line2 = mrz.get("line1", ""), mrz.get("line2", "")
    if not line2:
        return False
    valid, _ = mrz_td3_valid(line1, line2)
    return not valid


# Gate registry. Order is irrelevant — the right-pass check requires EXACTLY
# the named gate to fire, so we always evaluate the whole battery.
GATES = {
    "wage_below_prevailing":          gate_wage_below_prevailing,
    "identity_name_mismatch":         gate_identity_name_mismatch,
    "soc_code_mismatch":              gate_soc_code_mismatch,
    "worksite_outside_lca_area":      gate_worksite_outside_lca_area,
    "employer_name_mismatch":         gate_employer_name_mismatch,
    "employer_ein_mismatch":          gate_employer_ein_mismatch,
    "passport_expired_before_period": gate_passport_expired_before_period,
    "mrz_checkdigit_corrupt":         gate_mrz_checkdigit_corrupt,
}


def fired_gates(gt: dict) -> set[str]:
    """Run the full battery; return the set of gate names that trip."""
    return {name for name, fn in GATES.items() if fn(gt)}


# ===========================================================================
# Status-clock (H/L-1 max-out + recapture) — deterministic re-implementation
# ===========================================================================
def add_years_clamped(d: date, n: int) -> date:
    """Add n years, clamping Feb-29 to Feb-28 in non-leap target years."""
    try:
        return d.replace(year=d.year + n)
    except ValueError:
        return d.replace(year=d.year + n, day=28)


def compute_status_clock(periods: list[dict], travel: list[dict]) -> dict:
    """
    The 6-year H/L-1 max-out clock.

      * The 6-year window runs from the earliest in-status period start
        (L-1 time counts toward the H/L cap, so all periods feed the window).
      * An absence abroad of >= 1 year RESETS the clock — the window then runs
        from the first period start AFTER that absence ends, and no days are
        recaptured (a reset and a recapture are mutually exclusive here).
      * Otherwise each foreign-travel segment recaptures (returned - departed)
        days, extending the max-out.

    Returns base_max_out / adjusted_max_out (ISO strings), recaptured_days,
    reset (bool). The caller asserts only the keys present in the fixture's
    ``expect`` block.
    """
    starts = sorted(parse_date(p["start"]) for p in periods if parse_date(p["start"]))
    if not starts:
        return {}

    # Detect a >= 1-year absence (the reset trigger).
    reset = False
    reset_after: date | None = None
    for t in travel:
        dep, ret = parse_date(t.get("departed")), parse_date(t.get("returned"))
        if dep and ret and (ret - dep).days >= 365:
            reset = True
            # The clock resumes at the earliest period start AFTER the return.
            later = [s for s in starts if s >= ret]
            if later:
                cand = min(later)
                reset_after = cand if reset_after is None else min(reset_after, cand)

    if reset and reset_after is not None:
        window_start = reset_after
        recaptured = 0  # reset and recapture are mutually exclusive
    else:
        window_start = starts[0]
        recaptured = sum(
            (parse_date(t["returned"]) - parse_date(t["departed"])).days
            for t in travel
            if parse_date(t.get("departed")) and parse_date(t.get("returned"))
        )

    base = add_years_clamped(window_start, 6)
    adjusted = base + timedelta(days=recaptured)
    return {
        "base_max_out": base.isoformat(),
        "adjusted_max_out": adjusted.isoformat(),
        "recaptured_days": recaptured,
        "reset": reset,
    }


# ===========================================================================
# TIER 1 — Integrity (structural validity of all corpora)
# ===========================================================================
def check_integrity(res: Results) -> None:
    print("== integrity ==")

    # --- Happy path: required files present, ground-truth parses, MRZ valid,
    #     persona self-resolves. ---
    for d in case_dirs("h1b"):
        name = f"h1b/{os.path.basename(d)}"
        try:
            gt = load_json(os.path.join(d, "ground-truth.json"))
        except (OSError, ValueError) as exc:
            res.record("FAIL", name, f"ground-truth.json unreadable: {exc}")
            continue
        missing = [f for f in HAPPY_REQUIRED if not os.path.exists(os.path.join(d, f))]
        if missing:
            res.record("FAIL", name, f"missing required files: {missing}")
            continue
        persona = gt.get("persona")
        if not persona or not os.path.isdir(os.path.join(CASES, "h1b", persona)):
            res.record("FAIL", name, f"persona '{persona}' does not resolve")
            continue
        ok, detail = mrz_td3_valid(gt.get("mrz", {}).get("line1", ""),
                                   gt.get("mrz", {}).get("line2", ""))
        if not ok:
            res.record("FAIL", name, f"happy-path MRZ check digits invalid: {detail}")
            continue
        res.record("PASS", name, "files+MRZ+persona OK")

    # --- Adversarial: required files, non-empty gate names, persona resolves,
    #     MRZ valid (except the mrz-checkdigit-corrupt case which must be
    #     correctly INVALID — that is its entire defect). ---
    for d in case_dirs("h1b-adversarial"):
        name = f"h1b-adversarial/{os.path.basename(d)}"
        try:
            gt = load_json(os.path.join(d, "ground-truth.json"))
        except (OSError, ValueError) as exc:
            res.record("FAIL", name, f"ground-truth.json unreadable: {exc}")
            continue
        missing = [f for f in ADVERSARIAL_REQUIRED if not os.path.exists(os.path.join(d, f))]
        if missing:
            res.record("FAIL", name, f"missing required files: {missing}")
            continue
        gates = gt.get("expected_gates") or []
        if not gates or not all(isinstance(g.get("gate"), str) and g["gate"]
                                for g in gates):
            res.record("FAIL", name, "expected_gates[].gate empty or non-string")
            continue
        persona = gt.get("base_persona")
        if not persona or not os.path.isdir(os.path.join(CASES, "h1b", persona)):
            res.record("FAIL", name, f"base_persona '{persona}' does not resolve")
            continue
        ok, detail = mrz_td3_valid(gt.get("mrz", {}).get("line1", ""),
                                   gt.get("mrz", {}).get("line2", ""))
        is_corrupt_case = gt.get("defect") == "mrz_checkdigit_corrupt"
        if is_corrupt_case and ok:
            res.record("FAIL", name, "corrupt-MRZ case unexpectedly has valid check digits")
            continue
        if not is_corrupt_case and not ok:
            res.record("FAIL", name, f"MRZ check digits invalid: {detail}")
            continue
        mrz_note = "MRZ correctly INVALID" if is_corrupt_case else "MRZ valid"
        res.record("PASS", name, f"files+gates+persona OK ({mrz_note})")

    # --- Incomplete: ground-truth parses, gate names non-empty, persona
    #     resolves. (Deep checks are the incomplete tier.) ---
    for d in case_dirs("h1b-incomplete"):
        name = f"h1b-incomplete/{os.path.basename(d)}"
        try:
            gt = load_json(os.path.join(d, "ground-truth.json"))
        except (OSError, ValueError) as exc:
            res.record("FAIL", name, f"ground-truth.json unreadable: {exc}")
            continue
        gates = gt.get("expected_gates") or []
        if not gates or not all(isinstance(g.get("gate"), str) and g["gate"]
                                for g in gates):
            res.record("FAIL", name, "expected_gates[].gate empty or non-string")
            continue
        persona = gt.get("base_persona")
        if not persona or not os.path.isdir(os.path.join(CASES, "h1b", persona)):
            res.record("FAIL", name, f"base_persona '{persona}' does not resolve")
            continue
        res.record("PASS", name, "ground-truth+gates+persona OK")


    # --- Initial intake: HR/FN upload packet exists, attorney-only answer key
    #     is separated, and legal-drafted filing artifacts are not in the
    #     upload folder because they are intentionally created after intake. ---
    for d in case_dirs("h1b-initial-intake"):
        slug = os.path.basename(d)
        name = f"h1b-initial-intake/{slug}"
        try:
            case = load_json(os.path.join(d, "case.json"))
            gt = load_json(os.path.join(d, "ground-truth.json"))
        except (OSError, ValueError) as exc:
            res.record("FAIL", name, f"metadata unreadable: {exc}")
            continue
        missing = [f for f in INTAKE_REQUIRED if not os.path.exists(os.path.join(d, f))]
        if missing:
            res.record("FAIL", name, f"missing required intake files: {missing}")
            continue
        if case.get("case_id") != gt.get("case_id"):
            res.record("FAIL", name, "case.json and ground-truth.json case_id differ")
            continue
        if case.get("workflow_stage") != "initial_intake" or gt.get("workflow_stage") != "initial_intake":
            res.record("FAIL", name, "workflow_stage must be initial_intake")
            continue
        if case.get("upload_folder") != "packet-for-lei-upload":
            res.record("FAIL", name, "upload_folder must be packet-for-lei-upload")
            continue
        do_not_upload = set(case.get("do_not_upload") or [])
        required_exclusions = {"attorney-only", "ground-truth.json", "case.json"}
        if not required_exclusions.issubset(do_not_upload):
            res.record("FAIL", name, f"do_not_upload missing {sorted(required_exclusions - do_not_upload)}")
            continue
        findings = gt.get("expected_findings") or []
        finding_ids = {f.get("id") for f in findings}
        required_findings = {
            "lca_absent_initial_intake",
            "support_letter_absent_initial_intake",
            "remote_worksite_athens",
            "passport_expires_soon",
        }
        if not required_findings.issubset(finding_ids):
            res.record("FAIL", name, f"expected_findings missing {sorted(required_findings - finding_ids)}")
            continue
        upload_root = os.path.join(d, "packet-for-lei-upload")
        uploaded_files = []
        for root, _, files in os.walk(upload_root):
            uploaded_files.extend(os.path.relpath(os.path.join(root, f), upload_root).lower() for f in files)
        forbidden = [f for f in uploaded_files if any(token in f for token in INTAKE_FORBIDDEN_UPLOAD_NAMES)]
        if forbidden:
            res.record("FAIL", name, f"legal-drafted artifact appears in upload packet: {forbidden}")
            continue
        res.record("PASS", name, f"initial-intake metadata+upload boundary OK ({len(findings)} expected findings)")

    # --- Aggregate JSON corpora (materiality, statusclock): parse + non-empty. ---
    for fname in ("h1b-materiality/cases.json", "h1b-statusclock/cases.json"):
        path = os.path.join(CASES, fname)
        try:
            blob = load_json(path)
        except (OSError, ValueError) as exc:
            res.record("FAIL", fname, f"unreadable: {exc}")
            continue
        if not blob.get("cases"):
            res.record("FAIL", fname, "no cases[] present")
            continue
        res.record("PASS", fname, f"{len(blob['cases'])} cases parse")

    res.summary("integrity")


# ===========================================================================
# TIER 2 — Adversarial gates (right-pass discipline)
# ===========================================================================
def check_adversarial(res: Results) -> None:
    print("== adversarial ==")
    for d in case_dirs("h1b-adversarial"):
        name = f"h1b-adversarial/{os.path.basename(d)}"
        gt = load_json(os.path.join(d, "ground-truth.json"))
        expected = gt.get("expected_gates", [{}])[0].get("gate")
        if expected not in GATES:
            res.record("FAIL", name, f"expected gate '{expected}' is not implemented")
            continue
        fired = fired_gates(gt)
        if fired == {expected}:
            res.record("PASS", name, f"only '{expected}' fired (right-pass)")
        elif expected not in fired:
            res.record("FAIL", name, f"named gate '{expected}' did NOT fire "
                                     f"(fired: {sorted(fired) or 'none'})")
        else:
            siblings = sorted(fired - {expected})
            res.record("FAIL", name, f"sibling gate(s) also fired: {siblings} "
                                     f"(wrong-reason pass)")
    res.summary("adversarial")


# ===========================================================================
# TIER 3 — Incomplete (missing required document / field)
# ===========================================================================
def check_incomplete(res: Results) -> None:
    print("== incomplete ==")
    for d in case_dirs("h1b-incomplete"):
        name = f"h1b-incomplete/{os.path.basename(d)}"
        gt = load_json(os.path.join(d, "ground-truth.json"))
        gate = gt.get("expected_gates", [{}])[0]
        kind = gate.get("gate")

        if kind == "missing_required_document":
            missing_kind = gate.get("missing_kind")
            # The declared-missing kind must be in documents_missing ...
            if missing_kind not in (gt.get("documents_missing") or []):
                res.record("FAIL", name,
                           f"missing_kind '{missing_kind}' not in documents_missing")
                continue
            # ... and the corresponding file must be genuinely absent on disk.
            fname = KIND_TO_FILE.get(missing_kind)
            if fname and os.path.exists(os.path.join(d, fname)):
                res.record("FAIL", name,
                           f"document '{missing_kind}' declared missing but {fname} exists")
                continue
            # ... and no fact should claim that source kind.
            facts = gt.get("facts") or []
            if any(f.get("source_kind") == missing_kind for f in facts):
                res.record("FAIL", name,
                           f"facts reference missing source_kind '{missing_kind}'")
                continue
            res.record("PASS", name, f"missing document '{missing_kind}' confirmed absent")

        elif kind == "missing_required_field":
            field = gate.get("missing_field")
            facts = gt.get("facts") or []
            # The field must be genuinely absent from the extracted facts.
            if any(f.get("predicate") == field for f in facts):
                res.record("FAIL", name,
                           f"field '{field}' declared missing but present in facts")
                continue
            res.record("PASS", name, f"missing field '{field}' confirmed absent")

        else:
            res.record("FAIL", name, f"unexpected completeness gate '{kind}'")
    res.summary("incomplete")


# ===========================================================================
# TIER 4 — Status-clock arithmetic
# ===========================================================================
def check_statusclock(res: Results) -> None:
    print("== statusclock ==")
    blob = load_json(os.path.join(CASES, "h1b-statusclock", "cases.json"))
    for case in blob.get("cases", []):
        cid = case["id"]
        name = f"statusclock/{cid}"
        expect = case.get("expect", {})
        computed = compute_status_clock(case.get("periods", []), case.get("travel", []))
        if not computed:
            res.record("SKIP", name, "no parseable periods")
            continue
        # Assert only the keys the fixture chose to pin (some omit
        # adjusted_max_out on a reset, where it is undefined).
        mismatches = []
        for key in ("base_max_out", "adjusted_max_out", "recaptured_days", "reset"):
            if key in expect and expect[key] != computed.get(key):
                mismatches.append(f"{key}: expected {expect[key]!r}, got {computed.get(key)!r}")
        if mismatches:
            res.record("FAIL", name, "; ".join(mismatches))
        else:
            res.record("PASS", name,
                       f"max-out {computed['base_max_out']} "
                       f"(+{computed['recaptured_days']}d, reset={computed['reset']})")
    res.summary("statusclock")


# ===========================================================================
# TIER 5 — Materiality (structural + internal consistency)
# ===========================================================================
def check_materiality(res: Results) -> None:
    print("== materiality ==")
    blob = load_json(os.path.join(CASES, "h1b-materiality", "cases.json"))
    verdict_classes = set(blob.get("verdict_classes", {}))
    if not verdict_classes:
        res.record("FAIL", "materiality/_schema", "no verdict_classes declared")
        res.summary("materiality")
        return

    seen_ids: set[str] = set()
    for case in blob.get("cases", []):
        cid = case.get("id", "<no-id>")
        name = f"materiality/{cid}"

        # No id collisions.
        if cid in seen_ids:
            res.record("FAIL", name, "duplicate case id")
            continue
        seen_ids.add(cid)

        expect = case.get("expect", {})
        change = case.get("change", {})

        # change.predicate must be present.
        if not change.get("predicate"):
            res.record("FAIL", name, "change.predicate missing")
            continue

        # The explicit negative case: empty expect (no impact). Validate it
        # really is structured as a no-op and does not also claim rules.
        if expect.get("empty"):
            if expect.get("rule_ids") or expect.get("primary_kind"):
                res.record("FAIL", name, "empty-expect case also asserts rule_ids/primary_kind")
            else:
                res.record("PASS", name, "no-op (empty expect) structurally valid")
            continue

        # expect.rule_ids non-empty list of strings.
        rule_ids = expect.get("rule_ids")
        if not isinstance(rule_ids, list) or not rule_ids \
                or not all(isinstance(r, str) and r for r in rule_ids):
            res.record("FAIL", name, "expect.rule_ids missing/empty/non-string")
            continue

        # expect.material must be a bool.
        if not isinstance(expect.get("material"), bool):
            res.record("FAIL", name, "expect.material is not a bool")
            continue

        # expect.primary_kind must be one of the declared verdict classes.
        pk = expect.get("primary_kind")
        if pk not in verdict_classes:
            res.record("FAIL", name,
                       f"primary_kind '{pk}' not in verdict_classes {sorted(verdict_classes)}")
            continue

        # Internal consistency: a 'stale' verdict is by definition not material;
        # an 'amendment_required' verdict is material; an 'advisory' ("it depends")
        # is a judgment call the engine never auto-asserts as material.
        if pk == "stale" and expect["material"] is True:
            res.record("FAIL", name, "primary_kind 'stale' but material=true (inconsistent)")
            continue
        if pk == "amendment_required" and expect["material"] is False:
            res.record("FAIL", name, "primary_kind 'amendment_required' but material=false")
            continue
        if pk == "advisory" and expect["material"] is True:
            res.record("FAIL", name, "primary_kind 'advisory' but material=true (an 'it depends' is never auto-material)")
            continue

        # forbid_rule_ids, when present, must be disjoint from rule_ids.
        forbid = expect.get("forbid_rule_ids") or []
        overlap = set(forbid) & set(rule_ids)
        if overlap:
            res.record("FAIL", name, f"forbid_rule_ids overlaps rule_ids: {sorted(overlap)}")
            continue

        res.record("PASS", name, f"{pk} / material={expect['material']} / {rule_ids}")

    res.summary("materiality")


# ===========================================================================
# Driver
# ===========================================================================
TIERS = {
    "integrity":   check_integrity,
    "adversarial": check_adversarial,
    "incomplete":  check_incomplete,
    "statusclock": check_statusclock,
    "materiality": check_materiality,
}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Reference validator for the pearson-demo-cases H-1B corpus.")
    parser.add_argument(
        "tier", nargs="?", default="all",
        choices=["all"] + list(TIERS),
        help="which corpus tier to validate (default: all)")
    args = parser.parse_args(argv)

    if not os.path.isdir(CASES):
        print(f"error: cases dir not found at {CASES}", file=sys.stderr)
        return 1

    to_run = list(TIERS) if args.tier == "all" else [args.tier]

    total = Results()
    for tier in to_run:
        res = Results()
        TIERS[tier](res)
        total.passed += res.passed
        total.failed += res.failed
        total.skipped += res.skipped
        print()

    print("=" * 60)
    print(f"TOTAL: {total.passed} passed, {total.failed} failed, "
          f"{total.skipped} skipped")
    print("=" * 60)
    return 0 if total.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
