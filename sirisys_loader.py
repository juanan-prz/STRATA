"""
sirisys_loader.py — finds and loads the newest SIRISYS framework in a folder.

A program asks for "the framework" instead of a specific file. The loader
looks in its own folder for files named

    Sirisys_Framework_v<MAJOR>_<MINOR>.py

and loads the highest version it finds. The strict naming convention is kept:
it is exactly what makes the newest version identifiable.

    v13_10 beats v13_9 (compared as numbers, not text); names that do not
    match exactly (e.g. Sirisys_Framework_v13_3_backup.py) are ignored

To pin an exact file (to reproduce an experiment, or to keep a long-lived
instance on the framework it was born with), set the environment variable:

    export SIRISYS_FRAMEWORK="Sirisys_Framework_v13_3.py"

Usage, from any program in the same folder:

    from sirisys_loader import load_framework
    S = load_framework()
    print(S.__sirisys_file__, S.__sirisys_version__)

The cycle (new_session, run_cycle) and continuity (resume_session,
save_session_atomic) live in the framework itself, so every program runs the
same loop by construction. This file only finds and loads the framework.
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
