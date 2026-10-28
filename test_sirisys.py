"""Core: the proof ledger and the life of one instance.

Determinism without a PRNG, the cost of a cycle, time that never goes back, a
complete and tamper-evident record, resume, torn writes, a single writer,
conflict identity across reloads, bounded memory, flat cost, and a resumed
instance that equals an uninterrupted one.
No model and no network: the framework's own run(), with a fixed perception.
Usage: python3 test_sirisys.py        (the first life lasts STEPS=40 cycles)"""
import contextlib
import io
import itertools
import json
import os
import re
import statistics
import time

from sirisys_testkit import Checks, FRAMEWORK, fresh_framework, quiet, raises, read_jsonl, scratch

STEPS = int(os.environ.get("STEPS", "40"))
# The machine's own readings would make two lives incomparable: three fixed states, in turn
READINGS = [("latent", "nominal", 0.55, 0.60), ("synchronizing", "coherent", 0.62, 0.48),
            ("resonant", "oscillating", 0.71, 0.66)]
check = Checks()


def framework():
    """A fresh copy of the framework whose perception repeats READINGS."""
    m = fresh_framework()
    turn = itertools.count()

    def perceive(include_hour=True):
        cpu, mem, cpu_w, mem_w = READINGS[next(turn) % len(READINGS)]
        true = m.TetraState.TRUE
        return [{"src": "SYSTEM", "rel": "PERCEIVES", "tgt": f"cpu::{cpu}", "weight": cpu_w, "state": true},
                {"src": "SYSTEM", "rel": "PERCEIVES", "tgt": f"mem::{mem}", "weight": mem_w, "state": true},
                {"src": "SYSTEM", "rel": "PERCEIVES", "tgt": "time::meridian", "weight": 0.75, "state": true}]

    m.perceive_real = perceive
    return m


def live(m, folder, steps):
    """The framework's own run() in `folder`; returns (its result, seconds, what it printed)."""
    cwd, printed = os.getcwd(), io.StringIO()
    os.chdir(folder)
    try:
        start = time.perf_counter()
        with contextlib.redirect_stdout(printed):
            result = m.run(steps=steps)
        return result, time.perf_counter() - start, printed.getvalue()
    finally:
        os.chdir(cwd)


def proofs_in(x):
    """Every proof held anywhere in a snapshot."""
    if isinstance(x, dict) and {"witness", "relation", "anchor"} <= x.keys():
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from proofs_in(v)
    elif isinstance(x, list):
        for v in x:
            yield from proofs_in(v)


def field_json(field):
    return json.dumps(field.to_dict(), sort_keys=True, default=str)


check.section(f"1 · Determinism without a PRNG ({STEPS} cycles)")
source = FRAMEWORK.read_text(encoding="utf-8")
check("no PRNG in the framework",
      not re.search(r"^\s*(import|from)\s+(random|secrets)\b|\brandom\.\w+\(", source, re.M))
home, twin_home = scratch(), scratch()
m = framework()
(field, *_), seconds, _ = live(m, home, STEPS)
twin = framework()
(twin_field, *_), _, _ = live(twin, twin_home, STEPS)
twin.get_ledger().close()
check("same percepts → identical field (history-oriented choices)",
      field_json(field) == field_json(twin_field))

check.section("2 · Cost of a cycle")
ledger = home / m.LEDGER_FILE
records = read_jsonl(ledger)
size = ledger.stat().st_size
check("time per cycle within 100 ms (snapshot saved every cycle)", 1000 * seconds / STEPS <= 100,
      f"{1000 * seconds / STEPS:.1f} ms/cycle · ledger {size / 1024:.0f} KB "
      f"≈ {size / len(records):.0f} B/proof · {len(records) / STEPS:.0f} proofs/cycle")

check.section("3 · Time never goes back")
times = [tuple(r["time"]) for r in records]
back = next((i for i in range(1, len(times)) if times[i] < times[i - 1]), None)
check("ledger times non-decreasing (era, offset)", back is None,
      f"{len(records)} proofs" if back is None else
      f"first violation at {back}: {times[back - 1]}→{times[back]} ({records[back]['relation']})")

