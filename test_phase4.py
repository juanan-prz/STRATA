"""Storage: segmented ledger, tampering across segments, power cuts during rotation, disk use.
Run next to the newest framework: python3 test_phase4.py
(No model, no network. Uses small ledger segments to exercise rotation.)"""
import io, sys, json, gzip, time, shutil, tempfile, contextlib, importlib.util, re
from pathlib import Path
HERE = Path(__file__).resolve().parent
NEW = sorted((p.name for p in HERE.iterdir() if re.match(r"^Sirisys_Framework_v13_(\d+)\.py$", p.name)),
             key=lambda n: int(re.findall(r"v13_(\d+)", n)[0]))[-1]
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
def load(seg_bytes=64 * 1024):
    spec = importlib.util.spec_from_file_location(f"m{time.time_ns()}", HERE / NEW)
    m = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(m)
    m.SEGMENT_BYTES = seg_bytes
    return m
def life(m, d, start, stop, ss=None):
    with contextlib.redirect_stdout(io.StringIO()):
        if ss is None:
            ss = m.new_session(m.LLMIntermediary(backend="none"))
        for c in range(start, stop):
            m.run_cycle(ss, c, percepts=m.synthetic_percepts(c, 0))
    return ss
abs_t = lambda t: t[0] * 10_000 + t[1]
def all_records(m, lp):
    return [json.loads(line) for line, _err in m._ledger_lines(lp) if line]

print(f"\n== B2/B3 · Segmented ledger ({NEW})")
d = Path(tempfile.mkdtemp()); lp = d / "ledger.jsonl"
m = load(); m.set_ledger(m.ProofLedger(lp))
ss = life(m, d, 0, 300)
with contextlib.redirect_stdout(io.StringIO()):
    m.save_session_atomic(d / "state.json", ss, 300)
m.get_ledger().close()
idx = m.ProofLedger.read_index(lp)
v = m.verify_ledger(lp)
check("rotation produced compressed segments; chain verifies across them",
      len(idx) >= 3 and v["ok"] and v["count"] == m.get_ledger().count, f"{len(idx)} segments, {v['count']} proofs")
recs = all_records(m, lp)
check("time strictly ordered across segments", all(abs_t(recs[i]["time"]) >= abs_t(recs[i-1]["time"]) for i in range(1, len(recs))))
m2 = load(); m2.set_ledger(m2.ProofLedger(lp))
with contextlib.redirect_stdout(io.StringIO()):
    ss2, nxt = m2.resume_session(d / "state.json", m2.LLMIntermediary(backend="none"))
life(m2, d, nxt, 400, ss2); head_resumed = m2.get_ledger().head; m2.get_ledger().close()
du = Path(tempfile.mkdtemp()); mu = load(); mu.set_ledger(mu.ProofLedger(du / "ledger.jsonl"))
life(mu, du, 0, 400); head_straight = mu.get_ledger().head; mu.get_ledger().close()
check("resume across segments equals an uninterrupted life (same head at 400)", head_resumed == head_straight)

print("\n== B2 · Tampering across segments")
def tamper(label, fn, expect):
    t = Path(tempfile.mkdtemp()); [shutil.copy2(f, t / f.name) for f in d.iterdir() if f.is_file()]
    fn(t); r = m.verify_ledger(t / "ledger.jsonl")
    check(f"{label} detected", not r["ok"] and expect in (r["reason"] or ""), r["reason"])
idx = m.ProofLedger.read_index(lp)          # current index (the resumed life added segments)
def flip(t):
    seg = t / idx[1]["file"]; b = bytearray(seg.read_bytes()); b[len(b) // 2] ^= 0xFF; seg.write_bytes(bytes(b))
tamper("altered compressed segment", flip, "altered")
tamper("deleted segment", lambda t: (t / idx[0]["file"]).unlink(), "missing")
def swap(t):
    a, b = t / idx[0]["file"], t / idx[1]["file"]; tmp = t / "x"; a.rename(tmp); b.rename(a); tmp.rename(b)
tamper("swapped segments", swap, "altered")
def rewrite_segment(t):   # recompress a segment with one edited proof (sha in index no longer matches)
    seg = t / idx[1]["file"]; lines = gzip.decompress(seg.read_bytes()).decode().splitlines()
    r = json.loads(lines[3]); r["object"] += "_x"; lines[3] = json.dumps(r, sort_keys=True, ensure_ascii=False)
    seg.write_bytes(gzip.compress(("\n".join(lines) + "\n").encode()))
tamper("edited and recompressed segment", rewrite_segment, "altered")
def extra(t):
    shutil.copy2(t / idx[0]["file"], m.ProofLedger.segment_path(t / "ledger.jsonl", len(idx) + 1))
tamper("unlisted extra segment", extra, "unlisted")

print("\n== B1 · Power cut in the middle of a rotation")
dr = Path(tempfile.mkdtemp()); mr = load(seg_bytes=1 << 40); mr.set_ledger(mr.ProofLedger(dr / "ledger.jsonl"))
life(mr, dr, 0, 60); mr.get_ledger().close()
base = mr.verify_ledger(dr / "ledger.jsonl")["count"]
def cut_case(label, prepare):
    t = Path(tempfile.mkdtemp()); [shutil.copy2(f, t / f.name) for f in dr.iterdir() if f.is_file()]
    prepare(t / "ledger.jsonl")
    mm = load(); L = mm.ProofLedger(t / "ledger.jsonl"); L.close()
    r = mm.verify_ledger(t / "ledger.jsonl")
    check(f"{label}: recovered, nothing lost or duplicated",
          r["ok"] and r["count"] == base and L.count == base, f"{r['count']} of {base} proofs")
def orphan_gz(lp_t):   # cut after the compressed copy was renamed, before the index
    m.ProofLedger.segment_path(lp_t, 1).write_bytes(gzip.compress(lp_t.read_bytes()))
cut_case("compressed copy written, index not yet", orphan_gz)
def index_not_truncated(lp_t):   # cut after the index, before truncating the active segment
    raw = lp_t.read_bytes(); seg = m.ProofLedger.segment_path(lp_t, 1); seg.write_bytes(gzip.compress(raw, 6))
    lines = raw.decode().splitlines(); last, first = json.loads(lines[-1]), json.loads(lines[0])
    m.ProofLedger.index_path(lp_t).write_text(json.dumps([{
        "file": seg.name, "first_seq": first["seq"], "count": last["seq"] + 1 - first["seq"],
        "last_hash": last["chain_hash"], "last_time": last["time"],
        "sha256": __import__("hashlib").sha256(seg.read_bytes()).hexdigest()}]))
cut_case("index written, active segment not yet truncated", index_not_truncated)

print("\n== C3 · Disk")
# Production segments are 32 MB; tiny test segments compress worse, so the
# yearly figure is computed by compressing the same proofs as one segment.
raw = ("\n".join(l for l, e in m._ledger_lines(lp) if l) + "\n").encode("utf-8")
per_cycle = len(gzip.compress(raw, 6)) / 400
check("ledger ≤ 6 GB/year at one cycle every 10 s (32 MB segments)", per_cycle * 8640 * 365 <= 6e9,
      f"{per_cycle/1024:.2f} KB/cycle stored ({len(raw)/400/1024:.1f} KB raw) → {per_cycle*8640*365/1e9:.1f} GB/year")
st = (d / "state.json").stat().st_size
check("compact snapshot", st < 600 * 1024, f"{st/1024:.0f} KB")

print(f"\nSUMMARY: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
