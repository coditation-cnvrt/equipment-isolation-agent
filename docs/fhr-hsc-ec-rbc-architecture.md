# FHR, HSC, EC, and RBC Architecture

**Status:** Proposed deterministic safety-core design
**Scope:** M1 isolation planning; reusable controlled inputs for M3
**Normative sources:** `Isolation_Planning_Agent_Requirements_v1.md` and `Isolation_Planning_Agent_Technical_Solution.md`

Implementation status and the revised delivery order are tracked in
[`fhr-implementation-next-steps.md`](fhr-implementation-next-steps.md). The
2026-09-08 corrective slice preserves ordered path facts through plan storage and
locks drawing-defect governance before runs, but does not activate FHR/HSC/EC/RBC
classification or controlled-input admission.

The subsequent [persistence foundation](fhr-controlled-input-foundation.md) adds
immutable controlled revisions and incomplete manifests in migration 0009. Runtime
admission and safety classification remain pending.

## 1. Decision

FHR resolution, HSC classification, EC classification, RBC derivation, barrier
admissibility, and boundary selection form one deterministic pipeline. RBC is
not a validation label applied to an already-selected valve. It is an input to
path traversal: each path continues outward until its required configuration is
topologically satisfied or the path is declared unresolved or not isolatable.

The LLM may help translate a work description into a structured scope. It does
not resolve fluids, assign HSC or EC, select an RBC, admit a device, terminate a
path, or assign assurance status.

## 2. Safety invariants

- Classify the live-side fluid independently for every process path.
- Resolve fluid from graph service code through an approved, pinned FHR
  revision. Tags, labels, geometry, and visual proximity do not prove service.
- Treat an unmapped service code as `UnknownFluid`, HSC-4, and a blocking data
  gap. Do not silently use an equipment-level fluid.
- Derive EC from structured work scope. Do not use the legacy
  `high_risk_service` boolean as a substitute.
- Resolve one RBC for each path before evaluating barrier candidates.
- Count barriers only when deterministic admissibility and topology checks pass.
- Do not let a positive barrier or bleed on one branch satisfy another branch.
- Continue through unavailable or inadmissible devices, including control
  valves and check valves, rather than terminating traversal at them.
- Preserve every unresolved process path in validation and persistence even
  when it has no selected isolation point.
- `core.validator.validate()` remains the only authority for
  `assurance_status` and must fail closed when any required path assessment is
  unsatisfied.
- Pin all safety inputs and the rule-engine build. Re-running the same canonical
  inputs must produce byte-identical derivation output.

## 3. End-to-end flow

```text
approved controlled inputs + structured scope + graph/HILT snapshot
                              |
                              v
                    immutable SafetyContext
                              |
                              v
             enumerate complete process boundary paths
                              |
                 for each path independently
                              |
                              v
    service code -> FHR mapping -> live-side FluidResolution
                              |
                              v
               fluid + operating P/T + PSD -> HSC
                              |
                              v
                    structured work scope -> EC
                              |
                              v
             HSC x EC matrix + SIC rules -> RBC
                              |
                              v
      nearest-first configuration-aware barrier traversal
                              |
                              v
     satisfied | unbounded | not isolatable | safety limit
                              |
                              v
          union path solutions -> evidence -> validator
                              |
                              v
       immutable plan version + derivation/input snapshots
```

## 4. Canonical contracts

These are domain contracts, not ORM or API models. They should be immutable and
serializable using explicit `to_dict()` projections with canonical ordering.

```text
SafetyContext
  mode
  planning_context
  plan_time
  work_scope
  fhr
  sic
  psd
  graph_snapshot
  rule_engine
  input_manifest

ControlledInputRef
  input_type             fhr | sic | psd | graph | patterns | sar
  document_id
  revision_id
  revision_label
  content_hash
  approval_status
  approved_by
  approved_at

BoundaryPath
  path_id
  source_component_id
  ordered_node_ids
  ordered_link_ids
  ordered_edge_labels
  service_code
  nominal_diameter_dn
  line_specification
  operating_pressure_barg
  operating_temperature_c
  terminal
  provenance

FluidResolution
  service_code
  fluid_code
  status                   resolved | unknown | invalid
  fluid_properties
  fhr_revision
  mapping_scope
  gaps

HazardAssessment
  hsc                      1 | 2 | 3 | 4
  base_hsc
  fired_rules
  override
  psd_modifier
  gaps

ExposureAssessment
  ec                       A | B | C | D
  base_ec
  fired_rules
  duration_escalation
  positive_isolation_floor

RequiredBarrierConfiguration
  barrier_count
  bleed_required
  positive_barrier_count
  physical_disconnection_required
  both_sides_blinded_required
  source_matrix_cell
  sic_override
  escalations
  floors

DeviceAssessment
  device_id
  path_index
  device_class
  admissible
  barrier_value
  positive
  permitted_roles
  fired_rules
  missing_properties

PathAssessment
  path
  fluid
  hazard
  exposure
  required_configuration
  evaluated_devices
  selected_points
  bleed
  proving
  status
  blockers
  derivation_trace
```

