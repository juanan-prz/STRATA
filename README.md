# STRATA

**S**IRISYS · **T**etralemma · **R**ecursive · **A**rchitecture · **T**opology · **A**nalysis

A software interpretation of the SIRISYS recursive ontological system: a field of constructs that evolves cycle by cycle through concordancy operations, cussive collapse and stratified emergence across four ontological layers, with every event sealed in an irreversible, hash-chained record.

The field follows *Pre of Then: The Material Constructs* (TMC) as its primary source, together with other confidential materials and documentation. It is an interpretation built in software, not the original system; the framework header labels every citation by source level (primary, interpretive, design choice).

Author: Juan A. Pérez-Gómez.

> New to the terminal? Start with `Guia_SIRISYS_Mac.pdf` (Spanish): it walks through installation, the tests and the first experiments step by step.

-----

## Contents

| File | Purpose |
|---|---|
| `Sirisys_Framework_v13_3.py` | The field: tetralemma, concordancy operator, cussive collapse, chirality, breathing, proof ledger, and the canonical cycle `run_cycle` |
| `sirisys_loader.py` | Finds and loads the newest framework file in the folder |
| `Sirisys_Server.py` | Experiment mode: runs the field and serves it to the live visualizer |
| `Sirisys_Live_Visualizer.html` | Live topology in the browser (experiment mode) |
| `Sirisys_Static_Visualizer.html` | Inspector of a saved instance: opens its `state.json` in the browser (no server, no connection) to examine each construct, its proofs, its genesis and its relations; several files of one instance make a timeline |
| `run_report.py` | Instrumented runs on the same synthetic streams: the model, the model asking only the Sombunal questions, and a control without a model; writes `sirisys_report.json` |
| `field_topology.py` | Read-only topology and depth of the field, recorded by `run_report.py` and `live_c2.py` |
| `sirisys_measures.py` | Shared measurements: the self-adjustment criteria, and the model-health watch that stops a run whose model does not answer |
| `test_sirisys.py`, `test_phase1.py`, `test_phase2_guarantee.py`, `test_phase4.py`, `test_ontology.py` | Test suites |
| `sirisys_testkit.py` | What the test suites share: the checks and their summary, fresh copies of the framework, a local stand-in for an Ollama model |
| `measure_phase3.py`, `soak.py`, `live_c2.py` | Measurements: self-adjustment criteria, a long life, real percepts |
| `requirements.txt` | Python dependencies |
| `Guia_SIRISYS_Mac.pdf` | Step-by-step setup on a Mac for first-time users (Spanish) |
| `Sirisys_Guia_v13.md` | Technical guide to modes, files and options (Spanish) |
| `SIRISYS_Concepts_v13_EN.pdf`, `SIRISYS_Concepts_v13_ES.pdf` | Glossary: every concept with its source and how the code implements it (English, Spanish) |

-----

## Setup

Python 3.10 or higher on macOS, Linux, or Windows with WSL.

```bash
pip3 install -r requirements.txt
```

A model is optional. Without one everything runs and constructs get synthetic names; with one, an LLM intermediary names emergents, labels conflicts, narrates the field and asks the Sombunal questions that enter the field as constructs. Two backends:

- **Ollama** (local and recommended: nothing leaves the machine). Install it from ollama.com and pull a general-purpose model, for example `ollama pull llama3.1`. Reasoning models that "think" before answering can spend the short reply budget thinking and return empty names. If more than one model is installed, choose one with `export SIRISYS_LLM_MODEL=llama3.1`; otherwise the first one Ollama lists is used.
- **Anthropic API**: `export ANTHROPIC_API_KEY="sk-ant-..."` in the terminal session. Never store the key in a file in this folder.

Select the backend with `SIRISYS_LLM_BACKEND=ollama|anthropic|none` (or `--backend` in `run_report.py`), the model with `SIRISYS_LLM_MODEL`, and a non-default Ollama address with `OLLAMA_HOST`. Keep the same backend, model and profile across runs you intend to compare.

A model that fails or answers empty would leave the field on synthetic names without notice. With a model, `run_report.py` and `live_c2.py` first make two real calls and stop if the answers are missing or empty; during the run they stop (exit code 3) when 3 calls in a row fail or more than 10 % of the last 50 fail or come back empty. The output is still written, marked `aborted`, with the reason. The probe also records which model exactly answered (for Ollama: digest, size, parameters and quantization), and the health report keeps the first answers of each kind. Experiment mode watches the model the same way: when the watch trips it pauses once, and the live visualizer says why.

The model reaches the field through two channels: the names it gives (they become construct keys, and so enter every orientation) and the Sombunal questions (they enter the field as constructs). `run_report.py` separates them with a third arm in which the model only asks the questions while the names stay the control's; withholding the questions too gives the control bit for bit, which `test_phase1.py` checks.

-----

## Quick start

```bash
python3 test_sirisys.py                    # integrity, determinism, bounded memory
python3 Sirisys_Server.py --play           # experiment mode, live percepts
```

Open `http://127.0.0.1:8000`. Play, Step and Reset control the field; Fit recentres the view; relations and strata change the layout (keys: Space, S, F, V); `Ctrl+C` in the terminal stops the server.

```bash
python3 run_report.py --cycles 20 --seeds 1 --backend ollama    # short measured run
```

