# Process safety inputs in normal equipment runs

Implemented 2026-09-08. FHR/SIC/PSD now enter the existing Workspace → isolation
run → Plan review workflow. The separate input lab is no longer required to test
this integration. This is advisory functionality; it does not establish approved
site policy or complete governed production admission.

## UI testing

1. In Workspace select project 277, collection 206, UniGraph 21, drawing 2151 and
   the actual equipment (the verified example is P3 / CO2 discharge KO vessel).
2. Planning documents load automatically for this drawing. Alternatively import
   a `process-safety-inputs-v1` JSON document in **Review or replace planning
   documents**. Other scopes must supply their own matching documents. The UI
   and API require scoped documents before creating a run.
3. Set structured scope and assessment time. Click the existing run action.
4. In ordinary Plan review inspect **FHR / HSC / EC / RBC derivation**. The result
   contains the submitted documents, their hash, per-path classifications and
   requirements, and unresolved input/configuration evidence.
5. Click **New run**. The UI returns to Workspace with the consumed safety inputs
   restored. Enable personnel entry and run again. HSC-4/EC-D requires physical
   disconnection with both sides blinded; unavailable configurations remain blocked.
6. Historical runs remain readable. Creating or deriving a new run without these
   inputs is no longer supported; start a new document-backed run in Workspace.

Examples remain synthetic and unapproved. Their fixed dates and deliberately
missing PSD values are preserved; loading an example does not renew a declaration.
The FHR's different unit mappings may not resolve every real service under the
supplied unit scope. Missing/conflicting mappings produce UnknownFluid/HSC-4 and
blockers. No tag-based service guessing or silent mapping-scope rewrite is applied.

## Runtime behavior

- `ProcessSafetyInputs` is an immutable canonical domain contract. API validation
  checks its document scopes against the selected job/project/collection/UniGraph
  and requires structural selected-asset identity. Its structured flags are the
  authoritative source of the corresponding legacy scope booleans.
- `build_run_config` transports the validated object to the agentic/deterministic
  paths and HILT search policy. Shared classification lives in
  `domain/process_classification.py`, not in the preview implementation.
- Before dispatch, the normal RunStore captures the original HILT export, validates
  the selected equipment identity and persists it with the input-bearing queued
  request. Capture/persistence failure prevents dispatch. Execution checks the
  capture hash; bbox, instrument and downstream HILT reads use that capture.
- The real export has differing outer versus payload endpoint representations.
  `HiltRunCapture` preserves all original records and reports source/endpoint gaps;
  it does not drop problematic links to make a normalized graph look complete.
- Repository request refresh retains admitted safety documents, HILT capture and
  scope. Retargeting is rejected; a legacy run cannot receive safety inputs after
  dispatch. These are application/repository guards in existing JSON storage, not
  a new complete governed manifest or new database immutability triggers.
- Input-bearing HILT traversal searches past the first candidate until candidate
  barrier/positive counts meet recomputed path requirements or it reaches an
  unresolved terminal/other nozzle/cycle/budget. Explored candidates remain visible
  even when the configuration cannot be met. Spectacle-open devices are not
  counted as demonstrated positive closure. Search budgets remain explicit.
- These are candidate configurations. The search does not prove lockability,
  rating, bleed destination, physical disconnection, or field execution, nor does
  stopping there prove that all further live-side facts were captured. Branches
  retain unresolved status and those limitations feed deterministic validation.
- Both runners pass immutable inputs to `core.validator.validate`. It recomputes
  path assessments, including candidate-free HILT obligations, rather than trusting
  supplied/agent-created assessment verdicts. All currently supported input-bearing
  results are `not_isolated` with incomplete readiness because repository approval,
  source completeness and configuration/proving evidence remain unresolved.
- Results and saved normalized plan content retain the assessment. Existing request
  hash meaning and historical records are preserved. HILT capture bodies are hidden
  from run-status projections; the result carries its capture hash.

## Verification

- Backend: **496 tests passed**, including **21 opt-in PostgreSQL tests**. New
  integration coverage includes scope mismatch, authoritative structured scope,
  forged assessment rejection, capture identity/hash rejection, no dispatch after
  capture failure, outward HILT search, EC-D positive counts, candidate-free paths,
  original malformed endpoint retention and request-refresh pin preservation.
- UI: **83 tests**, lint and build pass. New tests cover normal workspace input
  loading/editing/error propagation and ordinary plan-review presentation.
- Chromium with real CNVRT authentication: normal run review displays the process
  assessment; New run restores its documents into ordinary Workspace; no page errors.
- Real P3 runs against drawing 2151:
  - Previous legacy run: `476fe1fdf9374c9fb2743d2a6ff281d7`, 16 points,
    `provisional_unproven_isolation`, no process assessment.
  - EC-B: `a52252e93540486bb901cb1446d91025`, 30 candidate points, 20 assessed paths,
    `not_isolated`, captured HILT hash recorded.
  - EC-D: `0c9eb7a40af34fe8a4de35035788e909`, 30 candidate points, 20 assessed paths,
    disconnection/both-sides-blinding requirements and `not_isolated`.
  These are advisory test records, not approved isolation plans. Equal point counts
  in B/D do not indicate equal adequacy; D has stronger unmet requirements.
- OpenAPI regenerated. No migration in this slice; head remains 0010.
  Backend/UI changes remain uncommitted; viewer unchanged. No pushes.

## Remaining production work

Complete governed approval identity and source-revision pins, immutable UniGraph
capture/coherence, full configuration/admissibility/bleed/fallback evaluation,
assessment coverage against a complete boundary, source freshness and input-change
re-derivation comparisons. The present normal-run integration must not be represented
as completion of those B2-and-later production release gates. Approval cannot be
established by editing JSON claims.

The API remains on port 8088 against the separate local `eia_test_preview_ui`
database/socket described in `fhr-frontend-preview.md`. UI remains on 5173.
Configured `.env` files and the original configured database were not changed.
