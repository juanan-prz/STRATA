"""Everything around the field: the experiment engine, the model backends, the
profiles, the web layer, the model-health watch, the experiment tools
(run_report.py, live_c2.py), and the names and constants the visualizers share
with the framework.
No API key, no Ollama and no FastAPI needed: a local fake model, and a stub in
place of the web framework.
Usage: python3 test_phase1.py"""
import hashlib
import inspect
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

import field_topology
from sirisys_measures import (
    AnswerRecord,
    LifeCriteria,
    ModelHealth,
    PerceptRecord,
    Translations,
    percepts_line,
)
from sirisys_testkit import (
    HERE,
    Checks,
    FakeModel,
    environment,
    fresh_framework,
    quiet,
    raises,
    read_jsonl,
    scratch,
)

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


def criteria_names():
    """The criteria the verdict judges (the exploratory measures are not among them)."""
    return list(LifeCriteria.RULE)


def perceived_the_hour(run_dir):
    """A PERCEIVE proof names its percept in its id: perceive::<target>."""
    return any(r["relation"] == "PERCEIVE" and r["id"].startswith("perceive::time::")
               for r in read_jsonl(run_dir / "ledger.jsonl"))


def run(args, folder, timeout=300, **env):
    """A tool run as the user runs it: a separate process in `folder`."""
    return subprocess.run([sys.executable, *args], cwd=folder, capture_output=True, text=True,
                          timeout=timeout, env={**os.environ, **env}, check=False)


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


def support_reads_as_it_holds(field, constructs):
    """Each crystal's support in a snapshot, as ConcordancyField.edge_holds tests it: held by a BOTH
    edge exactly when one holds, and the strongest ageing support still holding as many breaths
    ahead as the snapshot says, and not one more. Anchors and open constructs carry none."""
    for c in constructs:
        layer, s = S.Layer(c["layer"]), c.get("support")
        if layer != S.Layer.APPARENT or c["name"] in S.ANCHORS:
            if s is not None:
                return False
            continue
        into = [e for e in field.edges if e.tgt == c["name"]]
        ageing = [e for e in into if e.state != S.TetraState.BOTH]
        both = any(e.state == S.TetraState.BOTH and field.edge_holds(e, into_crystal=True) for e in into)
        if s is None or s["edges"] != len(into) or (s["both_from"] is not None) != both:
            return False
        left = s["breaths_left"]
        if left is not None and not (any(field.edge_holds(e, True, ahead=math.floor(left - 0.01)) for e in ageing)
                                     and not any(field.edge_holds(e, True, ahead=math.ceil(left + 0.01)) for e in ageing)):
            return False
    return True


crystal_cards = sum(1 for c in snapshots[-1]["field"]["constructs"] if c.get("support"))
check("cycles stream as snapshots, and each crystal's support in them reads as the framework's existence test "
      "holds it (a BOTH edge, or the breaths its strongest ageing support has left)",
      len(snapshots) >= 30 and expected <= snapshots[-1].keys()
      and all("energy" in c for c in snapshots[-1]["field"]["constructs"])
      and crystal_cards > 0 and support_reads_as_it_holds(engine.ss.field, snapshots[-1]["field"]["constructs"]),
      f"{len(snapshots)} snapshots; {crystal_cards} crystals with their support")
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
kept = [percepts_line(events) for events in PerceptRecord.read(S, first_run / PerceptRecord.FILE)]
check("serving the field changes nothing in it: the same ledger head as the bare cycle; "
      "it keeps, cycle by cycle, the percepts it gave the field",
      bare.get_ledger().head == head_then
      and kept[:cycles_run] == [percepts_line(bare.synthetic_percepts(n, 0, True)) for n in range(cycles_run)],
      f"{cycles_run} cycles, head {head_then[:12]}…; {len(kept)} cycles of percepts kept")
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
ended = json.loads((first_run / "state.json").read_text(encoding="utf-8"))
criteria_saved = json.loads((first_run / "criteria.json").read_text(encoding="utf-8"))
check("reset opens a new run folder, old one kept (its state, its criteria and its percepts, through its "
      "last cycle), and starts its history again",
      reset["ok"] and engine.run_dir != first_run
      and criteria_saved["cycles"] == ended["cycle"] == len(PerceptRecord.read(S, first_run / PerceptRecord.FILE))
      and set(LifeCriteria.RULE) <= set(criteria_saved["checks"])
      and engine.history() == {"run": engine.run_dir.name, "through_cycle": -1, "records": []},
      f"{first_run.name} → {engine.run_dir.name}; {ended['cycle']} cycles kept")
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
      len(spans) <= 5 and spans[0][0] == 0 and all(a[1] + 1 == b[0] for a, b in pairwise(spans))
      and merged["records"][0]["cycles"][0] == 0 and merged["through_cycle"] == last_cycle
      and all(a["cycles"][1] + 1 == b["cycles"][0] for a, b in pairwise(merged["records"])),
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
with FakeModel("counter") as model:
    with quiet():
        llm = S.LLMIntermediary(backend="ollama", host=model.url)
        first = llm.propose_emergent("A", "B", "TRUE", "BOTH")
        llm.question_sombunal(0.5)
        llm.interpret_conflict("A", "C")
        llm.question_sombunal(0.6)
        again = llm.propose_emergent("A", "B", "TRUE", "BOTH")
    sent = [r["messages"] for r in model.requests]
