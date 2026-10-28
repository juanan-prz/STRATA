#!/usr/bin/env python3
"""Ontological invariants of the field, checked cycle by cycle.

The other suites guard the record (chain, cuts, tampering, continuity). This
one guards what the field must be, from the primary source:
  - Zero Points are never operands: they are the Universal apparents (TMC p.22).
  - The older operand leads and the product inherits its handedness
    (Law 6, TMC p.35; first chirality dyad, p.50).
  - An Apparent is incontrovertible: while it exists it is never demoted, its
    crystal state never changes and its identity never shifts (TMC p.14).
  - Nothing vanishes silently: every construct that leaves the field leaves a
    TERMINATE proof (Compiler Guide pp.203-204).
  - The Stop Chasm and the Adsurdic threshold (TMC p.41): never more than
    MAX_CONFLICTS_PER_CYCLE conflicts in a cycle, and conflict recursion never
    deeper than MAX_CF_DEPTH.
  - The anchors (Zero Points, I::Am, I::AmNot, SYSTEM) never conclude.
  - The field's own tolerance stays between its floor and 1.
  - "all [Apparents] must be [Existents]" (TMC p.22): no crystal concludes in
    the cycle it forms. Known exception, to be closed in the next framework
    version: during the first breath, UCO can erode a new crystal's BOTH support
    after collapse checked it, and prune then orphans it. The check allows it
    only within the first breath.
  - No randomness with a model in the loop (TMC p.42): every request carries a
    seed oriented by the history, and two identical runs seal the same ledger.
Every life runs the minimal profile. The model is a local, deterministic fake.
Usage: python3 test_ontology.py [cycles per stream]        (default 400)"""
import sys

from sirisys_loader import load_framework
from sirisys_testkit import Checks, FakeModel, quiet

with quiet():
    S = load_framework()
N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
CO = S.ConcordancyOperator
INVARIANTS = ("zp_operand", "leader_not_older", "chirality_not_leader", "crystal_changed",
              "vanished_silently", "stop_chasm", "adsurdic", "anchor_concluded", "tolerance_out",
              "crystal_concluded_at_birth")
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


def first_breath_only(cycles):
    return all(c < S.BREATH_PERIOD for c in cycles)


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
check("nothing leaves the field without a TERMINATE proof", not broken["vanished_silently"])
check("at most MAX_CONFLICTS_PER_CYCLE conflicts in a cycle (Stop Chasm, TMC p.41)", not broken["stop_chasm"])
check("conflict recursion never passes MAX_CF_DEPTH (Adsurdic threshold, TMC p.41)", not broken["adsurdic"])
check("the anchors never conclude", not broken["anchor_concluded"])
check("the tolerance stays between its floor and 1", not broken["tolerance_out"])
births = broken["crystal_concluded_at_birth"]
check("no crystal concludes in the cycle it forms after the first breath (TMC p.22)",
      first_breath_only(births),
      f"{len(births)} during the first breath (known; next framework version)" if births else "none")

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
kept = len(llm.history)
print(f"  [KNOWN] the intermediary keeps its whole conversation in memory: {kept} entries after "
      f"{N // 2} cycles, about {round(kept * 1000 / max(1, N // 2))} per 1000. Harmless in an experiment; "
      f"to be bounded in the next framework version, before any life of months.")
check("the invariants hold with the model in the loop",
      not any(b1[name] for name in INVARIANTS if name != "crystal_concluded_at_birth")
      and first_breath_only(b1["crystal_concluded_at_birth"]))

check.finish()
