"""Ontological invariants of the field, checked cycle by cycle.

The other suites guard the record (chain, cuts, tampering, continuity). This
one guards what the field must be, from the primary source:
  - Zero Points are never operands: they are the Universal apparents (TMC p.22).
  - The older operand leads and the product inherits its handedness
    (Law 6, TMC p.35; first chirality dyad, p.50).
  - An Apparent is incontrovertible: while it exists it is never demoted, its
    crystal state never changes and its identity never shifts (TMC p.14).
  - A crystal holds at most the tension of its own commitment, whenever it
    banked it: once collapsed it is no "free modulator" (Understanding_TMC p.81).
  - Half to Each (TMC pp.110, 114): a BOTH channel that closes exchanges one
    [Ꮠ], one [Ꮙ] to each end (TMC pp.24, 26), whatever its weight and age.
  - The escapement (TMC p.24): each BOTH channel beats on its own. A channel
    that closes re-arms wherever it stands, and a sibling still in BOTH keeps
    the exchange it has accumulated (TMC p.59: no leftovers).
  - The Halo toward the Apparent (TMC pp.47, 55): what dissolves of a
    crystal's exchanges presses on its support from all sides and repairs it,
    never past its strength at birth (TMC p.14).
  - Nothing vanishes silently: every construct that leaves the field leaves a
    TERMINATE proof (Compiler Guide pp.203-204).
  - The Stop Chasm and the Adsurdic threshold (TMC p.41): never more than
    MAX_CONFLICTS_PER_CYCLE conflicts in a cycle, and conflict recursion never
    deeper than MAX_CF_DEPTH.
  - The anchors (Zero Points, I::Am, I::AmNot, SYSTEM) never conclude.
  - The field's own tolerance stays between its floor and 1.
  - "all [Apparents] must be [Existents]" (TMC p.22): no crystal concludes in
    the cycle it forms, and none is admitted with a support that would not
    hold one breath later (TMC pp.14, 45). "The non-existent [00] ... cannot
    be an apparent" (TMC p.22): a unit crystallizes only in an existent state,
    TRUE or BOTH, never NEITHER.
  - The exchange makes existent (TMC p.25): a BOTH channel that completes its
    exchange at the quantum stays TRUE.
  - [::] from the key (TMC pp.16, 102): on the pair (is, is-not) every product
    is the join, is OR and is-not OR; NEITHER × NEITHER stays the reversion.
  - The unreal meets the unreal (TMC p.44): units in NEITHER are routed only
    against each other, and their encounter is the conflict. A conflict in
    NEITHER is unreal too: it meets the unreal, and their encounter is a deeper
    conflict (TMC p.41), never a pairing with an existent unit.
  - No randomness with a model in the loop (TMC p.42): every request carries a
    seed oriented by the history, and two identical runs seal the same ledger.
Every life runs the minimal profile. The model is a local, deterministic fake.
Usage: python3 test_ontology.py [cycles per stream]        (default 400)"""
import json
import sys

from sirisys_loader import load_framework
from sirisys_testkit import Checks, FakeModel, quiet

with quiet():
    S = load_framework()
N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
CO = S.ConcordancyOperator
INVARIANTS = ("zp_operand", "leader_not_older", "chirality_not_leader", "crystal_changed",
              "crystal_over_cap", "vanished_silently", "stop_chasm", "adsurdic", "anchor_concluded",
              "tolerance_out", "crystal_concluded_at_birth")
check = Checks()


def crystals_of(field):
    return {n: (c.crystal_state, c.version) for n, c in field.constructs.items()
            if c.layer == S.Layer.APPARENT}


