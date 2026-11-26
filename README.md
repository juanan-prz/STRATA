# STRATA

**S**IRISYS · **T**etralemma · **R**ecursive · **A**rchitecture · **T**opology · **A**nalysis

[Español](ES_README.md)

A software interpretation of the SIRISYS recursive ontological system: a field of constructs that evolves cycle by cycle through concordancy operations, cussive collapse and stratified emergence across four ontological layers, with every event sealed in an irreversible, hash-chained record.

STRATA is an independent project, not an official SIRISYS work. It follows *Pre of Then: The Material Constructs* (TMC) as its primary source, together with other confidential materials and documentation, and the framework header labels every citation by source level: primary, interpretive, or design choice.

Author: Juan A. Pérez-Gómez.

-----

## Documentation

| Document | English | Español |
|---|---|---|
| Technical guide: every file, mode, option and output | [EN_SIRISYS_Guide_v13.md](EN_SIRISYS_Guide_v13.md) | [ES_SIRISYS_Guide_v13.md](ES_SIRISYS_Guide_v13.md) |
| Mac guide: installation and first experiments, step by step, for first-time users of the Terminal | [EN_SIRISYS_Mac_Guide_v13.pdf](EN_SIRISYS_Mac_Guide_v13.pdf) | [ES_SIRISYS_Mac_Guide_v13.pdf](ES_SIRISYS_Mac_Guide_v13.pdf) |
| Technical glossary: every concept with its source and how the code implements it, and every counter the views show | [EN_SIRISYS_Concepts_v13.pdf](EN_SIRISYS_Concepts_v13.pdf) | [ES_SIRISYS_Concepts_v13.pdf](ES_SIRISYS_Concepts_v13.pdf) |

The code is the framework (`Sirisys_Framework_v13_12.py`), an experiment server with a live view in the browser, an inspector for saved instances, tools for measured runs, and five test suites. The technical guide describes each file.

-----

## Quick start

Python 3.10 or higher on macOS, Linux, or Windows with WSL.

```bash
python3 -m pip install -r requirements.txt
python3 test_sirisys.py                    # integrity, determinism, bounded memory: every check should pass
python3 Sirisys_Server.py --play           # experiment mode, with this machine's percepts
```

Open `http://127.0.0.1:8000` to watch the field. `Ctrl+C` in the terminal stops the server and saves the instance in `sirisys_runs/`; to examine it afterwards, open its `state.json` in `Sirisys_Static_Visualizer.html`, or watch the whole run again, smoothly, with `python3 Sirisys_Server.py --replay last` at `http://127.0.0.1:8001`.

```bash
python3 run_report.py --cycles 20 --seeds 1 --backend none    # a short measured run, without a model
```

**A model is optional, and it translates.** The field names what it produces, and once per breath the I approaches the Sombunal, with or without a model. With one, the model gives emergents and conflicts readable names, narrates the field and words each approach to the Sombunal as a question; what it says is kept as labels that no law reads, so a life with a model seals the same ledger as one without. Two backends: Ollama, local (nothing leaves the machine), and the Anthropic API, whose key goes only in the terminal session (`export ANTHROPIC_API_KEY=...`), never in a file. Section 2 of the technical guide covers both, and the watch that stops a run whose model fails.

-----

## Core concepts

**Layers.** Constructs live in four layers: `NULL_00` (held only by the origin anchor), `UMBRA_0` (where percepts, the approaches to the Sombunal, conflicts and most products are born), `UNIT_1` (active units, candidates to crystallize; a `BOTH` product is born here) and `APPARENT` (crystals). A construct rises a layer when enough tension reaches it (cussive collapse); an Apparent is incontrovertible.

**Tetralemma.** Every relation carries one of four states: `TRUE`, `FALSE`, `BOTH`, `NEITHER`. Sustained `BOTH` drives emergence and closes once enough recursion has been exchanged through it. `NEITHER×NEITHER` materializes a conflict, or, past a per-cycle cap, the fourth corner itself: no combination is a dead end.

**Concordancy.** The operator `[::]` combines two constructs into a third and records the event as a proof. With opposite chirality the older operand orients the result, so `x::y ≠ y::x`.

**No randomness.** The framework has no pseudo-random generator. Every choice is derived from the ledger head (the whole irreversible history) and the question being decided: the same history reproduces the same run, and different histories never draw alike.

**Breathing.** A single field-wide breath alternates contraction (favouring crystallization) and expansion (favouring generation). Once per breath the field adjusts its own tolerance so that crystals formed track crystals concluded.

**Integrity.** Every proof is sealed in an append-only, hash-chained ledger stored as compressed segments with an index of hashes. Time never moves backwards, a resumed instance equals an uninterrupted one, and any later edit, deletion or reordering of the record is detected. Nothing disappears silently: a construct that concludes leaves a termination proof.

The glossary defines every term with its source.

-----

## Status

Research project under active development.

