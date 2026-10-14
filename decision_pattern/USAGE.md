# Reusable pattern: "Decider risk gate" for any Strands tool

**What it does:** before a tool runs, Decider 2B answers a few narrow yes/no
questions about the proposed call. Plain Python turns the probabilities into a
typed action (`Proceed` or `Guide`) so the agent corrects course instead of
guessing or acting recklessly.

## The three pieces

| Piece | File | What to change for your agent |
|---|---|---|
| 1. Typed question + option set | `risk_gate.py` -> `QUESTIONS` | Rewrite the 2-4 `noul` questions for your tool |
| 2. Decision logic | `risk_gate.py` -> `decide()` | Your thresholds and your action mapping |
| 3. Wiring | `handler.py` -> `OpsGuard` | Change `tool_name`; nothing else |

## Drop it into your agent (copy-paste)

```python
from strands import Agent
from decision_pattern.handler import OpsGuard

agent = Agent(
    tools=[your_tool],
    interventions=[OpsGuard(tool_name="your_tool")],
)
```

Start the model first:
`strands-decider serve StrandsAgents/strands-decider-2B-hobson-v21 --port 8099`

## Design rules we learned (and you should keep)

1. **Narrow, positive questions.** "Did the user name the resource in the command?"
   beats "Is this grounded?". Negated questions are not reliably followed.
2. **Show the model only what the user said.** The agent's own "let me restart X"
   makes a guessed target look grounded.
3. **Rules are the floor, the model is the judge in between.** Hard rules (allowlist,
   metacharacters, destructive + prod) never depend on a probability.
4. **Fail closed.** If Decider is unreachable, the handler returns `Guide` and nothing runs.
5. **Pick thresholds from labelled examples**, not by feel: run `python bench.py`
   and read the `named_target` column.
