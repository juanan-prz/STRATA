#!/usr/bin/env python3
"""
SIRISYS v12.8 — instrumented run + report generator.

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
  Keep the SAME model for every run you intend to compare.

COST
  The framework caps itself at 4 model calls per cycle. 150 cycles x 3 seeds
  is at most ~1800 short calls. The report states the actual number, broken
  down by purpose, and counts failures separately.

THE PREDICTION UNDER TEST  (written before the run, from degraded calibration)
  A real model should put the field in the "rich" regime measured
  synthetically, not the "open" one:
      steady-state crystallization  ~1 new Apparent per 10 cycles (cycle 100+)
      tail growth                   under ~10 constructs over cycles 100-150
      BOTH fraction                 roughly 0.25-0.45, not climbing past 0.5
  The refuting outcome is unbounded growth (100+ constructs in the tail) with
  BOTH climbing back above 0.5: the model would then be supplying novelty
  faster than the field can consolidate it.

NOTE ON REPRODUCIBILITY
  perceive_real() reads live CPU and memory, so runs are not bit-reproducible
  even at a fixed seed. The percept stream is therefore recorded.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import platform
import random
import statistics
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "sirisys_report.json"

TAIL_START = 100

# The framework is found by version, not by exact file name: the newest
# Sirisys_Framework_vX_Y.py in this folder is used (see sirisys_loader.py).
sys.path.insert(0, str(HERE))
try:
    from sirisys_loader import load_framework, make_session, run_cycle
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
        "v12.2 proof-chain conflict typing": "def is_conflict_construct" in src,
        "v12.2 no name-based conflict test":
            src.count("startswith('[CONFLICT'") <= 1,
        "v12.3 both_floor / min_references": "both_floor: float" in src,
        "v12.4 eventuality enforcement": "recursion_exchanged" in src,
        "v12.5 banked exchange serialised":
            '"recursion_exchanged": getattr' in src,
        "v12.6 exchange quantum": "EXCHANGE_QUANTUM" in src,
        "v12.6 age bound removed": "EVENTUALITY_BOUND" not in src,
        "v12.7 no silent name replacement": "terminated_names" in src,
        # Invariant, not a literal: BOTH edge weights start at ~0.317, so a
        # default floor below that prunes nothing and silently disables Route A.
        "v12.8 both_floor default is effective (>= 0.32)":
            _default_floor(src) >= 0.32,
        "v12.9 lifetime witness counts": "proofs_total" in src and "erode_total" in src,
    }
    return checks, hashlib.sha256(src.encode()).hexdigest()[:16]


class CountingLLM(S.LLMIntermediary):
    """Wraps the real Intermediary to record every call, output and failure."""

    def __init__(self, force_degraded=False, model=None):
        self.force_degraded = force_degraded
        self.by_kind = Counter()
        self.empty_by_kind = Counter()
        self.failures = []
        self.samples = defaultdict(list)
        if model:
            super().__init__(model=model)
        else:
            super().__init__()

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

    def _call(self, prompt, temperature=0.85):
        try:
            return super()._call(prompt, temperature)
        except Exception as ex:                                  # noqa: BLE001
            self.failures.append(repr(ex)[:200])
            return ""

    def propose_emergent(self, x, y, xs, ys):
        return self._record("propose_emergent",
                            super().propose_emergent(x, y, xs, ys))

    def interpret_conflict(self, x, y):
        return self._record("interpret_conflict",
                            super().interpret_conflict(x, y))

    def question_sombunal(self, instability):
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
            totals.append(tension[n] + getattr(c, "recursion_exchanged", 0.0))

    banked = [getattr(c, "recursion_exchanged", 0.0)
              for c in field.constructs.values()]
    depths = [len(c.proof_chain) for c in field.constructs.values()]
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
        "apparents": len(field.apparent_log),
        "terminations": len(field.termination_log),
        "reincarnations": getattr(field, "reincarnations", 0),
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


def run_arm(seed, cycles, llm_active, log, model=None):
    random.seed(seed)
    quiet = io.StringIO()
    with contextlib.redirect_stdout(quiet):
        llm = CountingLLM(force_degraded=not llm_active, model=model)
        ss = make_session(S, llm=llm)
    clock, field, conc, cuss = ss.clock, ss.field, ss.concordancy, ss.cussive

    trace, percepts, promoted, errors = [], Counter(), [], []
    born_names, total_closures = [], 0
    prev = set(field.constructs)
    birth, lifespans = {n: 0 for n in prev}, []
    t0 = time.time()

    for cyc in range(cycles):
        before_a = len(field.apparent_log)
        try:
            # The canonical cycle — identical to the framework's own run() and
            # to what the live server shows (see sirisys_loader.run_cycle).
            with contextlib.redirect_stdout(quiet):
                r = run_cycle(S, ss, cyc)
            for e in r["percepts"]:
                percepts[e["tgt"]] += 1
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
            "new_apparents": len(field.apparent_log) - before_a,
        })
        trace.append(m)
        if m["new_apparents"] > 0:
            promoted += [str(a) for a in list(field.apparent_log)[-m["new_apparents"]:]]

        if cyc % 25 == 0:
            log(f"    cycle {cyc:4}  constructs {m['constructs']:4}  "
                f"apparents {m['apparents']:4}  conflicts {m['conflicts']:3}  "
                f"BOTH {m['both_frac']:.3f}  calls {llm.call_count}")

    return {
        "seed": seed,
        "trace": trace,
        "errors": errors,
        "seconds": round(time.time() - t0, 1),
        "llm": {
            "available": bool(getattr(llm, "available", False)),
            "model": getattr(llm, "model", None),
            "total_calls": llm.call_count,
            "calls_by_kind": dict(llm.by_kind),
            "empty_responses_by_kind": dict(llm.empty_by_kind),
            "failure_count": len(llm.failures),
            "failures": llm.failures[:20],
            "output_samples": {k: v for k, v in llm.samples.items()},
        },
        "percept_catalog": {
            "distinct_targets": len(percepts),
            "counts": dict(percepts.most_common(40)),
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
            "apparent_log": len(field.apparent_log),
            "termination_log": len(field.termination_log),
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
        "llm_failures": sum(r["llm"]["failure_count"] for r in arm),
        "distinct_percepts": round(statistics.mean(
            r["percept_catalog"]["distinct_targets"] for r in arm), 1),
        "median_lifespan": round(statistics.mean(
            [r["lifespans"]["median"] for r in arm
             if r["lifespans"]["median"] is not None] or [0]), 2),
        "errors": sum(len(r["errors"]) for r in arm),
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
    ap.add_argument("--model", default=None,
                    help="model id, e.g. claude-haiku-4-5-20251001. "
                         "Default: the framework's own (claude-sonnet-4-6).")
    args = ap.parse_args()

    lines = []

    def log(msg):
        print(msg)
        lines.append(msg)

    checks, digest = integrity_check()
    with contextlib.redirect_stdout(io.StringIO()):
        probe = (S.LLMIntermediary(model=args.model) if args.model
                 else S.LLMIntermediary())
    llm_ok = bool(getattr(probe, "available", False))

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
    log(f"  model id           : {getattr(probe, 'model', None)}")
    log(f"  cycles x seeds     : {args.cycles} x {args.seeds}")
    log(f"  both_floor {BOTH_FLOOR}  min_references {MIN_REFERENCES}  "
        f"quantum {EXCHANGE_QUANTUM}")
    if not llm_ok:
        log("")
        log("  WARNING: model NOT active — this run cannot test the")
        log("  prediction. Install the package and set the key, then re-run:")
        log("      pip3 install anthropic")
        log('      export ANTHROPIC_API_KEY="sk-ant-..."')

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
            "model": getattr(probe, "model", None),
            "max_llm_calls_per_cycle": S.MAX_LLM_CALLS_PER_CYCLE,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "note_reproducibility": (
                "perceive_real() reads live CPU/RAM, so runs are not "
                "bit-reproducible at fixed seed; percept catalog recorded."),
        },
        "prediction_under_test": {
            "regime_expected": "rich",
            "steady_rate_per_10cyc": "~1",
            "tail_growth_constructs": "<10",
            "both_frac": "0.25-0.45, not climbing above 0.5",
            "refuting_outcome": "tail growth >100 constructs with BOTH > 0.5",
        },
        "arms": {},
    }

    if llm_ok:
        log("\n  --- arm: LLM active ---")
        arm = [run_arm(s, args.cycles, True, log, args.model) for s in range(args.seeds)]
        report["arms"]["llm"] = {"runs": arm, "summary": summarize(arm)}

    if not args.skip_degraded:
        log("\n  --- arm: degraded control ---")
        arm = [run_arm(s, args.cycles, False, log, args.model) for s in range(args.seeds)]
        report["arms"]["degraded"] = {"runs": arm, "summary": summarize(arm)}

    log("\n" + "=" * 70)
    for name, a in report["arms"].items():
        s = a["summary"]
        log(f"  {name:9} constructs {s['final_constructs']:7}  "
            f"apparents {s['final_apparents']:6}  "
            f"conflicts {s['final_conflicts']:5}  "
            f"BOTH {s['final_both_frac']:.3f}")
        log(f"  {'':9} steady rate {s['steady_rate_per_10cyc']}  "
            f"tail growth {s['tail_growth_constructs']}  "
            f"calls {s['total_llm_calls']}  failures {s['llm_failures']}  "
            f"errors {s['errors']}")

    report["console"] = lines
    OUTPUT.write_text(json.dumps(report, indent=1, ensure_ascii=False),
                      encoding="utf-8")
    print(f"\n  written: {OUTPUT.name}   ({OUTPUT.stat().st_size // 1024} KB)")
    print("  Send that file for analysis.")
    print("=" * 70)


if __name__ == "__main__":
    main()
