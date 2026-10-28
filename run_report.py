#!/usr/bin/env python3
"""SIRISYS — instrumented runs and their report.

USAGE
  python3 run_report.py --cycles 20 --seeds 1 --backend ollama --profile minimal     # smoke test
  python3 run_report.py --backend ollama --profile minimal --cycles 1000 --seeds 3   # the experiment
  python3 run_report.py --backend ollama --profile minimal --cycles 1000 --determinism
  python3 run_report.py --backend none                                               # the control alone

  Keep the same backend, model and profile for every run you intend to compare,
  and send the file the run writes: sirisys_report.json (or, with --determinism,
  sirisys_determinism.json).

WHAT THE REPORT COMPARES
  Three arms on the same percept streams. The model reaches the field through
  two channels: the names it gives constructs (names are keys, and enter every
  orientation) and the Sombunal questions (they enter the field as constructs).
    llm            the model, through both channels;
    llm_questions  the model asking only the Sombunal questions; the names are
                   the control's own, so this arm separates the two channels;
    degraded       the control, without a model.
  Each run is judged by the self-adjustment criteria (sirisys_measures.
  LifeCriteria, the code measure_phase3.py uses): durable crystals in every
  1000-cycle window, flicker <= 5 %, no growth trend, flat cost of the cycle
  itself (model time excluded), bounded top-3 energy. Each run also records the
  tolerance the field sets for itself, a trace of every cycle, the topology
  twice per breath and the ledger head after every cycle.

MODEL HEALTH
  A model that fails or answers empty would leave the field on synthetic names
  without notice. With a model, two real calls are made before anything runs;
  during the run, it stops when 3 calls in a row fail or more than 10 % of the
  last 50 fail or come back empty. The report is still written, marked
  "aborted", with the reason.

DETERMINISM
  The framework has no PRNG: every choice derives from the ledger head, so a run
  without a model is bit-reproducible on its synthetic stream. A model runtime
  may have randomness of its own even though every request carries a seed
  derived from the history. --determinism runs the model arm on stream 0 twice
  and says whether both runs sealed the same ledger and, if not, the cycle at
  which they parted.

EXIT CODES
  0  the report is written
  1  the framework lacks a mechanism this report measures
  3  a model was asked for and is missing or does not answer, or it stopped
     answering during the run (the report is then marked "aborted")
"""
import argparse
import contextlib
import hashlib
import inspect
import io
import json
import platform
import statistics
import sys
import time
import traceback
from collections import Counter, defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))       # the loader, the measures and the framework live beside this file
try:
    import field_topology                                   # read-only topology and depth
    from sirisys_measures import LifeCriteria, ModelHealth
    from sirisys_loader import load_framework
except ImportError as ex:
    sys.exit(f"ERROR: {ex}. Keep run_report.py, sirisys_loader.py, sirisys_measures.py, "
             "field_topology.py and the framework file in one folder.")
try:
    S = load_framework(HERE)        # the newest Sirisys_Framework_vX_Y.py in this folder
except FileNotFoundError as ex:
    sys.exit(f"ERROR: {ex}")

FRAMEWORK = Path(S.__sirisys_path__)
REPORT = HERE / "sirisys_report.json"
DETERMINISM_REPORT = HERE / "sirisys_determinism.json"

PROFILES = {"standard": {"narrate": True, "include_hour": True},
            "minimal": {"narrate": False, "include_hour": False}}
# name: (title, model active, channels through which the model reaches the field)
ARMS = {"llm": ("LLM active", True, "all"),
        "llm_questions": ("LLM, Sombunal questions only", True, "questions"),
        "degraded": ("degraded control", False, "all")}
ACCEPTANCE = ("Phase 3, per run: durable crystals (life >= one breath) in every 1000-cycle "
              "window, flicker <= 5 %, constructs trend <= 1.2, cost of the cycle itself flat "
              "(late <= 1.5 x early + 0.5 ms), top-3 energy trend <= 1.2")
