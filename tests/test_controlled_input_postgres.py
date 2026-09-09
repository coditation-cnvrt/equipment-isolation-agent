"""Opt-in real PostgreSQL constraint, provenance and concurrent-transaction tests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from threading import Barrier, Event
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy import event, select, text
from sqlalchemy.exc import DBAPIError

from equipment_isolation.api.controlled_inputs import ControlledInputRepository
from equipment_isolation.api.db_models import ControlledInput, ControlledInputRevision, RunInputManifest, RunInputManifestItem
from equipment_isolation.domain.controlled_inputs import ControlledInputError, content_hash
from tests import test_source_defect_postgres as fixtures
from tests.test_isolation_standard import _approved_fhr


@unittest.skipUnless(os.environ.get("EIA_TEST_POSTGRES_HOST"), "requires explicit disposable PostgreSQL")
class ControlledInputPostgresTests(unittest.TestCase):
    start_run = fixtures.SourceDefectPostgresTests.start_run
    finish_run = fixtures.SourceDefectPostgresTests.finish_run

    def setUp(self):
        fixtures.SourceDefectPostgresTests.setUp(self)
        self.inputs = ControlledInputRepository(self.repo._session_factory)
        self.document = self.inputs.create_document("fhr", self.context, "FHR-1", "author")

    def submit(self, label="1", document=None):
        payload = _approved_fhr()
        payload["document"]["revision"] = label
        payload["fluids"][0]["revision"] = label
        return self.inputs.submit_revision((document or self.document)["input_id"], label, "fhr-v1", payload, "author")

    def approve(self, revision=None, expected=None):
        revision = revision or self.submit()
        return self.inputs.decide_revision(revision["revision_id"], "approved", "reviewer", "Reviewed source content", expected_head=expected)

    def pinned_run(self, revision):
        record = self.start_run()
        manifest = self.inputs.lock_manifest(record.run_id, {"fhr": revision["revision_id"]}, plan_time=datetime.now(timezone.utc))
        return record, manifest

    def promote(self, record):
        self.finish_run(record)
        return self.repo.create_plan_from_run(record.run_id)[0]

    def reject_sql(self, statement, **params):
        with self.assertRaises(DBAPIError), self.repo._engine.begin() as connection:
            connection.execute(text(statement), params)

    def test_submission_scope_approval_and_immutable_decisions(self):
        revision = self.submit()
        self.assertEqual(revision["decision"], "pending")  # imported 'approved' did not grant authority
        self.assertIsNone(self.inputs.get_approved_head("fhr", self.context))
        with self.assertRaises(ControlledInputError):
            self.inputs.create_document("fhr", self.context, "other-key", "author")
        with self.assertRaises(ControlledInputError):
            self.submit()
        self.reject_sql("UPDATE controlled_input_revision SET payload = '{}' WHERE revision_id = :id", id=revision["revision_id"])
        self.reject_sql("UPDATE controlled_input SET approved_revision_id = :r WHERE input_id = :d", r=revision["revision_id"], d=self.document["input_id"])
        approved = self.approve(revision)
        self.assertEqual(self.approve(revision), approved)
        with self.assertRaises(ControlledInputError):
            self.inputs.decide_revision(revision["revision_id"], "rejected", "reviewer", "different", expected_head=revision["revision_id"])
        for sql in ("UPDATE controlled_input_revision SET decision_reason = 'edit' WHERE revision_id = :id",
                    "DELETE FROM controlled_input_revision WHERE revision_id = :id"):
            self.reject_sql(sql, id=revision["revision_id"])
        self.assertEqual(self.inputs.get_approved_head("fhr", self.context)["revision_id"], approved["revision_id"])
        other = self.inputs.create_document("fhr", {**self.context, "job_id": str(uuid4().int)}, "other", "author")
        self.reject_sql("UPDATE controlled_input SET approved_revision_id = :r WHERE input_id = :d", r=approved["revision_id"], d=other["input_id"])

    def test_unsupported_sic_and_mock_remain_unapproved(self):
        sic = self.inputs.create_document("sic", {**self.context, "collection_id": str(uuid4().int)}, "SIC", "author")
        revision = self.inputs.submit_revision(sic["input_id"], "1", "sic-v1", {}, "author")
        with self.assertRaises(ControlledInputError):
            self.approve(revision)
        rejected = self.inputs.decide_revision(revision["revision_id"], "rejected", "reviewer", "Unsupported policy", expected_head=None)
        self.assertEqual(rejected["decision"], "rejected")
        payload = _approved_fhr()
        payload["document"]["status"] = "draft_mock_unapproved"
        mock = self.inputs.submit_revision(self.document["input_id"], "1", "fhr-v1", payload, "author")
        with self.assertRaises(ControlledInputError):
            self.approve(mock)
        self.assertEqual(self.inputs.get_revision(mock["revision_id"])["decision"], "pending")

    def test_manifest_hash_pins_retry_scope_and_direct_mutation_guards(self):
        revision = self.approve()
        record, manifest = self.pinned_run(revision)
        self.assertEqual(manifest["completeness"], "incomplete")
        envelope = {key: value for key, value in manifest.items() if key not in {"manifest_id", "run_id", "locked_at", "manifest_hash"}}
        envelope["items"] = [{key: value for key, value in item.items() if key != "manifest_id"} for item in envelope["items"]]
        self.assertEqual(content_hash(envelope), manifest["manifest_hash"])
        self.assertEqual(self.inputs.lock_manifest(record.run_id, {"fhr": revision["revision_id"]}, plan_time=datetime.fromisoformat(manifest["plan_time"].replace("Z", "+00:00"))), manifest)
        for sql in ("UPDATE run_input_manifest SET context = '{}' WHERE manifest_id = :id",
                    "DELETE FROM run_input_manifest WHERE manifest_id = :id",
                    "UPDATE run_input_manifest_item SET content_hash = repeat('0',64) WHERE manifest_id = :id",
                    "DELETE FROM run_input_manifest_item WHERE manifest_id = :id",
                    "INSERT INTO run_input_manifest_item SELECT * FROM run_input_manifest_item WHERE manifest_id = :id"):
            self.reject_sql(sql, id=manifest["manifest_id"])
        wrong = self.start_run({**self.context, "job_id": str(uuid4().int)})
        with self.assertRaises(ControlledInputError):
            self.inputs.lock_manifest(wrong.run_id, {"fhr": revision["revision_id"]}, plan_time=datetime.now(timezone.utc))
        self.assertIsNone(self.inputs.get_manifest(wrong.run_id))
        legacy = self.start_run()
        self.finish_run(legacy)
        with self.assertRaises(ControlledInputError):
            self.inputs.lock_manifest(legacy.run_id, {"fhr": revision["revision_id"]}, plan_time=datetime.now(timezone.utc))

    def test_unlocked_manifest_and_bad_pin_cannot_commit(self):
        revision = self.approve()
        record, manifest = self.pinned_run(revision)
        another = self.start_run()
        with self.assertRaises(DBAPIError), self.repo._session_factory.begin() as session:
            source = session.get(RunInputManifest, UUID(manifest["manifest_id"]))
            values = {column.name: getattr(source, column.name) for column in source.__table__.columns if column.name not in {"manifest_id", "locked_at", "run_id"}}
            session.add(RunInputManifest(**values, run_id=another.run_id))
        self.assertIsNone(self.inputs.get_manifest(another.run_id))
        # Intercept initial item construction to verify DB rejects forged snapshots.
        from equipment_isolation.api import controlled_inputs as module
        actual = module.RunInputManifestItem
        other_document = self.inputs.create_document("fhr", {**self.context, "job_id": str(uuid4().int)}, "other", "author")
        other_revision = self.approve(self.submit(document=other_document))
        for overrides in (
            {"approval_snapshot": {"decision": "approved", "decided_by": "forged"}},
            {"input_id": UUID(other_document["input_id"])},
            {"revision_id": UUID(other_revision["revision_id"])},
            {"content_hash": "0" * 64}, {"input_type": "sic"}, {"schema_version": "fhr-v99"},
        ):
            def forged(**kwargs):
                return actual(**{**kwargs, **overrides})
            with self.subTest(overrides=overrides), patch.object(module, "RunInputManifestItem", side_effect=forged), self.assertRaises(DBAPIError):
                self.inputs.lock_manifest(another.run_id, {"fhr": revision["revision_id"]}, plan_time=datetime.now(timezone.utc))
            self.assertIsNone(self.inputs.get_manifest(another.run_id))

    def test_approval_before_and_after_promotion_and_multiple_revisions(self):
        first = self.approve()
        early, _ = self.pinned_run(first)
        late, _ = self.pinned_run(first)
        early_plan = self.promote(early)
        second = self.approve(self.submit("2"), first["revision_id"])
        late_plan = self.promote(late)
        third = self.approve(self.submit("3"), second["revision_id"])
        for plan in (early_plan, late_plan):
            version_id = plan["latest_plan_version_id"]
            invalidations = self.inputs.list_invalidations(version_id)
            self.assertEqual({row["replacement_revision_id"] for row in invalidations}, {second["revision_id"], third["revision_id"]})
            self.assertEqual(self.inputs.freshness([version_id])[version_id]["status"], "stale")
            self.reject_sql("DELETE FROM plan_version_invalidation WHERE plan_version_id = :id", id=version_id)
        self.assertEqual(self.inputs.get_manifest(early.run_id)["items"][0]["revision_id"], first["revision_id"])
        # Retrying an old approved decision cannot reset the current head.
        self.approve(first)
        self.assertEqual(self.inputs.get_approved_head("fhr", self.context)["revision_id"], third["revision_id"])
        current, _ = self.pinned_run(third)
        current_plan = self.promote(current)
        self.assertEqual(self.inputs.freshness([current_plan["latest_plan_version_id"]])[current_plan["latest_plan_version_id"]]["status"], "incomplete")
        legacy = self.promote(self.start_run())
        self.assertEqual(self.inputs.freshness([legacy["latest_plan_version_id"]])[legacy["latest_plan_version_id"]]["status"], "historical_unknown")

    def test_child_promotion_also_reconciles_replacement(self):
        first = self.approve()
        record, _ = self.pinned_run(first)
        parent = self.promote(record)
        defect = fixtures.SourceDefectPostgresTests.report(self)
        fixtures.SourceDefectPostgresTests.action(self, defect, "confirm")
        prepared = self.repo.prepare_derivation(parent["plan_id"], parent["latest_plan_version_id"], "reviewer", "source_data_defects")
        child = self.start_run(prepared["request"])
        self.inputs.lock_manifest(child.run_id, {"fhr": first["revision_id"]}, plan_time=datetime.now(timezone.utc))
        second = self.approve(self.submit("2"), first["revision_id"])
        self.finish_run(child)
        latest = self.repo.get_plan(parent["plan_id"])
        self.assertNotEqual(latest["latest_plan_version_id"], parent["latest_plan_version_id"])
        self.assertEqual(self.inputs.list_invalidations(latest["latest_plan_version_id"])[0]["replacement_revision_id"], second["revision_id"])

    def test_concurrent_approvals_have_one_winner(self):
        first = self.approve()
        candidates = [self.submit("2"), self.submit("3")]
        barrier = Barrier(2)
        def decide(revision):
            barrier.wait(timeout=5)
            try:
                return self.approve(revision, first["revision_id"])["decision"]
            except ControlledInputError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(decide, candidates))
        self.assertCountEqual(results, ["approved", "head_changed"])

    def test_approval_transaction_rolls_back_head_decision_and_invalidation(self):
        first = self.approve()
        run, _ = self.pinned_run(first)
        plan = self.promote(run)
        second = self.submit("2")
        # Raise after both flushes, as a failing surrounding service operation would.
        from equipment_isolation.api import controlled_inputs as module
        with patch.object(module, "_revision", side_effect=RuntimeError("rollback")), self.assertRaises(RuntimeError):
            self.approve(second, first["revision_id"])
        self.assertEqual(self.inputs.get_approved_head("fhr", self.context)["revision_id"], first["revision_id"])
        self.assertEqual(self.inputs.get_revision(second["revision_id"])["decision"], "pending")
        self.assertEqual(self.inputs.list_invalidations(plan["latest_plan_version_id"]), [])

    def test_concurrent_approval_and_promotion_do_not_miss_invalidation(self):
        # Force both lock orders, holding the winner's transaction open until the
        # other operation reaches its competing statement. No timing sleeps.
        for first_operation in ("approval", "promotion"):
            with self.subTest(first_operation=first_operation):
                if first_operation == "promotion":
                    self.context["job_id"] = str(uuid4().int)
                    self.document = self.inputs.create_document("fhr", self.context, "FHR-race", "author")
                first = self.approve()
                second = self.submit("2")
                run, _ = self.pinned_run(first)
                self.finish_run(run)
                held, competing, release = Event(), Event(), Event()
                def after_execute(conn, cursor, statement, parameters, context, many):
                    hold_statement = "UPDATE controlled_input SET" if first_operation == "approval" else "INSERT INTO external_run_link"
                    if statement.startswith(hold_statement):
                        held.set()
                        if not release.wait(5):
                            raise RuntimeError("timed out releasing held transaction")
                def before_execute(conn, cursor, statement, parameters, context, many):
                    if not held.is_set():
                        return
                    if first_operation == "approval" and statement.startswith("INSERT INTO external_run_link"):
                        competing.set()
                    if first_operation == "promotion" and "FROM controlled_input " in statement and "FOR UPDATE" in statement:
                        competing.set()
                event.listen(self.repo._engine, "after_cursor_execute", after_execute)
                event.listen(self.repo._engine, "before_cursor_execute", before_execute)
                try:
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        approve = lambda: self.approve(second, first["revision_id"])
                        promote = lambda: self.repo.create_plan_from_run(run.run_id)[0]
                        winner = executor.submit(approve if first_operation == "approval" else promote)
                        try:
                            self.assertTrue(held.wait(5))
                            loser = executor.submit(promote if first_operation == "approval" else approve)
                            self.assertTrue(competing.wait(5))
                        finally:
                            release.set()
                        first_result, second_result = winner.result(timeout=10), loser.result(timeout=10)
                        plan = second_result if first_operation == "approval" else first_result
                finally:
                    release.set()
                    event.remove(self.repo._engine, "after_cursor_execute", after_execute)
                    event.remove(self.repo._engine, "before_cursor_execute", before_execute)
                self.assertEqual(len(self.inputs.list_invalidations(plan["latest_plan_version_id"])), 1)

    def test_direct_approval_without_head_and_missing_actor_cannot_commit(self):
        revision = self.submit()
        self.reject_sql("UPDATE controlled_input_revision SET decision = 'approved', decided_by = 'reviewer', decided_at = now(), decision_reason = 'reviewed' WHERE revision_id = :id", id=revision["revision_id"])
        self.assertEqual(self.inputs.get_revision(revision["revision_id"])["decision"], "pending")
        self.reject_sql("UPDATE controlled_input_revision SET decision = 'rejected', decided_at = now(), decision_reason = 'reviewed' WHERE revision_id = :id", id=revision["revision_id"])

    def test_plan_hash_and_provenance_link_remain_unchanged(self):
        from equipment_isolation.api.db_models import PlanVersion
        from equipment_isolation.api.plans import canonical_hash
        first = self.approve()
        record, _ = self.pinned_run(first)
        plan = self.promote(record)
        version_id = UUID(plan["latest_plan_version_id"])
        with self.repo._session_factory() as session:
            version = session.get(PlanVersion, version_id)
            original_hash, original_content = version.input_hash, version.content
        self.assertEqual(original_hash, canonical_hash(self.repo.get_run(record.run_id)["request"]))
        self.approve(self.submit("2"), first["revision_id"])
        with self.repo._session_factory() as session:
            version = session.get(PlanVersion, version_id)
            self.assertEqual((version.input_hash, version.content), (original_hash, original_content))
        self.reject_sql("DELETE FROM external_run_link WHERE run_id = :id", id=record.run_id)
        self.reject_sql("UPDATE external_run_link SET link_role = 'supporting' WHERE run_id = :id", id=record.run_id)

    def test_b1_sic_draft_is_validated_stored_and_still_cannot_be_approved(self):
        from equipment_isolation.integrations.safety_input_adapters import sic_from_mock
        from tests.test_safety_inputs import fixture
        payload = sic_from_mock(fixture("sic")).to_dict()
        scope = {**self.context, "collection_id": str(uuid4().int)}
        payload["context"] = {key: scope[key] for key in ("cnvrt_project_id", "collection_id")}
        document = self.inputs.create_document("sic", scope, "SIC-B1", "author")
        revision = self.inputs.submit_revision(document["input_id"], payload["revision_label"], "sic-process-v1", payload, "author")
        self.assertEqual(revision["validation"]["status"], "draft_validated")
        self.assertEqual(self.inputs.get_revision(revision["revision_id"])["payload"], payload)
        with self.assertRaises(ControlledInputError):
            self.approve(revision)
        self.assertIsNone(self.inputs.get_approved_head("sic", scope))
        with self.assertRaises(ControlledInputError):
            self.inputs.submit_revision(document["input_id"], "wrong-label", "sic-process-v1", payload, "author")
        payload["revision_label"] = "MOCK-0.2"
        payload["context"]["collection_id"] = "wrong-scope"
        with self.assertRaises(ControlledInputError):
            self.inputs.submit_revision(document["input_id"], "MOCK-0.2", "sic-process-v1", payload, "author")
