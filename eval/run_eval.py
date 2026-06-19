#!/usr/bin/env python3
"""
run_eval.py — run a model against the corpus and strict-score it.

Drives any OpenAI-compatible chat endpoint over the eval tasks and scores the
result against each task's oracle (see EVAL-PROTOCOL.md). Stdlib only.

What it measures: the agent's *reasoning over visible state* — given a case's
extracted facts, does the model identify exactly the right validation gate
(adversarial, right-pass discipline) or the right change-impact verdict
(materiality)? It deliberately hands the model the facts (not raw PDFs), which
isolates the planner's reasoning from the extraction/harness layer — so a low
score here is model-bound, a high score here means any agent failure is
substrate-bound. That disambiguation is the whole point of measuring.

Usage:
  python3 eval/run_eval.py --endpoint http://127.0.0.1:18384/v1 --model qwen3.5-9b
  python3 eval/run_eval.py --endpoint ... --model qwen3.6-27b-mtp --split test
  # run two models and print the delta:
  python3 eval/run_eval.py --endpoint ... --model qwen3.5-9b --model qwen3.6-27b-mtp

Notes:
  - Default is ZERO-SHOT over ALL adversarial + materiality cases (no few-shot
    drawn from the corpus, so there is no train/test contamination to avoid).
    Once you few-shot or fine-tune on the corpus, pass --split test/dev and draw
    exemplars only from the train split (EVAL-PROTOCOL.md).
  - Scoring is strict: adversarial passes only on the exact named gate.
"""
import argparse
import glob
import json
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_tasks(split=None):
    import subprocess
    subprocess.run(["python3", os.path.join(HERE, "build_eval_tasks.py")],
                   check=True, stdout=subprocess.DEVNULL)
    tasks = [json.loads(l) for l in open(os.path.join(HERE, "eval_tasks.jsonl"))]
    if split:
        tasks = [t for t in tasks if t["split"] == split]
    return tasks


def gate_menu():
    """gate_id -> one-line 'detects' description, from the adversarial corpus."""
    menu = {}
    for gt in glob.glob(os.path.join(ROOT, "cases", "h1b-adversarial", "*", "ground-truth.json")):
        eg = json.load(open(gt))["expected_gates"][0]
        menu[eg["gate"]] = eg.get("detects", "")
    return menu


def adversarial_facts(case_id):
    """Flatten a case's document facts + the contradiction values into a fact list
    the model must reason over (presented as plain facts, not as 'the defect')."""
    gt = json.load(open(os.path.join(ROOT, "cases", case_id, "ground-truth.json")))
    facts = {}
    for blk in ("beneficiary_from_passport", "employment_from_offer_letter",
                "status_from_i94", "education_from_degree"):
        for k, v in (gt.get(blk) or {}).items():
            facts[f"{blk.split('_')[0]}.{k}"] = v
    for k, v in (gt["expected_gates"][0].get("evidence") or {}).items():
        facts.setdefault(k, v)
    return facts


def call(endpoint, model, system, user, timeout=180):
    # enable_thinking=false disables qwen3 reasoning for a clean, fast, uniform
    # classification answer (a reasoning block otherwise blows the token budget and
    # the model never reaches its answer — which silently scores 0).
    body = json.dumps({
        "model": model, "temperature": 0, "max_tokens": 256,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(endpoint.rstrip("/") + "/chat/completions",
                                 data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    return d["choices"][0]["message"]["content"]


def pick(text, options):
    """Extract the model's chosen option robustly: prefer an explicit 'ANSWER: <x>'
    line; else strip any <think> reasoning block and take the LAST option mentioned
    (the final answer, not a word from the reasoning)."""
    t = text or ""
    # strip a (possibly unclosed) <think> block so reasoning text can't pollute the match
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S | re.I)
    t = re.sub(r"<think>.*$", "", t, flags=re.S | re.I)
    m = re.findall(r"answer\s*[:=]\s*([a-z_]+)", t, flags=re.I)
    if m:
        cand = m[-1].lower()
        for o in options:
            if o.lower() == cand:
                return o
    low = t.lower()
    hits = [(low.rfind(o.lower()), o) for o in options if o.lower() in low]
    if hits:
        return max(hits)[1]   # last-occurring option = the final answer
    return "none"


def score_adversarial(task, endpoint, model, menu):
    facts = adversarial_facts(task["id"])
    fact_lines = "\n".join(f"  - {k}: {v}" for k, v in facts.items())
    menu_lines = "\n".join(f"  - {g}: {d}" for g, d in menu.items())
    system = ("You are an H-1B petition intake reviewer. Given the facts extracted "
              "from a case's documents, decide which ONE validation gate should fire, "
              "or 'none'. A gate fires only when the facts actually trigger it. "
              "Reply with exactly one line: ANSWER: <gate_id>")
    user = f"Facts:\n{fact_lines}\n\nGates:\n{menu_lines}\n  - none: no problem\n\nWhich gate fires?"
    out = call(endpoint, model, system, user)
    chosen = pick(out, list(menu) + ["none"])
    return chosen == task["oracle"]["must_fire"], chosen


def score_materiality(task, endpoint, model):
    classes = ["amendment_required", "notice_obligation", "stale", "constraint_violated"]
    system = ("You classify the impact of a change to a filed H-1B petition. "
              "Choose one of: " + ", ".join(classes) + ". "
              "Reply with exactly one line: ANSWER: <choice>")
    user = (f"Change to a filed petition: {task['task'].split(': ', 1)[-1]}\n\n"
            "Which disposition is correct?")
    out = call(endpoint, model, system, user)
    chosen = pick(out, classes)
    return chosen == task["oracle"]["primary_kind"], chosen


def run_model(tasks, endpoint, model, menu):
    rows = []
    for t in tasks:
        try:
            if t["corpus"] == "h1b-adversarial":
                ok, got = score_adversarial(t, endpoint, model, menu)
            elif t["corpus"] == "h1b-materiality" and t["oracle"].get("primary_kind"):
                ok, got = score_materiality(t, endpoint, model)
            else:
                continue
        except Exception as e:
            ok, got = False, f"ERROR:{type(e).__name__}"
        rows.append((t["id"], ok, got))
        print(f"  [{'PASS' if ok else 'fail'}] {t['id']:46} -> {got}")
    p = sum(1 for _, ok, _ in rows if ok)
    return p, len(rows), rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://127.0.0.1:18384/v1")
    ap.add_argument("--model", action="append", required=True, help="repeatable")
    ap.add_argument("--split", choices=["train", "dev", "test"], default=None)
    ap.add_argument("--corpus", choices=["h1b-adversarial", "h1b-materiality"], default=None)
    args = ap.parse_args()

    tasks = load_tasks(args.split)
    if args.corpus:
        tasks = [t for t in tasks if t["corpus"] == args.corpus]
    tasks = [t for t in tasks if t["corpus"] in ("h1b-adversarial", "h1b-materiality")]
    menu = gate_menu()
    scope = f"split={args.split or 'ALL (zero-shot)'}"

    results = {}
    for model in args.model:
        print(f"\n=== {model}  ({scope}) ===")
        p, n, _ = run_model(tasks, args.endpoint, model, menu)
        results[model] = (p, n)
        print(f"  {model}: {p}/{n}")

    print("\n=== summary ===")
    for m, (p, n) in results.items():
        print(f"  {m:24} {p}/{n}  ({100*p//max(n,1)}%)")
    if len(results) == 2:
        (m1, (p1, n1)), (m2, (p2, n2)) = results.items()
        print(f"  delta ({m2} - {m1}): {p2-p1:+d}")


if __name__ == "__main__":
    main()
