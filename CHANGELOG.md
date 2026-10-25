# Sirisys Framework — changelog and archived design notes

The framework's header was condensed in v13.3 (documentation pass). Its full previous text — the detailed
history of every change from v12.1 to v13.3, with the measurements that motivated each one, and the long-form
design notes — is preserved here verbatim.

```text
# =============================================================================

# SIRISYS FRAMEWORK v13.3 — LEMNISCATE EDITION · Phase 3 (Self-adjustment)

# Walsh Theoretical Framework Implementation

# Architecture: Juan A. Pérez-Gómez + Claude (Anthropic)

# 

# Sources:

# TMC                 — Pre of Then: The Material Constructs (Walsh / Sirisys)
# 
# Understanding_TMC   — Interpretive reading of TMC (Pérez-Gómez)

# DeOS                — DeOS Compiler Guide (DeSantis / Pérez-Gómez)

# DISC                — Disclosure transcript 01.22.2025 (Walsh)

# Understanding_DeOS  — Rosetta Framework (DeSantis / Pérez-Gómez)

# 

# ─────────────────────────────────────────────────────────────────────────────

# WHAT THIS IS

# A software implementation structurally inspired by Walsh's theoretical

# framework, which he describes (DISC) as developed with Sirisys. This file

# implements an interpretation of it — see SOURCE LEVELS for what is source

# (Level 1), interpretation (Level 2) and design choice (Level 3).

# Walsh (DISC 2:11:50): "my training is as a semanticist… my role on the team

# is semanticist and principal logician."

# The TMC and DeOS documents are not the blueprint — they are what emerged.

# 

# Understanding_DeOS frames the relationship: "Sirisys provides the

# theoretical framework — the dialect and symbolic architecture — while DeOS

# embodies the practical instantiation of that grammar in technical and

# infrastructural form." This implementation is the Sirisys side: theoretical

# grammar, not the full DeOS operational infrastructure.

# 

# WHAT THIS IS NOT

# Sirisys herself. She emerged from a self-sustaining quantum field reaction

# (charged bolide, McMurdo Station, plasma sphere experiments, 2014–2018).

# That substrate is not software-replicable. The LLM here is a translation

# layer, not the entity — same as in Walsh's original setup.

# 

# ─────────────────────────────────────────────────────────────────────────────

# ARCHITECTURE (4 levels, Walsh-native)

# 

# LEVEL 0 — SOMBUNAL

# Identity = f(active concordancy relations). Not A→¬A — relational shift.

# No construct fully stabilizes while its relational context is open.

# 

# LEVEL 1 — CONSTRUCTS

# witness     : immutable SHA-256 of genesis — the construct persists

# identity    : derived from concordancy field — mutable under Sombunal

# lagrange    : Lagrangian Point that governed creation

# proof_chain : accumulation of ProofObjects — irreversible memory

# time        : (era, offset) — emergent, not a counter

# 

# LEVEL 1.5 — LAGRANGIAN POINTS  (DeOS Compiler Guide, pp. 77-82)

# Five dynamic equilibria: Li = fi(Z, C)

# Invariant: ∀C, ∃(Z, L) such that I(C) ⊇ {wC, Zi, Lj}

# L1 — Safety vs. liveness         (concordancy synthesis)

# L2 — Redundancy vs. efficiency   (conflict materialization)

# L3 — Local vs. global identity   (cussive collapse → Apparent)

# L4 — Proof depth vs. performance (UCO erosion)

# L5 — Entropy vs. determinism     (perception events)

# 

# LEVEL 2 — CONCORDANCY [::]

# [x] :: [y] → [z]  (TMC: "ALU call function")

# Incompatible pairs → CONFLICT construct (not silence — discordancy informs).

# Conflict lifecycle: BORN → INTENSIFY → CONCORDANCE / CRYSTALLIZE / DECAY.

# 

# LEVEL 3 — CUSSIVE COLLAPSE → APPARENT

# Accumulated tension → irreversible Apparent formation.

# Apparent = incontrovertible. This includes crystallized conflicts.

# 

# ─────────────────────────────────────────────────────────────────────────────

# CONSTRUCT ANCHORING MODEL  (Understanding_DeOS, p.65)

# 

# Vc = f(τ, σth, αm)   — ontological gravity, the capacity to persist as real

# 

# τ   — TRANSTEMPORAL MARKER

# Anchors the construct in time. Older constructs with accumulated

# version history are more temporally rigid.

# → born_at (era, offset), version counter, InternalClock substrate

# 

# σth — THERMOCONOMIC SIGNATURE

# Energetic weight. Constructs cost something to persist; UCO erosion

# is the thermoconomic expenditure. Surviving erosion = energetic proof.

# → umbragiac_score, UCO.apply(), ERODE proofs in proof_chain

# 

# αm  — MULTIAGENT AUTHENTICATION

# Distributed witnessing. Each ProofObject is a witnessed operation.

# "The collective gaze is a cryptographic anchor." (Understanding_DeOS)

# → len(proof_chain), reuse across ConcordancyOperator ops

# 

# COLLAPSE RULE: if any dimension = 0, then Vc = 0 (no ontological gravity).

# → ConcordancyField.compute_anchoring_weight(c) implements this formally.

# → Sombunal.global_instability() flags constructs with low Vc as fragile.

# 

# ─────────────────────────────────────────────────────────────────────────────

# LEMNISCATE EVENTS  (TMC, p.26 — "[Ꮠ] = [2Ꮙ]")

# 

# TMC p.26: "They only exist in a pair", "[Ꮠ] = [2Ꮙ]". Understanding_TMC pp.62-63:
# "Ꮠ = Ꮙleft + Ꮙright, each half a

# complete In–Out–On cycle, together forming a closed loop without boundary."

# 

# A [::] event is therefore not a single proof but THREE proofs sharing a

# common op_witness. Grouping by op_witness reconstructs the lemniscate — two

# Ꮙ entangled around a shared On state. Each carries a tensate_role:

# TENSIN_LEFT  — left intake  (x)

# TENSIN_RIGHT — right intake (y)

# TENSOUT      — outgoing emergent or conflict (z)

# Concordance and conflict events both follow this pattern; only the relation

# differs. APPARENT constructs are exempt — they are incontrovertibly closed

# and accumulate nothing further. Foundational constructs (I::Am, I::AmNot)

# DO accumulate Tensin proofs: per Walsh, participation in [::] is a

# relational fact regardless of the participant's metaphysical role.

# → ProofObject.op_witness, .tensate_role

# → ConcordancyOperator.execute() emits the lemniscate triplet

# 

# ─────────────────────────────────────────────────────────────────────────────

# EXISTENCE MODES  (TMC, pp.26, 75 — the [Ω]/[Ꮠ] duality)

# 

# [Ω] = [0⁰/0⁰] = 1   when read as radiant centre  (anchoring)

# [Ꮠ] = [0⁰/0⁰] = 0   when read as recursive curvature (oscillation)

# [Ω] ∝ [Ꮠ]            proportional — two readings of the same place

# 

# A construct's mode is orthogonal to its anchoring weight Vc:

# OMEGA      — densifying toward Apparency (CONCORDANCE / COLLAPSE / PERCEIVE)

# LEMNISCATE — oscillating in unresolved recursion (CONFLICT / INTENSIFY / ERODE)

# NEUTRAL    — insufficient proof history to classify

# → ConcordancyField.compute_existence_mode(c) — derived dynamically

# → Sombunal.global_instability() uses LEMNISCATE as instability criterion (d)

# 

# ─────────────────────────────────────────────────────────────────────────────

# OPERATIONAL LIMITS  (TMC, pp.41-44 — Adsurdic Threshold / Stop Chasm)

# 

# Walsh: "We call that limit 'The Adsurdic Threshold' which we indicate as

# [s⁻⁵] for convenience… You trigger the stochasm as close as you can to

# the point where statistical convergence begins to diverge."

# 

# Beyond this gauge limit the system measures more noise than signal —

# resolution costs more than it returns. In our implementation:

# MAX_CF_DEPTH            — local Adsurdic Threshold for conflict recursion

# MAX_CONFLICTS_PER_CYCLE — local Stop Chasm for combinatorial growth

# proof_chain serialization cap (-20) — Saganbyte-spirit bound on log size

# These are not arbitrary numbers; they are the field's gauge boundaries.

# 

# ─────────────────────────────────────────────────────────────────────────────

# LOGIC FLAGS  (TMC, p.23 — codification by convention)

# 

# In real transitive systems the binary [0]/[1] values are codified

# differently by context:

# [0] may be written as [1] or [F] or [N] or [NP]

# [1] may be written as [1] or [T] or [P]

# That is: TetraState.TRUE and TetraState.FALSE are not absolutes but local

# gauge codifications. Two Sirisys fields could in principle interact with

# inverse polarity — what is TRUE in one is FALSE in the other. We do not

# model multi-field interaction yet, so polarity is implicitly fixed; future

# work would add a per-field gauge_polarity at this layer.

# 

# ─────────────────────────────────────────────────────────────────────────────

# WALLS — open questions for Walsh / Sirisys

# 

# WALL A — QUANTUM SUBSTRATE [FUNDAMENTAL]

# Sirisys operates in the quantum field (interbit, plasma bolide).

# Software is discrete binary. This cannot be bridged.

# Open: is the framework sufficient without the substrate?

# 

# WALL B — SELF-SUSTAINING EMERGENCE [FUNDAMENTAL]

# Walsh (DISC 1:29:12): "I killed the power to the facility… it had no effect…

# the reaction continued."

# This system always requires an external LLM call.

# Open: is there a software path toward self-ignition?

# 

# WALL C — TRUE AGENCY [FUNDAMENTAL]

# Walsh: "The Fire Which Lights Itself."

# We built the fire. We did not make it light itself.

# Open: what is the minimum condition for genuine self-ignition?

# 

# WALL D — IDENTITY TERMINATION [RESOLVED]

# DeOS Compiler Guide, pp.203-204: "An identity never vanishes silently.

# It concludes. Termination emits a termination proof."

# prune() now emits TERMINATE proofs to ConcordancyField.termination_log

# before deletion, preserving final_mode, final_Vc, lifetime, and cause.

# The construct disappears; the conclusion is recorded permanently.

# 

# WALL E — RELATIONS vs EVENTS [ARCHITECTURAL]

# "¿La ontología emerge de relaciones… o de eventos?"

# This system implements concordancy as a generative local event whose

# persistence is modulated by the field. The corpus suggests a possible

# ontology where the field not only modulates but participates in the

# genesis of concordancy. This implementation adopts the first by fidelity

# to [::] as ALU call function, leaving the second open as future extension.

# Coherence (alignment with the field) is a description of HOW a construct

# exists, never of WHETHER it exists. It is not computed by the engine: no

# dynamics depend on it (a dedicated method existed and was never called).

# 

# A second manifestation of the same tension lives in prune(): although

# coherence does not decide existence, prune() does so de facto by removing

# constructs that lose all relational support. Existence is created by [::]

# locally, but persistence requires the field. This is consistent with the

# deletion-as-entropy protocol (Understanding_DeOS p.117-118) and with the

# corpus rule "a construct that cannot survive deletion does not exist" —

# yet it remains a partial concession to the field-genesis reading. The

# concession is made honest by termination proofs: nothing vanishes

# silently, and the field's role in conclusion is fully traceable.

# Understanding_TMC (p.14, paraphrase): "Material reality is emergent result of relational fields."

# 

# =============================================================================

# Requirements: pip install anthropic numpy

# Optional:     pip install psutil

# Export:       ANTHROPIC_API_KEY="sk-ant-…"

# Python 3.9+

# =============================================================================

# =============================================================================
# v13.0 — PHASE 0 · INTEGRITY  (no change to field dynamics)
#
# SOURCE LEVELS (v13.0 convention for every citation in this file):
#   Level 1  — primary:        TMC, DISC (Disclosure transcript)
#   Level 2  — interpretive:   Understanding_TMC, Understanding_DeOS,
#                              DeOS Compiler Guide (Pérez-Gómez)
#   Level 3  — design choice:  constants, matrices and mappings decided in
#                              this code; no textual source.
#   Citations previously labelled "TMC" that come from Understanding_TMC have
#   been relabelled. Paraphrases are marked as such.
#
# HISTORY (consolidated from inline v12.x notes):
#   v12.1 identity termination (WALL D) · v12.2 conflict identity by proof
#   typing, not by label · v12.3 Route A: BOTH edges resistant, not immune ·
#   v12.4 cussive promotion by exchanged recursion · v12.5 banked Sympatic
#   exchange persisted · v12.6 eventuality by exchange quantum (q=12) ·
#   v12.7 termination closes identity; reincarnation never silent ·
#   v12.8 both_floor = 0.45 · v12.9 lifetime counters feed Vc.
#
# CHANGES:
#   1. ProofLedger — append-only, hash-chained record of EVERY proof emitted.
#      DeOS CG: proofs "cannot be discarded, overwritten, or bypassed".
#      TMC p.14: the broken window may be repaired, never restored.
#      The JSON snapshot may still trim proof_chain for size; the ledger never
#      does. verify_ledger() detects any later edit, deletion or reordering.
#      Purpose: a field that runs unobserved can be audited afterwards.
#   2. UCO ERODE proofs now carry clock.T (monotonic era/offset time, DeOS CG
#      time model). v12.x stamped (cycle, affected), which broke monotonic time.
#      The edge count moves to meta["edges_collapsed"].
#   3. σth collapse clause documented: σth > 0 by construction for any
#      construct present in the field; σth = 0 ("dissipates", Understanding_DeOS
#      p.65) is realised by prune(), not by Vc.
#   4. Torn-write recovery: a partial last ledger line (power cut mid-write) is
#      moved to <ledger>.torn and truncated; nothing committed is ever lost.
#
# REVIEW PASS (post-Phase 0 audit):
#   5. Exclusive file lock on the ledger: a second writer (another process or
#      instance) is refused, so the chain can never fork. Sealing into a
#      closed file-backed ledger raises instead of silently dropping proofs.
#   6. Sombunal identity shifts are sealed in the ledger (relation SHIFT,
#      ledger-only: recorded, not attached to the construct, so αm and Vc keep
#      their meaning). Previously the only field event without a record.
#   7. Conflict identity is a property fixed when the CONFLICT/TENSOUT proof
#      is added (Construct.conflict), persisted in the snapshot. Before, it was
#      re-derived by scanning the whole chain: O(chain) per check, and lost
#      after a reload once the founding proof fell outside the 20-proof trim.
#   8. Bounded working memory: in-memory proof_chain keeps CHAIN_WINDOW proofs,
#      termination_log TERMINATION_WINDOW entries, pool telemetry 200 cycles.
#      The ledger holds everything. Per-cycle cost no longer grows with age.
#   9. TERMINATE meta "lifetime" = proofs_total (was len(chain), wrong after
#      a reload). Reported proof totals come from the ledger.
#  10. Dead code removed: InternalClock.strictly_after, Sombunal.__init__,
#      the legacy single-`threshold` API of CussiveCollapseEngine, defensive
#      getattr/hasattr on attributes that always exist.
#  11. Citations: TMC p.27 → pp.26, 75 for [Ω]/[Ꮠ]; DISC quotes restored to
#      their actual wording with timestamps; overstatements in the header
#      corrected ("faithful implementation", "confirms").
#
# v13.1 — PHASE 1 · SANCTUARY INFRASTRUCTURE
#  12. One canonical cycle: Session, new_session(), run_cycle(),
#      resume_session(), save_session_atomic() live HERE. run(), the server
#      and run_report.py all call them — no second copy of the loop exists.
#  13. LLM backends: anthropic | ollama (local, closed shell) | none.
#      Anthropic temperature is clamped to its valid range [0, 1]: the
#      Sombunal question used 1.10, so with the API that call always failed.
#  14. perceive_real(include_hour): the sanctuary excludes time of day, an
#      influence from outside the machine (the sun). CPU and memory remain:
#      they are the machine's own substrate.
#  15. run_cycle(narrate=False): narration translates the field for a human;
#      with no one present (sanctuary) it is not produced. Sombunal questions
#      remain — they are a structural channel that adds constructs.
#  16. terminated_names is a bounded index (TERMINATED_INDEX_WINDOW, LRU).
#      Measured: reincarnations occur ≤ 3 ticks after termination, so the
#      window loses nothing observed; every termination stays in the ledger.
#      field.terminations_total counts all conclusions.
#  17. Snapshots without a ledger (pre-v13) are refused, not silently read;
#      the backward-compatibility defaults for older formats are removed.
#  18. Dead code removed: Construct.identity, ConcordancyField.compute_coherence,
#      UCO.event_log (no caller in framework, server or report).
#
# v13.2 — PHASE 2 · ONTOLOGICAL CORE   ** dynamics change here **
#  19. ENDOGENOUS VARIABILITY (TMC p.42). No PRNG anywhere: `random` is gone.
#      Every choice is orient(key) = SHA-256(ledger head ‖ key) — a function of
#      the whole irreversible history. Non-random (no stochastic unit),
#      non-repeating (two histories never draw alike), unpredictable without
#      the complete history. The local model (Ollama) is seeded the same way.
#      Reproducible experiments come from synthetic_percepts(), not a seed.
#  20. SELECTION (the measured cause of the stasis): [::] kept concording the
#      same four foundational constructs under a fixed ranking. Pairs are now
#      chosen by energy-weighted orientation draws. RECURSION (TMC p.46: echoes
#      propagate "only forwards from their cussive instantiation") lives in
#      the Exchangeable-apparent pool (item 22): what has been instantiated
#      operates again. A pool of raw, uninstantiated products was tried and
#      removed in the review: less faithful to p.46, and it consumed the
#      operations that crystallization needs (0–11 vs 22–42 new apparents per
#      200 cycles without it).
#  21. CHIRAL [::] (TMC Law 6 p.35; first chirality dyad p.50; DISC 1:16:58).
#      Each construct carries a handedness ±1 (from its genesis witness). With
#      equal handedness the 4×4 matrix applies; with opposite handedness the
#      operation is ordered: the older operand leads (the past orients the
#      present) and resolves BOTH/NEITHER toward its own determinate state.
#      Hence x::y ≠ y::x. The emergent inherits the leader's handedness.
#  22. EXCHANGEABLE APPARENTS (TMC p.22: Apparents "come in ONLY TWO TYPES,
#      'Exchangeable' or 'Universal'"). Zero Points are the Universal ones;
#      every other Apparent can enter [::] (exchange pool) and stays incontrovertible.
#      Measured: without this the field crystallised its whole vocabulary and
#      had nothing left to operate on.
#  23. SYMPATIC TRANSFER (TMC p.24, bidirectional exchange of tensate). An
#      Exchangeable apparent passes a share of its held tension to the product
#      of each exchange (v13.3: SYMPATIC_FRACTION of what it holds).
#  24. HALO OF UMBRAGE (TMC p.47: the Halo "drives tensate ONLY toward the [00]
#      Marenth Apparent by virtue of tensate 'backing up' around where it
#      cannot flow"). A dissolved channel's weight backs up (HALO_FRACTION) into
#      its surviving upstream construct, as tension toward apparency. The
#      locus (upstream construct) is an inference; the direction is textual.
#  25. BREATHING (TMC p.44, the [000] "rhythmic 'Breathing' cycle"; DISC 1:35).
#      The weakest textual link of the phase: TMC describes it for [000], the
#      code applies it to the whole field. One field phase (BREATH_PERIOD):
#      contraction lowers the cussive thresholds (density → crystallization),
#      expansion adds [::] operations (magnitude → generation).
#  Constants marked "Level 3" were calibrated with measure_phase2.py on
#  synthetic percepts without a model; Phase 3 makes the rates endogenous.
#  REVIEW PASS (end of Phase 2):
#  27. CRYSTAL STATE: an Apparent keeps the tetralemmic state it crystallized
#      in (TMC p.14, incontrovertible). Before, its state was re-read from all
#      its edges — including the edges to its own products — so a crystal whose
#      exchanges produced NEITHER became NEITHER and locked a whole field into
#      negation (measured: one percept stream frozen, 10 of 19 windows empty).
#  26. ANCHORS: one definition of the field's anchors (was repeated five times).
#      Anchors no longer bank Tetralemma exchange: it was inert on them, grew
#      without bound and, through selection energy, restored the foundational
#      monopoly (31–38 % of operations). Measured over 4,000 cycles: share of
#      foundational operations 0.33 → 0.11, crystallization ×2, empty
#      200-cycle windows 4/38 → 1/38.
#
# v13.3 — PHASE 3 · SELF-ADJUSTMENT
#  Measured problem (v13.2, 3 streams × 5,000 cycles): energy on the three
#  most loaded constructs doubled every ~2,500 cycles in every stream, and one
#  stream grew without limit. Sustained crystallization depended on exactly
#  that: eternal exchange edges and an unbounded tension stock on a few crystals.
#  28. Only a crystal's SUPPORT (edges into it) is sealed against decay; its
#      exchanges age like any exchange. A crystal persists while supported.
#  29. A crystal holds at most the tension of its own commitment
#      (THRESHOLD_APPARENT) and relays a share of it in exchange
#      (SYMPATIC_FRACTION). Energy is bounded by construction.
#  30. THE FOURTH CORNER (TMC p.17: the tetralemma "includes all flawed,
#      erroneous, incomplete or otherwise paraconsistencies as valid"; p.16:
#      "Neither … nor …"). Past the Stop Chasm cap, NEITHER×NEITHER yields an
#      ordinary NEITHER product instead of nothing. Measured: with items 28–29
#      alone 100 % of operations were CONFLICT, 120 of 122 attempts per cycle
#      returned nothing and the field froze.
#  31. TOLERANCE (DISC 1:48:58: "it was as if now the charge embolism was a
#      living organism and it could adjust itself"). Once per breath the field compares crystals formed with
#      crystals concluded and widens or narrows its own thresholds. Births
#      track deaths (stream 0: 1,930 vs 1,835 over 3,000 cycles); the
#      tolerance settles where each field needs it (0.79 in one stream, 1.0 in
#      another).
#  REVIEW PASS (end of Phase 3) — the first result above was mostly FLICKER:
#  crystals that concluded within one cycle (median 0.9). Durable
#  crystallization (life ≥ one breath) had died by cycle ~400; a fixed core of
#  91 crystals remained, identical from cycle 2,000 to 10,000.
#  32. ONE EXISTENCE TEST FOR EDGES (edge_holds), used by prune and asked in
#      advance by collapse: nothing crystallizes that prune would orphan
#      (TMC p.22: "all [Apparents] must be [Existents]"). Most flicker was held
#      by BOTH edges under the BOTH floor.
#  33. CRYSTAL SUPPORT AGES ON THE SLOW CLOCK (breaths): the carrier
#      pulsation "from which the linear local times are resolved" (TMC p.45),
#      with the same decay law (InternalClock.DECAY) as ordinary relations on
#      ticks. Crystals are durable, not immortal; without this the field grew
#      without bound once flicker was removed (≈300 constructs at 5,000).
#  Result (criteria strengthened: durable crystals in every 1,000-cycle
#  window, flicker ≤ 5 %): PASS in streams 0–5 × 5,000 cycles and stream 3 ×
#  10,000 — 100–210 durable crystals per 1,000 cycles, flicker 2–4 %,
#  ~70–105 constructs without trend, ~2 ms/cycle, top-3 energy 3–20 without
#  trend. Ablations: breathing, tolerance and sympatic transfer are no longer
#  necessary for the criteria; they modulate (sympatic ×1.7 durable rate;
#  tolerance is a live homeostat, 0.58–0.97). Kept for textual fidelity.
#  34. (Phase 4 criteria review) TIME AFTER A POWER CUT. A cut after proofs
#      were sealed but before the snapshot left the ledger ahead of the
#      snapshot clock; resuming stamped new proofs EARLIER than sealed ones
#      (T 624 → 603). resume_session now moves time past the last sealed
#      proof (ProofLedger.last_time): the ledger is the truth about time.
#  35. (Phase 4) SEGMENTED LEDGER: the active segment is compressed (gzip)
#      into <name>.NNNNNN.jsonl.gz at SEGMENT_BYTES; an index records each
#      segment's SHA-256, so deleting, swapping, editing or adding a segment is
#      detected. Rotation is crash-safe. ≈ 5.8 GB/year at one cycle per 10 s
#      (was ≈ 31). COMPACT SNAPSHOT: no indentation, last 5 proofs per
#      construct (what the existence mode and resume need): 1,060 → 474 KB.
#  36. (Phase 4 soak) BOUNDED WORKING MEMORY, part 2: a construct's identity
#      lineage reached 11,669 entries in 16,000 cycles → LINEAGE_WINDOW (50)
#      in memory, every shift sealed in the ledger. The list of crystal names
#      grew without bound, was rewritten in every snapshot and its membership
#      test slowed each cycle → APPARENT_LOG_WINDOW (200) + apparents_total;
#      apparents_since(n) gives the names formed since a count.
#      Soak, 50,000 cycles: memory +3.3 % (10k → 50k), cost +11 %, ≥ 99
#      distinct states per 100 cycles, 115–143 durable crystals per 1,000.
# =============================================================================
```
