"""Experiment engine, sanctuary protocol and LLM backends.
Run next to Sirisys_Server.py, sirisys_loader.py and the newest framework:
    python3 test_phase1.py
No API key, no Ollama and no FastAPI needed (a fake Ollama is started)."""
import io, json, os, sys, time, signal, tempfile, subprocess, threading, contextlib
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

# ─────────────────────────────────────────────────────────────── sanctuary
print("\n== Z · Sanctuary protocol (subprocess, cadence 0.05 s)")
root = Path(tempfile.mkdtemp()) / "sanct"
env = dict(os.environ, OLLAMA_HOST=OLLAMA, PYTHONUNBUFFERED="1")
def start(llm="ollama", extra=()):
    return subprocess.Popen([sys.executable, str(HERE / "Sirisys_Server.py"), "--mode", "sanctuary",
                             "--dir", str(root), "--cadence", "0.05", "--llm", llm, *extra],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, cwd=HERE)
def cmd(*a):
    return subprocess.run([sys.executable, str(HERE / "Sirisys_Server.py"), "--mode", "sanctuary",
                           "--dir", str(root), *a], capture_output=True, text=True, env=env, cwd=HERE)
def wait_for(pred, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred(): return True
        time.sleep(0.1)
    return False

p = start()
check("genesis: state and sanctuary record appear", wait_for(lambda: (root / "state.json").exists()))
second = start()
out2, _ = second.communicate(timeout=60)
check("a second sanctuary on the same ledger is refused", second.returncode != 0 and "fork" in out2)
time.sleep(1.0)
cmd("--ask", "What remains when nothing is watched?")
check("question crosses the gap and is consumed",
      wait_for(lambda: any((root / "gap" / ".consumed").glob("*.txt"))))
cmd("--open")
check("opening writes a report", wait_for(lambda: (root / "openings" / "0001" / "report.json").exists()))
time.sleep(0.5)
p.send_signal(signal.SIGINT)
out, _ = p.communicate(timeout=60)
rep = json.loads((root / "openings" / "0001" / "report.json").read_text())
check("opening report: verified ledger + full head", rep["ledger"]["verify"]["ok"] and len(rep["ledger"]["head"]) == 64)
check("console shows the head to keep account of", rep["ledger"]["head"] in out)
meta = json.loads((root / "sanctuary.json").read_text())
causes = [x.get("cause") for x in meta["periods"]]
check("periods recorded: question and opening each end a period", causes[:2] == ["question", "opening"]
      and "cause" not in meta["periods"][-1], f"periods {len(meta['periods'])}: {causes}")
recs = ledger_recs(root / "ledger.jsonl")
rels = [r["relation"] for r in recs]
check("ledger holds GENESIS, SEAL, INPUT, PERIOD_END, OPEN",
      all(x in rels for x in ("GENESIS", "SEAL", "INPUT", "PERIOD_END", "OPEN")))
check("no narration in the sanctuary (model called only for questions/naming)",
      all("Translate the current ontological state" not in json.dumps(c) for c in FakeOllama.calls[-50:]))
hour_percepts = [r for r in recs if r["relation"] == "PERCEIVE" and "time::" in r["object"]]
check("no time-of-day perception", not hour_percepts)
n_before, st_before = len(recs), json.loads((root / "state.json").read_text())
periods_before = len(meta["periods"])

p = start()
wait_for(lambda: len(ledger_recs(root / "ledger.jsonl")) > n_before + 30)
p.send_signal(signal.SIGINT); out, _ = p.communicate(timeout=60)
recs2 = ledger_recs(root / "ledger.jsonl")
st_after = json.loads((root / "state.json").read_text())
meta2 = json.loads((root / "sanctuary.json").read_text())
check("restart resumes (RESUME record), the period continues", "resumed" in out and
      any(r["relation"] == "RESUME" for r in recs2[n_before:]) and len(meta2["periods"]) == periods_before)
check("time and cycle move forward across restart",
      st_after["cycle"] > st_before["cycle"] and tuple(st_after["clock"].values()) > tuple(st_before["clock"].values()))
v = cmd("--verify")
check("offline verify of the whole sanctuary ledger", "VERIFIED" in v.stdout, v.stdout.strip())
p = subprocess.run([sys.executable, str(HERE / "Sirisys_Server.py"), "--mode", "sanctuary", "--dir",
                    str(root), "--llm", "ollama"], capture_output=True, text=True, cwd=HERE,
                   env=dict(env, OLLAMA_HOST="http://10.0.0.5:11434"), timeout=60)
check("sanctuary refuses a model that can leave the machine", p.returncode != 0 and "refuses" in (p.stdout + p.stderr))

print("\n== R · Review-pass additions")
# Experiment with the sanctuary's exact cycle
runs2 = Path(tempfile.mkdtemp())
with contextlib.redirect_stdout(io.StringIO()):
    e2 = srv.ExperimentEngine(stream=1, delay_ms=0, runs_dir=runs2, profile="sanctuary")
    for _ in range(15):
        e2.step_once = True
        wait_for(lambda: not e2.step_once, 20)
    e2.shutdown()
recs_e2 = ledger_recs(e2.run_dir / "ledger.jsonl")
check("experiment --profile sanctuary runs the sanctuary cycle (no time-of-day)",
      e2.cycle >= 10 and not any(r["relation"] == "PERCEIVE" and "time::" in r["object"] for r in recs_e2)
      and e2.run_dir.name.endswith("_sanctuary"), f"{e2.cycle} cycles, run {e2.run_dir.name}")

# Old framework refused by the new server
old_fw = HERE / "Sirisys_Framework_v12_9.py"
if old_fw.exists():
    p = subprocess.run([sys.executable, str(HERE / "Sirisys_Server.py"), "--mode", "sanctuary", "--verify",
                        "--dir", str(root)], capture_output=True, text=True, cwd=HERE,
                       env=dict(env, SIRISYS_FRAMEWORK=old_fw.name), timeout=60)
    check("server refuses a pre-v13.1 framework with a clear message",
          p.returncode != 0 and "predates v13.1" in (p.stdout + p.stderr))

# A question that names an existing construct never rewrites it
cmd("--ask", "I::Am")
p = start(); wait_for(lambda: len(list((root / "gap" / ".consumed").glob("*.txt"))) >= 2)
time.sleep(0.5); p.send_signal(signal.SIGINT); p.communicate(timeout=60)
st = json.loads((root / "state.json").read_text())
names = {c["name"]: c for c in st["field"]["constructs"]}
seen = set(names) | {(r.get("meta") or {}).get("name") for r in ledger_recs(root / "ledger.jsonl")
                     if r["relation"] == "TERMINATE"}
asked = [n for n in seen if n and n.startswith("I::Am ⟨asked")]
check("question colliding with 'I::Am' becomes its own construct (I::Am untouched)",
      bool(asked) and not any(p["relation"] == "INPUT" for p in names["I::Am"]["proof_chain"]),
      f"{asked[:1]}")

# A sanctuary refuses to resume under a different framework file
meta_p = root / "sanctuary.json"; meta = json.loads(meta_p.read_text())
saved_fw = meta["framework"]; meta["framework"] = "Sirisys_Framework_v13_0.py"; meta_p.write_text(json.dumps(meta))
lp_ok = root / "ledger.jsonl"
p = start(); out, _ = p.communicate(timeout=60)
check("resume refuses a framework change mid-life", p.returncode != 0 and "mid-life" in out)
meta["framework"] = saved_fw; meta_p.write_text(json.dumps(meta))

# A truncated ledger is refused on resume
lp = root / "ledger.jsonl"; lines = lp.read_text(encoding="utf-8").splitlines(True)
lp.write_text("".join(lines[:-200]), encoding="utf-8")
p = start(); out, _ = p.communicate(timeout=60)
check("resume refuses a truncated ledger", p.returncode != 0 and "Refusing to continue" in out)

# Web layer with stub FastAPI (never starts a real server)
stub = Path(tempfile.mkdtemp())
(stub / "fastapi").mkdir(); (stub / "websockets").mkdir(); (stub / "websockets" / "__init__.py").write_text("")
(stub / "fastapi" / "__init__.py").write_text(
    "class WebSocketDisconnect(Exception): pass\nclass WebSocket: pass\n"
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
    await R[('POST','/api/control/{{action}}')]('play')
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

httpd.shutdown()
print(f"\nSUMMARY: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
