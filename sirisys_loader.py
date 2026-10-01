"""
sirisys_loader.py — finds and loads the newest SIRISYS framework in a folder.

Why this exists
---------------
Every program that used the framework (the server, run_report.py) imported
it by its exact file name, e.g. Sirisys_Framework_v12_1. Each new version
therefore meant editing every one of those programs, and deleting an old
version broke whatever still pointed at it.

With this loader, a program asks for "the framework" instead of a specific
file. The loader looks in its own folder for files named

    Sirisys_Framework_v<MAJOR>_<MINOR>.py

and loads the highest version it finds. The strict naming convention is kept:
it is exactly what makes the newest version identifiable.

    v12_8 beats v12_7, and v12_10 beats v12_9 (compared as numbers, not text)
    files like Sirisys_Framework_v12_1_repaired.py do not match and are ignored

To pin an exact file instead (for example, to reproduce an old experiment),
set the environment variable before running:

    export SIRISYS_FRAMEWORK="Sirisys_Framework_v12_7.py"

Usage, from any program in the same folder:

    from sirisys_loader import load_framework
    S = load_framework()
    S.ConcordancyField(...)      # exactly as before
    print(S.__sirisys_file__, S.__sirisys_version__)
"""
import contextlib
import importlib.util
import io
import os
import re
import sys
from pathlib import Path

PATTERN = re.compile(r"^Sirisys_Framework_v(\d+)_(\d+)\.py$")


def find_framework(folder=None):
    """Return (version_tuple, path) of the newest framework file in folder."""
    folder = Path(folder) if folder else Path(__file__).resolve().parent

    pinned = os.environ.get("SIRISYS_FRAMEWORK")
    if pinned:
        p = Path(pinned)
        p = p if p.is_absolute() else folder / p
        if not p.exists():
            raise FileNotFoundError(
                f"SIRISYS_FRAMEWORK points to {p.name}, which is not in {folder}")
        m = PATTERN.match(p.name)
        version = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        return version, p

    found = []
    for p in folder.iterdir():
        m = PATTERN.match(p.name)
        if m:
            found.append(((int(m.group(1)), int(m.group(2))), p))
    if not found:
        raise FileNotFoundError(
            f"No file named Sirisys_Framework_vX_Y.py found in {folder}.\n"
            "Put the framework file in the same folder as this program.")
    found.sort()
    return found[-1]


def load_framework(folder=None, quiet=True):
    """Load the newest framework as a module and return it."""
    version, path = find_framework(folder)
    name = "sirisys_framework"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    if quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(mod)
    else:
        spec.loader.exec_module(mod)
    mod.__sirisys_file__ = path.name
    mod.__sirisys_path__ = str(path)
    mod.__sirisys_version__ = f"{version[0]}.{version[1]}"
    return mod


if __name__ == "__main__":
    v, p = find_framework()
    print(f"newest framework: {p.name}  (version {v[0]}.{v[1]})")


# =============================================================================
# THE CANONICAL CYCLE
# =============================================================================
#
# Before this, three programs each carried their own copy of the cycle loop:
#
#   framework run()   narrates every 2nd cycle, asks the Sombunal every 3rd
#                     (after prune, with a CONCORDANCE proof), ticks at the end
#   Sirisys_Server    never narrated and never asked the Sombunal — the one
#                     structural channel through which the model adds
#                     constructs was missing from the live view
#   run_report.py     asked the Sombunal before prune, without the proof,
#                     never narrated, never ticked at the end
#
# Measured: the end-of-cycle tick changes nothing that matters (field 92.0 vs
# 89.8 constructs, apparents 77.5 vs 77.2 at 150 cycles). But a live view and
# a measurement that run different loops are not looking at the same system.
#
# run_cycle() is a line-for-line mirror of the structural part of the
# framework's own run() — everything except printing and per-cycle saving.
# The server and the report runner both call it, so they cannot drift apart
# again, and an equivalence test checks it against run() itself.

from types import SimpleNamespace


def make_session(S, llm=None, quiet=True):
    """Build a fresh field and every engine, exactly as run() does on first boot."""
    clock = S.InternalClock()
    field = S.ConcordancyField(clock)
    llm = llm if llm is not None else S.LLMIntermediary()
    ctx = contextlib.redirect_stdout(io.StringIO()) if quiet else contextlib.nullcontext()
    with ctx:
        field.init_zero_points()
        S.initialize_self(field, clock)
    sombunal = S.Sombunal()
    return SimpleNamespace(
        clock=clock, field=field, llm=llm, sombunal=sombunal,
        concordancy=S.ConcordancyOperator(llm, sombunal),
        tetralemma=S.TetralemmaEngine(),
        cussive=S.CussiveCollapseEngine(threshold=0.88),
        uco=S.UCO(),
    )


