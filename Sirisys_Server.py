"""SIRISYS server: experiment mode, and the replay of a run, served to the live visualizer.

The canonical cycle (run_cycle, in the framework) runs in a worker thread, and
every cycle becomes a snapshot for Sirisys_Live_Visualizer.html. Every start,
and every Reset, is a new instance in a run folder of its own; nothing is
overwritten:
    sirisys_runs/<date-time>_<live|streamN>[_minimal]/ledger.jsonl     every proof, as it is sealed
    sirisys_runs/<date-time>_<live|streamN>[_minimal]/percepts.jsonl   what it perceived, cycle by cycle
    sirisys_runs/<date-time>_<live|streamN>[_minimal]/answers.jsonl    what the model answered, cycle by cycle
    sirisys_runs/<date-time>_<live|streamN>[_minimal]/state.json       the instance, when it ends
    sirisys_runs/<date-time>_<live|streamN>[_minimal]/criteria.json    its criteria, when it ends

USAGE
    python3 Sirisys_Server.py                       # this machine's percepts, paused: press Play
    python3 Sirisys_Server.py --play                # start cycling at once
    python3 Sirisys_Server.py --stream 0 --play     # synthetic stream 0: the same run every time
    python3 Sirisys_Server.py --profile minimal     # no narration, no time-of-day percept
    python3 Sirisys_Server.py --replay last         # the latest run again (REPLAY), on port 8001
  Then open http://127.0.0.1:8000 (a replay: 8001). Ctrl+C stops the server and
  saves the instance.
  Options: --delay-ms (pause between cycles, default 80), --host (default
  127.0.0.1: this machine only), --port (default 8000; 8001 for a replay).
  The model: SIRISYS_LLM_BACKEND=anthropic|ollama|none, SIRISYS_LLM_MODEL,
  OLLAMA_HOST, ANTHROPIC_API_KEY.

INTERFACE (what the visualizer uses)
    GET  /                       the visualizer
    GET  /api/status             the instance: cycle, stream, run folder, ledger, model
    GET  /api/snapshot           the snapshots not yet delivered, as a list
    GET  /api/history            the instance's metabolism, breath by breath (METABOLISM)
    POST /api/control/<action>   play · pause · step · reset {"stream": "live" | N}
                                 · speed {"cycle_delay_ms": N}   (a replay's reset takes no stream)
    WS   /ws                     the status first, then each snapshot as it is made;
                                 {"action": ...} messages are answered with an ack, and the
                                 status is sent again when the engine starts or stops otherwise
  A snapshot is delivered once, to whichever client reads it first: one viewer
  at a time. While nobody reads, only the last MAX_PENDING are kept.

METABOLISM
  Each snapshot carries what its cycle did to the population: the constructs
  born (those that concluded before the cycle ended, never on any snapshot,
  among them), those that concluded by their last layer, the rises and the
  crystallizations. Born minus concluded is the change in the population,
  exactly, every cycle. The engine also adds them up breath by breath for the
  whole instance (/api/history), so a viewer that arrives late sees all of it;
  past HISTORY_KEPT breaths the oldest are merged in pairs.

THE CRITERIA
  The engine measures the instance as run_report.py does (sirisys_measures.
  LifeCriteria, the self-adjustment criteria of Phase 3): every CRITERIA_EVERY
  cycles the result, each criterion and the verdict go to the status and to
  that cycle's snapshot. The verdict needs 1000 cycles. When the instance
  ends (Reset, Ctrl+C) the reading as it stands goes to criteria.json in its
  run folder. Measuring changes nothing in the field; its record grows with the
  instance (some 100 bytes a cycle).

WHAT IT PERCEIVED, AND WHAT THE MODEL ANSWERED
  As each cycle ends, its percepts go to percepts.jsonl (sirisys_measures.
  PerceptRecord) and, with a model, the model's answers, in order, to
  answers.jsonl (AnswerRecord). Recording changes nothing in the field nor in
  the calls. A life read from this machine can then be lived again, the same
  real percepts with or without a model, with
      python3 live_c2.py <cycles> none <profile> --replay sirisys_runs/<run>/percepts.jsonl
  or watched again here (REPLAY).

REPLAY
      python3 Sirisys_Server.py --replay sirisys_runs/<run>      (or: --replay last)
  lives a run again from its record, the same percepts and the model's
  answers as it gave them, at the speed chosen in the view and without asking
  any model: the field, the labels, the narration, the questions, the event
  log, the metabolism and the criteria, as they went. It listens on port 8001,
  so it can run beside a live server on 8000. Nothing is written: the ledger is
  kept in memory and, as each cycle ends, compared with the run's own; the
  status says how far they are the same (on the machine that recorded it, all
  the way; on another platform the arithmetic differs and it departs within
  the first cycles). It stops at the end of the record; Play, or Reset at any
  point, plays it again from its first cycle. It runs at most REPLAY_AHEAD
  cycles ahead of what the view has taken, so every cycle reaches the view.
  A run recorded before answers.jsonl replays without its model's labels and
  words (whole, if its saved state shows it had no model); one recorded before
  percepts.jsonl cannot be replayed. In a replay the cost criterion measures
  the replay's own time.

THE MODEL WATCH
  With a model, the engine watches every call as run_report.py does
  (sirisys_measures.ModelHealth). The field does not need the model (since
  v13.5 it only labels and words), but one that fails or answers empty would,
  unnoticed, leave the constructs without labels. When the watch trips, the
  engine pauses once and the status and the snapshots say why; Play goes on.

REQUIREMENTS
    pip3 install -r requirements.txt     (fastapi, uvicorn and websockets for this server)
    Beside this file: sirisys_loader.py, Sirisys_Framework_vX_Y.py, Sirisys_Live_Visualizer.html,
    and sirisys_measures.py (the criteria, the model watch, the records of the percepts and the
    answers); without it the server runs and says that the criteria are not measured nor the
    records kept, and a replay cannot run
"""
import argparse
import asyncio
import contextlib
import io
import json
import logging
import sys
import threading
import time
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sirisys_loader import load_framework, quiet  # noqa: E402

