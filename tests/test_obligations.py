import unittest

from equipment_isolation.core.obligations import analyze_isolation_obligations


class ObligationTests(unittest.TestCase):
    def test_selected_source_is_isolated_and_extra_candidate_is_manual_check(self):
        data = analyze_isolation_obligations(
            {
                "candidates": [{"candidate_id": "valve-1"}],
                "_candidate_pool": [
                    _candidate("source-1", "valve-1", [10, 10, 20, 20]),
                    _candidate("source-1", "valve-2", [40, 10, 20, 20]),
                ],
                "debug": {
                    "bbox_source_visual_selection_samples": [
                        {
                            "equipment_tag": "EQ-1",
                            "source_component": "source-1",
                            "source_component_tag": "N1_EQ1",
                            "selected_candidate_ids": ["valve-1"],
                        }
                    ]
                },
            },
            config=None,
        )

        result = data["isolation_obligations"]
        self.assertEqual(result["summary"]["process_obligation_count"], 1)
        self.assertEqual(result["summary"]["isolated_count"], 1)
        self.assertEqual(result["summary"]["unresolved_count"], 0)
        self.assertEqual(result["summary"]["manual_candidate_count"], 1)
        self.assertEqual(result["items"][0]["manual_candidates"][0]["uuid"], "valve-2")

    def test_hilt_branch_obligations_are_first_class_and_exclude_selected_visual_ids(self):
        data = analyze_isolation_obligations(
            {
                "candidates": [
                    {"candidate_id": "uuid-valve-1", "visual_id": "uuid-valve-1"},
                    {"candidate_id": "uuid-valve-2", "visual_id": "uuid-valve-2"},
                ],
                "_candidate_pool": [
                    _candidate("source-1", "graph-valve-1", [10, 10, 20, 20], visual_id="uuid-valve-1"),
                    _candidate("source-1", "graph-valve-2", [40, 10, 20, 20], visual_id="uuid-valve-2"),
                    _candidate("source-1", "extra-valve", [80, 10, 20, 20]),
                ],
                "hilt_branch_obligations": [
                    {
                        "equipment_tag": "EQ-1",
                        "source_component": "source-1",
                        "source_component_tag": "N1_EQ1",
                        "source_visual_id": "source-uuid",
                        "branches": [
                            {"status": "isolated", "branch_id": "b1", "valve": {"valve_id": "uuid-valve-1"}, "basis": "first branch valve"},
                            {"status": "isolated", "branch_id": "b2", "valve": {"valve_id": "uuid-valve-2"}, "basis": "first branch valve"},
                        ],
                    }
                ],
                "debug": {},
            },
            config=None,
        )

        result = data["isolation_obligations"]
        self.assertEqual(result["summary"]["process_obligation_count"], 2)
        self.assertEqual(result["summary"]["isolated_count"], 2)
        self.assertEqual(result["summary"]["manual_candidate_count"], 0)
        self.assertEqual(result["items"][0]["branch_id"], "b1")
        self.assertEqual(result["items"][1]["branch_id"], "b2")
        self.assertEqual(result["items"][0]["manual_candidates"], [])
        self.assertEqual(result["items"][1]["manual_candidates"], [])

    def test_unselected_process_source_is_unresolved(self):
        data = analyze_isolation_obligations(
            {
                "_candidate_pool": [_candidate("source-2", "valve-3", [80, 10, 20, 20])],
                "debug": {
                    "bbox_unselected_source_components": [
                        {
                            "equipment_tag": "EQ-1",
                            "source_component": "source-2",
                            "source_component_tag": "N2_EQ1",
                            "source_hilt_lines": [{"entity_class": "primary_process_line"}],
                        }
                    ]
                },
            },
            config=None,
        )

        item = data["isolation_obligations"]["items"][0]
        self.assertEqual(item["status"], "unresolved")
        self.assertEqual(item["source_type"], "process")
        self.assertEqual(data["isolation_obligations"]["summary"]["unresolved_count"], 1)

    def test_unselected_context_source_is_not_process_obligation(self):
        data = analyze_isolation_obligations(
            {
                "debug": {
                    "bbox_unselected_source_components": [
                        {
                            "equipment_tag": "EQ-1",
                            "source_component": "source-3",
                            "source_component_tag": "LI-1",
                            "source_hilt_lines": [{"entity_class": "piping_to_instrument_line"}],
                        }
                    ]
                },
            },
            config=None,
        )

        item = data["isolation_obligations"]["items"][0]
        self.assertEqual(item["status"], "context")
        self.assertEqual(item["source_type"], "instrument_context")
        self.assertEqual(data["isolation_obligations"]["summary"]["process_obligation_count"], 0)

    def test_unselected_source_with_existing_selected_candidate_is_covered_not_manual(self):
        data = analyze_isolation_obligations(
            {
                "candidates": [{"candidate_id": "valve-1"}],
                "_candidate_pool": [_candidate("source-4", "valve-1", [80, 10, 20, 20])],
                "debug": {
                    "bbox_unselected_source_components": [
                        {
                            "equipment_tag": "EQ-1",
                            "source_component": "source-4",
                            "source_component_tag": "N4_EQ1",
                            "source_hilt_lines": [{"entity_class": "main_process_line"}],
                        }
                    ]
                },
            },
            config=None,
        )

        item = data["isolation_obligations"]["items"][0]
        self.assertEqual(item["status"], "isolated")
        self.assertEqual(item["selected_candidate_ids"], ["valve-1"])
        self.assertEqual(item["manual_candidates"], [])
        self.assertEqual(data["isolation_obligations"]["summary"]["unresolved_count"], 0)

    def test_unavailable_selected_valve_leaves_source_unresolved(self):
        unavailable = {
            **_candidate("source-4", "valve-1", [80, 10, 20, 20]),
            "availability_status": "unavailable",
            "available_for_isolation": False,
        }
        data = analyze_isolation_obligations(
            {
                "candidates": [unavailable],
                "_candidate_pool": [unavailable],
                "debug": {
                    "bbox_source_visual_selection_samples": [{
                        "equipment_tag": "EQ-1",
                        "source_component": "source-4",
                        "source_component_tag": "N4_EQ1",
                        "selected_candidate_ids": ["valve-1"],
                    }]
                },
            },
            config=None,
        )

        item = data["isolation_obligations"]["items"][0]
        self.assertEqual(item["status"], "unresolved")
        self.assertEqual(item["selected_candidate_ids"], [])
        self.assertEqual(item["manual_candidates"], [])

    def test_unigraph_split_paths_are_validated_independently(self):
        data = analyze_isolation_obligations(
            {
                "candidates": [{"candidate_id": "valve-a"}],
                "_candidate_pool": [
                    _candidate("source-split", "valve-a", [10, 10, 20, 20]),
                    _candidate("source-split", "valve-b", [40, 10, 20, 20]),
                ],
                "unigraph_branch_obligations": [
                    {
                        "equipment_tag": "EQ-1",
                        "source_component": "source-split",
                        "source_component_tag": "N-SPLIT",
                        "branch_id": "unigraph:a",
                        "status": "isolated",
                        "barrier_id": "valve-a",
                        "path_node_ids": ["source-split", "junction", "valve-a"],
                    },
                    {
                        "equipment_tag": "EQ-1",
                        "source_component": "source-split",
                        "source_component_tag": "N-SPLIT",
                        "branch_id": "unigraph:b",
                        "status": "isolated",
                        "barrier_id": "valve-b",
                        "path_node_ids": ["source-split", "junction", "valve-b"],
                    },
                ],
                "debug": {},
            },
            config=None,
        )

        items = data["isolation_obligations"]["items"]
        self.assertEqual([item["status"] for item in items], ["isolated", "unresolved"])
        self.assertEqual(data["isolation_obligations"]["summary"]["unresolved_count"], 1)

    def test_hilt_context_classification_prevents_graph_fallback_process_blocker(self):
        data = analyze_isolation_obligations(
            {
                "unigraph_branch_obligations": [{
                    "equipment_tag": "EQ-1",
                    "source_component": "instrument-source",
                    "source_component_tag": "PI-1",
                    "branch_id": "unigraph:instrument",
                    "status": "isolated",
                    "barrier_id": "small-valve",
                    "path_node_ids": ["instrument-source", "small-valve"],
                }],
                "boundary_context_sources": [{
                    "equipment_tag": "EQ-1",
                    "source_component": "instrument-source",
                    "source_component_tag": "PI-1",
                }],
                "debug": {},
            },
            config=None,
        )

        item = data["isolation_obligations"]["items"][0]
        self.assertEqual(item["status"], "context")
        self.assertEqual(item["source_type"], "instrument_context")
        self.assertEqual(data["isolation_obligations"]["summary"]["process_obligation_count"], 0)

    def test_connected_relief_network_is_context_not_five_process_blockers(self):
        data = analyze_isolation_obligations(
            {
                "hilt_branch_obligations": [
                    {
                        "equipment_tag": "OLAA10 BB001",
                        "source_component": "check-source",
                        "branches": [
                            {
                                "status": "unresolved",
                                "branch_id": "check:1",
                                "path_node_ids": ["N-C", "CV", "OPC"],
                                "path_node_classes": ["equipment_nozzle", "check_valve", "off_or_on_page_connector"],
                            }
                        ],
                    },
                    {
                        "equipment_tag": "OLAA10 BB001",
                        "source_component": "57512",
                        "branches": [
                            {
                                "status": "unresolved",
                                "branch_id": "57512:1",
                                "path_node_ids": ["N1", "RV", "T1", "J1", "S1", "END"],
                                "path_node_classes": ["equipment_nozzle", "pressure_or_vacuum_relief_valve", "tee", "junction", "silencer", "null_node"],
                            },
                            {
                                "status": "unresolved",
                                "branch_id": "57512:2",
                                "path_node_ids": ["N1", "RV", "T1", "J2", "T2", "N2"],
                                "path_node_classes": ["equipment_nozzle", "pressure_or_vacuum_relief_valve", "tee", "junction", "tee", "equipment_nozzle"],
                            },
                        ],
                    },
                    {
                        "equipment_tag": "OLAA10 BB001",
                        "source_component": "77880",
                        "branches": [
                            {
                                "status": "unresolved",
                                "branch_id": "77880:1",
                                "path_node_ids": ["N2", "T2", "S1", "J1"],
                                "path_node_classes": ["equipment_nozzle", "tee", "silencer", "junction"],
                            },
                            {
                                "status": "unresolved",
                                "branch_id": "77880:2",
                                "path_node_ids": ["N2", "T2", "S1", "END"],
                                "path_node_classes": ["equipment_nozzle", "tee", "silencer", "null_node"],
                            },
                            {
                                "status": "unresolved",
                                "branch_id": "77880:3",
                                "path_node_ids": ["N2", "T2", "J2", "T1", "RV", "N1"],
                                "path_node_classes": ["equipment_nozzle", "tee", "junction", "tee", "pressure_or_vacuum_relief_valve", "equipment_nozzle"],
                            },
                        ],
                    },
                ],
                "debug": {},
            },
            config=None,
        )

        obligations = data["isolation_obligations"]
        self.assertEqual(obligations["summary"]["process_obligation_count"], 1)
        self.assertEqual(obligations["summary"]["unresolved_count"], 1)
        self.assertEqual(obligations["summary"]["relief_context_count"], 5)
        self.assertEqual(obligations["summary"]["relief_source_count"], 2)
        relief_items = [item for item in obligations["items"] if item["source_type"] == "relief_context"]
        self.assertTrue(all(item["status"] == "context" for item in relief_items))
        self.assertEqual({device for item in relief_items for device in item["relief_device_ids"]}, {"RV"})

    def test_electrical_signal_line_is_context(self):
        data = analyze_isolation_obligations(
            {
                "debug": {
                    "bbox_unselected_source_components": [
                        {
                            "equipment_tag": "EQ-1",
                            "source_component": "source-5",
                            "source_component_tag": "SIG-1",
                            "source_hilt_lines": [{"entity_class": "electrical_signal_line"}],
                        }
                    ]
                },
            },
            config=None,
        )

        item = data["isolation_obligations"]["items"][0]
        self.assertEqual(item["status"], "context")
        self.assertEqual(item["source_type"], "instrument_context")


def _candidate(source, candidate_id, bbox, visual_id=None):
    return {
        "equipment_tag": "EQ-1",
        "source_component_id": source,
        "source_component_tag": source,
        "candidate_id": candidate_id,
        "visual_id": visual_id or candidate_id,
        "bbox": bbox,
        "candidate_label": "gate_valve",
        "traversal_depth": 1,
        "source_visual_distance": 1,
        "properties": {"entity_class": "gate_valve"},
    }


if __name__ == "__main__":
    unittest.main()
