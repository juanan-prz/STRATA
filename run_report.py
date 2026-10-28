#!/usr/bin/env python3
"""
SIRISYS — instrumented run and report generator.

WHAT TO DO
  1. Put this file, sirisys_loader.py and the framework file in one folder.
     The newest Sirisys_Framework_vX_Y.py in that folder is used automatically.
  2. In Terminal:
         pip3 install anthropic numpy psutil
         export ANTHROPIC_API_KEY="sk-ant-..."
         python3 run_report.py --cycles 20 --seeds 1      # smoke test first
         python3 run_report.py                            # full run
  3. Send the file sirisys_report.json that appears in the folder.

  To use a different Claude model (optional):
         python3 run_report.py --model claude-haiku-4-5-20251001
  To use a local model through Ollama instead of the API:
         python3 run_report.py --backend ollama [--model <installed model>]
  Keep the SAME backend and model for every run you intend to compare.

COST
  The framework caps itself at 4 model calls per cycle. Before the arms run,
  two real calls prove the model answers and give an upper estimate of the
  model time. The report states the actual number of calls, broken down by
  purpose, with failures, empty answers and latency.

WHAT THE REPORT COMPARES
  Three arms on the same percept streams: the model (it names constructs and
  asks the Sombunal questions), the model asking only the Sombunal questions
  (names stay the control's), and a control without a model. The model reaches
  the field through those two channels; the middle arm separates them. Each run is judged by the Phase 3 criteria (sirisys_measures.
  LifeCriteria, the same code as measure_phase3.py): durable crystals in every
  1000-cycle window, flicker <= 5 %, no growth trend, flat cost of the cycle
  itself (model time excluded), bounded top-3 energy; with the tolerance the
  field sets for itself. Each run also carries the topology trace.

MODEL HEALTH
  A model that fails or answers empty leaves the field on synthetic names
  without notice. With --backend ollama|anthropic the run stops (exit code 3)
  if the model does not answer before the arms start, or if during the run
  3 calls in a row fail or more than 10 % of the last 50 fail or come back
  empty. The report is still written, marked "aborted", with the reason.

NOTE ON REPRODUCIBILITY
  The framework has no PRNG. With --percepts synthetic (default)
  each "seed" selects a reproducible percept stream and the degraded arm is
  bit-reproducible; with --percepts live, runs read this machine's CPU/RAM.
"""
import argparse
import contextlib
import hashlib
import io
import json
import platform
import statistics
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path
import field_topology  # read-only topology (pure Python, no networkx)
from sirisys_measures import LifeCriteria, ModelHealth

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "sirisys_report.json"

TAIL_START = 100

# The framework is found by version, not by exact file name: the newest
# Sirisys_Framework_vX_Y.py in this folder is used (see sirisys_loader.py).
sys.path.insert(0, str(HERE))
try:
    from sirisys_loader import load_framework
except ImportError:
    sys.exit("ERROR: sirisys_loader.py not found. Put it in the same folder "
             "as run_report.py and the framework file.")
try:
    S = load_framework(HERE)
except FileNotFoundError as ex:
    sys.exit(f"ERROR: {ex}")
FRAMEWORK = Path(S.__sirisys_path__)

# Configuration is READ from the framework, so the report records what
# actually ran instead of what this script assumed.
import inspect as _inspect
_prune = _inspect.signature(S.ConcordancyField.prune).parameters
BOTH_FLOOR = _prune["both_floor"].default
MIN_REFERENCES = _prune["min_references"].default
EXCHANGE_QUANTUM = S.TetralemmaEngine.EXCHANGE_QUANTUM


def _default_floor(src):
    import re as _re
    m = _re.search(r"both_floor:\s*float\s*=\s*([0-9.]+)", src)
    return float(m.group(1)) if m else 0.0


