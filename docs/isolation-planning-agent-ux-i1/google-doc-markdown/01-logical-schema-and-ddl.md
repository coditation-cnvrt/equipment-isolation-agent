# Logical schema & DDL


1 · Scope, source topology & controlled inputs


## isolation_plan

Stable business identity across re-derivations; the isolation-register row.


- **PK** plan_id *uuid*
- plan_number *text unique*
- **FK** active_plan_version_id *uuid*
- mode, lifecycle_state *enum*
- area_code, created_at *text, timestamptz*


Active version must be authorised and non-superseded. The plan identity itself is never replaced.


## plan_version

Immutable deterministic result for one derivation.


- **PK** plan_version_id *uuid*
- **FK** plan_id, parent_version_id? *uuid*
- version_no, derivation_status *int, enum*
- input_hash, model_hash *text*
- derived_at, superseded_at *time*


v2 is a child of v1. Never UPDATE computed content; derive a child instead.


## work_scope

User-selected work conditions from Workspace.


- **PK** work_scope_id *uuid*
- **FK** plan_version_id *uuid*
- activity, duration_hours *text, numeric*
- break_containment *boolean*
- entry, hot_work, offsite *boolean*


The requested equipment is linked separately through `work_scope_asset`.


## asset_reference

Local reference to a UniGraph asset, drawing, connector, line or nozzle.


- **PK** asset_ref_id *uuid*
- external_system, external_id *text*
- tag, asset_class *text*
- area_code, attributes *text, jsonb*


References source-of-truth graph data; it does not duplicate its topology.


## work_scope_asset

Explicitly identifies the equipment/assets included in a work scope.


- **PK** work_scope_id + asset_ref_id *uuid*
- scope_role *enum*
- selection_source *enum*
- selected_at *timestamptz*


Makes “isolate P-1201A” a proper database relationship, not a tag stored in free text.


## input_snapshot

Pins the input artefacts used to make a plan: UniGraph traversal, P&ID revisions, FHR, SIC, PSD, SAR and isometric data.


- **PK** snapshot_id *uuid*
- **FK** plan_version_id *uuid*
- source_type, source_uri *enum, text*
- revision, content_hash *text*
- captured_at, expires_at *timestamptz*
- declared_by, payload *text, jsonb*


PSD declarations carry expiry and named declarer; stale/missing input becomes a visible blocking gap.


2 · Deterministic boundary, hazard and isolation decisions


## isolation_branch

One unique, safety-relevant route from the work zone to a source, safe declaration, unresolved endpoint, or protected impact.


- **PK** branch_id *uuid*
- **FK** plan_version_id, parent_branch_id? *uuid*
- branch_code, disposition, source_state *text, enum, enum*
- topology_signature, topology *text, jsonb*
- drawing_trace, confidence *jsonb, enum*


Stores reviewed isolation branches—not every raw graph-search route. Each derived version owns a complete branch set.


## path_assessment

HSC/EC/RBC derivation and provability for each isolation branch.


- **PK** assessment_id *uuid*
- **FK** branch_id *uuid*
- hazard_severity_class *smallint*
- exposure_class, barrier_config *enum*
- proving_method, residual_risk *text, jsonb*


The model preserves the rule outcome and its factual derivation trace.


## isolation_point

A selected valve, blind, plug, breaker, bleed or test location.


- **PK** isolation_point_id *uuid*
- **FK** plan_version_id, asset_ref_id *uuid*
- point_type, required_state *enum*
- barrier_role, sequence_no *enum, int*
- provenance, confidence *enum*


One point may satisfy several paths, and can be protected by another active plan.


## path_point

Many-to-many placement of a point in an isolation branch.


- **PK** branch_id + point_id *uuid*
- path_order, live_side *int, boolean*
- selection_reason *text*
- is_primary_barrier *boolean*


Allows branch-level explanation such as “why V-2210 is in boundary”.


## finding

A unified, traceable issue: gap, assumption, discrepancy, impact, deviation, conflict or emergency advisory.


- **PK** finding_id *uuid*
- **FK** plan_version_id *uuid*
- finding_type, severity, state *enum*
- rule_ref, title, detail *text*
- blocks_authorisation, provenance *boolean, enum*
- raised_at, resolved_at, resolution *time, time, jsonb*


Every finding is scoped to a plan version. Optional context lives in `finding_context`, so it need not name an asset.


## finding_context

Optional, typed references that explain where a finding applies.


- **PK** finding_context_id *uuid*
- **FK** finding_id *uuid*
- context_type *enum*
- asset / path / input / step? *one FK*
- external_reference?, note *text*


Zero contexts = plan-level finding. Each context row identifies exactly one asset, path, input, step, or external dependency.