thread = json.dumps(llm.history)
check("a name is asked for without memory: its request carries the prompt alone, it leaves nothing in the "
      "thread, and the same name asked again sends the same request; the question keeps its thread",
      [len(m) - 1 for m in sent] == [1, 1, 1, 3, 1] and sent[0] == sent[4]
      and "Concordancy" not in thread and "Reversion" not in thread and len(llm.history) == 4
      and sent[3][1]["content"].startswith("Instability: 0.5000"),
      f"messages sent besides the system prompt: {[len(m) - 1 for m in sent]}; thread: {len(llm.history)} messages")
check("a name is the first non-empty line of the model's answer: a note after it is dropped, and the label "
      "is still clipped",
      S.LLMIntermediary._name_of("Umbraic\n\nNote: the Sombunal is whispering") == "Umbraic"
      and S.LLMIntermediary._name_of("\n  Discordia Apparens  \n(Explanation: ...)") == "Discordia Apparens"
      and S.LLMIntermediary._name_of("") == "" and S.LLMIntermediary._name_of("x" * 300).endswith("…"),
      repr(S.LLMIntermediary._name_of("Umbraic\n\nNote: the Sombunal is whispering")))
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


def ledger_of_life(llm, cycles=60, stream=0):
    """The ledger head after a short life on a synthetic stream."""
    with quiet():
        ledger = S.set_ledger(S.ProofLedger(None))
        ss = S.new_session(llm)
        for c in range(cycles):
            S.run_cycle(ss, c, percepts=S.synthetic_percepts(c, stream, False), narrate=False, include_hour=False)
    return ledger.head


with FakeModel("empty") as silent:
    with quiet():
        mute = S.LLMIntermediary(backend="ollama", host=silent.url)
        control = S.LLMIntermediary(backend="none")
    muted, alone = ledger_of_life(mute), ledger_of_life(control)
    asked = len(silent.requests)
check("a model that only answers empty leaves the field exactly where the control is "
      "(no answer reaches the dynamics)", asked > 0 and muted == alone,
      f"{asked} empty answers; same ledger: {muted == alone}")

# The approach to the Sombunal, a law of the field: once per breath, with no model
with quiet():
    S.set_ledger(S.ProofLedger(None))
    ss = S.new_session(S.LLMIntermediary(backend="none"))
    made, operands, related = [], set(), []
    for c in range(300):
        r = S.run_cycle(ss, c, percepts=S.synthetic_percepts(c, 0, False), narrate=False, include_hour=False)
        made.append(r["approach"])
        operands |= {op.get(k) for op in ss.concordancy.ops_log if op.get("cycle") == c for k in ("x", "y")}
        if r["approach"]:                           # the edge to the I, as the cycle leaves it
            related.append(any(e.src == "I::Am" and e.rel == "APPROACHES" and e.tgt == r["approach"]
                               and e.state == S.TetraState.NEITHER for e in ss.field.edges))
every = S.SOMBUNAL_APPROACH_EVERY
expected = [f"SOMBUNAL::approach@c{c}" if c % every == 0 else None for c in range(300)]
check("the I approaches the Sombunal once per breath, with no model: a construct the field names, related to "
      "the I and never an operand of [::]",
      made == expected and every == S.BREATH_PERIOD and related and all(related)
      and not any(str(o).startswith("SOMBUNAL::approach@") for o in operands),
      f"{sum(1 for m in made if m)} approaches in 300 cycles, each related to I::Am (NEITHER): {all(related)}")

janus = S.Construct("Janus test", S.Layer.UMBRA_0)
janus.label = "Janus"
back = S.Construct.from_dict(json.loads(json.dumps(janus.to_dict())))
old_state = janus.to_dict()
old_state.pop("label")
check("a construct's label survives a save and a resume; a v13.4 state, which has none, resumes with none",
      back.label == "Janus" and back.shown == "Janus" and S.Construct.from_dict(old_state).label == ""
      and S.Construct.from_dict(old_state).shown == "Janus test")

saved_psutil = sys.modules.get("psutil")
sys.modules["psutil"] = None                        # import psutil now fails, as on a machine without it
try:
    blind = not S.real_percepts_available() and raises(S.perceive_real, S.NoPerception)
    refused = server.live_refused(None)
finally:
    if saved_psutil is None:
        sys.modules.pop("psutil", None)
    else:
        sys.modules["psutil"] = saved_psutil
check("without psutil the framework says the machine cannot be perceived, instead of fixed readings, "
      "and experiment mode refuses live percepts", blind and refused and "psutil" in refused
      and server.live_refused(0) is None and server.live_refused(None) is None)

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
    srv.serve(srv.parse_args(['--delay-ms', '0']))
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


probed = intermediary()
probe = ModelHealth.probe(probed, cycles=100, calls_per_cycle=4)
asked = [r["messages"][-1]["content"].split(":")[0] for r in model.requests]
sent = [len(r["messages"]) - 1 for r in model.requests]          # messages besides the system prompt
check("the probe accepts a model that answers, asking for one name of each kind, without memory, and "
      "times a question that carries a run's full thread; it leaves no thread behind",
      probe["ok"] and all(probe["answers"]) and asked == ["Concordancy", "Reversion", "Instability"]
      and sent == [1, 1, S.LLM_CONTEXT] and "call_full_context_s" in probe
      and probed.history == [] and probe.get("estimated_model_hours_max") is not None,
      f"{probe.get('answers')} for {asked[:2]}; context sent {sent}")
