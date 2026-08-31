# Backlog

## Isolation-plan feedback

- The shared database and backend category framework is implemented. Continue separating plan feedback by domain behaviour, validation, permissions, lifecycle effects, and UI language:
  - **Input correction — partially supported.** The agent can apply local tag corrections and availability overlays before re-running validation. It cannot update authoritative UniGraph, HILT, or CNVRT data.
  - **Requirement deviation — not supported.** Add a derived isolation-requirement model, compensating-measure rules, deviation authority, approval governance, and certificate representation. A deviation must remain beside the original requirement rather than silently replacing it.
  - **Manual observation — partially supported.** The agent can include a graph-identifiable point and re-derive the plan. Add safe representation of unmodelled connections, temporary hoses, and devices absent from the authoritative graph, retaining explicit `MANUAL` provenance and raising a source-data defect.
  - **Execution failure — traversal support only.** An unavailable valve can trigger outward barrier traversal. Add field-step state, proving results, plan supersession, re-authorisation, and an execution audit workflow before treating this as field-execution support.
- Preserve the current UI boundary: expose only supported feedback actions. Do not present requirement deviations, unmodelled topology changes, or execution failures as operational capabilities until their deterministic rules and governance exist.
- Align the mature workflow with `docs/isolation-planning-agent-ux-i1/Isolation Planning Agent v2.dc.html`: correct authoritative inputs and re-derive, record governed deviations without deleting derived requirements, and keep human-added observations visibly separate from derived content.

## Compatibility cleanup

- Remove the temporary root command launchers (`run.py`, `agent.py`, `api.py`,
  and `eval_compare.py`) after downstream automation has migrated to the
  installed `equipment-isolation*` console commands.
