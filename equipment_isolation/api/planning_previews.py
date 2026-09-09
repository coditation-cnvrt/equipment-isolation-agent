"""Authenticated, owner-scoped synthetic planning previews and immutable history."""
from datetime import datetime, timezone
from importlib.resources import files
import json
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from equipment_isolation.api.db_models import PlanningPreview
from equipment_isolation.domain.controlled_inputs import ControlledInputError, canonical_bytes, content_hash
from equipment_isolation.domain.planning_preview import evaluate_preview
from equipment_isolation.integrations.graph_snapshots import capture_hilt_export
from equipment_isolation.domain.safety_inputs import timestamp
from equipment_isolation.integrations.safety_input_adapters import sic_from_mock, psd_from_mock

router = APIRouter(prefix='/planning-previews', tags=['Synthetic planning previews'])


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    inputs: dict
    parent_id: UUID | None = None


class PreviewDetail(BaseModel):
    preview_id: UUID
    parent_id: UUID | None
    created_at: str
    input_hash: str
    result_hash: str
    inputs: dict
    result: dict
    comparison: dict | None


class PreviewSummary(BaseModel):
    preview_id: UUID
    parent_id: UUID | None
    created_at: str
    input_hash: str
    result_hash: str


class PreviewList(BaseModel):
    items: list[PreviewSummary]


class PreviewTemplate(BaseModel):
    inputs: dict
    scenarios: list[dict]


def template():
    def fixture(kind):
        return json.loads(files('equipment_isolation.fixtures').joinpath(f'mock_{kind}_pnid_2151.json').read_text())
    fhr, sic, psd = fixture('fhr'), fixture('sic'), fixture('psd')
    nodes = [{'id': 'MOCK-EQUIPMENT', 'payload': {'entity_type': 'equipment'}}]
    links = []
    for code in ('CDH', 'PC', 'SWS', 'SWR', 'VRP'):
        previous = 'MOCK-EQUIPMENT'
        for suffix, props in [('V1', {'device_kind': 'ball', 'lockable': True, 'available': True}),
                              ('V2', {'device_kind': 'blind', 'rating_verified': True, 'available': True}),
                              ('HEADER', {'preview_terminal': True})]:
            identity = f'MOCK-{code}-{suffix}'
            nodes.append({'id': identity, 'payload': {'entity_type': 'component', **props}})
            links.append({'id': f'MOCK-L-{code}-{suffix}', 'source': previous, 'target': identity,
                          'payload': {'service_code': code, 'unit_scope': next(row['unit_scope'] for row in fhr['service_code_map'] if row['pid_service_code'] == code)}})
            previous = identity
    return {'inputs': {'schema_version': 'planning-preview-input-v1', 'mode': 'synthetic',
        'plan_time': '2026-09-08T07:00:00Z', 'unit_scope': fhr['service_code_map'][0]['unit_scope'],
        'target_entity_id': 'MOCK-EQUIPMENT', 'fhr': fhr, 'sic': sic_from_mock(sic).to_dict(),
        'psd': psd_from_mock(psd).to_dict(), 'hilt_graph': {'nodes': nodes, 'links': links},
        'work_scope': {'schema_version': 'work-scope-v1', 'activity_type': 'Cooler inspection',
            'expected_duration_days': 1, 'shift_coverage': 'single_shift', 'containment_break': True,
            'continuously_attended': True, 'personnel_enter_boundary': False,
            'hot_work_on_or_within_boundary': False, 'equipment_leaves_site': False}},
        'scenarios': [{'id': 'base', 'label': 'Stopped equipment / live headers'},
                      {'id': 'expired', 'label': 'Expired plant declaration'},
                      {'id': 'unknown', 'label': 'Unmapped service'},
                      {'id': 'unavailable', 'label': 'Unavailable first valve'},
                      {'id': 'entry', 'label': 'Personnel entry'},
                      {'id': 'cycle', 'label': 'Cyclic graph'}]}


def _actor(request):
    from equipment_isolation.api.routes import _actor_id
    return _actor_id(request)


