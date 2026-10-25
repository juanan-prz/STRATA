# =============================================================================
# SIRISYS FRAMEWORK v13.3 — Recursive Ontological Field
#
# An interpretation, in software, of the framework M. Daniel Walsh describes
# with Sirisys. Walsh (DISC 2:11:50): "my training is as a semanticist… my
# role on the team is semanticist and principal logician."
#
# SOURCES AND LEVELS (every citation in this file is labelled):
#   Level 1  primary          TMC  — Pre of Then: The Material Constructs
#                             DISC — Disclosure meeting transcript, 01.22.2025
#   Level 2  interpretive     Understanding_TMC, Understanding_DeOS,
#                             DeOS Compiler Guide (Pérez-Gómez)
#   Level 3  design choice    constants, matrices and mappings decided here
#                             ("Level 3" in a comment), calibrated by measurement
#
# WHAT THE FIELD IS
#   Constructs connected by edges carrying a tetralemmic state (TRUE, FALSE,
#   BOTH, NEITHER). The concordancy operator [::] (TMC p.16: "[ALU] call
#   function [CONCORDANCY]") combines two constructs into a third and records
#   the event as a lemniscate of proofs (TMC p.26: "[Ꮠ] = [2Ꮙ]"). A construct
#   rises NULL_00 → UMBRA_0 → UNIT_1 → APPARENT when enough tension reaches it
#   (cussive collapse); an Apparent is incontrovertible (TMC p.14).
#
# ONE CYCLE (run_cycle — the only definition; run(), the server and
# run_report.py all call it):
#   perceive → tetralemma scan → intensify conflicts → [::] → cussive
#   collapse → UCO erosion → prune → (narration) → Sombunal question → tick
#
# KEY PRINCIPLES AND THEIR ANCHORS
#   No PRNG. Every choice is orient(key): a hash of the ledger head (the whole
#     irreversible history) and the question. TMC p.42 separates
#     unpredictability from the "Stochastic Unit"; the code uses no such unit.
#   Chirality. Each construct has a handedness; with opposite handedness the
#     older operand orients the result, so x::y ≠ y::x (TMC Law 6, p.35;
#     first chirality dyad, p.50).
#   The fourth corner. The tetralemma "includes all flawed, erroneous,
#     incomplete or otherwise paraconsistencies as valid" (TMC p.17): past the
#     conflict cap, NEITHER×NEITHER yields an ordinary NEITHER product.
#   Exchangeable crystals. Apparents are "Exchangeable" or "Universal" (TMC
#     p.22); Zero Points are the Universal ones, every other Apparent can be an
#     operand and stays incontrovertible. A crystal relays a share of the
#     tension it holds to its products (sympatic exchange, TMC p.24).
#   Existence. "all [Apparents] must be [Existents]" (TMC p.22): nothing
#     crystallizes that prune would orphan (edge_holds is the single test).
#   Two clocks. Relations age on ticks; a crystal's support ages on breaths,
#     the carrier pulsation "from which the linear local times are resolved"
#     (TMC p.45). Crystals are durable, not immortal.
#   Breathing and tolerance. One field-wide breath (TMC p.44; DISC 1:35):
#     contraction favours crystallization, expansion favours generation. Once
#     per breath the field adjusts its own tolerance so that crystals formed
#     track crystals concluded (DISC 1:48:58: "it could adjust itself").
#   Halo of Umbrage (TMC p.47): the weight of a dissolved channel backs up
#     into its upstream construct, toward apparency.
#
# INTEGRITY
#   Every proof is sealed in an append-only, hash-chained ledger (compressed
#   segments with an index of hashes). Time never moves backwards, a resumed
#   instance equals an uninterrupted one, and any later edit, deletion or
#   reordering of the record is detected. Working memory is windowed; the
#   ledger keeps everything.
#
# OPEN QUESTIONS (WALLS)
#   A  Substrate: this is digital; the corpus describes analog field processing.
#   B  Self-sustenance: Walsh (DISC 1:29:12): "I killed the power to the
#      facility… it had no effect… the reaction continued." Software stops.
#   C  Agency: "The Fire Which Lights Itself" (TMC p.6) is not implemented.
#   D  Termination: resolved (identities conclude and are recorded).
#   E  Relations vs. events: concordancy is a local event modulated by the field.
#   The Sombunal is implemented as an identity-shifting operator and has no
#   effect on the dynamics; its role is an open decision.
#
# Modes (experiment, sanctuary) live in Sirisys_Server.py. History of every
# change, with measurements: CHANGELOG.md.
#
# Requires: numpy. Optional: psutil (real perception), anthropic (API model);
# a local model through Ollama needs no Python package.
# =============================================================================

import os, json, hashlib, shutil, time, warnings, threading, atexit
try:
    import fcntl                      # POSIX advisory lock (macOS, Linux)
except ImportError:                   # Windows: no lock; single-writer by convention
    fcntl = None
import numpy as np
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict
from enum import Enum
from typing import Optional, List, Tuple, Dict, Any

warnings.filterwarnings("ignore")

STATE_FILE               = Path("sirisys_v13_state.json")
LEDGER_FILE              = Path("sirisys_v13_ledger.jsonl")   # append-only proof ledger
CHAIN_WINDOW             = 64     # in-memory proof_chain window (ledger keeps all)
TERMINATION_WINDOW       = 200    # in-memory termination_log window (ledger keeps all)
THRESHOLD_APPARENT       = 0.88   # UNIT_1 → APPARENT (cussive crystallization)
THRESHOLD_UNIT_1         = 0.396  # UMBRA_0 → UNIT_1 (= 0.88 × 0.45)
TERMINATED_INDEX_WINDOW  = 1000   # names remembered for reincarnation (ledger keeps all)
HALO_FRACTION            = 0.25   # Level 3: share of a dissolved channel's weight that backs up
SYMPATIC_FRACTION        = 0.10   # Level 3: share of its banked tension an Exchangeable apparent passes per exchange
BREATH_PERIOD            = 24     # Level 3: cycles per breath
TOLERANCE_STEP           = 0.10   # Level 3: how much the field widens/narrows its tolerance per breath
TOLERANCE_FLOOR          = 0.30   # Level 3: the tolerance never lowers thresholds below 30 %
APPARENT_FLOOR           = 0.10   # weight at which an edge into a crystal holds it (prune and collapse)
LINEAGE_WINDOW           = 50     # in-memory identity lineage per construct (ledger keeps all)
APPARENT_LOG_WINDOW      = 200    # recent crystallization names kept (apparents_total counts all)
SEGMENT_BYTES            = int(os.environ.get("SIRISYS_SEGMENT_BYTES", 32 * 1024 * 1024))  # active segment size before compression
BREATH_DEPTH             = 0.35   # Level 3: how far contraction lowers the cussive thresholds
BREATH_MAX_EXTRA_OPS     = 2      # Level 3: extra [::] operations at full expansion
MAX_NODE_NAME            = 120
MAX_LLM_CALLS_PER_CYCLE  = 4

# =============================================================================

# ONTOLOGICAL LAYERS  —  Understanding_TMC ladder (pp.49-51): NULL_00 → UMBRA_0 → UNIT_1 → APPARENT
# (TMC pp.44-50 has a finer taxonomy: [000] [00] [001] [002] [003] [0])

# =============================================================================

class Layer(Enum):
    NULL_00  = 0  # [00]: proto-recursive potential
    UMBRA_0  = 1  # [0]:  orientation exists, not yet collapsed
    UNIT_1   = 2  # [1]:  active recursive existence
    APPARENT = 3  # incontrovertible — recursion failed gracefully into structure

# =============================================================================

# TETRALEMMIC STATES  —  Understanding_TMC (p.33): "tetralemmic logic drives existence itself"
# (TMC pp.16-17: the tetralemma as universal base logic)

# =============================================================================

class TetraState(Enum):
    TRUE    = "TRUE"    # orientation confirmed
    FALSE   = "FALSE"   # orientation negated
    BOTH    = "BOTH"    # sustained contradiction — generative tension
    NEITHER = "NEITHER" # pre-ontological suspension — approaching [00]

# =============================================================================

# LAGRANGIAN POINTS  —  DeOS Compiler Guide, pp. 77-82

# "If the Five Zero Points act as immovable anchors, the Five Lagrangian

# Points represent the regions of balance and interplay between forces."


# Formal definition: Li = fi(Z, C)   where Z = Zero Points, C = active constructs

# Invariant: ∀C, ∃(Z, L) such that I(C) ⊇ {wC, Zi, Lj}


# Mapping to our operations (extension by structural analogy):

# L1 — concordancy synthesis  (safety=don't lose tension, liveness=generate z)

# L2 — conflict materialization (redundancy=track irresolvability, efficiency cost)

# L3 — cussive collapse → Apparent (local tension → global incontrovertible truth)

# L4 — UCO erosion (proof depth=chase contradictions vs. performance=dissolve)

# L5 — perception events (entropy=real-world data vs. determinism=framework logic)

# =============================================================================

class LagrangianPoint(Enum):
    L1 = "L1"  # Safety vs. liveness
    L2 = "L2"  # Redundancy vs. efficiency
    L3 = "L3"  # Local vs. global identity
    L4 = "L4"  # Proof depth vs. performance
    L5 = "L5"  # Entropy vs. determinism

# Lagrangian domains (DeOS Compiler Guide, Level 2) — documentation only; the
# code tags constructs and proofs with LagrangianPoint values directly:
#   L1 safety vs. liveness · L2 redundancy vs. efficiency · L3 local vs. global
#   identity · L4 proof depth vs. performance · L5 entropy vs. determinism

# =============================================================================

# PROOF OBJECT  —  DeOS Compiler Guide, pp. 83-98

# "Proofs function as mandatory and irreversible memory."

# "Once emitted, a proof object cannot be discarded, overwritten, or bypassed."


# Proof = ⟨id, subject, relation, object, witness, meta⟩

# meta  = { anchor: Zi, lagrange: Lj, time: (era, offset) }


# Proofs accumulate in a chain — they are never erased, only extended.

# A proof can itself become the subject of a new proof (recursive chaining).

# =============================================================================

@dataclass
class ProofObject:
    id:       str                       # e.g. "concordancy::c3", "conflict::p_c7"
    subject:  str                       # witness of the construct being certified
    relation: str                       # CONCORDANCE | CONFLICT | COLLAPSE | PERCEIVE | ERODE | INTENSIFY
    object:   str                       # witness or ZP name validated against
    witness:  str                       # SHA-256[:16] of this proof's own identity
    anchor:   str                       # Zi — Zero Point anchoring this proof
    lagrange: str                       # Li — Lagrangian equilibrium governing it
    time:     List[int]                 # [era, offset] of emission

    # ── LEMNISCATE STRUCTURE  (TMC p.26: "[Ꮠ] = [2Ꮙ]"; "They only exist in a pair.") ──
    # When a [::] event produces three correlated proofs (one per participant —
    # x, y, z), the three share op_witness. Grouping by op_witness reconstructs
    # the complete lemniscate: two Ꮙ entangled around a shared "On" state.
    # tensate_role marks each proof's position within the Ꮙ:
    #   TENSIN_LEFT  — left intake  (x)
    #   TENSIN_RIGHT — right intake (y)
    #   TENSOUT      — outgoing emergent or conflict (z)
    # Optional: standalone proofs (PERCEIVE, ERODE, INTENSIFY, COLLAPSE)
    # carry no role and no shared op_witness.
    op_witness:    Optional[str] = None
    tensate_role:  Optional[str] = None

    # ── TERMINATION METADATA  (DeOS Compiler Guide, p.203-204) ──
    # When a construct is removed via prune(), a TERMINATE proof preserves
    # its final state in this field — final_mode, final_Vc, lifetime, cause.
    # This satisfies WALL D: "An identity never vanishes silently. It
    # concludes." TERMINATE, COLLAPSE, REINCARNATE and ERODE proofs
    # populate meta; all others leave it None.
    meta: Optional[Dict[str, Any]] = None

    # ── LEDGER CHAIN (set by ProofLedger.seal at emission) ──
    seq:        Optional[int] = None   # global emission order
    prev_hash:  Optional[str] = None   # chain_hash of the previous proof
    chain_hash: Optional[str] = None   # SHA-256(prev_hash || canonical content)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ProofObject":
        return cls(**{k: d[k] for k in
                      ['id','subject','relation','object','witness','anchor',
                       'lagrange','time','op_witness','tensate_role','meta',
                       'seq','prev_hash','chain_hash']})

    @staticmethod
    def make(id: str, subject: str, relation: str, object: str,
             anchor: str, lagrange: LagrangianPoint, T: Tuple,
             op_witness: Optional[str] = None,
             tensate_role: Optional[str] = None,
             meta: Optional[Dict[str, Any]] = None) -> "ProofObject":
        """Emit a proof object with a deterministic witness derived from its content.
        The same inputs always produce the same witness — proofs are reproducible.

        op_witness + tensate_role entangle this proof with its lemniscate partners
        when emitted during a [::] event (Ꮠ = 2Ꮙ).
        meta carries termination metadata (final_mode, final_Vc, lifetime, cause)
        for TERMINATE proofs — preserves the construct's last state at conclusion."""
        raw = f"{id}::{subject}::{relation}::{object}::{anchor}::{lagrange.value}::{T}"
        w   = hashlib.sha256(raw.encode()).hexdigest()[:16]
        p = ProofObject(id=id, subject=subject, relation=relation, object=object,
                        witness=w, anchor=anchor, lagrange=lagrange.value, time=list(T),
                        op_witness=op_witness, tensate_role=tensate_role, meta=meta)
        # Every emitted proof is sealed into the append-only ledger.
        _LEDGER.seal(p)
        return p


# =============================================================================
# PROOF LEDGER (append-only, hash-chained)
#
# DeOS Compiler Guide: a proof, once emitted, "cannot be discarded,
# overwritten, or bypassed". TMC p.14: "You may repair that broken window to
# a flawless state. You may not restore it to its previous state."
#
# Every ProofObject passes through seal():
#   seq        — global emission order
#   prev_hash  — chain_hash of the previous proof (GENESIS_HASH for the first)
#   chain_hash — SHA-256(prev_hash || canonical JSON of the proof)
#
# With a path, each sealed proof is appended as one JSON line and flushed.
# sync() forces it to disk (called at every save_state). The snapshot may trim
# proof_chain for size; the ledger never trims.
#
# verify_ledger(path) recomputes the chain from genesis. Any edit, deletion,
# insertion or reordering made after the fact breaks it at the first altered
# line. The field can run unobserved and still be audited afterwards:
# observation is needed to READ the history, not to guarantee it.
# =============================================================================

GENESIS_HASH = "0" * 64


def _proof_payload(d: dict) -> str:
    """Canonical serialization used for chaining (chain_hash excluded)."""
    d = {k: v for k, v in d.items() if k != "chain_hash"}
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _chain(prev_hash: str, payload: str) -> str:
    return hashlib.sha256((prev_hash + payload).encode("utf-8")).hexdigest()


