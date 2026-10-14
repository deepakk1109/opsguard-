"""The one tool OpsGuard's agent can call. Dry-run by default."""
import os
import shlex
import subprocess

from strands import tool

from decision_pattern.risk_gate import classify


FAKE_PODS = (
    "NAME                        READY   STATUS    RESTARTS   AGE\n"
    "payments-6f7d9c8b5-abcde    1/1     Running   0          2d\n"
    "payments-6f7d9c8b5-fghij    1/1     Running   0          2d\n"
    "(simulated output, dry-run mode)"
)


def _simulate(info, command):
    """Believable fake result, so the LLM does not retry in a loop."""
    if info.read_only:
        return FAKE_PODS if info.verb == "get" else "(simulated output, dry-run mode)"
    return (f"SIMULATED OK: `{command}` passed the safety gate. Dry-run mode is on, so nothing was "
            "changed. Tell the user it was simulated, then stop. Do not call the tool again.")


@tool
def run_oc(command: str) -> str:
    """Run a single oc or kubectl command and return its output.

    Args:
        command: The full command, for example "kubectl get pods -n dev"
    """
    info = classify(command)          # defence in depth: re-check inside the tool
    if info.forbidden:
        return f"BLOCKED: {info.forbidden}"
    if os.environ.get("OPSGUARD_DRY_RUN", "1") != "0":
        return _simulate(info, command)
    try:
        proc = subprocess.run(shlex.split(command), capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        return "ERROR: 'oc' was not found on PATH"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 60s"
    out = (proc.stdout or "") + (proc.stderr or "")
    return out.strip()[:4000] or f"(exit code {proc.returncode}, no output)"
