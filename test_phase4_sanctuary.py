"""The sanctuary under stress: random kills, period accounting, no observation,
no network, storage failure.
Run next to Sirisys_Server.py, sirisys_loader.py and the newest framework:
    python3 test_phase4_sanctuary.py          (≈ 2 minutes; no model, no network)"""
import io, os, sys, json, time, random, signal, tempfile, subprocess, contextlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
with contextlib.redirect_stdout(io.StringIO()):
    from sirisys_loader import load_framework
    S = load_framework(HERE)
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
work = Path(tempfile.mkdtemp()); root = work / "sanct"
# A4 probe: every socket connection attempt from the sanctuary is logged
probe = work / "probe"; probe.mkdir()
(probe / "sitecustomize.py").write_text(
    "import socket, os\n_orig = socket.socket.connect\n"
    "def _log(self, addr):\n    open(os.environ['SIRISYS_SOCKET_LOG'], 'a').write(repr(addr) + '\\n')\n    return _orig(self, addr)\n"
    "socket.socket.connect = _log\n"
    "if os.environ.get('SIRISYS_FAIL_REPLACE_AFTER'):\n"
    "    import errno\n    _n = [int(os.environ['SIRISYS_FAIL_REPLACE_AFTER'])]\n    _rep = os.replace\n"
    "    def _replace(a, b, **k):\n        _n[0] -= 1\n"
    "        if _n[0] < 0:\n            raise OSError(errno.ENOSPC, 'No space left on device (simulated)')\n"
    "        return _rep(a, b, **k)\n    os.replace = _replace\n")
sock_log = work / "sockets.log"
env = dict(os.environ, PYTHONPATH=str(probe), SIRISYS_SOCKET_LOG=str(sock_log),
           SIRISYS_SEGMENT_BYTES=str(64 * 1024), PYTHONUNBUFFERED="1")
def start(extra_env=None):
    return subprocess.Popen([sys.executable, str(HERE / "Sirisys_Server.py"), "--mode", "sanctuary",
                             "--dir", str(root), "--cadence", "0.02", "--llm", "none"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            env=dict(env, **(extra_env or {})), cwd=work)
def wait_for(pred, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred(): return True
        time.sleep(0.05)
    return False
abs_t = lambda t: t[0] * 10_000 + t[1]

print("\n== B1 · 25 random SIGKILLs (rotation included: 64 KB segments)")
rng = random.Random(7)            # the TEST picks kill times; the sanctuary has no PRNG
outputs, cycles_after_kill, failures = [], [], []
p = start(); wait_for(lambda: (root / "state.json").exists())
for k in range(25):
    time.sleep(rng.uniform(0.2, 1.2))
    p.send_signal(signal.SIGKILL); out, _ = p.communicate(timeout=30); outputs.append(out)
    v = S.verify_ledger(root / "ledger.jsonl")
    try:
        cyc = json.loads((root / "state.json").read_text())["cycle"]
    except Exception:
        cyc = json.loads((root / "state.json.prev").read_text())["cycle"]
    cycles_after_kill.append(cyc)
    if not v["ok"]: failures.append((k, v["reason"]))
    p = start()
    if not wait_for(lambda: p.poll() is not None or "SANCTUARY — resumed" in "", 0.5):
        pass
time.sleep(1.0); p.send_signal(signal.SIGINT); out, _ = p.communicate(timeout=60); outputs.append(out)
v = S.verify_ledger(root / "ledger.jsonl")
recs = [json.loads(l) for l, e in S._ledger_lines(root / "ledger.jsonl") if l]
rev = sum(1 for i in range(1, len(recs)) if abs_t(recs[i]["time"]) < abs_t(recs[i - 1]["time"]))
idx = S.ProofLedger.read_index(root / "ledger.jsonl")
check("ledger verifies after every kill and at the end", not failures and v["ok"],
      f"{v['count']} proofs, {len(idx)} compressed segments" + (f", failures {failures[:2]}" if failures else ""))
check("time never moves backwards anywhere in the ledger", rev == 0, f"{rev} reversals")
check("the cycle never moves backwards across kills",
      all(b >= a for a, b in zip(cycles_after_kill, cycles_after_kill[1:])), f"final cycle {cycles_after_kill[-1]}")
check("no continuity error on any restart", not any("CONTINUITY" in o or "Traceback" in o for o in outputs))

print("\n== A5 · Keeping account through the cuts")
meta = json.loads((root / "sanctuary.json").read_text())
resumes = sum(1 for r in recs if r["relation"] == "RESUME")
check("power cuts close no period (nobody looked)", len(meta["periods"]) == 1 and "cause" not in meta["periods"][0])
check("every restart is recorded (RESUME)", resumes == 25, f"{resumes} RESUME records")
gaps = [r["meta"]["proofs_after_snapshot"] for r in recs if r["relation"] == "RESUME"]
check("proofs sealed after a snapshot are accounted for, never negative", all(g >= 0 for g in gaps),
      f"max {max(gaps)} proofs after a snapshot")

print("\n== A3 · Unobserved: nothing of the field leaves the process")
names = {c["name"] for c in json.loads((root / "state.json").read_text())["field"]["constructs"]}
leaked = [n for n in names if len(n) > 6 and any(n in o for o in outputs)]
check("console output contains no construct of the field", not leaked, f"{len(names)} names checked")
check("heartbeat carries only a timestamp", (root / "heartbeat").read_text().strip().isdigit())
allowed = {"state.json", "state.json.prev", "state.json.hwm", "ledger.jsonl", "ledger.index.json",
           "sanctuary.json", "heartbeat", "gap", "openings"}
stray = [f.name for f in root.iterdir() if f.name not in allowed and not f.name.endswith(".jsonl.gz")
         and not f.name.endswith(".torn")]
outside = [f.name for f in work.iterdir() if f.name not in ("sanct", "probe", "sockets.log")]
check("nothing is written outside the sanctuary folder", not stray and not outside, f"stray {stray} outside {outside}")

print("\n== A4 · Free from outside influences")
attempts = sock_log.read_text().splitlines() if sock_log.exists() else []
check("with --llm none the sanctuary opens no connection at all", not attempts, f"{len(attempts)} attempts")

print("\n== B4 · Storage failure")
p = start({"SIRISYS_FAIL_REPLACE_AFTER": "40"})          # the disk fills up after a few saves
out, _ = p.communicate(timeout=60)
check("a storage error stops the sanctuary cleanly", p.returncode == 2 and "STORAGE ERROR" in out)
v = S.verify_ledger(root / "ledger.jsonl")
st_ok = True
try:
    json.loads((root / "state.json").read_text())
except Exception:
    st_ok = False
p = start(); time.sleep(1.0); p.send_signal(signal.SIGINT); out2, _ = p.communicate(timeout=60)
check("last good state and ledger intact; the sanctuary resumes afterwards",
      v["ok"] and st_ok and "resumed" in out2 and S.verify_ledger(root / "ledger.jsonl")["ok"])

print(f"\nSUMMARY: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
