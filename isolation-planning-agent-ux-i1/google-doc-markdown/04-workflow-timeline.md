# Workflow timeline


## Isolation-plan workflow

One technical step at a time. Blue chips are records written; outlined chips are source records read. The walkthrough uses the same P-1201A → v3 example.


technical timeline


01


### Select the equipment and define the work

The planner searches for `P-1201A` and records the requested activity, duration, containment break, and other work conditions. A stable plan identity and its initial draft version are created.


#### Read

UniGraph asset lookup

Resolve the selected tag to a source-system identity, not just a display string.


#### Write

isolation_planplan_versionwork_scopeasset_referencework_scope_asset

`scope-303 → asset-p1201a` makes the selected equipment explicit.


02


### Pin the exact planning inputs

The system reads the controlled versions of topology, P&IDs, FHR, PSD, SIC, and any available walkdown/isometric information. It pins a complete input set for this version before deriving any safety decision.


#### Read

UniGraphFHRPSDSICP&ID / isometric


#### Write

input_snapshot

Each snapshot records source type, revision, hash, capture time, expiry and declarer. This makes v1 reproducible.


03


### Derive the reviewed isolation branches and schedule

The deterministic planner traverses from the work zone to live sources, discards raw search noise, retains unique safety-relevant branches, assesses them, selects barriers, generates the ordered procedure, and raises review findings.


#### Read

plan_versioninput_snapshotasset_reference


#### Write

isolation_branchpath_assessmentisolation_pointpath_pointplan_stepfindingfinding_context

The BF mapping gap becomes a blocking `finding` linked to P-08 and the FHR snapshot.


04


### Review findings and request a correction

The reviewer sees the derived v1 plan. A data gap cannot be accepted as a substitute for resolution, so the FHR issue is raised as a controlled source correction.


#### Read

findingfinding_contextinput_snapshotplan_step


#### Write

change_requestaudit_event

`CR-01` is raised against v1. It proposes FHR revision 4.3; v1 remains immutable and blocked.


05


### Lock mandatory corrections and re-derive a child version

After Process Safety approves CR-01, backend code locks a manifest containing every outstanding approved correction. It then creates v2 with v1 as its parent and regenerates the full result; it does not patch v1’s points, branches, or schedule.


#### Read

plan_version v1approved change_request CR-01FHR rev 4.3


#### Write

derivation_manifestderivation_manifest_changeplan_versionplan_version_changeinput_snapshotisolation_branchisolation_pointplan_stepfindingchange_coverage_result

Coverage must prove CR-01 was handled before v2 can be authorised.


06


### Capture a field addition and create the active version

A walkdown identifies a temporary hose. CR-02 is approved; backend code locks it in a manifest, then creates v3 from v2 with the walkdown snapshot. The new branch, positive isolation point, proof step, and drawing-defect finding are all v3 records.


#### Read

plan_version v2change_request CR-02walkdown WD-118


#### Write

asset_referencederivation_manifestderivation_manifest_changeplan_version v3plan_version_changeinput_snapshotisolation_branchisolation_pointplan_stepfindingfinding_contextchange_coverage_result


07


### Authorise and activate the reviewed version

The isolation authority approves v3 only after every mandatory correction has a passing deterministic coverage result. The plan’s one allowed mutable pointer then changes to v3; relevant protections are registered so competing plans can be blocked.


#### Read

plan_version v3change_coverage_resultfindingprotected_asset


#### Write / controlled update

authorisationprotected_assetaudit_eventisolation_plan.active_plan_version_id

Any missing or failed mandatory coverage blocks authorisation and activation.


08


### Execute, prove, and close or re-derive

The field app presents v3’s ordered steps. Each confirmation, hold-point proof, and photo is appended. A failed proof marks the version non-executable and starts the correction/re-derivation path again.


#### Read

plan_stepisolation_pointauthorisation


#### Write

step_executionevidence_attachmentaudit_eventchange_request

Successful close-out updates lifecycle/protection end dates; a failure produces a new child-version workflow.


01 / 08

