"""SSE event formatting for compact agent progress updates."""
from __future__ import annotations

import json
import time
from typing import Any


SUMMARY_KEYS = (
    "assurance_status",
    "total_candidates",
    "bbox_resolved_count",
    "barrier_count",
    "positive_count",
    "verification_count",
    "missing_boundary_count",
    "isolation_points_count",
    "warning_count",
    "error",
    "matched_equipment_count",
    "traversal_limit_hit",
    "job_resolution",
    "job_resolution_error",
    "fatal",
)


def compact_event(kind: str, payload: Any) -> dict:
    if kind == "tool_result" and isinstance(payload, dict):
        result = payload.get("result") or {}
        payload = {
            "name": payload.get("name"),
            "result": {key: result[key] for key in SUMMARY_KEYS if key in result},
        }
    elif kind == "model_text":
        payload = {"text": str(payload).strip().replace("\n", " ")[:240]}
    return {"kind": kind, "payload": payload}


def sse_frame(event: str, data: dict, *, event_id: str = "") -> str:
    id_line = f"id: {event_id}\n" if event_id else ""
    return f"{id_line}event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def asset_condition_event_stream(
    repository,
    context: dict[str, str],
    *,
    last_event_id: str = "",
    poll_interval: float = 1.0,
    heartbeat_interval: float = 15.0,
):
    """Stream durable scoped asset-condition invalidation events from PostgreSQL."""

    requested_cursor = str(last_event_id or "").strip()
    if hasattr(repository, "asset_condition_event_replay_state"):
        replay = repository.asset_condition_event_replay_state(
            context, requested_cursor
        )
        cursor = str(replay.get("cursor_id") or "")
        cursor_occurred_at = replay.get("cursor_occurred_at")
        seen_ids = set(replay.get("seen_ids") or set())
    else:
        cursor = requested_cursor or repository.latest_asset_condition_event_id(context)
        cursor_occurred_at = None
        seen_ids = {cursor} if cursor else set()
    yield sse_frame(
        "ready",
        {"kind": "ready", "context": context, "last_event_id": cursor or None},
    )
    last_output = time.monotonic()
    while True:
        rows = repository.list_asset_condition_events(
            context,
            after_id=cursor,
            exclude_ids=seen_ids,
        )
        for row in rows:
            event_id = str(row["event_id"])
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)
            occurred_at = row.get("occurred_at")
            if cursor_occurred_at is None or (
                occurred_at is not None and occurred_at >= cursor_occurred_at
            ):
                cursor = event_id
                cursor_occurred_at = occurred_at
            yield sse_frame(
                "asset_condition.changed",
                row,
                event_id=event_id,
            )
            last_output = time.monotonic()
        if time.monotonic() - last_output >= heartbeat_interval:
            yield ": heartbeat\n\n"
            last_output = time.monotonic()
        time.sleep(poll_interval)
