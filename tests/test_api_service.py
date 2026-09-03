import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from equipment_isolation.api.service import list_project_equipment
from equipment_isolation.integrations.api_client import Plant360Client


class EquipmentServiceTests(unittest.TestCase):
    def test_authorized_job_uses_nested_permission_checked_endpoint(self):
        client = Plant360Client(
            SimpleNamespace(
                base_url="https://cnvrt.example",
                auth_token="user-token",
                verify_ssl=True,
            )
        )
        expected = {
            "id": 2151,
            "project": {"id": 277},
            "collection": {"id": 206},
        }
        with patch.object(client, "get_json", return_value=expected) as get_json:
            result = client.authorized_job(277, 206, 2151)

        self.assertEqual(result, expected)
        get_json.assert_called_once_with(
            "/projects/277/collections/206/jobs/2151"
        )

    @patch("equipment_isolation.api.service.list_equipment")
    @patch("equipment_isolation.api.service.Plant360Client")
    @patch("equipment_isolation.api.service.config_from_equipment_request")
    def test_listing_validates_mapping_without_loading_pnid_reviews(
        self, config_from_request, client_class, list_equipment
    ):
        graph = object()
        config_from_request.return_value = SimpleNamespace(
            unigraph_api_base_url="https://unigraph.example",
            api=SimpleNamespace(verify_ssl=True),
            graph=graph,
        )
        client = client_class.return_value
        client.get_json.return_value = [{"id": 20}]
        list_equipment.return_value = [{"id": "asset-1", "job_id": "2151"}]
        request = SimpleNamespace(
            cnvrt_project_id="277",
            collection_id="206",
            unigraph_project_id="20",
            limit=0,
        )

        items = list_project_equipment(request, "token")

        self.assertEqual(items, [{"id": "asset-1", "job_id": "2151"}])
        client.get_json.assert_called_once_with(
            "/api/projects/by-cnvrt?cnvrt_project_id=277&cnvrt_collection_id=206"
        )
        list_equipment.assert_called_once_with(graph, 0)

    @patch("equipment_isolation.api.service.list_equipment")
    @patch("equipment_isolation.api.service.Plant360Client")
    @patch("equipment_isolation.api.service.config_from_equipment_request")
    def test_listing_accepts_project_export_collection_fallback(
        self, config_from_request, client_class, list_equipment
    ):
        graph = object()
        config_from_request.return_value = SimpleNamespace(
            unigraph_api_base_url="https://unigraph.example",
            api=SimpleNamespace(verify_ssl=True),
            graph=graph,
        )
        client_class.return_value.get_json.side_effect = [
            [],
            [{"id": 19}],
            {"collections": [{"cnvrt_collection_id": 252}]},
        ]
        list_equipment.return_value = [{"id": "asset-1", "job_id": "2509"}]
        request = SimpleNamespace(
            cnvrt_project_id="306",
            collection_id="252",
            unigraph_project_id="19",
            limit=0,
        )

        items = list_project_equipment(request, "token")

        self.assertEqual(items, [{"id": "asset-1", "job_id": "2509"}])
        list_equipment.assert_called_once_with(graph, 0)

    @patch("equipment_isolation.api.service.list_equipment")
    @patch("equipment_isolation.api.service.Plant360Client")
    @patch("equipment_isolation.api.service.config_from_equipment_request")
    def test_listing_rejects_unmapped_unigraph_project(
        self, config_from_request, client_class, list_equipment
    ):
        config_from_request.return_value = SimpleNamespace(
            unigraph_api_base_url="https://unigraph.example",
            api=SimpleNamespace(verify_ssl=True),
            graph=object(),
        )
        client_class.return_value.get_json.return_value = [{"id": 19}]
        request = SimpleNamespace(
            cnvrt_project_id="277",
            collection_id="206",
            unigraph_project_id="20",
            limit=0,
        )

        with self.assertRaisesRegex(ValueError, "not mapped"):
            list_project_equipment(request, "token")

        list_equipment.assert_not_called()


if __name__ == "__main__":
    unittest.main()