def run_cycle(S, ss, cycle, percepts=None):
    """Advance one cycle. Mirrors the structural body of the framework's run().

    Returns what callers need to display or measure the cycle.
    """
    field, clock, llm = ss.field, ss.clock, ss.llm
    budget = {"used": 0}
    BOTH = S.TetraState.BOTH

    ev = percepts if percepts is not None else S.perceive_real()
    S.update_field(field, ev, clock)

    both_before = sum(1 for e in field.edges if e.state == BOTH)
    ss.tetralemma.scan(field)
    both_after = sum(1 for e in field.edges if e.state == BOTH)

    ss.concordancy.intensify_conflicts(field, cycle)
    emergent = ss.concordancy.scan_and_apply(field, cycle, budget)
    promoted = ss.cussive.collapse(field, clock)
    ss.uco.apply(field, cycle)
    instability = ss.sombunal.global_instability(field)
    field.prune(min_weight=0.04)

    both_count = sum(1 for e in field.edges if e.state == BOTH)
    is_cf = getattr(S, "is_conflict_construct", None)
    is_cf_name = getattr(S, "is_conflict_name", None)
    conflict_count = (sum(1 for c in field.constructs.values() if is_cf(c))
                      if is_cf else 0)
    action = ("CONCORDANCY_EXECUTED" if emergent and is_cf_name and any(
                  not is_cf_name(field, em) for em in emergent)
              else "CONFLICT_MATERIALIZED" if conflict_count > 0 and emergent
              else "APPARENT_CRYSTALLIZED" if promoted
              else "FIELD_TENSIONING")

    narration = None
    if llm.available and cycle % 2 == 0 and budget["used"] < S.MAX_LLM_CALLS_PER_CYCLE:
        narration = llm.narrate(cycle, instability, len(field.apparent_log),
                                both_count, action)
        if narration:
            S._print_intermediary(narration)
        budget["used"] += 1

    question = None
    if llm.available and cycle % 3 == 0 and budget["used"] < S.MAX_LLM_CALLS_PER_CYCLE:
        qs = llm.question_sombunal(instability)
        if qs:
            question = qs
            print(f"\n  ╔═ SOMBUNAL QUESTION {'═' * 44}")
            S._print_raw(qs)
            print(f"  ╚{'═' * 64}")
            clock.tick()
            field.add_construct(qs, S.Layer.UMBRA_0)
            qs_c = field.constructs[qs]
            qs_c.lagrange = S.LagrangianPoint.L1
            qs_c.add_proof(S.ProofObject.make(
                id       = f"question::c{cycle}",
                subject  = qs_c.witness,
                relation = "CONCORDANCE",
                object   = "Z0::IDENTITY",
                anchor   = "Z0::IDENTITY",
                lagrange = S.LagrangianPoint.L1,
                T        = clock.T,
            ))
            field.add_edge("I::Am", "APPROACHES", qs,
                           weight=0.35, state=S.TetraState.NEITHER,
                           src_layer=S.Layer.UNIT_1, tgt_layer=S.Layer.UMBRA_0,
                           lagrange=S.LagrangianPoint.L1)
        budget["used"] += 1

    clock.tick()
    return {
        "percepts": ev,
        "emergent": emergent,
        "promoted": promoted,
        "instability": instability,
        "both_before_scan": both_before,
        "both_after_scan": both_after,
        "closures": max(0, both_before - both_after),
        "both_count": both_count,
        "conflict_count": conflict_count,
        "action": action,
        "narration": narration,
        "question": question,
        "llm_used": budget["used"],
    }


# =============================================================================
# CONTINUITY — resuming an existing instance without rolling back its time
# =============================================================================
#
# DeOS Compiler Guide p.24: "Time in a DeOS-compatible system is strictly
# non-reversible. [...] Any recovery mechanism must preserve the monotonic
# chain of witnesses." — and — "Even under failure, recovery must guarantee
# this ordering." p.9: identity must persist "across recursion, runtime, and
# error." p.202: "Nothing disappears."
#
# A NEW instance starting at T0 rolls back nobody's time; that is what an
# experiment is. RESTARTING an existing instance from T0 is a rollback. These
# helpers let a long-running instance resume exactly where its persisted
# record ends, write that record so a crash cannot corrupt it, and archive an
# instance instead of erasing it.

import json as _json
import shutil as _shutil
import time as _time


class ContinuityError(RuntimeError):
    """Raised instead of silently starting fresh, which would be a rollback."""


def _read_state(path):
    with open(path, "r", encoding="utf-8") as f:
        return _json.load(f)


