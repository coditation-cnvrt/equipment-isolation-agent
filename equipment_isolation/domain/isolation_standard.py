from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from equipment_isolation.domain.enums import StringEnum


class IsolationStandardValidationError(ValueError):
    pass


class HazardSeverityClass(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    EXTREME = 4


class ExposureClass(StringEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class FluidPhase(StringEnum):
    LIQUID = "liquid"
    GAS = "gas"
    TWO_PHASE = "two_phase"
    FLASHING_LIQUID = "flashing_liquid"


class SpecialHazard(StringEnum):
    PYROPHORIC = "pyrophoric"
    WATER_REACTIVE = "water_reactive"
    OXIDISER = "oxidiser"
    POLYMERISING = "polymerising"
    CATALYST_BEARING = "catalyst_bearing"
    NONE = "none"


class FluidResolutionStatus(StringEnum):
    RESOLVED = "resolved"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class FhrDocument:
    title: str
    revision: str
    status: str
    approved_by: str
    approved_date: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FhrDocument":
        return cls(
            title=_required_string(payload, "title", "document"),
            revision=_required_string(payload, "revision", "document"),
            status=_required_string(payload, "status", "document"),
            approved_by=_optional_string(payload.get("approved_by")),
            approved_date=_optional_string(payload.get("approved_date")),
        )

    @property
    def is_approved(self) -> bool:
        return self.status.lower() == "approved" and bool(self.approved_by and self.approved_date)


@dataclass(frozen=True)
class FluidHazard:
    fluid_code: str
    service_description: str
    phase_at_operating: FluidPhase
    nfpa_health: int
    nfpa_flammability: int
    nfpa_instability: int
    special_hazards: tuple[SpecialHazard, ...]
    h2s_content_ppm: float | None
    benzene_content_pct: float | None
    idlh_ppm: float | None
    tlv_twa_ppm: float | None
    flash_point_c: float | None
    autoignition_temp_c: float | None
    normal_boiling_point_c: float | None
    is_asphyxiant: bool
    is_cryogenic: bool
    is_corrosive: bool
    hsc_override: HazardSeverityClass | None
    source_document: str
    revision: str
    approved_by: str
    approved_date: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, index: int) -> "FluidHazard":
        location = f"fluids[{index}]"
        hazards = _special_hazards(payload.get("special_hazards"), location)
        override_value = payload.get("hsc_override")
        override = None
        if override_value not in (None, ""):
            override = HazardSeverityClass(_bounded_int(override_value, 1, 4, f"{location}.hsc_override"))
        return cls(
            fluid_code=_code(payload.get("fluid_code"), f"{location}.fluid_code"),
            service_description=_required_string(payload, "service_description", location),
            phase_at_operating=_enum_value(FluidPhase, payload.get("phase_at_operating"), f"{location}.phase_at_operating"),
            nfpa_health=_bounded_int(payload.get("nfpa_health"), 0, 4, f"{location}.nfpa_health"),
            nfpa_flammability=_bounded_int(payload.get("nfpa_flammability"), 0, 4, f"{location}.nfpa_flammability"),
            nfpa_instability=_bounded_int(payload.get("nfpa_instability"), 0, 4, f"{location}.nfpa_instability"),
            special_hazards=hazards,
            h2s_content_ppm=_optional_nonnegative_number(payload.get("h2s_content_ppm"), f"{location}.h2s_content_ppm"),
            benzene_content_pct=_optional_percentage(payload.get("benzene_content_pct"), f"{location}.benzene_content_pct"),
            idlh_ppm=_optional_nonnegative_number(payload.get("idlh_ppm"), f"{location}.idlh_ppm"),
            tlv_twa_ppm=_optional_nonnegative_number(payload.get("tlv_twa_ppm"), f"{location}.tlv_twa_ppm"),
            flash_point_c=_optional_number(payload.get("flash_point_c"), f"{location}.flash_point_c"),
            autoignition_temp_c=_optional_number(payload.get("autoignition_temp_c"), f"{location}.autoignition_temp_c"),
            normal_boiling_point_c=_optional_number(payload.get("normal_boiling_point_c"), f"{location}.normal_boiling_point_c"),
            is_asphyxiant=_required_bool(payload.get("is_asphyxiant"), f"{location}.is_asphyxiant"),
            is_cryogenic=_required_bool(payload.get("is_cryogenic"), f"{location}.is_cryogenic"),
            is_corrosive=_required_bool(payload.get("is_corrosive"), f"{location}.is_corrosive"),
            hsc_override=override,
            source_document=_required_string(payload, "source_document", location),
            revision=_required_string(payload, "revision", location),
            approved_by=_optional_string(payload.get("approved_by")),
            approved_date=_optional_string(payload.get("approved_date")),
        )


@dataclass(frozen=True)
class ServiceCodeMapping:
    pid_service_code: str
    fluid_code: str
    unit_scope: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, index: int) -> "ServiceCodeMapping":
        location = f"service_code_map[{index}]"
        return cls(
            pid_service_code=_code(payload.get("pid_service_code"), f"{location}.pid_service_code"),
            fluid_code=_code(payload.get("fluid_code"), f"{location}.fluid_code"),
            unit_scope=_optional_string(payload.get("unit_scope")),
        )


