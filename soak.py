"""Soak: one long life on synthetic percepts, no model (memory, cost,
non-repetition, durable crystallization).
Usage: python3 soak.py [cycles] [stream] > soak_result.json"""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sirisys_loader import load_framework, quiet  # noqa: E402

S = load_framework(HERE)


def shape(field):
    """The field with every number in a name ignored: two cycles alike in shape match."""
    def norm(name):
        return re.sub(r"\d+", "#", name)
    edges = sorted((norm(e.src), e.rel, norm(e.tgt), e.state.value) for e in field.edges)
    constructs = sorted((norm(n), c.layer.value) for n, c in field.constructs.items())
    return hashlib.sha1(repr((edges, constructs)).encode()).hexdigest()[:12]


def main(cycles, stream):
    proc = psutil.Process()
    S.set_ledger(S.ProofLedger(None))
    born, durable, flicker, seen = {}, [], 0, 0
    # Aggregated on the fly: per-cycle lists would themselves grow by ~4 MB over
    # 40,000 cycles and contaminate the memory measurement.
    window, distinct, ms_blocks, size_blocks, rss, e3 = set(), [], [], [], {}, []
    t_acc, s_acc = 0.0, 0
    with quiet():
        ss = S.new_session(S.LLMIntermediary(backend="none"))
        for c in range(cycles):
            t = time.perf_counter()
            S.run_cycle(ss, c, percepts=S.synthetic_percepts(c, stream))
            t_acc += time.perf_counter() - t
            f = ss.field
            s_acc += len(f.constructs)
            window.add(shape(f))
            for n in f.apparents_since(seen):
                born[n] = c
            seen = f.apparents_total
            for n, b in list(born.items()):
                alive = n in f.constructs and f.constructs[n].layer == S.Layer.APPARENT
                if not alive:
                    flicker += (c - b) < S.BREATH_PERIOD
                    del born[n]
                elif c - b >= S.BREATH_PERIOD:
                    durable.append(b)
                    del born[n]
            if c % 100 == 99:
                if c >= 1000:
                    distinct.append(len(window))
                window = set()
            if c % 5000 == 4999:
                ms_blocks.append(t_acc / 5000)
                t_acc = 0.0
            if c % 10_000 == 9999:
                size_blocks.append(s_acc / 10_000)
                s_acc = 0
            if c % 500 == 499:
                energy = sorted(ss.concordancy._energy_map(f).values(), reverse=True)
                e3.append(sum(energy[:3]))
            if (c + 1) in (min(10_000, cycles), cycles):
                rss[c + 1] = proc.memory_info().rss
    if cycles % 5000:
        ms_blocks.append(t_acc / (cycles % 5000))
    if cycles % 10_000:
        size_blocks.append(s_acc / (cycles % 10_000))
    if not distinct:
        distinct = [len(window)]
    dw = [sum(1 for b in durable if a <= b < a + 1000) for a in range(0, cycles - S.BREATH_PERIOD, 1000)]
    half = len(e3) // 2
    return {
        "cycles": cycles, "stream": stream, "framework": S.__sirisys_file__,
        "A2_distinct_per_100_min": min(distinct),
        "A2_distinct_per_100_mean": round(sum(distinct) / len(distinct), 1),
        "C1_rss_MB_10k_to_end": [round(rss.get(10_000, 0) / 2**20, 1), round(rss[cycles] / 2**20, 1)],
        "C1_rss_growth": round(rss[cycles] / rss.get(10_000, rss[cycles]), 3),
        "C1_ms_first_last_5k": [round(1000 * ms_blocks[0], 2), round(1000 * ms_blocks[-1], 2)],
        "P3_durable_per_1000_min": min(dw), "P3_durable_per_1000_mean": round(sum(dw) / len(dw), 1),
        "P3_flicker_share": round(flicker / max(1, ss.field.apparents_total), 3),
        "constructs_mean_per_10k": [round(x, 1) for x in size_blocks],
        "P3_top3_energy_half_ratio": round((sum(e3[half:]) / (len(e3) - half)) / (sum(e3[:half]) / half), 3),
        "ledger_proofs": S.get_ledger().count, "clock": list(ss.clock.T),
    }


if __name__ == "__main__":
    print(json.dumps(main(int(sys.argv[1]) if len(sys.argv) > 1 else 50_000,
                          int(sys.argv[2]) if len(sys.argv) > 2 else 0), indent=1))
