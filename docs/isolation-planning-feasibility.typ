#set page(paper: "a4", margin: (x: 18mm, y: 18mm))
#set text(font: "Noto Sans", size: 10pt, fill: rgb("1f2937"))
#set par(leading: 0.65em)
#set heading(outlined: false)
#set table(
  align: (left + top),
  fill: (x, y) => if y == 0 { rgb("e2e8f0") } else if calc.even(y) { rgb("f8fafc") },
  inset: 6pt,
  stroke: 0.35pt + rgb("cbd5e1"),
)
#show table.header: set text(weight: "bold", fill: rgb("111827"))

= Current Isolation Agent UI Delivery Timeline

#strong[Objective:] turn the current Equipment Isolation Agent into a usable review UI for its existing advisory functionality. The UI will expose the agent's current inputs, run progress, P&ID overlays, isolation findings, evidence, warnings, procedure, impact analysis, and audit trace in a clear review workflow.

#strong[Estimate:] #strong[6 engineering days] for one engineer.

== Scope

The work reuses the current agent pipeline and its structured result. It does not add new plant-data sources, safety-authorisation workflow, or new isolation-engineering logic.

#strong[Included:]

- Equipment and project-context selection.
- Agent-run submission, progress, completion, failure, and retry states.
- P&ID image and candidate/boundary overlays.
- Readable presentation of selected isolation candidates, topology findings, coverage, evidence, assurance status, relief findings, instrument context, and downstream impacts.
- LOTO procedure, field holds, warnings, and restoration guidance.
- Agent tool-call trace and the evidence supporting visible findings.
- Saved run results and a usable review of prior runs.
- Responsive desktop and mobile review experience.
- Contract and regression hardening for the existing agent output.

#strong[Excluded:]

- FHR, PSD, SIC, SAR, isometric, C&E/SIF, SLD, permit-register, or live isolation-register integrations.
- Site-authorised barrier decisions, permit issuance, field execution, authorisation, or lifecycle controls.
- New safety logic beyond presenting current deterministic/agent results clearly and preserving their warnings.

== Delivery Timeline (Current UI)

#table(
  columns: (20%, 20%, 45%, 15%),
  table.header([Workstream], [Deliverable], [Work], [Estimate]),
  [1. Foundation], [Usable run workflow], [Create the UI shell; equipment and project-context selection; submit an agent run; show queued, running, complete, and failed states; load a completed run result.], [1 day],
  [2. Plan review], [Isolation-plan view], [Present equipment context, assurance status, warnings, selected candidates, topology paths, coverage, relief findings, evidence, instrument context, and downstream impact in a reviewable hierarchy.], [1 day],
  [3. P&ID review], [Drawing review], [Display the source P&ID, existing candidate/boundary overlays, tag labels, legend, and a details panel linked to result data.], [1 day],
  [4. Procedure], [Field-oriented procedure view], [Present the existing LOTO procedure, isolation order, verification/field holds, warnings-before-steps, restoration guidance, and clear advisory-status language.], [0.5 day],
  [5. Evidence and trace], [Explainability view], [Expose evidence classification, validator rationale, unavailable-analysis reasons, agent audit trace, and source references without exposing raw internal pipeline payloads by default.], [0.5 day],
  [6. Run history], [Saved-result access], [Link to existing saved result, P&ID, and trace artifacts; no run-management interface beyond current artifacts.], [0.5 day],
  [7. Hardening], [Release-ready current-agent UI], [Handle empty/missing data, agent failures, loading states, responsive layout, output-contract validation, and focused offline regression coverage.], [1.5 days],
  [Total], [Current-agent UI], [A usable advisory review product over all capabilities already produced by the current agent.], [#strong[6 days]],
)

== Implementable Requirements Timeline

This is a focused additional increment after the current UI estimate. It improves the current graph-based agent and its review output only. It excludes lifecycle/authorisation, offline field execution, emergency mode, permits, canonical exports, multi-tenancy, and every requirement blocked by unavailable plant data or upstream-platform dependencies.

