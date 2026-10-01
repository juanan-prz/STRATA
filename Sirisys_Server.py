"""
SIRISYS Live Server
====================

A small FastAPI + WebSocket server that runs Sirisys cycle-by-cycle and
streams the field state to a browser visualizer in real time.

USAGE (terminal):
    python3 Sirisys_Server.py                      # experiment mode (default)
    python3 Sirisys_Server.py --mode continuous    # the long-running instance
    python3 Sirisys_Server.py --mode continuous --play
                                                   # ...and start cycling at once,
                                                   # no browser needed

TWO MODES — one file, so the two can never drift apart:

  experiment   Every start is a NEW instance with its own timeline from T0.
               Use this while calibrating. Saves to sirisys_v12_state.json
               on stop, readable by the static visualizer.

  continuous   ONE instance that lives across restarts. It resumes exactly
               where its record ends, saves after every cycle with a
               crash-safe write, and never rolls its time back. Reset does
               not erase it: the instance is archived in sirisys_archive/
               and a new one begins. Its record is a separate file,
               sirisys_living_state.json, so running experiments can never
               overwrite it.

  Corpus basis (DeOS Compiler Guide): identity "persists across recursion,
  runtime, and error" (p.9); time is "strictly non-reversible ... Any recovery
  mechanism must preserve the monotonic chain of witnesses" and "even under
  failure, recovery must guarantee this ordering" (p.24); "Nothing
  disappears" (p.202). A new instance starting at T0 rolls back nobody's
  time; restarting an existing instance from T0 does.

Then open the URL printed in the terminal (default: http://localhost:8000)
in your browser. Press Play in the visualizer to start the simulation.

REQUIREMENTS:
    pip install fastapi uvicorn numpy psutil

FILES THAT MUST SIT IN THE SAME FOLDER:
    Sirisys_Server.py
    sirisys_loader.py               finds the framework + the canonical cycle
    Sirisys_Framework_vX_Y.py       the newest version is used automatically
    Sirisys_Live_Visualizer.html

If you also want LLM-active runs:
    pip install anthropic
    export ANTHROPIC_API_KEY="sk-ant-..."

WHAT IT DOES:
    - experiment mode: boots a fresh field every start (a new instance)
    - continuous mode: resumes the living instance; see TWO MODES above
    - Exposes a WebSocket at /ws that streams cycle snapshots
    - Serves the HTML visualizer at /
    - Accepts control messages: play / pause / step / stop / reset

NOTES:
    - The simulation runs in its own thread; the FastAPI event loop is not blocked
    - Each cycle takes ~60–200 ms (depending on whether LLM is active)
    - The client polls/streams; no file system intermediary needed
    - The same state file (sirisys_v12_state.json) is still written on stop,
      so the static visualizer (load JSON manually) continues to work
    - Each cycle is run by sirisys_loader.run_cycle(), the same function
      run_report.py uses, verified identical to the framework's own run().
      The live view and the measurements therefore show the same system.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
import random
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# Make sure we can import the Sirisys module that sits next to this file.
HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(HERE))

# The framework is located by version, not by exact file name: the newest
# Sirisys_Framework_vX_Y.py next to this file is loaded (see sirisys_loader.py).
# New framework versions need no change here.
from sirisys_loader import (load_framework, make_session, run_cycle,  # noqa: E402
                            resume_session, save_session_atomic,
                            archive_state, ContinuityError)
import argparse  # noqa: E402
import os  # noqa: E402

s = load_framework(HERE)


def _resolve_mode() -> str:
    """--mode on the command line, else SIRISYS_MODE, else 'experiment'."""
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--mode", choices=["experiment", "continuous"])
    ap.add_argument("--play", action="store_true")
    known, _ = ap.parse_known_args()
    mode = known.mode or os.environ.get("SIRISYS_MODE", "experiment")
    if mode not in ("experiment", "continuous"):
        raise SystemExit(f"unknown mode: {mode}")
    autoplay = known.play or os.environ.get("SIRISYS_PLAY") == "1"
    return mode, autoplay


# --play starts cycling at once, with no browser needed — what a living
# instance needs after a restart. Without it the server waits for Play.
MODE, AUTOPLAY = _resolve_mode()
EXPERIMENT_STATE = HERE / "sirisys_v12_state.json"
LIVING_STATE     = HERE / "sirisys_living_state.json"
ARCHIVE_DIR      = HERE / "sirisys_archive"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("sirisys_live")

# ─────────────────────────────────────────────────────────────────────────────
#  Engine wrapper — runs Sirisys cycles in a background thread
# ─────────────────────────────────────────────────────────────────────────────

class SirisysEngine:
    """
    Wraps a Sirisys session and exposes start/pause/step/reset controls.
    Runs the cycle loop in a worker thread; the main asyncio loop is never
    blocked. Each cycle, the engine pushes a snapshot to an internal queue
    that the WebSocket task drains and forwards to the browser.
    """

    def __init__(self, seed: int = 42, cycle_delay_ms: int = 80,
                 mode: str = "experiment"):
        self.mode             = mode
        self.resumed_from     = None                 # continuous mode only
        self.last_T           = None                 # monotonicity guard
        self.seed             = seed
        self.cycle_delay_ms   = cycle_delay_ms       # gap between cycles (UI pacing)
        self.cycle            = 0
        self.running          = False                # play / pause flag
        self.alive            = True                 # global stop signal
        self.step_once        = False                # single-step request
        self._lock            = threading.Lock()   # guards the snapshot queue
        # Held for the whole duration of a cycle. reset() and the shutdown save
        # take it too, so neither can swap or serialise the field while a cycle
        # is half-way through mutating it. Lock order is always
        # _cycle_lock -> _lock, so the two cannot deadlock.
        self._cycle_lock      = threading.Lock()
        self._snapshot_queue: list[dict] = []        # pushed by worker, drained by WS task
        self._broadcast_event = asyncio.Event()      # set whenever new snapshots are ready
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None  # set on first WS

        # Engine state — built lazily so we can reset cleanly
        self._init_session()
        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._worker_thread.start()

    def _init_session(self, fresh: bool = False) -> None:
        random.seed(self.seed)
        np.random.seed(self.seed)
        session, start_cycle = (None, 0)
        if self.mode == "continuous" and not fresh:
            # Raises ContinuityError rather than silently starting over.
            session, start_cycle = resume_session(s, LIVING_STATE)
        if session is None:
            with contextlib.redirect_stdout(io.StringIO()):
                session = make_session(s)
            self.resumed_from = None
        else:
            self.resumed_from = session.resumed_from
        self.session = session
        self.clock        = self.session.clock
        self.field        = self.session.field
        self.llm          = self.session.llm
        self.sombunal     = self.session.sombunal
        self.concordancy  = self.session.concordancy
        self.tetralemma   = self.session.tetralemma
        self.cussive      = self.session.cussive
        self.uco          = self.session.uco
        self.cycle = start_cycle
        self.last_T = tuple(self.clock.T)
        # termination proofs already reported (so each snapshot lists only new ones)
        self._term_seen = len(self.field.termination_log)
        if self.resumed_from:
            log.info("Living instance RESUMED from %s at cycle %d, T=%s (framework %s)",
                     self.resumed_from, self.cycle, list(self.clock.T),
                     s.__sirisys_file__)
            gap = getattr(self.session, "recovery_gap_cycles", 0)
            if gap:
                log.warning("Recovered from the previous copy: %d cycle(s) of record "
                            "were lost. Time was moved forward past the last T this "
                            "instance reached; the lost cycles are a gap, not re-lived.",
                            gap)
        else:
            log.info("Sirisys session initialized (mode=%s, seed=%d, framework %s)",
                     self.mode, self.seed, s.__sirisys_file__)
        if self.mode == "continuous":
            save_session_atomic(s, LIVING_STATE, self.session, self.cycle)

    # ──── Worker loop ─────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        """Run forever; advance one cycle whenever play OR a single step is requested."""
        while self.alive:
            if not (self.running or self.step_once):
                time.sleep(0.02)
                continue
            try:
                self._step_one_cycle()
            except Exception as ex:                  # noqa: BLE001
                log.exception("Cycle %d raised: %s", self.cycle, ex)
                self.running = False                 # auto-pause on error
            finally:
                if self.step_once:
                    self.step_once = False
                    self.running   = False           # single-step does not auto-continue
            time.sleep(max(self.cycle_delay_ms, 0) / 1000.0)

    def _step_one_cycle(self) -> None:
        """One Sirisys cycle, plus a snapshot push.

        The cycle is the canonical one (sirisys_loader.run_cycle), identical to
        the framework's run(): it includes the Intermediary's narration and the
        Sombunal questions, which the previous inline loop omitted. Those
        questions are the one channel through which an active model adds new
        constructs to the field, so without them the live view showed a
        different system from the one being measured.
        """
        with self._cycle_lock:
            # Capture per-cycle stdout so it can be streamed (cussive lines,
            # narration, Sombunal questions)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                r = run_cycle(s, self.session, self.cycle)
            log_lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]

            T_now = tuple(self.clock.T)
            if self.last_T is not None and T_now <= self.last_T:
                raise ContinuityError(
                    f"internal time did not advance: {list(self.last_T)} -> {list(T_now)}")
            self.last_T = T_now

            snapshot = self._snapshot(r, log_lines)
            with self._lock:
                self._snapshot_queue.append(snapshot)
            self.cycle += 1
            if self.mode == "continuous":
                # Saved after EVERY cycle, like the framework's own run(), so the
                # persisted record never lags what an observer has already seen.
                save_session_atomic(s, LIVING_STATE, self.session, self.cycle)

        # Wake the WebSocket task
        if self._main_loop is not None:
            self._main_loop.call_soon_threadsafe(self._broadcast_event.set)

    def _slim_field(self) -> dict:
        """
        Compact field representation tailored for the live visualizer.

        The full `field.to_dict()` includes complete proof_chains for every
        construct, which grows monotonically and bloats snapshots to >250 KB
        after ~100 cycles. The visualizer only needs:
          - construct: name, layer (int), born_at, witness, umbragiac_score,
                       lagrange, plus the LENGTH of the proof chain (not its
                       content)
          - edge:      src, tgt, state, weight (the rest is invisible in
                       topology and not used in tooltips)
        This keeps each snapshot under ~50 KB regardless of run length.
        """
        constructs = []
        is_cf = getattr(s, "is_conflict_construct", None)
        for c in self.field.constructs.values():
            constructs.append({
                "name":            c.name,
                "layer":           c.layer.value,
                "born_at":         list(c.born_at),
                "witness":         c.witness,
                "umbragiac_score": round(c.umbragiac_score, 4),
                "lagrange":        c.lagrange.name if c.lagrange else None,
                # Count only — the frontend displays it. Lifetime count (v12.9),
                # so it stays exact after a continuous-mode resume trims chains.
                "proof_chain":     getattr(c, "proofs_total", len(c.proof_chain)),
                # ── additive: what the inspector needs to analyse a construct ──
                "vc":              round(self.field.compute_anchoring_weight(c), 4),
                "mode":            self.field.compute_existence_mode(c),
                "conflict":        bool(is_cf(c)) if is_cf else False,
                "banked":          round(getattr(c, "recursion_exchanged", 0.0), 3),
            })
        edges = []
        for e in self.field.edges:
            edges.append({
                "src":    e.src,
                "tgt":    e.tgt,
                "state":  e.state.name if hasattr(e.state, 'name') else str(e.state),
                "weight": round(e.weight, 4),
            })
        return {"constructs": constructs, "edges": edges}

    def _snapshot(self, r: dict, log_lines) -> dict:
        """A compact JSON-serializable snapshot of the current field.

        Every key the visualizer already reads is unchanged. New keys are
        additive and ignored by clients that do not use them.
        """
        emergent, promoted = r["emergent"], r["promoted"]
        instability = r["instability"]
        field = self.field

        # Constructs that concluded this cycle, read from their TERMINATE proofs
        # (Compiler Guide pp.203-204: "An identity never vanishes silently. It
        # concludes."). The engine only prints a count; the proofs say who.
        new_terms = field.termination_log[self._term_seen:]
        self._term_seen = len(field.termination_log)
        concluded = []
        for tp in new_terms:
            meta = getattr(tp, "meta", None) or {}
            concluded.append({
                "name":  meta.get("name"),
                "layer": meta.get("final_layer"),
                "mode":  meta.get("final_mode"),
                "vc":    meta.get("final_Vc"),
            })
        clock = self.clock
        era, offset = clock.T

        # Mode counts over current constructs
        modes  = {"OMEGA": 0, "LEMNISCATE": 0, "NEUTRAL": 0}
        layers = {"NULL_00": 0, "UMBRA_0": 0, "UNIT_1": 0, "APPARENT": 0}
        for cs in field.constructs.values():
            m = field.compute_existence_mode(cs)
            if m in modes: modes[m] += 1
            layers[cs.layer.name] = layers.get(cs.layer.name, 0) + 1

        telem_last = self.concordancy.pool_telemetry[-1] if self.concordancy.pool_telemetry else {}

        return {
            "type":          "cycle",
            "cycle":         self.cycle,
            "T":             [era, offset],
            "constructs":    len(field.constructs),
            "edges":         len(field.edges),
            "apparents":     len(field.apparent_log),
            "terminations":  len(field.termination_log),
            "instability":   round(instability, 4),
            "modes":         modes,
            "layers":        layers,
            "events":        len(emergent),
            "emergent_names": emergent,
            "promoted":      len(promoted),
            "promoted_names": promoted,
            "llm_used":      r["llm_used"],
            "log":           log_lines,
            # ── additive, v12.8 ──
            "conflicts":      r["conflict_count"],
            "closures":       r["closures"],
            "both_edges":     r["both_count"],
            "reincarnations": getattr(field, "reincarnations", 0),
            "action":         r["action"],
            "narration":      r["narration"],
            "question":       r["question"],
            "concluded":      concluded,
            "telemetry":     telem_last,
            "field":         self._slim_field(),   # compact state for the topology view
        }

    # ──── Controls (called from FastAPI) ────────────────────────────────

    def control(self, action: str, **kwargs) -> dict:
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
            seed = int(kwargs.get("seed", self.seed))
            self.running = False
            self.seed    = seed
            archived = None
            with self._cycle_lock:            # never swap the field mid-cycle
                if self.mode == "continuous":
                    # "Nothing disappears" (p.202): the instance is archived,
                    # not erased, and a NEW instance begins its own timeline.
                    save_session_atomic(s, LIVING_STATE, self.session, self.cycle)
                    archived = archive_state(LIVING_STATE, ARCHIVE_DIR)
                    log.info("Living instance archived to %s", archived)
                self._init_session(fresh=True)
                with self._lock:
                    self._snapshot_queue.clear()
            return {"ok": True, "reset": True, "seed": seed,
                    "archived": str(archived.name) if archived else None}
        if action == "speed":
            ms = int(kwargs.get("cycle_delay_ms", 80))
            self.cycle_delay_ms = max(0, ms)
            return {"ok": True, "cycle_delay_ms": self.cycle_delay_ms}
        return {"ok": False, "error": f"unknown action: {action}"}

    def status(self) -> dict:
        era, offset = self.clock.T
        return {
            "running":         self.running,
            "cycle":           self.cycle,
            "T":               [era, offset],
            "seed":            self.seed,
            "cycle_delay_ms":  self.cycle_delay_ms,
            "llm_active":      getattr(self.llm, '_available', False),
            "mode":            self.mode,
            "resumed_from":    self.resumed_from,
            "recovery_gap_cycles": getattr(self.session, "recovery_gap_cycles", 0),
            "framework":       s.__sirisys_file__,
            "framework_version": s.__sirisys_version__,
        }

    # ──── Stream draining (called from the WS task) ──────────────────────

    def drain_snapshots(self) -> list[dict]:
        with self._lock:
            out, self._snapshot_queue = self._snapshot_queue, []
        return out

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._main_loop is None:
            self._main_loop = loop

    def shutdown(self) -> None:
        self.running = False
        self.alive   = False


# ─────────────────────────────────────────────────────────────────────────────
#  FastAPI app
# ─────────────────────────────────────────────────────────────────────────────

# Path where the engine persists its state when the server stops.
STATE_PATH = LIVING_STATE if MODE == "continuous" else EXPERIMENT_STATE

try:
    engine = SirisysEngine(mode=MODE)
except ContinuityError as ex:
    raise SystemExit(f"\n  CONTINUITY ERROR — the server will not start.\n  {ex}\n")
if AUTOPLAY:
    engine.running = True


@asynccontextmanager
async def lifespan(app):
    # Startup — engine is already constructed above; nothing to do.
    yield
    # Shutdown — stop the worker and persist the final state so the classic
    # visualizer can load it post-hoc.
    engine.shutdown()
    try:
        # Wait for any cycle in flight, so the field is not serialised mid-mutation
        with engine._cycle_lock, contextlib.redirect_stdout(io.StringIO()):
            if engine.mode == "continuous":
                save_session_atomic(s, LIVING_STATE, engine.session, engine.cycle)
            else:
                s.save_state(STATE_PATH, engine.field, engine.clock, engine.llm,
                             engine.cycle, engine.concordancy)
        log.info("Final state persisted to %s", STATE_PATH)
    except Exception as ex:                                # noqa: BLE001
        log.warning("Could not persist final state: %s", ex)


app = FastAPI(title="SIRISYS live", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Serve the live visualizer."""
    html_path = HERE / "Sirisys_Live_Visualizer.html"
    if not html_path.exists():
        return HTMLResponse(
            "<h1>Sirisys_Live_Visualizer.html not found</h1>"
            "<p>Place it next to Sirisys_Server.py and reload.</p>",
            status_code=500,
        )
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/status")
def api_status() -> JSONResponse:
    return JSONResponse(engine.status())