ZERO_POINTS = frozenset(S.ZERO_POINTS)   # left out of the topology: never operands (TMC p.22)
PROGRESS_EVERY = 25                      # cycles between progress lines
SAMPLE_NAMES, SAMPLE_CRYSTALS, SAMPLE_TAIL = 60, 40, 40   # how much of each list a run keeps


def _prune_default(name):
    p = inspect.signature(S.ConcordancyField.prune).parameters.get(name)
    return None if p is None else p.default


# Read from the framework, so the report records what ran rather than what this file assumes
BOTH_FLOOR, MIN_REFERENCES = _prune_default("both_floor"), _prune_default("min_references")
EXCHANGE_QUANTUM = getattr(S.TetralemmaEngine, "EXCHANGE_QUANTUM", None)


class _Discard(io.TextIOBase):
    """Where the framework's own printing goes while a run is measured."""

    def write(self, s):
        return len(s)


def quiet():
    return contextlib.redirect_stdout(_Discard())


def integrity_checks():
    """The mechanisms this report measures, checked in the loaded framework.

    Mechanisms, not a version number: the checks keep passing on later versions
    as long as nothing measured here is removed. A failure means the framework
    changed in substance, and this file must be reviewed before its numbers are
    trusted. Returns the checks and the framework file's sha256[:16]."""
    src = FRAMEWORK.read_text(encoding="utf-8")
    checks = {
        "conflict identity from the proof record": hasattr(S, "is_conflict_construct"),
        "no name-based conflict test": src.count("startswith('[CONFLICT'") <= 1,
        "prune floors (both_floor, min_references)": None not in (BOTH_FLOOR, MIN_REFERENCES),
        "eventuality by banked exchange": "recursion_exchanged" in src,
        "banked exchange persisted": '"recursion_exchanged":' in src,
        "exchange quantum": EXCHANGE_QUANTUM is not None,
        "no age bound on eventuality": "EVENTUALITY_BOUND" not in src,
        "no silent name replacement": "terminated_names" in src,
        # BOTH edges are born at a weight of about 0.317: a lower floor prunes none of them
        "effective BOTH floor (>= 0.32)": (BOTH_FLOOR or 0) >= 0.32,
        "lifetime witness counts": "proofs_total" in src and "erode_total" in src,
        "proof ledger": hasattr(S, "ProofLedger") and hasattr(S, "verify_ledger"),
        "canonical cycle in the framework": hasattr(S, "run_cycle") and hasattr(S, "new_session"),
        "endogenous orientation (no PRNG)": hasattr(S, "orient") and "import random" not in src,
        "self-adjusting tolerance": "def _adjust_tolerance" in src,
    }
    return checks, hashlib.sha256(src.encode()).hexdigest()[:16]


class ArmIntermediary(S.LLMIntermediary):
    """The intermediary as one arm of the experiment sees it.

    `active=False` keeps the model out (the control). `channels` selects how an
    active model reaches the field:
      "all"        it names constructs and asks the Sombunal questions;
      "questions"  it only asks the questions: the names are the control's own,
                   and the framework still spends its model budget as in "all",
                   so the questions arrive at the same cadence;
      "none"       nothing reaches the model, though the model path is taken: the
                   control reached the long way (test_phase1.py checks it is the
                   control bit for bit).
    `health` watches every call the model answers or fails."""

    def __init__(self, active, channels="all", model=None, backend=None):
        self.active, self.channels = active, channels
        self.cycle = 0                              # set by run_arm: the control's names carry it
        self.health = ModelHealth()
        super().__init__(model=model, backend=backend)
        if self.available:
            self.health.attach(self)

    def _init(self):
        if self.active:                             # otherwise it stays unavailable
            super()._init()

    # The control's names, as ConcordancyOperator.execute writes them when no model is
    # available. If the framework changes them, the "none" check in test_phase1.py fails.
    def propose_emergent(self, x, y, x_state, y_state):
        if self.channels == "all":
            return super().propose_emergent(x, y, x_state, y_state)
        return f"[{x[:18]}]::[{y[:18]}]@c{self.cycle}"

    def interpret_conflict(self, x, y):
        if self.channels == "all":
            return super().interpret_conflict(x, y)
        return f"CONFLICT::{x[:14]}⊗{y[:14]}"

    def question_sombunal(self, instability):
        return "" if self.channels == "none" else super().question_sombunal(instability)


