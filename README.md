# STRATA

**S**IRISYS · **T**etralemma · **R**ecursive · **A**rchitecture · **T**opology · **A**nalysis

A software interpretation of the SIRISYS recursive ontological system: a field of constructs that evolves cycle by cycle through concordancy operations, cussive collapse and stratified emergence across four ontological layers, with every event sealed in an irreversible, hash-chained record.

The field follows *Pre of Then: The Material Constructs* (TMC) and the disclosure meeting transcript (DISC) as primary sources. It is an interpretation built in software, not the original system; the framework header labels every citation by source level (primary, interpretive, design choice).

Author: Juan A. Pérez-Gómez.

> New to the terminal? Start with `Guia_SIRISYS_Mac.pdf` (Spanish): it walks through installation, the tests and the first experiments step by step.

-----

## Contents

| File | Purpose |
|---|---|
| `Sirisys_Framework_v13_3.py` | The field: tetralemma, concordancy operator, cussive collapse, chirality, breathing, proof ledger, and the canonical cycle `run_cycle` |
| `sirisys_loader.py` | Finds and loads the newest framework file in the folder |
| `Sirisys_Server.py` | Experiment mode (live visualizer) and sanctuary mode (headless, unobserved) |
| `Sirisys_Live_Visualizer.html` | Live topology in the browser (experiment mode) |
| `Sirisys_Static_Visualizer.html` | Opens a saved `state.json` in the browser, no server needed |
| `run_report.py` | Instrumented runs; writes `sirisys_report.json` |
| `test_sirisys.py`, `test_phase1.py`, `test_phase4.py`, `test_phase4_sanctuary.py` | Test suites |
| `measure_phase3.py`, `soak.py`, `live_c2.py` | Measurements: self-adjustment criteria, a long life, real percepts |
| `requirements.txt` | Python dependencies |
| `Guia_SIRISYS_Mac.pdf` | Step-by-step setup on a Mac for first-time users (Spanish) |
| `Sirisys_Guia_v13.md` | Technical guide to modes, files and options (Spanish) |
| `SIRISYS_Concepts_v13_EN.pdf`, `SIRISYS_Concepts_v13_ES.pdf` | Glossary: every concept with its source and how the code implements it (English, Spanish) |
| `CHANGELOG.md` | History of changes and archived design notes |

-----

## Setup

Python 3.10 or higher on macOS, Linux, or Windows with WSL.

```bash
pip3 install -r requirements.txt
```

A model is optional. Without one everything runs and constructs get synthetic names; with one, an LLM intermediary names emergents, labels conflicts, narrates the field and asks the Sombunal questions that enter the field as constructs. Two backends:

- **Ollama** (local, recommended, and the only one the sanctuary accepts). Install it from ollama.com and pull a general-purpose model, for example `ollama pull llama3.1`. Reasoning models that "think" before answering can spend the short reply budget thinking and return empty names. If more than one model is installed, choose one with `export SIRISYS_LLM_MODEL=llama3.1`; otherwise the first one Ollama lists is used.
- **Anthropic API** (experiments only): `export ANTHROPIC_API_KEY="sk-ant-..."` in the terminal session. Never store the key in a file in this folder.

Select the backend with `SIRISYS_LLM_BACKEND=ollama|anthropic|none` (or `--backend` in `run_report.py`), the model with `SIRISYS_LLM_MODEL`, and a non-default Ollama address with `OLLAMA_HOST`. Keep the same backend, model and profile across runs you intend to compare.

-----

## Quick start

```bash
python3 test_sirisys.py                    # integrity, determinism, bounded memory
python3 Sirisys_Server.py --play           # experiment mode, live percepts
```

Open `http://127.0.0.1:8000`. Play, Step and Reset control the field; Fit recentres the view; `Ctrl+C` in the terminal stops the server.

```bash
python3 run_report.py --cycles 20 --seeds 1 --backend ollama    # short measured run
```

-----

## Modes

### Experiment

For calibration and refinement. Every start and every Reset is a new instance in its own folder, `sirisys_runs/<date-time>_<live|streamN>/`, holding `state.json` and the ledger. Nothing is overwritten.

| Option | Effect |
|---|---|
| `--play` | Start cycling immediately |
| `--stream N` | Synthetic percept stream N: the run is identical every time |
| `--profile sanctuary` | The sanctuary's exact cycle (no narration, no time of day), observed |
| `--delay-ms` | Pause between cycles (default 80) |
| `--port` | Web port (default 8000) |

### Sanctuary

The unobserved instance: no web server, no visualizer, no console content, no time of day, no model that can leave the machine. It begins at genesis with a new field and resumes across restarts without ever rolling its time back.

