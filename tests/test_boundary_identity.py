import unittest

from unittest import mock

from boundary import _fetch_selected_equipment_vertices, _verify_selected_asset
from domain.identity import PlanningContext, SelectedAsset, SelectionSource


class BoundaryIdentityTests(unittest.TestCase):
    def setUp(self):
        context = PlanningContext(
            cnvrt_project_id="277",
            collection_id="206",
            unigraph_project_id="15",
            job_id="2151",
        )
        self.selected = SelectedAsset(
            tag="P3",
            context=context,
            selection_source=SelectionSource.HILT_EQUIPMENT_LIST,
            hilt_entity_id="hilt-p3",
            hilt_entity_class="vertical_vessel",
        )

    def test_exact_lookup_never_uses_tag_properties(self):
        traversal = mock.MagicMock()
        traversal.g.V.return_value = traversal
        traversal.hasLabel.return_value = traversal
        traversal.or_.return_value = traversal
        traversal.valueMap.return_value = traversal
        traversal.toList.return_value = []

        _fetch_selected_equipment_vertices(traversal.g, "hilt-p3")

        traversal.or_.assert_called_once()
        query_text = " ".join(str(call) for call in traversal.method_calls)
        self.assertIn("node_id", query_text)
        self.assertNotIn("tag_number", query_text)

    def test_exact_source_identity_selects_one_vertex(self):
        vertices = [
            {"id": 1, "tag": "P3", "node_id": "different"},
            {"id": 2, "tag": "P3", "node_id": "hilt-p3"},
        ]
        matches, identity = _verify_selected_asset(vertices, self.selected)
        self.assertEqual(matches, [vertices[1]])
        self.assertEqual(identity["status"], "verified")
        self.assertEqual(identity["unigraph_vertex_id"], "2")
        self.assertEqual(identity["unigraph_identity_property"], "node_id")

    def test_tag_equality_does_not_prove_identity(self):
        with self.assertRaisesRegex(RuntimeError, "not_found"):
            _verify_selected_asset([{"id": 1, "tag": "P3", "node_id": "different"}], self.selected)

    def test_duplicate_source_identity_is_rejected_as_ambiguous(self):
        vertices = [
            {"id": 1, "tag": "P3", "node_id": "hilt-p3"},
            {"id": 2, "tag": "P3", "cnvrt_id": "hilt-p3"},
        ]
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            _verify_selected_asset(vertices, self.selected)

    def test_legacy_mode_preserves_tag_discovered_vertices(self):
        vertices = [{"id": 1, "tag": "P3"}, {"id": 2, "tag": "P3"}]
        matches, identity = _verify_selected_asset(vertices, None)
        self.assertEqual(matches, vertices)
        self.assertEqual(identity["identity_quality"], "legacy_tag_only")


if __name__ == "__main__":
    unittest.main()
