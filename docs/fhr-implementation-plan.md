# FHR and isolation-run implementation plan

Normal-run integration is now available: [runtime delivery and remaining gates](process-safety-run-integration.md).

Frontend synthetic testing is now available: see [the preview delivery](fhr-frontend-preview.md).
Migration head is 0010. This does not mark production B2 or the later safety gates complete.

Status: A1/A2 and B1 development contracts implemented 2026-09-08; B2 onward planned. No safety-policy approval is implied.

See the [foundation implementation notes](fhr-controlled-input-foundation.md) for
actual interfaces, scope limits, files changed and verification.
[B1 implementation notes](fhr-b1-input-contracts.md) cover the subsequent input
contracts and captures. Next: B2 integration; production activation gates remain.

This is the detailed execution plan for the remaining FHR → HSC → EC → RBC work.
The [status document](fhr-implementation-next-steps.md) records completed fixes;
[the architecture](fhr-hsc-ec-rbc-architecture.md) defines the intended domain.
Requirements and technical solution under `isolation-planning-agent-ux-i1/extracted/`
remain the source requirements. The delivery order below supersedes the original
order in architecture section 9. This plan now tracks implementation as well as remaining delivery.

## 1. Outcome and scope

A new governed planning run must consume exact, approved safety inputs and a
reproducible graph/state snapshot. Every retained process path must have an
explainable fluid, hazard, exposure, required configuration, and topology verdict.
The deterministic validator must reject an unsatisfied required path. A reviewer
must be able to inspect the consumed inputs and understand why re-derivation is
needed after a source changes.

This completes the FHR-driven process-isolation portion of advisory planning. It
does not deliver the entire requirements document: permit generation, execution
lifecycle/authorisation, full cascade analysis, and all energy-domain planners
remain separate work. M3 may reuse these input contracts later; this project does
not claim to implement M3. Existing non-process obligations must remain intact.

## 2. Current implementation and integration points

| Area | Current state | Planned change |
|---|---|---|
| `domain/isolation_standard.py` | FHR parsing, explicit fluid resolution, base RBC matrix | Governed input adapter, SIC and pure classification contracts |
| `integrations/hilt_*`, `core/boundary.py` | Ordered facts preserved; first-barrier stopping | Immutable graph input and configuration-aware exploration |
| `core/candidates.py`, `domain/path_facts.py` | Path facts survive point deduplication | Preserve path occurrences independently of device union |
| `api/db_models.py`, migrations through `0008_source_data_defects` | Runs, plans, defect/feedback derivations | Controlled revisions, manifests, invalidations, later assessments |
| `api/db.py` | Request hashes, source checkpoints, plan promotion/freshness | Exact input pins and controlled-source freshness |
| `api/service.py`, routes and run coordinator | Config builder and agent pipeline | Admission before worker dispatch; immutable context passed through both runners |
| `core/obligations.py`, `core/evidence.py`, `core/validator.py` | Existing assurance model | Authoritative path assessments and completeness checks |
| UI `src/api.ts`, `src/App.tsx` and workflow components | Legacy scope and review routes | Structured intake, input status, path derivation and refresh diff |
| Viewer 0.2.0 | Generic graph rendering and whole-link highlights | Reuse existing API unless a demonstrated rendering gap requires a release |

The drawing-defect `_source_defect_snapshot` is already locked before execution.
It cannot stand in for an FHR/SIC manifest. Historical requests, hashes, audit
records, and saved results must not be reconstructed using current inputs.

## 3. Decisions and release gates

Engineering proposals below can be implemented without inventing safety rules.
The following decisions require recorded answers before their dependent behavior
is activated. Record owner, decision, source/rule IDs, examples and boundary cases,
review date, and the controlled version containing the answer.