def broken_in(ss, cycle, present, crystals, terminations_before):
    """The invariants broken in `cycle`, once per offending construct or operation,
    given the field as it stood before the cycle."""
    f = ss.field
    k = f.terminations_total - terminations_before
    ended = {t.meta["name"]: t for t in (f.termination_log[-k:] if k else [])}
    for name, t in ended.items():
        if t.meta["final_layer"] == "APPARENT" and name not in crystals:
            yield "crystal_concluded_at_birth"
    for name, (state, version) in crystals.items():
        c = f.constructs.get(name)
        if c is not None and (c.layer != S.Layer.APPARENT or c.crystal_state != state
                              or c.version != version):
            yield "crystal_changed"
    for c in f.constructs.values():
        if c.layer == S.Layer.APPARENT and c.recursion_exchanged > S.THRESHOLD_APPARENT + 1e-12:
            yield "crystal_over_cap"
    for name in present - set(f.constructs):
        if name not in ended:
            yield "vanished_silently"
    ops = [op for op in ss.concordancy.ops_log if op["cycle"] == cycle]
    conflicts = [op for op in ops if op.get("state") == "CONFLICT"]
    if len(conflicts) > CO.MAX_CONFLICTS_PER_CYCLE:
        yield "stop_chasm"
    if (any(op.get("depth", 0) > CO.MAX_CF_DEPTH for op in conflicts)
            or any(e.concordancy_depth > CO.MAX_CF_DEPTH for e in f.edges)):
        yield "adsurdic"
    if any(a not in f.constructs for a in S.ANCHORS):
        yield "anchor_concluded"
    if not S.TOLERANCE_FLOOR <= f.tolerance <= 1.0:
        yield "tolerance_out"
    for op in ops:
        x, y, z = op["x"], op["y"], op["z"]
        if x in S.ZERO_POINTS or y in S.ZERO_POINTS:
            yield "zp_operand"
        cx, cy, cz = f.constructs.get(x), f.constructs.get(y), f.constructs.get(z)
        if cx and cy:
            if (tuple(cx.born_at), x) > (tuple(cy.born_at), y):
                yield "leader_not_older"
            if cz and op.get("state") != "CONFLICT" and cz.chirality != cx.chirality:
                yield "chirality_not_leader"


def life(stream, cycles, llm):
    """One life on synthetic stream `stream`. Returns the cycles at which each
    invariant was broken, the ledger head and the number of crystals formed."""
    S.set_ledger(S.ProofLedger(None))
    broken = {name: [] for name in INVARIANTS}
    with quiet():
        ss = S.new_session(llm)
        f = ss.field
        for c in range(cycles):
            before = set(f.constructs), crystals_of(f), f.terminations_total
            S.run_cycle(ss, c, percepts=S.synthetic_percepts(c, stream, False),
                        narrate=False, include_hour=False)
            for name in broken_in(ss, c, *before):
                broken[name].append(c)
    return broken, S.get_ledger().head, f.apparents_total


check.section(f"1 · Field invariants (3 streams × {N} cycles, no model)")
broken, formed = {name: [] for name in INVARIANTS}, 0
for stream in (0, 1, 2):
    with quiet():
        llm = S.LLMIntermediary(backend="none")
    b, _, crystals = life(stream, N, llm)
    formed += crystals
    for name, cycles in b.items():
        broken[name] += cycles
check("Zero Points are never operands (TMC p.22)", not broken["zp_operand"])
check("the older operand leads (Law 6, TMC p.35)", not broken["leader_not_older"])
check("the product inherits the leader's handedness (TMC p.50)", not broken["chirality_not_leader"])
check("a crystal is never demoted, restated or shifted (TMC p.14)", not broken["crystal_changed"],
      f"{formed} crystals formed")
with quiet():
    S.set_ledger(S.ProofLedger(None))
    probe = S.new_session(S.LLMIntermediary(backend="none"))
probe.field.add_construct("CAP::banked", S.Layer.UNIT_1)
probe.field.constructs["CAP::banked"].recursion_exchanged = 2 * S.TetralemmaEngine.EXCHANGE_QUANTUM
probe.field.lock_apparent("CAP::banked")
check("a crystal holds at most the tension of its own commitment, also what it banked before committing "
      "(Understanding_TMC p.81): locked with twice the quantum banked it keeps THRESHOLD_APPARENT, and no "
      "crystal ever holds more", probe.field.constructs["CAP::banked"].recursion_exchanged == S.THRESHOLD_APPARENT
      and not broken["crystal_over_cap"], f"{len(broken['crystal_over_cap'])} crystal-cycles over the cap")
