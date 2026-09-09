"""HTTP route handlers for the isolation API."""

from __future__ import annotations

import logging
import os
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse

from equipment_isolation.api.models import (
    AssetConditionActionRequest,
    AssetConditionDetail,
    AssetConditionList,
    ChangeRequestDetail,
    ChangeRequestList,
    CreateIsolationPlanFromRunRequest,
    CreateAssetConditionRequest,
    CreateChangeRequest,
    DerivationAccepted,
    DerivePlanRequest,
    DerivedIsolationRunRequest,
    EquipmentListRequest,
    IsolationPlanDetail,
    IsolationPlanList,
    IsolationRunRequest,
    PlanVersionContent,
    PlanVersionDiff,
    PlanningCollectionList,
    PlanningDrawingList,
    PlanningProjectList,
    PlanningUniGraphProjectList,
    RunAccepted,
    RunList,
    RunStatus,
    ReportSourceDefectRequest,
    ReclassifySourceDefectRequest,
    RecordSourceDefectRemediationRequest,
    SourceDefectActionRequest,
    AddSourceDefectEvidenceRequest,
    SourceDefectDetail,
    SourceDefectList,
    SourceDefectPolicyDetail,
)
from equipment_isolation.api.plans import PlanDomainError
from equipment_isolation.api.events import asset_condition_event_stream, source_defect_event_stream
from equipment_isolation.api.runs import RunStore, event_stream
from equipment_isolation.api.service import (
    authorize_planning_context,
    list_cnvrt_collections,
    list_cnvrt_drawings,
    get_cnvrt_drawing_image,
    get_cnvrt_hilt_graph,
    get_hilt_ui_symbols,
    get_equipment_bbox,
    list_cnvrt_projects,
    list_project_equipment,
    list_unigraph_projects,
)
from equipment_isolation.api.db import postgres_configured
from equipment_isolation.domain.source_defects import policy_catalogue

router = APIRouter()
LOGGER = logging.getLogger(__name__)


def _store(request: Request) -> RunStore:
    return request.app.state.run_store


def _plan_repository(request: Request):
    repository = getattr(_store(request), "repository", None)
    if repository is None or not hasattr(repository, "list_plans"):
        raise HTTPException(
            status_code=503,
            detail={
                "kind": "plan_store_unavailable",
                "message": "Saved-plan persistence requires PostgreSQL.",
            },
        )
    return repository


def _raise_plan_error(error: PlanDomainError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail()) from None


def _run_record(request: Request, run_id: str):
    try:
        record = _store(request).get(run_id)
    except Exception:
        LOGGER.exception("Run read failed")
        raise HTTPException(
            status_code=503,
            detail={
                "kind": "run_store_unavailable",
                "message": "Run persistence is unavailable.",
            },
        ) from None
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"kind": "unknown_run", "message": "Unknown run id."},
        )
    return record


def _bearer_token(authorization: str = "") -> str:
    value = str(authorization or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


def _plant360_token(authorization: str = "") -> str:
    return (
        _bearer_token(authorization)
        or os.environ.get("PLANT360_AUTH_TOKEN", "").strip()
    )


def _require_run_read_auth(authorization: str = "") -> str:
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={
                "kind": "missing_auth_token",
                "message": "Bearer authorization is required.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def _actor_id(request: Request) -> str:
    token_data = getattr(request.state, "token_data", None) or {}
    user = token_data.get("user") if isinstance(token_data, dict) else None
    actor = (user or {}).get("id") if isinstance(user, dict) else None
    if actor in {None, ""}:
        raise HTTPException(status_code=401, detail={"kind": "authenticated_user_missing", "message": "Authenticated CNVRT user identity is required."})
    return str(actor)


def _authorize_asset_scope(
    context: dict,
    authorization: str,
    *,
    asset_system: str = "",
) -> None:
    token = _require_run_read_auth(authorization)
    try:
        authorize_planning_context(
            context,
            token,
            asset_system=asset_system,
        )
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail={
                "kind": "asset_condition_scope_forbidden",
                "message": "The authenticated user cannot access this equipment scope.",
            },
        ) from None
    except Exception:
        LOGGER.exception("Asset-condition scope authorization failed")
        raise HTTPException(
            status_code=502,
            detail={
                "kind": "asset_condition_scope_authorization_failed",
                "message": "Unable to verify access to this equipment scope.",
            },
        ) from None


def _authorized_asset_condition(request: Request, condition_id: UUID, authorization: str):
    item = _plan_repository(request).get_asset_condition(str(condition_id))
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={"kind": "unknown_asset_condition", "message": "Unknown asset condition."},
        )
    asset = item.get("asset") or {}
    _authorize_asset_scope(
        asset.get("context") or {},
        authorization,
        asset_system=str(asset.get("external_system") or ""),
    )
    return item


