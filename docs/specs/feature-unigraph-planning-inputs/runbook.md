# Verification and rollout runbook

Status: implementation verification and release-acceptance instructions. Automated verification is complete; live upstream/broker acceptance remains.

## Configuration and environments

Configure the existing UniGraph HTTP base URL for the intended environment and a stable non-secret source identity. Configure EIA_UNIGRAPH_EVENTS_BROKER_URL for the worker; do not commit populated credentials. Local broker is 127.0.0.1:55672, manual-development vhost unigraph_dev; management UI is http://127.0.0.1:55673. Do not use the automated-test vhost for manual acceptance data.

UniGraph local fixture projects 99001/99002 belong to plant 277. Production-style project 21 is absent locally. Verify a real drawing/graph association before running full isolation; the document-only fixture does not establish graph availability. Do not rewrite selected IDs to bypass this mismatch.

Use fresh caller authentication for HTTP checks. Never paste tokens into committed examples, logs, fixtures or screenshots. Event consumers do not need a user token. Do not claim broker availability is proof of current document verification.

## Acceptance walkthrough

1. Apply reviewed migrations to a disposable database and verify packaged Alembic head; then follow normal deployment migration procedure for the target environment.
2. Start the durable subscriber with `uv run equipment-isolation-document-events`; inspect exchange binding and worker logs/receipt diagnostics. Confirm the queue survives worker disconnect/reconnect.
3. Authenticate, load the plant bundle and verify approvals, hashes and adapted inputs; create a run and inspect its retained manifest.
4. In an isolated test plant upload a replacement: existing plan stays current while pending. Approve it: one plant change invalidates all relevant old versions despite multi-project fan-out.
5. Review diff, rerun and confirm immutable child version/current pins. Verify failed rerun leaves parent stale.
6. Test withdrawal, repeated/late events, event arrival during derivation, missed notifications and reconciliation after restart.
7. Verify UI refresh, disconnected SSE recovery, unavailable UniGraph and historical review without current upstream content.
8. Remove runtime mock fallback only after V01–V08 pass; retain fixtures and historic records.

Do not alter real approvals just to generate test traffic. Do not delete production queues or shared databases. Record broker publication, delivery and consumer-commit evidence separately.

## Operational checks and rollback

Monitor worker connectivity, unprocessed/quarantined messages, generation conflicts and HTTP verification failures. No healthy/green authorization claim follows from these diagnostics. If integration fails, disable new run admission and preserve historical review; never silently restore mock inputs. Stop the worker if necessary while retaining its durable queue. Review data-preserving migration rollback separately; do not automatically downgrade or drop snapshots.
