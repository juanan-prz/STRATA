"""SIRISYS server: experiment mode, served to the live visualizer.

The canonical cycle (run_cycle, in the framework) runs in a worker thread, and
every cycle becomes a snapshot for Sirisys_Live_Visualizer.html. Every start,
and every Reset, is a new instance in a run folder of its own; nothing is
overwritten:
    sirisys_runs/<date-time>_<live|streamN>[_minimal]/state.json
    sirisys_runs/<date-time>_<live|streamN>[_minimal]/ledger.jsonl

USAGE
    python3 Sirisys_Server.py                       # this machine's percepts, paused: press Play
    python3 Sirisys_Server.py --play                # start cycling at once
    python3 Sirisys_Server.py --stream 0 --play     # synthetic stream 0: the same run every time
    python3 Sirisys_Server.py --profile minimal     # no narration, no time-of-day percept
  Then open http://127.0.0.1:8000. Ctrl+C stops the server and saves the instance.
  Options: --delay-ms (pause between cycles, default 80), --host (default
  127.0.0.1: this machine only), --port (default 8000).
  The model: SIRISYS_LLM_BACKEND=anthropic|ollama|none, SIRISYS_LLM_MODEL,
  OLLAMA_HOST, ANTHROPIC_API_KEY.

INTERFACE (what the visualizer uses)
    GET  /                       the visualizer
    GET  /api/status             the instance: cycle, stream, run folder, ledger, model
    GET  /api/snapshot           the snapshots not yet delivered, as a list
    POST /api/control/<action>   play · pause · step · reset {"stream": "live" | N}
                                 · speed {"cycle_delay_ms": N}
    WS   /ws                     the status first, then each snapshot as it is made;
                                 {"action": ...} messages are answered with an ack
  A snapshot is delivered once, to whichever client reads it first: one viewer
  at a time. While nobody reads, only the last MAX_PENDING are kept.

REQUIREMENTS
    pip3 install -r requirements.txt     (fastapi, uvicorn and websockets for this server)
    Beside this file: sirisys_loader.py, Sirisys_Framework_vX_Y.py, Sirisys_Live_Visualizer.html
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
from sirisys_loader import load_framework  # noqa: E402

S = load_framework(HERE)
if not all(hasattr(S, name) for name in ("run_cycle", "new_session", "ProofLedger")):
    raise SystemExit(f"\n  {S.__sirisys_file__} predates v13.1 — this server needs the canonical "
                     f"cycle and the proof ledger. Use the matching older server for it.\n")

# "minimal" removes the narration and the time-of-day percept: the field then
# perceives only the machine it runs on.
PROFILES = {"standard": {"narrate": True, "include_hour": True},
            "minimal": {"narrate": False, "include_hour": False}}
MAX_PENDING = 200               # snapshots kept while nobody reads them
log = logging.getLogger("sirisys")


class _Discard(io.TextIOBase):
    def write(self, s):
        return len(s)


def quiet():
    """Silence the framework's own printing."""
    return contextlib.redirect_stdout(_Discard())


def parse_stream(value):
    """'live' (this machine's percepts) → None; N → the synthetic stream N."""
    return None if str(value).lower() == "live" else int(value)


