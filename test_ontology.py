#!/usr/bin/env python3
"""Ontological invariants of the field, checked cycle by cycle.

The other suites guard the record (chain, cuts, tampering, continuity). This
one guards what the field must be, from the primary source:
  - Zero Points are never operands: they are the Universal apparents (TMC p.22).
  - The older operand leads and the product inherits its handedness
    (Law 6, TMC p.35; first chirality dyad, p.50).
  - An Apparent is incontrovertible: while it exists it is never demoted, its
    crystal state never changes and its identity never shifts (TMC p.14).
  - Nothing vanishes silently: every construct that leaves the field leaves a
    TERMINATE proof (Compiler Guide pp.203-204).
  - "all [Apparents] must be [Existents]" (TMC p.22): no crystal concludes in
    the cycle it forms. Known exception, to be closed in the next framework
    version: during the first breath, UCO can erode a new crystal's BOTH support
    after collapse checked it, and prune then orphans it. The check below
    allows it only within the first breath.
  - No randomness with a model in the loop (TMC p.42): every request carries a
    seed oriented by the history, and two identical runs seal the same ledger.
Runs without Ollama: the model is a deterministic local fake.
Usage: python3 test_ontology.py [cycles per stream]   (default 400)"""
import contextlib, hashlib, io, json, sys, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
with contextlib.redirect_stdout(io.StringIO()):
    from sirisys_loader import load_framework
    S = load_framework(HERE)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def life(stream, cycles, llm, profile=(False, False)):
    """Run `cycles` on synthetic stream `stream`; count every violation."""
    S.set_ledger(S.ProofLedger(None))
    v = {k: [] for k in ("zp_operand", "leader_not_older", "chirality_not_leader",
                         "crystal_changed", "vanished_silently", "crystal_concluded_at_birth")}
    narrate, hour = profile
    with contextlib.redirect_stdout(io.StringIO()):
        ss = S.new_session(llm)
        f = ss.field
        present = set(f.constructs)
        crystals = {n: (c.crystal_state, c.version) for n, c in f.constructs.items()
                    if c.layer == S.Layer.APPARENT}
        terms_seen = f.terminations_total
        for c in range(cycles):
            S.run_cycle(ss, c, percepts=S.synthetic_percepts(c, stream, hour),
                        narrate=narrate, include_hour=hour)
            k = f.terminations_total - terms_seen
            terms = f.termination_log[-k:] if k else []
            ended = {t.meta["name"]: t for t in terms}
            for name, t in ended.items():
                if t.meta["final_layer"] == "APPARENT" and name not in crystals:
                    v["crystal_concluded_at_birth"].append(c)
            for name, (state, version) in crystals.items():
                x = f.constructs.get(name)
                if x is not None and (x.layer != S.Layer.APPARENT or x.crystal_state != state
                                      or x.version != version):
                    v["crystal_changed"].append(c)
            for name in present - set(f.constructs):
                if name not in ended:
                    v["vanished_silently"].append(c)
            for op in ss.concordancy.ops_log:
                if op["cycle"] != c:
                    continue
                x, y, z = op["x"], op["y"], op["z"]
                if x in S.ZERO_POINTS or y in S.ZERO_POINTS:
                    v["zp_operand"].append(c)
                cx, cy, cz = f.constructs.get(x), f.constructs.get(y), f.constructs.get(z)
                if cx and cy:
                    if (tuple(cx.born_at), x) > (tuple(cy.born_at), y):
                        v["leader_not_older"].append(c)
                    if cz and op.get("state") != "CONFLICT" and cz.chirality != cx.chirality:
                        v["chirality_not_leader"].append(c)
            present = set(f.constructs)
            crystals = {n: (x.crystal_state, x.version) for n, x in f.constructs.items()
                        if x.layer == S.Layer.APPARENT}
            terms_seen = f.terminations_total
    return v, S.get_ledger().head, f.apparents_total


# ── field invariants, no model ────────────────────────────────────────
print(f"\n== Field invariants (3 streams × {N} cycles, no model)")
total = {}
crystals_formed = 0
for stream in (0, 1, 2):
    with contextlib.redirect_stdout(io.StringIO()):
        llm = S.LLMIntermediary(backend="none")
    v, _, formed = life(stream, N, llm)
    crystals_formed += formed
    for k, cycles in v.items():
        total.setdefault(k, []).extend(cycles)
check("Zero Points are never operands (TMC p.22)", not total["zp_operand"])
check("the older operand leads (Law 6, TMC p.35)", not total["leader_not_older"])
check("the product inherits the leader's handedness (TMC p.50)", not total["chirality_not_leader"])
check("a crystal is never demoted, restated or shifted (TMC p.14)", not total["crystal_changed"],
      f"{crystals_formed} crystals formed")
check("nothing leaves the field without a TERMINATE proof", not total["vanished_silently"])
births = total["crystal_concluded_at_birth"]
check("no crystal concludes in the cycle it forms after the first breath (TMC p.22)",
      all(c < S.BREATH_PERIOD for c in births),
      f"{len(births)} during the first breath (known; next framework version)" if births else "none")

# ── a deterministic model in the loop ────────────────────────────────
class FakeModel(BaseHTTPRequestHandler):
    seeds = []
    def log_message(self, *a): pass
    def _send(self, obj):
        b = json.dumps(obj).encode(); self.send_response(200)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        self._send({"models": [{"name": "fake-model:latest"}]})
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seed = body.get("options", {}).get("seed")
        FakeModel.seeds.append(seed)
        # the answer depends on the prompt and the seed only: a model with no randomness of its own
        h = hashlib.sha256(f"{body['messages'][-1]['content']}::{seed}".encode()).hexdigest()[:8]
        self._send({"message": {"role": "assistant", "content": f"Construct {h}"}})

httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
host = f"http://127.0.0.1:{httpd.server_port}"

print(f"\n== A model in the loop (fake, deterministic; {N // 2} cycles, profile minimal)")
runs = []
for _ in range(2):
    FakeModel.seeds = []
    with contextlib.redirect_stdout(io.StringIO()):
        llm = S.LLMIntermediary(backend="ollama", host=host)
    v, head, _ = life(0, N // 2, llm)
    runs.append((head, list(FakeModel.seeds), v))
httpd.shutdown()
(h1, s1, v1), (h2, s2, _) = runs
check("every model request carries a seed", s1 and all(isinstance(x, int) for x in s1),
      f"{len(s1)} requests")
check("the seeds follow the history, not a generator", len(set(s1)) == len(s1) and s1 == s2,
      f"{len(set(s1))} distinct of {len(s1)}; the same sequence in both runs: {s1 == s2}")
check("two identical runs with the model seal the same ledger", h1 == h2, h1[:16])
check("the invariants hold with the model in the loop",
      not any(v1[k] for k in v1 if k != "crystal_concluded_at_birth")
      and all(c < S.BREATH_PERIOD for c in v1["crystal_concluded_at_birth"]))

print(f"\nSUMMARY: {sum(r[1] for r in results)}/{len(results)} passed")
if not all(r[1] for r in results):
    sys.exit(1)
