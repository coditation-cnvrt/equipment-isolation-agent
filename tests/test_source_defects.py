import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock
from uuid import UUID

from pydantic import ValidationError

from equipment_isolation.api.models import (
    ReclassifySourceDefectRequest,
    ReportSourceDefectRequest,
    SourceDefectActionRequest,
)
from equipment_isolation.api.routes import claim_source_defect, confirm_source_defect, release_source_defect, report_source_defect, source_defect_policy
from equipment_isolation.api.db import _capture_source_defect_snapshot, _reconcile_current_material_defects, _defect_match, _effective_derivation_trigger, _governance_freshness_status, _governance_readiness_for_dependency, _material_source_defect_event, _new_source_defect_event, _persist_source_dependency, _plans_freshness, _source_defect_event_dict, _source_identifiers
from equipment_isolation.api.plans import PlanDomainError
from equipment_isolation.api.plans import normalized_plan_content
from equipment_isolation.api.db_models import PlanSourceDependency, SourceDataDefect, SourceDataDefectEvent
from equipment_isolation.domain.source_defects import (
    DEFECT_CATEGORIES,
    governance_status,
    match_dependency,
    policy_catalogue,
    policy_snapshot,
    validate_transition,
)


DEFECT_ID = UUID("60d75269-83fb-4498-bc76-f106cd745871")


def report_payload(**overrides):
    values = {
        "context": {
            "cnvrt_project_id": "277",
            "collection_id": "206",
            "unigraph_project_id": "15",
            "job_id": "2151",
        },
        "category": "missing_device",
        "anchor": {"anchor_type": "region", "anchor_id": "region:10,20,30,40", "facts": {"bbox": [10, 20, 30, 40], "expected_device": "isolation valve"}},
        "description": "Expected valve is absent from the source drawing",
        "evidence_refs": ["inspection:123"],
    }
    values.update(overrides)
    return ReportSourceDefectRequest(**values)


class Repository:
    def __init__(self):
        self.calls = []
        self.item = {
            "defect_id": str(DEFECT_ID),
            "version": 1,
            "context": report_payload().context.model_dump(),
            "category": "missing_device",
            "anchor": report_payload().anchor.model_dump(),
            "description": "Expected valve is absent from the source drawing",
            "state": "reported",
            "policy_snapshot": policy_snapshot("missing_device"),
            "policy_hash": policy_snapshot("missing_device")["policy_hash"],
            "reported_by": "42",
            "reported_at": "2026-09-07T00:00:00Z",
            "updated_at": "2026-09-07T00:00:00Z",
            "events": [],
            "affected_plans": [],
        }

    def list_plans(self, **_filters):
        return [], 0

    def create_source_defect(self, payload, actor):
        self.calls.append(("report", payload, actor))
        return self.item

    def get_source_defect(self, _defect_id):
        return self.item

    def transition_source_defect(self, defect_id, action, payload, actor):
        self.calls.append((action, defect_id, payload, actor))
        return {**self.item, "version": 2, "state": "confirmed"}

    def coordinate_source_defect(self, defect_id, action, payload, actor):
        self.calls.append((action, defect_id, payload, actor))
        return {**self.item, "version": payload.expected_version + 1, "claimed_by": actor if action == "claimed" else None}