| Decision | Needed from | Blocks |
|---|---|---|
| Authoritative FHR/SIC approval permission and stable actor identity; whether submitter may approve | Product + identity owner + safety authority | Public approve/reject routes and production onboarding |
| Stable document namespace and scope hierarchy | Product/data owner | Cross-unit/site lookup and production document uniqueness |
| Named approver and controlled version of default SIC | Process safety authority | Governed run activation |
| Highest-match HSC/EC precedence and PSD reduction versus overrides/UnknownFluid | Process safety authority | Classifiers using these combinations |
| One-valve bleed placement; intermediate bleed for all two-barrier cells | Process safety authority | Affected configuration verdicts |
| Safe bleed destination vocabulary and fallback strength | Process safety authority | Bleed verification and outward fallback |
| Service and operating P/T source precedence, units and conversions | Data + process safety owners | Conflicting/missing condition resolution |
| Incomplete mapped fluid and `two_phase` behavior | Process safety authority | Affected HSC classifications |
| Global versus unit FHR mapping precedence | Data + process safety owners | Overlapping mapping resolution |
| Versioned graph export and PSD source/validity contract | Graph/state owners | Reproducible production SafetyContext |

Until scope hierarchy is settled, implement exact drawing/job FHR scope and exact
collection SIC scope as proposed in the architecture; no implicit global fallback.
Treat document lookup scope separately from the FHR's internal unit mappings.
Confirm these provisional scopes before onboarding production data. Do not infer
approval authority from `authorize_planning_context()` or caller-provided names.

An unresolved safety case returns a typed blocker. A foundation release may ship
with no public approval route; activation must wait for real approved inputs.

## 4. Milestone A — controlled-input persistence

This is the first implementation batch. It is backend-only and does not enable
new run semantics. Split review into schema/contracts and repository behavior.

### A1. Schema and integrity

Add a reviewed migration after `0008_source_data_defects`. Confirm the actual head
when starting; do not replace that existing untracked migration.

| Record | Minimum fields and database invariants |
|---|---|
| `controlled_input` | UUID, type, canonical scope fields/key, stable document key, approved-head revision ID, created metadata; unique active document identity per supported exact type/scope |
| `controlled_input_revision` | UUID, parent input ID, unique revision label per input, schema/canonicalization version, canonical payload, server SHA-256, submission actor/time, validation result, pending/approved/rejected decision and actor/time/reason |
| `run_input_manifest` | UUID, unique run ID, mode/context, canonical semantic request, request hash, manifest hash/schema, plan time, completeness and missing-source reasons, locked time |
| `run_input_manifest_item` | Manifest ID, unique logical input slot, controlled revision reference where applicable, exact hash/schema, provenance and approval snapshot |
| `plan_version_invalidation` | Plan version, consumed revision, replacement revision, reason, recorded time; unique event identity, append-only |

Use UUID/JSONB conventions and RESTRICT for provenance relationships. Enforce that
an approved head belongs to the same document and is approved; a bare revision FK
is insufficient. Use composite keys/constraints plus narrowly scoped triggers
where cross-row checks need them. Nullable scope fields must not bypass uniqueness.
Reject changes to submitted payloads/hashes and deletion of provenance. Allow one
pending → approved/rejected decision; terminal metadata cannot change. A correction
is a new revision. A replacement changes the head, not the old approval record.

Manifests are inserted and locked in one transaction; no externally visible draft
manifest is needed initially. Triggers reject later item insertion, updates and
deletes. Arrange the insert/lock order so protection does not prevent initial pins.

The proposed manifest slot is `(input_type, role)`, rather than only input type:
SIC needs separately pinned base and optional client delta, plus a hashed effective
composition. First foundation use can restrict roles to one FHR and one SIC.
Document this deliberate refinement of the earlier handoff before implementing it.
The generic schema must not imply that PSD/graph/pattern/SAR validators exist.

### A2. Canonical content and approval adapter

Create a versioned canonicalization contract with golden vectors. Reject NaN,
infinity, unsupported values and ambiguous units. Sort object keys and semantically
unordered FHR rows by stable keys; preserve ordered paths and other meaningful
arrays. Define numeric representation and UTC timestamp encoding explicitly.
Keep existing `api/plans.py` hash behavior unchanged for legacy records.

Separate submitted safety content from authoritative approval metadata. Existing
`FhrDocument.is_approved` and row checks accept document fields; those fields alone
must never establish server approval. Validate submitted content with
`FluidHazardRegister.from_dict()`, then use a tested domain adapter combining its
immutable content with the repository decision. Preserve imported approval claims
as source metadata; do not silently rewrite content after hashing. Define treatment
of row-level approval evidence explicitly in that adapter. Reject the synthetic
mock from approval regardless of its structural validity.

