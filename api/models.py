"""Pydantic models for the isolation API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class WorkScopeRequest(BaseModel):
    intrusive_work: bool = True
    high_risk_service: bool = True
    confined_space_entry: bool = False
    hot_work: bool = False


class IsolationRunRequest(BaseModel):
    equipment_tag: str = Field(..., min_length=1)
    job_name: str = ""
    job_id: str = ""
    cnvrt_project_id: str = Field(..., min_length=1)
    collection_id: str = Field(..., min_length=1)
    unigraph_project_id: str = Field(..., min_length=1)
    collection_name: str = ""
    api_base_url: str = "https://api.plant360.ai:8080"
    unigraph_api_base_url: str = ""
    host: str = ""
    port: str = ""
    traversal_source: str = ""
    max_depth: int | None = None
    work_scope: WorkScopeRequest = Field(default_factory=WorkScopeRequest)
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


class EquipmentListRequest(BaseModel):
    cnvrt_project_id: str = Field(..., min_length=1)
    collection_id: str = Field(..., min_length=1)
    unigraph_project_id: str = Field(..., min_length=1)
    collection_name: str = ""
    api_base_url: str = "https://api.plant360.ai:8080"
    unigraph_api_base_url: str = ""
    host: str = ""
    port: str = ""
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
