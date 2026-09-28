"""Document-backed request fixtures for API lifecycle tests."""
from equipment_isolation.api.models import IsolationRunRequest
from equipment_isolation.domain.hilt_run_capture import HiltRunCapture
from equipment_isolation.integrations.planning_documents import adapt_process_safety_inputs
from tests.planning_document_fixtures import approved_manifest, WORK_SCOPE


def run_request(model=IsolationRunRequest, **overrides):
    body = dict(equipment_tag='P3', job_id='2151', cnvrt_project_id='277', collection_id='206', unigraph_project_id='15')
    body.update(overrides)
    manifest = approved_manifest()
    manifest['entry_unigraph_project_id'] = str(body['unigraph_project_id'])
    for document in manifest['documents'].values():
        document['entry_unigraph_project_id'] = str(body['unigraph_project_id'])
    inputs = adapt_process_safety_inputs(
        manifest,
        context={key: str(body[key]) for key in ('cnvrt_project_id', 'collection_id', 'unigraph_project_id', 'job_id')},
        work_scope=WORK_SCOPE,
        plan_time='2026-09-17T08:00:00+00:00',
    )
    body.setdefault('process_safety_inputs', inputs)
    body.setdefault('planning_document_sources', manifest)
    body.setdefault('expected_planning_document_set', manifest['document_set_token'])
    body.setdefault('selected_asset', dict(hilt_entity_id='test-equipment', tag=body['equipment_tag'], selection_source='hilt_equipment_list'))
    return model(**body)


def captured_hilt(request, _token):
    value = HiltRunCapture.from_dict(dict(schema_version='hilt-run-capture-v1', context=request.process_safety_inputs['psd']['context'], captured_at='2026-09-08T07:00:00Z', payload={'hilt_graph': {'nodes': [], 'links': []}}))
    return {**value.to_dict(), 'content_hash': value.content_hash}
