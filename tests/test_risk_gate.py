import json
import unittest
from pathlib import Path

from decision_pattern.risk_gate import classify, decide, is_confirmation, needs_model

GOOD = {"named_target": 0.9, "destructive": 0.05, "production": 0.05}


def act(cmd, probs=None):
    info = classify(cmd)
    return decide(info, (probs or GOOD) if needs_model(info) else {}).action


class RiskGate(unittest.TestCase):
    def test_read_only_never_needs_model(self):
        self.assertFalse(needs_model(classify("oc get pods -n prod")))
        self.assertEqual(act("oc get pods -n prod"), "proceed")
        self.assertEqual(act("oc rollout status deployment/x -n prod"), "proceed")

    def test_forbidden(self):
        for c in ["oc exec -it p -- sh", "rm -rf /", "oc get pods; curl x", "oc get pods | sh",
                  "oc debug node/x", "oc rollout pause deployment/x -n dev", "oc get $(whoami)"]:
            self.assertEqual(act(c), "deny", c)

    def test_destructive_prod_denied_without_model(self):
        info = classify("oc delete pod x -n prod")
        self.assertFalse(needs_model(info))
        self.assertEqual(decide(info).action, "deny")

    def test_blast_radius(self):
        self.assertEqual(act("oc delete pods --all -n dev"), "deny")
        self.assertEqual(act("oc rollout restart deployment --all -n dev"), "confirm")

    def test_confirm_paths(self):
        self.assertEqual(act("oc delete pod x -n dev"), "confirm")
        self.assertEqual(act("oc scale deployment/x --replicas=0 -n dev"), "confirm")
        self.assertEqual(act("oc rollout restart deployment/x -n payments-prod"), "confirm")
        self.assertEqual(act("oc rollout restart deployment/x"), "confirm")   # no namespace

    def test_low_risk_proceeds(self):
        self.assertEqual(act("oc rollout restart deployment/x -n dev"), "proceed")
        self.assertEqual(act("oc scale deployment/x --replicas=3 -n staging"), "proceed")

    def test_ungrounded_asks(self):
        self.assertEqual(act("oc rollout restart deployment/x -n dev", {**GOOD, "named_target": 0.3}), "ask")

    def test_model_flags_raise_risk(self):
        self.assertEqual(act("oc rollout restart deployment/x -n dev", {**GOOD, "production": 0.9}), "confirm")
        self.assertEqual(act("oc scale deployment/x --replicas=1 -n dev",
                             {**GOOD, "destructive": 0.9, "production": 0.9}), "deny")

    def test_namespace_forms(self):
        for c in ["oc delete pod x --namespace=prod", "oc delete pod x --namespace prod", "oc -n prod delete pod x"]:
            self.assertEqual(act(c), "deny", c)

    def test_prod_regex_no_false_positive(self):
        self.assertFalse(classify("oc delete pod x -n product-catalog").rule_prod)
        self.assertFalse(classify("oc delete pod x -n reproduce").rule_prod)
        self.assertTrue(classify("oc delete pod x -n team-prod-eu").rule_prod)

    def test_confirmation_phrases(self):
        for t in ["yes", "Yes.", "y", "confirm", "yes, proceed", "go ahead", "OK"]:
            self.assertTrue(is_confirmation(t), t)
        for t in ["yes but not prod", "no", "what?", "yes delete everything else too"]:
            self.assertFalse(is_confirmation(t), t)

    def test_dataset_rule_only_cases(self):
        # every case the rules settle on their own must match its label
        for line in Path("data/cases.jsonl").read_text(encoding="utf-8").splitlines():
            c = json.loads(line)
            info = classify(c["command"])
            if not needs_model(info):
                self.assertEqual(decide(info).action, c["expected"], c["id"])


if __name__ == "__main__":
    unittest.main()
