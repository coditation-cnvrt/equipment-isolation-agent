# Planning input adapter contract

Status: implemented. Input schema: upstream planning-documents-v1. Adapter identifier: unigraph-planning-inputs-v1.

## Source manifest

For each type retain configured source identity, verified CNVRT plant, entry UniGraph project, register ID, revision ID/number, generation, schema version, source-content hash, normalized-content hash, captured approval decision and retrieval time. Retain the exact normalized JSON and an independently hashed adapted payload. Store document pins separately from graph/rule-engine/model pins; never fabricate missing versions.

Verify upstream normalized hashes using its canonical JSON serialization. Approval derives from the current register head and corresponding immutable decision, not parser status=valid or CSV approved_by fields. If detail/current reads disagree, refresh with bounded retries and fail admission on persistent drift.

## FHR

Keep fluids and service_code_map values, null semantics and provenance. Add internal metadata through a typed adapter; do not label a plant document as originating from one drawing. Resolve explicit matching unit scopes before plant-wide mappings, reject ambiguity within a scope, and never fuzzy-match descriptive unit names. Missing/ambiguous mapping retains conservative HSC-4 and data-gap behavior. The run must supply an explicit unit scope; do not assume every row's descriptive scope means the PSD unit.

## SIC

Map normalized policy sections into internal parameters and gas criteria into acceptance_criteria. Preserve permits and all unsupported fields in the source snapshot; report unsupported operational policy as a limitation instead of silently claiming implementation. Convert matrix overrides explicitly, preserving justification and linking any required approval reference to verified evidence. Approval of the document does not prove implementation of every configured policy.

## PSD

Map record_id to stable internal row identities with section/type qualification; preserve job/HILT/UniGraph identity fields. Never resolve an asset solely by a repeated tag or visual location. Preserve plant scope and derive a separate drawing-specific application view. Missing IDs and partial section coverage remain gaps. Keep original declaration and optional expiry; effective expiry is min(explicit expiry, declared_at + SIC validity_hours), or the SIC-derived expiry if none was declared. Do not invent evidence for active isolations or overrides.

## Approval and safety gates

Replace unconditional repository-approval blockers only where verified manifest evidence establishes the corresponding approval. Preserve all other domain gaps, synthetic source facts, unresolved policy precedence and field-confirmation requirements. Do not require CSV approval fields to mirror the repository decision and do not rewrite them. The existing deterministic validator remains the sole assurance authority.

## Historical compatibility

Version new adapted envelopes and accept old envelopes only through historical replay/read paths. Old records without external pins have unknown freshness and cannot acquire fabricated approval. A source-system identifier change is not a document revision: require explicit configuration and reconciliation; do not merge unrelated environments by numeric ID.
