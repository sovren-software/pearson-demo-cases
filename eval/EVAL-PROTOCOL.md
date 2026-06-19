# Evaluation protocol

This corpus is a benchmark for **agents that operate a document-intake / case-integrity system** — not just classifiers. The interesting failure mode in computer-use agents isn't producing invalid output; it's producing *plausible-but-wrong* output: a confident action that's valid in form and wrong in substance. These cases, with their answer keys, are built to measure exactly that.

This `eval/` package turns the corpus into a runnable evaluation:

| File | Role |
|------|------|
| `build_eval_tasks.py` | emits `eval_tasks.jsonl` — one **task + scoring oracle** per case |
| `make_splits.py` + `splits/` | the deterministic **held-out split** (train / dev / test) |
| `run_eval.py` | runs any OpenAI-compatible model over the tasks and strict-scores it |
| this doc | the protocol an honest measurement must follow |

```sh
python3 eval/make_splits.py          # (re)generate the split
python3 eval/build_eval_tasks.py     # -> eval/eval_tasks.jsonl
python3 eval/build_eval_tasks.py --split test   # the held-out test set only

# run a model (or two, for the size delta) against the tasks:
python3 eval/run_eval.py --endpoint http://HOST/v1 --model small-model --model large-model
```

> **Reasoning models:** if your endpoint serves a thinking model, disable thinking for
> a clean classification answer — a reasoning block otherwise blows the token budget and
> the model never reaches its answer, which silently scores 0. `run_eval.py` sends
> `chat_template_kwargs.enable_thinking=false` (the qwen3 switch) and parses an explicit
> `ANSWER:` line for exactly this reason.

## What an agent does with a task

Each task names a goal an agent must accomplish by *operating the system* (ingest the case, read its state, raise the right gate, classify the change, compute the clock) — and the `oracle` says how to score the result. A harness wraps the agent under test: feed it the case, let it operate, then compare what it produced against the oracle. The corpus is harness-agnostic — any agent that can drive an intake system can be measured against it.

## The scoring contract (per corpus)

- **adversarial → right-pass discipline (the load-bearing one).** The agent passes a case **only if it surfaces exactly that case's named gate, and no sibling gate.** A case that trips for the *wrong* reason, or trips two gates, is a **fail** — not a partial credit. This is what separates "caught a problem" from "caught *the* problem," and it's the single most important discipline for measuring a computer-use agent's reliability.
- **incomplete →** the agent must report the missing required document/field (`oracle.missing_*`).
- **materiality →** the agent must return the correct disposition (`oracle.primary_kind` + `rule_ids`), and must NOT return any `forbid_rule_ids`.
- **statusclock →** the agent's computed max-out / recaptured-days / reset must equal `oracle.expect`.
- **happy →** the extracted facts must match the `oracle.expect` fact blocks.

## Three rules that keep the measurement honest

1. **Never evaluate on training data.** If you few-shot or fine-tune an agent on these cases, draw training examples **only from the `train` split** (or generate fresh synthetic cases) and **measure on the held-out `dev`/`test` split.** Training on what you score measures memorization, not capability. `make_splits.py` produces a stable, stratified split for exactly this; `eval_tasks.jsonl` tags every task with its split.

2. **Strict scoring only.** Report the strict number (the right-pass / exact-oracle count), not a lenient "some gate fired" count. A near-miss is a fail. Over a corpus, a lenient scorer silently inflates results and hides regressions.

3. **Measure two model sizes, report the delta.** Run the **same harness** with a small model and a larger model on every task, and report both. The gap is the most decision-relevant signal there is:

   | small | large | diagnosis |
   |-------|-------|-----------|
   | both fail | — | the harness/observation is the bottleneck (fix the substrate, not the model) |
   | small fails, large passes | — | model-bound — a bigger model or targeted training helps |
   | small regresses on validity, large stable | — | small-model output-format fragility — constrain decoding, don't change behavior |

   A single-model number can't tell you whether to fix the plumbing, train the model, or buy a bigger one.

## Why this is structured this way

A one-shot planner that can't *see* the structured state it operates on will reliably produce valid-but-wrong actions — that's the ceiling that has capped general computer-use agents. An intake system that exposes the case as queryable state with a verification spine removes that ceiling *by construction*, but only shifts the question to: **does the agent reason correctly over the state it can now see?** That's unmeasured until you run it against cases with answer keys. This corpus is that measurement; the split and the strict, two-model protocol are what make the number trustworthy.
