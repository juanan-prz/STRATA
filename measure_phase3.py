"""Acceptance measurements: 3 synthetic streams x N cycles, no model.
Criteria: durable crystals (life >= one breath) in every 1000-cycle window,
flicker <= 5 %, no growth trend, flat cost, bounded top-3 energy.
The criteria themselves live in sirisys_measures.LifeCriteria, shared with
run_report.py and live_c2.py.
Usage: python3 measure_phase3.py [cycles] [framework_file]
       (the newest framework in this folder unless a file is named)"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sirisys_loader import load_framework, quiet  # noqa: E402
from sirisys_measures import LifeCriteria  # noqa: E402


def run(stream, cycles):
    """The criteria of one life on synthetic stream `stream`, in a fresh copy of the framework."""
    S = load_framework(HERE)
    S.set_ledger(S.ProofLedger(None))
    life = LifeCriteria(S)
    with quiet():
        ss = S.new_session(S.LLMIntermediary(backend="none"))
        for c in range(cycles):
            t = time.perf_counter()
            S.run_cycle(ss, c, percepts=S.synthetic_percepts(c, stream))
            life.after_cycle(ss, c, time.perf_counter() - t)
    return life.result()


if __name__ == "__main__":
    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    if len(sys.argv) > 2:
        os.environ["SIRISYS_FRAMEWORK"] = sys.argv[2]           # the loader's pin
    out = {f"stream {s}": run(s, cycles) for s in (0, 1, 2)}
    for k, r in out.items():
        print(f"{k}: {'PASS' if LifeCriteria.verdict(r) else 'FAIL'}  {r}")
    with open(HERE / "phase3_measurements.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
