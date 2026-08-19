import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from api.service import list_project_equipment


class EquipmentServiceTests(unittest.TestCase):
    @patch("api.service.list_equipment")
    @patch("api.service.Plant360Client")
    @patch("api.service.config_from_equipment_request")
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

    @patch("api.service.list_equipment")
    @patch("api.service.Plant360Client")
    @patch("api.service.config_from_equipment_request")
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

    @patch("api.service.list_equipment")
    @patch("api.service.Plant360Client")
    @patch("api.service.config_from_equipment_request")
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