def integrity_check():
    """Confirm the loaded framework carries every mechanism the report measures.

    These are checks of MECHANISMS, not of a version number, so they keep
    passing on future versions as long as nothing measured here is removed.
    A failure means the framework changed in substance — exactly the moment
    this runner should be reviewed before trusting its numbers.
    """
    src = FRAMEWORK.read_text(encoding="utf-8")
    checks = {
        "conflict identity from the proof record": "def is_conflict_construct" in src,
        "no name-based conflict test":
            src.count("startswith('[CONFLICT'") <= 1,
        "prune floors (both_floor, min_references)": "both_floor: float" in src,
        "eventuality by banked exchange": "recursion_exchanged" in src,
        "banked exchange persisted":
            '"recursion_exchanged":' in src,
        "exchange quantum": "EXCHANGE_QUANTUM" in src,
        "no age bound on eventuality": "EVENTUALITY_BOUND" not in src,
        "no silent name replacement": "terminated_names" in src,
        # Invariant, not a literal: BOTH edge weights start at ~0.317, so a
        # default floor below that prunes nothing and disables BOTH resistance.
        "effective BOTH floor (>= 0.32)":
            _default_floor(src) >= 0.32,
        "lifetime witness counts": "proofs_total" in src and "erode_total" in src,
        "proof ledger": hasattr(S, "ProofLedger") and hasattr(S, "verify_ledger"),
        "canonical cycle in the framework": hasattr(S, "run_cycle") and hasattr(S, "new_session"),
        "endogenous orientation (no PRNG)": hasattr(S, "orient") and "import random" not in src,
        "self-adjusting tolerance": "def _adjust_tolerance" in src,
    }
    return checks, hashlib.sha256(src.encode()).hexdigest()[:16]


class CountingLLM(S.LLMIntermediary):
    """Wraps the real Intermediary to record every call and output; `health`
    watches failures, empty answers and latency (sirisys_measures.ModelHealth).

    `channels` separates the two ways the model enters the field:
      "all"        names (construct keys, hence orientation) and Sombunal questions;
      "questions"  Sombunal questions only: names are the control's own synthetic
                   ones, and the model budget is spent exactly as in "all", so the
                   questions arrive at the same cadence;
      "none"       nothing reaches the model, yet the model path is taken: the
                   control, reached the long way (it checks the ablation itself).
    """

    def __init__(self, force_degraded=False, model=None, backend=None, channels="all"):
        self.force_degraded = force_degraded
        self.channels = channels
        self.cycle = 0                          # set by run_arm; the control's names carry it
        self.by_kind = Counter()
        self.empty_by_kind = Counter()
        self.samples = defaultdict(list)
        self.health = ModelHealth()
        super().__init__(model=model, backend=backend)
        if self.available:
            self.health.attach(self)

    def _init(self):
        if self.force_degraded:
            self._available = False
            return
        super()._init()

    def _record(self, kind, out):
        self.by_kind[kind] += 1
        if not out:
            self.empty_by_kind[kind] += 1
        elif len(self.samples[kind]) < 25:
            self.samples[kind].append(str(out)[:160])
        return out

    # The control's synthetic names (ConcordancyOperator.execute, model unavailable).
    # If the framework changes them, the "none" check in test_phase1.py fails.
    def propose_emergent(self, x, y, xs, ys):
        if self.channels != "all":
            return f"[{x[:18]}]::[{y[:18]}]@c{self.cycle}"
        return self._record("propose_emergent",
                            super().propose_emergent(x, y, xs, ys))

    def interpret_conflict(self, x, y):
        if self.channels != "all":
            return f"CONFLICT::{x[:14]}⊗{y[:14]}"
        return self._record("interpret_conflict",
                            super().interpret_conflict(x, y))

    def question_sombunal(self, instability):
        if self.channels == "none":
            return ""
        return self._record("question_sombunal",
                            super().question_sombunal(instability))

    def narrate(self, *a, **k):
        return self._record("narrate", super().narrate(*a, **k))


