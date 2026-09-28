# UniGraph event consumption contract

Status: subscriber, durable inbox and plant-scoped browser notification stream implemented; live broker recovery acceptance pending.

| Setting | Value |
|---|---|
| Exchange | unigraph.events |
| Exchange type | topic, durable |
| Producer routing | unigraph.graph.updated.{unigraph_project_id} |
| Consumer binding | unigraph.graph.updated.* |
| Consumer queue | equipment-isolation.planning-input-events.v1 |
| Queue lifetime | durable, non-exclusive, not auto-deleted |
| Encoding | JSON, persistent delivery_mode=2 |

Use explicitly configured EIA_UNIGRAPH_EVENTS_BROKER_URL, never an implicit production default. The worker is a separate process, not one subscriber per FastAPI worker. Multiple worker instances may compete safely on the same queue. Local/manual vhost is unigraph_dev; automated tests must use their isolated vhost/resources.

## Dispatch

| event_type | Effect |
|---|---|
| unigraph.planning_document.revision.validated | Record receipt; refresh availability notices only. |
| unigraph.planning_document.revision.rejected | Record receipt; refresh availability notices only. |
| unigraph.planning_document.current_changed | Apply newer approved head and invalidate mismatching dependencies. |
| unigraph.planning_document.revision.withdrawn | Apply newer null head and invalidate affected dependencies. |
| unigraph.graph.version.published | Recognize as a distinct graph event; do not treat as a document change. Graph invalidation integration is separate follow-on scope. |

Required common fields: event_id, event_type, event_version=1, unigraph_project_id, cnvrt_project_id, document_id, document_type, change_id and updated_at. For head changes additionally validate generation, current_revision_id, previous_revision_id and decision_id. Revision/hash fields are present when applicable; withdrawal may have no current revision. Use source-qualified IDs; never trust the routing key as sufficient type or plant evidence.

Persist receipt, observed head and invalidation/audit effects transactionally; acknowledge after commit. Duplicate deliveries are acknowledged without duplicate effects. Fan-out event IDs differ by destination; change_id is shared. Same-generation conflicting heads are quarantined and flagged for HTTP reconciliation. Older generations cannot restore freshness. Newer generations with identical content still change the approved basis and require rerun.

On transient storage/connection failure retain messages for retry with bounded backoff; malformed/unsupported payloads enter a durable quarantine with bounded diagnostic metadata and no credentials. Unknown event types have no plan effects and remain observable. Do not invent graph versions for document actions.

An exchange is not a replay log. Durable queue setup must precede reliance on events. Startup/reconnect drains retained messages, while authenticated HTTP reconciliation repairs gaps from before subscription. Publisher confirmation alone does not prove consumer processing.