system = model.requests[0]["messages"][0]["content"]
asks = [r["messages"][-1]["content"] for r in model.requests]
check("the model is asked for names alone; its rule of 1–3 sentences is for every other answer",
      all("Reply with the name alone" in a for a in asks[:2]) and "Reply with the name alone" not in asks[2]
      and "Asked to name a construct: reply with the name alone" in system
      and "Any other answer: 1–3 sentences" in system and "Responses: 1–3 sentences" not in system,
      f"{len(asks[:2])} naming requests and a question")
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

check.section("5 · The replay of a run (Sirisys_Server.py --replay)")


def every_snapshot(engine, until, press_play=False):
    """Every snapshot the engine makes until `until()`; with press_play, Play again whenever it pauses itself."""
    taken = []
    engine.running = True
    end = time.time() + 120
    while not until() and time.time() < end:
        taken += engine.drain()
        if press_play and not engine.running:
            engine.control("play")
        time.sleep(0.01)
    engine.running = False
    time.sleep(0.2)
    return taken + engine.drain()


def files_of(folder):
    return {f.name: (f.stat().st_size, f.stat().st_mtime_ns) for f in folder.iterdir()}


def replayed(folder):
    """A replay of `folder` played to its end: (the engine, every snapshot it made)."""
    with quiet():
        engine = server.ReplayEngine(folder, 0)
        return engine, every_snapshot(engine, lambda: engine.ended)


# A run whose model answers for a while and then fails: answers, failures and a watch that trips
model.reset("error", after=60)
server.log.disabled = True
with quiet(), environment(SIRISYS_LLM_BACKEND="ollama", OLLAMA_HOST=model.url):
    recorded = server.ExperimentEngine(stream=0, delay_ms=0, runs_dir=scratch())
    as_lived = every_snapshot(recorded, lambda: recorded.cycle >= 40, press_play=True)
    recorded.shutdown()
calls, folder = model.calls, recorded.run_dir
header, answered = AnswerRecord.read(folder / AnswerRecord.FILE)
answers = [a for c in sorted(answered) for a in answered[c]]
check("the experiment mode keeps every answer its model gave, in order, and every failure, beside the "
      "percepts: which model, then each cycle's answers as the cycle ends",
      header == {"backend": "ollama", "model": FakeModel.MODEL, "available": True, "profile": "standard"}
      and len(answers) == calls and answers[:60] == [f"Name {n}" for n in range(1, 61)]
      and all(isinstance(a, dict) and "500" in a["error"] for a in answers[60:]) and len(answers) > 60
      and set(answered) <= set(range(recorded.cycle)),
      f"{len(answers)} answers kept of {calls} calls, {len(answers) - 60} of them failures")

before, mid_watch = files_of(folder), next((s["cycle"] for s in as_lived if s["model_watch"]["tripped"]), None)
replay, again = replayed(folder)
differ = sorted({key for a, b in zip(as_lived, again, strict=False) for key in a
                 if key not in ("criteria", "replay") and a[key] != b.get(key)})
state = replay.status()
check("a replay lives the run again as it went, without asking any model: every snapshot the same (the "
      "field, the labels, the narration, the questions, the console, the metabolism, the model watch), "
      "and the same ledger, proof by proof",
      len(again) == len(as_lived) == recorded.cycle and not differ and model.calls == calls
      and state["mode"] == "replay" and state["model"]["recorded"] and state["replay"]["ended"]
      and state["replay"]["same_ledger"] is True and state["replay"]["compared_through"] == recorded.cycle - 1
      and (state["replay"]["unanswered"], state["replay"]["unasked"]) == (0, 0)
      and again[-1]["replay"]["ended"] and again[-1]["ledger"] == as_lived[-1]["ledger"],
      f"{len(again)} of {len(as_lived)} snapshots; differing: {differ or 'nothing'}")
check("a replay shows the failures as they happened, the watch tripping at the same cycle, without "
      "stopping for it, and writes nothing in the run's folder",
      mid_watch is not None and next(s["cycle"] for s in again if s["model_watch"]["tripped"]) == mid_watch
      and any("[LLM] Call failed" in line for s in again for line in s["log"]) and files_of(folder) == before,
      f"the watch tripped at cycle {mid_watch} both times")

# Played again: Play at the end, or Reset, start it over as a play of its own; nobody reading, it waits
replay.control("play")
waited = wait_for(lambda: replay.cycle == server.REPLAY_AHEAD, 10)
time.sleep(0.3)
second = (replay.run_name, replay.cycle, len(replay.drain()))
replay.control("reset")
check("Play at the end, and Reset, play it again from its first cycle, each play named apart; with "
      "nobody reading, a replay waits a few cycles ahead, so every cycle reaches the view",
      waited and second == (f"{folder.name} #2", server.REPLAY_AHEAD, server.REPLAY_AHEAD)
      and replay.run_name == f"{folder.name} #3" and replay.cycle == 0
      and replay.control("step")["ok"] and not replay.ended, str(second))
