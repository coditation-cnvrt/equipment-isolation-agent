"""In-process run execution with PostgreSQL as the authoritative store."""
from __future__ import annotations

import logging
import queue
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from equipment_isolation.agent.session import jsonable
from equipment_isolation.api.events import compact_event, sse_frame
from equipment_isolation.api.service import execute_agent_request

LOGGER = logging.getLogger(__name__)
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def is_valid_run_id(run_id: str) -> bool:
    return bool(RUN_ID_PATTERN.fullmatch(str(run_id or "")))


class _DaemonWorkerPool:
    def __init__(self, max_workers: int):
        self._tasks: queue.Queue = queue.Queue()
        self._shutdown = False
        self._lock = threading.Lock()
        self._workers = []
        for index in range(max(1, int(max_workers or 1))):
            thread = threading.Thread(target=self._work, name=f"isolation-run-worker-{index + 1}", daemon=True)
            thread.start()
            self._workers.append(thread)

    def submit(self, callback, *args, **kwargs) -> None:
        with self._lock:
            if self._shutdown:
                raise RuntimeError("run worker pool is shut down")
            self._tasks.put((callback, args, kwargs))

    def shutdown(self, *, wait: bool = False, cancel_futures: bool = True) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            if cancel_futures:
                self._drain_pending_tasks()
            for _thread in self._workers:
                self._tasks.put(None)
        if wait:
            for thread in self._workers:
                thread.join()

    def _drain_pending_tasks(self) -> None:
        while True:
            try:
                self._tasks.get_nowait()
            except queue.Empty:
                return
            else:
                self._tasks.task_done()

    def _work(self) -> None:
        while True:
            task = self._tasks.get()
            try:
                if task is None:
                    return
                callback, args, kwargs = task
                callback(*args, **kwargs)
            except Exception:
                LOGGER.exception("Run worker task failed")
            finally:
                self._tasks.task_done()


@dataclass
class RunRecord:
    run_id: str
    equipment_tag: str
    runner: str
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    agent: dict[str, Any] | None = None
    request: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    trace: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    parent_run_id: str | None = None
    derivation_manifest_id: str | None = None
    produced_plan_version_id: str | None = None
    events: queue.Queue = field(default_factory=queue.Queue)