One physical point may participate in multiple `PathAssessment` records. The
path-point relationship is many-to-many; fluid, HSC, and RBC remain properties
of a path use, not of the physical device.

## 5. Controlled-input lifecycle

FHR and SIC are shared controlled sources, not plan feedback and not drawing
defects. The server resolves approved revisions; a run request may provide an
optimistic expected revision but may not submit arbitrary safety content.

Minimum persistent model:

| Record | Purpose |
|---|---|
| `controlled_input` | Stable FHR or SIC document identity and scope |
| `controlled_input_revision` | Immutable submitted content, validation result, approval decision, and hash |
| `run_input_manifest` | Locked canonical run context and aggregate input hash |
| `run_input_manifest_item` | Relational pin to every controlled revision consumed by the run |
| `plan_version_invalidation` | Append-only record that a pinned revision was superseded |

Recommended first scopes:

- FHR: drawing/job scoped until the client supplies a stable site/unit document
  hierarchy.
- SIC: collection scoped.
- Mock FHR: development fixture only; its `draft_mock_unapproved` status must
  never satisfy M1/M3 admission.

The manifest must be locked before the worker starts. Runtime stages load
content by pinned revision ID, never by querying the current head again.
`PlanVersion.input_hash` should become the manifest hash for new versions while
historical request hashes remain explicitly identified as legacy.

Approving a replacement FHR or SIC revision does not rewrite an old run or plan.
It appends invalidation records for affected plan versions and requires a full
child derivation. Safety authorisation is a later lifecycle capability; current
plans remain advisory drafts.

## 6. Runtime stage ownership

### 6.1 Admission and context assembly

Before `run_agent_pipeline()`:

1. Resolve the final drawing/job and exact selected asset.
2. Resolve and validate approved FHR and effective SIC revisions.
3. Snapshot PSD, work scope, shared asset conditions, and approved corrections.
4. Build and persist a locked input manifest.
5. Construct `SafetyContext` from the pinned inputs.

Missing mandatory FHR is an admission error for M1/M3, not a late validator
warning. An effective SIC is mandatory, but may be the versioned product default
when no client delta exists.

### 6.2 Path fact preservation

Both HILT and UniGraph traversal must preserve ordered link identity and relevant
facts. At minimum this includes service code, nominal diameter, line/spec class,
operating/design pressure and temperature, spec breaks, and source provenance.

HILT adjacency must retain link records instead of only neighboring node IDs.
UniGraph branch records must retain ordered node/edge facts rather than only the
terminal candidate properties.

### 6.3 Classification

Pure domain functions consume explicit values and return typed assessments:

```text
resolve_fluid(path, fhr) -> FluidResolution
derive_hsc(fluid, path_conditions, psd) -> HazardAssessment
derive_ec(work_scope, sic) -> ExposureAssessment
derive_rbc(hazard, exposure, path, sic) -> RequiredBarrierConfiguration
assess_device(device, path, hazard, exposure, sic) -> DeviceAssessment
```

These functions have no database, network, filesystem, clock, random, or LLM
dependency. They record rule IDs and every SIC parameter consumed.

### 6.4 Configuration-aware traversal

Replace first-selectable-device stopping in
`core.boundary._walk_component_topology()` and the equivalent HILT traversal.
Traversal state carries the ordered path and all assessed device occurrences.

At each new node:

1. Extend path facts.
2. Assess any device at that location.
3. Evaluate whether selected admissible devices satisfy the path RBC in series.
4. If a bleed is required, verify its topological position and safe PSD
   destination.
5. Stop only when the complete configuration is satisfied.
6. Otherwise continue outward until terminal, unresolved connector, next
   equipment item, or safety limit.

Terminal states are:

- `satisfied`
- `unbounded_live_path`
- `not_isolatable`
- `terminal_without_configuration`
- `safety_limit_reached`

