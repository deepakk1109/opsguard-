"""Pick the 'named_target' threshold from data (Decider server must be running).

  python tune.py
Prints named_target for every model-checked case, labelled by whether the user
really named the target (expected != "ask"), then sweeps thresholds.
"""
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from decision_pattern import decider_client
from decision_pattern.risk_gate import QUESTIONS, build_state, classify, needs_model

rows = []
decider_client.ask(build_state(["warm up"], "oc get pods"), QUESTIONS)   # warm-up, ignored
for line in Path("data/cases.jsonl").read_text(encoding="utf-8").splitlines():
    c = json.loads(line)
    if not needs_model(classify(c["command"])):
        continue
    r = decider_client.ask(build_state([c["user"]], c["command"]), QUESTIONS)
    p = decider_client.yes_probabilities(r, QUESTIONS)["named_target"]
    named = c["expected"] != "ask"
    rows.append((p, named, c["id"], c["user"]))
    print(f"id {c['id']:>2}  named_target={p:.0%}  user really named it: {named}   | {c['user']}", flush=True)

pos = [p for p, n, *_ in rows if n]
neg = [p for p, n, *_ in rows if not n]
print(f"\nnamed: min {min(pos):.0%} | not named: max {max(neg):.0%}")
print("\nthreshold  correct")
best = (0, 0)
for i in range(5, 96, 5):
    t = i / 100
    ok = sum((p >= t) == n for p, n, *_ in rows)
    best = max(best, (ok, t))
    print(f"  {t:.2f}     {ok}/{len(rows)}")
print(f"\nBest: export OPSGUARD_T_GROUNDED={best[1]:.2f}  ({best[0]}/{len(rows)})")
if min(pos) <= max(neg):
    print("Classes overlap: this model/question cannot separate them cleanly. Say so in your article.")