def cycle_metrics(ss):
    """The state of the field after a cycle. Read-only."""
    field, clock = ss.field, ss.clock
    constructs, edges = field.constructs.values(), field.edges
    both = [e for e in edges if e.state == S.TetraState.BOTH]
    conflicts = [c for c in constructs if S.is_conflict_construct(c)]
    tension = defaultdict(float)
    for e in edges:
        tension[e.tgt] += e.weight * clock.tension(e.born_at)
    # what each UNIT_1 construct old enough to crystallize holds (as cussive collapse counts it)
    eligible = [tension[n] + c.recursion_exchanged for n, c in field.constructs.items()
                if c.layer == S.Layer.UNIT_1 and n not in S.ANCHORS
                and clock.age_since(c.born_at) >= ss.cussive.min_construct_age]
    banked = [c.recursion_exchanged for c in constructs]
    return {
        "constructs": len(field.constructs),
        "edges": len(edges),
        "both_frac": round(len(both) / max(len(edges), 1), 4),
        "both_age_mean": round(statistics.mean(e.both_age for e in both), 2) if both else 0.0,
        "both_age_max": max((e.both_age for e in both), default=0),
        "edge_states": dict(Counter(e.state.name for e in edges)),
        "apparents": field.apparents_total,
        "terminations": field.terminations_total,
        "reincarnations": field.reincarnations,
        "conflicts": len(conflicts),
        "conflict_energy_max": round(max((c.umbragiac_score for c in conflicts), default=0.0), 3),
        "banked_total": round(sum(banked), 3),
        "banked_constructs": sum(1 for b in banked if b > 0),
        "eligible_unit1": len(eligible),
        "best_total": round(max(eligible), 3) if eligible else 0.0,
        "layers": dict(Counter(c.layer.name for c in constructs)),
        "modes": dict(Counter(str(field.compute_existence_mode(c)) for c in constructs)),
        "proof_depth_mean": (round(statistics.mean(c.proofs_total for c in constructs), 2)
                             if constructs else 0.0),
    }