def _repository(request):
    return PreviewRepository(request.app.state.run_store.repository._session_factory)


def _summary(row):
    return {'preview_id': str(row.preview_id), 'parent_id': str(row.parent_id) if row.parent_id else None,
            'created_at': row.created_at.astimezone(timezone.utc).isoformat(), 'input_hash': row.input_hash, 'result_hash': row.result_hash}


def _detail(row):
    return {**_summary(row), 'inputs': row.inputs, 'result': row.result, 'comparison': row.comparison}


def evaluate_inputs(inputs):
    captured_at = datetime.fromisoformat(timestamp(inputs['plan_time'], 'plan_time').replace('Z', '+00:00'))
    graph = capture_hilt_export(inputs['hilt_graph'], planning_context=inputs['psd']['context'], captured_at=captured_at)
    return evaluate_preview(inputs, graph)


class PreviewRepository:
    def __init__(self, session_factory):
        self.sessions = session_factory

    def list(self, actor):
        with self.sessions() as session:
            rows = session.scalars(select(PlanningPreview).where(PlanningPreview.actor_id == actor)
                                   .order_by(PlanningPreview.created_at.desc(), PlanningPreview.preview_id).limit(50))
            return {'items': [_summary(row) for row in rows]}

    def read(self, actor, preview_id):
        with self.sessions() as session:
            row = session.scalar(select(PlanningPreview).where(PlanningPreview.preview_id == preview_id, PlanningPreview.actor_id == actor))
            if row is None: raise HTTPException(404, 'Unknown preview')
            return _detail(row)

    def create(self, actor, inputs, parent_id=None):
        # Detach and bound before evaluation; snapshots and result commit together.
        encoded = canonical_bytes(inputs)
        if len(encoded) > 1_000_000:
            raise HTTPException(413, 'Preview inputs exceed 1 MB')
        inputs = json.loads(encoded)
        result = evaluate_inputs(inputs)
        with self.sessions.begin() as session:
            comparison = None
            if parent_id is not None:
                parent = session.scalar(select(PlanningPreview).where(PlanningPreview.preview_id == parent_id, PlanningPreview.actor_id == actor))
                if parent is None: raise HTTPException(404, 'Unknown parent preview')
                old = parent.result
                before = {p['path_id']: p for p in old['paths']}
                after = {p['path_id']: p for p in result['paths']}
                comparison = {'parent_result_hash': parent.result_hash,
                    'changed_inputs': sorted(k for k in result['input_hashes'] if result['input_hashes'][k] != old['input_hashes'].get(k)),
                    'added_paths': sorted(after.keys() - before.keys()), 'removed_paths': sorted(before.keys() - after.keys()),
                    'changed_paths': sorted(k for k in before.keys() & after.keys() if content_hash(before[k]) != content_hash(after[k]))}
            row = PlanningPreview(preview_id=uuid4(), parent_id=parent_id, actor_id=actor,
                created_at=datetime.now(timezone.utc), inputs=inputs, result=result,
                input_hash=content_hash(inputs), result_hash=content_hash(result), comparison=comparison)
            session.add(row)
            session.flush()
            return _detail(row)


@router.get('/template', response_model=PreviewTemplate)
def get_template(request: Request):
    _actor(request)
    return template()


@router.get('', response_model=PreviewList)
def list_previews(request: Request):
    return _repository(request).list(_actor(request))


@router.get('/{preview_id}', response_model=PreviewDetail)
def read_preview(preview_id: UUID, request: Request):
    return _repository(request).read(_actor(request), preview_id)


@router.post('', response_model=PreviewDetail, status_code=201)
def create_preview(body: PreviewRequest, request: Request):
    actor = _actor(request)
    try:
        return _repository(request).create(actor, body.inputs, body.parent_id)
    except (ControlledInputError, ValueError, TypeError, KeyError) as exc:
        # Parsing errors carry field locations, never the full submitted document.
        message = str(exc) if isinstance(exc, ControlledInputError) else 'Malformed preview inputs'
        raise HTTPException(422, detail={'kind': 'invalid_preview_input', 'message': message}) from None
