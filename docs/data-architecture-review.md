# Equipment Isolation — Data Architecture Review

**Status:** Proposed architecture baseline for review
**Scope:** Deterministic pipeline, agent orchestration, API contracts, PostgreSQL plans, and React view models
**Purpose:** Stabilize relationships and identity semantics before adding normalized plans, corrections, authorization, or execution

## 1. Executive summary

The current application has a sound safety boundary: deterministic modules produce evidence, `validator.validate()` owns `assurance_status`, and the LLM orchestrates but cannot override validation. The main structural risk is elsewhere: the same evolving dictionaries are used as pipeline state, domain objects, API payloads, persisted JSON, and frontend input.

Recent drawing-highlight defects exposed the consequence. These values had overlapping meanings:

- UniGraph vertex ID
- HILT node ID
- source-nozzle HILT ID
- candidate ID
- result-row ID
- drawing bbox

The immediate fix separated `selection_id`, `drawing_entity_id`, `source_visual_id`, and fallback `bbox`. That separation should become a general rule throughout the system.

The recommended direction is not a wholesale rewrite. Introduce canonical identities and typed contracts at boundaries, preserve deterministic algorithms, and migrate one stage at a time. Normalize plans only after those contracts are agreed.

## 2. Current data flow

```text
CNVRT project / collection / drawing
             │
             ├── HILT graph + symbol library + STLM geometry
             │
UniGraph project / traversal source
             │
             └── equipment + components + traversed vertices
                              │
                              ▼
                     fetch_boundaries()
                              │ cumulative dict
                              ▼
                      find_candidates()
                              │ cumulative dict
                              ▼
                       resolve_bboxes()
                              │ adds HILT/STLM/raw payloads
                              ▼
        obligations / relief / instrument context / evidence
                              │ cumulative dict
                              ▼
                       plan_requests()
                              │ cumulative dict
                              ▼
                         validate()
                              │ authoritative status
                              ▼
                  impact / LOTO / final payload
                              │
              ┌───────────────┴────────────────┐
              ▼                                ▼
      PostgreSQL run JSONB             React view models
              │                                │
              ▼                                ▼
      run-to-draft plan link       HILT-native or bbox overlay
```

Both runners invoke the same deterministic modules. The agent runner stores each stage in `AgentSession`, but tool functions also mutate earlier stage dictionaries and sometimes patch the final payload after it has been assembled.

## 3. Existing representation layers

| Layer | Current representation | Responsibility | Structural concern |
|---|---|---|---|
| External CNVRT | Raw JSON | Projects, drawings, HILT, STLM, symbols | External naming and coordinate systems leak downstream |
| External UniGraph | Normalized vertex dictionaries | Authoritative execution topology | IDs are not explicitly project-scoped |
| Pipeline configuration | Frozen dataclasses in `config.py` | Context, policy, legacy work scope | `project_id` can mean UniGraph project; scope is incomplete |
| Pipeline domain | Some frozen dataclasses in `domain/models.py` | Candidate classification, bbox, impact | Candidate becomes a mutable dictionary immediately |
| Pipeline stage state | Cumulative dictionaries | Carries all prior and new stage data | No declared ownership; stages mutate shared state |
| Agent state | `AgentSession` fields plus dictionaries | Server-side stage storage and trace | Analyses are copied into several prior snapshots |
| API request | Pydantic models | Validates run inputs | Selected HILT equipment identity is absent; tag is primary input |
| API result | Raw final payload dictionary | UI-facing advisory result | No versioned response contract; fields mix domain and display concerns |
| Run persistence | JSONB request/result/trace/event | Immutable execution record | Appropriate for run provenance, but not normalized plan identity |
| Plan persistence | Plan/version/run-link tables | Stable draft identity and provenance | Scope/assets still read through linked-run JSON |
| Frontend API model | Handwritten TypeScript types | Consumer contract | Duplicates backend concepts and derives missing identity/state |
| Frontend view state | React IDs and derived arrays | Selection and rendering | Presentation identity can be confused with domain identity |

## 4. Principal findings

### 4.1 Identity is encoded in field names, not in types

`candidate_id` may be a UniGraph vertex ID for graph-discovered candidates or a HILT UUID for topology-authoritative candidates. `visual_id` has meant a prospective drawing identity, while `source_visual_id` means the source nozzle. IDs are frequently typed as `Any`, `str | number`, or unqualified strings.