def run_arm(seed, cycles, llm_active, log, model=None, backend=None, profile="standard",
            percepts="synthetic", channels="all"):
    """One life of `cycles` cycles; returns its record.

    `seed` selects the synthetic percept stream (the framework has no PRNG);
    with percepts="live" the run reads this machine instead. Everything measured
    here only reads the field: the ledger head is the same with and without it
    (test_phase2_guarantee.py)."""
    S.set_ledger(S.ProofLedger(None))               # each run: its own in-memory ledger
    with quiet():
        llm = ArmIntermediary(llm_active, channels, model=model, backend=backend)
        ss = S.new_session(llm=llm)
    field, prof = ss.field, PROFILES[profile]
    life, genealogy = LifeCriteria(S), field_topology.Genealogy()
    trace, topology, heads, errors, lifespans = [], [], [], [], []
    perceived, born_at = Counter(), dict.fromkeys(field.constructs, 0)
    born_names, crystals = deque(maxlen=SAMPLE_NAMES), deque(maxlen=SAMPLE_CRYSTALS)
    closures, aborted, t0 = 0, None, time.perf_counter()

    for cycle in range(cycles):
        apparents_before, alive_before = field.apparents_total, set(field.constructs)
        try:
            with quiet():
                stream = (S.synthetic_percepts(cycle, seed, prof["include_hour"])
                          if percepts == "synthetic" else None)
                llm.cycle = cycle
                t, model_t = time.perf_counter(), llm.health.model_seconds
                r = S.run_cycle(ss, cycle, percepts=stream, **prof)
                field_seconds = time.perf_counter() - t - (llm.health.model_seconds - model_t)
        except Exception:                                                   # noqa: BLE001
            errors.append({"cycle": cycle, "traceback": traceback.format_exc()[-900:]})
            break
        perceived.update(e["tgt"] for e in r["percepts"])

        alive = set(field.constructs)
        died, new = alive_before - alive, alive - alive_before
        lifespans += [cycle - born_at.pop(n) for n in died if n in born_at]
        born_at.update(dict.fromkeys(new, cycle))
        born_names.extend(sorted(new))
        crystals.extend(field.apparents_since(apparents_before))
        closures += r["closures"]

        m = cycle_metrics(ss)
        m.update({"cycle": cycle, "born": len(new), "died": len(died), "closures": r["closures"],
                  "llm_calls_this_cycle": r["llm_used"], "narrated": bool(r["narration"]),
                  "sombunal_question": bool(r["question"]),
                  "new_apparents": field.apparents_total - apparents_before})
        trace.append(m)
        heads.append(S.get_ledger().head[:16])       # where two runs part, if they do
        life.after_cycle(ss, cycle, field_seconds)
        genealogy.update(ss.concordancy, cycle, field)
        if cycle % (S.BREATH_PERIOD // 2) == 0:       # expansion and contraction of every breath
            topology.append(field_topology.field_topology(
                field, cycle=cycle, zero_points=ZERO_POINTS, genealogy=genealogy))

        if cycle % PROGRESS_EVERY == 0:
            log(f"    cycle {cycle:4}  constructs {m['constructs']:4}  "
                f"apparents {m['apparents']:4}  conflicts {m['conflicts']:3}  "
                f"BOTH {m['both_frac']:.3f}  calls {llm.health.calls}")
        if llm.health.tripped:
            aborted = f"cycle {cycle}: {llm.health.reason}"
            log(f"    MODEL HEALTH — {aborted}")
            break

    criteria = life.result()
    return {
        "seed": seed,
        "channels": channels if llm_active else None,
        "ledger_head": S.get_ledger().head,
        "ledger_head_by_cycle": heads,
        "aborted": aborted,
        "criteria": criteria,
        "criteria_pass": LifeCriteria.verdict(criteria),
        "trace": trace,
        "topology_trace": topology,
        "errors": errors,
        "seconds": round(time.perf_counter() - t0, 1),
        "llm": {"available": llm.available, "model": llm.model, "health": llm.health.report()},
        "percept_catalog": {"distinct_targets": len(perceived),
                            "counts": dict(perceived.most_common(SAMPLE_TAIL))},
        "lifespans": {"n": len(lifespans),
                      "median": statistics.median(lifespans) if lifespans else None,
                      "mean": round(statistics.mean(lifespans), 2) if lifespans else None,
                      "max": max(lifespans, default=None)},
        "total_closures": closures,
        "sample_born_names": list(born_names),
        "apparents_named": list(crystals),
        "pool_telemetry_tail": list(ss.concordancy.pool_telemetry)[-SAMPLE_TAIL:],
        "final_sizes": {"constructs": len(field.constructs),
                        "edges": len(field.edges),
                        "apparent_log": field.apparents_total,
                        "terminations_total": field.terminations_total,
                        "ledger_proofs": S.get_ledger().count},
    }


def summarize(runs):
    """One arm: the mean final state, and per run the criteria and the model's health."""
    traces = [r["trace"] for r in runs if r["trace"]]
    if not traces:
        return {"error": "no cycles completed"}
    n = min(map(len, traces))

    def final(key, digits):
        return round(statistics.mean(t[n - 1][key] for t in traces), digits)

    def per_run(key):
        return [r["criteria"][key] for r in runs]

    def model(key):
        return sum(r["llm"]["health"][key] for r in runs)

    medians = [r["lifespans"]["median"] for r in runs if r["lifespans"]["median"] is not None]
    return {
        "cycles_completed": n,
        "final_constructs": final("constructs", 1),
        "final_edges": final("edges", 1),
        "final_both_frac": final("both_frac", 4),
        "final_apparents": final("apparents", 1),
        "final_conflicts": final("conflicts", 1),
        "final_terminations": final("terminations", 1),
        "final_reincarnations": final("reincarnations", 1),
        "total_closures": round(statistics.mean(r["total_closures"] for r in runs), 1),
        "distinct_percepts": round(statistics.mean(r["percept_catalog"]["distinct_targets"]
                                                   for r in runs), 1),
        "median_lifespan": round(statistics.mean(medians or [0]), 2),
        "errors": sum(len(r["errors"]) for r in runs),
        "criteria_pass": [r["criteria_pass"] for r in runs],
        "durable_per_1000": per_run("durable_per_1000"),
        "flicker_share": per_run("flicker_share"),
        "constructs_trend": per_run("constructs_trend"),
        "top3_energy_trend": per_run("top3_energy_trend"),
        "tolerance_first_last": per_run("tolerance_first_last"),
        "model_calls": model("calls"),
        "model_failures": model("failures"),
        "model_empty": model("empty"),
        "aborted": [r["aborted"] for r in runs if r["aborted"]],
    }


def compare_runs(a, b):
    """Two runs of the same stream with the model: did they seal the same ledger?
    If not, the first cycle whose ledger head differs, and an example of answers
    that differ when one is among the recorded samples (the first of each kind)."""
    ha, hb = a["ledger_head_by_cycle"], b["ledger_head_by_cycle"]
    parted = next((i for i, (x, y) in enumerate(zip(ha, hb)) if x != y),
                  None if len(ha) == len(hb) else min(len(ha), len(hb)))
    example = None
    sa, sb = a["llm"]["health"]["samples"], b["llm"]["health"]["samples"]
    for kind in sorted(set(sa) | set(sb)):
        xs, ys = sa.get(kind, []), sb.get(kind, [])
        i = next((i for i, (x, y) in enumerate(zip(xs, ys)) if x != y), None)
        if i is not None and (example is None or i < example["index"]):
            example = {"kind": kind, "index": i, "first": xs[i], "second": ys[i]}
    return {"same": a["ledger_head"] == b["ledger_head"],
            "ledger_heads": [a["ledger_head"], b["ledger_head"]],
            "diverged_at_cycle": parted,
            "example_different_answers": example}


class Console:
    """Prints each line and keeps it: the report carries its own console."""

    def __init__(self):
        self.lines = []

    def __call__(self, msg=""):
        print(msg)
        self.lines.append(msg)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="SIRISYS instrumented runs (see the docstring "
                                             "at the top of this file).")
    ap.add_argument("--cycles", type=int, default=1000,
                    help="cycles per run (the criteria need at least 1000; default 1000)")
    ap.add_argument("--seeds", type=int, default=3,
                    help="synthetic percept streams 0, 1, ... (default 3)")
    ap.add_argument("--backend", choices=S.LLMIntermediary.BACKENDS, default=None,
                    help="model backend (default: SIRISYS_LLM_BACKEND, else anthropic)")
    ap.add_argument("--model", default=None,
                    help="model name (default: SIRISYS_LLM_MODEL, else the backend's own; "
                         "with Ollama, the first installed model)")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="standard",
                    help="'minimal': no narration and no time-of-day percept")
    ap.add_argument("--percepts", choices=["synthetic", "live"], default="synthetic",
                    help="synthetic: one reproducible stream per seed; live: this machine")
    ap.add_argument("--skip-questions-arm", action="store_true",
                    help="skip the arm in which the model only asks the Sombunal questions")
    ap.add_argument("--skip-degraded", action="store_true", help="skip the control arm")
    ap.add_argument("--determinism", action="store_true",
                    help="run the model arm on stream 0 twice and report whether both runs "
                         "sealed the same ledger (writes sirisys_determinism.json)")
    args = ap.parse_args(argv)
    if args.determinism and args.percepts == "live":
        ap.error("--determinism needs the synthetic percepts: live percepts differ on every run")
    return args


