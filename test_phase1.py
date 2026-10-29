"""Everything around the field: the experiment engine, the model backends, the
profiles, the web layer, the model-health watch, the experiment tools
(run_report.py, live_c2.py), and the names and constants the visualizers share
with the framework.
No API key, no Ollama and no FastAPI needed: a local fake model, and a stub in
place of the web framework.
Usage: python3 test_phase1.py"""
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from sirisys_measures import ModelHealth
from sirisys_testkit import HERE, Checks, FakeModel, environment, fresh_framework, quiet, raises, read_jsonl, scratch

with quiet():
    import Sirisys_Server as server
S = server.S
check = Checks()


def wait_for(condition, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.05)
    return False


def no_log(line):
    pass


def perceived_the_hour(run_dir):
    """A PERCEIVE proof names its percept in its id: perceive::<target>."""
    return any(r["relation"] == "PERCEIVE" and r["id"].startswith("perceive::time::")
               for r in read_jsonl(run_dir / "ledger.jsonl"))


def run(args, folder, timeout=300, **env):
    """A tool run as the user runs it: a separate process in `folder`."""
    return subprocess.run([sys.executable, *args], cwd=folder, capture_output=True, text=True,
                          timeout=timeout, env={**os.environ, **env})


check.section("1 · Experiment engine (no web server needed)")
with quiet():
    engine = server.ExperimentEngine(stream=0, delay_ms=0, runs_dir=scratch())
    engine.running = True
    wait_for(lambda: engine.cycle >= 30)
    engine.running = False
    time.sleep(0.2)
snapshots, first_run, history = engine.drain(), engine.run_dir, engine.history()
cycles_run, head_then = engine.cycle, engine.ledger.head
expected = {"run", "cycle", "T", "constructs", "edges", "apparents", "terminations", "concluded", "field",
            "ledger", "instability", "modes", "layers", "action", "breath", "crystallized", "model_watch",
            "metabolism"}
check("cycles stream as snapshots", len(snapshots) >= 30 and expected <= snapshots[-1].keys()
      and all("energy" in c for c in snapshots[-1]["field"]["constructs"]), f"{len(snapshots)} snapshots")
check("snapshot is JSON-serializable", bool(json.dumps(snapshots[-1])))
crystallized = sum(len(s["crystallized"]) for s in snapshots)
check("a snapshot says which of the cycle's promotions crystallized, from the field's own record",
      all(set(s["crystallized"]) <= set(s["promoted_names"]) for s in snapshots) and 0 < crystallized
      == snapshots[-1]["apparents"] - snapshots[0]["apparents"] + len(snapshots[0]["crystallized"]),
      f"{crystallized} of {sum(s['promoted'] for s in snapshots)} promotions")

# The metabolism: born minus concluded is the change in the population, every cycle
flows = [s["metabolism"] for s in snapshots]
balanced = all(m["born"] - sum(m["concluded"].values()) == s["constructs"] - p["constructs"]
               for p, s, m in zip(snapshots, snapshots[1:], flows[1:]))
check("each snapshot says what its cycle did to the population: born minus concluded is the change, every cycle",
      balanced and all(m["risen"] + m["crystallized"] == s["promoted"] and m["unseen"] <= m["born"]
                       for s, m in zip(snapshots, flows)) and sum(m["unseen"] for m in flows) > 0,
      f"{sum(m['born'] for m in flows)} born ({sum(m['unseen'] for m in flows)} never on a snapshot), "
      f"{sum(sum(m['concluded'].values()) for m in flows)} concluded")
records = history["records"]
check("the history adds the cycles up breath by breath, for the whole instance",
      history["run"] == first_run.name and history["through_cycle"] == snapshots[-1]["cycle"]
      and [r["breaths"][0] for r in records] == sorted({m["breath"] for m in flows})
      and all(sum(r[k] for r in records) == sum(m[k] for m in flows) for k in ("born", "unseen", "risen", "crystallized"))
      and records[-1]["population"] == snapshots[-1]["layers"], f"{len(records)} breaths, cycles 0–{history['through_cycle']}")