Consequences:

- IDs from different source systems can compare equal accidentally.
- A tag or source nozzle can be used when a physical isolation device is intended.
- Project/drawing scope is not carried with an external ID.
- A graph reimport can change a numeric UniGraph vertex ID.

### 4.2 The target equipment request is tag-first

The frontend knows the selected HILT node ID, but `IsolationRunRequest` sends only `equipment_tag`. `boundary._fetch_equipment_vertices()` searches by tag-like properties and can return more than one equipment vertex. The pipeline then traverses every matched vertex.

Tags are useful labels but are not durable identities. Execution should verify the selected HILT node against exactly one project-scoped UniGraph asset.

### 4.3 Pipeline stage contracts are implicit

Most stages return `{**prior_data, new_fields...}`. This preserves information conveniently but makes it difficult to answer:

- Which stage owns `candidates`?
- Which candidate fields are guaranteed after bbox resolution?
- Whether `instrument_context` is advisory metadata or validation evidence?
- Whether an earlier stage snapshot may be mutated later?

`AgentSession` currently stores nominal stage snapshots, but tool implementations update multiple snapshots and the final payload in place. This weakens audit semantics because a variable named `bbox_data` may contain later obligation and relief analysis.

### 4.4 Typed candidates are not the actual inter-stage contract

`IsolationCandidate` is used to construct initial candidates, then serialized to a dictionary. Later stages add many undeclared fields through `extra`, including geometry, source identity, branch data, topology provenance, and flow roles. No later stage reconstructs or validates the dataclass.

The model currently documents initial construction rather than the actual lifecycle.

### 4.5 Physical devices and path usages are conflated

One physical isolation device may cover multiple source paths. Current candidate deduplication combines paths into `source_paths`, while topology analysis can create branch-specific candidate records. The final payload can therefore contain repeated references to one physical device.

A durable plan needs separate concepts:

- physical isolation device
- plan-version isolation point decision
- boundary/path coverage relation

### 4.6 Geometry lacks an explicit coordinate-frame contract

HILT node centers use a bottom-left drawing coordinate convention and are transformed by the viewer. Backend STLM/HILT bboxes are image-space top-left rectangles. Rotation is native to the HILT node but absent from a simple bbox.

The system now correctly prefers native HILT geometry and uses bbox geometry as fallback, but the contract should explicitly state the coordinate frame and source.

### 4.7 Work scope has three inconsistent shapes

- API: four legacy booleans
- `config.WorkScope`: the same booleans plus policy behavior
- Target plan model: activity, duration, containment break, personnel entry, hot work, equipment leaving site, and risk context

The frontend also has work-scope text that is not submitted. New plan behavior should not be built on the legacy scope shape.

### 4.8 Saved plans remain projections over execution JSON

`isolation_plan` and `plan_version` are stable, but list/detail queries join the derivation run and derive equipment, context, assurance, and request details from JSONB. This is acceptable for the transitional run-to-draft bridge, not for authorization or execution.

### 4.9 Validation authority is correct but point decisions are reconstructed by the frontend

The validator returns ID sets such as `barrier_candidate_ids` and `manual_review_candidate_ids`. The frontend joins those sets back to points and derives `validation_state`. That is safe only while candidate identity is unambiguous and every consumer implements the same precedence.

The backend should publish an explicit point-level decision projection while retaining the authoritative validator record.

## 5. Canonical terminology

The following terms should be used consistently.

| Term | Meaning |
|---|---|
| **Planning context** | Explicit CNVRT project, collection, drawing/job, and UniGraph project scope |
| **Target asset** | Equipment whose work scope requires isolation planning |
| **Asset reference** | Durable source-scoped reference to equipment, persisted independently of a plan |
| **Boundary source** | Equipment attachment/nozzle or other energy-entry path requiring assessment |
| **Isolation branch** | A process path from a boundary source toward an isolation boundary/open endpoint |
| **Isolation device** | Physical valve, blind, flange, breaker, disconnect, or equivalent candidate |
| **Candidate occurrence** | A device discovered through a particular traversal/source/branch with evidence and provenance |
| **Isolation point** | A plan-version decision concerning a physical isolation device |
| **Path-point link** | Many-to-many relation showing which point covers which branch/path |
| **Drawing entity reference** | Exact HILT entity identity plus drawing context; not a bbox |
| **Geometry fallback** | Source-qualified image-space bbox used when no drawing entity can be rendered |
| **Finding** | Structured unresolved, blocking, or advisory issue for a plan version |
| **Selection ID** | Frontend-only identity for a rendered list occurrence; never persisted as domain identity |