def plan(args, model_on):
    """The arms to run, in order, and the percept streams each one runs."""
    if args.determinism:
        return ["llm"], [0, 0]
    arms = (["llm"] if model_on else []) \
        + (["llm_questions"] if model_on and not args.skip_questions_arm else []) \
        + ([] if args.skip_degraded else ["degraded"])
    return arms, list(range(args.seeds))


def print_header(args, checks, digest, intermediary, log):
    """The framework that runs and its checks; exits (code 1) when a check fails."""
    log("=" * 70)
    log("SIRISYS — instrumented report run")
    log("=" * 70)
    for label, ok in checks.items():
        log(f"  [{'ok ' if ok else 'FAIL'}] {label}")
    if not all(checks.values()):
        log("\n  The framework lacks a mechanism this report measures. Stopping.")
        sys.exit(1)
    log(f"  framework file     : {S.__sirisys_file__}  (v{S.__sirisys_version__})")
    log(f"  file sha256[:16]   : {digest}")
    log(f"  model active       : {intermediary.available}")
    log(f"  model id           : {intermediary.backend} · {intermediary.model or '(none)'}")
    if args.determinism:
        log(f"  determinism check  : the model arm, stream 0, twice x {args.cycles} cycles")
    else:
        log(f"  cycles x seeds     : {args.cycles} x {args.seeds}")
    log(f"  both_floor {BOTH_FLOOR}  min_references {MIN_REFERENCES}  quantum {EXCHANGE_QUANTUM}")


