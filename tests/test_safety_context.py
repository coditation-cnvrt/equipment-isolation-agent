from copy import deepcopy
from datetime import datetime, timezone
from dataclasses import replace
import unittest
from uuid import uuid4

from equipment_isolation.domain.controlled_inputs import ControlledInputError, content_hash
from equipment_isolation.domain.safety_inputs import FrozenJSON, compose_sic, ConfigurationFloor
from equipment_isolation.domain.safety_context import ControlledInputRef, SafetyContext
from equipment_isolation.domain.source_snapshots import GraphSnapshot
from equipment_isolation.integrations.graph_snapshots import capture_hilt_export, capture_unigraph_export
from equipment_isolation.integrations.safety_input_adapters import psd_from_mock, sic_from_mock
from tests.test_safety_inputs import fixture, work_scope, delta
from tests.test_isolation_standard import _approved_fhr

CONTEXT = {"cnvrt_project_id": "277", "collection_id": "206", "unigraph_project_id": "21", "job_id": "2151"}
NOW = datetime(2026,9,8,7,tzinfo=timezone.utc)


def hilt():
    return {"hilt_graph": {"nodes": [{"id": "E", "payload": {"entity_type": "equipment"}},
        {"id": "V", "payload": {"entity_type": "component"}}],
        "links": [{"id": "L1", "source": "E", "target": "V", "payload": {"service_code": "CDH"}},
                  {"id": "L2", "source": "E", "target": "V", "payload": {"service_code": "SWS"}}]}}


def snapshot():
    return capture_hilt_export(hilt(), planning_context=CONTEXT, captured_at=NOW)


def safety_context():
    sic, composition = compose_sic(sic_from_mock(fixture("sic")))
    return SafetyContext(FrozenJSON.from_dict(CONTEXT), NOW, work_scope(), sic, composition,
        psd_from_mock(fixture("psd")), (snapshot(),))


