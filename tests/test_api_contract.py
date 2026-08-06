import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException
from pydantic import ValidationError

from api.models import EquipmentListRequest, IsolationRunRequest, RunStatus
from api.routes import (
    create_run,
    equipment,
    health,
    list_runs,
    planning_context_collections,
    planning_context_drawings,
    planning_context_projects,
    planning_context_unigraph_projects,
    run_pid_image,
    run_result,
    run_status,
)
from api.service import (
    list_cnvrt_collections,
    list_cnvrt_drawings,
    list_cnvrt_projects,
    list_unigraph_projects,
)
from api.runs import RunRecord, RunStore, _error_detail


def _payload(tag="P3"):
    return {
        "error": False,
        "message": "Completed",
        "debug": {},
        "data": [
            {
                "selected_equipment": [tag],
                "assurance_status": "provisional_unproven_isolation",
                "isolation_points": [{"uuid": "u1"}],
            }
        ],
    }


class _Result:
    def __init__(self, config, payload=None):
        self.config = config
        self.final_payload = payload if payload is not None else _payload(config.equipment_tag)
        self.agent_result = {
            "steps_used": 3,
            "forced": [],
            "assurance_status": "provisional_unproven_isolation",
            "validate_terminal": True,
        }
        self.trace = [{"tool": "fetch_boundary", "args": {}, "result": {"ok": True}}]
        self.metadata_debug = {"status": "ok"}


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_env = dict(os.environ)
        os.environ["EIA_RUNS_DIR"] = str(Path(self.tmp.name) / "runs")
        os.environ["EIA_MAX_CONCURRENT_RUNS"] = "1"
        os.environ["GEMINI_API_KEY"] = "gemini-key"
        self.store = RunStore(Path(self.tmp.name) / "runs", max_workers=1)
        self.request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(run_store=self.store)))

    def tearDown(self):
        self.store.shutdown()
        os.environ.clear()
        os.environ.update(self.old_env)
        self.tmp.cleanup()

    def _submit(self, body=None, token="plant-token"):
        payload = {
            "equipment_tag": "P3",
            "cnvrt_project_id": "277",
            "collection_id": "206",
            "unigraph_project_id": "15",
            "include_viewer": False,
        }
        if body:
            payload.update(body)
        return create_run(
            self.request,
            IsolationRunRequest(**payload),
            authorization=f"Bearer {token}" if token else "",
        )

    def _read_auth(self, token="plant-token"):
        return f"Bearer {token}"

    def _wait(self, run_id):
        for _ in range(100):
            data = run_status(self.request, run_id, authorization=self._read_auth())
            if data["status"] in {"succeeded", "failed"}:
                return data
            time.sleep(0.01)
        self.fail("run did not finish")

    def test_health_does_not_require_external_services(self):
        self.assertTrue(health()["gemini_api_key_configured"])

    def test_create_run_requires_plant360_token(self):
        os.environ.pop("PLANT360_AUTH_TOKEN", None)
        with self.assertRaises(HTTPException) as caught:
            self._submit(token="")
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(caught.exception.detail["kind"], "missing_auth_token")

    def test_body_auth_token_is_not_accepted(self):
        os.environ.pop("PLANT360_AUTH_TOKEN", None)
        payload = {
            "equipment_tag": "P3",
            "cnvrt_project_id": "277",
            "collection_id": "206",
            "unigraph_project_id": "15",
            "auth_token": "body-secret",
        }
        with self.assertRaises(HTTPException) as caught:
            create_run(self.request, IsolationRunRequest(**payload), authorization="")
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(caught.exception.detail["kind"], "missing_auth_token")

    def test_request_model_requires_equipment_tag(self):
        with self.assertRaises(ValidationError):
            IsolationRunRequest()

    def test_request_model_rejects_blank_equipment_tag(self):
        with self.assertRaises(ValidationError):
            IsolationRunRequest(
                equipment_tag="   ",
                cnvrt_project_id="277",
                collection_id="206",
                unigraph_project_id="15",
            )

    def test_request_model_requires_project_context(self):
        with self.assertRaises(ValidationError):
            IsolationRunRequest(equipment_tag="P3")

    def test_create_run_can_use_server_side_plant360_token(self):
        os.environ["PLANT360_AUTH_TOKEN"] = "server-token"
        with mock.patch("api.service.run_agent_pipeline", side_effect=lambda config, **_: _Result(config)), \
             mock.patch("api.service.resolve_pid_image", return_value=("", {})):
            accepted = self._submit(token="")
            done = self._wait(accepted.run_id)
        self.assertEqual(done["status"], "succeeded")

    def test_create_run_requires_gemini_key(self):
        os.environ.pop("GEMINI_API_KEY", None)
        with self.assertRaises(HTTPException) as caught:
            self._submit()
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.detail["kind"], "missing_gemini_api_key")

    def test_unknown_run_returns_404(self):
        with self.assertRaises(HTTPException) as caught:
            run_status(self.request, "nope", authorization=self._read_auth())
        self.assertEqual(caught.exception.status_code, 404)

    def test_invalid_run_id_cannot_traverse_run_directory(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "status.json").write_text(
            '{"run_id": "../outside", "status": "succeeded", "equipment_tag": "P3", "runner": "agentic", "created_at": 1}',
            encoding="utf-8",
        )

        with self.assertRaises(HTTPException) as caught:
            run_status(self.request, "../outside", authorization=self._read_auth())

        self.assertEqual(caught.exception.status_code, 404)

    def test_run_read_endpoints_require_bearer_auth(self):
        with self.assertRaises(HTTPException) as caught:
            run_status(self.request, "nope")
        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(caught.exception.detail["kind"], "missing_auth_token")

    def test_run_list_requires_bearer_auth(self):
        with self.assertRaises(HTTPException) as caught:
            list_runs(self.request)
        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(caught.exception.detail["kind"], "missing_auth_token")

    def test_equipment_lookup_requires_project_context(self):
        with self.assertRaises(ValidationError):
            EquipmentListRequest()

    def test_equipment_lookup_uses_explicit_project_context(self):
        os.environ["PLANT360_AUTH_TOKEN"] = "server-token"
        with mock.patch("api.routes.list_project_equipment", return_value=[{"tag": "P3"}]):
            response = equipment(
                EquipmentListRequest(
                    cnvrt_project_id="277",
                    collection_id="206",
                    unigraph_project_id="15",
                )
            )
        self.assertEqual(response, {"items": [{"tag": "P3"}]})

    def test_planning_context_projects_forwards_bearer_token(self):
        projects = [{"id": "277", "name": "Aker", "status": "ready"}]
        with mock.patch("api.routes.list_cnvrt_projects", return_value=projects) as project_lookup:
            response = planning_context_projects(authorization=self._read_auth("user-token"))

        self.assertEqual(response, {"items": projects})
        project_lookup.assert_called_once_with("user-token")

    def test_planning_context_projects_requires_plant360_token(self):
        os.environ.pop("PLANT360_AUTH_TOKEN", None)
        with self.assertRaises(HTTPException) as caught:
            planning_context_projects()
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(caught.exception.detail["kind"], "missing_auth_token")

    def test_planning_context_projects_hides_upstream_failure(self):
        with mock.patch("api.routes.list_cnvrt_projects", side_effect=RuntimeError("CNVRT details")):
            with self.assertRaises(HTTPException) as caught:
                planning_context_projects(authorization=self._read_auth())
        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(caught.exception.detail["kind"], "project_discovery_failed")
        self.assertNotIn("CNVRT details", str(caught.exception.detail))

    def test_cnvrt_project_discovery_normalizes_paginated_response(self):
        client = mock.Mock()
        client.get_json.return_value = {
            "count": 2,
            "results": [
                {"id": 277, "name": "Aker", "status": "ready", "description": "ignored"},
                {"id": 278, "name": "Bio", "status": "processing"},
            ],
        }
        with mock.patch("api.service.Plant360Client", return_value=client) as client_class:
            projects = list_cnvrt_projects("user-token")

        self.assertEqual(
            projects,
            [
                {"id": "277", "name": "Aker", "status": "ready"},
                {"id": "278", "name": "Bio", "status": "processing"},
            ],
        )
        self.assertEqual(client_class.call_args.args[0].auth_token, "user-token")
        client.get_json.assert_called_once_with("/projects")

    def test_cnvrt_project_discovery_follows_all_pages(self):
        client = mock.Mock()
        client.get_json.side_effect = [
            {
                "count": 2,
                "next": "https://api.plant360.ai/projects?page=2",
                "results": [{"id": 314, "name": "Newest", "status": "created"}],
            },
            {
                "count": 2,
                "next": None,
                "results": [{"id": 277, "name": "Aker", "status": "created"}],
            },
        ]
        with mock.patch("api.service.Plant360Client", return_value=client):
            projects = list_cnvrt_projects("user-token")

        self.assertEqual([project["id"] for project in projects], ["314", "277"])
        self.assertEqual(client.get_json.call_args_list, [mock.call("/projects"), mock.call("/projects?page=2")])

    def test_planning_context_collections_forwards_project_and_bearer_token(self):
        collections = [{"id": "206", "name": "Unit"}]
        with mock.patch("api.routes.list_cnvrt_collections", return_value=collections) as collection_lookup:
            response = planning_context_collections(277, authorization=self._read_auth("user-token"))

        self.assertEqual(response, {"items": collections})
        collection_lookup.assert_called_once_with(277, "user-token")

    def test_cnvrt_collection_discovery_normalizes_paginated_response(self):
        client = mock.Mock()
        client.get_json.return_value = {
            "count": 2,
            "results": [
                {"id": 206, "name": "Unit", "change_version": 3},
                {"id": 207, "name": "Utilities"},
            ],
        }
        with mock.patch("api.service.Plant360Client", return_value=client):
            collections = list_cnvrt_collections(277, "user-token")

        self.assertEqual(
            collections,
            [
                {"id": "206", "name": "Unit"},
                {"id": "207", "name": "Utilities"},
            ],
        )
        client.get_json.assert_called_once_with("/projects/277/collections")

    def test_cnvrt_collection_discovery_follows_all_pages(self):
        client = mock.Mock()
        client.get_json.side_effect = [
            {
                "next": "https://api.plant360.ai/projects/277/collections?page=2",
                "results": [{"id": 206, "name": "Unit"}],
            },
            {"next": None, "results": [{"id": 207, "name": "Utilities"}]},
        ]
        with mock.patch("api.service.Plant360Client", return_value=client):
            collections = list_cnvrt_collections(277, "user-token")

        self.assertEqual([collection["id"] for collection in collections], ["206", "207"])
        self.assertEqual(
            client.get_json.call_args_list,
            [mock.call("/projects/277/collections"), mock.call("/projects/277/collections?page=2")],
        )

    def test_planning_context_drawings_forwards_context_and_bearer_token(self):
        drawings = [
            {
                "id": "2100",
                "name": "P&ID 2",
                "status": "complete",
                "current_phase": "done",
                "input_file_type": "pdf",
            }
        ]
        with mock.patch("api.routes.list_cnvrt_drawings", return_value=drawings) as drawing_lookup:
            response = planning_context_drawings(277, 206, authorization=self._read_auth("user-token"))

        self.assertEqual(response, {"items": drawings})
        drawing_lookup.assert_called_once_with(277, 206, "user-token")

    def test_cnvrt_drawing_discovery_normalizes_paginated_response(self):
        client = mock.Mock()
        client.get_json.return_value = {
            "count": 1,
            "results": [
                {
                    "id": 2100,
                    "name": "P&ID 2",
                    "status": "complete",
                    "current_phase": "post_process",
                    "input_file_type": "pdf",
                    "change_version": 7,
                }
            ],
        }
        with mock.patch("api.service.Plant360Client", return_value=client):
            drawings = list_cnvrt_drawings(277, 206, "user-token")

        self.assertEqual(
            drawings,
            [
                {
                    "id": "2100",
                    "name": "P&ID 2",
                    "status": "complete",
                    "current_phase": "post_process",
                    "input_file_type": "pdf",
                }
            ],
        )
        client.get_json.assert_called_once_with("/projects/277/collections/206/jobs")

    def test_planning_context_unigraph_projects_forwards_context_and_bearer_token(self):
        projects = [
            {
                "id": "15",
                "name": "Aker graph",
                "state": "ready",
                "status": "complete",
                "export_type": "collection_export",
                "has_taxonomy": True,
            }
        ]
        with mock.patch("api.routes.list_unigraph_projects", return_value=projects) as project_lookup:
            response = planning_context_unigraph_projects(277, 206, authorization=self._read_auth("user-token"))

        self.assertEqual(response, {"items": projects})
        project_lookup.assert_called_once_with(277, 206, "user-token")

    def test_unigraph_project_discovery_normalizes_all_collection_matches(self):
        client = mock.Mock()
        client.get_json.side_effect = [
            [
                {
                    "id": 15,
                    "name": "Aker graph A",
                    "state": "ready",
                    "status": "complete",
                    "export_type": "project_export",
                    "has_taxonomy": True,
                },
                {
                    "id": 16,
                    "name": "Aker graph B",
                    "state": "draft",
                    "status": "processing",
                    "export_type": "project_export",
                    "has_taxonomy": False,
                },
            ],
            [],
            {"collections": [{"cnvrt_collection_id": 206}]},
            {"collections": [{"cnvrt_collection_id": 207}]},
        ]
        with mock.patch("api.service.Plant360Client", return_value=client):
            projects = list_unigraph_projects(277, 206, "user-token")

        self.assertEqual([project["id"] for project in projects], ["15"])
        self.assertTrue(projects[0]["has_taxonomy"])
        self.assertEqual(
            client.get_json.call_args_list,
            [
                mock.call("/api/projects/by-cnvrt?cnvrt_project_id=277"),
                mock.call("/api/projects/by-cnvrt?cnvrt_project_id=277&cnvrt_collection_id=206"),
                mock.call("/api/projects/15/collections"),
                mock.call("/api/projects/16/collections"),
            ],
        )

    def test_run_lifecycle_returns_payload_unmodified(self):
        with mock.patch("api.service.run_agent_pipeline", side_effect=lambda config, **_: _Result(config)), \
             mock.patch("api.service.resolve_pid_image", return_value=("", {"pid_image_error": "skipped"})):
            accepted = self._submit()
            self.assertIn(accepted.status, {"queued", "running"})
            done = self._wait(accepted.run_id)

        self.assertEqual(done["status"], "succeeded")
        self.assertNotIn("result", done)
        self.assertEqual(done["agent"]["steps_used"], 3)
        result = run_result(self.request, accepted.run_id, authorization=self._read_auth())
        self.assertEqual(result["data"][0]["selected_equipment"], ["P3"])
        self.assertEqual(result["data"][0]["isolation_points"], [{"uuid": "u1"}])

    def test_run_status_is_lightweight_and_result_endpoint_returns_payload(self):
        with mock.patch("api.service.run_agent_pipeline", side_effect=lambda config, **_: _Result(config)), \
             mock.patch("api.service.resolve_pid_image", return_value=("", {})):
            accepted = self._submit()
            done = self._wait(accepted.run_id)

        self.assertEqual(done["status"], "succeeded")
        self.assertNotIn("result", done)
        result = run_result(self.request, accepted.run_id, authorization=self._read_auth())
        self.assertEqual(result["message"], "Completed")
        self.assertEqual(result["data"][0]["selected_equipment"], ["P3"])

    def test_run_status_response_model_does_not_serialize_result(self):
        with mock.patch("api.service.run_agent_pipeline", side_effect=lambda config, **_: _Result(config)), \
             mock.patch("api.service.resolve_pid_image", return_value=("", {})):
            accepted = self._submit()
            done = self._wait(accepted.run_id)

        public_status = RunStatus.model_validate({**done, "result": {"should": "drop"}}).model_dump()
        self.assertNotIn("result", public_status)

    def test_list_runs_returns_lightweight_summaries(self):
        with mock.patch("api.service.run_agent_pipeline", side_effect=lambda config, **_: _Result(config)), \
             mock.patch("api.service.resolve_pid_image", return_value=("", {})):
            accepted = self._submit()
            self._wait(accepted.run_id)

        response = list_runs(self.request, authorization=self._read_auth())
        self.assertEqual(response["items"][0]["run_id"], accepted.run_id)
        self.assertEqual(response["items"][0]["status"], "succeeded")
        self.assertNotIn("result", response["items"][0])

    def test_failed_run_records_structured_error(self):
        with mock.patch("api.service.run_agent_pipeline", side_effect=RuntimeError("boom")):
            accepted = self._submit()
            done = self._wait(accepted.run_id)
        self.assertEqual(done["status"], "failed")
        self.assertEqual(done["error"]["kind"], "pipeline_error")
        self.assertIn("boom", done["error"]["message"])
        events = (Path(self.tmp.name) / "runs" / accepted.run_id / "events.jsonl").read_text(encoding="utf-8")
        self.assertIn("boom", events)

    def test_not_ok_run_persists_error_event(self):
        with mock.patch(
            "api.runs.execute_agent_request",
            return_value={"ok": False, "error": {"kind": "pipeline_error", "message": "not ok"}, "trace": []},
        ):
            accepted = self._submit()
            done = self._wait(accepted.run_id)
        self.assertEqual(done["status"], "failed")
        events = (Path(self.tmp.name) / "runs" / accepted.run_id / "events.jsonl").read_text(encoding="utf-8")
        self.assertIn("not ok", events)

    def test_error_detail_classifies_known_pipeline_failures(self):
        self.assertEqual(
            _error_detail(RuntimeError("Configured project metadata failed for equipment P3"))["kind"],
            "project_metadata",
        )
        self.assertEqual(
            _error_detail(RuntimeError("Configured CNVRT job resolution failed for equipment P3"))["kind"],
            "job_resolution",
        )

    def test_result_before_completion_is_409(self):
        class SlowResult(_Result):
            pass

        def slow(config, **_):
            time.sleep(0.2)
            return SlowResult(config)

        with mock.patch("api.service.run_agent_pipeline", side_effect=slow), \
             mock.patch("api.service.resolve_pid_image", return_value=("", {})):
            accepted = self._submit()
            with self.assertRaises(HTTPException) as caught:
                run_result(self.request, accepted.run_id, authorization=self._read_auth())
            self.assertEqual(caught.exception.status_code, 409)
            self._wait(accepted.run_id)

    def test_succeeded_run_without_payload_does_not_return_null_result(self):
        run_id = "a" * 32
        run_dir = Path(self.tmp.name) / "runs" / run_id
        run_dir.mkdir(parents=True)
        record = RunRecord(
            run_id=run_id,
            equipment_tag="P3",
            runner="agentic",
            run_dir=run_dir,
            status="succeeded",
        )
        self.store._records[record.run_id] = record

        with self.assertRaises(HTTPException) as caught:
            run_result(self.request, record.run_id, authorization=self._read_auth())

        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(caught.exception.detail["kind"], "result_not_available")

    def test_pid_image_route_is_public_for_embedded_viewer_image(self):
        run_id = "c" * 32
        run_dir = Path(self.tmp.name) / "runs" / run_id
        run_dir.mkdir(parents=True)
        image_path = run_dir / "P3_pid.png"
        image_path.write_bytes(b"png")
        record = RunRecord(
            run_id=run_id,
            equipment_tag="P3",
            runner="agentic",
            run_dir=run_dir,
            status="succeeded",
        )
        self.store._records[record.run_id] = record

        response = run_pid_image(self.request, record.run_id)

        self.assertEqual(Path(response.path), image_path)

    def test_run_timeout_marks_stuck_worker_failed(self):
        self.store.shutdown()
        self.store = RunStore(Path(self.tmp.name) / "timeout-runs", max_workers=1, run_timeout_seconds=1)
        self.request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(run_store=self.store)))

        def stuck(config, **_):
            time.sleep(2)
            return _Result(config)

        with mock.patch("api.service.run_agent_pipeline", side_effect=stuck):
            accepted = self._submit()
            done = self._wait(accepted.run_id)
        self.assertEqual(done["status"], "failed")
        self.assertEqual(done["error"]["kind"], "timeout")

    def test_run_timeout_does_not_start_while_queued(self):
        self.store.shutdown()
        self.store = RunStore(Path(self.tmp.name) / "queued-runs", max_workers=1, run_timeout_seconds=1)
        self.request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(run_store=self.store)))

        calls = {"count": 0}

        def first_slow_then_fast(config, **_):
            calls["count"] += 1
            if calls["count"] == 1:
                time.sleep(1.5)
            return _Result(config)

        with mock.patch("api.service.run_agent_pipeline", side_effect=first_slow_then_fast), \
             mock.patch("api.service.resolve_pid_image", return_value=("", {})):
            first = self._submit()
            second = self._submit(body={"equipment_tag": "P4"})
            first_done = self._wait(first.run_id)
            second_done = self._wait(second.run_id)
        self.assertEqual(first_done["status"], "failed")
        self.assertEqual(first_done["error"]["kind"], "timeout")
        self.assertEqual(second_done["status"], "succeeded")
        self.assertIsNotNone(second_done["started_at"])

    def test_token_does_not_leak_to_status_result_or_trace(self):
        sentinel = "secret-token-123"
        with mock.patch("api.service.run_agent_pipeline", side_effect=lambda config, **_: _Result(config)), \
             mock.patch("api.service.resolve_pid_image", return_value=("", {})):
            accepted = self._submit(token=sentinel)
            status = self._wait(accepted.run_id)
            result = str(run_result(self.request, accepted.run_id, authorization=self._read_auth(sentinel)))
            trace = (Path(self.tmp.name) / "runs" / accepted.run_id / "trace.json").read_text(encoding="utf-8")
        self.assertNotIn(sentinel, str(status))
        self.assertNotIn(sentinel, result)
        self.assertNotIn(sentinel, trace)


if __name__ == "__main__":
    unittest.main()
