import copy
import json
import unittest
from pathlib import Path

from equipment_isolation.domain.isolation_standard import (
    ExposureClass,
    FluidHazardRegister,
    FluidResolutionStatus,
    HazardSeverityClass,
    IsolationStandardValidationError,
    base_required_barrier_configuration,
    resolve_path_fluid,
)


class FluidHazardRegisterTests(unittest.TestCase):
    def test_mock_fhr_is_structurally_valid_but_not_approved(self):
        payload = json.loads(
            (Path(__file__).parents[1] / "docs" / "mock_fhr_pnid_2151.json").read_text(encoding="utf-8")
        )

        register = FluidHazardRegister.from_dict(payload)

        self.assertEqual(len(register.fluids), 5)
        with self.assertRaisesRegex(IsolationStandardValidationError, "is not approved"):
            register.assert_approved()

    def test_approved_fhr_resolves_a_global_service_code(self):
        register = FluidHazardRegister.from_dict(_approved_fhr())

        register.assert_approved()
        resolution = register.resolve_fluid(" cw ")

        self.assertEqual(resolution.status, FluidResolutionStatus.RESOLVED)
        self.assertEqual(resolution.service_code, "CW")
        self.assertEqual(resolution.fluid.fluid_code, "COOLING_WATER")
        self.assertFalse(resolution.blocks_authorisation)
        self.assertIsNone(resolution.conservative_hsc)

    def test_unknown_service_is_hsc4_and_blocks_authorisation(self):
        register = FluidHazardRegister.from_dict(_approved_fhr())

        resolution = register.resolve_fluid("UNKNOWN")

        self.assertEqual(resolution.status, FluidResolutionStatus.UNKNOWN)
        self.assertEqual(resolution.gap_code, "fhr_mapping_missing")
        self.assertEqual(resolution.conservative_hsc, HazardSeverityClass.EXTREME)
        self.assertTrue(resolution.blocks_authorisation)

    def test_multiple_scoped_meanings_fail_closed_until_precedence_is_approved(self):
        payload = _approved_fhr()
        payload["fluids"].append(
            {
                **payload["fluids"][0],
                "fluid_code": "PROCESS_WATER",
                "service_description": "Process water",
            }
        )
        payload["service_code_map"] = [
            {"pid_service_code": "W", "fluid_code": "COOLING_WATER", "unit_scope": "Utilities"},
            {"pid_service_code": "W", "fluid_code": "PROCESS_WATER", "unit_scope": "Process"},
        ]
        register = FluidHazardRegister.from_dict(payload)

        resolution = register.resolve_fluid("W", unit_scope="Utilities")

        self.assertEqual(resolution.status, FluidResolutionStatus.BLOCKED)
        self.assertEqual(resolution.gap_code, "fhr_mapping_scope_ambiguous")
        self.assertEqual(resolution.conservative_hsc, HazardSeverityClass.EXTREME)

    def test_duplicate_mapping_in_same_scope_is_rejected(self):
        payload = _approved_fhr()
        payload["service_code_map"].append(copy.deepcopy(payload["service_code_map"][0]))

        with self.assertRaisesRegex(IsolationStandardValidationError, "duplicate pid_service_code"):
            FluidHazardRegister.from_dict(payload)

    def test_mapping_to_missing_fluid_is_rejected(self):
        payload = _approved_fhr()
        payload["service_code_map"][0]["fluid_code"] = "MISSING"

        with self.assertRaisesRegex(IsolationStandardValidationError, "references unknown fluid"):
            FluidHazardRegister.from_dict(payload)

    def test_invalid_fhr_domains_are_rejected(self):
        mutations = (
            ("invalid phase", lambda row: row.update(phase_at_operating="solid"), "phase_at_operating"),
            ("invalid NFPA", lambda row: row.update(nfpa_health=5), "nfpa_health"),
            ("invalid override", lambda row: row.update(hsc_override=0), "hsc_override"),
            (
                "none plus hazard",
                lambda row: row.update(special_hazards=["none", "pyrophoric"]),
                "cannot combine",
            ),
        )
        for name, mutate, expected in mutations:
            with self.subTest(name=name):
                payload = _approved_fhr()
                mutate(payload["fluids"][0])
                with self.assertRaisesRegex(IsolationStandardValidationError, expected):
                    FluidHazardRegister.from_dict(payload)

    def test_hilt_path_fluid_code_resolves_against_approved_fhr(self):
        register = FluidHazardRegister.from_dict(_approved_fhr())

        assessment = resolve_path_fluid(
            {
                "branch_id": "hilt:1",
                "path_link_facts": [
                    {"line_id": "L1", "fluid_code": "CW", "service_designation": "Cooling water"},
                    {"line_id": "L2", "fluid_code": "CW"},
                ],
            },
            register,
        )

        self.assertEqual(assessment.path_id, "hilt:1")
        self.assertEqual(assessment.service_codes, ("CW",))
        self.assertEqual([item.source_id for item in assessment.evidence], ["L1", "L2"])
        self.assertEqual(assessment.resolution.status, FluidResolutionStatus.RESOLVED)
        self.assertEqual(assessment.resolution.fluid.fluid_code, "COOLING_WATER")

    def test_unigraph_node_fluid_code_resolves_without_label_inference(self):
        register = FluidHazardRegister.from_dict(_approved_fhr())

        assessment = resolve_path_fluid(
            {
                "path_id": "unigraph:1",
                "path_node_facts": [
                    {"id": "P1", "properties": {"fluid_code": "cw", "service_designation": "ignored"}}
                ],
            },
            register,
        )

        self.assertEqual(assessment.service_codes, ("CW",))
        self.assertEqual(assessment.evidence[0].source_kind, "unigraph_node")
        self.assertEqual(assessment.resolution.status, FluidResolutionStatus.RESOLVED)

    def test_path_with_conflicting_service_codes_fails_closed(self):
        register = FluidHazardRegister.from_dict(_approved_fhr())

        assessment = resolve_path_fluid(
            {
                "branch_id": "conflict",
                "path_link_facts": [
                    {"line_id": "L1", "fluid_code": "CW"},
                    {"line_id": "L2", "fluid_code": "PROCESS"},
                ],
            },
            register,
        )

        self.assertEqual(assessment.resolution.status, FluidResolutionStatus.BLOCKED)
        self.assertEqual(assessment.resolution.gap_code, "path_service_code_conflict")
        self.assertEqual(assessment.resolution.conservative_hsc, HazardSeverityClass.EXTREME)
        self.assertTrue(assessment.resolution.blocks_authorisation)

    def test_path_without_explicit_service_code_fails_closed(self):
        register = FluidHazardRegister.from_dict(_approved_fhr())

        assessment = resolve_path_fluid(
            {
                "branch_id": "missing",
                "path_link_facts": [{"line_id": "L1", "service_designation": "Cooling water"}],
            },
            register,
        )

        self.assertEqual(assessment.service_codes, ())
        self.assertEqual(assessment.resolution.status, FluidResolutionStatus.UNKNOWN)
        self.assertEqual(assessment.resolution.gap_code, "path_service_code_missing")
        self.assertEqual(assessment.resolution.conservative_hsc, HazardSeverityClass.EXTREME)

    def test_path_resolution_rejects_unapproved_fhr_by_default(self):
        payload = _approved_fhr()
        payload["document"].update(status="draft", approved_by=None, approved_date=None)
        register = FluidHazardRegister.from_dict(payload)

        with self.assertRaisesRegex(IsolationStandardValidationError, "is not approved"):
            resolve_path_fluid({"path_link_facts": [{"fluid_code": "CW"}]}, register)


