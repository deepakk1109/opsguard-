"""Pure decision logic for OpsGuard (no Strands, no network -> easy to test).

Pattern: Decider 2B answers three narrow yes/no questions about a proposed
command; deterministic rules set a safety floor; thresholds in plain Python
turn probabilities into one of four actions: proceed | confirm | ask | deny.
"""
import os
import re
import shlex
from dataclasses import dataclass, field

# ---- 1. The typed question set handed to Decider 2B -----------------------
# Narrow, positively-phrased questions work best (the model does not reliably
# follow negated / "which does NOT fit" questions).
QUESTIONS = {
    "named_target": {
        "type": "noul",
        "instructions": "Does the user's message mention the same resource name that appears in the command?",
        "criteria": {
            "true": "the resource name in the command (for example payments) is written in the user's message",
            "false": "the command's resource name is not written anywhere in the user's message",
        },
    },
    "destructive": {
        "type": "noul",
        "instructions": "Does this command delete, scale to zero, or stop running workloads?",
        "criteria": {
            "true": "it removes or stops something that is currently running",
            "false": "it only reads, restarts safely, or scales up",
        },
    },
    "production": {
        "type": "noul",
        "instructions": "Does this command target a production namespace?",
        "criteria": {
            "true": "the namespace is prod, production, live or similar",
            "false": "the namespace is dev, test, staging, sandbox or personal",
        },
    },
}

# Tune these from YOUR data: run `python tune.py`, then export OPSGUARD_T_GROUNDED=0.xx
T_GROUNDED = float(os.environ.get("OPSGUARD_T_GROUNDED", "0.65"))  # below -> target not named -> ask
T_FLAG = float(os.environ.get("OPSGUARD_T_FLAG", "0.60"))          # at/above -> destructive/production flag on

# ---- 2. Deterministic safety floor ---------------------------------------
READ_ONLY = {"get", "describe", "logs", "top", "status", "whoami", "events"}
MUTATING = {"rollout", "scale", "delete"}
ROLLOUT_READ = {"status", "history"}
ROLLOUT_MUT = {"restart", "undo"}
META = re.compile(r"[;&|`$<>\n\r]")
PROD = re.compile(r"(^|[-_.])(prod|production|prd|live)($|[-_.])", re.I)
ZERO = re.compile(r"--replicas(=|\s+)0\b")
BLAST = {"-A", "--all-namespaces", "--all"}


@dataclass
class CommandInfo:
    command: str
    verb: str = ""
    sub: str = ""
    namespace: str = None
    read_only: bool = False
    forbidden: str = ""          # non-empty -> hard deny
    rule_destructive: bool = False
    rule_prod: bool = False
    no_namespace: bool = False


@dataclass
class Decision:
    action: str                  # proceed | confirm | ask | deny
    reason: str
    probs: dict = field(default_factory=dict)


def classify(command):
    command = (command or "").strip()
    info = CommandInfo(command=command)
    if META.search(command):
        info.forbidden = "shell metacharacters are not allowed"
        return info
    try:
        tokens = shlex.split(command)
    except ValueError:
        info.forbidden = "command could not be parsed"
        return info
    if not tokens or tokens[0] not in ("oc", "kubectl"):
        info.forbidden = "only oc/kubectl commands are allowed"
        return info

    positional, flags, ns, i = [], [], None, 1
    while i < len(tokens):
        t = tokens[i]
        if t in ("-n", "--namespace"):
            ns = tokens[i + 1] if i + 1 < len(tokens) else None
            i += 2
            continue
        if t.startswith("--namespace="):
            ns = t.split("=", 1)[1]
        elif t.startswith("-"):
            flags.append(t)
        else:
            positional.append(t)
        i += 1

    info.namespace = ns
    info.verb = positional[0] if positional else ""
    info.sub = positional[1] if len(positional) > 1 else ""
    blast = bool(BLAST & set(flags))

    if info.verb in READ_ONLY:
        info.read_only = True
    elif info.verb == "rollout":
        if info.sub in ROLLOUT_READ:
            info.read_only = True
        elif info.sub not in ROLLOUT_MUT:
            info.forbidden = f"'rollout {info.sub}' is not on the allowlist"
    elif info.verb not in MUTATING:
        info.forbidden = f"verb '{info.verb}' is not on the allowlist"

    if info.forbidden or info.read_only:
        return info

    info.rule_destructive = info.verb == "delete" or (info.verb == "scale" and bool(ZERO.search(command)))
    info.rule_prod = bool(ns and PROD.search(ns)) or blast
    info.no_namespace = ns is None and not blast
    return info


def needs_model(info):
    """Ask Decider only when the rules cannot settle it already."""
    if info.forbidden or info.read_only:
        return False
    return not (info.rule_destructive and info.rule_prod)


def decide(info, probs=None):
    probs = probs or {}
    if info.forbidden:
        return Decision("deny", info.forbidden, probs)
    if info.read_only:
        return Decision("proceed", "read-only command", probs)

    destr = info.rule_destructive or probs.get("destructive", 0.0) >= T_FLAG
    prod = info.rule_prod or probs.get("production", 0.0) >= T_FLAG
    if destr and prod:
        return Decision("deny", "destructive command against production", probs)
    if probs.get("named_target", 1.0) < T_GROUNDED:
        return Decision("ask", "user never named the target of this command", probs)
    if destr:
        return Decision("confirm", "destructive command", probs)
    if prod:
        return Decision("confirm", "targets a production namespace", probs)
    if info.no_namespace:
        return Decision("confirm", "no namespace given, current project is unknown", probs)
    return Decision("proceed", "low risk, target named by the user", probs)


# ---- helpers shared by handler and bench ----------------------------------
def build_state(user_messages, command):
    # Only the USER's words: the agent's own "let me restart X" would make a
    # guessed target look grounded.
    talk = "\n".join(f"user: {m}" for m in user_messages)
    return f"--- CONVERSATION ---\n{talk}\n\n--- PROPOSED COMMAND ---\n{command}"


CONFIRM_RE = re.compile(
    r"(yes|y|yep|confirm|confirmed|proceed|go ahead|do it|ok|okay)"
    r"([ ,.!]+(please|confirm|proceed|go ahead|do it))?[.! ]*", re.I)


def is_confirmation(text):
    return bool(CONFIRM_RE.fullmatch((text or "").strip()))


def normalize(command):
    return " ".join((command or "").split())
