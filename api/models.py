"""Pydantic models for the isolation API."""
from __future__ import annotations

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
    image_url: str = ""
    include_viewer: bool = True
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
    artifacts: dict[str, str] = Field(default_factory=dict)
    error: dict[str, Any] | None = None


class RunList(BaseModel):
    items: list[RunStatus]
