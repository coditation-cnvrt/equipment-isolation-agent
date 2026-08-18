from __future__ import annotations

from enum import Enum


class StringEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class IsolationDecision(StringEnum):
    AUTOMATIC = "automatic"
    CONDITIONAL_MANUAL_REVIEW = "conditional_manual_review"
    CONTEXT = "context"
    EXCLUDED = "excluded"
    NOT_ISOLATION = "not_isolation"


class FlowRole(StringEnum):
    INLET = "inlet"
    OUTLET = "outlet"
    BIDIRECTIONAL = "bidirectional"
    UNKNOWN = "unknown"


class SourceType(StringEnum):
    PROCESS = "process"
    RELIEF_CONTEXT = "relief_context"
    INSTRUMENT_CONTEXT = "instrument_context"


class ObligationStatus(StringEnum):
    ISOLATED = "isolated"
    UNRESOLVED = "unresolved"
    CONTEXT = "context"


class AssuranceStatus(StringEnum):
    NOT_ISOLATED = "not_isolated"
    PROVISIONAL_UNPROVEN_ISOLATION = "provisional_unproven_isolation"
    COMPLETE_POSITIVE_ISOLATION = "complete_positive_isolation"
    COMPLETE_PROVEN_ISOLATION = "complete_proven_isolation"
    INSUFFICIENT_DATA = "insufficient_data"


class AssuranceReasonCode(StringEnum):
    NO_ISOLATION_CANDIDATES = "no_isolation_candidates"
    NO_DETERMINISTIC_BARRIER = "no_deterministic_barrier"
    BOUNDARY_PATH_WITHOUT_BARRIER = "boundary_path_without_barrier"
    CONDITIONAL_DEVICE_MANUAL_REVIEW = "conditional_device_manual_review"
    EVIDENCE_CHECK_INCOMPLETE = "evidence_check_incomplete"
    ZERO_ENERGY_VERIFICATION_MISSING = "zero_energy_verification_missing"


class AssuranceTerminalReason(StringEnum):
    UNRESOLVED_OFF_PAGE_CONNECTOR = "unresolved_off_page_connector"
    TOPOLOGY_SEARCH_LIMIT_REACHED = "topology_search_limit_reached"
    PATH_ENDED_WITHOUT_BARRIER = "path_ended_without_barrier"
    UNKNOWN = "unknown"


class ImpactSeverity(StringEnum):
    LIKELY = "likely"
    POSSIBLE = "possible"


class OverlayKind(StringEnum):
    TARGET = "target"
    ISOLATION = "isolation"
    SCHEME = "scheme"
    IMPACT = "impact"
    MANUAL = "manual"
    OBLIGATION_MANUAL = "obligation_manual"
    CONTEXT = "context"
    INSTRUMENT = "instrument"
    RELIEF = "relief"


class EvidenceKind(StringEnum):
    BARRIER = "barrier"
    POSITIVE_ISOLATION = "positive_isolation"
    VERIFICATION = "verification"
