"""Tiny stdlib client for a locally served Strands Decider 2B.

Start the server first:
    strands-decider serve StrandsAgents/strands-decider-2B-hobson-v21 --port 8099
"""
import json
import os
import urllib.error
import urllib.request

HOST = os.environ.get("STRANDS_DECIDER_HOST", "127.0.0.1:8099")


class DeciderUnavailable(RuntimeError):
    """Raised when the Decider server cannot be reached or answers badly."""


def ask(state, questions, host=None, timeout=120):
    """POST /v1/systemone. Returns the parsed JSON (answers + latency_ms)."""
    url = "http://" + (host or HOST) + "/v1/systemone"
    body = json.dumps({"state": state, "questions": questions}).encode()
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read())
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise DeciderUnavailable(f"Decider server not reachable at {url}: {e}") from e


def yes_probabilities(response, names):
    """Pull the 'yes' probability of every noul question out of a response."""
    try:
        return {n: float(response["answers"][n]["noul"]) for n in names}
    except (KeyError, TypeError, ValueError) as e:
        raise DeciderUnavailable(f"Unexpected Decider response: {response!r}") from e
