from dataclasses import replace
from copy import deepcopy
from unittest.mock import patch, MagicMock
import unittest

from equipment_isolation.api.models import IsolationRunRequest
from equipment_isolation.api.service import config_from_run_request, capture_run_hilt
from equipment_isolation.core.validator import validate
from equipment_isolation.domain.process_safety import ProcessSafetyInputs
from equipment_isolation.fixtures.safety_examples import example_process_inputs
from equipment_isolation.integrations.hilt_topology import _hilt_index, _nearest_branch_devices
from equipment_isolation.presentation.payload import build_final_payload
from equipment_isolation.api.plans import normalized_plan_content


def request():
    return IsolationRunRequest(equipment_tag='P3', job_id='2151', cnvrt_project_id='277', collection_id='206', unigraph_project_id='21',
        selected_asset={'hilt_entity_id':'E', 'tag':'P3', 'entity_class':'vessel', 'selection_source':'hilt_equipment_list'},
        process_safety_inputs=example_process_inputs())


def graph():
    return {'hilt_graph': {'nodes': [
        {'id': 'E', 'payload': {'entity_type': 'equipment', 'entity_class': 'vessel'}},
        *[{'id': n, 'payload': {'entity_type': 'component', 'entity_class': kind}}
          for n,kind in [('N','equipment_nozzle'),('V1','gate_valve'),('V2','blind'),('V3','blind')]]],
        'links': [{'id': str(i), 'source': a, 'target': b, 'payload': {'entity_class': 'process_line', 'service_code': 'CDH'}}
                  for i,(a,b) in enumerate([('N','V1'),('V1','V2'),('V2','V3')])]}}