check.section("4 · Nothing trimmed is lost")
state = json.loads((home / m.STATE_FILE).read_text(encoding="utf-8"))
snapshot = list(proofs_in(state["field"]))
sealed = {r["chain_hash"] for r in records}
check("every snapshot proof is in the ledger", all(p["chain_hash"] in sealed for p in snapshot),
      f"snapshot holds {len(snapshot)}, ledger holds {len(records)} "
      f"({len(records) - len(snapshot)} only in ledger)")
check("snapshot ledger head == ledger file head",
      state["ledger"]["head"] == records[-1]["chain_hash"] and state["ledger"]["count"] == len(records))

check.section("5 · Tampering is detected")
v = m.verify_ledger(ledger)
check("untouched ledger verifies", v["ok"], f"{v['count']} links")
lines = ledger.read_text(encoding="utf-8").splitlines(True)
k = len(lines) // 2


def edited(rehash=False):
    """Line k with its content changed; with rehash, its own hash recomputed too."""
    rec = json.loads(lines[k])
    rec["object"] += "_x"
    if rehash:
        rec["chain_hash"] = m._chain(rec["prev_hash"], m._proof_payload(rec))
    return json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n"


def tampered(label, new_lines, expect_at, reason):
    """The damaged copy must fail at the right line, for the right reason."""
    copy = home / f"tamper_{label.replace(' ', '_')}.jsonl"
    copy.write_text("".join(new_lines), encoding="utf-8")
    r = m.verify_ledger(copy)
    check(f"{label} detected", not r["ok"] and r["error_at"] == expect_at and reason in (r["reason"] or ""),
          f"error_at={r['error_at']} reason={r['reason']}")


tampered("content edit", lines[:k] + [edited()] + lines[k + 1:], k, "content altered")
tampered("deletion", lines[:k] + lines[k + 1:], k, "sequence gap")
tampered("reorder", lines[:k] + [lines[k + 1], lines[k]] + lines[k + 2:], k, "sequence gap")
# The forger rehashes the edited line: that line verifies, the next link breaks
tampered("edit with rehash", lines[:k] + [edited(rehash=True)] + lines[k + 1:], k + 1, "broken link")

check.section("6 · Resume continues the same chain")
m.get_ledger().close()                                   # release the single-writer lock
resumed = framework()
_, _, printed = live(resumed, home, 10)
records_after = read_jsonl(ledger)
v = m.verify_ledger(ledger)
check("chain intact across restart", v["ok"] and len(records_after) > len(records),
      f"{len(records)} → {len(records_after)} proofs")
check("resume reports ledger position", f"{len(records)} proofs" in printed)

check.section("7 · Torn write recovery (power cut mid-line)")
resumed.get_ledger().close()
with open(ledger, "a", encoding="utf-8") as f:
    f.write('{"seq": 99999, "partial')
with quiet():                                            # it reports the recovery itself
    recovered = framework().ProofLedger(ledger)
recovered.close()
v = m.verify_ledger(ledger)
check("torn tail truncated, chain verifies", v["ok"] and v["count"] == len(records_after),
      f"{recovered.torn_bytes} bytes moved to .torn")
check(".torn sidecar preserves the bytes", ledger.with_name(ledger.name + ".torn").exists())
check("recovered head/count match",
      recovered.count == len(records_after) and recovered.head == records_after[-1]["chain_hash"])

check.section("8 · Single writer")
writer = m.ProofLedger(ledger)
check("second writer refused", raises(lambda: m.ProofLedger(ledger), RuntimeError, "fork"))
writer.close()
proof = m.ProofObject(id="x", subject="s", relation="R", object="o", witness="w",
                      anchor="Z0::IDENTITY", lagrange="L1", time=[0, 0])
check("sealing into a closed file ledger raises (no silent loss)",
      raises(lambda: writer.seal(proof), RuntimeError))