3 · Authorisation, field execution & evidence


## plan_step

Authoritative sequence: set, lock/tag, prove, hold point, work or reinstate.


- **PK** step_id *uuid*
- **FK** plan_version_id, point_id? *uuid*
- step_no, phase, action *int, enum, text*
- role_required, hold_point *text, boolean*
- predecessor_step_id *uuid*


A predecessor graph enforces the gloved/offline, one-step-at-a-time field experience.


## step_execution

Field confirmation, failed proof, queued offline event or supervised override.


- **PK** execution_id *uuid*
- **FK** step_id, operator_id *uuid*
- outcome, occurred_at *enum, time*
- device_state, measurements *jsonb*
- offline_captured_at, synced_at *time*


A failed proving outcome supersedes the executable plan and requires re-derivation.


## evidence_attachment

Photo, signature, gas test, reading or linked document evidencing execution.


- **PK** evidence_id *uuid*
- **FK** execution_id, captured_by *uuid*
- evidence_type, uri, hash *enum, text*
- captured_at, metadata *time, jsonb*


Immutable content hash supports blind ID/photo and hold-point evidence.


## authorisation

Named review and sign-off for a specific immutable plan version.


- **PK** authorisation_id *uuid*
- **FK** plan_version_id, approver_id *uuid*
- authority_role, decision *enum*
- signed_at, comment *time, text*
- invalidated_at, reason *time, text*


Authorisation belongs to a version—not the long-lived plan identity.


4 · Governance, shared protection & audit


## protected_asset

T4 / shared point protections held while an isolation is active.


- **PK** protection_id *uuid*
- **FK** plan_id, asset_ref_id *uuid*
- protection_basis, tier *text, enum*
- active_from, active_to *time*


Checked against every new plan to stop collective loss of protection.


## change_request

Immutable correction, addition, removal, source fix or deviation; never a direct edit.


- **PK** change_id *uuid*
- **FK** plan_id, raised_against_version_id *uuid*
- change_type, target_type, target_id *enum, enum, uuid*
- proposed_change, justification *jsonb, text*
- state, raised_by, approved_by *enum, uuid, uuid*


Manual provenance stays distinct. Approval alone does not mutate a plan—it permits a new derivation.


## plan_version_change

The explicit application ledger for a child derivation.


- **PK** plan_version_id + change_id *uuid*
- application_outcome *enum*
- applied_at, applied_by *time, uuid*
- derivation_note *text*


Shows exactly which approved corrections/additions/removals were applied, rejected as inapplicable, or superseded.


## derivation_manifest

Backend-locked definition of one child-plan derivation.


- **PK** manifest_id *uuid*
- **FK** plan_id, parent_version_id *uuid*
- **FK** child_version_id? *uuid*
- state, policy_hash *enum, text*
- locked_at, created_by *time, uuid*


The service—not the LLM—freezes every approved correction and required input that v3 must consider.


## derivation_manifest_change

Mandatory corrections included in a locked derivation manifest.


- **PK** manifest_id + change_id *uuid*
- mandatory *boolean*
- required_effects *jsonb*
- included_at *timestamptz*


Prevents the agent or caller from silently dropping an approved correction from the next version.


## change_coverage_result

Deterministic proof that a manifest correction was handled by its child plan.


- **PK** coverage_result_id *uuid*
- **FK** manifest_id + change_id *uuid*
- status *applied / failed / N/A*
- evidence, reason *jsonb, text*
- validated_at, validator *time, text*


Authorisation/activation is blocked unless every mandatory correction has passing coverage.


## audit_event

Append-only event stream for queries, agent runs, decisions and status changes.


- **PK** audit_event_id *uuid*
- plan_id, plan_version_id? *uuid*
- event_type, actor_type *enum*
- actor_id, occurred_at *uuid, time*
- payload, previous_hash *jsonb, text*


Captures “Ask the plan”, emergency answers, agent tools and all authorisation-relevant activity.


## external_run_link

Bridge to existing isolation_runs and its raw result/trace artifacts.


- **PK** run_link_id *uuid*
- **FK** plan_version_id *uuid*
- run_id, runner *text*
- result_uri, trace_uri *text*


Keeps operational data normalized while retaining current API persistence.


## Key relationships and screen coverage


`isolation_plan 1 ──< plan_version (parent → child)`

The plan owns one active version. Every version has at most one direct parent, allowing v1 → v2 → v3 lineage and full history.


`work_scope 1 ──< work_scope_asset >── asset_reference`

The selected equipment becomes an explicit link to a source-system object; points, findings and protections reuse the same asset identity.


`plan_version >──< plan_version_change >── change_request`