-----

## Experiment mode

For calibration and refinement. Every start and every Reset is a new instance in its own folder, `sirisys_runs/<date-time>_<live|streamN>/`, holding `state.json` and the ledger. Nothing is overwritten. To examine an instance afterwards, open its `state.json` in `Sirisys_Static_Visualizer.html`.

| Option | Effect |
|---|---|
| `--play` | Start cycling immediately |
| `--stream N` | Synthetic percept stream N: the run is identical every time |
| `--profile minimal` | No narration and no time-of-day percept: the field perceives only the machine it runs on |
| `--delay-ms` | Pause between cycles (default 80) |
| `--host` | Address to listen on (default `127.0.0.1`: this machine only) |
| `--port` | Web port (default 8000) |

The visualizer connects over a WebSocket; where that is blocked, it falls back to polling over HTTP and shows "connected (polling)". Its header shows the ledger (proofs sealed and the head) and the model with its watch; the event log can be filtered by kind of entry. The field is laid out by its relations, or by strata: the Zero Points at the centre, then the anchors, UMBRA_0, UNIT_1 and APPARENT outwards, so that a construct that rises a layer moves out. The inspector offers the same two layouts. The server can be left cycling with no browser open: it keeps only the latest 200 snapshots for the next viewer. The interface (the routes and the control actions) is described at the top of `Sirisys_Server.py`; details are in `Sirisys_Guia_v13.md`.

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
python3 test_phase1.py               # experiment engine, model backends, web layer, model health, experiment tools
python3 test_phase2_guarantee.py     # measuring topology and depth leaves the ledger and the field unchanged
python3 test_phase4.py               # segmented ledger, tampering, crash during rotation, disk
python3 test_ontology.py             # invariants of the field, cycle by cycle, with and without a model
python3 measure_phase3.py            # self-adjustment criteria (3 streams × 5,000 cycles)
python3 soak.py 50000 > soak_result.json
python3 live_c2.py 10000 none minimal > live_none.json       # real percepts, no model
python3 run_report.py --backend ollama --profile minimal --cycles 1000 --seeds 3
python3 run_report.py --backend ollama --profile minimal --cycles 1000 --determinism
python3 live_c2.py 3000 ollama minimal > live_ollama.json    # real percepts, local model
```

Each suite ends with a `SUMMARY` line; every check should pass. `test_ontology.py` checks what the field must be, from the primary source: Zero Points are never operands, the older operand leads and hands its chirality on, a crystal is never demoted or altered, nothing leaves without a termination proof, no crystal concludes in the cycle it forms, and with a model in the loop every request carries a seed oriented by the history; also the Stop Chasm and Adsurdic caps on conflicts (TMC p.41), anchors that never conclude, and the tolerance within its bounds. One case is known and allowed only during the first breath: a new crystal whose `BOTH` support is eroded by UCO in the same cycle.

The framework has no randomness, but a model runtime may have some even though every request carries a seed derived from the history. `--determinism` runs the model arm on the first stream twice and says whether both runs sealed the same ledger and, if not, the cycle at which they parted; it writes `sirisys_determinism.json` and leaves `sirisys_report.json` alone. Every report also prints the ledger head of each run.

`run_report.py` and `live_c2.py` judge every run by the self-adjustment criteria (durable crystals in every 1000-cycle window, flicker ≤ 5 %, no growth trend, flat cost of the cycle itself, bounded top-3 energy), with the code `measure_phase3.py` uses. `live_c2.py` also records what the field perceived (counts per 1000 cycles and the whole sequence) and the Sombunal questions that entered it. Real percepts read the machine: leave it idle during a `live_c2.py` run whose results you intend to compare.

`run_report.py` and `live_c2.py` also write a `topology_trace`: twice per breath, at expansion and at contraction, the shape of the field (weak components, directed cycles, reciprocity, clustering, the most connected construct, edges by tetralemmic state and by layer pair, and how much of the `BOTH` lies in the largest component) and two depths: the conflict depth of each conflict, which the field caps at the Adsurdic threshold, and the genealogical depth of every construct by layer, the number of `[::]` generations that separate it from what the field did not produce itself (percepts, anchors, questions). Zero Points are left out, and each sample carries its cycle, breath, contraction and tolerance. The measurement only reads the field: the ledger head is identical with and without it.

-----

## Files created while running

| Path | Written by |
|---|---|
| `sirisys_runs/` | experiment mode, one folder per instance |
| `sirisys_report.json`, `sirisys_determinism.json` | `run_report.py` |
| `sirisys_v13_state.json`, `sirisys_v13_ledger*` | the framework run on its own |

None of these belong in the repository; `.gitignore` excludes them.

-----

## Status

Research project under active development.

- On synthetic percepts and without a model, the field meets its self-adjustment criteria: durable crystals every breath, little flicker, bounded size, flat memory and cost. With the machine's real percepts the crystallization rate trends downward over long runs; this is under study.
- Calibration with an active local model is in progress.
- Open questions are recorded in the framework header as WALLS: substrate (digital, not analog), self-sustenance, agency, and relations versus events. The role of the Sombunal and the Lagrangian points, which tag constructs and proofs but do not yet govern any decision, are open design decisions.

-----

## License

PolyForm Noncommercial 1.0.0. See `LICENSE`.
