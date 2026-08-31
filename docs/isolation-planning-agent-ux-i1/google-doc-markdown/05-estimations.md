# Estimations


## Delivery estimations

Indicative implementation estimate for building the already-defined isolation product: extend the existing FastAPI isolation service, use CNVRT for project/job/HILT/P&ID context, and build a separate isolation-agent UI that adopts selected CNVRT UI components and authentication/authorisation patterns.


delivery estimate


**Boundary of this estimate** It excludes implementation, cleansing and onboarding of FHR, SIC, PSD, SLD, SAR, C&E and isometric inputs. They are treated as versioned/pinned contracts only. It also excludes permit generation, emergency advisory, CMMS adapters, true offline synchronisation and formal certification/independent safety assurance.


### Architecture assumptions

| Area | Assumption |
|----|----|
| Isolation service | This FastAPI service owns isolation plans, immutable versions, execution records, audit events and its PostgreSQL schema. It retains the deterministic engine and its authoritative `validate()` result. |
| CNVRT backend | CNVRT Django supplies project, collection, job, P&ID image and HILT context. The isolation service receives explicit context and uses compatible bearer-token authentication/authorisation; it does not depend on CLI project profiles. |
| New isolation UI | Build a separate UI for the isolation agent. Extract/adapt selected CNVRT UI components and patterns—authentication/authorisation, Axios token handling, Ant Design, notifications, image/HILT loading—but do not reuse the CNVRT application shell or add an isolation route to that application. |


### Concrete implementation work

The items below total 32 working days. With integration overhead, review and contingency, this remains a 6–7 week delivery window.

| Concrete task | Time required | What is delivered |
|----|----|----|
| Extract reusable UI primitives from CNVRT UI | 1 day | Extract/adapt the useful Ant Design wrappers, notification/loading states, token-aware Axios client, image loader and HILT/P&ID interaction patterns into the new isolation UI codebase. |
| Implement CNVRT-compatible authentication and authorisation | 1 day | Use the CNVRT bearer-token pattern in the new UI and isolation service; attach tokens to calls and enforce project, collection and job context on requests. |
| Build equipment/work-scope selection and run launcher | 2 days | Use existing planning-context, equipment and bbox APIs to select project, collection, drawing and equipment; capture the available work-scope fields and launch `POST /isolation-runs`. |
| Show the current agent result in the new UI | 2 days | Render current assurance status, isolation points, evidence gaps, LOTO procedure, downstream impact, result/trace links and run progress without changing agent behaviour. |
| Build and test plan/draft APIs | 2 days | Build `POST /isolation-plans`, plan list/detail and draft persistence for the selected scope, source context, result, trace and run link. |
| Wire saved drafts into the UI | 1 day | Add draft list/detail views so a prior P3-style result can be reopened instead of existing only as output files. |
| Build and test plan-version and boundary APIs | 3 days | Build version read/derive/diff APIs that persist input snapshots, isolation branches, path assessments, isolation points, path-point links, LOTO steps and findings from the deterministic run. |
| Wire plan review and P&ID/HILT overlay into the UI | 2 days | Show each selected point on the original P&ID, connect table-to-bbox selection, expose path/provenance/trace and display available HILT context. |
| Build and test findings/correction APIs | 3 days | Build findings/context, individual acknowledgement, change request, approval, child re-derivation, version-change ledger and audit-event APIs. |
| Wire correction and version-diff UI | 2 days | Let reviewers raise a correction, view added/removed/changed points and findings, and open the new immutable version without editing derived content in place. |
| Build and test authorisation/register APIs | 3 days | Build version authorisation/invalidation, active-version update, protected-asset conflict checks and isolation-register/handover endpoints. |
| Wire authorisation and register UI | 2 days | Show blocking findings, version-specific authorisation, active/draft/superseded state, active isolations and protected/shared points. |
| Build and test field-execution APIs | 3 days | Build next-step, step-execution, evidence attachment, hold-point proof, failed-proof, reinstatement and close-out endpoints. |
| Wire field execution UI | 2 days | Build the online tablet-style sequence for set/lock actions, proof readings, evidence capture, cannot-complete reporting and failed-proof re-derivation. |
| End-to-end test and pilot hardening | 3 days | Test P3 and representative scenarios across UI, APIs, persistence and CNVRT context; add lifecycle/authz/regression coverage, fix UAT defects and prepare the runbook. |


### Required API inventory