def _authorize_defect_scope(context: dict, authorization: str) -> None:
    token = _require_run_read_auth(authorization)
    try:
        authorize_planning_context(context, token, asset_system="cnvrt_drawing_entity")
    except PermissionError:
        raise HTTPException(status_code=403, detail={"kind": "source_defect_scope_forbidden", "message": "The authenticated user cannot access this exact drawing."}) from None
    except Exception:
        LOGGER.exception("Source-defect drawing authorization failed")
        raise HTTPException(status_code=502, detail={"kind": "source_defect_scope_authorization_failed", "message": "Unable to verify access to this exact drawing."}) from None


def _authorized_source_defect(request: Request, defect_id: UUID, authorization: str):
    item = _plan_repository(request).get_source_defect(str(defect_id))
    if item is None:
        raise HTTPException(status_code=404, detail={"kind": "unknown_source_defect", "message": "Unknown source-data defect."})
    _authorize_defect_scope(item["context"], authorization)
    return item


def _authorize_plan_scope(context: dict, authorization: str) -> None:
    token = _require_run_read_auth(authorization)
    try:
        authorize_planning_context(
            context, token, asset_system="cnvrt_drawing_entity"
        )
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail={
                "kind": "plan_scope_forbidden",
                "message": "The authenticated user cannot access this plan's exact drawing.",
            },
        ) from None
    except Exception:
        LOGGER.exception("Plan drawing authorization failed")
        raise HTTPException(
            status_code=502,
            detail={
                "kind": "plan_scope_authorization_failed",
                "message": "Unable to verify access to this plan's exact drawing.",
            },
        ) from None


def _authorize_persisted_plan(
    repository,
    plan_id: UUID,
    authorization: str,
    *,
    version_id: UUID | None = None,
) -> dict:
    context = repository.get_plan_authorization_context(
        str(plan_id), str(version_id) if version_id is not None else None
    )
    if context is None:
        kind = "unknown_plan_version" if version_id is not None else "unknown_plan"
        message = "Unknown plan version." if version_id is not None else "Unknown plan id."
        raise HTTPException(status_code=404, detail={"kind": kind, "message": message})
    _authorize_plan_scope(context, authorization)
    return context


@router.get("/health")
def health():
    return {
        "ok": True,
        "gemini_api_key_configured": bool(os.environ.get("GEMINI_API_KEY")),
        "plant360_server_token_configured": bool(os.environ.get("PLANT360_AUTH_TOKEN")),
        "postgres_configured": postgres_configured(),
        "plan_persistence_available": postgres_configured(),
        "default_model": os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash",
    }


@router.post("/equipment")
def equipment(
    request_body: EquipmentListRequest, authorization: str = Header(default="")
):
    token = _plant360_token(authorization)
    if not token:
        raise HTTPException(
            status_code=400,
            detail={
                "kind": "missing_auth_token",
                "message": "Plant360 auth token is required.",
            },
        )
    return {"items": list_project_equipment(request_body, token)}


@router.post(
    "/asset-conditions",
    response_model=AssetConditionDetail,
    status_code=201,
)
def create_asset_condition(
    request: Request,
    request_body: CreateAssetConditionRequest,
    authorization: str = Header(default=""),
):
    _authorize_asset_scope(
        request_body.asset.context(),
        authorization,
        asset_system=request_body.asset.external_system,
    )
    try:
        return _plan_repository(request).create_asset_condition(
            request_body, _actor_id(request)
        )
    except PlanDomainError as error:
        _raise_plan_error(error)


