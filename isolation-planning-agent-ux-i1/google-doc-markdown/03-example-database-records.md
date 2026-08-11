# Example database records


## Example database records

A condensed, realistic example of one isolation plan evolving after an FHR correction and a field walkdown. IDs are shortened only for readability; production rows use UUIDs.


v3 is active


### plan_version · v1

Derived from FHR 4.2. Barrier-fluid mapping is missing; authorisation blocked.


→


### change_request · CR-01

FHR mapping for BF is corrected and approved by Process Safety.


→


### manifest · M-02

Backend locks CR-01 as mandatory before deriving v2.


→


### plan_version · v2

Uses FHR 4.3. New barrier decision is produced; initial authorisation later superseded.


→


### change_request · CR-02

Walkdown finds a temporary hose on P-04; addition is approved.


→


### manifest · M-03

Backend locks CR-02; coverage must pass before v3 is allowed.


→


### plan_version · v3

Active and authorised for execution; uses the complete v3 input set.


### 1. Table: `isolation_plan` — stable plan identity

| plan_id | plan_number | active_plan_version_id | lifecycle_state |
|----|----|----|----|
| plan-0412 | ISO-2026-0412 | pv-0412-03 | executing |

The register points to v3 only. It does not overwrite or delete v1 and v2.


### 2. Table: `plan_version` — immutable version lineage

| plan_version_id | plan_id | version_no | parent_plan_version_id | derivation_status | derived_at |
|----|----|----|----|----|----|
| pv-0412-01 | plan-0412 | 1 | NULL | superseded | 2026-08-10 06:30 |
| pv-0412-02 | plan-0412 | 2 | pv-0412-01 | superseded | 2026-08-10 07:20 |
| pv-0412-03 | plan-0412 | 3 | pv-0412-02 | authorised_executable | 2026-08-10 09:45 |


### 3. Table: `change_request` — corrections are requests, not edits

| change_id | raised_against | type | target | proposed change | state |
|----|----|----|----|----|----|
| cr-0081 | pv-0412-01 | source_fix | FHR / service code BF | Map BF to hazardous barrier fluid; controlled FHR revision 4.3. | approved |
| cr-0082 | pv-0412-02 | manual_addition | Isolation branch P-04 | Temporary hose found during walkdown; add a positive isolation point and drawing defect. | approved |


### 4. Table: `plan_version_change` — exact correction application

| plan_version_id | change_id | application_outcome | derivation_note |
|----|----|----|----|
| pv-0412-02 | cr-0081 | applied | FHR 4.3 changes P-08 hazard classification and barrier configuration. |
| pv-0412-03 | cr-0082 | applied | P-04 gains temporary-hose point; sequence and proof steps were re-derived. |

v3 does not repeat CR-01 here: it is inherited through the parent chain. Its complete input set below makes v3 independently reproducible.


### 4a. Table: `derivation_manifest` — locked child-plan inputs

| manifest_id | parent_plan_version_id | child_plan_version_id | state | policy_hash |
|----|----|----|----|----|
| manifest-03 | pv-0412-02 | pv-0412-03 | completed | sic-1.7:fhr-4.3 |

The backend locked this manifest before derivation. The agent was not allowed to choose which approved corrections to include.


### 4b. Table: `derivation_manifest_change` — mandatory correction set

| manifest_id | change_id | mandatory | required_effects |
|----|----|----|----|
| manifest-03 | cr-0082 | true | walkdown snapshot; manual asset; re-evaluated/added branch; point and field steps; drawing-defect finding |


### 4c. Table: `change_coverage_result` — deterministic proof of handling

| coverage_result_id | manifest_id | change_id | status | evidence |
|----|----|----|----|----|
| coverage-03 | manifest-03 | cr-0082 | applied | snap-305, asset-temp-hose-01, br-304, ip-315, steps 14–15, find-102 |

If this row were `failed` or missing, v3 could not be authorised or activated.


### 5. Table: `input_snapshot` — complete pinned input set for active v3

| snapshot_id | plan_version_id | source_type | revision / identity | content_hash | purpose in derivation |
|----|----|----|----|----|----|
| snap-301 | pv-0412-03 | unigraph_topology | graph 15 / traversal 11 | sha256:a21… | Connected live-source paths and valve locations. |
| snap-302 | pv-0412-03 | FHR | revision 4.3 | sha256:f43… | Fluid hazard and barrier-fluid mapping. |
| snap-303 | pv-0412-03 | PSD | declaration 09:30 | sha256:p17… | Live flare and closed-drain state. |
| snap-304 | pv-0412-03 | SIC | version 1.7 | sha256:s17… | Barrier admissibility and proving rules. |
| snap-305 | pv-0412-03 | walkdown | WD-118 | sha256:w18… | Temporary hose observation from CR-02. |


