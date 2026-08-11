# Isolation Planning AI Agent — Technical Solution Document
Document type: Technical Solution / Software Architecture for Development Version: 1.0 (Draft for engineering review) Covers: Requirements Specification v1.0 + Addendum A (four-layer scenario model, cascading isolation, cross-drawing boundaries, output UX) Platform context: Plant360.AI (Convert P&ID, UniGraph, Drawing & Document AI Agent) Audience: Development team, tech leads, QA, DevOps
## 1. Purpose of This Document
This document translates the Isolation Planning Agent requirements (spec v1.0 + Addendum A) into a buildable technical solution: system decomposition, data model, algorithms, interfaces, technology choices, testing and assurance approach, and a delivery plan mapped to the four requirement phases.
Requirement IDs (REQ-xxx, CI-x, S-xx) are referenced throughout so every design element is traceable to a requirement. Where this document makes a decision the requirements leave open, it is flagged with rationale.
### 1.1 Reading order for a new developer
Section 2 (architecture overview) and Section 3 (architectural decisions) — the shape of the system and the non-negotiables.
Section 5 (data model) — the vocabulary every service shares.
The component section (Section 4) for the service you are assigned.
Section 10 (determinism & reproducibility) — rules that apply to every line of code in the safety core.
### 1.2 Product posture: an application, not a chatbot
This system is a workflow application with a user interface, in which agentic/AI capability is embedded automation — it is not an interactive chatbot that produces isolation plans.
Users interact with the product through four purpose-built surfaces (U1 Plan Review, U2 Boundary Explorer, U3 Field Execution, U4 Isolation Register) plus the emergency shell, driving a controlled plan lifecycle (Draft → Authorised → … → Closed) with gating, acknowledgements and an audit ledger. All plan-determining logic is deterministic, versioned code (REQ-ARCH-01). Natural-language interaction exists at exactly three scoped entry points, each of which is a translation layer around deterministic machinery — never a decision-maker:
Entry point
What the LLM does
What it hands off
What it can never do
Work scope intake (5.8, §4.2)
Interprets an NL job description or CMMS work order
Resolved graph node IDs + structured scope attributes, user-confirmed before generation
Define the boundary or scope silently
Interrogation bar / what-if (REQ-F8-02, §4.13)
Maps a question to a fixed catalogue of deterministic query intents; renders the structured result as prose
A DSC query execution
Compute or invent an answer outside the plan model
Emergency triage (REQ-E-03, §4.12)
Parses an unstructured event description
Event type + resolved location entities
Select or rank isolation actions
Design red flag: any feature proposal shaped as "the user chats with the agent and it decides X" — where X is a boundary, barrier, sequence, classification or authorisation state — violates REQ-ARCH-02 and must be redesigned as (a) a structured UI interaction, or (b) an NL front-end to a new deterministic query intent. The Verification Gate (AD-05) enforces this at the type level, but the posture should also be enforced at design review.
Corollary for planning: the UI surfaces are the product as experienced by every user, and Addendum A §17 treats their design as safety-relevant (complacency-resistant acknowledgement, surface-visible provenance, gloved field usability). Expect the frontend/UX workstream to be comparable in size to the engine workstream — see the team-shape note in Section 12.
## 2. Solution Architecture Overview
### 2.1 The single most important constraint
REQ-ARCH-01/02/03 partition the system into two worlds that must never blur:
Deterministic Safety Core (DSC) — versioned, testable, conventional code. Everything that decides what the boundary is, which barriers are required, what order things happen in. Pure functions over pinned, immutable input snapshots. No LLM calls, no wall-clock reads, no network I/O, no randomness.
LLM Periphery — interprets natural-language scope, resolves ambiguous tags, extracts document content (via the Drawing & Document AI Agent), drafts narrative/permit prose, answers interrogatives, and triages emergency event descriptions. Everything it produces passes through a Verification Gate before it can influence a plan: entities must resolve to real UniGraph node IDs; free text is stored in fields typed as llm_generated and rendered visually distinct (REQ-ARCH-03).
Anything that cannot be classified into one of these two worlds is a design error.
### 2.2 System context
### 2.3 Service decomposition
A modular monolith for the DSC, with separately deployable services only where deployment characteristics genuinely differ. Rationale: the safety core is a chain of pure functions over one in-memory snapshot; splitting it into microservices adds network non-determinism, versioning skew, and latency — all directly hostile to REQ-F8-04 (byte-identical reproducibility) and REQ-NF-01 (performance). Independent deployables:
Deployable
Contents
Why separate
iso-core
Snapshot Assembler, Derivation, Traversal, Cascade, Pattern, Sequencing, Impact, Energy, SIS modules; plan generation API
The safety core; one artifact, one version number, one SBOM (REQ-SA-03)
iso-app
Plan lifecycle, authorisation, audit ledger, input ingestion/validation, exports, interrogation routing
Business logic; changes far more often than the core
iso-llm
LLM orchestration, prompt templates, verification gate, document Q&A proxy to the Drawing & Document Agent
Different scaling/cost profile; can be updated without recertifying the core (REQ-SA-04)
iso-emergency
M2 service with pre-warmed snapshots and precomputed indexes
Hard latency budget (<10 s first response, REQ-E-13); isolated failure domain; per-site enable flag (REQ-E-02)
iso-field
Offline-first PWA backend: sync API, conflict resolution, media (photo) store
Different availability and sync semantics (REQ-OM-02, REQ-NF-05)
iso-web
U1/U2/U4 frontends
Standard SPA delivery
All deployables are multi-tenant with hard tenant partitioning (Section 12).
## 3. Architectural Decisions (AD register)
ID
Decision
Driven by
Consequence
AD-01
Safety core is a library of pure functions over an immutable PlanContext snapshot; no I/O, clocks, env vars, or randomness inside
REQ-ARCH-01, REQ-F8-04
Same inputs → same bytes. All time-dependent logic (PSD expiry, duration escalation) receives time as an explicit input captured at snapshot time
AD-02
Content-addressed version pinning: every input artifact (graph snapshot, FHR, SIC, PSD, SAR, pattern library, rule engine build) is identified by a SHA-256 of its canonical serialization; a plan records the full set of hashes
REQ-SA-03, REQ-OM-04/05, REQ-IN-01/03
Reproducibility is verifiable, not asserted. A hash mismatch = authorisation invalidated
AD-03
Event-sourced audit ledger: every plan mutation, state transition, acknowledgement, field confirmation and emergency query is an append-only event; current state is a projection
REQ-OM-03, REQ-NF-03, REQ-E-14
Immutability by construction; diffs and shift-handover views are projections, not bolt-ons
AD-04
Scenario/pattern content is data (YAML), loaded and hash-pinned like any other input
REQ-SL-01, REQ-EP-03
Process safety engineers edit patterns without a software release; MoC applies to content, CI applies to schema
AD-05
LLM Verification Gate is the only path from iso-llm into plan data; it accepts only (a) resolved node IDs with resolution evidence, (b) typed llm_generated text fields
REQ-ARCH-03
Fabricated-device failure mode (REQ-SA-07) is structurally impossible, not just tested against
AD-06
Traversal operates on the stitched graph only; drawings exist solely as render metadata (sheet, grid ref, coordinates) on nodes/edges
REQ-XD-01
A drawing edge cannot terminate a path. Off-page-connector integrity is a snapshot admission check, not a traversal concern
AD-07
Emergency mode runs on a pre-warmed, periodically refreshed snapshot with precomputed reverse-reachability and remote-valve indexes
REQ-E-13, REQ-NF-01
Meets the 10 s budget without weakening M1 determinism
AD-08
Sequencing is modelled as a constraint DAG; generic ordering rules, pattern sequence constraints and L3 sequence inversions are all edges with provenance; inversions are hard edges that win conflicts
REQ-F6-02, REQ-FP-01, REQ-SL-03
One solver, one trace, no special-casing in code
AD-09
Plan documents (certificate, schedule, marked P&IDs, BOM) are renderings of the plan model, generated on export, watermarked with lifecycle state
A8.1, REQ-UX-E01..03
No document is ever the source of truth
AD-10
Field app is an offline-first PWA with a local event queue and CRDT-free, server-arbitrated conflict resolution (field events are append-only facts, so conflicts are rare and resolvable by ordering)
REQ-OM-02, REQ-NF-05
Simple, auditable sync; every field fact is an audit event
## 4. Component Design
### 4.1 Snapshot Assembler (iso-core)
Builds the immutable PlanContext that every downstream engine consumes.
Inputs: UniGraph version reference, FHR revision, SIC version, PSD instance, SAR revision, pattern-library revision, work scope (already resolved to node IDs by the intake flow), plan-time timestamp.
Responsibilities:
Fetch the pinned UniGraph version and materialise it into the in-memory adjacency model (Section 5.2). Never "latest" — always a named version (REQ-DEP-03).
Admission checks (fail = context not buildable; produces a structured gap report instead of a context):
Off-page connector resolution: every connector on any sheet in the loaded set resolves to a counterpart entity (REQ-XD-02). Unresolved connectors are recorded; if later found on/adjacent to a boundary path they escalate to unbounded live path (REQ-XD-03). Implementation: connector resolution status is a node attribute computed here, consumed by the traversal engine.
Drawing-set completeness: every drawing referenced by a traversable connector exists in the graph version (REQ-XD-04).
Tag uniqueness: same tag on multiple sheets must map to one entity; cross-unit duplicates flagged as ambiguities (REQ-XD-06).
Revision consistency metadata captured per sheet (REQ-XD-05).
Fluid resolution: join line service codes → service_code_map → fluids. Unmapped codes create an UnknownFluid marker carrying HSC-4 default + data gap (REQ-IN-02).
State overlay: apply the PSD as an overlay on the graph — equipment states, header statuses, valve position exceptions, active isolations (imported as ActiveIsolation objects with their T4 sets), active overrides. PSD age and validity are computed here against the plan-time timestamp and frozen into the context (AD-01); expiry blocks authorisation downstream (REQ-IN-06, S-31 lists exactly which declarations are stale).
Worst-case defaults for any path-relevant missing PSD entry: header live & pressurised, spare unavailable, valve at P&ID normal position — each recorded as a ConservativeDefault provenance item (REQ-IN-05, P4).
Compute and store the content hashes of every input (AD-02).
Output: PlanContext { graph, fluidMap, stateOverlay, sic, sar, patterns, scope, timeContext, provenanceIndex, admissionReport, hashes } — deeply immutable.
### 4.2 Input Services (iso-app)
One ingestion pipeline per structured input, each with: schema validation → semantic validation → controlled-document metadata capture → version registration (hash) → availability to the Snapshot Assembler.
Input
Format
Key validations beyond schema
FHR (5.2)
XLSX/CSV, two sheets
Enum domains; hsc_override ∈ 1–4; every service_code_map.fluid_code FK resolves; revision/approver present (REQ-IN-03); duplicate pid_service_code per unit_scope rejected
PSD (5.3)
XLSX/CSV or in-app form
declared_at + validity window; mandatory system_status rows for flare, closed drain, open drain, N₂, IA, steam, CW; tags resolve against the graph version (unresolvable tags are warnings listed to the declarer); active isolations parse into boundary-point ID lists
SIC (5.4)
YAML or controlled UI
Full parameter domain validation; matrix overrides require non-empty justification + approver (REQ-D-01); OSHA-aligned default profile ships as the base layer, client SIC is a delta over it (REQ-IN-08)
SAR (5.5)
XLSX/CSV
Radius stated in header; neighbour tags resolved where possible (unresolved = warning, retained as free text); zone/access enums
Scope (5.8)
tag list / NL / CMMS ref / graphical / system name
NL and CMMS routes go through iso-llm + Verification Gate; graphical selection returns node IDs natively; REQ-IN-16 attributes captured by a mandatory intake form (activity type, duration, shift coverage, containment break, man-entry, hot work, equipment off-site) — these feed EC derivation directly
Electrical Isolation Register (5.7)
XLSX/CSV
Only when electrical_isolation_mode = manual_input; tags resolve; merged into sequencing as externally-supplied steps (REQ-IN-13)
In-app PSD form: build the in-app form in Phase 1 alongside spreadsheet upload (open question 3 of the spec). The form is generated from the same JSON Schema as the spreadsheet validator, so both routes produce identical PSD objects. Spreadsheet upload remains for bulk/turnaround use.
### 4.3 Derivation Engine — HSC / EC / RBC (iso-core)
Implements Section 6 as a forward-chaining rule set over typed facts, but deliberately not a general-purpose rules engine.
Hand-written, strongly-typed rule functions in the core language (Section 9), one function per criterion row, registered in an ordered rule table — not Drools/CLIPS/etc. Rationale: the rule count is small (~30), auditability of code is a certification requirement (REQ-SA-02/06), and a third-party inference engine adds an unverifiable dependency to the safety case. The SIC provides the configurability the spec demands; the rule structure is code under MoC.
Pipeline per path:
PathFacts (fluid, phase, P/T, PSD state, scope attrs, SIC)
  → HSC classifier      : returns (hsc, firedCriterion, override?, depressurisedModifier?)
  → EC classifier       : returns (ec, driver, durationEscalation?)
  → RBC matrix lookup   : (hsc, ec) → cell, + SIC override w/ justification ref
  → Escalators          : positive-isolation-mandatory duration, small-bore rule (REQ-D-02),
                          barrier-confidence modifiers from L3 (REQ-FP-02),
                          service-pattern floors (HF: positive floor, non-overridable)
  → RBC result + full DerivationTrace fragment (REQ-D-09)
