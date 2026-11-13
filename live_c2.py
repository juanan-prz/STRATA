"""Real percepts (this machine), measured over a long life.
Usage: python3 live_c2.py [cycles] [backend: none|ollama|anthropic] [profile: standard|minimal]
       python3 live_c2.py [cycles] [backend] [profile] --replay FILE
Defaults: 3000 cycles, no model, standard profile.

--replay FILE feeds the field, cycle by cycle, the percepts a previous live_c2.py
run recorded (its percept_sequence) instead of reading this machine: the same
real percepts, with or without a model. Replaying a run without a model, with
no model, seals the same ledger (ledger_head). Since v13.5 a model never reaches
the dynamics, so a run with the model, replayed without it, seals the same
ledger too: the replay says whether it did ("same ledger as the replayed run").

Writes one JSON document to standard output (redirect it to a file):
- the Phase 3 criteria (sirisys_measures.LifeCriteria) and their verdict;
- the topology trace (field_topology), twice per breath;
- what the field perceived: counts per 1000 cycles, and the whole sequence,
  one string per cycle, events separated by ";", each "REL TARGET WEIGHT STATE";
- the questions in which a model worded the Sombunal approach, per 1000 cycles;
- with a model, every label it gave (cycle, kind, the two constructs as it saw
  them, label, and its whole answer), and the key and label of each construct
  that crystallized;
- with a model: the probe and the health of every call;
- the framework file and its sha256[:16], the machine it ran on and when.
Without psutil it does not start (exit code 2): the machine cannot be perceived.
With a model the run stops (exit code 3) if the model does not answer before
it starts, or if its calls keep failing or coming back empty; the JSON is still
written, marked "aborted". Messages for the person running it go to the
terminal (standard error)."""
import sys, io, json, time, hashlib, contextlib
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
with contextlib.redirect_stdout(io.StringIO()):
    from sirisys_loader import load_framework
    import field_topology  # read-only topology (pure Python, no networkx)
    from sirisys_measures import LifeCriteria, ModelHealth, Translations, machine_record
    S = load_framework(Path(__file__).resolve().parent)
ARGS = sys.argv[1:]
REPLAY = None
if "--replay" in ARGS:
    i = ARGS.index("--replay")
    REPLAY, ARGS = Path(ARGS[i + 1]), ARGS[:i] + ARGS[i + 2:]
N = int(ARGS[0]) if len(ARGS) > 0 else 3000
BACKEND = ARGS[1] if len(ARGS) > 1 else "none"
PROFILE = ARGS[2] if len(ARGS) > 2 else "standard"
NARRATE, HOUR = (False, False) if PROFILE == "minimal" else (True, True)
S.set_ledger(S.ProofLedger(None))


def say(msg):
    print(msg, file=sys.stderr, flush=True)


def parse_percepts(line):
    """One cycle of a recorded percept_sequence back into the percepts the field received."""
    events = []
    for item in line.split(";") if line else []:
        rel, tgt, weight, state = item.split(" ")
        events.append({"src": "SYSTEM", "rel": rel, "tgt": tgt, "weight": float(weight),
                       "state": S.TetraState[state]})
    return events


framework = Path(__file__).resolve().parent / S.__sirisys_file__
recorded = None
if REPLAY:
    source = json.loads(REPLAY.read_text(encoding="utf-8"))
    recorded = [parse_percepts(line) for line in source["percept_sequence"]]
    N = min(N, len(recorded))
out = {"cycles": N, "backend": BACKEND, "profile": PROFILE,
       "percepts": f"replay of {REPLAY.name}" if REPLAY else "live (psutil)",
       "framework": S.__sirisys_file__,
       "framework_sha256_16": hashlib.sha256(framework.read_text(encoding="utf-8").encode()).hexdigest()[:16],
       "machine": machine_record(), "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
if REPLAY:
    out["replayed_from"] = {"file": REPLAY.name, "framework_sha256_16": source.get("framework_sha256_16"),
                            "backend": source.get("backend"), "machine": source.get("machine"),
                            "ledger_head": source.get("ledger_head")}
elif not S.real_percepts_available():
    out["aborted"] = "no psutil: the machine cannot be perceived"
    print(json.dumps(out, indent=1))
    say(f"\n  STOP: {S.NO_PERCEPTION}.\n  Nothing was run.\n")
    sys.exit(2)
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
translations, crystal_labels = Translations(), []   # every label a model gave; the crystals' [cycle, key, label]
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
        translations.attach(ss.llm)
    for c in range(N):
        t_cycle, t_model = time.perf_counter(), health.model_seconds
        translations.cycle = c
        apparents_before = ss.field.apparents_total
        r = S.run_cycle(ss, c, percepts=recorded[c] if recorded else None, narrate=NARRATE, include_hour=HOUR)
        life.after_cycle(ss, c, (time.perf_counter() - t_cycle) - (health.model_seconds - t_model))
        f = ss.field
        if c % 1000 == 0:
            per_1000.append(Counter()); questions.append(0)
        for e in r["percepts"]:
            per_1000[-1][e["tgt"]] += 1
        sequence.append(";".join(f"{e['rel']} {e['tgt']} {float(e['weight'])!r} {e['state'].name}"
                                 for e in r["percepts"]))
        questions[-1] += bool(r["question"])
        crystal_labels.extend([c, n, f.constructs[n].label] for n in f.apparents_since(apparents_before)
                              if n in f.constructs and f.constructs[n].label)
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
    "ledger_head": S.get_ledger().head,
    "model": ss.llm.model, "model_active": ss.llm.available, "llm_calls": ss.llm.call_count,
    "model_health": health.report() if BACKEND != "none" else None,
    "sombunal_questions_per_1000": questions,
    "labels": translations.entries,
    "crystal_labels": crystal_labels,
    "percepts_per_1000": [dict(sorted(p.items())) for p in per_1000],
    "topology_trace": topo_trace,
    "percept_sequence": sequence,
})
if REPLAY and out["replayed_from"].get("ledger_head") and not aborted and N == source.get("cycles"):
    out["same_ledger_as_replayed"] = out["ledger_head"] == out["replayed_from"]["ledger_head"]
print(json.dumps(out, indent=1))
if "same_ledger_as_replayed" in out:
    say(f"\n  same ledger as the replayed run: {'YES' if out['same_ledger_as_replayed'] else 'NO'}\n")
if aborted:
    say(f"\n  STOPPED — model health: {aborted}\n  The JSON is partial. Check Ollama and the model, then run again.\n")
    sys.exit(3)