SIC submission may be stored as unsupported/pending while its validator is built.
Approval must reject unsupported schema/type versions. A generic JSON envelope is
not sufficient validation of an effective safety policy.

### A3. Repository operations and concurrency

Return domain projections, never ORM entities. Proposed operations: submit
revision; validate and decide revision; resolve exact approved head; read revision;
lock/read run manifest; append/read plan invalidations. Actor identity enters via a
trusted service adapter; the repository is not itself an HTTP authorisation layer.

Approval transaction:

1. Lock the document/head; validate expected head and pending revision ownership.
2. Validate supported content and trusted decision context.
3. Store terminal decision and replace the approved head.
4. Insert idempotent invalidations for existing plans that consumed superseded
   revisions of this document, including plans more than one revision behind.
5. Commit all changes together; any failure rolls everything back.

Require an expected-head token for replacement to prevent silent concurrent
last-writer-wins approvals. Retrying the same decision is idempotent; a conflicting
terminal decision is a conflict. Lock multiple documents in stable ID order.

Plan promotion must also compare pinned heads and create missing invalidations in
its transaction under the same lock discipline. Otherwise a revision approved
while a run executes would miss a plan created after the approval scan. Cover both
initial promotion and child derivation, with unique constraints preventing duplicate
records. Freshness reads should reconcile conservatively against current heads;
never change consumed revision pins to make a result appear fresh.

### A4. Acceptance

Offline canonicalization/domain tests plus real disposable PostgreSQL tests for:
wrong-parent head/pin, invalid approval, mock rejection, payload/terminal/manifest
mutation, duplicate labels/slots, simultaneous approvals, expected-head conflict,
transaction rollback, repeated decisions, approval versus promotion in either order,
and history two or more revisions behind. Exercise direct SQL trigger rejection,
not only repository guards.

Run fresh upgrade, upgrade from populated 0008 fixtures, migration SQL review,
ORM drift check and empty disposable downgrade/re-upgrade. Do not downgrade a
populated shared database; document backup/restore and forward-fix deployment policy.
Stop this batch after backend checks. No mandatory admission, UI changes or public
approval endpoint is needed to call the foundation complete.

## 5. Milestone B — supported inputs and immutable admission

### B1. Domain contracts and source capture

Implement immutable structured WorkScope, validated SIC base/delta/effective policy,
ControlledInputRef and SafetyContext. Define all supported field ranges, units,
unknown states, rule IDs and schema versions from the source requirements and
approved decision register. Validate SIC matrix overrides with justification and
approval references; non-overridable floors cannot be weakened by composition.

Pin graph content, not merely a mutable URL or job ID. Establish whether UniGraph
and HILT can supply coherent immutable versions. Otherwise persist the exact
normalized data consumed, hash it and record retrieval provenance; do not claim
cross-source atomicity that the providers do not offer. Mutable lazy graph fetches
after locking are incompatible with reproducibility: capture a bounded execution
subgraph before locking, or use a genuinely immutable versioned provider. Inability
to demonstrate required graph completeness remains a blocker.

Capture PSD rows/declarer/validity, asset conditions, accepted corrections, drawing
defect checkpoint and plan time. Pin pattern/SAR sources if consumed; explicitly
record not-applicable or unavailable by mode. Freeze the rule-engine build and
normalization version. FHR/SIC pins alone cannot make the full manifest complete.
A mutable live connector identifier is not a snapshot.

### B2. Admission transaction and dispatch

Resolve final authorized project/collection/job/equipment before admission. Perform
network retrieval outside database locks, then validate final identities/versions
and lock authoritative local sources in deterministic order. In one transaction,
create the queued run, exact manifest and items, and associate derivation context.
Dispatch only after commit. A transaction failure must not leave an executing worker.
Specify recovery for committed queued runs whose dispatch fails or process exits;
retry from the same pins, never silently refresh inputs on resume.

