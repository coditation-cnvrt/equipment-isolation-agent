"""Immutable safety inputs and assessments for the equipment isolation pipeline.

Submitted document claims never establish approval. Retained path facts are
assessed without assuming first-barrier paths prove complete RBC coverage.
"""
from dataclasses import asdict
from datetime import datetime

from equipment_isolation.domain.controlled_inputs import content_hash
from equipment_isolation.domain.isolation_standard import FluidHazardRegister, resolve_path_fluid, base_required_barrier_configuration
from equipment_isolation.domain.path_facts import path_facts
from equipment_isolation.domain.plant_state import PlantStateDeclaration
from equipment_isolation.domain.process_classification import derive_hsc, derive_ec
from equipment_isolation.domain.safety_inputs import FrozenJSON, SicProfile, StructuredWorkScope, compose_sic, obj, enum, timestamp, string, invalid


class ProcessSafetyInputs(FrozenJSON):
    @staticmethod
    def _validate(value):
        obj(value, ['schema_version', 'fhr', 'sic', 'psd', 'work_scope', 'plan_time', 'unit_scope'], 'process_safety_inputs')
        enum(value['schema_version'], {'process-safety-inputs-v1'}, 'schema_version')
        value['work_scope'] = StructuredWorkScope.from_dict(value['work_scope']).to_dict()
        value['sic'] = SicProfile.from_dict(value['sic']).to_dict()
        value['psd'] = PlantStateDeclaration.from_dict(value['psd']).to_dict()
        value['plan_time'] = timestamp(value['plan_time'], 'plan_time')
        value['unit_scope'] = string(value['unit_scope'], 'unit_scope')
        FluidHazardRegister.from_dict(value['fhr'])
        ctx = value['psd']['context']
        if value['sic']['context'] != {k: ctx[k] for k in ('cnvrt_project_id', 'collection_id')}:
            invalid('sic.context', 'must match PSD context')
        doc = value['fhr']['document']
        for key, field in [('cnvrt_project_id', 'cnvrt_project_id'), ('collection_id', 'collection_id'), ('job_id', 'pnid_job_id')]:
            if str(doc.get(field)) != ctx[key]: invalid('fhr.context', 'must match PSD drawing scope')
        return value

    def require_scope(self, context):
        expected = self.to_dict()['psd']['context']
        if any(str(context.get(key, '')) != value for key, value in expected.items()):
            invalid('process_safety_inputs.context', 'does not match the selected run scope')