### 6. Table: `isolation_branch` — re-derived safety-relevant routes

| branch_id | plan_version_id | parent_branch_id | branch_code | disposition | topology_signature | source / trace |
|----|----|----|----|----|----|----|
| br-201 | pv-0412-02 | br-101 | P-01 | requires_isolation | sig:4b8… | Live suction header → V-2210 → work zone. |
| br-301 | pv-0412-03 | br-201 | P-01 | requires_isolation | sig:4b8… | Unchanged logical branch, re-derived for v3. |
| br-304 | pv-0412-03 | NULL | P-04 | requires_isolation | sig:9c2… | KO drum V-1205 → temporary hose → work zone; new in v3. |

Each version owns its complete reviewed branch set. Parent links and signatures make v3-v2 differences explicit; raw graph-search routes are not stored here.


### 7. Table: `isolation_point` — selected barrier/proving locations

| isolation_point_id | plan_version_id | asset_ref_id | point_type | required_state | barrier_role | provenance |
|----|----|----|----|----|----|----|
| ip-301 | pv-0412-03 | asset-v2219 | valve | closed_locked | barrier | graph |
| ip-315 | pv-0412-03 | asset-temp-hose-01 | blind | installed_verified | positive_isolation | manual_walkdown |

`ip-315` exists only because CR-02 was approved and incorporated during the v3 derivation.


### 8. Table: `plan_step` — the executable isolation schedule

| step_id | plan_version_id | step_no | isolation_point_id | phase | action | predecessor_step_id | hold_point |
|----|----|----|----|----|----|----|----|
| step-311 | pv-0412-03 | 11 | ip-301 | set_isolation | Close and lock V-2219. | step-310 | false |
| step-314 | pv-0412-03 | 14 | ip-315 | set_positive_isolation | Install and verify blind at temporary hose connection. | step-313 | false |
| step-315 | pv-0412-03 | 15 | ip-315 | prove | Prove zero pressure and sign the hold point. | step-314 | true |

Yes: the plan’s actual ordered procedure is stored here. Each version has its own complete step set, which the field application executes.


### 9. Table: `authorisation` — named approval of the specific version

| authorisation_id | plan_version_id | approver_id | authority_role | decision | signed_at | invalidated_at |
|----|----|----|----|----|----|----|
| auth-017 | pv-0412-02 | user-mwhitfield | isolation_authority | approved | 2026-08-10 08:10 | 2026-08-10 09:05 |
| auth-019 | pv-0412-03 | user-mwhitfield | isolation_authority | approved | 2026-08-10 10:05 | NULL |

v2’s approval remains historically visible but is invalidated when the CR-02 child plan is produced. Only v3’s current authorisation permits execution.


**What this means in practice**When the system executes v3, it reads only v3’s rows: v3 inputs, v3 isolation branches, v3 points and v3 steps. The parent chain and change ledger explain how it got there; they are not used to patch or mutate historic derived records.


**Extended data for the same active plan version**Every row below either belongs directly to `pv-0412-03` or references an object used by that version. These tables complete the proposed logical schema.


### 10. Table: `work_scope` — requested work conditions

| work_scope_id | plan_version_id | activity | duration_hours | break_containment | hot_work |
|----|----|----|----|----|----|
| scope-303 | pv-0412-03 | seal replacement | 14 | true | false |


### 10a. Table: `work_scope_asset` — selected equipment in the scope

| work_scope_id | asset_ref_id | scope_role | selection_source | selected_at |
|----|----|----|----|----|
| scope-303 | asset-p1201a | primary_work_target | workspace_tag_search | 2026-08-10 06:20 |

This is the missing explicit link: the user selected P-1201A, so the work scope points to its source-system identity through `asset-p1201a`.


### 11. Table: `asset_reference` — links to authoritative plant objects

| asset_ref_id | external_system | external_id | tag | asset_class | purpose |
|----|----|----|----|----|----|
| asset-p1201a | unigraph | vertex-8821 | P-1201A | pump | work-scope equipment |
| asset-p1201b | unigraph | vertex-8823 | P-1201B | pump | T4 protected running train |
| asset-v2219 | unigraph | vertex-8891 | V-2219 | gate_valve | isolation point ip-301 |
| asset-temp-hose-01 | manual_walkdown | WD-118:obs-04 | TEMP-HOSE-01 | temporary_connection | isolation point ip-315 |