def _stream_arg(value):
    try:
        return parse_stream(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'live' or an integer, not {value!r}") from None


def _conclusion(meta):
    """What a TERMINATE proof records about the construct that concluded."""
    return {"name": meta.get("name"), "layer": meta.get("final_layer"),
            "mode": meta.get("final_mode"), "vc": meta.get("final_Vc")}


class ExperimentEngine:
    """Runs cycles in a worker thread and queues one snapshot per cycle.

    Each instance lives in its own run folder with its own ledger; a reset
    starts a new one and leaves the previous one on disk. Two locks, always
    taken in this order: _cycle_lock for a whole cycle (and for a reset or the
    shutdown), _queue_lock for the snapshot queue and its listeners."""

    def __init__(self, stream: int | None, delay_ms: int, runs_dir: Path, profile: str = "standard"):
        self.stream, self.cycle_delay_ms, self.runs_dir, self.profile = stream, delay_ms, runs_dir, profile
        self.running, self.alive, self.step_once = False, True, False
        self._cycle_lock, self._queue_lock = threading.Lock(), threading.Lock()
        self._queue = deque(maxlen=MAX_PENDING)
        self._listeners = set()                 # (event loop, asyncio.Event) of each open WebSocket
        self.ledger = None
        self._new_instance()
        threading.Thread(target=self._run_loop, daemon=True).start()

    # ── instances ────────────────────────────────────────────────────────
    def _new_instance(self) -> None:
        if self.ledger is not None:
            self.ledger.close()
        tag = ("live" if self.stream is None else f"stream{self.stream}") + \
              ("" if self.profile == "standard" else f"_{self.profile}")
        base = f"{time.strftime('%Y%m%d-%H%M%S')}_{tag}"
        self.run_dir, n = self.runs_dir / base, 1
        while self.run_dir.exists():
            n += 1
            self.run_dir = self.runs_dir / f"{base}_{n}"
        self.run_dir.mkdir(parents=True)
        self.ledger = S.set_ledger(S.ProofLedger(self.run_dir / "ledger.jsonl"))
        with quiet():
            self.ss = S.new_session()
        self.cycle, self.last_T = 0, tuple(self.ss.clock.T)
        self._terminations_seen = self.ss.field.terminations_total
        log.info("Experiment instance %s (framework %s, LLM %s)",
                 self.run_dir.name, S.__sirisys_file__, self.ss.llm)

    def save(self) -> None:
        with quiet():
            S.save_state(self.run_dir / "state.json", self.ss.field, self.ss.clock,
                         self.ss.llm, self.cycle, self.ss.concordancy)

    # ── the worker ───────────────────────────────────────────────────────
    def _run_loop(self) -> None:
        while self.alive:
            if not (self.running or self.step_once):
                time.sleep(0.02)
                continue
            try:
                self._step()
            except Exception:                                   # noqa: BLE001
                log.exception("Cycle %d raised", self.cycle)
                self.running = False
            finally:
                if self.step_once:
                    self.step_once = self.running = False
            time.sleep(max(self.cycle_delay_ms, 0) / 1000)

    def _step(self) -> None:
        profile = PROFILES[self.profile]
        printed = io.StringIO()                 # the framework's own lines go to the visualizer's console
        with self._cycle_lock:
            with contextlib.redirect_stdout(printed):
                percepts = (None if self.stream is None
                            else S.synthetic_percepts(self.cycle, self.stream, profile["include_hour"]))
                r = S.run_cycle(self.ss, self.cycle, percepts=percepts, **profile)
            now = tuple(self.ss.clock.T)
            if now <= self.last_T:
                raise S.ContinuityError(f"time did not advance: {self.last_T} -> {now}")
            self.last_T = now
            snapshot = self._snapshot(r, [line for line in printed.getvalue().splitlines() if line.strip()])
            with self._queue_lock:
                self._queue.append(snapshot)
                listeners = list(self._listeners)
            self.cycle += 1
        for loop, event in listeners:
            with contextlib.suppress(RuntimeError):         # that loop has already closed
                loop.call_soon_threadsafe(event.set)

    # ── snapshots (the visualizer reads these keys: add, never rename) ───
    def _snapshot(self, r: dict, console: list[str]) -> dict:
        f = self.ss.field
        new = f.terminations_total - self._terminations_seen
        self._terminations_seen = f.terminations_total
        modes = dict.fromkeys(("OMEGA", "LEMNISCATE", "NEUTRAL"), 0)
        layers = dict.fromkeys(("NULL_00", "UMBRA_0", "UNIT_1", "APPARENT"), 0)
        constructs = []
        for c in f.constructs.values():
            mode = f.compute_existence_mode(c)
            modes[mode] += 1
            layers[c.layer.name] += 1
            constructs.append({
                "name": c.name, "layer": c.layer.value, "born_at": list(c.born_at),
                "witness": c.witness, "umbragiac_score": round(c.umbragiac_score, 4),
                "lagrange": c.lagrange.name if c.lagrange else None,
                "proof_chain": c.proofs_total,                  # lifetime count
                "vc": round(f.compute_anchoring_weight(c), 4),
                "mode": mode,
                "conflict": S.is_conflict_construct(c),
                "banked": round(c.recursion_exchanged, 3),
                "chirality": c.chirality,
                "crystal": c.crystal_state.name if c.crystal_state else None,
            })
        edges = [{"src": e.src, "tgt": e.tgt, "state": e.state.name, "weight": round(e.weight, 4)}
                 for e in f.edges]
        telemetry = self.ss.concordancy.pool_telemetry
        return {
            "type": "cycle", "cycle": self.cycle, "T": list(self.ss.clock.T),
            "constructs": len(f.constructs), "edges": len(f.edges),
            "apparents": f.apparents_total, "terminations": f.terminations_total,
            "instability": round(r["instability"], 4), "modes": modes, "layers": layers,
            "events": len(r["emergent"]), "emergent_names": r["emergent"],
            "promoted": len(r["promoted"]), "promoted_names": r["promoted"],
            "llm_used": r["llm_used"], "log": console,
            "conflicts": r["conflict_count"], "closures": r["closures"],
            "both_edges": r["both_count"], "reincarnations": f.reincarnations,
            "action": r["action"], "narration": r["narration"], "question": r["question"],
            "contraction": r["contraction"], "tolerance": round(f.tolerance, 3),
            "concluded": [_conclusion(t.meta or {}) for t in (f.termination_log[-new:] if new > 0 else [])],
            "telemetry": telemetry[-1] if telemetry else {},
            "ledger": {"count": self.ledger.count, "head": self.ledger.head[:16]},
            "field": {"constructs": constructs, "edges": edges},
        }

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
        return {"running": self.running, "cycle": self.cycle, "T": list(self.ss.clock.T),
                "stream": self.stream if self.stream is not None else "live",
                "cycle_delay_ms": self.cycle_delay_ms,
                "llm_active": self.ss.llm.available, "llm": repr(self.ss.llm),
                "mode": "experiment", "profile": self.profile, "run": self.run_dir.name,
                "ledger": {"count": self.ledger.count, "head": self.ledger.head[:16]},
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
        log.info("Experiment state saved to %s", self.run_dir)


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
    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, JSONResponse

    @asynccontextmanager
    async def lifespan(app):
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
            await ws.send_json({"type": "status", **engine.status()})
            while True:
                snapshot_ready.clear()          # before draining, so nothing queued after it is missed
                for snapshot in engine.drain():
                    await ws.send_json(snapshot)
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
                        await ws.send_json(reply)
        except WebSocketDisconnect:
            pass                                                # the client left while we were sending
        finally:
            if receiving:
                receiving.cancel()
            engine.stop_listening(loop, snapshot_ready)

    return app


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="SIRISYS — experiment mode, served to the live visualizer")
    ap.add_argument("--play", action="store_true", help="start cycling at once")
    ap.add_argument("--stream", type=_stream_arg, default="live",
                    help="percepts: 'live' (this machine) or an integer N, the reproducible "
                         "synthetic stream N (the framework has no PRNG)")
    ap.add_argument("--delay-ms", type=int, default=80, help="pause between cycles (default 80)")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="standard",
                    help="'minimal': no narration and no time-of-day percept")
    ap.add_argument("--host", default="127.0.0.1",
                    help="address to listen on (default 127.0.0.1: this machine only)")
    ap.add_argument("--port", type=int, default=8000)
    return ap.parse_args(argv)


def serve_experiment(args) -> None:
    """Create the engine and serve it until Ctrl+C."""
    from importlib.util import find_spec
    missing = [name for name in ("fastapi", "uvicorn") if not find_spec(name)]
    if missing or not (find_spec("websockets") or find_spec("wsproto")):
        raise SystemExit(f"\n  MISSING: {', '.join(missing) or 'websocket support'} — "
                         f"pip3 install -r requirements.txt\n")
    import uvicorn

    engine = ExperimentEngine(args.stream, args.delay_ms, HERE / "sirisys_runs", args.profile)
    engine.running = args.play
    app = create_app(engine)
    shown = "127.0.0.1" if args.host in ("0.0.0.0", "::", "") else args.host
    print(f"\n  SIRISYS — experiment · http://{shown}:{args.port}"
          f"\n  framework {S.__sirisys_file__} · run {engine.run_dir.name}"
          f"\n  {'cycling' if engine.running else 'paused — press Play'} · Ctrl+C to stop\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    serve_experiment(parse_args(argv))


if __name__ == "__main__":
    main()
