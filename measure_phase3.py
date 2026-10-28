"""Acceptance measurements: 3 synthetic streams x N cycles, no model.
Criteria: durable crystals (life >= one breath) in every 1000-cycle window,
flicker <= 5 %, no growth trend, flat cost, bounded top-3 energy.
The criteria themselves live in sirisys_measures.LifeCriteria, shared with
run_report.py and live_c2.py.
Usage: python3 measure_phase3.py [cycles] [framework_file]"""
import sys, io, time, json, contextlib, importlib.util
from pathlib import Path
from sirisys_measures import LifeCriteria
N  = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
FW = sys.argv[2] if len(sys.argv) > 2 else sorted(Path(".").glob("Sirisys_Framework_v13_*.py"))[-1].name

def load(fname, tweak=None):
    spec = importlib.util.spec_from_file_location(f"m{time.time_ns()}", fname)
    m = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(m)
    if tweak: tweak(m)
    return m

def run(stream, tweak=None):
    S = load(FW, tweak); S.set_ledger(S.ProofLedger(None))
    life = LifeCriteria(S)
    with contextlib.redirect_stdout(io.StringIO()):
        ss = S.new_session(S.LLMIntermediary(backend="none"))
        for c in range(N):
            t = time.perf_counter()
            S.run_cycle(ss, c, percepts=S.synthetic_percepts(c, stream))
            life.after_cycle(ss, c, time.perf_counter() - t)
    return life.result()

verdict = LifeCriteria.verdict

if __name__ == "__main__":
    out = {f"stream {s}": run(s) for s in (0, 1, 2)}
    for k, r in out.items():
        print(f"{k}: {'PASS' if verdict(r) else 'FAIL'}  {r}")
    json.dump(out, open("phase3_measurements.json", "w"), indent=1)
