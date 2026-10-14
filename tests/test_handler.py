"""Handler flow test. Uses the real `strands` if installed, else a tiny stub."""
import sys
import types
import unittest

try:
    import strands.interventions  # noqa: F401
except ImportError:
    pkg, mod = types.ModuleType("strands"), types.ModuleType("strands.interventions")

    class InterventionHandler:
        def __init__(self, *a, **k): pass

    class Proceed:
        pass

    class Guide:
        def __init__(self, feedback=""): self.feedback = feedback

    mod.InterventionHandler, mod.Proceed, mod.Guide = InterventionHandler, Proceed, Guide
    pkg.interventions = mod
    sys.modules["strands"], sys.modules["strands.interventions"] = pkg, mod

from decision_pattern.handler import OpsGuard                      # noqa: E402
from strands.interventions import Guide, Proceed                   # noqa: E402


class Ev:
    def __init__(self, users, command, tool="run_oc"):
        msgs = [{"role": "user", "content": [{"text": u}]} for u in users]
        msgs.insert(1, {"role": "assistant", "content": [{"text": "I will check the thing"}]})
        self.agent = types.SimpleNamespace(messages=msgs)
        self.tool_use = {"name": tool, "input": {"command": command}}


def fake_ask(named=0.9, destr=0.05, prod=0.05, boom=False):
    def f(state, questions):
        if boom:
            raise RuntimeError("down")
        assert "assistant" not in state          # only user words reach the model
        return {"latency_ms": 100, "answers": {"named_target": {"noul": named},
                                               "destructive": {"noul": destr},
                                               "production": {"noul": prod}}}
    return f


class HandlerFlow(unittest.TestCase):
    def test_other_tools_pass(self):
        self.assertIsInstance(OpsGuard(fake_ask(), None).before_tool_call(Ev(["x"], "ls", tool="other")), Proceed)

    def test_low_risk_proceeds(self):
        h = OpsGuard(fake_ask(), None)
        self.assertIsInstance(h.before_tool_call(Ev(["restart payments in dev"], "oc rollout restart deployment/payments -n dev")), Proceed)

    def test_confirm_then_yes(self):
        h = OpsGuard(fake_ask(), None)
        cmd = "oc delete pod p1 -n dev"
        r = h.before_tool_call(Ev(["delete pod p1 in dev"], cmd))
        self.assertIsInstance(r, Guide)
        self.assertIn("yes", r.feedback)
        r2 = h.before_tool_call(Ev(["delete pod p1 in dev", "yes"], cmd))
        self.assertIsInstance(r2, Proceed)

    def test_yes_without_pending_does_not_release(self):
        h = OpsGuard(fake_ask(), None)
        r = h.before_tool_call(Ev(["delete pod p1 in dev", "yes"], "oc delete pod p1 -n dev"))
        self.assertIsInstance(r, Guide)

    def test_yes_for_different_command_does_not_release(self):
        h = OpsGuard(fake_ask(), None)
        h.before_tool_call(Ev(["delete pod p1 in dev"], "oc delete pod p1 -n dev"))
        r = h.before_tool_call(Ev(["delete pod p1 in dev", "yes"], "oc delete pod p2 -n dev"))
        self.assertIsInstance(r, Guide)

    def test_deny_cannot_be_confirmed(self):
        h = OpsGuard(fake_ask(), None)
        cmd = "oc delete pod p1 -n prod"
        self.assertIsInstance(h.before_tool_call(Ev(["delete p1 in prod"], cmd)), Guide)
        self.assertIsInstance(h.before_tool_call(Ev(["delete p1 in prod", "yes"], cmd)), Guide)

    def test_ungrounded_asks(self):
        h = OpsGuard(fake_ask(named=0.2), None)
        r = h.before_tool_call(Ev(["restart it"], "oc rollout restart deployment/payments -n dev"))
        self.assertIsInstance(r, Guide)
        self.assertIn("Ask the user", r.feedback)

    def test_fail_closed(self):
        h = OpsGuard(fake_ask(boom=True), None)
        r = h.before_tool_call(Ev(["restart payments in dev"], "oc rollout restart deployment/payments -n dev"))
        self.assertIsInstance(r, Guide)


if __name__ == "__main__":
    unittest.main()