Rules fire in a fixed, documented order; the trace records every fired rule, every SIC parameter consumed (REQ-IN-07), and every escalation. hsc_override and UnknownFluid → HSC-4 short-circuit the classifier but still emit trace entries. The PSD depressurised-modifier records its dependency on the specific declaration row (declarer name propagates to the certificate per REQ-IN-04).
Non-overridable floors: L3 patterns can declare floor_non_overridable: true (HF per A4.2). The SIC override mechanism is structurally unable to lower these — the override applies before floors, floors apply last.
### 4.4 Traversal & Boundary Engine (iso-core)
The heart of the system (Section 7.1, REQ-F1-01..07).
Graph model for traversal: a directed multigraph traversed undirected (REQ-F1-02 — all paths regardless of nominal flow). Edge types: pipe_segment (carries line attrs: service, size DN, class, spec-break markers), inline_device (valve/check/RO/RD as edge or 2-degree node — we model devices as nodes for uniform trace referencing), instrument_tapping, annulus (jacketed lines), tracing, connector_stitch (off-page resolution). Every edge/node carries sheetRefs[] for rendering (AD-06).
Algorithm — boundary determination:
function determineBoundary(ctx, scopeNodes):
    frontier = expandScopeToWorkZone(scopeNodes)        # the T0 zone incl. items
                                                        # mechanically inseparable (CI-10)
    paths = enumerateBoundaryPaths(ctx.graph, frontier) # every edge leaving the zone,
                                                        # each grown outward as a Path
    solutions = []
    for path in paths (deterministic order: sorted by pathId):
        fluid  = resolveLiveSideFluid(path, ctx)        # incl. UnknownFluid handling
        rbc    = deriveRBC(path, fluid, ctx)            # Section 4.3
        sol    = findBarrierConfiguration(path, rbc, ctx)
        solutions.append(sol)                           # may be Satisfied | Expanded |
                                                        # PositiveRequired | NotIsolatable
    boundary = union(solutions)                         # REQ-F1-03
    boundary = cascadeEngine.apply(boundary, ctx)       # Section 4.5 (may re-enter
                                                        # this function for T1 expansion)
    patternEngine.check(boundary, ctx)                  # completeness discrepancies only
    return boundary
