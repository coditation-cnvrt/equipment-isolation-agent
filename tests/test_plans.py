import unittest
from datetime import datetime, timezone
from importlib.resources import files
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException, Response

from api.models import CreateIsolationPlanFromRunRequest, IsolationPlanDetail
from api.plans import PlanDomainError, canonical_hash, derivation_status, normalized_plan_content, plan_content_diff, validate_promotable_result
from api.routes import create_plan_from_run, list_plans, plan_detail


PLAN_ID = "5fbaf888-bf86-4b23-b428-a609156c2f14"
VERSION_ID = "276627f1-884c-42ad-ae29-90c30dbd95bb"
RUN_ID = "f" * 32


def _plan():
    now = datetime(2026, 3, 20, tzinfo=timezone.utc)
    source_run = {
        "run_id": RUN_ID,
        "runner": "agentic",
        "status": "succeeded",
        "equipment_tag": "N7",
        "created_at": now,
        "assurance_status": "not_isolated",
        "job_id": "2151",
        "job_name": "Drawing N7",
        "cnvrt_project_id": "277",
        "collection_id": "206",
        "unigraph_project_id": "15",
        "request": {"job_id": "2151"},
        "agent": None,
        "result_url": f"/isolation-runs/{RUN_ID}/result",
        "trace_url": f"/isolation-runs/{RUN_ID}/trace",
    }
    version = {
        "plan_version_id": VERSION_ID,
        "parent_plan_version_id": None,
        "version_no": 1,
        "derivation_status": "completed",
        "input_hash": "sha256:input",
        "model_hash": "sha256:model",
        "derived_at": now,
        "superseded_at": None,
        "source_run": source_run,
    }
    return {
        "plan_id": PLAN_ID,
        "plan_number": "ISO-2026-000001",
        "active_plan_version_id": None,
        "mode": "advisory",
        "lifecycle_state": "draft",
        "area_code": "Area 12",
        "created_at": now,
        "latest_plan_version_id": VERSION_ID,
        "latest_version": version,
        "versions": [version],
    }


class _PlanRepository:
    def __init__(self):
        self.plan = _plan()
        self.created = True
        self.create_error = None
        self.create_calls = []

    def create_plan_from_run(self, run_id, area_code):
        self.create_calls.append((run_id, area_code))
        if self.create_error:
            raise self.create_error
        return self.plan, self.created

    def list_plans(self, **_):
        summary = dict(self.plan)
        summary.pop("versions")
        return [summary], 1

    def get_plan(self, plan_id):
        return self.plan if plan_id == PLAN_ID else None