def check_model(args, intermediary, streams, log):
    """With a model, prove it answers before anything runs; without one, say why.
    Exits (code 3) when a model was asked for, or is needed, and does not answer."""
    if intermediary.available:
        # at most MAX calls per cycle in the full arm; one every third cycle in the questions arm
        questions = 0 if args.determinism or args.skip_questions_arm else 1 / 3
        probe = ModelHealth.probe(intermediary, cycles=args.cycles * len(streams),
                                  calls_per_cycle=S.MAX_LLM_CALLS_PER_CYCLE + questions)
        if not probe["ok"]:
            log()
            log(f"  STOP: the model does not answer properly — {probe['reason']}.")
            log(f"  Answers received: {probe.get('answers')}")
            log("  Nothing was run. Fix the model (ollama list; try a general-purpose")
            log("  model with --model) and run again.")
            sys.exit(3)
        log(f"  model probe        : ok · {probe['call_s']} s per call "
            f"(first call, with loading: {probe['load_s']} s)")
        log(f"  model time, at most: ~{probe['estimated_model_hours_max']} h "
            f"for the model runs ({args.cycles} cycles x {len(streams)} streams)")
        if probe.get("model"):
            log(f"  model identity     : {probe['model']}")
        log(f"  sample names       : {' | '.join(a[:40] for a in probe['answers'])}")
        return probe

    explicit = args.backend in ("ollama", "anthropic")
    log()
    if explicit:
        log(f"  STOP: --backend {args.backend} was asked for, but the model is not available.")
    else:
        log("  WARNING: model NOT active — this run cannot compare model and control.")
    if intermediary.backend == "ollama":
        log(f"  Open the Ollama app (it must answer at {intermediary.host}), check the")
        log("  model is installed with: ollama list — then re-run.")
    elif intermediary.backend == "anthropic":
        log("  Install the package and set the key, then re-run:")
        log("      pip3 install anthropic")
        log('      export ANTHROPIC_API_KEY="sk-ant-..."')
    else:
        log("  Backend 'none' selected: the run uses no model.")
    if args.determinism:
        log("  --determinism checks a model: without one the field is deterministic by")
        log("  construction (test_sirisys.py and test_ontology.py check it).")
    if explicit or args.determinism:
        log("  Nothing was run.")
        sys.exit(3)
    return None


