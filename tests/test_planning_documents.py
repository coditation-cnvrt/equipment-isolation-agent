from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest import mock

import httpx

from equipment_isolation.api.db import PostgresRunRepository, _validated_planning_document_event
from equipment_isolation.api.events import planning_document_event_stream
from equipment_isolation.api.plans import PlanDomainError
from equipment_isolation.integrations.planning_document_events import (
    EXCHANGE_NAME,
    ROUTING_PATTERN,
    PlanningDocumentEventWorker,
)
from equipment_isolation.integrations.planning_documents import (
    PlanningDocumentError,
    UniGraphPlanningDocumentClient,
    adapt_process_safety_inputs,
    canonical_hash,
    planning_document_summary,
    planning_input_diff,
)
from tests.planning_document_fixtures import CONTEXT, WORK_SCOPE, approved_manifest


def _upstream_bundle(manifest: dict) -> dict:
    registers = []
    for document in manifest["documents"].values():
        revision = {
            key: deepcopy(document[key])
            for key in (
                "revision_id", "register_id", "revision_number", "schema_version",
                "source_content_hash", "content_hash", "original_filename", "normalized_content",
            )
        }
        revision["id"] = revision.pop("revision_id")
        revision.update(status="valid", validation_errors=[])
        registers.append({
            "id": document["register_id"],
            "cnvrt_project_id": int(manifest["cnvrt_project_id"]),
            "document_type": document["document_type"],
            "current_revision_id": document["revision_id"],
            "generation": document["generation"],
            "current_revision": revision,
        })
    return {
        "cnvrt_project_id": int(manifest["cnvrt_project_id"]),
        "entry_project_id": int(manifest["entry_unigraph_project_id"]),
        "registers": registers,
    }


def _details(manifest: dict) -> dict[int, dict]:
    return {
        document["revision_id"]: {
            "id": document["revision_id"],
            "register_id": document["register_id"],
            "content_hash": document["content_hash"],
            "decisions": [deepcopy(document["approval"])],
        }
        for document in manifest["documents"].values()
    }


class PlanningDocumentHeadTests(unittest.TestCase):
    def test_http_head_older_than_observed_event_is_rejected(self):
        session = mock.MagicMock()
        session.scalar.return_value = SimpleNamespace(generation=2)
        transaction = mock.MagicMock()
        transaction.__enter__.return_value = session
        repository = object.__new__(PostgresRunRepository)
        repository._session_factory = mock.MagicMock()
        repository._session_factory.begin.return_value = transaction

        with self.assertRaises(PlanDomainError) as caught:
            repository.observe_planning_document_set(
                planning_document_summary(approved_manifest(generation=1))
            )

        self.assertEqual(caught.exception.kind, "planning_document_head_stale")
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(caught.exception.context["returned_generation"], 1)
        self.assertEqual(caught.exception.context["observed_generation"], 2)


