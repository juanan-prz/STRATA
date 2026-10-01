# STRATA

**S**IRISYS · **T**etralemma · **R**ecursive · **A**rchitecture · **T**opology · **A**nalysis

Real-time implementation and exploration of the SIRISYS recursive ontological system — a field of constructs that evolves cycle by cycle through concordancy operations, cussive collapse, and stratified emergence across four ontological layers.

The repository includes:

- **Engine** (`Sirisys_Framework_vX_Y.py`): the construct field — tetralemma, concordancy operator, cussive collapse, proof-carrying constructs, Lagrangian points. Only the newest version needs to be in the folder; see *Versions* below.
- **Loader and canonical cycle** (`sirisys_loader.py`): finds the newest engine automatically and defines the single cycle that every program runs, so the live view and the measurements always show the same system.
- **Live server** (`Sirisys_Server.py`): runs the engine and streams it to the browser over WebSocket. Two modes: *experiment* (a fresh instance every start) and *continuous* (one instance that lives across restarts without ever rolling its time back).
- **Live visualizer** (`Sirisys_Live_Visualizer.html`): force-directed topology with shapes by ontological category, toggleable filters, pool telemetry, cussive collapse animation and a live event log.
- **Static visualizer** (`Sirisys_Static_Visualizer_v7.html`): post-hoc inspection of saved states, with radial layout by layer and proof overlay.
- **Report runner** (`run_report.py`): runs a measured experiment and writes everything needed for analysis into a single file, `sirisys_report.json`.

-----

## Setup

### Requirements

- Python 3.10 or higher
- macOS, Linux, or Windows with WSL

### Installation

```bash
pip3 install -r requirements.txt
```

To let the system use Claude through the Anthropic API (naming emergents, interpreting conflicts, questioning the Sombunal):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Without a key everything still runs, in *degraded mode*: labels are generated synthetically and the Sombunal is never questioned. See *Degraded mode* below for what that changes.

A step-by-step guide for first-time users on a Mac is in `Guia_SIRISYS_Mac.pdf` (Spanish).

-----

## Quick start

### Watch the field live

From the repository folder:

```bash
python3 Sirisys_Server.py
```

Open `http://localhost:8000` in Safari or Chrome and click **Play**. When you are done, press `Ctrl+C` in the terminal. The final state is saved to `sirisys_v12_state.json`, which the static visualizer can open.

### Run the long-lived instance

```bash
python3 Sirisys_Server.py --mode continuous --play
```

The instance resumes where its record ends and starts cycling immediately, with no browser needed. Open `http://localhost:8000` at any time to watch it. See *Server modes* below.

### Run a measured experiment

```bash
python3 run_report.py --cycles 20 --seeds 1     # short smoke test
python3 run_report.py                           # full run: 150 cycles x 3 seeds
```

The runner checks that the engine carries every mechanism it measures, runs an arm with the model active and a degraded control arm, and writes `sirisys_report.json`. Use `--model <model-id>` to choose the Claude model; keep it fixed across runs you intend to compare.

For a full guide to the interface and the concepts, see `Sirisys_Live_Guia.md` (Spanish).

-----

## Server modes

| | experiment (default) | continuous |
|---|---|---|
| Start | always a **new** instance at T0 | **resumes** the living instance |
| Saved | on stop, to `sirisys_v12_state.json` | after **every cycle**, to `sirisys_living_state.json` |
| Crash | the run is lost | resumes from the last cycle |
| Reset | discards the session | **archives** the instance in `sirisys_archive/`, then begins a new one |
| Use | calibration, watching a run | the instance meant to live indefinitely |

The two modes write different files, so running an experiment can never overwrite the living instance.

Continuous mode follows the DeOS Compiler Guide: identity "persists across recursion, runtime, and error" (p. 9); time is "strictly non-reversible" and "even under failure, recovery must guarantee this ordering" (p. 24); "Nothing disappears" (p. 202). A new instance starting at T0 rolls back nobody's time; restarting an existing instance at T0 would. Concretely:

- Saves are crash-safe: written to a temporary file, the previous good copy kept as `.prev`, then swapped in atomically.
- A high-water mark (`.hwm`) records the furthest T ever reached. If the main record is ever lost and the previous copy is used, time is moved *past* that mark and the lost cycles are recorded as a gap, never re-lived.
- If no readable record exists, the server refuses to start rather than silently beginning again at T0.

-----

## System architecture

```
Your computer
├── Terminal: python3 Sirisys_Server.py [--mode continuous] [--play]
│   ├── sirisys_loader.py  →  newest Sirisys_Framework_vX_Y.py
│   ├── SIRISYS engine in a worker thread, one run_cycle() per cycle
│   ├── FastAPI + uvicorn on localhost:8000
│   └── WebSocket on /ws
└── Browser: http://localhost:8000
    └── Sirisys_Live_Visualizer.html
        └── WebSocket client → receives snapshots in real time
```