@router.get("/asset-conditions", response_model=AssetConditionList)
def list_asset_conditions(
    request: Request,
    cnvrt_project_id: str,
    collection_id: str,
    unigraph_project_id: str,
    job_id: str = "",
    state: Literal["active", "cleared", "all"] = "active",
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    authorization: str = Header(default=""),
):
    _authorize_asset_scope(
        {
            "cnvrt_project_id": cnvrt_project_id,
            "collection_id": collection_id,
            "unigraph_project_id": unigraph_project_id,
            "job_id": job_id,
        },
        authorization,
    )
    items, total = _plan_repository(request).list_asset_conditions(
        cnvrt_project_id=cnvrt_project_id,
        collection_id=collection_id,
        unigraph_project_id=unigraph_project_id,
        job_id=job_id,
        state=state,
        limit=limit,
        offset=offset,
    )
    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "total": total,
    }


@router.get("/asset-conditions/events")
def asset_condition_events(
    request: Request,
    cnvrt_project_id: Annotated[str, Query(min_length=1)],
    collection_id: Annotated[str, Query(min_length=1)],
    unigraph_project_id: Annotated[str, Query(min_length=1)],
    job_id: str = Query(default=""),
    authorization: str = Header(default=""),
    last_event_id: str = Header(default="", alias="Last-Event-ID"),
):
    context = {
        "cnvrt_project_id": cnvrt_project_id,
        "collection_id": collection_id,
        "unigraph_project_id": unigraph_project_id,
        "job_id": job_id,
    }
    _authorize_asset_scope(context, authorization)
    repository = _plan_repository(request)
    return StreamingResponse(
        asset_condition_event_stream(
            repository,
            context,
            last_event_id=last_event_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/asset-conditions/{condition_id}", response_model=AssetConditionDetail)
def asset_condition_detail(
    request: Request,
    condition_id: UUID,
    authorization: str = Header(default=""),
):
    return _authorized_asset_condition(request, condition_id, authorization)


@router.post("/source-data-defects", response_model=SourceDefectDetail, status_code=201)
def report_source_defect(request: Request, request_body: ReportSourceDefectRequest, authorization: str = Header(default="")):
    _authorize_defect_scope(request_body.context.authorization_context(), authorization)
    try:
        return _plan_repository(request).create_source_defect(request_body, _actor_id(request))
    except PlanDomainError as error:
        _raise_plan_error(error)


@router.get("/source-data-defects/policy", response_model=SourceDefectPolicyDetail)
def source_defect_policy():
    return policy_catalogue()


@router.get("/source-data-defects", response_model=SourceDefectList)
def list_source_defects(
    request: Request,
    cnvrt_project_id: str,
    collection_id: str,
    unigraph_project_id: str,
    job_id: str,
    state: Literal["open", "reported", "confirmed", "remediation_recorded", "resolved", "rejected", "withdrawn", "all"] = "open",
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    authorization: str = Header(default=""),
):
    context = {"cnvrt_project_id": cnvrt_project_id, "collection_id": collection_id, "unigraph_project_id": unigraph_project_id, "job_id": job_id}
    _authorize_defect_scope(context, authorization)
    items, total = _plan_repository(request).list_source_defects(context=context, state=state, limit=limit, offset=offset)
    return {"items": items, "limit": limit, "offset": offset, "total": total}


@router.get("/source-data-defects/events")
def source_defect_events(
    request: Request,
    cnvrt_project_id: str,
    collection_id: str,
    unigraph_project_id: str,
    job_id: str,
    authorization: str = Header(default=""),
    last_event_id: str = Header(default="", alias="Last-Event-ID"),
):
    context = {"cnvrt_project_id": cnvrt_project_id, "collection_id": collection_id, "unigraph_project_id": unigraph_project_id, "job_id": job_id}
    _authorize_defect_scope(context, authorization)
    return StreamingResponse(source_defect_event_stream(_plan_repository(request), context, last_event_id=last_event_id), media_type="text/event-stream", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


@router.get("/source-data-defects/{defect_id}", response_model=SourceDefectDetail)
def source_defect_detail(request: Request, defect_id: UUID, authorization: str = Header(default="")):
    return _authorized_source_defect(request, defect_id, authorization)


def _source_defect_action(request: Request, defect_id: UUID, action: str, body, authorization: str):
    _authorized_source_defect(request, defect_id, authorization)
    try:
        return _plan_repository(request).transition_source_defect(str(defect_id), action, body, _actor_id(request))
    except PlanDomainError as error:
        _raise_plan_error(error)


@router.post("/source-data-defects/{defect_id}/confirm", response_model=SourceDefectDetail)
def confirm_source_defect(request: Request, defect_id: UUID, request_body: SourceDefectActionRequest, authorization: str = Header(default="")):
    return _source_defect_action(request, defect_id, "confirm", request_body, authorization)


@router.post("/source-data-defects/{defect_id}/remediation", response_model=SourceDefectDetail)
def record_source_defect_remediation(request: Request, defect_id: UUID, request_body: RecordSourceDefectRemediationRequest, authorization: str = Header(default="")):
    return _source_defect_action(request, defect_id, "remediation_recorded", request_body, authorization)


@router.post("/source-data-defects/{defect_id}/resolve", response_model=SourceDefectDetail)
def resolve_source_defect(request: Request, defect_id: UUID, request_body: SourceDefectActionRequest, authorization: str = Header(default="")):
    return _source_defect_action(request, defect_id, "resolve", request_body, authorization)


@router.post("/source-data-defects/{defect_id}/reject", response_model=SourceDefectDetail)
def reject_source_defect(request: Request, defect_id: UUID, request_body: SourceDefectActionRequest, authorization: str = Header(default="")):
    return _source_defect_action(request, defect_id, "reject", request_body, authorization)


@router.post("/source-data-defects/{defect_id}/withdraw", response_model=SourceDefectDetail)
def withdraw_source_defect(request: Request, defect_id: UUID, request_body: SourceDefectActionRequest, authorization: str = Header(default="")):
    return _source_defect_action(request, defect_id, "withdraw", request_body, authorization)


@router.post("/source-data-defects/{defect_id}/reopen", response_model=SourceDefectDetail)
def reopen_source_defect(request: Request, defect_id: UUID, request_body: SourceDefectActionRequest, authorization: str = Header(default="")):
    return _source_defect_action(request, defect_id, "reopen", request_body, authorization)


@router.post("/source-data-defects/{defect_id}/reclassify", response_model=SourceDefectDetail)
def reclassify_source_defect(request: Request, defect_id: UUID, request_body: ReclassifySourceDefectRequest, authorization: str = Header(default="")):
    _authorized_source_defect(request, defect_id, authorization)
    try:
        return _plan_repository(request).reclassify_source_defect(str(defect_id), request_body, _actor_id(request))
    except PlanDomainError as error:
        _raise_plan_error(error)


@router.post("/source-data-defects/{defect_id}/comments", response_model=SourceDefectDetail)
def comment_on_source_defect(request: Request, defect_id: UUID, request_body: SourceDefectActionRequest, authorization: str = Header(default="")):
    _authorized_source_defect(request, defect_id, authorization)
    try:
        return _plan_repository(request).annotate_source_defect(str(defect_id), "commented", request_body, _actor_id(request))
    except PlanDomainError as error:
        _raise_plan_error(error)


@router.post("/source-data-defects/{defect_id}/evidence", response_model=SourceDefectDetail)
def add_source_defect_evidence(request: Request, defect_id: UUID, request_body: AddSourceDefectEvidenceRequest, authorization: str = Header(default="")):
    _authorized_source_defect(request, defect_id, authorization)
    try:
        return _plan_repository(request).annotate_source_defect(str(defect_id), "evidence_added", request_body, _actor_id(request))
    except PlanDomainError as error:
        _raise_plan_error(error)


def _coordinate_source_defect(request: Request, defect_id: UUID, action: str, body, authorization: str):
    _authorized_source_defect(request, defect_id, authorization)
    try:
        return _plan_repository(request).coordinate_source_defect(str(defect_id), action, body, _actor_id(request))
    except PlanDomainError as error:
        _raise_plan_error(error)


@router.post("/source-data-defects/{defect_id}/claim", response_model=SourceDefectDetail)
def claim_source_defect(request: Request, defect_id: UUID, request_body: SourceDefectActionRequest, authorization: str = Header(default="")):
    return _coordinate_source_defect(request, defect_id, "claimed", request_body, authorization)


@router.post("/source-data-defects/{defect_id}/release", response_model=SourceDefectDetail)
def release_source_defect(request: Request, defect_id: UUID, request_body: SourceDefectActionRequest, authorization: str = Header(default="")):
    return _coordinate_source_defect(request, defect_id, "released", request_body, authorization)


@router.post(
    "/asset-conditions/{condition_id}/confirm",
    response_model=AssetConditionDetail,
)
def confirm_asset_condition(
    request: Request,
    condition_id: UUID,
    request_body: AssetConditionActionRequest,
    authorization: str = Header(default=""),
):
    _authorized_asset_condition(request, condition_id, authorization)
    try:
        return _plan_repository(request).confirm_asset_condition(
            str(condition_id), request_body, _actor_id(request)
        )
    except PlanDomainError as error:
        _raise_plan_error(error)


@router.post(
    "/asset-conditions/{condition_id}/clear",
    response_model=AssetConditionDetail,
)
def clear_asset_condition(
    request: Request,
    condition_id: UUID,
    request_body: AssetConditionActionRequest,
    authorization: str = Header(default=""),
):
    _authorized_asset_condition(request, condition_id, authorization)
    try:
        return _plan_repository(request).clear_asset_condition(
            str(condition_id), request_body, _actor_id(request)
        )
    except PlanDomainError as error:
        _raise_plan_error(error)


@router.get("/planning-context/projects", response_model=PlanningProjectList)
def planning_context_projects(authorization: str = Header(default="")):
    token = _plant360_token(authorization)
    if not token:
        raise HTTPException(
            status_code=400,
            detail={
                "kind": "missing_auth_token",
                "message": "Plant360 auth token is required.",
            },
        )
    try:
        return {"items": list_cnvrt_projects(token)}
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={
                "kind": "project_discovery_failed",
                "message": "Unable to load CNVRT projects.",
            },
        ) from None


@router.get(
    "/planning-context/projects/{cnvrt_project_id}/collections",
    response_model=PlanningCollectionList,
)
def planning_context_collections(
    cnvrt_project_id: int, authorization: str = Header(default="")
):
    token = _plant360_token(authorization)
    if not token:
        raise HTTPException(
            status_code=400,
            detail={
                "kind": "missing_auth_token",
                "message": "Plant360 auth token is required.",
            },
        )
    try:
        return {"items": list_cnvrt_collections(cnvrt_project_id, token)}
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={
                "kind": "collection_discovery_failed",
                "message": "Unable to load CNVRT collections.",
            },
        ) from None


@router.get(
    "/planning-context/projects/{cnvrt_project_id}/collections/{collection_id}/drawings",
    response_model=PlanningDrawingList,
)
def planning_context_drawings(
    cnvrt_project_id: int, collection_id: int, authorization: str = Header(default="")
):
    token = _plant360_token(authorization)
    if not token:
        raise HTTPException(
            status_code=400,
            detail={
                "kind": "missing_auth_token",
                "message": "Plant360 auth token is required.",
            },
        )
    try:
        return {"items": list_cnvrt_drawings(cnvrt_project_id, collection_id, token)}
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={
                "kind": "drawing_discovery_failed",
                "message": "Unable to load CNVRT drawings.",
            },
        ) from None