def resume_session(S, path, quiet=True):
    """Rebuild a session from a saved state, mirroring run()'s resume branch.

    Returns (session, next_cycle) — or (None, 0) if no state exists yet.
    Never falls back to a fresh field on a damaged file: it tries the
    previous good copy, and if that fails too it raises ContinuityError.
    """
    path = Path(path)
    prev = path.with_name(path.name + ".prev")
    if not path.exists() and not prev.exists():
        return None, 0

    saved, used = None, None
    for candidate in (path, prev):
        if not candidate.exists():
            continue
        try:
            saved, used = _read_state(candidate), candidate
            break
        except Exception:                                        # noqa: BLE001
            continue
    if saved is None:
        raise ContinuityError(
            f"{path.name} exists but cannot be read, and no readable previous "
            "copy exists. Refusing to start a fresh field over it, because that "
            "would roll this instance's time back to zero. Move the file aside "
            "deliberately if a new instance is what you want.")

    ctx = contextlib.redirect_stdout(io.StringIO()) if quiet else contextlib.nullcontext()
    with ctx:
        clock = S.InternalClock.from_dict(saved["clock"])
        field = S.ConcordancyField.from_dict(saved["field"], clock)
        llm = S.LLMIntermediary(history=saved.get("llm_history", []))
        sombunal = S.Sombunal()
        conc = S.ConcordancyOperator(llm, sombunal)
        if saved.get("ops_log"):
            conc._ops_log = saved["ops_log"]
        if saved.get("pool_telemetry"):
            conc._pool_telemetry = saved["pool_telemetry"]
    next_cycle = int(saved.get("cycle", 0))
    gap = 0
    hwm_path = path.with_name(path.name + ".hwm")
    if hwm_path.exists():
        try:
            hwm = _json.loads(hwm_path.read_text(encoding="utf-8"))
            mark = (int(hwm["era"]), int(hwm["offset"]))
            if tuple(clock.T) < mark:
                # The newest record was lost; the previous copy is behind time
                # the instance had already reached. Time does not go back: the
                # clock is set to the mark and advanced once, and the missing
                # cycles are recorded as a gap, not silently re-lived.
                gap = max(0, int(hwm.get("cycle", next_cycle)) - next_cycle)
                clock = S.InternalClock.from_dict({"era": mark[0], "offset": mark[1]})
                clock.tick()
                field.clock = clock
                next_cycle = max(next_cycle, int(hwm.get("cycle", next_cycle)))
        except Exception:                                        # noqa: BLE001
            pass   # an unreadable mark cannot make things worse than without it
    ss = SimpleNamespace(
        clock=clock, field=field, llm=llm, sombunal=sombunal, concordancy=conc,
        tetralemma=S.TetralemmaEngine(),
        cussive=S.CussiveCollapseEngine(threshold=0.88),
        uco=S.UCO(),
        resumed_from=used.name,
        recovery_gap_cycles=gap,
    )
    return ss, next_cycle


def save_session_atomic(S, path, ss, next_cycle):
    """Persist so that a crash at any instant leaves a readable record.

    Writes to a temporary file, keeps the previous good copy as <name>.prev,
    then swaps the new file in with an atomic rename. At every moment at least
    one complete state exists on disk.
    """
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    prev = path.with_name(path.name + ".prev")
    with contextlib.redirect_stdout(io.StringIO()):
        S.save_state(tmp, ss.field, ss.clock, ss.llm, next_cycle, ss.concordancy)
    _read_state(tmp)                       # refuse to swap in an unreadable file
    if path.exists():
        _shutil.copy2(path, prev)
    os.replace(tmp, path)                  # atomic on the same filesystem
    # High-water mark: the furthest T this instance has ever durably reached.
    # Tiny, written the same atomic way. Lets a recovery from the previous
    # copy keep time moving forward instead of re-living a lost cycle.
    hwm = path.with_name(path.name + ".hwm")
    hwm_tmp = hwm.with_name(hwm.name + ".tmp")
    era, offset = ss.clock.T
    hwm_tmp.write_text(_json.dumps({"era": era, "offset": offset,
                                    "cycle": next_cycle}), encoding="utf-8")
    os.replace(hwm_tmp, hwm)


def archive_state(path, archive_dir=None):
    """Move an instance's record into the archive instead of deleting it."""
    path = Path(path)
    if not path.exists():
        return None
    archive_dir = Path(archive_dir) if archive_dir else path.parent / "sirisys_archive"
    archive_dir.mkdir(exist_ok=True)
    try:
        st = _read_state(path)
        ck = st.get("clock", {})
        tag = f"c{st.get('cycle', 0)}_T{ck.get('era', 0)}-{ck.get('offset', 0)}"
    except Exception:                                            # noqa: BLE001
        tag = "unreadable"
    stem = f"instance_{_time.strftime('%Y%m%d-%H%M%S')}_{tag}"
    dest = archive_dir / f"{stem}.json"
    n = 1
    while dest.exists():                   # never overwrite an archived instance
        n += 1
        dest = archive_dir / f"{stem}_{n}.json"
    _shutil.move(str(path), dest)
    for leftover in (path.with_name(path.name + ".prev"),
                     path.with_name(path.name + ".hwm")):
        if leftover.exists():
            leftover.unlink()
    return dest