S = load_framework(HERE)
if not all(hasattr(S, name) for name in ("run_cycle", "new_session", "ProofLedger")):
    raise SystemExit(f"\n  {S.__sirisys_file__} predates v13.1 — this server needs the canonical "
                     f"cycle and the proof ledger. Use the matching older server for it.\n")

# "minimal" removes the narration and the time-of-day percept: the field then
# perceives only the machine it runs on.
PROFILES = {"standard": {"narrate": True, "include_hour": True},
            "minimal": {"narrate": False, "include_hour": False}}
MAX_PENDING = 200               # snapshots kept while nobody reads them
REPLAY_AHEAD = 4                # a replay's snapshots waiting for the view before it waits too
HISTORY_KEPT = 2048             # metabolism records before the oldest are merged in pairs
CRITERIA_EVERY = 200            # cycles between two readings of the criteria
PORTS = {"experiment": 8000, "replay": 8001}
LAYER_NAMES = ("NULL_00", "UMBRA_0", "UNIT_1", "APPARENT")
log = logging.getLogger("sirisys")


def parse_stream(value):
    """'live' (this machine's percepts) → None; N → the synthetic stream N."""
    return None if str(value).lower() == "live" else int(value)


def live_refused(stream):
    """Why live percepts cannot be used (the machine cannot be perceived), or None."""
    return S.NO_PERCEPTION if stream is None and not S.real_percepts_available() else None