def cycle_metrics(field, clock, cuss):
    edges = field.edges
    both = [e for e in edges if e.state == S.TetraState.BOTH]
    conflicts = [c for c in field.constructs.values()
                 if S.is_conflict_construct(c)]

    tension = defaultdict(float)
    for e in edges:
        tension[e.tgt] += e.weight * clock.tension(e.born_at)

    protected = set(S.ZERO_POINTS) | {"I::Am", "I::AmNot", "SYSTEM"}
    elig, totals = 0, []
    for n, c in field.constructs.items():
        if c.layer != S.Layer.UNIT_1 or n in protected:
            continue
        if clock.age_since(c.born_at) >= cuss.min_construct_age:
            elig += 1
            totals.append(tension[n] + c.recursion_exchanged)

    banked = [c.recursion_exchanged
              for c in field.constructs.values()]
    depths = [c.proofs_total for c in field.constructs.values()]
    modes = Counter()
    for c in field.constructs.values():
        try:
            modes[str(field.compute_existence_mode(c))] += 1
        except Exception:                                        # noqa: BLE001
            modes["ERROR"] += 1

    return {
        "constructs": len(field.constructs),
        "edges": len(edges),
        "both_frac": round(len(both) / max(len(edges), 1), 4),
        "both_age_mean": round(statistics.mean([e.both_age for e in both]), 2)
                         if both else 0.0,
        "both_age_max": max([e.both_age for e in both], default=0),
        "edge_states": dict(Counter(e.state.name for e in edges)),
        "apparents": field.apparents_total,
        "terminations": field.terminations_total,
        "reincarnations": field.reincarnations,
        "conflicts": len(conflicts),
        "conflict_energy_max": round(
            max([c.umbragiac_score for c in conflicts], default=0.0), 3),
        "banked_total": round(sum(banked), 3),
        "banked_constructs": sum(1 for v in banked if v > 0),
        "eligible_unit1": elig,
        "best_total": round(max(totals), 3) if totals else 0.0,
        "layers": dict(Counter(c.layer.name for c in field.constructs.values())),
        "modes": dict(modes),
        "proof_depth_mean": round(statistics.mean(depths), 2) if depths else 0.0,
    }


PROFILES = {"standard": {"narrate": True,  "include_hour": True},
            "minimal":  {"narrate": False, "include_hour": False}}