@router.get(
    "/planning-context/projects/{cnvrt_project_id}/collections/{collection_id}/drawings/{job_id}/image"
)
def planning_context_drawing_image(
    cnvrt_project_id: int,
    collection_id: int,
    job_id: int,
    authorization: str = Header(default=""),
):
    token = _plant360_token(authorization)
    if not token:
        raise HTTPException(
            status_code=400,
            detail={
                "kind": "missing_auth_token",
                "message": "Plant360 auth token is required.",
            },
        )
    try:
        content, content_type = get_cnvrt_drawing_image(
            cnvrt_project_id, collection_id, job_id, token
        )
        return Response(
            content=content, media_type=content_type or "application/octet-stream"
        )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={
                "kind": "drawing_image_failed",
                "message": "Unable to load CNVRT drawing image.",
            },
        ) from None


@router.get("/planning-context/drawings/{job_id}/hilt-graph")
def planning_context_hilt_graph(job_id: int, authorization: str = Header(default="")):
    token = _plant360_token(authorization)
    if not token:
        raise HTTPException(
            status_code=400,
            detail={
                "kind": "missing_auth_token",
                "message": "Plant360 auth token is required.",
            },
        )
    try:
        return get_cnvrt_hilt_graph(job_id, token)
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={
                "kind": "hilt_graph_failed",
                "message": "Unable to load the exported HILT graph.",
            },
        ) from None


