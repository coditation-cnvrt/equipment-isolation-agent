import unittest

from equipment_isolation.config import GraphConfig, RunConfig
from equipment_isolation.domain.identity import (
    DrawingEntityReference,
    ExternalIdentity,
    GeometryFallback,
    IdentityQuality,
    IdentitySource,
    PlanningContext,
    SelectedAsset,
    SelectionSource,
)
from equipment_isolation.domain.models import BBox


class IdentityContractTests(unittest.TestCase):
    def setUp(self):
        self.context = PlanningContext(
            cnvrt_project_id="277",
            collection_id="206",
            unigraph_project_id="15",
            job_id="2151",
            job_name="p3",
        )

    def test_external_identity_requires_source_scope_and_id(self):
        identity = ExternalIdentity(IdentitySource.UNIGRAPH, "project:15", "vertex:172184")
        self.assertEqual(
            identity.to_dict(),
            {
                "source_system": "unigraph",
                "project_scope": "project:15",
                "external_id": "vertex:172184",
            },
        )
        with self.assertRaises(ValueError):
            ExternalIdentity(IdentitySource.UNIGRAPH, "", "172184")

    def test_planning_context_uses_unambiguous_project_name(self):
        self.assertEqual(
            self.context.to_dict(),
            {
                "cnvrt_project_id": "277",
                "collection_id": "206",
                "unigraph_project_id": "15",
                "job_name": "p3",
                "job_id": "2151",
            },
        )
        legacy = self.context.to_dict(include_legacy_project_id=True)
        self.assertEqual(legacy["project_id"], "15")

    def test_hilt_selection_requires_drawing_scope_and_exact_entity(self):
        selected = SelectedAsset(
            tag="P3",
            context=self.context,
            selection_source=SelectionSource.HILT_EQUIPMENT_LIST,
            hilt_entity_id="08196784-d2a7-48bc-80e8-08bfd3b2657a",
            hilt_entity_class="vertical_vessel",
        )
        self.assertEqual(selected.identity_quality, IdentityQuality.EXACT)
        self.assertIsInstance(selected.drawing_entity, DrawingEntityReference)
        self.assertEqual(selected.drawing_entity.identity.project_scope, "job:2151")

        with self.assertRaises(ValueError):
            SelectedAsset(tag="P3", context=self.context, selection_source=SelectionSource.HILT_CANVAS)

    def test_cli_selection_explicitly_has_legacy_identity_quality(self):
        selected = SelectedAsset(tag="P3", context=self.context, selection_source=SelectionSource.CLI_TAG)
        self.assertEqual(selected.identity_quality, IdentityQuality.LEGACY_TAG_ONLY)
        self.assertIsNone(selected.drawing_entity)

    def test_geometry_declares_frame_and_cannot_use_unigraph_as_source(self):
        geometry = GeometryFallback(
            bbox=BBox(1, 2, 3, 4),
            source=IdentitySource.CNVRT_STLM,
            match_method="stlm_uuid",
            job_id="2151",
        )
        self.assertEqual(geometry.to_dict()["coordinate_frame"], "image_top_left")
        with self.assertRaises(ValueError):
            GeometryFallback(
                bbox=BBox(1, 2, 3, 4),
                source=IdentitySource.UNIGRAPH,
                match_method="vertex_id",
                job_id="2151",
            )

    def test_run_config_exposes_typed_context_without_changing_legacy_context(self):
        config = RunConfig(
            equipment_tag="P3",
            cnvrt_project_id="277",
            collection_id="206",
            job_id="2151",
            graph=GraphConfig(project_id="15", traversal_source_name="graph15_traversal"),
        )
        self.assertEqual(config.planning_context.unigraph_project_id, "15")
        self.assertEqual(config.context["project_id"], "15")
        self.assertNotIn("traversal_source", config.context)


if __name__ == "__main__":
    unittest.main()
