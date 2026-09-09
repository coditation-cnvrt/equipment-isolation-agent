import unittest
from dataclasses import replace

from equipment_isolation.core.boundary import _walk_component_topology
from equipment_isolation.config import IsolationPolicy


def vertex(identifier, entity_class):
    return {
        "id": identifier,
        "label": "Component",
        "entity_class": entity_class,
        "tag": identifier,
    }


def expander(adjacency):
    def expand(vertex_ids):
        return {
            str(identifier): [
                {"vertex": vertex(target, entity_class), "edge_label": "HAS_A"}
                for target, entity_class in adjacency.get(str(identifier), [])
            ]
            for identifier in vertex_ids
        }

    return expand


def fact_expander(adjacency):
    def expand(vertex_ids):
        return {
            str(identifier): [
                {
                    "vertex": {
                        **vertex(item["target"], item["entity_class"]),
                        **(item.get("properties") or {}),
                    },
                    "edge_label": "PHYSICALLY_CONNECTED_TO",
                    "edge_fact": {
                        "edge_id": item["edge_id"],
                        "edge_label": "PHYSICALLY_CONNECTED_TO",
                        "from_node_id": str(identifier),
                        "to_node_id": item["target"],
                        "properties": item.get("edge_properties") or {},
                    },
                }
                for item in adjacency.get(str(identifier), [])
            ]
            for identifier in vertex_ids
        }

    return expand


class UniGraphTopologyTests(unittest.TestCase):
    def test_ordered_edge_and_node_facts_are_preserved(self):
        adjacency = {
            "S": [
                {
                    "target": "P",
                    "entity_class": "pipe",
                    "edge_id": "E1",
                    "properties": {"fluid_code": "CDH", "operating_pressure": 18},
                    "edge_properties": {"connection_kind": "process"},
                }
            ],
            "P": [
                {
                    "target": "V",
                    "entity_class": "gate_valve",
                    "edge_id": "E2",
                    "properties": {"line_specification": "CS150"},
                }
            ],
        }

        samples, branches, hit_limit = _walk_component_topology(
            "S", fact_expander(adjacency), IsolationPolicy(), set()
        )

        self.assertFalse(hit_limit)
        barrier = samples[-1]
        self.assertEqual(barrier["graph_path_edge_ids"], ["E1", "E2"])
        self.assertEqual(barrier["graph_path_edge_facts"][0]["properties"], {"connection_kind": "process"})
        self.assertEqual(barrier["graph_path_node_facts"][1]["properties"]["fluid_code"], "CDH")
        self.assertEqual(barrier["graph_path_node_facts"][2]["properties"]["line_specification"], "CS150")
        self.assertEqual(branches[0]["path_edge_ids"], ["E1", "E2"])
        self.assertEqual(branches[0]["branch_id"], "unigraph:S>P>V|edges:E1>E2")

    def test_parallel_edges_survive_candidate_and_plan_projection(self):
        from equipment_isolation.config import RunConfig
        from equipment_isolation.core.candidates import _candidate_from_vertex, _dedupe_candidates
        from equipment_isolation.presentation.bbox_util import _dedupe_candidates as dedupe_visual
        from equipment_isolation.presentation.payload import build_final_payload
        from equipment_isolation.api.plans import normalized_plan_content
        adjacency = {"S": [
            {"target": "V", "entity_class": "gate_valve", "edge_id": edge, "edge_properties": {"fluid_code": code}}
            for edge, code in (("E1", "CW"), ("E2", "PROCESS"))
        ]}
        policy = IsolationPolicy()
        samples, _, _ = _walk_component_topology("S", fact_expander(adjacency), policy)
        candidates = [_candidate_from_vertex("P1", "S", "S", {}, item, "adaptive component path", policy) for item in samples]
        candidates = dedupe_visual(_dedupe_candidates(candidates))
        self.assertEqual(len(candidates), 1)
        result = build_final_payload({"candidates": candidates, "assurance_status": "not_isolated"}, RunConfig(equipment_tag="P1"))
        branches = normalized_plan_content({}, result)["branches"]
        self.assertEqual({tuple(branch["path_edge_ids"]) for branch in branches}, {("E1",), ("E2",)})
        self.assertEqual({branch["path_edge_facts"][0]["properties"]["fluid_code"] for branch in branches}, {"CW", "PROCESS"})

    def test_unavailable_barrier_is_passed_and_next_barrier_is_selected(self):
        adjacency = {
            "S": [("U", "gate_valve")],
            "U": [("S", "nozzle"), ("V", "gate_valve")],
            "V": [("U", "gate_valve")],
        }

        samples, branches, hit_limit = _walk_component_topology(
            "S", expander(adjacency), IsolationPolicy(), {"U"}
        )

        self.assertFalse(hit_limit)
        self.assertEqual([sample["graph_path_status"] for sample in samples], ["unavailable_pass_through", "barrier"])
        self.assertEqual(len(branches), 1)
        self.assertEqual(branches[0]["status"], "isolated")
        self.assertEqual(branches[0]["barrier_id"], "V")
        self.assertEqual(branches[0]["path_node_ids"], ["S", "U", "V"])

    def test_split_paths_each_require_their_own_first_barrier(self):
        adjacency = {
            "S": [("J", "pipe")],
            "J": [("S", "nozzle"), ("V1", "gate_valve"), ("V2", "blind")],
        }

        _samples, branches, hit_limit = _walk_component_topology(
            "S", expander(adjacency), IsolationPolicy(), set()
        )

        self.assertFalse(hit_limit)
        self.assertEqual({branch["barrier_id"] for branch in branches}, {"V1", "V2"})
        self.assertTrue(all(branch["status"] == "isolated" for branch in branches))

    def test_terminal_without_barrier_is_unresolved(self):
        adjacency = {"S": [("P", "pipe")], "P": [("S", "nozzle")]}

        _samples, branches, hit_limit = _walk_component_topology(
            "S", expander(adjacency), IsolationPolicy(), set()
        )

        self.assertFalse(hit_limit)
        self.assertEqual(branches[0]["status"], "unresolved")
        self.assertEqual(branches[0]["reason"], "terminal_without_barrier")

    def test_safety_ceiling_never_implies_isolation(self):
        adjacency = {"S": [("U", "gate_valve")], "U": [("V", "gate_valve")]}
        policy = replace(IsolationPolicy(), max_traversal_depth=1)

        _samples, branches, hit_limit = _walk_component_topology(
            "S", expander(adjacency), policy, {"U"}
        )

        self.assertTrue(hit_limit)
        self.assertEqual(branches[0]["status"], "unresolved")
        self.assertEqual(branches[0]["reason"], "safety_limit_reached")


if __name__ == "__main__":
    unittest.main()
