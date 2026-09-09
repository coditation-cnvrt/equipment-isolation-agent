import unittest

from equipment_isolation.config import IsolationPolicy
from equipment_isolation.integrations.hilt_topology import resolve_source_branch_isolation


class HiltPathFactTests(unittest.TestCase):
    def test_branch_preserves_ordered_link_identity_and_line_facts(self):
        graph = {
            "nodes": [
                _node("S", "equipment_nozzle"),
                _node("T", "tee"),
                _node("V", "gate_valve"),
            ],
            "links": [
                _link("L1", "S", "T", fluid_code="CDH"),
                _link("L2", "T", "V", fluid_code="CDH"),
            ],
        }

        branch = _resolve(graph)[0]

        self.assertEqual(branch["path_node_ids"], ["S", "T", "V"])
        self.assertEqual(branch["path_link_ids"], ["L1", "L2"])
        first_link = branch["path_link_facts"][0]
        self.assertEqual(first_link["from_node_id"], "S")
        self.assertEqual(first_link["to_node_id"], "T")
        self.assertEqual(first_link["fluid_code"], "CDH")
        self.assertEqual(first_link["service_designation"], "CO2 compressor discharge")
        self.assertEqual(first_link["line_number"], "33")
        self.assertEqual(first_link["nominal_diameter"], "50")
        self.assertEqual(first_link["line_specification"], "CS150")
        self.assertEqual(first_link["operating_pressure"], "18 barg")
        self.assertEqual(first_link["operating_temperature"], "85 C")

    def test_reverse_traversal_records_path_direction_without_changing_source_edge(self):
        graph = {
            "nodes": [_node("S", "equipment_nozzle"), _node("V", "gate_valve")],
            "links": [_link("L1", "V", "S", fluid_code="CDH")],
        }

        facts = _resolve(graph)[0]["path_link_facts"][0]

        self.assertEqual((facts["source"], facts["target"]), ("V", "S"))
        self.assertEqual((facts["from_node_id"], facts["to_node_id"]), ("S", "V"))

    def test_reconverging_paths_remain_distinct(self):
        graph = {
            "nodes": [
                _node("S", "equipment_nozzle"),
                _node("A", "tee"),
                _node("B", "tee"),
                _node("C", "junction"),
                _node("V", "gate_valve"),
            ],
            "links": [
                _link("SA", "S", "A"),
                _link("SB", "S", "B"),
                _link("AC", "A", "C"),
                _link("BC", "B", "C"),
                _link("CV", "C", "V"),
            ],
        }

        branches = _resolve(graph)

        self.assertEqual(len(branches), 2)
        self.assertEqual(
            {tuple(branch["path_link_ids"]) for branch in branches},
            {("SA", "AC", "CV"), ("SB", "BC", "CV")},
        )
        self.assertEqual({branch["valve"]["valve_id"] for branch in branches}, {"V"})

    def test_conflicting_system_and_segment_values_are_preserved_without_guessing(self):
        link = _link("L1", "S", "V", fluid_code="CDH")
        link["payload"]["piping_network_segment"]["attributes"].extend(
            [
                {"name": "tag", "value": "44"},
                {"name": "Nominal Diameter", "value": "25"},
                {"name": "Operating Pressure", "value": "19 barg"},
            ]
        )
        graph = {
            "nodes": [_node("S", "equipment_nozzle"), _node("V", "gate_valve")],
            "links": [link],
        }

        facts = _resolve(graph)[0]["path_link_facts"][0]

        self.assertIsNone(facts["line_number"])
        self.assertEqual(facts["segment_line_number"], "44")
        self.assertEqual(facts["system_line_number"], "33")
        self.assertIsNone(facts["nominal_diameter"])
        self.assertEqual(facts["segment_nominal_diameter"], "25")
        self.assertEqual(facts["system_nominal_diameter"], "50")
        self.assertIsNone(facts["operating_pressure"])
        self.assertEqual(facts["segment_operating_pressure"], "19 barg")
        self.assertEqual(facts["system_operating_pressure"], "18 barg")