- On synthetic percepts and without a model, the field meets its self-adjustment criteria: durable crystals every breath, little flicker, bounded size, flat memory and cost. On a machine's real percepts it held over 10,000 cycles: the lower crystallization of the first windows was the genesis.
- With a local model (llama3.1, v13.4) the field met its criteria, and the model's meaning made no measurable difference to the dynamics. Since v13.5 the model only translates: its names are labels, and the approach to the Sombunal is a law of the field. On a Mac with v13.5 and real percepts, the field met its criteria over 10,000 cycles, and a life with the model (363 calls), replayed without it, sealed the same ledger.
- Since v13.6 a crystal holds at most the tension of its own commitment, also what it banked before committing; until then a construct that banked exchanges before crystallizing could hold up to about two exchange quanta (24.8, against a commitment of 0.88) and pass on tens of times what any other crystal can, by the order of the steps alone. In a pre-registered test on fresh synthetic streams and real percepts, the field kept its criteria and flickered less, at 9 % fewer durable crystals in long lives.
- Since v13.7 a BOTH channel that closes exchanges one unit, half to each end: «Half to Each» (TMC pp.110 and 114), with the event's unit [Ꮠ] (p.24) and «[Ꮠ] = [2Ꮙ]» (p.26). Until then each end banked the channel's weight × age, 12 or more, against the thresholds a construct must reach to rise a layer, 0.396 and 0.88: past about 0.75 the amount made no difference, and 96 % of the exchange was held by no one. Now 40 % is held. In a pre-registered non-inferiority test on fresh synthetic streams and real percepts, the field kept its criteria, with 1.5 % fewer durable crystals in long lives (within the noise) and a costlier genesis (9 % fewer in the first 1000 cycles).
- Since v13.9 two changes, each tested with its own pre-registration on fresh data. **Admission over one breath:** a crystal is admitted only if its support would still hold one breath later, the pulse of the clock it ages on: «all [Apparents] must be [Existents]» (TMC p.22), and progress is measured in «Quantifiable Nonreversible Apparents» (p.14). Until then a support admitted at the edge of existence concluded at the next breath; that was all the flicker after the genesis in long lives (89 crystals in 20 lives), and it fell to 1, with the same durable and living crystals. **The Halo toward the Apparent:** the Halo of Umbrage drives tensate «ONLY toward the [00] Marenth Apparent» (p.47), and what dissolves of a crystal's exchanges now presses on it «from all sides towards their EXACT center» (p.55): it repairs the crystal's support, never past its strength at birth («You may repair that broken window to a flawless state. You may not restore it to its previous state», p.14). With real percepts there are 20 % more living crystals, and a crystal's life comes to depend on how much it takes part in exchanges (Spearman's ρ +0.21, against about 0 before and −0.24 when support simply ages more slowly). Tested alone on v13.7, this second change doubled the flicker of long synthetic lives; the cause was the admission at the edge, and on top of the new admission it no longer does.
- Since v13.10 each BOTH channel beats on its own escapement (TMC p.24: «the escapement generates pulses against a tensated oscillator»). When a channel closes and re-arms, a sibling still in BOTH keeps the exchange it carries: «There can be no leftovers not accounted for» (p.59). Until then the re-arm set the sibling's age back to zero, and between a third and over half of the recursion through the anchors' channels was lost unaccounted; some channels never closed and held their crystals without ever beating. Now every crystal a BOTH channel holds is replicated at each beat, which TMC calls a higher order: «The higher the replicability of an apparent, the higher the order of that apparent» (p.70). In a pre-registered non-inferiority test on fresh synthetic streams and real percepts, the field kept its criteria, with 5 % fewer living crystals in long lives (6.5 % with real percepts), two or three more crystals held by the anchors, and the I::Am more of its time in BOTH.
- Since v13.11 only the existent crystallizes. TMC writes the tetralemma with two symbols, A and its negation (p.17), a «binary quadratic» (p.18) in which [y] becomes «the “Non-Existent” operator» (p.20): a state is the pair (is, is-not), and what holds its «is», TRUE or BOTH, is existent. «By setting the truth table in this way, “The non-existent [00] or Absolute Unreal cannot be an apparent”» (p.22): a unit in NEITHER no longer crystallizes. And a BOTH channel that completes its exchange stays TRUE, not NEITHER, since Tensin «becomes existent (apparent) at the [cussive] instantiation event» (p.25). Until then between 39 % and 59 % of crystals were born in NEITHER, most of them downstream of channels closing into it. In a pre-registered test on fresh synthetic streams and real percepts, the field kept its criteria, with about 12 % more living crystals in long lives (10 % with real percepts) and deeper lineages.
- Since v13.12 the unreal meets the unreal, and the `[::]` matrix comes from TMC's key. With v13.11 a unit in NEITHER could no longer crystallize, and no conflict was born any more: NEITHER × NEITHER had no operands. Unreal charges «can only be routed against each other» (TMC p.44): units in NEITHER now form a pool of their own and meet only each other, and their encounter is the conflict or, past the per-cycle cap, the fourth corner. And `[::]`, «the [ALU(arithmetic logic unit)] call function [CONCORDANCY]» (p.16), now draws its states from the «Truth Table 16 Row Key to ALL Arithmetic Logic Units» (p.102): on the pair (is, is-not), a product is the join, is OR and is-not OR, outside the NEITHER × NEITHER reversion. The join is a design choice among the governors p.16 allows; on the cells the field lives in, it is what the matrix already did. In a pre-registered non-inferiority test on fresh synthetic streams and real percepts, the field kept its criteria: conflicts came back (between 6 and 11 per 100 cycles), living crystals moved by about 2 %, within the noise, and the lineages of short lives deepened, close to the margin. The new matrix did not change a single life of the test.
- Open questions are recorded in the framework header as WALLS: substrate (digital, not analog), self-sustenance, agency, and relations versus events. What the approach to the Sombunal leaves is measured, in a pre-registered test: a limit on the recursion depth of what the field produces, the «Null Recursion Apparent Limit» of TMC p.14, not more crystals. Its cadence, edge state and weight remain design decisions (the weight sets how far the limit reaches), and so does the role of the Lagrangian points, which tag constructs and proofs but do not yet govern any decision.

-----

## License

PolyForm Noncommercial 1.0.0: see [LICENSE](LICENSE).