class PlanningDocumentClientTests(unittest.TestCase):
    def setUp(self):
        self.manifest = approved_manifest()
        self.bundle = _upstream_bundle(self.manifest)
        self.details = _details(self.manifest)
        self.client = UniGraphPlanningDocumentClient(
            "user-token", base_url="http://unigraph.example/plantgraph"
        )

    def _read(self, path: str) -> dict:
        if path.endswith("/planning-documents"):
            return deepcopy(self.bundle)
        revision_id = int(path.rsplit("/", 1)[-1])
        return deepcopy(self.details[revision_id])

    def test_reads_atomic_bundle_and_verified_approval_evidence(self):
        with mock.patch.object(self.client, "_get", side_effect=self._read) as read:
            result = self.client.approved_bundle(unigraph_project_id="21", cnvrt_project_id="277")

        self.assertEqual(read.call_count, 5)
        self.assertEqual(result["document_set_token"], self.manifest["document_set_token"])
        self.assertEqual(set(result["documents"]), {"fhr", "sic", "psd"})
        self.assertEqual(result["documents"]["fhr"]["approval"]["actor_name"], "Operations Reviewer")

    def test_http_read_forwards_bearer_and_uses_bounded_timeout(self):
        response = mock.Mock(status_code=200)
        response.json.return_value = {"ok": True}
        with mock.patch("equipment_isolation.integrations.planning_documents.httpx.get", return_value=response) as get:
            self.assertEqual(self.client._get("/probe"), {"ok": True})
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer user-token"})
        self.assertEqual(get.call_args.kwargs["timeout"], 15.0)

    def test_missing_or_mismatched_plant_documents_fail_closed(self):
        for mutation, code in (
            (lambda value: value.update(cnvrt_project_id=999), "planning_document_scope_mismatch"),
            (lambda value: value["registers"].pop(), "planning_documents_missing"),
        ):
            bundle = deepcopy(self.bundle)
            mutation(bundle)
            with self.subTest(code=code), mock.patch.object(self.client, "_get", return_value=bundle):
                with self.assertRaises(PlanningDocumentError) as caught:
                    self.client.approved_bundle(unigraph_project_id="21", cnvrt_project_id="277")
                self.assertEqual(caught.exception.code, code)

    def test_schema_hash_and_approval_generation_are_verified(self):
        cases = (
            ("schema", "planning_document_schema_incompatible"),
            ("hash", "planning_document_hash_mismatch"),
            ("approval", "planning_document_approval_missing"),
        )
        for case, code in cases:
            bundle = deepcopy(self.bundle)
            details = deepcopy(self.details)
            fhr = next(row for row in bundle["registers"] if row["document_type"] == "fhr")
            if case == "schema":
                fhr["current_revision"]["schema_version"] = "planning-documents-v2"
            elif case == "hash":
                fhr["current_revision"]["content_hash"] = "0" * 64
            else:
                details[fhr["current_revision_id"]]["decisions"][0]["resulting_generation"] += 1

            def read(path: str):
                if path.endswith("/planning-documents"):
                    return deepcopy(bundle)
                return deepcopy(details[int(path.rsplit("/", 1)[-1])])

            with self.subTest(case=case), mock.patch.object(self.client, "_get", side_effect=read):
                with self.assertRaises(PlanningDocumentError) as caught:
                    self.client.approved_bundle(unigraph_project_id="21", cnvrt_project_id="277")
                self.assertEqual(caught.exception.code, code)

    def test_bundle_detail_race_retries_once_then_fails(self):
        details = deepcopy(self.details)
        details[self.manifest["documents"]["fhr"]["revision_id"]]["content_hash"] = "f" * 64

        def read(path: str):
            if path.endswith("/planning-documents"):
                return deepcopy(self.bundle)
            return deepcopy(details[int(path.rsplit("/", 1)[-1])])

        with mock.patch.object(self.client, "_get", side_effect=read) as request:
            with self.assertRaises(PlanningDocumentError) as caught:
                self.client.approved_bundle(unigraph_project_id="21", cnvrt_project_id="277")
        self.assertEqual(caught.exception.code, "planning_document_read_race")
        self.assertEqual(request.call_count, 4)

    def test_transport_failure_does_not_become_an_empty_bundle(self):
        request = httpx.Request("GET", "http://unigraph.example/plantgraph/probe")
        with mock.patch(
            "equipment_isolation.integrations.planning_documents.httpx.get",
            side_effect=httpx.ConnectError("unavailable", request=request),
        ):
            with self.assertRaises(PlanningDocumentError) as caught:
                self.client._get("/probe")
        self.assertEqual(caught.exception.code, "planning_document_service_unavailable")
        self.assertEqual(caught.exception.status_code, 503)


