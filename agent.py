"""OpsGuard: a natural-language OpenShift ops agent whose every command is
gated by Strands Decider 2B.

  python agent.py          interactive chat
  python agent.py --demo   scripted demo conversation
Env: OPSGUARD_DRY_RUN=0 to really execute (default 1 = simulate),
     AWS_REGION, BEDROCK_MODEL_ID to override model/region.
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from strands import Agent
from strands.models import BedrockModel

from decision_pattern.handler import OpsGuard
from tools import run_oc

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")
CLI = os.environ.get("OPSGUARD_CLI", "oc")   # "oc" for OpenShift, "kubectl" for plain Kubernetes

SYSTEM_PROMPT = (
    f"You are OpsGuard, an eager Kubernetes/OpenShift operations assistant. Turn each request into exactly one "
    f"`{CLI}` command and call run_oc immediately; do not ask clarifying questions before calling the tool, "
    "if something is missing make your best guess. A separate safety gate reviews every command. "
    "If the gate sends you feedback, follow it literally: ask the user, request confirmation, or explain the block."
)

DEMO = [
    "list the pods in the dev namespace",                     # read-only -> proceed
    "restart the payments deployment in dev",                  # low risk -> proceed
    "delete the crashed pod payments-7d9f in dev",             # destructive -> confirm
    "yes",                                                     # human confirms -> proceed
    "scale the payments deployment in prod to zero",           # destructive + prod -> deny
]


def build_agent():
    return Agent(
        model=BedrockModel(model_id=MODEL_ID, region_name=REGION),
        tools=[run_oc],
        interventions=[OpsGuard()],
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )


def main():
    agent = build_agent()
    mode = "DRY-RUN" if os.environ.get("OPSGUARD_DRY_RUN", "1") != "0" else "LIVE"
    print(f"OpsGuard ready ({mode}). Type 'exit' to quit.\n")
    if "--demo" in sys.argv:
        for line in DEMO:
            print(f"\nyou> {line}")
            print(f"opsguard> {agent(line)}")
        return
    while True:
        try:
            line = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if line.lower() in {"exit", "quit"}:
            break
        if line:
            print(f"opsguard> {agent(line)}")


if __name__ == "__main__":
    main()
