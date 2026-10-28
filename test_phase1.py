"""Experiment engine, LLM backends, model health, the report's percepts and the web layer.
Run next to Sirisys_Server.py, sirisys_loader.py and the newest framework:
    python3 test_phase1.py
No API key, no Ollama and no FastAPI needed (a fake Ollama is started)."""
import io, json, os, sys, time, tempfile, subprocess, threading, contextlib
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
results = []
def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

sys.argv = [sys.argv[0]]
with contextlib.redirect_stdout(io.StringIO()):
    import Sirisys_Server as srv
S = srv.S

def ledger_recs(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]

# ─────────────────────────────────────────────────────────────── experiment
print("\n== E · Experiment engine (no web server needed)")
runs = Path(tempfile.mkdtemp())
with contextlib.redirect_stdout(io.StringIO()):
    eng = srv.ExperimentEngine(stream=0, delay_ms=0, runs_dir=runs)
    eng.running = True
    t0 = time.time()
    while eng.cycle < 30 and time.time() - t0 < 60:
        time.sleep(0.05)
    eng.running = False
    time.sleep(0.2)
snaps = eng.drain()
first_run = eng.run_dir
keys = {"cycle", "T", "constructs", "edges", "apparents", "terminations", "concluded",
        "field", "ledger", "instability", "modes", "layers", "action"}
check("cycles stream as snapshots", len(snaps) >= 30 and keys <= snaps[-1].keys(), f"{len(snaps)} snapshots")
check("snapshot is JSON-serializable", bool(json.dumps(snaps[-1])))
res = eng.control("reset", stream="live")
check("reset opens a new run folder, old one kept", res["ok"] and first_run.exists() and eng.run_dir != first_run
      and (first_run / "state.json").exists(), f"{first_run.name} → {eng.run_dir.name}")
check("old run's ledger verifies", S.verify_ledger(first_run / "ledger.jsonl")["ok"])
check("live-percept reset recorded", eng.stream is None and eng.run_dir.name.endswith("_live"))
eng.shutdown()
check("shutdown saves the current run", (eng.run_dir / "state.json").exists())

# ─────────────────────────────────────────────────────────────── fake ollama
class FakeOllama(BaseHTTPRequestHandler):
    calls = []
    def log_message(self, *a): pass
    def _send(self, obj):
        b = json.dumps(obj).encode(); self.send_response(200)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        self._send({"models": [{"name": "fake-model:latest"}]})
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.calls.append(body)
        self._send({"message": {"role": "assistant", "content": f"echo {len(FakeOllama.calls)}"}})
httpd = HTTPServer(("127.0.0.1", 0), FakeOllama)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
OLLAMA = f"http://127.0.0.1:{httpd.server_port}"

print("\n== L · LLM backends")
with contextlib.redirect_stdout(io.StringIO()):
    llm = S.LLMIntermediary(backend="ollama", host=OLLAMA)
q = llm.question_sombunal(0.5)
body = FakeOllama.calls[-1] if FakeOllama.calls else {}
check("ollama backend: discovers model and completes", llm.available and llm.model == "fake-model:latest" and q == "echo 1")
check("ollama request carries system prompt, history and options",
      body.get("messages", [{}])[0].get("role") == "system" and body.get("stream") is False
      and body["options"]["temperature"] == 1.10, f"temperature {body.get('options', {}).get('temperature')}")
check("ollama on loopback is local", llm.is_local)
with contextlib.redirect_stdout(io.StringIO()):
    remote = S.LLMIntermediary(backend="ollama", host="http://10.0.0.5:11434")
check("ollama on another host is NOT local", not remote.is_local)
class FakeMessages:
    def create(self, **kw): self.kw = kw; return type("R", (), {"content": [type("C", (), {"text": " ok "})()]})()
with contextlib.redirect_stdout(io.StringIO()):
    a = S.LLMIntermediary(backend="anthropic")
a._client = type("Cl", (), {"messages": FakeMessages()})(); a._available = True
a.question_sombunal(0.3)
check("anthropic temperature clamped to [0, 1] (was 1.10)", a._client.messages.kw["temperature"] == 1.0)
try:
    S.LLMIntermediary(backend="openai"); bad = False