bare = fresh_framework()                            # the same cycles, with nothing watching
bare.set_ledger(bare.ProofLedger(scratch() / "ledger.jsonl"))
with quiet():
    session = bare.new_session()
    for n in range(cycles_run):
        bare.run_cycle(session, n, percepts=bare.synthetic_percepts(n, 0, True), **server.PROFILES["standard"])
check("serving the field changes nothing in it: the same ledger head as the bare cycle",
      bare.get_ledger().head == head_then, f"{cycles_run} cycles, head {head_then[:12]}…")
with quiet():                                       # the visualizer's buttons
    engine.control("pause")
    time.sleep(0.1)
    at = engine.cycle
    time.sleep(0.2)
    held = engine.cycle == at
    engine.control("step")
    wait_for(lambda: not engine.step_once)
    one = engine.cycle == at + 1
    engine.control("play")
    wait_for(lambda: engine.cycle >= at + 5)
    engine.control("step")                          # while playing: one more cycle, then paused
    wait_for(lambda: not engine.step_once)
    time.sleep(0.1)
    stopped = not engine.running
    speed, unknown = engine.control("speed", cycle_delay_ms=5), engine.control("dance")
check("controls: pause holds, step advances one cycle and pauses, play, speed; an unknown action refused",
      held and one and stopped and speed == {"ok": True, "cycle_delay_ms": 5} and unknown["ok"] is False,
      f"held {held}, one cycle {one}, paused after step {stopped}, {unknown.get('error')}")
with quiet():
    reset = engine.control("reset", stream="live")
check("reset opens a new run folder, old one kept, and starts its history again",
      reset["ok"] and first_run.exists() and (first_run / "state.json").exists()
      and engine.run_dir != first_run and engine.history() == {"run": engine.run_dir.name, "through_cycle": -1, "records": []},
      f"{first_run.name} → {engine.run_dir.name}")
check("old run's ledger verifies", S.verify_ledger(first_run / "ledger.jsonl")["ok"])
check("live-percept reset recorded", engine.stream is None and engine.run_dir.name.endswith("_live"))
with quiet():
    engine.shutdown()
check("shutdown saves the current run", (engine.run_dir / "state.json").exists())

# A long instance: past HISTORY_KEPT records the oldest are merged in pairs, nothing lost
kept, server.HISTORY_KEPT = server.HISTORY_KEPT, 4
with quiet():
    long = server.ExperimentEngine(stream=0, delay_ms=0, runs_dir=scratch())
    long.running = True
    wait_for(lambda: long.history()["records"] and long.history()["records"][-1]["breaths"][1] >= 9)
    long.running = False
    time.sleep(0.2)
    merged, last_cycle = long.history(), long.cycle - 1
    long.shutdown()
server.HISTORY_KEPT = kept
spans = [r["breaths"] for r in merged["records"]]
check("a long history stays bounded: the oldest breaths merged in pairs, every cycle still counted",
      len(spans) <= 5 and spans[0][0] == 0 and all(a[1] + 1 == b[0] for a, b in zip(spans, spans[1:]))
      and merged["records"][0]["cycles"][0] == 0 and merged["through_cycle"] == last_cycle
      and all(a["cycles"][1] + 1 == b["cycles"][0] for a, b in zip(merged["records"], merged["records"][1:])),
      f"breaths {spans}")

check.section("2 · Model backends")
with FakeModel("counter") as model:
    with quiet():
        llm = S.LLMIntermediary(backend="ollama", host=model.url)
        answer = llm.question_sombunal(0.5)
    request = model.requests[-1] if model.requests else {}
check("ollama backend: discovers model and completes",
      llm.available and llm.model == FakeModel.MODEL and answer == "Name 1")
check("ollama request carries system prompt, history and options",
      request.get("messages", [{}])[0].get("role") == "system" and request.get("stream") is False
      and request.get("options", {}).get("temperature") == 1.10,
      f"temperature {request.get('options', {}).get('temperature')}")
check("ollama on loopback is local", llm.is_local)
with quiet():
    remote = S.LLMIntermediary(backend="ollama", host="http://10.0.0.5:11434")
check("ollama on another host is NOT local", not remote.is_local)


