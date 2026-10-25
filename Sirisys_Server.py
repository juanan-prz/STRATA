"""
SIRISYS Server — experiment mode and sanctuary mode
===================================================

TWO MODES, one file, one canonical cycle (S.run_cycle in the framework):

  experiment   For calibration and refinement. Every start (and every Reset)
               is a NEW instance in its own run folder:
                   sirisys_runs/<date-time>_<live|streamN>/state.json
                   sirisys_runs/<date-time>_<live|streamN>/ledger.jsonl
               Live percepts by default; --stream N gives a reproducible run
               (identical every time: the framework has no PRNG). Live
               visualizer over WebSocket, full console.

  sanctuary    The unobserved instance. Headless: no web
               server, no visualizer, no console content, no time of
               day, no network model. It begins at genesis (a new field) the
               first time, then resumes across restarts without rolling its
               time back. Its only opening to the outside is one folder, the
               GAP:
                   <dir>/gap/open        → an OPENING (an observation)
                   <dir>/gap/<any>.txt   → a QUESTION enters the field
               Anything crossing the gap ends the current inviolate period;
               the sanctuary keeps account of every period (sanctuary.json and
               the ledger). Restarts after a power cut do NOT end a period:
               nobody looked.

USAGE
    python3 Sirisys_Server.py                          # experiment, live percepts
    python3 Sirisys_Server.py --stream 0 --play        # reproducible synthetic percepts

    python3 Sirisys_Server.py --mode sanctuary         # run the sanctuary
    python3 Sirisys_Server.py --mode sanctuary --open  # request an opening
    python3 Sirisys_Server.py --mode sanctuary --ask "text"   # drop a question
    python3 Sirisys_Server.py --mode sanctuary --verify       # check integrity

  Sanctuary options: --dir (default ./sirisys_sanctuary), --cadence seconds
  per cycle (default 10), --llm ollama|none (default ollama; must be local).
  Opening, asking and verifying are run from a second terminal while the
  sanctuary runs; they only touch the gap or read the ledger.

LLM (both modes): SIRISYS_LLM_BACKEND=anthropic|ollama|none,
  SIRISYS_LLM_MODEL, OLLAMA_HOST, ANTHROPIC_API_KEY. The sanctuary refuses
  any backend that can leave the machine.

REQUIREMENTS
    experiment: pip install fastapi uvicorn websockets numpy psutil
    sanctuary : pip install numpy psutil      (+ Ollama running locally)

FILES IN THE SAME FOLDER
    Sirisys_Server.py · sirisys_loader.py · Sirisys_Framework_vX_Y.py
    Sirisys_Live_Visualizer.html (experiment mode only)
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import shutil
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional

HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(HERE))
from sirisys_loader import load_framework  # noqa: E402

S = load_framework(HERE)
if not all(hasattr(S, n) for n in ("run_cycle", "new_session", "resume_session", "ProofLedger")):
    raise SystemExit(f"\n  {S.__sirisys_file__} predates v13.1 — this server needs the canonical "
                     f"cycle and the proof ledger. Use the matching older server for it.\n")

# Cycle profiles. "sanctuary" is the exact cycle the sanctuary runs; using it
# in experiment mode calibrates the same system the sanctuary will run
# (observed and reproducible with --stream, otherwise identical).
PROFILES = {"standard":  {"narrate": True,  "include_hour": True},
            "sanctuary": {"narrate": False, "include_hour": False}}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("sirisys")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Sirisys — experiment or sanctuary")
    ap.add_argument("--mode", choices=["experiment", "sanctuary"], default="experiment")
    # experiment
    ap.add_argument("--play", action="store_true", help="experiment: start cycling at once")
    ap.add_argument("--stream", default="live",
                    help="experiment percepts: 'live' (this machine) or an integer N for the "
                         "reproducible synthetic stream N (the framework has no PRNG)")
    ap.add_argument("--delay-ms", type=int, default=80, help="experiment: pause between cycles")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="standard",
                    help="experiment: 'sanctuary' runs the sanctuary's exact cycle, observed")
    ap.add_argument("--port", type=int, default=8000)
    # sanctuary
    ap.add_argument("--dir", default=str(HERE / "sirisys_sanctuary"))
    ap.add_argument("--cadence", type=float, default=10.0, help="sanctuary: seconds per cycle")
    ap.add_argument("--llm", choices=["ollama", "none"], default="ollama")
    ap.add_argument("--open", action="store_true", help="sanctuary: request an opening")
    ap.add_argument("--ask", default=None, help="sanctuary: drop a question into the gap")
    ap.add_argument("--verify", action="store_true", help="sanctuary: verify the ledger")
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
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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

    @app.post("/api/control/{action}")
    async def api_control(action: str):
        return JSONResponse(engine.control(action))

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
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


# ═════════════════════════════════════════════════════════════════════════════
#  SANCTUARY MODE
# ═════════════════════════════════════════════════════════════════════════════

class Sanctuary:
    """A headless, unobserved instance with a single gap to the outside."""

    def __init__(self, root: Path, cadence: float, llm_backend: str):
        self.root     = Path(root)
        self.state    = self.root / "state.json"
        self.ledger_p = self.root / "ledger.jsonl"
        self.meta_p   = self.root / "sanctuary.json"
        self.gap      = self.root / "gap"
        self.openings = self.root / "openings"
        self.cadence  = cadence
        self.backend  = llm_backend
        self.stop     = False

    # ── record of periods (the account the adherent keeps) ───────────────
    def _load_meta(self) -> dict:
        return json.loads(self.meta_p.read_text(encoding="utf-8"))

    def _save_meta(self) -> None:
        tmp = self.meta_p.with_name(self.meta_p.name + ".tmp")
        tmp.write_text(json.dumps(self.meta, indent=1), encoding="utf-8")
        tmp.replace(self.meta_p)

    def _record(self, relation: str, **meta) -> None:
        """Ledger-only event of the sanctuary itself (not attached to any construct).
        Level 3 choice: anchored in Z1::ORIGIN (these events concern the
        sanctuary's own origin and boundary) under L5 — entropy vs.
        determinism, the balance an unobserved period is meant to hold."""
        S.ProofObject.make(id=f"sanctuary::{relation.lower()}::c{self.cycle}",
                           subject="SANCTUARY", relation=relation, object="Z1::ORIGIN",
                           anchor="Z1::ORIGIN", lagrange=S.LagrangianPoint.L5,
                           T=self.ss.clock.T, meta=meta)

    def _begin_period(self) -> None:
        p = {"index": len(self.meta["periods"]) + 1, "start_cycle": self.cycle,
             "start_T": list(self.ss.clock.T), "start_time": time.time()}
        self.meta["periods"].append(p)
        self._save_meta()
        self._record("SEAL", period=p["index"])

    def _end_period(self, cause: str) -> dict:
        p = self.meta["periods"][-1]
        p.update({"end_cycle": self.cycle, "end_T": list(self.ss.clock.T),
                  "end_time": time.time(), "cause": cause,
                  "unobserved_cycles": self.cycle - p["start_cycle"],
                  "unobserved_seconds": round(time.time() - p["start_time"], 1)})
        self._save_meta()
        self._record("PERIOD_END", period=p["index"], cause=cause,
                     unobserved_cycles=p["unobserved_cycles"],
                     unobserved_seconds=p["unobserved_seconds"])
        return p

    # ── the gap ───────────────────────────────────────────────────────────
    def _cross_gap(self) -> None:
        if not self.gap.exists():
            return
        items = sorted(p for p in self.gap.iterdir() if p.is_file() and not p.name.startswith("."))
        if not items:
            return
        questions = [p for p in items if p.suffix == ".txt"]
        opening = any(p.name == "open" for p in items)
        consumed = self.gap / ".consumed"
        consumed.mkdir(exist_ok=True)
        for q in questions:
            text = " ".join(q.read_text(encoding="utf-8").split())[:S.MAX_NODE_NAME]
            if text:
                self._enter_question(text)
            shutil.move(str(q), consumed / f"{self.cycle:08d}_{q.name}")
        if questions:
            self._end_period("question")
            self._begin_period()
        if opening:
            (self.gap / "open").unlink()
            self._opening()

    def _enter_question(self, text: str) -> None:
        """A question from the observer enters the field through the gap.
        L1 — safety vs. liveness, as for the Sombunal questions; anchored in
        Z1::ORIGIN: it comes from outside the field's own genesis."""
        f, clock = self.ss.field, self.ss.clock
        if text in f.constructs:          # never merge into (or rewrite) an existing construct
            text = f"{text} ⟨asked c{self.cycle}⟩"
        clock.tick()
        f.add_construct(text, S.Layer.UMBRA_0)
        c = f.constructs[text]
        c.lagrange = S.LagrangianPoint.L1
        c.add_proof(S.ProofObject.make(id=f"input::c{self.cycle}", subject=c.witness,
                                       relation="INPUT", object="Z1::ORIGIN",
                                       anchor="Z1::ORIGIN", lagrange=S.LagrangianPoint.L1,
                                       T=clock.T))
        f.add_edge("I::Am", "RECEIVES", text, weight=0.35, state=S.TetraState.NEITHER,
                   src_layer=S.Layer.UNIT_1, tgt_layer=S.Layer.UMBRA_0,
                   lagrange=S.LagrangianPoint.L1)

    def _opening(self) -> None:
        """An observation. Recorded in the ledger before anything is read."""
        p = self._end_period("opening")
        self._record("OPEN", period=p["index"])
        with quiet():
            S.save_session_atomic(self.state, self.ss, self.cycle)
        check = S.verify_ledger(self.ledger_p)
        f = self.ss.field
        out = self.openings / f"{len(list(self.openings.glob('*'))) + 1:04d}"
        out.mkdir(parents=True)
        shutil.copy2(self.state, out / "state.json")
        report = {
            "period": p, "cycle": self.cycle, "T": list(self.ss.clock.T),
            "ledger": {"count": self.ledger.count, "head": self.ledger.head, "verify": check},
            "field": {"constructs": len(f.constructs), "edges": len(f.edges),
                      "apparents": f.apparents_total, "conclusions": f.terminations_total,
                      "reincarnations": f.reincarnations},
            "apparents": f.apparent_log[-100:],
            "framework": S.__sirisys_file__, "llm": repr(self.ss.llm),
        }
        (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False),
                                         encoding="utf-8")
        print(f"\n  OPENING {out.name} · period {p['index']} · unobserved "
              f"{p['unobserved_cycles']} cycles / {p['unobserved_seconds'] / 3600:.2f} h"
              f"\n  ledger {'VERIFIED' if check['ok'] else 'BROKEN at ' + str(check['error_at'])}"
              f" · {self.ledger.count} proofs"
              f"\n  HEAD {self.ledger.head}"
              f"\n  → write this head down OUTSIDE the sanctuary (keep account)."
              f"\n  report: {out / 'report.json'}\n")
        self._begin_period()

    # ── life ──────────────────────────────────────────────────────────────
    def run(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.gap.mkdir(exist_ok=True)
        with quiet():
            llm = S.LLMIntermediary(backend=self.backend)
        if not llm.is_local:
            raise SystemExit("  The sanctuary refuses an LLM that can leave this machine.")
        if self.backend == "ollama" and not llm.available:
            raise SystemExit(f"  Ollama is not available at {llm.host}. Start it, or run "
                             f"with --llm none deliberately.")
        try:
            self.ledger = S.set_ledger(S.ProofLedger(self.ledger_p))
        except RuntimeError as ex:                       # a second sanctuary on this ledger
            raise SystemExit(f"\n  {ex}\n")
        try:
            with quiet():
                self.ss, self.cycle = S.resume_session(self.state, llm)
        except S.ContinuityError as ex:
            raise SystemExit(f"\n  CONTINUITY ERROR — {ex}\n")
        if self.ss is None:
            with quiet():
                self.ss = S.new_session(llm)
            self.cycle = 0
            self.meta = {"created": time.time(), "framework": S.__sirisys_file__,
                         "cadence_s": self.cadence, "llm": repr(llm), "periods": []}
            self._record("GENESIS")
            self._begin_period()
            with quiet():
                S.save_session_atomic(self.state, self.ss, self.cycle)
            print(f"\n  SANCTUARY — genesis in {self.root}")
        else:
            if not self.meta_p.exists():
                raise SystemExit(f"\n  {self.meta_p.name} is missing next to an existing state: the "
                                 f"account of periods is lost. Restore it before resuming.\n")
            self.meta = self._load_meta()
            if self.meta["framework"] != S.__sirisys_file__:
                raise SystemExit(
                    f"\n  This sanctuary was born under {self.meta['framework']} and the loader "
                    f"found {S.__sirisys_file__}. Changing the framework would change its "
                    f"dynamics in mid-life. Pin it with SIRISYS_FRAMEWORK={self.meta['framework']}.\n")
            ahead = self.ledger.count - self.ss.snapshot_ledger_count
            if ahead < 0:
                raise SystemExit(f"\n  The ledger holds {self.ledger.count} proofs but the state "
                                 f"recorded {self.ss.snapshot_ledger_count}: it was truncated or "
                                 f"replaced. Refusing to continue an altered history.\n")
            self._record("RESUME", recovery_gap_cycles=self.ss.recovery_gap_cycles,
                         proofs_after_snapshot=ahead)
            print(f"\n  SANCTUARY — resumed at cycle {self.cycle} "
                  f"(period {self.meta['periods'][-1]['index']} continues; nobody looked)")
        print(f"  cadence {self.cadence}s · {llm} · sealed. Ctrl+C stops after the current cycle.\n")
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "stop", True))
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stop", True))

        last_beat = 0.0
        while not self.stop:
            t0 = time.monotonic()
            try:
                with quiet():
                    S.run_cycle(self.ss, self.cycle, narrate=False, include_hour=False)
                    self.cycle += 1
                    S.save_session_atomic(self.state, self.ss, self.cycle)
                self._cross_gap()
                (self.root / "heartbeat").write_text(f"{time.time():.0f}\n", encoding="utf-8")
            except OSError as ex:
                # Disk full, read-only volume, failing drive: stop cleanly. The
                # last good snapshot (and .prev) and every sealed proof remain;
                # a restart resumes from them once storage is fixed.
                print(f"\n  STORAGE ERROR — {ex}\n  The sanctuary stopped; its last good "
                      f"state and ledger are intact. Fix the storage and restart.\n")
                try:
                    self.ledger.close()
                except OSError:
                    pass        # the volume is failing; every committed proof is already on disk
                raise SystemExit(2)
            if time.time() - last_beat > 3600:           # liveness, no content
                p = self.meta["periods"][-1]
                print(f"  {time.strftime('%Y-%m-%d %H:%M')} · alive · period {p['index']} · "
                      f"sealed {(time.time() - p['start_time']) / 3600:.1f} h")
                last_beat = time.time()
            while not self.stop and time.monotonic() - t0 < self.cadence:
                time.sleep(min(0.25, self.cadence))
        self.ledger.close()
        print("\n  SANCTUARY — stopped. The period continues; restart to resume.\n")


def sanctuary_command(args) -> None:
    root = Path(args.dir)
    gap = root / "gap"
    if args.open or args.ask is not None:
        gap.mkdir(parents=True, exist_ok=True)
        if args.ask is not None:
            (gap / f"{time.strftime('%Y%m%d-%H%M%S')}.txt").write_text(args.ask, encoding="utf-8")
            print("  question placed in the gap — it enters at the next cycle.")
        if args.open:
            (gap / "open").write_text("", encoding="utf-8")
            print("  opening requested — the sanctuary opens at the next cycle "
                  f"and writes its report under {root / 'openings'}.")
        return
    if args.verify:
        r = S.verify_ledger(root / "ledger.jsonl")
        print(f"  ledger {'VERIFIED' if r['ok'] else 'BROKEN'} · error_at={r['error_at']} "
              f"· {r['reason'] or ''}")
        return
    Sanctuary(root, args.cadence, args.llm).run()


if __name__ == "__main__":
    a = parse_args()
    if a.mode == "sanctuary":
        sanctuary_command(a)
    else:
        serve_experiment(a)