@router.get("/planning-context/symbol-projects/{symbol_project_id}/symbols")
def planning_context_symbols(
    symbol_project_id: int, authorization: str = Header(default="")
):
    token = _plant360_token(authorization)
    if not token:
        raise HTTPException(
            status_code=400,
            detail={
                "kind": "missing_auth_token",
                "message": "Plant360 auth token is required.",
            },
        )
    try:
        return get_hilt_ui_symbols(symbol_project_id, token)
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={
                "kind": "symbol_library_failed",
                "message": "Unable to load the project symbol library.",
            },
        ) from None


@router.get("/planning-context/drawings/{job_id}/equipment/{node_id}/bbox")
def planning_context_equipment_bbox(
    job_id: int, node_id: str, authorization: str = Header(default="")
):
    token = _plant360_token(authorization)
    if not token:
        raise HTTPException(
            status_code=400,
            detail={
                "kind": "missing_auth_token",
                "message": "Plant360 auth token is required.",
            },
        )
    try:
        bbox = get_equipment_bbox(job_id, node_id, token)
        if not bbox:
            raise HTTPException(
                status_code=404,
                detail={
                    "kind": "equipment_bbox_not_found",
                    "message": "Equipment is not located on this drawing.",
                },
            )
        return {"bbox": bbox}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={
                "kind": "equipment_bbox_failed",
                "message": "Unable to load equipment bbox.",
            },
        ) from None


