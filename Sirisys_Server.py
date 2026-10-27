"""
SIRISYS Server — experiment mode
================================

One canonical cycle (S.run_cycle in the framework), served to the live
visualizer. Every start (and every Reset) is a NEW instance in its own run
folder:
    sirisys_runs/<date-time>_<live|streamN>/state.json
    sirisys_runs/<date-time>_<live|streamN>/ledger.jsonl
Live percepts by default; --stream N gives a reproducible run (identical
every time: the framework has no PRNG). Live visualizer over WebSocket, full
console.

USAGE
    python3 Sirisys_Server.py                          # live percepts, paused
    python3 Sirisys_Server.py --play                   # start cycling at once
    python3 Sirisys_Server.py --stream 0 --play        # reproducible synthetic percepts
    python3 Sirisys_Server.py --profile minimal        # no narration, no time of day

LLM: SIRISYS_LLM_BACKEND=anthropic|ollama|none, SIRISYS_LLM_MODEL,
  OLLAMA_HOST, ANTHROPIC_API_KEY.

REQUIREMENTS
    pip install fastapi uvicorn websockets numpy psutil

FILES IN THE SAME FOLDER
    Sirisys_Server.py · sirisys_loader.py · Sirisys_Framework_vX_Y.py
    Sirisys_Live_Visualizer.html
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Optional

HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(HERE))
from sirisys_loader import load_framework  # noqa: E402

S = load_framework(HERE)
if not all(hasattr(S, n) for n in ("run_cycle", "new_session", "ProofLedger")):
    raise SystemExit(f"\n  {S.__sirisys_file__} predates v13.1 — this server needs the canonical "
                     f"cycle and the proof ledger. Use the matching older server for it.\n")

# Cycle profiles. "minimal" removes the narration and the time-of-day percept:
# the field then perceives only the machine it runs on.
PROFILES = {"standard": {"narrate": True,  "include_hour": True},
            "minimal":  {"narrate": False, "include_hour": False}}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("sirisys")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Sirisys — experiment mode")
    ap.add_argument("--play", action="store_true", help="start cycling at once")
    ap.add_argument("--stream", default="live",
                    help="percepts: 'live' (this machine) or an integer N for the "
                         "reproducible synthetic stream N (the framework has no PRNG)")
    ap.add_argument("--delay-ms", type=int, default=80, help="pause between cycles")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="standard",
                    help="'minimal': no narration and no time-of-day percept")
    ap.add_argument("--host", default="127.0.0.1",
                    help="bind address (default: 127.0.0.1 loopback only)")
    ap.add_argument("--port", type=int, default=8000)
    return ap.parse_args(argv)


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


# ═════════════════════════════════════════════════════════════════════════════
#  EXPERIMENT MODE
# ═════════════════════════════════════════════════════════════════════════════

class ExperimentEngine:
    """Runs cycles in a worker thread and queues compact snapshots for the
    WebSocket task. Every instance lives in its own run folder with its own
    ledger; Reset starts a new instance and leaves the previous one on disk."""

    def __init__(self, stream: Optional[int], delay_ms: int, runs_dir: Path,
                 profile: str = "standard"):
        self.stream, self.cycle_delay_ms, self.runs_dir = stream, delay_ms, runs_dir
        self.profile = profile
        self.running, self.alive, self.step_once = False, True, False
        self._lock = threading.Lock()          # guards the snapshot queue
        self._cycle_lock = threading.Lock()    # held for a whole cycle; order: cycle → queue
        self._queue: list[dict] = []
        self._broadcast = None                 # asyncio.Event, created on first WS
        self._loop = None
        self._new_instance()
        threading.Thread(target=self._run_loop, daemon=True).start()

    # ── instance lifecycle ───────────────────────────────────────────────
    def _new_instance(self) -> None:
        if getattr(self, "ledger", None):
            self.ledger.close()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        tag = (f"stream{self.stream}" if self.stream is not None else "live") + \
              ("" if self.profile == "standard" else f"_{self.profile}")
        self.run_dir = self.runs_dir / f"{stamp}_{tag}"
        n = 1
        while self.run_dir.exists():
            n += 1
            self.run_dir = self.runs_dir / f"{stamp}_{tag}_{n}"
        self.run_dir.mkdir(parents=True)
        self.ledger = S.set_ledger(S.ProofLedger(self.run_dir / "ledger.jsonl"))
        with quiet():
            self.ss = S.new_session()
        self.cycle, self.last_T = 0, tuple(self.ss.clock.T)
        self._terms_seen = self.ss.field.terminations_total
        log.info("Experiment instance %s (framework %s, LLM %s)",
                 self.run_dir.name, S.__sirisys_file__, self.ss.llm)

    def save(self) -> None:
        with quiet():
            S.save_state(self.run_dir / "state.json", self.ss.field, self.ss.clock,
                         self.ss.llm, self.cycle, self.ss.concordancy)

    # ── worker ───────────────────────────────────────────────────────────
    def _run_loop(self) -> None:
        while self.alive:
            if not (self.running or self.step_once):
                time.sleep(0.02)
                continue
            try:
                self._step()
            except Exception as ex:                          # noqa: BLE001
                log.exception("Cycle %d raised: %s", self.cycle, ex)
                self.running = False
            finally:
                if self.step_once:
                    self.step_once, self.running = False, False
            time.sleep(max(self.cycle_delay_ms, 0) / 1000.0)

    def _step(self) -> None:
        with self._cycle_lock:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                prof = PROFILES[self.profile]
                ev = (None if self.stream is None else
                      S.synthetic_percepts(self.cycle, self.stream, prof["include_hour"]))
                r = S.run_cycle(self.ss, self.cycle, percepts=ev, **prof)
            T_now = tuple(self.ss.clock.T)
            if T_now <= self.last_T:
                raise S.ContinuityError(f"time did not advance: {self.last_T} -> {T_now}")
            self.last_T = T_now
            snap = self._snapshot(r, [ln for ln in buf.getvalue().splitlines() if ln.strip()])
            with self._lock:
                self._queue.append(snap)
            self.cycle += 1
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._broadcast.set)

    # ── snapshots (keys unchanged for the visualizer; additive only) ─────
    def _slim_field(self) -> dict:
        f = self.ss.field
        constructs = [{
            "name": c.name, "layer": c.layer.value, "born_at": list(c.born_at),
            "witness": c.witness, "umbragiac_score": round(c.umbragiac_score, 4),
            "lagrange": c.lagrange.name if c.lagrange else None,
            "proof_chain": c.proofs_total,               # lifetime count
            "vc": round(f.compute_anchoring_weight(c), 4),
            "mode": f.compute_existence_mode(c),
            "conflict": S.is_conflict_construct(c),
            "banked": round(c.recursion_exchanged, 3),
            "chirality": c.chirality,
            "crystal": c.crystal_state.name if c.crystal_state else None,
        } for c in f.constructs.values()]
        edges = [{"src": e.src, "tgt": e.tgt, "state": e.state.name,
                  "weight": round(e.weight, 4)} for e in f.edges]
        return {"constructs": constructs, "edges": edges}

    def _snapshot(self, r: dict, log_lines) -> dict:
        f = self.ss.field
        new_terms = f.terminations_total - self._terms_seen
        self._terms_seen = f.terminations_total
        concluded = [{"name": (tp.meta or {}).get("name"), "layer": (tp.meta or {}).get("final_layer"),
                      "mode": (tp.meta or {}).get("final_mode"), "vc": (tp.meta or {}).get("final_Vc")}
                     for tp in (f.termination_log[-new_terms:] if new_terms > 0 else [])]
        modes = {"OMEGA": 0, "LEMNISCATE": 0, "NEUTRAL": 0}
        layers = {"NULL_00": 0, "UMBRA_0": 0, "UNIT_1": 0, "APPARENT": 0}
        for c in f.constructs.values():
            modes[f.compute_existence_mode(c)] += 1
            layers[c.layer.name] += 1
        tel = self.ss.concordancy.pool_telemetry
        return {
            "type": "cycle", "cycle": self.cycle, "T": list(self.ss.clock.T),
            "constructs": len(f.constructs), "edges": len(f.edges),
            "apparents": f.apparents_total, "terminations": f.terminations_total,
            "instability": round(r["instability"], 4), "modes": modes, "layers": layers,
            "events": len(r["emergent"]), "emergent_names": r["emergent"],
            "promoted": len(r["promoted"]), "promoted_names": r["promoted"],
            "llm_used": r["llm_used"], "log": log_lines,
            "conflicts": r["conflict_count"], "closures": r["closures"],
            "both_edges": r["both_count"], "reincarnations": f.reincarnations,
            "action": r["action"], "narration": r["narration"], "question": r["question"],
            "contraction": r["contraction"], "tolerance": round(f.tolerance, 3),
            "concluded": concluded, "telemetry": tel[-1] if tel else {},
            "ledger": {"count": self.ledger.count, "head": self.ledger.head[:16]},
            "field": self._slim_field(),
        }

    # ── controls ─────────────────────────────────────────────────────────
    def control(self, action: str, **kw) -> dict:
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
            self.running = False
            if "stream" in kw:
                self.stream = None if str(kw["stream"]).lower() == "live" else int(kw["stream"])
            with self._cycle_lock:
                self.save()                     # the old instance stays on disk
                previous = self.run_dir.name
                self._new_instance()
                with self._lock:
                    self._queue.clear()
            return {"ok": True, "reset": True, "stream": self.stream, "previous_run": previous}
        if action == "speed":
            self.cycle_delay_ms = max(0, int(kw.get("cycle_delay_ms", 80)))
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
        with self._lock:
            out, self._queue = self._queue, []
        return out

    def shutdown(self) -> None:
        self.running, self.alive = False, False
        with self._cycle_lock:
            self.save()
            self.ledger.close()
        log.info("Experiment state saved to %s", self.run_dir)


def serve_experiment(args) -> None:
    import asyncio
    from contextlib import asynccontextmanager
    from importlib.util import find_spec
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn

    if not (find_spec("websockets") or find_spec("wsproto")):
        raise SystemExit("\n  MISSING WEBSOCKET SUPPORT — pip3 install websockets\n")
    stream = None if str(args.stream).lower() == "live" else int(args.stream)
    engine = ExperimentEngine(stream, args.delay_ms, HERE / "sirisys_runs", args.profile)
    engine.running = args.play

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.shutdown()

    app = FastAPI(title="SIRISYS experiment", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    def index():
        html = HERE / "Sirisys_Live_Visualizer.html"
        if not html.exists():
            return HTMLResponse("<h1>Sirisys_Live_Visualizer.html not found</h1>", status_code=500)
        return HTMLResponse(html.read_text(encoding="utf-8"))

    @app.get("/api/status")
    def api_status():
        return JSONResponse(engine.status())

    @app.get("/api/snapshot")
    def api_snapshot():
        snaps = engine.drain()
        return JSONResponse(snaps)  # always returns a list, empty when no snapshots

    @app.post("/api/control/{action}")
    async def api_control(action: str, request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        # Remove 'action' from body to avoid "got multiple values for argument 'action'"
        body.pop("action", None)
        return JSONResponse(engine.control(action, **body))

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        if engine._loop is None:
            engine._loop, engine._broadcast = asyncio.get_running_loop(), asyncio.Event()
        await ws.send_json({"type": "status", **engine.status()})
        try:
            while True:
                for snap in engine.drain():
                    await ws.send_json(snap)
                recv = asyncio.create_task(ws.receive_text())
                event = asyncio.create_task(engine._broadcast.wait())
                done, pending = await asyncio.wait({recv, event}, timeout=1.0,
                                                   return_when=asyncio.FIRST_COMPLETED)
                for t in pending:
                    t.cancel()
                if recv in done:
                    try:
                        raw = recv.result()
                    except (WebSocketDisconnect, RuntimeError):
                        # The client is gone: stop serving this socket (catching
                        # and continuing would spin on a dead socket at full CPU).
                        break
                    try:
                        payload = json.loads(raw)
                    except ValueError:
                        continue
                    if payload.get("action"):
                        res = engine.control(payload["action"],
                                             **{k: v for k, v in payload.items() if k != "action"})
                        await ws.send_json({"type": "ack", **res, "status": engine.status()})
                if event in done:
                    engine._broadcast.clear()
        except WebSocketDisconnect:
            pass                                 # client closed while we were sending

    print(f"\n  SIRISYS — experiment · http://127.0.0.1:{args.port}"
          f"\n  framework {S.__sirisys_file__} · run {engine.run_dir.name}"
          f"\n  {'cycling' if engine.running else 'paused — press Play'} · Ctrl+C to stop\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    serve_experiment(parse_args())
