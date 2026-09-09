"""Opt-in repository regressions; use a migrated disposable eia_test_* database.

Set EIA_TEST_POSTGRES_HOST to a local Unix socket directory and optionally
EIA_TEST_POSTGRES_PORT, EIA_TEST_POSTGRES_DB, EIA_TEST_POSTGRES_USER.
Ordinary unittest discovery remains offline.
"""
from tests.run_request_fixtures import run_request
import getpass
import os
import time
import unittest
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from equipment_isolation.api.database import PostgresConfig
from equipment_isolation.api.db import PostgresRunRepository
from equipment_isolation.api.db_models import DerivationManifest, PlanSourceDependency
from equipment_isolation.api.models import ReportSourceDefectRequest, SourceDefectActionRequest, RecordSourceDefectRemediationRequest, ReclassifySourceDefectRequest


@unittest.skipUnless(os.environ.get("EIA_TEST_POSTGRES_HOST"), "requires explicit disposable PostgreSQL")
class SourceDefectPostgresTests(unittest.TestCase):
    def setUp(self):
        host = os.environ["EIA_TEST_POSTGRES_HOST"]
        dbname = os.environ.get("EIA_TEST_POSTGRES_DB", "eia_test_review")
        if not host.startswith("/tmp/") or not dbname.startswith("eia_test_"):
            raise RuntimeError("Use a disposable /tmp Unix socket and eia_test_* database")
        self.repo = PostgresRunRepository(PostgresConfig(host, int(os.environ.get("EIA_TEST_POSTGRES_PORT", "5432")), dbname, os.environ.get("EIA_TEST_POSTGRES_USER", getpass.getuser()), "", "disable"))
        self.addCleanup(self.repo.close)
        self.repo.check_ready()
        self.context = dict(cnvrt_project_id="277", collection_id="206", unigraph_project_id="15", job_id=str(uuid4().int))

    def test_historical_plan_is_readable_but_cannot_start_legacy_derivation(self):
        from equipment_isolation.api.plans import PlanDomainError
        record = self.start_run(dict(self.context, equipment_tag='P1'))
        self.finish_run(record)
        plan = self.repo.create_plan_from_run(record.run_id)[0]
        with self.assertRaises(PlanDomainError) as caught:
            self.repo.prepare_derivation(plan['plan_id'], plan['latest_plan_version_id'], 'reviewer')
        self.assertEqual(caught.exception.kind, 'process_safety_inputs_required')
        self.assertIsNotNone(self.repo.get_run(record.run_id))
        self.assertIsNotNone(self.repo.get_plan(plan['plan_id']))
        with self.repo._session_factory() as session:
            self.assertIsNone(session.scalar(select(DerivationManifest).where(DerivationManifest.plan_id == UUID(plan['plan_id']))))

    def report(self):
        return self.repo.create_source_defect(ReportSourceDefectRequest(
            context=self.context, category="incorrect_label",
            anchor={"anchor_type": "entity", "anchor_id": "V1", "facts": {"observed_label": "old", "expected_label": "new"}},
            description="Incorrect source label", evidence_refs=["drawing:1"],
        ), "reporter")

    def action(self, defect, action):
        body = dict(expected_version=defect["version"], comment="Review drawing evidence", evidence_refs=["drawing:1"])
        if action == "remediation_recorded":
            payload = RecordSourceDefectRemediationRequest(**body, remediation={"summary": "Drawing fixed", "reference": "fix:1"})
        else:
            payload = SourceDefectActionRequest(**body)
        return self.repo.transition_source_defect(defect["defect_id"], action, payload, "reviewer")

    def start_run(self, request=None):
        record = SimpleNamespace(run_id=uuid4().hex, equipment_tag="P1", runner="agentic", status="queued", created_at=time.time(), started_at=None, finished_at=None, agent=None, result=None, trace=None, error=None)
        self.repo.insert_run(record, request or run_request(**self.context, equipment_tag="P1").model_dump())
        return record

    def finish_run(self, record):
        record.status = "succeeded"
        record.finished_at = time.time()
        record.result = {"data": [{"assurance_status": "not_isolated"}]}
        self.repo.update_run(record)

    def plan(self):
        record = self.start_run()
        self.finish_run(record)
        return self.repo.create_plan_from_run(record.run_id)[0]

    def test_comments_evidence_and_claims_do_not_make_plan_stale(self):
        defect = self.action(self.report(), "confirm")
        plan = self.plan()
        self.assertEqual(plan["freshness"]["status"], "fresh")
        for action in ("commented", "evidence_added", "claimed", "released"):
            payload = SourceDefectActionRequest(expected_version=defect["version"], comment="Coordination only", evidence_refs=["drawing:1"])
            operation = self.repo.coordinate_source_defect if action in {"claimed", "released"} else self.repo.annotate_source_defect
            defect = operation(defect["defect_id"], action, payload, "reviewer")
            self.assertEqual(self.repo.get_plan(plan["plan_id"])["freshness"]["status"], "fresh", action)

    def test_locked_derivation_remains_stale_when_defect_resolves_during_run(self):
        plan = self.plan()
        defect = self.action(self.report(), "confirm")
        prepared = self.repo.prepare_derivation(plan["plan_id"], plan["latest_plan_version_id"], "reviewer", "source_data_defects")
        with self.repo._session_factory() as session:
            locked = session.get(DerivationManifest, UUID(prepared["manifest_id"])).trigger_snapshot["source_dependency_snapshot"]
        record = self.start_run(prepared["request"])
        # Runtime request refreshes must retain the server checkpoint.
        self.repo.update_run_request(record.run_id, {**prepared["request"], "_source_defect_snapshot": {"forged": True}})
        defect = self.action(self.action(defect, "remediation_recorded"), "resolve")
        self.finish_run(record)
        child = self.repo.get_plan(plan["plan_id"])
        self.assertEqual(child["freshness"]["status"], "stale")
        with self.repo._session_factory() as session:
            dependency = session.get(PlanSourceDependency, UUID(child["latest_plan_version_id"]))
            self.assertEqual(dependency.source_defect_event_ids, locked["event_ids"])
            self.assertNotIn(defect["events"][-1]["event_id"], dependency.source_defect_event_ids)
        # A new derivation consuming that resolution is fresh.
        next_derivation = self.repo.prepare_derivation(child["plan_id"], child["latest_plan_version_id"], "reviewer", "source_data_defects")
        next_record = self.start_run(next_derivation["request"])
        self.finish_run(next_record)
        self.assertEqual(self.repo.get_plan(plan["plan_id"])["freshness"]["status"], "fresh")

    def test_initial_run_does_not_absorb_defect_opened_and_closed_before_promotion(self):
        record = self.start_run({**self.context, "_source_defect_snapshot": {"forged": True}})
        defect = self.action(self.report(), "confirm")
        self.action(self.action(defect, "remediation_recorded"), "resolve")
        self.finish_run(record)
        plan = self.repo.create_plan_from_run(record.run_id)[0]
        self.assertEqual(plan["freshness"]["status"], "stale")
        self.assertTrue(plan["freshness"]["source_data_defects_changed"])

    def test_report_and_reclassification_events_retain_immutable_anchor_facts(self):
        defect = self.report()
        original = defect["events"][0]
        self.assertEqual(original["payload"]["anchor"]["facts"]["expected_label"], "new")
        defect = self.repo.reclassify_source_defect(defect["defect_id"], ReclassifySourceDefectRequest(
            expected_version=defect["version"], comment="Correct region anchor", evidence_refs=["drawing:2"], category="missing_device",
            anchor={"anchor_type": "region", "anchor_id": "region:1,2,3,4", "facts": {"bbox": [1, 2, 3, 4], "expected_device": "valve"}},
        ), "reviewer")
        self.assertEqual(defect["events"][0], original)
        latest = defect["events"][-1]
        self.assertEqual(latest["payload"]["anchor"]["facts"]["bbox"], [1, 2, 3, 4])
        self.assertEqual(latest["previous_hash"], original["event_hash"])
        with self.assertRaises(DBAPIError):
            with self.repo._engine.begin() as connection:
                connection.execute(text("UPDATE source_data_defect_event SET payload = '{}'::jsonb WHERE event_id = :id"), {"id": original["event_id"]})