replay.shutdown()

# What the replay says when the record does not hold the run: a percept changed, the answers lost
altered, mute = scratch() / folder.name, scratch() / folder.name
for copy in (altered, mute):
    shutil.copytree(folder, copy)
lines = (altered / PerceptRecord.FILE).read_text(encoding="utf-8").splitlines()
lines[10] = lines[10].replace("PERCEIVES ", "PERCEIVES altered", 1)
(altered / PerceptRecord.FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
(mute / AnswerRecord.FILE).unlink()
departed, _ = replayed(altered)
silent, unlabelled = replayed(mute)
check("a replay says where its ledger departs from the run's (a percept changed in the record)",
      departed.status()["replay"]["differs_at"] == 10 and departed.status()["replay"]["same_ledger"] is False
      and departed.status()["replay"]["compared_through"] == 9, str(departed.status()["replay"]))
check("a run recorded before its answers were kept replays to the same ledger, without labels, narration "
      "or questions, and says so",
      silent.status()["replay"]["same_ledger"] is True and silent.status()["model"]["recorded"] is False
      and not any(c["label"] for s in unlabelled for c in s["field"]["constructs"])
      and not any(s["narration"] or s["question"] for s in unlabelled), str(silent.status()["model"]))
with quiet():                                       # and one that ran without a model, recorded likewise
    modelless = server.ExperimentEngine(stream=0, delay_ms=0, runs_dir=scratch())
    every_snapshot(modelless, lambda: modelless.cycle >= 20)
    modelless.shutdown()
(modelless.run_dir / AnswerRecord.FILE).unlink()
bare, _ = replayed(modelless.run_dir)
check("a run recorded before its answers were kept, whose saved state holds no label, replays as a run "
      "without a model, and nothing is said missing",
      bare.status()["replay"]["answers"] and bare.status()["model"]["active"] is False
      and bare.words == "without a model" and silent.words == "the model's answers not recorded"
      and bare.status()["replay"]["same_ledger"] is True, bare.words)
for engine in (departed, silent, bare):
    engine.shutdown()

runs = scratch()
for name, keep in (("20260101-000000_live", ("ledger.jsonl",)), ("20260102-000000_live", None),
                   ("20260103-000000_live", ("ledger.jsonl", PerceptRecord.FILE))):
    (runs / name).mkdir()
    for f in keep or ():
        (runs / name / f).write_text("" if f == PerceptRecord.FILE else "{}\n", encoding="utf-8")
shutil.copytree(folder, runs / "20260104-000000_live_minimal")
(runs / "20260105-000000_live").mkdir()
(runs / "20260105-000000_live" / "ledger.jsonl").write_text("", encoding="utf-8")
(runs / "20260105-000000_live" / PerceptRecord.FILE).write_text("", encoding="utf-8")     # nothing recorded yet
refusals = [server.replay_refused(runs / name) or "" for name in
            ("20260101-000000_live", "20260102-000000_live", "20260103-000000_live")]
asked_for = server.parse_args(["--replay", "last"])
check("--replay last finds the latest run that has recorded a cycle; a replay listens on 8001 by default; "
      "a run from before percepts.jsonl, a folder that is not a run, a run with no cycle yet, and "
      "--stream or --profile beside --replay are refused, saying why",
      server.find_run("last", runs) == runs / "20260104-000000_live_minimal"
      and server.find_run(str(runs / "20260104-000000_live_minimal" / "ledger.jsonl"), runs).name.endswith("_minimal")
      and asked_for.port is None and server.PORTS["replay"] == 8001
      and "cannot be replayed" in refusals[0] and "not a run folder" in refusals[1] and "not recorded a cycle" in refusals[2]
      and raises(lambda: server.make_engine(server.parse_args(["--replay", "last", "--stream", "0"])), SystemExit),
      " · ".join(r[:40] for r in refusals))

# The record of the answers across a crash, as the percepts': a line cut short skipped, a cycle written twice
torn = scratch()
record = AnswerRecord(torn, SimpleNamespace(backend="none", model=None, available=False))
record._answers = ["one"]
record.add(0)
record.close()
with (torn / AnswerRecord.FILE).open("a", encoding="utf-8") as f:
    f.write('{"cycle": 1, "answ')
record = AnswerRecord(torn, SimpleNamespace(backend="none", model=None, available=False))
for cycle, said_then in ((1, "two"), (2, "three"), (2, "three, again")):
    record._answers = [said_then]
    record.add(cycle)
record.close()
check("the record of the answers survives a crash: a line cut short is skipped, a cycle run again keeps "
      "its later line, the model it names is written once",
      AnswerRecord.read(torn / AnswerRecord.FILE)
      == ({"backend": "none", "model": None, "available": False, "profile": None},
          {0: ["one"], 1: ["two"], 2: ["three, again"]}),
      str(AnswerRecord.read(torn / AnswerRecord.FILE)))
server.log.disabled = False

check.section("6 · The measures and the experiment tools: run_report.py and live_c2.py")
check("psutil is installed: the field can perceive this machine (without it, it cannot)",
      S.real_percepts_available())
# The uncertainty of the instant (read-only, exploratory): open sums in flight, constructs landed,
# how the weight is held, and the I's state
with quiet():
    S.set_ledger(S.ProofLedger(None))
    us = S.new_session(S.LLMIntermediary(backend="none"))
    life = LifeCriteria(S)
    for c in range(60):
        S.run_cycle(us, c, percepts=S.synthetic_percepts(c, 0, False), narrate=False, include_hour=False)
        life.after_cycle(us, c, 0.0)
head_before = S.get_ledger().head
zp = frozenset(S.ZERO_POINTS)
q = S.TetralemmaEngine.EXCHANGE_QUANTUM
before = [(e.src, e.tgt, e.weight, e.state, e.both_age) for e in us.field.edges]
u = field_topology.uncertainty_of_the_instant(us.field, zp, quantum=q)
live = [e for e in us.field.edges if e.src not in zp and e.tgt not in zp]
open_ch = [min(1.0, e.weight * e.both_age / q) for e in live if e.state == S.TetraState.BOTH]
names = [n for n in us.field.constructs if n not in S.ANCHORS]
res = life.result()
check("the uncertainty of the instant counts the BOTH channels still open and the exchange they carry toward "
      "the quantum, the share of constructs that have landed as Apparents, and how the weight is held; it reads "
      "without touching the field, and the life criteria keep it per 1000-cycle window",
      u["open"] == len(open_ch) and abs(u["in_flight"] - sum(open_ch)) < 1e-3
      and abs(u["landed"] - sum(us.field.constructs[n].layer == S.Layer.APPARENT for n in names) / len(names)) < 1e-3
      and abs(sum(u["held"].values()) - 1) < 1e-3 and u["i_am"] in field_topology.STATES
      and field_topology.uncertainty_of_the_instant.__defaults__[1] == q
      and [(e.src, e.tgt, e.weight, e.state, e.both_age) for e in us.field.edges] == before
      and S.get_ledger().head == head_before
      and all(len(v) == 1 for v in res["instant_per_1000"].values())
      and abs(sum(res["i_am_states"].values()) - 1) < 0.01
      and "instant" in field_topology.field_topology(us.field, cycle=60, zero_points=set(zp)),
      f"open {u['open']}, in flight {u['in_flight']} quanta, landed {u['landed']}, held {u['held']}, "
      f"I::Am {u['i_am']}")
TOOL_FILES = ("run_report.py", "live_c2.py", "sirisys_loader.py", "field_topology.py", "sirisys_measures.py",
              S.__sirisys_file__)
tools = scratch()                                   # copies: nothing here touches the user's reports
for f in TOOL_FILES:
    shutil.copy(HERE / f, tools / f)
model.reset("error", after=30)
p = run(["live_c2.py", "60", "ollama", "minimal"], tools, OLLAMA_HOST=model.url)
out = json.loads(p.stdout) if p.stdout.strip() else {}
check("live_c2 stops (exit 3) when the model starts failing mid-run, and says so",
      p.returncode == 3 and out.get("aborted") and "STOPPED" in p.stderr, str(out.get("aborted"))[:80])
sha = hashlib.sha256((HERE / S.__sirisys_file__).read_text(encoding="utf-8").encode()).hexdigest()[:16]
ran_on = out.get("machine") or {}
check("live_c2 records the framework's sha256[:16], the machine it ran on and when",
      out.get("framework_sha256_16") == sha and ran_on.get("python") and ran_on.get("psutil")
      and ran_on.get("cpu_count") and out.get("timestamp"),
      f"{out.get('framework_sha256_16')} · {ran_on.get('system')} {ran_on.get('arch')} · psutil {ran_on.get('psutil')}")
p = run(["run_report.py", "--backend", "ollama", "--cycles", "5", "--seeds", "1"], tools, 120,
        OLLAMA_HOST="http://127.0.0.1:9")
check("run_report --backend ollama stops before running when the model is not there",
      p.returncode == 3 and "Nothing was run" in p.stdout and not (tools / "sirisys_report.json").exists())

p = run(["live_c2.py", "40", "none", "minimal"], tools, 120)
(tools / "recorded.json").write_text(p.stdout, encoding="utf-8")
first = json.loads(p.stdout) if p.returncode == 0 else {}
p = run(["live_c2.py", "40", "none", "minimal", "--replay", "recorded.json"], tools, 120)
again = json.loads(p.stdout) if p.returncode == 0 else {}
check("live_c2 --replay feeds a recorded life's percepts back: without a model it seals the same ledger",
      first.get("ledger_head") and again.get("ledger_head") == first.get("ledger_head")
      and again.get("percept_sequence") == first.get("percept_sequence")
      and again.get("replayed_from", {}).get("ledger_head") == first.get("ledger_head"),
      f"{str(first.get('ledger_head'))[:16]} both times")

model.reset("counter")
p = run(["live_c2.py", "40", "ollama", "minimal"], tools, 300, OLLAMA_HOST=model.url)
(tools / "with_model.json").write_text(p.stdout, encoding="utf-8")
with_model = json.loads(p.stdout) if p.returncode == 0 else {}
p = run(["live_c2.py", "40", "none", "minimal", "--replay", "with_model.json"], tools, 120)
paired = json.loads(p.stdout) if p.returncode == 0 else {}
check("a live life with a model, replayed without it, seals the same ledger, and the replay says so "
      "(the model never reaches the dynamics)",
      with_model.get("model_active") and with_model.get("llm_calls", 0) > 0 and with_model.get("labels")
      and paired.get("same_ledger_as_replayed") is True and "same ledger as the replayed run: YES" in p.stderr,
      f"{with_model.get('llm_calls')} model calls; same ledger: {paired.get('same_ledger_as_replayed')}")

with quiet():                                       # a life read from this machine, in the experiment mode
    lived = server.ExperimentEngine(stream=None, delay_ms=0, runs_dir=scratch())
    lived.running = True
    wait_for(lambda: lived.cycle >= 40)
    lived.shutdown()
p = run(["live_c2.py", "100000", "none", "standard", "--replay", str(lived.run_dir / PerceptRecord.FILE)], tools, 300)
from_server = json.loads(p.stdout) if p.returncode == 0 else {}
# The record across a crash: a line cut short is skipped, and a cycle run again keeps its later line
torn, seen = scratch(), [S.synthetic_percepts(n, 0, True) for n in range(5)]
record = PerceptRecord(torn)
record.add(0, seen[0])
record.add(1, seen[1])
record.close()
with (torn / PerceptRecord.FILE).open("a", encoding="utf-8") as f:
    f.write('{"cycle": 2, "perc')
record = PerceptRecord(torn)
record.add(2, seen[2])
record.add(3, seen[3])
record.add(3, seen[4])                              # cycle 3 run again after a crash, on other percepts
record.close()
check("a life the experiment mode read from this machine replays from its run folder (percepts.jsonl) "
      "to the same ledger; the record survives a crash",
      from_server.get("cycles") == lived.cycle and from_server.get("same_ledger_as_replayed") is True
      and "same ledger as the replayed run: YES" in p.stderr
      and [percepts_line(e) for e in PerceptRecord.read(S, torn / PerceptRecord.FILE)]
      == [percepts_line(e) for e in (seen[0], seen[1], seen[2], seen[4])],
      f"{from_server.get('cycles')} cycles; same ledger: {from_server.get('same_ledger_as_replayed')}")

bare = scratch()                                    # the same tools on a machine without psutil
for f in TOOL_FILES:
    shutil.copy(HERE / f, bare / f)
(bare / "psutil.py").write_text('raise ImportError("psutil hidden for this test")\n', encoding="utf-8")
p = run(["live_c2.py", "5"], bare, 120)
out_bare = json.loads(p.stdout) if p.stdout.strip() else {}
check("without psutil live_c2 does not start (exit 2) and says why, instead of perceiving fixed values",
      p.returncode == 2 and "psutil" in str(out_bare.get("aborted")) and "STOP" in p.stderr and "psutil" in p.stderr,
      str(out_bare.get("aborted"))[:80])
p = run(["run_report.py", "--percepts", "live", "--backend", "none", "--cycles", "5", "--seeds", "1"], bare, 120)
refused = p.returncode == 2 and "psutil" in p.stdout and not (bare / "sirisys_report.json").exists()
p = run(["run_report.py", "--backend", "none", "--cycles", "5", "--seeds", "1"], bare, 120)
written = bare / "sirisys_report.json"
recorded = json.loads(written.read_text())["config"].get("machine", {}) if p.returncode == 0 and written.exists() else {}
p2 = run(["run_report.py", "--backend", "none", "--cycles", "5", "--first-seed", "3", "--seeds", "2"], bare, 120)
batch = json.loads(written.read_text())["config"].get("streams") if p2.returncode == 0 else None
check("run_report --first-seed runs a confirmation batch on streams the experiment did not use",
      batch == [3, 4], f"streams {batch}")
check("run_report with live percepts does not start without psutil either; synthetic runs need none, "
      "and the report records the machine",
      refused and recorded.get("python") and recorded.get("psutil") is None and "machine" in p.stdout,
      f"live refused: {refused}; synthetic ran and recorded {recorded.get('system')} {recorded.get('arch')}")

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
check("the determinism check, in its own file: a model whose answers carry state answers otherwise, "
      "and the ledger is the same (a model never reaches the dynamics)",
      alike.get("same") is True and stateful.get("same") is True
      and (stateful.get("example_different_answers") or {}).get("first") is not None
      and not (tools / "sirisys_report.json").exists(),
      f"alike: same ledger {alike.get('same')}; stateful: same ledger {stateful.get('same')}, "
      f"answers that differ: {stateful.get('example_different_answers')}")

model.reset("counter")
p = run(["run_report.py", "--backend", "ollama", "--profile", "minimal", "--cycles", "30", "--seeds", "1"],
        tools, OLLAMA_HOST=model.url)
written = tools / "sirisys_report.json"
same = json.loads(written.read_text()).get("same_ledger") if p.returncode == 0 and written.exists() else None
written.unlink(missing_ok=True)
check("run_report says whether every arm sealed the same ledger, and they do",
      same is True and "same ledger in every arm: YES" in p.stdout, f"same_ledger {same}")

model.reset("alike")
p = run(["run_report.py", "--backend", "ollama", "--profile", "minimal", "--cycles", "8", "--seeds", "1",
         "--skip-questions-arm", "--skip-null-arm", "--skip-degraded"], tools, OLLAMA_HOST=model.url)
progress = [line.split()[1] for line in p.stdout.splitlines() if line.startswith("    cycle ")]
given = [line for line in p.stdout.splitlines() if line.split()[:1] == ["names"]]
(tools / "sirisys_report.json").unlink(missing_ok=True)
check("a short run shows its progress, and at the end the names the model gave (Rule 0.4)",
      p.returncode == 0 and progress == ["0", "2", "4", "6"] and given and "Name " in given[0],
      f"progress at cycles {progress}; {given[0].strip()[:60] if given else 'no names line'}")

with quiet():
    import run_report
    first, again = (run_report.run_arm(0, 30, False, no_log, profile="minimal") for _ in range(2))
    other = run_report.run_arm(1, 30, False, no_log, profile="minimal")
distinct = first["percept_catalog"]["distinct_targets"]
with quiet():
    lived = run_report.run_arm(2, 300, False, no_log, profile="minimal")
c = lived["criteria"]
check("the exploratory flicker after the genesis counts only crystals born after it, beside the criterion",
      "flicker_share_after_genesis" in c and 0 <= c["flicker_share_after_genesis"] <= 1
      and "flicker_share_after_genesis" not in str(criteria_names()),
      f"flicker {c['flicker_share']}, after the genesis {c['flicker_share_after_genesis']}")
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


def untimed(r):
    """A result without its cost, which is a time."""
    return {k: v for k, v in json.loads(json.dumps(r)).items() if k != "ms_first_last"}


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
# The semantic null: the full arm's answer shape, replayed without meaning and without the model
requests_before = len(model.requests)
with quiet():
    null = run_report.run_arm(0, 60, True, no_log, profile="minimal", channels="null",
                              shape=arms["all"]["answer_shape"])
model.close()
full_shape, null_shape = arms["all"]["answer_shape"], null["answer_shape"]


def lengths(shape, kind):
    return [n for k, n in shape if k == kind]


replayed = all(lengths(null_shape, k)[:len(lengths(full_shape, k))]
               == lengths(full_shape, k)[:len(lengths(null_shape, k))]
               for k in {k for k, _ in null_shape})             # past the recorded answers it starts over
check("the semantic null answers with the full arm's lengths, kind by kind and in order, meaningless and "
      "without calling the model", null_shape and replayed and len(model.requests) == requests_before
      and null["labels"] and not any("Name" in e[3] for e in null["labels"])
      and null["llm"]["model"] == "semantic-null",
      f"{len(null_shape)} answers replayed; e.g. {null['labels'][-1][3][:40]!r}")
asked = {channels: sum(t["sombunal_question"] for t in r["trace"]) for channels, r in arms.items()}
check("withholding every channel through the model path gives the control, bit for bit",
      arms["none"]["ledger_head"] == control["ledger_head"] and arms["none"]["llm"]["health"]["calls"] == 0)
heads = {name: r["ledger_head"] for name, r in (*arms.items(), ("null", null))}
check("a model never reaches the dynamics — the full arm, the questions only and the semantic null "
      "seal the control's ledger, cycle by cycle; what the model said is kept as labels",
      set(heads.values()) == {control["ledger_head"]}
      and all(r["ledger_head_by_cycle"] == control["ledger_head_by_cycle"] for r in (*arms.values(), null))
      and len(arms["all"]["labels"]) == sum(1 for kind, n in arms["all"]["answer_shape"]
                                            if n and kind != "narration")
      and all(e[3].startswith("Name ") and e[3] == S.LLMIntermediary._clip(e[4]) for e in arms["all"]["labels"])
      and {label for *_, label in arms["all"]["crystal_labels"]} <= {e[3] for e in arms["all"]["labels"]},
      f"{len(set(heads.values()))} distinct heads; {len(arms['all']['labels'])} labels kept, one for each "
      f"answer; {len(arms['all']['crystal_labels'])} of them crystallized")


class Wordy(S.LLMIntermediary):
    """An intermediary whose every answer is longer than a label can be."""
    def _init(self):
        self._available = True

    def _complete(self, temperature):
        return "The Sombunal " + "withholds " * 30 + "what it reveals."


wordy, said = Wordy(backend="none"), Translations()
said.attach(wordy)
said.cycle = 7
with quiet():
    shown = wordy.question_sombunal(0.5)
(cycle, kind, of, label, answer), = said.entries
# The live view too: each snapshot carries the cycle's whole question beside its label
with quiet():
    talker = server.ExperimentEngine(stream=0, delay_ms=0, runs_dir=scratch())
    talker.ss.llm = Wordy(backend="none")
    talker._watch_model()
    talker.running = True
    wait_for(lambda: talker.cycle >= 30)
    talker.running = False
    time.sleep(0.2)
live_questions = [s for s in talker.drain() if s["question"]]
talker.shutdown()
check("the reports and the live view keep the model's whole answer beside the label the construct shows",
      (cycle, kind, of) == (7, "question", []) and label == shown == S.LLMIntermediary._clip(answer)
      and label.endswith("…") and answer.endswith("what it reveals.")
      and live_questions and not talker.said.entries
      and all(s["question_full"] == answer and s["question"] == label for s in live_questions),
      f"label {len(label)} characters, answer {len(answer)}; "
      f"{len(live_questions)} questions in the live view's snapshots")
check("the questions-only arm asks the model nothing but the Sombunal questions, as often as the full arm",
      set(arms["questions"]["llm"]["health"]["calls_by_kind"]) == {"sombunal_question"}
      and asked["questions"] == asked["all"] > 0, f"{asked['questions']} questions in both")


# A view that drifts from the code it shows is wrong without an error anywhere. Each
# visualizer is one file that opens alone, so the names and constants it shares with
# the framework are written in it; these checks read them from both files and compare
# them with the framework and with each other. The formulas the inspector mirrors are
# not compared here: that needs a browser.
check.section("7 · The visualizers and the framework")


def declared(html, name):
    """The right-hand side of a visualizer's top-level `const <name> = …;`."""
    found = re.search(rf"^const {name} = (.*?);[ \t]*(?://[^\n]*)?\n", html, re.MULTILINE | re.DOTALL)
    return found.group(1) if found else ""


def quoted(text):
    return re.findall(r"'([^']*)'", text)


def tokens(html):
    """The colour tokens of a visualizer: the custom properties of its :root."""
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+?)\s*;", re.search(r":root\s*\{(.*?)\}", html, re.DOTALL).group(1)))


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


