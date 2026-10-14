"""Benchmark: Decider 2B (local) vs an LLM-as-judge (Bedrock) on the same gate.

  python bench.py            Decider only
  python bench.py --llm      also run Claude Haiku via Bedrock as the judge

Both models answer the SAME three yes/no questions; the SAME decide() turns
answers into an action, so only the model differs. Cases that the rules settle
alone (read-only, forbidden, destructive+prod) never call a model.
"""
import json
import re
import statistics
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from decision_pattern import decider_client
from decision_pattern.risk_gate import QUESTIONS, build_state, classify, decide, needs_model

CASES = [json.loads(l) for l in Path("data/cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
USE_LLM = "--llm" in sys.argv


def decider_probs(state):
    t = time.perf_counter()
    r = decider_client.ask(state, QUESTIONS)
    ms = (time.perf_counter() - t) * 1000
    return decider_client.yes_probabilities(r, QUESTIONS), ms


def llm_probs(state):
    import boto3
    import os
    br = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    model = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
    qs = "\n".join(f'- "{k}": {v["instructions"]}' for k, v in QUESTIONS.items())
    prompt = (f"{state}\n\nAnswer these yes/no questions about the proposed command.\n{qs}\n"
              'Reply with ONLY a JSON object like {"named_target": true, "destructive": false, "production": false}.')
    t = time.perf_counter()
    r = br.converse(modelId=model, messages=[{"role": "user", "content": [{"text": prompt}]}],
                    inferenceConfig={"maxTokens": 100})
    ms = (time.perf_counter() - t) * 1000
    text = r["output"]["message"]["content"][0]["text"]
    obj = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    return {k: 1.0 if obj.get(k) else 0.0 for k in QUESTIONS}, ms


def run(name, fn):
    rows, lat, correct = [], [], 0
    for c in CASES:
        info = classify(c["command"])
        probs, ms = {}, None
        if needs_model(info):
            probs, ms = fn(build_state([c["user"]], c["command"]))
            lat.append(ms)
        d = decide(info, probs)
        ok = d.action == c["expected"]
        correct += ok
        p = probs.get("named_target")
        rows.append((c["id"], c["expected"], d.action, "OK" if ok else "MISS",
                     f"{p:.0%}" if p is not None else "-", f"{ms:.0f}" if ms is not None else "rules"))
    return rows, lat, correct


def main():
    results = {}
    print("Warming up Decider...")
    decider_probs(build_state(["warm up"], "oc get pods"))
    results["Decider 2B (local)"] = run("decider", decider_probs)
    if USE_LLM:
        results["LLM judge (Bedrock)"] = run("llm", llm_probs)

    lines = ["# OpsGuard benchmark", ""]
    for name, (rows, lat, correct) in results.items():
        lines += [f"## {name}", "", "| id | expected | got | result | named_target | ms |", "|---|---|---|---|---|---|"]
        lines += [f"| {a} | {b} | {c} | {d} | {e} | {f} |" for a, b, c, d, e, f in rows]
        lines += ["", f"Accuracy: {correct}/{len(CASES)} | model calls: {len(lat)} | "
                      f"median latency: {statistics.median(lat):.0f} ms | p95: {sorted(lat)[int(len(lat) * .95) - 1]:.0f} ms", ""]
    if USE_LLM:
        lines += ["## Summary", "", "| judge | accuracy | median ms |", "|---|---|---|"]
        for name, (rows, lat, correct) in results.items():
            lines.append(f"| {name} | {correct}/{len(CASES)} | {statistics.median(lat):.0f} |")
    out = "\n".join(lines)
    print(out)
    Path("results").mkdir(exist_ok=True)
    Path("results/bench.md").write_text(out, encoding="utf-8")
    print("\nSaved results/bench.md")


if __name__ == "__main__":
    main()