@router.get(
    "/planning-context/projects/{cnvrt_project_id}/collections/{collection_id}/unigraph-projects",
    response_model=PlanningUniGraphProjectList,
)
def planning_context_unigraph_projects(
    cnvrt_project_id: int, collection_id: int, authorization: str = Header(default="")
):
    token = _plant360_token(authorization)
    if not token:
        raise HTTPException(
            status_code=400,
            detail={
                "kind": "missing_auth_token",
                "message": "Plant360 auth token is required.",
            },
        )
    try:
        return {"items": list_unigraph_projects(cnvrt_project_id, collection_id, token)}
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={
                "kind": "unigraph_project_discovery_failed",
                "message": "Unable to load UniGraph projects.",
            },
        ) from None


@router.post("/isolation-runs", response_model=RunAccepted, status_code=202)
def create_run(
    request: Request,
    request_body: IsolationRunRequest,
    authorization: str = Header(default=""),
):
    token = _plant360_token(authorization)
    if not token:
        raise HTTPException(
            status_code=400,
            detail={
                "kind": "missing_auth_token",
                "message": "Plant360 auth token is required.",
            },
        )
    try:
        record = _store(request).create(request_body, token)
    except Exception:
        LOGGER.exception("Run creation persistence failed")
        raise HTTPException(
            status_code=503,
            detail={
                "kind": "run_store_unavailable",
                "message": "Run persistence is unavailable.",
            },
        ) from None
    return RunAccepted(
        run_id=record.run_id,
        status=record.status,
        status_url=f"/isolation-runs/{record.run_id}",
        events_url=f"/isolation-runs/{record.run_id}/events",
    )


@router.get("/isolation-runs", response_model=RunList)
def list_runs(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    equipment_tag: str = "",
    status: str = "",
    job_id: str = "",
    cnvrt_project_id: str = "",
    collection_id: str = "",
    unigraph_project_id: str = "",
    authorization: str = Header(default=""),
):
    _require_run_read_auth(authorization)
    try:
        items = _store(request).list(
            limit=limit,
            offset=offset,
            equipment_tag=equipment_tag,
            status=status,
            job_id=job_id,
            cnvrt_project_id=cnvrt_project_id,
            collection_id=collection_id,
            unigraph_project_id=unigraph_project_id,
        )
    except Exception:
        LOGGER.exception("Run listing failed")
        raise HTTPException(
            status_code=503,
            detail={
                "kind": "run_store_unavailable",
                "message": "Run persistence is unavailable.",
            },
        ) from None
    return {"items": items}


@router.post("/isolation-plans/from-run", response_model=IsolationPlanDetail)
def create_plan_from_run(
    request: Request,
    request_body: CreateIsolationPlanFromRunRequest,
    response: Response,
    authorization: str = Header(default=""),
):
    repository = _plan_repository(request)
    source_run = repository.get_run(request_body.run_id)
    if source_run is None:
        raise HTTPException(
            status_code=404,
            detail={"kind": "unknown_run", "message": "Unknown persisted run id."},
        )
    _authorize_plan_scope((source_run.get("request") or {}), authorization)
    try:
        plan, created = repository.create_plan_from_run(
            request_body.run_id, request_body.area_code
        )
    except PlanDomainError as error:
        _raise_plan_error(error)
    except Exception:
        LOGGER.exception("Plan promotion failed")
        raise HTTPException(
            status_code=503,
            detail={
                "kind": "plan_store_unavailable",
                "message": "Saved-plan persistence is unavailable.",
            },
        ) from None
    response.status_code = 201 if created else 200
    if created:
        response.headers["Location"] = f"/isolation-plans/{plan['plan_id']}"
    return plan


