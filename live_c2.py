"""Real percepts (this machine), measured over a long life.
Usage: python3 live_c2.py [cycles] [backend: none|ollama|anthropic] [profile: standard|minimal]
Defaults: 3000 cycles, no model, standard profile."""
import sys, io, json, time, contextlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
with contextlib.redirect_stdout(io.StringIO()):
    from sirisys_loader import load_framework
    import field_topology  # read-only topology (pure Python, no networkx)
    S = load_framework(Path(__file__).resolve().parent)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
BACKEND = sys.argv[2] if len(sys.argv) > 2 else "none"
PROFILE = sys.argv[3] if len(sys.argv) > 3 else "standard"
NARRATE, HOUR = (False, False) if PROFILE == "minimal" else (True, True)
S.set_ledger(S.ProofLedger(None))
born, durable, flicker, seen, sizes, topo_trace = {}, [], 0, 0, [], []
t0 = time.time()
# Output is discarded, not buffered, so memory measures the field alone.
class _Null:
    def write(self, s): return len(s)
    def flush(self): pass
with contextlib.redirect_stdout(_Null()):
    ss = S.new_session(S.LLMIntermediary(backend=BACKEND))
    for c in range(N):
        S.run_cycle(ss, c, narrate=NARRATE, include_hour=HOUR)
        f = ss.field; sizes.append(len(f.constructs))
        # Topology once per half-breath (read-only, no seal, no mutation)
        if c % (S.BREATH_PERIOD // 2) == 0:
            topo_trace.append(field_topology.field_topology(f, cycle=c, zero_points=set(S.ZERO_POINTS.keys())))
        for n in f.apparents_since(seen):
            born[n] = c
        seen = f.apparents_total
        for n, b in list(born.items()):
            alive = n in f.constructs and f.constructs[n].layer == S.Layer.APPARENT
            if not alive:
                flicker += (c - b) < S.BREATH_PERIOD; del born[n]
            elif c - b >= S.BREATH_PERIOD:
                durable.append(b); del born[n]
dw = [sum(1 for b in durable if a <= b < a + 1000) for a in range(0, N - S.BREATH_PERIOD, 1000)]
print(json.dumps({"cycles": N, "seconds": round(time.time() - t0), "durable_per_1000": dw,
                  "flicker_share": round(flicker / max(1, ss.field.apparents_total), 3),
                  "constructs_first_last_1000": [round(sum(sizes[:1000]) / 1000, 1), round(sum(sizes[-1000:]) / 1000, 1)],
                  "tolerance": round(ss.field.tolerance, 2), "percepts": "live (psutil)",
                  "backend": BACKEND, "model": ss.llm.model, "model_active": ss.llm.available,
                  "llm_calls": ss.llm.call_count, "profile": PROFILE,
                  "topology_trace": topo_trace}, indent=1))