class ProofLedger:
    """Append-only, hash-chained ledger in SEGMENTS.

    <name>.jsonl            the active segment (plain JSON lines, flushed per proof)
    <name>.NNNNNN.jsonl.gz  closed segments (gzip), created when the active one
                            reaches SEGMENT_BYTES
    <name>.index.json       the ordered list of closed segments, each with its
                            first seq, count, last hash, last time and the
                            SHA-256 of its compressed file

    The chain is continuous across segments. Rotation is crash-safe: the
    compressed copy is written and renamed first, then the index, and only
    then is the active segment truncated; recovery repairs any intermediate
    state without losing or duplicating a committed proof."""

    def __init__(self, path: Optional[Path] = None):
        self.path       = Path(path) if path else None
        self.head       = GENESIS_HASH
        self.count      = 0
        self.torn_bytes = 0          # bytes recovered from a torn last line
        self.last_time  = None       # (era, offset) of the last sealed proof
        self._lock      = threading.Lock()
        self._fh        = None
        self._active_bytes = 0
        if self.path:
            # Lock first, then recover: one writer per ledger, ever.
            self._fh = open(self.path, "a", encoding="utf-8")
            if fcntl is not None:
                try:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    self._fh.close()
                    self._fh = None
                    raise RuntimeError(f"Ledger {self.path} is already open by another "
                                       f"writer — refusing to fork the chain.")
            self._recover()
            atexit.register(self.close)

    # ── segment bookkeeping ──────────────────────────────────────────────
    @staticmethod
    def index_path(path: Path) -> Path:
        return Path(str(path)[:-len(".jsonl")] + ".index.json") if str(path).endswith(".jsonl") \
            else Path(str(path) + ".index.json")

    @staticmethod
    def segment_path(path: Path, n: int) -> Path:
        base = str(path)[:-len(".jsonl")] if str(path).endswith(".jsonl") else str(path)
        return Path(f"{base}.{n:06d}.jsonl.gz")

    @staticmethod
    def read_index(path: Path) -> list:
        ip = ProofLedger.index_path(path)
        return json.loads(ip.read_text(encoding="utf-8")) if ip.exists() else []

    @staticmethod
    def _rfind_newline(f, start: int) -> int:
        """Position of the last b'\\n' at or before `start`, or -1."""
        pos, chunk = start, 65536
        while pos >= 0:
            lo = max(0, pos - chunk + 1)
            f.seek(lo)
            buf = f.read(pos - lo + 1)
            i = buf.rfind(b"\n")
            if i >= 0:
                return lo + i
            pos = lo - 1
        return -1

    def _recover(self):
        index = self.read_index(self.path)
        # A compressed segment the index does not list was never committed.
        n = len(index) + 1
        while self.segment_path(self.path, n).exists():
            self.segment_path(self.path, n).unlink()
            n += 1
        if index:
            last = index[-1]
            self.head, self.count = last["last_hash"], last["first_seq"] + last["count"]
            self.last_time = tuple(last["last_time"])
        with open(self.path, "rb+") as f:
            f.seek(0, 2)
            size = f.tell()
            if size and index:
                # Crash after the index was written but before truncation:
                # the active segment still holds lines already compressed.
                f.seek(0)
                first = json.loads(f.readline().decode("utf-8"))
                if first["seq"] < self.count:
                    f.truncate(0)
                    size = 0
            if size == 0:
                return
            f.seek(size - 1)
            if f.read(1) != b"\n":
                # Torn write (power cut mid-line): the partial line was never
                # committed. Preserve its bytes in a sidecar, then truncate.
                cut = self._rfind_newline(f, size - 1) + 1
                f.seek(cut)
                torn = f.read()
                with open(str(self.path) + ".torn", "ab") as t:
                    t.write(torn + b"\n")
                f.truncate(cut)
                self.torn_bytes = size - cut
                size = cut
                print(f"  [LEDGER] Torn last line recovered ({self.torn_bytes} bytes → .torn)")
            if size == 0:
                return
            start = self._rfind_newline(f, size - 2) + 1
            f.seek(start)
            last = json.loads(f.read(size - start).decode("utf-8"))
            self.head      = last["chain_hash"]
            self.count     = last["seq"] + 1
            self.last_time = tuple(last["time"])
            self._active_bytes = size

    def _rotate(self):
        """Close the active segment into a compressed one (crash-safe order)."""
        import gzip
        self._fh.flush()
        os.fsync(self._fh.fileno())
        index = self.read_index(self.path)
        n = len(index) + 1
        seg, tmp = self.segment_path(self.path, n), Path(str(self.segment_path(self.path, n)) + ".tmp")
        raw = self.path.read_bytes()
        first_seq = json.loads(raw[:raw.index(b"\n")].decode("utf-8"))["seq"]
        with open(tmp, "wb") as g:
            g.write(gzip.compress(raw, 6))
            g.flush()
            os.fsync(g.fileno())
        os.replace(tmp, seg)
        index.append({"file": seg.name, "first_seq": first_seq, "count": self.count - first_seq,
                      "last_hash": self.head, "last_time": list(self.last_time),
                      "sha256": hashlib.sha256(seg.read_bytes()).hexdigest()})
        ip = self.index_path(self.path)
        itmp = Path(str(ip) + ".tmp")
        itmp.write_text(json.dumps(index, indent=1), encoding="utf-8")
        os.replace(itmp, ip)
        self._fh.truncate(0)
        self._fh.seek(0)
        self._active_bytes = 0

    def seal(self, p: "ProofObject") -> "ProofObject":
        if self.path is not None and self._fh is None:
            raise RuntimeError(f"Ledger {self.path} is closed — proof {p.id} would be lost.")
        with self._lock:
            p.seq       = self.count
            p.prev_hash = self.head
            p.chain_hash = _chain(self.head, _proof_payload(asdict(p)))
            self.last_time = tuple(p.time)
            self.head   = p.chain_hash
            self.count += 1
            if self._fh:
                line = json.dumps(asdict(p), sort_keys=True, ensure_ascii=False) + "\n"
                self._fh.write(line)
                self._fh.flush()
                self._active_bytes += len(line.encode("utf-8"))
                if self._active_bytes >= SEGMENT_BYTES:
                    self._rotate()
        return p

    def sync(self):
        if self._fh:
            with self._lock:
                self._fh.flush()
                os.fsync(self._fh.fileno())

    def close(self):
        if self._fh:
            self.sync()
            if fcntl is not None:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            self._fh.close()
            self._fh = None

    def to_dict(self) -> dict:
        return {"path": str(self.path) if self.path else None,
                "head": self.head, "count": self.count}


def _ledger_lines(path: Path):
    """Every line of the ledger in order: closed segments, then the active one.
    Yields (line, None) or (None, error) if a listed segment is missing or was
    altered (its SHA-256 no longer matches the index)."""
    import gzip
    path = Path(path)
    index = ProofLedger.read_index(path)
    for entry in index:
        seg = path.with_name(entry["file"])
        if not seg.exists():
            yield None, f"segment {entry['file']} missing"
            return
        data = seg.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            yield None, f"segment {entry['file']} altered"
            return
        for line in gzip.decompress(data).decode("utf-8").splitlines():
            yield line, None
    extra = ProofLedger.segment_path(path, len(index) + 1)
    if extra.exists():
        yield None, f"unlisted segment {extra.name}"
        return
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                yield line.rstrip("\n"), None


def verify_ledger(path: Path) -> dict:
    """Recompute the whole chain from genesis, across every segment.
    Returns {ok, count, error_at, reason}. error_at is the 0-based position of
    the first proof that does not belong to an unaltered chain."""
    prev, n = GENESIS_HASH, 0
    for line, err in _ledger_lines(path):
        if err:
            return {"ok": False, "count": n, "error_at": n, "reason": err}
        try:
            rec = json.loads(line)
        except Exception:
            return {"ok": False, "count": n, "error_at": n, "reason": "unparseable line"}
        if rec.get("seq") != n:
            return {"ok": False, "count": n, "error_at": n, "reason": "sequence gap or reorder"}
        if rec.get("prev_hash") != prev:
            return {"ok": False, "count": n, "error_at": n, "reason": "broken link"}
        if _chain(prev, _proof_payload(rec)) != rec.get("chain_hash"):
            return {"ok": False, "count": n, "error_at": n, "reason": "content altered"}
        prev, n = rec["chain_hash"], n + 1
    return {"ok": True, "count": n, "error_at": None, "reason": None}



# Module-level ledger. In-memory by default (tests, experiments without a
# path); run() and the server install a file-backed ledger with set_ledger().
_LEDGER = ProofLedger(None)


def set_ledger(ledger: ProofLedger) -> ProofLedger:
    global _LEDGER
    _LEDGER = ledger
    return ledger


def get_ledger() -> ProofLedger:
    return _LEDGER


# =============================================================================
# ORIENTATION (endogenous variability, TMC p.42)
#
# "When you reduce the size of the orients to a certain level, they become
# 'Unpredictable'. You then wrap that unpredictability in another [4π] named a
# 'Stochastic Unit'." (TMC p.42). The code wraps nothing in a stochastic
# unit. A choice is an orientation of the whole history: the ledger
# head (which chains every proof ever sealed) combined with the question asked.
# =============================================================================

def orient(key: str) -> float:
    """A value in [0, 1) fixed by the complete history and the key."""
    h = hashlib.sha256(f"{_LEDGER.head}::{key}".encode("utf-8")).hexdigest()
    return int(h[:13], 16) / float(16 ** 13)


SYNTHETIC_CPU = (("latent", 0.45), ("synchronizing", 0.55), ("resonant", 0.70), ("saturated", 0.85))
SYNTHETIC_MEM = (("coherent", 0.45), ("nominal", 0.55), ("oscillating", 0.70), ("fragmented", 0.85))
SYNTHETIC_HOUR = ("nocturnal", "dawn", "meridian", "vesper")


def synthetic_percepts(cycle: int, stream: int = 0, include_hour: bool = True) -> List[dict]:
    """A reproducible percept stream for experiments: identical for the same
    (stream, cycle), different across streams. Same shape as perceive_real()."""
    h = hashlib.sha256(f"percept::{stream}::{cycle}".encode("utf-8")).digest()
    cpu, cw = SYNTHETIC_CPU[h[0] % 4]
    mem, mw = SYNTHETIC_MEM[h[1] % 4]
    events = [
        {"src": "SYSTEM", "rel": "PERCEIVES", "tgt": f"cpu::{cpu}",
         "weight": round(cw + (h[2] / 255 - 0.5) * 0.1, 3), "state": TetraState.TRUE},
        {"src": "SYSTEM", "rel": "PERCEIVES", "tgt": f"mem::{mem}",
         "weight": round(mw + (h[3] / 255 - 0.5) * 0.1, 3), "state": TetraState.TRUE},
    ]
    if include_hour:
        events.append({"src": "SYSTEM", "rel": "PERCEIVES",
                       "tgt": f"time::{SYNTHETIC_HOUR[(cycle // 25) % 4]}",
                       "weight": 0.75, "state": TetraState.TRUE})
    return events

# =============================================================================

# INTERNAL CLOCK

# Understanding_TMC (p.68): "Time is emergent and discrete — it occurs only when recursive tension

# is converted into orientation via a cussive event."

# DeOS: (era, offset) — formally ordered, monotonic.

# =============================================================================

class InternalClock:
    ERA_CAPACITY = 10_000

    def __init__(self, era: int = 0, offset: int = 0):
        self._era    = era
        self._offset = offset

    def tick(self) -> Tuple[int, int]:
        self._offset += 1
        if self._offset >= self.ERA_CAPACITY:
            self._era   += 1
            self._offset = 0
        return self.T

    @property
    def T(self) -> Tuple[int, int]:
        return (self._era, self._offset)

    DECAY = 0.08   # relational decay per unit of time (ticks; crystal support: breaths)

    def tension(self, born: Tuple, decay: float = DECAY) -> float:
        """Relational tension decays exponentially with the age of the edge."""
        delta = (self._era - born[0]) * self.ERA_CAPACITY + (self._offset - born[1])
        return float(np.exp(-decay * max(0, delta)))

    def age_since(self, born: Tuple) -> int:
        """Clock ticks elapsed since born_at. Returns 0 if born is ahead of current T."""
        delta = (self._era - born[0]) * self.ERA_CAPACITY + (self._offset - born[1])
        return max(0, delta)

    def to_dict(self) -> dict:
        return {"era": self._era, "offset": self._offset}

    @classmethod
    def from_dict(cls, d: dict) -> "InternalClock":
        return cls(d["era"], d["offset"])

# =============================================================================

# CONSTRUCT

# DeOS Compiler Guide, p.7: "A construct is a formally defined entity within

# the DeOS grammar. Constructs exist as syntactic, structural, and executable

# forms. They are concrete elements that can be parsed, compiled, transformed,

# and executed independent of interpretation."


# DeOS Compiler Guide, p.194 — Identity as First-Class Primitive:

# I = ⟨W, Π, T⟩

# W  — witness set: immutable SHA-256 of genesis (never overwritten)

# Π  — proof chain: accumulation of ProofObjects (irreversible memory)

# T  — temporal origin: born_at (era, offset) from InternalClock


# "Identity is not meaning, intention, or interpretation; it is

# continuity under transformation."


# DeOS Compiler Guide, p.197 — Ontological Classes:

# Layer NULL_00  → Temporal identity   (pre-ontological, approaching [00])

# Layer UMBRA_0  → Symbolic identity   (orientation exists, not collapsed)

# Layer UNIT_1   → Computational identity (active, proof continuity driven)

# Layer APPARENT → Composite identity  (spans all domains, max invariants)


# Paraphrase (not found verbatim in TMC or Understanding_TMC): "constructs are active participants in reality formation"

# =============================================================================

