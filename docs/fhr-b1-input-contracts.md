# B1 input contracts and captured snapshots

Implemented 2026-09-08 using the researched SIC/PSD fixtures. This slice implements
validated development contracts, immutable input capture and SIC draft storage.
It does not activate governed run admission or claim that live graph retrieval is
an atomic snapshot. All B1 SafetyContexts reject execution explicitly.

## Contracts

`domain/safety_inputs.py` provides:

- `FrozenJSON`: canonical bytes with detached projections. Nested values cannot
  mutate a captured object. Raw-byte construction also validates; duplicate JSON
  keys, non-finite numbers and non-JSON values are rejected.
- `StructuredWorkScope` (`work-scope-v1`): all requested scope flags are explicit,
  with activity, finite nonnegative duration and enumerated shift coverage. No
  legacy boolean is inferred and no EC classification is assigned here.
- `SicProfile` (`sic-process-v1`): strict parameter groups, explicit unknowns,
  numeric domains, gas-range checks, matrix override validation and provenance.
  There is no silently installed default profile. Permit generation is outside
  this schema; enabled electrical/emergency modes remain implementation blockers.
- `SicDelta` (`sic-process-delta-v1`): exact base hash/revision, exact collection
  scope, explicit allowed leaf replacements and justification. Composition rejects
  wrong bases/scopes, unsupported edits and invalid resulting parameters.
- `ConfigurationFloor`: immutable rule/source/cell/configuration records outside
  SIC-editable paths. Composition retains these and rejects an override below a
  supplied floor. The future RBC engine must apply floors to its final assessment;
  retaining a floor here does not demonstrate an adequate isolation configuration.

`compose_sic()` returns the effective draft profile and a canonical composition
record with base/delta/effective hashes and per-parameter origins. Imported approver
references on matrix overrides are required trace information, not server approval.
Synthetic status cannot be cleared by a delta. Unresolved-policy/approval blockers
remain even if a caller removes the fixture's own unresolved-decision list.

`domain/plant_state.py` provides `PlantStateDeclaration` (`psd-v1`). It validates
all six requested PSD sections, UTC-aware times, state enums, row/tag/source-ID
uniqueness and units. Null pressure stays unknown; zero stays a declaration; gauge
pressure may be negative. Active isolation and override references are retained
without asserting verification. Register coverage distinguishes not-reviewed,
partial and declared-complete data.

`assess(plan_time=..., validity_hours=...)` uses only explicit time. Its effective
expiry is the earlier of the declared expiry and the supplied SIC age limit. The
expiry boundary itself is expired. The projection reports missing values,
conflicts, unverified identities and Operations authority, stale records and
future-dated records; it cannot prove isolation or a safe bleed destination.

## Adapters and graph capture

`integrations/safety_input_adapters.py` converts the versioned, explicitly synthetic
research fixtures to the strict contracts. Source descriptions, row annotations,
research references and handover information remain in immutable provenance.
Fixture test scenarios are not runtime data. The adapter rejects a relabeled
approved fixture and cannot resolve a MOCK identity to a graph vertex.

`integrations/graph_snapshots.py` captures already-fetched HILT exports and normalized
UniGraph JSON exports. It performs no network requests and does not accept lazy
traversal callbacks. `domain/source_snapshots.py` owns the immutable GraphSnapshot
contract, keeping domain validation independent of integration code.

Captures retain original node/edge records, source-scoped IDs, parallel edges and
metadata; normalized identities/endpoints must agree with the retained records.
Duplicate or missing identities and conflicting aliases fail explicitly. Dangling
endpoints remain stored with blockers. Sorting nodes/edges makes equivalent input
permutations canonical. The graph hash excludes capture time; the complete capture
hash includes audit time and the supplied source revision label.

A revision label does not prove source consistency. Every current capture reports
provider consistency and coverage as unverified. HILT's existing job-ID fetch and
UniGraph's live frontier expansion have not established an immutable-version
contract. Durable graph snapshot storage and execution exclusively against pinned
content remain B2 work; these B1 objects can be serialized for that integration.

## SafetyContext and repository boundary

`domain/safety_context.py` assembles immutable planning context, structured scope,
effective SIC/composition, PSD and assessment, graph captures, optional FHR
repository revision, rule-engine build and governance captures. It checks scope,
content hashes, composition identity and duplicate graph sources. Optional target
IDs are checked against structural equipment type where captured data exists;
cross-source identity reconciliation remains a separate blocker.

`ControlledInputRef.from_revision()` projects exact repository identities, hashes
and decision metadata. FHR content hashes and drawing scope must match the context.
The FHR approval adapter consumes a trusted repository projection, never an HTTP
request. Missing inputs and approval/capture times after plan time produce blockers.
A build digest is required when build metadata is supplied; arbitrary governance
JSON cannot establish source completeness.

`SafetyContext.to_dict()` records `safety-context-b1-v1`, development mode, blocked
admission and sorted reasons. `require_executable()` always rejects B1 contexts.
B2 must implement an explicit supported admission/context version backed by real
pins, source-specific governance validation and authoritative approvals. Removing
one blocker string must not become the activation mechanism.

The controlled-input repository now recognizes `sic-process-v1` as
`draft_validated`, checks its label/collection against the registry document, and
stores the canonical content/hash. It still rejects approval. Existing unsupported
SIC schemas remain unsupported; submitted historical records are unchanged. SIC
base/delta relational roles and approved-head behavior require a later reviewed
migration once the supported approval contract exists. Migration head remains 0009.

## Verification and changed files

Full backend suite with disposable PostgreSQL: **471 tests passed**. This includes
26 new offline input/context/capture tests and one new PostgreSQL SIC draft test.
The database regressions total 16 (12 controlled-input and four source-defect).

Coverage includes all seven researched PSD scenarios, exact expiry boundaries,
null versus zero, duplicate identities, scope/approval gaps, deterministic ordering,
deep immutability, wrong-base deltas, protected floors, direct-constructor topology
tampering, structural equipment identity and rejected SIC draft approval.

Changed application files:

- `domain/safety_inputs.py` (new)
- `domain/plant_state.py` (new)
- `domain/source_snapshots.py` (new)
- `domain/safety_context.py` (new)
- `integrations/safety_input_adapters.py` (new)
- `integrations/graph_snapshots.py` (new)
- `domain/controlled_inputs.py` (recognize validated SIC drafts)
- `api/controlled_inputs.py` (SIC draft label/scope check)

Paths above are under `equipment_isolation/`. Tests: `tests/test_safety_inputs.py`
and `tests/test_safety_context.py` (new), plus `tests/test_controlled_input_postgres.py`.
Documentation: this note, implementation status/plan/foundation links and workspace
handoff. The researched fixture files were not modified.

No ORM migration, HTTP/OpenAPI, UI, viewer or runtime calculation change occurred.
Backend diff-check passed. Existing uncommitted work remains; nothing was committed
or pushed. Next is B2's persistence/admission integration, with production activation
still gated on approved policy, trusted Operations input, reconciled identity and a
complete, reproducible source-capture contract.
