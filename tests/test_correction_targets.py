import unittest
from types import SimpleNamespace
from unittest import mock

from equipment_isolation.config import IsolationPolicy
from equipment_isolation.core.correction_targets import _bfs_nearest_sources, enrich_approved_correction_targets


TARGET = "04b611df-474b-452a-8a72-fb72f3aa641c"


def correction():
    return {"change_id": "change-1", "change_type": "add_manual_isolation_point", "target_id": TARGET}


def boundary():
    return {
        "equipment_boundaries": [{
            "equipment": {"id": 1, "properties": {"Equipment Name": "BB001"}},
            "component_boundaries": [{
                "component": {"id": 100, "label": "Component", "properties": {"tag": "N1", "node_id": "hilt-nozzle-1"}},
            }],
        }],
    }


def config():
    return SimpleNamespace(
        graph=object(),
        policy=IsolationPolicy(),
        approved_corrections=(correction(),),
    )


class CorrectionTargetLookupTests(unittest.TestCase):
    def test_bfs_finds_nearest_boundary_beyond_automatic_depth(self):
        adjacency = {
            217240: [10], 10: [217240, 20], 20: [10, 30], 30: [20, 40],
            40: [30, 50], 50: [40, 100], 100: [50],
        }

        def expand(frontier):
            return [(origin, neighbor) for origin in frontier for neighbor in adjacency.get(origin, [])]

        result = _bfs_nearest_sources(217240, {100}, expand, 12)
        self.assertEqual(result["depth"], 6)
        self.assertEqual(result["source_ids"], ["100"])
        self.assertEqual(result["paths"]["100"], ["217240", "10", "20", "30", "40", "50", "100"])

    @mock.patch("equipment_isolation.core.correction_targets._resolve_target_from_graph")
    def test_approved_exact_target_is_added_to_candidate_pool(self, resolve):
        resolve.return_value = {
            "status": "resolved",
            "vertex": {
                "id": 217240,
                "label": "Component",
                "properties": {
                    "node_id": TARGET,
                    "cnvrt_id": TARGET,
                    "entity_class": "wedge_type_gate_valve",
                    "type": "piping_component",
                    "tag": "1HGA30",
                },
            },
            "depth": 6,
            "source_ids": ["100"],
            "paths": {"100": ["217240", "10", "20", "30", "40", "50", "100"]},
        }
        result = enrich_approved_correction_targets({"candidates": [], "_candidate_pool": [], "debug": {}}, boundary(), config())
        self.assertEqual(len(result["_candidate_pool"]), 1)
        candidate = result["_candidate_pool"][0]
        self.assertEqual(candidate["candidate_id"], 217240)
        self.assertEqual(candidate["visual_id"], TARGET)
        self.assertEqual(candidate["traversal_depth"], 6)
        self.assertTrue(candidate["manual_target_lookup"])
        self.assertEqual(result["correction_target_resolution"][0]["status"], "resolved")

    @mock.patch("equipment_isolation.core.correction_targets._resolve_target_from_graph")
    def test_failed_or_ambiguous_lookup_does_not_fabricate_candidate(self, resolve):
        resolve.return_value = {"status": "ambiguous", "reason": "Exact target identity matched multiple UniGraph vertices."}
        result = enrich_approved_correction_targets({"candidates": [], "_candidate_pool": [], "debug": {}}, boundary(), config())
        self.assertEqual(result["_candidate_pool"], [])
        self.assertEqual(result["correction_target_resolution"][0]["status"], "ambiguous")


if __name__ == "__main__":
    unittest.main()