class HiltPathRegressionTests(unittest.TestCase):
    def test_barrierless_cycle_is_explicit_with_or_without_another_barrier(self):
        for include_valve in (False, True):
            with self.subTest(include_valve=include_valve):
                nodes = [_node("S", "equipment_nozzle"), _node("A", "tee"), _node("B", "tee")]
                links = [_link("SA", "S", "A"), _link("AB", "A", "B"), _link("BS", "B", "S")]
                if include_valve:
                    nodes.append(_node("V", "gate_valve"))
                    links.append(_link("SV", "S", "V"))
                branches = _resolve({"nodes": nodes, "links": links})
                cycles = [b for b in branches if b["basis"] == "cycle_without_demonstrated_barrier"]
                self.assertEqual(len(cycles), 1)
                self.assertEqual(cycles[0]["status"], "unresolved")
                self.assertEqual(set(cycles[0]["path_link_ids"]), {"SA", "AB", "BS"})

    def test_source_code_conflicts_survive_hilt_extraction(self):
        from equipment_isolation.domain.isolation_standard import FluidHazardRegister, resolve_path_fluid
        from tests.test_isolation_standard import _approved_fhr
        link = _link("SV", "S", "V", fluid_code="CW")
        link["payload"]["piping_network_system"]["attributes"].append({"name": "Fluid Code", "value": "PROCESS"})
        link["payload"]["attributes"].append({"name": "Service Code", "value": "OTHER"})
        branch = _resolve({"nodes": [_node("S", "equipment_nozzle"), _node("V", "gate_valve")], "links": [link]})[0]
        result = resolve_path_fluid(branch, FluidHazardRegister.from_dict(_approved_fhr()))
        self.assertEqual(result.service_codes, ("CW", "OTHER", "PROCESS"))
        self.assertEqual(result.resolution.gap_code, "path_service_code_conflict")
        self.assertTrue(result.resolution.blocks_authorisation)

    def test_reconverging_paths_survive_candidate_payload_and_plan_projection(self):
        from equipment_isolation.config import RunConfig
        from equipment_isolation.integrations.hilt_merge import _merge_hilt_source_branches
        from equipment_isolation.presentation.payload import build_final_payload
        from equipment_isolation.api.plans import normalized_plan_content
        graph = {"nodes": [_node("S", "equipment_nozzle"), _node("A", "tee"), _node("B", "tee"), _node("C", "junction"), _node("V", "gate_valve")],
                 "links": [_link("SA", "S", "A"), _link("SB", "S", "B"), _link("AC", "A", "C"), _link("BC", "B", "C"), _link("CV", "C", "V")]}
        branches = _resolve(graph)
        candidates = _merge_hilt_source_branches([], [{"equipment_tag": "E-1", "source_component": "SRC", "source_visual_id": "S", "branches": branches}], {}, "E-1", IsolationPolicy())
        self.assertEqual(len(candidates), 1)
        result = build_final_payload({"candidates": candidates, "assurance_status": "not_isolated"}, RunConfig(equipment_tag="E-1"))
        plan = normalized_plan_content({}, result)
        self.assertEqual({tuple(b["path_link_ids"]) for b in plan["branches"]}, {("SA", "AC", "CV"), ("SB", "BC", "CV")})
        for branch in plan["branches"]:
            self.assertEqual([fact["line_id"] for fact in branch["path_link_facts"]], branch["path_link_ids"])


def _resolve(graph):
    result = resolve_source_branch_isolation(
        {"hilt_graph": graph},
        [{"equipment_tag": "E-1", "source_component_id": "SRC", "source_visual_id": "S"}],
        policy=IsolationPolicy(),
    )
    return result[0]["branches"]


def _node(node_id, entity_class):
    return {
        "id": node_id,
        "payload": {
            "id": node_id,
            "entity_type": "piping_component",
            "entity_class": entity_class,
            "attributes": [],
        },
    }


def _link(link_id, source, target, *, fluid_code=""):
    return {
        "source": source,
        "target": target,
        "payload": {
            "id": link_id,
            "source_id": link_id,
            "from": source,
            "to": target,
            "entity_type": "process_line",
            "entity_class": "primary_process_line",
            "flow": "UNKNOWN_FLOW",
            "attributes": [],
            "piping_network_system": {
                "id": "SYS-1",
                "attributes": [
                    {"name": "LineNumberAssignmentClass", "value": "33"},
                    {"name": "Nominal Diameter", "value": "50"},
                    {"name": "ServiceDesignation", "value": "CO2 compressor discharge"},
                    {"name": "Operating Pressure", "value": "18 barg"},
                    {"name": "Operating Temperature", "value": "85 C"},
                ],
            },
            "piping_network_segment": {
                "id": f"SEG-{link_id}",
                "attributes": [
                    {"name": "Fluid Code", "value": fluid_code},
                    {"name": "Line Specification", "value": "CS150"},
                ],
            },
        },
    }


if __name__ == "__main__":
    unittest.main()
