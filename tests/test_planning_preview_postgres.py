"""Real persistence checks, opted in only against an explicitly disposable DB."""
import os
import unittest
from uuid import UUID, uuid4
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from equipment_isolation.api.planning_previews import PreviewRepository, template, router
from tests import test_source_defect_postgres as source_fixtures


@unittest.skipUnless(os.environ.get('EIA_TEST_POSTGRES_HOST'), 'requires explicit disposable PostgreSQL')
class PlanningPreviewPostgresTests(unittest.TestCase):
    def setUp(self):
        source_fixtures.SourceDefectPostgresTests.setUp(self)
        self.previews = PreviewRepository(self.repo._session_factory)
        self.actor = 'preview-test-' + uuid4().hex

    def test_parent_child_exact_history_and_owner_isolation(self):
        inputs = template()['inputs']
        parent = self.previews.create(self.actor, inputs)
        inputs['work_scope']['personnel_enter_boundary'] = True
        child = self.previews.create(self.actor, inputs, UUID(parent['preview_id']))
        self.assertEqual(self.previews.read(self.actor, UUID(parent['preview_id'])), parent)
        self.assertIn('work_scope', child['comparison']['changed_inputs'])
        self.assertEqual(len(child['comparison']['changed_paths']), 5)
        self.assertEqual(len(self.previews.list(self.actor)['items']), 2)
        self.assertEqual(self.previews.list('other-' + self.actor)['items'], [])
        with self.assertRaises(HTTPException):
            self.previews.read('other-' + self.actor, UUID(parent['preview_id']))
        with self.assertRaises(HTTPException):
            self.previews.create('other-' + self.actor, inputs, UUID(parent['preview_id']))

    def test_direct_mutation_and_owner_forgery_rejected(self):
        saved = self.previews.create(self.actor, template()['inputs'])
        for sql in (
            "UPDATE planning_preview SET inputs = '{}' WHERE preview_id = :id",
            "DELETE FROM planning_preview WHERE preview_id = :id",
            "INSERT INTO planning_preview SELECT gen_random_uuid(), preview_id, 'different-owner', created_at, input_hash, result_hash, inputs, result, comparison FROM planning_preview WHERE preview_id = :id",
            "INSERT INTO planning_preview SELECT gen_random_uuid(), NULL, actor_id, created_at, input_hash, result_hash, '{}'::jsonb, '{}'::jsonb, comparison FROM planning_preview WHERE preview_id = :id",
        ):
            with self.assertRaises(DBAPIError), self.repo._engine.begin() as connection:
                connection.execute(text(sql), {'id': saved['preview_id']})
        self.assertEqual(self.previews.read(self.actor, UUID(saved['preview_id'])), saved)

    def test_insert_failure_rolls_back_entire_snapshot(self):
        from sqlalchemy import event
        def fail(connection, cursor, statement, params, context, executemany):
            if statement.startswith('INSERT INTO planning_preview'):
                raise RuntimeError('injected persistence failure')
        event.listen(self.repo._engine, 'before_cursor_execute', fail)
        try:
            with self.assertRaises(RuntimeError):
                self.previews.create(self.actor, template()['inputs'])
        finally:
            event.remove(self.repo._engine, 'before_cursor_execute', fail)
        self.assertEqual(self.previews.list(self.actor)['items'], [])

    def test_http_create_read_compare_and_reopen(self):
        app = FastAPI(); app.include_router(router)
        @app.middleware('http')
        async def authenticate_test_actor(request, call_next):
            request.state.token_data = {'user': {'id': self.actor}}
            return await call_next(request)
        with patch('equipment_isolation.api.planning_previews._repository', return_value=self.previews), TestClient(app) as client:
            inputs = client.get('/planning-previews/template').json()['inputs']
            response = client.post('/planning-previews', json={'inputs': inputs})
            self.assertEqual(response.status_code, 201, response.text)
            parent = response.json()
            inputs['plan_time'] = '2026-09-10T07:00:00Z'
            child = client.post('/planning-previews', json={'inputs': inputs, 'parent_id': parent['preview_id']})
            self.assertEqual(child.status_code, 201, child.text)
            self.assertEqual(client.get('/planning-previews/' + parent['preview_id']).json(), parent)
            self.assertEqual(len(client.get('/planning-previews').json()['items']), 2)

    def test_real_run_safety_inputs_survive_context_refresh(self):
        from tests.test_process_safety_integration import request
        body=request().model_dump()
        body['_captured_hilt']={'content_hash':'captured-original'}
        record=source_fixtures.SourceDefectPostgresTests.start_run(self,body)
        changed={**body,'process_safety_inputs':{'forged':True},'_captured_hilt':{'forged':True}}
        self.repo.update_run_request(record.run_id,changed)
        saved=self.repo.get_run(record.run_id)['request']
        self.assertEqual(saved['process_safety_inputs'],body['process_safety_inputs'])
        self.assertEqual(saved['_captured_hilt'],body['_captured_hilt'])
        with self.assertRaises(ValueError):
            self.repo.update_run_request(record.run_id,{**changed,'job_id':'other'})