class SourceDefectTests(unittest.TestCase):
    def setUp(self):
        self.repository = Repository()
        self.request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(run_store=SimpleNamespace(repository=self.repository))),
            state=SimpleNamespace(token_data={"user": {"id": "42"}}),
        )
        patcher = mock.patch("equipment_isolation.api.routes.authorize_planning_context")
        self.authorize = patcher.start()
        self.addCleanup(patcher.stop)

    def test_catalogue_and_intrinsic_policy_are_complete_and_stable(self):
        self.assertEqual(len(DEFECT_CATEGORIES), 12)
        advisory = policy_snapshot("incorrect_symbol")
        other = policy_snapshot("other")
        self.assertEqual(advisory["severity"], "advisory")
        self.assertEqual(policy_snapshot("incorrect_label")["severity"], "blocking")
        self.assertEqual(policy_snapshot("incorrect_attribute")["fallback"], "fail_closed_when_dependency_unknown")
        self.assertEqual(other["severity"], "warning")
        self.assertTrue(other["confirmation_requires_reclassification"])
        self.assertEqual(policy_snapshot("missing_device"), policy_snapshot("missing_device"))
        self.assertIn("assurance_status", advisory["excluded_effects"])
        self.assertEqual(policy_catalogue()["policy_version"], "source-defect-policy/1.0")
        self.assertEqual(source_defect_policy(), policy_catalogue())
        expected = {
            "missing_device": ("blocking", ["point", "region"], "drawing"),
            "extra_device": ("blocking", ["entity"], "exact_then_unknown_fallback"),
            "incorrect_device_type": ("blocking", ["entity"], "exact_then_unknown_fallback"),
            "incorrect_symbol": ("advisory", ["entity", "region"], "exact_then_unknown_fallback"),
            "incorrect_label": ("blocking", ["entity", "link"], "exact_then_unknown_fallback"),
            "incorrect_attribute": ("blocking", ["entity", "link"], "exact_then_unknown_fallback"),
            "missing_connection": ("blocking", ["point", "region"], "drawing"),
            "phantom_connection": ("blocking", ["link"], "exact_then_unknown_fallback"),
            "incorrect_connection": ("blocking", ["link"], "exact_then_unknown_fallback"),
            "off_page_connector_mismatch": ("blocking", ["entity", "link"], "drawing"),
            "source_revision_mismatch": ("blocking", ["region"], "source_revision"),
            "other": ("warning", ["entity", "link", "point", "region"], "drawing"),
        }
        for category, values in expected.items():
            policy = policy_snapshot(category)
            self.assertEqual((policy["severity"], policy["anchors"], policy["matching"]), values)

    def test_frontend_contract_rejects_computed_scope_and_impact(self):
        for field in ("impact", "scope", "affected_plan_ids"):
            raw = report_payload().model_dump()
            raw[field] = ["not-client-owned"]
            with self.assertRaises(ValidationError):
                ReportSourceDefectRequest(**raw)
        raw = report_payload().model_dump()
        raw["anchor"]["facts"]["impact"] = "blocking"
        with self.assertRaises(ValidationError):
            ReportSourceDefectRequest(**raw)

    def test_category_specific_anchor_facts_and_evidence_are_required(self):
        with self.assertRaisesRegex(ValidationError, "expected_device"):
            report_payload(anchor={"anchor_type": "region", "anchor_id": "r1", "facts": {}})
        with self.assertRaisesRegex(ValidationError, "evidence reference"):
            report_payload(evidence_refs=[])
        with self.assertRaisesRegex(ValidationError, "anchor types"):
            report_payload(anchor={"anchor_type": "entity", "anchor_id": "e1", "facts": {"expected_device": "valve"}})

    def test_complete_manifest_does_not_fallback_for_unrelated_exact_anchor(self):
        policy = policy_snapshot("incorrect_label")
        complete = {"manifest_status": "complete", "exact_anchor_ids": ["entity-1"]}
        incomplete = {"manifest_status": "incomplete", "exact_anchor_ids": ["entity-1"]}
        self.assertIsNone(match_dependency(policy, "entity-2", complete))
        self.assertEqual(match_dependency(policy, "entity-2", incomplete)["match_scope"], "drawing_fallback")
        self.assertEqual(match_dependency(policy, "entity-1", complete)["match_scope"], "exact")

    def test_partial_normalized_identity_manifest_collects_exact_ids_and_fails_closed(self):
        content = normalized_plan_content(
            {
                "equipment_tag": "P-101",
                "selected_asset": {"hilt_entity_id": "equipment-101", "tag": "P-101"},
            },
            {"data": [{
                "assurance_status": "not_isolated",
                "isolation_points": [{
                    "uuid": "valve-candidate-1",
                    "drawing_entity_id": "hilt-valve-1",
                    "branch_id": "suction",
                    "branch_path_node_ids": ["equipment-101", "nozzle-1", "hilt-valve-1"],
                    "branch_path_link_ids": ["link-equipment-nozzle", "link-nozzle-valve"],
                }],
            }]},
        )
        identifiers = _source_identifiers(content)
        self.assertTrue({
            "equipment-101", "nozzle-1", "hilt-valve-1", "valve-candidate-1",
            "link-equipment-nozzle", "link-nozzle-valve",
        }.issubset(identifiers))
        dependency = {"manifest_status": "incomplete", "exact_anchor_ids": sorted(identifiers)}
        policy = policy_snapshot("incorrect_label")
        self.assertEqual(match_dependency(policy, "link-nozzle-valve", dependency)["match_scope"], "exact")
        fallback = match_dependency(policy, "unrepresented-drawing-entity", dependency)
        self.assertEqual(fallback["match_scope"], "drawing_fallback")
        self.assertEqual(fallback["resolution"], "dependency_unknown_fail_closed")

        session = mock.MagicMock()
        session.scalars.return_value.all.return_value = []
        session.execute.return_value.all.return_value = []
        request = {
            "cnvrt_project_id": "277", "collection_id": "206",
            "unigraph_project_id": "15", "job_id": "2151",
        }
        request["_source_defect_snapshot"] = _capture_source_defect_snapshot(session, request)
        session.scalars.return_value.all.return_value = []
        _persist_source_dependency(
            session,
            SimpleNamespace(plan_version_id=UUID("4bb4be1a-2fef-4a32-ad98-138873199ba7")),
            request,
            content,
        )
        persisted = session.add.call_args.args[0]
        self.assertIsInstance(persisted, PlanSourceDependency)
        self.assertEqual(persisted.manifest_status, "incomplete")
        self.assertIn("link-nozzle-valve", persisted.exact_anchor_ids)
        self.assertFalse(persisted.provenance["identity_manifest_exhaustive"])
        self.assertIn(
            "pg_advisory_xact_lock",
            str(session.execute.call_args_list[0].args[0]),
        )
        unmatched_defect = SimpleNamespace(
            category="incorrect_label",
            policy_snapshot=policy,
            anchor_id="unrepresented-drawing-entity",
            anchor_facts={},
        )
        self.assertEqual(_defect_match(unmatched_defect, persisted)["match_scope"], "drawing_fallback")

    def test_revision_matching_uses_known_provenance_and_unknown_fallback(self):
        policy = policy_snapshot("source_revision_mismatch")
        facts = {"observed_revision": "A", "expected_revision": "B"}
        self.assertEqual(match_dependency(policy, "drawing", {"manifest_status": "complete", "verified_source_revision": "A"}, facts)["match_scope"], "source_revision")
        self.assertIsNone(match_dependency(policy, "drawing", {"manifest_status": "complete", "verified_source_revision": "B"}, facts))
        self.assertEqual(match_dependency(policy, "drawing", {"manifest_status": "historical_unknown"}, facts)["resolution"], "historical_revision_unknown")
        label_policy = policy_snapshot("incorrect_label")
        self.assertEqual(match_dependency(label_policy, "entity-1", {"manifest_status": "complete", "exact_anchor_ids": ["entity-1"]})["match_scope"], "exact")
        self.assertIsNone(match_dependency(label_policy, "entity-1", {"manifest_status": "complete", "exact_anchor_ids": []}))

    def test_plan_dependency_defect_snapshots_are_json_serializable(self):
        updated_at = datetime(2026, 9, 7, tzinfo=timezone.utc)
        defect = SimpleNamespace(
            defect_id=DEFECT_ID,
            version=2,
            category="incorrect_label",
            state="confirmed",
            policy_snapshot=policy_snapshot("incorrect_label"),
            anchor_type="entity",
            anchor_id="entity-1",
            anchor_facts={},
            description="Incorrect label",
            updated_at=updated_at,
        )
        session = mock.MagicMock()
        session.scalars.return_value.all.return_value = [defect]
        session.execute.return_value.all.return_value = []

        request = {
            "cnvrt_project_id": "277", "collection_id": "206",
            "unigraph_project_id": "15", "job_id": "2151",
        }
        request["_source_defect_snapshot"] = _capture_source_defect_snapshot(session, request)
        session.scalars.return_value.all.return_value = []
        _persist_source_dependency(
            session,
            SimpleNamespace(plan_version_id=UUID("4bb4be1a-2fef-4a32-ad98-138873199ba7")),
            request,
            {"selected_asset": {"drawing_entity_id": "entity-1"}},
        )

        persisted = session.add.call_args.args[0]
        self.assertEqual(persisted.source_defect_snapshots[0]["updated_at"], str(updated_at))
        json.dumps(persisted.source_defect_snapshots)

    def test_reporter_provenance_is_explicitly_informational(self):
        defect = SimpleNamespace(
            category="incorrect_label",
            policy_snapshot=policy_snapshot("incorrect_label"),
            anchor_id="entity-1",
            anchor_facts={},
            reported_source_revision="arbitrary-client-revision",
            reported_source_snapshot_hash="arbitrary-client-hash",
        )
        dependency = SimpleNamespace(
            manifest_status="complete",
            verified_source_revision=None,
            verified_source_snapshot_hash=None,
            exact_anchor_ids=["entity-1"],
            provenance={},
        )
        self.assertEqual(
            _defect_match(defect, dependency)["match_scope"],
            "exact",
        )

    def test_transition_policy_requires_confirmation_and_remediation_evidence(self):
        with self.assertRaisesRegex(ValueError, "evidence"):
            validate_transition(policy_snapshot("incorrect_label"), "confirm", [])
        with self.assertRaisesRegex(ValueError, "remediation requires"):
            validate_transition(policy_snapshot("incorrect_label"), "remediation_recorded", ["work-order:1"], {"summary": "Fixed"})
        with self.assertRaisesRegex(ValueError, "reclassified"):
            validate_transition(policy_snapshot("other"), "confirm", ["inspection:1"])

    def test_transition_uses_supplied_stored_policy_snapshot(self):
        stored_policy = policy_snapshot("incorrect_label")
        stored_policy["transition_requirements"]["confirm"] = {"evidence_refs": 0}
        validate_transition(stored_policy, "confirm", [])

    def test_report_and_confirm_use_exact_drawing_authorization_and_same_actor(self):
        payload = report_payload()
        report_source_defect(self.request, payload, authorization="Bearer user-token")
        confirm_source_defect(
            self.request,
            DEFECT_ID,
            SourceDefectActionRequest(expected_version=1, comment="Reviewed against source"),
            authorization="Bearer user-token",
        )
        self.assertEqual(self.repository.calls[0][2], "42")
        self.assertEqual(self.repository.calls[1][3], "42")
        expected_context = payload.context.authorization_context()
        self.authorize.assert_has_calls([
            mock.call(expected_context, "user-token", asset_system="cnvrt_drawing_entity"),
            mock.call(payload.context.model_dump(), "user-token", asset_system="cnvrt_drawing_entity"),
        ])

    def test_action_models_require_optimistic_version_and_factual_reclassification(self):
        with self.assertRaises(ValidationError):
            SourceDefectActionRequest(comment="Reviewed evidence")
        request = ReclassifySourceDefectRequest(
            expected_version=2, comment="Specific classification", category="incorrect_label",
            evidence_refs=["inspection:2"],
            anchor={"anchor_type": "entity", "anchor_id": "entity-1", "facts": {"observed_label": "XV-1", "expected_label": "XV-101"}},
        )
        self.assertEqual(request.category, "incorrect_label")

    def test_governance_status_does_not_claim_assurance(self):
        self.assertEqual(governance_status([{"state": "confirmed", "policy_snapshot": policy_snapshot("missing_device")}]), "blocked")
        self.assertEqual(governance_status([{"state": "confirmed", "policy_snapshot": policy_snapshot("incorrect_symbol")}]), "advisory")

    def test_repository_event_builder_hash_links_immutable_snapshots(self):
        defect = SourceDataDefect(
            defect_id=DEFECT_ID, version=2, category="incorrect_label", state="confirmed",
            anchor_type="entity", anchor_id="entity-1", anchor_facts={"observed_label": "old", "expected_label": "new"}, policy_snapshot=policy_snapshot("incorrect_label"),
        )
        session = mock.Mock()
        session.scalar.return_value = "previous-hash"
        event = _new_source_defect_event(
            session, defect, "confirmed", "reported", "confirmed", "42",
            {"evidence_refs": ["inspection:1"], "policy_snapshot": defect.policy_snapshot},
        )
        self.assertEqual(event.previous_hash, "previous-hash")
        self.assertRegex(event.event_hash, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(event.payload["state"], "confirmed")
        self.assertEqual(event.payload["category"], "incorrect_label")
        self.assertEqual(event.payload["anchor"]["facts"], defect.anchor_facts)

    def test_nonmaterial_version_changes_do_not_invalidate_captured_material_event(self):
        event = SimpleNamespace(event_id=DEFECT_ID, defect_version=2)
        defect = SimpleNamespace(defect_id=DEFECT_ID, version=6, state="confirmed")
        dependency = SimpleNamespace(
            source_defect_ids=[str(DEFECT_ID)], source_defect_event_ids=[str(DEFECT_ID)],
            source_defect_snapshots=[{"defect_id": str(DEFECT_ID), "state": "confirmed", "version": 2}],
        )
        changes, changed = _reconcile_current_material_defects(
            [defect], dependency, {DEFECT_ID: event}, set(), datetime.now(timezone.utc),
        )
        self.assertEqual(changes, [])
        self.assertFalse(changed)

    def test_legacy_run_does_not_capture_current_defects_at_promotion(self):
        session = mock.MagicMock()
        session.scalars.return_value.all.return_value = []
        _persist_source_dependency(session, SimpleNamespace(plan_version_id=DEFECT_ID), {}, {})
        dependency = session.add.call_args.args[0]
        self.assertEqual(dependency.manifest_status, "historical_unknown")
        self.assertEqual(dependency.source_defect_event_ids, [])

    def test_material_confirmed_impact_survives_resolution_and_reclassification(self):
        blocking = policy_snapshot("incorrect_label")
        resolved = SourceDataDefectEvent(
            event_type="resolved", from_state="remediation_recorded", to_state="resolved",
            payload={"policy_snapshot": blocking},
        )
        reclassified = SourceDataDefectEvent(
            event_type="reclassified", from_state="confirmed", to_state="confirmed",
            payload={"policy_snapshot": policy_snapshot("incorrect_symbol"), "previous_policy_snapshot": blocking},
        )
        advisory_confirmed = SourceDataDefectEvent(
            event_type="confirmed", from_state="reported", to_state="confirmed",
            payload={"policy_snapshot": policy_snapshot("incorrect_symbol")},
        )
        self.assertTrue(_material_source_defect_event(resolved))
        self.assertTrue(_material_source_defect_event(reclassified))
        self.assertTrue(_material_source_defect_event(advisory_confirmed))

    def test_confirmed_advisory_and_its_resolution_are_material(self):
        advisory = policy_snapshot("incorrect_symbol")
        confirmed = SourceDataDefectEvent(
            event_type="confirmed", from_state="reported", to_state="confirmed",
            payload={"policy_snapshot": advisory},
        )
        resolved = SourceDataDefectEvent(
            event_type="resolved", from_state="remediation_recorded", to_state="resolved",
            payload={"policy_snapshot": advisory},
        )
        reported_warning = SourceDataDefectEvent(
            event_type="reported", from_state=None, to_state="reported",
            payload={"policy_snapshot": policy_snapshot("other")},
        )
        self.assertTrue(_material_source_defect_event(confirmed))
        self.assertTrue(_material_source_defect_event(resolved))
        self.assertFalse(_material_source_defect_event(reported_warning))

    def test_historical_unknown_freshness_is_unknown_unless_fail_closed_change_exists(self):
        self.assertEqual(_governance_freshness_status(asset_changed=False, source_defects_changed=False, historical_unknown=True), "unknown")
        self.assertEqual(_governance_freshness_status(asset_changed=False, source_defects_changed=True, historical_unknown=True), "stale")
        self.assertEqual(_governance_readiness_for_dependency("advisory", historical_unknown=True, source_defects_changed=True), "blocked")
        self.assertEqual(_governance_readiness_for_dependency("ready", historical_unknown=True, source_defects_changed=False), "warning")

    def test_missing_exact_drawing_identity_is_unknown_and_not_ready(self):
        session = mock.MagicMock()
        session.execute.return_value.all.return_value = []
        session.scalars.return_value.all.return_value = []
        version_id = UUID("4bb4be1a-2fef-4a32-ad98-138873199ba7")
        freshness = _plans_freshness(session, [(version_id, {
            "cnvrt_project_id": "277", "collection_id": "206",
            "unigraph_project_id": "15", "job_id": "",
        })])[version_id]
        self.assertEqual(freshness["status"], "unknown")
        self.assertEqual(freshness["governance_readiness"], "warning")

    def test_historical_dependency_with_exact_context_is_unknown_and_warning(self):
        session = mock.MagicMock()
        session.execute.return_value.all.return_value = []
        session.scalars.return_value.all.return_value = []
        version_id = UUID("4bb4be1a-2fef-4a32-ad98-138873199ba7")
        freshness = _plans_freshness(session, [(version_id, {
            "cnvrt_project_id": "277", "collection_id": "206",
            "unigraph_project_id": "15", "job_id": "2151",
        })])[version_id]
        self.assertEqual(freshness["status"], "unknown")
        self.assertEqual(freshness["governance_readiness"], "warning")

    def test_current_material_defect_missing_from_capture_is_stale_without_impact_row(self):
        now = datetime(2026, 9, 7, tzinfo=timezone.utc)
        version_id = UUID("4bb4be1a-2fef-4a32-ad98-138873199ba7")
        defect_id = UUID("60d75269-83fb-4498-bc76-f106cd745871")
        event_id = UUID("f2ddaa35-795e-4dc8-a72d-1a330a14255f")
        policy = policy_snapshot("missing_device")
        dependency = SimpleNamespace(
            plan_version_id=version_id, manifest_status="incomplete",
            exact_anchor_ids=[], source_defect_ids=[], source_defect_event_ids=[],
            source_defect_snapshots=[],
            source_defect_event_watermark_at=now,
            verified_source_revision=None, verified_source_snapshot_hash=None,
            provenance={},
        )
        defect = SimpleNamespace(
            defect_id=defect_id, version=2, category="missing_device",
            state="confirmed", policy_snapshot=policy, anchor_type="region",
            anchor_id="region:10,20,30,40", anchor_facts={},
            description="Missing isolation valve", updated_at=now, reported_at=now,
            cnvrt_project_id="277", collection_id="206", job_id="2151",
        )
        event = SimpleNamespace(
            event_id=event_id, defect_id=defect_id, defect_version=2,
            event_type="confirmed", from_state="reported", to_state="confirmed",
            occurred_at=now, payload={"policy_snapshot": policy},
        )

        def rows(values):
            result = mock.MagicMock()
            result.all.return_value = values
            return result

        session = mock.MagicMock()
        session.execute.side_effect = [rows([]), rows([]), rows([])]
        session.scalars.side_effect = [rows([dependency]), rows([defect]), rows([event])]
        freshness = _plans_freshness(session, [(version_id, {
            "cnvrt_project_id": "277", "collection_id": "206",
            "unigraph_project_id": "15", "job_id": "2151",
        })])[version_id]
        self.assertEqual(freshness["status"], "stale")
        self.assertEqual(freshness["governance_readiness"], "blocked")
        self.assertTrue(freshness["source_data_defects_changed"])
        self.assertEqual(freshness["changes"][0]["event_id"], str(event_id))
        self.assertEqual(freshness["changes"][0]["defect"]["match_scope"], "drawing")

    def test_derivation_trigger_distinguishes_governed_input_changes(self):
        self.assertEqual(
            _effective_derivation_trigger("source_data_defects", corrections_changed=False, asset_conditions_changed=False, source_defects_changed=True),
            ("source_data_defects", ["source_data_defects"]),
        )
        self.assertEqual(
            _effective_derivation_trigger("asset_conditions", corrections_changed=False, asset_conditions_changed=True, source_defects_changed=False)[0],
            "asset_conditions",
        )
        self.assertEqual(
            _effective_derivation_trigger("source_data_defects", corrections_changed=True, asset_conditions_changed=True, source_defects_changed=True)[0],
            "combined",
        )
        with self.assertRaisesRegex(PlanDomainError, "No material source-data defect"):
            _effective_derivation_trigger("source_data_defects", corrections_changed=False, asset_conditions_changed=True, source_defects_changed=False)

    def test_any_scoped_actor_may_claim_and_release(self):
        claim_source_defect(
            self.request, DEFECT_ID,
            SourceDefectActionRequest(expected_version=1, comment="Coordinating review"),
            authorization="Bearer user-token",
        )
        self.request.state.token_data = {"user": {"id": "84"}}
        release_source_defect(
            self.request, DEFECT_ID,
            SourceDefectActionRequest(expected_version=2, comment="Releasing coordination"),
            authorization="Bearer other-token",
        )
        self.assertEqual(self.repository.calls[-2][3], "42")
        self.assertEqual(self.repository.calls[-1][3], "84")

    def test_sse_event_uses_historical_snapshot_not_current_defect_values(self):
        event = SourceDataDefectEvent(
            event_id=UUID("a43e49c1-389a-4c07-a5f1-af25496af860"),
            event_type="confirmed", defect_id=DEFECT_ID, defect_version=2,
            from_state="reported", to_state="confirmed", actor_id="42",
            payload={"state": "confirmed", "category": "incorrect_label"},
            previous_hash="hash-1", event_hash="hash-2",
        )
        current = SourceDataDefect(defect_id=DEFECT_ID, state="resolved", category="incorrect_symbol")
        item = _source_defect_event_dict(event, current)
        self.assertEqual(item["state"], "confirmed")
        self.assertEqual(item["category"], "incorrect_label")


if __name__ == "__main__":
    unittest.main()
