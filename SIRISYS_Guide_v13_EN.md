# STRATA · SIRISYS v13.3 — Technical guide

[Español](SIRISYS_Guide_v13_ES.md)

The manual of STRATA: what every file does, every mode and option, and what each output contains. The [README](README.md) introduces the project, the glossary (`SIRISYS_Concepts_v13_EN.pdf`) defines the concepts and their sources, and the Mac guide (`SIRISYS_Mac_Guide_v13_EN.pdf`) takes a first-time user through installation step by step.

Some names carry the project's development phases: the self-adjustment criteria were adopted in Phase 3 (hence `measure_phase3.py` and "Phase 3" in the interface), and the test suites `test_phase1.py`, `test_phase2_guarantee.py` and `test_phase4.py` guard what each phase added.

## Contents

1. [Files](#1-files)
2. [Installation and models](#2-installation-and-models)
3. [Experiment mode](#3-experiment-mode)
4. [The inspector](#4-the-inspector)
5. [Reports](#5-reports)
6. [Measurements and topology](#6-measurements-and-topology)
7. [Tests](#7-tests)
8. [Continuity, versions and disk](#8-continuity-versions-and-disk)

-----

## 1. Files

Keep every file in one folder, with no subfolders: each program finds the others beside it.

| File | Purpose |
|---|---|
| `Sirisys_Framework_v13_3.py` | The field and its canonical cycle `run_cycle`, continuity and the proof ledger. Run on its own, a console demonstration (§8) |
| `sirisys_loader.py` | Finds and loads the newest framework file in the folder |
| `Sirisys_Server.py` | Experiment mode: runs the field and serves it to the live view |
| `Sirisys_Live_Visualizer.html` | The live view, served by the server |
| `Sirisys_Static_Visualizer.html` | The inspector of a saved instance; opens directly in the browser |
| `run_report.py` | Instrumented runs in three arms; writes `sirisys_report.json` |
| `sirisys_measures.py` | The self-adjustment criteria and the model-health watch, shared by the server and every measurement |
| `field_topology.py` | Read-only topology and depth of the field |
| `measure_phase3.py`, `soak.py`, `live_c2.py` | Measurements: the criteria on three streams, a long life, the machine's real percepts |
| `test_sirisys.py`, `test_phase1.py`, `test_phase2_guarantee.py`, `test_phase4.py`, `test_ontology.py` | The test suites |
| `sirisys_testkit.py` | What the suites share: the checks and their summary, fresh copies of the framework, a local stand-in for a model |
| `requirements.txt` | Python dependencies |
| `README.md`, `README_ES.md` | The front page (English, Spanish) |
| `SIRISYS_Guide_v13_EN.md`, `SIRISYS_Guide_v13_ES.md` | This guide (English, Spanish) |
| `SIRISYS_Mac_Guide_v13_EN.pdf`, `SIRISYS_Mac_Guide_v13_ES.pdf` | Step-by-step setup on a Mac (English, Spanish) |
| `SIRISYS_Concepts_v13_EN.pdf`, `SIRISYS_Concepts_v13_ES.pdf` | Technical glossary: every concept with its source and how the code implements it, and every counter the views show (English, Spanish) |
| `LICENSE` | PolyForm Noncommercial 1.0.0 |

-----

## 2. Installation and models

Python 3.10 or higher on macOS, Linux, or Windows with WSL.

```bash
pip3 install -r requirements.txt
```

This installs `numpy` and `psutil` (the field and its real percepts), `fastapi`, `uvicorn` and `websockets` (experiment mode) and `anthropic` (the API backend). On a Python managed by Homebrew, pip may refuse with `externally-managed-environment`; then use `pip3 install --break-system-packages -r requirements.txt`, or a virtual environment.

### What a model does

A model is optional: without one everything runs and constructs get synthetic names. With one, an intermediary names emergents, labels conflicts, narrates the field and asks the Sombunal questions. It reaches the field through two channels: the names it gives (they become construct keys, and so enter every orientation) and the questions (they enter the field as constructs). Every request carries a seed derived from the ledger head.

### Choosing it

| Variable | Values | Default |
|---|---|---|
| `SIRISYS_LLM_BACKEND` | `anthropic`, `ollama`, `none` | `anthropic` |
| `SIRISYS_LLM_MODEL` | a model name | Anthropic: `claude-sonnet-4-6`; Ollama: the first model it lists |
| `OLLAMA_HOST` | the Ollama address | `http://127.0.0.1:11434` |
| `ANTHROPIC_API_KEY` | the API key | none |

With the default backend and no key, the field runs without a model and says so at start (`degraded mode`). `run_report.py` also takes `--backend` and `--model`.

- **Ollama**, local: nothing leaves the machine while `OLLAMA_HOST` points to this computer. Install it from ollama.com and pull a general-purpose model, for example `ollama pull llama3.1`. Reasoning models that "think" before answering can spend the short reply budget thinking and return empty names; the model watch then stops the run.
- **Anthropic API**: the requests leave the machine. Set the key in the terminal session, `export ANTHROPIC_API_KEY="sk-ant-..."`; it lasts while that window stays open. Never store it in a file in this folder.

Keep the same backend, model and profile across runs you intend to compare.

### The model watch

A model that fails or answers empty would leave the field on synthetic names without notice: the run would look like a run with a model and not be one. `sirisys_measures.ModelHealth` prevents that.

- Before a run, `run_report.py` and `live_c2.py` make two real calls, and do not start if the answers are missing or empty.
- During the run they stop (exit code 3) when 3 calls in a row fail, or more than 10 % of the last 50 fail or come back empty. The output is still written, marked `aborted`, with the reason.
- The probe records which model exactly answered (with Ollama: digest, size, parameters and quantization), and the health report keeps the first answers of each kind.
- Experiment mode watches the same way: when the watch trips, the engine pauses once and the live view says why; Play goes on.

-----

## 3. Experiment mode

For calibration and refinement: the field cycles in the server, and the browser shows it.

```bash
python3 Sirisys_Server.py                       # this machine's percepts, paused: press Play
python3 Sirisys_Server.py --play                # start cycling at once
python3 Sirisys_Server.py --stream 0 --play     # synthetic stream 0: the same run every time
python3 Sirisys_Server.py --profile minimal     # no narration and no time-of-day percept
```

Then open `http://127.0.0.1:8000`. `Ctrl+C` in the terminal stops the server and saves the instance.

| Option | Effect |
|---|---|
| `--play` | Start cycling immediately |
| `--stream N` | Synthetic percept stream N instead of the machine's (`live`, the default) |
| `--profile minimal` | No narration and no time-of-day percept: the field perceives only the machine it runs on (`standard` by default) |
| `--delay-ms N` | Pause between cycles, in milliseconds (default 80; the live view changes it too) |
| `--host` | Address to listen on (default `127.0.0.1`: this machine only) |
| `--port` | Web port (default 8000) |

**No seed.** The framework has no pseudo-random generator: every choice derives from the ledger head and the question being decided. With `--stream N` and no model, two runs are identical; with `live`, the machine's own readings make each run unique.

**Run folders.** Every start and every Reset is a new instance in its own folder, `sirisys_runs/<date-time>_<live|streamN>[_minimal]/`. The ledger (`ledger.jsonl`, §8) is written proof by proof; `state.json` is written when the instance ends, at Reset or `Ctrl+C`. Nothing is overwritten.

### 3.1 The live view

**Connection.** The view connects over a WebSocket. Where that is blocked, it asks the server over HTTP and shows "connected (polling)"; every 30 s it tries the WebSocket again.

**Header.** The cycle; the internal time T (era, offset), which never moves backwards; the number of constructs; the ledger (proofs sealed · the head, the whole history in one hash); the criteria mark (✓ or ✗); the model with its watch; and the server mode, framework version and run folder.

**Controls.** Play/Pause, Step (one cycle; while playing it pauses first) and Reset, which asks for confirmation and starts a new instance (the current one stays in `sirisys_runs/`). The `delay` slider sets the pause between cycles, 0–500 ms.

**Keys.**

| Key | Action |
|---|---|
| Space | Play / Pause |
| S | Step one cycle |
| F | Fit the view to the constructs on show |
| V | Change the layout: relations ↔ strata |
| A | Quiet anchors |
| M | Show or hide the metabolism |

Space works right after a click on any button. A button reached with the keyboard (Tab) keeps Space and Enter for itself, as usual.

**Field State panel** (left).

- *Counters*: cycle, T, constructs, edges, apparents (every crystallization in the instance; the Zero Points are crystals from the start), concluded, conflicts, BOTH edges, closures in the cycle, reincarnations, top-3 energy, instability (the share of uncrystallized constructs unstable in some way) and how many cycles ago the last crystal formed.
- *Breathing*: completed breaths, contraction (0 at full expansion, 1 at full contraction) and the tolerance the field sets for itself once per breath.
- *Criteria*: see below.
- *Modes*, *Layers*, *Lagrangian*: the population by existence mode, by layer and by Lagrangian tag. The tags do not yet govern any decision.
- *Filters*: hide or show constructs by layer and edges by tetralemmic state.
- *Pool telemetry*: the candidates for `[::]` this cycle (pools of matured BOTH, energetic conflicts and exchangeable crystals), the operations that gave a product of those tried, the foundational and exchange products, and a chart of the last 200 cycles.

The glossary (section VIII) defines every counter.

**Event Log** (right). Products of `[::]`, cussive collapses, conclusions, narration, Sombunal questions and model notices. A click on a kind's chip hides or shows it; the latest 150 entries of each kind are kept.

**Pointing at a construct** shows its kind, layer, witness, energy, umbragiac score, banked exchange, Vc, existence mode, chirality, what it crystallized as, Lagrangian tag, proofs and the T it was born at.

### 3.2 How the field is drawn

The live view and the inspector draw the field alike, and the legend keys all of it.

- **Layouts.** *relations*: placed by their relations. *strata*: the Zero Points at the centre, then the anchors, NULL_00, UMBRA_0, UNIT_1 and APPARENT outwards, so that a construct that rises a layer moves out.
- **Layers** on one warm ramp from shadow (NULL_00) to light (APPARENT).
- **Shapes.** A construct is a dot in the colour of its layer; an anchor (I::Am, I::AmNot, SYSTEM), a diamond; a crystal the field formed, an open hexagon, so that the active strata stand out; a Zero Point, a star; a conflict, a ringed dot. One ring is drawn where a construct rises to UNIT_1, two where it crystallizes.
- **Edges** in the colour of their tetralemmic state, told apart with any colour vision: TRUE blue, FALSE orchid and dashed, BOTH vermilion and thicker, NEITHER grey and fainter, so that a thin blue line stands out beside it. An edge into a crystal, BOTH aside, is drawn with a faint halo, as crystal support: it ages on breaths, not on cycles.
- **A BOTH channel** is drawn faint, with what it has exchanged (weight × age) brighter from its middle outwards: whole when it closes at the exchange quantum.
- **Direction.** From zoom ×2 each edge shows its direction.
- **Existence modes** are written with their signs, [Ω] and [Ꮠ].
- **Quiet anchors** (A) makes the anchors' relations, often most of the edges, faint, so that the rest of the structure shows.
- The interface's own accent colour marks nothing of the field.

### 3.3 Metabolism

Under the field, breath by breath: the constructs born (among them those that concluded within their cycle and so never reached the screen), those that concluded, the rises and the crystallizations with the crystals that concluded, and the population by layer. Born minus concluded is the change in the population, exactly, every cycle.

The server keeps this history for the whole instance (`GET /api/history`; past 2,048 records the oldest are merged in pairs), so a viewer that opens late, or missed cycles another viewer read, still sees all of it.

### 3.4 Criteria

The live view judges the instance by the self-adjustment criteria, measured as `run_report.py` measures a run (§5). Every 200 cycles the server reads them; the panel gives each value with its threshold, and the verdict once 1000 cycles allow one. Measuring changes nothing in the field; its record grows with the instance, some 100 bytes a cycle.

### 3.5 Without a browser

The server can be left cycling with no browser open: it keeps only the latest 200 snapshots for the next viewer. Each snapshot is delivered once, to whichever client reads it first, so the view is meant for one viewer at a time.

### 3.6 Interface

What the live view uses, also described at the top of `Sirisys_Server.py`:

| Route | Use |
|---|---|
| `GET /` | The live view |
| `GET /api/status` | The instance: cycle, stream, run folder, ledger, model, criteria |
| `GET /api/snapshot` | The snapshots not yet delivered, as a list |
| `GET /api/history` | The metabolism, breath by breath |
| `POST /api/control/<action>` | `play`, `pause`, `step`, `reset` with `{"stream": "live" \| N}`, `speed` with `{"cycle_delay_ms": N}` |
| `WS /ws` | The status first, then each snapshot as it is made; `{"action": ...}` messages are answered with an ack |

-----

## 4. The inspector

`Sirisys_Static_Visualizer.html` opens directly in the browser: no server and no connection, and nothing is sent anywhere. It shows one moment of an instance in depth.

**Opening.** *Open state.json…* (or O), or drop the files anywhere on the page. A run folder's `state.json` is the usual file; the framework's own `sirisys_v13_state.json` (§8) opens too.

**One file.** Select a construct, on the canvas or with the search box (*find a construct…*; Enter takes the first name that contains the text), to examine its proofs, its genesis (its operands, drawn on the canvas) and its relations. Values the framework derives at run time and does not store (existence mode, Vc, selection energy, dominant state, instability) are computed exactly as the framework computes them.

**Several files of one instance** make a timeline: a slider, ◀ ▶ (or ← →) and Play, about one state per second. Stepping forward, a ring marks each construct the previous state did not hold, and *Since the previous file* gives the cycles, born, concluded, crystallized and the population, from the two files' own totals. Files of different runs are shown, with a warning and no counts between them.

In experiment mode an instance writes one `state.json`, when it ends. For a timeline, copy the state as it grows; for example, with the console demonstration, which resumes the same instance on every run:

```bash
python3 Sirisys_Framework_v13_3.py && cp sirisys_v13_state.json state_08.json
python3 Sirisys_Framework_v13_3.py && cp sirisys_v13_state.json state_16.json
```

**Keys.**

| Key | Action |
|---|---|
| O | Open files |
| ← → | Previous / next state of the timeline |
| F | Fit the view |
| V | Change the layout: relations ↔ strata |
| P | Ring the constructs whose saved proofs carry the relation chosen in its list (a dashed ring; the selection's is solid) |
| A | Quiet anchors |
| Esc | Clear the selection |

-----

## 5. Reports

`run_report.py` makes instrumented runs on the same percept streams and writes one report.

```bash
python3 run_report.py --cycles 20 --seeds 1 --backend ollama --profile minimal     # smoke test
python3 run_report.py --backend ollama --profile minimal --cycles 1000 --seeds 3   # the experiment
python3 run_report.py --backend ollama --profile minimal --cycles 1000 --determinism
python3 run_report.py --backend none                                               # the control alone
```

| Option | Effect |
|---|---|
| `--cycles N` | Cycles per run (default 1000, the least the criteria need) |
| `--seeds N` | Synthetic streams 0 … N−1 (default 3) |
| `--backend`, `--model` | The model (§2) |
| `--profile minimal` | No narration and no time-of-day percept |
| `--percepts live` | The machine's real percepts instead of the synthetic streams |
| `--skip-questions-arm` | Leave out the arm in which the model only asks the questions |
| `--skip-degraded` | Leave out the control |
| `--determinism` | See below; writes `sirisys_determinism.json` instead |

**The three arms**, on the same streams:

- `llm`: the model, through both channels;
- `llm_questions`: the model asking only the Sombunal questions, while the names stay the control's own, so that the two channels can be told apart;
- `degraded`: the control, without a model.

Without a model only the control runs, with a warning; when `--backend ollama` or `anthropic` is asked for and the model is not available, nothing runs (exit code 3). Withholding the questions as well gives the control bit for bit, which `test_phase1.py` checks.

**The criteria.** Each run is judged by the self-adjustment criteria (`sirisys_measures.LifeCriteria`, the same code as `measure_phase3.py`, `live_c2.py` and the live view):

- durable crystals (a life of at least one breath) in every 1000-cycle window;
- flicker, crystals that conclude within one breath, ≤ 5 %;
- no growth trend: constructs trend ≤ 1.2;
- flat cost of the cycle itself, model time excluded: late ≤ 1.5 × early + 0.5 ms;
- bounded top-3 energy: trend ≤ 1.2.

**Determinism.** The framework has no randomness, but a model runtime may have some even though every request carries a seed derived from the history. `--determinism` runs the model arm on stream 0 twice and says whether both runs sealed the same ledger and, if not, the cycle at which they parted, with an example of different answers. It needs the synthetic percepts and leaves `sirisys_report.json` alone. Every report also prints the ledger head of each run.

**What the report holds.**

- `config`: framework file, version and the first 16 characters of its SHA-256, the integrity checks, the constants the measurements depend on, cycles, streams, backend, model and its probe, profile, percepts, platform and Python version.
- `acceptance_criteria`: the criteria in words.
- `arms`: for each arm a summary over its runs, and each run in full: the criteria and their verdict, the ledger head (and after every cycle), a trace of every cycle, the topology (§6), what was perceived, lifespans, the crystals and a sample of the names born, the pool telemetry, the model's health and any errors.
- `aborted`, `determinism` (with `--determinism`) and `console`, everything the run printed.

**Exit codes.** 0 the report is written; 1 the framework lacks a mechanism the report measures; 3 a model was asked for and is missing or does not answer, or it stopped answering during the run (the report is then marked `aborted`).

-----

## 6. Measurements and topology

Run them from the project folder. None uses a model unless asked.

| Command | What it measures | Output |
|---|---|---|
| `measure_phase3.py [cycles] [framework file]` | The criteria on synthetic streams 0, 1 and 2 (default 5,000 cycles each) | `phase3_measurements.json`, and PASS or FAIL per stream on screen |
| `soak.py [cycles] [stream]` | One long life on synthetic percepts (default 50,000 cycles, stream 0): memory, cost, non-repetition, durable crystallization | JSON on standard output |
| `live_c2.py [cycles] [none\|ollama\|anthropic] [standard\|minimal]` | The machine's real percepts over a long life (default 3,000 cycles, no model, standard profile) | JSON on standard output; messages for the person running it on the terminal |

```bash
python3 measure_phase3.py                                   # about a minute
python3 soak.py 50000 > soak_result.json                    # about 3 minutes
python3 live_c2.py 10000 none minimal > live_none.json      # real percepts, no model (about 10 minutes)
python3 live_c2.py 3000 ollama minimal > live_ollama.json   # real percepts, the local model
```

`live_c2.py` records the criteria and their verdict, the topology, what the field perceived (counts per 1000 cycles and the whole sequence, one entry per cycle) and the Sombunal questions that entered the field. With a model it probes and watches it as `run_report.py` does; when the model fails, it stops with exit code 3, the JSON still written and marked `aborted`. Real percepts read the machine: leave it idle during a run whose results you intend to compare.

**Topology.** `run_report.py` and `live_c2.py` write a `topology_trace`: twice per breath, at expansion and at contraction, the shape of the field. Zero Points are left out, and each sample carries its cycle, breath, contraction and tolerance.

- weak components and directed cycles;
- reciprocity and clustering;
- the most connected construct;
- edges by tetralemmic state and by layer pair;
- how much of the BOTH lies in the largest component;
- the conflict depth of each conflict, which the field caps at the Adsurdic threshold;
- the genealogical depth by layer: how many `[::]` generations separate each construct from what the field did not produce itself (percepts, anchors, questions).

The measurement only reads the field: the ledger head is identical with and without it, which `test_phase2_guarantee.py` checks.

-----

## 7. Tests

No API key, no Ollama and no network: where a model is needed, a local stand-in answers. Each suite ends with a `SUMMARY` line, and every check should pass. Run them after any change.

| Suite | What it guards |
|---|---|
| `test_sirisys.py` | The record and the life of one instance: determinism without a PRNG, time that never goes back, a complete and tamper-evident ledger, resume, torn writes, a single writer, bounded memory, flat cost, and a resumed instance that equals an uninterrupted one |
| `test_phase1.py` | Everything around the field: the experiment engine, the model backends, the profiles, the web layer, the model watch, `run_report.py` and `live_c2.py`, and the names and constants the views share with the framework |
| `test_phase2_guarantee.py` | Measuring never changes what is measured, with and without a model; the genealogical depth |
| `test_phase4.py` | The segmented ledger: tampering across segments, power cuts during a rotation, disk use |
| `test_ontology.py` | What the field must be, cycle by cycle (below) |

`test_ontology.py` checks, from the primary source, that:

- Zero Points are never operands;
- the older operand leads and hands its chirality on;
- a crystal is never demoted or altered;
- nothing leaves the field without a termination proof;
- no crystal concludes in the cycle it forms;
- conflicts respect the Stop Chasm and the Adsurdic depth (TMC p.41);
- the anchors never conclude;
- the tolerance stays between its floor and 1;
- with a model in the loop, every request carries a seed oriented by the history, and two identical runs seal the same ledger.

One case is known and allowed only during the first breath: a new crystal whose BOTH support is eroded by UCO in the same cycle.

-----

## 8. Continuity, versions and disk

**Continuity.** A resumed instance equals an uninterrupted one, and time never moves backwards: after a cut it moves on past the last sealed proof. An instance never restarts silently over a damaged record.

**The ledger.** Every proof is sealed in an append-only, hash-chained ledger:

- `ledger.jsonl`, the active segment;
- `ledger.NNNNNN.jsonl.gz`, closed segments, compressed, created when the active one reaches the segment size;
- `ledger.index.json`, the ordered list of closed segments with the hash of each, so deleting, changing or adding a segment is detected.

The segment size is 32 MB; `SIRISYS_SEGMENT_BYTES` changes it. To check a ledger from genesis across all its segments:

```bash
python3 -c "from sirisys_loader import load_framework; print(load_framework().verify_ledger('sirisys_runs/<run>/ledger.jsonl'))"
```

It answers `ok` and the number of proofs or, for a damaged record, the position of the first proof that does not belong and why.

**Versions.** Framework files follow `Sirisys_Framework_vX_Y.py`, and every program loads the highest version in the folder (v13_10 is above v13_9). Experiment mode and the reports say which one they loaded, and `python3 sirisys_loader.py` says which one would be loaded. A name that does not match exactly, such as `Sirisys_Framework_v13_3_backup.py`, is ignored. To reproduce a run with one file, or to keep a long-lived instance on the framework it was born with:

```bash
export SIRISYS_FRAMEWORK="Sirisys_Framework_v13_3.py"
```

**The framework on its own.** `python3 Sirisys_Framework_v13_3.py` runs a console demonstration: 8 cycles of one instance kept in `sirisys_v13_state.json` and `sirisys_v13_ledger.jsonl`, begun at genesis or resumed.

**Files created while running.**

| Path | Written by |
|---|---|
| `sirisys_runs/` | Experiment mode, one folder per instance |
| `sirisys_report.json`, `sirisys_determinism.json` | `run_report.py` |
| `phase3_measurements.json` | `measure_phase3.py` |
| `sirisys_v13_state.json`, `sirisys_v13_ledger*` | The framework run on its own |

None of these belong in the repository; `.gitignore` excludes them, together with the outputs of `soak.py` and `live_c2.py` when they are named as in these examples (`soak_result.json`, `live_none.json`, `live_ollama.json`).
