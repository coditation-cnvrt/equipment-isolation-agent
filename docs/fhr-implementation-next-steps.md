# FHR implementation: status and next delivery steps

Normal-run integration is now available: [runtime delivery and remaining gates](process-safety-run-integration.md).

Frontend synthetic testing is now available: see [the preview delivery](fhr-frontend-preview.md).
Migration head is 0010. This does not mark production B2 or the later safety gates complete.

Updated 2026-09-08 after the cross-repository review and corrective slice.

The [detailed implementation plan](fhr-implementation-plan.md) expands the delivery
order below into schema invariants, transaction/race handling, source contracts,
compatibility, acceptance tests, and production activation gates. It is the
execution reference for the next implementation batches.

## B1 development contracts implemented

The [B1 implementation notes](fhr-b1-input-contracts.md) describe strict SIC/PSD/work
scope contracts, protected composition, immutable graph captures and development
SafetyContext. SIC drafts are stored as `draft_validated` but cannot be approved.
All B1 contexts remain non-executable. Backend: 471 tests passed with PostgreSQL.
Next: B2 persistence/admission integration and the documented source/approval gates.

## B1 input research and fixtures

[Public-source SIC/PSD research](sic-psd-public-research.md) now supplies
`mock_sic_pnid_2151.json` and `mock_psd_pnid_2151.json`. Both are synthetic,
unapproved fixture formats aligned to the existing FHR context. Operational
criteria and graph identities remain explicit gaps. Research and B1 development contracts are implemented; production
source guarantees and admission remain pending.

## Completed persistence foundation (A1/A2)

The [controlled-input foundation](fhr-controlled-input-foundation.md) now implements
migration `0009_controlled_inputs`, scoped immutable revisions, trusted repository
approval/rejection, locked incomplete manifests, and transactional plan invalidation.
Both approval/promotion race orders are covered. Backend verification: 444 tests
passed with PostgreSQL enabled; fresh/populated upgrades, empty downgrade/re-upgrade
and ORM drift checks passed. No public routes, OpenAPI or UI contracts changed.

B1 development contracts are now implemented; see the notes above.
Run admission/classification remains inactive. The older delivery outline below is
retained as the roadmap; its persistence step is now complete.

## Completed corrective slice

- HILT cycles that contain edges absent from returned barrier/terminal paths now
  remain explicit unresolved branches. Reconverging paths to a barrier remain
  distinct without adding duplicate loop obligations for already represented edges.
- Explicit fluid/service codes from HILT segment, system, payload, and link fields
  and attributes retain source evidence. Conflicts block fluid resolution.
- Ordered HILT links and UniGraph edges/node facts survive candidate deduplication,
  final result assembly, path memberships, and normalized plan branches. New
  topology signatures include edge/link identity when available.
- Defect report and reclassification audit events preserve complete anchor facts.
  Previously stored events are not rewritten or supplied with invented facts.
- Freshness compares the latest material event with the captured material version;
  comments, evidence additions, and coordination do not invalidate a plan.
- New initial runs capture drawing-defect state before execution. Derived runs
  inherit the checkpoint locked in their derivation manifest. Request refreshes
  cannot replace this server-owned checkpoint. Completion records intervening
  events as unconsumed impacts, including defects opened and closed during a run.
- Legacy runs/manifests without a checkpoint, or runs whose exact scope changes
  during execution, produce an explicitly unknown governance dependency instead
  of capturing current state retrospectively.
- Route restoration releases its lock on cancellation and ignores late results.

The defect checkpoint is stored in the existing JSON request/derivation records.
It is an interim governance mechanism, not the proposed controlled FHR/SIC run
input manifest. Existing persisted plans, hashes, and audit events remain intact.
No ORM migration or public approval endpoint was added in this slice.

## What is still absent

`resolve_path_fluid()` and the base RBC matrix remain domain functions without
production run callers. The controlled revision registry exists, but there is no mandatory
FHR admission, HSC/EC classifier, effective SIC evaluation, configuration-aware
boundary solver, or authoritative per-path RBC validation. The UI still uses the
legacy work-scope booleans. Current plans remain advisory drafts.

## Delivery order and acceptance gates

### 1. Controlled-input persistence foundation — completed A1/A2

Add a reviewed migration after `0008_source_data_defects` and matching ORM models:
`controlled_input`, `controlled_input_revision`, `run_input_manifest`,
`run_input_manifest_item`, and `plan_version_invalidation`.

Implement server-side canonical hashing, FHR validation, immutable submission and
terminal decisions, scoped approved-head lookup, relational revision pins, and
atomic head replacement plus plan freshness invalidations. Preserve legacy hash
meaning; add an explicit hash-kind/schema discriminator when introducing aggregate
manifest hashes. Never seed or approve the synthetic mock.

Acceptance: offline domain/repository tests plus disposable PostgreSQL tests for
constraints, immutability triggers, concurrent approvals, transaction rollback,
manifest locking, historical readability, and replacement-revision invalidation.
Validate migration upgrade, downgrade policy, and ORM drift. No public approval
endpoint until authoritative approval permissions are established.

