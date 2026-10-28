"""Storage: the segmented ledger, tampering across segments, power cuts during a
rotation, and disk use.
No model and no network. Small segments (64 KB) make the ledger rotate often.
Usage: python3 test_phase4.py"""
import gzip
import hashlib
import json
import shutil

from sirisys_testkit import Checks, FRAMEWORK, fresh_framework, quiet, scratch

SEGMENT = 64 * 1024
CYCLES, RESUMED_TO = 300, 400
check = Checks()


def life(m, start, stop, ss=None):
    """Cycles start..stop-1 of synthetic stream 0, in a new session unless one is given."""
    with quiet():
        ss = ss or m.new_session(m.LLMIntermediary(backend="none"))
        for c in range(start, stop):
            m.run_cycle(ss, c, percepts=m.synthetic_percepts(c, 0))
    return ss


def copy_of(folder):
    """A copy of a ledger folder, to damage without touching the original."""
    target = scratch()
    for f in folder.iterdir():
        if f.is_file():
            shutil.copy2(f, target / f.name)
    return target


def records(m, path):
    return [json.loads(line) for line, _error in m._ledger_lines(path) if line]


check.section(f"1 · Segmented ledger ({FRAMEWORK.name})")
home = scratch()
path = home / "ledger.jsonl"
m = fresh_framework(SEGMENT_BYTES=SEGMENT)
m.set_ledger(m.ProofLedger(path))
ss = life(m, 0, CYCLES)
with quiet():
    m.save_session_atomic(home / "state.json", ss, CYCLES)
m.get_ledger().close()
index, v = m.ProofLedger.read_index(path), m.verify_ledger(path)
check("rotation produced compressed segments; chain verifies across them",
      len(index) >= 3 and v["ok"] and v["count"] == m.get_ledger().count,
      f"{len(index)} segments, {v['count']} proofs")
times = [tuple(r["time"]) for r in records(m, path)]
check("time never goes back across segments", all(b >= a for a, b in zip(times, times[1:])))

resumed = fresh_framework(SEGMENT_BYTES=SEGMENT)
resumed.set_ledger(resumed.ProofLedger(path))
with quiet():
    ss, next_cycle = resumed.resume_session(home / "state.json", resumed.LLMIntermediary(backend="none"))
life(resumed, next_cycle, RESUMED_TO, ss)
head_resumed = resumed.get_ledger().head
resumed.get_ledger().close()
straight = fresh_framework(SEGMENT_BYTES=SEGMENT)
straight.set_ledger(straight.ProofLedger(scratch() / "ledger.jsonl"))
life(straight, 0, RESUMED_TO)
head_straight = straight.get_ledger().head
straight.get_ledger().close()
check(f"resume across segments equals an uninterrupted life (same head at {RESUMED_TO})",
      head_resumed == head_straight)

check.section("2 · Tampering across segments")
index = m.ProofLedger.read_index(path)                   # the resumed life added segments


def segment(folder, i):
    return folder / index[i]["file"]


def tamper(label, damage, reason):
    folder = copy_of(home)
    damage(folder)
    r = m.verify_ledger(folder / "ledger.jsonl")
    check(f"{label} detected", not r["ok"] and reason in (r["reason"] or ""), r["reason"])


def flip_a_byte(folder):
    seg = segment(folder, 1)
    data = bytearray(seg.read_bytes())
    data[len(data) // 2] ^= 0xFF
    seg.write_bytes(bytes(data))


def swap_two(folder):
    a, b, spare = segment(folder, 0), segment(folder, 1), folder / "spare"
    a.rename(spare)
    b.rename(a)
    spare.rename(b)


def edit_and_recompress(folder):
    """One proof edited, the segment compressed again: its sha256 no longer matches the index."""
    seg = segment(folder, 1)
    lines = gzip.decompress(seg.read_bytes()).decode().splitlines()
    rec = json.loads(lines[3])
    rec["object"] += "_x"
    lines[3] = json.dumps(rec, sort_keys=True, ensure_ascii=False)
    seg.write_bytes(gzip.compress(("\n".join(lines) + "\n").encode()))


def add_unlisted(folder):
    shutil.copy2(segment(folder, 0), m.ProofLedger.segment_path(folder / "ledger.jsonl", len(index) + 1))


tamper("altered compressed segment", flip_a_byte, "altered")
tamper("deleted segment", lambda folder: segment(folder, 0).unlink(), "missing")
tamper("swapped segments", swap_two, "altered")
tamper("edited and recompressed segment", edit_and_recompress, "altered")
tamper("unlisted extra segment", add_unlisted, "unlisted")

check.section("3 · Power cut in the middle of a rotation")
cut_home = scratch()
mr = fresh_framework(SEGMENT_BYTES=1 << 40)              # one active segment, never rotated
mr.set_ledger(mr.ProofLedger(cut_home / "ledger.jsonl"))
life(mr, 0, 60)
mr.get_ledger().close()
proofs = mr.verify_ledger(cut_home / "ledger.jsonl")["count"]


def power_cut(label, leave_as_cut):
    """The rotation interrupted at one point; reopening must recover every proof, once."""
    active = copy_of(cut_home) / "ledger.jsonl"
    leave_as_cut(active)
    with quiet():                                        # it reports the recovery itself
        reopened = fresh_framework(SEGMENT_BYTES=SEGMENT).ProofLedger(active)
    reopened.close()
    r = m.verify_ledger(active)
    check(f"{label}: recovered, nothing lost or duplicated",
          r["ok"] and r["count"] == proofs and reopened.count == proofs, f"{r['count']} of {proofs} proofs")


def compressed_copy_only(active):
    """Cut after the compressed copy was renamed into place, before the index was written."""
    m.ProofLedger.segment_path(active, 1).write_bytes(gzip.compress(active.read_bytes()))


def index_without_truncation(active):
    """Cut after the index was written, before the active segment was truncated."""
    raw = active.read_bytes()
    seg = m.ProofLedger.segment_path(active, 1)
    seg.write_bytes(gzip.compress(raw, 6))
    lines = raw.decode().splitlines()
    first, last = json.loads(lines[0]), json.loads(lines[-1])
    m.ProofLedger.index_path(active).write_text(json.dumps([{
        "file": seg.name, "first_seq": first["seq"], "count": last["seq"] + 1 - first["seq"],
        "last_hash": last["chain_hash"], "last_time": last["time"],
        "sha256": hashlib.sha256(seg.read_bytes()).hexdigest()}]))


power_cut("compressed copy written, index not yet", compressed_copy_only)
power_cut("index written, active segment not yet truncated", index_without_truncation)

check.section("4 · Disk")
# Production segments are 32 MB and tiny test segments compress worse, so the yearly
# figure compresses the same proofs as one segment.
raw = ("\n".join(line for line, _error in m._ledger_lines(path) if line) + "\n").encode("utf-8")
per_cycle = len(gzip.compress(raw, 6)) / RESUMED_TO
per_year = per_cycle * 8640 * 365                         # one cycle every 10 s
check("ledger ≤ 6 GB/year at one cycle every 10 s (32 MB segments)", per_year <= 6e9,
      f"{per_cycle / 1024:.2f} KB/cycle stored ({len(raw) / RESUMED_TO / 1024:.1f} KB raw) "
      f"→ {per_year / 1e9:.1f} GB/year")
snapshot = (home / "state.json").stat().st_size
check("compact snapshot", snapshot < 600 * 1024, f"{snapshot / 1024:.0f} KB")

check.finish()