## 6. Canonical identity model

### 6.1 Source-scoped external identity

Every external identity must include its namespace and scope.

```text
ExternalIdentity
  source_system       unigraph | cnvrt_hilt | cnvrt_stlm | manual
  project_scope       source-specific project identifier
  external_id         identifier within that scope
```

Examples:

```text
unigraph / project:15 / vertex:172184
cnvrt_hilt / job:2151 / 08196784-d2a7-48bc-80e8-08bfd3b2657a
```

A bare `172184`, UUID, or tag is not a complete cross-system identity.

### 6.2 Asset identity

```text
AssetReference
  asset_ref_id                 internal UUID
  authoritative_identity      project-scoped UniGraph/CNVRT identity
  tag                          display/search label
  asset_class
  aliases[]                    optional source identities
  attributes                  bounded source metadata
```

Preferred stable key where evidence supports it:

```text
unigraph / project:{unigraph_project_id} / cnvrt:{cnvrt_id}
```

Fallback:

```text
unigraph / project:{unigraph_project_id} / vertex:{vertex_id}
```

Fallback identity quality must be explicit. It must not silently be upgraded from tag equality.

### 6.3 Drawing entity identity

```text
DrawingEntityReference
  source_system = cnvrt_hilt
  cnvrt_project_id
  collection_id
  job_id
  entity_id
  entity_type
  entity_class
```

`drawing_entity_id` identifies the physical rendered isolation device. `source_drawing_entity_id` identifies the boundary source/nozzle. They are never interchangeable.

### 6.4 Execution and persistence IDs

| ID | Scope | Durable? | Usage |
|---|---|---:|---|
| `run_id` | API execution | Yes | Immutable execution record |
| `candidate_occurrence_id` | One derivation | No | Internal traversal occurrence |
| `unigraph_vertex_id` | UniGraph project | Source-dependent | Graph lookup/provenance |
| `hilt_entity_id` | Drawing/job | Source-dependent | Native viewer entity |
| `asset_ref_id` | Database | Yes | Normalized target asset |
| `point_id` | Plan version/database | Yes | Persisted isolation point |
| `branch_id` | Plan version/database | Yes | Persisted branch/path |
| `selection_id` | Browser render | No | List and interaction state only |
| Tag | Human label | No | Search/display; never identity |

## 7. Proposed canonical domain structures

These are logical contracts. Exact Python/SQL syntax should follow after review.

### 7.1 PlanningContext

```text
PlanningContext
  cnvrt_project_id        required
  collection_id           required
  job_id                  required for drawing-scoped runs
  job_name                descriptive
  unigraph_project_id     required
  traversal_source        derived/explicit
```

Remove ambiguous generic `project_id` from new contracts. Legacy payloads may continue exposing it as an alias for `unigraph_project_id` during transition.

### 7.2 SelectedAsset

```text
SelectedAsset
  tag
  hilt_entity_id
  hilt_entity_class
  selection_source        hilt_equipment_list | hilt_canvas | cli_tag
  context                  PlanningContext
```

API/browser runs require exact HILT identity. CLI runs may remain tag-based and should report weaker identity quality.

### 7.3 WorkScope

```text
WorkScope
  activity
  duration_hours          positive decimal
  break_containment
  personnel_entry
  hot_work
  equipment_leaves_site
  high_risk_service
```

Legacy aliases:

```text
intrusive_work       -> break_containment
confined_space_entry -> personnel_entry
```

Canonical serialization uses only the new names. Policy evaluation must be a method/service over canonical scope rather than duplicated Boolean logic.

### 7.4 BoundarySource

```text
BoundarySource
  source_id                    execution-local typed key
  target_asset_identity
  unigraph_component_identity
  source_drawing_entity
  tag
  source_type                  process | instrument_context
  flow_role                    inlet | outlet | bidirectional | unknown
  properties
```

### 7.5 IsolationDeviceReference

```text
IsolationDeviceReference
  device_key                   source-scoped physical identity
  unigraph_identity?
  drawing_entity?
  tag
  entity_class
  entity_type
  geometry_fallback?
```

### 7.6 CandidateOccurrence

