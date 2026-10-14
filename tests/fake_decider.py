"""Fake /v1/systemone server (keyword heuristic) to smoke-test bench.py without the model.
NOT the real model: never use its numbers in your article."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers["content-length"])
        req = json.loads(self.rfile.read(n))
        s = req["state"].lower()
        user, _, cmd = s.partition("--- proposed command ---")
        res = cmd.split("\n")[1] if "\n" in cmd else cmd
        words = [w for w in res.replace("/", " ").replace("-", " ").split() if w not in {"oc", "rollout", "restart", "deployment", "n", "delete", "pod", "scale", "replicas", "dev"}]
        named = 0.9 if any(w in user for w in words if len(w) > 3) else 0.2
        body = {"latency_ms": 5.0, "answers": {
            "named_target": {"noul": named},
            "destructive": {"noul": 0.9 if " delete " in res or "replicas=0" in res else 0.05},
            "production": {"noul": 0.9 if "prod" in res or "live" in res else 0.05}}}
        out = json.dumps(body).encode()
        self.send_response(200); self.send_header("content-type", "application/json"); self.end_headers(); self.wfile.write(out)

    def log_message(self, *a): pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8099), H).serve_forever()