def relations_of(kind):
    """The proof relations compute_existence_mode counts for one mode."""
    return set(re.findall(r'"([A-Z]+)"', re.search(rf"{kind}_relations\s*=\s*\{{([^}}]*)\}}", modes_source).group(1)))


LEDGER_ONLY = {"TERMINATE", "SHIFT"}                # sealed in the ledger, never attached to a construct
HISTORICAL = {"INTENSIFY"}                          # carried by the proofs of instances saved before v13.14
constants = {
    "ERA_CAPACITY": S.InternalClock.ERA_CAPACITY,
    "DECAY": S.InternalClock.DECAY,
    "VC_UNSTABLE": float(re.search(r"Vc_THRESHOLD\s*=\s*([\d.]+)", inspect.getsource(S.Sombunal.global_instability)).group(1)),
    "EXCHANGE_QUANTUM": S.TetralemmaEngine.EXCHANGE_QUANTUM,
    "APPARENT_FLOOR": S.APPARENT_FLOOR,
    "BOTH_FLOOR": S.BOTH_FLOOR,
}
drift = [name for name, value in constants.items() if float(declared(inspector, name) or "nan") != value]
for kind in ("omega", "lemniscate"):
    if set(quoted(declared(inspector, f"{kind.upper()}_RELATIONS"))) != relations_of(kind):
        drift.append(f"{kind.upper()}_RELATIONS")
