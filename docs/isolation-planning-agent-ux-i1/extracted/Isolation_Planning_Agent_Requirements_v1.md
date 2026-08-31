# Isolation Planning AI Agent — Requirements Specification
Version: 1.0 Platform: Plant360.AI Depends on: UniGraph, Convert P&ID, Drawing & Document AI Agent Target industries: Oil & gas, refining, chemicals, petrochemicals (nuclear excluded from v1) Commercial framing: Licensed product to asset operators
## 1. Purpose and Scope
### 1.1 Purpose
The Isolation Planning Agent generates energy isolation plans and associated work permits for asset-intensive process plant, reasoning over the connected engineering data in UniGraph plus supporting drawings, documents and structured operational inputs.
### 1.2 Operating modes
Mode
Trigger
Objective
Time budget
M1 — Planned Isolation
Work order / maintenance scope
Complete, provable isolation enabling safe work
Minutes acceptable
M2 — Emergency Isolation
Live loss of containment, fire, gas release
Minimum set of actions to stop or limit the release
Seconds; degraded data tolerated
M3 — Permit Generation
Following M1, or standalone
Draft the permit(s) governing the work
Minutes
The three modes share the same graph, hazard model and traversal engine, but apply different objective functions and different data-sufficiency gates. The agent shall never silently switch modes; the active mode is declared in every output header.
### 1.3 In scope
Process isolation: fluid, pressure, inventory
Mechanical and stored-energy isolation
Instrument, control and safety-system isolation, including override identification
Depressurisation, draining, venting, purging, inerting, gas-freeing
Impact analysis on live plant
Reinstatement planning
Permit drafting (hot work, confined space entry, breaking containment, general/cold work, electrical work at LV, radiography, working at height where linked to the isolation)
Emergency isolation advisory
### 1.4 Out of scope (v1)
Environmental compliance assessment (venting, flaring, disposal permits)
HV electrical isolation, earthing/grounding of HV systems
Nuclear technical-specification / LCO reasoning
Autonomous execution or field actuation of any kind
Proposing plant reconfiguration alternatives (D-21)
Turnaround-scale multi-work-order optimisation
Automated learning from reviewer feedback
3D proximity computation (replaced by the Spatial & Adjacency Register)
### 1.5 Governing principle
The agent is decision support, not a decision maker. Every output is a proposal for authorisation by the site's competent person. In emergency mode, the agent is explicitly subordinate to the plant's ESD system, alarm response procedures and emergency response plan; it advises, it does not direct.
## 2. Definitions
Term
Meaning
Work scope
The item(s) and activity requiring isolation
Isolation boundary
The closed surface separating the de-energised work zone from live plant
Isolation point
A device or action forming part of the boundary
Barrier
A single admissible isolating element (Section 6.4)
Positive isolation
Blind, spade, spectacle blind in blinded position, blind flange, or physical disconnection
Proving
Positive demonstration that the isolation holds
HSC
Hazard Severity Class (1–4), derived per path
EC
Exposure Class (A–D), derived from activity and duration
RBC
Required Barrier Configuration, output of the derivation model
Live side
Plant remaining in service outside the boundary
SIC / FHR / PSD / SAR
The four structured configuration and state inputs (Section 5)
## 3. Users and Operating Model
Primary user: Operations. Specifically the shift/panel operator, the field operator executing isolations, and the operations supervisor / isolation authority who authorises.
Design consequences of an operations-first user base:
REQ-OM-01 Outputs shall be expressed in operational language and field terms (valve tags, locations, "close and lock", "prove at the bleed"), not engineering-analysis language.
REQ-OM-02 The field execution view shall be usable on a tablet in a hazardous area with gloves, and shall function offline with later synchronisation.
REQ-OM-03 The agent shall support a plan lifecycle: Draft → Authorised → Issued → Being Set → Set & Proved → Active → Being Removed → Reinstated → Closed, with an immutable audit trail of every state change and every edit.
REQ-OM-04 Transition to Authorised requires an identified human authoriser, and records the authoriser identity, timestamp, and the exact plan version, graph version and rule-set version approved.
REQ-OM-05 Any change to UniGraph, the FHR, the PSD, the SIC, or the work scope after authorisation shall invalidate the authorisation and force re-authorisation, presenting a diff that classifies each change as safety-significant or not.
REQ-OM-06 The agent shall support shift handover: an active isolation must be reviewable at handover with an at-a-glance state of every point (set / proved / not set / failed / removed).
## 4. Architectural Constraint (Safety-Critical)
REQ-ARCH-01 — Deterministic safety core. The isolation-standard derivation model (Section 6), the graph traversal that determines the boundary (Section 7), the barrier admissibility rules, and the sequencing rules shall be implemented as deterministic, version-controlled, testable code — not as LLM inference.
REQ-ARCH-02 — LLM confined to the periphery. LLM/agentic reasoning is used for: interpreting natural-language work scopes, resolving ambiguous tag references, extracting from documents, generating explanations and narrative, drafting permit text, conversational interrogation of the plan, and emergency-mode triage of an unstructured event description. It shall not determine which barriers are required or where the boundary lies.
REQ-ARCH-03 — No LLM output enters the plan unverified. Any entity referenced in a plan must resolve to a real UniGraph node. Any isolation standard must be traceable to a fired rule. Free-text generated by the LLM shall be visually distinguished from deterministically derived content.
Rationale: the client has no isolation matrix to encode, so the derivation logic is the product's core IP and its principal safety claim. It must be inspectable, repeatable and certifiable. An LLM deciding "this needs double block and bleed" is not verifiable evidence and will not survive a client's software safety assessment (D-04).
## 5. Inputs
### 5.1 UniGraph (primary)
Required content, unchanged from v0.1 except as noted:
Topology — complete connectivity including all branches: vents, drains, sample points, purge connections, instrument tappings, seal flush/quench, steam-out, warm-up/bypass, chemical injection, analyser take-offs, utility station connections, cross-ties. Line numbers with service code, size, piping class, insulation/tracing flags, design and operating P/T. Spec breaks.
Devices — valve tag, type (gate/globe/ball/plug/butterfly/diaphragm/check/needle), actuation, fail position, normal position (NO/NC/CSO/CSC/LO/LC), body/trim material, pressure class, seat type, lockability. Distinction between block, control, on/off actuated, ESD/SDV, check, PSV/PVRV, rupture disc, restriction orifice. Existing blinds/spades/spectacle blinds and their normal position. Flanged joints (from P&ID).
Equipment — tag, type, service, design conditions, volume, orientation. PSV-to-protected-equipment relationships. Driver-to-driven relationships. Package units as black-box nodes with declared battery-limit connections (D-17).
Instrumentation — tag, type, measured variable, tapping point, manifold arrangement, loop membership, participation in control loops / interlocks / SIFs with voting arrangement.
REQ-IN-01 UniGraph shall be version-stamped; every plan records the graph version used.
### 5.2 Fluid Hazard Register (FHR) — mandatory input
Client-supplied, per site or per unit. Excel or CSV. Without it, the agent shall refuse to produce a plan in M1/M3.
Sheet fluids — one row per fluid/service:
Column
Type
Notes
fluid_code
text
Primary key
service_description
text
e.g. "Sour crude", "LP steam", "Instrument air"
phase_at_operating
enum
liquid / gas / two_phase / flashing_liquid
nfpa_health
0–4
nfpa_flammability
0–4
nfpa_instability
0–4
special_hazards
multi-enum
pyrophoric / water_reactive / oxidiser / polymerising / catalyst_bearing / none
h2s_content_ppm
number
benzene_content_pct
number
idlh_ppm
number
tlv_twa_ppm
number
flash_point_c
number
autoignition_temp_c
number
normal_boiling_point_c
number
is_asphyxiant
bool
N₂, CO₂, Ar
is_cryogenic
bool
is_corrosive
bool
hsc_override
1–4 or blank
Direct override of derived Hazard Severity Class
source_document
text
Traceability
revision, approved_by, approved_date
Change control
Sheet service_code_map — maps P&ID line-number service codes to fluid_code:
Column
Notes
pid_service_code
e.g. "HC", "PW", "IA", "SC"
fluid_code
FK to fluids
unit_scope
Optional; some codes mean different things per unit
REQ-IN-02 Where a line's service code has no FHR mapping, the agent shall treat the fluid as unknown, apply HSC-4 (most severe) as the conservative default, mark the affected path as a data gap, and state that the plan is not authorisable until resolved.
REQ-IN-03 The FHR is a controlled document. Its revision is recorded on every plan.
### 5.3 Plant State Declaration (PSD) — mandatory input for M1/M2
Since no historian or DCS access exists (D-16), plant state is declared by Operations at plan time. Excel/CSV or in-app form.
Sheet
Columns
header
site, unit, declared_by, role, declared_at, plant_mode (normal / reduced_rate / shutdown / turnaround / start_up)
equipment_state
tag, state (running / standby / stopped / isolated / out_of_service), remarks
system_status
system_or_header_tag, status (live / depressurised / out_of_service), pressure_barg, temperature_c — required for flare header, closed drain header, open drain, N₂, IA, steam, cooling water
valve_position_exceptions
tag, actual_position, reason — only where the field position differs from the P&ID normal position
active_isolations
isolation_id, scope, boundary_points, set_date, expiry
active_overrides
sif_or_loop_tag, override_type, since, reason
REQ-IN-04 Every value taken from the PSD shall be reproduced on the isolation certificate as a stated assumption requiring field confirmation, with the declarer's name against it.
REQ-IN-05 Where the PSD is incomplete for a path the boundary depends on, the agent shall assume the worst case (header live and pressurised; spare not available; valve in its normal-operation position) and flag it.
REQ-IN-06 The PSD shall have a validity period (configurable, default 24 h). A plan built on an expired PSD cannot be authorised.
#### 5.3.1 Why plant state matters even without a historian
Live data is not strictly required for planning, but plant state is, because five decisions depend on it and cannot be derived from a P&ID:
Is the live side actually live? A path to a depressurised header needs a different barrier count than a path to a live one. Without state, everything is assumed live — safe, but produces heavier isolations than necessary and erodes user trust.
Is the drain/vent destination usable? Bleeding a DBB into a live closed-drain header is not proving an isolation. The agent must know header status.
Are there existing isolations or overrides? Nesting, shared points, and conflicting override requests all depend on this.
What is the spare/standby doing? Not to propose transferring duty (excluded by D-21), but to warn that a boundary removes the last available train.
Are any valves already out of their normal position? A car-sealed-open valve found closed, or a bypass found open, changes the boundary.
A structured PSD covers all five. Historian integration would only make it faster and less error-prone, and can be added later without changing the model. Recommendation: keep the PSD as the contract; treat any future historian integration as an auto-fill of the same schema.
### 5.4 Site Isolation Configuration (SIC) — mandatory input
Per-client/per-site configuration of the derivation model. YAML or a controlled UI, version-controlled, change requiring approval.
Group
Parameters
Barrier policy
check_valve_role: none (default) / secondary_below_hsc3; actuated_valve_as_barrier: allowed / not_allowed / allowed_if_lockable; soft_seat_permitted_for_hot_work: bool; small_bore_threshold_dn (default DN50)
Escalation thresholds
duration_escalate_days (default 7), positive_isolation_mandatory_days (default 30), unattended_overnight_escalates: bool, shift_change_requires_reprove: bool
Matrix overrides
Cell-level overrides of the HSC × EC matrix, each requiring a documented justification field
Proving
pressure_decay_hold_minutes, acceptance_criterion, re_prove_interval_hours for long-term isolations
Gas testing
LEL %, O₂ % range, H₂S ppm, benzene ppm acceptance criteria; retest intervals
Purging
Target O₂ %, number of volume changes, permitted purge media
Tagging
Lock colour scheme, tag numbering format, hasp/box policy, personal-lock policy
Electrical
electrical_isolation_mode: out_of_scope / manual_input / sld_graph (D-10)
Permits
Enabled permit types, templates, default validity periods, signature blocks
Modes
emergency_mode_enabled: bool
Export
Target CMMS adapter: none / maximo / sap_pm / canonical
REQ-IN-07 Every SIC parameter used in a derivation shall appear in that point's derivation trace.
REQ-IN-08 The SIC ships with an OSHA-aligned default profile (D-05) that is safe out of the box; a client that supplies nothing still gets a conservative, defensible plan.
### 5.5 Spatial & Adjacency Register (SAR) — required for hot work and access assessment
Substitute for 3D proximity (D-13). Excel/CSV, derived from plot plans, area drawings, or a field walkdown. Can be built incrementally — only needed for scopes involving hot work, confined space, or difficult access.
Column
Notes
tag
Equipment or line tag
area, module, deck_or_level
Location grouping
elevation_m
access_type
grade / platform / ladder / scaffold_required / confined / requires_rope_access
hazardous_area_zone
Zone 0 / 1 / 2 / unclassified
congestion
open / congested / enclosed
neighbours_within_radius
Semicolon-separated tag list, with the radius stated in the sheet header (default 15 m)
drain_or_funnel_within_radius
bool + tag
ignition_sensitive_neighbours
Tag list
remarks
REQ-IN-09 For hot-work scopes, if the SAR has no entry for the work location, the agent shall not produce a hot-work permit; it shall list the adjacency assessment as a mandatory manual step.
REQ-IN-10 The SAR shall also drive execution-effort estimation (scaffold-required points, high-elevation valves) and emergency-mode accessibility judgement.
### 5.6 Isometric-derived geometry (via Drawing & Document AI Agent)
REQ-IN-11 The Drawing & Document AI Agent shall extract and publish into UniGraph, per line:
Field
Purpose
elevation_m per node
Low/high point identification
is_low_point, is_high_point
Trapped liquid, venting
drain_at_low_point (tag or none)
Drain-down feasibility
vent_at_high_point (tag or none)
Depressurisation feasibility
joint_id, joint_type (flanged / welded / threaded)
Blinding feasibility
flange_size, rating, facing
Blind BOM
is_spool_boundary, spool_id, spool_removable
Physical disconnection planning (D-14)
line_volume_m3
Drain volume estimation
This answers the open question directly: yes, removable spools must come from the Drawing & Document AI Agent via isometrics. P&IDs do not carry them. Until that extraction exists, the agent shall plan positive isolation using flanged joints known from the P&ID only, and shall state that spool-removal options were not assessed.
### 5.7 Electrical inputs (deferred, flag-controlled)
REQ-IN-12 Where electrical_isolation_mode = out_of_scope, the agent shall include a standing placeholder section in every plan: "Electrical isolation not assessed by this system. To be planned separately by the authorised electrical person." — and shall list the powered devices it can identify within the boundary from UniGraph (motors, actuators, heaters, agitators) as a checklist for that person.
REQ-IN-13 Where electrical_isolation_mode = manual_input, the agent shall accept an Electrical Isolation Register (tag → isolation device → location → lock point) and incorporate it into the sequence and schedule.
REQ-IN-14 Where electrical_isolation_mode = sld_graph, the agent shall use the SLD-derived hierarchy in UniGraph once Convert-for-SLD is available. Requirements REQ-F5-01 to REQ-F5-04 (v0.1) apply at that point. LV only (D-10).
### 5.8 Work scope input
REQ-IN-15 Accept: explicit tag list; natural-language description; CMMS work order reference or export; graphical selection on a P&ID; named plant system.
REQ-IN-16 Elicit and record: activity type, expected duration, shift coverage, whether containment is broken, whether man-entry is required, whether hot work is required, whether equipment leaves site.
## 6. First-Principles Isolation Standard Derivation Model
This section is the safety core (REQ-ARCH-01). It replaces the client isolation matrix that does not exist (D-06). It is deterministic, and every output carries a derivation trace.
### 6.1 Step 1 — Hazard Severity Class (HSC), per path
Computed for the live-side fluid on each individual boundary path, not for the equipment as a whole. A pump may have HSC-4 on its process connections and HSC-1 on its cooling water.
HSC
Criteria (any one qualifies)
4 — Extreme
idlh_ppm ≤ 100, or h2s_content_ppm ≥ 100, or special_hazards includes pyrophoric / water_reactive, or (nfpa_health ≥ 3 AND gas/flashing phase), or flashing liquid ≥ 10 barg, or operating temp ≥ autoignition_temp_c
3 — High
Flammable (nfpa_flammability ≥ 3) in gas or flashing phase, or liquid above flash_point_c, or nfpa_health = 3 in liquid phase, or steam/hot fluid ≥ 150 °C, or cryogenic, or operating pressure ≥ 20 barg for any hazardous fluid
2 — Medium
Flammable liquid below flash point, nfpa_health = 2, corrosive, asphyxiant, hot fluid 60–150 °C, or any fluid ≥ 10 barg
1 — Low
Non-hazardous utilities below 10 barg and below 60 °C (cooling water, service water, service air)
hsc_override in the FHR takes precedence. Unknown fluid → HSC-4 (REQ-IN-02).
Modifier: where the live side is confirmed depressurised and out of service by the PSD, HSC is reduced by one class (floor of 1), and the derivation trace records the dependency on that declaration.
### 6.2 Step 2 — Exposure Class (EC)
EC
Criteria
A
No containment break. External work only (insulation, painting, external NDT, vibration survey).
B
Containment break, single shift, continuously attended, work party outside the boundary volume.
C
Containment break spanning multiple shifts, or boundary left open unattended, or equipment removed from site.
D
Personnel enter the boundary volume (confined space entry), or hot work performed on or within the boundary.
Duration escalation. Isolation duration ≥ duration_escalate_days → EC advances one level (max D). Duration ≥ positive_isolation_mandatory_days → positive isolation mandatory regardless of matrix output.
### 6.3 Step 3 — Required Barrier Configuration (RBC)
EC-A
EC-B
EC-C
EC-D
HSC-1
1 valve
1 valve
1 valve + bleed
2 barriers, ≥1 positive
HSC-2
1 valve
1 valve + bleed
2 barriers + bleed
2 barriers, ≥1 positive
HSC-3
1 valve
2 barriers + bleed (DBB)
2 barriers, ≥1 positive, + bleed
2 barriers, ≥1 positive, + bleed
HSC-4
2 barriers + bleed
2 barriers, ≥1 positive, + bleed
2 barriers, ≥1 positive, + bleed
Physical disconnection + blinded both sides
Reading: "2 barriers + bleed" is conventional double block and bleed. "≥1 positive" means at least one of the two must be a blind, spade or disconnection.
REQ-D-01 The matrix is configurable per client via SIC overrides, but every override requires a recorded justification and named approver, and appears in the derivation trace.
### 6.4 Step 4 — Barrier admissibility
Device
Barrier value
Conditions
Manual block valve (gate, ball, plug), full or reduced bore
1
Must be lockable or capable of chain-and-lock; must be in the isolation path
Butterfly valve
1
Not admissible as the sole barrier for HSC ≥ 3; not admissible for hot work if soft-seated and soft_seat_permitted_for_hot_work is false
Globe valve
1
Admissible; flag directional seating
Actuated on/off valve (SDV/XV/ESDV)
1
Only if actuated_valve_as_barrier permits, AND it can be mechanically locked closed, AND its motive power is isolated and locked
Control valve
0
Never a barrier
Check valve / NRV
0 by default
If check_valve_role = secondary_below_hsc3: counts as a secondary barrier only, never the primary, and never for HSC ≥ 3 or EC-D
Restriction orifice, flow element, rupture disc
0
Blind / spade / spectacle blind (blinded position) / blind flange
1, positive
Rating must meet the higher side of any spec break
Spool removal with both ends blinded
2, positive, satisfies disconnection
Requires isometric data (REQ-IN-11)
Removed instrument with tapping plugged/capped
1, positive
Small-bore only
Threaded plug / cap on a small-bore connection
1, positive
≤ small_bore_threshold_dn
Freeze plug, inflatable stopper, hot tap plug
0
Not admissible in v1
REQ-D-02 Small-bore rule. Any connection ≤ small_bore_threshold_dn that penetrates the boundary shall be isolated by valve plus plug/cap/blind regardless of matrix output, because small-bore valve failures are a dominant cause of loss of containment.
REQ-D-03 Two-barriers-in-series rule. Two barriers must be in series in the same flow path, with the bleed point between them. Two valves in parallel branches are not a DBB. The traversal engine shall verify series topology, not just count devices.
### 6.5 Step 5 — Provability
REQ-D-04 Where RBC requires a bleed, the agent shall identify a bleed/vent/drain point located topologically between the two barriers, and shall verify its destination is a safe, non-pressurised location per the PSD.
REQ-D-05 If no bleed exists between the two barriers, the required configuration cannot be achieved on that path. The agent shall, in this order: (a) walk outward to the next candidate point pair that does provide a bleed; (b) if none, require positive isolation; (c) if positive isolation is not achievable with available flanged joints, declare the path not isolatable as designed and stop. It shall not propose modifications (D-21).
REQ-D-06 Each isolation point shall carry a proving method: monitored bleed, pressure decay test with hold time and acceptance criterion from SIC, visual confirmation of blind installation with witness, or position verification with lock check.
### 6.6 Step 6 — Recorded assumptions and residual risk
REQ-D-07 Because valve integrity and leak-test history are unavailable (D-18), every plan shall carry a standing assumption statement:
"Isolation valves are assumed to seat and hold. This has not been verified against valve integrity or leak-test records, which are not available to this system. All isolations must be proved in the field before work commences, and any bleed showing continued pressure or flow shall be treated as a failed isolation."
REQ-D-08 Failed proving in the field shall trigger automatic re-derivation with that valve marked as passing, producing a revised plan (Scenario S-30).
### 6.7 Derivation trace
REQ-D-09 Each isolation point shall carry a machine-readable trace: path identifier, live-side fluid and its FHR source, computed HSC with the criterion that fired, EC with its driver, matrix cell used and any SIC override applied, barrier devices selected with their admissibility rule, bleed point and destination status, proving method, and any escalation applied. This trace is the evidence base for the software safety case (Section 11).
## 7. Functional Requirements — Planned Isolation (M1)
### 7.1 Boundary determination
REQ-F1-01 Determine the boundary by exhaustive traversal outward from the work scope along every connected path, terminating each path at the first location satisfying its RBC.
REQ-F1-02 Traversal shall follow all paths regardless of nominal flow direction, including: main process; recycle, bypass, kickback and minimum-flow lines; vents and PSV inlet/outlet to relief headers; open and closed drain headers including back-flow paths; seal flush, quench, barrier and buffer fluid (API 682 plans), lube and seal oil; purge/blanket gas, steam-out, chemical injection, sample and analyser lines; all utility connections; cross-ties to parallel trains and standby equipment; jacketed-line annuli and tracing circuits; instrument impulse lines and their manifolds; level bridles and standpipes (both connections).
REQ-F1-03 Every path is evaluated independently for HSC and RBC. The boundary is the union of per-path solutions.
REQ-F1-04 Handle nested boundaries: detect that a proposed boundary lies inside an existing active isolation (from PSD), generate only the incremental isolation, and re-validate that the parent isolation still satisfies the new work's RBC.
REQ-F1-05 Identify isolation points shared with other active isolations and flag them as protected — they must not be removed while another party depends on them.
REQ-F1-06 For package units (D-17), terminate traversal at the declared battery limits, isolate there, and state explicitly that internal isolation is per the vendor manual and outside the agent's knowledge.
REQ-F1-07 Where a path is not isolatable as designed, the agent shall clearly report the path, the reason, and the alternative it would require (plant section shutdown, upstream source shutdown) — as information, not as a proposal to reconfigure.
### 7.2 Residual and stored energy
REQ-F2-01 Enumerate residual energy remaining inside the boundary after barriers are set: trapped pressure and inventory (including dead legs and low-point pockets from isometrics); liquid head from elevated equipment; thermal energy and cryogenic vaporisation on warm-up; stored mechanical energy (spring-return actuators, accumulators, tensioned components); rotating inertia and windmilling; chemical residues (FeS, catalyst, polymer, reactive residues); oxygen-deficient or enriched atmospheres.
REQ-F2-02 For each, specify the mitigation and its verification, and identify the specific vent, drain or purge point in the graph that enables it, together with its destination status from the PSD.
REQ-F2-03 Where a low point identified from isometrics has no drain, flag trapped liquid and require a controlled joint-break procedure with the specific hazard stated.
REQ-F2-04 Where the SIC electrical mode is out_of_scope, mechanical stored energy (rotation, springs, accumulators) is still in scope and shall be planned — the exclusion is electrical supply isolation only.
### 7.3 Instrument, control and safety-system isolation
REQ-F3-01 For instruments on or within the boundary, determine impulse-line isolation: root valve, manifold configuration, and the correct valve sequence for DP transmitters to avoid over-ranging.
REQ-F3-02 Determine the control consequence of isolating or removing each instrument: loops going open-loop, final elements moving, interlocks tripping.
REQ-F3-03 Using the C&E matrix (via Drawing & Document AI Agent), identify every trip, alarm, ESD and F&G action affected, and produce the list of required overrides with justification, expected duration and compensating measure.
REQ-F3-04 Apply safety-system rules: identify voting degradation (2oo3 → 1oo2 acceptable; 1oo1 → SIF defeated); refuse to produce a plan that wholly defeats a SIF without an explicit deviation record; enforce maximum inhibit duration from SIC.
REQ-F3-05 Identify final elements whose fail position depends on a utility being isolated, and state the resulting position of every such device inside and outside the boundary.
REQ-F3-06 Identify safety-critical element impairments (fire water, deluge, F&G detection, ESD valves, relief devices) and generate an impairment record with compensating measures.
### 7.4 Depressurisation, draining, purging
REQ-F4-01 Generate the depressurisation route and sequence with target end conditions, respecting destination availability from the PSD.
REQ-F4-02 Generate the drain-down plan: drain points, destination, estimated volume from equipment and line volumes, and sequence respecting gravity and venting.
REQ-F4-03 Generate the purge/inerting plan: medium, connection points, flow path, volume changes or cycles per SIC, target concentrations, and test points.
REQ-F4-04 Flag asphyxiation risk wherever N₂ is specified, and require air-freeing before entry.
REQ-F4-05 Specify gas tests: locations, acceptance criteria from SIC, and repeat intervals.
### 7.5 Impact analysis on live plant
REQ-F5-01 Determine what the boundary removes from service beyond the work scope: downstream consumers deprived, upstream equipment deadheaded or blocked in, loss of cooling/flushing/purge to live equipment, loss of a minimum-flow path.
REQ-F5-02 Relief path integrity check. Verify that no isolation blocks the relief path of live equipment and no PSV protecting live equipment is isolated or removed. Explicitly check car-sealed and locked-open valves in relief paths, and refuse to close them without a recorded deviation.
REQ-F5-03 Availability check. Using the PSD, determine whether the boundary removes the last available train, the last fire pump, or the last detector in a coverage zone. Report as an impact — do not propose a workaround (D-21).
REQ-F5-04 Determine whether the plant can remain in its declared mode with the isolation in place; if not, state the required plant state.
REQ-F5-05 Identify SIMOPS conflicts with active isolations and permits from the PSD.
### 7.6 Sequencing
REQ-F6-01 Produce a numbered isolation sequence with, per step: step number, action, tag, device, required end position, lock/tag requirement, responsible role, verification method, and predecessor dependencies.
REQ-F6-02 Sequence shall be safe by construction: stop and confirm stopped before isolating; isolate process before breaking any joint; remove rotational energy before any work that could cause rotation; depressurise before draining; drain before purging; break the joint furthest from the live side first; install blinds only after the upstream isolation is proved.
REQ-F6-03 Produce the reinstatement sequence, which is not simply the reverse: blind reconciliation (count in = count out, by unique blind ID); removal of overrides and restoration of protective functions; leak/tightness testing; re-establishment of purges and seal systems; functional checks; and confirmation of every valve against its normal operating position.
REQ-F6-04 Include hold points requiring explicit sign-off: after proving zero pressure; before man-entry; before hot work; before removal of the final blind; before re-pressurisation.
REQ-F6-05 Support partial reinstatement and partial re-isolation for staged or interrupted work.
### 7.7 Outputs
REQ-F7-01 Isolation schedule — point ID, tag, description, P&ID number and grid reference, location and elevation (from SAR/isometrics), isolation method, required position, lock type/colour and tag number, sequence number, discipline, proving method, and fields for set-by / proved-by / removed-by.
REQ-F7-02 Marked-up P&ID — boundary, isolation points, blinds, bleeds, drains and vents rendered on the original drawing. Requires REQ-DEP-01.
REQ-F7-03 Bill of materials — blind/spade size, rating, facing, thickness and material derived from the piping class; gaskets; bolting; locks, hasps, tags, chains; nitrogen; test equipment.
REQ-F7-04 Isolation certificate draft in the site template.
REQ-F7-05 Assumption, gap and deviation register — one place listing every PSD-declared assumption, data gap, conservative default, deviation, impairment and override request, for the authoriser.
REQ-F7-06 Effort estimate — points by discipline, blinds to install, scaffold-required points, estimated duration.
REQ-F7-07 Canonical export (D-03) — a documented JSON/XML schema covering the plan, schedule, permits and BOM, with adapters mapping to Maximo work order operations and SAP PM order/permit objects. The agent's internal model shall not depend on either system's data model.
### 7.8 Explainability
REQ-F8-01 Every point carries its derivation trace (REQ-D-09) in human-readable form.
REQ-F8-02 The agent shall answer interrogatives: why is V-2210 in the boundary; what happens if V-2213 is left open; show every path from the work zone to a live hydrocarbon source; what changes if this becomes a 3-week job; which points would change if the flare header were out of service.
REQ-F8-03 Confidence shall be expressed per point, separating topologically certain conclusions, rule-derived conclusions, and items dependent on declared or missing data.
REQ-F8-04 Reproducibility: the same graph version, FHR revision, SIC version, PSD and scope shall produce a byte-identical plan.
## 8. Emergency Isolation Mode (M2)
### 8.1 Positioning
REQ-E-01 Emergency mode is advisory support to the emergency response, subordinate to the ESD system, alarm response procedures and the incident commander. Every output shall carry this statement prominently.
REQ-E-02 Emergency mode shall be independently enabled per site (emergency_mode_enabled), and shall be disabled by default until the client has assessed its integration with their emergency response procedures.
### 8.2 Input
REQ-E-03 Accept a minimal, fast input: event type (leak / fire / gas release / spill / loss of containment), location (tag, line number, or P&ID grid reference), estimated magnitude, and whether personnel are in the area. Natural language accepted and parsed by the LLM layer (REQ-ARCH-02).
REQ-E-04 Operate on the most recent PSD available; if none is current, proceed with the assumption that all systems are live, and state this.
### 8.3 Objective function
Emergency mode optimises for fastest reduction of the release, not for enabling work. Specifically:
REQ-E-05 Identify the minimum set of actions that stops or limits flow to the release point, ranked by time-to-effect.
REQ-E-06 Prefer remotely-operable devices: ESDVs, SDVs, blowdown valves, and MOVs identified in the graph. Present them first, with their initiating action.
REQ-E-07 Identify the residual inventory that will continue to feed the release after the remote isolation acts — the volume between the closed valves and the leak point — and estimate it from line and equipment volumes.
REQ-E-08 Identify the available depressurisation/blowdown route to reduce that residual inventory, and its destination.
REQ-E-09 Identify manual isolation points that would further reduce the release, and mark each one as accessible / likely inaccessible based on the SAR (proximity to the release point, congestion, access route).
REQ-E-10 Identify escalation targets: equipment and inventory within the SAR radius of the release, with their contents and inventory, ranked by consequence.
REQ-E-11 State the consequences of each proposed action on the rest of the plant (what trips, what else goes down) — as information, without recommending against action on operational grounds.
### 8.4 Degraded operation
REQ-E-12 Emergency mode shall produce useful output with incomplete data and shall never block on a data-quality gate. Missing data is reported alongside the answer, not instead of it.
REQ-E-13 Response shall be returned progressively: remote isolation options first (target < 10 s), then residual inventory and blowdown, then manual points and escalation analysis.
REQ-E-14 Every emergency output shall be logged in full for post-incident review.
### 8.5 Explicit non-goals
REQ-E-15 Emergency mode shall not attempt to actuate anything, shall not instruct personnel to enter any area, and shall not produce a permit.
### 8.6 Override/inhibit register — decision (D-11)
Recommendation: v1 produces override requests only; no register integration. Rationale: the override register is a live, safety-critical operational record whose integrity is the plant's responsibility, usually held in the DCS/SIS or a controlled register. Writing to it from a decision-support tool that has no live plant data creates a record that can silently diverge from reality — which is worse than no integration. The agent produces a structured override request list, tracks it in the plan, and reconciles it at reinstatement (every requested override must be confirmed removed before the plan can close). Register integration becomes appropriate once live plant state exists.
## 9. Permit Generation Mode (M3)
REQ-P-01 Supported permit types (enabled per SIC): general/cold work; hot work (spark-producing and open flame treated separately); confined space entry; breaking containment / line breaking; electrical work (LV); radiography; working at height. All aligned to OSHA baseline (D-05).
REQ-P-02 Permits shall be generated from the isolation plan, and shall reference the isolation certificate by ID and version. A permit cannot exist without a valid isolation reference where isolation is required.
REQ-P-03 Permit content shall include: work description and exact location; hazards derived from the FHR for the fluids present; the isolation reference and its proving status; required gas tests with acceptance criteria and retest intervals; PPE; precautions and controls; fire watch requirements and duration for hot work; entry controls, attendant and rescue provisions for confined space; adjacent-work and SIMOPS conflicts; validity period; signature blocks per SIC.
REQ-P-04 Permit validity coupling. Permit validity shall not exceed the isolation proving validity. If an isolation requires re-proving at shift change, the permit shall require re-validation at the same point.
REQ-P-05 Cross-permit conflict detection. Detect conflicts between concurrent permits: hot work adjacent to a line-breaking permit within the SAR radius; confined space entry adjacent to purging operations; radiography adjacent to occupied work areas.
REQ-P-06 Hot work permits shall not be generated without a SAR entry for the location (REQ-IN-09).
REQ-P-07 Permits shall be exported through the same canonical schema and adapters as the isolation plan (REQ-F7-07).
REQ-P-08 Permits are drafts requiring authorisation by the site's permit authority. The agent shall never mark a permit as issued.
## 10. Scenario Catalogue
These are build-and-test specifications for the development team. Each is a required behaviour, and each states the discriminating capability and the failure to guard against.
### Family A — Rotating equipment
S-01 Centrifugal pump seal replacement, sour hydrocarbon service, running spare Boundary: suction, discharge, minimum-flow/kickback, casing drain, vent, seal flush (API 682 Plan 11/21/32/52), buffer gas, seal cooler cooling water, PI/PG tappings. Must demonstrate: discharge check valve rejected as barrier; common suction/discharge header with the parallel spare identified as a live path protected only by a check valve; HSC-4 on the process paths from H₂S content and HSC-1 on cooling water, giving different barrier counts on the same job; mechanical rotation prevention even with electrical out of scope. Guard against: treating the check valve as the discharge isolation; missing the seal flush line.
S-02 Compressor overhaul, multi-stage, with lube and seal oil systems Must demonstrate: lube oil, seal oil and buffer gas systems as separate isolation paths; rotating inertia and windmilling; anti-surge and recycle line; suction knock-out drum inventory; interstage cooler and condensate paths; nitrogen purge requirement. Guard against: treating the machine as one item and missing auxiliary system paths.
S-03 Agitator/mixer seal work on a live-adjacent vessel Must demonstrate: rotation prevention as a first-class isolation requirement; vessel contents as the hazard even though the vessel is not opened; agitator seal purge/flush.
### Family B — Static equipment
S-04 Vessel man-entry for internal inspection EC-D, requiring positive isolation on every connection including small-bore, instrument tappings, PSV inlet and outlet, flare and closed drain, N₂ blanket, and both level bridle connections. Must demonstrate: blind list with unique IDs; blind reconciliation at reinstatement; demonstration that PSV removal does not leave the vessel unprotected during re-pressurisation; drain, purge, air-free, continuous monitoring; small-bore valve-plus-plug rule. Guard against: missing the second bridle connection; missing the PSV outlet path to a live flare header.
S-05 Shell-and-tube exchanger tube bundle removal Two independent boundaries with different fluids, HSCs and barrier requirements. Steam and condensate on one side, process on the other. Must demonstrate: per-path HSC computation on a single item; thermal cool-down hold; the possibility that a tube leak has cross-contaminated the other side (agent must flag the hazard, not assume clean); channel head flange break as a blinded joint.
S-06 Column / tower entry for tray work Must demonstrate: multiple manways and multiple entry levels; reboiler and condenser circuits; reflux, feed and draw-off paths at several elevations; trapped liquid on trays and in the sump; the requirement to prove each section, not just the bottom.
S-07 Filter / strainer element change, frequent short-duration job EC-B, short duration, HSC-3. Should produce a proportionate isolation, demonstrating that the model does not over-isolate routine work. Guard against: over-isolation eroding user trust — this scenario is the counterweight to S-04.
S-08 Storage tank cleaning Must demonstrate: gravity head as residual energy; sludge and FeS; multiple nozzles at various elevations; mixer; foam and fire system connections; nitrogen or vapour-recovery connections; roof drain; the difficulty of positively isolating a tank with a common manifold.
### Family C — Valves and piping
S-09 Control valve removal, toxic service Must demonstrate: block valves either side plus the bypass valve as a leak path requiring isolation; actuator air supply and solenoid; trapped inventory between blocks; loop consequence of removing the final element. Guard against: missing the bypass; treating the control valve itself as a barrier.
S-10 PSV removal for recertification with the unit online Must demonstrate: relief protection relationship check; identification of a spare PSV on a changeover valve and the rule that both must never be closed; car-sealed-open inlet block valve handling; refusal to permit the online option where no alternative relief exists, with a clear statement that shutdown is required. Guard against: closing a CSO valve without a recorded deviation.
S-11 Line section replacement requiring spool removal Must demonstrate: use of isometric-derived spool boundaries (REQ-IN-11); flange rating and facing for blinds; the sequence of breaking the far joint first; and — where isometric data is absent — an explicit statement that spool options were not assessed and only P&ID flanged joints were considered.
S-12 Pig launcher / receiver door opening High-consequence scenario class. Must demonstrate: interlock sequence with pressure proven zero before door opening as a hard hold point; trapped pressure behind the pig; kicker line; vent and drain; closure interlock integrity as a precondition. Guard against: producing any sequence in which the door can be opened before proving.
S-13 Utility station / temporary hose connection A hose connects a utility station to the work zone; not on the P&ID. Must demonstrate: temporary connections prompted as a mandatory checklist item on every plan; once declared, incorporated into the boundary.
### Family D — Instruments and control
S-14 DP transmitter replacement on a live SIS line No main-line isolation; isolation at root valves and manifold. Must demonstrate: correct manifold sequence to avoid over-ranging; C&E lookup identifying the SIF; voting analysis; permitted inhibit with duration and compensating measure; refusal where the SIF would be wholly defeated; inhibit removal reconciled at reinstatement.
S-15 Level bridle / displacer work Must demonstrate: both bridle isolations; trapped liquid in the bridle; the standpipe as a second path to the vessel; interlock consequence of losing level measurement.
S-16 ESD valve overhaul The isolation device is itself the work scope. Must demonstrate: the valve cannot be its own barrier; boundary must be established upstream and downstream by other means; the C&E consequence of the ESDV being unavailable; the impairment record for a safety-critical element.
S-17 Analyser house / sample system work Must demonstrate: sample take-off and return paths as live hydrocarbon paths; fast loop return to a live line; analyser house purge (Ex p) dependency on instrument air; small-bore rule application throughout.
### Family E — Utilities
S-18 Instrument air header valve replacement Wide-impact scenario. Must demonstrate: enumeration of every device fed downstream with its fail position; identification of fail-in-place devices whose position is hazardous; air-driven pumps; Ex p panel purges; ESD valves that will move; conclusion that online isolation may not be possible.
S-19 Steam and condensate system isolation Must demonstrate: trapped condensate; steam traps; thermal energy and burn hazard with a cool-down hold; condensate back-flow from a live common header requiring blinding; flash steam on depressurisation.
S-20 Cooling water isolation affecting live equipment Must demonstrate: identification of live heat exchangers, seal coolers and lube oil coolers that lose cooling; impact reported clearly; low HSC on the cooling water path itself but high consequence on the live side.
S-21 Flare / closed drain header connection Must demonstrate: recognition that the common header cannot be isolated by valve; positive isolation at a flanged joint; bleed destinations rejected where they route to the live header; back-flow from the header as a hazard path.
### Family F — Special hazards
S-22 HF alkylation unit work HSC-4 with acute toxicity. Must demonstrate: maximum barrier configuration; neutralisation and water-wash steps; specific PPE in the permit; the rule that no configuration below positive isolation is acceptable regardless of duration.
S-23 Reactor entry with pyrophoric deposits and catalyst Must demonstrate: chemical residual energy handling (FeS wetting or continuous inerting); the conflict between inert atmosphere for pyrophoric control and breathable atmosphere for entry, surfaced explicitly with a defined transition procedure and monitoring; catalyst removal under nitrogen.
S-24 Cryogenic / LNG line valve replacement Must demonstrate: trapped liquid vaporising after apparent depressurisation, requiring a warm-up hold and re-vent before joint break; thermal contraction; material constraints on blinds; low-point concerns. Guard against: declaring the section depressurised after a single vent.
S-25 Acid / caustic service Must demonstrate: corrosion and material compatibility of blinds and gaskets in the BOM; flushing and neutralisation before joint break; PPE and emergency shower proximity in the permit.
### Family G — Degenerate and edge cases
S-26 Required barrier configuration not physically available Only a single block valve exists where DBB is required. Must demonstrate: detection; outward walk to the next compliant point with the additional plant taken out of service stated; if none, positive isolation via an available flanged joint; if none, declaration that the path is not isolatable as designed. Must not silently accept the single valve, and must not propose modifications (D-21).
S-27 Missing data Service fluid unmapped in the FHR; valve type unknown; drain destination not connected in the graph. Must demonstrate: HSC-4 default for the unknown fluid; explicit gap register; mandatory field verification items; and a clear statement that the plan is not authorisable until resolved.
S-28 Vendor package unit Must demonstrate: isolation at declared battery limits; explicit statement that internal isolation is outside the agent's knowledge and per the vendor manual; refusal to infer internal topology.
S-29 Nested isolation / scope added mid-job Additional work inside an already-isolated boundary. Must demonstrate: evaluation of whether the existing boundary satisfies the new work's HSC/EC; generation of only the incremental isolation; no unnecessary full reinstatement.
S-30 Failed proving during execution Field reports pressure building on the bleed. Must demonstrate: automatic re-derivation with that valve marked passing; escalation of the standard or outward boundary walk; revised sequence, schedule and certificate; forced re-authorisation; the original plan marked superseded and not executable.
S-31 Expired plant state The PSD is older than its validity period when the plan is presented for authorisation. Must demonstrate: block on authorisation, with a clear list of which specific declarations need refreshing rather than a demand to redo the whole PSD.
S-32 Over-isolation regression test A simple, low-hazard, short-duration job (e.g. replacing a pressure gauge on a cooling water line) must produce a one- or two-point isolation. This scenario exists to detect drift toward blanket conservatism, which is itself a safety failure because it drives users around the tool.
### Family H — Emergency mode
S-33 Flange leak on a live hydrocarbon line Must demonstrate: remote isolation options returned within seconds; residual inventory between the closed ESDVs and the leak estimated; blowdown route identified; manual points marked accessible or likely inaccessible using the SAR; escalation targets within the radius listed with their inventories.
S-34 Gas release in a congested module with unknown source Must demonstrate: reasoning from the release location to candidate sources; ranked isolation options with the confidence in each; graceful degradation with no current PSD; explicit statement of the assumptions made.
S-35 Fire adjacent to a vessel Must demonstrate: escalation-target analysis prioritised over isolation; identification of the vessel's inventory, its relief path, and its blowdown route; explicit deference to the emergency response plan.
### Family I — Permits
S-36 Hot work on a line inside an existing isolation boundary Must demonstrate: EC-D escalation; positive isolation from all flammable sources; gas testing regime with retest intervals; fire watch duration; adjacency assessment from the SAR; refusal to issue the hot work permit if no SAR entry exists.
S-37 Concurrent permits with a conflict Confined space entry in one vessel while an adjacent line is being purged with nitrogen. Must demonstrate: cross-permit conflict detection and a clear statement of the conflict to the permit authority.
S-38 Permit validity vs isolation validity A long-duration isolation requiring re-proving at shift change. Must demonstrate: permit validity capped to the proving validity, and re-validation required at the same point.
### Family J — Reinstatement
S-39 Full reinstatement with blind reconciliation Must demonstrate: every blind installed accounted for on removal by unique ID; overrides confirmed removed; protective functions restored and functionally checked; leak test; every valve confirmed against its normal operating position; refusal to close the plan with any item outstanding.
S-40 Partial reinstatement Work completed on one item of a multi-item scope; the rest continues. Must demonstrate: selective removal of only the points not required by the remaining scope, with re-validation that the reduced boundary still satisfies the remaining work's RBC.
## 11. Safety-Related Software Assurance
Given D-04, the following are requirements, not recommendations.
REQ-SA-01 Classification. Produce a documented classification argument. The agent performs no online safety function; it is an engineering and operational support tool whose output is subject to independent human authorisation. Recommend positioning analogous to an offline support tool under IEC 61511 clause 11 tool requirements, with a documented tool validation strategy. The classification must be agreed with each client's process safety function.
REQ-SA-02 Deterministic core. Per REQ-ARCH-01, the safety-determining logic is conventional code, under configuration management, with full unit and integration test coverage and a requirements-to-test traceability matrix.
REQ-SA-03 Version pinning. Every authorised plan records the versions of: the rule engine, the SIC, the FHR, UniGraph, the PSD, and any model used in peripheral functions. A plan is reproducible from those versions alone.
REQ-SA-04 Change control. Changes to the derivation model, the barrier admissibility table, or the RBC matrix are managed under formal MoC with regression testing against the full scenario catalogue before release. No silent updates.
REQ-SA-05 Regression suite. The scenario catalogue in Section 10 shall be implemented as an executable regression suite. A release that fails any Family G scenario is blocked.
REQ-SA-06 Independent verification. The derivation model shall be independently reviewed by a qualified process safety engineer not involved in its development, and that review recorded.
REQ-SA-07 Failure mode controls.
Failure
Consequence
Control
Missed isolation point
Catastrophic — live hydrocarbon at an open joint
Exhaustive traversal; Family A–F scenarios; mandatory human authorisation
Under-specified barrier configuration
Leak past a single valve during work
Conservative defaults; HSC-4 for unknowns; escalation bias
Fabricated device
Field confusion, loss of trust
REQ-ARCH-03: every entity resolves to a graph node
Silent assumption
Undetected gap
Assumption register on every certificate
Over-isolation
Unnecessary outage and, worse, users routing around the tool
S-32 regression test
Stale graph or PSD
Wrong plan
Version pinning, validity periods
Automation complacency
Rubber-stamped authorisation
Explicit per-item acknowledgement of deviations and gaps
Emergency-mode over-reliance
Delayed or wrong emergency action
REQ-E-01 positioning; default disabled; full logging
REQ-SA-08 Limitations statement. Every output carries a standing statement of what the system does not assess: electrical isolation (where out of scope), environmental compliance, valve integrity history, plant conditions not declared in the PSD, internal topology of package units, and anything not represented on the source P&IDs.
## 12. Non-Functional Requirements
REQ-NF-01 Performance — M1 single-item scope: within 5 minutes. M1 system scope: within 30 minutes. M3: within 5 minutes. M2: first response within 10 seconds, full analysis within 60 seconds. Latency optimisation deferred (D-20).
REQ-NF-02 Scale — At least 500 P&IDs / 500,000 nodes per site; at least 500 concurrent active isolations.
REQ-NF-03 Auditability — Immutable audit trail of inputs, versions, outputs, edits and authorisations, retained per site records requirements.
REQ-NF-04 Multi-tenancy — Strict segregation between operator clients (D-22 commercial framing); no cross-tenant data access; per-tenant SIC, FHR and templates.
REQ-NF-05 Offline field operation — The execution view functions without connectivity and synchronises on reconnection, with conflict handling.
REQ-NF-06 Localisation — Units configurable (metric/imperial), and permit templates translatable.
## 13. Dependencies on Other Plant360 Components
Ref
Component
Requirement
REQ-DEP-01
Convert P&ID
Retain bi-directional links from graph entities to source-drawing coordinates, for boundary mark-up
REQ-DEP-02
Convert P&ID
Capture valve type, actuation, fail position, normal position, CSO/CSC/LO/LC annotations, blind and spectacle-blind symbols with position, flanged joints
REQ-DEP-03
UniGraph
Version and change-track the graph; support pinning a plan to a graph version
REQ-DEP-04
UniGraph
Model package units as black-box nodes with explicit battery-limit connections
REQ-DEP-05
Drawing & Document AI Agent
Extract C&E matrices in queryable form: initiator → action → affected element, with voting
REQ-DEP-06
Drawing & Document AI Agent
Extract from isometrics: elevations, low/high points, flanged joints, spool boundaries and removability, line volumes (REQ-IN-11) — blocking dependency for positive-isolation planning beyond P&ID flanges
REQ-DEP-07
Drawing & Document AI Agent
Extract from loop drawings: instrument power source and safe signal-isolation points (needed when electrical mode is enabled)
REQ-DEP-08
Convert for SLD (future)
Electrical hierarchy for electrical_isolation_mode = sld_graph
REQ-DEP-09
Platform
Canonical export schema plus Maximo and SAP PM adapters
## 14. Phasing
Phase 1 — Planned isolation core. Process and mechanical isolation, first-principles derivation engine, FHR/PSD/SIC inputs, boundary determination, sequencing, reinstatement, isolation schedule and certificate. Electrical out of scope. Scenario families A–G implemented and passing.
Phase 2 — Permits and instruments. SIS/C&E integration, override requests, SAR-based hot-work assessment, permit generation. Families D, I.
Phase 3 — Emergency mode and field execution. M2, tablet execution view, field verification capture, failed-proving re-derivation. Families H, J.
Phase 4 — Integration and electrical. Maximo/SAP adapters, isometric-derived geometry, SLD-based electrical isolation once Convert-for-SLD lands.
## 15. Remaining Open Questions
Blind register ownership. Sites usually run a physical blind register. Should the agent own it, or export to an existing one? Blind reconciliation (S-39) is a real safety control and needs a single source of truth.
Who maintains the FHR? It is the highest-leverage input in the system. Does the client own it, or does Plant360 build it during onboarding from line lists and safety data sheets?
PSD capture mechanism. Spreadsheet upload is workable but will decay in daily use. Is an in-app operator form acceptable for v1, and can operations realistically declare header status per plan?
Emergency mode appetite. Do the target clients actually want AI advisory in the emergency-response loop? It is technically achievable but carries assurance and liability implications well beyond planned isolation. It may be better positioned as a pre-incident tool — "what would we do if this line leaked" — used during drills and scenario planning rather than live.
Isolation certificate templates. Can you supply two or three real certificate templates from target clients? They constrain the output schema more than anything else.
Small-bore threshold and other defaults. The OSHA-based default profile needs a first pass by a process safety engineer before it ships. Who signs it off?