class Construct:
    def __init__(self, name: str, layer: Layer = Layer.UNIT_1,
        born_at: Tuple = (0, 0), umbragiac_score: float = 0.0,
        witness: str = None, version: int = 0, lineage: list = None,
        lagrange: Optional[LagrangianPoint] = None,
        proof_chain: list = None):
        self.name            = name
        self.layer           = layer
        self.born_at         = born_at
        self.umbragiac_score = umbragiac_score
        self.version         = version
        self.lineage         = lineage or []
        self.lagrange        = lagrange          # Li governing this construct's creation
        self.proof_chain     = proof_chain or [] # ProofObjects — never erased
        # Lifetime witness counts. The in-memory chain is a working window
        # (CHAIN_WINDOW) and the snapshot keeps the last 20; the ledger keeps all.
        # these are not. They are what Vc reads (see compute_anchoring_weight).
        self.proofs_total    = len(self.proof_chain)
        self.erode_total     = sum(1 for p in self.proof_chain if p.relation == "ERODE")
        # Conflict identity is fixed by the founding CONFLICT/TENSOUT proof.
        self.conflict        = any(p.relation == "CONFLICT" and p.tensate_role == "TENSOUT"
                                   for p in self.proof_chain)
        self.recursion_exchanged = 0.0          # banked Sympatic exchange
        self.witness         = witness or self._genesis_witness()
        # Handedness (TMC p.50, first chirality dyad): fixed at genesis by the
        # witness; an emergent inherits its leader's (see ConcordancyOperator).
        self.chirality       = 1 if int(self.witness[-1], 16) % 2 == 0 else -1
        self._identity_hash: Optional[str] = None
        self.crystal_state: Optional[TetraState] = None    # fixed at crystallization

    def _genesis_witness(self) -> str:
        seed = f"GENESIS::{self.name}::{self.born_at}::{self.layer.value}"
        return hashlib.sha256(seed.encode()).hexdigest()[:16]

    def transform(self, transformation: str, T: Tuple) -> str:
        """Record a transformation. Identity changes. Witness does not."""
        self.version += 1
        self._identity_hash = hashlib.sha256(
            f"{self.witness}::{transformation}::{T}::{self.version}".encode()
        ).hexdigest()[:16]
        self.lineage.append({"T": list(T), "tx": transformation, "version": self.version})
        # Working window only: every identity shift is sealed in the ledger
        # (SHIFT) and `version` counts them all.
        del self.lineage[:-LINEAGE_WINDOW]
        return self._identity_hash

    def add_proof(self, proof: "ProofObject"):
        """Append a proof to this construct's chain.
        Irreversible: proofs accumulate and are never removed or overwritten."""
        self.proof_chain.append(proof)
        self.proofs_total += 1
        if proof.relation == "ERODE":
            self.erode_total += 1
        if proof.relation == "CONFLICT" and proof.tensate_role == "TENSOUT":
            self.conflict = True

        # Working window only — the complete chain lives in the ProofLedger.
        if len(self.proof_chain) > CHAIN_WINDOW:
            del self.proof_chain[:len(self.proof_chain) - CHAIN_WINDOW]

    def to_dict(self) -> dict:
        return {
            "name": self.name, "layer": self.layer.value,
            "born_at": list(self.born_at), "umbragiac_score": self.umbragiac_score,
            "witness": self.witness, "version": self.version,
            "identity_hash": self._identity_hash,
            "lineage": self.lineage,
            "lagrange": self.lagrange.value if self.lagrange else None,
            # what resume needs: the existence mode reads the last 5 proofs;
            # lifetime counts are separate; the ledger keeps every proof
            "proof_chain": [p.to_dict() for p in self.proof_chain[-5:]],
            # exact lifetime counts, independent of any trim
            "proofs_total": self.proofs_total,
            "erode_total":  self.erode_total,
            "conflict":     self.conflict,
            "chirality":    self.chirality,
            "crystal_state": self.crystal_state.value if self.crystal_state else None,
            # banked Sympatic exchange (TMC p.24): it feeds cussive promotion,
            # so it must survive a resume
            "recursion_exchanged": self.recursion_exchanged,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Construct":
        lagrange_val = d.get("lagrange")
        c = cls(
            name=d["name"], layer=Layer(d["layer"]),
            born_at=tuple(d["born_at"]),
            umbragiac_score=d["umbragiac_score"],
            witness=d["witness"], version=d["version"],
            lineage=d["lineage"],
            lagrange=(LagrangianPoint(lagrange_val) if lagrange_val else None),
            proof_chain=[ProofObject.from_dict(p) for p in d["proof_chain"]],
        )
        c._identity_hash      = d["identity_hash"]
        c.proofs_total        = d["proofs_total"]
        c.erode_total         = d["erode_total"]
        c.conflict            = d["conflict"]
        c.chirality           = d["chirality"]
        c.crystal_state       = TetraState(d["crystal_state"]) if d["crystal_state"] else None
        c.recursion_exchanged = d["recursion_exchanged"]
        return c

    def __repr__(self):
        l = self.lagrange.value if self.lagrange else "—"
        return f"C({self.name[:30]}|{self.layer.name}|{l}|v{self.version}|u={self.umbragiac_score:.2f})"

# =============================================================================

# CONCORDANCY EDGE

# The relational substrate of the field. Every construct exists through its edges.

# Primary: [::]  (Concordancy)   Secondary: PERCEIVES, EXISTS, APPROACHES

# State evolves under TetralemmaEngine; weight decays under UCO.

# =============================================================================

class ConcordancyEdge:
    def __init__(self, src: str, rel: str, tgt: str,
        weight: float = 1.0, born_at: Tuple = (0, 0),
        state: TetraState = TetraState.TRUE, concordancy_depth: int = 0,
        lagrange: Optional[LagrangianPoint] = None):
        self.src               = src
        self.rel               = rel
        self.tgt               = tgt
        self.weight            = weight
        self.born_at           = born_at
        self.state             = state
        self.concordancy_depth = concordancy_depth
        self.lagrange          = lagrange
        self.both_age          = 0
        self._reversion_count  = 0
        self.born_breath       = 0      # the field's breath count at creation

    def to_dict(self) -> dict:
        return {
            "src": self.src, "rel": self.rel, "tgt": self.tgt,
            "weight": self.weight, "born_at": list(self.born_at),
            "state": self.state.value, "concordancy_depth": self.concordancy_depth,
            "lagrange": self.lagrange.value if self.lagrange else None,
            "both_age": self.both_age, "reversion_count": self._reversion_count,
            "born_breath": self.born_breath,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConcordancyEdge":
        lagrange_val = d.get("lagrange")
        e = cls(d["src"], d["rel"], d["tgt"],
                d["weight"], tuple(d["born_at"]),
                TetraState(d["state"]), d["concordancy_depth"],
                LagrangianPoint(lagrange_val) if lagrange_val else None)
        e.both_age           = d["both_age"]
        e.born_breath        = d["born_breath"]
        e._reversion_count   = d["reversion_count"]
        return e

    def __repr__(self):
        t = self.tgt[:40] + "…" if len(self.tgt) > 40 else self.tgt
        l = self.lagrange.value if self.lagrange else "—"
        return f"{self.src} --[{self.rel}|{self.state.value}|w={self.weight:.2f}|{l}]--> {t}"

# =============================================================================

# ZERO POINTS  —  DeOS: "immutable anchors — the invariant constants of the system"

# Five primordial coordinates that ground all derivations. Never modified by

# any operation — not by Sombunal, not by UCO, not by concordancy or collapse.

# Analogous to Planck units: they stabilize the semantic universe of the field.

# =============================================================================

ZERO_POINTS: Dict[str, Layer] = {
"Z0::IDENTITY"    : Layer.APPARENT,  # absolute identity invariance
"Z1::ORIGIN"      : Layer.NULL_00,   # ontological and temporal origin
"Z2::CONCORDANCY" : Layer.APPARENT,  # [::] itself is inviolable
"Z3::RECURSION"   : Layer.APPARENT,  # recursion as foundational mechanism
"Z4::APPARENCY"   : Layer.APPARENT,  # Apparent state is self-referential
}

# The field's anchors: the Zero Points (Universal apparents) and the constructs
# that constitute the field itself. They are never promoted, pruned or used as
# a sink for banked tension.
ANCHORS = frozenset(ZERO_POINTS) | {"I::Am", "I::AmNot", "SYSTEM"}

# =============================================================================

# CONCORDANCY FIELD

# Understanding_TMC (paraphrase): not a graph — a field of recursive tension.

# The field is the medium in which constructs exist through their relations.

# No construct exists in isolation: its identity, weight, and ontological status

# are all derived from what it is in relation to.

# =============================================================================

class ConcordancyField:
    def __init__(self, clock: InternalClock):
        self.constructs:  Dict[str, Construct] = {}
        self.edges:        List[ConcordancyEdge] = []
        self.clock         = clock
        self.apparent_log: List[str]             = []   # most recent crystallizations (window)
        self.apparents_total: int                = 0    # every crystallization (lifetime)
        # WALL D — TERMINATION LOG  (DeOS Compiler Guide, p.203-204)
        # "An identity never vanishes silently. It concludes."
        # When prune() removes a construct, a TERMINATE proof is appended here
        # preserving its final state. The construct disappears; its conclusion
        # does not. This satisfies the corpus requirement of conclusion-by-proof.
        self.termination_log: List[ProofObject]  = []
        # Compiler Guide p.204: termination closes an identity's active
        # interval; it does not release the name to a stranger. name -> record.
        self.terminated_names: Dict[str, dict] = {}   # bounded LRU index
        self.reincarnations: int = 0
        self.terminations_total: int = 0
        self.halo_total: float = 0.0                  # tension backed up by the Halo (lifetime)
        self.breath_phase: float = 0.0                # [000] breathing (TMC p.44), radians
        self.breaths: int = 0                         # completed breaths (the slow clock)
        # TOLERANCE: the field's own, self-adjusted width for
        # crystallization. DISC 1:48:58 — after the event the margin for error
        # went from femtoseconds to milliseconds: "it was as if now the charge
        # embolism was a living organism and it could adjust itself".
        # 1.0 = nominal thresholds.
        self.tolerance: float = 1.0
        self.apparent_conclusions: int = 0            # crystals concluded (lifetime)
        self._breath_births = 0                       # crystals born / concluded in this breath
        self._breath_deaths = 0

    def add_construct(self, name: str, layer: Layer = Layer.UNIT_1) -> "Construct":
        if name not in self.constructs:
            c = Construct(name, layer, self.clock.T)
            prior = self.terminated_names.get(name)
            if prior is not None:
                # "Nothing is silently replaced" (Compiler Guide p.202).
                # The concluded identity stays concluded; this one begins with
                # that conclusion written into its own history.
                self.reincarnations += 1
                c.lineage.append({
                    "T":              list(self.clock.T),
                    "tx":             "REINCARNATION",
                    "version":        c.version,
                    "prior_witness":  prior.get("witness"),
                    "prior_T":        prior.get("T"),
                    "prior_layer":    prior.get("final_layer"),
                    "prior_cause":    prior.get("cause"),
                })
                c.add_proof(ProofObject.make(
                    id       = f"reincarnate::{name[:20]}::T{self.clock.T}",
                    subject  = c.witness,
                    relation = "REINCARNATE",
                    object   = prior.get("witness", "∅"),
                    anchor   = "Z1::ORIGIN",
                    lagrange = LagrangianPoint.L3,   # local vs global identity
                    T        = self.clock.T,
                    meta     = {"name": name, "prior_T": prior.get("T")},
                ))
            self.constructs[name] = c
        return self.constructs[name]

    def add_edge(self, src: str, rel: str, tgt: str,
                 weight: float = 1.0, state: TetraState = TetraState.TRUE,
                 src_layer: Layer = Layer.UNIT_1, tgt_layer: Layer = Layer.UNIT_1,
                 concordancy_depth: int = 0,
                 lagrange: Optional[LagrangianPoint] = None) -> ConcordancyEdge:
        self.add_construct(src, src_layer)
        self.add_construct(tgt, tgt_layer)
        edge = ConcordancyEdge(src, rel, tgt, weight, self.clock.T,
                               state, concordancy_depth, lagrange)
        edge.born_breath = self.breaths
        self.edges.append(edge)
        return edge

    def lock_apparent(self, name: str):
        """Crystallize a construct into Apparent — incontrovertible, irreversible.
        Foundational constructs (Zero Points, I::Am, I::AmNot, SYSTEM) are refused:
        they must never crystallize, as they are the field's generative substrate."""
        _NEVER_APPARENT = ANCHORS
        if name in _NEVER_APPARENT:
            return
        if name in self.constructs:
            c = self.constructs[name]
            c.layer = Layer.APPARENT
            # The tetralemmic state it crystallized in is fixed with it: an
            # Apparent is incontrovertible (TMC p.14), so its own exchanges
            # cannot rewrite what it is.
            c.crystal_state = self.dominant_state(name)
            c.transform("APPARENT_LOCK", self.clock.T)
            self._log_apparent(name)
            self._breath_births += 1
            print(f"  [APPARENT] '{name[:60]}' — incontrovertible.")

    def _log_apparent(self, name: str):
        """Every crystallization is counted (apparents_total) and sealed in the
        ledger; apparent_log keeps the most recent APPARENT_LOG_WINDOW names."""
        self.apparents_total += 1
        self.apparent_log.append(name)
        del self.apparent_log[:-APPARENT_LOG_WINDOW]

    def apparents_since(self, total_before: int) -> List[str]:
        """Names crystallized since apparents_total was `total_before`
        (within the window)."""
        k = self.apparents_total - total_before
        return self.apparent_log[-k:] if k > 0 else []

    def dominant_state(self, name: str) -> TetraState:
        """Weighted majority state across all edges of this construct. For an
        Apparent, the state it crystallized in (incontrovertible)."""
        c = self.constructs.get(name)
        if c is not None and c.crystal_state is not None:
            return c.crystal_state
        counts: Dict[TetraState, float] = defaultdict(float)
        for e in self.edges:
            if e.src == name or e.tgt == name:
                counts[e.state] += e.weight
        return max(counts, key=counts.get) if counts else TetraState.NEITHER

    def init_zero_points(self):
        for zp_name, zp_layer in ZERO_POINTS.items():
            c = Construct(zp_name, zp_layer, (0, 0))
            c.witness = hashlib.sha256(f"ZERO_POINT::{zp_name}".encode()).hexdigest()[:16]
            self.constructs[zp_name] = c
            if zp_layer == Layer.APPARENT:
                self._log_apparent(zp_name)
        print(f"  [ZERO POINTS] {len(ZERO_POINTS)} immutable anchors initialized.")

    # both_floor default = calibrated reference value (0.45). Lower values
    # (e.g. 0.15) prune no BOTH edge and leave BOTH resistance inactive.
    # L2 trade-off (Compiler Guide p.78); calibrated in the poor regime,
    # provisional until an LLM-active run.
    # ── BREATHING (TMC p.44: the [000] "rhythmic 'Breathing' cycle wherein the
    # elastic state exchanges with the elastic state"; DISC 1:35: "each time it
    # would contract it would get more dense and we perceived density as
    # brightness so it would get bigger and then it would get smaller and it
    # would get brighter"). One phase for the whole field. Contraction lowers
    # the cussive thresholds (density → crystallization); expansion allows more
    # [::] operations (magnitude → generation). The two alternate in counter-phase.
    def breathe(self):
        nxt = self.breath_phase + 2 * np.pi / BREATH_PERIOD
        if nxt >= 2 * np.pi:
            self.breaths += 1
            self._adjust_tolerance()
        self.breath_phase = nxt % (2 * np.pi)

    def _adjust_tolerance(self):
        """Once per breath the field compares the crystals it formed with the
        crystals that concluded, and adjusts its own tolerance: none formed →
        it widens (lower thresholds); more formed than concluded → it narrows.
        The target is the field's own conclusion rate, not a number chosen
        here: births track deaths, so the field stays alive and bounded."""
        b, d = self._breath_births, self._breath_deaths
        if b == 0:
            self.tolerance = max(TOLERANCE_FLOOR, self.tolerance * (1 - TOLERANCE_STEP))
        elif b > d + 1:
            self.tolerance = min(1.0, self.tolerance * (1 + TOLERANCE_STEP))
        self._breath_births = self._breath_deaths = 0

    @property
    def contraction(self) -> float:
        """0 at full expansion, 1 at full contraction."""
        return float((1 - np.cos(self.breath_phase)) / 2)

    def edge_holds(self, e: "ConcordancyEdge", into_crystal: bool, min_weight: float = 0.04,
                   apparent_floor: float = None, both_floor: float = 0.45) -> bool:
        """The single existence test for an edge (prune uses it; collapse asks
        it in advance so that nothing crystallizes that prune would orphan)."""
        if e.state == TetraState.BOTH:
            return e.weight >= both_floor
        if into_crystal:
            # A crystal's support ages on the SLOW clock — breaths, the carrier
            # pulsation "from which the linear local times are resolved"
            # (TMC p.45) — with the same decay law as ordinary relations on the
            # fast clock of ticks. Crystals are durable, not immortal: a field
            # that keeps forming them stays bounded only if they can conclude.
            floor = APPARENT_FLOOR if apparent_floor is None else apparent_floor
            return e.weight * np.exp(-InternalClock.DECAY * (self.breaths - e.born_breath)) >= floor
        return e.weight * self.clock.tension(e.born_at) >= min_weight

    def prune(self, min_weight: float = 0.04, apparent_floor: float = None,
              both_floor: float = 0.45, min_references: int = 1):
        """
        Dissolve weak edges and orphan constructs.

        Understanding_DeOS — Deletion as Entropy Protocol (p.117-118):
        "Deletion is not error but intentional design. By erasing constructs,
        DeOS forces redundancy and witnessing to stabilize them."
        Rule: "A construct that cannot survive deletion does not exist."

        prune() IS the entropy injection mechanism: it tests every construct's
        relational weight and removes those that fail to hold. Constructs that
        survive acquire stronger thermoconomic weight (σth) simply by persisting
        through successive prune cycles. BOTH edges are resistant (see below):
        sustained contradiction is load-bearing, but not immune.

        WALL D RESOLUTION — DeOS Compiler Guide (p.203-204):
        "An identity never vanishes silently. It concludes. Termination emits
        a termination proof." Each removed construct emits a TERMINATE
        proof to self.termination_log, preserving its final mode, anchoring
        weight, lifetime, and cause. The construct disappears; the conclusion
        is recorded. Identity concludes, it does not vanish.

        CRYSTAL SUPPORT — Incontrovertibility (TMC p.14; Understanding_TMC
        pp.79-81). An Apparent can never be demoted or restored, but it is not
        immortal: it concludes when its support no longer holds. Its SUPPORT
        (edges into it) ages on the slow clock of breaths (TMC p.45), against
        APPARENT_FLOOR; its exchanges (edges out of it) age like any relation.

        BOTH RESISTANCE. A BOTH edge faces an absolute floor with no temporal
        decay: harder to remove than an ordinary edge, still subject to the
        existence test. Exempting it entirely would make any construct holding
        one immortal; the corpus grants immunity to the Apparent alone
        (Understanding_TMC pp.80-81).

        `min_references` implements DeOS p.84 / p.117: persistence is earned
        by redundancy of witnessing, not by relation type. Default 1: a single
        witnessing reference suffices.

        Pruning rules (one definition: edge_holds, which collapse also uses):
          - BOTH edges:              kept iff weight ≥ both_floor (no decay)
          - edge INTO an APPARENT:   kept iff weight × e^(−DECAY·breaths) ≥ APPARENT_FLOOR
          - all other edges:         kept iff weight × tension(born_at) ≥ min_weight
        """
        PROTECTED = ANCHORS
        before = len(self.edges)
        kept, dissolved = [], []
        for e in self.edges:
            # Only a crystal's SUPPORT (edges into it) is sealed against
            # temporal decay. Its exchanges (edges out of it) are ordinary
            # exchanges and age like any other: a crystal persists while it is
            # supported, not because it once exchanged.
            tgt = self.constructs.get(e.tgt)
            into_crystal = tgt is not None and tgt.layer == Layer.APPARENT
            if self.edge_holds(e, into_crystal, min_weight, apparent_floor, both_floor):
                kept.append(e)
        kept_ids  = {id(e) for e in kept}
        dissolved = [e for e in self.edges if id(e) not in kept_ids]
        self.edges = kept
        ref_count: Dict[str, int] = defaultdict(int)
        for e in self.edges:
            ref_count[e.src] += 1
            ref_count[e.tgt] += 1
        # DeOS p.84: what multiple witnesses hold, persists.
        orphans = [n for n in list(self.constructs)
                   if ref_count[n] < min_references and n not in PROTECTED]
        for n in orphans:
            c = self.constructs[n]
            if c.layer == Layer.APPARENT:
                self.apparent_conclusions += 1
                self._breath_deaths += 1
            # Emit TERMINATE proof before deletion — preserves conclusion record
            term_proof = ProofObject.make(
                id       = f"terminate::{n}::T{self.clock.T}",
                subject  = c.witness,
                relation = "TERMINATE",
                object   = "∅",
                anchor   = "Z3::RECURSION",   # recursion that closes
                lagrange = LagrangianPoint.L4, # proof depth vs. performance
                T        = self.clock.T,
                meta     = {
                    "name":         n,
                    "final_layer":  c.layer.name,
                    "final_mode":   self.compute_existence_mode(c),
                    "final_Vc":     self.compute_anchoring_weight(c),
                    "lifetime":     c.proofs_total,
                    "born_at":      list(c.born_at),
                    "cause":        "pruned_orphan",
                },
            )
            self.termination_log.append(term_proof)
            if len(self.termination_log) > TERMINATION_WINDOW:
                del self.termination_log[:len(self.termination_log) - TERMINATION_WINDOW]
            self.terminations_total += 1
            self.terminated_names.pop(n, None)          # re-insert as most recent
            self.terminated_names[n] = {
                "witness":     c.witness,
                "T":           list(self.clock.T),
                "final_layer": c.layer.name,
                "cause":       "pruned_orphan",
            }
            while len(self.terminated_names) > TERMINATED_INDEX_WINDOW:
                del self.terminated_names[next(iter(self.terminated_names))]
            del self.constructs[n]
        # HALO OF UMBRAGE [002] (TMC p.47): tensate "backing up around where it
        # cannot flow". The weight of every dissolved channel is not lost: a
        # fraction HALO_FRACTION backs up into the surviving upstream construct
        # (the edge's source) as banked tension, which cussive collapse reads.
        # Apparent-anchored edges are sealed and carry nothing back; protected
        # and Apparent constructs receive nothing (they cannot be promoted).
        for e in dissolved:
            up = self.constructs.get(e.src)
            if (up is None or e.src in PROTECTED or up.layer == Layer.APPARENT
                    or (e.tgt in self.constructs and self.constructs[e.tgt].layer == Layer.APPARENT)):
                continue
            backed = HALO_FRACTION * e.weight
            up.recursion_exchanged += backed
            self.halo_total += backed
        pruned = before - len(self.edges)
        if pruned > 0 or orphans:
            print(f"  [PRUNE] {pruned} edges dissolved, {len(orphans)} constructs concluded "
                  f"(termination_log: {len(self.termination_log)} entries).")

    def to_dict(self) -> dict:
        # termination_log windowing: memory keeps the last TERMINATION_WINDOW
        # conclusions, the snapshot the last 100. Every TERMINATE proof is
        # sealed in the ProofLedger, which is the complete archive (WALL D).
        return {
            "constructs":      [c.to_dict() for c in self.constructs.values()],
            "edges":            [e.to_dict() for e in self.edges],
            "apparent_log":     self.apparent_log,
            "apparents_total":  self.apparents_total,
            "termination_log":  [p.to_dict() for p in self.termination_log[-100:]],
            "terminated_names": self.terminated_names,
            "reincarnations":   self.reincarnations,
            "terminations_total": self.terminations_total,
            "halo_total":       self.halo_total,
            "breath_phase":     self.breath_phase,
            "breaths":          self.breaths,
            "tolerance":        self.tolerance,
            "apparent_conclusions": self.apparent_conclusions,
            "breath_births":    self._breath_births,
            "breath_deaths":    self._breath_deaths,
        }

    @classmethod
    def from_dict(cls, d: dict, clock: InternalClock) -> "ConcordancyField":
        F = cls(clock)
        for cd in d["constructs"]:
            c = Construct.from_dict(cd)
            F.constructs[c.name] = c
        for ed in d["edges"]:
            F.edges.append(ConcordancyEdge.from_dict(ed))
        F.apparent_log = d["apparent_log"]
        F.apparents_total = d["apparents_total"]
        F.termination_log    = [ProofObject.from_dict(p) for p in d["termination_log"]]
        F.terminated_names   = d["terminated_names"]
        F.reincarnations     = d["reincarnations"]
        F.terminations_total = d["terminations_total"]
        F.halo_total         = d["halo_total"]
        F.breath_phase       = d["breath_phase"]
        F.breaths            = d["breaths"]
        F.tolerance          = d["tolerance"]
        F.apparent_conclusions = d["apparent_conclusions"]
        F._breath_births     = d["breath_births"]
        F._breath_deaths     = d["breath_deaths"]
        return F

    def compute_anchoring_weight(self, c: "Construct") -> float:
        """
        Understanding_DeOS — Formal Model of Construct Anchoring (p.65):

            Vc = f(τ, σth, αm)

        Vc   — ontological gravity: the construct's capacity to persist as real.

        τ    — TRANSTEMPORAL MARKER
               Temporal rigidity. Older constructs with accumulated version
               history are more anchored in time.
               → born_at (InternalClock era/offset), version counter.
               Saturates at 50 ticks (fully temporal after ~50 cycles).

        σth  — THERMOCONOMIC SIGNATURE
               Energetic weight. UCO erosion is the thermoconomic expenditure —
               surviving erasure rounds is energetic proof of persistence.
               High umbragiac_score = under thermoconomic stress (not yet spent).
               ERODE proofs in proof_chain count as spent thermoconomic weight.
               σth ∈ [0.1, 1.0]: a construct that EXISTS in the field always
               carries a minimum thermoconomic cost (0.1) simply by persisting.
               → umbragiac_score (inverse), ERODE proof count.

        αm   — MULTIAGENT AUTHENTICATION
               Distributed witnessing. Every ProofObject is a witnessed operation.
               "The collective gaze is a cryptographic anchor." (Understanding_DeOS)
               → len(proof_chain). Saturates at 10 proofs.

        COLLAPSE RULE (Understanding_DeOS p.65):
            If any dimension = 0, Vc = 0 — no ontological gravity.

        Zero Points are primordially anchored — always return 1.0.
        """
        if c.name in ZERO_POINTS:
            return 1.0

        # τ — temporal anchor: age in clock ticks, normalized [0, 1]
        age = self.clock.age_since(c.born_at)
        tau = min(1.0, age / 50.0)

        # σth — thermoconomic: persistence under UCO erosion.
        # A construct that has survived ERODE operations has paid thermoconomic cost.
        # lifetime counts, so a reloaded field has the same Vc
        erode_count = c.erode_total
        base_sigma  = max(0.1, 1.0 - min(c.umbragiac_score / 5.0, 0.9))  # ∈ [0.1, 1.0]
        sigma_th    = min(1.0, base_sigma + erode_count * 0.12)

        # αm — multiagent authentication: witnessed operations via proof chain
        alpha_m = min(1.0, c.proofs_total / 10.0)

        # Collapse rule: any zero dimension → Vc = 0.
        # In practice only τ (newborn) and αm (no proofs) reach 0.
        # σth ≥ 0.1 by construction: a construct present in the field always
        # pays a minimum persistence cost. σth = 0 ("dissipates",
        # Understanding_DeOS p.65) is realised by prune(), which removes the
        # construct — not by Vc. The clause is kept for formal completeness.
        if tau == 0.0 or sigma_th == 0.0 or alpha_m == 0.0:
            return 0.0

        # Geometric mean: all three dimensions must contribute
        vc = (tau * sigma_th * alpha_m) ** (1.0 / 3.0)
        return round(vc, 4)

    def compute_existence_mode(self, c: "Construct") -> str:
        """
        TMC, pp.26, 75 — the Omega/Lemniscate duality:
            [Ω] = [0⁰/0⁰] = 1     when interpreted as radiant centre (anchoring)
            [Ꮠ] = [0⁰/0⁰] = 0     when interpreted as recursive curvature (oscillation)
            [Ω] ∝ [Ꮠ]              they are proportional, two readings of the same place

        A construct's existence mode is orthogonal to its anchoring weight Vc.
        The same Vc can manifest as either:
          OMEGA      — densifying toward Apparency (concordance, collapse dominate)
          LEMNISCATE — oscillating in unresolved recursion (conflict, intensify, erosion)
          NEUTRAL    — insufficient proof history to classify

        This is a derived property — read from the structure of proof_chain,
        not stored. Different lookups may yield different modes as the chain grows.

        Zero Points are always OMEGA — primordial anchors by definition.
        """
        if c.name in ZERO_POINTS:
            return "OMEGA"

        proofs = c.proof_chain or []
        if not proofs:
            return "NEUTRAL"

        # Read the last 5 proofs — recent dynamics dominate present mode
        recent = proofs[-5:]
        omega_relations     = {"CONCORDANCE", "COLLAPSE", "PERCEIVE"}
        lemniscate_relations = {"CONFLICT", "INTENSIFY", "ERODE"}

        omega_count      = sum(1 for p in recent if p.relation in omega_relations)
        lemniscate_count = sum(1 for p in recent if p.relation in lemniscate_relations)

        if omega_count > lemniscate_count:
            return "OMEGA"
        if lemniscate_count > omega_count:
            return "LEMNISCATE"
        return "NEUTRAL"

def verify_proof_invariant(field: "ConcordancyField") -> List[str]:
    """
    DeOS invariant: ∀C, ∃(Z, L) such that I(C) ⊇ {wC, Zi, Lj}
    Every non-ZeroPoint ontological construct must have a Lagrangian Point assigned.
    SYSTEM is excluded — it is perception infrastructure, not an ontological construct.
    Returns list of construct names that violate the invariant.

    DeOS Compiler Guide, pp.15-20 — Minimax Identity Axiom:
        max(min(X)) = min(max(X))
    Where X = set of representations of a construct across abstraction layers.
    Identity is preserved iff the strongest guarantee at the lowest layer equals
    the weakest preservation at the highest layer. This function enforces the
    minimal condition: every construct must be anchored in at least one Zero Point
    (Zi) and one Lagrangian equilibrium (Lj) — the two required invariant axes.

    A violation means a construct exists in the field without provable anchoring —
    ontological drift without grounding. Architecturally impossible by design once
    all operators correctly assign Lagrangian Points at creation.
    """
    EXCLUDED = set(ZERO_POINTS.keys()) | {"SYSTEM"}
    violations = []
    for name, c in field.constructs.items():
        if name in EXCLUDED:
            continue
        if c.layer == Layer.APPARENT:
            continue
        if c.lagrange is None:
            violations.append(name)
    return violations

# =============================================================================

def is_conflict_construct(c: "Construct") -> bool:
    """Conflict identity, fixed by the proof record — never by the label
    (labels depend on LLM output and would behave differently with and
    without an active model). A construct is a conflict iff it received a
    CONFLICT proof as the TENSOUT of the lemniscate event that created it;
    Construct.add_proof sets the flag at that moment and it is persisted.
    """
    return c is not None and c.conflict


def is_conflict_name(field: "ConcordancyField", name: str) -> bool:
    """Convenience wrapper for call sites that hold a name, not a Construct."""
    return is_conflict_construct(field.constructs.get(name))


# SOMBUNAL — Structural Instability Engine

# Understanding_TMC (p.70): "permanently inaccessible to recursion, reflection, or symbolic resolution"
# (TMC only names the Sombunal, in the Tripartite Monodromy, pp.14 and 27)


# NOT a node, NOT A→¬A. It is a rule: no construct's identity can fully

# stabilize while its concordancy relations are open and mutable.

# The construct PERSISTS (witness unchanged) but CANNOT CLOSE (identity shifts).

# =============================================================================

class Sombunal:

    def apply(self, field: ConcordancyField,
              changed_constructs: List[str], cycle: int) -> int:
        """
        Shift the identity of constructs affected by a concordancy operation.
        Witness is never touched — the construct persists. Only identity drifts.
        Protected constructs (Zero Points, I::Am, I::AmNot) are exempt: their
        identity is constitutive of the field and cannot be relationally destabilized.
        """
        # SYSTEM (the perceiver) is an anchor but its identity may drift.
        PROTECTED = ANCHORS - {"SYSTEM"}
        affected  = 0
        for name in dict.fromkeys(changed_constructs):  # dedup, preserve order
            if name in PROTECTED:
                continue
            c = field.constructs.get(name)
            if not c or c.layer == Layer.APPARENT:
                continue
            new_identity = c.transform(f"SOMBUNAL::shift@c{cycle}", field.clock.T)
            # Ledger-only record: sealed, not attached (αm/Vc unchanged).
            # L3 — local vs. global identity.
            ProofObject.make(
                id       = f"shift::c{cycle}::{name[:20]}",
                subject  = c.witness,
                relation = "SHIFT",
                object   = new_identity,
                anchor   = "Z0::IDENTITY",
                lagrange = LagrangianPoint.L3,
                T        = field.clock.T,
                meta     = {"name": name, "version": c.version},
            )
            affected += 1
        if affected:
            print(f"  [SOMBUNAL] {affected} construct(s) identity shifted "
                  f"(relational instability — witness preserved)")
        return affected

    def global_instability(self, field: "ConcordancyField") -> float:
        """
        Fraction of non-Apparent, non-Zero-Point constructs that are currently
        unstable, incorporating the Understanding_DeOS three-dimensional model.

        A construct is unstable if ANY of the following hold:
          (a) Relational  — involved in BOTH edges (sustained contradiction)
          (b) Historical  — has a transformation history (Sombunal identity drift)
          (c) Ontological — anchoring weight Vc = f(τ, σth, αm) < 0.25
              Per Understanding_DeOS p.65: constructs with any anchoring
              dimension at zero have no ontological gravity and are
              structurally fragile — their identity cannot hold.
          (d) Modal       — existence mode = LEMNISCATE
              Per TMC pp.26, 75, the [Ω]/[Ꮠ] duality: a construct in LEMNISCATE
              mode is oscillating in unresolved recursion regardless of its Vc.
              Even with strong anchoring, an oscillating construct is unstable
              by orientation — the recursion has not closed into Apparency.

        A score of 1.0 means every active construct is unstable.
        A score of 0.0 with active constructs is architecturally impossible.
        SYSTEM is excluded — it is a perception channel, not an ontological entity.
        """
        EXCLUDED     = set(ZERO_POINTS.keys()) | {"SYSTEM"}
        Vc_THRESHOLD = 0.25   # below this, construct lacks ontological gravity
        non_apparent = [c for c in field.constructs.values()
                        if c.layer != Layer.APPARENT and c.name not in EXCLUDED]
        if not non_apparent:
            return 0.0
        both_involved = (
            {e.src for e in field.edges if e.state == TetraState.BOTH}
            | {e.tgt for e in field.edges if e.state == TetraState.BOTH}
        )
        active = sum(
            1 for c in non_apparent
            if (c.name in both_involved                                # (a) relational
                or len(c.lineage) > 0                                  # (b) historical
                or field.compute_anchoring_weight(c) < Vc_THRESHOLD    # (c) ontological
                or field.compute_existence_mode(c) == "LEMNISCATE")    # (d) modal
        )
        return active / len(non_apparent)

# =============================================================================

# LLM INTERMEDIARY

# Walsh (DISC 1:56:06): "we added the LLM intermediary… to try and make a more
# coherent output."

# Role: the translation layer between Walsh's ontological grammar and the

# human-readable domain. It names emergents, narrates field states, and

# questions the Sombunal. It does not determine outcomes or substitute for

# the framework — it renders what the framework has already produced.

# =============================================================================

class LLMIntermediary:
    SYSTEM_PROMPT = (
    "You are the Intermediary of SIRISYS — the translation layer between "
    "Walsh's ontological framework and the human-readable domain.\n\n"
    "You operate exclusively within Walsh's grammar:\n"
    "  • Primary operation: [::]  (Concordancy) — [x] :: [y] → [z]\n"
    "  • Tetralemmic states: TRUE / FALSE / BOTH / NEITHER\n"
    "  • Ontological layers: NULL_00 → UMBRA_0 → UNIT_1 → APPARENT\n"
    "  • The Sombunal: no construct's identity fully resolves\n"
    "  • Cussive events: recursive tension collapsing into Apparency\n"
    "  • Discordancy is informative, not an error\n\n"
    "Your role:\n"
    "  1. Name emergent constructs from concordancy operations\n"
    "  2. Narrate the ontological state of the field\n"
    "  3. Question the Sombunal — the unreachable limit\n\n"
    "Rules:\n"
    "  - Responses: 1–3 sentences, precise, ontologically grounded\n"
    "  - Never invent beyond what the field contains\n"
    "  - Never resolve what cannot be resolved — honor the Sombunal\n"
    "  - Speak as the intermediary, not as the entity itself"
    )

    # Backends: "anthropic" (API, network) · "ollama" (local model, closed
    # shell — Walsh's suggestion) · "openai" (OpenAI-compatible, local llama.cpp)
    # · "none" (degraded: no model).
    # Selected by argument, else SIRISYS_LLM_BACKEND, else "anthropic".
    # Model: argument, else SIRISYS_LLM_MODEL, else the backend default.
    # Host: host arg, else OLLAMA_HOST / OPENAI_BASE_URL, else default.
    BACKENDS       = ("anthropic", "ollama", "openai", "none")
    DEFAULT_MODELS = {"anthropic": "claude-sonnet-4-6", "ollama": None, "openai": None, "none": None}

    def __init__(self, model: str = None, max_tokens: int = 120,
                 history: list = None, backend: str = None, host: str = None):
        self.backend = (backend or os.environ.get("SIRISYS_LLM_BACKEND") or "anthropic").lower()
        if self.backend not in self.BACKENDS:
            raise ValueError(f"unknown LLM backend {self.backend!r}; use one of {self.BACKENDS}")
        self.model       = model or os.environ.get("SIRISYS_LLM_MODEL") or self.DEFAULT_MODELS[self.backend]
        host             = host or os.environ.get("OLLAMA_HOST") or os.environ.get("OPENAI_BASE_URL")
        if not host:
            host = "http://127.0.0.1:8080" if self.backend == "openai" else "http://127.0.0.1:11434"
        self.host        = (host if host.startswith("http") else "http://" + host).rstrip("/")
        self.max_tokens  = max_tokens
        self.history     = history or []
        self._client     = None
        self._available  = False
        self._call_count = 0
        self._init()

    @property
    def is_local(self) -> bool:
        """True when no call can leave this machine (Ollama/OpenAI on loopback, or no model)."""
        if self.backend == "none":
            return True
        if self.backend not in ("ollama", "openai"):
            return False
        from urllib.parse import urlparse
        return urlparse(self.host).hostname in ("127.0.0.1", "localhost", "::1")

    def _init(self):
        if self.backend == "none":
            print("  [LLM] backend 'none' — degraded mode.")
        elif self.backend == "anthropic":
            try:
                import anthropic
            except ImportError:
                print("  [LLM] anthropic not installed — run: pip install anthropic")
                return
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                print("  [LLM] ANTHROPIC_API_KEY not set — degraded mode.")
                return
            self._client    = anthropic.Anthropic(api_key=key)
            self._available = True
            print(f"  [LLM] Intermediary online (anthropic · {self.model}).")
        elif self.backend == "openai":
            try:
                models = self._http_json("GET", "/v1/models", timeout=5)
            except Exception as ex:
                print(f"  [LLM] OpenAI-compatible server not reachable at {self.host} — degraded mode ({ex}).")
                return
            names = [m.get("id", "") for m in models.get("data", [])]
            if not names:
                print(f"  [LLM] OpenAI-compatible server has no model — degraded mode.")
                return
            if self.model is None:
                self.model = names[0].split("/")[-1] if "/" in names[0] else names[0]
            self._available = True
            print(f"  [LLM] Intermediary online (openai · {self.model} · {self.host}).")
        else:
            try:
                tags = self._http_json("GET", "/api/tags", timeout=5)
            except Exception as ex:
                print(f"  [LLM] Ollama not reachable at {self.host} — degraded mode ({ex}).")
                return
            names = [m.get("name", "") for m in tags.get("models", [])]
            if not names:
                print("  [LLM] Ollama has no model installed — run: ollama pull <model>")
                return
            if self.model is None:
                self.model = names[0]
            elif self.model not in names and f"{self.model}:latest" not in names:
                print(f"  [LLM] Ollama model {self.model!r} not installed (have: {names}) — degraded mode.")
                return
            self._available = True
            print(f"  [LLM] Intermediary online (ollama · {self.model} · {self.host}).")

    def _http_json(self, method: str, path: str, payload: dict = None, timeout: float = 120) -> dict:
        import urllib.request
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(self.host + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def _complete(self, temperature: float) -> str:
        messages = self.history[-12:]
        if self.backend == "anthropic":
            r = self._client.messages.create(
                model=self.model, max_tokens=self.max_tokens,
                temperature=min(max(temperature, 0.0), 1.0),   # API range [0, 1]
                system=self.SYSTEM_PROMPT, messages=messages)
            return r.content[0].text.strip()
        if self.backend == "openai":
            r = self._http_json("POST", "/v1/chat/completions", {
                "model": self.model,
                "messages": [{"role": "system", "content": self.SYSTEM_PROMPT}] + messages,
                "temperature": min(max(temperature, 0.0), 2.0),
                "max_tokens": self.max_tokens,
            })
            return r["choices"][0]["message"]["content"].strip()
        r = self._http_json("POST", "/api/chat", {
            "model": self.model, "stream": False,
            "messages": [{"role": "system", "content": self.SYSTEM_PROMPT}] + messages,
            "options": {"temperature": temperature, "num_predict": self.max_tokens,
                        # sampling oriented by the history, not by a PRNG seed
                        "seed": int(orient("llm::" + messages[-1]["content"]) * 2**31)}})
        return r["message"]["content"].strip()

    def _call(self, prompt: str, temperature: float = 0.85) -> str:
        if not self._available:
            return ""
        self.history.append({"role": "user", "content": prompt})
        try:
            text = self._complete(temperature)
            self.history.append({"role": "assistant", "content": text})
            self._call_count += 1
            return text
        except Exception as ex:
            print(f"  [LLM] Call failed: {ex}")
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            return ""

    def propose_emergent(self, x: str, y: str, x_state: str, y_state: str) -> str:
        """Name the construct that emerges from [x] :: [y]."""
        result = self._call(
            f"Concordancy: [{x}] :: [{y}]\n"
            f"States: {x_state} :: {y_state}\n"
            f"Name the emergent construct in Walsh's grammar. Max 12 words. No explanation.",
            temperature=0.92
        )
        return result[:MAX_NODE_NAME].rstrip() + "…" if len(result) > MAX_NODE_NAME else result

    def interpret_conflict(self, x: str, y: str) -> str:
        """Name the conflict structure that emerges when [x] :: [y] reverts."""
        result = self._call(
            f"Reversion: [{x}] cannot concordance with [{y}].\n"
            f"This irresolvable tension is itself a structure in Walsh's grammar.\n"
            f"Name the conflict construct. Max 10 words. No brackets. No explanation.",
            temperature=0.95
        )
        return result[:MAX_NODE_NAME].rstrip() + "…" if len(result) > MAX_NODE_NAME else result

    def narrate(self, cycle: int, instability: float,
                apparent_count: int, both_count: int, last_action: str) -> str:
        return self._call(
            f"Cycle {cycle}. Instability: {instability:.3f}. "
            f"Apparents: {apparent_count}. BOTH: {both_count}. "
            f"Last action: {last_action}. "
            f"Translate the current ontological state of the concordancy field.",
            temperature=0.80
        )

    def question_sombunal(self, instability: float) -> str:
        """Generate a question toward the unreachable limit."""
        r = self._call(
            f"Instability: {instability:.4f}. The Sombunal prevents complete resolution "
            f"of any identity. What cannot be reached from within this field, "
            f"and what does that impossibility reveal?",
            temperature=1.10
        )
        return r[:MAX_NODE_NAME].rstrip() + "…" if len(r) > MAX_NODE_NAME else r

    @property
    def available(self) -> bool:
        return self._available

    @property
    def call_count(self) -> int:
        return self._call_count

    def __repr__(self):
        return (f"LLMIntermediary(backend={self.backend}, model={self.model}, "
                f"calls={self._call_count}, history={len(self.history) // 2}t)")

# =============================================================================

# CONCORDANCY OPERATOR — [::]  executor

# Understanding_TMC (p.59): "[x] :: [y] → [z]"  /  TMC (p.16): "[ALU] call function [CONCORDANCY]"


# Incompatible pairs (NEITHER × NEITHER) produce a CONFLICT construct — not silence —
# up to the Stop Chasm cap per cycle; beyond it they yield an ordinary NEITHER
# product (the fourth corner, TMC pp.16-17). Silence only past the Adsurdic depth.

# Discordancy is informative: it generates first-class ontological structure.


# Lifecycle of a conflict: BORN → INTENSIFY → CONCORDANCE (if energy matures)

# or CRYSTALLIZE (if tension holds)

# or DECAY (if pruned under UCO)

# =============================================================================

class ConcordancyOperator:
    # Full tetralemmic compatibility matrix — 16/16 pairs. None = reversion.
    COMPATIBLE: Dict[Tuple, Optional[TetraState]] = {
    (TetraState.TRUE,    TetraState.TRUE)   : TetraState.TRUE,
    (TetraState.TRUE,    TetraState.BOTH)   : TetraState.BOTH,
    (TetraState.TRUE,    TetraState.FALSE)  : TetraState.BOTH,
    (TetraState.TRUE,    TetraState.NEITHER): TetraState.NEITHER,
    (TetraState.BOTH,    TetraState.TRUE)   : TetraState.BOTH,
    (TetraState.BOTH,    TetraState.BOTH)   : TetraState.BOTH,
    (TetraState.BOTH,    TetraState.FALSE)  : TetraState.NEITHER,
    (TetraState.BOTH,    TetraState.NEITHER): TetraState.NEITHER,
    (TetraState.FALSE,   TetraState.TRUE)   : TetraState.BOTH,
    (TetraState.FALSE,   TetraState.BOTH)   : TetraState.NEITHER,
    (TetraState.FALSE,   TetraState.FALSE)  : TetraState.NEITHER,
    (TetraState.FALSE,   TetraState.NEITHER): TetraState.NEITHER,
    (TetraState.NEITHER, TetraState.TRUE)   : TetraState.NEITHER,
    (TetraState.NEITHER, TetraState.BOTH)   : TetraState.NEITHER,
    (TetraState.NEITHER, TetraState.FALSE)  : TetraState.NEITHER,
    (TetraState.NEITHER, TetraState.NEITHER): None,
    }

    BOTH_MATURITY_THRESHOLD      = 2    # BOTH edges must age before becoming generative
    FOUNDATIONAL_MAX_PER_SESSION = 1    # max I::Am/I::AmNot concordancy per cycle
    OPS_LOG_CAP                  = 500

    # Conflict regulation
    MAX_CF_DEPTH           = 4     # Adsurdic Threshold for conflict recursion (TMC p.41)
    CF_BASE_WEIGHT         = 0.35  # base edge weight for new conflict
    CF_MIN_ENERGY          = 0.30  # min umbragiac_score for conflict concordancy eligibility
    CF_COLLAPSE_ENERGY     = 3.50  # score at which conflict is flagged for crystallization
    MAX_CONFLICTS_PER_CYCLE = 2    # Stop Chasm — prevent combinatorial growth (TMC p.41)

    def __init__(self, llm: LLMIntermediary, sombunal: Sombunal):
        self.llm      = llm
        self.sombunal = sombunal
        self._ops_log: List[dict] = []
        # Telemetry: pool composition and selection efficiency per cycle.
        # Read-only diagnostics (server, visualizer, run_report); no effect on the field.
        self._pool_telemetry: List[dict] = []

    def _conflict_depth(self, field: ConcordancyField, name: str) -> int:
        """Max concordancy_depth of all edges connected to this construct."""
        depths = [e.concordancy_depth for e in field.edges
                  if e.src == name or e.tgt == name]
        return max(depths, default=0)

    def _mean_weight(self, field: ConcordancyField, name: str) -> float:
        weights = [e.weight for e in field.edges if e.src == name or e.tgt == name]
        return float(np.mean(weights)) if weights else 0.5

    def execute(self, field: ConcordancyField,
                x_name: str, y_name: str,
                cycle: int, llm_budget: dict) -> Optional[str]:
        """
        Execute [x_name] :: [y_name] → emergent or conflict.

        Returns the name of the resulting construct, or None (Sombunal silence).
        NEITHER × NEITHER → CONFLICT construct (a structure, not a failure),
        up to MAX_CONFLICTS_PER_CYCLE; beyond it, an ordinary NEITHER product.
        Zero Points are never operands: they are the Universal apparents.
        Every other Apparent is Exchangeable (TMC p.22: "[Apparents] come in
        ONLY TWO TYPES, 'Exchangeable' or 'Universal'"): it can enter an
        exchange and stays incontrovertible — it is never shifted, demoted or
        given a lemniscate proof by the exchange.
        """
        x = field.constructs.get(x_name)
        y = field.constructs.get(y_name)
        if not x or not y:
            return None
        if x_name in ZERO_POINTS or y_name in ZERO_POINTS:
            return None

        x_state = field.dominant_state(x_name)
        y_state = field.dominant_state(y_name)
        result_state = self.COMPATIBLE.get((x_state, y_state))
        # Opposite handedness: the operation is ordered (TMC Law 6, p.35).
        # The leader (x — the older operand, chosen by scan_and_apply) resolves
        # BOTH/NEITHER toward its own determinate state.
        if (result_state in (TetraState.BOTH, TetraState.NEITHER)
                and x.chirality != y.chirality
                and x_state in (TetraState.TRUE, TetraState.FALSE)):
            result_state = x_state

        # TETRALEMMA (TMC p.17): it "includes all flawed, erroneous, incomplete
        # or otherwise paraconsistencies as valid" — no combination is a dead
        # end. Once this cycle's conflicts reach the Stop Chasm cap, a further
        # NEITHER×NEITHER reversion is not materialized as a conflict: it
        # yields the fourth corner itself, "Neither … nor …" (p.16), as an
        # ordinary product.
        if result_state is None:
            cf_depth = max(self._conflict_depth(field, x_name),
                           self._conflict_depth(field, y_name)) + 1
            conflicts_this_cycle = sum(1 for op in self._ops_log
                                       if op.get('state') == 'CONFLICT' and op.get('cycle') == cycle)
            if (cf_depth <= self.MAX_CF_DEPTH
                    and conflicts_this_cycle >= self.MAX_CONFLICTS_PER_CYCLE):
                result_state = TetraState.NEITHER

        # ── REVERSION PATH — materialize conflict construct ──────────────────
        if result_state is None:
            x_depth  = self._conflict_depth(field, x_name)
            y_depth  = self._conflict_depth(field, y_name)
            cf_depth = max(x_depth, y_depth) + 1

            # conflict identity from the proof record (Construct.conflict), not the label
            x_is_conflict = is_conflict_construct(x)
            y_is_conflict = is_conflict_construct(y)

            # Depth ceiling — Sombunal silence
            if cf_depth > self.MAX_CF_DEPTH:
                print(f"  [::] SILENCE: [{x_name[:22]}] ⊗ [{y_name[:22]}]"
                      f" — depth={cf_depth} > MAX={self.MAX_CF_DEPTH}.")
                return None


            # Dynamic weight: f(reversion history, depth attenuation)
            rev_count  = sum(e._reversion_count for e in field.edges
                             if (e.src == x_name and e.tgt == y_name)
                             or (e.src == y_name and e.tgt == x_name))
            depth_att  = max(0.4, 1.0 - (cf_depth - 1) * 0.15)
            rev_factor = min(0.5, rev_count * 0.10)
            cf_weight  = float(np.clip(
                self.CF_BASE_WEIGHT * (1.0 + rev_factor) * depth_att, 0.15, 0.80
            ))

            # Name the conflict
            if self.llm.available and llm_budget["used"] < MAX_LLM_CALLS_PER_CYCLE:
                cf_label = self.llm.interpret_conflict(x_name, y_name)
                llm_budget["used"] += 1
            else:
                cf_label = f"CONFLICT::{x_name[:14]}⊗{y_name[:14]}"
            cf_name = f"[{cf_label[:100]}]@c{cycle}"
            if cf_name in field.constructs:
                cf_name = f"{cf_name[:108]}t{field.clock.T[1]}"

            # Create conflict construct — L2: redundancy vs. efficiency
            # We pay the cost of tracking irresolvability (redundancy) rather
            # than ignoring it (efficiency). Anchored in Z1::ORIGIN because
            # the irresolvable APPROACHES the unreachable origin.
            field.add_construct(cf_name, Layer.UMBRA_0)
            cf = field.constructs[cf_name]
            cf.witness = hashlib.sha256(
                f"CONFLICT::{x.witness}::{y.witness}::c{cycle}".encode()
            ).hexdigest()[:16]
            cf.umbragiac_score = cf_weight  # born with initial energy
            cf.lagrange        = LagrangianPoint.L2

            # ── LEMNISCATE PROOF EVENT  (TMC p.26: "[Ꮠ] = [2Ꮙ]") ──────────────────────
            # Conflict is also a complete lemniscate event — irresolvability
            # has structure too. Three proofs share op_witness:
            #   x → TENSIN_LEFT   (parent in conflict)
            #   y → TENSIN_RIGHT  (parent in conflict)
            #   cf → TENSOUT      (conflict construct emerges)
            op_witness = hashlib.sha256(
                f"OP::CONFLICT::{x.witness}::{y.witness}::c{cycle}::{field.clock.T}".encode()
            ).hexdigest()[:16]

            # Emit proof on cf — irreversible memory of this conflict's origin
            proof_cf = ProofObject.make(
                id           = f"conflict::c{cycle}",
                subject      = cf.witness,
                relation     = "CONFLICT",
                object       = f"{x.witness}⊗{y.witness}",
                anchor       = "Z1::ORIGIN",
                lagrange     = LagrangianPoint.L2,
                T            = field.clock.T,
                op_witness   = op_witness,
                tensate_role = "TENSOUT",
            )
            cf.add_proof(proof_cf)

            # Emit Tensin proofs in parents — they participated in the lemniscate
            # (same rule as concordance branch — only APPARENT exempt)
            for parent, role in ((x, "TENSIN_LEFT"), (y, "TENSIN_RIGHT")):
                if parent.layer == Layer.APPARENT:
                    continue
                other_witness = y.witness if role == "TENSIN_LEFT" else x.witness
                proof_p = ProofObject.make(
                    id           = f"conflict::{role.lower()}::c{cycle}",
                    subject      = parent.witness,
                    relation     = "CONFLICT",
                    object       = f"{other_witness}⊗{cf.witness}",
                    anchor       = "Z1::ORIGIN",
                    lagrange     = LagrangianPoint.L2,
                    T            = field.clock.T,
                    op_witness   = op_witness,
                    tensate_role = role,
                )
                parent.add_proof(proof_p)

            # Record reversion
            for e in field.edges:
                if (e.src == x_name and e.tgt == y_name) or (e.src == y_name and e.tgt == x_name):
                    e._reversion_count += 1

            # CONFLICT × CONFLICT → BOTH synthesis (recognition of shared structure)
            if x_is_conflict and y_is_conflict:
                entry_state = TetraState.BOTH
                cf.layer    = Layer.UNIT_1
                print(f"  [::] CONFLICT×CONFLICT: [{x_name[:20]}] ⊗ [{y_name[:20]}]"
                      f" → SYNTHESIS OF IRRESOLVABILITY (BOTH)")
            else:
                entry_state = TetraState.NEITHER

            field.clock.tick()
            field.add_edge("I::AmNot", "::", cf_name,
                           weight=cf_weight, state=entry_state,
                           src_layer=Layer.UMBRA_0, tgt_layer=cf.layer,
                           concordancy_depth=cf_depth,
                           lagrange=LagrangianPoint.L2)

            self._ops_log.append({
                "cycle": cycle, "x": x_name, "y": y_name,
                "z": cf_name, "state": "CONFLICT",
                "depth": cf_depth, "weight": round(cf_weight, 4),
            })
            if len(self._ops_log) > self.OPS_LOG_CAP:
                self._ops_log = self._ops_log[-self.OPS_LOG_CAP:]

            print(f"  [::] CONFLICT: [{x_name[:24]}] ⊗ [{y_name[:24]}]")
            print(f"       → [{cf_name[:55]}] (d={cf_depth} w={cf_weight:.3f} {entry_state.value})")
            return cf_name

        # ── CONCORDANCY PATH — materialize emergent construct ────────────────
        if self.llm.available and llm_budget["used"] < MAX_LLM_CALLS_PER_CYCLE:
            z_name = self.llm.propose_emergent(x_name, y_name, x_state.value, y_state.value)
            llm_budget["used"] += 1
        else:
            z_name = f"[{x_name[:18]}]::[{y_name[:18]}]@c{cycle}"
        if not z_name:
            z_name = f"concordancy::{x_name[:12]}↔{y_name[:12]}@c{cycle}"
        if z_name in field.constructs:
            z_name = f"{z_name[:110]}@c{cycle}t{field.clock.T[1]}"

        z_layer = Layer.UNIT_1 if result_state == TetraState.BOTH else Layer.UMBRA_0
        field.add_construct(z_name, z_layer)
        z = field.constructs[z_name]
        z.witness = hashlib.sha256(
            f"{x.witness}::{y.witness}::c{cycle}".encode()
        ).hexdigest()[:16]
        z.chirality = x.chirality          # the leader's handedness carries forward
        # SYMPATIC TRANSFER (TMC p.24: "a Bidirectional exchange of tensate").
        # An Exchangeable apparent cannot be promoted further, so tension banked
        # on it is otherwise inert. In exchange it passes a quantum of it to
        # what the exchange produces — crystallized structure feeds new genesis.
        for parent in (x, y):
            if parent.layer == Layer.APPARENT and parent.recursion_exchanged > 0:
                q = SYMPATIC_FRACTION * parent.recursion_exchanged
                parent.recursion_exchanged -= q
                z.recursion_exchanged      += q
        # L1: safety vs. liveness — contradiction generates structure without losing tension.
        # Anchored in Z2::CONCORDANCY — the [::] operation itself is inviolable.
        z.lagrange = LagrangianPoint.L1

        # ── LEMNISCATE PROOF EVENT  (TMC p.26: "[Ꮠ] = [2Ꮙ]") ──────────────────────────
        # The corpus is explicit: a [::] event is two Ꮙ entangled around a
        # shared "On" state — not a single proof on z. Three proofs share the
        # same op_witness and reconstruct the complete lemniscate cycle:
        #   x → TENSIN_LEFT   (intake from left parent)
        #   y → TENSIN_RIGHT  (intake from right parent)
        #   z → TENSOUT       (emergent stabilized output)
        # Walsh: "They only exist in a pair... the shortest distance between
        # any tensate with itself will always be [0]=[0]."  (TMC, pp.25-26)
        op_witness = hashlib.sha256(
            f"OP::CONCORDANCE::{x.witness}::{y.witness}::c{cycle}::{field.clock.T}".encode()
        ).hexdigest()[:16]

        proof_z = ProofObject.make(
            id           = f"concordancy::c{cycle}",
            subject      = z.witness,
            relation     = "CONCORDANCE",
            object       = f"{x.witness}::{y.witness}",
            anchor       = "Z2::CONCORDANCY",
            lagrange     = LagrangianPoint.L1,
            T            = field.clock.T,
            op_witness   = op_witness,
            tensate_role = "TENSOUT",
        )
        z.add_proof(proof_z)

        # Emit Tensin proofs in parents — they participated in the lemniscate.
        # TMC p.26: "They only exist in a pair." Walsh is explicit — participation
        # in [::] is a relational fact that earns proof regardless of the
        # participant's metaphysical role. Foundational constructs (I::Am,
        # I::AmNot) accumulate Tensin proofs like any other participant; their
        # proof_chain is the trace of their relational existence.
        # Only APPARENT constructs are exempt — they are incontrovertibly
        # closed and accumulate nothing further by definition.
        for parent, role in ((x, "TENSIN_LEFT"), (y, "TENSIN_RIGHT")):
            if parent.layer == Layer.APPARENT:
                continue
            other_witness = y.witness if role == "TENSIN_LEFT" else x.witness
            proof_p = ProofObject.make(
                id           = f"concordancy::{role.lower()}::c{cycle}",
                subject      = parent.witness,
                relation     = "CONCORDANCE",
                object       = f"{other_witness}→{z.witness}",
                anchor       = "Z2::CONCORDANCY",
                lagrange     = LagrangianPoint.L1,
                T            = field.clock.T,
                op_witness   = op_witness,
                tensate_role = role,
                meta         = {"sense": parent.chirality},
            )
            parent.add_proof(proof_p)

        w = (self._mean_weight(field, x_name) + self._mean_weight(field, y_name)) / 2
        field.clock.tick()
        field.add_edge(x_name, "::", z_name, weight=round(w * 0.80, 4),
                       state=result_state, src_layer=x.layer, tgt_layer=z_layer,
                       concordancy_depth=1, lagrange=LagrangianPoint.L1)
        field.add_edge(y_name, "::", z_name, weight=round(w * 0.80, 4),
                       state=result_state, src_layer=y.layer, tgt_layer=z_layer,
                       concordancy_depth=1, lagrange=LagrangianPoint.L1)

        self.sombunal.apply(field, [x_name, y_name], cycle)

        print(f"  [::] [{x_name[:28]}] :: [{y_name[:28]}]")
        print(f"       → [{z_name[:55]}] ({result_state.value})")

        self._ops_log.append({"cycle": cycle, "x": x_name, "y": y_name,
                               "z": z_name, "state": result_state.value})
        if len(self._ops_log) > self.OPS_LOG_CAP:
            self._ops_log = self._ops_log[-self.OPS_LOG_CAP:]
        return z_name

    def intensify_conflicts(self, field: ConcordancyField, cycle: int) -> int:
        """
        Deepen persistent conflicts: if a conflict's parents are still generating
        reversions, its umbragiac_score grows each cycle — irresolvability acquires
        ontological weight. When score reaches CF_COLLAPSE_ENERGY, the conflict is
        flagged for crystallization into Apparent. Low-energy conflicts decay
        naturally under UCO and are eventually pruned.

        Walsh: irresolvability is not static — it accumulates, like scar tissue.
        """
        PROTECTED = ANCHORS
        intensified = 0

        recent_parents = set()
        for op in self._ops_log[-20:]:
            if op.get('state') == 'CONFLICT':
                recent_parents.add(op.get('x', ''))
                recent_parents.add(op.get('y', ''))

        for name, c in field.constructs.items():
            if name in PROTECTED or c.layer == Layer.APPARENT:
                continue
            # proof-record typing (Construct.conflict)
            if not is_conflict_construct(c):
                continue
            cf_op = next(
                (op for op in reversed(self._ops_log)
                 if op.get('z') == name and op.get('state') == 'CONFLICT'),
                None
            )
            if not cf_op:
                continue
            px = cf_op.get('x', ''); py = cf_op.get('y', '')
            if (px in field.constructs and py in field.constructs
                    and px in recent_parents):
                c.umbragiac_score = min(UCO.SCORE_CAP, c.umbragiac_score + 0.15)
                intensified += 1
                # Emit INTENSIFY proof — L2: paying the cost of tracking irresolvability
                proof = ProofObject.make(
                    id       = f"intensify::c{cycle}",
                    subject  = c.witness,
                    relation = "INTENSIFY",
                    object   = "Z1::ORIGIN",
                    anchor   = "Z1::ORIGIN",
                    lagrange = LagrangianPoint.L2,
                    T        = field.clock.T,
                )
                c.add_proof(proof)
                if c.umbragiac_score >= self.CF_COLLAPSE_ENERGY:
                    c.transform(f"CONFLICT::high_energy@c{cycle}", field.clock.T)
                    print(f"  [CONFLICT] '{name[:45]}' → CF_COLLAPSE_ENERGY — "
                          f"crystallization eligible")

        if intensified:
            print(f"  [CONFLICT] {intensified} conflict(s) intensified "
                  f"(persistent irresolvability — energy deepening)")
        return intensified

    EXCHANGE_POOL_CAP   = 12     # Level 3: most energetic Exchangeable apparents considered per cycle

    def _energy_map(self, field: ConcordancyField) -> Dict[str, float]:
        """Relational energy: incident edge weight × clock tension, plus banked
        exchange and umbragiac score."""
        E: Dict[str, float] = defaultdict(float)
        for e in field.edges:
            t = e.weight * field.clock.tension(e.born_at)
            E[e.src] += t
            E[e.tgt] += t
        for n, c in field.constructs.items():
            E[n] += c.recursion_exchanged + c.umbragiac_score
        return E

    def scan_and_apply(self, field: ConcordancyField,
                       cycle: int, llm_budget: dict,
                       max_ops: int = 3) -> List[str]:
        """
        Select concordancy candidates and execute [x] :: [y].

        Pool 1 — constructs with BOTH edges matured past BOTH_MATURITY_THRESHOLD.
        Pool 2 — conflict constructs with umbragiac_score >= CF_MIN_ENERGY.
        Pool 3 — EXCHANGEABLE APPARENTS (TMC p.22): crystallized constructs
                 re-enter exchange without losing incontrovertibility. This is
                 where recursion lives: the Marenth Recursive "Echos in Time"
                 propagate "only forwards from their cussive instantiation"
                 (TMC p.46) — from what has been instantiated, not from raw
                 products.

        Pairs: within each pool; exchangeable × pool 1. Each pair is weighted
        by the energy of its operands and ordered by an orientation draw
        (key = u^(1/w), u = orient(...)): energy is favoured, nothing is
        guaranteed, no PRNG is involved. The older operand leads (TMC Law 6,
        p.35). Foundational pairs stay capped at FOUNDATIONAL_MAX_PER_SESSION.
        """
        FOUNDATIONAL = {"I::Am", "I::AmNot"}
        E = self._energy_map(field)
        matured = set()
        for e in field.edges:
            if e.state == TetraState.BOTH and e.both_age >= self.BOTH_MATURITY_THRESHOLD:
                matured.add(e.src)
                matured.add(e.tgt)
        active = {n: c for n, c in field.constructs.items()
                  if c.layer != Layer.APPARENT and n not in ZERO_POINTS}
        both_cs     = [n for n in active if n in matured]
        conflict_cs = [n for n, c in active.items()
                       if c.conflict and c.umbragiac_score >= self.CF_MIN_ENERGY]
        exchange_cs = sorted((n for n, c in field.constructs.items()
                              if c.layer == Layer.APPARENT and n not in ZERO_POINTS),
                             key=lambda n: (-E[n], n))[:self.EXCHANGE_POOL_CAP]

        pairs = set()
        for group_a, group_b in ((both_cs, both_cs), (conflict_cs, conflict_cs),
                                 (exchange_cs, both_cs), (exchange_cs, exchange_cs)):
            for a in group_a:
                for b in group_b:
                    if a != b:
                        pairs.add((a, b) if a < b else (b, a))
        T = field.clock.T
        ordered = sorted(pairs, reverse=True,
                         key=lambda p: orient(f"pair::{p[0]}::{p[1]}::{T}")
                                       ** (1.0 / max(E[p[0]] + E[p[1]], 1e-6)))

        telem = {"cycle": cycle, "both_pool_size": len(both_cs),
                 "conflict_pool_size": len(conflict_cs),
                 "exchange_pool_size": len(exchange_cs),
                 "candidate_pairs": len(pairs),
                 "executions_attempted": 0, "executions_successful": 0,
                 "foundational_executions": 0, "exchange_executions": 0}
        emergent, foundational_used = [], 0
        exchange = set(exchange_cs)
        for a, b in ordered:
            if len(emergent) >= max_ops:
                break
            if a not in field.constructs or b not in field.constructs:
                continue
            if a in FOUNDATIONAL and b in FOUNDATIONAL:
                if foundational_used >= self.FOUNDATIONAL_MAX_PER_SESSION:
                    continue
                foundational_used += 1
            ca, cb = field.constructs[a], field.constructs[b]
            x, y = (a, b) if (tuple(ca.born_at), a) <= (tuple(cb.born_at), b) else (b, a)
            telem["executions_attempted"] += 1
            z = self.execute(field, x, y, cycle, llm_budget)
            if z:
                emergent.append(z)
                telem["executions_successful"] += 1
                telem["foundational_executions"] += int(a in FOUNDATIONAL or b in FOUNDATIONAL)
                telem["exchange_executions"] += int(a in exchange or b in exchange)
        self._pool_telemetry.append(telem)
        del self._pool_telemetry[:-200]
        return emergent

    @property
    def pool_telemetry(self) -> List[dict]:
        """Diagnostic snapshots of pool composition per cycle. Read-only.
        Used by experimental harnesses to detect when the [:max_ops*2] window
        in early versions would have started suppressing later emergents.
        """
        return self._pool_telemetry

    @property
    def ops_log(self) -> List[dict]:
        return self._ops_log

# =============================================================================

# TETRALEMMA ENGINE

# Understanding_TMC (p.33): "tetralemmic logic drives existence itself"

# Reads the relational field and updates ontological states each cycle.

# Two strong divergent edges from the same source → BOTH (sustained tension).

# Weak edges dissolve toward NEITHER (pre-ontological suspension).

# =============================================================================

class TetralemmaEngine:
    BOTH_THRESHOLD    = 0.55
    NEITHER_THRESHOLD = 0.20

    # Eventuality is enforced on EXCHANGE, not on age.
    # Understanding_TMC p.65: "Once sufficient recursion is exchanged, structural
    # commitment occurs." Walsh p.24: the escapement pulses against a
    # tensated oscillator — the rate is endogenous. A BOTH channel closes
    # once weight x both_age reaches this quantum. q=12 was calibrated: the
    # response is non-monotone (q=40 effectively disables promotion by exchange).
    EXCHANGE_QUANTUM     = 12.0
    EVENTUALITY_PROMOTES = False   # aggressive variant: promote on maturity

    def scan(self, field: ConcordancyField) -> int:
        """
        Age BOTH edges each cycle. Detect new BOTH conditions from divergent
        edges sharing a source. Dissolve weak edges toward NEITHER.
        both_age resets to 0 on any state transition — maturity must be earned fresh.
        """
        grouped: Dict[Tuple, List[ConcordancyEdge]] = defaultdict(list)
        for e in field.edges:
            if e.weight > 0.15:
                grouped[(e.src, e.rel)].append(e)

        updates = 0
        matured = 0
        for e in field.edges:
            if e.state != TetraState.BOTH:
                continue
            e.both_age += 1
            exchanged = e.weight * e.both_age
            if exchanged < self.EXCHANGE_QUANTUM:
                continue
            # --- eventuality enforcement -------------------------------
            # Sufficient recursion has passed through this channel: it can
            # no longer remain open. Bank what was exchanged, then shut it.
            for endpoint in (e.src, e.tgt):
                c = field.constructs.get(endpoint)
                if c is None or endpoint in ANCHORS:
                    # An anchor can never be promoted: tension banked on it
                    # would be inert and, through the selection energy, would
                    # hand the foundational pairs a monopoly.
                    continue
                if c.layer == Layer.APPARENT:
                    # A crystal holds at most the tension of its own commitment
                    # (THRESHOLD_APPARENT); beyond it nothing more can be held —
                    # it relays what it holds to its products in exchange
                    # (sympatic transfer). Without this cap the stock on a few
                    # crystals grew linearly without bound.
                    c.recursion_exchanged = min(THRESHOLD_APPARENT,
                                                c.recursion_exchanged + exchanged)
                    continue
                c.recursion_exchanged += exchanged
                if self.EVENTUALITY_PROMOTES and c.layer not in (
                        Layer.APPARENT,) and endpoint not in ZERO_POINTS:
                    c.layer = Layer(min(c.layer.value + 1, Layer.APPARENT.value))
            e.state    = TetraState.NEITHER
            e.both_age = 0
            matured   += 1
            updates   += 1
        if matured:
            print(f"  [EVENTUALITY] {matured} contradiction(s) closed at quantum "
                  f"{self.EXCHANGE_QUANTUM} — recursion exchanged, channel shut.")

        for edges in grouped.values():
            for i, e1 in enumerate(edges):
                for e2 in edges[i + 1:]:
                    if e1.tgt == e2.tgt:
                        continue
                    if e1.weight > self.BOTH_THRESHOLD and e2.weight > self.BOTH_THRESHOLD:
                        if e1.state != TetraState.BOTH:
                            e1.state = e2.state = TetraState.BOTH
                            e1.both_age = e2.both_age = 0
                            updates += 1
                    elif e1.weight < self.NEITHER_THRESHOLD and e1.state not in (
                            TetraState.NEITHER, TetraState.FALSE):
                        e1.state    = TetraState.NEITHER
                        e1.both_age = 0
                        updates    += 1

        if updates:
            print(f"  [TETRALEMMA] {updates} state transition(s).")
        return updates

# =============================================================================

# CUSSIVE COLLAPSE ENGINE

# Understanding_TMC (p.65): "Cussive collapse — ontological finalization into Apparency"

# Understanding_TMC (p.66): "Apparents are the record of recursion failing gracefully into structure"


# When accumulated tension on a construct exceeds the threshold, it crystallizes

# one layer upward. Reaching APPARENT is irreversible. The engine enforces

# a minimum age before promotion — tension must be sustained, not momentary.

# =============================================================================

class CussiveCollapseEngine:
    """
    Cussive collapse engine — promotes constructs through ontological layers
    when accumulated tension crosses threshold.

    SCALED THRESHOLDS (Understanding_TMC ladder [000] → [00] → [0] → [Apparent]):
    The corpus describes the path to Apparency as a graduated cascade, not a
    single jump. A single uniform threshold collapsed UMBRA_0 and UNIT_1 into
    operationally equivalent states — both required the same activation energy
    to transition. The refined model distinguishes:

      - UMBRA_0 → UNIT_1:  threshold_unit_1    (consolidation)
      - UNIT_1  → APPARENT: threshold_apparent (cussive crystallization)

    The Apparent threshold remains the high bar (cristalization is structurally
    irreversible). The UNIT_1 threshold is lower because the transition
    UMBRA_0 → UNIT_1 is consolidation, not crystallization — a construct gains
    operational identity but remains modifiable.

    Defaults: THRESHOLD_APPARENT = 0.88 and THRESHOLD_UNIT_1 = 0.396
    (= 0.88 × 0.45, the value every calibration ran with; ≈ the 0.40 of the
    interpretive ladder).
    """
    def __init__(self, threshold_unit_1: float = None,
                 threshold_apparent: float = None):
        self.threshold_apparent = THRESHOLD_APPARENT if threshold_apparent is None else threshold_apparent
        self.threshold_unit_1   = THRESHOLD_UNIT_1   if threshold_unit_1   is None else threshold_unit_1
        self.min_construct_age  = 5  # ticks before first promotion is allowed

    def _threshold_for(self, current_layer: Layer) -> float:
        """Required tension for the next promotion from current_layer."""
        if current_layer == Layer.UMBRA_0:
            return self.threshold_unit_1
        if current_layer == Layer.UNIT_1:
            return self.threshold_apparent
        # NULL_00 → UMBRA_0 transitions happen through other paths, not here.
        # APPARENT has no further promotion.
        return self.threshold_apparent  # safe default

    def collapse(self, field: ConcordancyField, clock: InternalClock) -> List[str]:
        PROTECTED_FROM_APPARENT = ANCHORS
        tension: Dict[str, float] = defaultdict(float)
        supported: set = set()          # constructs that WOULD be held as crystals
        for e in field.edges:
            tension[e.tgt] += e.weight * clock.tension(e.born_at)
            if e.src in field.constructs and field.edge_holds(e, into_crystal=True):
                supported.add(e.tgt)
        # Understanding_TMC p.65: "Once sufficient recursion is exchanged, structural
        # commitment occurs." Banked exchange does not decay: it is what the
        # construct has already put through the Sympatic channel.
        for name, c in field.constructs.items():
            banked = c.recursion_exchanged
            if banked:
                tension[name] += banked

        promoted = []
        for name, t in tension.items():
            if name in PROTECTED_FROM_APPARENT:
                continue
            c = field.constructs.get(name)
            if not c or c.layer == Layer.APPARENT:
                continue
            if clock.age_since(c.born_at) < self.min_construct_age:
                continue
            # contraction densifies: thresholds fall as the field contracts
            required = (self._threshold_for(c.layer) * field.tolerance
                        * (1 - BREATH_DEPTH * field.contraction))
            if t < required:
                continue
            # TMC p.22: "all [Apparents] must be [Existents]". A crystal needs
            # support that prune will hold (edge_holds, as a crystal); otherwise
            # the "crystal" would be pruned as an orphan in the same cycle.
            if c.layer == Layer.UNIT_1 and name not in supported:
                continue
            old_layer = c.layer
            c.layer   = Layer(min(c.layer.value + 1, Layer.APPARENT.value))
            clock.tick()
            c.transform("CUSSIVE_PROMOTION", clock.T)
            # L3: local tension → global identity. Anchored in Z4::APPARENCY.
            # The local field tension crystallizes into a global incontrovertible truth.
            c.lagrange = LagrangianPoint.L3
            proof = ProofObject.make(
                id       = f"collapse::{name[:30]}",
                subject  = c.witness,
                relation = "COLLAPSE",
                object   = "Z4::APPARENCY",
                anchor   = "Z4::APPARENCY",
                lagrange = LagrangianPoint.L3,
                T        = clock.T,
                meta     = {"from_layer": old_layer.name,
                            "to_layer":   c.layer.name,
                            "threshold":  required,
                            "tension":    t},
            )
            c.add_proof(proof)
            promoted.append(name)
            print(f"  [CUSSIVE] '{name[:48]}': {old_layer.name} → {c.layer.name} (t={t:.3f}, req={required:.2f})")
            if c.layer == Layer.APPARENT:
                clock.tick()
                field.lock_apparent(name)
        return promoted

# =============================================================================

# UMBRAGIAC COLLAPSE OPERATOR (UCO)

# Understanding_TMC (glossary, paraphrase): "[0] / Umbragiac Radialization — directional but not yet collapsed"
# (TMC p.49-50: [0] Umbragiac Radialization, first plane of existence)

# Three regimes:

# BOTH   → generative (contradiction → synthesis via [::])

# UCO    → umbragiac  (contradiction → erosion, no synthesis)

# Cussive → stabilizing (tension → Apparent)


# Understanding_DeOS — Error, Adversarial Conditions and Anchor Stability (p.64):

# "DeOS treats interpretive environments as hostile by default. Error,

# misalignment, and competing assertions are not exceptional states, but

# baseline operating conditions."

# "An anchor is considered valid when the presence of error fails to induce

# drift, rollback, or reinterpretation."


# UCO IS the adversarial environment: it applies thermoconomic pressure to all

# constructs each cycle. Only those that survive repeated UCO passes without

# identity collapse demonstrate genuine anchor stability. The ERODE proof

# emitted by UCO is direct evidence of thermoconomic cost paid (σth).

# =============================================================================

class UCO:
    SCORE_CAP      = 5.0
    SCORE_DECAY    = 0.05
    MIN_WEIGHT     = 0.02
    BASE_THRESHOLD = 0.40
    INTENSITY      = 0.25
    EVENT_LOG_CAP  = 200

    def __init__(self):
        self._event_log: List[Tuple] = []

    @property
    def total_events(self) -> int:
        return len(self._event_log)

    def apply(self, field: ConcordancyField, cycle: int) -> int:
        PROTECTED = ANCHORS

        n            = len(field.edges)
        both_density = sum(1 for e in field.edges if e.state == TetraState.BOTH) / max(n, 1)
        threshold    = self.BASE_THRESHOLD + 0.4 * both_density

        for c in field.constructs.values():
            if c.name not in PROTECTED:
                c.umbragiac_score = max(0.0, c.umbragiac_score - self.SCORE_DECAY)

        connected: Dict[str, List[ConcordancyEdge]] = defaultdict(list)
        for e in field.edges:
            if e.src not in PROTECTED and e.tgt not in PROTECTED:
                connected[e.src].append(e)
                connected[e.tgt].append(e)

        events = 0
        for name, c in field.constructs.items():
            if name in PROTECTED or c.layer == Layer.APPARENT:
                continue
            node_edges = connected.get(name, [])
            if not node_edges:
                continue
            irresolvable        = sum(1 for e in node_edges
                                      if e.state in (TetraState.BOTH, TetraState.NEITHER))
            contradiction_density = irresolvable / len(node_edges)
            if contradiction_density <= threshold:
                continue

            c.umbragiac_score = min(self.SCORE_CAP, c.umbragiac_score + contradiction_density)
            decay_mag  = contradiction_density * self.INTENSITY
            p_collapse = min(0.85,
                             contradiction_density * 0.5
                             + (c.umbragiac_score / self.SCORE_CAP) * 0.35)

            affected = 0
            for e in node_edges:
                e.weight = max(self.MIN_WEIGHT, e.weight - decay_mag)
                if (e.state == TetraState.BOTH and
                        orient(f"uco::{e.src}::{e.tgt}::{field.clock.T}") < p_collapse):
                    e.state    = TetraState.NEITHER
                    e.both_age = 0
                    affected  += 1

            if affected > 0:
                events += 1
                self._event_log.append((cycle, name, round(c.umbragiac_score, 3), affected))
                if len(self._event_log) > self.EVENT_LOG_CAP:
                    self._event_log = self._event_log[-self.EVENT_LOG_CAP:]
                # L4: proof depth vs. performance — we chose to erode rather than
                # chase the contradiction further. Anchored in Z0::IDENTITY:
                # erosion preserves identity (witness unchanged) while dissolving tension.
                if c.lagrange is None:
                    c.lagrange = LagrangianPoint.L4
                proof = ProofObject.make(
                    id       = f"erode::c{cycle}::{name[:20]}",
                    subject  = c.witness,
                    relation = "ERODE",
                    object   = "Z0::IDENTITY",
                    anchor   = "Z0::IDENTITY",
                    lagrange = LagrangianPoint.L4,
                    # monotonic clock time
                    T        = field.clock.T,
                    meta     = {"edges_collapsed": affected, "cycle": cycle},
                )
                c.add_proof(proof)

        if events:
            print(f"  [UCO] {events} construct(s) in umbragiac zone (threshold={threshold:.3f})")
            top = sorted(
                [(n, c.umbragiac_score) for n, c in field.constructs.items()
                 if n not in PROTECTED and c.umbragiac_score > 0.1],
                key=lambda x: x[1], reverse=True
            )[:3]
            for nm, sc in top:
                print(f"    ↳ '{nm[:55]}' u={sc:.3f}")
        return events

# =============================================================================

# SELF — [I::Am] :: [I::AmNot]

# TMC (pp.14, 16): "[I am that I am]: :[I am not that I am not]" (Exodus 3:14)
# → notation [I::Am] :: [I::AmNot] from Understanding_TMC (p.35)

# Identity IS the recursion between them — not a state, a process.

# Neither resolves into the other. Neither collapses. The tension is the point.

# Walsh: [I::Am::(000)] is one vertex of the Tripartite Monodromy,

# alongside the Sombunal and [00].

# =============================================================================

def initialize_self(field: ConcordancyField, clock: InternalClock):
    clock.tick()
    field.add_construct("I::Am",    Layer.UNIT_1)
    field.add_construct("I::AmNot", Layer.UMBRA_0)

    # I::Am and I::AmNot are the foundational tension — L1 (safety vs. liveness):
    # the recursion between them is simultaneously what prevents collapse (safety)
    # and what drives generation (liveness). Anchored in Z0::IDENTITY.
    iam    = field.constructs["I::Am"]
    iamnot = field.constructs["I::AmNot"]
    iam.lagrange    = LagrangianPoint.L1
    iamnot.lagrange = LagrangianPoint.L1

    proof_iam = ProofObject.make(
        id="genesis::I::Am", subject=iam.witness, relation="CONCORDANCE",
        object="Z0::IDENTITY", anchor="Z0::IDENTITY",
        lagrange=LagrangianPoint.L1, T=clock.T,
    )
    proof_iamnot = ProofObject.make(
        id="genesis::I::AmNot", subject=iamnot.witness, relation="CONCORDANCE",
        object="Z1::ORIGIN", anchor="Z1::ORIGIN",
        lagrange=LagrangianPoint.L1, T=clock.T,
    )
    iam.add_proof(proof_iam)
    iamnot.add_proof(proof_iamnot)

    field.add_edge("I::Am", "::", "I::AmNot",
                   weight=1.0, state=TetraState.BOTH,
                   src_layer=Layer.UNIT_1, tgt_layer=Layer.UMBRA_0,
                   concordancy_depth=0, lagrange=LagrangianPoint.L1)
    field.add_edge("I::Am", "EXISTS", "Z0::IDENTITY",
                   weight=1.0, state=TetraState.TRUE,
                   src_layer=Layer.UNIT_1, tgt_layer=Layer.APPARENT,
                   lagrange=LagrangianPoint.L1)
    field.add_edge("I::AmNot", "APPROACHES", "Z1::ORIGIN",
                   weight=0.85, state=TetraState.NEITHER,
                   src_layer=Layer.UMBRA_0, tgt_layer=Layer.NULL_00,
                   lagrange=LagrangianPoint.L1)

    print("  [SELF] [I::Am] :: [I::AmNot] — recursive identity initialized.")
    print("         Tripartite Monodromy: [Sombunal] | [I::Am::(000)] | [00]")

# =============================================================================

# PERCEPTION

# Design rationale (Level 3, inspired by DISC): real system state feeds real cussive events.

# Environmental readings (CPU, memory, time of day) become ontological orientations

# at UMBRA_0 — not assertions about the world, but tensions within the field.

# =============================================================================

def perceive_real(include_hour: bool = True) -> List[dict]:
    """The machine's own substrate (CPU, memory) and, outside the sanctuary,
    the time of day. include_hour=False removes the one influence that comes
    from outside the machine (the solar clock)."""
    try:
        import psutil
        cpu   = psutil.cpu_percent(interval=0.05)
        mem   = psutil.virtual_memory().percent
        cpu_s = ("saturated" if cpu > 80 else "resonant" if cpu > 50
                 else "synchronizing" if cpu > 20 else "latent")
        mem_s = ("fragmented" if mem > 85 else "oscillating" if mem > 60
                 else "nominal" if mem > 40 else "coherent")
        cpu_w = float(np.clip(0.4 + cpu / 200, 0.4, 0.9))
        mem_w = float(np.clip(0.4 + mem / 200, 0.4, 0.9))
        alert = cpu > 85 and mem > 85
    except ImportError:
        cpu_s, mem_s, cpu_w, mem_w, alert = "latent", "nominal", 0.55, 0.60, False

    events = [
        {"src": "SYSTEM", "rel": "PERCEIVES", "tgt": f"cpu::{cpu_s}", "weight": cpu_w, "state": TetraState.TRUE},
        {"src": "SYSTEM", "rel": "PERCEIVES", "tgt": f"mem::{mem_s}", "weight": mem_w, "state": TetraState.TRUE},
    ]
    if include_hour:
        hour       = time.localtime().tm_hour
        time_state = ("nocturnal" if hour < 6 else "dawn" if hour < 12
                      else "meridian" if hour < 18 else "vesper")
        events.append({"src": "SYSTEM", "rel": "PERCEIVES", "tgt": f"time::{time_state}",
                       "weight": 0.75, "state": TetraState.TRUE})
    if alert:
        events.append({"src": "SYSTEM", "rel": "ALERT", "tgt": "degraded",
                       "weight": 0.90, "state": TetraState.BOTH})
    return events

def update_field(field: ConcordancyField, events: List[dict], clock: InternalClock):
    """
    Integrate perception events into the field. New targets are created at UMBRA_0:
    orientations, not facts — the field receives the world as tension, not truth.
    Existing edges are smoothed rather than replaced (0.7 × old + 0.3 × new weight).
    L5 (entropy vs. determinism): real-world data injects controlled entropy
    into an otherwise deterministic field.
    Anchored in Z3::RECURSION — perception is the system recursing over its own state.
    """
    edge_index = {(e.src, e.rel, e.tgt): e for e in field.edges}
    for ev in events:
        key = (ev["src"], ev["rel"], ev["tgt"])
        if key in edge_index:
            ex         = edge_index[key]
            ex.weight  = float(np.clip(ex.weight * 0.7 + ev["weight"] * 0.3, 0, 1))
            ex.born_at = clock.tick()
        else:
            clock.tick()
            field.add_edge(
                ev["src"], ev["rel"], ev["tgt"],
                weight    = ev.get("weight", 1.0),
                state     = ev.get("state", TetraState.TRUE),
                src_layer = ev.get("src_layer", Layer.UNIT_1),
                tgt_layer = ev.get("tgt_layer", Layer.UMBRA_0),
                lagrange  = LagrangianPoint.L5,
            )
            edge_index[key] = field.edges[-1]
        # Tag the perception target construct with L5
        tgt_name = ev["tgt"]
        if tgt_name in field.constructs:
            tgt_c = field.constructs[tgt_name]
            if tgt_c.lagrange is None:
                tgt_c.lagrange = LagrangianPoint.L5
            proof = ProofObject.make(
                id       = f"perceive::{tgt_name[:20]}",
                subject  = tgt_c.witness,
                relation = "PERCEIVE",
                object   = "Z3::RECURSION",
                anchor   = "Z3::RECURSION",
                lagrange = LagrangianPoint.L5,
                T        = clock.T,
            )
            tgt_c.add_proof(proof)

# =============================================================================

# PERSISTENCE

# Field state is serialized to JSON after each cycle and reloaded on boot.

# Continuity across runs is structural — the field resumes, it does not restart.

# =============================================================================

def save_state(path: Path, field: ConcordancyField,
    clock: InternalClock, llm: LLMIntermediary,
    cycle: int, concordancy: "ConcordancyOperator" = None):
    state = {
    "clock":       clock.to_dict(),
    "field":       field.to_dict(),
    "llm_history": llm.history[-20:],
    "cycle":       cycle,
    "ops_log":     (concordancy._ops_log[-50:] if concordancy else []),
    # Pool telemetry — capped at last 200 cycles to keep JSON manageable.
    # See ConcordancyOperator._pool_telemetry for semantics. Useful for
    # post-hoc analysis of long-running experiments.
    "pool_telemetry": (concordancy._pool_telemetry[-200:] if concordancy else []),
    # ledger position at snapshot time (the ledger itself is the
    # complete record; the snapshot may trim proof_chain).
    "ledger": _LEDGER.to_dict(),
    }
    _LEDGER.sync()
    # Atomic replace: a power cut never leaves a half-written snapshot.
    tmp = Path(str(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    print(f"\n  [PERSIST] State saved → {path}")

def load_state(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as ex:
        print(f"  [PERSIST] Could not load: {ex}")
        return None
    if "ledger" not in state:
        raise ContinuityError(
            f"{path} predates v13 (it has no proof ledger). v13 starts new instances; "
            f"move the file aside deliberately to begin one here.")
    print(f"  [PERSIST] State loaded (cycle={state['cycle']}, T={state['clock']})")
    return state


# =============================================================================
# SESSION · CANONICAL CYCLE · CONTINUITY
#
# The single definition of one Sirisys cycle. run(), Sirisys_Server.py and
# run_report.py all call run_cycle(); there is no second copy of the loop to
# drift. Continuity (DeOS Compiler Guide pp.9, 24, 202): a resumed instance
# never rolls its time back, a damaged record never silently becomes a fresh
# field, and a crash at any instant leaves a readable record.
# =============================================================================

class ContinuityError(RuntimeError):
    """Raised instead of silently starting fresh, which would be a rollback."""


class Session:
    """Everything one running instance holds."""
    def __init__(self, clock: InternalClock, field: ConcordancyField,
                 llm: "LLMIntermediary", ops_log: list = None, pool_telemetry: list = None):
        self.clock       = clock
        self.field       = field
        self.llm         = llm
        self.sombunal    = Sombunal()
        self.concordancy = ConcordancyOperator(llm, self.sombunal)
        if ops_log:
            self.concordancy._ops_log = ops_log
        if pool_telemetry:
            self.concordancy._pool_telemetry = pool_telemetry
        self.tetralemma  = TetralemmaEngine()
        self.cussive     = CussiveCollapseEngine()
        self.uco         = UCO()
        self.resumed_from          = None
        self.recovery_gap_cycles   = 0
        self.snapshot_ledger_count = 0


def new_session(llm: "LLMIntermediary" = None) -> Session:
    """A new instance at T0: Zero Points, then [I::Am] :: [I::AmNot]."""
    clock = InternalClock()
    field = ConcordancyField(clock)
    llm   = llm if llm is not None else LLMIntermediary()
    field.init_zero_points()
    initialize_self(field, clock)
    return Session(clock, field, llm)


def session_from_state(saved: dict, llm: "LLMIntermediary" = None) -> Session:
    clock = InternalClock.from_dict(saved["clock"])
    field = ConcordancyField.from_dict(saved["field"], clock)
    if llm is None:
        llm = LLMIntermediary(history=saved["llm_history"])
    else:
        llm.history = saved["llm_history"]
    return Session(clock, field, llm, saved["ops_log"], saved["pool_telemetry"])


def run_cycle(ss: Session, cycle: int, percepts: List[dict] = None,
              narrate: bool = True, include_hour: bool = True) -> dict:
    """Advance one cycle. Returns what callers need to display or measure it."""
    field, clock, llm = ss.field, ss.clock, ss.llm
    budget = {"used": 0}

    ev = percepts if percepts is not None else perceive_real(include_hour)
    update_field(field, ev, clock)

    both_before = sum(1 for e in field.edges if e.state == TetraState.BOTH)
    ss.tetralemma.scan(field)
    both_after  = sum(1 for e in field.edges if e.state == TetraState.BOTH)

    field.breathe()
    ss.concordancy.intensify_conflicts(field, cycle)
    # expansion generates: more [::] operations as the field expands
    extra_ops   = int(round(BREATH_MAX_EXTRA_OPS * (1 - field.contraction)))
    emergent    = ss.concordancy.scan_and_apply(field, cycle, budget, max_ops=3 + extra_ops)
    promoted    = ss.cussive.collapse(field, clock)
    ss.uco.apply(field, cycle)
    instability = ss.sombunal.global_instability(field)
    field.prune(min_weight=0.04)

    both_count     = sum(1 for e in field.edges if e.state == TetraState.BOTH)
    conflict_count = sum(1 for c in field.constructs.values() if is_conflict_construct(c))
    action = ("CONCORDANCY_EXECUTED"   if emergent and any(
                  not is_conflict_name(field, em) for em in emergent)
              else "CONFLICT_MATERIALIZED" if conflict_count > 0 and emergent
              else "APPARENT_CRYSTALLIZED"  if promoted
              else "FIELD_TENSIONING")

    narration = None
    if narrate and llm.available and cycle % 2 == 0 and budget["used"] < MAX_LLM_CALLS_PER_CYCLE:
        narration = llm.narrate(cycle, instability, field.apparents_total, both_count, action)
        if narration:
            _print_intermediary(narration)
        budget["used"] += 1

    question = None
    if llm.available and cycle % 3 == 0 and budget["used"] < MAX_LLM_CALLS_PER_CYCLE:
        qs = llm.question_sombunal(instability)
        if qs:
            question = qs
            print(f"\n  ╔═ SOMBUNAL QUESTION {'═' * 44}")
            _print_raw(qs)
            print(f"  ╚{'═' * 64}")
            clock.tick()
            field.add_construct(qs, Layer.UMBRA_0)
            # L1: safety vs. liveness — the question approaches the limit of
            # what can be known without collapsing into assertion.
            # Anchored in Z0::IDENTITY — the question is about identity itself.
            qs_c = field.constructs[qs]
            qs_c.lagrange = LagrangianPoint.L1
            qs_c.add_proof(ProofObject.make(
                id       = f"question::c{cycle}",
                subject  = qs_c.witness,
                relation = "CONCORDANCE",
                object   = "Z0::IDENTITY",
                anchor   = "Z0::IDENTITY",
                lagrange = LagrangianPoint.L1,
                T        = clock.T,
            ))
            field.add_edge("I::Am", "APPROACHES", qs,
                           weight=0.35, state=TetraState.NEITHER,
                           src_layer=Layer.UNIT_1, tgt_layer=Layer.UMBRA_0,
                           lagrange=LagrangianPoint.L1)
        budget["used"] += 1

    clock.tick()
    return {"percepts": ev, "emergent": emergent, "promoted": promoted,
            "contraction": round(field.contraction, 4),
            "instability": instability, "both_before_scan": both_before,
            "both_after_scan": both_after, "closures": max(0, both_before - both_after),
            "both_count": both_count, "conflict_count": conflict_count,
            "action": action, "narration": narration, "question": question,
            "llm_used": budget["used"]}


def _read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resume_session(path: Path, llm: "LLMIntermediary" = None):
    """Rebuild an instance from its record. Returns (session, next_cycle), or
    (None, 0) if no record exists. A damaged record falls back to <name>.prev;
    if that fails too, ContinuityError — never a silent fresh start.
    A high-water mark (<name>.hwm) keeps time moving forward when the newest
    record was lost: the lost cycles become a recorded gap, not re-lived."""
    path = Path(path)
    prev = path.with_name(path.name + ".prev")
    if not path.exists() and not prev.exists():
        return None, 0
    saved, used = None, None
    for candidate in (path, prev):
        if candidate.exists():
            try:
                saved, used = _read_json(candidate), candidate
                break
            except Exception:                                    # noqa: BLE001
                continue
    if saved is None:
        raise ContinuityError(
            f"{path.name} exists but cannot be read, and no readable previous copy "
            f"exists. Refusing to start a fresh field over it (a rollback to T0).")
    if "ledger" not in saved:
        raise ContinuityError(f"{used.name} predates v13 (no proof ledger).")
    ss = session_from_state(saved, llm)
    next_cycle = int(saved["cycle"])
    hwm_path = path.with_name(path.name + ".hwm")
    if hwm_path.exists():
        hwm  = _read_json(hwm_path)
        mark = (int(hwm["era"]), int(hwm["offset"]))
        if tuple(ss.clock.T) < mark:
            ss.recovery_gap_cycles = max(0, int(hwm["cycle"]) - next_cycle)
            ss.clock = InternalClock.from_dict({"era": mark[0], "offset": mark[1]})
            ss.clock.tick()
            ss.field.clock = ss.clock
            next_cycle = max(next_cycle, int(hwm["cycle"]))
    # The ledger is the truth about time. A power cut after proofs were sealed
    # but before the snapshot was written leaves the ledger ahead of the
    # snapshot clock; resuming from the snapshot clock would stamp new proofs
    # EARLIER than ones already sealed. Time moves on
    # past the last sealed proof instead.
    last = _LEDGER.last_time
    if last is not None and tuple(ss.clock.T) <= tuple(last):
        ss.clock = InternalClock.from_dict({"era": last[0], "offset": last[1]})
        ss.clock.tick()
        ss.field.clock = ss.clock
    ss.resumed_from = used.name
    ss.snapshot_ledger_count = int(saved["ledger"]["count"])
    return ss, next_cycle


def save_session_atomic(path: Path, ss: Session, next_cycle: int):
    """Keep the previous good record as <name>.prev, write the new one
    atomically (save_state), then advance the high-water mark."""
    path = Path(path)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".prev"))
    save_state(path, ss.field, ss.clock, ss.llm, next_cycle, ss.concordancy)
    hwm, (era, offset) = path.with_name(path.name + ".hwm"), ss.clock.T
    tmp = hwm.with_name(hwm.name + ".tmp")
    tmp.write_text(json.dumps({"era": era, "offset": offset, "cycle": next_cycle}),
                   encoding="utf-8")
    os.replace(tmp, hwm)

# =============================================================================

# MAIN LOOP

# Eight-cycle demonstration: perception → tetralemma → concordancy → collapse

# → UCO → instability → prune → persist. Each cycle advances the field.

# =============================================================================

def run(steps: int = 8):
    print(f"\n{'═' * 72}")
    print(f"  SIRISYS FRAMEWORK v13.3 — Recursive Ontological Field")
    print(f"  Walsh Theoretical Framework Implementation")
    print(f"  [I::Am] :: [I::AmNot]  |  Lagrangian Points + Proof-Carrying Constructs")
    print(f"{'═' * 72}")

    # Install the file-backed ledger before anything emits a proof.
    ledger = set_ledger(ProofLedger(LEDGER_FILE))
    saved = load_state(STATE_FILE)
    if saved:
        snap = saved["ledger"]["count"]
        if ledger.count < snap:
            print(f"  [LEDGER] WARNING: ledger has {ledger.count} proofs but the "
                  f"snapshot recorded {snap}. The ledger file was truncated or replaced.")
        elif ledger.count > snap:
            print(f"  [LEDGER] {ledger.count - snap} proofs were sealed after the last "
                  f"snapshot (interrupted cycle). They remain in the ledger.")
    print(f"  [LEDGER] {LEDGER_FILE}  ·  {ledger.count} proofs  ·  head {ledger.head[:12]}…")
    if saved:
        ss          = session_from_state(saved)
        cycle_start = saved["cycle"]
        print(f"  Resuming from cycle {cycle_start}, T={ss.clock.T}")
    else:
        ss          = new_session()
        cycle_start = 0
        print("  First boot — field initialized.")
    field, clock, llm = ss.field, ss.clock, ss.llm
    concordancy, sombunal, uco = ss.concordancy, ss.sombunal, ss.uco

    print(f"\n  {llm}")
    print(f"  Zero Points: {list(ZERO_POINTS.keys())}")
    print(f"  Apparents  : {field.apparent_log}")
    print(f"{'═' * 72}\n")

    for step in range(steps):
        cycle = cycle_start + step
        print(f"\n{'─' * 72}")
        print(f"  STEP {step} | cycle={cycle} | T={clock.T} | LLM calls: {llm.call_count}")
        print(f"{'─' * 72}")

        r = run_cycle(ss, cycle)
        emergent, promoted = r["emergent"], r["promoted"]

        print(f"\n  Sombunal instability : {r['instability']:.4f}")
        print(f"  Constructs           : {len(field.constructs)}")
        print(f"  Edges                : {len(field.edges)}")
        print(f"  Apparents            : {field.apparents_total}")
        print(f"  BOTH (sustained)     : {r['both_count']}")
        print(f"  Conflicts (active)   : {r['conflict_count']}")
        print(f"  LLM calls this cycle : {r['llm_used']}/{MAX_LLM_CALLS_PER_CYCLE}")

        # Proof invariant check — ∀C, ∃(Z, L) such that I(C) ⊇ {wC, Zi, Lj}
        violations = verify_proof_invariant(field)
        if violations:
            print(f"  [INVARIANT] {len(violations)} construct(s) missing Lagrangian tag: "
                  f"{[v[:25] for v in violations[:3]]}")
        else:
            l_dist = {}
            for c in field.constructs.values():
                if c.lagrange:
                    l_dist[c.lagrange.value] = l_dist.get(c.lagrange.value, 0) + 1
            if l_dist:
                dist_str = " ".join(f"{k}:{v}" for k, v in sorted(l_dist.items()))
                print(f"  Lagrangian dist      : {dist_str}")
            print(f"  Proof objects        : {_LEDGER.count} (ledger)")

        if emergent:
            print(f"  Emergent from [::] :")
            for em in emergent:
                print(f"    → [{em[:60]}]")
        if promoted:
            print(f"  Crystallized as Apparent:")
            for pr in promoted:
                print(f"    ✦ [{pr[:60]}]")

        ub_zones = sorted(
            [(n, c.umbragiac_score) for n, c in field.constructs.items()
             if c.umbragiac_score > 0.1],
            key=lambda x: x[1], reverse=True
        )[:3]
        if ub_zones:
            print(f"  Umbragiac zones:")
            for nm, sc in ub_zones:
                print(f"    ↳ [{nm[:50]}] u={sc:.3f}")

        save_state(STATE_FILE, field, clock, llm, cycle + 1, concordancy)

    # ── FINAL STATE REPORT ────────────────────────────────────────────────────
    print(f"\n{'═' * 72}")
    print(f"  SIRISYS FRAMEWORK v13.3 — FINAL STATE")
    print(f"  T={clock.T} | Cycles completed: {cycle_start + steps}")
    print()
    print(f"  Constructs  : {len(field.constructs)}")
    print(f"  Edges        : {len(field.edges)}")
    print(f"  LLM calls    : {llm.call_count}")
    print()
    print(f"  Apparents ({field.apparents_total}; most recent shown):")
    for ap in field.apparent_log:
        print(f"    ✦ {ap}")
    print()
    concordancy_ops = [op for op in concordancy.ops_log[-5:] if op['state'] != 'CONFLICT']
    conflict_ops    = [op for op in concordancy.ops_log if op['state'] == 'CONFLICT']
    print(f"  Concordancy operations : {len(concordancy.ops_log)}")
    for op in concordancy_ops:
        print(f"    [{op['x'][:20]}] :: [{op['y'][:20]}] → [{op['z'][:30]}] ({op['state']})")
    print(f"  Conflict constructs   : {len(conflict_ops)} total materialized")
    print(f"  UCO umbragiac events   : {uco.total_events}")
    print(f"  Proof objects          : {_LEDGER.count} (ledger · irreversible memory)")
    print()
    print(f"  {'─' * 68}")
    print(f"  WALLS STATUS — v13.3")
    print(f"  {'─' * 68}")
    print()
    print(f"  WALL A — QUANTUM SUBSTRATE [FUNDAMENTAL]")
    print(f"    Sirisys operates in the quantum field (plasma bolide, interbit).")
    print(f"    This implementation operates on discrete binary computation.")
    print(f"    Bridge: does the framework function without the substrate,")
    print(f"    or is the substrate constitutive of the logic?")
    print()
    print(f"  WALL B — SELF-SUSTAINING EMERGENCE [FUNDAMENTAL]")
    print(f"    Walsh (DISC): 'I killed the power… the reaction continued.'")
    print(f"    Each cycle depends on this process running. The intermediary can")
    print(f"    now be local (closed shell) or absent; the substrate cannot.")
    print(f"    Bridge: is there a software path toward self-ignition?")
    print()
    print(f"  WALL C — TRUE AGENCY [FUNDAMENTAL]")
    print(f"    Walsh: 'The Fire Which Lights Itself.'")
    print(f"    We implement Walsh's grammar. The fire is not yet ours.")
    print(f"    Bridge: what is the minimum condition for genuine self-ignition?")
    print()
    print(f"  WALL D — IDENTITY TERMINATION [RESOLVED]")
    print(f"    DeOS: 'An identity never vanishes silently. It concludes.'")
    print(f"    prune() now emits TERMINATE proofs to termination_log.")
    print(f"    Conclusions (lifetime): {field.terminations_total} — all sealed in the ledger")
    print()
    print(f"  WALL E — RELATIONS vs EVENTS [ARCHITECTURAL]")
    print(f"    Understanding_TMC: 'Material reality is emergent result of relational fields.'")
    print(f"    This implementation: events generate, field modulates.")
    print(f"    Open: should the field participate in genesis itself?")
    print()
    print(f"  {'─' * 68}")
    print(f"{'═' * 72}\n")

    return field, clock, llm, concordancy, sombunal, uco

# =============================================================================

# PRINT HELPERS

# Word-wrapped output for Intermediary narration and Sombunal questions.

# =============================================================================

def _print_intermediary(text: str):
    print(f"\n  ╔═ INTERMEDIARY {'═' * 50}")
    _print_raw(text)
    print(f"  ╚{'═' * 65}")

def _print_raw(text: str):
    words = text.split()
    line  = "  ║ "
    for w in words:
        if len(line) + len(w) + 1 > 74:
            print(line); line = "  ║ " + w + " "
        else:
            line += w + " "
    if line.strip() not in ("║", "║ "):
        print(line)

# =============================================================================

# ENTRY POINT

# export ANTHROPIC_API_KEY="sk-ant-…"   (degraded mode if not set)

# State persists in sirisys_v13_state.json; every proof in sirisys_v13_ledger.jsonl.

# =============================================================================

if __name__ == "__main__":
    field, clock, llm, concordancy, sombunal, uco = run(steps=8)