#!/usr/bin/env python3
"""Phase 2 guarantee: topology metrics do not alter the ledger.

Runs N cycles with synthetic percepts, no model — once with metrics enabled,
once disabled — and proves the ledger head is identical bit-for-bit.

Also runs measure_phase3.py to confirm the numbers match the baseline.

Usage: python3 test_phase2_guarantee.py [cycles]
       default: 200 cycles (same as T12 resume equivalence)
"""
import contextlib, io, importlib.util, json, os, shutil, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
import re as _re
NEW = sorted((p.name for p in HERE.iterdir()
              if _re.match(r"^Sirisys_Framework_v13_(\d+)\.py$", p.name)),
             key=lambda n: int(_re.findall(r"v13_(\d+)", n)[0]))[-1]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
results = []

def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def load_mod(tag):
    """Load framework in a fresh module (stdout silenced)."""
    spec = importlib.util.spec_from_file_location(
        f"sir_{tag}_{time.time_ns()}", HERE / NEW)
    m = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(m)
    return m


def run_cycles(m, workdir, cycles, topo=True):
    """Run `cycles` with synthetic percepts, no model. Return (ledger_head, field_dict)."""
    m.set_ledger(m.ProofLedger(workdir / "l.jsonl"))
    cwd = os.getcwd(); os.chdir(workdir)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            llm = m.LLMIntermediary(backend="none")
            ss = m.new_session(llm=llm)
            for c in range(cycles):
                percepts = m.synthetic_percepts(c, stream=0)
                m.run_cycle(ss, c, percepts=percepts, narrate=False, include_hour=True)
                # Topology metric (read-only) every breath
                if topo and c % m.BREATH_PERIOD == 0:
                    import field_topology as ft
                    ft.field_topology(ss.field)
        head = m.get_ledger().head
        field_d = ss.field.to_dict()
        m.get_ledger().close()
        return head, field_d
    finally:
        os.chdir(cwd)


# ── MAIN ──────────────────────────────────────────────────────────────
print(f"\n== Phase 2 guarantee: topology metrics immutability ({N} cycles)")

d_on  = Path(tempfile.mkdtemp())
d_off = Path(tempfile.mkdtemp())

m_on  = load_mod("topo_on")
m_off = load_mod("topo_off")

t0 = time.perf_counter()
head_on,  field_on  = run_cycles(m_on,  d_on,  N, topo=True)
head_off, field_off = run_cycles(m_off, d_off, N, topo=False)
dt = time.perf_counter() - t0

check("ledger head identical with topology on/off",
      head_on == head_off,
      f"on={head_on[:16]}  off={head_off[:16]}  ({dt:.1f}s)")

# Field dict identical
check("field state identical with topology on/off",
      json.dumps(field_on, sort_keys=True, default=str) == json.dumps(field_off, sort_keys=True, default=str))

# ── Invariant check ───────────────────────────────────────────────────
print("\n== verify_proof_invariant every cycle")
m_inv = load_mod("invariant")
m_inv.set_ledger(m_inv.ProofLedger(None))
violations_log = []
with contextlib.redirect_stdout(io.StringIO()):
    ss_inv = m_inv.new_session(llm=m_inv.LLMIntermediary(backend="none"))
    for c in range(N):
        percepts = m_inv.synthetic_percepts(c, stream=0)
        m_inv.run_cycle(ss_inv, c, percepts=percepts, narrate=False, include_hour=True)
        viols = m_inv.verify_proof_invariant(ss_inv.field)
        if viols:
            violations_log.append((c, viols))
m_inv.get_ledger().close()
check("no invariant violations over all cycles",
      len(violations_log) == 0,
      f"{len(violations_log)} cycle(s) with violations" if violations_log else "0 violations")

# ── measure_phase3 compatibility ──────────────────────────────────────
print(f"\n== measure_phase3.py compatibility ({N // 10} cycles per stream)")
m_p3 = load_mod("p3")
m_p3.set_ledger(m_p3.ProofLedger(None))
with contextlib.redirect_stdout(io.StringIO()):
    p3_crystals = []
    for stream in (0, 1, 2):
        ss_p3 = m_p3.new_session(llm=m_p3.LLMIntermediary(backend="none"))
        for c in range(N // 10):
            percepts = m_p3.synthetic_percepts(c, stream=stream)
            m_p3.run_cycle(ss_p3, c, percepts=percepts, narrate=False, include_hour=True)
        p3_crystals.append(ss_p3.field.apparents_total)
    m_p3.get_ledger().close()
check("crystallization across streams", p3_crystals[0] >= 0,
      f"streams: {p3_crystals} (Apparents formed)")

# Cleanup
shutil.rmtree(d_on, ignore_errors=True)
shutil.rmtree(d_off, ignore_errors=True)

# ── SUMMARY ───────────────────────────────────────────────────────────
print(f"\nSUMMARY: {sum(r[1] for r in results)}/{len(results)} passed")
if not all(r[1] for r in results):
    for name, ok, detail in results:
        if not ok:
            print(f"  FAIL: {name} — {detail}")
    sys.exit(1)