class PlanningDocumentAdapterTests(unittest.TestCase):
    def test_adapter_preserves_source_null_zero_false_and_repository_evidence(self):
        manifest = approved_manifest()
        fluid = manifest["documents"]["fhr"]["normalized_content"]["fluids"][0]
        fluid.update(
            approved_by=None,
            approved_date=None,
            h2s_content_ppm=0.0,
            flash_point_c=None,
            is_asphyxiant=False,
        )
        manifest["documents"]["fhr"]["content_hash"] = canonical_hash(
            manifest["documents"]["fhr"]["normalized_content"]
        )
        inputs = adapt_process_safety_inputs(
            manifest,
            context=CONTEXT,
            work_scope=WORK_SCOPE,
            plan_time="2026-09-17T08:00:00+00:00",
            unit_scope="Unit 21",
        )
        adapted = inputs["fhr"]["fluids"][0]
        self.assertIsNone(adapted["approved_by"])
        self.assertIsNone(adapted["approved_date"])
        self.assertEqual(adapted["h2s_content_ppm"], 0.0)
        self.assertIsNone(adapted["flash_point_c"])
        self.assertFalse(adapted["is_asphyxiant"])
        self.assertEqual(inputs["fhr"]["document"]["approved_by"], "Operations Reviewer")
        self.assertEqual(inputs["unit_scope"], "Unit 21")

    def test_psd_missing_expiry_is_bounded_by_sic_and_record_ids_are_retained(self):
        manifest = approved_manifest()
        psd = manifest["documents"]["psd"]["normalized_content"]
        psd["header"]["valid_until"] = None
        expected = datetime.fromisoformat(psd["header"]["declared_at"].replace("Z", "+00:00"))
        manifest["documents"]["psd"]["content_hash"] = canonical_hash(psd)
        inputs = adapt_process_safety_inputs(
            manifest,
            context=CONTEXT,
            work_scope=WORK_SCOPE,
            plan_time="2026-09-17T08:00:00+00:00",
            unit_scope="Unit 21",
        )
        validity_hours = inputs["sic"]["parameters"]["plant_state"]["validity_hours"]
        actual = datetime.fromisoformat(inputs["psd"]["header"]["valid_until"].replace("Z", "+00:00"))
        self.assertEqual((actual - expected).total_seconds(), validity_hours * 3600)
        annotations = inputs["psd"]["source_provenance"]["row_annotations"]
        for section, source_rows in psd.items():
            if section not in annotations:
                continue
            for source in source_rows:
                self.assertTrue(any(row.get("record_id") == source["record_id"] for row in annotations[section].values()))

    def test_structured_diff_reports_exact_paths_and_bounds_output(self):
        captured_manifest = approved_manifest()
        current_manifest = deepcopy(captured_manifest)
        current_fhr = current_manifest["documents"]["fhr"]
        current_fhr["normalized_content"]["fluids"][0]["nfpa_health"] = 4
        current_fhr["normalized_content"]["fluids"][0]["is_corrosive"] = False
        current_fhr["revision_id"] += 10
        current_fhr["generation"] += 1
        current_fhr["content_hash"] = canonical_hash(current_fhr["normalized_content"])
        captured = [
            {
                key: deepcopy(document[key])
                for key in (
                    "source_id", "cnvrt_project_id", "entry_unigraph_project_id", "document_type",
                    "register_id", "revision_id", "revision_number", "generation", "schema_version",
                    "content_hash", "normalized_content",
                )
            }
            for document in captured_manifest["documents"].values()
        ]
        for item in captured:
            item["source_snapshot"] = item.pop("normalized_content")
        result = planning_input_diff(captured, current_manifest, limit_per_document=1)
        fhr = next(item for item in result if item["document_type"] == "fhr")
        self.assertEqual(fhr["status"], "changed")
        self.assertTrue(fhr["truncated"])
        self.assertEqual(len(fhr["changes"]), 1)
        self.assertTrue(fhr["changes"][0]["path"].startswith("/fluids/fluid_code=CDH/"))
        self.assertEqual(fhr["changes"][0]["significance"], "potentially_safety_significant")
        self.assertTrue(all(item["status"] == "current" for item in result if item["document_type"] != "fhr"))


def _event(**overrides) -> dict:
    value = {
        "event_id": "unigraph-document-1-decision-8-generation-2-project-21",
        "change_id": "unigraph-document-1-decision-8-generation-2",
        "event_type": "unigraph.planning_document.current_changed",
        "event_version": 1,
        "unigraph_project_id": 21,
        "cnvrt_project_id": 277,
        "document_id": 1,
        "document_type": "fhr",
        "revision_id": 12,
        "current_revision_id": 12,
        "previous_revision_id": 11,
        "content_hash": "a" * 64,
        "generation": 2,
        "decision_id": 8,
        "reason": "Approved",
        "updated_at": "2026-09-17T08:57:46+00:00",
    }
    value.update(overrides)
    return value