| Method and path | Purpose / data-model coverage | Status |
|----|----|----|
| `GET /planning-context/projects` | List CNVRT projects available to the caller. | Implemented |
| `GET /planning-context/projects/{project_id}/collections` | List collections available within the selected CNVRT project. | Implemented |
| `GET /planning-context/projects/{project_id}/collections/{collection_id}/drawings` | List drawing jobs for workspace scope selection. | Implemented |
| `GET /planning-context/projects/{project_id}/collections/{collection_id}/drawings/{job_id}/image` | Proxy the selected source P&ID image into the isolation UI. | Implemented |
| `GET /planning-context/projects/{project_id}/collections/{collection_id}/unigraph-projects` | Resolve UniGraph project context for the selected CNVRT project and collection. | Implemented |
| `POST /equipment` | List selectable equipment for explicit project/collection/UniGraph context. | Implemented |
| `GET /planning-context/drawings/{job_id}/equipment/{node_id}/bbox` | Resolve an equipment bounding box from STLM symbols for drawing selection/highlighting. | Implemented |
| `GET CNVRT /jobs/get_job_details/{job_id}` | Retrieve job metadata and source-image reference used by the isolation service. | Implemented · used by agent |
| `GET CNVRT /jobs/get_job_hilt_graph/{job_id}` | Retrieve enriched HILT topology; authoritative source for the agent's nozzle-to-valve analysis. | Implemented · used by agent |
| `GET CNVRT /symbol_text_line_master/get_stl_master_by_job_id/{job_id}` | Retrieve STLM symbols and drawing coordinates for bbox/overlay resolution. | Implemented · used by agent |
| `GET CNVRT /projects/{project_id}/collections/{collection_id}/jobs/{job_id}/image/source` | Retrieve the original P&ID image through the permission-aware CNVRT endpoint. | Implemented · used by agent |
| `POST /isolation-runs` | Start the current asynchronous agent run. | Implemented · used by agent |
| `GET /isolation-runs` and `GET /isolation-runs/{run_id}` | List current runs and retrieve run status. | Implemented |
| `GET /isolation-runs/{run_id}/result` | Return the completed raw isolation result payload. | Implemented |
| `GET /isolation-runs/{run_id}/trace` and `/events` | Return audit trace and stream run progress. | Implemented |
| `GET /isolation-runs/{run_id}/viewer` and `/pid-image` | Return current static viewer and downloaded P&ID artifact. | Implemented |
| `POST /isolation-plans` | Create an `isolation_plan`, initial `plan_version`, `work_scope` and `work_scope_asset` from explicit CNVRT context and selected equipment. | Pending |
| `GET /isolation-plans` and `GET /isolation-plans/{plan_id}` | List and read stable plan identities for the isolation register. | Pending |
| `POST /isolation-plans/{plan_id}/derive` | Run deterministic/agent planning and persist a complete child `plan_version`, input snapshots, branches, assessments, points, steps and findings. | Pending |
| `GET /isolation-plans/{plan_id}/versions/{version_id}` | Read a complete immutable version, including input snapshots, derivation trace and linked run artifact. | Pending |
| `GET /isolation-plans/{plan_id}/versions/{version_id}/diff` | Compare a version to its parent and classify changes for review/re-authorisation. | Pending |
| `GET /isolation-plans/{plan_id}/versions/{version_id}/findings` | Return `finding` rows and typed `finding_context` for plan review. | Pending |
| `POST /isolation-plans/{plan_id}/versions/{version_id}/findings/{finding_id}/acknowledgements` | Record an individual non-blocking finding acknowledgement; blocking findings remain unacknowledgeable. | Pending |
| `POST /isolation-plans/{plan_id}/changes`; `POST /changes/{change_id}/approve` | Create and approve immutable `change_request` records without editing derived plan data in place. | Pending |
| `POST /isolation-plans/{plan_id}/versions/{version_id}/authorisations` | Record named version-level authorisation after server-side eligibility checks. | Pending |
| `POST /isolation-plans/{plan_id}/activate` | Move the one mutable active-version pointer only when authorised, non-superseded and conflict-free; create protected-asset records. | Pending |
| `GET /isolation-register` | Return active plans, state, outstanding actions, re-prove dates and protected assets for register/handover views. | Pending |
| `GET /isolation-plans/{plan_id}/versions/{version_id}/execution/next` | Return the next executable `plan_step` after checking predecessor and authorisation state. | Pending |
| `POST /plan-steps/{step_id}/executions` | Append `step_execution` confirmation, measurement, proof result or exception; never overwrite a field record. | Pending |
| `POST /step-executions/{execution_id}/evidence` | Store evidence-attachment metadata and immutable object-storage reference/hash for photos, readings and signatures. | Pending |
| `POST /plan-steps/{step_id}/failed-proof` | Mark the version non-executable, create the failure/audit record and initiate required child-version re-derivation. | Pending |
| `POST /isolation-plans/{plan_id}/close-out` | Validate reinstatement, blind reconciliation and outstanding actions before transitioning the plan to closed. | Pending |


**Material risks and follow-ons**The estimate grows if certificate templates must be implemented, CNVRT OAuth tokens cannot be validated by the isolation service, or the editable HILT editor must be embedded rather than adapted read-only. True offline execution/synchronisation is a separate 8–12 calendar-week increment. Source-data integrations named above remain prerequisites for the complete PRD, but are intentionally not estimated here.