An expected revision supplied by the client is an optimistic check, not permission
to inject content or select an unapproved revision. Context refresh must not change
safety-relevant identity after locking; require new admission if scope changes.
Pass SafetyContext through `build_run_config` and `run_agent_pipeline`, including
the deterministic runner path. Stages load pinned content only.

Derived runs resolve and pin the newly admitted sources for a full child derivation,
while retaining parent lineage and existing locked feedback/defect semantics. Keep
`DerivationManifest` (workflow/trigger state) distinct from `run_input_manifest`
(consumed safety inputs); do not overload the former's mutable running/failed state.

### B3. Compatibility and persistence

Introduce an explicit calculation/schema mode: legacy versus governed. Old saved
records remain legacy/unknown; missing fields never imply a completed assessment.
Define server rollout policy; a governed request must not fall back to legacy after
an admission error. Do not let a browser choose legacy merely to bypass required
inputs once governed mode is mandatory for its scope.

Add a manifest link and hash-kind discriminator before changing new
`PlanVersion.input_hash` values. Keep old bytes and their request-hash meaning.
Materialize immutable assessment payloads separately from mutable freshness.
Use bounded batched queries for plan-list freshness; preserve the existing defect
and asset-condition reasons alongside controlled-input reasons.

Acceptance: missing/unapproved/invalid/conflicting input errors; head replacement
before/during/after admission; dispatch failure/restart; derived-run race; changed
scope rejection; exact historical readback; no current-head lookup during execution.
Regenerate OpenAPI whenever public contracts change and update UI adapters in the
same delivery slice so compatibility is continuously tested.

## 6. Milestone C — deterministic classification

Implement pure `derive_hsc`, `derive_ec`, `derive_rbc` and `assess_device` functions
around the existing fluid resolver and matrix. All time comes from SafetyContext.
No database, network, clock, random or LLM dependency belongs in these functions.
Each result includes consumed values, source references, fired rule IDs, blockers,
and explicit schema/build versions. Canonical derivation bytes exclude generated
run IDs and audit timestamps that are not semantic inputs.

Apply approved override/escalation/floor ordering explicitly. Resolve live-side
service per path; conflicting evidence is not repaired using a tag or equipment
fluid. Unknown fluid remains HSC-4 with a blocker, not proof of a safe conservative
solution. Do not use legacy `high_risk_service` to alter the new result.

First run in an explicit observational stage. Existing first-barrier paths may
show incomplete input/assessment coverage; they cannot establish final RBC
compliance. Classification of longer configuration paths is recomputed as traversal
extends; later facts or spec/service breaks must not leave an earlier lighter RBC
in force. Define the accepted path/service boundary with the source owners.

Acceptance: all 16 matrix cells; every criterion and threshold boundary; overlapping
rules; overrides/floors; PSD validity/modifiers; incomplete fluids; unit conversion;
input permutations; repeated byte-identical derivation with identical semantic
inputs. Pending policy cases stay blocked and have tests demonstrating that block.

## 7. Milestone D — boundary solver and authoritative validation

Use one domain configuration evaluator with HILT and UniGraph adapters supplying
ordered facts. Avoid two independently implemented safety rule engines. Preserve
HILT structural connectivity authority and explicit fallback provenance.

Traversal carries path-local device occurrences and facts, not just a set of chosen
points. Continue past unavailable/inadmissible devices and insufficient first
barriers. Prove series versus parallel placement, positive barrier roles, closure
requirements, bleed location and its own path to a safe destination. A shared
physical device can have distinct roles and requirements on different path uses.

Do not stop before evaluating live-side facts necessary for classification and
proving. Define cycle, reconvergence, connector, terminal and exhaustion behavior.
Exploration budgets must yield explicit `safety_limit_reached` assessments; neither
candidate caps nor search pruning may silently discard an unsatisfied branch.

Project every required process path into obligations, including paths with no
selected device. Evidence and validator check path-local roles and requirements.
The validator must also check assessment coverage against the authoritative
boundary input, so omission of a path by an agent or payload cannot produce success.
Keep configuration satisfaction distinct from field proving and execution state.