# Half to Each (TMC pp.110, 114): a closing BOTH channel exchanges one [Ꮠ], one [Ꮙ] to each end (TMC pp.24, 26),
# whatever its weight and its age; an anchor banks nothing and a crystal holds at most its commitment
with quiet():
    S.set_ledger(S.ProofLedger(None))
    h2e = S.new_session(S.LLMIntermediary(backend="none"))
q, quo = S.TetralemmaEngine.EXCHANGE_QUANTUM, S.TetralemmaEngine.QUO
for name in ("H2E::a", "H2E::b", "H2E::c"):
    h2e.field.add_construct(name, S.Layer.UNIT_1)
h2e.field.add_construct("H2E::crystal", S.Layer.UNIT_1)
h2e.field.lock_apparent("H2E::crystal")
h2e.field.constructs["H2E::crystal"].recursion_exchanged = S.THRESHOLD_APPARENT - quo / 2
closing = []
for src, tgt, w in (("H2E::a", "H2E::b", 0.6), ("I::Am", "H2E::c", 0.9), ("H2E::a", "H2E::crystal", 0.75)):
    e = h2e.field.add_edge(src, "::", tgt, weight=w, state=S.TetraState.BOTH)
    e.both_age = -(-q // w) - 1                         # the next scan brings it to the quantum
    closing.append(e)
ends = ("H2E::a", "H2E::b", "H2E::c", "H2E::crystal", "I::Am")
held = {n: h2e.field.constructs[n].recursion_exchanged for n in ends}
with quiet():
    S.TetralemmaEngine().scan(h2e.field)
gain = {n: round(h2e.field.constructs[n].recursion_exchanged - held[n], 9) for n in ends}
check("Half to Each: a BOTH channel that reaches the quantum gives each end one [Ꮙ], whatever it weighed and "
      "however long it stood (the end of two closing channels gets two); an anchor banks nothing; a crystal "
      "fills up to its commitment, no more; the channel's exchange starts afresh",
      gain["H2E::b"] == quo and gain["H2E::c"] == quo and gain["H2E::a"] == 2 * quo and gain["I::Am"] == 0
      and h2e.field.constructs["H2E::crystal"].recursion_exchanged == S.THRESHOLD_APPARENT
      and all(e.both_age == 0 for e in closing),
      f"[Ꮙ] = {quo}, gains {gain}")
# The escapement (TMC p.24): each BOTH channel beats on its own. Three channels from one source: when the
# oldest closes, the younger ones keep their age; when the youngest closes, it re-arms although the older
# ones are still in BOTH
with quiet():
    S.set_ledger(S.ProofLedger(None))
    esc = S.new_session(S.LLMIntermediary(backend="none"))
ef, eng = esc.field, S.TetralemmaEngine()
ef.add_construct("ESC::src", S.Layer.UNIT_1)
chan = {}
for tgt, w in (("ESC::a", 0.9), ("ESC::b", 0.8), ("ESC::c", 0.7)):
    ef.add_construct(tgt, S.Layer.UNIT_1)
    chan[tgt] = ef.add_edge("ESC::src", "::", tgt, weight=w, state=S.TetraState.BOTH)
chan["ESC::a"].both_age = -(-q // 0.9) - 1                 # the next scan brings the oldest to the quantum
chan["ESC::b"].both_age, chan["ESC::c"].both_age = 5, 7
with quiet():
    eng.scan(ef)
first = {t: (e.state.name, e.both_age) for t, e in chan.items()}
chan["ESC::c"].both_age = -(-q // 0.7) - 1                 # now the youngest reaches the quantum
with quiet():
    eng.scan(ef)
second = {t: (e.state.name, e.both_age) for t, e in chan.items()}
check("the escapement (TMC p.24): a channel that closes re-arms and starts afresh, wherever it stands; its "
      "siblings in BOTH keep the exchange they carry (TMC p.59)",
      first == {"ESC::a": ("BOTH", 0), "ESC::b": ("BOTH", 6), "ESC::c": ("BOTH", 8)}
      and second == {"ESC::a": ("BOTH", 1), "ESC::b": ("BOTH", 7), "ESC::c": ("BOTH", 0)},
      f"oldest closes: {first}; youngest closes: {second}")
# The admission over one breath (TMC pp.14, 22, 45): a support that holds now but not one breath later
# does not admit a crystal; one that holds a breath later does
with quiet():
    S.set_ledger(S.ProofLedger(None))
    adm = S.new_session(S.LLMIntermediary(backend="none"))
af = adm.field
edge_of = {}
for name, w in (("ADM::edge", 0.105), ("ADM::held", 0.12)):
    af.add_construct(name, S.Layer.UNIT_1)
    edge_of[name] = af.add_edge(f"{name}::source", "::", name, weight=w)
    af.constructs[name].recursion_exchanged = 5.0
for _ in range(8):
    af.clock.tick()
with quiet():
    S.CussiveCollapseEngine().collapse(af, af.clock)
check("the admission over one breath: a support that holds now but not one breath later (TMC p.45) admits no "
      "crystal; one that still holds then does (TMC pp.14, 22)",
      af.edge_holds(edge_of["ADM::edge"], into_crystal=True)
      and not af.edge_holds(edge_of["ADM::edge"], into_crystal=True, ahead=1)
      and af.constructs["ADM::edge"].layer == S.Layer.UNIT_1
      and af.constructs["ADM::held"].layer == S.Layer.APPARENT,
      f"weight 0.105: {af.constructs['ADM::edge'].layer.name}; weight 0.12: {af.constructs['ADM::held'].layer.name}")
# The exchange makes existent (TMC p.25): a BOTH channel with no diverging sibling that reaches the quantum
# closes TRUE and starts afresh
with quiet():
    S.set_ledger(S.ProofLedger(None))
    ex = S.new_session(S.LLMIntermediary(backend="none"))
xf = ex.field
xf.add_construct("EX::src", S.Layer.UNIT_1)
xf.add_construct("EX::tgt", S.Layer.UNIT_1)
lone = xf.add_edge("EX::src", "::", "EX::tgt", weight=0.8, state=S.TetraState.BOTH)
lone.both_age = -(-q // 0.8) - 1                           # the next scan brings it to the quantum
with quiet():
    S.TetralemmaEngine().scan(xf)
check("the exchange makes existent (TMC p.25): a BOTH channel that completes its exchange at the quantum "
      "stays TRUE, not NEITHER, and starts afresh",
      lone.state == S.TetraState.TRUE and lone.both_age == 0
      and xf.constructs["EX::tgt"].recursion_exchanged == S.TetralemmaEngine.QUO,
      f"{lone.state.name}, age {lone.both_age}, banked {xf.constructs['EX::tgt'].recursion_exchanged}")
# Only the existent crystallizes (TMC p.22): three units with tension and support enough to crystallize,
# whose states are TRUE, BOTH and NEITHER; the NEITHER one stays a unit
with quiet():
    S.set_ledger(S.ProofLedger(None))
    ext = S.new_session(S.LLMIntermediary(backend="none"))
tf = ext.field
for name, state in (("EXI::true", S.TetraState.TRUE), ("EXI::both", S.TetraState.BOTH),
                    ("EXI::neither", S.TetraState.NEITHER)):
    tf.add_construct(name, S.Layer.UNIT_1)
    tf.add_edge(f"{name}::source", "::", name, weight=0.6, state=state)
    tf.constructs[name].recursion_exchanged = 5.0
for _ in range(8):
    tf.clock.tick()
with quiet():
    S.CussiveCollapseEngine().collapse(tf, tf.clock)
layers = {n: tf.constructs[n].layer.name for n in ("EXI::true", "EXI::both", "EXI::neither")}
check("only the existent crystallizes (TMC p.22): units in TRUE and BOTH become Apparent; one in NEITHER, "
      "the [00], stays a unit with the same tension and support",
      layers == {"EXI::true": "APPARENT", "EXI::both": "APPARENT", "EXI::neither": "UNIT_1"}
      and tf.constructs["EXI::both"].crystal_state == S.TetraState.BOTH,
      f"{layers}")
# [::] from the key (TMC pp.16, 102): the matrix is the join on the pair (is, is-not), with the encoding
# written here independently of the framework; NEITHER x NEITHER stays outside it, as the reversion
T_, F_, B_, N_ = S.TetraState.TRUE, S.TetraState.FALSE, S.TetraState.BOTH, S.TetraState.NEITHER
enc = {T_: (1, 0), F_: (0, 1), B_: (1, 1), N_: (0, 0)}
dec = {v: k for k, v in enc.items()}
want = {(x, y): None if x == y == N_ else dec[(enc[x][0] | enc[y][0], enc[x][1] | enc[y][1])]
        for x in S.TetraState for y in S.TetraState}
earlier = {(T_, T_): T_, (T_, B_): B_, (B_, T_): B_, (B_, B_): B_, (T_, F_): B_, (F_, T_): B_}
check("[::] from the key (TMC pp.16, 102): every product is the join of its operands' (is, is-not), "
      "NEITHER x NEITHER stays the reversion, and the cells with TRUE or BOTH operands are as before",
      dict(CO.COMPATIBLE) == want and all(CO.COMPATIBLE[k] == v for k, v in earlier.items()),
      f"{sum(CO.COMPATIBLE.get(k) == v for k, v in want.items())}/16 cells")
# The unreal meets the unreal (TMC p.44): units in NEITHER and one in TRUE; the NEITHER units are routed
# against each other and give the conflict, and none of them is ever paired with an existent unit
with quiet():
    S.set_ledger(S.ProofLedger(None))
    ur = S.new_session(S.LLMIntermediary(backend="none"))
uf = ur.field
for name, state in (("UR::a", N_), ("UR::b", N_), ("UR::t", T_)):
    uf.add_construct(name, S.Layer.UNIT_1)
    uf.add_edge(f"{name}::source", "::", name, weight=0.6, state=state)
unreal = {n for n, c in uf.constructs.items() if c.layer != S.Layer.APPARENT and n not in S.ANCHORS
          and uf.dominant_state(n) == N_}
with quiet():
    ur.concordancy.scan_and_apply(uf, 0, {"used": 0})
ops = [op for op in ur.concordancy._ops_log if op.get("cycle") == 0]
met = [op for op in ops if op["x"] in unreal and op["y"] in unreal]
mixed = [op for op in ops if (op["x"] in unreal) != (op["y"] in unreal)]
cap = CO.MAX_CONFLICTS_PER_CYCLE
expected = ["CONFLICT"] * min(len(met), cap) + ["NEITHER"] * max(0, len(met) - cap)
check("the unreal meets the unreal (TMC p.44): units in NEITHER are routed against each other and give the "
      "conflict, past the Stop Chasm the fourth corner (TMC pp.17, 41); none is paired with an existent unit",
      "UR::a" in unreal and "UR::t" not in unreal and len(met) > cap
      and [op["state"] for op in met] == expected
      and not mixed and ur.concordancy.pool_telemetry[-1].get("unreal_pool_size") == len(unreal),
      f"{len(unreal)} unreal units, met {[op['state'] for op in met]}, {len(mixed)} mixed")
# A conflict is unreal too (TMC pp.44, 22, 41): a conflict in NEITHER, below the conflict pool's energy,
# meets an unreal unit and gives a deeper conflict; it is never paired with an existent unit
with quiet():
    S.set_ledger(S.ProofLedger(None))
    uc = S.new_session(S.LLMIntermediary(backend="none"))
cf_field = uc.field
cf_field.add_construct("CF::x", S.Layer.UMBRA_0)
cf_field.constructs["CF::x"].conflict = True
cf_field.add_edge("I::AmNot", "::", "CF::x", weight=0.6, state=N_, concordancy_depth=2)
for name, state in (("UC::n", N_), ("UC::t", T_)):
    cf_field.add_construct(name, S.Layer.UNIT_1)
    cf_field.add_edge(f"{name}::source", "::", name, weight=0.6, state=state)
cf_unreal = {n for n, c in cf_field.constructs.items() if c.layer != S.Layer.APPARENT and n not in S.ANCHORS
             and not n.startswith("SOMBUNAL::") and cf_field.dominant_state(n) == N_}
with quiet():
    uc.concordancy.scan_and_apply(cf_field, 0, {"used": 0})
cf_ops = [op for op in uc.concordancy._ops_log if op.get("cycle") == 0 and "CF::x" in (op["x"], op["y"])]
cf_met = [op for op in cf_ops if {op["x"], op["y"]} <= cf_unreal]
cf_mixed = [op for op in cf_ops if not {op["x"], op["y"]} <= cf_unreal]
check("a conflict is unreal too (TMC pp.44, 22): a conflict in NEITHER meets an unreal unit and gives a "
      "deeper conflict (TMC p.41); it is never paired with an existent unit",
      "CF::x" in cf_unreal and "UC::t" not in cf_unreal
      and cf_field.constructs["CF::x"].umbragiac_score < CO.CF_MIN_ENERGY
      and any(op["state"] == "CONFLICT" and op["depth"] == 3 for op in cf_met) and not cf_mixed,
      f"{len(cf_met)} encounters {[(op['state'], op.get('depth')) for op in cf_met]}, {len(cf_mixed)} mixed")
# The Halo toward the Apparent (TMC pp.47, 55): what dissolves of a crystal's exchanges presses on its
# support from all sides and repairs it, never past its strength at birth (TMC p.14); what no construct can
# hold goes to the null, accounted (TMC pp.45, 59)
with quiet():
    S.set_ledger(S.ProofLedger(None))
    hal = S.new_session(S.LLMIntermediary(backend="none"))
hf, lam = hal.field, S.InternalClock.DECAY
hf.add_construct("HALO::crystal", S.Layer.UNIT_1)
hf.lock_apparent("HALO::crystal")
hf.add_construct("HALO::open", S.Layer.UNIT_1)
aging = hf.add_edge("HALO::a", "::", "HALO::crystal", weight=0.6)
held_both = hf.add_edge("HALO::b", "::", "HALO::crystal", weight=0.5, state=S.TetraState.BOTH)
from_crystal = hf.add_edge("HALO::crystal", "::", "HALO::x", weight=0.8)
from_open = hf.add_edge("HALO::open", "::", "HALO::y", weight=0.8)
hf.breaths, born = aging.born_breath + 10, aging.born_breath


def strength(e):
    return e.weight * S.np.exp(-lam * (hf.breaths - e.born_breath - e.repaired))


before, banked = strength(aging), hf.constructs["HALO::open"].recursion_exchanged
hf._back_up_halo([from_crystal, from_open])
after = strength(aging)
share = S.HALO_FRACTION * from_crystal.weight / 2       # two sides: the aging support and the BOTH one
hf._press_toward_center("HALO::crystal", 10.0)          # far more than any support can take
from_anchor = hf.add_edge("I::Am", "::", "HALO::z", weight=0.4)
sealed = hf.add_edge("HALO::open2", "::", "HALO::crystal", weight=0.3)
hf._back_up_halo([from_anchor, sealed])                 # an anchor receives nothing; a sealed support carries nothing
offered = S.HALO_FRACTION * (from_crystal.weight + from_open.weight + from_anchor.weight + sealed.weight) + 10.0
accounted = hf.halo_total + hf.halo_repaired + hf.halo_to_null
saved = json.loads(json.dumps(aging.to_dict()))         # what a save keeps of the repair
older = {k: v for k, v in saved.items() if k != "repaired"}                 # a state written before v13.9
resumed = S.ConcordancyField.from_dict(json.loads(json.dumps(hf.to_dict())), hf.clock)
old_field = {k: v for k, v in json.loads(json.dumps(hf.to_dict())).items() if k != "halo_to_null"}
check("the Halo toward the Apparent: a crystal's dissolved exchange presses on its support from all sides and "
      "repairs what ages, up to its strength at birth and no further (TMC pp.47, 55, 14); a BOTH support takes "
      "nothing; the birth is not rewritten; an open construct's dissolved exchange is still banked; the repair "
      "survives a save and a resume, and a state from before v13.9 resumes with none; what no construct can hold "
      "returns to the null, accounted (TMC pp.45, 59): offered = banked + repaired + to the null",
      abs(after - (before + share)) < 1e-9 and abs(strength(aging) - aging.weight) < 1e-9
      and held_both.repaired == 0 and aging.born_breath == born
      and abs(hf.constructs["HALO::open"].recursion_exchanged - banked - S.HALO_FRACTION * from_open.weight) < 1e-12
      and S.ConcordancyEdge.from_dict(saved).repaired == aging.repaired > 0
      and S.ConcordancyEdge.from_dict(older).repaired == 0
      and resumed.halo_repaired == hf.halo_repaired > 0
      and abs(accounted - offered) < 1e-9 and hf.halo_to_null > 0
      and resumed.halo_to_null == hf.halo_to_null
      and S.ConcordancyField.from_dict(old_field, hf.clock).halo_to_null == 0,
      f"strength {before:.4f} -> {after:.4f} -> {strength(aging):.4f} of {aging.weight}; repaired {aging.repaired:.3f} breaths")
check("nothing leaves the field without a TERMINATE proof", not broken["vanished_silently"])
check("at most MAX_CONFLICTS_PER_CYCLE conflicts in a cycle (Stop Chasm, TMC p.41)", not broken["stop_chasm"])
check("conflict recursion never passes MAX_CF_DEPTH (Adsurdic threshold, TMC p.41)", not broken["adsurdic"])
check("the anchors never conclude", not broken["anchor_concluded"])
check("the tolerance stays between its floor and 1", not broken["tolerance_out"])
births = broken["crystal_concluded_at_birth"]
check("no crystal concludes in the cycle it forms: all Apparents must be Existents (TMC p.22)",
      not births, f"at cycles {births[:5]}" if births else f"{formed} crystals, none")

check.section(f"2 · A model in the loop (fake, deterministic; {N // 2} cycles)")
runs = []
with FakeModel("alike") as model:
    for _ in range(2):
        model.reset("alike")
        with quiet():
            llm = S.LLMIntermediary(backend="ollama", host=model.url)
        b, head, _ = life(0, N // 2, llm)
        runs.append((head, model.seeds, max(len(r["messages"]) for r in model.requests), b))
(head1, seeds1, largest, b1), (head2, seeds2, _, _) = runs
check("every model request carries a seed", seeds1 and all(isinstance(s, int) for s in seeds1),
      f"{len(seeds1)} requests")
check("the seeds follow the history, not a generator", len(set(seeds1)) == len(seeds1) and seeds1 == seeds2,
      f"{len(set(seeds1))} distinct of {len(seeds1)}; the same sequence in both runs: {seeds1 == seeds2}")
check("two identical runs with the model seal the same ledger", head1 == head2, head1[:16])
check("a request carries the system prompt and at most the last 12 messages", largest <= 13,
      f"largest request: {largest} messages")
check("the intermediary keeps only its last LLM_HISTORY_WINDOW messages, whatever the length of the life",
      len(llm.history) <= S.LLM_HISTORY_WINDOW and llm.call_count > S.LLM_HISTORY_WINDOW,
      f"{len(llm.history)} kept after {llm.call_count} calls")
check("the invariants hold with the model in the loop", not any(b1[name] for name in INVARIANTS))

check.finish()