class RunStore:
    def __init__(self, max_workers: int = 2, run_timeout_seconds: int = 900, repository=None):
        self._executor = _DaemonWorkerPool(max_workers=max_workers)
        # PostgreSQL owns run history; this registry coordinates active local workers only.
        self._records: dict[str, RunRecord] = {}
        self._lock = threading.Lock()
        self._closing = False
        self.run_timeout_seconds = run_timeout_seconds
        self.repository = repository

    def create(self, request, auth_token: str, *, parent_run_id: str | None = None) -> RunRecord:
        run_id = uuid.uuid4().hex
        record = RunRecord(
            run_id=run_id,
            equipment_tag=request.equipment_tag,
            runner=request.runner,
            request=_request_payload(request),
            parent_run_id=parent_run_id,
            derivation_manifest_id=str((getattr(request, "derivation_context", {}) or {}).get("manifest_id") or "") or None,
        )
        # Persist before exposing or scheduling the run. PostgreSQL failure must
        # reject run creation rather than producing an untracked local run.
        if self.repository:
            self.repository.insert_run(record, record.request)
        with self._lock:
            self._records[run_id] = record
        try:
            self._executor.submit(self._run, record, request, auth_token)
        except Exception as exc:
            error = _error_detail(exc)
            try:
                self._mark(record, status="failed", finished_at=time.time(), error=error)
            finally:
                self._evict_terminal(record)
            raise
        return record

    def get(self, run_id: str) -> RunRecord | None:
        if not is_valid_run_id(run_id):
            return None
        with self._lock:
            record = self._records.get(run_id)
        if record is not None:
            return record
        if not self.repository:
            return None
        row = self.repository.get_run(run_id)
        return _record_from_row(row) if row else None

    def list(self, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        active_filters = {key: str(value) for key, value in filters.items() if value not in {None, ""}}
        if self.repository:
            rows = self.repository.list_runs(limit=limit, offset=offset, **active_filters)
            return [self.snapshot(_record_from_row(row), include_result=False) for row in rows]
        with self._lock:
            records = list(self._records.values())
        items = [self.snapshot(record) for record in records if _record_matches(record, active_filters)]
        items.sort(key=lambda item: item.get("created_at") or 0, reverse=True)
        return items[offset : offset + limit]

    def shutdown(self) -> None:
        self._interrupt_nonterminal_runs()
        self._executor.shutdown(wait=False, cancel_futures=True)
        close = getattr(self.repository, "close", None)
        if close:
            close()

    def snapshot(self, record: RunRecord, include_result: bool = False) -> dict:
        payload = {
            "run_id": record.run_id,
            "status": record.status,
            "equipment_tag": record.equipment_tag,
            "runner": record.runner,
            "created_at": record.created_at,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "agent": record.agent,
            "request": dict(record.request),
            "error": record.error,
            "parent_run_id": record.parent_run_id,
            "derivation_manifest_id": record.derivation_manifest_id,
            "produced_plan_version_id": record.produced_plan_version_id,
        }
        if include_result:
            payload["result"] = record.result
        return payload

    def _run(self, record: RunRecord, request, auth_token: str) -> None:
        timer: threading.Timer | None = None

        def on_event(kind, payload):
            event = compact_event(kind, jsonable(payload))
            if kind in {"tool_call", "tool_result"} and isinstance(payload, dict):
                self._set_progress(record, kind=kind, tool=str(payload.get("name") or ""))
            self._emit_event(record, event)

        try:
            if self._is_interrupted(record):
                return
            if not self._mark(record, status="running", started_at=time.time()):
                return
            if self.run_timeout_seconds > 0:
                timer = threading.Timer(self.run_timeout_seconds, self._timeout, args=(record,))
                timer.daemon = True
                timer.start()

            outcome = execute_agent_request(
                run_id=record.run_id,
                request=request,
                auth_token=auth_token,
                on_event=on_event,
            )
            if outcome.get("ok"):
                if not self._mark(
                    record,
                    status="succeeded",
                    finished_at=time.time(),
                    result=outcome.get("payload"),
                    agent=outcome.get("agent"),
                    trace=outcome.get("trace"),
                    error=None,
                ):
                    return
            else:
                error = outcome.get("error") or {"kind": "pipeline_error", "message": "Run failed."}
                if not self._mark(
                    record,
                    status="failed",
                    finished_at=time.time(),
                    trace=outcome.get("trace"),
                    error=error,
                ):
                    return
                self._emit_event(record, {"kind": "error", "payload": error})
        except Exception as exc:
            error = _error_detail(exc)
            try:
                if self._mark(record, status="failed", finished_at=time.time(), error=error):
                    self._emit_event(record, {"kind": "error", "payload": error})
            except Exception:
                LOGGER.exception("Failed to persist terminal state for run %s", record.run_id)
        finally:
            if timer:
                timer.cancel()
            record.events.put(None)
            self._evict_terminal(record)

    def _set_progress(self, record: RunRecord, *, kind: str, tool: str) -> None:
        with self._lock:
            if record.status != "running":
                return
            previous = record.agent
            record.agent = {"progress": {"kind": kind, "tool": tool, "updated_at": time.time()}}
            try:
                self._persist(record)
            except Exception:
                record.agent = previous
                raise

    def _mark(self, record: RunRecord, **updates) -> bool:
        with self._lock:
            if record.status in {"succeeded", "failed"}:
                return False
            previous = {key: getattr(record, key) for key in updates}
            for key, value in updates.items():
                setattr(record, key, value)
            try:
                self._persist(record)
            except Exception:
                for key, value in previous.items():
                    setattr(record, key, value)
                raise
        return True

    def _timeout(self, record: RunRecord) -> None:
        error = {
            "kind": "timeout",
            "message": f"Run exceeded timeout of {self.run_timeout_seconds} seconds.",
        }
        if not self._mark(record, status="failed", finished_at=time.time(), error=error):
            return
        self._emit_event(record, {"kind": "error", "payload": error})
        record.events.put(None)
        self._evict_terminal(record)

    def _persist(self, record: RunRecord) -> None:
        if self.repository:
            self.repository.update_run(record)

    def _emit_event(self, record: RunRecord, event: dict) -> None:
        if self.repository:
            self.repository.append_event(record.run_id, event)
        record.events.put(event)

    def _evict_terminal(self, record: RunRecord) -> None:
        """Retain only active runs in memory when PostgreSQL is authoritative."""
        if not self.repository or record.status not in {"succeeded", "failed"}:
            return
        with self._lock:
            if self._records.get(record.run_id) is record:
                self._records.pop(record.run_id, None)

    def _interrupt_nonterminal_runs(self) -> None:
        error = {"kind": "server_shutdown", "message": "API server shut down before this run completed."}
        with self._lock:
            self._closing = True
            records = [record for record in self._records.values() if record.status not in {"succeeded", "failed"}]
        for record in records:
            try:
                if self._mark(record, status="failed", finished_at=time.time(), error=error):
                    self._emit_event(record, {"kind": "error", "payload": error})
                    record.events.put(None)
                    self._evict_terminal(record)
            except Exception:
                LOGGER.exception("Failed to persist shutdown state for run %s", record.run_id)

    def _is_interrupted(self, record: RunRecord) -> bool:
        with self._lock:
            return self._closing and record.status == "failed" and bool(record.error)


def event_stream(record: RunRecord, repository=None):
    last_db_event_id = 0
    while True:
        if repository:
            rows = repository.list_events(record.run_id, after_id=last_db_event_id)
            for row in rows:
                last_db_event_id = row["id"]
                item = row["event"]
                yield sse_frame(str(item.get("kind") or "message"), item)
        if record.status in {"succeeded", "failed"}:
            yield sse_frame("done", {"status": record.status})
            break
        try:
            item = record.events.get(timeout=15)
        except queue.Empty:
            yield ": heartbeat\n\n"
            continue
        if not repository and isinstance(item, dict):
            yield sse_frame(str(item.get("kind") or "message"), item)


def _record_matches(record: RunRecord, filters: dict[str, str]) -> bool:
    for key, expected in filters.items():
        if key == "status":
            actual = record.status
        elif key == "equipment_tag":
            actual = record.equipment_tag
        else:
            actual = record.request.get(key)
        if str(actual or "") != expected:
            return False
    return True


def _error_detail(exc: Exception) -> dict:
    message = str(exc)
    if "Configured project metadata failed" in message:
        kind = "project_metadata"
    elif "Configured CNVRT job resolution failed" in message:
        kind = "job_resolution"
    else:
        kind = "pipeline_error"
    return {"kind": kind, "message": f"{type(exc).__name__}: {message}"}


def _request_payload(request) -> dict:
    return request.model_dump(mode="json", exclude={"auth_token"})


def _record_from_row(row: dict) -> RunRecord:
    return RunRecord(
        run_id=row["run_id"],
        equipment_tag=row["equipment_tag"],
        runner=row["runner"],
        status=row["status"],
        created_at=row["created_at"],
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        agent=row.get("agent"),
        request=row.get("request") or {},
        result=row.get("result"),
        trace=row.get("trace"),
        error=row.get("error"),
        parent_run_id=row.get("parent_run_id"),
        derivation_manifest_id=row.get("derivation_manifest_id"),
        produced_plan_version_id=row.get("produced_plan_version_id"),
    )
