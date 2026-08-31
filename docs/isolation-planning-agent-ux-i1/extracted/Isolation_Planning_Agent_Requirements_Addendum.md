# Isolation Planning AI Agent — Addendum A
Scenario Library Architecture, Cascading Isolation, Cross-Drawing Boundaries, and Output UX
Version: 1.0 Status: Supersedes Section 10 of the main specification. Adds Sections 16 and 17.
## A1. What Changed and Why
Section 10 of v1.0 listed forty illustrative scenarios — useful as acceptance tests, but the wrong shape for a development team, because a hand-written list can never be complete and gives no structure for extension.
This addendum replaces it with a four-layer scenario model, where scenarios are data, not code:
Layer
Name
Keyed on
Purpose
L1
Cascading isolation rules
Graph relationships
Determines when isolating one item forces action on another
L2
Equipment isolation patterns
Equipment class
Completeness checklist per equipment type
L3
Service / fluid patterns
fluid_code, service class
Fluid-specific steps, prohibitions, escalations, sequence inversions
L4
Process unit patterns
Unit type
Unit-specific known hazards and configurations
REQ-SL-01 All four layers shall be implemented as versioned, human-readable rule/pattern files (YAML), editable by a process safety engineer without code changes, under the same MoC as the derivation model (REQ-SA-04).
REQ-SL-02 — Layers are checks, not substitutes. The graph traversal (Section 7.1) remains the authoritative boundary generator. L2/L3/L4 patterns run as an independent completeness check over the traversal result. Where a pattern expects something the traversal did not find, the agent raises a discrepancy — it does not silently add it.
This redundancy is one of the strongest safety mechanisms in the system: two independent mechanisms — topological traversal and type-based expectation — must agree. Disagreement means either the graph is incomplete or the traversal has a defect. Both are things you want to know.
REQ-SL-03 — Conflict resolution. Where layers conflict, the most conservative requirement wins, except for sequence inversions (L3), which are hard constraints overriding generic sequencing rules (REQ-F6-02). All conflicts and their resolutions appear in the derivation trace.
## A2. Layer 1 — Cascading Isolation
### A2.1 The problem
"Isolate P-1201A" is almost never a single-item job. Isolating one item creates obligations on others, for at least twelve structurally distinct reasons. If the agent models only the boundary, it will produce technically correct isolations that are operationally unusable or unsafe.
### A2.2 Impact tiers
REQ-CI-01 Every plan shall classify affected items into four tiers, and shall present them as a dependency tree:
Tier
Meaning
Agent obligation
T0
The work scope
Isolate
T1
Inside the boundary as a consequence
Isolate; include in schedule
T2
Outside the boundary but requiring action (shutdown, mode change, alternative protection)
Specify the required action; do not plan its isolation unless it needs one
T3
Outside the boundary, degraded or deprived but requiring no action
Report as impact
T4
Protected — must not be isolated or disturbed while this isolation is active
Flag as locked; block conflicting plans
### A2.3 Cascade types
Each is a detection rule over the graph plus a defined behaviour.
CI-1 — Barrier-unavailable cascade Detection: No admissible barrier configuration exists on a path before reaching the next item. Behaviour: Boundary expands outward to swallow the intervening item, which becomes T1. Report explicitly: "no compliant barrier between the work scope and E-1301; E-1301 is therefore inside the boundary."
CI-2 — Shared-header cascade Detection: The chosen isolation point lies on a header serving other items; or the work scope shares suction/discharge/feed headers with parallel equipment. Behaviour: Parallel items become T2 or T3 depending on whether they lose containment integrity or merely lose service. Explicitly test the cross-connection between duty and standby — a check valve is not a boundary (Section 6.4).
CI-3 — Protective-device cascade Detection: An isolation point lies in the relief path of live equipment, or a PSV/rupture disc protecting live equipment falls inside the boundary. Behaviour: The protected equipment becomes T2 — it requires action (shutdown, alternative relief, rate reduction) before the isolation can be set. The agent shall block plan authorisation until the action is recorded. This is the single most consequential cascade type and the one most often missed manually.
CI-4 — Utility-supply cascade Detection: The work scope or the boundary supplies a utility consumed by other items: seal flush, quench, barrier fluid, cooling water, lube oil, instrument air, nitrogen blanket, purge, steam tracing, fuel gas. Behaviour: Consumers become T2 (cannot continue running) or T3 (degraded). For seal-flush and lube-oil dependencies specifically, the consumer must be stopped before the supply is isolated — a sequencing dependency, not merely an impact.
CI-5 — Process-continuity cascade Detection: The work scope is in series in a process path. Behaviour: Upstream items may deadhead or block in; downstream items lose feed. Both become T2 with the required action stated. The agent reports the required plant state (REQ-F5-04) but does not propose reconfiguration (D-21).
CI-6 — Control and safety cascade Detection: Instruments or final elements inside the boundary participate in loops, interlocks or SIFs protecting other equipment. Behaviour: The protected equipment becomes T2 if the protection is wholly defeated, T3 if degraded but still functional. Override requests generated. Where a SIF protecting live equipment would be defeated, authorisation is blocked absent a recorded deviation.
CI-7 — Disposal-route cascade Detection: The depressurisation, drain or purge route required by this plan passes through, or discharges into, systems that are themselves isolated, out of service, or required by another party. Behaviour: The route owner becomes T4 (protected). If the route is unavailable per the PSD, the plan cannot proceed as drafted and the agent says so.
CI-8 — Physical access cascade Detection: Using the SAR — the work requires access through, above, or adjacent to other live equipment; spool removal requires a lift over live plant; hot work is within the adjacency radius of a live item. Behaviour: Adjacent items become T2 (require isolation or shutdown for hot work) or T3 (require barricading, monitoring). Drives the hot work permit (REQ-P-06).
CI-9 — Redundancy cascade (inverse) Detection: The work scope is one of a redundant set (duty/standby pumps, redundant detectors, A/B trains, multiple fire pumps). Behaviour: The remaining item(s) become T4 — protected. The agent shall flag them so that a subsequent plan attempting to isolate them is blocked or escalated. This is the mechanism that prevents the classic incident pattern of independently-approved isolations collectively removing all protection.
CI-10 — Mechanical coupling cascade Detection: Driver/driven relationships, common shafts, gearboxes, shared lube oil systems, common seal gas. Behaviour: The coupled item becomes T1 or T2 depending on whether the coupling can be broken. Rotation prevention required on both.
CI-11 — Blinding-access cascade Detection: Positive isolation requires breaking joint J, and J is not itself protected by an existing isolation. Behaviour: A preparatory isolation is required before the blind can be installed — a temporary, lesser isolation that enables the joint break, which may itself take out further equipment. The agent shall generate this as an explicit sub-plan with its own sequence and hold point. This is a recursive case; see A2.4.
CI-12 — Nested isolation cascade Detection: The proposed boundary lies wholly or partly inside an existing active isolation (from the PSD). Behaviour: Inherit the parent boundary, re-validate it against this work's RBC, generate only the incremental isolation, and mark the parent's points as T4 for the duration.
### A2.4 Termination and containment of the cascade
Cascades are recursive: expanding a boundary can trigger CI-3, which triggers CI-5, which triggers CI-2. Without control this converges on "shut down the plant."
REQ-CI-02 Cascade recursion applies only to T1 expansion (items pulled inside the boundary). T2/T3/T4 classification is evaluated once and is not recursed — an item that loses feed does not cause the agent to plan an isolation for its downstream neighbours.
REQ-CI-03 T1 expansion depth shall be bounded (configurable, default 3 levels). On exceeding the bound, the agent stops and reports: "this scope cannot be isolated without an expanding boundary; a unit shutdown is likely required" — and shows the expansion path that led there. It does not silently produce a fifty-point plan.
REQ-CI-04 Every cascade shall record which rule fired, on which relationship, and why — visible in the dependency tree UI (A4.4).
REQ-CI-05 The T4 protected set shall persist in the isolation register for the life of the isolation, and shall be checked against every new plan created while it is active.
## A3. Layer 2 — Equipment Isolation Patterns
### A3.1 Pattern structure
Each pattern is a YAML record keyed on equipment class:
equipment_class: shell_and_tube_exchanger
expected_connections:          # completeness check against traversal
  - {role: shell_inlet,  cardinality: 1..2, mandatory: true}
  - {role: shell_outlet, cardinality: 1..2, mandatory: true}
  ...