class FakeMessages:
    """Stands in for anthropic.Anthropic().messages and keeps what it was asked."""

    def create(self, **request):
        self.request = request
        return SimpleNamespace(content=[SimpleNamespace(text=" ok ")])


with quiet():
    claude = S.LLMIntermediary(backend="anthropic")
    claude._client, claude._available = SimpleNamespace(messages=FakeMessages()), True
    claude.question_sombunal(0.3)                   # asks at 1.10
check("anthropic temperature clamped to [0, 1] (was 1.10)",
      claude._client.messages.request["temperature"] == 1.0)
check("unknown backend refused", raises(lambda: S.LLMIntermediary(backend="openai"), ValueError))

check.section("3 · Profiles, framework check, web layer")
with quiet():
    minimal = server.ExperimentEngine(stream=1, delay_ms=0, runs_dir=scratch(), profile="minimal")
    for _ in range(15):
        minimal.step_once = True
        wait_for(lambda: not minimal.step_once, 20)
    minimal.shutdown()
check("experiment --profile minimal perceives no time of day (the standard run of section 1 does)",
      minimal.cycle >= 10 and not perceived_the_hour(minimal.run_dir) and perceived_the_hour(first_run)
      and minimal.run_dir.name.endswith("_minimal"), f"{minimal.cycle} cycles, run {minimal.run_dir.name}")

old = scratch()                                     # a framework without the canonical cycle
for f in ("Sirisys_Server.py", "sirisys_loader.py"):
    shutil.copy(HERE / f, old / f)
(old / "Sirisys_Framework_v12_9.py").write_text('"""A framework older than v13.1."""\n', encoding="utf-8")
p = run(["Sirisys_Server.py", "--help"], old, 60, SIRISYS_FRAMEWORK="Sirisys_Framework_v12_9.py")
check("server refuses a pre-v13.1 framework with a clear message",
      p.returncode != 0 and "predates v13.1" in p.stdout + p.stderr)

# The web layer with a stub in place of FastAPI and uvicorn: no server is ever started
stub = scratch()
(stub / "fastapi").mkdir()
(stub / "websockets").mkdir()
(stub / "websockets" / "__init__.py").write_text("")
(stub / "fastapi" / "__init__.py").write_text(
    "class WebSocketDisconnect(Exception): pass\nclass WebSocket: pass\nclass Request: pass\n"
    "class FastAPI:\n def __init__(self,title=None,lifespan=None): self.routes={}; self.lifespan=lifespan\n"
    " def _r(self,k):\n  def d(f): self.routes[k]=f; return f\n  return d\n"
    " def get(self,p,**k): return self._r(('GET',p))\n def post(self,p,**k): return self._r(('POST',p))\n"
    " def websocket(self,p): return self._r(('WS',p))\n")
(stub / "fastapi" / "responses.py").write_text(
    "class HTMLResponse:\n def __init__(self,content='',status_code=200): self.content=content; "
    "self.status_code=status_code\nclass JSONResponse:\n def __init__(self,content): self.content=content\n")
