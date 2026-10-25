"""Soak: one long life on synthetic percepts, no model (memory, cost,
non-repetition, durable crystallization).
Usage: python3 soak.py [cycles] [stream] > soak_result.json"""
import sys, io, re, json, time, hashlib, contextlib
from pathlib import Path
import psutil
sys.path.insert(0, str(Path(__file__).resolve().parent))
with contextlib.redirect_stdout(io.StringIO()):
    from sirisys_loader import load_framework
    S = load_framework(Path(__file__).resolve().parent)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 50_000
STREAM = int(sys.argv[2]) if len(sys.argv) > 2 else 0
norm = lambda s: re.sub(r"\d+", "#", s)
proc = psutil.Process()
S.set_ledger(S.ProofLedger(None))
born, durable, flicker, seen = {}, [], 0, 0
# Aggregated on the fly: per-cycle lists would themselves grow by ~4 MB over
# 40,000 cycles and contaminate the memory measurement.
win_sigs, distinct, ts_blocks, size_blocks, rss, e3 = set(), [], [], [], {}, []
t_acc, s_acc = 0.0, 0
# Output is discarded, not buffered, so memory measures the field alone
# (the sanctuary discards its output the same way).
class _Null:
    def write(self, s): return len(s)
    def flush(self): pass
with contextlib.redirect_stdout(_Null()):
    ss = S.new_session(S.LLMIntermediary(backend="none"))
    for c in range(N):
        t = time.perf_counter()
        S.run_cycle(ss, c, percepts=S.synthetic_percepts(c, STREAM))
        t_acc += time.perf_counter() - t
        f = ss.field
        s_acc += len(f.constructs)
        win_sigs.add(hashlib.sha1(repr((sorted((norm(e.src), e.rel, norm(e.tgt), e.state.value) for e in f.edges),
                                       sorted((norm(n), x.layer.value) for n, x in f.constructs.items()))).encode()).hexdigest()[:12])
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
            if c >= 1000:
                distinct.append(len(win_sigs))
            win_sigs = set()
        if c % 5000 == 4999:
            ts_blocks.append(t_acc / 5000); t_acc = 0.0
        if c % 10_000 == 9999:
            size_blocks.append(s_acc / 10_000); s_acc = 0
        if c % 500 == 499:
            E = sorted(ss.concordancy._energy_map(f).values(), reverse=True); e3.append(sum(E[:3]))
        if (c + 1) in (min(10_000, N), N):
            rss[c + 1] = proc.memory_info().rss
if N % 5000:
    ts_blocks.append(t_acc / (N % 5000))
if N % 10_000:
    size_blocks.append(s_acc / (N % 10_000))
if not distinct:
    distinct = [len(win_sigs)]
dw = [sum(1 for b in durable if a <= b < a + 1000) for a in range(0, N - S.BREATH_PERIOD, 1000)]
half = len(e3) // 2
out = {
    "cycles": N, "stream": STREAM, "framework": S.__sirisys_file__,
    "A2_distinct_per_100_min": min(distinct), "A2_distinct_per_100_mean": round(sum(distinct) / len(distinct), 1),
    "C1_rss_MB_10k_to_end": [round(rss.get(10_000, 0) / 2**20, 1), round(rss[N] / 2**20, 1)],
    "C1_rss_growth": round(rss[N] / rss.get(10_000, rss[N]), 3),
    "C1_ms_first_last_5k": [round(1000 * ts_blocks[0], 2), round(1000 * ts_blocks[-1], 2)],
    "P3_durable_per_1000_min": min(dw), "P3_durable_per_1000_mean": round(sum(dw) / len(dw), 1),
    "P3_flicker_share": round(flicker / max(1, ss.field.apparents_total), 3),
    "constructs_mean_per_10k": [round(x, 1) for x in size_blocks],
    "P3_top3_energy_half_ratio": round((sum(e3[half:]) / (len(e3) - half)) / (sum(e3[:half]) / half), 3),
    "ledger_proofs": S.get_ledger().count, "clock": list(ss.clock.T),
}
print(json.dumps(out, indent=1))
