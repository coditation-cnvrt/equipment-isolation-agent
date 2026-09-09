"""Deterministic, synthetic-only planning evaluation. No execution authority.

Rules are traced to project requirements 6.1-6.4. Highest-match precedence is
an explicit development proposal, never an approved site policy. Inputs are
captured before evaluation; no clocks, live lookups or LLM calls occur here.
"""
from dataclasses import asdict
from datetime import datetime
from itertools import combinations

from equipment_isolation.domain.controlled_inputs import content_hash
from equipment_isolation.domain.isolation_standard import (
    FluidHazardRegister, base_required_barrier_configuration, resolve_path_fluid,
)
from equipment_isolation.domain.safety_inputs import (
    StructuredWorkScope, SicProfile, SicDelta, compose_sic, invalid, obj, timestamp,
)
from equipment_isolation.domain.plant_state import PlantStateDeclaration
from equipment_isolation.domain.source_snapshots import GraphSnapshot

from equipment_isolation.domain.process_classification import derive_hsc, derive_ec

ENGINE_VERSION = 'synthetic-process-preview-v1'
MAX_EXPANSIONS = 2000
MAX_DEPTH = 64


def enumerate_paths(graph, target):
    """Bounded undirected source topology; never stop at the first barrier.

    Terminals are explicit synthetic declarations. Loops, unknown endpoints and
    budget exhaustion are retained as unresolved path occurrences.
    """
    nodes = {x['id']: x['record'].get('payload', {}) for x in graph['nodes']}
    edges = {x['id']: x for x in graph['edges']}
    if target not in nodes or nodes[target].get('entity_type') != 'equipment':
        invalid('target_entity_id', 'must identify structural equipment in the captured graph')
    adjacency = {key: [] for key in nodes}
    for edge in edges.values():
        for start, end in ((edge['source'], edge['target']), (edge['target'], edge['source'])):
            adjacency.setdefault(start, []).append((edge['id'], end))
    stack, paths, expansions = [(target, [target], [])], [], 0
    while stack:
        node, node_ids, link_ids = stack.pop()
        reason = None
        if node not in nodes: reason = 'unresolved_endpoint'
        elif len(node_ids) > 1 and nodes[node].get('preview_terminal') is True: reason = 'declared_terminal'
        elif len(link_ids) >= MAX_DEPTH: reason = 'safety_limit_reached'
        choices = [(e, n) for e, n in sorted(adjacency.get(node, [])) if e not in link_ids]
        if reason is None and not choices: reason = 'unresolved_dead_end'
        if reason:
            paths.append((node_ids, link_ids, reason))
            continue
        for edge, neighbor in choices:
            expansions += 1
            if expansions > MAX_EXPANSIONS:
                # Whole-run coverage is blocked; retain a sentinel for omitted frontier.
                paths.append((node_ids, link_ids, 'safety_limit_reached'))
                return paths, nodes, edges
            if neighbor in node_ids:
                paths.append((node_ids + [neighbor], link_ids + [edge], 'unresolved_cycle'))
            else:
                stack.append((neighbor, node_ids + [neighbor], link_ids + [edge]))
    return paths, nodes, edges


def assess_device(identity, facts, hsc, ec, scope, sic):
    kind = facts.get('device_kind', 'unknown')
    reasons, positive = [], False
    if facts.get('available') is not True: reasons.append('availability_unverified_or_unavailable')
    if kind in {'gate', 'ball', 'plug_valve', 'globe', 'butterfly'}:
        if facts.get('lockable') is not True: reasons.append('lockability_unverified')
        if kind == 'butterfly' and hsc >= 3: reasons.append('butterfly_sole_barrier_not_permitted')
        if kind == 'butterfly' and scope['hot_work_on_or_within_boundary'] and facts.get('soft_seated') is not False and not sic['barrier_policy']['soft_seat_permitted_for_hot_work']:
            reasons.append('soft_seat_hot_work')
    elif kind in {'blind', 'spade', 'blind_flange'}:
        positive = True
        if facts.get('rating_verified') is not True: reasons.append('rating_unverified')
    else:
        reasons.append('device_not_supported_as_barrier')
    return {'entity_id': identity, 'kind': kind, 'admissible_in_preview': not reasons,
            'positive': positive, 'reasons': reasons, 'field_proving_required': True,
            'rule_id': 'REQ-6.4:device_admissibility',
            'notes': ['directional_seating_review'] if kind == 'globe' else []}