Persist normalized assessment records linked to existing plan branches and
many-to-many point membership, with full immutable trace snapshots and versioned
contracts. Add a separate reviewed migration when this model is ready. Preserve
non-process isolation validation and historical plan projections.

Acceptance: split/reconverging/cyclic/parallel-edge graphs; two barriers in series
versus parallel; shared valve/different hazards; missing bleed and unsafe destination;
check/control/unavailable continuation; spec/service changes beyond first device;
all terminal states; cross-branch evidence leakage; incomplete graph/assessment;
agent omission/override attempts; old electrical/mechanical obligations unchanged.

## 8. Milestone E — API/UI completion and rollout

Add read/status and intake contracts when admission lands, then full assessment
contracts with the solver. Suggested error categories: input missing, unapproved,
invalid, ambiguous scope, expected revision changed, snapshot unavailable, and
work scope invalid. Use stable codes with actionable field/source references;
retain existing authentication behavior and distinguish dependency outages.
Use 409 for state/revision conflicts and 422 for invalid/incomplete request inputs.

UI delivery:

- Intake: structured work-scope fields, required input availability and approved
  revision references; confirm any LLM-proposed scope before submitting it.
- Run review: distinguish admission failure, execution failure, incomplete
  assessment and a completed but unsatisfied configuration.
- Plan review: path fluid/HSC/EC/RBC derivation, selected/rejected device roles,
  bleed/proving requirements, source links and blockers.
- Freshness/child derivation: list superseded input revisions and parent/child
  differences in input, classifications, requirements and selected topology.
- Historical views: explicit legacy/unknown data states and tolerant adapters.

Use the existing viewer for whole-node/link focus and highlights. Keep all business
meaning in the UI. If a generic rendering extension becomes necessary, verify and
publish viewer first, then update the UI exact version and lockfile; publishing
requires explicit user authorization. Do not invent partial-link coloring.

Production activation gates: recorded safety decisions, authoritative approval
integration, real approved FHR and default/effective SIC, reproducible source
capture, all acceptance tests, representative data replay reviewed by the safety
owner, and explicit operational rollout ownership. Enable governed mode by scope;
rollback may disable new governed submissions, but must not reinterpret saved
results or silently run governed requests through legacy calculations.

## 9. Delivery checklist and verification

| Batch | Concrete reviewable result | Dependency |
|---|---|---|
| A1 | Canonicalization contract, five-table migration/ORM, integrity tests | Current 0008 baseline |
| A2 | Repository decisions/pins/invalidation, concurrent PG regressions | A1 |
| B1 | SIC/work scope/SafetyContext contracts and source snapshot adapters | Approved applicable policy/source decisions |
| B2 | Atomic admission, dispatch recovery, hashes/freshness and minimal API/UI | A2 + B1 + trusted approved inputs |
| C | Pure classifiers, device assessments and observational traces | B1 + applicable safety decisions |
| D1 | Configuration traversal with exhaustive failure reporting | C + immutable graph adapter |
| D2 | Validator/obligations/evidence + immutable assessment persistence | D1 |
| E | Full review/derivation UI and governed-mode release | B2 + D2 + release gates |

B1 source discovery and decision collection can progress alongside A. No numerical
time estimate is committed before the graph snapshot and approval integration
contracts are known. A1/A2 and B1 development contracts are complete; B2 integration is next; later batches should
remain separately reviewable across the independent repositories.

For each backend batch run focused tests then full stdlib unittest discovery; use
real disposable PostgreSQL for transaction, trigger and migration behavior. Update
OpenAPI on contract changes. For each UI contract/workflow change run tests, lint,
and build. Viewer verification is test/build/pack only when it changes. Run
`git diff --check` and `git status` separately in touched repositories. Preserve all
existing dirty work and report only changes made by the batch. No commits/pushes
without instruction.

End-to-end release scenario: approve FHR A and SIC A → admit run with exact graph,
PSD and scope → inspect all path assessments → approve FHR B while the run is in
flight → persist the A-based result as stale → derive a child pinned to B → review
classification/topology/input diff → confirm the parent remains byte-preserved.
Repeat with admission failure, unresolved path, and legacy-plan reopening.