(stub / "uvicorn.py").write_text("APP=None\ndef run(app,**k):\n global APP; APP=app\n")
(stub / "web.py").write_text(f"""
import sys, asyncio, io, contextlib, json, pathlib
sys.path.insert(0, {str(stub)!r}); sys.path.insert(0, {str(HERE)!r}); sys.argv = ['web']
import Sirisys_Server as srv, uvicorn, fastapi
srv.HERE = pathlib.Path({str(stub)!r})
with contextlib.redirect_stdout(io.StringIO()):
    srv.serve_experiment(srv.parse_args(['--delay-ms', '0']))
routes = uvicorn.APP.routes
class Request:
    def __init__(self, body): self.body = body
    async def json(self):
        if self.body is None: raise ValueError('no body')
        return self.body
async def go():
    control = routes[('POST', '/api/control/{{action}}')]
    replies = [(await control(action, Request(body))).content
               for action, body in (('play', None), ('reset', {{'stream': 'abc'}}), ('pause', [1, 2]))]
    # two malformed messages, one step, half a second for its snapshot; then play, and a step
    # while playing: one more cycle and the engine pauses itself; then the client goes
    sent, script = [], ['[1]', 'not json', json.dumps({{'action': 'step'}}), 0.5,
                        json.dumps({{'action': 'play'}}), 0.3, json.dumps({{'action': 'step'}}), 0.5]
    class Socket:
        async def accept(self): pass
        async def send_json(self, o): sent.append(o)
        async def receive_text(self):
            while script:
                item = script.pop(0)
                if isinstance(item, str): return item
                await asyncio.sleep(item)
            raise fastapi.WebSocketDisconnect()
    await asyncio.wait_for(routes[('WS', '/ws')](Socket()), 10)
    history = routes[('GET', '/api/history')]().content
    async with uvicorn.APP.lifespan(uvicorn.APP): pass
    print(json.dumps({{'replies': replies, 'sent': [m.get('type') for m in sent], 'history': history,
                      'snapshot_cycles': [m['cycle'] for m in sent if m.get('type') == 'cycle'],
                      'acks': [m.get('stepping') for m in sent if m.get('type') == 'ack'],
                      'told': [m['running'] if m.get('type') == 'status' else m['status']['running']
                               for m in sent if m.get('type') in ('status', 'ack')]}}))
asyncio.run(go())
""")
p = run(["web.py"], stub, 60)
output = (p.stdout + p.stderr).strip()
web = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 and p.stdout.strip() else {}
replies, sent = web.get("replies", [{}] * 3), web.get("sent", [])
check("malformed control requests get an answer, not an error (a bad stream, a body that is not an object)",
      replies[0].get("ok") and replies[1].get("ok") is False and "stream" in replies[1].get("error", "")
      and replies[2] == {"ok": True, "running": False}, str(replies)[:90] if web else output[-90:])
check("WebSocket: status first, malformed messages ignored, a step acknowledged and its snapshot sent, "
      "exits when the client goes",
      sent[:1] == ["status"] and web.get("acks", [])[:1] == [True] and "cycle" in sent[sent.index("ack"):],
      f"{len(sent)} messages, {sent.count('cycle')} snapshot(s)" if web else output[-90:])
told = web.get("told", [])
history, seen = web.get("history") or {}, web.get("snapshot_cycles", [])
check("GET /api/history: the instance's metabolism, through the last cycle it ran",
      history.get("records") and history["through_cycle"] >= max(seen, default=0) >= 0
      and history["records"][-1]["cycles"][1] == history["through_cycle"]
      and sum(r["born"] for r in history["records"]) > 0, f"{len(history.get('records', []))} breath(s), "
      f"through cycle {history.get('through_cycle')}" if web else output[-90:])
check("WebSocket: when the engine pauses itself (a step while playing), the client is told",
      web.get("acks") == [True, None, True] and True in told and told[-1] is False,
      f"running as told: {told}" if web else output[-90:])

# Nobody reading: the queue keeps only the latest snapshots, so memory stays flat
with quiet():
    unread = server.ExperimentEngine(stream=2, delay_ms=0, runs_dir=scratch())
    unread.running = True
    wait_for(lambda: unread.cycle >= server.MAX_PENDING + 20, 120)
    unread.running = False
    time.sleep(0.2)
    pending = unread.drain()
    unread.shutdown()
check(f"unread snapshots are capped at the latest {server.MAX_PENDING}",
      len(pending) == server.MAX_PENDING and pending[-1]["cycle"] == unread.cycle - 1,
      f"{unread.cycle} cycles, {len(pending)} kept")

check.section("4 · Model health")
model = FakeModel("counter")


def intermediary():
    with quiet():
        return S.LLMIntermediary(backend="ollama", host=model.url)


probe = ModelHealth.probe(intermediary(), cycles=100, calls_per_cycle=4)
check("the probe accepts a model that answers", probe["ok"] and all(probe["answers"]),
      str(probe.get("answers")))
model.reset("empty")
probe = ModelHealth.probe(intermediary())
check("the probe refuses a model that answers empty", not probe["ok"] and "empty" in probe["reason"])
model.reset("error")
llm, health = intermediary(), ModelHealth()
health.attach(llm)
with quiet():
    names = [llm.propose_emergent("a", "b", "TRUE", "TRUE") for _ in range(4)]
check("watching trips after 3 failed calls in a row (the field itself only sees empty names)",
      health.tripped and health.failures >= 3 and not any(names), health.reason)