```text
CandidateOccurrence
  occurrence_id
  device                      IsolationDeviceReference
  source                      BoundarySource
  branch_key?
  discovery_source            unigraph_traversal | hilt_topology | manual
  traversal_depth
  classification
  method
  evidence/provenance
  reason
```

Candidate occurrence is not the persisted isolation point. Several occurrences can resolve to one physical device.

### 7.7 GeometryFallback

```text
GeometryFallback
  bbox                        x, y, width, height
  coordinate_frame            image_top_left
  source                      stlm | calibrated_hilt | manual
  match_method                stlm_uuid | hilt_uuid | ...
  job_id
```

Rules:

1. HILT viewer rendering prefers `DrawingEntityReference`.
2. Geometry fallback is used only when exact drawing identity is unavailable.
3. Bbox is retained for provenance, raster overlays, and historical compatibility.
4. Geometry never establishes equipment/device identity.

### 7.8 ValidationResult

```text
ValidationResult
  assurance_status
  rationale
  terminal
  coverage
  candidate_decisions[]
  unresolved_obligations[]
  unresolved_checks[]
  missing_evidence[]
  validator_version
```

Each `candidate_decision` should explicitly contain the candidate/device key and one decision:

```text
barrier | positive | manual_review | rejected | verification
```

The existing ID arrays remain available in a compatibility projection, but new consumers should not reconstruct decisions themselves.

### 7.9 Plan-version structures

```text
PlanVersion
  WorkScope (exactly one)
  TargetAssetLink (one primary initially; extensible to many)
  InputSnapshot[]
  IsolationBranch[]
  PathAssessment[]
  IsolationPoint[]
  PathPointLink[]
  PlanStep[]
  Finding[]
  DerivationRunLink
```

Important cardinalities:

```text
plan 1 ── * plan_version
plan_version 1 ── 1 work_scope
work_scope 1 ── * work_scope_asset
asset_reference 1 ── * work_scope_asset
plan_version 1 ── * isolation_branch
plan_version 1 ── * isolation_point
isolation_branch * ── * isolation_point   through path_point_link
plan_version 1 ── * finding
plan_version 1 ── * plan_step
plan_version 1 ── * external_run_link
```

## 8. Stage contracts

The deterministic algorithm order remains unchanged. Each stage should have a declared input and owned output rather than an undocumented cumulative dictionary.

| Stage | Input | Owned output |
|---|---|---|
| Context resolution | Requested planning context | `ResolvedPlanningContext` |
| Boundary | Context + selected asset | `BoundaryResult` with target and sources |
| Candidate discovery | Boundary + policy | `CandidateSet` |
| Drawing/topology resolution | Candidate set + HILT/STLM | Enriched device refs, branches, geometry, provenance |
| Obligations | Boundary + branches + candidates | `ObligationAnalysis` |
| Relief/schemes | Topology result | `ReliefAnalysis` |
| Instrument context | Topology result | `InstrumentContextAnalysis` (advisory only) |
| Evidence | Candidates + obligations + scope | `EvidenceState` |
| Planner checks | Evidence state | `RequiredCheckSet` |
| Validation | Evidence + required checks | `ValidationResult` (authoritative) |
| Downstream impact | Validated devices + HILT | `DownstreamImpact` |
| LOTO | Validation + scope + optional ordering | `LotoProcedure` |
| Payload assembly | Explicit stage outputs | Versioned API result |

### Stage rules

- A stage does not mutate its input.
- A stage result does not silently include every prior result.
- Debug metadata belongs to the stage that emitted it.
- Raw HILT/STLM payloads remain session-local and are not part of public domain contracts.
- Instrument context cannot alter validator inputs unless a future deterministic rule explicitly promotes a defined field.
- Final payload is assembled once after all required outputs exist; later tools do not patch it in place.

## 9. Proposed orchestration state

Replace semantically drifting names such as `bbox_data` with explicit immutable snapshots or typed envelopes.

```text
PipelineState
  context
  boundary
  candidates
  topology
  obligations
  relief
  instrument_context
  evidence
  required_checks
  validation
  downstream_impact
  loto
```

The LLM continues to choose tool order within guardrails. Tool wrappers write only their own state slot and return compact summaries. A deterministic finalizer reads state slots and produces the response.

The audit trace should record:

- tool name and arguments
- input state fingerprints
- output state fingerprint
- compact result/error
- timestamp

Heavy source data remains server-side as today.

