# Isolation-plan feedback architecture

Plan feedback is the plan-local context. Shared plant facts use the separate
asset-condition model described below; they are not represented by feedback
rows with nullable plan foreign keys.

## Decision

Plan feedback is one governed record family with four distinct categories:

- `input_correction`: changes a versioned local input overlay and requires a complete re-derivation.
- `manual_observation`: adds or reviews human-observed planning evidence with explicit manual provenance and requires a complete re-derivation.
- `requirement_deviation`: leaves the derived requirement unchanged and attaches a governed deviation. This category is reserved until requirements and authorisation are first-class domains.
- `execution_failure`: records a failed field action or proving result, supersedes the executable plan, and may trigger re-derivation. This category is reserved until field execution exists.

The categories may share persistence and audit infrastructure, but they must not share untyped application behavior. A submitted feedback record never changes a plan directly. Only an approved, supported feedback subtype may be translated by the backend into a deterministic derivation input.

## Compatibility

The existing `/isolation-plans/{plan_id}/changes` API remains available during the transition. Existing `change_type` values are mapped to a single authoritative `feedback_category`; callers may provide the category, but a mismatched category is rejected.

Existing supported actions map as follows:

- `input_correction`: `correct_label`, `mark_point_unavailable`, `mark_point_available`.
- `manual_observation`: `accept_manual_candidate`, `reject_manual_candidate`, `confirm_bypass`, `add_manual_isolation_point`.

Point actions are state transitions, not a generic menu. Accepted barriers may
be relabelled or reported unavailable; manual-review candidates may be accepted,
accepted specifically for an alternate flow path, or rejected; excluded points
cannot be rejected again; and unavailable points may only be relabelled or
returned to service. Availability is independent of selection, so a known
excluded candidate may still be reported physically unavailable.

No requirement-deviation or execution-failure subtype is currently registered. Merely storing one of those category names cannot affect deterministic validation.

## Persistence

`plan_feedback` is the immutable submitted record and retains a current-state projection for efficient queries. Review decisions are append-only in `feedback_review_decision`. Derivation manifests lock the approved feedback set, `feedback_application_result` records deterministic coverage, and `plan_version_feedback` links the outcome to the resulting immutable plan version.

Feedback has no expiry date in the current increment. Later temporal plant-state support must be added deliberately rather than inferred from creation timestamps.

## Shared operational context

`asset_condition` records the current lifecycle of a shared fact about an exact
`asset_reference`. The first supported condition is `unavailable`. Reporting it
makes the condition active immediately; `asset_condition_event` preserves
append-only report, confirmation, and clear events. Returning an asset to
service clears the active condition rather than creating an active `available`
fact.

Fresh and derived runs load active conditions in their explicit UniGraph and
CNVRT drawing scopes. When a request omits `job_id`, the run refreshes and
persists the condition snapshot immediately after authoritative boundary/job
resolution and before HILT candidate resolution. The backend translates them
into deterministic unavailable overlays after plan-local feedback, so local
feedback cannot weaken the shared safety state. `plan_version_asset_condition`
and an input snapshot
preserve exactly which conditions a completed version considered.

Plan freshness is computed from that immutable snapshot and the currently
applicable active-condition set. A changed set makes the latest version
`stale`; it does not mutate or revoke the saved version. The scoped
`/asset-conditions/events` SSE stream is an invalidation signal only. Clients
refetch plan detail and use the backend freshness result rather than deriving
authority from event order or timestamps. The stream uses overlap replay plus
event-ID deduplication so a transaction that commits late is not skipped by a
timestamp cursor. Every condition read, mutation, and stream subscription first
verifies the bearer token against the persisted CNVRT/UniGraph scope.

A stale version can launch a complete child derivation with the
`asset_conditions` trigger even when no approved plan feedback exists.
Derivation manifests record `corrections`, `asset_conditions`, or `combined`
provenance. The child run snapshots the current shared conditions, and normal
plan-version lineage and structural diffing remain authoritative.

Identity matching is exact and source-scoped. Tags are not physical-asset keys.
Cross-drawing propagation requires a future governed canonical-asset mapping;
the current model does not infer that two repeated tags identify one valve.

## Invariants

- A feedback subtype belongs to exactly one category.
- Category/subtype mismatches are rejected at the API and domain boundaries.
- Unsupported subtypes cannot enter a derivation request.
- Feedback targets the latest normalized plan version when submitted.
- Feedback must be valid for the target's state in that version; no-op inclusion,
  exclusion, availability, and missing-point requests are rejected.
- Only one submitted or approved feedback record may be open for a target's
  selection, availability, label, or addition behavior at a time.
- Review decisions are append-only; projection fields on `plan_feedback` are compatibility/read-model fields.
- Derivation always reruns the complete authoritative pipeline.
- Shared-condition events invalidate clients; only backend snapshot comparison determines staleness.
- Asset-condition re-evaluation creates a child plan version and never rewrites the stale parent.
- Failed or stale application is recorded, never silently treated as applied.
- Manual observations retain manual provenance; they are not represented as authoritative source-data updates.