A child version records every exact correction it applied. An approved request can be applied once, be inapplicable, or be superseded—nothing is assumed implicitly.


`derivation_manifest >──< manifest_change ──> change_request`

The backend freezes every approved correction that is mandatory for one child derivation; the caller cannot choose a subset.


`manifest_change 1 ── 1 change_coverage_result`

Deterministic coverage must pass for each mandatory correction before the child version can be authorised or activated.


`finding 1 ──< finding_context ──> optional typed target`

A finding may reference any combination of assets, branches, source snapshots, steps, or external dependencies—or no extra target at all.


`plan_version 1 ──< isolation_branch ──< path_point >── isolation_point`

Each version re-derives a complete, reviewed branch set. Parent branch and signature fields make additions/changes/unchanged branches diffable.


`plan_step 1 ──< step_execution ──< evidence_attachment`

Drives Field execution with enforced predecessors, hold points, offline queueing, proof measurements and photos.


## Illustrative PostgreSQL DDL


Core deployable pattern — use enums/check constraints to make the lifecycle explicit; use JSONB only for source payloads and evidence details.


-- Extensions and controlled vocabulary omitted for brevity. CREATE TABLE isolation_plan ( plan_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plan_number text NOT NULL UNIQUE, active_plan_version_id uuid, mode text NOT NULL, lifecycle_state text NOT NULL, area_code text, created_at timestamptz NOT NULL DEFAULT now() ); CREATE TABLE plan_version ( plan_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plan_id uuid NOT NULL REFERENCES isolation_plan(plan_id), version_no integer NOT NULL, derivation_status text NOT NULL, input_hash text NOT NULL, model_hash text NOT NULL, derived_at timestamptz NOT NULL DEFAULT now(), parent_plan_version_id uuid REFERENCES plan_version(plan_version_id), superseded_at timestamptz, UNIQUE (plan_id, version_no) ); ALTER TABLE isolation_plan ADD CONSTRAINT isolation_plan_active_version_fk FOREIGN KEY (active_plan_version_id) REFERENCES plan_version(plan_version_id); CREATE TABLE asset_reference ( asset_ref_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), external_system text NOT NULL, external_id text NOT NULL, tag text NOT NULL, asset_class text NOT NULL, area_code text, attributes jsonb NOT NULL DEFAULT '{}'::jsonb, UNIQUE (external_system, external_id) ); CREATE TABLE work_scope ( work_scope_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plan_version_id uuid NOT NULL REFERENCES plan_version(plan_version_id), activity text NOT NULL, duration_hours numeric, break_containment boolean NOT NULL DEFAULT false, personnel_entry boolean NOT NULL DEFAULT false, hot_work boolean NOT NULL DEFAULT false, equipment_leaves_site boolean NOT NULL DEFAULT false ); CREATE TABLE work_scope_asset ( work_scope_id uuid NOT NULL REFERENCES work_scope(work_scope_id), asset_ref_id uuid NOT NULL REFERENCES asset_reference(asset_ref_id), scope_role text NOT NULL, selection_source text NOT NULL, selected_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (work_scope_id, asset_ref_id) ); CREATE TABLE input_snapshot ( snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plan_version_id uuid NOT NULL REFERENCES plan_version(plan_version_id), source_type text NOT NULL, source_uri text, revision text, content_hash text NOT NULL, captured_at timestamptz NOT NULL, expires_at timestamptz, declared_by text, payload jsonb NOT NULL DEFAULT '{}'::jsonb ); CREATE TABLE change_request ( change_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plan_id uuid NOT NULL REFERENCES isolation_plan(plan_id), raised_against_version_id uuid NOT NULL REFERENCES plan_version(plan_version_id), change_type text NOT NULL, target_type text NOT NULL, target_id uuid, proposed_change jsonb NOT NULL, justification text NOT NULL, state text NOT NULL, raised_by uuid NOT NULL, approved_by uuid, created_at timestamptz NOT NULL DEFAULT now() ); CREATE TABLE plan_version_change ( plan_version_id uuid NOT NULL REFERENCES plan_version(plan_version_id), change_id uuid NOT NULL REFERENCES change_request(change_id), application_outcome text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now(), applied_by uuid, derivation_note text, PRIMARY KEY (plan_version_id, change_id) ); CREATE TABLE derivation_manifest ( manifest_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plan_id uuid NOT NULL REFERENCES isolation_plan(plan_id), parent_plan_version_id uuid NOT NULL REFERENCES plan_version(plan_version_id), child_plan_version_id uuid UNIQUE REFERENCES plan_version(plan_version_id), state text NOT NULL, policy_hash text NOT NULL, created_by uuid, created_at timestamptz NOT NULL DEFAULT now(), locked_at timestamptz ); CREATE TABLE derivation_manifest_change ( manifest_id uuid NOT NULL REFERENCES derivation_manifest(manifest_id), change_id uuid NOT NULL REFERENCES change_request(change_id), mandatory boolean NOT NULL DEFAULT true, required_effects jsonb NOT NULL DEFAULT '{}'::jsonb, included_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (manifest_id, change_id) ); CREATE TABLE change_coverage_result ( coverage_result_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), manifest_id uuid NOT NULL, change_id uuid NOT NULL, status text NOT NULL, evidence jsonb NOT NULL DEFAULT '{}'::jsonb, reason text, validator text NOT NULL, validated_at timestamptz NOT NULL DEFAULT now(), FOREIGN KEY (manifest_id, change_id) REFERENCES derivation_manifest_change(manifest_id, change_id), UNIQUE (manifest_id, change_id) ); CREATE TABLE isolation_branch ( branch_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plan_version_id uuid NOT NULL REFERENCES plan_version(plan_version_id), parent_branch_id uuid REFERENCES isolation_branch(branch_id), branch_code text NOT NULL, disposition text NOT NULL, source_state text NOT NULL, topology_signature text NOT NULL, topology jsonb NOT NULL, drawing_trace jsonb, confidence text NOT NULL, UNIQUE (plan_version_id, branch_code) ); CREATE TABLE path_assessment ( assessment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), branch_id uuid NOT NULL REFERENCES isolation_branch(branch_id), hazard_severity_class smallint NOT NULL, exposure_class text NOT NULL, barrier_config text NOT NULL, proving_method text, residual_risk jsonb, UNIQUE (branch_id) ); CREATE TABLE isolation_point ( isolation_point_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plan_version_id uuid NOT NULL REFERENCES plan_version(plan_version_id), asset_ref_id uuid NOT NULL REFERENCES asset_reference(asset_ref_id), point_type text NOT NULL, required_state text NOT NULL, barrier_role text, sequence_no integer, provenance text NOT NULL, confidence text NOT NULL ); CREATE TABLE path_point ( branch_id uuid NOT NULL REFERENCES isolation_branch(branch_id), isolation_point_id uuid NOT NULL REFERENCES isolation_point(isolation_point_id), path_order integer NOT NULL, live_side boolean NOT NULL, selection_reason text NOT NULL, PRIMARY KEY (branch_id, isolation_point_id) ); CREATE TABLE finding ( finding_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plan_version_id uuid NOT NULL REFERENCES plan_version(plan_version_id), finding_type text NOT NULL, severity text NOT NULL, state text NOT NULL, rule_ref text, title text NOT NULL, detail text NOT NULL, blocks_authorisation boolean NOT NULL DEFAULT false, provenance text NOT NULL ); CREATE TABLE plan_step ( step_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plan_version_id uuid NOT NULL REFERENCES plan_version(plan_version_id), isolation_point_id uuid REFERENCES isolation_point(isolation_point_id), step_no integer NOT NULL, phase text NOT NULL, action text NOT NULL, role_required text NOT NULL, hold_point boolean NOT NULL DEFAULT false, predecessor_step_id uuid REFERENCES plan_step(step_id), UNIQUE (plan_version_id, step_no) ); CREATE TABLE finding_context ( finding_context_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), finding_id uuid NOT NULL REFERENCES finding(finding_id), context_type text NOT NULL, asset_ref_id uuid REFERENCES asset_reference(asset_ref_id), branch_id uuid REFERENCES isolation_branch(branch_id), input_snapshot_id uuid REFERENCES input_snapshot(snapshot_id), plan_step_id uuid REFERENCES plan_step(step_id), external_reference text, note text, CHECK (num_nonnulls(asset_ref_id, branch_id, input_snapshot_id, plan_step_id, external_reference) = 1) ); CREATE TABLE step_execution ( execution_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), step_id uuid NOT NULL REFERENCES plan_step(step_id), operator_id uuid NOT NULL, outcome text NOT NULL, occurred_at timestamptz NOT NULL, device_state jsonb, measurements jsonb, offline_captured_at timestamptz, synced_at timestamptz ); CREATE TABLE authorisation ( authorisation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plan_version_id uuid NOT NULL REFERENCES plan_version(plan_version_id), approver_id uuid NOT NULL, authority_role text NOT NULL, decision text NOT NULL, signed_at timestamptz, comment text, invalidated_at timestamptz, invalidation_reason text ); -- Add protected_asset, evidence_attachment, audit_event and indexes as shown above. -- Enforce active version eligibility with a transaction/trigger: same plan, authorised, non-superseded.