def evaluate_preview(payload, graph: GraphSnapshot):
    obj(payload, ['schema_version', 'mode', 'plan_time', 'work_scope', 'fhr', 'sic', 'psd', 'hilt_graph', 'target_entity_id', 'unit_scope'], 'preview', ['sic_delta'])
    if payload['schema_version'] != 'planning-preview-input-v1' or payload['mode'] != 'synthetic':
        invalid('mode', 'only explicit synthetic preview is supported')
    plan_time = datetime.fromisoformat(timestamp(payload['plan_time'], 'plan_time').replace('Z', '+00:00'))
    scope = StructuredWorkScope.from_dict(payload['work_scope'])
    sic = SicProfile.from_dict(payload['sic'])
    psd = PlantStateDeclaration.from_dict(payload['psd'])
    if not sic.to_dict()['synthetic'] or not psd.to_dict()['synthetic']:
        invalid('synthetic', 'preview requires synthetic SIC and PSD')
    if payload['fhr'].get('document', {}).get('status') != 'draft_mock_unapproved':
        invalid('fhr', 'preview requires explicitly unapproved mock FHR')
    register = FluidHazardRegister.from_dict(payload['fhr'])
    ctx = psd.to_dict()['context']
    fhr_doc = payload['fhr']['document']
    for key, field in [('cnvrt_project_id', 'cnvrt_project_id'), ('collection_id', 'collection_id'), ('job_id', 'pnid_job_id')]:
        if str(fhr_doc.get(field)) != ctx[key]: invalid('fhr.context', 'scope mismatch')
    if sic.to_dict()['context'] != {k: ctx[k] for k in ('cnvrt_project_id', 'collection_id')}:
        invalid('sic.context', 'scope mismatch')
    delta = SicDelta.from_dict(payload['sic_delta']) if payload.get('sic_delta') is not None else None
    sic, composition = compose_sic(sic, delta)
    if graph.to_dict()['context'] != ctx:
        invalid('graph.context', 'scope mismatch')
    if len(graph.to_dict()['graph']['nodes']) > 500 or len(graph.to_dict()['graph']['edges']) > 1000:
        invalid('hilt_graph', 'preview supports at most 500 nodes and 1000 links')
    paths, nodes, edges = enumerate_paths(graph.to_dict()['graph'], payload['target_entity_id'])
    ec = derive_ec(scope, sic)
    state = psd.assess(plan_time=plan_time, validity_hours=sic.to_dict()['parameters']['plant_state']['validity_hours']).to_dict()
    blockers = {'synthetic_inputs_not_approved', 'policy_precedence_unapproved', 'operations_authority_unverified',
                'governed_admission_not_integrated', 'field_execution_not_authorized'}
    blockers.update(state['blockers']); blockers.update(sic.blockers); blockers.update(graph.blockers)
    results = []
    for node_ids, link_ids, termination in paths:
        path_id = content_hash({'nodes': node_ids, 'links': link_ids})[:24]
        facts = [{'id': e, **edges[e]['record'].get('payload', {})} for e in link_ids]
        unit_scopes = {fact['unit_scope'] for fact in facts if isinstance(fact.get('unit_scope'), str) and fact['unit_scope']}
        unit_scope = next(iter(unit_scopes)) if len(unit_scopes) == 1 else payload['unit_scope']
        fluid = resolve_path_fluid({'path_id': path_id, 'path_link_facts': facts}, register,
                                  unit_scope=unit_scope, require_approved=False)
        codes = fluid.service_codes
        rows = [x for x in psd.to_dict()['system_status'] if x['service_code'] in codes]
        conditions = rows[0] if len(rows) == 1 else {}
        hsc = derive_hsc(fluid.resolution.fluid, conditions.get('pressure_barg'), conditions.get('temperature_c'))
        gaps = set(hsc['blockers'])
        if len(unit_scopes) > 1:
            gaps.add('path_unit_scope_conflict')
            hsc = {'value': 4, 'rules': [], 'blockers': ['path_unit_scope_conflict']}
        if fluid.resolution.gap_code: gaps.add(fluid.resolution.gap_code)
        if len(rows) != 1: gaps.add('psd_service_missing_or_ambiguous')
        if termination != 'declared_terminal': gaps.add(termination)
        config = asdict(base_required_barrier_configuration(hsc['value'], ec['value']))
        if ec['positive_mandatory']:
            config['positive_barrier_count'] = max(1, config['positive_barrier_count'])
        if sic.to_dict()['matrix_overrides']: gaps.add('sic_matrix_overrides_require_approval')
        devices = [assess_device(n, nodes[n], hsc['value'], ec['value'], scope.to_dict(), sic.to_dict()['parameters'])
                   for n in node_ids[1:] if n in nodes and 'device_kind' in nodes[n]]
        admissible = [d for d in devices if d['admissible_in_preview']] if termination == 'declared_terminal' else []
        selected = []
        for group in combinations(admissible, config['barrier_count']):
            if sum(d['positive'] for d in group) >= config['positive_barrier_count']:
                selected = [d['entity_id'] for d in group]; break
        if not selected: gaps.add('required_barriers_not_found_in_series')
        # Location/pressure declarations are not a proved safe disposal destination.
        if config['bleed_required']: gaps.add('bleed_topology_and_safe_destination_unverified')
        if config['physical_disconnection_required']: gaps.add('disconnection_and_both_sides_blinding_unverified')
        # Missing size/spec data cannot silently evade the small-bore rule.
        gaps.add('connection_size_and_spec_breaks_unverified')
        gaps.add('field_proving_required')
        results.append({'path_id': path_id, 'node_ids': node_ids, 'link_ids': link_ids, 'termination': termination,
            'service_codes': list(codes), 'fluid_code': fluid.resolution.fluid.fluid_code if fluid.resolution.fluid else None,
            'service_evidence': [asdict(e) for e in fluid.evidence], 'unit_scope': unit_scope, 'conditions': conditions,
            'hsc': hsc, 'ec': ec, 'rbc': config, 'devices': devices, 'selected_entity_ids': selected,
            'configuration_status': 'blocked', 'blockers': sorted(gaps)})
    results.sort(key=lambda r: r['path_id'])
    snapshots = {'fhr': payload['fhr'], 'sic': sic.to_dict(), 'sic_composition': composition.to_dict(),
                 'psd': psd.to_dict(), 'hilt': graph.to_dict(), 'work_scope': scope.to_dict()}
    return {'schema_version': 'planning-preview-result-v1', 'engine_version': ENGINE_VERSION,
            'mode': 'synthetic', 'executable': False, 'status': 'blocked', 'plan_time': timestamp(payload['plan_time'], 'plan_time'),
            'input_hashes': {k: content_hash(v) for k, v in snapshots.items()}, 'snapshots': snapshots,
            'psd_assessment': state, 'exposure': ec, 'paths': results,
            'blockers': sorted(blockers), 'path_count': len(results),
            'coverage': 'limited_synthetic_graph_only',
            'proving': sic.to_dict()['parameters']['proving']}
