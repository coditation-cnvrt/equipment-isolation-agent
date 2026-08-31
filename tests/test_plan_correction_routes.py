import unittest
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError

from equipment_isolation.api.models import CreateChangeRequest, DerivePlanRequest
from equipment_isolation.api.plans import PlanDomainError
from equipment_isolation.api.routes import approve_plan_change, create_plan_change, derive_plan, list_plan_changes


PLAN_ID = UUID("5fbaf888-bf86-4b23-b428-a609156c2f14")
VERSION_ID = "276627f1-884c-42ad-ae29-90c30dbd95bb"
CHANGE_ID = UUID("974eb15d-e89f-48be-a347-d8dcf5f236fe")


class Repository:
    def __init__(self):
        self.failed_manifest = None
        self.change = {
            "change_id": str(CHANGE_ID), "plan_id": str(PLAN_ID), "raised_against_version_id": VERSION_ID,
            "change_type": "accept_manual_candidate", "target_type": "candidate", "target_id": "v1",
            "proposed_change": {}, "justification": "Field verified", "state": "submitted", "raised_by": "7",
            "approved_by": None, "created_at": "2026-08-26T00:00:00Z", "approved_at": None,
        }

    def create_change(self, plan_id, payload, actor):
        self.change["raised_by"] = actor
        return self.change

    def list_plans(self, **kwargs):
        return [], 0

    def approve_change(self, plan_id, change_id, actor):
        self.change.update(state="approved", approved_by=actor)
        return self.change

    def list_changes(self, plan_id):
        return [self.change]

    def prepare_derivation(self, plan_id, parent, actor):
        return {
            "manifest_id": "f2ddaa35-795e-4dc8-a72d-1a330a14255f",
            "parent_run_id": "a" * 32,
            "request": {
                "equipment_tag": "N7", "job_id": "2151", "cnvrt_project_id": "277", "collection_id": "206", "unigraph_project_id": "15",
                "approved_corrections": [self.change], "derivation_context": {"manifest_id": "f2ddaa35-795e-4dc8-a72d-1a330a14255f"},
            },
        }

    def fail_derivation_launch(self, manifest_id, actor_id, error):
        self.failed_manifest = (manifest_id, actor_id, error)


class Store:
    def __init__(self):
        self.repository = Repository()
        self.parent = None

    def create(self, request, token, parent_run_id=None):
        self.parent = parent_run_id
        return SimpleNamespace(run_id="b" * 32, status="queued")


class FailingStore(Store):
    def create(self, request, token, parent_run_id=None):
        raise RuntimeError("worker unavailable")


class PlanCorrectionRouteTests(unittest.TestCase):
    def request(self, user_id="7"):
        store = Store()
        return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(run_store=store)), state=SimpleNamespace(token_data={"user": {"id": user_id}}))

    def body(self):
        return CreateChangeRequest(raised_against_version_id=VERSION_ID, change_type="accept_manual_candidate", target_type="candidate", target_id="v1", justification="Field verified")

    def test_whitespace_only_change_text_is_rejected(self):
        with self.assertRaises(ValidationError):
            CreateChangeRequest(raised_against_version_id=VERSION_ID, change_type="add_manual_isolation_point", target_type="isolation_point", target_id=" ", justification="   ")

    def test_corrected_label_must_be_nonblank(self):
        with self.assertRaises(ValidationError):
            CreateChangeRequest(raised_against_version_id=VERSION_ID, change_type="correct_label", target_type="candidate", target_id="v1", proposed_change={"label": "   "}, justification="Field verified")

    def test_feedback_category_is_inferred_and_mismatch_is_rejected(self):
        body = self.body()
        self.assertEqual(body.feedback_category, "manual_observation")
        with self.assertRaisesRegex(ValidationError, "belongs to category"):
            CreateChangeRequest(
                raised_against_version_id=VERSION_ID,
                change_type="correct_label",
                feedback_category="manual_observation",
                target_type="candidate",
                target_id="v1",
                proposed_change={"label": "XV-101"},
                justification="Field tag plate checked",
            )

    def test_operational_availability_corrections_are_part_of_the_api_contract(self):
        unavailable = CreateChangeRequest(
            raised_against_version_id=VERSION_ID,
            change_type="mark_point_unavailable",
            target_type="isolation_point",
            target_id="v1",
            proposed_change={"drawing_entity_id": "hilt-v1", "operational_status": "unavailable"},
            justification="Valve stem seized",
        )
        restored = CreateChangeRequest(
            raised_against_version_id=VERSION_ID,
            change_type="mark_point_available",
            target_type="isolation_point",
            target_id="v1",
            justification="Valve repaired and function tested",
        )
        self.assertEqual(unavailable.change_type, "mark_point_unavailable")
        self.assertEqual(restored.change_type, "mark_point_available")
        self.assertEqual(unavailable.proposed_change["operational_status"], "unavailable")
        self.assertEqual(restored.proposed_change["operational_status"], "available")
        with self.assertRaisesRegex(ValidationError, "operational_status"):
            CreateChangeRequest(
                raised_against_version_id=VERSION_ID,
                change_type="mark_point_unavailable",
                target_type="isolation_point",
                target_id="v1",
                proposed_change={"operational_status": "available"},
                justification="Valve stem seized",
            )

    def test_authenticated_actor_is_recorded_and_listed(self):
        request = self.request("7")
        created = create_plan_change(request, PLAN_ID, self.body(), authorization="Bearer token")
        listed = list_plan_changes(request, PLAN_ID, authorization="Bearer token")
        self.assertEqual(created["raised_by"], "7")
        self.assertEqual(listed["items"][0]["change_id"], str(CHANGE_ID))

    def test_advisory_correction_can_be_self_approved(self):
        request = self.request("7")
        approved = approve_plan_change(request, PLAN_ID, CHANGE_ID, authorization="Bearer token")
        self.assertEqual(approved["state"], "approved")
        self.assertEqual(approved["approved_by"], "7")

    def test_derivation_returns_child_run_lineage(self):
        request = self.request("8")
        accepted = derive_plan(request, PLAN_ID, DerivePlanRequest(parent_plan_version_id=VERSION_ID), authorization="Bearer token")
        self.assertEqual(accepted["run_id"], "b" * 32)
        self.assertEqual(request.app.state.run_store.parent, "a" * 32)

    def test_derivation_launch_failure_releases_manifest(self):
        request = self.request("8")
        request.app.state.run_store = FailingStore()
        with self.assertRaises(HTTPException) as caught:
            derive_plan(request, PLAN_ID, DerivePlanRequest(parent_plan_version_id=VERSION_ID), authorization="Bearer token")
        self.assertEqual(caught.exception.status_code, 503)
        failed = request.app.state.run_store.repository.failed_manifest
        self.assertEqual(failed[0], "f2ddaa35-795e-4dc8-a72d-1a330a14255f")
        self.assertEqual(failed[1], "8")


if __name__ == "__main__":
    unittest.main()