`run_cycle()` in `sirisys_loader.py` is a line-for-line mirror of the structural body of the engine's own `run()`, verified to produce identical fields for the same seed. The server and `run_report.py` both call it.

-----

## Fundamental concepts

SIRISYS operates on four ontological layers:

- **NULL_00**: anchored void
- **UMBRA_0**: pre-emergent
- **UNIT_1**: operative emergent
- **APPARENT**: crystallized, structurally irreversible

Relations between constructs can be in one of four tetra states: `TRUE`, `FALSE`, `BOTH`, `NEITHER`. Sustained contradictions (`BOTH`) drive emergence. They are load-bearing but not immortal: a `BOTH` channel closes once enough recursion has been exchanged through it, and what was exchanged is banked toward crystallization ("Once sufficient recursion is exchanged, structural commitment occurs", *Understanding: TMC* p. 65).

Every construct carries an irreversible proof chain. What a construct *is* — a conflict, a concordance emergent — is read from that chain, never from its name.

-----

## Versions

Engine files follow a strict naming convention, `Sirisys_Framework_vX_Y.py`. Every program loads the **highest** version present in the folder (compared numerically, so `v12_10` is newer than `v12_9`), and prints which one it loaded. A new version needs no edits anywhere else: drop it in the folder.

To reproduce a run with an older engine, pin it explicitly:

```bash
export SIRISYS_FRAMEWORK="Sirisys_Framework_v12_7.py"
```

-----

## Files

| File | Description |
|---|---|
| `Sirisys_Framework_vX_Y.py` | SIRISYS engine (newest version is loaded) |
| `sirisys_loader.py` | Version discovery, canonical cycle, continuity helpers |
| `Sirisys_Server.py` | FastAPI/WebSocket server, experiment and continuous modes |
| `Sirisys_Live_Visualizer.html` | Live visualizer |
| `Sirisys_Static_Visualizer_v7.html` | Static visualizer (post-hoc) |
| `run_report.py` | Measured experiment runner |
| `Sirisys_Live_Guia.md` | Complete user guide (Spanish) |
| `Guia_SIRISYS_Mac.pdf` | First-time setup guide for Mac (Spanish) |
| `requirements.txt` | Python dependencies |

Files the system creates while running:

| File | Written by |
|---|---|
| `sirisys_v12_state.json` | experiment-mode server on stop; also used by the engine's own `run()`, which resumes from it |
| `sirisys_living_state.json` (+ `.prev`, `.hwm`) | continuous-mode server, every cycle |
| `sirisys_archive/instance_*.json` | continuous-mode reset — archived instances |
| `sirisys_report.json` | `run_report.py` |

-----

## Degraded mode

Without an API key the engine runs the same structural code, with two differences that matter: emergent and conflict labels are synthetic and repetitive, and the Sombunal is never questioned — and those questions are the one channel through which an active model adds new constructs to the field. Steady-state behaviour depends strongly on how much novelty enters the field, so results obtained in degraded mode are a lower bound on novelty, not a stand-in for an active run.

-----

## Project status

Research project under active development. Changes since v12.1, each delivered as a separate, documented version:

| Version | Change |
|---|---|
| v12.1 (repaired) | Source repaired from iOS copy-paste corruption; whitespace and quotes only, verified content-identical |
| v12.2 | Conflict identity read from the proof chain instead of the construct name |
| v12.3 | `BOTH` edges resistant to pruning rather than immune; optional witness redundancy (`min_references`) |
| v12.4 | Eventuality enforcement: `BOTH` channels must close; exchanged recursion is banked toward crystallization |
| v12.5 | Banked exchange persisted across save/load |
| v12.6 | Closure triggered by an exchange quantum instead of a fixed age |
| v12.7 | A terminated name that reappears is declared as a reincarnation, never silently replaced |
| v12.8 | Calibrated `both_floor` default, so every caller runs the same configuration |
| v12.9 | Lifetime witness counts (`proofs_total`, `erode_total`) saved with every construct, so Vc is identical before and after a save/reload |

Known limitations, recorded rather than hidden:

- Parameters (`both_floor`, exchange quantum) were calibrated in degraded mode and are provisional until LLM-active runs are analysed.
- Lagrangian points are recorded on every construct and proof but do not yet govern any decision. The DeOS Compiler Guide (p. 78) defines them as equilibrium functions over the field, *Lᵢ = fᵢ(Z, C)*; implementing that is open work.
- Saved states keep the last 20 proofs and 50 lineage entries per construct and the last 100 terminations. Since v12.9 the *counts* of witnesses survive exactly, so anchoring weight (Vc) no longer changes across a restart; the older individual proofs themselves are still not kept. Keeping them needs the external archive described under Wall D.