except ValueError:
    bad = True
check("unknown backend refused", bad)

print("\n== R · Profiles, framework check, web layer")
def wait_for(pred, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred(): return True
        time.sleep(0.1)
    return False

# The minimal profile: no narration, no time-of-day percept
runs2 = Path(tempfile.mkdtemp())
with contextlib.redirect_stdout(io.StringIO()):
    e2 = srv.ExperimentEngine(stream=1, delay_ms=0, runs_dir=runs2, profile="minimal")
    for _ in range(15):
        e2.step_once = True
        wait_for(lambda: not e2.step_once, 20)
    e2.shutdown()
recs_e2 = ledger_recs(e2.run_dir / "ledger.jsonl")
check("experiment --profile minimal perceives no time of day",
      e2.cycle >= 10 and not any(r["relation"] == "PERCEIVE" and "time::" in r["object"] for r in recs_e2)
      and e2.run_dir.name.endswith("_minimal"), f"{e2.cycle} cycles, run {e2.run_dir.name}")

# Old framework refused by the server
old_fw = HERE / "Sirisys_Framework_v12_9.py"
if old_fw.exists():
    p = subprocess.run([sys.executable, str(HERE / "Sirisys_Server.py"), "--help"],
                       capture_output=True, text=True, cwd=HERE,
                       env=dict(os.environ, SIRISYS_FRAMEWORK=old_fw.name), timeout=60)
    check("server refuses a pre-v13.1 framework with a clear message",
          p.returncode != 0 and "predates v13.1" in (p.stdout + p.stderr))

# Web layer with stub FastAPI (never starts a real server)
stub = Path(tempfile.mkdtemp())
(stub / "fastapi").mkdir(); (stub / "websockets").mkdir(); (stub / "websockets" / "__init__.py").write_text("")
(stub / "fastapi" / "__init__.py").write_text(
    "class WebSocketDisconnect(Exception): pass\nclass WebSocket: pass\nclass Request: pass\n"
    "class FastAPI:\n def __init__(self,title=None,lifespan=None): self.routes={}; self.lifespan=lifespan\n"
    " def _r(self,k):\n  def d(f): self.routes[k]=f; return f\n  return d\n"
    " def get(self,p,**k): return self._r(('GET',p))\n def post(self,p,**k): return self._r(('POST',p))\n"
    " def websocket(self,p): return self._r(('WS',p))\n")
(stub / "fastapi" / "responses.py").write_text(
    "class HTMLResponse:\n def __init__(self,content='',status_code=200): self.content=content; self.status_code=status_code\n"
    "class JSONResponse:\n def __init__(self,content): self.content=content\n")
(stub / "uvicorn.py").write_text("APP=None\ndef run(app,**k):\n global APP; APP=app\n")
web = stub / "web.py"
web.write_text(f"""
import sys, asyncio, json, io, contextlib
sys.path.insert(0, {str(stub)!r}); sys.path.insert(0, {str(HERE)!r}); sys.argv=['x']
import Sirisys_Server as srv, uvicorn, fastapi
srv.HERE = __import__('pathlib').Path({str(stub)!r})
with contextlib.redirect_stdout(io.StringIO()):
    srv.serve_experiment(srv.parse_args(['--delay-ms','0']))
R = uvicorn.APP.routes
async def go():
    class MockReq:
        async def json(self): return dict()
    await R[('POST','/api/control/{{action}}')]('play', MockReq())
    msgs = []
    class WS:
        n = 0
        async def accept(self): pass
        async def send_json(self, o): msgs.append(o)
        async def receive_text(self):
            WS.n += 1
            raise fastapi.WebSocketDisconnect()     # the client has already gone
    await asyncio.wait_for(R[('WS','/ws')](WS()), 10)
    async with uvicorn.APP.lifespan(uvicorn.APP): pass
    print('WS_EXITED', len(msgs), WS.n)
asyncio.run(go())
""")
p = subprocess.run([sys.executable, str(web)], capture_output=True, text=True, timeout=60, cwd=stub)
check("WebSocket handler exits on disconnect (no busy loop on a dead socket)",
      "WS_EXITED" in p.stdout, (p.stdout + p.stderr).strip().splitlines()[-1][:90] if (p.stdout + p.stderr).strip() else "")

# ─────────────────────────────────────────────────────────────── model health
print("\n== H · Model health and the report's percepts")
from sirisys_measures import ModelHealth
import shutil

class HealthFake(BaseHTTPRequestHandler):
    mode, after, n = "ok", 0, 0                      # ok | empty | error, after `after` answers
    def log_message(self, *a): pass
    def _send(self, obj, code=200):
        b = json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        self._send({"models": [{"name": "fake-model:latest"}]})
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        HealthFake.n += 1
        if HealthFake.n > HealthFake.after and HealthFake.mode == "error":
            return self._send({"error": "model crashed"}, 500)
        text = "" if HealthFake.n > HealthFake.after and HealthFake.mode == "empty" else f"Name {HealthFake.n}"
        self._send({"message": {"role": "assistant", "content": text}})
hf = HTTPServer(("127.0.0.1", 0), HealthFake)
threading.Thread(target=hf.serve_forever, daemon=True).start()
HF = f"http://127.0.0.1:{hf.server_port}"
def fake(mode, after=0):
    HealthFake.mode, HealthFake.after, HealthFake.n = mode, after, 0

def model():
    with contextlib.redirect_stdout(io.StringIO()):
        return S.LLMIntermediary(backend="ollama", host=HF)
fake("ok")
pr = ModelHealth.probe(model(), cycles=100, calls_per_cycle=4)
check("the probe accepts a model that answers", pr["ok"] and all(pr["answers"]), str(pr.get("answers")))
fake("empty")
pr = ModelHealth.probe(model())
check("the probe refuses a model that answers empty", not pr["ok"] and "empty" in pr["reason"])
fake("error")
llm, h = model(), ModelHealth()
h.attach(llm)
with contextlib.redirect_stdout(io.StringIO()):
    names = [llm.propose_emergent("a", "b", "TRUE", "TRUE") for _ in range(4)]
check("watching trips after 3 failed calls in a row (the field itself only sees empty names)",
      h.tripped and h.failures >= 3 and not any(names), h.reason)

# Copies of the tools in a scratch folder: nothing here touches the user's reports
tools = Path(tempfile.mkdtemp())
for f in ["run_report.py", "live_c2.py", "sirisys_loader.py", "field_topology.py", "sirisys_measures.py",
          S.__sirisys_file__]:
    shutil.copy(HERE / f, tools / f)
fake("error", after=30)
p = subprocess.run([sys.executable, "live_c2.py", "60", "ollama", "minimal"], capture_output=True, text=True,
                   cwd=tools, env=dict(os.environ, OLLAMA_HOST=HF), timeout=300)
out = json.loads(p.stdout) if p.stdout.strip() else {}
check("live_c2 stops (exit 3) when the model starts failing mid-run, and says so",
      p.returncode == 3 and out.get("aborted") and "STOPPED" in p.stderr, str(out.get("aborted"))[:80])
p = subprocess.run([sys.executable, "run_report.py", "--backend", "ollama", "--cycles", "5", "--seeds", "1"],
                   capture_output=True, text=True, cwd=tools,
                   env=dict(os.environ, OLLAMA_HOST="http://127.0.0.1:9"), timeout=120)
check("run_report --backend ollama stops before running when the model is not there",
      p.returncode == 3 and "Nothing was run" in p.stdout and not (tools / "sirisys_report.json").exists())
sys.argv = ["run_report.py"]
with contextlib.redirect_stdout(io.StringIO()):
    import run_report as RR
    a1, a2 = (RR.run_arm(0, 30, False, lambda m: None, profile="minimal") for _ in range(2))
    b1 = RR.run_arm(1, 30, False, lambda m: None, profile="minimal")
check("run_report feeds the synthetic stream when asked, reproducibly",
      a1["percept_catalog"]["distinct_targets"] > 2 and a1["trace"] == a2["trace"] and a1["trace"] != b1["trace"],
      f"{a1['percept_catalog']['distinct_targets']} distinct percepts; seed 0 twice identical: "
      f"{a1['trace'] == a2['trace']}; seed 1 different: {a1['trace'] != b1['trace']}")
hf.shutdown()

httpd.shutdown()
print(f"\nSUMMARY: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