def assess_process_paths(data, inputs: ProcessSafetyInputs):
    value = inputs.to_dict()
    register = FluidHazardRegister.from_dict(value['fhr'])
    sic, composition = compose_sic(SicProfile.from_dict(value['sic']))
    scope = StructuredWorkScope.from_dict(value['work_scope'])
    state = PlantStateDeclaration.from_dict(value['psd']).assess(
        plan_time=datetime.fromisoformat(value['plan_time'].replace('Z', '+00:00')),
        validity_hours=sic.to_dict()['parameters']['plant_state']['validity_hours']).to_dict()
    exposure = derive_ec(scope, sic)
    # A supplied approval name/flag is not a trusted repository revision pin.
    blockers = {'fhr_repository_approval_required', 'sic_repository_approval_required',
                'policy_precedence_unapproved', 'live_graph_snapshot_completeness_unverified'}
    blockers.update(sic.blockers); blockers.update(state['blockers'])
    paths = {}
    for candidate in data.get('candidates') or []:
        occurrences = candidate.get('source_paths') or [candidate]
        for occurrence in occurrences:
            facts = path_facts(occurrence)
            key = str(occurrence.get('branch_id') or occurrence.get('graph_path_key') or content_hash(facts))
            row = paths.setdefault(key, {'path_id': key, **facts, 'candidate_ids': [], 'source_component_id': occurrence.get('source_component_id')})
            if str(candidate.get('candidate_id')) not in row['candidate_ids']:
                row['candidate_ids'].append(str(candidate.get('candidate_id')))
    for source in data.get('hilt_branch_obligations') or []:
        for branch in source.get('branches') or []:
            key = str(branch.get('branch_id') or content_hash(branch))
            row = paths.setdefault(key, {'path_id': key, 'candidate_ids': [], 'source_component_id': source.get('source_component')})
            row.update(path_facts(branch))
            row['termination'] = branch.get('basis')
    for occurrence in (data.get('debug') or {}).get('bbox_unselected_source_components') or []:
        facts = path_facts(occurrence)
        key = str(occurrence.get('branch_id') or content_hash({'source': occurrence, 'facts': facts}))
        paths.setdefault(key, {'path_id': key, **facts, 'candidate_ids': [], 'source_component_id': occurrence.get('source_component_id')})
    if not paths: blockers.add('process_path_coverage_missing')
    candidates = {str(c.get('candidate_id')): c for c in data.get('candidates') or []}
    assessments = []
    for key, path in sorted(paths.items()):
        fluid = resolve_path_fluid(path, register, unit_scope=value['unit_scope'], require_approved=False)
        rows = [row for row in value['psd']['system_status'] if row['service_code'] in fluid.service_codes]
        conditions = rows[0] if len(rows) == 1 else {}
        hsc = derive_hsc(fluid.resolution.fluid, conditions.get('pressure_barg'), conditions.get('temperature_c'))
        rbc = asdict(base_required_barrier_configuration(hsc['value'], exposure['value']))
        if exposure['positive_mandatory']: rbc['positive_barrier_count'] = max(1, rbc['positive_barrier_count'])
        gaps = set(hsc['blockers'])
        if fluid.resolution.gap_code: gaps.add(fluid.resolution.gap_code)
        if len(rows) != 1: gaps.add('psd_service_missing_or_ambiguous')
        # Existing selection can provide context, never evidence of complete RBC.
        gaps.update({'configuration_coverage_not_demonstrated', 'device_admissibility_and_proving_unverified'})
        if not path['candidate_ids']: gaps.add('path_has_no_selected_device')
        if rbc['bleed_required']: gaps.add('bleed_topology_and_safe_destination_unverified')
        if rbc['physical_disconnection_required']: gaps.add('disconnection_and_both_sides_blinding_unverified')
        if any(candidates[c].get('available_for_isolation') is False for c in path['candidate_ids']): gaps.add('selected_device_unavailable')
        if sic.to_dict()['matrix_overrides']: gaps.add('sic_matrix_overrides_require_approval')
        assessments.append({**path, 'service_codes': list(fluid.service_codes),
            'fluid_code': fluid.resolution.fluid.fluid_code if fluid.resolution.fluid else None,
            'service_evidence': [asdict(e) for e in fluid.evidence], 'conditions': conditions,
            'hsc': hsc, 'ec': exposure, 'rbc': rbc, 'blockers': sorted(gaps), 'configuration_status': 'not_demonstrated'})
    return {'schema_version': 'process-safety-assessment-v1', 'input_hash': inputs.content_hash,
            'input_snapshot': value, 'sic_composition': composition.to_dict(), 'psd_assessment': state,
            'status': 'blocked', 'blockers': sorted(blockers), 'paths': assessments,
            'coverage': 'retained_paths_only_not_complete_boundary_proof'}


def required_configuration_for_path(path, inputs):
    """Recompute requirements as outward traversal accumulates service facts."""
    value = inputs.to_dict()
    fluid = resolve_path_fluid(path, FluidHazardRegister.from_dict(value['fhr']), unit_scope=value['unit_scope'], require_approved=False)
    rows = [r for r in value['psd']['system_status'] if r['service_code'] in fluid.service_codes]
    conditions = rows[0] if len(rows) == 1 else {}
    hsc = derive_hsc(fluid.resolution.fluid, conditions.get('pressure_barg'), conditions.get('temperature_c'))
    ec = derive_ec(StructuredWorkScope.from_dict(value['work_scope']), SicProfile.from_dict(value['sic']))
    rbc = asdict(base_required_barrier_configuration(hsc['value'], ec['value']))
    if ec['positive_mandatory']: rbc['positive_barrier_count'] = max(1, rbc['positive_barrier_count'])
    return rbc