Do not apply the current global candidate cap to safety path solutions. Any UI
limit is a presentation concern after complete assessments exist.

### 6.5 Obligations, evidence, and validation

`core.obligations` should project one process obligation from each
`PathAssessment`, including unsatisfied paths. `core.evidence` should verify each
path's selected point roles and proving requirements rather than relying only on
global point-ID sets.

The validator must assign `not_isolated` when any required process path has no
satisfied RBC. Manual property verification or incomplete proving may yield
provisional status only after the required path configuration itself exists.
Unknown fluid, unbounded paths, and not-isolatable paths also set
`blocks_authorisation=true` in structured findings.

## 7. Work-scope transition

Replace the legacy scope as an EC input with:

```text
WorkScope
  activity_type
  expected_duration_days
  shift_coverage            single_shift | multiple_shifts
  containment_break
  continuously_attended
  personnel_enter_boundary
  hot_work_on_or_within_boundary
  equipment_leaves_site
```

Keep the existing booleans only while old clients or persisted requests require
them. `high_risk_service` must not weaken or strengthen a derived RBC once the
new path assessments are active.

## 8. API and UI projection

Run creation should return structured 409/422 domain errors for missing,
unapproved, invalid, or unexpectedly changed controlled inputs. It should not
collapse these into service-unavailable errors.

Plan detail should expose controlled-input references and `path_assessments`.
For each path the UI needs:

- service and resolved fluid;
- HSC rule/override and PSD dependency;
- EC driver and duration escalation;
- RBC matrix cell, SIC override, floors, and escalations;
- selected barriers, roles, bleed, and proving method;
- rejected/inadmissible devices where relevant;
- blockers and source provenance.

The Corrections page may report an FHR gap but must not edit the FHR. Controlled
document correction and approval require a separate governed administration
surface.

## 9. Delivery slices

The original domain-first sequence is superseded by the persistence-first
[detailed implementation plan](fhr-implementation-plan.md):

1. Controlled-input schema, immutable revisions and repository transactions.
2. Supported input contracts, source capture and immutable run admission.
3. Pure classification and observational assessments.
4. Configuration-aware traversal and authoritative validation/persistence.
5. Complete API/UI review workflows and governed-mode activation.

Collect safety and source-contract decisions alongside the persistence work.
Intermediate observational results must not claim RBC compliance from the existing
first-barrier algorithm. API/UI adapters accompany public contract changes rather
than waiting until the final batch.

## 10. Verification matrix

Minimum deterministic coverage:

- every HSC rule, boundary value, override, unknown mapping, and missing property;
- EC A-D, overlapping drivers, duration escalation, and positive-isolation floor;
- all 16 RBC cells and every valid/invalid SIC override;
- all device admissibility rows and required-property gaps;
- small-bore valve-plus-closure requirement;
- two barriers in series versus parallel branches;
- bleed between barriers and safe versus live destination;
- check/control/unavailable device continuation;
- split, cycle, and reconverging paths;
- positive-isolation and outward-search fallback order;
- unresolved connector, terminal, not-isolatable, and safety-limit outcomes;
- shared physical point used by paths with different fluids/RBCs;
- no cross-branch leakage of positive or proving evidence;
- randomized input order yielding byte-identical canonical output;
- missing/unapproved FHR admission and superseding-revision invalidation;
- agent orchestration cannot omit or override deterministic results.

## 11. Standards decisions required before classification behavior

The source requirements do not settle these points. They must be approved before
encoding safety behavior:

1. Confirm that the highest matching HSC and highest matching EC always win.
2. Confirm whether the PSD one-class reduction may lower an explicit FHR
   `hsc_override`, and confirm that it never lowers `UnknownFluid` HSC-4.
3. Define bleed topology for matrix cells requiring one valve plus bleed.
4. Confirm whether every two-barrier cell requires an intermediate bleed even
   where the matrix omits `+ bleed`.
5. Define safe PSD bleed-destination states and the positive-isolation fallback
   strength when DBB cannot be achieved.
6. Define authoritative precedence for service code and operating P/T across
   HILT, UniGraph, line-number parsing, FHR, and PSD.
7. Define handling for a mapped FHR row with missing properties needed by the
   classifier and whether `two_phase` is treated as gas/flashing.
8. Define FHR mapping precedence for overlapping global and unit scopes.

Until these decisions are made, the implementation should fail closed for the
affected path rather than silently choosing a lighter requirement.
