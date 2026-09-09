"""Public synthetic documents for explicit loading; never production defaults."""
from importlib.resources import files
import json
from equipment_isolation.integrations.safety_input_adapters import sic_from_mock, psd_from_mock


def example_process_inputs():
    def read(kind):
        return json.loads(files('equipment_isolation.fixtures').joinpath(f'mock_{kind}_pnid_2151.json').read_text())
    fhr = read('fhr')
    return {'schema_version': 'process-safety-inputs-v1', 'fhr': fhr,
        'sic': sic_from_mock(read('sic')).to_dict(), 'psd': psd_from_mock(read('psd')).to_dict(),
        'unit_scope': fhr['service_code_map'][0]['unit_scope'], 'plan_time': '2026-09-08T07:00:00Z',
        'work_scope': {'schema_version': 'work-scope-v1', 'activity_type': 'Equipment inspection',
            'expected_duration_days': 1, 'shift_coverage': 'single_shift', 'containment_break': True,
            'continuously_attended': True, 'personnel_enter_boundary': False,
            'hot_work_on_or_within_boundary': False, 'equipment_leaves_site': False}}