model.reset("error", after=20)                      # experiment mode: a model that starts failing
server.log.disabled = True                          # its warning, on the console, is for the user
with quiet(), environment(SIRISYS_LLM_BACKEND="ollama", OLLAMA_HOST=model.url):
    watched = server.ExperimentEngine(stream=0, delay_ms=0, runs_dir=scratch())
    watched.running = True
    paused = wait_for(lambda: not watched.running)
    paused_at, status = watched.cycle, watched.status()
    watched.control("play")
    went_on = wait_for(lambda: watched.cycle >= paused_at + 5)
    watched.shutdown()
server.log.disabled = False
said = (status["model"]["watch"] or {}).get("reason") or ""
check("experiment mode pauses once when the model watch trips, says why in its status and "
      "snapshots, and Play goes on",
      paused and status["model"]["active"] and "in a row failed" in said and went_on
      and watched.drain()[-1]["model_watch"]["tripped"], f"paused at cycle {paused_at}: {said[:50]}")

check.section("5 · The experiment tools: run_report.py and live_c2.py")
tools = scratch()                                   # copies: nothing here touches the user's reports
for f in ("run_report.py", "live_c2.py", "sirisys_loader.py", "field_topology.py", "sirisys_measures.py",
          S.__sirisys_file__):
    shutil.copy(HERE / f, tools / f)
model.reset("error", after=30)
p = run(["live_c2.py", "60", "ollama", "minimal"], tools, OLLAMA_HOST=model.url)
out = json.loads(p.stdout) if p.stdout.strip() else {}
check("live_c2 stops (exit 3) when the model starts failing mid-run, and says so",
      p.returncode == 3 and out.get("aborted") and "STOPPED" in p.stderr, str(out.get("aborted"))[:80])
p = run(["run_report.py", "--backend", "ollama", "--cycles", "5", "--seeds", "1"], tools, 120,
        OLLAMA_HOST="http://127.0.0.1:9")
check("run_report --backend ollama stops before running when the model is not there",
      p.returncode == 3 and "Nothing was run" in p.stdout and not (tools / "sirisys_report.json").exists())

determinism = {}
for mode in ("alike", "counter"):          # answers alike to the same request and seed, or carrying state
    model.reset(mode)
    (tools / "sirisys_determinism.json").unlink(missing_ok=True)
    p = run(["run_report.py", "--backend", "ollama", "--profile", "minimal", "--cycles", "40",
             "--determinism"], tools, OLLAMA_HOST=model.url)
    written = tools / "sirisys_determinism.json"
    determinism[mode] = (json.loads(written.read_text()).get("determinism") or {}
                         if p.returncode == 0 and written.exists() else {})
alike, stateful = determinism["alike"], determinism["counter"]
check("the determinism check tells a model that answers alike from one that does not, in its own file",
      alike.get("same") is True and stateful.get("same") is False
      and stateful.get("diverged_at_cycle") is not None and not (tools / "sirisys_report.json").exists(),
      f"alike: same ledger {alike.get('same')}; stateful: same ledger {stateful.get('same')}, "
      f"parted at cycle {stateful.get('diverged_at_cycle')}")

with quiet():
    import run_report
    first, again = (run_report.run_arm(0, 30, False, no_log, profile="minimal") for _ in range(2))
    other = run_report.run_arm(1, 30, False, no_log, profile="minimal")
distinct = first["percept_catalog"]["distinct_targets"]
check("run_report feeds the synthetic stream when asked, reproducibly",
      distinct > 2 and first["trace"] == again["trace"] and first["trace"] != other["trace"],
      f"{distinct} distinct percepts; seed 0 twice identical: {first['trace'] == again['trace']}; "
      f"seed 1 different: {first['trace'] != other['trace']}")

# The live view's criteria are the reports': the same code on the same life
every, server.CRITERIA_EVERY = server.CRITERIA_EVERY, 40
with quiet(), environment(SIRISYS_LLM_BACKEND="none"):
    measured = server.ExperimentEngine(stream=0, delay_ms=0, runs_dir=scratch())
    for _ in range(40):
        measured.step_once = True
        wait_for(lambda: not measured.step_once, 20)
    reading, carried = measured.status()["criteria"], [s for s in measured.drain() if "criteria" in s]
    measured.shutdown()
    reported = run_report.run_arm(0, 40, False, no_log)["criteria"]