check.section("9 · Conflict identity survives reload, even with long chains")
m9 = framework()
probe = m9.Construct("probe", m9.Layer.UMBRA_0)
between = dict(subject="a", object="b", anchor="Z2::CONCORDANCY", lagrange=m9.LagrangianPoint.L2)
probe.add_proof(m9.ProofObject.make(id="g", relation="CONFLICT", T=(0, 1), tensate_role="TENSOUT", **between))
for i in range(80):                                      # pushes the founding proof out of the window
    probe.add_proof(m9.ProofObject.make(id=f"p{i}", relation="INTENSIFY", T=(0, 2 + i), **between))
reloaded = m9.Construct.from_dict(json.loads(json.dumps(probe.to_dict())))
check("founding CONFLICT proof outside window, identity kept",
      m9.is_conflict_construct(probe) and m9.is_conflict_construct(reloaded),
      f"in-memory chain {len(probe.proof_chain)} (window {m9.CHAIN_WINDOW}), "
      f"snapshot {len(reloaded.proof_chain)}, proofs_total {reloaded.proofs_total}")

check.section("10 · SHIFT records, bounded memory, flat compute cost (400 cycles)")
home10, m10 = scratch(), framework()
(field10, *_), _, _ = live(m10, home10, 400)
ledger10 = home10 / m10.LEDGER_FILE
shifts = sum(1 for r in read_jsonl(ledger10) if r["relation"] == "SHIFT")
check("Sombunal shifts are sealed in the ledger", shifts > 0, f"{shifts} SHIFT records")
longest = max(len(c.proof_chain) for c in field10.constructs.values())
check("working memory bounded",
      longest <= m10.CHAIN_WINDOW and len(field10.termination_log) <= m10.TERMINATION_WINDOW
      and len(field10.terminated_names) <= m10.TERMINATED_INDEX_WINDOW,
      f"max chain {longest}, termination_log {len(field10.termination_log)}, "
      f"index {len(field10.terminated_names)}")
check("400-cycle ledger verifies", m10.verify_ledger(ledger10)["ok"])
m10.get_ledger().close()
# The canonical cycle alone, without file I/O, compared on the cheapest tenth of each
# window: a cost that grows lifts every cycle, a busy machine (another program, the
# garbage collector) slows only some of them.
m10.set_ledger(m10.ProofLedger(None))
costs = []
with quiet():
    ss = m10.new_session(m10.LLMIntermediary(backend="none"))
    for c in range(900):
        start = time.perf_counter()
        m10.run_cycle(ss, c)
        costs.append(time.perf_counter() - start)
early, late = (statistics.quantiles(costs[a:b], n=10)[0] for a, b in ((300, 450), (750, 900)))
check("compute cost per cycle flat (late/early < 1.3)", late / early < 1.3,
      f"{1000 * early:.2f} → {1000 * late:.2f} ms/cycle (cheapest tenth)")

check.section("11 · A resumed instance equals an uninterrupted one")


def head_after(total, cut=None):
    """The ledger head after `total` cycles of stream 0, optionally saved and resumed at `cut`."""
    folder, m = scratch(), framework()
    m.set_ledger(m.ProofLedger(folder / "ledger.jsonl"))
    with quiet():
        ss = m.new_session(m.LLMIntermediary(backend="none"))
        for c in range(cut or total):
            m.run_cycle(ss, c, percepts=m.synthetic_percepts(c, 0))
        if cut:
            m.save_session_atomic(folder / "state.json", ss, cut)
            m.get_ledger().close()
            m = framework()
            m.set_ledger(m.ProofLedger(folder / "ledger.jsonl"))
            ss, next_cycle = m.resume_session(folder / "state.json", m.LLMIntermediary(backend="none"))
            for c in range(next_cycle, total):
                m.run_cycle(ss, c, percepts=m.synthetic_percepts(c, 0))
    head = m.get_ledger().head
    m.get_ledger().close()
    return head


straight, with_cut = head_after(200), head_after(200, cut=97)
check("same ledger head after 200 cycles, with or without a cut at cycle 97", straight == with_cut,
      straight[:16])

check.finish()
