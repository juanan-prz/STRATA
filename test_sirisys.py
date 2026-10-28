"""Core tests: proof ledger, monotonic time, tamper detection, resume,
torn writes, single writer, determinism without a PRNG, bounded memory.
Put this file next to the newest Sirisys_Framework_v13_X.py.
Run: python3 test_sirisys.py   (STEPS=40 by default). No API key needed:
degraded model mode with deterministic perception."""
import importlib.util, io, os, sys, json, tempfile, shutil, statistics, time, contextlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
import re as _re
NEW = sorted((p.name for p in HERE.iterdir() if _re.match(r"^Sirisys_Framework_v13_(\d+)\.py$", p.name)),
             key=lambda n: int(_re.findall(r"v13_(\d+)", n)[0]))[-1]
STEPS = int(os.environ.get("STEPS", "40"))
results = []

def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

def load(modfile, tag):
    spec = importlib.util.spec_from_file_location(f"sir_{tag}_{time.time_ns()}", HERE / modfile)
    m = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(m)
    # Deterministic perception (psutil/hour would make runs incomparable)
    calls = {"n": 0}
    states = [("latent", "nominal", 0.55, 0.60), ("synchronizing", "coherent", 0.62, 0.48),
              ("resonant", "oscillating", 0.71, 0.66)]
    def perceive_stub(include_hour=True):
        cs, ms, cw, mw = states[calls["n"] % 3]; calls["n"] += 1
        T = m.TetraState.TRUE
        return [{"src": "SYSTEM", "rel": "PERCEIVES", "tgt": f"cpu::{cs}", "weight": cw, "state": T},
                {"src": "SYSTEM", "rel": "PERCEIVES", "tgt": f"mem::{ms}", "weight": mw, "state": T},
                {"src": "SYSTEM", "rel": "PERCEIVES", "tgt": "time::meridian", "weight": 0.75, "state": T}]
    m.perceive_real = perceive_stub
    return m

def run_in(m, workdir, steps):
    cwd = os.getcwd(); os.chdir(workdir)
    try:
        t0 = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            out = m.run(steps=steps)
        dt = time.perf_counter() - t0
        return out, dt, buf.getvalue()
    finally:
        os.chdir(cwd)

PROOF_VOLATILE = {"witness", "time", "meta", "seq", "prev_hash", "chain_hash"}
NEW_KEYS = {"conflict", "terminations_total", "terminated_names"}   # v13 additions; terminated_names is a bounded index by design
def is_proof(d): return isinstance(d, dict) and {"witness", "relation", "anchor"} <= d.keys()
def scrub(x):
    if is_proof(x): return {k: scrub(v) for k, v in x.items() if k not in PROOF_VOLATILE}
    if isinstance(x, dict): return {k: scrub(v) for k, v in x.items() if k not in NEW_KEYS}
    if isinstance(x, list): return [scrub(v) for v in x]
    return x
def proofs_in(x, acc):
    if is_proof(x): acc.append(x)
    elif isinstance(x, dict): [proofs_in(v, acc) for v in x.values()]
    elif isinstance(x, list): [proofs_in(v, acc) for v in x]
    return acc

print(f"\n== T1 · Determinism without a PRNG ({STEPS} cycles)")
d_old, d_new = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
m_new = load(NEW, "new")
src_new = (HERE / NEW).read_text(encoding="utf-8")
check("no PRNG in the framework", "import random" not in src_new and "random." not in src_new.replace("# ", ""))
(n_field, n_clock, *_), t_new, log_new = run_in(m_new, d_new, STEPS)
fn = n_field.to_dict()
m_rep = load(NEW, "rep")
(r_field, *_), _, _ = run_in(m_rep, d_old, STEPS)
h = lambda f: json.dumps(f.to_dict(), sort_keys=True, default=str)
check("same percepts → identical field (history-oriented choices)", h(n_field) == h(r_field))
m_rep.get_ledger().close()
print("\n== T2 · Monotonic time across the whole ledger")
ledger = d_new / "sirisys_v13_ledger.jsonl"
recs = [json.loads(l) for l in open(ledger, encoding="utf-8")]
times = [tuple(r["time"]) for r in recs]
bad = [i for i in range(1, len(times)) if times[i] < times[i-1]]
check("ledger times non-decreasing (era, offset)", not bad, f"{len(recs)} proofs" + (f", first violation at {bad[0]}: {times[bad[0]-1]}→{times[bad[0]]} ({recs[bad[0]]['relation']})" if bad else ""))
print("\n== T3 · Completeness: nothing trimmed is lost")
state = json.load(open(d_new / "sirisys_v13_state.json", encoding="utf-8"))
snap_proofs = proofs_in(state["field"], [])
ledger_hashes = {r["chain_hash"] for r in recs}
check("every snapshot proof is in the ledger", all(p["chain_hash"] in ledger_hashes for p in snap_proofs),
      f"snapshot holds {len(snap_proofs)}, ledger holds {len(recs)} ({len(recs)-len(snap_proofs)} only in ledger)")