server.CRITERIA_EVERY = every
untimed = lambda r: {k: v for k, v in json.loads(json.dumps(r)).items() if k != "ms_first_last"}   # the cost is a time
check("the live view's criteria are run_report's: the same result on the same life, each criterion and the verdict",
      reading and reading["cycles"] == 40 and untimed(reading["result"]) == untimed(reported)
      and reading["verdict"] is None and set(reading["checks"]) == {"durable", "flicker", "population", "cost", "energy"}
      and [s["cycle"] for s in carried] == [39],
      f"{reading['cycles']} cycles: durable {reading['result']['durable_per_1000']}, flicker "
      f"{reading['result']['flicker_share']}; the verdict needs 1000" if reading else "no reading")

# The arm that keeps only the Sombunal questions: exact by construction
model.reset("counter")
with quiet(), environment(OLLAMA_HOST=model.url):
    control = run_report.run_arm(0, 60, False, no_log, backend="ollama", profile="minimal")
    arms = {channels: run_report.run_arm(0, 60, True, no_log, backend="ollama", profile="minimal",
                                         channels=channels)
            for channels in ("none", "questions", "all")}
model.close()
asked = {channels: sum(t["sombunal_question"] for t in r["trace"]) for channels, r in arms.items()}
check("withholding every channel through the model path gives the control, bit for bit",
      arms["none"]["ledger_head"] == control["ledger_head"] and arms["none"]["llm"]["health"]["calls"] == 0)
check("the questions-only arm asks the model nothing but the Sombunal questions, as often as the full arm",
      set(arms["questions"]["llm"]["health"]["calls_by_kind"]) == {"sombunal_question"}
      and asked["questions"] == asked["all"] > 0, f"{asked['questions']} questions in both")


# A view that drifts from the code it shows is wrong without an error anywhere. Each
# visualizer is one file that opens alone, so the names and constants it shares with
# the framework are written in it; these checks read them from both files and compare
# them with the framework and with each other. The formulas the inspector mirrors are
# not compared here: that needs a browser.
check.section("6 · The visualizers and the framework")


def declared(html, name):
    """The right-hand side of a visualizer's top-level `const <name> = …;`."""
    found = re.search(rf"^const {name} = (.*?);[ \t]*(?://[^\n]*)?\n", html, re.M | re.S)
    return found.group(1) if found else ""


def quoted(text):
    return re.findall(r"'([^']*)'", text)


def tokens(html):
    """The colour tokens of a visualizer: the custom properties of its :root."""
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+?)\s*;", re.search(r":root\s*\{(.*?)\}", html, re.S).group(1)))


views = {name: (HERE / f).read_text(encoding="utf-8") for name, f in
         (("live", "Sirisys_Live_Visualizer.html"), ("inspector", "Sirisys_Static_Visualizer.html"))}
framework_source = Path(S.__file__).read_text(encoding="utf-8")
modes_source = inspect.getsource(S.ConcordancyField.compute_existence_mode)
framework_names = {
    "layers": [layer.name for layer in sorted(S.Layer, key=lambda layer: layer.value)],
    "states": [s.value for s in S.TetraState],
    "modes": set(re.findall(r'return "([A-Z]+)"', modes_source)),
    "zero points": set(S.ZERO_POINTS),
    "anchors": set(S.ANCHORS),
    "Lagrangian points": {p.value for p in S.LagrangianPoint},
}
drift = []
for view, html in views.items():
    zero_points = set(quoted(declared(html, "ZERO_POINTS")))
    anchors = set(quoted(declared(html, "ANCHORS"))) | (zero_points if "...ZERO_POINTS" in declared(html, "ANCHORS") else set())
    carried = {
        "layers": quoted(declared(html, "LAYERS")),
        "states": quoted(declared(html, "STATES")),
        "modes": set(quoted(declared(html, "MODES"))),
        "zero points": zero_points,
        "anchors": anchors,
        "Lagrangian points": set(re.findall(r"\b(L\d):", declared(html, "LAGRANGE"))),
    }
    drift += [f"{view}: {what}" for what in framework_names if carried[what] != framework_names[what]]
    if declared(html, "APPARENT") != str(S.Layer.APPARENT.value):
        drift.append(f"{view}: APPARENT")
