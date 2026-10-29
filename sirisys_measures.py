"""Shared measurements for the experiment tools. Read-only: nothing here seals a
proof, changes the field or alters what the model is asked or answers.

LifeCriteria
    The self-adjustment criteria adopted in Phase 3, computed in one place for
    measure_phase3.py, run_report.py and live_c2.py: durable crystals (life of
    at least one breath) in every 1000-cycle window, flicker <= 5 %, no growth
    trend, flat cost, bounded top-3 energy. Also the tolerance the field sets
    for itself, first and last. checks() says which criterion holds, one by one
    (the live view shows them); verdict() is the whole rule.

ModelHealth
    A model that fails or answers empty leaves the field on synthetic names
    without notice: the run looks like a run with a model and is not one.
    probe() proves the model completes before a run starts; attach() watches
    every call during the run and trips when calls keep failing or coming back
    empty.
"""
import time
from collections import Counter, defaultdict, deque


class LifeCriteria:
    """Feed after_cycle() once per cycle; read result() and verdict() at the end."""

    def __init__(self, S):
        self.S = S
        self.ap, self.cs, self.ts, self.e3, self.tol = [], [], [], [], []
        self.born, self.durable, self.flicker, self.seen = {}, [], 0, 0
        self.apparents_total = 0

    def after_cycle(self, ss, cycle, field_seconds):
        """field_seconds: time of the cycle itself, without the model's calls."""
        S, f = self.S, ss.field
        self.ts.append(field_seconds)
        self.ap.append(f.apparents_total)
        self.cs.append(len(f.constructs))
        self.tol.append(f.tolerance)
        for n in f.apparents_since(self.seen):
            self.born[n] = cycle
        self.seen = f.apparents_total
        for n, b in list(self.born.items()):
            alive = n in f.constructs and f.constructs[n].layer == S.Layer.APPARENT
            if not alive:
                self.flicker += (cycle - b) < S.BREATH_PERIOD
                del self.born[n]
            elif cycle - b >= S.BREATH_PERIOD:
                self.durable.append(b)
                del self.born[n]
        if cycle % 100 == 99:
            top = sorted(ss.concordancy._energy_map(f).values(), reverse=True)
            self.e3.append(sum(top[:3]))
        self.apparents_total = f.apparents_total

    def result(self):
        N, S = len(self.cs), self.S
        ap, cs, ts, e3, tol = self.ap, self.cs, self.ts, self.e3, self.tol
        w = [ap[min(a + 199, N - 1)] - ap[a - 1] for a in range(200, N, 200)]
        if N >= 2000:                       # the last 1000 cycles against the 1000 before
            last, prev = sum(cs[-1000:]) / 1000, sum(cs[-2000:-1000]) / 1000
        else:                               # shorter lives: second half against first half
            h = N // 2
            last, prev = sum(cs[h:]) / max(1, N - h), sum(cs[:h]) / max(1, h)
        k = min(500, N // 2)
        h3 = len(e3) // 2
        durable = Counter(b // 1000 for b in self.durable)      # by the 1000-cycle window it was born in
        return {
            "cycles": N,
            "durable_per_1000": [durable[a // 1000] for a in range(0, N - S.BREATH_PERIOD, 1000)],
            "flicker_share": round(self.flicker / max(1, self.apparents_total), 3),
            "zero_windows": w.count(0), "windows": len(w),
            "new_per_200": (min(w), round(sum(w) / len(w), 1), max(w)) if w else None,
            "constructs_final": cs[-1] if cs else 0,
            "constructs_trend": round(last / prev, 3) if prev else None,
            "ms_first_last": (round(1000 * sum(ts[:k]) / max(1, k), 2),
                              round(1000 * sum(ts[-k:]) / max(1, k), 2)) if k else None,
            # mean of the second half vs the first half of the samples (a two-point
            # ratio was too noisy: energy fluctuates 3–20 with no trend)
            "top3_energy_trend": (round((sum(e3[h3:]) / (len(e3) - h3))
                                        / max(1e-9, sum(e3[:h3]) / h3), 3) if h3 else None),
            "top3_energy_final": round(e3[-1], 1) if e3 else None,
            "tolerance_first_last": (round(sum(tol[:k]) / max(1, k), 3),
                                     round(sum(tol[-k:]) / max(1, k), 3)) if k else None,
        }

    # The Phase 3 acceptance rule, criterion by criterion, in the order it is judged
    RULE = {
        "durable": lambda r: min(r["durable_per_1000"]) >= 1,
        "flicker": lambda r: r["flicker_share"] <= 0.05,
        "population": lambda r: r["constructs_trend"] <= 1.2,
        "cost": lambda r: r["ms_first_last"][1] <= 1.5 * r["ms_first_last"][0] + 0.5,
        "energy": lambda r: r["top3_energy_trend"] <= 1.2,
    }

    @staticmethod
    def checks(r):
        """Each criterion of the rule: True or False, or None where the life is
        too short to say."""
        held = {}
        for name, rule in LifeCriteria.RULE.items():
            try:
                held[name] = bool(rule(r))
            except (TypeError, ValueError, KeyError):
                held[name] = None
        return held

    @staticmethod
    def verdict(r):
        """The Phase 3 acceptance rule; None for a life shorter than one
        1000-cycle window, too short to judge."""
        if r.get("cycles", 0) < 1000:
            return None
        for held in LifeCriteria.checks(r).values():     # in order, as the rule reads
            if held is not True:
                return held
        return True


def _kind(prompt):
    """Which question the intermediary was asked, from the prompt itself."""
    if prompt.startswith("Concordancy:"):
        return "name"
    if prompt.startswith("Reversion:"):
        return "conflict"
    if prompt.startswith("Cycle "):
        return "narration"
    return "sombunal_question"


class ModelHealth:
    """Watches the intermediary's calls. Trips (sets `tripped` and `reason`) when
    MAX_CONSECUTIVE_FAILURES calls in a row raise, or when more than
    MAX_BAD_SHARE of the last WINDOW calls failed or came back empty. Tools check
    `tripped` after each cycle and stop. Watching changes nothing in the calls."""

    MAX_CONSECUTIVE_FAILURES = 3
    WINDOW = 50
    MAX_BAD_SHARE = 0.10

    def __init__(self):
        self.calls, self.ok, self.failures, self.empty = 0, 0, 0, 0
        self.by_kind, self.empty_by_kind = Counter(), Counter()
        self.errors, self.latencies = [], []
        self.samples = defaultdict(list)            # the first answers of each kind, to judge them
        self.model_seconds = 0.0
        self.recent = deque(maxlen=self.WINDOW)
        self.consecutive_failures = 0
        self.tripped, self.reason = False, None

    def attach(self, llm):
        """Wrap llm._complete (the single place every backend's answer passes)."""
        inner = llm._complete

        def watched(temperature):
            kind = _kind(llm.history[-1]["content"]) if llm.history else "other"
            t = time.perf_counter()
            try:
                out = inner(temperature)
            except Exception as ex:                      # the intermediary logs it and returns ""
                self._record(kind, time.perf_counter() - t, failed=True, error=ex)
                raise
            self._record(kind, time.perf_counter() - t, empty=not str(out).strip())
            if str(out).strip() and len(self.samples[kind]) < 10:
                self.samples[kind].append(str(out).strip()[:120])
            return out

        llm._complete = watched
        return llm

    def _record(self, kind, seconds, failed=False, empty=False, error=None):
        self.calls += 1
        self.by_kind[kind] += 1
        self.model_seconds += seconds
        self.latencies.append(seconds)
        if failed:
            self.failures += 1
            self.consecutive_failures += 1
            if len(self.errors) < 10:
                self.errors.append(f"{kind}: {error!r}"[:200])
        else:
            self.consecutive_failures = 0
            if empty:
                self.empty += 1
                self.empty_by_kind[kind] += 1
            else:
                self.ok += 1
        self.recent.append(failed or empty)
        if not self.tripped:
            if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                self.tripped = True
                self.reason = (f"{self.consecutive_failures} model calls in a row failed "
                               f"(last: {self.errors[-1] if self.errors else '?'})")
            elif (len(self.recent) == self.WINDOW
                  and sum(self.recent) / self.WINDOW > self.MAX_BAD_SHARE):
                self.tripped = True
                self.reason = (f"{sum(self.recent)} of the last {self.WINDOW} model calls "
                               f"failed or came back empty")

    def report(self):
        lat = sorted(self.latencies)
        q = lambda p: round(lat[min(len(lat) - 1, int(p * len(lat)))], 3) if lat else None
        return {"calls": self.calls, "ok": self.ok, "failures": self.failures,
                "empty": self.empty, "calls_by_kind": dict(self.by_kind),
                "empty_by_kind": dict(self.empty_by_kind),
                "latency_s": {"median": q(0.5), "p95": q(0.95), "max": q(1.0)},
                "model_seconds": round(self.model_seconds, 1),
                "tripped": self.tripped, "reason": self.reason, "errors": self.errors,
                "samples": dict(self.samples)}

    @staticmethod
    def identity(llm):
        """Which model exactly: for Ollama, the installed entry (digest, size,
        parameters, quantization), since one tag can name different builds."""
        ident = {"backend": llm.backend, "name": llm.model}
        if llm.backend == "ollama":
            try:
                for m in llm._http_json("GET", "/api/tags", timeout=5).get("models", []):
                    if m.get("name") == llm.model or m.get("model") == llm.model:
                        ident.update({k: m[k] for k in ("digest", "size", "details") if k in m})
            except Exception as ex:                              # identity is a record, not a gate
                ident["error"] = repr(ex)[:120]
        return ident

    @staticmethod
    def probe(llm, cycles=None, calls_per_cycle=None):
        """Two real completions on a separate intermediary: the first may include
        loading the model, the second gives the latency. Returns a dict with ok,
        the reason when not ok, the answers, the latency and, given cycles, an
        upper estimate of the run's model time."""
        if not llm.available:
            return {"ok": False, "reason": "the model is not available"}
        answers, secs = [], []
        h = ModelHealth()
        h.attach(llm)
        for x, y in (("I::Am", "SYSTEM"), ("SYSTEM", "I::AmNot")):
            t = time.perf_counter()
            answers.append(llm.propose_emergent(x, y, "TRUE", "TRUE"))
            secs.append(time.perf_counter() - t)
        if h.failures:
            return {"ok": False, "reason": f"the model call failed: {h.errors[-1]}", "answers": answers}
        if not all(a.strip() for a in answers):
            return {"ok": False, "answers": answers,
                    "reason": "the model answered empty (a reasoning model can spend its short "
                              "budget thinking; choose a general-purpose model)"}
        out = {"ok": True, "answers": answers, "load_s": round(secs[0], 2), "call_s": round(secs[1], 2),
               "model": ModelHealth.identity(llm)}
        if cycles and calls_per_cycle:
            out["estimated_model_hours_max"] = round(cycles * calls_per_cycle * secs[1] / 3600, 1)
        return out
