"""Real percepts (this machine), measured over a long life.
Usage: python3 live_c2.py [cycles] [backend: none|ollama|anthropic] [profile: standard|minimal]
Defaults: 3000 cycles, no model, standard profile.

Writes one JSON document to standard output (redirect it to a file):
- the Phase 3 criteria (sirisys_measures.LifeCriteria) and their verdict;
- the topology trace (field_topology), twice per breath;
- what the field perceived: counts per 1000 cycles, and the whole sequence,
  one string per cycle, events separated by ";", each "REL TARGET WEIGHT STATE";
- the Sombunal questions that entered the field, per 1000 cycles;
- with a model: the probe and the health of every call.
With a model the run stops (exit code 3) if the model does not answer before
it starts, or if its calls keep failing or coming back empty; the JSON is still
written, marked "aborted". Messages for the person running it go to the
terminal (standard error)."""
import sys, io, json, time, contextlib
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
with contextlib.redirect_stdout(io.StringIO()):
    from sirisys_loader import load_framework
    import field_topology  # read-only topology (pure Python, no networkx)
    from sirisys_measures import LifeCriteria, ModelHealth
    S = load_framework(Path(__file__).resolve().parent)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
BACKEND = sys.argv[2] if len(sys.argv) > 2 else "none"
PROFILE = sys.argv[3] if len(sys.argv) > 3 else "standard"
NARRATE, HOUR = (False, False) if PROFILE == "minimal" else (True, True)
S.set_ledger(S.ProofLedger(None))


def say(msg):
    print(msg, file=sys.stderr, flush=True)


out = {"cycles": N, "backend": BACKEND, "profile": PROFILE, "percepts": "live (psutil)"}
health = ModelHealth()
if BACKEND != "none":
    with contextlib.redirect_stdout(io.StringIO()):
        probe_llm = S.LLMIntermediary(backend=BACKEND)
    probe = ModelHealth.probe(probe_llm, cycles=N, calls_per_cycle=S.MAX_LLM_CALLS_PER_CYCLE)
    out["model_probe"] = probe
    if not probe["ok"]:
        out["aborted"] = f"model probe: {probe['reason']}"
        print(json.dumps(out, indent=1))
        say(f"\n  STOP: the model does not answer properly — {probe['reason']}.\n  Nothing was run.\n")
        sys.exit(3)
    say(f"  model ok · {probe['model']['name']} · {probe['call_s']} s per call · model time at most "
        f"~{probe['estimated_model_hours_max']} h for {N} cycles")

life, genealogy = LifeCriteria(S), field_topology.Genealogy()
zero_points = set(S.ZERO_POINTS.keys())
topo_trace, per_1000, questions, sequence = [], [], [], []
aborted = None
t0 = time.time()
# Output is discarded, not buffered, so memory measures the field alone.
class _Null:
    def write(self, s): return len(s)
    def flush(self): pass
with contextlib.redirect_stdout(_Null()):
    ss = S.new_session(S.LLMIntermediary(backend=BACKEND))
    if ss.llm.available:
        health.attach(ss.llm)
    for c in range(N):
        t_cycle, t_model = time.perf_counter(), health.model_seconds
        r = S.run_cycle(ss, c, narrate=NARRATE, include_hour=HOUR)
        life.after_cycle(ss, c, (time.perf_counter() - t_cycle) - (health.model_seconds - t_model))
        f = ss.field
        if c % 1000 == 0:
            per_1000.append(Counter()); questions.append(0)
        for e in r["percepts"]:
            per_1000[-1][e["tgt"]] += 1
        sequence.append(";".join(f"{e['rel']} {e['tgt']} {round(float(e['weight']), 4)} {e['state'].name}"
                                 for e in r["percepts"]))
        questions[-1] += bool(r["question"])
        # Read-only: genealogy every cycle, topology once per half-breath
        genealogy.update(ss.concordancy, c, f)
        if c % (S.BREATH_PERIOD // 2) == 0:
            topo_trace.append(field_topology.field_topology(
                f, cycle=c, zero_points=zero_points, genealogy=genealogy))
        if health.tripped:
            aborted = f"cycle {c}: {health.reason}"
            break

criteria = life.result()
cs = life.cs
out.update({
    "seconds": round(time.time() - t0),
    "aborted": aborted,
    "criteria_pass": LifeCriteria.verdict(criteria),
    "criteria": criteria,
    "durable_per_1000": criteria["durable_per_1000"],
    "flicker_share": criteria["flicker_share"],
    "constructs_first_last_1000": [round(sum(cs[:1000]) / max(1, len(cs[:1000])), 1),
                                   round(sum(cs[-1000:]) / max(1, len(cs[-1000:])), 1)],
    "tolerance": round(ss.field.tolerance, 2),
    "model": ss.llm.model, "model_active": ss.llm.available, "llm_calls": ss.llm.call_count,
    "model_health": health.report() if BACKEND != "none" else None,
    "sombunal_questions_per_1000": questions,
    "percepts_per_1000": [dict(sorted(p.items())) for p in per_1000],
    "topology_trace": topo_trace,
    "percept_sequence": sequence,
})
print(json.dumps(out, indent=1))
if aborted:
    say(f"\n  STOPPED — model health: {aborted}\n  The JSON is partial. Check Ollama and the model, then run again.\n")
    sys.exit(3)
