from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from equipment_isolation.api.planning_previews import router, template, evaluate_inputs
from equipment_isolation.domain.controlled_inputs import ControlledInputError, content_hash
from equipment_isolation.domain.isolation_standard import FluidHazardRegister, base_required_barrier_configuration
from equipment_isolation.domain.planning_preview import derive_hsc, derive_ec
from equipment_isolation.domain.safety_inputs import StructuredWorkScope, SicProfile


class PlanningPreviewTests(unittest.TestCase):
    def setUp(self):
        self.inputs = template()['inputs']

    def test_packaged_mocks_match_researched_documents(self):
        root = Path(__file__).parents[1]
        for kind in ('fhr', 'sic', 'psd'):
            name = f'mock_{kind}_pnid_2151.json'
            self.assertEqual((root/'docs'/name).read_bytes(), (root/'equipment_isolation/fixtures'/name).read_bytes())

    def test_all_paths_and_snapshots_are_preserved_without_authority(self):
        result = evaluate_inputs(self.inputs)
        self.assertEqual(result['path_count'], 5)
        self.assertFalse(result['executable'])
        self.assertNotIn('assurance_status', result)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual({p['service_codes'][0] for p in result['paths']}, {'PC','CDH','SWS','SWR','VRP'})
        self.assertTrue(all(len(p['link_ids']) == 3 for p in result['paths']))
        self.assertEqual(result, evaluate_inputs(self.inputs))
        # A caller cannot mutate stored snapshots by changing its source object.
        before = content_hash(result)
        self.inputs['work_scope']['expected_duration_days'] = 100
        self.assertEqual(before, content_hash(result))

    def test_permuted_graphs_have_identical_derivation(self):
        first = evaluate_inputs(self.inputs)
        self.inputs['hilt_graph']['nodes'].reverse()
        self.inputs['hilt_graph']['links'].reverse()
        self.assertEqual(first, evaluate_inputs(self.inputs))

    def test_unknown_and_conflicting_services_remain_blocked(self):
        for link in self.inputs['hilt_graph']['links']:
            if '-CDH-' in link['id']: link['payload']['service_code'] = 'UNMAPPED'
        result = evaluate_inputs(self.inputs)
        path = next(p for p in result['paths'] if p['service_codes'] == ['UNMAPPED'])
        self.assertEqual(path['hsc']['value'], 4)
        self.assertIn('unknown_fluid', path['blockers'])
        self.inputs['hilt_graph']['links'][0]['payload']['service_code'] = 'PC'
        result = evaluate_inputs(self.inputs)
        self.assertTrue(any('path_service_code_conflict' in p['blockers'] for p in result['paths']))

    def test_expiry_and_declared_zero_never_prove_isolation(self):
        self.inputs['plan_time'] = '2026-09-10T07:00:00Z'
        self.inputs['psd']['system_status'][0]['pressure_barg'] = 0
        result = evaluate_inputs(self.inputs)
        self.assertTrue(any('expired' in gap for gap in result['blockers']))
        self.assertFalse(result['executable'])

    def test_cycles_dangling_links_and_budgets_retain_blockers(self):
        graph = self.inputs['hilt_graph']
        graph['links'].append({'id': 'cycle', 'source': 'MOCK-CDH-V2', 'target': 'MOCK-EQUIPMENT', 'payload': {'service_code': 'CDH'}})
        self.assertTrue(any('unresolved_cycle' in p['blockers'] for p in evaluate_inputs(self.inputs)['paths']))
        graph['links'][-1]['target'] = 'missing'
        self.assertTrue(any('unresolved_endpoint' in p['blockers'] for p in evaluate_inputs(self.inputs)['paths']))
        with patch('equipment_isolation.domain.planning_preview.MAX_EXPANSIONS', 1):
            self.assertTrue(any('safety_limit_reached' in p['blockers'] for p in evaluate_inputs(self.inputs)['paths']))

    def test_unavailable_first_barrier_does_not_stop_traversal(self):
        for node in self.inputs['hilt_graph']['nodes']:
            if node['id'].endswith('-V1'): node['payload']['available'] = False
        result = evaluate_inputs(self.inputs)
        self.assertTrue(all(len(p['link_ids']) == 3 for p in result['paths']))
        self.assertTrue(all(any('availability_unverified_or_unavailable' in d['reasons'] for d in p['devices']) for p in result['paths']))

    def test_parallel_barriers_are_not_combined(self):
        graph = self.inputs['hilt_graph']
        graph['links'] = [l for l in graph['links'] if not l['id'].endswith('-V2')]
        result = evaluate_inputs(self.inputs)
        self.assertTrue(all(len(p['selected_entity_ids']) <= 1 for p in result['paths']))
        self.assertTrue(all('unresolved_dead_end' in p['blockers'] for p in result['paths']))

    def test_scope_relabel_and_production_mode_rejected(self):
        for mutate in (
            lambda x: x.update(mode='governed'),
            lambda x: x['sic'].update(synthetic=False),
            lambda x: x['psd'].update(synthetic=False),
            lambda x: x['fhr']['document'].update(status='approved'),
            lambda x: x['sic']['context'].update(collection_id='other'),
            lambda x: x.update(target_entity_id='MOCK-CDH-V1'),
            lambda x: x['work_scope'].update(containment_break='false'),
        ):
            value = deepcopy(self.inputs); mutate(value)
            with self.assertRaises(ControlledInputError): evaluate_inputs(value)

    def test_exposure_thresholds_and_matrix_cells(self):
        sic = SicProfile.from_dict(self.inputs['sic'])
        def exposure(**updates):
            scope = StructuredWorkScope.from_dict({**self.inputs['work_scope'], **updates})
            return derive_ec(scope, sic)
        self.assertEqual(exposure(containment_break=False)['value'], 'A')
        self.assertEqual(exposure()['value'], 'B')
        self.assertEqual(exposure(expected_duration_days=6.99)['value'], 'B')
        self.assertEqual(exposure(expected_duration_days=7)['value'], 'C')
        self.assertEqual(exposure(personnel_enter_boundary=True)['value'], 'D')
        self.assertEqual(exposure(hot_work_on_or_within_boundary=True)['value'], 'D')
        self.assertTrue(exposure(expected_duration_days=30)['positive_mandatory'])
        for h in range(1,5):
            for e in 'ABCD':
                self.assertEqual(base_required_barrier_configuration(h,e).matrix_cell, f'HSC-{h}/EC-{e}')

    def test_hazard_thresholds_and_missing_values(self):
        water = next(f for f in FluidHazardRegister.from_dict(self.inputs['fhr']).fluids if f.fluid_code == self.inputs['fhr']['service_code_map'][2]['fluid_code'])
        water = replace(water, nfpa_health=0, nfpa_flammability=0, nfpa_instability=0,
                        is_corrosive=False, is_asphyxiant=False, is_cryogenic=False, hsc_override=None,
                        idlh_ppm=None, h2s_content_ppm=0, autoignition_temp_c=None)
        self.assertEqual(derive_hsc(water, 9.99, 59.99)['value'], 1)
        self.assertEqual(derive_hsc(water, 10, 20)['value'], 2)
        self.assertEqual(derive_hsc(water, 1, 60)['value'], 2)
        self.assertEqual(derive_hsc(water, 1, 150)['value'], 3)
        self.assertEqual(derive_hsc(water, None, 20)['value'], 4)
        self.assertEqual(derive_hsc(replace(water, h2s_content_ppm=100), 1, 20)['value'], 4)

    def test_routes_require_actor_and_reject_unknown_fields(self):
        app = FastAPI(); app.include_router(router)
        with TestClient(app) as client:
            self.assertEqual(client.get('/planning-previews/template').status_code, 401)
        app = FastAPI(); app.include_router(router)
        @app.middleware('http')
        async def actor(request, call_next):
            request.state.token_data = {'user': {'id': 'test-actor'}}
            return await call_next(request)
        with TestClient(app) as client:
            self.assertEqual(client.get('/planning-previews/template').status_code, 200)
            self.assertEqual(client.post('/planning-previews', json={'inputs': self.inputs, 'mode': 'approved'}).status_code, 422)
            with patch('equipment_isolation.api.planning_previews._repository') as repo:
                repo.return_value.create.side_effect = ControlledInputError('invalid_safety_input', 'wrong scope')
                self.assertEqual(client.post('/planning-previews', json={'inputs': self.inputs}).status_code, 422)