class ProcessSafetyIntegrationTests(unittest.TestCase):
    def test_new_run_requires_documents_and_structural_identity(self):
        for key in ('process_safety_inputs', 'selected_asset'):
            for missing in (True, False):
                with self.subTest(key=key, omitted=missing):
                    body = request().model_dump()
                    if missing: body.pop(key)
                    else: body[key] = None
                    with self.assertRaises(ValueError):
                        IsolationRunRequest.model_validate(body)

    def test_dispatch_rejects_legacy_payload_before_capture_or_persistence(self):
        from equipment_isolation.api.runs import RunStore
        body = request().model_dump()
        body.pop('process_safety_inputs')
        repo = MagicMock()
        store = RunStore(repository=repo)
        self.addCleanup(store.shutdown)
        with patch('equipment_isolation.api.service.capture_run_hilt') as capture, patch.object(store._executor, 'submit') as dispatch:
            with self.assertRaises(ValueError):
                store.create(IsolationRunRequest.model_construct(**body), 'unused')
            capture.assert_not_called()
            dispatch.assert_not_called()
            repo.insert_run.assert_not_called()

    def test_scope_mismatch_rejected_and_structured_scope_is_authoritative(self):
        body = request().model_dump()
        body['job_id']='different'
        with self.assertRaises(ValueError): IsolationRunRequest.model_validate(body)
        body = request().model_dump(); body['process_safety_inputs']['work_scope']['personnel_enter_boundary']=True
        parsed=IsolationRunRequest.model_validate(body)
        self.assertTrue(parsed.work_scope.confined_space_entry)
        config=config_from_run_request(parsed, 'unused')
        self.assertTrue(config.work_scope.confined_space_entry)
        self.assertIs(config.policy.process_safety_inputs, config.process_safety_inputs)

    def test_validator_cannot_accept_omitted_or_forged_assessment(self):
        data = {'candidates':[{'candidate_id':'V1'}], 'evidence_state':{'barrier_candidate_ids':['V1'], 'positive_candidate_ids':['V1'], 'verification_candidate_ids':['PI'], 'missing_boundary_count':0},
                'process_safety_assessment': {'status':'complete'}}
        config=config_from_run_request(request(), 'unused')
        result=validate(data, process_safety_inputs=config.process_safety_inputs)
        self.assertEqual(result['assurance_status'],'not_isolated')
        self.assertEqual(result['plan_readiness']['status'],'incomplete')
        self.assertEqual(result['process_safety_assessment']['status'],'blocked')
        self.assertEqual(result['process_safety_assessment']['paths'][0]['hsc']['value'],4)
        final=build_final_payload(result,config)
        self.assertEqual(normalized_plan_content(request().model_dump(),final)['process_safety_assessment'], final['data'][0]['process_safety_assessment'])

    def test_capture_checks_structural_identity_and_preserves_content(self):
        source=graph()
        with patch('equipment_isolation.api.service.get_cnvrt_hilt_graph',return_value=source):
            capture=capture_run_hilt(request(),'unused')
        self.assertEqual(capture['payload'],source)
        self.assertEqual(len(capture['content_hash']),64)
        source['hilt_graph']['nodes'][0]['payload']['entity_type']='component'
        with patch('equipment_isolation.api.service.get_cnvrt_hilt_graph',return_value=source),self.assertRaises(ValueError):
            capture_run_hilt(request(),'unused')

    def test_capture_failure_never_dispatches(self):
        from equipment_isolation.api.runs import RunStore
        repo=MagicMock(); store=RunStore(repository=repo)
        self.addCleanup(store.shutdown)
        with patch('equipment_isolation.api.service.capture_run_hilt',side_effect=ValueError('bad identity')), patch.object(store._executor,'submit') as dispatch:
            with self.assertRaises(ValueError): store.create(request(),'unused')
            dispatch.assert_not_called(); repo.insert_run.assert_not_called()

    def test_hilt_search_continues_and_scope_changes_required_positive_count(self):
        config=config_from_run_request(request(),'unused')
        nodes,adj=_hilt_index(graph()['hilt_graph'])
        # Test graph vocabulary is the same process-line class accepted by production.
        self.assertTrue(adj)
        branches=_nearest_branch_devices('N',adj,nodes,24,policy=config.policy)
        self.assertTrue(any(len(b.get('barrier_candidates',[])) >= 2 for b in branches))
        body=request().model_dump(); body['process_safety_inputs']['work_scope']['personnel_enter_boundary']=True
        config=config_from_run_request(IsolationRunRequest.model_validate(body),'unused')
        branches=_nearest_branch_devices('N',adj,nodes,24,policy=config.policy)
        self.assertTrue(any(b.get('required_configuration',{}).get('positive_barrier_count') == 2 for b in branches))

    def test_unselected_hilt_path_is_assessed(self):
        config=config_from_run_request(request(),'unused')
        data={'hilt_branch_obligations':[{'source_component':'N','branches':[{'branch_id':'uncovered','status':'unresolved','path_node_ids':['N']}]}]}
        result=validate(data,process_safety_inputs=config.process_safety_inputs)
        self.assertIn('uncovered',[p['path_id'] for p in result['process_safety_assessment']['paths']])

    def test_original_hilt_capture_keeps_endpoint_disagreements_as_blockers(self):
        from equipment_isolation.domain.hilt_run_capture import HiltRunCapture
        value={'schema_version':'hilt-run-capture-v1','context':request().process_safety_inputs['psd']['context'],
               'captured_at':'2026-09-08T07:00:00Z','payload':graph()}
        value['payload']['hilt_graph']['links'][0]['payload']['from']='different'
        capture=HiltRunCapture.from_dict(value)
        self.assertEqual(capture.to_dict()['payload'],value['payload'])
        self.assertTrue(any('unresolved_endpoint' in gap for gap in capture.blockers))

    def test_executor_rejects_tampered_capture_before_pipeline(self):
        from equipment_isolation.api.service import execute_agent_request
        with patch('equipment_isolation.api.service.get_cnvrt_hilt_graph',return_value=graph()):
            capture=capture_run_hilt(request(),'unused')
        capture['payload']['hilt_graph']['nodes'][0]['payload']['entity_class']='modified'
        with patch('equipment_isolation.api.service.run_agent_pipeline') as pipeline:
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                execute_agent_request(run_id='test',request=request(),auth_token='unused',captured_hilt=capture)
            pipeline.assert_not_called()