findBarrierConfiguration(path, rbc, ctx) walks outward along the path evaluating candidate point sets, nearest-first:
Collect devices on the path in order; classify each against the admissibility table (6.4) using device attributes + SIC policy (check_valve_role, actuated_valve_as_barrier, butterfly/HSC rule, soft-seat/hot-work rule). Admissibility verdict + rule ID goes in the trace.
For configurations needing two barriers: candidates must be in series on this path with a bleed candidate topologically between them — verified structurally, not by counting (REQ-D-03). Parallel-branch valves are rejected with an explicit trace entry.
Bleed verification (REQ-D-04): the bleed's own sub-path is traced to its destination; the destination's PSD status must be non-pressurised/safe. A bleed routing to a live closed-drain or flare header is rejected (S-21) and the search continues.
If no compliant configuration exists before the next equipment item: apply REQ-D-05 in order — (a) walk outward to the next candidate pair with a bleed (this is CI-1: the swallowed item becomes T1); (b) fall back to positive isolation at the nearest admissible joint — joint sourcing rule: if isometric extraction (REQ-IN-11) is present in the graph version use spool boundaries and full joint data; otherwise only P&ID flanged joints, and set the plan-level flag spoolOptionsNotAssessed (Section 5.6 of the spec); (c) if neither exists → NotIsolatable with the path, reason, and the plant-state alternative stated as information (REQ-F1-07, D-21 — the engine has no code path that proposes modifications).
Small-bore rule applied per penetrating connection ≤ small_bore_threshold_dn: valve + plug/cap/blind regardless of matrix (REQ-D-02).
Rating checks: blinds must meet the higher side of any spec break crossed (6.4); BOM attributes derived from piping class.
Special path semantics:
Check valves: never terminate a traversal; at most a secondary barrier under the SIC option, never for HSC≥3 or EC-D. The duty/standby cross-connection test (CI-2, S-01) falls out of this naturally: the path through the parallel train's check valve continues to the live header.
Package units: traversal terminates at declared battery-limit nodes (REQ-F1-06, REQ-DEP-04); the plan carries the vendor-manual disclaimer; the engine refuses to traverse "into" a package node even if internal edges exist in the graph (defensive check).
Nested/active isolations: existing boundary points from the PSD are recognised; if the new boundary lies inside an active isolation, generate incremental points only and re-validate the parent against the new RBC (REQ-F1-04, CI-12, S-29). Shared points → flagged protected/T4 (REQ-F1-05).
Instrument tappings, bridles, standpipes: modelled as first-class paths; level bridles contribute two paths (S-04, S-15).
Unresolved connectors: if a path reaches a node whose connector-resolution status is unresolved → path result = UnboundedLivePath; plan is not authorisable (REQ-XD-03). This is the only way a "drawing edge" can affect traversal, and it fails safe.
Determinism: path enumeration order, candidate ordering, and set iteration are all canonically sorted (by stable node/edge IDs). No hash-map iteration order leaks into output (Section 10).
Complexity & performance: worst case is bounded by boundary-local subgraph size, not site size. Target: single-item scope < 5 s of engine time on a 500 k-node site (well inside REQ-NF-01's 5-minute budget, leaving room for rendering and pattern checks). Site graph held in memory per tenant with copy-on-write PSD overlays; 500 k nodes ≈ low hundreds of MB.
### 4.5 Cascade Engine (iso-core)
Implements A2 (CI-1..CI-12, tiers T0–T4, recursion control).
Design: each cascade type is a detector (predicate over the boundary + graph + PSD overlay) plus a behaviour (tier assignment, action requirement, sequencing dependency, sub-plan generation, or authorisation block). Detectors run in a fixed order after each boundary computation pass.
Cascade
Detector sketch
Behaviour hooks
CI-1 barrier-unavailable
Emitted by findBarrierConfiguration when it expands past an item
Item → T1; boundary re-entered (recursion, bounded)
CI-2 shared header
Chosen point lies on an edge with >1 downstream consumer, or scope shares suction/discharge header with a parallel item
Parallel item → T2/T3; explicit duty/standby cross-connection test
CI-3 protective device
Point ∈ relief path of live equipment, or PSV/RD protecting live equipment ∈ boundary; uses PSV-to-protected relationships
Protected item → T2 with required-action record; authorisation blocked until action recorded (the highest-consequence rule in the engine). CSO/LO valves in relief paths: closing requires a recorded deviation (REQ-F5-02, S-10)
CI-4 utility supply
Boundary contains a supply edge whose consumers are live (seal flush, CW, lube oil, IA, N₂, tracing, fuel gas)
Consumers → T2/T3; seal-flush/lube-oil consumers get a hard sequencing edge: stop consumer before isolating supply
CI-5 process continuity
Scope in series in a process path
Upstream deadhead / downstream feed-loss → T2 with required action; required plant state stated (REQ-F5-04)
CI-6 control & safety
Boundary instruments participate in loops/interlocks/SIFs protecting other equipment (via C&E data, Section 4.9)
T2 if wholly defeated (block absent deviation), T3 if degraded; override requests generated
CI-7 disposal route
Depressurise/drain/purge route passes through or discharges into isolated/OOS/claimed systems (PSD)
Route owner → T4; plan cannot proceed as drafted if route unavailable — stated plainly
CI-8 physical access
SAR: access through/above/adjacent live equipment; lifts over live plant; hot work within adjacency radius
Adjacent items → T2 (isolate/shut down for hot work) or T3 (barricade/monitor); feeds hot-work permit (REQ-P-06)
CI-9 redundancy (inverse)
Scope ∈ a redundant set (duty/standby, A/B trains, fire pumps, detector coverage) — from driver/driven + parallel-train relationships + PSD availability
Remaining items → T4 protected, persisted in the register for the isolation's life and checked against every new plan (REQ-CI-05)
CI-10 mechanical coupling
Driver/driven, common shaft/gearbox, shared lube/seal systems
Coupled item → T1/T2; rotation prevention on both (in scope even when electrical is out of scope, REQ-F2-04)
CI-11 blinding access
Positive isolation requires breaking joint J; J not protected by an existing isolation
Generate a preparatory sub-plan (own sequence + hold point); recursive — sub-plan runs through the same pipeline with depth counted
CI-12 nested isolation
Boundary ⊂ active isolation (PSD)
Inherit + re-validate parent; incremental points only; parent points → T4
Recursion control (REQ-CI-02/03): only T1 expansion and CI-11 sub-plans recurse; T2/T3/T4 classification is single-pass. A depth counter (SIC-configurable, default 3) travels with every expansion; on breach the engine stops and emits the expansion path with the message "this scope cannot be isolated without an expanding boundary; a unit shutdown is likely required" — never a silently huge plan.
Output: a DependencyTree — nodes are affected items, each annotated with tier, the cascade rule that fired, the graph relationship it fired on, and the required action if T2 (REQ-CI-04). Rendered as the U1 cascade tree with T2 expanded by default (A8.3).
### 4.6 Pattern Engine — L2/L3/L4 (iso-core + content pipeline in iso-app)
Content pipeline: patterns are YAML files in a per-tenant, git-backed content store. CI validates them against JSON Schemas (one per layer); merge requires the MoC approval workflow (author, reviewer, approval record per REQ-EP-03); the merged library is hashed and becomes a pinnable artifact (AD-04). Base library ships as product content; client additions layer over it (open question A9.2 — the architecture supports both ownership models).
L2 execution (REQ-SL-02, REQ-EP-01/02): after traversal, for each equipment item in T0/T1, load its equipment_class pattern and compare expected_connections (role + cardinality + mandatory flag) against the connections the traversal actually found:
Missing mandatory connection → completeness discrepancy, blocks authorisation until resolved as "drawing incomplete" or "confirmed absent" (each resolution is an audited decision).
Extra connections found → included in the boundary regardless; the pattern never restricts (REQ-EP-02).
Pattern-supplied residual_energy, mandatory_holds, sequence_constraints, independent_boundaries, bom_additions feed the respective engines. independent_boundaries (e.g. shell/tube sides, process/firing sides) instructs the boundary engine to partition the item's paths into separate certificated boundaries (A3.2, A3.4).
Connection-role matching: roles (shell_inlet, seal_flush, …) are matched via a role-classification function using edge service codes, connected-line attributes, and nozzle metadata from UniGraph, with an explicit per-site role-mapping override table for non-standard tagging. Unmatchable expected roles degrade to a discrepancy, never a silent pass.
L3 execution: joined by fluid_code/service_class; contributes HSC floors, prohibitions, additional steps, BOM/permit/gas-test additions, sequence inversions (hard DAG edges, AD-08), and barrier-confidence modifiers (REQ-FP-02: solids/polymerising/coking/molten/sour-FeS services escalate the RBC one level or force positive isolation).
L4 execution: unit-type patterns contribute advisory hazards, extra expected items and T4 declarations (e.g. hydrotreater recycle compressor, alkylation rapid-de-inventory systems).
Conflict resolution (REQ-SL-03): most conservative wins, computed on a defined severity ordering of barrier configurations (1 valve < valve+bleed < DBB < DBB+positive < disconnection+double blind); sequence inversions override generic sequencing; every conflict + resolution → trace.
### 4.7 Sequencing Engine (iso-core)
Model (AD-08): every plan step is a node; ordering constraints are edges with provenance:
Generic safety rules (REQ-F6-02) as edge templates: stop→isolate, isolate-process→break-joint, remove-rotation→work, depressurise→drain, drain→purge, far-joint-first, prove-upstream→install-blind.
Pattern sequence_constraints (L2) and sequence inversions (L3) as hard edges — molten sulphur "jacketing stays live until drained" blocks the generic "isolate utilities first" edge and the conflict is traced (REQ-FP-01).
Cascade sequencing dependencies (CI-4 stop-consumer-first; CI-11 preparatory sub-plan before blind).
Hold points (REQ-F6-04) as gate nodes requiring sign-off events: zero-pressure proved, pre-man-entry, pre-hot-work, pre-final-blind-removal, pre-repressurisation, plus pattern mandatory_holds (cool-down targets, prove-both-sides).
Topological sort with a canonical tie-breaker (area → discipline → tag) yields the numbered sequence (REQ-F6-01: step no., action, tag, device, end position, lock/tag, role, verification, predecessors). A cycle = a genuine contradiction → surfaced as a plan error with the conflicting edges named, never silently broken.
Reinstatement (REQ-F6-03): generated as its own DAG — explicitly not a reversal: blind reconciliation by unique ID (count-in = count-out), override removal + protective-function restoration and functional checks, leak/tightness test, purge/seal re-establishment, valve-by-valve confirmation against normal position, controlled re-pressurisation steps from L3 (oxygen slow-repress, steam warm-up). Partial reinstatement/re-isolation (REQ-F6-05, S-40): the engine recomputes the minimal boundary for the remaining scope and diffs point sets to produce selective removal steps, re-validating the reduced boundary's RBC.
### 4.8 Residual Energy & Depressurisation Planner (iso-core)
Implements 7.2 and 7.4. Runs over the inside of the boundary:
Inventory & trapped liquid: line/equipment volumes (isometrics where available) + low-point analysis (is_low_point, drain_at_low_point). Low point with no drain → trapped-liquid flag + controlled joint-break requirement (REQ-F2-03). Dead legs flagged specifically for polymerising services (L3).
Head, thermal, cryogenic: elevation data → static head; L3/L2 thermal holds; cryogenic re-vent cycle (S-24 sequence inversion).
Mechanical & chemical: spring/accumulator/rotation from device attributes and patterns; FeS/catalyst/polymer from L3/L2; the inert-vs-breathable-atmosphere conflict for pyrophoric entry surfaced as an explicit transition procedure requirement (S-23), never auto-resolved.
Depressurise/drain/purge routes (REQ-F4-01..05): route search over vent/drain/purge connections with destination status from the PSD overlay; volumes estimated; purge cycles/targets from SIC; N₂ → asphyxiation flag + air-freeing requirement; gas-test points, acceptance criteria and retest intervals from SIC.
### 4.9 Instrument, Control & Safety-System Module (iso-core, data via Drawing & Document Agent)
Impulse-line isolation from tapping/manifold topology; DP-manifold ordering emitted as sequence edges (REQ-F3-01, S-14).
Loop/interlock consequence from loop-membership relationships (REQ-F3-02); final-element fail positions vs isolated utilities enumerated inside and outside the boundary (REQ-F3-05, S-18).
C&E integration (REQ-DEP-05): the Drawing & Document Agent publishes C&E matrices in queryable form (initiator → action → affected element, with voting). This module consumes that as structured graph data, pinned in the snapshot like everything else — the LLM extraction happened upstream, so its output is already frozen, reviewable content, not live inference (consistent with REQ-ARCH-02).
Voting degradation analysis (2oo3→1oo2 OK; 1oo1→defeated); wholly-defeated SIF → authorisation block absent a recorded deviation; max inhibit duration from SIC (REQ-F3-04). Override requests are generated artifacts tracked to reinstatement reconciliation — no register write-back in v1 (D-11 decision adopted as designed).
Safety-critical element impairments (fire water, deluge, F&G, ESD valves, relief) → impairment records with compensating measures (REQ-F3-06, S-16).
### 4.10 Impact Analysis Module (iso-core)
Implements 7.5 over the live-side graph: consumers deprived, deadheads/block-ins, cooling/flush/purge losses, minimum-flow losses (REQ-F5-01); relief-path integrity check (REQ-F5-02) — a dedicated verifier that walks every live item's relief path and asserts no boundary point blocks it; last-train/last-fire-pump/last-detector availability from PSD (REQ-F5-03, report-only per D-21); plant-mode feasibility (REQ-F5-04); SIMOPS conflicts vs active isolations/permits (REQ-F5-05).
### 4.11 Permit Generator — M3 (iso-core structure + iso-llm prose)
Permit structure and every safety-relevant field are deterministic: type enablement from SIC, hazards from FHR for the fluids present, isolation reference + proving status, gas-test regime, fire-watch, confined-space controls, adjacency/SIMOPS conflicts, validity. LLM contributes only narrative work descriptions, typed llm_generated.
Permit ⇄ isolation coupling: a permit cannot exist without a valid isolation reference where required (REQ-P-02); validity ≤ proving validity, re-validation synchronised with re-proving (REQ-P-04, S-38) — implemented as a shared validity clock object on the plan.
Cross-permit conflict detection (REQ-P-05, S-37): spatial joins over the SAR adjacency lists between concurrent permits (hot work vs line-break radius; CSE vs purging; radiography vs occupancy).
Hot work without a SAR entry: permit generation refuses; adjacency assessment listed as a mandatory manual step (REQ-IN-09, REQ-P-06, S-36).
Permits are always drafts; there is no "issued" transition in this system (REQ-P-08).
### 4.12 Emergency Mode — M2 (iso-emergency)
Separate service, per-site flag, default off (REQ-E-02).
Pre-warmed state (AD-07): on graph/PSD update, the service rebuilds: (a) an in-memory snapshot; (b) a remote-operable device index (ESDV/SDV/BDV/MOV with initiating actions); (c) reverse-reachability structures so "what feeds node X" resolves in milliseconds; (d) per-segment inventory volumes; (e) SAR accessibility lookups.
Request path: NL event description → iso-llm triage (event type, location entity, magnitude, personnel) with the Verification Gate resolving the location to graph entities → deterministic analysis, streamed progressively (REQ-E-13):
< 10 s: remote isolation options that stop/limit flow to the release point, ranked by time-to-effect (REQ-E-05/06).
Residual feeding inventory between closed devices and the leak, from volumes (REQ-E-07); blowdown route + destination (REQ-E-08).
Manual points marked accessible / likely inaccessible from SAR proximity, congestion and access route (REQ-E-09); escalation targets within the SAR radius ranked by inventory/consequence (REQ-E-10); consequences of each action stated as information (REQ-E-11).
Degraded operation: no data-sufficiency gates; missing PSD → assume all live, stated in the output (REQ-E-04, REQ-E-12, S-34). Every request and response logged in full to the audit ledger (REQ-E-14). The service has no code paths for actuation, entry instruction, or permit output (REQ-E-15), and every response frame carries the advisory/subordination banner (REQ-E-01). Distinct UI shell per A8.7.
### 4.13 LLM Orchestration & Verification Gate (iso-llm)
iso-llm implements the three scoped NL entry points of Section 1.2 plus narrative generation. It is a translation and rendering service, not an agent loop: there is no autonomous multi-step tool use, no LLM-initiated plan mutation, and no conversational session state that influences plan content — every invocation is a bounded request/response around a deterministic operation.
Permitted functions (REQ-ARCH-02): NL scope interpretation, ambiguous tag resolution, document extraction routing (to the Drawing & Document Agent), explanation/narrative generation from derivation traces, permit prose, plan interrogation (REQ-F8-02), emergency triage.
Verification Gate (AD-05):
Entity channel: candidate tag/entity references → exact-match, then normalised-match, then fuzzy candidate lists against the pinned graph; anything below exact match returns candidates to the user for confirmation; only confirmed node IDs pass. Unresolvable references never silently drop — they surface as "unrecognised reference" items.
Text channel: narrative fields typed llm_generated, stored with the prompt/template version, rendered in a visually distinct style in every surface and export (REQ-ARCH-03).
No numeric channel: the gate has no pathway for the LLM to set an HSC, a barrier count, a sequence position, or any derived value. This is enforced by the type system of the plan model, not by convention.
Interrogation (REQ-F8-02, U1 interrogation bar, U2 what-if): questions are parsed to one of a fixed catalogue of deterministic query intents — why_point(tag), consequence_if_open(tag), paths_to_live_source(zone, fluid_class), recompute_with(duration|activity|state-change), trace_path_across_sheets(pathId) (REQ-XD-14). The DSC executes the query (what-if runs a full re-derivation on a modified context and diffs); the LLM renders the structured answer as prose. Answers logged. Questions that don't map to an intent get an honest "can't answer that from the plan model" rather than a generated guess.
Model access: Anthropic API (the platform standard); prompt templates version-controlled and hash-pinned per plan (REQ-SA-03 "any model used in peripheral functions").
### 4.14 Plan Lifecycle & Authorisation (iso-app)
State machine (REQ-OM-03): Draft → Authorised → Issued → Being Set → Set & Proved → Active → Being Removed → Reinstated → Closed, plus Superseded (reachable from any post-Draft state via re-derivation). Transitions are ledger events with actor, timestamp, and — for Authorised — the exact hash set of plan version, graph version, rule-engine build and SIC/FHR/PSD/SAR/pattern revisions (REQ-OM-04).
Invalidation (REQ-OM-05): the authorisation record binds to input hashes. Any input change → authorisation invalid → forced re-authorisation with a classified diff: the diff engine compares plan models structurally and classifies each change safety-significant or not via a rule table (boundary point add/remove/method change, RBC change, sequence-edge change, hold-point change = significant; narrative text, formatting = not). Diff view is the default on re-authorisation (A8.3).
Authorisation gating — the authorise action is disabled until zero outstanding: blocking data gaps (unknown fluids, unresolved connectors, completeness discrepancies, expired PSD with the stale rows listed per S-31), unacknowledged deviations/assumptions/impairments/overrides (individually acknowledged, no bulk accept — REQ-UX-N01, P5), unrecorded T2 actions (CI-3/CI-6 blocks), and missing multi-area authorisers (REQ-XD-07: the plan computes its area set from point locations; each area's isolation authority must sign; the schedule is grouped per area).
Failed proving (REQ-D-08, S-30): a field cannot_complete/pressure_on_bleed event triggers automatic re-derivation with the failed valve marked non-seating (a state-overlay mutation → new context → new plan version), supersedes the original (rendered non-executable everywhere, exports watermarked SUPERSEDED), and forces re-authorisation.
Shift handover (REQ-OM-06) and the U4 register are ledger projections: per-isolation point-state rollups, T4 protected sets (checked on every new plan draft — REQ-CI-05), re-prove due dates, expiries.
### 4.15 Export Service & Adapters (iso-app)
Canonical schema (REQ-F7-07, D-03): a versioned JSON Schema (XML rendering derivable) covering plan, boundary, schedule, sequence, BOM, permits, assumption/gap/deviation register, dependency tree, traces. Internal model → canonical is the only supported direction; adapters (Maximo work-order operations, SAP PM order/permit objects) map from canonical only, so the core never depends on either CMMS model. Adapter conformance tested with golden-file suites.
Document exports (AD-09): certificate (site template engine — templates are SIC-referenced content), isolation schedule, per-sheet marked-up P&IDs (REQ-F7-02 — rendered from source-drawing coordinates via REQ-DEP-01, with continuation markers per REQ-XD-11), boundary schematic (REQ-XD-12), BOM, effort estimate (REQ-F7-06 from SAR scaffold/elevation data). All exports: state watermark, full version footer, and a QR/plan-version code resolving to current validity (REQ-UX-E01..03); monochrome-legible print styles (REQ-UX-A04).
### 4.16 UX Surfaces (iso-web, iso-field)
Built to A8 as specified; engineering notes only:
U1 Plan Review: header provenance strip binds directly to the plan's hash set; the must-read panel is a projection of the gating query in 4.14, so the disabled authorise button and the panel can never disagree ("4 items require acknowledgement" is the same query). Critical-item screen position is randomised per session from a seeded shuffle (P5) — the seed is logged so sessions are reproducible in audit.
U2 Boundary Explorer: P&ID overlay uses Convert P&ID coordinates; continuation-marker navigation loads the next sheet centred on the counterpart connector (REQ-XD-13); "trace to live source" animates the deterministic path query; the what-if control calls the recompute intent (4.13) and renders a boundary diff. Filters and per-sheet point counts from the plan model.
U3 Field Execution: offline-first PWA on IS-rated Android tablets, with a printed-pack export as the degraded fallback so the answer to "operators carry nothing" is a product configuration, not a redesign. One step per screen; tag number largest; equal-weight Confirm / Cannot-complete (P6); proving as a separate step with value entry + live decay timer; blind IDs scanned/entered with mandatory photo; sequence locks enforced client-side from the DAG, supervisor override logged; explicit unsynced-queue indicator; 48 px targets, high-contrast mode, dual-channel severity encoding (REQ-UX-A01/A03).
U4 Register: ledger projections (4.14).
Emergency shell: separate route, distinct visual system, streaming answers, no auth flow/exports (A8.7).
Anti-requirements REQ-UX-N01..N07 are encoded as lint rules in the design system where mechanically checkable (no bulk-dismiss component exists; no global "complete" badge component exists; colour-only encodings fail component review).
Offline sync (AD-10): field events (confirmations, proving values, discrepancy reports, photos) queue locally as signed, timestamped, append-only facts; sync replays them into the ledger; conflicts (e.g. a step confirmed on two devices) resolve by server arbitration with both facts retained and flagged to the supervisor. The plan itself is read-only on the device; only facts about execution originate there.
## 5. Data Model
### 5.1 Core plan model (simplified)
Plan
├── planId, version, mode (M1|M2|M3), lifecycleState
├── inputHashes { graph, fhr, sic, psd, sar, patterns, ruleEngineBuild, promptSet }
├── scope { nodes[], activityType, duration, shiftCoverage, containmentBreak,
│           manEntry, hotWork, equipmentOffSite }               # REQ-IN-16
├── boundaries[]                    # ≥1; independent_boundaries split here (A3.2)
│   ├── paths[]
│   │   ├── pathId, edgeSequence[], liveSideFluid {fluidCode|UNKNOWN}
│   │   ├── hsc {value, firedCriterion, override?, psdModifier?}
│   │   ├── ec  {value, driver, escalations[]}
│   │   ├── rbc {cell, sicOverride?, floors[], confidenceModifiers[]}
│   │   └── result: Satisfied | Expanded(→T1) | PositiveRequired
│   │             | NotIsolatable(reason) | UnboundedLivePath(connectorRef)
│   └── isolationPoints[]
│       ├── pointId, nodeId (graph FK — never free text), method, requiredPosition
│       ├── lock {type, colour, tagNumber}, sequenceNo, discipline
│       ├── proving {method, criteria, holdMinutes, reProveIntervalHours}
│       ├── location {sheet, gridRef, area, elevation, accessType}   # SAR/iso join
│       ├── provenance: GraphDerived | DeclarationDependent(declarer)
│       │             | ConservativeDefault | UnverifiedGap          # P4
│       └── derivationTrace (REQ-D-09, machine-readable, renders to prose)
├── dependencyTree { items[]: {nodeId, tier T0..T4, firedRule, relationship,
│                    requiredAction?, actionRecorded?} }             # A2
├── sequences { isolation: DAG, reinstatement: DAG, holdPoints[] }
├── residualEnergy[], depressurisationPlan, drainPlan, purgePlan, gasTests[]
├── impactAnalysis { deprivedConsumers[], deadheads[], reliefIntegrity,
│                    availability[], plantModeFeasibility, simops[] }
├── registers { assumptions[], gaps[], deviations[], impairments[],
│               overrideRequests[], completenessDiscrepancies[],
│               crossDrawingIssues[] }                               # REQ-F7-05
├── blindRegister[] {blindId, size, rating, facing, material, installedPhoto?,
│                    installedAt?, removedAt?}                       # S-39
├── permits[] { type, fields (deterministic), narrative (llm_generated),
│               validityClockRef }                                   # REQ-P-04
├── bom[], effortEstimate
├── drawingIndex[] {sheet, revision, pointCount, areas[], crossings[]} # REQ-XD-10
└── llmContent[] { fieldRef, text, promptVersion }    # the ONLY LLM-writable store
### 5.2 Graph adjacency model (in-memory, iso-core)
Immutable, index-backed structure built by the Snapshot Assembler:
nodes[]: typed (equipment, valve subtype, instrument, joint, connector, battery-limit, header segment) with attribute bags from UniGraph (5.1 of the spec: valve type/actuation/fail/normal position/lockability, PSV relationships, driver/driven, loop/SIF membership, isometric fields where present).
edges[]: typed as in 4.4, undirected traversal with nominal-direction metadata retained (needed for check-valve semantics and deadhead analysis, not for path pruning).
Indexes: tag→nodeId, node→incidentEdges (sorted), header membership, relief-path membership, redundancy groups, remote-operable set, sheet→entities.
PSD overlay: copy-on-write layer; the base graph is shared across concurrent plans of a tenant.
### 5.3 Audit ledger
Append-only event store per tenant: {eventId, planId, type, actor, role, timestamp, payload, priorEventHash} — hash-chained for tamper evidence (REQ-NF-03). Event types cover the full lifecycle, edits, acknowledgements, field facts, interrogations, emergency queries, exports. Projections: current plan state, U4 register, handover view, blind reconciliation status.
### 5.4 Storage
Store
Technology (recommendation)
Contents
Relational (PostgreSQL, schema-per-tenant)
Plans (JSONB model + relational projections), ledger, users/roles, input registrations, validity clocks
System of record
Object store (S3-compatible, per-tenant prefix + KMS key)
Input artifacts (FHR/PSD/SIC/SAR files), pattern library bundles, graph snapshots, photos, rendered exports
Content-addressed by hash (AD-02)
In-memory graph (per iso-core instance)
Materialised adjacency model per tenant/graph-version, LRU-managed
Performance
Pattern content repo (git)
L2/L3/L4 YAML + schemas + MoC metadata
AD-04
No dedicated graph database in v1. The traversal workload is bounded-neighbourhood, read-only, latency-critical and determinism-critical — a bespoke in-memory structure over snapshot files beats a general graph DB on all four axes and removes a certification-relevant dependency. UniGraph remains the upstream source of truth in whatever store it uses; iso-core consumes exported, versioned snapshots.
## 6. Key Algorithms — Reference Pseudocode
### 6.1 Series DBB verification (REQ-D-03)
function verifySeriesDBB(path, b1, b2):
    assert b1, b2 ∈ path.deviceSequence            # same flow path, by construction
    assert index(b1) < index(b2)                   # in series along the path
    segment = path.edgesBetween(b1, b2)
    bleeds = branchesOff(segment) where isBleedCandidate(branch)
    for bleed in bleeds (canonical order):
        dest = traceToDestination(bleed)
        if psdStatus(dest) in {depressurised, safe_open}:  return OK(bleed, dest)
        else: trace.reject(bleed, "destination live: " + dest.tag)   # S-21
    return NoValidBleed                            # triggers REQ-D-05 ladder
### 6.2 Cascade recursion bound (REQ-CI-02/03)
function applyCascades(boundary, ctx, depth=0):
    tree = classifyTiers(boundary, ctx)            # single-pass T2/T3/T4 detectors
    expansions = t1Expansions(tree) ∪ ci11SubPlans(tree)
    if expansions.isEmpty(): return finalize(tree)
    if depth ≥ ctx.sic.cascadeDepthLimit:          # default 3
        return AbortWithExpansionPath(tree, expansions,
               "unit shutdown likely required")
    boundary' = recomputeBoundary(ctx, boundary.scope ∪ expansions.t1Items)
    return applyCascades(boundary', ctx, depth+1)
### 6.3 Reproducibility contract (REQ-F8-04)
All collection iteration in iso-core over sorted, stable IDs; no map-order dependence (enforced by a custom lint rule banning raw hash-map iteration in the core module).
Canonical serialization: UTF-8, sorted keys, fixed number formatting, no timestamps of generation inside the plan body (generation metadata lives outside the hashed payload).
Time enters exactly once, via PlanContext.timeContext set at snapshot assembly.
CI job: generate every regression-scenario plan twice on different machines; byte-compare. Divergence fails the build.
## 7. API Design (iso-app public surface, REST + SSE)
Endpoint
Purpose
`POST /inputs/{fhr
psd
POST /plans {scopeRef, mode, inputRefs} → planId; GET /plans/{id} (model), /trace/{pointId}, /diff/{v1}/{v2}
Plan generation & retrieval
POST /plans/{id}/transitions {target, actor} — server enforces state machine + gating
Lifecycle
POST /plans/{id}/acknowledgements {itemRef} (one item per call — no bulk endpoint exists, REQ-UX-N01)
Must-read gating
POST /plans/{id}/interrogate {question} → SSE answer + logged
REQ-F8-02
POST /plans/{id}/whatif {mutations} → boundary diff
U2 what-if
POST /field/sync (batch signed field facts) → arbitration results
U3
POST /emergency/query → SSE progressive frames
M2 (separate service, same gateway)
GET /plans/{id}/exports/{artifact}?format=
AD-09
GET /register (active isolations, T4 sets, conflicts)
U4
AuthN: OIDC (site IdP federation); AuthZ: role model {planner, field operator, isolation authority (per area), permit authority, supervisor, process safety engineer, admin} with per-area scoping to support REQ-XD-07.
## 8. Technology Stack (recommendation)
Layer
Choice
Rationale
iso-core language
Kotlin/JVM (alt: Rust)
Strong typing for the trace/provenance model, mature test/coverage tooling for the assurance case (REQ-SA-02), deterministic behaviour achievable with the Section 6.3 contract; Rust if the team prefers — the architecture is language-agnostic but demands static typing, and rules out dynamically-typed cores
iso-app, iso-llm, iso-field backend
Kotlin or TypeScript/Node
Team-standard; not safety-core
Frontends
TypeScript + React; U3 as PWA (service worker, IndexedDB queue)
Offline-first requirement
P&ID/schematic rendering
SVG overlay engine on Convert P&ID coordinate output; boundary schematic as a bespoke radial layout component (REQ-XD-12)
A9.1 flags this as the highest-risk UX assumption — build behind a feature flag and validate with real isolation authorities early
Rule/pattern content
YAML + JSON Schema + git + CI validation
AD-04
Persistence
PostgreSQL, S3-compatible object store
5.4
Messaging
Postgres-backed outbox → lightweight broker only where needed (export jobs, snapshot refresh)
Avoid infrastructure the safety case must explain
LLM
Anthropic API via iso-llm; prompts hash-pinned
4.13
## 9. Multi-Tenancy & Security
Hard partition (REQ-NF-04): schema-per-tenant Postgres + per-tenant object-store prefix with per-tenant KMS keys; per-tenant in-memory graph spaces; no shared caches across tenants; tenant ID derived from the auth token server-side only, never from request bodies.
Per-tenant SIC, FHR, SAR, pattern layers, certificate/permit templates, and feature flags (emergency_mode_enabled, electrical_isolation_mode).
Field devices: device registration + short-lived signed sync tokens; queued field facts signed on-device.
Full audit of admin/config changes through the same ledger.
Data residency configurable per tenant at deployment.
## 10. Testing, Assurance & MoC (REQ-SA-01..08)
### 10.1 Test architecture
Level
Content
Unit
Every derivation rule, admissibility rule, cascade detector, sequencing template — one test module per rule ID; requirements-to-test traceability matrix generated from annotations (REQ-SA-02)
Property-based
Traversal invariants: boundary closure (no path from work zone to live inventory without crossing a satisfied configuration), monotonicity (adding hazard never shrinks the boundary), pattern-never-restricts (REQ-EP-02), recursion bound respected
Scenario regression (REQ-SA-05, REQ-SL-04)
Generator produces the {equipment class} × {service class} × {exposure class} × {cascade type} cross-product over synthetic plant models; curated subset ≥200 cases with expected boundary, barrier configuration, cascade set and discrepancies as golden files; the 40 v1.0 scenarios (S-01..S-40) implemented as named acceptance cases on top. Family G failures block release; S-32 (over-isolation) and S-07 are explicit anti-conservatism gates
Reproducibility
Section 6.3 double-build byte-compare
Determinism fuzz
Randomised input orderings (row order in FHR/PSD files, node insertion order) must not change output bytes
UX
Gating logic (authorise-button state = must-read query), no-bulk-accept, provenance rendering, offline sync replay tests
### 10.2 Synthetic plant models
A library of hand-built test plants (per equipment pattern + composed units) with known-correct isolation answers reviewed by a process safety engineer (feeds REQ-SA-06 independent verification). Stored as graph fixtures alongside golden plans.
### 10.3 MoC pipeline (REQ-SA-04)
Changes to the derivation model, admissibility table, RBC matrix or pattern schemas: PR → independent process-safety review recorded → full regression suite → release notes enumerating rule changes → new ruleEngineBuild hash. Pattern content changes follow the content-repo MoC (4.6) with the same regression gate. No auto-update channel exists; sites adopt versions explicitly.
### 10.4 Classification support (REQ-SA-01)
Engineering deliverables for the safety case: architecture description (this document), determinism contract + evidence, traceability matrix, regression results per release, SBOM per iso-core build, tool-validation strategy positioning the system as an offline support tool under IEC 61511 cl. 11 — agreed per client.
## 11. Performance & Scale Engineering (REQ-NF-01/02)
Budgets: M1 single-item ≤ 5 min (engine target < 5 s, rendering/pattern checks/export the remainder); M1 system scope ≤ 30 min (parallel per-path evaluation — safe because paths are independent until union; the union step is single-threaded and canonical); M3 ≤ 5 min; M2 first frame < 10 s via AD-07.
500 P&IDs / 500 k nodes per site: in-memory model sized and benchmarked at 1 M nodes in CI.
500 concurrent active isolations: register projections indexed; T4 conflict check is an indexed set intersection per new plan.
Latency optimisation beyond budgets is explicitly deferred (D-20) — budgets are correctness requirements, tuning is not Phase 1 work.
## 12. Delivery Plan (mapped to spec Section 14)
Phase
Engineering scope
Exit criteria
1 — Planned isolation core
iso-core (snapshot, derivation, traversal, cascade CI-1/2/4/5/7/9/10/12, L2/L3 pattern engine, sequencing, energy planner, impact), input services incl. in-app PSD form, lifecycle/authorisation/ledger, U1 + U2 (no what-if), schedule/certificate/BOM exports, boundary schematic behind a flag
Scenario families A–G green in the regression suite; reproducibility gate green; independent process-safety review of the derivation model complete
2 — Permits & instruments
SIS/C&E module, CI-3/CI-6 full behaviour incl. authorisation blocks, override request tracking, SAR-driven hot-work assessment, permit generator + validity coupling + cross-permit conflicts, U1 must-read extensions
Families D, I green; permit golden files approved against ≥2 real certificate templates (spec open question 5)
3 — Emergency & field
iso-emergency incl. pre-warm pipeline and streaming UI shell; iso-field PWA + sync + blind scanning/photos; failed-proving re-derivation loop; U4 register; printed-pack fallback
Families H, J green; M2 latency budget met under load; offline sync soak test
4 — Integration & electrical
Canonical schema freeze + Maximo/SAP adapters; isometric-derived geometry consumption (unlocks spool-based positive isolation — until then spoolOptionsNotAssessed stands); electrical_isolation_mode = manual_input then sld_graph when Convert-for-SLD lands; U2 what-if GA
Adapter conformance suites green; spool-planning scenarios added to regression
Team shape (per Section 1.2): this is an application build, not an agent build. Recommended workstream split from Phase 1: (a) safety-core engineering (iso-core + regression suite), (b) application & data engineering (iso-app, inputs, lifecycle, exports), (c) frontend/UX for U1–U4 and the emergency shell — staffed as a first-class workstream, not a wrapper, including early validation of the boundary schematic and field-view ergonomics with real users, (d) a small iso-llm effort scoped strictly to the three NL entry points. LLM work is deliberately the smallest of the four.
Cross-phase blocking dependencies to track weekly: REQ-DEP-06 (isometric extraction — blocks spool positive isolation beyond P&ID flanges), REQ-DEP-05 (queryable C&E — blocks Phase 2), REQ-DEP-01/02 (drawing coordinates + valve annotations — blocks mark-ups and admissibility fidelity), off-page connector resolution fidelity in Convert P&ID (A9.5 — if resolution is weak, REQ-XD-03 will block plans frequently; instrument this from day one and report resolution rates per site).
## 13. Engineering Risks & Open Items
#
Risk / open item
Mitigation in this design
1
Off-page connector resolution rate unknown (A9.5)
Admission-check telemetry from first ingest; a per-site "connector health" report before any planning is attempted
2
Boundary schematic is an unvalidated UX bet (A9.1)
Built behind a flag in Phase 1; validated with ≥2 real isolation authorities before it becomes the default review artifact
3
Field hardware unknown (A9.4)
PWA + printed-pack dual output; no native-app commitment until hardware confirmed
4
Pattern ownership undecided (A9.2)
Layered content model supports product-owned base + client-owned overlay; decision is configuration, not architecture
5
Multi-area authorisation practice unknown (A9.3)
REQ-XD-07 implemented with a per-site toggle: multi-authority or single-authority-with-area-grouping
6
FHR ownership / onboarding (spec Q2)
FHR pipeline includes an onboarding-assist mode: draft FHR rows generated from line lists + SDS via the Drawing & Document Agent, always human-approved before registration
7
OSHA default profile sign-off (spec Q6)
Default SIC ships as a controlled document with its own approver field; release blocked until a named process safety engineer signs the profile
8
Blind register ownership (spec Q1)
Plan-scoped blind register + reconciliation implemented in-product (S-39 needs it); canonical export includes blind records so a site register can consume them — ownership decision deferred without blocking
9
Emergency mode appetite (spec Q4)
Default-off flag; identical engine usable in a "drill mode" against hypothetical events — a pre-incident positioning is a config change
## 14. Traceability
Every requirement ID in spec v1.0 and Addendum A maps to at least one section of this document; the machine-readable traceability matrix (requirement → design element → test module) is generated from source annotations and ships with each release (Section 10.1). Gaps in the matrix fail CI.
— End of document —