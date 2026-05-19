"""
SIRISYS Live Server
====================

A small FastAPI + WebSocket server that runs Sirisys cycle-by-cycle and
streams the field state to a browser visualizer in real time.

USAGE (terminal):
    python Sirisys_Server.py

Then open the URL printed in the terminal (default: http://localhost:8000)
in your browser. Press Play in the visualizer to start the simulation.

REQUIREMENTS:
    pip install fastapi uvicorn

If you also want LLM-active runs:
    pip install anthropic
    export ANTHROPIC_API_KEY="sk-ant-..."

WHAT IT DOES:
    - Boots Sirisys (loads previous state if `sirisys_v12_state.json` exists)
    - Exposes a WebSocket at /ws that streams cycle snapshots
    - Serves the HTML visualizer at /
    - Accepts control messages: play / pause / step / stop / reset

NOTES:
    - The simulation runs in its own thread; the FastAPI event loop is not blocked
    - Each cycle takes ~60–200 ms (depending on whether LLM is active)
    - The client polls/streams; no file system intermediary needed
    - The same state file (sirisys_v12_state.json) is still written on stop,
      so the existing visualizer (load JSON manually) continues to work
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

import Sirisys_Framework_v12_1 as s  # noqa: E402

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

    def __init__(self, seed: int = 42, cycle_delay_ms: int = 80):
        self.seed             = seed
        self.cycle_delay_ms   = cycle_delay_ms       # gap between cycles (UI pacing)
        self.cycle            = 0
        self.running          = False                # play / pause flag
        self.alive            = True                 # global stop signal
        self.step_once        = False                # single-step request
        self._lock            = threading.Lock()
        self._snapshot_queue: list[dict] = []        # pushed by worker, drained by WS task
        self._broadcast_event = asyncio.Event()      # set whenever new snapshots are ready
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None  # set on first WS

        # Engine state — built lazily so we can reset cleanly
        self._init_session()
        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._worker_thread.start()

    def _init_session(self) -> None:
        random.seed(self.seed)
        np.random.seed(self.seed)
        self.clock        = s.InternalClock()
        self.field        = s.ConcordancyField(self.clock)
        self.llm          = s.LLMIntermediary()
        self.sombunal     = s.Sombunal()
        self.concordancy  = s.ConcordancyOperator(self.llm, self.sombunal)
        self.tetralemma   = s.TetralemmaEngine()
        self.cussive      = s.CussiveCollapseEngine(threshold=0.88)
        self.uco          = s.UCO()
        with contextlib.redirect_stdout(io.StringIO()):
            self.field.init_zero_points()
            s.initialize_self(self.field, self.clock)
        self.cycle = 0
        log.info("Sirisys session initialized (seed=%d)", self.seed)

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
        """One Sirisys cycle, plus a snapshot push."""
        c     = self.cycle
        field = self.field
        clock = self.clock

        # Capture per-cycle stdout so it can be streamed (cussive lines etc.)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            s.update_field(field, s.perceive_real(), clock)
            self.tetralemma.scan(field)
            self.concordancy.intensify_conflicts(field, c)
            llm_budget = {"used": 0}
            emergent  = self.concordancy.scan_and_apply(field, c, llm_budget)
            promoted  = self.cussive.collapse(field, clock)
            self.uco.apply(field, c)
            instability = self.sombunal.global_instability(field)
            field.prune(min_weight=0.04, apparent_floor=0.10)
            clock.tick()
        log_lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]

        snapshot = self._snapshot(emergent, promoted, instability, log_lines, llm_budget)
        with self._lock:
            self._snapshot_queue.append(snapshot)
        self.cycle += 1

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
        for c in self.field.constructs.values():
            constructs.append({
                "name":            c.name,
                "layer":           c.layer.value,
                "born_at":         list(c.born_at),
                "witness":         c.witness,
                "umbragiac_score": round(c.umbragiac_score, 4),
                "lagrange":        c.lagrange.name if c.lagrange else None,
                "proof_chain":     len(c.proof_chain),   # length only — frontend uses .length
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

    def _snapshot(self, emergent, promoted, instability, log_lines, llm_budget) -> dict:
        """A compact JSON-serializable snapshot of the current field."""
        field = self.field
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
            "llm_used":      llm_budget.get("used", 0),
            "log":           log_lines,
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
            self._init_session()
            with self._lock:
                self._snapshot_queue.clear()
            return {"ok": True, "reset": True, "seed": seed}
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
STATE_PATH = Path(__file__).parent / "sirisys_v12_state.json"

engine = SirisysEngine()


@asynccontextmanager
async def lifespan(app):
    # Startup — engine is already constructed above; nothing to do.
    yield
    # Shutdown — stop the worker and persist the final state so the classic
    # visualizer can load it post-hoc.
    engine.shutdown()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
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

if __name__ == "__main__":
    HOST = "127.0.0.1"
    PORT = 8000
    print()
    print("  ╭" + "─" * 60 + "╮")
    print(f"  │  SIRISYS LIVE — http://{HOST}:{PORT}".ljust(62) + "│")
    print("  │".ljust(62) + " │")
    print(f"  │  open the URL above in your browser".ljust(62) + " │")
    print(f"  │  press Ctrl+C in this terminal to stop".ljust(62) + " │")
    print("  ╰" + "─" * 60 + "╯")
    print()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