@router.get("/isolation-plans", response_model=IsolationPlanList)
def list_plans(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    lifecycle_state: str = "",
    equipment_tag: str = "",
    job_id: str = "",
    cnvrt_project_id: str = "",
    collection_id: str = "",
    unigraph_project_id: str = "",
    plan_number: str = "",
    authorization: str = Header(default=""),
):
    _require_run_read_auth(authorization)
    repository = _plan_repository(request)
    filters = {
        "lifecycle_state": lifecycle_state or None,
        "equipment_tag": equipment_tag or None,
        "job_id": job_id or None,
        "cnvrt_project_id": cnvrt_project_id or None,
        "collection_id": collection_id or None,
        "unigraph_project_id": unigraph_project_id or None,
        "plan_number": plan_number or None,
    }
    try:
        authorized_contexts = []
        for context in repository.list_plan_authorization_contexts(**filters):
            try:
                _authorize_plan_scope(context, authorization)
            except HTTPException as error:
                if error.status_code == 403:
                    continue
                raise
            authorized_contexts.append(context)
        items, total = repository.list_plans(
            limit=limit,
            offset=offset,
            **filters,
            authorized_contexts=authorized_contexts,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception("Plan listing failed")
        raise HTTPException(
            status_code=503,
            detail={
                "kind": "plan_store_unavailable",
                "message": "Saved-plan persistence is unavailable.",
            },
        ) from None
    return {"items": items, "limit": limit, "offset": offset, "total": total}


@router.get("/isolation-plans/{plan_id}", response_model=IsolationPlanDetail)
def plan_detail(
    request: Request, plan_id: UUID, authorization: str = Header(default="")
):
    repository = _plan_repository(request)
    _authorize_persisted_plan(repository, plan_id, authorization)
    try:
        plan = repository.get_plan(str(plan_id))
    except Exception:
        LOGGER.exception("Plan read failed")
        raise HTTPException(
            status_code=503,
            detail={
                "kind": "plan_store_unavailable",
                "message": "Saved-plan persistence is unavailable.",
            },
        ) from None
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail={"kind": "unknown_plan", "message": "Unknown plan id."},
        )
    return plan


@router.post("/isolation-plans/{plan_id}/changes", response_model=ChangeRequestDetail, status_code=201)
def create_plan_change(request: Request, plan_id: UUID, request_body: CreateChangeRequest, authorization: str = Header(default="")):
    repository = _plan_repository(request)
    _authorize_persisted_plan(repository, plan_id, authorization)
    try:
        return repository.create_change(str(plan_id), request_body, _actor_id(request))
    except PlanDomainError as error:
        _raise_plan_error(error)


@router.get("/isolation-plans/{plan_id}/changes", response_model=ChangeRequestList)
def list_plan_changes(request: Request, plan_id: UUID, authorization: str = Header(default="")):
    repository = _plan_repository(request)
    _authorize_persisted_plan(repository, plan_id, authorization)
    try:
        return {"items": repository.list_changes(str(plan_id))}
    except PlanDomainError as error:
        _raise_plan_error(error)


@router.post("/isolation-plans/{plan_id}/changes/{change_id}/approve", response_model=ChangeRequestDetail)
def approve_plan_change(request: Request, plan_id: UUID, change_id: UUID, authorization: str = Header(default="")):
    repository = _plan_repository(request)
    _authorize_persisted_plan(repository, plan_id, authorization)
    try:
        return repository.approve_change(str(plan_id), str(change_id), _actor_id(request))
    except PlanDomainError as error:
        _raise_plan_error(error)


