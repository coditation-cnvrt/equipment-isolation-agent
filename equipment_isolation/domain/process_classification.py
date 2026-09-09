"""Pure process classification rules. Policy approval is assessed separately.

Highest-match and imported override precedence remain unapproved proposals.
"""

def derive_hsc(fluid, pressure, temperature):
    rules, gaps = [], []
    if fluid is None:
        return {'value': 4, 'rules': ['REQ-IN-02:unknown_fluid'], 'blockers': ['unknown_fluid']}
    gas = fluid.phase_at_operating.value in {'gas', 'flashing_liquid'}
    liquid = fluid.phase_at_operating.value == 'liquid'
    if fluid.phase_at_operating.value == 'two_phase':
        gaps.append('two_phase_policy_unresolved')
    if pressure is None or temperature is None:
        gaps.append('operating_conditions_missing')
    def match(level, name, condition):
        if condition:
            rules.append({'level': level, 'rule_id': 'REQ-6.1:' + name})
    match(4, 'idlh', fluid.idlh_ppm is not None and fluid.idlh_ppm <= 100)
    match(4, 'h2s', fluid.h2s_content_ppm is not None and fluid.h2s_content_ppm >= 100)
    match(4, 'special_hazard', bool({'pyrophoric', 'water_reactive'} & {x.value for x in fluid.special_hazards}))
    match(4, 'health_gas', fluid.nfpa_health >= 3 and gas)
    match(4, 'flashing_pressure', fluid.phase_at_operating.value == 'flashing_liquid' and pressure is not None and pressure >= 10)
    match(4, 'autoignition', temperature is not None and fluid.autoignition_temp_c is not None and temperature >= fluid.autoignition_temp_c)
    match(3, 'flammable_gas', fluid.nfpa_flammability >= 3 and gas)
    match(3, 'above_flashpoint', liquid and temperature is not None and fluid.flash_point_c is not None and temperature > fluid.flash_point_c)
    match(3, 'health_liquid', liquid and fluid.nfpa_health == 3)
    match(3, 'hot', temperature is not None and temperature >= 150)
    match(3, 'cryogenic', fluid.is_cryogenic)
    hazardous = any((fluid.nfpa_health, fluid.nfpa_flammability, fluid.nfpa_instability,
                     fluid.is_asphyxiant, fluid.is_corrosive, fluid.is_cryogenic,
                     any(x.value != 'none' for x in fluid.special_hazards)))
    match(3, 'hazardous_pressure', hazardous and pressure is not None and pressure >= 20)
    match(2, 'flammable_liquid', liquid and fluid.nfpa_flammability > 0 and temperature is not None and fluid.flash_point_c is not None and temperature < fluid.flash_point_c)
    match(2, 'health', fluid.nfpa_health == 2)
    match(2, 'corrosive', fluid.is_corrosive)
    match(2, 'asphyxiant', fluid.is_asphyxiant)
    match(2, 'warm', temperature is not None and 60 <= temperature < 150)
    match(2, 'pressure', pressure is not None and pressure >= 10)
    match(1, 'low_hazard', not hazardous and pressure is not None and pressure < 10 and temperature is not None and temperature < 60)
    if not rules:
        gaps.append('hsc_criteria_incomplete')
    if liquid and fluid.nfpa_flammability and fluid.flash_point_c is None:
        gaps.append('flashpoint_missing')
    if fluid.hsc_override is not None:
        gaps.append('hsc_override_precedence_unapproved')
    # Unknown cases remain conservatively 4 without asserting that this solves them.
    unresolved = [gap for gap in gaps if gap != 'hsc_override_precedence_unapproved']
    value = 4 if unresolved else (int(fluid.hsc_override) if fluid.hsc_override else max(x['level'] for x in rules))
    return {'value': value, 'rules': rules, 'blockers': gaps,
            'override_claim': int(fluid.hsc_override) if fluid.hsc_override else None,
            'precedence': 'highest_match_development_proposal', 'psd_reduction_applied': False}


def derive_ec(scope, sic):
    s, p = scope.to_dict(), sic.to_dict()['parameters']['escalation_thresholds']
    matches = []
    if not s['containment_break']: matches.append(('A', 'REQ-6.2:external'))
    if s['containment_break'] and s['shift_coverage'] == 'single_shift' and s['continuously_attended']:
        matches.append(('B', 'REQ-6.2:attended_break'))
    if (s['containment_break'] and (s['shift_coverage'] == 'multiple_shifts' or not s['continuously_attended'])) or s['equipment_leaves_site']:
        matches.append(('C', 'REQ-6.2:extended_exposure'))
    if s['personnel_enter_boundary'] or s['hot_work_on_or_within_boundary']:
        matches.append(('D', 'REQ-6.2:entry_or_hot_work'))
    value = max((x[0] for x in matches), default='D')
    rules = [x[1] for x in matches]
    if s['expected_duration_days'] >= p['duration_escalate_days']:
        value = 'ABCD'[min('ABCD'.index(value) + 1, 3)]
        rules.append('REQ-6.2:duration_escalation')
    return {'value': value, 'rules': rules, 'positive_mandatory': s['expected_duration_days'] >= p['positive_isolation_mandatory_days'],
            'precedence': 'highest_match_development_proposal'}