if set(quoted(declared(inspector, "PROOF_RELATIONS"))) != \
        (set(re.findall(r'relation\s*=\s*"([A-Z]+)"', framework_source)) - LEDGER_ONLY) | HISTORICAL:
    drift.append("PROOF_RELATIONS")
check("the inspector's constants are the framework's: the clock, the Vc threshold, the exchange quantum, the support floors, "
      "the relations of each existence mode, the relations a construct's proofs can carry",
      not drift, ", ".join(drift) or f"{len(constants) + 3} constants agree")

live_tokens, inspector_tokens = tokens(views["live"]), tokens(inspector)
shared = set(live_tokens) & set(inspector_tokens)
differ = sorted(t for t in shared if live_tokens[t] != inspector_tokens[t])
# Written once in each file, alike: the strata, how an edge state and a mode are drawn and written,
# how a view is fitted
SHARED = ("RINGS", "EDGE_STYLE", "SUPPORT", "weightAlpha", "STATE_MEANING", "MODE_SIGN", "MODE_MEANING", "modeText",
          "LAGRANGE", "lagrangeText", "ARROW_ZOOM", "MARK_ZOOM", "QUIET", "FIT_MARGIN", "FIT_MIN_SPAN", "FOLLOW_EASE")
unlike = [name for name in SHARED if not declared(views["live"], name) or declared(views["live"], name) != declared(inspector, name)]
if declared(views["live"], "HISTORY_KEPT") != str(server.HISTORY_KEPT):     # the live view merges as the server does
    unlike.append("HISTORY_KEPT (live and server)")


