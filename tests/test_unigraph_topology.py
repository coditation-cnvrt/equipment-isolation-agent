import unittest
from dataclasses import replace

from boundary import _walk_component_topology
from config import IsolationPolicy


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


class UniGraphTopologyTests(unittest.TestCase):
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
