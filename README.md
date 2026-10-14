# OpsGuard: a Decider-gated OpenShift ops agent

> Built for the AWS **Agent Experience Hackathon: Strands Decider**.
> Tags: `#strands-decider-2b` `#guardrails`

Tell an agent *"restart the payments pod"* and it will happily run
`oc delete pod ... -n prod` if the LLM guesses wrong. **OpsGuard** puts
**Strands Decider 2B** in front of every `oc` command. The LLM (Amazon Bedrock)
proposes the command; Decider answers three yes/no questions in ~100 ms and the agent
gets a typed action back: **Proceed**, **Confirm** (ask a human), **Ask** (clarify) or **Deny**.

```
 user ──► Bedrock LLM (Strands Agent) ──► proposes: oc delete pod payments-7d9f -n dev
                                              │
                       InterventionHandler.before_tool_call
                                              │
        rules: allowlist / no shell chars / destructive? / prod? / blast radius
                                              │
        Decider 2B (local):  named_target?  destructive?  production?
                                              │
              proceed ◄── confirm ◄── ask ◄── deny      (Guide feedback to the agent)
                                              │
                                       run_oc (dry-run by default)
```

## Decision table

| Situation | Action |
|---|---|
| Read-only (`get`, `describe`, `logs`, `rollout status`) | Proceed (no model call) |
| Not on allowlist (`exec`, `debug`), shell metacharacters | Deny |
| Destructive **and** production (or `--all`) | Deny |
| User never named the target (LLM guessed) | Ask the user |
| Destructive, or production, or no namespace | Confirm: human must reply "yes" to the exact command |
| Otherwise | Proceed |

## Quick start (Windows / PowerShell)

See [SETUP_WINDOWS.md](SETUP_WINDOWS.md) for the full walk-through. Short version:

```powershell
.\scripts\setup.ps1            # venv + dependencies
.\scripts\start_decider.ps1    # terminal 2: serves Decider on :8099
aws login                      # AWS creds with Bedrock access
.\scripts\run_demo.ps1         # terminal 1: scripted demo (dry-run)
python agent.py                # interactive
python bench.py --llm          # Decider vs LLM-as-judge
python -m unittest discover -s tests -t .
```

Set `$env:OPSGUARD_DRY_RUN="0"` to really execute against your `oc login` cluster.

## Reusable pattern

`decision_pattern/` is the drop-in asset: typed question set, `InterventionHandler`
wiring and usage note. See [decision_pattern/USAGE.md](decision_pattern/USAGE.md).

## Results

Run `python bench.py --llm` and paste `results/bench.md` here. (Numbers in this
README must come from your own run on your hardware.)

## Limitations (honest)

- Decider 2B is an **experimental** model. A high probability is not a guarantee, which is why
  deterministic rules form the safety floor and a human confirms anything risky.
- 4K context: only the user's messages and the single proposed command are sent.
- Confirmation is matched to the exact command text; if the agent rewrites the command, it is gated again.
- Allowlist covers `get/describe/logs/top/status/events/rollout/scale/delete` only.
- Not a replacement for RBAC. Run the agent with a least-privilege service account.

## Layout

```
agent.py                 Strands agent (Bedrock) + interactive/demo loop
tools.py                 run_oc tool (dry-run default, re-checks the rules)
bench.py                 Decider vs LLM-as-judge: accuracy + latency
data/cases.jsonl         18 labelled cases
decision_pattern/        the reusable pattern (questions, rules, handler, client)
tests/                   20 unit tests (no model or AWS needed)
```