class RequiredBarrierConfigurationTests(unittest.TestCase):
    def test_base_matrix_matches_all_sixteen_requirement_cells(self):
        expected = {
            (1, "A"): (1, False, 0, False, False, "1 valve"),
            (1, "B"): (1, False, 0, False, False, "1 valve"),
            (1, "C"): (1, True, 0, False, False, "1 valve + bleed"),
            (1, "D"): (2, False, 1, False, False, "2 barriers, at least 1 positive"),
            (2, "A"): (1, False, 0, False, False, "1 valve"),
            (2, "B"): (1, True, 0, False, False, "1 valve + bleed"),
            (2, "C"): (2, True, 0, False, False, "2 barriers + bleed"),
            (2, "D"): (2, False, 1, False, False, "2 barriers, at least 1 positive"),
            (3, "A"): (1, False, 0, False, False, "1 valve"),
            (3, "B"): (2, True, 0, False, False, "2 barriers + bleed (DBB)"),
            (3, "C"): (2, True, 1, False, False, "2 barriers, at least 1 positive, + bleed"),
            (3, "D"): (2, True, 1, False, False, "2 barriers, at least 1 positive, + bleed"),
            (4, "A"): (2, True, 0, False, False, "2 barriers + bleed"),
            (4, "B"): (2, True, 1, False, False, "2 barriers, at least 1 positive, + bleed"),
            (4, "C"): (2, True, 1, False, False, "2 barriers, at least 1 positive, + bleed"),
            (4, "D"): (2, False, 2, True, True, "physical disconnection + blinded both sides"),
        }

        for (hsc, ec), values in expected.items():
            with self.subTest(hsc=hsc, ec=ec):
                result = base_required_barrier_configuration(hsc, ec)
                self.assertEqual(
                    (
                        result.barrier_count,
                        result.bleed_required,
                        result.positive_barrier_count,
                        result.physical_disconnection_required,
                        result.both_sides_blinded_required,
                        result.description,
                    ),
                    values,
                )
                self.assertEqual(result.matrix_cell, f"HSC-{hsc}/EC-{ec}")

    def test_base_matrix_accepts_domain_enums(self):
        result = base_required_barrier_configuration(HazardSeverityClass.HIGH, ExposureClass.B)

        self.assertEqual(result.matrix_cell, "HSC-3/EC-B")


def _approved_fhr():
    return {
        "document": {
            "title": "Approved test FHR",
            "revision": "1",
            "status": "approved",
            "approved_by": "isolation-authority@example.test",
            "approved_date": "2026-09-08",
        },
        "fluids": [
            {
                "fluid_code": "COOLING_WATER",
                "service_description": "Cooling water",
                "phase_at_operating": "liquid",
                "nfpa_health": 0,
                "nfpa_flammability": 0,
                "nfpa_instability": 0,
                "special_hazards": ["none"],
                "h2s_content_ppm": 0,
                "benzene_content_pct": 0,
                "idlh_ppm": None,
                "tlv_twa_ppm": None,
                "flash_point_c": None,
                "autoignition_temp_c": None,
                "normal_boiling_point_c": 100,
                "is_asphyxiant": False,
                "is_cryogenic": False,
                "is_corrosive": False,
                "hsc_override": None,
                "source_document": "Test SDS",
                "revision": "1",
                "approved_by": "isolation-authority@example.test",
                "approved_date": "2026-09-08",
            }
        ],
        "service_code_map": [
            {"pid_service_code": "CW", "fluid_code": "COOLING_WATER", "unit_scope": ""}
        ],
    }


if __name__ == "__main__":
    unittest.main()