@router.post("/isolation-plans/{plan_id}/derive", response_model=DerivationAccepted, status_code=202)
def derive_plan(request: Request, plan_id: UUID, request_body: DerivePlanRequest, authorization: str = Header(default="")):
    token = _require_run_read_auth(authorization)
    repository = _plan_repository(request)
    _authorize_persisted_plan(repository, plan_id, authorization)
    actor_id = _actor_id(request)
    prepared = None
    try:
        prepared = repository.prepare_derivation(
            str(plan_id),
            request_body.parent_plan_version_id,
            actor_id,
            trigger=request_body.trigger,
        )
        if not prepared['request'].get('process_safety_inputs'):
            raise PlanDomainError('process_safety_inputs_required', 'Start a new run from Workspace with FHR, SIC and PSD.', 409)
        derived_request = DerivedIsolationRunRequest.model_validate(prepared["request"])
        record = _store(request).create(derived_request, token, parent_run_id=prepared["parent_run_id"])
    except PlanDomainError as error:
        if prepared is not None:
            repository.fail_derivation_launch(prepared["manifest_id"], actor_id, {"kind": error.kind, "message": error.message})
        _raise_plan_error(error)
    except Exception as error:
        if prepared is not None:
            repository.fail_derivation_launch(prepared["manifest_id"], actor_id, {"kind": "derivation_launch_failed", "message": str(error)})
        LOGGER.exception("Correction derivation launch failed")
        raise HTTPException(status_code=503, detail={"kind": "derivation_launch_failed", "message": "Unable to launch correction derivation."}) from None
    return {"manifest_id": prepared["manifest_id"], "parent_plan_version_id": request_body.parent_plan_version_id, "run_id": record.run_id, "status": record.status, "status_url": f"/isolation-runs/{record.run_id}", "events_url": f"/isolation-runs/{record.run_id}/events"}


@router.get("/isolation-plans/{plan_id}/versions/{version_id}", response_model=PlanVersionContent)
def plan_version_detail(request: Request, plan_id: UUID, version_id: UUID, authorization: str = Header(default="")):
    repository = _plan_repository(request)
    _authorize_persisted_plan(repository, plan_id, authorization, version_id=version_id)
    try:
        item = repository.get_plan_version(str(plan_id), str(version_id))
    except PlanDomainError as error:
        _raise_plan_error(error)
    if item is None:
        raise HTTPException(status_code=404, detail={"kind": "unknown_plan_version", "message": "Unknown plan version."})
    return item


@router.get("/isolation-plans/{plan_id}/versions/{version_id}/diff", response_model=PlanVersionDiff)
def plan_version_diff(request: Request, plan_id: UUID, version_id: UUID, authorization: str = Header(default="")):
    repository = _plan_repository(request)
    _authorize_persisted_plan(repository, plan_id, authorization, version_id=version_id)
    try:
        item = repository.get_plan_version_diff(str(plan_id), str(version_id))
    except PlanDomainError as error:
        _raise_plan_error(error)
    if item is None:
        raise HTTPException(status_code=404, detail={"kind": "unknown_plan_version", "message": "Unknown plan version."})
    return item


@router.get("/isolation-runs/{run_id}", response_model=RunStatus)
def run_status(request: Request, run_id: str, authorization: str = Header(default="")):
    _require_run_read_auth(authorization)
    return _store(request).snapshot(_run_record(request, run_id), include_result=False)


@router.get("/isolation-runs/{run_id}/result")
def run_result(request: Request, run_id: str, authorization: str = Header(default="")):
    _require_run_read_auth(authorization)
    record = _run_record(request, run_id)
    if record.status != "succeeded":
        raise HTTPException(
            status_code=409,
            detail={
                "kind": "result_not_ready",
                "status": record.status,
                "error": record.error,
            },
        )
    if record.result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "kind": "result_not_available",
                "message": "Result is not available.",
            },
        )
    return record.result


@router.get("/isolation-runs/{run_id}/trace")
def run_trace(request: Request, run_id: str, authorization: str = Header(default="")):
    _require_run_read_auth(authorization)
    record = _run_record(request, run_id)
    if record.trace is not None:
        return record.trace
    raise HTTPException(
        status_code=404,
        detail={"kind": "trace_not_available", "message": "Trace is not available."},
    )


@router.get("/isolation-runs/{run_id}/events")
def run_events(request: Request, run_id: str, authorization: str = Header(default="")):
    _require_run_read_auth(authorization)
    record = _run_record(request, run_id)
    return StreamingResponse(
        event_stream(record, repository=getattr(_store(request), "repository", None)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.get('/planning-context/process-safety-example')
def process_safety_example(request: Request):
    """Explicit unapproved example documents; no drawing or approval access granted."""
    _actor_id(request)
    from equipment_isolation.fixtures.safety_examples import example_process_inputs
    return example_process_inputs()