check("both visualizers carry the framework's names: layers and edge states in order, existence modes, "
      "Zero Points, anchors, Lagrangian points", not drift, ", ".join(drift) or "live and inspector agree with the framework")

inspector = views["inspector"]
relations_of = lambda kind: set(re.findall(r'"([A-Z]+)"', re.search(rf"{kind}_relations\s*=\s*\{{([^}}]*)\}}", modes_source).group(1)))
LEDGER_ONLY = {"TERMINATE", "SHIFT"}                # sealed in the ledger, never attached to a construct
constants = {
    "ERA_CAPACITY": S.InternalClock.ERA_CAPACITY,
    "DECAY": S.InternalClock.DECAY,
    "VC_UNSTABLE": float(re.search(r"Vc_THRESHOLD\s*=\s*([\d.]+)", inspect.getsource(S.Sombunal.global_instability)).group(1)),
    "EXCHANGE_QUANTUM": S.TetralemmaEngine.EXCHANGE_QUANTUM,
}
drift = [name for name, value in constants.items() if float(declared(inspector, name) or "nan") != value]
for kind in ("omega", "lemniscate"):
    if set(quoted(declared(inspector, f"{kind.upper()}_RELATIONS"))) != relations_of(kind):
        drift.append(f"{kind.upper()}_RELATIONS")
if set(quoted(declared(inspector, "PROOF_RELATIONS"))) != set(re.findall(r'relation\s*=\s*"([A-Z]+)"', framework_source)) - LEDGER_ONLY:
    drift.append("PROOF_RELATIONS")
check("the inspector's constants are the framework's: the clock, the Vc threshold, the exchange quantum, "
      "the relations of each existence mode, the relations a construct's proofs can carry",
      not drift, ", ".join(drift) or f"{len(constants) + 3} constants agree")

live_tokens, inspector_tokens = tokens(views["live"]), tokens(inspector)
shared = set(live_tokens) & set(inspector_tokens)
differ = sorted(t for t in shared if live_tokens[t] != inspector_tokens[t])
# Written once in each file, alike: the strata, how an edge state and a mode are drawn and written
SHARED = ("RINGS", "EDGE_STYLE", "EXCHANGE_QUANTUM", "STATE_MEANING", "MODE_SIGN", "MODE_MEANING", "modeText",
          "LAGRANGE", "lagrangeText", "ARROW_ZOOM", "QUIET")
unlike = [name for name in SHARED if not declared(views["live"], name) or declared(views["live"], name) != declared(inspector, name)]
if declared(views["live"], "HISTORY_KEPT") != str(server.HISTORY_KEPT):     # the live view merges as the server does
    unlike.append("HISTORY_KEPT (live and server)")


def function(html, name):
    """The whole of a visualizer's top-level `function <name>(…) {…}`."""
    found = re.search(rf"^function {name}\(", html, re.M)
    if not found:
        return ""
    depth, at = 0, html.index("{", found.end())
    for at in range(at, len(html)):
        depth += {"{": 1, "}": -1}.get(html[at], 0)
        if depth == 0:
            break
    return html[found.start():at + 1]


DRAWN_ALIKE = ("shapeOf", "tracePolygon", "traceShape", "line", "ring", "arrowhead", "drawRelation", "edgeMark",
               "renderBreakdown", "renderLagrangian", "buildFilters")
unlike += [f"{name}()" for name in DRAWN_ALIKE if not function(views["live"], name)
           or function(views["live"], name) != function(inspector, name)]
check("the two views agree with each other and the live view with its server: the strata rings, how each edge "
      "state and mode is drawn and written, the functions they draw with, every colour token both define, "
      "the history kept", not unlike and len(shared) > 20 and not differ, ", ".join(unlike + differ)
      or f"{len(SHARED)} declarations, {len(DRAWN_ALIKE)} functions and {len(shared)} colour tokens alike")

check.finish()
