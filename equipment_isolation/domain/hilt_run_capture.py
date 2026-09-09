"""Immutable original HILT export, including records with topology defects."""
from equipment_isolation.domain.safety_inputs import FrozenJSON, obj, context, timestamp, invalid


class HiltRunCapture(FrozenJSON):
    @staticmethod
    def _validate(value):
        obj(value, ['schema_version', 'context', 'captured_at', 'payload'], 'hilt_run_capture')
        if value['schema_version'] != 'hilt-run-capture-v1': invalid('schema_version', 'unsupported HILT capture')
        value['context'] = context(value['context'])
        value['captured_at'] = timestamp(value['captured_at'], 'captured_at')
        payload = value['payload']
        graph = payload.get('hilt_graph') if isinstance(payload, dict) else None
        if not isinstance(graph, dict) or not isinstance(graph.get('nodes'), list) or not isinstance(graph.get('links'), list):
            invalid('hilt', 'expected exported HILT graph')
        for row in graph['nodes'] + graph['links']:
            if not isinstance(row, dict) or not isinstance(row.get('payload', {}), dict): invalid('hilt', 'malformed source record')
        return value

    @property
    def blockers(self):
        from equipment_isolation.domain.source_snapshots import _consistent
        from equipment_isolation.domain.controlled_inputs import ControlledInputError
        graph = self.to_dict()['payload']['hilt_graph']
        gaps = {'hilt_provider_consistency_unverified', 'hilt_coverage_unverified'}
        ids = [str(row.get('id') or row.get('payload', {}).get('id') or '') for row in graph['nodes']]
        if '' in ids or len(ids) != len(set(ids)): gaps.add('hilt_node_identity_missing_or_duplicated')
        edge_ids=[]
        for index,row in enumerate(graph['links']):
            identity=str(row.get('id') or row.get('payload',{}).get('id') or '')
            edge_ids.append(identity)
            for key, alias in [('source','from'),('target','to')]:
                try:
                    endpoint = _consistent([row.get(key), row.get('payload',{}).get(alias)], key)
                    if endpoint not in ids: gaps.add(f'hilt_unresolved_endpoint:{identity or index}:{key}')
                except ControlledInputError: gaps.add(f'hilt_unresolved_endpoint:{identity or index}:{key}')
        if '' in edge_ids or len(edge_ids) != len(set(edge_ids)): gaps.add('hilt_link_identity_missing_or_duplicated')
        return sorted(gaps)
