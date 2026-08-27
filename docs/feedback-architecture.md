# Isolation-plan feedback architecture

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

No requirement-deviation or execution-failure subtype is currently registered. Merely storing one of those category names cannot affect deterministic validation.

## Persistence

`plan_feedback` is the immutable submitted record and retains a current-state projection for efficient queries. Review decisions are append-only in `feedback_review_decision`. Derivation manifests lock the approved feedback set, `feedback_application_result` records deterministic coverage, and `plan_version_feedback` links the outcome to the resulting immutable plan version.

Feedback has no expiry date in the current increment. Later temporal plant-state support must be added deliberately rather than inferred from creation timestamps.

## Invariants

- A feedback subtype belongs to exactly one category.
- Category/subtype mismatches are rejected at the API and domain boundaries.
- Unsupported subtypes cannot enter a derivation request.
- Feedback targets the latest normalized plan version when submitted.
- Review decisions are append-only; projection fields on `plan_feedback` are compatibility/read-model fields.
- Derivation always reruns the complete authoritative pipeline.
- Failed or stale application is recorded, never silently treated as applied.
- Manual observations retain manual provenance; they are not represented as authoritative source-data updates.
