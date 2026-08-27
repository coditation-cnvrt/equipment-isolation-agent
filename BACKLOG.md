# Backlog

## Isolation-plan feedback

- The shared database and backend category framework is implemented. Continue separating plan feedback by domain behaviour, validation, permissions, lifecycle effects, and UI language:
  - **Input correction — partially supported.** The agent can apply local tag corrections and availability overlays before re-running validation. It cannot update authoritative UniGraph, HILT, or CNVRT data.
  - **Requirement deviation — not supported.** Add a derived isolation-requirement model, compensating-measure rules, deviation authority, approval governance, and certificate representation. A deviation must remain beside the original requirement rather than silently replacing it.
  - **Manual observation — partially supported.** The agent can include a graph-identifiable point and re-derive the plan. Add safe representation of unmodelled connections, temporary hoses, and devices absent from the authoritative graph, retaining explicit `MANUAL` provenance and raising a source-data defect.
  - **Execution failure — traversal support only.** An unavailable valve can trigger outward barrier traversal. Add field-step state, proving results, plan supersession, re-authorisation, and an execution audit workflow before treating this as field-execution support.
- Preserve the current UI boundary: expose only supported feedback actions. Do not present requirement deviations, unmodelled topology changes, or execution failures as operational capabilities until their deterministic rules and governance exist.
- Align the mature workflow with `isolation-planning-agent-ux-i1/Isolation Planning Agent v2.dc.html`: correct authoritative inputs and re-derive, record governed deviations without deleting derived requirements, and keep human-added observations visibly separate from derived content.

## Repository structure

- Replace the historical flat collection of root-level Python modules with an application-owned package such as `equipment_isolation/`.
- Group modules by responsibility, for example:
  - deterministic isolation logic under `core/`;
  - JanusGraph, UniGraph, HILT, STLM, CNVRT, and HTTP clients under `integrations/`;
  - payload, viewer, and overlay code under `presentation/`;
  - feedback, pipeline, agent, API, and domain code in dedicated subpackages.
- Move `test_gremlin_connection.py` under `tests/` or `scripts/`, and move root-level architecture/reference documents under `docs/` where appropriate.
- Verify whether the root `alembic/` directory is obsolete now that runtime migration assets live under `api/migrations/`; remove it only after CLI, source-checkout, and installed-wheel migration workflows are confirmed.
- Keep generated packaging artifacts (`build/`, `dist/`, and `equipment_isolation.egg-info/`) out of the working tree and document the commands that recreate them.
- Perform this as a dedicated structural change. Update imports, CLI entry points, package discovery, tests, and wheel verification coherently; use temporary compatibility imports if external consumers still rely on top-level modules.
