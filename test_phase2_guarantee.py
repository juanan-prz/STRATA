#!/usr/bin/env python3
"""Phase 2 guarantee: topology metrics do not alter the ledger.

Runs N cycles with synthetic percepts, no model — once with metrics enabled
(topology every half-breath, genealogy every cycle), once disabled — and
proves the ledger head is identical bit-for-bit.

Also checks the genealogical depth (percepts and anchors at depth 0, each
product one generation below its deeper parent) and verifies the proof
invariant every cycle.

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
    """Run `cycles` with synthetic percepts, no model.
    Return (ledger_head, field_dict, session, genealogy)."""
    import field_topology as ft
    m.set_ledger(m.ProofLedger(workdir / "l.jsonl"))
    genealogy = ft.Genealogy() if topo else None
    cwd = os.getcwd(); os.chdir(workdir)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            llm = m.LLMIntermediary(backend="none")
            ss = m.new_session(llm=llm)
            for c in range(cycles):
                percepts = m.synthetic_percepts(c, stream=0)
                m.run_cycle(ss, c, percepts=percepts, narrate=False, include_hour=True)
                # Read-only, as in run_report.py and live_c2.py: genealogy
                # every cycle, topology every half-breath
                if topo:
                    genealogy.update(ss.concordancy, c, ss.field)
                    if c % (m.BREATH_PERIOD // 2) == 0:
                        ft.field_topology(ss.field, cycle=c, zero_points=set(m.ZERO_POINTS.keys()),
                                          genealogy=genealogy)
        head = m.get_ledger().head
        field_d = ss.field.to_dict()
        m.get_ledger().close()
        return head, field_d, ss, genealogy
    finally:
        os.chdir(cwd)


# ── MAIN ──────────────────────────────────────────────────────────────
print(f"\n== Phase 2 guarantee: topology metrics immutability ({N} cycles)")

d_on  = Path(tempfile.mkdtemp())
d_off = Path(tempfile.mkdtemp())

m_on  = load_mod("topo_on")
m_off = load_mod("topo_off")

t0 = time.perf_counter()
head_on,  field_on,  ss_on, gen = run_cycles(m_on,  d_on,  N, topo=True)
head_off, field_off, _, _       = run_cycles(m_off, d_off, N, topo=False)
dt = time.perf_counter() - t0

check("ledger head identical with topology on/off",
      head_on == head_off,
      f"on={head_on[:16]}  off={head_off[:16]}  ({dt:.1f}s)")

# Field dict identical
check("field state identical with topology on/off",
      json.dumps(field_on, sort_keys=True, default=str) == json.dumps(field_off, sort_keys=True, default=str))

# ── Genealogical depth ────────────────────────────────────────────────
print("\n== Genealogical depth")
f_on = ss_on.field
roots = [n for n in f_on.constructs
         if n in m_on.ANCHORS or n.split("::")[0] in ("cpu", "mem", "time")]
check("percepts and anchors are at depth 0",
      roots and all(gen.depth.get(n, 0) == 0 for n in roots),
      f"{len(roots)} constructs")
# The latest cycle whose operations still have product and parents in the field
alive = [op for op in ss_on.concordancy.ops_log
         if op.get("z") and all(op.get(k) in f_on.constructs for k in ("x", "y", "z"))]
last_c = max((op["cycle"] for op in alive), default=-1)
bad, seen = [], 0
for op in alive:
    x, y, z = op["x"], op["y"], op["z"]
    if op["cycle"] != last_c:
        continue
    seen += 1
    if gen.depth.get(z) != 1 + max(gen.depth.get(x, 0), gen.depth.get(y, 0)):
        bad.append(z)
    # A concordancy product hangs from its operands by '::' edges (a conflict
    # hangs from I::AmNot instead): the operations log names the true parents.
    if op.get("state") != "CONFLICT":
        parents = {e.src for e in f_on.edges if e.tgt == z and e.rel == "::"}
        if not parents <= {x, y}:
            bad.append(z)
max_depth = max(gen.depth.values(), default=0)
check("each product is one generation below its deeper parent",
      seen and not bad and max_depth >= 2,
      f"{seen} product(s) of cycle {last_c} checked, deepest construct at {max_depth}")

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