#table(
  columns: (28%, 24%, 34%, 14%),
  table.header([Workstream], [Requirements], [Deliverable], [Estimate]),
  [Operational review language], [REQ-OM-01, REQ-IN-12], [Use field-oriented action/proving wording and add the electrical-out-of-scope powered-device checklist.], [2--3 days],
  [Scope intake], [REQ-IN-15..16], [Capture the missing structured work-scope fields needed by the current review and warning output.], [2--3 days],
  [Topology and evidence review], [REQ-F1-02, REQ-D-03, REQ-D-07], [Expand current direction-independent graph traversal, show candidate series relationships, and add the valve-integrity limitation statement.], [2--3 days],
  [Procedure and explainability], [REQ-F6-01, REQ-F6-04, REQ-F8-03], [Add structured per-step fields, generic hold-point presentation, and clear confidence categories to the current advisory output.], [2--3 days],
  [Regression hardening], [REQ-SA-02, REQ-SA-05], [Add focused requirements-to-test mapping and offline regression cases for the current-agent success, gap, and failure paths.], [2--3 days],
  [Total], [Focused implementable increment], [Additional work after the six-day current UI increment; excludes blocked data, operational workflow, and new product modes.], [#strong[10--15 days]],
)

== Requirements Feasibility

#table(
  columns: (24%, 18%, 58%),
  table.header([Requirement], [Feasibility], [Assessment]),
  [REQ-OM-01: Operational language], [#strong[Implementable]], [Outputs include tags and generic procedure language; add consistent field location, action, and proving terminology.],
  [REQ-OM-02: Offline tablet execution], [#strong[Implementable]], [Requires a field execution UI, offline storage, synchronisation, and a glove-oriented tablet workflow.],
  [REQ-OM-03: Plan lifecycle], [#strong[Implementable]], [Requires a controlled lifecycle and immutable audit trail for plan state changes and edits.],
  [REQ-OM-04: Authorisation record], [#strong[Implementable]], [Requires a human authoriser, approval timestamp, and approved plan/graph/rule-version record.],
  [REQ-OM-05: Re-authorisation after change], [#strong[Implementable]], [Requires change detection, safety-significance diff, invalidation, and re-authorisation workflow.],
  [REQ-OM-06: Shift handover], [#strong[Implementable]], [Requires point-level execution state and a handover view.],
  [REQ-ARCH-01: Deterministic safety core], [#strong[Implementable]], [Candidate selection, validation, and LOTO phases are deterministic; add HSC/RBC derivation, exhaustive traversal, barrier rules, and sequencing core.],
  [REQ-ARCH-02: LLM confined to periphery], [#strong[Implementable]], [The deterministic validator remains authoritative; complete the verified safety core before confining the LLM to the specified peripheral role.],
  [REQ-ARCH-03: Verified LLM plan content], [#strong[Implementable]], [Requires a complete fired-rule trace and a visual distinction for generated narrative.],
  [REQ-IN-01: Version-stamped UniGraph], [#strong[Implementable with UniGraph support]], [Requires pinning and recording an authoritative UniGraph graph version.],
  [REQ-IN-02: Unknown fluid], [#strong[Implementable]], [Requires the HSC-4 fallback, gap record, and non-authorisable status for an unmapped service code.],
  [REQ-IN-03: FHR revision], [#strong[Not implementable with current inputs]], [No controlled FHR or FHR revision is available to record on a plan.],
  [REQ-IN-04: PSD assumptions], [#strong[Not implementable with current inputs]], [No PSD declarations exist to reproduce on a certificate with the declarer's identity.],
  [REQ-IN-05: Incomplete PSD defaults], [#strong[Implementable]], [Requires conservative PSD defaults and explicit provenance.],
  [REQ-IN-06: PSD validity], [#strong[Not implementable with current inputs]], [No PSD validity record or authorisation gate exists.],
  [REQ-IN-07: SIC derivation trace], [#strong[Implementable with SIC]], [Requires a versioned SIC and parameter-level derivation trace.],
  [REQ-IN-08: Default SIC], [#strong[Implementable]], [Generic conservative policy exists; make it a controlled OSHA-aligned SIC profile.],
  [REQ-IN-09: SAR hot-work gate], [#strong[Not implementable with current inputs]], [No SAR supports the required hot-work permit gate.],
  [REQ-IN-10: SAR effort/access], [#strong[Not implementable with current inputs]], [No SAR supports effort estimation or emergency accessibility.],
  [REQ-IN-11: Isometric geometry], [#strong[Blocked by dependency]], [Drawing and Document AI extraction of geometry is not available in UniGraph.],
  [REQ-IN-12: Electrical-out-of-scope placeholder], [#strong[Implementable]], [Requires a standing electrical limitation section and powered-device checklist.],
  [REQ-IN-13: Electrical isolation register], [#strong[Not implementable with current inputs]], [No electrical isolation register input or sequence integration exists.],
  [REQ-IN-14: SLD electrical hierarchy], [#strong[Blocked by dependency]], [No Convert-for-SLD hierarchy is available.],
  [REQ-IN-15: Work-scope inputs], [#strong[Implementable]], [Equipment-tag scope is supported; add natural language, CMMS, graphical, and named-system intake.],
  [REQ-IN-16: Work-scope details], [#strong[Implementable]], [Limited scope flags exist; add activity, duration, shift, containment, entry, hot-work, and off-site fields.],
  [REQ-D-01: RBC matrix overrides], [#strong[Implementable with SIC]], [Requires a versioned SIC matrix, override justification, approver, and derivation trace.],
  [REQ-D-02: Small-bore rule], [#strong[Not implementable with current inputs]], [Nominal diameter and a controlled small-bore threshold are unavailable.],
  [REQ-D-03: Series barrier verification], [#strong[Implementable]], [HILT topology can identify candidate valve connectivity; add complete per-path barrier verification.],
  [REQ-D-04: Valid bleed], [#strong[Not implementable with current inputs]], [This requires per-path barriers, bleed topology, and PSD destination state.],
  [REQ-D-05: No-bleed escalation], [#strong[Not implementable with current inputs]], [Outward topology search is feasible, but a compliant result requires RBC, bleed, and flanged-joint inputs.],
  [REQ-D-06: Proving method], [#strong[Not implementable with current inputs]], [SIC proving criteria and validated selected barriers are unavailable.],
  [REQ-D-07: Valve-integrity limitation], [#strong[Implementable]], [Current outputs include warnings and field holds; add the required standing limitation statement on every plan.],
  [REQ-D-08: Failed-proving re-derivation], [#strong[Implementable]], [Requires field proving capture, plan supersession, and re-authorisation workflow.],
  [REQ-D-09: Derivation trace], [#strong[Not implementable with current inputs]], [No HSC/EC/RBC derivation exists to trace.],
  [REQ-F1-01: Boundary to RBC], [#strong[Not implementable with current inputs]], [Traversal exists in limited form, but cannot terminate at a required barrier configuration until HSC/RBC are available.],
  [REQ-F1-02: Direction-independent traversal], [#strong[Implementable]], [Current traversal is bounded/local; expand it to traverse all authoritative UniGraph paths regardless of direction.],
  [REQ-F1-03: Per-path HSC/RBC], [#strong[Not implementable with current inputs]], [FHR, PSD, SIC, device attributes, and complete scope are absent.],
  [REQ-F1-04: Nested boundaries], [#strong[Not implementable with current inputs]], [A PSD with active boundary points and HSC/RBC inputs is absent.],
  [REQ-F1-05: Shared isolation points], [#strong[Not implementable with current inputs]], [A PSD active-isolation register with dependency/ownership data is absent.],
  [REQ-F1-06: Package-unit boundaries], [#strong[Blocked by dependency]], [Current UniGraph code does not model package units or declared battery-limit connections.],
  [REQ-F1-07: Non-isolatable paths], [#strong[Not implementable with current inputs]], [The reporting UI is possible, but the required no-valid-RBC conclusion is not.],
  [REQ-F2-01: Residual and stored energy], [#strong[Not implementable with current inputs]], [Isometrics, volumes, elevation, thermal/chemical service data, and mechanical design data are absent.],
  [REQ-F2-02: Energy mitigation], [#strong[Not implementable with current inputs]], [Energy inventory, vent/drain/purge topology, and PSD destination state are absent.],
  [REQ-F2-03: Undrained low points], [#strong[Not implementable with current inputs]], [Isometric low-point and drain-location data are absent.],
  [REQ-F2-04: Mechanical energy], [#strong[Not implementable with current inputs]], [Equipment-specific rotation, spring, accumulator, and tension data are absent.],
  [REQ-F3-01: Instrument impulse isolation], [#strong[Not implementable with current inputs]], [Root-valve/manifold topology and DP sequence data are absent.],
  [REQ-F3-02: Control consequence], [#strong[Not implementable with current inputs]], [Loop, final-element, interlock, and fail-action data are absent.],
  [REQ-F3-03: C&E overrides], [#strong[Blocked by dependency]], [Queryable C&E data from the Drawing and Document AI Agent is unavailable.],
  [REQ-F3-04: SIF voting/inhibition], [#strong[Not implementable with current inputs]], [SIF voting, C&E, deviation workflow, and SIC duration policy are absent.],
  [REQ-F3-05: Utility-dependent final elements], [#strong[Not implementable with current inputs]], [Utility dependencies, final-element fail positions, and utility state are absent.],
  [REQ-F3-06: Safety-critical impairments], [#strong[Not implementable with current inputs]], [Safety-system relationships and an impairment workflow are absent.],
  [REQ-F4-01: Depressurisation], [#strong[Not implementable with current inputs]], [Vent topology, PSD destination state, SIC targets, and a valid derived boundary are absent.],
  [REQ-F4-02: Drain-down], [#strong[Not implementable with current inputs]], [Drain topology, volumes, elevations, low points, and PSD destination state are absent.],
  [REQ-F4-03: Purge/inerting], [#strong[Not implementable with current inputs]], [SIC purge rules, connection topology, volumes, targets, and test points are absent.],
  [REQ-F4-04: Nitrogen/asphyxiation], [#strong[Not implementable with current inputs]], [A generic warning is possible, but a derived nitrogen plan and entry context are absent.],
  [REQ-F4-05: Gas tests], [#strong[Not implementable with current inputs]], [Test-point topology, SIC criteria, repeat intervals, and permit context are absent.],
  [REQ-F5-01: Live-plant impact], [#strong[Not implementable with current inputs]], [HILT reachability flags possible impacts, but a complete derived boundary and live plant state are absent.],
  [REQ-F5-02: Relief integrity], [#strong[Not implementable with current inputs]], [Relief relationships, PSD state, CSO/LO state, and deviation workflow are absent.],
  [REQ-F5-03: Availability], [#strong[Not implementable with current inputs]], [PSD availability and train/fire-pump/detector coverage data are absent.],
  [REQ-F5-04: Plant-mode viability], [#strong[Not implementable with current inputs]], [PSD plant mode and mode-specific service requirements are absent.],
  [REQ-F5-05: SIMOPS], [#strong[Not implementable with current inputs]], [Active isolation and permit records with scope, location, status, and timing are absent.],
  [REQ-F6-01: Numbered sequence], [#strong[Implementable]], [Generic LOTO steps exist; add per-device actions, end positions, roles, proving methods, and dependencies.],
  [REQ-F6-02: Safe sequence], [#strong[Not implementable with current inputs]], [The fixed LOTO phase order is present; derived process, joint, drain/purge, blind, and energy dependencies are absent.],
  [REQ-F6-03: Reinstatement], [#strong[Not implementable with current inputs]], [Blind IDs, override records, normal positions, test requirements, and execution state are unavailable.],
  [REQ-F6-04: Signed hold points], [#strong[Implementable]], [Generic holds can be displayed; add applicable-hold derivation and sign-off workflow.],
  [REQ-F6-05: Partial re-isolation], [#strong[Implementable]], [Requires a point-level lifecycle and staged-work model.],
  [REQ-F7-01: Isolation schedule], [#strong[Not implementable with current inputs]], [Current output has candidates/procedure, but location, lock/tag, discipline, and execution data are absent.],
  [REQ-F7-02: Marked-up P&ID], [#strong[Not implementable with current inputs]], [Candidate overlays exist, but a complete derived boundary/blind/bleed/drain/vent markup requires unavailable plan inputs.],
  [REQ-F7-03: Bill of materials], [#strong[Not implementable with current inputs]], [Piping class, geometry, blind/gasket data, and complete derivation are absent.],
  [REQ-F7-04: Certificate draft], [#strong[Not implementable with current inputs]], [A site template and complete controlled plan data are absent.],
  [REQ-F7-05: Assumption/gap/deviation register], [#strong[Implementable with PSD]], [Warnings and gaps exist; add a unified PSD/deviation/impairment/override register.],
  [REQ-F7-06: Effort estimate], [#strong[Not implementable with current inputs]], [SAR, blind data, and duration/discipline data are absent.],
  [REQ-F7-07: Canonical export], [#strong[Implementable]], [Requires a documented canonical JSON/XML plan schema and CMMS adapters.],
  [REQ-F8-01: Point derivation], [#strong[Not implementable with current inputs]], [Evidence and traces exist, but HSC/EC/RBC inputs needed for a complete point derivation are absent.],
  [REQ-F8-02: Interrogatives], [#strong[Implementable with required inputs]], [Requires a what-if and complete path-explanation interface backed by versioned inputs.],
  [REQ-F8-03: Per-point confidence], [#strong[Implementable]], [Requires categories separating graph, rule, declared, and missing-data conclusions.],
  [REQ-F8-04: Byte-identical reproducibility], [#strong[Implementable with version pinning]], [Requires all inputs to be version-pinned and a deterministic planning path.],
  [REQ-E-01: Emergency advisory position], [#strong[Implementable]], [Requires an emergency-mode output and standing emergency advisory statement.],
  [REQ-E-02: Emergency enablement], [#strong[Implementable]], [Requires site-level emergency-mode configuration.],
  [REQ-E-03: Emergency intake], [#strong[Implementable]], [Requires an emergency event input and natural-language emergency parsing.],
  [REQ-E-04: Emergency PSD fallback], [#strong[Implementable]], [Requires emergency-mode PSD handling and an all-live fallback.],
  [REQ-E-05: Flow-limiting actions], [#strong[Implementable with UniGraph data]], [Requires emergency release-source traversal and action-ranking logic.],
  [REQ-E-06: Remote isolation], [#strong[Implementable with UniGraph data]], [Requires a remote-device action model and emergency prioritisation.],
  [REQ-E-07: Residual inventory], [#strong[Blocked by dependency]], [Line and equipment volume data are absent.],
  [REQ-E-08: Blowdown route], [#strong[Not implementable with current inputs]], [Requires blowdown topology and destination state.],
  [REQ-E-09: Manual accessibility], [#strong[Blocked by dependency]], [SAR accessibility data is unavailable.],
  [REQ-E-10: Escalation targets], [#strong[Blocked by dependency]], [SAR proximity and inventory data are unavailable.],
  [REQ-E-11: Plant consequences], [#strong[Implementable with required inputs]], [Requires emergency action impact analysis and plant-state context.],
  [REQ-E-12: Degraded emergency output], [#strong[Implementable]], [Requires an emergency-mode output path that reports assumptions and gaps.],
  [REQ-E-13: Progressive response], [#strong[Implementable]], [Requires an emergency response pipeline and performance implementation.],
  [REQ-E-14: Emergency logging], [#strong[Implementable]], [Requires a retained emergency output record.],
  [REQ-E-15: Emergency non-goals], [#strong[Implementable]], [Requires these constraints to be enforced by the emergency-mode workflow.],
  [REQ-P-01: Permit types], [#strong[Implementable with SIC]], [Requires permit-generation capability and SIC permit configuration.],
  [REQ-P-02: Permit/isolation link], [#strong[Implementable]], [Requires a permit model linked to a controlled isolation plan.],
  [REQ-P-03: Permit content], [#strong[Not implementable with current inputs]], [FHR, proving, gas-test, SAR, SIMOPS, and template data are absent.],
  [REQ-P-04: Permit validity], [#strong[Implementable]], [Requires a permit lifecycle and proving-validity model.],
  [REQ-P-05: Permit conflicts], [#strong[Not implementable with current inputs]], [SAR and active-permit data are absent.],
  [REQ-P-06: SAR hot-work gate], [#strong[Not implementable with current inputs]], [No SAR exists.],
  [REQ-P-07: Permit export], [#strong[Implementable]], [Requires a canonical schema and permit adapter.],
  [REQ-P-08: Permit draft only], [#strong[Implementable]], [Requires a permit workflow that preserves authorisation as a human action.],
  [REQ-SA-01: Classification argument], [#strong[Implementable with client input]], [Requires an agreed client safety-tool classification and validation strategy.],
  [REQ-SA-02: Assurance and traceability], [#strong[Implementable]], [Some deterministic code and unit tests exist; add full coverage and a requirements-to-test matrix.],
  [REQ-SA-03: Version pinning], [#strong[Implementable]], [Requires authorised plans to record the required input and model versions.],
  [REQ-SA-04: Change control], [#strong[Implementable]], [Requires formal MoC and release gates for derivation and policy changes.],
  [REQ-SA-05: Scenario regression], [#strong[Implementable]], [Requires the specification scenario catalogue to become an executable regression suite.],
  [REQ-SA-06: Independent review], [#strong[Implementable with process-safety input]], [Requires a recorded independent process-safety review.],
  [REQ-SA-07: Failure controls], [#strong[Implementable]], [Warnings and deterministic validation address some failure modes; add the full specified controls.],
  [REQ-SA-08: Limitations statement], [#strong[Implementable]], [Current outputs carry safety warnings; add the required standing limitations statement.],
  [REQ-NF-01: Performance], [#strong[Unverified]], [No representative tests demonstrate the specified M1/M2/M3 performance targets.],
  [REQ-NF-02: Scale], [#strong[Unverified]], [No tests demonstrate 500 P&IDs, 500,000 nodes, or 500 concurrent active isolations.],
  [REQ-NF-03: Immutable auditability], [#strong[Implementable]], [Agent traces exist; add an immutable audit trail across inputs, edits, authorisation, and retention.],
  [REQ-NF-04: Multi-tenancy], [#strong[Implementable]], [Requires tenant segregation and per-tenant controlled configuration.],
  [REQ-NF-05: Offline field operation], [#strong[Implementable]], [Requires offline execution and synchronisation.],
  [REQ-NF-06: Localisation], [#strong[Implementable]], [Requires configurable units and template translation.],
  [REQ-DEP-01: Graph-to-drawing links], [#strong[Implementable with Convert P&ID]], [HILT/STLM bounding boxes provide overlay coordinates; full bi-directional entity/drawing coordinate links need verification.],
  [REQ-DEP-02: Valve/joint attributes], [#strong[Implementable with Convert P&ID]], [Some component classes exist; the complete valve, position, blind, and joint attribute set must be provided.],
  [REQ-DEP-03: UniGraph versioning], [#strong[Blocked by dependency]], [Authoritative graph version/change tracking is not currently consumed by the agent.],
  [REQ-DEP-04: Package battery limits], [#strong[Blocked by dependency]], [The current UniGraph backend/parser has no package-unit or battery-limit model.],
  [REQ-DEP-05: Queryable C&E], [#strong[Blocked by dependency]], [Drawing and Document AI C&E extraction is not integrated.],
  [REQ-DEP-06: Isometric geometry], [#strong[Blocked by dependency]], [Drawing and Document AI isometric extraction is not integrated.],
  [REQ-DEP-07: Loop-drawing extraction], [#strong[Blocked by dependency]], [No loop-drawing power/signal extraction is available.],
  [REQ-DEP-08: SLD hierarchy], [#strong[Blocked by dependency]], [Convert for SLD is explicitly future work.],
  [REQ-DEP-09: Canonical export/adapters], [#strong[Implementable]], [Requires a canonical export schema and Maximo/SAP adapters.],
)

== Question

Do we need to build the PSD workflow, or will another operational system provide PSD snapshots? If we need to build it, who owns the declared plant-state data and approvals?

== Definition of Done

- A user can select an equipment tag and explicit project context, start the current agent, and follow the run to completion or a clear failure state.
- A completed result is reviewable without reading raw JSON or an HTML artifact directly.
- The user can inspect the P&ID overlay and connect a selected device or warning to its evidence and rationale.
- Procedure, warnings, assurance status, field holds, relief findings, instrument context, downstream impact, and agent trace are visible in the UI.
- Prior results remain accessible for review.
- Missing source information is shown as unavailable or requiring field review; it is never presented as a validated safety conclusion.
- The existing offline test suite and UI/API contract checks pass for normal, incomplete-data, and failed-run cases.

== Assumptions

- The current API can invoke `agent.runner.run_agent_pipeline` and persist result artifacts as described in the repository.
- Existing P&ID images, overlay data, structured output, and agent traces remain available to the UI.
- Estimates exclude stakeholder review, deployment infrastructure, design-system creation, external-data onboarding, and formal process-safety validation.
