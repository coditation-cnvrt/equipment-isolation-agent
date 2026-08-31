import unittest
from types import SimpleNamespace
from unittest.mock import patch

from equipment_isolation.pipeline.equipment import _job_id_from_pnid_reference, add_equipment_jobs, add_equipment_jobs_from_metadata


class EquipmentDrawingResolutionTests(unittest.TestCase):
    def test_extracts_exact_job_id_from_unigraph_pnid_reference(self):
        self.assertEqual(_job_id_from_pnid_reference("pnid:job:2152"), "2152")
        self.assertEqual(_job_id_from_pnid_reference("2151"), "2151")
        self.assertEqual(_job_id_from_pnid_reference(""), "")

    def test_metadata_adds_drawing_name_for_graph_job_id(self):
        items = [{"tag": "P3", "job_id": "2151", "job_name": ""}]

        add_equipment_jobs_from_metadata(items, {"P3 source drawing": "2151"})

        self.assertEqual(items[0]["job_id"], "2151")
        self.assertEqual(items[0]["job_name"], "P3 source drawing")

    def test_stlm_fallback_does_not_scan_drawings_when_jobs_are_resolved(self):
        items = [{"tag": "P3", "job_id": "2151", "job_name": "P3 source drawing"}]

        with patch("equipment_isolation.pipeline.equipment.Plant360Client") as client:
            result = add_equipment_jobs(
                items,
                SimpleNamespace(auth_token="token"),
                {"P3 source drawing": "2151"},
            )

        self.assertIs(result, items)
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
