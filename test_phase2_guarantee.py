#!/usr/bin/env python3
"""Measuring never changes what is measured.

The same life twice: once with every observer the experiment tools use (the
topology every half-breath; the genealogy and the self-adjustment criteria
every cycle; with a model, the model-health watch), once with none. The ledger
head and the field must be identical, without a model and with one (a local,
deterministic fake). Also: the genealogical depth is right, and
verify_proof_invariant holds every cycle.
Usage: python3 test_phase2_guarantee.py [cycles]        (default 200)"""
import json
import sys

import field_topology
from sirisys_measures import LifeCriteria, ModelHealth
from sirisys_testkit import Checks, FakeModel, fresh_framework, quiet

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
check = Checks()


def life(cycles, observe, host=None):
    """`cycles` of synthetic stream 0 in a fresh copy of the framework, with every
    observer on or none; no model, or the one at `host`.
    Returns (framework, session, ledger head, genealogy)."""
    m = fresh_framework()
    m.set_ledger(m.ProofLedger(None))
    zero_points = frozenset(m.ZERO_POINTS)
    genealogy, criteria = (field_topology.Genealogy(), LifeCriteria(m)) if observe else (None, None)
    with quiet():
        llm = m.LLMIntermediary(backend="ollama", host=host) if host else m.LLMIntermediary(backend="none")
        if observe and host:
            ModelHealth().attach(llm)
        ss = m.new_session(llm=llm)
        for c in range(cycles):
            m.run_cycle(ss, c, percepts=m.synthetic_percepts(c, stream=0), narrate=False, include_hour=True)
            if observe:                       # as run_report.py and live_c2.py do
                criteria.after_cycle(ss, c, 0.0)
                genealogy.update(ss.concordancy, c, ss.field)
                if c % (m.BREATH_PERIOD // 2) == 0:
                    field_topology.field_topology(ss.field, cycle=c, zero_points=zero_points,
                                                  genealogy=genealogy)
    return m, ss, m.get_ledger().head, genealogy


def field_json(ss):
    return json.dumps(ss.field.to_dict(), sort_keys=True, default=str)


check.section(f"1 · Observers change nothing ({N} cycles)")
m, ss, head_on, genealogy = life(N, observe=True)
_, ss_off, head_off, _ = life(N, observe=False)
check("ledger head identical with topology on/off", head_on == head_off,
      f"on={head_on[:16]}  off={head_off[:16]}")
check("field state identical with topology on/off", field_json(ss) == field_json(ss_off))
with FakeModel("alike") as model:
    *_, model_on, _ = life(N // 2, observe=True, host=model.url)
    *_, model_off, _ = life(N // 2, observe=False, host=model.url)
check("with a model in the loop, every observer on: the same ledger head", model_on == model_off,
      f"on={model_on[:16]}  off={model_off[:16]}")

check.section("2 · Genealogical depth")
field = ss.field
roots = [n for n in field.constructs if n in m.ANCHORS or n.split("::")[0] in ("cpu", "mem", "time")]
check("percepts and anchors are at depth 0",
      roots and all(genealogy.depth.get(n, 0) == 0 for n in roots), f"{len(roots)} constructs")
# The latest cycle whose operations still have their product and both parents in the field
alive = [op for op in ss.concordancy.ops_log
         if op.get("z") and all(op.get(k) in field.constructs for k in ("x", "y", "z"))]
last = max((op["cycle"] for op in alive), default=-1)
checked, wrong = 0, []
for op in (op for op in alive if op["cycle"] == last):
    x, y, z = op["x"], op["y"], op["z"]
    checked += 1
    if genealogy.depth.get(z) != 1 + max(genealogy.depth.get(x, 0), genealogy.depth.get(y, 0)):
        wrong.append(z)
    # A concordancy product hangs from its operands by '::' edges (a conflict hangs
    # from I::AmNot instead): the operations log names the true parents.
    parents = {e.src for e in field.edges if e.tgt == z and e.rel == "::"}
    if op.get("state") != "CONFLICT" and not parents <= {x, y}:
        wrong.append(z)
deepest = max(genealogy.depth.values(), default=0)
check("each product is one generation below its deeper parent", checked and not wrong and deepest >= 2,
      f"{checked} product(s) of cycle {last} checked, deepest construct at {deepest}")

check.section("3 · The proof invariant, every cycle")
m = fresh_framework()
m.set_ledger(m.ProofLedger(None))
broken = []
with quiet():
    ss = m.new_session(llm=m.LLMIntermediary(backend="none"))
    for c in range(N):
        m.run_cycle(ss, c, percepts=m.synthetic_percepts(c, stream=0), narrate=False, include_hour=True)
        if m.verify_proof_invariant(ss.field):
            broken.append(c)
check("no invariant violations over all cycles", not broken,
      f"{len(broken)} cycle(s) with violations" if broken else "0 violations")

check.finish()