### 12. Table: `path_assessment` — deterministic risk and barrier result

| assessment_id | branch_id | HSC | exposure_class | barrier_config | proving_method |
|----|----|----|----|----|----|
| assess-304 | br-304 | 4 | B | valve_plus_positive_isolation | zero-pressure proof at bleed; hold point |


### 13. Table: `path_point` — puts each isolation point in a branch

| branch_id | isolation_point_id | path_order | live_side | is_primary_barrier | selection_reason |
|----|----|----|----|----|----|
| br-304 | ip-301 | 1 | true | true | First lockable barrier from live KO-drum source. |
| br-304 | ip-315 | 2 | false | true | Positive isolation required after temporary-hose observation. |


### 14. Table: `finding` — gaps, impacts and discrepancies

| finding_id | plan_version_id | finding_type | severity | state | blocks_authorisation | title |
|----|----|----|----|----|----|----|
| find-081 | pv-0412-01 | data_gap | high | resolved | true | BF service code has no FHR mapping. |
| find-102 | pv-0412-03 | drawing_defect | medium | open | false | Temporary hose absent from PID-2103. |

The finding itself needs only plan-version scope. Its optional contexts are stored separately below.


### 14a. Table: `finding_context` — optional context for each finding

| finding_context_id | finding_id | context_type | target | note |
|----|----|----|----|----|
| ctx-081a | find-081 | isolation_branch | branch_id = br-108 (P-08) | Barrier-fluid supply branch affected by missing mapping. |
| ctx-081b | find-081 | input_snapshot | input_snapshot_id = snap-102 (FHR rev 4.2) | Source that lacks the BF mapping. |
| ctx-102a | find-102 | asset | asset_ref_id = asset-temp-hose-01 | Walkdown object absent from drawing. |
| ctx-102b | find-102 | input_snapshot | input_snapshot_id = snap-305 (walkdown WD-118) | Evidence source for the drawing defect. |

There is no asset context for a plan-wide finding. A dependency with no database object uses `context_type = external_dependency` and `external_reference`, for example “isometric extraction, Area 12”.


### 15. Table: `step_execution` — field confirmation of a plan step

| execution_id | step_id | operator_id | outcome | occurred_at | measurements | synced_at |
|----|----|----|----|----|----|----|
| exec-501 | step-314 | user-rpatel | confirmed | 2026-08-10 11:10 | {"blind_id":"SP-15"} | 2026-08-10 11:14 |
| exec-502 | step-315 | user-rpatel | passed | 2026-08-10 11:40 | {"pressure_barg":0.0} | 2026-08-10 11:41 |


### 16. Table: `evidence_attachment` — proof linked to execution

| evidence_id | execution_id | evidence_type | uri | content_hash | captured_by |
|----|----|----|----|----|----|
| ev-701 | exec-501 | photo | api_runs/0412/blind-SP-15.jpg | sha256:e71… | user-rpatel |
| ev-702 | exec-502 | instrument_reading | api_runs/0412/proof-step-15.json | sha256:e72… | user-rpatel |


### 17. Table: `protected_asset` — assets another plan must not disturb

| protection_id | plan_id | asset_ref_id | tier | protection_basis | active_from | active_to |
|----|----|----|----|----|----|----|
| protect-41 | plan-0412 | asset-p1201b | T4 | last_available_charge_train | 2026-08-10 10:05 | NULL |
| protect-42 | plan-0412 | asset-v2219 | shared_point | required_barrier_for_active_plan | 2026-08-10 10:05 | NULL |


### 18. Table: `audit_event` — append-only operational history

| audit_event_id | plan_id | plan_version_id | event_type | actor_type | occurred_at | payload |
|----|----|----|----|----|----|----|
| audit-901 | plan-0412 | pv-0412-03 | plan_activated | system | 2026-08-10 10:06 | {"previous_active":"pv-0412-02"} |
| audit-902 | plan-0412 | pv-0412-03 | plan_question_answered | user | 2026-08-10 10:30 | {"question":"Why V-2219?"} |


### 19. Table: `external_run_link` — bridge to the current runner persistence

| run_link_id | plan_version_id | run_id | runner | result_uri | trace_uri |
|----|----|----|----|----|----|
| runlink-03 | pv-0412-03 | run-7f92 | agentic_gemini | api_runs/run-7f92/result.json | api_runs/run-7f92/trace.json |