class PlanTests(unittest.TestCase):
    def _request(self, repository=None):
        store = SimpleNamespace(repository=repository)
        return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(run_store=store)))

    def test_canonical_hash_is_order_independent(self):
        self.assertEqual(canonical_hash({"b": 2, "a": 1}), canonical_hash({"a": 1, "b": 2}))

    def test_degraded_derivation_uses_distinct_status(self):
        self.assertEqual(derivation_status({"orchestration_error": {"message": "503"}}), "completed_degraded")
        self.assertEqual(derivation_status({}), "completed")

    def test_promotable_result_requires_plan_assurance(self):
        validate_promotable_result({"data": [{"assurance_status": "not_isolated"}]})
        with self.assertRaises(PlanDomainError) as caught:
            validate_promotable_result({"data": []})
        self.assertEqual(caught.exception.kind, "invalid_run_result")

    def test_normalized_content_and_structural_diff_are_plan_owned(self):
        request = {"equipment_tag": "N7", "work_scope": {"intrusive_work": True}, "selected_asset": {"hilt_entity_id": "hilt-n7", "tag": "N7"}}
        first = normalized_plan_content(request, {"data": [{"assurance_status": "provisional_unproven_isolation", "isolation_points": [{"uuid": "v1", "tag_number": "XV-1", "branch_id": "b1", "branch_path_node_ids": ["n1", "v1"]}]}]})
        second = normalized_plan_content(request, {"data": [{"assurance_status": "provisional_unproven_isolation", "isolation_points": [{"uuid": "v1", "tag_number": "XV-101", "branch_id": "b1", "branch_path_node_ids": ["n1", "v1"]}, {"uuid": "v2", "tag_number": "XV-2", "branch_id": "b2"}]}]})
        self.assertEqual(first["selected_asset"]["hilt_entity_id"], "hilt-n7")
        diff = plan_content_diff(first, second)
        self.assertEqual(diff["summary"]["added"], 2)  # one point and one branch
        self.assertGreaterEqual(diff["summary"]["changed"], 1)
        self.assertGreater(diff["summary"]["safety_significant"], 0)

    def test_shared_point_preserves_every_source_branch(self):
        result = {"data": [{
            "assurance_status": "provisional_unproven_isolation",
            "isolation_points": [{
                "uuid": "shared-v1",
                "tag_number": "XV-SHARED",
                "branch_id": "branch-a",
                "branch_path_node_ids": ["a-nozzle", "shared-v1"],
                "source_paths": [
                    {"branch_id": "branch-a", "source_component_id": "N-A"},
                    {"branch_id": "branch-b", "source_component_id": "N-B"},
                ],
            }],
        }]}
        content = normalized_plan_content({"equipment_tag": "N7"}, result)
        self.assertEqual([branch["key"] for branch in content["branches"]], ["branch-a", "branch-b"])
        self.assertEqual(content["points"][0]["branch_keys"], ["branch-a", "branch-b"])
        self.assertEqual(content["branches"][1]["point_keys"], ["shared-v1"])

    def test_step_normalization_uses_semantic_identity_not_position(self):
        request = {"equipment_tag": "N7"}
        first = normalized_plan_content(request, {"data": [{
            "assurance_status": "provisional_unproven_isolation",
            "loto_procedure": {"ordered_steps": [
                {"step": 1, "phase": 3, "device_uuid": "v1", "action": "Close XV-1"},
                {"step": 2, "phase": 3, "device_uuid": "v2", "action": "Close XV-2"},
            ]},
        }]})
        second = normalized_plan_content(request, {"data": [{
            "assurance_status": "provisional_unproven_isolation",
            "loto_procedure": {"ordered_steps": [
                {"step": 1, "phase": 3, "device_uuid": "v2", "action": "Close XV-2"},
                {"step": 2, "phase": 3, "device_uuid": "v1", "action": "Close XV-1"},
            ]},
        }]})

        self.assertEqual({item["key"] for item in first["steps"]}, {
            "phase:3:operate_isolation:v1",
            "phase:3:operate_isolation:v2",
        })
        diff = plan_content_diff(first, second)
        self.assertEqual(diff["summary"]["added"], 0)
        self.assertEqual(diff["summary"]["removed"], 0)
        self.assertEqual(diff["summary"]["changed"], 2)

    def test_plan_detail_response_contract_accepts_repository_payload(self):
        validated = IsolationPlanDetail.model_validate(_plan())
        self.assertEqual(validated.latest_version.version_no, 1)
        self.assertIsNone(validated.active_plan_version_id)

    def test_create_from_run_returns_201_and_location(self):
        repository = _PlanRepository()
        response = Response()
        result = create_plan_from_run(
            self._request(repository),
            CreateIsolationPlanFromRunRequest(run_id=RUN_ID, area_code=" Area 12 "),
            response,
            authorization="Bearer token",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["location"], f"/isolation-plans/{PLAN_ID}")
        self.assertEqual(result["active_plan_version_id"], None)
        self.assertEqual(repository.create_calls, [(RUN_ID, "Area 12")])

    def test_duplicate_promotion_returns_200(self):
        repository = _PlanRepository()
        repository.created = False
        response = Response()
        create_plan_from_run(
            self._request(repository),
            CreateIsolationPlanFromRunRequest(run_id=RUN_ID),
            response,
            authorization="Bearer token",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("location", response.headers)

    def test_plan_routes_require_postgres_repository(self):
        with self.assertRaises(HTTPException) as caught:
            list_plans(self._request(), authorization="Bearer token")
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.detail["kind"], "plan_store_unavailable")

    def test_domain_error_is_preserved_by_create_route(self):
        repository = _PlanRepository()
        repository.create_error = PlanDomainError("run_not_succeeded", "Not complete.", 409, {"status": "failed"})
        with self.assertRaises(HTTPException) as caught:
            create_plan_from_run(
                self._request(repository),
                CreateIsolationPlanFromRunRequest(run_id=RUN_ID),
                Response(),
                authorization="Bearer token",
            )
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(caught.exception.detail["status"], "failed")

    def test_list_and_detail_are_lightweight_and_versioned(self):
        repository = _PlanRepository()
        listed = list_plans(self._request(repository), limit=20, offset=0, authorization="Bearer token")
        detail = plan_detail(self._request(repository), UUID(PLAN_ID), authorization="Bearer token")
        self.assertEqual(listed["total"], 1)
        self.assertNotIn("versions", listed["items"][0])
        self.assertEqual(detail["versions"][0]["version_no"], 1)
        self.assertIsNone(detail["active_plan_version_id"])

    def test_baseline_migration_contains_bridge_constraints(self):
        migration = (
            files("api.migrations.versions")
            .joinpath("0001_current_schema.py")
            .read_text(encoding="utf-8")
        )
        self.assertIn('op.create_table(\n        "isolation_plan"', migration)
        self.assertIn('op.create_table(\n        "plan_version"', migration)
        self.assertIn('op.create_table(\n        "external_run_link"', migration)
        self.assertIn("external_run_link_one_derivation_idx", migration)
        self.assertIn("plan_version_plan_id_parent_plan_version_id_fkey", migration)


if __name__ == "__main__":
    unittest.main()