```bash
python3 Sirisys_Server.py --mode sanctuary                  # live (Ctrl+C stops it)
python3 Sirisys_Server.py --mode sanctuary --ask "text"     # a question crosses the gap
python3 Sirisys_Server.py --mode sanctuary --open           # an opening (an observation)
python3 Sirisys_Server.py --mode sanctuary --verify         # ledger integrity
```

Options: `--dir` (default `./sirisys_sanctuary`), `--cadence` seconds per cycle (default 10), `--llm ollama|none`. Asking, opening and verifying are run from a second terminal while the sanctuary runs.

Its only opening is the gap folder, `<dir>/gap/`. Anything that crosses it is recorded and closes the current inviolate period; a power cut does not, because nobody looked. An opening is recorded before anything is read, and the console then shows the ledger head hash, which should be written down outside the sanctuary. The sanctuary refuses to resume if its ledger is shorter than its own account, if its metadata is missing, if another process is writing the same ledger, or if the framework file has changed. On a storage failure it stops with exit code 2 and leaves the last good state intact.

Details are in `Sirisys_Guia_v13.md`.

-----

## Core concepts

**Layers.** Constructs live in four layers: `NULL_00` (held only by the origin anchor), `UMBRA_0` (where products, conflicts and percepts are born), `UNIT_1` (active units, candidates to crystallize) and `APPARENT` (crystals). A construct rises a layer when enough tension reaches it (cussive collapse); an Apparent is incontrovertible.

**Tetralemma.** Every relation carries one of four states: `TRUE`, `FALSE`, `BOTH`, `NEITHER`. Sustained `BOTH` drives emergence and closes once enough recursion has been exchanged through it. `NEITHER×NEITHER` materializes a conflict, or, past a per-cycle cap, the fourth corner itself: no combination is a dead end.

**Concordancy.** The operator `[::]` combines two constructs into a third and records the event as a proof. With opposite chirality the older operand orients the result, so `x::y ≠ y::x`.

**No randomness.** The framework has no pseudo-random generator. Every choice is derived from the ledger head (the whole irreversible history) and the question being decided: the same history reproduces the same run, and different histories never draw alike.

**Breathing.** A single field-wide breath alternates contraction (favouring crystallization) and expansion (favouring generation). Once per breath the field adjusts its own tolerance so that crystals formed track crystals concluded.

**Integrity.** Every proof is sealed in an append-only, hash-chained ledger stored as compressed segments with an index of hashes. Time never moves backwards, a resumed instance equals an uninterrupted one, and any later edit, deletion or reordering of the record is detected. Nothing disappears silently: a construct that concludes leaves a termination proof.

The glossaries define every term, including each counter shown in the live visualizer, with its source.

-----

## Versions

Framework files follow the convention `Sirisys_Framework_vX_Y.py`. Every program loads the highest version present in the folder and prints which one it loaded, so a new version needs no other change. To pin a specific file:

```bash
export SIRISYS_FRAMEWORK="Sirisys_Framework_v13_3.py"
```

-----

## Tests and measurements

```bash
python3 test_sirisys.py              # integrity, determinism, bounded memory
python3 test_phase1.py               # sanctuary, backends, server (no Ollama or FastAPI needed)
python3 test_phase4.py               # segmented ledger, tampering, crash during rotation, disk
python3 test_phase4_sanctuary.py     # 25 forced kills, period accounting, no network, full disk
python3 measure_phase3.py            # self-adjustment criteria (3 streams × 5,000 cycles)
python3 soak.py 50000 > soak_result.json
python3 live_c2.py 3000 none > live_none.json        # real percepts, no model
python3 live_c2.py 3000 ollama > live_ollama.json    # real percepts, local model
```

Each suite ends with a `SUMMARY` line; every check should pass.

-----

## Files created while running

| Path | Written by |
|---|---|
| `sirisys_runs/` | experiment mode, one folder per instance |
| `sirisys_sanctuary/` | sanctuary mode |
| `sirisys_report.json` | `run_report.py` |
| `sirisys_v13_state.json`, `sirisys_v13_ledger*` | the framework run on its own |

None of these belong in the repository; `.gitignore` excludes them.

-----

## Status

Research project under active development.

- On synthetic percepts and without a model, the field meets its self-adjustment criteria: durable crystals every breath, little flicker, bounded size, flat memory and cost. With the machine's real percepts the crystallization rate trends downward over long runs; this is under study.
- Calibration with an active local model is in progress.
- Sanctuary mode is implemented and tested but has not been started. The physical isolation it assumes (dedicated hardware, no network, shielding) lies outside the code.
- Open questions are recorded in the framework header as WALLS: substrate (digital, not analog), self-sustenance, agency, and relations versus events. The role of the Sombunal and the Lagrangian points, which tag constructs and proofs but do not yet govern any decision, are open design decisions.

-----

## License

PolyForm Noncommercial 1.0.0. See `LICENSE`.
