"""Automatic draft lifecycle checks against an explicitly disposable database."""
import os
import unittest
from unittest.mock import patch
from sqlalchemy import select, func
from equipment_isolation.api.db_models import ExternalRunLink
from tests import test_source_defect_postgres as fixtures

@unittest.skipUnless(os.environ.get('EIA_TEST_POSTGRES_HOST'), 'requires explicit disposable PostgreSQL')
class AutomaticDraftTests(unittest.TestCase):
    setUp = fixtures.SourceDefectPostgresTests.setUp
    start_run = fixtures.SourceDefectPostgresTests.start_run
    finish_run = fixtures.SourceDefectPostgresTests.finish_run

    def test_completion_creates_one_draft_and_retry_reuses_it(self):
        run = self.start_run()
        self.finish_run(run)
        plan, created = self.repo.create_plan_from_run(run.run_id)
        self.assertFalse(created)
        self.assertEqual(plan['lifecycle_state'], 'draft')
        self.assertEqual(plan['latest_version']['version_no'], 1)
        self.repo.update_run(run)
        again, created = self.repo.create_plan_from_run(run.run_id)
        self.assertFalse(created)
        self.assertEqual(again['plan_id'], plan['plan_id'])
        with self.repo._session_factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalRunLink).where(ExternalRunLink.run_id == run.run_id)), 1)

    def test_draft_failure_rolls_back_completion(self):
        run = self.start_run()
        with patch.object(self.repo, '_ensure_plan_from_run', side_effect=RuntimeError('injected failure')):
            with self.assertRaises(RuntimeError):
                self.finish_run(run)
        self.assertEqual(self.repo.get_run(run.run_id)['status'], 'queued')
        with self.repo._session_factory() as session:
            self.assertIsNone(session.scalar(select(ExternalRunLink).where(ExternalRunLink.run_id == run.run_id)))

    def test_queued_and_failed_runs_do_not_create_drafts(self):
        run = self.start_run()
        run.status = 'failed'
        self.repo.update_run(run)
        with self.repo._session_factory() as session:
            self.assertIsNone(session.scalar(select(ExternalRunLink).where(ExternalRunLink.run_id == run.run_id)))