def _stream_arg(value):
    try:
        return parse_stream(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'live' or an integer, not {value!r}") from None


def _conclusion(meta):
    """What a TERMINATE proof records about the construct that concluded."""
    return {"name": meta.get("name"), "layer": meta.get("final_layer"),
            "mode": meta.get("final_mode"), "vc": meta.get("final_Vc")}


def _add_metabolism(record, cycle):
    """A record of the history with one more cycle's metabolism (the cycle's own
    record, with its cycle number, population and tolerance) added to it."""
    record["breaths"][1] = cycle["breath"]
    record["cycles"][1] = cycle["cycle"]
    for key in ("born", "unseen", "risen", "crystallized"):
        record[key] += cycle[key]
    for layer, n in cycle["concluded"].items():
        record["concluded"][layer] += n
    record["population"], record["tolerance"] = dict(cycle["population"]), cycle["tolerance"]
    return record


def _merge_metabolism(older, newer):
    """Two neighbouring records of the history as one: the flows added, the ending kept."""
    merged = {"breaths": [older["breaths"][0], newer["breaths"][1]],
              "cycles": [older["cycles"][0], newer["cycles"][1]],
              "concluded": {layer: older["concluded"][layer] + newer["concluded"][layer] for layer in LAYER_NAMES},
              "population": newer["population"], "tolerance": newer["tolerance"]}
    for key in ("born", "unseen", "risen", "crystallized"):
        merged[key] = older[key] + newer[key]
    return merged


class ExperimentEngine:
    """Runs cycles in a worker thread and queues one snapshot per cycle.

    Each instance lives in its own run folder with its own ledger; a reset
    starts a new one and leaves the previous one on disk. Two locks, always
    taken in this order: _cycle_lock for a whole cycle (and for a reset or the
    shutdown), _queue_lock for the snapshot queue, its listeners and the history."""

    MODE = "experiment"
    PAUSES_FOR_MODEL = True         # once, when the model watch trips (THE MODEL WATCH)

    def __init__(self, stream: int | None, delay_ms: int, runs_dir: Path, profile: str = "standard"):
        self.stream, self.cycle_delay_ms, self.runs_dir, self.profile = stream, delay_ms, runs_dir, profile
        self.running, self.alive, self.step_once = False, True, False
        self._cycle_lock, self._queue_lock = threading.Lock(), threading.Lock()
        self._queue = deque(maxlen=MAX_PENDING)
        self._listeners = set()                 # (event loop, asyncio.Event) of each open WebSocket
        self.ledger = self.percepts = self.answers = None
        self._new_instance()
        threading.Thread(target=self._run_loop, daemon=True).start()

    # ── instances ────────────────────────────────────────────────────────
    def _new_instance(self) -> None:
        if self.ledger is not None:
            self.ledger.close()
        self._close_records()
        tag = ("live" if self.stream is None else f"stream{self.stream}") + \
              ("" if self.profile == "standard" else f"_{self.profile}")
        base = f"{time.strftime('%Y%m%d-%H%M%S')}_{tag}"
        run_dir, n = self.runs_dir / base, 1
        while run_dir.exists():
            n += 1
            run_dir = self.runs_dir / f"{base}_{n}"
        run_dir.mkdir(parents=True)
        with self._queue_lock:                  # a viewer asking for the history gets one instance's, whole
            self.run_dir, self._history = run_dir, []       # the metabolism, breath by breath (METABOLISM)
        self.ledger = S.set_ledger(S.ProofLedger(self.run_dir / "ledger.jsonl"))
        self._begin()
        try:                                    # WHAT IT PERCEIVED, AND WHAT THE MODEL ANSWERED
            from sirisys_measures import AnswerRecord, PerceptRecord
            self.percepts = PerceptRecord(self.run_dir)
            self.answers = AnswerRecord(self.run_dir, self.ss.llm, self.profile)
        except ImportError:
            pass                                # _begin has said so
        log.info("Experiment instance %s (framework %s, LLM %s)",
                 self.run_dir.name, S.__sirisys_file__, self.ss.llm)

    def _begin(self, llm=None) -> None:
        """A session at T0 in the ledger just installed, with what measures and watches it."""
        with quiet():
            self.ss = S.new_session(llm)
        self.cycle, self.last_T = 0, tuple(self.ss.clock.T)
        self._terminations_seen = self.ss.field.terminations_total
        self._apparents_seen = self.ss.field.apparents_total
        self.life, self.criteria = None, None   # the criteria, and their last reading (THE CRITERIA)
        try:
            from sirisys_measures import LifeCriteria
            self.life = LifeCriteria(S)
        except ImportError:
            log.warning("sirisys_measures.py not found: the criteria are not measured, "
                        "nor what the instance perceived and the model answered kept")
        self._watch_model()
        self._paused_for_model = False

    def _close_records(self) -> None:
        for record in (self.percepts, self.answers):
            if record is not None:
                record.close()
        self.percepts = self.answers = None

    @property
    def run_name(self) -> str:
        """The instance's name in the snapshots, the status and the history: its run folder."""
        return self.run_dir.name

    def _watch_model(self) -> None:
        """With a model: the watch, and what the model says (the whole of each answer).
        Neither changes the calls."""
        self.health = self.said = None
        if self.ss.llm.available:
            # Only a run with a model needs them: importing this file does not
            from sirisys_measures import ModelHealth, Translations
            self.health = ModelHealth()
            self.health.attach(self.ss.llm)
            self.said = Translations()
            self.said.attach(self.ss.llm)

    def _whole_question(self) -> str | None:
        """The cycle's Sombunal question as the model wrote it: its label, the snapshot's
        `question`, is cut to MAX_NODE_NAME characters. What the model said is kept one cycle."""
        if not self.said:
            return None
        asked = [answer for _, kind, _, _, answer in self.said.entries if kind == "question"]
        self.said.entries.clear()
        return asked[-1] if asked else None

    def save(self) -> None:
        """The instance as it stands: its state and, once it has cycled, its criteria."""
        with quiet():
            S.save_state(self.run_dir / "state.json", self.ss.field, self.ss.clock,
                         self.ss.llm, self.cycle, self.ss.concordancy)
        if self.life and self.cycle:
            (self.run_dir / "criteria.json").write_text(json.dumps(self._read_criteria(), indent=1),
                                                        encoding="utf-8")

    # ── the worker ───────────────────────────────────────────────────────
    def _run_loop(self) -> None:
        while self.alive:
            if not (self.running or self.step_once) or self._waiting_for_view():
                time.sleep(0.02)
                continue
            try:
                self._step()
            except Exception:
                log.exception("Cycle %d raised", self.cycle)
                self.running = False
            finally:
                if self.step_once:
                    self.step_once = self.running = False
            time.sleep(max(self.cycle_delay_ms, 0) / 1000)

    def _waiting_for_view(self) -> bool:
        """Whether the next cycle waits for the view (only a replay does: REPLAY)."""
        return False

    def _before_cycle(self, profile: dict) -> list | None:
        """The cycle's percepts: None, for run_cycle to read this machine's, or the stream's."""
        if self.stream is None:
            return None
        return S.synthetic_percepts(self.cycle, self.stream, profile["include_hour"])

    def _after_cycle(self, r: dict) -> None:
        """What the cycle perceived and the model answered, kept: the answers first, so
        that every cycle the percept record holds has its answers."""
        if self.answers:
            self.answers.add(self.cycle)
        if self.percepts:
            self.percepts.add(self.cycle, r["percepts"])

    def _step(self) -> None:
        profile = PROFILES[self.profile]
        printed = io.StringIO()                 # the framework's own lines go to the visualizer's console
        with self._cycle_lock:
            before = set(self.ss.field.constructs)
            model_before = self.health.model_seconds if self.health else 0.0
            with contextlib.redirect_stdout(printed):
                percepts = self._before_cycle(profile)
                started = time.perf_counter()
                r = S.run_cycle(self.ss, self.cycle, percepts=percepts, **profile)
                # the field's own time, without the model's calls, as run_report.py measures it
                field_seconds = time.perf_counter() - started - (
                    (self.health.model_seconds if self.health else 0.0) - model_before)
            self._after_cycle(r)
            now = tuple(self.ss.clock.T)
            if now <= self.last_T:
                raise S.ContinuityError(f"time did not advance: {self.last_T} -> {now}")
            self.last_T = now
            if self.PAUSES_FOR_MODEL and self.health and self.health.tripped and not self._paused_for_model:
                self._paused_for_model, self.running = True, False   # once: Play goes on
                log.warning("The model watch tripped: %s. Paused: press Play to go on regardless.",
                            self.health.reason)
            console = [line for line in printed.getvalue().splitlines() if line.strip()]
            snapshot = self._snapshot(r, console, before, self._whole_question())
            if self.life:
                self.life.after_cycle(self.ss, self.cycle, field_seconds)
                if (self.cycle + 1) % CRITERIA_EVERY == 0:
                    self.criteria = snapshot["criteria"] = self._read_criteria()
            with self._queue_lock:
                self._queue.append(snapshot)
                self._record_metabolism(snapshot)
                listeners = list(self._listeners)
            self.cycle += 1
        for loop, event in listeners:
            with contextlib.suppress(RuntimeError):         # that loop has already closed
                loop.call_soon_threadsafe(event.set)

    # ── snapshots (the visualizer reads these keys: add, never rename) ───
    def _snapshot(self, r: dict, console: list[str], before: set, question_full: str | None) -> dict:
        f = self.ss.field
        new = f.terminations_total - self._terminations_seen
        self._terminations_seen = f.terminations_total
        crystallized = f.apparents_since(self._apparents_seen)  # the promotions that reached APPARENT
        self._apparents_seen = f.apparents_total
        concluded = [_conclusion(t.meta or {}) for t in (f.termination_log[-new:] if new > 0 else [])]
        energy = self.ss.concordancy._energy_map(f)            # what [::] selection weighs
        modes = dict.fromkeys(("OMEGA", "LEMNISCATE", "NEUTRAL"), 0)
        layers = dict.fromkeys(LAYER_NAMES, 0)
        constructs = []
        for c in f.constructs.values():
            mode = f.compute_existence_mode(c)
            modes[mode] += 1
            layers[c.layer.name] += 1
            constructs.append({
                "name": c.name, "label": c.label, "layer": c.layer.value, "born_at": list(c.born_at),
                "witness": c.witness, "umbragiac_score": round(c.umbragiac_score, 4),
                "energy": round(energy.get(c.name, 0.0), 4),
                "lagrange": c.lagrange.name if c.lagrange else None,
                "proof_chain": c.proofs_total,                  # lifetime count
                "vc": round(f.compute_anchoring_weight(c), 4),
                "mode": mode,
                "conflict": S.is_conflict_construct(c),
                "banked": round(c.recursion_exchanged, 3),
                "chirality": c.chirality,
                "crystal": c.crystal_state.name if c.crystal_state else None,
            })
        # both_age: the cycles a BOTH channel has stayed open; weight × both_age is what it has
        # exchanged, and it closes at TetralemmaEngine.EXCHANGE_QUANTUM
        edges = [{"src": e.src, "tgt": e.tgt, "state": e.state.name, "weight": round(e.weight, 4),
                  "both_age": e.both_age} for e in f.edges]
        telemetry = self.ss.concordancy.pool_telemetry
        return {
            "type": "cycle", "run": self.run_name, "cycle": self.cycle, "T": list(self.ss.clock.T),
            "constructs": len(f.constructs), "edges": len(f.edges),
            "apparents": f.apparents_total, "terminations": f.terminations_total,
            "instability": round(r["instability"], 4), "modes": modes, "layers": layers,
            "events": len(r["emergent"]), "emergent_names": r["emergent"],
            "promoted": len(r["promoted"]), "promoted_names": r["promoted"],
            "crystallized": crystallized,
            "llm_used": r["llm_used"], "model_watch": self._model_watch(), "log": console,
            "conflicts": r["conflict_count"], "closures": r["closures"],
            "both_edges": r["both_count"], "reincarnations": f.reincarnations,
            "action": r["action"], "narration": r["narration"], "question": r["question"],
            "question_full": question_full,
            "breath": f.breaths, "contraction": r["contraction"], "tolerance": round(f.tolerance, 3),
            "concluded": concluded,
            "metabolism": self._metabolism(before, concluded, r["promoted"], crystallized),
            "telemetry": telemetry[-1] if telemetry else {},
            "ledger": {"count": self.ledger.count, "head": self.ledger.head[:16]},
            "field": {"constructs": constructs, "edges": edges},
        }

    def _metabolism(self, before: set, concluded: list, promoted: list, crystallized: list) -> dict:
        """What the cycle did to the population. Born: the names in the field now that
        were not before it, and those that concluded in it without having been there
        (born and concluded in the same cycle: never on any snapshot)."""
        f = self.ss.field
        arrived = set(f.constructs) - before
        unseen = {c["name"] for c in concluded} - before - set(f.constructs)
        by_layer = dict.fromkeys(LAYER_NAMES, 0)
        for c in concluded:
            if c["layer"] in by_layer:
                by_layer[c["layer"]] += 1
        return {"breath": f.breaths, "born": len(arrived) + len(unseen), "unseen": len(unseen),
                "concluded": by_layer, "risen": len(promoted) - len(crystallized),
                "crystallized": len(crystallized)}

    def _record_metabolism(self, snapshot: dict) -> None:
        """Add a cycle to the history (under _queue_lock): to its breath's record, or to a new one."""
        cycle = {**snapshot["metabolism"], "cycle": snapshot["cycle"],
                 "population": snapshot["layers"], "tolerance": snapshot["tolerance"]}
        history = self._history
        if not history or history[-1]["breaths"][1] != cycle["breath"]:
            history.append({"breaths": [cycle["breath"]] * 2, "cycles": [cycle["cycle"]] * 2,
                            "born": 0, "unseen": 0, "risen": 0, "crystallized": 0,
                            "concluded": dict.fromkeys(LAYER_NAMES, 0)})
        _add_metabolism(history[-1], cycle)
        if len(history) > HISTORY_KEPT:                 # the oldest half, merged in pairs
            half = len(history) // 2 // 2 * 2
            history[:half] = [_merge_metabolism(history[i], history[i + 1]) for i in range(0, half, 2)]

    def history(self) -> dict:
        """The instance's metabolism so far, breath by breath, oldest first; through_cycle
        is the last cycle it includes (-1 before the first)."""
        with self._queue_lock:
            run = self.run_name
            records = [{**h, "breaths": list(h["breaths"]), "cycles": list(h["cycles"]),
                        "concluded": dict(h["concluded"]), "population": dict(h["population"])}
                       for h in self._history]
        return {"run": run, "through_cycle": records[-1]["cycles"][1] if records else -1, "records": records}

    def _read_criteria(self) -> dict:
        """The criteria as run_report.py reports them: the result, each criterion, what each
        asks, the verdict."""
        result = self.life.result()
        return {"cycles": result["cycles"], "result": result, "checks": self.life.checks(result),
                "rules": {name: words for name, (words, _) in self.life.RULE.items()},
                "verdict": self.life.verdict(result)}

    def _model_watch(self) -> dict | None:
        """The model watch so far; None without a model."""
        h = self.health
        if h is None:
            return None
        return {"calls": h.calls, "ok": h.ok, "failures": h.failures, "empty": h.empty,
                "tripped": h.tripped, "reason": h.reason}

    # ── what clients use ─────────────────────────────────────────────────
    def control(self, action: str, **options) -> dict:
        """play · pause · step · reset (stream: 'live' or N) · speed (cycle_delay_ms)."""
        if action == "play":
            self.running = True
            return {"ok": True, "running": True}
        if action == "pause":
            self.running = False
            return {"ok": True, "running": False}
        if action == "step":
            self.step_once = True
            return {"ok": True, "stepping": True}
        if action == "reset":
            try:
                stream = parse_stream(options["stream"]) if "stream" in options else self.stream
            except ValueError:
                return {"ok": False,
                        "error": f"stream must be 'live' or an integer, not {options['stream']!r}"}
            if live_refused(stream):
                return {"ok": False, "error": live_refused(stream)}
            self.running, self.stream = False, stream
            with self._cycle_lock:
                self.save()                                     # the old instance stays on disk
                previous = self.run_dir.name
                self._new_instance()
                with self._queue_lock:
                    self._queue.clear()
            return {"ok": True, "reset": True, "stream": self.stream, "previous_run": previous}
        if action == "speed":
            try:
                self.cycle_delay_ms = max(0, int(options.get("cycle_delay_ms", 80)))
            except (TypeError, ValueError):
                return {"ok": False, "error": "cycle_delay_ms must be an integer"}
            return {"ok": True, "cycle_delay_ms": self.cycle_delay_ms}
        return {"ok": False, "error": f"unknown action: {action}"}

    def status(self) -> dict:
        llm = self.ss.llm
        return {"running": self.running, "cycle": self.cycle, "T": list(self.ss.clock.T),
                "stream": self.stream if self.stream is not None else "live",
                "cycle_delay_ms": self.cycle_delay_ms,
                "model": {"backend": llm.backend, "name": llm.model, "active": llm.available,
                          "watch": self._model_watch()},
                "mode": self.MODE, "profile": self.profile, "run": self.run_name,
                "ledger": {"count": self.ledger.count, "head": self.ledger.head[:16]},
                "criteria": self.criteria if self.life else {"unavailable": "sirisys_measures.py not found"},
                "criteria_every": CRITERIA_EVERY,
                "framework": S.__sirisys_file__, "framework_version": S.__sirisys_version__}

    def drain(self) -> list[dict]:
        """Every snapshot not yet delivered, oldest first; the queue is left empty."""
        with self._queue_lock:
            pending = list(self._queue)
            self._queue.clear()
        return pending

    def listen(self, loop) -> asyncio.Event:
        """An event that `loop` sees set each time a snapshot is queued."""
        event = asyncio.Event()
        with self._queue_lock:
            self._listeners.add((loop, event))
        return event

    def stop_listening(self, loop, event) -> None:
        with self._queue_lock:
            self._listeners.discard((loop, event))

    def shutdown(self) -> None:
        """Stop cycling, save the instance and close its ledger."""
        self.running = self.alive = False
        with self._cycle_lock:
            self.save()
            self.ledger.close()
            self._close_records()
        log.info("Experiment state saved to %s", self.run_dir)


# ── REPLAY (at the top of this file) ─────────────────────────────────────

class RecordedFailure(Exception):
    """A call that failed in the run fails again in its replay, as it failed: the same
    console line, the same entry in the model watch."""

    def __init__(self, failure: dict):
        super().__init__(failure.get("error", ""))
        self._repr = failure.get("repr")

    def __repr__(self) -> str:
        return self._repr or super().__repr__()


class RecordedModel(S.LLMIntermediary):
    """The model of a recorded run: each call is answered as it was answered in the run,
    in the same order, from its answers.jsonl, and no model is asked. Only _complete,
    where an answer comes back, is replaced: the calls themselves (the thread, the
    console line of a failure, the watch) run as they ran. Without a record of the
    answers it is a run without a model."""

    def __init__(self, header: dict | None, answers: dict):
        self.header, self.recorded = header or {}, answers
        self._pending = deque()
        self.unanswered = self.unasked = 0  # calls the run did not make; answers the replay did not ask for
        super().__init__(backend=self.header.get("backend") or "none")
        self.model = self.header.get("model")

    def _init(self) -> None:
        self._available = bool(self.header.get("available"))

    @property
    def is_local(self) -> bool:
        return True

    def begin(self, cycle: int) -> None:
        """The answers of `cycle`, in the order the run asked for them."""
        self._pending = deque(self.recorded.get(cycle, ()))

    def end(self) -> None:
        self.unasked += len(self._pending)
        self._pending.clear()

    def _complete(self, temperature: float) -> str:
        if not self._pending:
            self.unanswered += 1
            return ""
        answer = self._pending.popleft()
        if isinstance(answer, dict):
            raise RecordedFailure(answer)
        return answer


class RunLedger:
    """A run's own ledger, read as its replay goes: the chain hash of proof n, n never going back."""

    def __init__(self, path: Path):
        self._lines = S._ledger_lines(path)     # every proof in order, across its segments
        self.read, self._last = 0, None

    def chain_hash(self, n: int) -> str | None:
        """The chain hash of the run's proof n (0-based); None where its ledger does not reach."""
        while self.read <= n:
            line, error = next(self._lines, (None, "ended"))
            if error:
                return None
            try:
                self._last = json.loads(line)["chain_hash"]
            except (ValueError, KeyError):      # a line cut short: the run is writing it
                return None
            self.read += 1
        return self._last if self.read == n + 1 else None


def replay_refused(source: Path) -> str | None:
    """Why a folder cannot be replayed, or None."""
    from importlib.util import find_spec
    if not find_spec("sirisys_measures"):
        return "sirisys_measures.py not found beside this server: a replay reads the run's record with it"
    if not (source / "ledger.jsonl").exists():
        return f"{source} is not a run folder: it has no ledger.jsonl"
    percepts = source / "percepts.jsonl"
    if not percepts.exists():
        return (f"{source.name} has no percepts.jsonl: it was recorded before STRATA kept what a life "
                f"perceives, so it cannot be replayed")
    if not percepts.stat().st_size:
        return f"{source.name} has not recorded a cycle yet"
    return None


def find_run(spec: str, runs_dir: Path) -> Path:
    """The run folder --replay names: a path, a folder of runs_dir, or 'last' (the latest
    run there that has recorded a cycle). A file inside a run folder names its folder."""
    if spec == "last":
        runs = sorted((p for p in runs_dir.glob("*/percepts.jsonl") if p.stat().st_size),
                      key=lambda p: p.parent.name)
        if not runs:
            raise SystemExit(f"\n  No run in {runs_dir} has recorded a cycle yet.\n")
        return runs[-1].parent
    path = Path(spec).expanduser()
    if not path.exists() and (runs_dir / spec).exists():
        path = runs_dir / spec
    return path.parent if path.is_file() else path


class ReplayEngine(ExperimentEngine):
    """A recorded run lived again (REPLAY): the percepts of its percepts.jsonl, the
    answers of its answers.jsonl, a ledger in memory compared with the run's own,
    and nothing written anywhere. Each play is an instance of its own for the view:
    the run's name, then '#2', '#3'… as it is played again."""

    MODE = "replay"
    PAUSES_FOR_MODEL = False    # the watch shows what it saw in the run; a replay does not stop for it

    def __init__(self, source: Path, delay_ms: int):
        self.source, self.plays = Path(source), 0
        self._load()
        # The profile matters only with a model (narration); a run that recorded no
        # answers is replayed without one
        super().__init__(None, delay_ms, self.source.parent, (self.header or {}).get("profile") or "standard")

    def _load(self) -> None:
        """The run's record, as far as it goes now."""
        from sirisys_measures import AnswerRecord, PerceptRecord
        self.recorded = PerceptRecord.read(S, self.source / PerceptRecord.FILE)
        answers = self.source / AnswerRecord.FILE
        self.header, self.answered = AnswerRecord.read(answers) if answers.exists() else (None, {})
        if self.header is None and self._saved_without_labels():
            self.header = {"backend": "none", "model": None, "available": False}   # nothing to record

    def _saved_without_labels(self) -> bool:
        """Whether a run recorded before answers.jsonl ran without a model: its saved state
        holds no label a model gave. Without a saved state it is not known."""
        try:
            state = json.loads((self.source / "state.json").read_text(encoding="utf-8"))
            return not any(c.get("label") for c in state["field"]["constructs"])
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return False

    def _new_instance(self) -> None:
        if self.plays:                          # the first play reads what __init__ has just read
            self._load()
        with self._queue_lock:
            self.run_dir, self.plays, self._history = self.source, self.plays + 1, []
        self.ledger = S.set_ledger(S.ProofLedger(None))         # in memory: a replay writes nothing
        self._begin(RecordedModel(self.header, self.answered))
        self.theirs = RunLedger(self.source / "ledger.jsonl")
        self.lived, self.compared, self.differs_at, self.ended = -1, -1, None, False
        log.info("Replay %d of %s: %d cycles recorded, %s", self.plays, self.source.name, len(self.recorded),
                 self.words)

    @property
    def run_name(self) -> str:
        return self.source.name if self.plays == 1 else f"{self.source.name} #{self.plays}"

    @property
    def words(self) -> str:
        """What the replay has of the run's model."""
        if self.header is None:
            return "the model's answers not recorded"
        return "with the model's answers" if self.header.get("available") else "without a model"

    def _waiting_for_view(self) -> bool:
        return len(self._queue) >= REPLAY_AHEAD

    def _before_cycle(self, profile: dict) -> list:
        self.ss.llm.begin(self.cycle)
        return self.recorded[self.cycle]

    def _after_cycle(self, r: dict) -> None:
        self.ss.llm.end()
        self.lived = self.cycle
        self._compare()
        if self.cycle + 1 >= len(self.recorded) and not self._went_on():
            self.ended, self.running = True, False
            log.info("Replay %d of %s ended at cycle %d: %s", self.plays, self.source.name, self.cycle,
                     self._verdict())

    def _went_on(self) -> bool:
        """Whether the run has recorded more cycles since it was read (it is still live)."""
        known = len(self.recorded)
        self._load()
        if len(self.recorded) <= known:
            return False
        self.ss.llm.recorded = self.answered
        self.theirs = RunLedger(self.source / "ledger.jsonl")
        return True

    def _compare(self) -> None:
        """The ledger as this cycle leaves it, against the run's at the same proof."""
        if self.differs_at is not None:
            return
        n = self.ledger.count - 1
        theirs = self.theirs.chain_hash(n)
        if theirs is not None and theirs != self.ledger.head:
            # once more from its start: a live run may have closed a segment under the reader
            self.theirs = RunLedger(self.source / "ledger.jsonl")
            theirs = self.theirs.chain_hash(n)
        if theirs == self.ledger.head:
            self.compared = self.cycle
        elif theirs is not None:
            self.differs_at = self.cycle

    def _verdict(self) -> str:
        if self.differs_at is not None:
            return f"the ledger departs from the run's at cycle {self.differs_at}"
        if self.lived >= 0 and self.compared == self.lived:
            return "the same ledger as the run"
        return f"the same ledger as the run through cycle {self.compared}; the run's ledger does not reach further"

    def _replay(self) -> dict:
        """How the replay stands: its run, how far it is the same, whether every answer was in its place."""
        llm = self.ss.llm
        same = (False if self.differs_at is not None
                else True if self.lived >= 0 and self.compared == self.lived else None)
        return {"of": self.source.name, "play": self.plays, "cycles": len(self.recorded),
                "answers": self.header is not None, "ended": self.ended,
                "same_ledger": same, "compared_through": self.compared, "differs_at": self.differs_at,
                "unanswered": llm.unanswered, "unasked": llm.unasked}

    def _snapshot(self, r: dict, console: list[str], before: set, question_full: str | None) -> dict:
        return {**super()._snapshot(r, console, before, question_full), "replay": self._replay()}

    def status(self) -> dict:
        status = super().status()
        status["stream"] = "recorded"
        status["model"]["recorded"] = self.header is not None
        return {**status, "replay": self._replay()}

    def control(self, action: str, **options) -> dict:
        """As the experiment's, but Reset, and Play once it has ended, play it again
        from its first cycle; Step at the end has nothing to step."""
        if action == "reset" or (action == "play" and self.ended):
            self.running = False
            with self._cycle_lock:
                self._new_instance()
                with self._queue_lock:
                    self._queue.clear()
            self.running = action == "play"
            return {"ok": True, "reset": True, "running": self.running, "play": self.plays}
        if action == "step" and self.ended:
            return {"ok": False, "error": "the replay has ended: Play or Reset plays it again"}
        return super().control(action, **options)

    def shutdown(self) -> None:
        """Stop cycling: a replay has nothing to save."""
        self.running = self.alive = False
        with self._cycle_lock:
            log.info("Replay of %s stopped at cycle %d; nothing was written", self.source.name, self.cycle)


def _options(body) -> dict:
    """A control request's options: a JSON object, without its own 'action' key."""
    return {k: v for k, v in body.items() if k != "action"} if isinstance(body, dict) else {}


def _reply(engine, message):
    """The ack for a WebSocket message {"action": ..., options}; None for anything else."""
    try:
        payload = json.loads(message)
    except ValueError:
        return None
    if not isinstance(payload, dict) or not payload.get("action"):
        return None
    result = engine.control(payload["action"], **_options(payload))
    return {"type": "ack", **result, "status": engine.status()}


def create_app(engine):
    """The web interface of one engine (INTERFACE, at the top of this file)."""
    # Only the experiment mode needs the web framework: importing this file does not
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, JSONResponse

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        yield
        engine.shutdown()                                       # Ctrl+C: save the instance

    app = FastAPI(title="SIRISYS experiment", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    def index():
        page = HERE / "Sirisys_Live_Visualizer.html"
        if not page.exists():
            return HTMLResponse(f"<h1>{page.name} not found</h1>", status_code=500)
        return HTMLResponse(page.read_text(encoding="utf-8"))

    @app.get("/api/status")
    def api_status():
        return JSONResponse(engine.status())

    @app.get("/api/snapshot")
    def api_snapshot():
        return JSONResponse(engine.drain())

    @app.get("/api/history")
    def api_history():
        return JSONResponse(engine.history())

    @app.post("/api/control/{action}")
    async def api_control(action: str, request: Request):
        try:
            body = await request.json()
        except ValueError:                                      # no body, or not JSON
            body = {}
        return JSONResponse(engine.control(action, **_options(body)))

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        loop = asyncio.get_running_loop()
        snapshot_ready = engine.listen(loop)
        receiving = None                        # the pending read of the client's next message
        try:
            status = engine.status()
            await ws.send_json({"type": "status", **status})
            told_running = status["running"]    # what the client was last told
            while True:
                snapshot_ready.clear()          # before draining, so nothing queued after it is missed
                for snapshot in engine.drain():
                    await ws.send_json(snapshot)
                if engine.running != told_running:
                    # Started or stopped otherwise: by itself (a step ended, the model watch
                    # tripped, a cycle raised) or by another client
                    status = engine.status()
                    told_running = status["running"]
                    await ws.send_json({"type": "status", **status})
                receiving = receiving or asyncio.create_task(ws.receive_text())
                waking = asyncio.create_task(snapshot_ready.wait())
                done, _ = await asyncio.wait({receiving, waking}, timeout=1.0,
                                             return_when=asyncio.FIRST_COMPLETED)
                waking.cancel()
                if receiving in done:
                    finished, receiving = receiving, None
                    try:
                        message = finished.result()
                    except (WebSocketDisconnect, RuntimeError):
                        break           # the client is gone: stop, rather than spin on a dead socket
                    reply = _reply(engine, message)
                    if reply:
                        told_running = reply["status"]["running"]
                        await ws.send_json(reply)
        except WebSocketDisconnect:
            pass                                                # the client left while we were sending
        finally:
            if receiving:
                receiving.cancel()
            engine.stop_listening(loop, snapshot_ready)

    return app


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="SIRISYS — experiment mode, and the replay of a run, "
                                             "served to the live visualizer")
    ap.add_argument("--play", action="store_true", help="start cycling at once")
    ap.add_argument("--stream", type=_stream_arg, default=None,
                    help="percepts: 'live' (this machine, the default) or an integer N, the "
                         "reproducible synthetic stream N (the framework has no PRNG)")
    ap.add_argument("--delay-ms", type=int, default=80, help="pause between cycles (default 80)")
    ap.add_argument("--profile", choices=sorted(PROFILES), default=None,
                    help="'minimal': no narration and no time-of-day percept (default 'standard')")
    ap.add_argument("--replay", metavar="RUN",
                    help="watch a recorded run again: its folder in sirisys_runs/, or 'last' (REPLAY)")
    ap.add_argument("--host", default="127.0.0.1",
                    help="address to listen on (default 127.0.0.1: this machine only)")
    ap.add_argument("--port", type=int, default=None, help="default 8000; 8001 for a replay")
    return ap.parse_args(argv)


def make_engine(args):
    """The engine the arguments ask for: an experiment instance, or the replay of a run."""
    runs = HERE / "sirisys_runs"
    if args.replay:
        if args.stream is not None or args.profile:
            raise SystemExit("\n  A replay lives the run on its own percepts and profile: "
                             "leave out --stream and --profile.\n")
        source = find_run(args.replay, runs)
        refused = replay_refused(source)
        if refused:
            raise SystemExit(f"\n  {refused}.\n")
        return ReplayEngine(source, args.delay_ms)
    if live_refused(args.stream):
        raise SystemExit(f"\n  {live_refused(args.stream)} (--stream N).\n")
    return ExperimentEngine(args.stream, args.delay_ms, runs, args.profile or "standard")


def serve(args) -> None:
    """Create the engine and serve it until Ctrl+C."""
    from importlib.util import find_spec
    missing = [name for name in ("fastapi", "uvicorn") if not find_spec(name)]
    if missing or not (find_spec("websockets") or find_spec("wsproto")):
        raise SystemExit(f"\n  MISSING: {', '.join(missing) or 'websocket support'} — "
                         f"pip3 install -r requirements.txt\n")
    import uvicorn

    engine = make_engine(args)
    engine.running = args.play
    app = create_app(engine)
    port = args.port or PORTS[engine.MODE]
    shown = "127.0.0.1" if args.host in ("0.0.0.0", "::", "") else args.host
    if engine.MODE == "replay":
        about = f"replay of {engine.source.name} · {len(engine.recorded)} cycles recorded, {engine.words}"
    else:
        about = f"run {engine.run_dir.name}"
    print(f"\n  SIRISYS — {engine.MODE} · http://{shown}:{port}"
          f"\n  framework {S.__sirisys_file__} · {about}"
          f"\n  {'cycling' if engine.running else 'paused — press Play'} · Ctrl+C to stop\n")
    uvicorn.run(app, host=args.host, port=port, log_level="warning")


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    serve(parse_args(argv))


if __name__ == "__main__":
    main()