@dataclass(frozen=True)
class FluidResolution:
    status: FluidResolutionStatus
    service_code: str
    fluid: FluidHazard | None
    mapping: ServiceCodeMapping | None
    conservative_hsc: HazardSeverityClass | None
    gap_code: str
    blocks_authorisation: bool


@dataclass(frozen=True)
class ServiceCodeEvidence:
    source_kind: str
    source_id: str
    service_code: str


@dataclass(frozen=True)
class PathFluidAssessment:
    path_id: str
    service_codes: tuple[str, ...]
    evidence: tuple[ServiceCodeEvidence, ...]
    resolution: FluidResolution


@dataclass(frozen=True)
class FluidHazardRegister:
    document: FhrDocument
    fluids: tuple[FluidHazard, ...]
    service_code_map: tuple[ServiceCodeMapping, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FluidHazardRegister":
        if not isinstance(payload, dict):
            raise IsolationStandardValidationError("FHR must be an object")
        document_payload = payload.get("document")
        if not isinstance(document_payload, dict):
            raise IsolationStandardValidationError("document must be an object")
        fluid_rows = payload.get("fluids")
        mapping_rows = payload.get("service_code_map")
        if not isinstance(fluid_rows, list) or not fluid_rows:
            raise IsolationStandardValidationError("fluids must be a non-empty array")
        if not isinstance(mapping_rows, list):
            raise IsolationStandardValidationError("service_code_map must be an array")

        document = FhrDocument.from_dict(document_payload)
        fluids = tuple(
            FluidHazard.from_dict(_object_row(row, f"fluids[{index}]"), index=index)
            for index, row in enumerate(fluid_rows)
        )
        mappings = tuple(
            ServiceCodeMapping.from_dict(_object_row(row, f"service_code_map[{index}]"), index=index)
            for index, row in enumerate(mapping_rows)
        )

        fluids_by_code: dict[str, FluidHazard] = {}
        for fluid in fluids:
            if fluid.fluid_code in fluids_by_code:
                raise IsolationStandardValidationError(f"duplicate fluid_code {fluid.fluid_code!r}")
            if fluid.revision != document.revision:
                raise IsolationStandardValidationError(
                    f"fluid {fluid.fluid_code!r} revision does not match document revision"
                )
            fluids_by_code[fluid.fluid_code] = fluid

        mapping_keys: set[tuple[str, str]] = set()
        for mapping in mappings:
            key = (mapping.pid_service_code, _scope_key(mapping.unit_scope))
            if key in mapping_keys:
                raise IsolationStandardValidationError(
                    f"duplicate pid_service_code {mapping.pid_service_code!r} in unit scope {mapping.unit_scope!r}"
                )
            mapping_keys.add(key)
            if mapping.fluid_code not in fluids_by_code:
                raise IsolationStandardValidationError(
                    f"service code {mapping.pid_service_code!r} references unknown fluid {mapping.fluid_code!r}"
                )
        return cls(document=document, fluids=fluids, service_code_map=mappings)

    def assert_approved(self) -> None:
        if not self.document.is_approved:
            raise IsolationStandardValidationError(
                f"FHR revision {self.document.revision!r} is not approved"
            )
        for fluid in self.fluids:
            if not fluid.approved_by or not fluid.approved_date:
                raise IsolationStandardValidationError(
                    f"fluid {fluid.fluid_code!r} has no approval record"
                )

    def resolve_fluid(self, service_code: str, *, unit_scope: str = "") -> FluidResolution:
        code = _optional_code(service_code)
        if not code:
            return _unresolved_fluid("", "service_code_missing", FluidResolutionStatus.UNKNOWN)

        matches = [mapping for mapping in self.service_code_map if mapping.pid_service_code == code]
        if not matches:
            return _unresolved_fluid(code, "fhr_mapping_missing", FluidResolutionStatus.UNKNOWN)

        scope = _scope_key(unit_scope)
        if len(matches) > 1:
            # Global/specific precedence is not defined by the requirements.
            return _unresolved_fluid(code, "fhr_mapping_scope_ambiguous", FluidResolutionStatus.BLOCKED)

        mapping = matches[0]
        mapping_scope = _scope_key(mapping.unit_scope)
        if mapping_scope and not scope:
            return _unresolved_fluid(code, "fhr_unit_scope_required", FluidResolutionStatus.BLOCKED)
        if mapping_scope and mapping_scope != scope:
            return _unresolved_fluid(code, "fhr_mapping_missing_for_unit", FluidResolutionStatus.UNKNOWN)

        fluid = next(item for item in self.fluids if item.fluid_code == mapping.fluid_code)
        return FluidResolution(
            status=FluidResolutionStatus.RESOLVED,
            service_code=code,
            fluid=fluid,
            mapping=mapping,
            conservative_hsc=None,
            gap_code="",
            blocks_authorisation=False,
        )


def resolve_path_fluid(
    path: dict[str, Any],
    register: FluidHazardRegister,
    *,
    unit_scope: str = "",
    require_approved: bool = True,
) -> PathFluidAssessment:
    if require_approved:
        register.assert_approved()
    evidence = tuple(_path_service_code_evidence(path))
    service_codes = tuple(sorted({item.service_code for item in evidence}))
    if not service_codes:
        resolution = _unresolved_fluid("", "path_service_code_missing", FluidResolutionStatus.UNKNOWN)
    elif len(service_codes) > 1:
        resolution = _unresolved_fluid(
            ",".join(service_codes),
            "path_service_code_conflict",
            FluidResolutionStatus.BLOCKED,
        )
    else:
        resolution = register.resolve_fluid(service_codes[0], unit_scope=unit_scope)
    return PathFluidAssessment(
        path_id=str(path.get("path_id") or path.get("branch_id") or ""),
        service_codes=service_codes,
        evidence=evidence,
        resolution=resolution,
    )


@dataclass(frozen=True)
class RequiredBarrierConfiguration:
    barrier_count: int
    bleed_required: bool
    positive_barrier_count: int
    physical_disconnection_required: bool
    both_sides_blinded_required: bool
    description: str
    matrix_cell: str


_RBC_MATRIX: dict[tuple[HazardSeverityClass, ExposureClass], RequiredBarrierConfiguration] = {}


def base_required_barrier_configuration(
    hsc: HazardSeverityClass | int,
    ec: ExposureClass | str,
) -> RequiredBarrierConfiguration:
    hazard = hsc if isinstance(hsc, HazardSeverityClass) else HazardSeverityClass(hsc)
    exposure = ec if isinstance(ec, ExposureClass) else ExposureClass(str(ec).upper())
    return _RBC_MATRIX[(hazard, exposure)]


def _rbc(
    hsc: HazardSeverityClass,
    ec: ExposureClass,
    *,
    barriers: int,
    bleed: bool = False,
    positive: int = 0,
    disconnection: bool = False,
    blinded_both_sides: bool = False,
    description: str,
) -> RequiredBarrierConfiguration:
    return RequiredBarrierConfiguration(
        barrier_count=barriers,
        bleed_required=bleed,
        positive_barrier_count=positive,
        physical_disconnection_required=disconnection,
        both_sides_blinded_required=blinded_both_sides,
        description=description,
        matrix_cell=f"HSC-{int(hsc)}/EC-{ec.value}",
    )


_RBC_MATRIX.update(
    {
        (HazardSeverityClass.LOW, ExposureClass.A): _rbc(HazardSeverityClass.LOW, ExposureClass.A, barriers=1, description="1 valve"),
        (HazardSeverityClass.LOW, ExposureClass.B): _rbc(HazardSeverityClass.LOW, ExposureClass.B, barriers=1, description="1 valve"),
        (HazardSeverityClass.LOW, ExposureClass.C): _rbc(HazardSeverityClass.LOW, ExposureClass.C, barriers=1, bleed=True, description="1 valve + bleed"),
        (HazardSeverityClass.LOW, ExposureClass.D): _rbc(HazardSeverityClass.LOW, ExposureClass.D, barriers=2, positive=1, description="2 barriers, at least 1 positive"),
        (HazardSeverityClass.MEDIUM, ExposureClass.A): _rbc(HazardSeverityClass.MEDIUM, ExposureClass.A, barriers=1, description="1 valve"),
        (HazardSeverityClass.MEDIUM, ExposureClass.B): _rbc(HazardSeverityClass.MEDIUM, ExposureClass.B, barriers=1, bleed=True, description="1 valve + bleed"),
        (HazardSeverityClass.MEDIUM, ExposureClass.C): _rbc(HazardSeverityClass.MEDIUM, ExposureClass.C, barriers=2, bleed=True, description="2 barriers + bleed"),
        (HazardSeverityClass.MEDIUM, ExposureClass.D): _rbc(HazardSeverityClass.MEDIUM, ExposureClass.D, barriers=2, positive=1, description="2 barriers, at least 1 positive"),
        (HazardSeverityClass.HIGH, ExposureClass.A): _rbc(HazardSeverityClass.HIGH, ExposureClass.A, barriers=1, description="1 valve"),
        (HazardSeverityClass.HIGH, ExposureClass.B): _rbc(HazardSeverityClass.HIGH, ExposureClass.B, barriers=2, bleed=True, description="2 barriers + bleed (DBB)"),
        (HazardSeverityClass.HIGH, ExposureClass.C): _rbc(HazardSeverityClass.HIGH, ExposureClass.C, barriers=2, bleed=True, positive=1, description="2 barriers, at least 1 positive, + bleed"),
        (HazardSeverityClass.HIGH, ExposureClass.D): _rbc(HazardSeverityClass.HIGH, ExposureClass.D, barriers=2, bleed=True, positive=1, description="2 barriers, at least 1 positive, + bleed"),
        (HazardSeverityClass.EXTREME, ExposureClass.A): _rbc(HazardSeverityClass.EXTREME, ExposureClass.A, barriers=2, bleed=True, description="2 barriers + bleed"),
        (HazardSeverityClass.EXTREME, ExposureClass.B): _rbc(HazardSeverityClass.EXTREME, ExposureClass.B, barriers=2, bleed=True, positive=1, description="2 barriers, at least 1 positive, + bleed"),
        (HazardSeverityClass.EXTREME, ExposureClass.C): _rbc(HazardSeverityClass.EXTREME, ExposureClass.C, barriers=2, bleed=True, positive=1, description="2 barriers, at least 1 positive, + bleed"),
        (HazardSeverityClass.EXTREME, ExposureClass.D): _rbc(
            HazardSeverityClass.EXTREME,
            ExposureClass.D,
            barriers=2,
            positive=2,
            disconnection=True,
            blinded_both_sides=True,
            description="physical disconnection + blinded both sides",
        ),
    }
)


def _unresolved_fluid(
    service_code: str,
    gap_code: str,
    status: FluidResolutionStatus,
) -> FluidResolution:
    return FluidResolution(
        status=status,
        service_code=service_code,
        fluid=None,
        mapping=None,
        conservative_hsc=HazardSeverityClass.EXTREME,
        gap_code=gap_code,
        blocks_authorisation=True,
    )


def _path_service_code_evidence(path):
    collections = (
        ("hilt_link", path.get("path_link_facts") or path.get("branch_path_link_facts") or []),
        ("unigraph_edge", path.get("path_edge_facts") or path.get("branch_path_edge_facts") or []),
        ("unigraph_node", path.get("path_node_facts") or path.get("branch_path_node_facts") or []),
    )
    result = []
    seen = set()
    for source_kind, facts in collections:
        for index, fact in enumerate(facts):
            if not isinstance(fact, dict):
                continue
            properties = fact.get("properties") if isinstance(fact.get("properties"), dict) else {}
            codes = _explicit_service_codes(fact, properties)
            source_id = str(
                fact.get("line_id")
                or fact.get("edge_id")
                or fact.get("id")
                or f"{source_kind}:{index}"
            )
            for code in codes:
                key = (source_kind, source_id, code)
                if key in seen:
                    continue
                seen.add(key)
                result.append(
                    ServiceCodeEvidence(
                        source_kind=source_kind,
                        source_id=source_id,
                        service_code=code,
                    )
                )
    return result


def _explicit_service_codes(fact, properties):
    values = []
    for source in (fact, properties, *(fact.get("service_code_evidence") or [])):
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            normalized_key = "".join(ch for ch in str(key).casefold() if ch.isalnum())
            if normalized_key not in {"fluidcode", "servicecode"}:
                continue
            candidates = value if isinstance(value, (list, tuple, set)) else (value,)
            for candidate in candidates:
                code = _optional_code(candidate)
                if code:
                    values.append(code)
    return tuple(sorted(set(values)))


def _object_row(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IsolationStandardValidationError(f"{location} must be an object")
    return value


def _required_string(payload: dict[str, Any], key: str, location: str) -> str:
    value = _optional_string(payload.get(key))
    if not value:
        raise IsolationStandardValidationError(f"{location}.{key} is required")
    return value


def _optional_string(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise IsolationStandardValidationError("expected a string")
    return value.strip()


def _optional_code(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise IsolationStandardValidationError("service code must be a string")
    return value.strip().upper()


def _code(value: Any, location: str) -> str:
    code = _optional_code(value)
    if not code:
        raise IsolationStandardValidationError(f"{location} is required")
    return code


def _scope_key(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _bounded_int(value: Any, minimum: int, maximum: int, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise IsolationStandardValidationError(f"{location} must be an integer from {minimum} to {maximum}")
    return value


def _required_bool(value: Any, location: str) -> bool:
    if not isinstance(value, bool):
        raise IsolationStandardValidationError(f"{location} must be a boolean")
    return value


def _optional_number(value: Any, location: str) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IsolationStandardValidationError(f"{location} must be a number or null")
    number = float(value)
    if not math.isfinite(number):
        raise IsolationStandardValidationError(f"{location} must be finite")
    return number


def _optional_nonnegative_number(value: Any, location: str) -> float | None:
    number = _optional_number(value, location)
    if number is not None and number < 0:
        raise IsolationStandardValidationError(f"{location} must not be negative")
    return number


def _optional_percentage(value: Any, location: str) -> float | None:
    number = _optional_nonnegative_number(value, location)
    if number is not None and number > 100:
        raise IsolationStandardValidationError(f"{location} must not exceed 100")
    return number


def _enum_value(enum_type, value: Any, location: str):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        values = ", ".join(item.value for item in enum_type)
        raise IsolationStandardValidationError(f"{location} must be one of: {values}") from exc


def _special_hazards(value: Any, location: str) -> tuple[SpecialHazard, ...]:
    if not isinstance(value, list) or not value:
        raise IsolationStandardValidationError(f"{location}.special_hazards must be a non-empty array")
    hazards = tuple(_enum_value(SpecialHazard, item, f"{location}.special_hazards") for item in value)
    if len(set(hazards)) != len(hazards):
        raise IsolationStandardValidationError(f"{location}.special_hazards contains duplicates")
    if SpecialHazard.NONE in hazards and len(hazards) > 1:
        raise IsolationStandardValidationError(f"{location}.special_hazards cannot combine 'none' with another hazard")
    return tuple(sorted(hazards, key=lambda item: item.value))
