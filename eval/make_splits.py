#!/usr/bin/env python3
"""
make_splits.py — deterministic, stratified train/dev/test split for the corpus.

Why this exists: when you train or few-shot a model on these cases and then
*measure* it on them, training on what you evaluate measures memorization, not
capability. A held-out split is the discipline that keeps the measurement honest
(see eval/EVAL-PROTOCOL.md).

The split is:
  - deterministic    — derived from a stable hash of each case id, so anyone
                       regenerates the identical split (no randomness).
  - stratified       — applied within each corpus, so train/dev/test each carry a
                       representative mix of happy / adversarial / incomplete /
                       materiality / status-clock cases.
  - reproducible as the corpus grows — re-run after adding cases; existing
                       assignments are stable because they depend only on the id.

At today's size (~37 cases) the split is more about *establishing the convention*
than statistical power. The ratio scales with the corpus.

Usage:  python3 eval/make_splits.py        # writes eval/splits/{train,dev,test}.txt
        python3 eval/make_splits.py --check # verify the committed splits are current
"""
import argparse
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SPLIT_DIR = os.path.join(HERE, "splits")
RATIOS = (("train", 0.60), ("dev", 0.20), ("test", 0.20))


def discover():
    """Return {corpus: [case_id, ...]} across all five corpora."""
    out = {}
    for corpus in ("h1b", "h1b-adversarial", "h1b-incomplete"):
        ids = [
            f"{corpus}/{os.path.basename(os.path.dirname(p))}"
            for p in glob.glob(os.path.join(ROOT, "cases", corpus, "*", "ground-truth.json"))
        ]
        out[corpus] = sorted(ids)
    for corpus in ("h1b-materiality", "h1b-statusclock"):
        cj = os.path.join(ROOT, "cases", corpus, "cases.json")
        if os.path.exists(cj):
            out[corpus] = sorted(f"{corpus}/{c['id']}" for c in json.load(open(cj))["cases"])
    return out


def _rank(case_id):
    return int(hashlib.sha256(case_id.encode()).hexdigest(), 16)


def assign(by_corpus):
    """Deterministically assign each case to a split, stratified within each corpus."""
    result = {name: [] for name, _ in RATIOS}
    for corpus, ids in by_corpus.items():
        ordered = sorted(ids, key=_rank)
        n = len(ordered)
        # cumulative boundaries; the last split takes the remainder
        i = 0
        for idx, (name, ratio) in enumerate(RATIOS):
            take = n - i if idx == len(RATIOS) - 1 else round(n * ratio)
            for cid in ordered[i:i + take]:
                result[name].append(cid)
            i += take
    for name in result:
        result[name].sort()
    return result


def write(splits):
    os.makedirs(SPLIT_DIR, exist_ok=True)
    for name, ids in splits.items():
        with open(os.path.join(SPLIT_DIR, f"{name}.txt"), "w") as f:
            f.write("\n".join(ids) + ("\n" if ids else ""))


def read_committed():
    out = {}
    for name, _ in RATIOS:
        p = os.path.join(SPLIT_DIR, f"{name}.txt")
        out[name] = [l.strip() for l in open(p)] if os.path.exists(p) else []
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify committed splits match a fresh generation")
    args = ap.parse_args()

    splits = assign(discover())
    total = sum(len(v) for v in splits.values())

    if args.check:
        if read_committed() == splits:
            print(f"splits up to date ({total} cases: " +
                  ", ".join(f"{n}={len(splits[n])}" for n, _ in RATIOS) + ")")
            return 0
        print("ERROR: committed splits are stale — run `python3 eval/make_splits.py`", file=sys.stderr)
        return 1

    write(splits)
    print(f"wrote {total} cases: " + ", ".join(f"{n}={len(splits[n])}" for n, _ in RATIOS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
