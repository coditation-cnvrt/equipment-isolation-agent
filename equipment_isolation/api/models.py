"""Pydantic models for the isolation API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from equipment_isolation.domain.feedback import validate_feedback_category

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
    selected_asset: SelectedAssetRequest | None = None
    model: str = ""
    max_steps: int = 16
    runner: Literal["agentic"] = "agentic"

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
