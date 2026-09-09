"""Pydantic models for the isolation API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from equipment_isolation.domain.feedback import validate_feedback_category
from equipment_isolation.domain.source_defects import validate_report

from equipment_isolation.domain.identity import REQUEST_SCHEMA_VERSION, RESULT_SCHEMA_VERSION


class WorkScopeRequest(BaseModel):
    intrusive_work: bool = True
    high_risk_service: bool = True
    confined_space_entry: bool = False
    hot_work: bool = False


class SelectedAssetRequest(BaseModel):
    """Exact browser selection identity; optional during the legacy transition."""

    hilt_entity_id: str = Field(..., min_length=1)
    tag: str = Field(..., min_length=1)
    entity_class: str = ""
    selection_source: Literal["hilt_equipment_list", "hilt_canvas"]

    @field_validator("hilt_entity_id", "tag")
    @classmethod
    def _identity_string_is_not_blank(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field is required")
        return value


class IsolationRunRequest(BaseModel):
    request_schema_version: Literal[REQUEST_SCHEMA_VERSION] = REQUEST_SCHEMA_VERSION
    equipment_tag: str = Field(..., min_length=1)
    job_name: str = ""
    job_id: str = ""
    cnvrt_project_id: str = Field(..., min_length=1)
    collection_id: str = Field(..., min_length=1)
    unigraph_project_id: str = Field(..., min_length=1)
    collection_name: str = ""
    traversal_source: str = ""
    max_depth: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Fail-safe hop ceiling for adaptive UniGraph branch traversal. "
            "Traversal normally stops semantically at barriers or terminals; reaching this ceiling leaves the path unresolved."
        ),
    )
    work_scope: WorkScopeRequest = Field(default_factory=WorkScopeRequest)
    selected_asset: SelectedAssetRequest
    process_safety_inputs: dict[str, Any]
    model: str = ""
    max_steps: int = 16
    runner: Literal["agentic"] = "agentic"

    @field_validator("process_safety_inputs")
    @classmethod
    def _safety_inputs(cls, value):
        from equipment_isolation.domain.process_safety import ProcessSafetyInputs
        return ProcessSafetyInputs.from_dict(value).to_dict()

    @model_validator(mode="after")
    def _safety_scope(self):
        if self.process_safety_inputs is not None:
            from equipment_isolation.domain.process_safety import ProcessSafetyInputs
            if self.selected_asset is None:
                raise ValueError("selected_asset is required with process safety inputs")
            ProcessSafetyInputs.from_dict(self.process_safety_inputs).require_scope(self.model_dump())
            scope = self.process_safety_inputs['work_scope']
            self.work_scope = WorkScopeRequest(intrusive_work=scope['containment_break'],
                high_risk_service=self.work_scope.high_risk_service,
                confined_space_entry=scope['personnel_enter_boundary'], hot_work=scope['hot_work_on_or_within_boundary'])
        return self

    @field_validator("equipment_tag", "cnvrt_project_id", "collection_id", "unigraph_project_id")
    @classmethod
    def _required_string_is_not_blank(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field is required")
        return value

    @model_validator(mode="after")
    def _validate_selected_asset_context(self):
        if self.selected_asset is None:
            return self
        if not str(self.job_id or "").strip():
            raise ValueError("job_id is required when selected_asset is supplied")
        if self.selected_asset.tag != self.equipment_tag:
            raise ValueError("selected_asset.tag must equal equipment_tag")
        return self


class DerivedIsolationRunRequest(IsolationRunRequest):
    """Server-created request; never accepted by the public run endpoint."""

    approved_corrections: list[dict[str, Any]] = Field(default_factory=list)
    derivation_context: dict[str, Any] = Field(default_factory=dict)


class EquipmentListRequest(BaseModel):
    cnvrt_project_id: str = Field(..., min_length=1)
    collection_id: str = Field(..., min_length=1)
    unigraph_project_id: str = Field(..., min_length=1)
    collection_name: str = ""
    traversal_source: str = ""
    limit: int = 0

    @field_validator("cnvrt_project_id", "collection_id", "unigraph_project_id")
    @classmethod
    def _required_string_is_not_blank(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field is required")
        return value


class AssetConditionAssetRequest(BaseModel):
    """Exact source identity for a physical asset; labels are descriptive only."""

    external_system: Literal["cnvrt_drawing_entity", "unigraph_candidate"]
    external_id: str = Field(..., min_length=1)
    tag: str = Field(..., min_length=1)
    asset_class: str = ""
    cnvrt_project_id: str = Field(..., min_length=1)
    collection_id: str = Field(..., min_length=1)
    unigraph_project_id: str = Field(..., min_length=1)
    job_id: str = ""

    @field_validator(
        "external_id",
        "tag",
        "cnvrt_project_id",
        "collection_id",
        "unigraph_project_id",
        mode="before",
    )
    @classmethod
    def _strip_required_identity(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field is required")
        return value

    @model_validator(mode="after")
    def _drawing_identity_requires_job(self):
        self.job_id = str(self.job_id or "").strip()
        if self.external_system == "cnvrt_drawing_entity" and not self.job_id:
            raise ValueError("job_id is required for a CNVRT drawing entity")
        return self

    def context(self) -> dict[str, str]:
        return {
            "cnvrt_project_id": self.cnvrt_project_id,
            "collection_id": self.collection_id,
            "unigraph_project_id": self.unigraph_project_id,
            "job_id": self.job_id,
        }


class CreateAssetConditionRequest(BaseModel):
    asset: AssetConditionAssetRequest
    condition_type: Literal["unavailable"] = "unavailable"
    reason_code: str | None = None
    notes: str = Field(..., min_length=3, max_length=4000)
    evidence: dict[str, Any] = Field(default_factory=dict)
    source_system: str | None = None
    source_reference: dict[str, Any] = Field(default_factory=dict)

    @field_validator("notes", mode="before")
    @classmethod
    def _strip_notes(cls, value: str) -> str:
        return str(value or "").strip()


class AssetConditionActionRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=4000)
    evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reason", mode="before")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        return str(value or "").strip()


class AssetConditionAssetDetail(BaseModel):
    asset_ref_id: str
    external_system: str
    scope_key: str
    external_id: str
    tag: str
    asset_class: str
    context: dict[str, Any]


class AssetConditionEventDetail(BaseModel):
    event_id: str
    event_type: Literal["reported", "confirmed", "cleared"]
    actor_id: str
    occurred_at: datetime
    payload: dict[str, Any]


class AssetConditionDetail(BaseModel):
    condition_id: str
    condition_type: Literal["unavailable"]
    state: Literal["active", "cleared"]
    reason_code: str | None = None
    notes: str
    evidence: dict[str, Any]
    source_system: str | None = None
    source_reference: dict[str, Any]
    reported_by: str
    reported_at: datetime
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    cleared_by: str | None = None
    cleared_at: datetime | None = None
    clear_reason: str | None = None
    asset: AssetConditionAssetDetail
    events: list[AssetConditionEventDetail] = Field(default_factory=list)


class AssetConditionList(BaseModel):
    items: list[AssetConditionDetail]
    limit: int
    offset: int
    total: int


DefectCategory = Literal[
    "missing_device", "extra_device", "incorrect_device_type", "incorrect_symbol",
    "incorrect_label", "incorrect_attribute", "missing_connection", "phantom_connection",
    "incorrect_connection", "off_page_connector_mismatch", "source_revision_mismatch", "other",
]
DefectState = Literal[
    "reported", "confirmed", "remediation_recorded", "resolved", "rejected", "withdrawn"
]


class SourceDefectContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cnvrt_project_id: str = Field(..., min_length=1)
    collection_id: str = Field(..., min_length=1)
    unigraph_project_id: str = Field(..., min_length=1)
    job_id: str = Field(..., min_length=1)
    reported_source_revision: str | None = None
    reported_source_snapshot_hash: str | None = None

    @field_validator("cnvrt_project_id", "collection_id", "unigraph_project_id", "job_id", mode="before")
    @classmethod
    def _strip_context(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field is required")
        return value

    @field_validator("reported_source_revision", "reported_source_snapshot_hash", mode="before")
    @classmethod
    def _strip_optional_provenance(cls, value: str | None) -> str | None:
        value = str(value or "").strip()
        return value or None

    def authorization_context(self) -> dict[str, str]:
        return self.model_dump(include={"cnvrt_project_id", "collection_id", "unigraph_project_id", "job_id"})


class SourceDefectAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    anchor_type: Literal["entity", "link", "point", "region"]
    anchor_id: str = Field(..., min_length=1)
    facts: dict[str, Any] = Field(default_factory=dict)

    @field_validator("anchor_id", mode="before")
    @classmethod
    def _strip_anchor(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("facts")
    @classmethod
    def _facts_are_client_observations_only(cls, value: dict[str, Any]) -> dict[str, Any]:
        _reject_computed_defect_fields(value)
        return value


class ReportSourceDefectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: SourceDefectContext
    category: DefectCategory
    anchor: SourceDefectAnchor
    description: str = Field(..., min_length=3, max_length=4000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    comment: str | None = Field(default=None, max_length=4000)

    @field_validator("description", mode="before")
    @classmethod
    def _strip_description(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("evidence_refs")
    @classmethod
    def _normalize_evidence_refs(cls, value: list[str]) -> list[str]:
        refs = [str(item or "").strip() for item in value]
        if any(not item for item in refs):
            raise ValueError("evidence references cannot be blank")
        return refs

    @model_validator(mode="after")
    def _validate_category_facts(self):
        validate_report(self.category, self.anchor.anchor_type, self.anchor.facts, self.evidence_refs)
        return self


class SourceDefectActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(..., ge=1)
    comment: str = Field(..., min_length=3, max_length=4000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("comment", mode="before")
    @classmethod
    def _strip_comment(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("evidence_refs")
    @classmethod
    def _strip_action_evidence(cls, value: list[str]) -> list[str]:
        refs = [str(item or "").strip() for item in value]
        if any(not item for item in refs):
            raise ValueError("evidence references cannot be blank")
        return refs


class RecordSourceDefectRemediationRequest(SourceDefectActionRequest):
    remediation: dict[str, Any]

    @field_validator("remediation")
    @classmethod
    def _remediation_is_factual(cls, value: dict[str, Any]) -> dict[str, Any]:
        _reject_computed_defect_fields(value)
        return value


class ReclassifySourceDefectRequest(SourceDefectActionRequest):
    category: DefectCategory
    anchor: SourceDefectAnchor


class AddSourceDefectEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(..., ge=1)
    evidence_refs: list[str] = Field(..., min_length=1, max_length=100)
    comment: str = Field(..., min_length=3, max_length=4000)

    @field_validator("comment", mode="before")
    @classmethod
    def _strip_evidence_comment(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("evidence_refs")
    @classmethod
    def _strip_evidence(cls, value: list[str]) -> list[str]:
        refs = [str(item or "").strip() for item in value]
        if any(not item for item in refs):
            raise ValueError("evidence references cannot be blank")
        return refs


class SourceDefectPolicyDetail(BaseModel):
    policy_version: str
    catalogue_hash: str
    categories: dict[str, dict[str, Any]]


class SourceDefectEventDetail(BaseModel):
    event_id: str
    event_type: str
    from_state: DefectState | None = None
    to_state: DefectState
    defect_version: int
    actor_id: str
    occurred_at: datetime
    payload: dict[str, Any]
    impact_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    previous_hash: str | None = None
    event_hash: str


class SourceDefectDetail(BaseModel):
    defect_id: str
    version: int
    context: dict[str, Any]
    category: DefectCategory
    anchor: dict[str, Any]
    description: str
    state: DefectState
    policy_snapshot: dict[str, Any]
    policy_hash: str
    reported_by: str
    reported_at: datetime
    updated_at: datetime
    claimed_by: str | None = None
    claimed_at: datetime | None = None
    events: list[SourceDefectEventDetail] = Field(default_factory=list)
    affected_plans: list[dict[str, Any]] = Field(default_factory=list)


class SourceDefectList(BaseModel):
    items: list[SourceDefectDetail]
    limit: int
    offset: int
    total: int


def _reject_computed_defect_fields(value: Any) -> None:
    prohibited = {
        "impact", "impacts", "scope", "affected_plan_id", "affected_plan_ids",
        "affected_plans", "severity", "policy", "policy_hash", "match_scope",
    }
    if isinstance(value, dict):
        found = prohibited.intersection(str(key).lower() for key in value)
        if found:
            raise ValueError(f"backend-computed defect fields are not accepted: {', '.join(sorted(found))}")
        for child in value.values():
            _reject_computed_defect_fields(child)
    elif isinstance(value, list):
        for child in value:
            _reject_computed_defect_fields(child)


class PlanningProject(BaseModel):
    id: str
    name: str
    status: str


class PlanningProjectList(BaseModel):
    items: list[PlanningProject]


class PlanningCollection(BaseModel):
    id: str
    name: str


class PlanningCollectionList(BaseModel):
    items: list[PlanningCollection]


class PlanningDrawing(BaseModel):
    id: str
    name: str
    status: str
    current_phase: str
    input_file_type: str


class PlanningDrawingList(BaseModel):
    items: list[PlanningDrawing]


class PlanningUniGraphProject(BaseModel):
    id: str
    name: str
    state: str
    status: str
    export_type: str
    has_taxonomy: bool


class PlanningUniGraphProjectList(BaseModel):
    items: list[PlanningUniGraphProject]


class RunAccepted(BaseModel):
    request_schema_version: Literal[REQUEST_SCHEMA_VERSION] = REQUEST_SCHEMA_VERSION
    result_schema_version: Literal[RESULT_SCHEMA_VERSION] = RESULT_SCHEMA_VERSION
    run_id: str
    status: str
    status_url: str
    events_url: str


class RunStatus(BaseModel):
    run_id: str
    status: str
    equipment_tag: str
    runner: str
    created_at: float
    started_at: float | None = None
    finished_at: float | None = None
    agent: dict[str, Any] | None = None
    request: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    parent_run_id: str | None = None
    derivation_manifest_id: str | None = None
    produced_plan_version_id: str | None = None


class RunList(BaseModel):
    items: list[RunStatus]


class CreateIsolationPlanFromRunRequest(BaseModel):
    run_id: str = Field(..., pattern=r"^[0-9a-f]{32}$")
    area_code: str | None = Field(default=None, max_length=100)

    @field_validator("area_code")
    @classmethod
    def _normalize_area_code(cls, value: str | None) -> str | None:
        value = str(value or "").strip()
        return value or None


class PlanSourceRun(BaseModel):
    run_id: str
    runner: str
    status: str
    equipment_tag: str
    created_at: datetime | None = None
    assurance_status: str | None = None
    job_id: str = ""
    job_name: str = ""
    cnvrt_project_id: str = ""
    collection_id: str = ""
    unigraph_project_id: str = ""
    request: dict[str, Any] = Field(default_factory=dict)
    agent: dict[str, Any] | None = None
    result_url: str
    trace_url: str


class PlanVersionSummary(BaseModel):
    plan_version_id: str
    parent_plan_version_id: str | None = None
    version_no: int
    derivation_status: str
    input_hash: str
    model_hash: str
    derived_at: datetime
    superseded_at: datetime | None = None
    normalization_status: Literal["complete", "legacy_incomplete"] = "legacy_incomplete"
    assurance_status: str | None = None
    source_run: PlanSourceRun


class PlanFreshnessChange(BaseModel):
    change_type: Literal["became_unavailable", "returned_to_service", "source_defect_opened", "source_defect_changed", "source_defect_closed"]
    condition_id: str | None = None
    defect_id: str | None = None
    occurred_at: datetime
    asset: AssetConditionAssetDetail | None = None
    defect: dict[str, Any] | None = None
    event_id: str | None = None
    material: bool | None = None


class PlanFreshness(BaseModel):
    status: Literal["fresh", "stale", "unknown"]
    reason: Literal["asset_condition_changed", "source_data_defect_changed", "governance_inputs_changed"] | None = None
    evaluated_at: datetime
    changes: list[PlanFreshnessChange] = Field(default_factory=list)
    governance_readiness: Literal["ready", "advisory", "warning", "blocked"] = "ready"
    source_defects: list[dict[str, Any]] = Field(default_factory=list)
    asset_conditions_changed: bool = False
    source_data_defects_changed: bool = False


class IsolationPlanSummary(BaseModel):
    plan_id: str
    plan_number: str
    active_plan_version_id: str | None = None
    mode: str
    lifecycle_state: str
    area_code: str | None = None
    created_at: datetime
    latest_plan_version_id: str
    latest_version: PlanVersionSummary
    freshness: PlanFreshness


class IsolationPlanDetail(IsolationPlanSummary):
    versions: list[PlanVersionSummary]


class IsolationPlanList(BaseModel):
    items: list[IsolationPlanSummary]
    limit: int
    offset: int
    total: int


CorrectionType = Literal[
    "accept_manual_candidate",
    "reject_manual_candidate",
    "confirm_bypass",
    "correct_label",
    "add_manual_isolation_point",
    "mark_point_unavailable",
    "mark_point_available",
]

FeedbackCategoryType = Literal[
    "input_correction",
    "requirement_deviation",
    "manual_observation",
    "execution_failure",
]


class CreateChangeRequest(BaseModel):
    raised_against_version_id: str
    change_type: CorrectionType
    feedback_category: FeedbackCategoryType | None = None
    target_type: Literal["candidate", "isolation_point", "branch"]
    target_id: str = Field(..., min_length=1)
    proposed_change: dict[str, Any] = Field(default_factory=dict)
    justification: str = Field(..., min_length=3, max_length=4000)
    source_system: str | None = None
    source_reference: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    supersedes_feedback_id: str | None = None

    @field_validator("target_id", "justification", mode="before")
    @classmethod
    def _strip_change_text(cls, value: str) -> str:
        return str(value or "").strip()

    @model_validator(mode="after")
    def _validate_change_payload(self):
        self.feedback_category = validate_feedback_category(
            self.change_type,
            self.feedback_category,
        ).value
        if self.change_type == "correct_label":
            label = str(self.proposed_change.get("label") or "").strip()
            if not label:
                raise ValueError("proposed_change.label is required for correct_label")
            self.proposed_change = {**self.proposed_change, "label": label}
        expected_status = {
            "mark_point_unavailable": "unavailable",
            "mark_point_available": "available",
        }.get(self.change_type)
        if expected_status:
            supplied_status = self.proposed_change.get("operational_status")
            if supplied_status not in (None, expected_status):
                raise ValueError(
                    f"proposed_change.operational_status must be {expected_status!r} "
                    f"for {self.change_type}"
                )
            self.proposed_change = {
                **self.proposed_change,
                "operational_status": expected_status,
            }
        return self


class FeedbackReviewDecisionDetail(BaseModel):
    review_decision_id: str
    decision: Literal["approved", "rejected"]
    actor_id: str
    reason: str | None = None
    created_at: datetime


class ChangeRequestDetail(BaseModel):
    change_id: str
    plan_id: str
    raised_against_version_id: str
    change_type: CorrectionType
    feedback_category: FeedbackCategoryType
    target_type: str
    target_id: str
    proposed_change: dict[str, Any]
    justification: str
    source_system: str | None = None
    source_reference: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    supersedes_feedback_id: str | None = None
    state: str
    raised_by: str
    approved_by: str | None = None
    created_at: datetime
    approved_at: datetime | None = None
    application_outcome: str | None = None
    coverage_status: str | None = None
    coverage_reason: str | None = None
    review_decisions: list[FeedbackReviewDecisionDetail] = Field(default_factory=list)


class ChangeRequestList(BaseModel):
    items: list[ChangeRequestDetail]


class DerivePlanRequest(BaseModel):
    parent_plan_version_id: str
    trigger: Literal["corrections", "asset_conditions", "source_data_defects"] = "corrections"


class DerivationAccepted(BaseModel):
    manifest_id: str
    parent_plan_version_id: str
    run_id: str
    status: str
    status_url: str
    events_url: str


class PlanVersionContent(BaseModel):
    plan_version_id: str
    plan_id: str
    parent_plan_version_id: str | None = None
    version_no: int
    normalization_status: str
    assurance_status: str | None = None
    content: dict[str, Any]


class DiffItem(BaseModel):
    key: str
    before: Any = None
    after: Any = None
    safety_significant: bool


class PlanVersionDiff(BaseModel):
    plan_id: str
    from_version_id: str | None = None
    to_version_id: str
    sections: dict[str, dict[str, list[DiffItem]]]
    summary: dict[str, int]
