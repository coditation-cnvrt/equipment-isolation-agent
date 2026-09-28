# Implementation plan

Status: implemented in the working tree; live upstream/broker acceptance pending. Requirements: [spec.md](spec.md). Verification record: [tasks.md](tasks.md).

## Architecture

Backend integration clients fetch authorized UniGraph HTTP documents; domain adapters validate and normalize inputs; PostgreSQL retains manifests, snapshots and freshness evidence; a separate RabbitMQ worker commits notification effects. The UI talks only to the isolation backend. Keep the viewer presentation-only.

Extend existing plan derivation, dependency, audit and HTTP/SSE infrastructure rather than introducing another plan store. Reuse experimental-backend concepts for immutable version pins and audit records, not its blanket superseding behavior or acknowledgement treatment.

## Persistence and concurrency

Introduce source-qualified document snapshots, per-run/version dependency pins, observed plant/type heads, event inbox receipts and append-only input-change evidence. An upstream integer revision ID must never be treated as an existing local controlled-input UUID. Identity includes configured source identity, CNVRT plant and register/type. Record head generation independently of document revision number and graph version.

Keep immutable snapshot content separate from mutable observed-head/freshness projections. Add uniqueness for source/event ID and source/change ID; one change can have several routing deliveries. Keep individual delivery receipts while applying one plant-wide change. Reject same-generation conflicting heads as an integrity problem; retain newer generations and ignore late older notifications.

Lock observed heads and dependent-version freshness updates consistently. Compare freshly retrieved heads with stored observations before admitting work. Persist the exact admitted manifest; a completion-time mismatch produces a stale version, never replacement input content. An upstream change can occur after any HTTP check; do not claim distributed atomicity. HTTP and events converge, and any future authorization must recheck at decision time.

Migrate using reviewed Alembic revisions. Backfill old runs as having unknown document freshness without inventing source pins. Do not modify original requests, results or version snapshots. Keep old snapshots readable without live upstream availability.

## Adapter and admission

Implement the rules in [contracts/inputs.md](contracts/inputs.md). Fetch the plant bundle plus approval decisions for selected immutable revisions; verify the current heads again if supplementary reads could have raced. Bound retries; return an input-change conflict if the bundle keeps changing.

New browser run submission supplies work scope and expected revision references. Backend-built process safety inputs continue through build_run_config and run_agent_pipeline. Integrate all new-run and child-derivation entrypoints; historical request deserialization must not allow client-supplied approval to bypass new admission.

Preserve the existing validity rule: effective PSD expiry is the earlier of declared expiry, if present, and declaration time plus SIC validity hours. Do not rewrite declaration time. An expired approved PSD is visible but blocks new governed admission until replaced; historical analysis remains readable.

## Freshness and notification behavior

Freshness is fresh, stale or unknown; upstream unavailability additionally records a verification error. A known stale result never becomes fresh because the service is unavailable. Combine document changes with existing asset/source freshness so either can require rerun.

The subscriber needs broker credentials only, never persisted end-user tokens. It records trusted-broker notification references, not full document content or permission grants. HTTP reconciliation uses the current requesting user's token. On worker startup, replay queued deliveries; authenticated reads reconcile gaps from before queue creation. Do not claim an unauthenticated startup fetch of protected documents.

Notify connected clients after database commit using existing stream mechanisms. Reconnection and ordinary HTTP reads remain authoritative. Expose worker connection state, last successful processing time, pending/quarantined counts and reconciliation errors without secrets.

## Diff and UI

Compare captured normalized documents with current authorized content using stable fluid/mapping keys and PSD/SIC record identities; report additions, removals and changed values. Classify engineering or unknown changes as potentially safety-significant. Only source_document, source revision labels and approval-display metadata are non-safety-significant; any current-head replacement still requires rerun. Missing current content yields an unavailable diff, not an empty diff.

Workspace loads approved document summaries and keeps work-scope controls. Review displays Draft · Inputs changed, reasons, expandable diff and rerun. An unknown historical basis requests rerun. Do not add authorization or execution controls. Use existing TanStack Query ownership and authenticated cache isolation; invalidate relevant plant/run keys on events and revalidate through backend admission regardless of client cache.

## Test matrix

| ID | Requirements | Evidence |
|---|---|---|
| V01 | PI-01/02 | Plant permissions, wrong project, 401/403/404/503, source identity and hashes. |
| V02 | PI-02/11 | FHR scopes, SIC shape conversion, PSD identities/expiry, null/zero/false and unsupported policies. |
| V03 | PI-03/04 | Immutable manifests, migration/backfill, replacement during admission and completion. |
| V04 | PI-05/06 | Durable queue, duplicate/fan-out/late events, withdrawal, rollback, reconnect and quarantine. |
| V05 | PI-06/07 | Plant-wide dependency selection, missed events, unavailable reads, older HTTP observations. |
| V06 | PI-08 | Rerun creates child; failed run preserves parent; feedback and shared conditions retained. |
| V07 | PI-09/12 | UI loading/errors/diffs/refresh; no authorization shortcuts; original assurance retained. |
| V08 | PI-10 | Live-document cutover, absent approvals block, no runtime mock fallback, old runs readable. |

Unit and contract tests are offline. Integration tests use disposable databases/broker resources only. Run backend unittest suite and OpenAPI generation for contract changes; UI test/lint/build; migration checks on disposable PostgreSQL; diff/status in each touched repo. Record precise commands and working-tree/commit identity when tests exist; baseline investigation is not implementation-test evidence.
