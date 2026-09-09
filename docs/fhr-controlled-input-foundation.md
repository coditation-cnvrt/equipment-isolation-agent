# Controlled-input persistence foundation

Implemented 2026-09-08: implementation-plan batches A1/A2.

Subsequent [B1 work](fhr-b1-input-contracts.md) adds validated SIC draft storage
and development contracts; SIC approval and runtime admission remain unavailable. This is an internal
backend repository capability; existing runs do not yet consume FHR/SIC or perform
HSC/EC/RBC classification. No public contract or approval endpoint changed.

## Integration

`api/controlled_inputs.py` provides `ControlledInputRepository(session_factory)`.
Use the same SQLAlchemy session factory as the run repository. It returns detached
plain projections and exposes:

- `create_document(input_type, context, document_key, actor_id)`
- `submit_revision(input_id, revision_label, schema_version, payload, actor_id)`
- `decide_revision(revision_id, decision, actor_id, reason, expected_head=...)`
- `get_revision(revision_id)` and `get_approved_head(input_type, context)`
- `lock_manifest(run_id, expected_revisions, plan_time=...)`, its composable
  `lock_manifest_in_session(...)` variant, and `get_manifest(run_id)`
- `list_invalidations(plan_version_id)` and batched `freshness(plan_version_ids)`

`decide_revision` is a trusted service operation, not an authorisation boundary.
Before exposing it, establish the authoritative approval permission and stable
actor identity. No caller-supplied HTTP approval identity may be forwarded as trusted.
There is deliberately no production default approver or auto-approved seed data.

FHR uses exact project/collection/job scope. SIC uses exact project/collection
scope with an empty job component. One stable document owns each type/scope;
creating a different document key does not bypass that uniqueness. Identity is
immutable. Global/site/unit resolution is not implemented.

## Content and decisions

`domain/controlled_inputs.py` defines `controlled-json-v1`: UTF-8, sorted object
keys, original meaningful array order, finite plain-decimal numbers, equivalent
integer/float values hashed alike, negative zero normalized to zero. Floats use
Python's shortest round-trip decimal representation. Non-JSON objects, non-string
keys, invalid Unicode and non-finite numbers are rejected. Explicit datetimes use
UTC with six fractional digits and `Z`; arbitrary datetime coercion is rejected.
Legacy `api.plans.canonical_hash` is unchanged.

`fhr-v1` validates via the existing FHR parser, rejects unknown safety fields or
alternate unit fields, and sorts fluid/service-map rows and special-hazard lists.
Source annotations belong in an object-valued top-level `metadata` field. Document
and fluid revision labels must agree with the submitted label. Submitted content,
validation outcome and server SHA-256 never change. Unsupported schemas, including
SIC today, can be stored pending but cannot be approved. Corrected content requires
a new label/revision; duplicate submissions produce an explicit conflict.

Imported approval strings are source evidence only. Every submission starts
pending. One trusted terminal decision approves or rejects the whole revision.
`approved_fhr(repository_projection)` produces an immutable runtime register with
the server decision applied to the document and all rows, while preserving imported
claims in the stored payload/hash. Never call this adapter on an HTTP request.
Known mock status/revision markers and synthetic metadata cannot be approved;
the annotated development fixture also does not satisfy the strict submission
schema. It is neither seeded nor used by production execution.

Replacement requires an explicit expected head, including `None` for initial
approval. Conflicting simultaneous replacements fail with `head_changed`. Retrying
an identical terminal decision returns its original record and does not reset a
newer head. PostgreSQL guards enforce immutable payloads/terminal decisions, matching
approved parent/head identity, and atomic approval/head replacement. SQLAlchemy and
SQL integrity checks complement the domain validator; the database is not a second
FHR schema-validation engine.

## Foundation manifests and freshness

The manifest operation reads the queued persisted run request; it cannot add pins
to an already-started run. It checks exact revision/type/scope/current approval,
locks documents in UUID order, computes hashes, inserts relational items, and locks
the manifest within one transaction. A deferred guard rejects an unlocked commit;
item guards reject forged pins and late additions. Identical retries return the
existing manifest. A future admission service can create the run and invoke the
in-session operation in one transaction before dispatch.