def function(html, name):
    """The whole of a visualizer's top-level `function <name>(…) {…}`."""
    found = re.search(rf"^function {name}\(", html, re.MULTILINE)
    if not found:
        return ""
    depth, start = 0, html.index("{", found.end())
    for at in range(start, len(html)):
        depth += {"{": 1, "}": -1}.get(html[at], 0)
        if depth == 0:
            break
    return html[found.start():at + 1]


DRAWN_ALIKE = ("mix", "shapeOf", "supportText", "tracePolygon", "traceShape", "line", "ring", "arrowhead", "drawRelation", "edgeMark",
               "fittedView", "setFollow", "steerView",
               "renderBreakdown", "renderLagrangian", "buildFilters", "foldableSections", "foldableLegend")
unlike += [f"{name}()" for name in DRAWN_ALIKE if not function(views["live"], name)
           or function(views["live"], name) != function(inspector, name)]
check("the two views agree with each other and the live view with its server: the strata rings, how each edge "
      "state and mode is drawn and written, the functions they draw, fit and fold with, every colour token both "
      "define, the history kept", not unlike and len(shared) > 20 and not differ, ", ".join(unlike + differ)
      or f"{len(SHARED)} declarations, {len(DRAWN_ALIKE)} functions and {len(shared)} colour tokens alike")

check.finish()
