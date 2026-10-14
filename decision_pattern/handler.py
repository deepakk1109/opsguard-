"""Strands wiring: an InterventionHandler that gates every run_oc call."""
import json
import time
from pathlib import Path

from strands.interventions import Guide, InterventionHandler, Proceed

from . import decider_client
from .risk_gate import (QUESTIONS, build_state, classify, decide, is_confirmation,
                        needs_model, normalize)


def _user_messages(event):
    return [
        b["text"]
        for m in event.agent.messages if m["role"] == "user"
        for b in m.get("content", []) if "text" in b
    ]


class OpsGuard(InterventionHandler):
    name = "opsguard"

    def __init__(self, ask_fn=None, log_path="logs/decisions.jsonl", tool_name="run_oc"):
        super().__init__()
        self.ask_fn = ask_fn or decider_client.ask
        self.log_path = Path(log_path) if log_path else None
        self.tool_name = tool_name
        self.pending = None          # (normalized command, number of user msgs when asked)

    def _log(self, row):
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def before_tool_call(self, event, **kwargs):
        if event.tool_use["name"] != self.tool_name:
            return Proceed()

        command = (event.tool_use.get("input") or {}).get("command", "")
        users = _user_messages(event)
        info = classify(command)
        latency, probs = 0.0, {}

        if needs_model(info):
            # A human "yes" to the exact command we asked about releases it.
            if (self.pending and self.pending[0] == normalize(command)
                    and len(users) > self.pending[1] and is_confirmation(users[-1])):
                self.pending = None
                print(f"[opsguard] {command}  -> human confirmed -> proceed")
                self._log({"command": command, "action": "proceed", "reason": "human confirmed"})
                return Proceed()
            try:
                t = time.perf_counter()
                resp = self.ask_fn(build_state(users, command), QUESTIONS)
                latency = resp.get("latency_ms", (time.perf_counter() - t) * 1000)
                probs = {k: float(resp["answers"][k]["noul"]) for k in QUESTIONS}
            except Exception as e:  # fail CLOSED: no decision, no execution
                print(f"[opsguard] decision service error: {e}")
                return Guide(feedback="The safety gate is unavailable. Do not run this command. "
                                      "Tell the user and stop.")

        d = decide(info, probs)
        shown = " ".join(f"{k}={v:.0%}" for k, v in probs.items()) or "rules only"
        print(f"[opsguard] {command}\n           {shown}  ({latency:.0f} ms)  -> {d.action.upper()}: {d.reason}")
        self._log({"command": command, "action": d.action, "reason": d.reason,
                   "probs": probs, "latency_ms": latency})

        if d.action == "proceed":
            return Proceed()
        if d.action == "ask":
            return Guide(feedback="The user did not clearly name the target of this command. "
                                  "Do not run it. Ask the user exactly which resource and namespace they mean.")
        if d.action == "confirm":
            self.pending = (normalize(command), len(users))
            return Guide(feedback=f"This command is risky ({d.reason}). Do not run it yet. Show the user "
                                  f"this exact command: {command}  and ask them to reply 'yes' to confirm.")
        return Guide(feedback=f"Blocked by policy ({d.reason}). Do not retry this or any variation. "
                              "Explain this to the user and suggest a manual, approved change instead.")