### 2. Resolve standards and source contracts alongside persistence

Obtain the decisions in architecture section 11: HSC/EC overlap precedence, PSD
reduction limits, bleed topology and safe destinations, fallback strength, service
and operating P/T precedence, incomplete fluid/two-phase handling, and overlapping
FHR scopes. Confirm stable document scope and the role allowed to approve FHR/SIC.
The default SIC needs a named process-safety approver and controlled version.

Acceptance: recorded decisions with rule IDs, example inputs, expected results,
and signed-off boundary cases. Until then, affected assessments remain blocked.
Drawing access does not establish controlled-document approval authority.

### 3. Admission and immutable SafetyContext

Resolve exact equipment and drawing scope before worker execution; select approved
FHR and effective SIC; snapshot the other required sources and structured work
scope; lock the manifest transactionally. Runtime reads revision IDs, never latest
heads. Define explicit legacy compatibility instead of silently enabling partial
new-mode runs. Do not reuse the defect checkpoint as proof that FHR/SIC were loaded.

Acceptance: missing/unapproved/conflicting inputs produce structured domain errors;
head changes during a run cannot alter consumed content; unavailable input states
cannot be mistaken for completed safety assessments.

### 4. Pure classification and observational path assessments

Implement validated SIC and structured work scope, HSC, EC, RBC overrides/floors,
and device admissibility with deterministic derivation traces. Attach assessments
to every retained process path. Do not claim RBC compliance from first-barrier
selection during this intermediate stage.

Acceptance: all matrix cells, thresholds, approved precedence cases, overrides,
unknown/missing properties, and input-order reproducibility tests.

### 5. Configuration-aware boundary solving and authoritative validation

Continue traversal until a complete admissible configuration is established or an
explicit failure state occurs. Preserve unresolved paths independently of selected
points. Verify series versus parallel barriers, branch-local positive isolation,
bleed position/destination, and unavailable/inadmissible-device continuation.
Replace safety reliance on candidate caps with explicit traversal failure states.
Drive obligations, evidence, and `core.validator.validate()` from those assessments.

Acceptance: scenario coverage for split/reconverging/cyclic graphs, shared devices
with different path hazards, all blocked outcomes, and agent omission/override
attempts. Store full assessments and traces so historical plans remain reviewable.

### 6. API/UI integration and release verification

Project input references, completeness, structured scope, per-path fluid/HSC/EC/RBC,
selected/rejected device roles, proving requirements, blockers, and derivation diffs.
Update API contracts, generated OpenAPI, UI types/adapters, intake, and review UI.
Keep FHR approval in a separately authorized controlled-document surface.

Acceptance: backend suite, PostgreSQL integration, UI test/lint/build, and end-to-end
run admission/review/refresh scenarios. No execution-authority claims. Change and
publish the viewer only if generic rendering capabilities actually require it.

## Corrective-slice verification

- Backend: 425 tests passed with disposable PostgreSQL enabled, including four
  opt-in database regressions. Without explicit test database configuration those
  four tests skip and the rest remain offline.
- Fresh database migrated to `0008_source_data_defects`; `alembic check` found no
  ORM drift. No schema change was needed for these fixes.
- OpenAPI regenerated and verified byte-identical to its pre-fix contents.
- UI verification and final Git checks are recorded in `NEXT_AGENT_HANDOFF.md`.

Database regression invocation, after migrating a disposable local database:

```bash
EIA_TEST_POSTGRES_HOST=/tmp/<disposable-socket-directory> \
EIA_TEST_POSTGRES_PORT=<port> \
EIA_TEST_POSTGRES_DB=eia_test_review \
uv run python -m unittest tests.test_source_defect_postgres
```

## Files changed by the corrective slice

Backend:

- `equipment_isolation/api/db.py`
- `equipment_isolation/api/plans.py`
- `equipment_isolation/core/candidates.py`
- `equipment_isolation/domain/isolation_standard.py`
- `equipment_isolation/domain/path_facts.py` (new)
- `equipment_isolation/integrations/hilt_index.py`
- `equipment_isolation/integrations/hilt_merge.py`
- `equipment_isolation/integrations/hilt_topology.py`
- `equipment_isolation/presentation/bbox_util.py`
- `equipment_isolation/presentation/payload.py`
- `tests/test_hilt_path_facts.py`
- `tests/test_source_defects.py`
- `tests/test_source_defect_postgres.py` (new)
- `tests/test_unigraph_topology.py`
- `docs/fhr-hsc-ec-rbc-architecture.md`
- `docs/fhr-implementation-next-steps.md` (new)

UI: `src/App.tsx`, `src/api.ts`, `src/test/AppWorkflowRoutes.test.tsx`.
Workspace: `NEXT_AGENT_HANDOFF.md`. Viewer: no changes.
