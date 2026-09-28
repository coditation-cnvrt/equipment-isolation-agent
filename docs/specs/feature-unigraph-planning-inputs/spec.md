# UniGraph planning inputs and draft-plan invalidation

Status: implemented in the working tree; automated verification complete, live upstream/broker acceptance pending. Recorded 2026-09-17; updated 2026-09-18.

## Purpose and ownership

Replace automatic mocked FHR/SIC/PSD inputs with approved plant documents retrieved from UniGraph. Preserve immutable run evidence while identifying plans that must be rerun after an approved input changes.

This package follows graph-convert's spec / plan / tasks / contracts / runbook structure. Start with this specification, then [plan.md](plan.md), [tasks.md](tasks.md), [HTTP contract](contracts/api.md), [event contract](contracts/events.md) and [adapter contract](contracts/inputs.md). The task checklist distinguishes implemented behavior from live-environment acceptance still required before release.

Application changes belong to equipment-isolation-agent and equipment-isolation-agent-ui. UniGraph and equipment-isolation-backend are reference implementations, not modification targets. No viewer change is required. Earlier mock-input documents remain historical/design references; this package governs the replacement integration.

## Confirmed decisions

- Plant identity is CNVRT project ID, shared across collections and linked UniGraph projects.
- Invalidate on approved current-head replacement or withdrawal, not upload, parsing or rejection of a pending revision.
- Deliver document governance first. Authorization, authorizer-role management and field execution are explicitly deferred; plans remain drafts.
- Closed plans will remain historical records when later lifecycle support exists. Reuse requires a new assessment; do not retrospectively rewrite approvals or closure.
- No automatic reruns. A user rerun creates a new immutable version through the full existing pipeline.
- Preserve separate run status, plan lifecycle, input freshness and deterministic assurance. A successful run does not become failed when its inputs become stale.

## Requirements and acceptance

| ID | Requirement | Acceptance |
|---|---|---|
| PI-01 | Resolve approved documents through authorized HTTP reads. | Caller bearer token and verified project-to-plant association; no direct UniGraph database reads in product code. |
| PI-02 | Adapt plant documents deterministically. | Explicit versioned adapter, schema/hash validation, no invented identities, approval or engineering values. |
| PI-03 | Pin immutable evidence. | Every new run/version retains source revisions, generations, hashes, approval evidence, raw normalized inputs and adapter version. |
| PI-04 | Control admission and races. | Backend resolves inputs; stale client expectations conflict. Reconcile at admission/completion; changed inputs leave a completed result stale. |
| PI-05 | Consume durable notifications. | Dedicated queue, transactional inbox/effects, retries, deduplication and ordered generation handling survive restart. |
| PI-06 | Invalidate all affected drafts. | Changed/withdrawn approved document marks mismatching plant dependencies stale across collections/exports; historical results remain unchanged. |
| PI-07 | Reconcile missed events. | Authenticated HTTP reads establish current heads on planning-context load, freshness checks and admission; unavailable verification is explicit. |
| PI-08 | Rerun against current inputs. | Full pipeline creates a child version, preserves applicable approved feedback and shared conditions; failure does not clear old staleness. |
| PI-09 | Explain freshness in UI. | Revision summaries, changed-document reasons, input diff and rerun action; historical review uses captured inputs. |
| PI-10 | Retire runtime mocks after verification. | No automatic sample fallback after cutover; fixtures and historical records still work. |
| PI-11 | Preserve safety distinctions. | Approval integration clears only justified provenance gates; topology, admissibility, field confirmation and policy gaps remain explicit. |
| PI-12 | Preserve authorization boundary. | No authorization/execution endpoints or controls, no lifecycle backfill beyond draft, no acknowledgement bypass. |

## Lifecycle and requirements traceability

[PRD](../../isolation-planning-agent-ux-i1/extracted/Isolation_Planning_Agent_Requirements_v1.md) REQ-OM-03 defines Draft → Authorised → Issued → Being Set → Set & Proved → Active → Being Removed → Reinstated → Closed. REQ-OM-04 requires identified human authorization and exact version pins. REQ-OM-05 requires invalidation and classified diffs after input changes. REQ-IN-03, REQ-IN-06 and REQ-SA-03 require document revision recording, PSD validity and reproducibility.

The [UX prototype](../../isolation-planning-agent-ux-i1/Isolation%20Planning%20Agent%20v2.dc.html) illustrates pinned inputs, change review and procedural status. It is not proof that these features are implemented. This release partially establishes OM-05/SA-03 infrastructure; it does not claim full lifecycle or authorization compliance.

## Observed baseline, 2026-09-17

- Current database constraint allows only draft plans; immutable versions and asset/source-condition freshness already exist.
- Local UniGraph runs at port 5050. Projects 99001 and 99002 map to plant 277; local project 21 returns 404.
- Authenticated bundle/current/detail reads returned HTTP 200. FHR register 1/revision ID 3/revision number 3/generation 3; PSD register 2/revision ID 4/revision number 1/generation 1; SIC register 3/revision ID 5/revision number 1/generation 1. All had approval decisions and matching normalized hashes.
- Uploaded content still contains mock assumptions, partial PSD inventories and missing structural identities. Repository approval does not erase that provenance.
- RabbitMQ exchange had 20 publications and no bindings before a temporary subscription test. Subscription succeeded; no new event arrived during observation. No end-to-end consumer behavior is implemented or certified by that test.

## Reference implementation

- [UniGraph feature specification](../../../../../graph-convert/docs/specs/feature-fhr-upload/spec.md)
- [UniGraph HTTP contract](../../../../../graph-convert/docs/specs/feature-fhr-upload/contracts/api.md)
- [UniGraph event contract](../../../../../graph-convert/docs/specs/feature-fhr-upload/contracts/events.md)
- [Experimental authorization use cases](../../../../equipment-isolation-backend/packages/isolation_planning_service/src/isolation_planning_service/application/use_cases/authorisation.py)

Sibling-checkout links are workspace references; the upstream repository and package identities remain authoritative when browsing this backend repository alone. Recheck upstream contracts before implementation rather than treating this investigation date as a pinned dependency.
