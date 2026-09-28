# HTTP contract and compatibility

Status: implemented; existing UniGraph wire contract remains authoritative upstream.

## Upstream reads

Use GET /api/projects/{unigraph_project_id}/planning-documents for the bundle, and GET /api/projects/{unigraph_project_id}/planning-documents/revisions/{revision_id} for approval decisions. Type-specific /{fhr|sic|psd}/current is available for diagnostic/targeted reads, not three independently assembled admission heads. Forward the caller's bearer token. Validate returned plant, register, type, schema and hashes. No direct database connection, original-file download or S3 access is needed in the product integration.

## Isolation API additions

- GET /planning-context/planning-documents with existing CNVRT project, collection, UniGraph project and drawing-context fields: return verified plant/source identity, one status per fhr/sic/psd, current references, approval summaries, compatibility/validity issues and a document-set token derived from ordered references. A missing head is represented explicitly; authentication/permission/upstream failures are errors, not empty bundles.
- GET /planning-context/planning-documents/events with the same authorized context: stream committed plant-level head changes from the durable PostgreSQL inbox. The initial ready event establishes a replay cursor; ordinary HTTP reads remain authoritative reconciliation.
- Extend new-run submission with work scope and expected document-set references. Use immutable source/register/revision/generation/hash tuples. Backend resolves content; clients cannot submit authoritative approval metadata. Reject mismatching expectations with HTTP 409 planning_documents_changed.
- Extend persisted plan/version responses with document dependencies, document freshness, verification status and changed-input summaries. Preserve existing lifecycle, run status and assurance fields.
- GET /isolation-plans/{plan_id}/versions/{version_id}/input-diff: authorized structured comparison of captured inputs and current document heads, including references, changed paths, old/new values and significance classification.
- Extend the existing derive action with a planning_inputs trigger. Successful responses use existing asynchronous run transport and immutable child-version linkage.

Define actual Pydantic models alongside implementation, export docs/openapi.json and update UI types/adapters in the same task. Reuse existing route-level scope checks and error envelope conventions.

## Error semantics

Missing/unapproved/withdrawn required heads or incompatible documents block admission with actionable input errors (409); changed expected heads return 409; invalid client shape returns 422; authentication remains 401; unauthorized scope remains 403; unavailable verification returns 503. Do not translate upstream project-not-found into a different graph ID.

Read-only historical results remain accessible with existing authorization even when UniGraph documents cannot currently be read. Current-input verification is separate and may be unknown/unavailable. No approval, execution or closed-state mutation API is part of this feature.

## Compatibility

Keep historical embedded process_safety_inputs deserializable for audit/review. New public submissions cannot opt into the historical mock/approval-claim path. Retain legitimate CLI/test fixtures explicitly outside production browser admission. Version the adapted snapshot format rather than silently changing the interpretation of old stored values.
