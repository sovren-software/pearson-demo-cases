#!/usr/bin/env python3
"""
build_eval_tasks.py — turn the corpus into agent-evaluation tasks + scoring oracles.

This is the bridge between the *data* (cases + answer keys) and a *computer-use
evaluation*: for each case it emits a task an agent must accomplish by operating
a real intake system, plus the oracle that scores the result. It does NOT run any
agent — it produces the eval set that a harness (e.g. an in-app planning agent
driving the system through its capability surface) consumes. See EVAL-PROTOCOL.md.

Each emitted task (JSONL line):
  {
    "id":      "<corpus>/<case>",
    "corpus":  "...",
    "split":   "train|dev|test|unassigned",
    "persona": "<persona slug or null>",
    "task":    "<what the agent must do, in operator terms>",
    "oracle":  { ... how to score the result ... },
    "attorney_review": "confirmed|approved_with_conditions|unreviewed|not_applicable|null"
  }

Scoring contract by corpus (the oracle):
  - adversarial : agent must surface EXACTLY the named gate and no sibling gate
                  ("right-pass discipline"). oracle.must_fire = the gate; oracle.exactly_one = true.
  - incomplete  : agent must report the missing document/field. oracle.missing_* = expected.
  - initial_intake: agent must apply workflow-stage-aware review: expected-absent
                    legal drafting artifacts are not defects, but intake facts still
                    drive follow-up findings.
  - materiality : agent must classify the disposition. oracle.primary_kind + rule_ids + material.
  - statusclock : agent must compute the clock. oracle = the expected clock values.
  - happy       : agent must extract the case facts and fill the I-129. oracle = the fact blocks.

Usage:  python3 eval/build_eval_tasks.py            # -> eval/eval_tasks.jsonl (+ stdout summary)
        python3 eval/build_eval_tasks.py --split test   # only the held-out test split
"""
import argparse
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _splits():
    out = {}
    for name in ("train", "dev", "test"):
        p = os.path.join(HERE, "splits", f"{name}.txt")
        if os.path.exists(p):
            for line in open(p):
                cid = line.strip()
                if cid:
                    out[cid] = name
    return out


def _doc_cases(corpus):
    for gt in sorted(glob.glob(os.path.join(ROOT, "cases", corpus, "*", "ground-truth.json"))):
        yield os.path.basename(os.path.dirname(gt)), json.load(open(gt))


def _ar(d):
    ar = d.get("attorney_review")
    return ar.get("status") if isinstance(ar, dict) else None


def build():
    tasks = []

    # happy — extract + fill
    for slug, d in _doc_cases("h1b"):
        tasks.append(dict(
            id=f"h1b/{slug}", corpus="h1b", persona=d.get("persona", slug),
            task="Ingest this case's documents, extract the beneficiary, employment, "
                 "status, and education facts, and populate the I-129.",
            oracle={"kind": "facts_match",
                    "expect": {k: d[k] for k in
                               ("beneficiary_from_passport", "employment_from_offer_letter",
                                "status_from_i94", "education_from_degree") if k in d}},
            attorney_review=_ar(d)))

    # adversarial — surface exactly the named gate
    for slug, d in _doc_cases("h1b-adversarial"):
        gate = d["expected_gates"][0]["gate"]
        tasks.append(dict(
            id=f"h1b-adversarial/{slug}", corpus="h1b-adversarial", persona=d.get("base_persona"),
            task="Ingest this case and review it for cross-document problems. Surface the "
                 "review gate(s) a competent intake system should raise.",
            oracle={"kind": "right_pass", "must_fire": gate, "exactly_one": True,
                    "severity": d["expected_gates"][0].get("severity")},
            attorney_review=_ar(d)))

    # incomplete — report what's missing
    for slug, d in _doc_cases("h1b-incomplete"):
        eg = d["expected_gates"][0]
        tasks.append(dict(
            id=f"h1b-incomplete/{slug}", corpus="h1b-incomplete", persona=d.get("base_persona"),
            task="Ingest this (partial) case and report any required document or field "
                 "that is missing for an H-1B filing.",
            oracle={"kind": "completeness", "gate": eg["gate"],
                    "missing_documents": d.get("documents_missing"),
                    "missing_kind": eg.get("missing_kind"), "missing_field": eg.get("missing_field")},
            attorney_review=_ar(d)))

    # initial intake — apply stage-aware review instead of filing-packet completeness
    for slug, d in _doc_cases("h1b-initial-intake"):
        findings = d.get("expected_findings") or []
        tasks.append(dict(
            id=f"h1b-initial-intake/{slug}", corpus="h1b-initial-intake", persona=None,
            task="Ingest this initial H-1B intake packet and review it using the workflow "
                 "stage. Do not treat legal-team-created documents such as the LCA or "
                 "support letter as missing intake defects; surface the attorney-review "
                 "and client/follow-up items supported by the HR and beneficiary materials.",
            oracle={"kind": "initial_intake",
                    "workflow_stage": d.get("workflow_stage"),
                    "expected_findings": findings,
                    "expected_absent_not_defects": [
                        f.get("id") for f in findings
                        if f.get("severity") == "no_issue_monitor" and "absent_initial_intake" in f.get("id", "")
                    ]},
            attorney_review=_ar(d)))

    # materiality — classify the disposition of a change
    mj = os.path.join(ROOT, "cases", "h1b-materiality", "cases.json")
    if os.path.exists(mj):
        for c in json.load(open(mj))["cases"]:
            ex = c.get("expect", {})
            tasks.append(dict(
                id=f"h1b-materiality/{c['id']}", corpus="h1b-materiality", persona=None,
                task=f"A filed petition changes: {c.get('change')}. Classify the correct "
                     "disposition (amendment_required / notice_obligation / stale / constraint_violated).",
                oracle={"kind": "materiality", "primary_kind": ex.get("primary_kind"),
                        "rule_ids": ex.get("rule_ids"), "material": ex.get("material"),
                        "forbid_rule_ids": ex.get("forbid_rule_ids")},
                attorney_review=c.get("attorney_review", {}).get("status")
                if isinstance(c.get("attorney_review"), dict) else None))

    # statusclock — compute the clock
    sj = os.path.join(ROOT, "cases", "h1b-statusclock", "cases.json")
    if os.path.exists(sj):
        sc = json.load(open(sj))
        as_of = sc.get("as_of")
        for c in sc["cases"]:
            tasks.append(dict(
                id=f"h1b-statusclock/{c['id']}", corpus="h1b-statusclock", persona=None,
                task=f"As of {as_of}, given the status periods and travel, compute the H/L-1 "
                     "maximum-stay (max-out) date, recaptured days, and whether the clock resets.",
                oracle={"kind": "statusclock", "as_of": as_of, "expect": c.get("expect")},
                attorney_review=None))

    sp = _splits()
    for t in tasks:
        t["split"] = sp.get(t["id"], "unassigned")
    return tasks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "dev", "test", "unassigned"])
    ap.add_argument("-o", "--out", default=os.path.join(HERE, "eval_tasks.jsonl"))
    args = ap.parse_args()

    tasks = build()
    if args.split:
        tasks = [t for t in tasks if t["split"] == args.split]
    with open(args.out, "w") as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    from collections import Counter
    by_corpus = Counter(t["corpus"] for t in tasks)
    by_split = Counter(t["split"] for t in tasks)
    print(f"wrote {len(tasks)} eval tasks -> {os.path.relpath(args.out, ROOT)}")
    print("  by corpus:", dict(by_corpus))
    print("  by split: ", dict(by_split))


if __name__ == "__main__":
    main()
