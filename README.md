# STRATA

**S**IRISYS · **T**etralemma · **R**ecursive · **A**rchitecture · **T**opology · **A**nalysis

[Español](README_ES.md)

A software interpretation of the SIRISYS recursive ontological system: a field of constructs that evolves cycle by cycle through concordancy operations, cussive collapse and stratified emergence across four ontological layers, with every event sealed in an irreversible, hash-chained record.

STRATA is an independent interpretation in software, not an official SIRISYS work. It follows *Pre of Then: The Material Constructs* (TMC) as its primary source, together with other confidential materials and documentation, and the framework header labels every citation by source level: primary, interpretive, or design choice.

Author: Juan A. Pérez-Gómez.

-----

## Documentation

| Document | English | Español |
|---|---|---|
| Technical guide: every file, mode, option and output | [SIRISYS_Guide_v13_EN.md](SIRISYS_Guide_v13_EN.md) | [SIRISYS_Guide_v13_ES.md](SIRISYS_Guide_v13_ES.md) |
| Mac guide: installation and first experiments, step by step, for first-time users of the Terminal | [SIRISYS_Mac_Guide_v13_EN.pdf](SIRISYS_Mac_Guide_v13_EN.pdf) | [SIRISYS_Mac_Guide_v13_ES.pdf](SIRISYS_Mac_Guide_v13_ES.pdf) |
| Technical glossary: every concept with its source and how the code implements it, and every counter the views show | [SIRISYS_Concepts_v13_EN.pdf](SIRISYS_Concepts_v13_EN.pdf) | [SIRISYS_Concepts_v13_ES.pdf](SIRISYS_Concepts_v13_ES.pdf) |

The code is the framework (`Sirisys_Framework_v13_3.py`), an experiment server with a live view in the browser, an inspector for saved instances, tools for measured runs, and five test suites. The technical guide describes each file.

-----

## Quick start

Python 3.10 or higher on macOS, Linux, or Windows with WSL.

```bash
pip3 install -r requirements.txt
python3 test_sirisys.py                    # integrity, determinism, bounded memory: every check should pass
python3 Sirisys_Server.py --play           # experiment mode, with this machine's percepts
```

Open `http://127.0.0.1:8000` to watch the field. `Ctrl+C` in the terminal stops the server and saves the instance in `sirisys_runs/`; to examine it afterwards, open its `state.json` in `Sirisys_Static_Visualizer.html`.

```bash
python3 run_report.py --cycles 20 --seeds 1 --backend none    # a short measured run, without a model
```

**A model is optional.** Without one everything runs and constructs get synthetic names. With one, it names emergents, labels conflicts, narrates the field and asks the Sombunal questions, which enter the field as constructs. Two backends: Ollama, local (nothing leaves the machine), and the Anthropic API, whose key goes only in the terminal session (`export ANTHROPIC_API_KEY=...`), never in a file. Section 2 of the technical guide covers both, and the watch that stops a run whose model fails.

-----

## Core concepts

**Layers.** Constructs live in four layers: `NULL_00` (held only by the origin anchor), `UMBRA_0` (where percepts, questions, conflicts and most products are born), `UNIT_1` (active units, candidates to crystallize; a `BOTH` product is born here) and `APPARENT` (crystals). A construct rises a layer when enough tension reaches it (cussive collapse); an Apparent is incontrovertible.

**Tetralemma.** Every relation carries one of four states: `TRUE`, `FALSE`, `BOTH`, `NEITHER`. Sustained `BOTH` drives emergence and closes once enough recursion has been exchanged through it. `NEITHER×NEITHER` materializes a conflict, or, past a per-cycle cap, the fourth corner itself: no combination is a dead end.

**Concordancy.** The operator `[::]` combines two constructs into a third and records the event as a proof. With opposite chirality the older operand orients the result, so `x::y ≠ y::x`.

**No randomness.** The framework has no pseudo-random generator. Every choice is derived from the ledger head (the whole irreversible history) and the question being decided: the same history reproduces the same run, and different histories never draw alike.

**Breathing.** A single field-wide breath alternates contraction (favouring crystallization) and expansion (favouring generation). Once per breath the field adjusts its own tolerance so that crystals formed track crystals concluded.

**Integrity.** Every proof is sealed in an append-only, hash-chained ledger stored as compressed segments with an index of hashes. Time never moves backwards, a resumed instance equals an uninterrupted one, and any later edit, deletion or reordering of the record is detected. Nothing disappears silently: a construct that concludes leaves a termination proof.

The glossary defines every term with its source.

-----

## Status

Research project under active development.

- On synthetic percepts and without a model, the field meets its self-adjustment criteria: durable crystals every breath, little flicker, bounded size, flat memory and cost. With the machine's real percepts the crystallization rate trends downward over long runs; this is under study.
- Calibration with an active local model is in progress.
- Open questions are recorded in the framework header as WALLS: substrate (digital, not analog), self-sustenance, agency, and relations versus events. The roles of the Sombunal and of the Lagrangian points are open design decisions; the Lagrangian points tag constructs and proofs but do not yet govern any decision.

-----

## License

PolyForm Noncommercial 1.0.0: see [LICENSE](LICENSE).