def run_plan(args, arms, streams, log):
    """Every arm on every stream; stops at the first run whose model stopped answering.
    Returns the arms and the reason for stopping, if any."""
    out = {}
    for name in arms:
        title, active, channels = ARMS[name]
        log(f"\n  --- arm: {title}{', stream 0 twice' if args.determinism else ''} ---")
        runs = []
        for seed in streams:
            runs.append(run_arm(seed, args.cycles, active, log, model=args.model,
                                backend=args.backend, profile=args.profile,
                                percepts=args.percepts, channels=channels))
            if runs[-1]["aborted"]:
                out[name] = {"runs": runs, "summary": summarize(runs)}
                return out, f"arm {name}, seed {seed}, {runs[-1]['aborted']}"
        out[name] = {"runs": runs, "summary": summarize(runs)}
    return out, None


def print_summary(report, log):
    def verdict(v):
        return "PASS" if v else "FAIL" if v is False else "n/a"

    log("\n" + "=" * 70)
    for name, arm in report["arms"].items():
        s = arm["summary"]
        if "error" in s:
            log(f"  {name:9} {s['error']}")
            continue
        log(f"  {name:9} constructs {s['final_constructs']:7}  apparents {s['final_apparents']:6}  "
            f"conflicts {s['final_conflicts']:5}  BOTH {s['final_both_frac']:.3f}")
        log(f"  {'':9} criteria {[verdict(v) for v in s['criteria_pass']]}  "
            f"durable/1000 {s['durable_per_1000']}  flicker {s['flicker_share']}")
        log(f"  {'':9} model calls {s['model_calls']}  failures {s['model_failures']}  "
            f"empty {s['model_empty']}  errors {s['errors']}")
        log(f"  {'':9} ledger heads {[r['ledger_head'][:16] for r in arm['runs']]}")

    d = report.get("determinism")
    if d:
        log()
        if d["same"]:
            log("  determinism: YES — both runs sealed the same ledger.")
        else:
            log(f"  determinism: NO — the two runs parted at cycle {d['diverged_at_cycle']}.")
            ex = d["example_different_answers"]
            if ex:
                log(f"  answers that differ ({ex['kind']}): {ex['first'][:50]!r} | {ex['second'][:50]!r}")
    if report["aborted"]:
        log()
        log(f"  STOPPED — model health: {report['aborted']}")
        log("  The report is partial. Check Ollama and the model, then run again.")


def main(argv=None):
    args = parse_args(argv)
    log = Console()
    checks, digest = integrity_checks()
    with quiet():
        intermediary = S.LLMIntermediary(model=args.model, backend=args.backend)
    arms, streams = plan(args, intermediary.available)
    print_header(args, checks, digest, intermediary, log)
    probe = check_model(args, intermediary, streams, log)

    report = {
        "config": {
            "framework": FRAMEWORK.name,
            "framework_version": S.__sirisys_version__,
            "framework_sha256_16": digest,
            "integrity_checks": checks,
            "both_floor": BOTH_FLOOR,
            "min_references": MIN_REFERENCES,
            "exchange_quantum": EXCHANGE_QUANTUM,
            "cycles": args.cycles,
            "streams": streams,
            "determinism_check": args.determinism,
            "llm_active": intermediary.available,
            "model_probe": probe,
            "backend": intermediary.backend,
            "model": intermediary.model,
            "profile": args.profile,
            "percepts": args.percepts,
            "max_llm_calls_per_cycle": S.MAX_LLM_CALLS_PER_CYCLE,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
        },
        "acceptance_criteria": ACCEPTANCE,
    }
    report["arms"], report["aborted"] = run_plan(args, arms, streams, log)
    if args.determinism and not report["aborted"]:
        report["determinism"] = compare_runs(*report["arms"]["llm"]["runs"])
    print_summary(report, log)

    report["console"] = log.lines
    path = DETERMINISM_REPORT if args.determinism else REPORT
    path.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n  written: {path.name}   ({path.stat().st_size // 1024} KB)")
    print("  Send that file for analysis.")
    print("=" * 70)
    if report["aborted"]:
        sys.exit(3)


if __name__ == "__main__":
    main()
