"""Acceptance measurements: 3 synthetic streams x N cycles, no model.
Criteria: durable crystals (life >= one breath) in every 1000-cycle window,
flicker <= 5 %, no growth trend, flat cost, bounded top-3 energy.
Usage: python3 measure_phase3.py [cycles] [framework_file]"""
import sys, io, time, json, contextlib, importlib.util
from pathlib import Path
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
    ap, cs, ts, e3 = [], [], [], []
    born, durable, flicker, seen = {}, [], 0, 0
    with contextlib.redirect_stdout(io.StringIO()):
        ss = S.new_session(S.LLMIntermediary(backend="none"))
        for c in range(N):
            t = time.perf_counter()
            S.run_cycle(ss, c, percepts=S.synthetic_percepts(c, stream))
            ts.append(time.perf_counter() - t)
            f = ss.field
            ap.append(f.apparents_total); cs.append(len(f.constructs))
            for n in f.apparents_since(seen):
                born[n] = c
            seen = f.apparents_total
            for n, b in list(born.items()):
                alive = n in f.constructs and f.constructs[n].layer == S.Layer.APPARENT
                if not alive:
                    flicker += (c - b) < S.BREATH_PERIOD; del born[n]
                elif c - b >= S.BREATH_PERIOD:
                    durable.append(b); del born[n]
            if c % 100 == 99:
                E = ss.concordancy._energy_map(f)
                top = sorted(E.values(), reverse=True)
                e3.append(sum(top[:3]))
    w = [ap[min(a + 199, N - 1)] - ap[a - 1] for a in range(200, N, 200)]
    last, prev = sum(cs[-1000:]) / 1000, sum(cs[-2000:-1000]) / 1000
    dw = [sum(1 for b in durable if a <= b < a + 1000) for a in range(0, N - S.BREATH_PERIOD, 1000)]
    return {"durable_per_1000": dw, "flicker_share": round(flicker / max(1, f.apparents_total), 3),
            "zero_windows": w.count(0), "windows": len(w), "new_per_200": (min(w), round(sum(w) / len(w), 1), max(w)),
            "constructs_final": cs[-1], "constructs_trend": round(last / prev, 3),
            "ms_first_last": (round(1000 * sum(ts[:500]) / 500, 2), round(1000 * sum(ts[-500:]) / 500, 2)),
            # mean of the second half vs the first half of the samples (a two-point
            # ratio was too noisy: energy fluctuates 3–20 with no trend)
            "top3_energy_trend": round((sum(e3[len(e3) // 2:]) / (len(e3) - len(e3) // 2))
                                       / max(1e-9, sum(e3[:len(e3) // 2]) / (len(e3) // 2)), 3),
            "top3_energy_final": round(e3[-1], 1)}

def verdict(r):
    return (min(r["durable_per_1000"]) >= 1 and r["flicker_share"] <= 0.05
            and r["constructs_trend"] <= 1.2
            and r["ms_first_last"][1] <= 1.5 * r["ms_first_last"][0] + 0.5
            and r["top3_energy_trend"] <= 1.2)

if __name__ == "__main__":
    out = {f"stream {s}": run(s) for s in (0, 1, 2)}
    for k, r in out.items():
        print(f"{k}: {'PASS' if verdict(r) else 'FAIL'}  {r}")
    json.dump(out, open("phase3_measurements.json", "w"), indent=1)