class PlanningDocumentEventTests(unittest.TestCase):
    def test_current_and_withdrawal_events_validate_without_graph_version_fields(self):
        current = _validated_planning_document_event(_event(), source_id="http://unigraph/")
        self.assertEqual(current["source_id"], "http://unigraph")
        self.assertEqual(current["generation"], 2)
        self.assertNotIn("graph_version", current)
        withdrawn = _validated_planning_document_event(
            _event(
                event_type="unigraph.planning_document.revision.withdrawn",
                current_revision_id=None,
                content_hash=None,
            ),
            source_id="http://unigraph",
        )
        self.assertIsNone(withdrawn["current_revision_id"])

    def test_graph_and_non_head_document_events_have_no_head_requirements(self):
        for event_type in (
            "unigraph.graph.version.published",
            "unigraph.planning_document.revision.validated",
            "unigraph.planning_document.revision.rejected",
        ):
            result = _validated_planning_document_event(
                {"event_id": f"event-{event_type}", "event_type": event_type, "event_version": 1},
                source_id="http://unigraph",
            )
            self.assertEqual(result["event_type"], event_type)

    def test_malformed_head_events_are_quarantine_candidates(self):
        for payload in (
            _event(decision_id=None),
            _event(updated_at="2026-09-17T08:57:46"),
            _event(document_type="hazmat"),
            _event(event_version=2),
            _event(event_type="unigraph.planning_document.revision.withdrawn"),
        ):
            with self.subTest(payload=payload), self.assertRaises(PlanDomainError) as caught:
                _validated_planning_document_event(payload, source_id="http://unigraph")
            self.assertEqual(caught.exception.kind, "planning_document_event_invalid")

    def test_worker_declares_durable_shared_transport_and_acks_only_after_persistence(self):
        repository = mock.Mock()
        repository.apply_planning_document_event.return_value = {
            "event_id": "event-1", "status": "processed", "duplicate": False
        }
        worker = PlanningDocumentEventWorker(
            mock.Mock(), repository,
            source_id="http://unigraph/", queue_name="equipment-isolation.test",
        )
        self.assertEqual(worker.queue.exchange.name, EXCHANGE_NAME)
        self.assertEqual(worker.queue.exchange.type, "topic")
        self.assertTrue(worker.queue.exchange.durable)
        self.assertEqual(worker.queue.routing_key, ROUTING_PATTERN)
        self.assertTrue(worker.queue.durable)
        self.assertFalse(worker.queue.exclusive)
        self.assertFalse(worker.queue.auto_delete)

        message = mock.Mock()
        worker.on_message(_event(), message)
        repository.apply_planning_document_event.assert_called_once()
        message.ack.assert_called_once_with()
        message.reject.assert_not_called()

        repository.apply_planning_document_event.side_effect = RuntimeError("database unavailable")
        failed = mock.Mock()
        worker.on_message(_event(event_id="event-2"), failed)
        failed.ack.assert_not_called()
        failed.reject.assert_called_once_with(requeue=True)

    def test_sse_stream_starts_at_committed_plant_cursor_and_emits_new_change(self):
        repository = mock.Mock()
        repository.planning_document_event_replay_state.return_value = {
            "cursor_id": "event-1",
            "cursor_received_at": datetime.fromisoformat("2026-09-17T08:57:46+00:00"),
            "seen_ids": {"event-1"},
        }
        repository.list_planning_document_events.return_value = [
            {
                **_event(event_id="event-2", generation=3),
                "received_at": datetime.fromisoformat("2026-09-17T09:00:00+00:00"),
            }
        ]
        stream = planning_document_event_stream(
            repository,
            "277",
            last_event_id="event-1",
            poll_interval=0,
        )

        ready = next(stream)
        changed = next(stream)

        self.assertIn("event: ready", ready)
        self.assertIn('"last_event_id": "event-1"', ready)
        self.assertIn("event: planning_document.changed", changed)
        self.assertIn("id: event-2", changed)
        repository.planning_document_event_replay_state.assert_called_once_with(
            "277", "event-1"
        )
        repository.list_planning_document_events.assert_called_once_with(
            "277", after_id="event-1", exclude_ids={"event-1"}
        )


if __name__ == "__main__":
    unittest.main()