def run_arm(seed, cycles, llm_active, log, model=None, backend=None, profile="standard",
            percepts="synthetic", channels="all"):
    # The framework has no PRNG: `seed` selects the synthetic percept
    # stream (reproducible); with percepts="live" runs read this machine.
    S.set_ledger(S.ProofLedger(None))          # each arm: its own in-memory ledger
    quiet = io.StringIO()
    with contextlib.redirect_stdout(quiet):
        llm = CountingLLM(force_degraded=not llm_active, model=model, backend=backend,
                          channels=channels)
        ss = S.new_session(llm=llm)
    clock, field, conc, cuss = ss.clock, ss.field, ss.concordancy, ss.cussive

    # `percepts` is the source ("synthetic" or "live"); what arrives is counted apart
    trace, perceived, promoted, errors, topo_trace = [], Counter(), [], [], []
    genealogy, zero_points = field_topology.Genealogy(), set(S.ZERO_POINTS.keys())
    life, aborted = LifeCriteria(S), None
    born_names, total_closures = [], 0
    prev = set(field.constructs)
    birth, lifespans = {n: 0 for n in prev}, []
    t0 = time.time()

    for cyc in range(cycles):
        before_a = field.apparents_total
        try:
            # The canonical cycle — identical to the framework's own run() and
            # to what the live server shows (see sirisys_loader.run_cycle).
            with contextlib.redirect_stdout(quiet):
                prof = PROFILES[profile]
                ev = (S.synthetic_percepts(cyc, seed, prof["include_hour"])
                      if percepts == "synthetic" else None)
                llm.cycle = cyc
                t_cycle, t_model = time.perf_counter(), llm.health.model_seconds
                r = S.run_cycle(ss, cyc, percepts=ev, **prof)
                field_seconds = ((time.perf_counter() - t_cycle)
                                 - (llm.health.model_seconds - t_model))
            for e in r["percepts"]:
                perceived[e["tgt"]] += 1
        except Exception:                                        # noqa: BLE001
            errors.append({"cycle": cyc,
                           "traceback": traceback.format_exc()[-900:]})
            break

        now = set(field.constructs)
        died = prev - now
        new = now - prev
        for n in died:
            if n in birth:
                lifespans.append(cyc - birth[n])
                del birth[n]
        for n in new:
            birth[n] = cyc
        born_names += list(new)
        prev = now
        closures = r["closures"]
        total_closures += closures

        m = cycle_metrics(field, clock, cuss)
        m.update({
            "cycle": cyc,
            "born": len(new),
            "died": len(died),
            "closures": closures,
            "llm_calls_this_cycle": r["llm_used"],
            "narrated": bool(r["narration"]),
            "sombunal_question": bool(r["question"]),
            "new_apparents": field.apparents_total - before_a,
        })
        trace.append(m)
        # Read-only: criteria and genealogy every cycle, topology once per half-breath
        life.after_cycle(ss, cyc, field_seconds)
        genealogy.update(conc, cyc, field)
        if cyc % (S.BREATH_PERIOD // 2) == 0:
            topo_trace.append(field_topology.field_topology(
                field, cycle=cyc, zero_points=zero_points, genealogy=genealogy))
        if m["new_apparents"] > 0:
            promoted += [str(a) for a in field.apparents_since(field.apparents_total - m["new_apparents"])]

        if cyc % 25 == 0:
            log(f"    cycle {cyc:4}  constructs {m['constructs']:4}  "
                f"apparents {m['apparents']:4}  conflicts {m['conflicts']:3}  "
                f"BOTH {m['both_frac']:.3f}  calls {llm.call_count}")
        if llm.health.tripped:
            aborted = f"cycle {cyc}: {llm.health.reason}"
            log(f"    MODEL HEALTH — {aborted}")
            break

    criteria = life.result()

    return {
        "seed": seed,
        "channels": channels if llm_active else None,
        "ledger_head": S.get_ledger().head,
        "aborted": aborted,
        "criteria": criteria,
        "criteria_pass": LifeCriteria.verdict(criteria),
        "trace": trace,
        "topology_trace": topo_trace,
        "errors": errors,
        "seconds": round(time.time() - t0, 1),
        "llm": {
            "available": llm.available,
            "model": llm.model,
            "total_calls": llm.call_count,
            "calls_by_kind": dict(llm.by_kind),
            "empty_responses_by_kind": dict(llm.empty_by_kind),
            "failure_count": llm.health.failures,
            "failures": llm.health.errors,
            "health": llm.health.report(),
            "output_samples": {k: v for k, v in llm.samples.items()},
        },
        "percept_catalog": {
            "distinct_targets": len(perceived),
            "counts": dict(perceived.most_common(40)),
        },
        "lifespans": {
            "n": len(lifespans),
            "median": statistics.median(lifespans) if lifespans else None,
            "mean": round(statistics.mean(lifespans), 2) if lifespans else None,
            "max": max(lifespans) if lifespans else None,
        },
        "total_closures": total_closures,
        "sample_born_names": born_names[-60:],
        "apparents_named": promoted[-40:],
        "pool_telemetry_tail": list(conc.pool_telemetry)[-40:],
        "final_sizes": {
            "constructs": len(field.constructs),
            "edges": len(field.edges),
            "apparent_log": field.apparents_total,
            "terminations_total": field.terminations_total,
            "ledger_proofs": S.get_ledger().count,
        },
    }


def summarize(arm):
    traces = [r["trace"] for r in arm if r["trace"]]
    if not traces:
        return {"error": "no cycles completed"}
    n = min(len(t) for t in traces)

    def at(i, k):
        return statistics.mean(t[i][k] for t in traces)

    out = {
        "cycles_completed": n,
        "final_constructs": round(at(n - 1, "constructs"), 1),
        "final_edges": round(at(n - 1, "edges"), 1),
        "final_both_frac": round(at(n - 1, "both_frac"), 4),
        "final_apparents": round(at(n - 1, "apparents"), 1),
        "final_conflicts": round(at(n - 1, "conflicts"), 1),
        "final_terminations": round(at(n - 1, "terminations"), 1),
        "final_reincarnations": round(at(n - 1, "reincarnations"), 1),
        "total_closures": round(statistics.mean(
            r["total_closures"] for r in arm), 1),
        "total_llm_calls": sum(r["llm"]["total_calls"] for r in arm),
        "distinct_percepts": round(statistics.mean(
            r["percept_catalog"]["distinct_targets"] for r in arm), 1),
        "median_lifespan": round(statistics.mean(
            [r["lifespans"]["median"] for r in arm
             if r["lifespans"]["median"] is not None] or [0]), 2),
        "errors": sum(len(r["errors"]) for r in arm),
        "criteria_pass": [r["criteria_pass"] for r in arm],
        "durable_per_1000": [r["criteria"]["durable_per_1000"] for r in arm],
        "flicker_share": [r["criteria"]["flicker_share"] for r in arm],
        "constructs_trend": [r["criteria"]["constructs_trend"] for r in arm],
        "top3_energy_trend": [r["criteria"]["top3_energy_trend"] for r in arm],
        "tolerance_first_last": [r["criteria"]["tolerance_first_last"] for r in arm],
        "model_calls": sum(r["llm"]["health"]["calls"] for r in arm),
        "model_failures": sum(r["llm"]["health"]["failures"] for r in arm),
        "model_empty": sum(r["llm"]["health"]["empty"] for r in arm),
        "aborted": [r["aborted"] for r in arm if r["aborted"]],
    }
    if n > TAIL_START:
        out["steady_rate_per_10cyc"] = round(statistics.mean(
            (t[n - 1]["apparents"] - t[TAIL_START]["apparents"])
            / ((n - TAIL_START) / 10) for t in traces), 3)
        out["tail_growth_constructs"] = round(statistics.mean(
            t[n - 1]["constructs"] - t[TAIL_START]["constructs"]
            for t in traces), 1)
        out["tail_eligible_unit1"] = round(statistics.mean(
            statistics.mean(t[i]["eligible_unit1"] for i in range(TAIL_START, n))
            for t in traces), 2)
        out["tail_best_total"] = round(statistics.mean(
            max(t[i]["best_total"] for i in range(TAIL_START, n))
            for t in traces), 3)
    else:
        out["steady_rate_per_10cyc"] = None
        out["tail_growth_constructs"] = None
        out["note"] = (f"fewer than {TAIL_START} cycles — steady-state figures "
                       "not computed; run 150 cycles to test the prediction")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=150)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--skip-degraded", action="store_true")
    ap.add_argument("--skip-questions-arm", action="store_true",
                    help="skip the arm in which the model only asks the Sombunal questions")
    ap.add_argument("--model", default=None,
                    help="model id, e.g. claude-haiku-4-5-20251001. "
                         "Default: the backend's own (anthropic: claude-sonnet-4-6; "
                         "ollama: first installed model).")
    ap.add_argument("--percepts", choices=["synthetic", "live"], default="synthetic",
                    help="synthetic: reproducible stream per seed; live: this machine")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="standard",
                    help="'minimal': no narration and no time-of-day percept")
    ap.add_argument("--backend", choices=["anthropic", "ollama", "none"], default=None,
                    help="LLM backend (default: SIRISYS_LLM_BACKEND, else anthropic)")
    args = ap.parse_args()

    lines = []

    def log(msg):
        print(msg)
        lines.append(msg)

    checks, digest = integrity_check()
    with contextlib.redirect_stdout(io.StringIO()):
        probe = S.LLMIntermediary(model=args.model, backend=args.backend)
    llm_ok = probe.available

    log("=" * 70)
    log("SIRISYS — instrumented report run")
    log("=" * 70)
    for k, v in checks.items():
        log(f"  [{'ok ' if v else 'FAIL'}] {k}")
    if not all(checks.values()):
        log("\n  The framework lacks a mechanism this report measures. Stopping.")
        sys.exit(1)
    log(f"  framework file     : {S.__sirisys_file__}  (v{S.__sirisys_version__})")
    log(f"  file sha256[:16]   : {digest}")
    log(f"  model active       : {llm_ok}")
    log(f"  model id           : {probe.backend} · {probe.model}")
    log(f"  cycles x seeds     : {args.cycles} x {args.seeds}")
    log(f"  both_floor {BOTH_FLOOR}  min_references {MIN_REFERENCES}  "
        f"quantum {EXCHANGE_QUANTUM}")
    explicit = args.backend in ("ollama", "anthropic")
    health_probe = None
    if llm_ok:
        # full arm: at most MAX calls per cycle; questions arm: one every third cycle
        per_cycle = S.MAX_LLM_CALLS_PER_CYCLE + (0 if args.skip_questions_arm else 1 / 3)
        health_probe = ModelHealth.probe(probe, cycles=args.cycles * args.seeds,
                                         calls_per_cycle=per_cycle)
        if health_probe["ok"]:
            log(f"  model probe        : ok · {health_probe['call_s']} s per call "
                f"(first call, with loading: {health_probe['load_s']} s)")
            log(f"  model time, at most: ~{health_probe['estimated_model_hours_max']} h "
                f"for the model arms ({args.cycles} cycles x {args.seeds} seeds)")
            if health_probe.get("model"):
                log(f"  model identity     : {health_probe['model']}")
            log(f"  sample names       : {' | '.join(a[:40] for a in health_probe['answers'])}")
        else:
            log("")
            log(f"  STOP: the model does not answer properly — {health_probe['reason']}.")
            log(f"  Answers received: {health_probe.get('answers')}")
            log("  Nothing was run. Fix the model (ollama list; try a general-purpose")
            log("  model with --model) and run again.")
            sys.exit(3)
    if not llm_ok:
        log("")
        if explicit:
            log(f"  STOP: --backend {args.backend} was asked for, but the model is not available.")
        else:
            log("  WARNING: model NOT active — this run cannot compare model and control.")
        if probe.backend == "ollama":
            log(f"  Open the Ollama app (it must answer at {probe.host}), check the")
            log("  model is installed with: ollama list — then re-run.")
        elif probe.backend == "anthropic":
            log("  Install the package and set the key, then re-run:")
            log("      pip3 install anthropic")
            log('      export ANTHROPIC_API_KEY="sk-ant-..."')
        else:
            log("  Backend 'none' selected: the run uses no model.")
        if explicit:
            log("  Nothing was run.")
            sys.exit(3)

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
            "seeds": args.seeds,
            "tail_start": TAIL_START,
            "llm_active": llm_ok,
            "model_probe": health_probe,
            "backend": probe.backend,
            "profile": args.profile,
            "percepts": args.percepts,
            "model": probe.model,
            "max_llm_calls_per_cycle": S.MAX_LLM_CALLS_PER_CYCLE,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "note_reproducibility": (
                "With --percepts synthetic a run is bit-reproducible (the "
                "framework has no PRNG); with live percepts it reads this machine."),
        },
        "acceptance_criteria": (
            "Phase 3, per run: durable crystals (life >= one breath) in every "
            "1000-cycle window, flicker <= 5 %, constructs trend <= 1.2, cost of the "
            "cycle itself flat (late <= 1.5 x early + 0.5 ms), top-3 energy trend <= 1.2"),
        "arms": {},
    }

    aborted = None
    plan = ([("llm", True, "all")] if llm_ok else []) \
        + ([("llm_questions", True, "questions")] if llm_ok and not args.skip_questions_arm else []) \
        + ([] if args.skip_degraded else [("degraded", False, "all")])
    titles = {"llm": "LLM active", "llm_questions": "LLM, Sombunal questions only",
              "degraded": "degraded control"}
    for name, active, channels in plan:
        log(f"\n  --- arm: {titles[name]} ---")
        arm = []
        for s in range(args.seeds):
            arm.append(run_arm(s, args.cycles, active, log, args.model, args.backend,
                               args.profile, args.percepts, channels))
            if arm[-1]["aborted"]:
                aborted = f"arm {name}, seed {s}, {arm[-1]['aborted']}"
                break
        report["arms"][name] = {"runs": arm, "summary": summarize(arm)}
        if aborted:
            break
    report["aborted"] = aborted

    log("\n" + "=" * 70)
    for name, a in report["arms"].items():
        s = a["summary"]
        if "error" in s:
            log(f"  {name:9} {s['error']}")
            continue
        log(f"  {name:9} constructs {s['final_constructs']:7}  "
            f"apparents {s['final_apparents']:6}  "
            f"conflicts {s['final_conflicts']:5}  "
            f"BOTH {s['final_both_frac']:.3f}")
        log(f"  {'':9} criteria {['PASS' if v else 'FAIL' if v is False else 'n/a' for v in s['criteria_pass']]}  "
            f"durable/1000 {s['durable_per_1000']}  flicker {s['flicker_share']}")
        log(f"  {'':9} model calls {s['model_calls']}  failures {s['model_failures']}  "
            f"empty {s['model_empty']}  errors {s['errors']}")

    if aborted:
        log("")
        log(f"  STOPPED — model health: {aborted}")
        log("  The report below is partial. Check Ollama and the model, then run again.")
    report["console"] = lines
    OUTPUT.write_text(json.dumps(report, indent=1, ensure_ascii=False),
                      encoding="utf-8")
    print(f"\n  written: {OUTPUT.name}   ({OUTPUT.stat().st_size // 1024} KB)")
    print("  Send that file for analysis.")
    print("=" * 70)
    if aborted:
        sys.exit(3)


if __name__ == "__main__":
    main()