All manifests in this schema are `mode=foundation`, `completeness=incomplete`.
Missing graph, PSD, structured work scope and rule-engine inputs are explicit,
as are absent FHR/SIC slots. These pins are foundation records, not proof that the
existing runtime consumed the sources. Milestone B must wire immutable execution
and extend supported manifest modes/schema. The logical primary key includes role;
only `source` is currently allowed. B1 must add supported SIC base/delta roles with
validated composition, rather than pretending generic JSON already implements it.

The aggregate hash includes canonical request, context, explicit plan time, exact
pins/approval snapshots and completeness. Generated manifest ID, run ID as a
separate storage field, and lock time are excluded. No `PlanVersion.input_hash`
values or semantics changed; adding a manifest hash discriminator remains B2 work.

Approval appends invalidations for existing plans using superseded revisions,
including revisions more than one head behind. The external-run-link insert trigger
also reconciles head changes for late promotion, covering initial and child plans.
Both paths use the same document locks. Provenance links for manifested runs cannot
be edited or deleted. Invalidations themselves are append-only. All this commits
with the surrounding approval/promotion transaction.

The separate repository freshness projection reports `historical_unknown`,
`incomplete`, or `stale`, with consumed/current revision IDs. It compares current
heads directly in a batched query as a conservative read-through check. It does
not yet alter the HTTP/UI freshness contract; that and combined defect/asset/input
reason presentation belong to B2. Existing source-defect behavior stays intact.

## Migration and verification

Migration `0009_controlled_inputs` follows the existing `0008_source_data_defects`.
It adds five tables, indexes, the cyclic head FK, mutation guards, and transactional
approval/promotion invalidation triggers. Apply with `uv run alembic upgrade head`
before API startup; current and packaged head must agree. No runtime DDL was added.

Verified on disposable PostgreSQL using an explicitly configured `/tmp` socket:

- Fresh upgrade through 0009 and ORM drift check.
- Empty 0009 → 0008 → 0009 round trip.
- Populated 0008 upgrade preserving serialized run, plan/hash, defect audit and
  dependency rows; no historical controlled inputs/manifests fabricated.
- Offline upgrade SQL and migration history reviewed.
- Full backend suite: 444 tests passed, including 11 new controlled-input database
  tests and the four existing source-defect database regressions.
- Eight new offline tests cover canonical golden vectors, rejected values/units,
  ordering, scope, timestamp encoding, mock rejection and the approval adapter.
- Forced competing transaction orders for approval/promotion, concurrent approval
  winner/conflict, rollback, head history, late child promotion, direct mutation/
  wrong-pin rejection, manifest retry, and preserved legacy hashes.

Database tests require `EIA_TEST_POSTGRES_HOST=/tmp/<socket>`, optionally port,
user and `EIA_TEST_POSTGRES_DB=eia_test_<name>`. Ordinary discovery skips these 15
opt-in tests. No shared database was modified. Downgrade is destructive to the new
registry: the round-trip check used an empty disposable database only. Populated
installations need verified backup/restore and forward-fix deployment procedures.

## Files changed in A1/A2

- `equipment_isolation/domain/controlled_inputs.py` (new)
- `equipment_isolation/api/controlled_inputs.py` (new)
- `equipment_isolation/api/db_models.py` (additive ORM records)
- `equipment_isolation/api/migrations/versions/0009_controlled_inputs_controlled_inputs.py` (new)
- `tests/test_controlled_inputs.py` (new)
- `tests/test_controlled_input_postgres.py` (new)
- `tests/test_api_db.py` (migration head, resource and table expectations)
- This document, implementation status/plan/architecture links, and workspace handoff.

OpenAPI, UI and viewer were not changed by this batch. Existing dirty work remains.
The next batch is B1: supported SIC/work-scope/SafetyContext contracts and exact
source capture, with the decision gates in the detailed implementation plan.
