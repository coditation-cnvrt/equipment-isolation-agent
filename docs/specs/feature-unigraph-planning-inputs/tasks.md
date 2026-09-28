# Implementation task checklist

Status: implementation complete in the working tree; automated verification complete, live upstream/broker acceptance pending.

Requirements: [spec.md](spec.md). Architecture/test matrix: [plan.md](plan.md). Operational acceptance: [runbook.md](runbook.md).

Read the applicable repository instructions and current diff before each task. Record evidence after the final relevant edit. Do not mark implementation complete from discovery checks or upstream tests. Preserve unrelated changes; verify and commit each repository separately. No push without request.

## T00 — Establish scope and baseline

Owner: backend documentation. Dependencies: none. Requirements: PI-01–PI-12.

- [x] Inspect current lifecycle, immutable versions and freshness mechanisms.
- [x] Read PRD/UX requirements and experimental-backend patterns.
- [x] Verify upstream HTTP bundle/current/detail reads, approval decisions and normalized hashes for all three document types.
- [x] Confirm plant-wide sharing and local project-ID differences.
- [x] Verify temporary RabbitMQ subscription connectivity; distinguish this from actual event receipt.
- [x] Confirm approved-change invalidation, deferred authorization and preserved closed history.
- [x] Record specification, plan, contracts and rollout guidance.

Evidence: 2026-09-17 discovery in spec.md. No isolation-agent event processing or integrated rerun has been verified.


## T01 — Freeze executable contracts

Owner: backend. Dependencies: T00. Requirements: PI-01/02/11. Verification: V01/V02.

- [x] Record upstream implementation revision and compare its current HTTP/event/schema contracts with this package.
- [x] Create sanitized fixtures for bundles, decisions, FHR/SIC/PSD, replacements and withdrawal; exclude tokens and private actor details.
- [x] Define typed external references and versioned adapted envelopes, keeping integer external IDs distinct from internal UUIDs.
- [x] Add hash/schema/null/zero/false tests, plant mismatch cases, exact FHR unit scopes, SIC mappings and PSD expiry/identity cases.

Acceptance: Fixtures match upstream semantics; missing engineering information remains explicit.


## T02 — Add durable persistence

Owner: backend. Dependencies: T01. Requirements: PI-03/05/06. Verification: V03/V04.

- [x] Add source-qualified immutable snapshots, dependency pins, observed heads, event inbox and input-change evidence.
- [x] Implement uniqueness and consistent transactions for event IDs, fan-out changes and generation ordering.
- [x] Review Alembic upgrade/downgrade; test fresh installation and upgrade on disposable PostgreSQL.
- [x] Preserve historical request/result content and mark absent document pins unknown; test immutable snapshots and concurrent updates.

Acceptance: Old versions remain readable; no fabricated pins or duplicate invalidation effects.


## T03 — Implement authorized reads and adapters

Owner: backend. Dependencies: T01/T02. Requirements: PI-01/02/07/11. Verification: V01/V02/V05.

- [x] Implement bounded-timeout UniGraph reads using the caller token and verified plant association.
- [x] Fetch approval evidence; validate hashes/schema; detect bundle/detail races with bounded retries.
- [x] Implement contracts/inputs.md and retain original normalized payloads separately from adapted hashes.
- [x] Expose approved/missing/expired/incompatible/unavailable document context; clear only provenance blockers established by verified evidence.

Acceptance: No fallback or guessed identity; remaining planning and field-confirmation gaps remain visible.


## T04 — Integrate admission and derivation

Owner: backend. Dependencies: T03. Requirements: PI-03/04/08/10. Verification: V03/V06/V08.

- [x] Add expected-document references and server-side resolution to every new public run entrypoint.
- [x] Capture manifests/work scope through existing config-builder and agent-pipeline ownership.
- [x] Reconcile heads at admission and completion; changed inputs retain completed-but-stale results.
- [x] Extend the derive trigger for planning inputs, preserving applicable approved feedback and current shared conditions.
- [x] Test stale expectations, replacement reconciliation, failed child runs and historical deserialization without an approval bypass.

Acceptance: Reruns create immutable child versions; refresh or failure never rewrites or refreshes the parent.


## T05 — Implement subscriber and reconciliation

Owner: backend. Dependencies: T02/T03/T04. Requirements: PI-05/06/07. Verification: V04/V05.

- [x] Add broker dependency/configuration and a separately runnable worker; document its exact command in runbook.md.
- [x] Declare the durable queue/binding and commit receipt/effects before acknowledgment.
- [x] Implement retry/requeue, quarantine, event-type dispatch, duplicates, fan-out, withdrawal and late/conflicting generations.
- [x] Invalidate mismatching plant dependencies and combine document freshness with existing asset/source freshness.
- [x] Add authenticated HTTP reconciliation, post-commit notifications and receipt diagnostics without retaining user tokens.

Acceptance: Reconnect preserves queued changes; unknown upstream state never silently makes a stale plan fresh.


## T06 — Integrate API, diff and UI

Owner: backend and UI; verify independently. Dependencies: T04/T05. Requirements: PI-09/12. Verification: V07.

- [x] Implement contracts/api.md; export OpenAPI and align UI types/adapters.
- [x] Add structured input diffs with explicit potentially-safety-significant classification and unavailable-diff handling.
- [x] Automatically load approved document summaries while preserving work-scope editing.
- [x] Show stale/unknown drafts, changed input reasons and current-input rerun actions; historical review uses captured inputs.
- [x] Invalidate scoped TanStack Query keys on notifications; retain HTTP focus/reconnect/poll reconciliation.
- [x] Confirm no authorization/execution controls or viewer changes are introduced.

Acceptance: UI explains changed inputs; browser cache never establishes authoritative admission.


## T07 — Verify and retire runtime mocks

Owner: backend and UI. Dependencies: T06. Requirements: PI-01–PI-12. Verification: V01–V08.

- [x] Run backend unittest suite, migration/readiness checks on disposable PostgreSQL, and OpenAPI generation/verification.
- [x] Run UI test, lint and build; retain the existing viewer dependency.
- [ ] Perform the isolated runbook walkthrough with valid graph/drawing context, documenting environment and IDs.
- [ ] Prove pending upload does not invalidate; approval/withdrawal does; multi-project delivery produces one plant change.
- [ ] Verify replacement during a run, failed/successful reruns, broker recovery and missed-event reconciliation.
- [x] Remove runtime example consumption and production mock fallback; retain fixtures and historical compatibility.
- [x] Rerun automated checks affected by removal; inspect diff/check/status separately in each touched repository.

Acceptance: automated contract and persistence coverage passes. The unchecked isolated-environment walkthrough items remain release prerequisites; new governed browser runs use approved upstream documents exclusively and missing inputs never select samples.


## Evidence record

Upstream contract inspected at graph-convert revision `cbc944b8fc2b43b1cc2da230f1b30994234054cf`. Automated evidence on 2026-09-18: backend unittest discovery; disposable PostgreSQL migration, schema-drift, immutability, deduplication, generation-conflict, staleness and replay smoke verification; OpenAPI export/contract verification; UI Vitest, lint and production build. Live upstream upload/approval, broker disconnect recovery and end-to-end drawing-context walkthrough remain unchecked above. This release does not claim authorization or field-execution acceptance.
