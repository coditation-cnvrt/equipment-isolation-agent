"""Document-backed request fixtures for API lifecycle tests."""
from equipment_isolation.api.models import IsolationRunRequest
from equipment_isolation.fixtures.safety_examples import example_process_inputs
from equipment_isolation.domain.hilt_run_capture import HiltRunCapture


def run_request(model=IsolationRunRequest, **overrides):
    body = dict(equipment_tag='P3', job_id='2151', cnvrt_project_id='277', collection_id='206', unigraph_project_id='15')
    body.update(overrides)
    inputs = example_process_inputs()
    inputs['psd']['context'] = {key: str(body[key]) for key in ('cnvrt_project_id', 'collection_id', 'unigraph_project_id', 'job_id')}
    inputs['sic']['context'] = {key: str(body[key]) for key in ('cnvrt_project_id', 'collection_id')}
    for source, target in [('cnvrt_project_id','cnvrt_project_id'),('collection_id','collection_id'),('job_id','pnid_job_id')]:
        inputs['fhr']['document'][target] = body[source]
    body.setdefault('process_safety_inputs', inputs)
    body.setdefault('selected_asset', dict(hilt_entity_id='test-equipment', tag=body['equipment_tag'], selection_source='hilt_equipment_list'))
    return model(**body)


def captured_hilt(request, _token):
    value = HiltRunCapture.from_dict(dict(schema_version='hilt-run-capture-v1', context=request.process_safety_inputs['psd']['context'], captured_at='2026-09-08T07:00:00Z', payload={'hilt_graph': {'nodes': [], 'links': []}}))
    return {**value.to_dict(), 'content_hash': value.content_hash}