@app.post("/api/control/{action}")
async def api_control(action: str) -> JSONResponse:
    return JSONResponse(engine.control(action))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    loop = asyncio.get_running_loop()
    engine.attach_loop(loop)
    log.info("WebSocket client connected")

    # Send initial status + any pending snapshots
    await ws.send_json({"type": "status", **engine.status()})
    for snap in engine.drain_snapshots():
        await ws.send_json(snap)

    try:
        while True:
            # Drain whatever the worker produced
            for snap in engine.drain_snapshots():
                await ws.send_json(snap)

            # Wait for next batch OR a control message from the client
            recv_task = asyncio.create_task(ws.receive_text())
            event_task = asyncio.create_task(engine._broadcast_event.wait())
            done, pending = await asyncio.wait(
                {recv_task, event_task},
                timeout=1.0,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()

            if recv_task in done:
                try:
                    payload = json.loads(recv_task.result())
                except Exception:
                    continue
                action = payload.get("action")
                if action:
                    result = engine.control(action, **{k: v for k, v in payload.items() if k != "action"})
                    await ws.send_json({"type": "ack", **result, "status": engine.status()})

            if event_task in done:
                engine._broadcast_event.clear()
    except WebSocketDisconnect:
        log.info("WebSocket client disconnected")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def _websocket_backend_missing() -> bool:
    """uvicorn serves WebSockets only if 'websockets' or 'wsproto' is installed.

    Without either, the server starts normally but every connection to /ws is
    refused, so the live visualizer stays on "disconnected" forever with no
    clear reason. Checked up front so the failure is never silent.
    """
    import importlib.util
    return not (importlib.util.find_spec("websockets") or importlib.util.find_spec("wsproto"))


if __name__ == "__main__":
    HOST = "127.0.0.1"
    PORT = 8000
    if _websocket_backend_missing():
        raise SystemExit(
            "\n  MISSING WEBSOCKET SUPPORT — the live visualizer could not connect.\n"
            "  Install the dependencies, then start the server again:\n"
            "      pip3 install -r requirements.txt\n"
            "  (or just:  pip3 install websockets)\n")
    print()
    print("  ╭" + "─" * 60 + "╮")
    print(f"  │  SIRISYS LIVE — http://{HOST}:{PORT}".ljust(62) + " │")
    print(f"  │  framework: {s.__sirisys_file__}".ljust(62) + " │")
    mode_line = (f"  │  mode: CONTINUOUS — living instance, resumed at cycle {engine.cycle}"
                 if engine.mode == "continuous" and engine.resumed_from else
                 f"  │  mode: CONTINUOUS — new living instance"
                 if engine.mode == "continuous" else
                 f"  │  mode: experiment — fresh instance")
    print(mode_line.ljust(62) + " │")
    print((f"  │  cycling: {'YES (started with --play)' if engine.running else 'paused — press Play'}").ljust(62) + " │")
    print("  │".ljust(62) + " │")
    print(f"  │  open the URL above in your browser".ljust(62) + " │")
    print(f"  │  press Ctrl+C in this terminal to stop".ljust(62) + " │")
    print("  ╰" + "─" * 60 + "╯")
    print()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
