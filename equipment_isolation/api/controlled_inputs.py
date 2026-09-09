"""Internal controlled-input repository. No public approval/admission endpoints.

Callers must establish decision authority before calling decide_revision. Imported
payload approval strings are never trusted. Sessions may be composed by a future
admission service through lock_manifest_in_session; no worker is dispatched here.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from equipment_isolation.api.db_models import (
    ControlledInput, ControlledInputRevision, ExternalRunLink, IsolationRun,
    PlanVersionInvalidation, RunInputManifest, RunInputManifestItem,
)
from equipment_isolation.domain.controlled_inputs import (
    CANONICAL_VERSION, ControlledInputError, content_hash, prepare_content,
    scope_for, utc_timestamp, validate_approval,
)

MISSING_FOUNDATION_SOURCES = ["graph_snapshot", "psd_snapshot", "rule_engine_build", "structured_work_scope"]


def _uuid(value) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ControlledInputError("invalid_id", "Expected a UUID") from exc


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ControlledInputError("invalid_content", f"{name} is required")
    return value.strip()


def _projection(row) -> dict:
    result = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, UUID):
            value = str(value)
        elif isinstance(value, datetime):
            value = utc_timestamp(value)
        result[column.name] = deepcopy(value)
    return result


def _revision(row, document) -> dict:
    return {**_projection(row), "input_type": document.input_type,
            "scope": {key: getattr(document, key) for key in ("cnvrt_project_id", "collection_id", "job_id")}}


def _decision_snapshot(row):
    return {"decision": row.decision, "decided_by": row.decided_by,
            "decided_at": utc_timestamp(row.decided_at), "decision_reason": row.decision_reason}


class ControlledInputRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def create_document(self, input_type: str, context: dict, document_key: str, actor_id: str) -> dict:
        scope = scope_for(input_type, context)
        try:
            with self._session_factory.begin() as session:
                document = ControlledInput(input_type=input_type, **scope,
                    document_key=_text(document_key, "document_key"), created_by=_text(actor_id, "actor_id"))
                session.add(document)
                session.flush()
                return _projection(document)
        except IntegrityError as exc:
            raise ControlledInputError("document_conflict", "A document already owns this exact type/scope") from exc

    def submit_revision(self, input_id, revision_label: str, schema_version: str, payload: dict, actor_id: str) -> dict:
        try:
            with self._session_factory.begin() as session:
                document = session.get(ControlledInput, _uuid(input_id))
                if document is None:
                    raise ControlledInputError("input_missing", "Unknown document")
                canonical, validation = prepare_content(document.input_type, schema_version, payload)
                label = _text(revision_label, "revision_label")
                if document.input_type == "fhr" and validation["status"] == "valid" and canonical["document"]["revision"] != label:
                    raise ControlledInputError("revision_mismatch", "FHR document and submission revisions must agree")
                if document.input_type == "sic" and validation["status"] == "draft_validated":
                    if canonical["revision_label"] != label or canonical["context"] != {
                        "cnvrt_project_id": document.cnvrt_project_id, "collection_id": document.collection_id,
                    }:
                        raise ControlledInputError("revision_mismatch", "SIC draft revision and scope must match its registry document")
                revision = ControlledInputRevision(input_id=document.input_id, revision_label=label,
                    schema_version=_text(schema_version, "schema_version"), canonical_version=CANONICAL_VERSION,
                    payload=canonical, content_hash=content_hash(canonical), validation=validation,
                    submitted_by=_text(actor_id, "actor_id"), decision="pending")
                session.add(revision)
                session.flush()
                return _revision(revision, document)
        except IntegrityError as exc:
            raise ControlledInputError("revision_conflict", "Revision label already exists") from exc

    def decide_revision(self, revision_id, decision: str, actor_id: str, reason: str, *, expected_head) -> dict:
        """Trusted service operation; authority must be checked by the caller.

        expected_head=None explicitly means no approved head. Exact terminal retries
        do not re-promote an old revision after another approval supersedes it.
        """
        actor_id, reason = _text(actor_id, "actor_id"), _text(reason, "reason")
        if decision not in {"approved", "rejected"}:
            raise ControlledInputError("invalid_decision", "Expected approved or rejected")
        expected = _uuid(expected_head) if expected_head is not None else None
        with self._session_factory.begin() as session:
            revision = session.get(ControlledInputRevision, _uuid(revision_id))
            if revision is None:
                raise ControlledInputError("revision_missing", "Unknown revision")
            document = session.scalar(select(ControlledInput).where(ControlledInput.input_id == revision.input_id).with_for_update())
            # Refresh after acquiring the document lock: another decision may have committed.
            session.refresh(revision)
            if revision.decision != "pending":
                if (revision.decision, revision.decided_by, revision.decision_reason) == (decision, actor_id, reason):
                    return _revision(revision, document)
                raise ControlledInputError("decision_conflict", "Revision already has a terminal decision")
            if document.approved_revision_id != expected:
                raise ControlledInputError("head_changed", "Approved revision changed; review the current head")
            if decision == "approved":
                validate_approval(document.input_type, revision.schema_version, revision.payload)
                if content_hash(revision.payload) != revision.content_hash:
                    raise ControlledInputError("hash_mismatch", "Stored content hash mismatch")
            now = datetime.now(timezone.utc)
            if document.approved_revision_id is not None:
                previous = session.get(ControlledInputRevision, document.approved_revision_id)
                now = max(now, previous.decided_at + timedelta(microseconds=1))
            revision.decision, revision.decided_by = decision, actor_id
            revision.decided_at, revision.decision_reason = now, reason
            session.flush()
            if decision == "approved":
                document.approved_revision_id = revision.revision_id
                # DB trigger creates existing-plan invalidations in this transaction.
                session.flush()
            return _revision(revision, document)

    def get_revision(self, revision_id) -> dict | None:
        with self._session_factory() as session:
            revision = session.get(ControlledInputRevision, _uuid(revision_id))
            if revision is None:
                return None
            return _revision(revision, session.get(ControlledInput, revision.input_id))

    def get_approved_head(self, input_type: str, context: dict) -> dict | None:
        scope = scope_for(input_type, context)
        with self._session_factory() as session:
            document = session.scalar(select(ControlledInput).filter_by(input_type=input_type, **scope))
            if document is None or document.approved_revision_id is None:
                return None
            return _revision(session.get(ControlledInputRevision, document.approved_revision_id), document)

    def lock_manifest(self, run_id: str, expected_revisions: dict[str, str], *, plan_time: datetime) -> dict:
        with self._session_factory.begin() as session:
            return self.lock_manifest_in_session(session, run_id, expected_revisions, plan_time=plan_time)

    def lock_manifest_in_session(self, session, run_id: str, expected_revisions: dict[str, str], *, plan_time: datetime) -> dict:
        """Foundation pins only, composed into a caller transaction if needed.

        The canonical request is taken from persisted run state, not client input.
        This operation deliberately cannot certify complete runtime admission.
        """
        utc_timestamp(plan_time)
        if not isinstance(expected_revisions, dict) or not expected_revisions or set(expected_revisions) - {"fhr", "sic"}:
            raise ControlledInputError("invalid_slots", "Supply explicit expected fhr/sic revision IDs")
        expected = {key: _uuid(value) for key, value in expected_revisions.items()}
        run = session.scalar(select(IsolationRun).where(IsolationRun.run_id == run_id).with_for_update())
        if run is None:
            raise ControlledInputError("run_missing", "Unknown persisted run")
        existing = session.scalar(select(RunInputManifest).where(RunInputManifest.run_id == run_id))
        if existing is not None:
            projection = self._manifest(session, existing)
            if {row["input_type"]: _uuid(row["revision_id"]) for row in projection["items"]} == expected and utc_timestamp(existing.plan_time) == utc_timestamp(plan_time):
                return projection
            raise ControlledInputError("manifest_conflict", "Run already has a different locked manifest")
        if run.status != "queued" or run.started_at is not None:
            raise ControlledInputError("run_already_started", "Cannot retrospectively pin execution inputs")
        context = scope_for("fhr", run.request or {})
        document_ids = []
        for kind, revision_id in expected.items():
            revision = session.get(ControlledInputRevision, revision_id)
            if revision is None:
                raise ControlledInputError("revision_missing", "Unknown expected revision")
            document_ids.append(revision.input_id)
        documents = {doc.input_id: doc for doc in session.scalars(select(ControlledInput).where(ControlledInput.input_id.in_(document_ids)).order_by(ControlledInput.input_id).with_for_update()).all()}
        items = []
        for kind, revision_id in sorted(expected.items()):
            revision = session.get(ControlledInputRevision, revision_id)
            session.refresh(revision)
            document = documents[revision.input_id]
            if document.input_type != kind or any(getattr(document, key) != value for key, value in scope_for(kind, context).items()):
                raise ControlledInputError("scope_mismatch", "Expected revision belongs to a different type/scope")
            if revision.decision != "approved":
                raise ControlledInputError("input_unapproved", "Expected revision is not approved")
            if document.approved_revision_id != revision_id:
                raise ControlledInputError("head_changed", "Expected revision is no longer current")
            validate_approval(kind, revision.schema_version, revision.payload)
            if content_hash(revision.payload) != revision.content_hash:
                raise ControlledInputError("hash_mismatch", "Stored content hash mismatch")
            items.append(dict(input_type=kind, role="source", input_id=document.input_id, revision_id=revision_id,
                content_hash=revision.content_hash, schema_version=revision.schema_version, approval_snapshot=_decision_snapshot(revision)))
        # Hash current stored context, including server-owned defect/feedback snapshots.
        request = deepcopy(run.request)
        missing = sorted(MISSING_FOUNDATION_SOURCES + [kind for kind in ("fhr", "sic") if kind not in expected])
        hash_items = [{key: str(value) if isinstance(value, UUID) else value for key, value in item.items()} for item in items]
        envelope = dict(schema_version="run-input-manifest-v1", canonical_version=CANONICAL_VERSION,
            mode="foundation", context=context, semantic_request=request, request_hash=content_hash(request),
            plan_time=utc_timestamp(plan_time), completeness="incomplete", missing_sources=missing, items=hash_items)
        manifest = RunInputManifest(**{key: value for key, value in envelope.items() if key not in {"items", "plan_time"}},
            run_id=run_id, plan_time=plan_time, manifest_hash=content_hash(envelope))
        session.add(manifest)
        session.flush()
        for item in items:
            session.add(RunInputManifestItem(manifest_id=manifest.manifest_id, **item))
        session.flush()
        manifest.locked_at = datetime.now(timezone.utc)
        session.flush()
        return self._manifest(session, manifest)

    def _manifest(self, session, manifest):
        items = session.scalars(select(RunInputManifestItem).where(RunInputManifestItem.manifest_id == manifest.manifest_id).order_by(RunInputManifestItem.input_type, RunInputManifestItem.role)).all()
        return {**_projection(manifest), "items": [_projection(item) for item in items]}

    def get_manifest(self, run_id: str) -> dict | None:
        with self._session_factory() as session:
            manifest = session.scalar(select(RunInputManifest).where(RunInputManifest.run_id == run_id))
            return self._manifest(session, manifest) if manifest is not None else None

    def list_invalidations(self, plan_version_id) -> list[dict]:
        with self._session_factory() as session:
            return [_projection(row) for row in session.scalars(select(PlanVersionInvalidation).where(
                PlanVersionInvalidation.plan_version_id == _uuid(plan_version_id)).order_by(
                PlanVersionInvalidation.recorded_at, PlanVersionInvalidation.replacement_revision_id)).all()]

    def freshness(self, plan_version_ids: list) -> dict:
        """Batched read-through check; no changes to legacy HTTP freshness contracts.

        Missing/incomplete manifests remain incomplete; superseded pins are stale
        even if a future import omitted append-only invalidation evidence.
        """
        ids = [_uuid(value) for value in plan_version_ids]
        result = {str(value): {"status": "historical_unknown", "superseded_inputs": []} for value in ids}
        if not ids:
            return result
        with self._session_factory() as session:
            rows = session.execute(select(ExternalRunLink.plan_version_id, RunInputManifestItem, ControlledInput.approved_revision_id)
                .join(RunInputManifest, RunInputManifest.run_id == ExternalRunLink.run_id)
                .join(RunInputManifestItem, RunInputManifestItem.manifest_id == RunInputManifest.manifest_id)
                .join(ControlledInput, ControlledInput.input_id == RunInputManifestItem.input_id)
                .where(ExternalRunLink.plan_version_id.in_(ids), ExternalRunLink.link_role == "derivation")
                .order_by(ExternalRunLink.plan_version_id, RunInputManifestItem.input_type, RunInputManifestItem.role)).all()
            for version_id, item, head in rows:
                entry = result[str(version_id)]
                if entry["status"] == "historical_unknown":
                    entry["status"] = "incomplete"
                if item.revision_id != head:
                    entry["status"] = "stale"
                    entry["superseded_inputs"].append({"input_id": str(item.input_id), "input_type": item.input_type,
                        "consumed_revision_id": str(item.revision_id), "current_revision_id": str(head) if head else None})
        return result