## 10. Persistence responsibilities

### 10.1 Runs

`isolation_runs` remains an immutable execution/provenance record containing:

- accepted request
- agent metadata
- final result
- trace
- error

`isolation_run_events` remains append-only progress history. JSONB is appropriate because runs preserve the exact contract emitted by a particular build.

Add a result/request contract version before changing shapes materially:

```text
request_schema_version
result_schema_version
```

### 10.2 Plans

Plans must not depend on linked-run JSON for their operational meaning. The next normalization slice should add:

- `asset_reference`
- `work_scope`
- `work_scope_asset`

Later complete derivation persistence adds branches, assessments, points, links, steps, findings, and snapshots as already described in the target data-model document.

`external_run_link` remains provenance, not the plan's source of normalized scope or asset identity.

### 10.3 Historical records

- Existing runs remain readable through their original result schema.
- Existing plans may remain `legacy_incomplete` if normalized scope/identity is absent.
- Exact HILT UUID matching may be performed at read time for display but is not written back as authoritative normalized identity.
- No tag-only automatic backfill.
- No speculative activity, duration, selection source, or offsite status.

## 11. API contract direction

### Run creation

A future canonical request should contain:

```json
{
  "context": {
    "cnvrt_project_id": "277",
    "collection_id": "206",
    "job_id": "2151",
    "unigraph_project_id": "15"
  },
  "selected_asset": {
    "hilt_entity_id": "08196784-d2a7-48bc-80e8-08bfd3b2657a",
    "tag": "P3",
    "entity_class": "vertical_vessel",
    "selection_source": "hilt_equipment_list"
  },
  "work_scope": {
    "activity": "mechanical_seal_replacement",
    "duration_hours": "12.00",
    "break_containment": true,
    "personnel_entry": false,
    "hot_work": false,
    "equipment_leaves_site": false,
    "high_risk_service": true
  }
}
```

Transition aliases may be accepted at the API adapter only. Pipeline/domain code receives canonical structures.

### Run result

The response should distinguish:

```text
result metadata
planning context
selected/verified asset
authoritative validation
physical isolation devices/points
branch/path coverage
advisory analyses
presentation references
```

Do not expose frontend `selection_id` from the backend. The frontend creates it from an occurrence key and index/version as a view concern.

### Contract generation

Pydantic response models should become the API source of truth. Generate or mechanically validate TypeScript contracts from OpenAPI rather than maintaining independent handwritten shapes once the canonical API is stable.

## 12. Frontend view-model boundary

The frontend should convert API results once:

```text
API IsolationPoint
    -> IsolationPointViewModel
         selectionId
         drawingEntityId
         fallbackBBox
         decision
         label
         canLocate
```

Rules:

- `selectionId` exists only in the view model.
- Drawing selection uses exact `drawingEntityId`.
- Result-row selection uses `selectionId`.
- `sourceDrawingEntityId` is shown as provenance/context and never highlighted as the barrier.
- Tags are labels/search values only.
- Point decision arrives from the backend; the frontend does not reinterpret validator arrays.
- HILT-native rendering is preferred; bbox is fallback.

## 13. Invariants to enforce

### Identity

1. A tag is never a primary key or sufficient reconciliation proof.
2. Every external ID carries source-system and project/drawing scope.
3. `source_drawing_entity_id` never identifies the isolation device.
4. `selection_id` is never persisted or sent to the pipeline.
5. API/browser execution resolves exactly one authoritative target asset.

### Safety authority

6. `validator.validate()` is the only producer of `assurance_status`.
7. LLM output cannot alter validator decisions.
8. Instrument context remains advisory unless an explicit deterministic rule says otherwise.
9. Unresolved OPCs remain open boundaries and block cross-drawing assurance.
10. LOTO phase order remains deterministic and fixed.

### Immutability and lifecycle

11. Runs, events, result, trace, plan versions, and run links are immutable/append-only according to their existing rules.
12. Derived plan content is changed through a child version, never in-place editing.
13. Latest and active plan versions remain distinct.
14. A draft v1 remains inactive until authorization/activation exists.

### Geometry

15. Native drawing geometry is used when exact HILT identity exists.
16. Bbox geometry declares coordinate frame, job, source, and match method.
17. Geometry is evidence/presentation data, not identity proof.

## 14. Incremental restructuring plan

### Step 1 — Freeze vocabulary and identity contracts

