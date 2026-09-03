import unittest
from types import SimpleNamespace
from unittest import mock
from uuid import UUID

from pydantic import ValidationError

from equipment_isolation.api.models import (
    AssetConditionActionRequest,
    AssetConditionAssetRequest,
    CreateAssetConditionRequest,
    DerivedIsolationRunRequest,
)
from equipment_isolation.api.routes import (
    clear_asset_condition,
    confirm_asset_condition,
    create_asset_condition,
    list_asset_conditions,
)
from equipment_isolation.api.service import (
    authorize_planning_context,
    config_from_run_request,
)
from equipment_isolation.config import RunConfig


CONDITION_ID = UUID("8f841903-36a4-49ed-8024-a3011c7a4378")


def asset_request(**overrides):
    values = {
        "external_system": "cnvrt_drawing_entity",
        "external_id": "hilt-valve-1",
        "tag": "XV-101",
        "asset_class": "gate_valve",
        "cnvrt_project_id": "277",
        "collection_id": "206",
        "unigraph_project_id": "15",
        "job_id": "2151",
    }
    values.update(overrides)
    return AssetConditionAssetRequest(**values)


class Repository:
    def __init__(self):
        self.calls = []
        self.condition = {
            "condition_id": str(CONDITION_ID),
            "state": "active",
            "asset": {
                "external_system": "cnvrt_drawing_entity",
                "context": asset_request().context(),
            },
        }

    def get_asset_condition(self, _condition_id):
        return self.condition

    def create_asset_condition(self, payload, actor):
        self.calls.append(("create", payload, actor))
        return self.condition

    def list_plans(self, **_filters):
        return [], 0

    def list_asset_conditions(self, **filters):
        self.calls.append(("list", filters))
        return [self.condition], 1

    def confirm_asset_condition(self, condition_id, payload, actor):
        self.calls.append(("confirm", condition_id, payload, actor))
        return self.condition

    def clear_asset_condition(self, condition_id, payload, actor):
        self.calls.append(("clear", condition_id, payload, actor))
        return {**self.condition, "state": "cleared"}


class AssetConditionTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch(
            "equipment_isolation.api.routes.authorize_planning_context"
        )
        self.authorize_scope = patcher.start()
        self.addCleanup(patcher.stop)

    def request(self):
        repository = Repository()
        store = SimpleNamespace(repository=repository)
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(run_store=store)),
            state=SimpleNamespace(token_data={"user": {"id": "42"}}),
        )
        return request, repository

    def test_drawing_asset_requires_exact_job_scope(self):
        with self.assertRaisesRegex(ValidationError, "job_id is required"):
            asset_request(job_id="")
        graph_asset = asset_request(
            external_system="unigraph_candidate", job_id="", external_id="graph-v1"
        )
        self.assertEqual(graph_asset.external_id, "graph-v1")

    def test_pre_plan_condition_routes_use_authenticated_actor_and_context(self):
        request, repository = self.request()
        payload = CreateAssetConditionRequest(
            asset=asset_request(), notes="Valve stem is seized"
        )
        created = create_asset_condition(request, payload, authorization="Bearer token")
        listed = list_asset_conditions(
            request,
            cnvrt_project_id="277",
            collection_id="206",
            unigraph_project_id="15",
            job_id="2151",
            authorization="Bearer token",
        )
        self.assertEqual(created["condition_id"], str(CONDITION_ID))
        self.assertEqual(listed["items"][0]["condition_id"], str(CONDITION_ID))
        self.assertEqual(repository.calls[0][2], "42")
        self.assertEqual(repository.calls[1][1]["job_id"], "2151")
        self.authorize_scope.assert_has_calls(
            [
                mock.call(
                    payload.asset.context(),
                    "token",
                    asset_system="cnvrt_drawing_entity",
                ),
                mock.call(
                    {
                        "cnvrt_project_id": "277",
                        "collection_id": "206",
                        "unigraph_project_id": "15",
                        "job_id": "2151",
                    },
                    "token",
                    asset_system="",
                ),
            ]
        )

    def test_confirm_and_clear_are_distinct_lifecycle_actions(self):
        request, repository = self.request()
        action = AssetConditionActionRequest(reason="Field function test completed")
        confirm_asset_condition(
            request, CONDITION_ID, action, authorization="Bearer token"
        )
        cleared = clear_asset_condition(
            request, CONDITION_ID, action, authorization="Bearer token"
        )
        self.assertEqual(cleared["state"], "cleared")
        self.assertEqual([call[0] for call in repository.calls], ["confirm", "clear"])
        self.assertEqual(
            self.authorize_scope.call_args_list,
            [
                mock.call(
                    asset_request().context(),
                    "token",
                    asset_system="cnvrt_drawing_entity",
                ),
                mock.call(
                    asset_request().context(),
                    "token",
                    asset_system="cnvrt_drawing_entity",
                ),
            ],
        )

    def test_scope_authorization_precedes_shared_condition_creation(self):
        request, repository = self.request()
        payload = CreateAssetConditionRequest(
            asset=asset_request(), notes="Valve stem is seized"
        )
        with mock.patch(
            "equipment_isolation.api.routes.authorize_planning_context",
            side_effect=PermissionError("forbidden"),
        ):
            with self.assertRaises(Exception) as caught:
                create_asset_condition(request, payload, authorization="Bearer token")
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(repository.calls, [])

    def test_scope_authorization_precedes_condition_listing(self):
        request, repository = self.request()
        with mock.patch(
            "equipment_isolation.api.routes.authorize_planning_context",
            side_effect=PermissionError("forbidden"),
        ):
            with self.assertRaises(Exception) as caught:
                list_asset_conditions(
                    request,
                    cnvrt_project_id="999",
                    collection_id="888",
                    unigraph_project_id="777",
                    authorization="Bearer token",
                )
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(repository.calls, [])

    def test_shared_unavailable_condition_is_applied_after_local_feedback(self):
        request_with_local = DerivedIsolationRunRequest(
            equipment_tag="P3",
            job_id="2151",
            cnvrt_project_id="277",
            collection_id="206",
            unigraph_project_id="15",
            approved_corrections=[
                {
                    "change_id": "local-1",
                    "change_type": "mark_point_available",
                    "target_id": "hilt-valve-1",
                }
            ],
        )
        condition = {
            "condition_id": str(CONDITION_ID),
            "condition_type": "unavailable",
            "state": "active",
            "notes": "Valve stem is seized",
            "reported_by": "42",
            "asset": {
                "asset_ref_id": "asset-1",
                "external_system": "cnvrt_drawing_entity",
                "scope_key": "cnvrt:277:collection:206:job:2151",
                "external_id": "hilt-valve-1",
            },
        }
        with mock.patch(
            "equipment_isolation.api.service.build_run_config",
            return_value=RunConfig(equipment_tag="P3"),
        ):
            config = config_from_run_request(
                request_with_local,
                "token",
                shared_asset_conditions=[condition],
            )
        self.assertEqual(config.approved_corrections[0]["change_type"], "mark_point_available")
        self.assertEqual(config.approved_corrections[-1]["change_type"], "mark_point_unavailable")
        self.assertEqual(
            config.approved_corrections[-1]["proposed_change"]["drawing_entity_id"],
            "hilt-valve-1",
        )

    @mock.patch("equipment_isolation.api.service._is_unigraph_project_mapped")
    @mock.patch("equipment_isolation.api.service.Plant360Client")
    @mock.patch("equipment_isolation.api.service._cnvrt_client")
    def test_context_authorization_checks_complete_hierarchy(
        self, cnvrt_client, _unigraph_client, mapped
    ):
        cnvrt_client.return_value.authorized_job.return_value = {
            "id": 2151,
            "project": {"id": 277},
            "collection": {"id": 206},
        }
        mapped.return_value = True
        authorize_planning_context(
            asset_request(external_system="unigraph_candidate").context(),
            "token",
            asset_system="unigraph_candidate",
        )
        cnvrt_client.return_value.authorized_job.assert_called_once_with(277, 206, 2151)
        cnvrt_client.return_value.job_details.assert_not_called()
        mapped.return_value = False
        with self.assertRaises(PermissionError):
            authorize_planning_context(
                asset_request(external_system="unigraph_candidate").context(),
                "token",
                asset_system="unigraph_candidate",
            )

    @mock.patch("equipment_isolation.api.service._is_unigraph_project_mapped")
    @mock.patch("equipment_isolation.api.service.Plant360Client")
    @mock.patch("equipment_isolation.api.service._cnvrt_client")
    def test_drawing_authorization_ignores_superseded_unigraph_export(
        self, cnvrt_client, unigraph_client, mapped
    ):
        cnvrt_client.return_value.authorized_job.return_value = {
            "id": 2151,
            "project": {"id": 277},
            "collection": {"id": 206},
        }
        authorize_planning_context(
            asset_request(unigraph_project_id="obsolete-export").context(),
            "token",
            asset_system="cnvrt_drawing_entity",
        )
        cnvrt_client.return_value.authorized_job.assert_called_once_with(277, 206, 2151)
        cnvrt_client.return_value.job_details.assert_not_called()
        unigraph_client.assert_not_called()
        mapped.assert_not_called()

    @mock.patch("equipment_isolation.api.service._cnvrt_client")
    def test_context_authorization_rejects_unexpected_nested_job_identity(
        self, cnvrt_client
    ):
        cnvrt_client.return_value.authorized_job.return_value = {
            "id": 2151,
            "project": {"id": 277},
            "collection": {"id": 999},
        }
        with self.assertRaisesRegex(PermissionError, "drawing is not accessible"):
            authorize_planning_context(
                asset_request().context(),
                "token",
                asset_system="cnvrt_drawing_entity",
            )

    @mock.patch("equipment_isolation.api.service._is_unigraph_project_mapped")
    @mock.patch("equipment_isolation.api.service.Plant360Client")
    @mock.patch("equipment_isolation.api.service._cnvrt_client")
    def test_only_canonical_drawing_system_skips_unigraph_authorization(
        self, cnvrt_client, _unigraph_client, mapped
    ):
        cnvrt_client.return_value.authorized_job.return_value = {
            "id": 2151,
            "project": {"id": 277},
            "collection": {"id": 206},
        }
        mapped.return_value = False

        with self.assertRaisesRegex(PermissionError, "UniGraph project"):
            authorize_planning_context(
                asset_request().context(),
                "token",
                asset_system="untrusted_drawing_alias",
            )

        mapped.assert_called_once()


if __name__ == "__main__":
    unittest.main()