independent_boundaries: [shell_side, tube_side]
residual_energy: [trapped_liquid, thermal, pressure_both_sides]
mandatory_holds: [cool_down_below_60c, prove_both_sides_independently]
known_failure_modes: [...]
sequence_constraints: [...]
bom_additions: [...]
REQ-EP-01 Where the traversal finds fewer connections than the pattern marks mandatory, the agent shall raise a completeness discrepancy against that item, blocking authorisation until resolved (either the drawing is incomplete, or the connection genuinely does not exist and is confirmed as such).
REQ-EP-02 Where the traversal finds connections the pattern does not expect, they are included in the boundary regardless. The pattern never restricts the boundary.
### A3.2 Worked pattern — Shell & tube heat exchanger
The example raised. Its distinguishing feature is that it is two independent isolations on one item, and treating it as one is the classic error.
Aspect
Requirement
Independent boundaries
Shell side and tube side are separate, each with its own HSC, EC, RBC, proving and certificate section
Expected connections
Shell in/out, tube in/out, shell vent (high point) and drain (low point), channel vent and drain, thermal relief PSV on the blocked-in side, TI/PI tappings on both sides, steam-out or N₂ connections where present, chemical cleaning connections
Cross-contamination
If either side is hydrocarbon and the other utility (cooling water, steam), the agent shall flag possible tube-leak cross-contamination as a hazard on the utility side, and require gas testing on the utility side before joint break — even though the utility fluid is HSC-1
Thermal
Cool-down hold with a target temperature before flange breaking; both sides
Trapped liquid
Shell side commonly has no low-point drain on the bottom of the shell; if isometrics show none, flag trapped-liquid at the channel/shell flange
Sequence
Depressurise both sides before draining either; drain the hotter side first; break the channel head last where the bundle is pulled
Bundle pull
Mechanical scope — the boundary must extend to any piping that must be removed for access, which becomes T1 by CI-8
Thermal relief
Blocking in a liquid-full exchanger side that receives heat requires thermal relief to remain in service or the side to be vented — a CI-3 case inside a single item
BOM
Two blind sets, different ratings and materials per side; channel head gasket
Common failure modes to test against: isolating only the process side; missing the thermal relief valve; treating cooling water as harmless when it may be contaminated; draining the shell before venting and pulling a vacuum.
### A3.3 Worked pattern — Centrifugal pump
Aspect
Requirement
Expected connections
Suction, discharge, minimum-flow/kickback, casing vent, casing drain, seal flush (per API 682 plan), seal quench/drain, barrier/buffer fluid supply and return, seal cooler cooling water in/out, bearing cooling, PI/PG tappings, suction strainer drain
Distinguishing check
The discharge check valve is not a barrier (Section 6.4); the parallel standby shares suction and discharge headers
Cascade triggers
CI-2 (common headers), CI-4 (seal flush may be supplied from a system used elsewhere), CI-9 (standby becomes T4), CI-10 (motor/driver)
Residual energy
Rotation/windmilling from the process side even with power removed; trapped liquid in casing; seal plan 53/54 pressurised reservoir (stored energy)
Sequence
Confirm stopped and rotation prevented before any joint break; stop the pump before isolating seal flush, never the reverse
Seal plan specifics
Plan 32 (external flush) means an external supply enters the pump — a separate live path from a different system. Plan 52/53 reservoirs hold pressure and must be depressurised. Plan 23 has a closed loop with a cooler
### A3.4 Worked pattern — Fired heater
Distinguishing feature: fuel gas isolation is a mandatory double block and bleed regardless of the derivation model output, and the process side and firing side are independent.
Aspect
Requirement
Independent boundaries
Process coil(s), main fuel gas, pilot gas, purge/snuffing steam, combustion air, flue gas path
Fuel gas
DBB with vent to a safe location mandatory; pilot gas isolated separately; both proved independently
Expected connections
Process in/out per pass, pass balancing, coil drains and vents, decoking/steam-air connections, snuffing steam, purge steam, soot blowers, sample connections, fuel gas main and pilot, atomising steam on oil-fired
Residual energy
Refractory heat retention — long cool-down hold; residual fuel in the header; natural draft causing air movement; stored heat causing coil contents to vaporise after isolation
Sequence constraint
Purge before any work; snuffing steam availability must be confirmed and it must not be isolated (T4) while any fuel path remains live
Cascade
CI-3 (coil thermal relief), CI-5 (process continuity — the heater is usually in series), CI-8 (confined space entry into the firebox)
Entry
Firebox entry is EC-D and requires positive isolation of every fuel connection plus atmosphere testing for CO and O₂
### A3.5 Worked pattern — Column / tower
Aspect
Requirement
Distinguishing feature
Many connections at many elevations; multiple manways; entry is multi-compartment
Expected connections
Feed(s), overhead vapour, reflux return, bottoms draw, reboiler supply and return, side draws and pumparounds, all instrument tappings and level bridles, PSV(s), N₂ blanket, steam-out, chemical injection, sample points, vent and drain, manway count
Entry specifics
Each compartment between trays is effectively a separate confined space; entry plan must address each; trapped liquid on trays and in the sump; falling debris between levels
Cascade
CI-1 (reboiler and condenser frequently pulled inside the boundary), CI-3 (PSV), CI-5 (whole unit continuity)
Residual energy
Liquid hold-up on trays; hydrostatic head; hot bottoms; pyrophoric deposits in overhead systems on sour service
### A3.6 Worked pattern — Reactor (fixed bed and stirred)
Aspect
Requirement
Expected connections
Feed, effluent, quench, recycle gas, catalyst loading and unloading nozzles, N₂ purge, steam-out, PSV/rupture disc, bed thermocouples (many), sample, drain, agitator seal system on stirred reactors
Chemical residual energy
Catalyst (pyrophoric when spent), residual reactants, exotherm potential if air ingresses, polymer or coke deposits
Sequence constraint
Inert atmosphere must be maintained until the catalyst is treated or removed — this conflicts with entry, and the transition to breathable atmosphere is a defined, monitored procedure, not a step
Cascade
CI-4 (recycle gas compressor and quench systems), CI-9 (parallel reactor trains)
### A3.7 Worked pattern — Storage tank
Aspect
Requirement
Distinguishing feature
Gravity head is the dominant residual energy; positive isolation is difficult because of common manifolds
Expected connections
Fill, suction/draw-off, recirculation, water draw, mixer, roof and rim vents, PVRV, foam and fire system connections, N₂ or vapour-recovery blanketing, heating coils, level and temperature instruments, manways, roof drain on floating roof
Residual energy
Static head until fully drained; sludge and FeS; vapour space; floating-roof legs
Cascade
CI-2 (common manifolds with other tanks), CI-3 (PVRV and emergency venting), CI-7 (slops routing)
Sequence
Isolate fill before draw-off; blanket gas last; roof drain considerations
### A3.8 Pattern library — remaining classes (summary)
Class
Distinguishing isolation feature
Positive displacement pump
Cannot be blocked in — relief valve is integral to the machine and is part of the boundary problem; discharge relief must remain or the pump must be positively isolated
Centrifugal compressor
Lube oil, seal oil, seal gas, buffer gas, anti-surge recycle, interstage KO drums and coolers; windmilling; nitrogen purge before opening
Reciprocating compressor
As above plus pulsation dampeners retaining pressure, cylinder cooling/jacket water, packing vents to flare
Air-cooled exchanger
Multiple bays and passes each requiring vent/drain; fan motors and louvre actuators; often no low-point drain on the header boxes; thermal relief
Plate heat exchanger
Gasket integrity; both sides; cannot be steamed out; frequently no vents
Filter / strainer
High-frequency short-duration job — must produce a proportionate isolation; duplex filters share headers (CI-2); backwash connections
Separator / KO drum
Multiple phases each with its own draw-off; boot and water draw; level bridles; PSV; frequently the flare KO drum which is T4 for everyone else
Agitator / mixer
Rotation prevention primary; seal system; vessel contents remain the hazard even when the vessel is not opened
PSV
The device is the protection — CI-3 always applies; changeover valve rules; car-sealed valves
Control valve
Bypass is a live path; actuator air and solenoid; loop consequence
ESDV / SDV
Cannot be its own barrier; safety-critical impairment record
Pig launcher / receiver
Interlock sequence; pressure proved zero before door opening is a hard hold point; trapped pressure behind the pig
Metering skid
Custody transfer implications; prover loop; densitometer and sampler take-offs
Package unit
Black box; isolate at battery limits; internal isolation per vendor manual (D-17)
REQ-EP-03 The library shall be extensible by the client's process safety engineer without a software release, and each pattern shall carry an author, revision and approval record.
## A4. Layer 3 — Service and Fluid Patterns
Keyed on fluid_code or a service class in the FHR. These express what is special about the fluid, beyond its HSC.
### A4.1 Pattern structure
service_class: molten_sulphur
hsc_floor: 3
additional_steps: [...]
prohibitions: [...]
sequence_inversions: [...]      # hard constraints overriding generic sequencing
bom_requirements: [...]
permit_additions: [...]
gas_test_additions: [...]
### A4.2 Service patterns
Service
Special requirements
Sour / H₂S-bearing
HSC-4 above the configured ppm threshold; H₂S gas testing at every joint break and at intervals; pyrophoric FeS in vapour spaces and on internals — keep wetted or inerted; BA/SCBA requirements in the permit; drain to closed systems only
HF (alkylation)
Positive isolation floor regardless of duration or exposure class; neutralisation and water-wash before any joint break; HF-specific PPE and emergency shower proximity from the SAR; blind and gasket material constraints (Monel); no configuration below L5 permitted, non-overridable
Chlorine / ammonia
Positive isolation floor; dry-air purge for chlorine (moisture creates corrosion); scrubber availability as a T4 dependency; specific gasket materials
Hydrogen / H₂-rich
Invisible flame — flame detection method stated in the permit; embrittlement constraints on blind material; very low ignition energy so hot work adjacency radius extended; small molecule so seat leakage assumptions weaker — favour positive isolation earlier
Oxygen service
BOM constraint: blinds, gaskets and any tooling entering the system must be oxygen-clean and hydrocarbon-free — the agent shall flag this on the BOM; prohibition on hydrocarbon-based thread lubricants; adiabatic compression hazard on re-pressurisation, so a controlled slow re-pressurisation step at reinstatement
LPG / flashing liquid
Auto-refrigeration on depressurisation causing cold burns and material embrittlement; liquid remaining after apparent depressurisation; repeated vent cycles with a hold between; extended drain-down
Cryogenic / LNG
Sequence inversion: warm-up hold and re-vent after apparent depressurisation and before joint break, because trapped liquid re-pressurises the section; thermal contraction on isolation points; low-temperature blind materials
Molten sulphur
Sequence inversion: steam jacketing and tracing must remain in service until the line is drained — the generic rule "isolate utilities first" is inverted and must be blocked; solidification risk on any isolation; H₂S evolution from molten sulphur; drain while hot
Hot oil / heat transfer fluid
Above autoignition temperature so leaks self-ignite; cool-down hold mandatory before joint break; expansion drum as an inventory source; leak-past on a hot valve seat behaves differently to cold
Steam / condensate
Trapped condensate; trap discharge to a live common header requiring blinding; thermal energy; flash on depressurisation; silent water hammer risk on reinstatement — controlled warm-up sequence required
Polymerising monomers (butadiene, styrene, VCM, acrylics)
Popcorn polymer in dead legs and behind closed valves — the agent shall flag dead legs within the boundary specifically; inhibitor dependency (isolating the inhibitor injection is itself a hazard — the inhibitor line becomes T4); polymer preventing a valve seating, undermining barrier assumptions
Amine
Heat-stable salts and corrosion; H₂S in rich amine; foaming; drain to amine slops not general slops
Caustic
Stress corrosion cracking; flushing before joint break; PPE; material compatibility of blinds
Acid (sulphuric, HCl)
Material compatibility of blinds and gaskets; hydrogen generation in storage; flush and neutralise; specific PPE
Catalyst / slurry / solids-bearing
Valves may not seat — barrier assumption weakened, escalate; line plugging preventing drainage; flushing requirement before isolation
Nitrogen / inert utilities
Asphyxiation — HSC-2 floor whenever confined space is involved even though the fluid is otherwise benign; a nitrogen connection into the work zone is a live path in and must be isolated with the same rigour as a process line
Instrument air
Low hazard fluid, extreme consequence — the impact analysis matters far more than the isolation itself (S-18 in v1.0)
Fuel gas
DBB with vent mandatory (see fired heater pattern)
REQ-FP-01 Sequence inversions are hard constraints. Where a service pattern specifies a sequence inversion (molten sulphur jacketing, cryogenic warm-up, oxygen slow re-pressurisation), it shall override the generic sequencing rules of REQ-F6-02 and shall be presented prominently in the plan with its rationale.
REQ-FP-02 Barrier confidence modifiers. Services that degrade valve seating (solids, polymerising, coking, molten, sour with FeS) shall reduce barrier confidence, escalating the required configuration by one level or requiring positive isolation. This is the mechanism that partially compensates for the absence of valve integrity data (D-18).
## A5. Layer 4 — Process Unit Patterns
Coarser-grained patterns capturing unit-level knowledge. Optional per site; extensible.
Unit
Isolation-relevant characteristics
Crude distillation
Desalter (high voltage — electrical hazard even though HV isolation is out of scope, so flag and hand off); overhead corrosion and NH₄Cl deposits; pyrophoric deposits in the overhead system; heavy ends solidification
Hydrotreater / hydrocracker
High-pressure hydrogen loop; recycle compressor as a T4 dependency; catalyst pyrophoricity; H₂S in the separator; high-pressure/low-pressure interface as a critical boundary
FCC
Catalyst circulation — isolation of one side affects the standpipe seal; CO and catalyst fines; slide valves are not isolation devices; regenerator temperature
Alkylation (HF or H₂SO₄)
Acid inventory; neutralisation; acid-specific materials; rapid de-inventory systems as T4
Amine treating / SRU
Rich amine H₂S; sulphur solidification; SRU reaction furnace refractory cool-down; tail gas
Ethylene / cracking
Coke deposits; decoking connections; cryogenic cold box (a black box with many connections); acetylene
LNG liquefaction
Cryogenic throughout; mixed refrigerant inventory; cold box; extended warm-up before any intervention
Utilities and offsites
Common headers serving everything — the highest cascade fan-out; the agent's impact analysis matters more than its boundary
Offshore topsides
Congestion drives CI-8; limited isolation points by design; muster and escape route impact; simultaneous drilling operations
## A6. Scenario Test Matrix
REQ-SL-04 The regression suite (REQ-SA-05) shall be generated as the cross-product of representative cases:
{equipment class} × {service class} × {exposure class} × {cascade type}
with a curated subset of at least 200 combinations covering every equipment class, every service pattern, every cascade type, and every degenerate case from v1.0 Family G. Every combination shall have an expected boundary, expected barrier configuration, expected cascade set and expected discrepancies.
REQ-SL-05 Any new pattern added to L2/L3/L4 shall ship with at least one test case, and the full suite shall run before any release.
## A7. Section 16 — Boundaries Spanning Multiple P&IDs
### A7.1 Why this is a safety issue, not a rendering issue
Almost every real isolation boundary spans several drawings. The danger is not that the picture is awkward — it is that a drawing edge silently terminates a traversal, producing a boundary with a hole in it that looks complete.
REQ-XD-01 — Drawing edges are not boundaries. The traversal engine shall have no concept of a drawing. It operates on the stitched graph. A path that leaves one sheet continues into the next without interruption.
### A7.2 Off-page connector integrity
REQ-XD-02 — Dangling connector detection. Before producing any plan, the agent shall identify every off-page connector, continuation arrow, or drawing reference on any path within or adjacent to the boundary that has not been resolved to a corresponding entity on another drawing.
REQ-XD-03 An unresolved connector on a path inside the boundary shall be treated as an unbounded live path — the most severe class of data gap. The agent shall not produce an authorisable plan. It shall name the connector, the source drawing and grid reference, the referenced drawing, and state that the path cannot be closed.
REQ-XD-04 — Drawing set completeness. The agent shall verify that every drawing referenced by a connector on any traversed path is present in the loaded graph. A reference to a drawing that has not been converted is a hard stop with the missing drawing named.
REQ-XD-05 — Revision consistency. The agent shall report the revision of every drawing contributing to the boundary and shall flag revision mismatches where connector metadata indicates the drawings were issued against different revisions of the same interface.
REQ-XD-06 — Tag uniqueness. Where the same tag appears on multiple drawings, the agent shall verify they resolve to a single graph entity. Duplicate tags across units — common in practice — shall be flagged as an ambiguity requiring resolution, not silently merged.
### A7.3 Organisational consequences
A boundary crossing a drawing edge frequently also crosses a unit, area, or ownership boundary, and this has real operational consequences that the agent must surface.
REQ-XD-07 — Multi-area authorisation. Where the boundary contains isolation points in more than one operating area or unit, the plan shall require authorisation from each area's isolation authority, and shall present the schedule grouped by area so each authority sees their own points in context.
REQ-XD-08 The plan shall identify battery-limit crossings explicitly, since these are frequently the natural isolation points and are frequently jointly-owned.
REQ-XD-09 Where the boundary crosses into an area under a different operating regime (contractor-operated, different shift pattern, a unit in shutdown while this one runs), the agent shall flag it as a coordination requirement.
### A7.4 Presentation of a multi-drawing boundary
REQ-XD-10 — Boundary index. Every plan shall open with a drawing index: each contributing P&ID, its revision, the number of isolation points on it, the areas involved, and the paths that cross between sheets.
REQ-XD-11 — Per-sheet mark-up. The marked-up P&ID output shall be produced per sheet, each showing the boundary segment on that sheet, with continuation markers at every sheet crossing: "boundary continues on P&ID-2104 at grid F7 — 3 further isolation points on that path."
REQ-XD-12 — Synthesised boundary schematic. In addition to the per-sheet mark-ups, the agent shall generate a single drawing-independent boundary schematic: the work zone at the centre, each path radiating outward to its isolation point, annotated with fluid, HSC, barrier configuration and source drawing. This is the artefact an authoriser actually reviews; the P&ID mark-ups are the artefact a field operator navigates.
This is the key insight for cross-drawing work: do not try to make a multi-sheet P&ID legible as a single picture. Generate a purpose-built representation of the boundary itself, and keep the P&ID mark-ups as the navigational reference.
REQ-XD-13 — Continuous navigation. In the interactive view, following a path across a sheet boundary shall be a single action that loads the next sheet centred on the continuation point, with the path highlighted. The user should never have to find their place manually.
REQ-XD-14 — Cross-sheet path tracing. The agent shall support "trace this path to a live source" as an interrogative, animating or listing the route across every sheet it traverses until it terminates at an isolation point or a live inventory.
## A8. Section 17 — Output User Experience
### A8.1 The central design decision
The output is not a document. It is a workspace with four surfaces, serving three different moments and three different postures.
Surface
User
Posture
Question being answered
U1 — Plan Review
Isolation authority / supervisor
Seated, desktop, deciding
Can I sign this?
U2 — Boundary Explorer
Authority, engineer
Seated, investigating
Why is this point here? What did you miss?
U3 — Field Execution
Field operator
Standing, gloved, outdoors, one-handed
What do I do next, and where?
U4 — Isolation Register
Shift supervisor
Handover, overview
What is currently isolated, and what needs attention?
Documents (certificate PDF, schedule, marked P&IDs, BOM) are exports from the workspace, not the workspace itself. They exist because permits are legal records, not because they are a good interface.
### A8.2 Design principles
P1 — The boundary is the primary object. Every view hangs off a visual boundary, not a list. Lists are derived views of the boundary, never the primary representation.
P2 — Progressive disclosure with a mandatory floor. Summary first, detail on demand — except deviations, data gaps, assumptions and impairments, which can never be collapsed, hidden behind a tab, or dismissed in bulk.
P3 — "Why" is always one click. Every isolation point, every impact, every number links to its derivation trace (REQ-D-09) in plain language. If a user cannot find out why in one action, they will stop asking, and an unquestioned plan is a dangerous plan.
P4 — Provenance is visible on the surface. Four visually distinct states, distinguished by shape and label as well as colour: derived from the graph (topologically certain), derived from a declaration (depends on the PSD, with the declarer named), conservative default (data was missing), unverified gap (blocking).
P5 — Design against complacency. Deviations must be acknowledged individually; there is no "accept all". The count of outstanding acknowledgements is always visible. Critical items are not always in the same screen position, so they cannot be dismissed by muscle memory.
P6 — Reporting a problem must be as easy as confirming success. In the field view, "cannot complete / doesn't match" is the same size and prominence as "confirm". If confirming is one tap and reporting a discrepancy is five, operators will confirm.
P7 — Never signal completeness the system cannot vouch for. No green "complete" badges, no checkmarks on the plan as a whole. Status language is procedural: drafted, authorised, set, proved.
P8 — Degraded environments are the design target, not the edge case. Sunlight, gloves, rain, noise, no connectivity, one hand on a ladder.
### A8.3 U1 — Plan Review
The screen the authoriser signs from. Layout, top to bottom:
Header band — plan ID and version; mode badge (PLANNED / EMERGENCY / PERMIT); work scope in one line; status; and a provenance strip showing graph revision, FHR revision, SIC version, PSD age with a warning if approaching expiry. The authoriser should be able to see in two seconds what this plan is built on.
The "must read" panel — above the fold, never collapsible. Grouped counts with individual acknowledgement:
Deviations from the derived standard
Data gaps blocking authorisation
Assumptions from the PSD requiring field confirmation
Safety-critical impairments
Override requests
Completeness discrepancies from L2 patterns
Cross-drawing issues (unresolved connectors, revision mismatches)
Each item is one line, expandable, with an explicit acknowledge control. The authorise button is disabled and visibly explains why — "4 items require acknowledgement" — rather than being absent or silently inert.
Boundary schematic (REQ-XD-12) — the work zone centred, paths radiating out, each terminating at its isolation point, annotated with fluid, HSC, barrier configuration, drawing reference. Colour and pattern encode barrier type. Click any point for its derivation trace. This is the single most important visual in the product.
Cascade / dependency tree — T0 through T4, showing which items are pulled in, which need action, which are protected, and which rule caused each. Collapsible per tier, but T2 (requires action) is expanded by default because those are the items that make a plan fail in execution.
Isolation schedule — the table, grouped by area then sequence, with per-area subtotals for multi-area authorisation (REQ-XD-07).
Interrogation bar — persistent, for natural-language questions about the plan (REQ-F8-02). Answers appear inline and are logged.
Diff view on re-authorisation — when a plan is revised, the default view is what changed, classified safety-significant or not, not the whole plan again.
### A8.4 U2 — Boundary Explorer
P&ID-centric, for investigation.
Sheet tabs with isolation point counts per sheet
Boundary overlay on the original drawing, at the original coordinates (REQ-DEP-01)
Continuation markers at sheet crossings; clicking one loads the next sheet centred on the continuation (REQ-XD-13)
Click any device: derivation trace, why it is or is not a barrier, what path it closes
"Trace to live source" — highlights the full route from the work zone outward, across sheets
Filters: by discipline, by fluid, by HSC, by barrier type, by "points I own"
A "what if" control: change duration, change activity type, mark the flare header out of service — and see the boundary recompute, with the differences highlighted. This is how an authority builds trust in the derivation model.
### A8.5 U3 — Field Execution
The surface where the plan meets reality. Mobile/tablet, offline-capable.
One step per screen. No scrolling to find the action.
Each step card carries, in descending size order: the tag number (largest element on screen), the action, the location and access notes from the SAR, the required end position, the lock/tag number to apply, and the reason in one line.
Two actions of equal visual weight: Set and confirm / Cannot complete — report. The second opens a short structured report: valve seized, valve missing, tag not found, access blocked, position differs from plan, other + free text + photo.
Proving is a separate step, never bundled with setting. Pressure decay holds get a live timer with the acceptance criterion on screen. The result is entered as a value, not a checkbox.
Blinds get unique IDs entered or scanned at installation and again at removal, feeding the reconciliation at reinstatement. A photo is mandatory for blind installation.
Sequence is enforced. Steps with unmet predecessors are visibly locked with the reason shown. Overriding sequence requires a supervisor action, logged.
Offline state is explicit — a persistent indicator showing how many confirmations are queued and unsynced.
Handover-safe. Any operator picking up the device mid-isolation sees the full state at a glance: set, proved, outstanding, failed.
### A8.6 U4 — Isolation Register
Area-level overview for shift supervision.
All active isolations by area, with age, expiry, re-prove due, outstanding points
T4 protected items prominently listed — the things that must not be touched, and which isolation protects them
Conflict warnings when a new plan touches a protected item
Long-term isolations approaching review dates
One-line status per isolation suitable for reading aloud at handover
### A8.7 Emergency mode UI
Deliberately different, so it can never be confused with a planned isolation.
Distinct visual treatment; large type; no navigation chrome
Answers stream progressively: remote isolation options first, then residual inventory and blowdown, then manual points and escalation targets (REQ-E-13)
Every option shows its time-to-effect and its confidence
Manual points marked accessible / likely inaccessible with the reason
A permanent, unmissable statement that this is advisory and subordinate to the emergency response plan
No authorisation flow, no permits, no exports — this surface produces advice and a log entry, nothing else
### A8.8 Anti-requirements
REQ-UX-N01 No "accept all" or bulk-dismiss control for deviations, gaps or assumptions. REQ-UX-N02 No global green completeness badge on a plan. REQ-UX-N03 No burying of gaps or assumptions behind a secondary tab. REQ-UX-N04 No auto-advance between field steps. REQ-UX-N05 No reliance on colour alone to convey barrier type, status or severity. REQ-UX-N06 No requirement to pinch-zoom a full P&ID to read a field instruction. REQ-UX-N07 No infinite scroll of caveats — caveats that are always present stop being read; standing limitations belong in a fixed, short block (REQ-SA-08), and only situation-specific items appear in the must-read panel.
### A8.9 Accessibility and environment
REQ-UX-A01 Field view: minimum 48 px touch targets, high-contrast mode for sunlight, usable with gloves, one-handed operation for all primary actions. REQ-UX-A02 WCAG 2.1 AA for the desktop surfaces. REQ-UX-A03 All status and severity conveyed by at least two channels (shape/icon/label plus colour). REQ-UX-A04 Print/PDF exports must remain legible in monochrome, since field copies are frequently printed on the unit printer.
### A8.10 Exports
REQ-UX-E01 Exports available at any lifecycle state, watermarked with the state (DRAFT / AUTHORISED / SUPERSEDED) so a printed copy can never be mistaken for a current one. REQ-UX-E02 Every export carries the plan version, graph revision, FHR revision, SIC version and PSD reference in a footer. REQ-UX-E03 Superseded exports shall be detectable — a QR or plan-version code that resolves to the current state, so a field operator holding a printout can check it is still valid.
## A9. Open Questions Arising
Boundary schematic form. I have specified a radial work-zone-centred schematic (REQ-XD-12) as the primary review artefact. Worth validating with two or three real isolation authorities before building — it is the highest-risk UX assumption in this document.
Pattern library ownership. Who authors and approves L2/L3/L4 patterns — Plant360, or the client's process safety function? It determines whether patterns ship as product content or as client configuration.
Multi-area authorisation. Do target clients actually operate multi-authority sign-off today, or is one authority signing for a cross-unit isolation the current practice? This changes REQ-XD-07 from a feature to a change-management exercise.
Field device reality. What hardware do operators actually carry — intrinsically safe tablets, phones, or nothing? If nothing, U3 becomes a printed pack and the design changes substantially.
Off-page connector fidelity. How reliably does Convert P&ID currently resolve off-page connectors? REQ-XD-02/03 make this a hard gate, and if resolution is imperfect the agent will block frequently.