- Review and approve this document.
- Add typed `PlanningContext`, `ExternalIdentity`, `DrawingEntityReference`, and `GeometryFallback` models.
- Document legacy aliases.
- Add contract-version fields to new run requests/results.
- Do not change deterministic behavior.

### Step 2 — Normalize selected target identity

- Add `SelectedAsset` to API run requests.
- Verify HILT identity against exactly one UniGraph equipment vertex.
- Preserve tag-only CLI mode with explicit weaker identity quality.
- Emit a server-generated verified target reference in results.

### Step 3 — Replace candidate identity ambiguity

- Introduce `IsolationDeviceReference` and `CandidateOccurrence` adapters.
- Keep existing internal dictionary algorithms temporarily.
- Validate stage outputs at candidate and topology boundaries.
- Replace ambiguous `visual_id` use with named device/source drawing references.

### Step 4 — Make pipeline state explicit

- Add typed stage result envelopes.
- Stop cross-mutating `AgentSession` snapshots.
- Store analyses in dedicated state slots.
- Assemble the final payload once.
- Fingerprint stage outputs in the trace.

### Step 5 — Version and type the API result

- Add Pydantic response models for the complete result.
- Emit explicit point decisions.
- Generate/validate frontend TypeScript contracts.
- Retain a v1 adapter for historical results.

### Step 6 — Normalize scope and assets in PostgreSQL

- Update the target data-model document first.
- Add `asset_reference`, `work_scope`, and `work_scope_asset`.
- Promote runs transactionally using verified target identity and canonical scope.
- Move plan filters/restoration to normalized joins.
- Keep legacy incomplete plans readable without speculative backfill.

### Step 7 — Persist complete immutable derivations

- Input snapshots
- Branches and path assessments
- Physical isolation points
- Path-point links
- LOTO steps
- Findings
- Parent/child version diffs

Only then proceed to corrections, authorization, register, and field execution.

## 15. Testing strategy

### Contract tests

- External IDs cannot be instantiated without required scope.
- Device and source drawing references are distinct fields.
- Canonical scope aliases map once at the API boundary.
- Result schema version is present and supported.

### Pipeline tests

- Every stage accepts and emits its declared contract.
- Input stage objects remain unchanged after downstream execution.
- Deterministic and agent runners produce equivalent typed stage outputs.
- Finalization is order-independent once required state slots are populated.

### Identity tests

- Duplicate tags across projects/drawings do not collide.
- Exact HILT-to-UniGraph reconciliation succeeds.
- Tag match with UUID mismatch fails.
- Multiple graph matches fail as ambiguous.
- Reimported UniGraph vertex with stable CNVRT ID reuses the asset.
- Source nozzle identity is never projected as isolation-device identity.

### Persistence tests

- Promotion atomically creates scope/asset/version links.
- Concurrent promotion remains idempotent.
- Two plans can share one asset reference.
- Existing external identity with incompatible metadata fails explicitly.
- Historical incomplete plans remain readable.

### Frontend tests

- Native HILT geometry is preferred.
- Bbox fallback works without entity mapping.
- Duplicate path occurrences render one physical device highlight.
- List-row selection remains occurrence-specific.
- Point decisions are displayed without frontend reclassification.

## 16. Decisions required before implementation

1. Confirm the canonical names `SelectedAsset`, `DrawingEntityReference`, `CandidateOccurrence`, and `IsolationDeviceReference`.
2. Confirm that API/browser runs require exact HILT selected-equipment identity.
3. Confirm CLI tag-only runs remain supported but may be marked non-promotable or weak-identity.
4. Confirm canonical duration is decimal hours with a positive API constraint.
5. Confirm one `work_scope` per plan version.
6. Confirm physical devices and path coverage are persisted separately through a many-to-many link.
7. Confirm result contract versioning before replacing validator ID arrays with explicit decisions.
8. Confirm historical plans receive no automatic normalized backfill.

## 17. Recommended immediate next action

Do not begin correction, authorization, or execution features yet. First implement Steps 1 and 2 as a narrow structural slice:

1. canonical context and identity models;
2. selected HILT equipment in the run request;
3. exact HILT-to-UniGraph reconciliation;
4. verified target reference in the result;
5. compatibility behavior for CLI and historical runs.

After that slice is tested against P3 and duplicate-tag scenarios, update the target data-model document and implement normalized work scope and asset persistence.