class SafetyContextTests(unittest.TestCase):
    def test_graph_capture_preserves_parallel_edges_and_source_facts(self):
        source = hilt()
        captured = capture_hilt_export(source, planning_context=CONTEXT, captured_at=NOW, source_revision="v1")
        edges = captured.to_dict()["graph"]["edges"]
        self.assertEqual([row["id"] for row in edges], ["L1", "L2"])
        self.assertEqual(edges[1]["record"]["payload"]["service_code"], "SWS")
        source["hilt_graph"]["links"][0]["payload"]["service_code"] = "CHANGED"
        self.assertEqual(edges[0]["record"]["payload"]["service_code"], "CDH")
        self.assertIn("hilt_provider_consistency_unverified", captured.blockers)

    def test_graph_permutations_and_audit_time_have_stable_topology_hash(self):
        original = snapshot()
        source = hilt()
        source["hilt_graph"]["nodes"].reverse()
        source["hilt_graph"]["links"].reverse()
        shuffled = capture_hilt_export(source, planning_context=CONTEXT, captured_at=NOW)
        self.assertEqual(original.content_hash, shuffled.content_hash)
        later = capture_hilt_export(source, planning_context=CONTEXT, captured_at=NOW.replace(hour=8))
        self.assertEqual(original.graph_hash, later.graph_hash)
        self.assertNotEqual(original.content_hash, later.content_hash)

    def test_dangling_endpoint_remains_visible(self):
        source = hilt()
        source["hilt_graph"]["links"][0]["target"] = "absent"
        captured = capture_hilt_export(source, planning_context=CONTEXT, captured_at=NOW)
        self.assertEqual(len(captured.to_dict()["graph"]["edges"]), 2)
        self.assertIn("hilt_unresolved_endpoint:L1:target", captured.blockers)

    def test_bad_graphs_do_not_silently_collapse(self):
        for mutate in (
            lambda p: p["hilt_graph"]["nodes"].append(deepcopy(p["hilt_graph"]["nodes"][0])),
            lambda p: p["hilt_graph"]["links"][0].pop("id"),
            lambda p: p["hilt_graph"]["links"][0]["payload"].update({"from": "different"}),
            lambda p: p.update(graph={}),
        ):
            source=hilt()
            mutate(source)
            with self.assertRaises(ControlledInputError):
                capture_hilt_export(source, planning_context=CONTEXT, captured_at=NOW)

    def test_unigraph_normalized_export_preserves_edges(self):
        source = {"nodes": [{"T.id": 1, "T.label": "Equipment"}, {"id": 2, "label": "Component"}],
            "edges": [{"edge_id": "e1", "edge_label": "CONNECTED_TO", "from_node_id": 1, "to_node_id": 2,
                       "properties": {"pressure_barg": 25, "service_code": "CDH"}}]}
        captured = capture_unigraph_export(source, planning_context=CONTEXT, captured_at=NOW)
        self.assertEqual(captured.to_dict()["graph"]["edges"][0]["source"], "1")
        self.assertIn("unigraph_coverage_unverified", captured.blockers)
        source["nodes"][0]["id"] = 99
        with self.assertRaises(ControlledInputError):
            capture_unigraph_export(source, planning_context=CONTEXT, captured_at=NOW)

    def test_context_is_reproducible_but_cannot_execute(self):
        ctx = safety_context()
        self.assertEqual(ctx.content_hash, safety_context().content_hash)
        projected=ctx.to_dict()
        projected["sic"]["parameters"]["plant_state"]["validity_hours"] = 999
        self.assertEqual(ctx.sic.to_dict()["parameters"]["plant_state"]["validity_hours"], 24)
        self.assertIn("synthetic_input", ctx.blockers)
        self.assertIn("fhr_revision_missing", ctx.blockers)
        self.assertIn("unigraph_snapshot_missing", ctx.blockers)
        with self.assertRaises(ControlledInputError):
            ctx.require_executable()

    def test_context_rejects_scope_and_composition_mismatch(self):
        ctx = safety_context()
        wrong = {**CONTEXT, "job_id": "other"}
        with self.assertRaises(ControlledInputError):
            replace(ctx, planning_context=FrozenJSON.from_dict(wrong))
        composition=ctx.sic_composition.to_dict()
        composition["effective_hash"]="0"*64
        with self.assertRaises(ControlledInputError):
            replace(ctx, sic_composition=FrozenJSON.from_dict(composition))
        with self.assertRaises(ControlledInputError):
            replace(ctx, graph_snapshots=(snapshot(), snapshot()))
        later = capture_hilt_export(hilt(), planning_context=CONTEXT, captured_at=NOW.replace(hour=8))
        self.assertIn("graph_capture_after_plan_time", replace(ctx, graph_snapshots=(later,)).blockers)

    def test_controlled_reference_binds_payload_hash_and_context(self):
        payload = _approved_fhr()
        revision = dict(input_type="fhr", input_id=str(uuid4()), revision_id=str(uuid4()), revision_label="1",
            schema_version="fhr-v1", content_hash=content_hash(payload), decision="approved", decided_by="repository-reviewer",
            decided_at="2026-09-08T06:00:00Z", payload=payload,
            scope={key: CONTEXT[key] for key in ("cnvrt_project_id", "collection_id", "job_id")})
        ref=ControlledInputRef.from_revision(revision)
        self.assertEqual(ref.to_dict()["revision_id"], revision["revision_id"])
        ctx=replace(safety_context(), fhr_revision=FrozenJSON.from_dict(revision))
        self.assertNotIn("fhr_revision_missing",ctx.blockers)
        with self.assertRaises(ControlledInputError):
            replace(ctx, fhr_revision=FrozenJSON.from_dict({**revision,"content_hash":"0"*64}))
        with self.assertRaises(ControlledInputError):
            ControlledInputRef.from_revision({**revision,"decision":"pending"})

    def test_configuration_floors_are_preserved_and_cannot_be_weakened(self):
        base=sic_from_mock(fixture("sic"))
        floor=ConfigurationFloor.from_dict({"hsc":2,"ec":"B","rule_id":"PATTERN-FLOOR-1","source_hash":"a"*64,
            "configuration":{"barrier_count":2,"bleed_required":True,"positive_barrier_count":1,
                "physical_disconnection_required":False,"both_sides_blinded_required":False}})
        _, trace=compose_sic(base,floors=(floor,))
        self.assertEqual(trace.to_dict()["non_overridable_floors"],[floor.to_dict()])
        row={"hsc":2,"ec":"B","configuration":{**floor.to_dict()["configuration"],"positive_barrier_count":0},
            "justification":"Unapproved example","approver_reference":"imported-claim"}
        with self.assertRaises(ControlledInputError):
            compose_sic(base,delta(base,{"/matrix_overrides":[row]}),floors=(floor,))

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(ControlledInputError):
            FrozenJSON(b'{"identity":1,"identity":2}')

    def test_snapshot_constructor_rejects_forged_normalized_topology(self):
        data = snapshot().to_dict()
        data["graph"]["edges"][0]["target"] = "invented"
        with self.assertRaises(ControlledInputError):
            GraphSnapshot.from_dict(data)

    def test_selected_asset_requires_structural_equipment_identity(self):
        ctx = safety_context()
        ctx = replace(ctx, selected_asset=FrozenJSON.from_dict({"hilt_entity_id": "V", "unigraph_vertex_id": "1"}))
        self.assertIn("selected_asset_not_equipment:hilt", ctx.blockers)
        ctx = replace(ctx, selected_asset=FrozenJSON.from_dict({"hilt_entity_id": "E", "unigraph_vertex_id": "1"}))
        self.assertNotIn("selected_asset_not_equipment:hilt", ctx.blockers)
        self.assertIn("asset_identity_reconciliation_not_integrated", ctx.blockers)

    def test_unvalidated_delta_cannot_bypass_editable_paths(self):
        base = sic_from_mock(fixture("sic"))
        patch = delta(base, {"/parameters/plant_state/validity_hours": 12}).to_dict()
        patch["changes"] = {"/synthetic": False}
        with self.assertRaises(ControlledInputError):
            compose_sic(base, FrozenJSON.from_dict(patch))