check("snapshot ledger head == ledger file head", state["ledger"]["head"] == recs[-1]["chain_hash"] and state["ledger"]["count"] == len(recs))

print("\n== T4 · Tamper detection")
v = m_new.verify_ledger(ledger)
check("untouched ledger verifies", v["ok"], f"{v['count']} links")
lines = open(ledger, encoding="utf-8").read().splitlines(True)
k = len(lines) // 2
def verify_variant(mutated, label, expect_at):
    p = d_new / f"tamper_{label}.jsonl"; p.write_text("".join(mutated), encoding="utf-8")
    r = m_new.verify_ledger(p)
    check(f"{label} detected", (not r["ok"]) and r["error_at"] == expect_at, f"error_at={r['error_at']} reason={r['reason']}")
rec = json.loads(lines[k]); rec["object"] = rec["object"] + "_x"
verify_variant(lines[:k] + [json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n"] + lines[k+1:], "content edit", k)
verify_variant(lines[:k] + lines[k+1:], "deletion", k)
verify_variant(lines[:k] + [lines[k+1], lines[k]] + lines[k+2:], "reorder", k)
# Forgery attempt: edit a line AND recompute its own hash — the next link still breaks
rec = json.loads(lines[k]); rec["object"] += "_x"
rec["chain_hash"] = m_new._chain(rec["prev_hash"], m_new._proof_payload(rec))
verify_variant(lines[:k] + [json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n"] + lines[k+1:], "edit with rehash", k + 1)

print("\n== T5 · Resume continues the same chain")
m_new.get_ledger().close()   # release the single-writer lock
m_res = load(NEW, "resume")
_, _, log_res = run_in(m_res, d_new, 10)
v2 = m_new.verify_ledger(ledger)
recs2 = [json.loads(l) for l in open(ledger, encoding="utf-8")]
check("chain intact across restart", v2["ok"] and len(recs2) > len(recs), f"{len(recs)} → {len(recs2)} proofs")
check("resume reports ledger position", f"{len(recs)} proofs" in log_res)

print("\n== T6 · Torn write recovery (power cut mid-line)")
m_res.get_ledger().close()
with open(ledger, "a", encoding="utf-8") as f: f.write('{"seq": 99999, "partial')
m_torn = load(NEW, "torn")
L = m_torn.ProofLedger(ledger)
L.close()
v3 = m_new.verify_ledger(ledger)
check("torn tail truncated, chain verifies", v3["ok"] and v3["count"] == len(recs2), f"{L.torn_bytes} bytes moved to .torn")
check(".torn sidecar preserves the bytes", (d_new / "sirisys_v13_ledger.jsonl.torn").exists())
check("recovered head/count match", L.count == len(recs2) and L.head == recs2[-1]["chain_hash"])

print("\n== T8 · Single writer: a second ledger on the same file is refused")
A = m_new.ProofLedger(ledger)
try:
    m_new.ProofLedger(ledger); refused = False
except RuntimeError as ex:
    refused = "fork" in str(ex)
check("second writer refused", refused)
A.close()
try:
    A.seal(m_new.ProofObject(id="x", subject="s", relation="R", object="o", witness="w",
                             anchor="Z0::IDENTITY", lagrange="L1", time=[0, 0])); sealed_closed = True
except RuntimeError:
    sealed_closed = False
check("sealing into a closed file ledger raises (no silent loss)", not sealed_closed)

print("\n== T9 · Conflict identity survives reload even with long chains")
m9 = load(NEW, "t9")
c = m9.Construct("probe", m9.Layer.UMBRA_0)
c.add_proof(m9.ProofObject.make(id="g", subject="a", relation="CONFLICT", object="b", anchor="Z2::CONCORDANCY",
                                lagrange=m9.LagrangianPoint.L2, T=(0, 1), tensate_role="TENSOUT"))
for i in range(80):
    c.add_proof(m9.ProofObject.make(id=f"p{i}", subject="a", relation="INTENSIFY", object="b",
                                    anchor="Z2::CONCORDANCY", lagrange=m9.LagrangianPoint.L2, T=(0, 2 + i)))
c2 = m9.Construct.from_dict(json.loads(json.dumps(c.to_dict())))
check("founding CONFLICT proof outside window, identity kept", m9.is_conflict_construct(c) and m9.is_conflict_construct(c2),
      f"in-memory chain {len(c.proof_chain)} (window {m9.CHAIN_WINDOW}), snapshot {len(c2.proof_chain)}, proofs_total {c2.proofs_total}")

print("\n== T10 · SHIFT records, bounded memory, flat compute cost")
d10 = Path(tempfile.mkdtemp()); m10 = load(NEW, "t10")
(f10, *_), _, _ = run_in(m10, d10, 400)
shifts = sum(1 for l in open(d10 / "sirisys_v13_ledger.jsonl", encoding="utf-8") if '"relation": "SHIFT"' in l)
check("Sombunal shifts are sealed in the ledger", shifts > 0, f"{shifts} SHIFT records")
mx = max(len(c.proof_chain) for c in f10.constructs.values())
check("working memory bounded", mx <= m10.CHAIN_WINDOW and len(f10.termination_log) <= m10.TERMINATION_WINDOW
      and len(f10.terminated_names) <= m10.TERMINATED_INDEX_WINDOW,
      f"max chain {mx}, termination_log {len(f10.termination_log)}, index {len(f10.terminated_names)}")
check("400-cycle ledger verifies", m10.verify_ledger(d10 / "sirisys_v13_ledger.jsonl")["ok"])
m10.get_ledger().close()
# Compute cost per cycle, measured on the canonical cycle (I/O excluded:
# snapshot size is bounded and saturates once the windows fill).
if hasattr(m10, "run_cycle"):
    m10.set_ledger(m10.ProofLedger(None))
    with contextlib.redirect_stdout(io.StringIO()):
        ss = m10.new_session(m10.LLMIntermediary(backend="none")); ts = []
        for c in range(900):
            t = time.perf_counter(); m10.run_cycle(ss, c); ts.append(time.perf_counter() - t)
    # Medians: a cost that grows moves the median; a pause of the machine
    # (another program, the garbage collector) does not.
    early, late = statistics.median(ts[300:450]), statistics.median(ts[750:900])
    check("compute cost per cycle flat (late/early < 1.3)", late / early < 1.3,
          f"{1000*early:.2f} → {1000*late:.2f} ms/cycle (medians)")

print("\n== T12 · A resumed instance equals an uninterrupted one")
if hasattr(m_new, "synthetic_percepts"):
    def life(m, d, cut=None, total=200):
        m.set_ledger(m.ProofLedger(d / "l.jsonl"))
        with contextlib.redirect_stdout(io.StringIO()):
            ss = m.new_session(m.LLMIntermediary(backend="none"))
            for c in range(cut or total):
                m.run_cycle(ss, c, percepts=m.synthetic_percepts(c, 0))
            if cut:
                m.save_session_atomic(d / "state.json", ss, cut); m.get_ledger().close()
                m2 = load(NEW, "resume2"); m2.set_ledger(m2.ProofLedger(d / "l.jsonl"))
                ss, nxt = m2.resume_session(d / "state.json", m2.LLMIntermediary(backend="none"))
                for c in range(nxt, total):
                    m2.run_cycle(ss, c, percepts=m2.synthetic_percepts(c, 0))
                m = m2
        head = m.get_ledger().head; m.get_ledger().close()
        return head
    h1 = life(load(NEW, "uninterrupted"), Path(tempfile.mkdtemp()))
    h2 = life(load(NEW, "interrupted"), Path(tempfile.mkdtemp()), cut=97)
    check("same ledger head after 200 cycles, with or without a cut at cycle 97", h1 == h2, h1[:16])

print("\n== T7 · Cost")
size = ledger.stat().st_size
ms_cycle = 1000 * t_new / STEPS
check("time per cycle within 100 ms (snapshot saved every cycle)", ms_cycle <= 100,
      f"{ms_cycle:.1f} ms/cycle · ledger {size/1024:.0f} KB "
      f"≈ {size/len(recs2):.0f} B/proof · {len(recs)/STEPS:.0f} proofs/cycle")

shutil.rmtree(d_old, ignore_errors=True)
print(f"\nSUMMARY: {sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
