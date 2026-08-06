"""Service helpers that bridge API requests to the shared agent runner."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from agent.loop import DEFAULT_MODEL
from agent.runner import AgentRunResult, run_agent_pipeline
from api_client import Plant360Client
from config import ApiConfig, DEFAULT_UNIGRAPH_API_BASE_URL, JOB_IDS_BY_NAME
from image import resolve_pid_image
from output import write_json, write_viewer
from pipeline.config_builder import build_run_config
from pipeline.equipment import add_equipment_jobs, add_equipment_jobs_from_metadata, list_equipment
from pipeline.stages import resolve_project_metadata


def config_from_run_request(request, auth_token: str, output_dir: Path):
    scope = request.work_scope
    return build_run_config(
        equipment_tag=request.equipment_tag,
        job_name=request.job_name,
        job_id=request.job_id,
        project_config="",
        project_profile="__api_no_profile__",
        auth_token=auth_token,
        api_base_url=request.api_base_url,
        verify_ssl=True,
        unigraph_api_base_url=request.unigraph_api_base_url,
        cnvrt_project_id=request.cnvrt_project_id,
        collection_id=request.collection_id,
        collection_name=request.collection_name,
        host=request.host,
        port=request.port,
        project_id=request.unigraph_project_id,
        traversal_source=request.traversal_source,
        max_depth=request.max_depth,
        intrusive_work=scope.intrusive_work,
        high_risk_service=scope.high_risk_service,
        confined_space_entry=scope.confined_space_entry,
        hot_work=scope.hot_work,
        output_dir=output_dir,
    )


def config_from_equipment_request(request, auth_token: str):
    return build_run_config(
        equipment_tag="",
        project_config="",
        project_profile="__api_no_profile__",
        auth_token=auth_token,
        api_base_url=request.api_base_url,
        verify_ssl=True,
        unigraph_api_base_url=request.unigraph_api_base_url,
        cnvrt_project_id=request.cnvrt_project_id,
        collection_id=request.collection_id,
        collection_name=request.collection_name,
        host=request.host,
        port=request.port,
        project_id=request.unigraph_project_id,
        traversal_source=request.traversal_source,
    )


def list_project_equipment(request, auth_token: str):
    config = config_from_equipment_request(request, auth_token)
    config, _metadata_debug = resolve_project_metadata(config)
    items = list_equipment(config.graph, request.limit)
    add_equipment_jobs_from_metadata(items, config.job_ids_by_name)
    add_equipment_jobs(items, config.api, config.job_ids_by_name or JOB_IDS_BY_NAME)
    return items


def list_cnvrt_projects(auth_token: str) -> list[dict[str, str]]:
    """Return the authenticated user's CNVRT projects for planning-context selection."""
    client = Plant360Client(ApiConfig(auth_token=auth_token))
    items = _list_cnvrt_pages(client, "/projects", "project")
    return [
        {
            "id": str(project["id"]),
            "name": str(project.get("name") or ""),
            "status": str(project.get("status") or ""),
        }
        for project in items
        if isinstance(project, dict) and project.get("id") not in (None, "")
    ]


def _list_cnvrt_pages(client: Plant360Client, path: str, item_name: str) -> list[dict]:
    expected_path = urlparse(path).path
    items = []
    for _ in range(100):
        payload = client.get_json(path)
        page_items = payload.get("results") if isinstance(payload, dict) else payload
        if not isinstance(page_items, list):
            raise ValueError(f"CNVRT {item_name} response does not contain a list")
        items.extend(page_items)

        next_url = payload.get("next") if isinstance(payload, dict) else None
        if not next_url:
            return items
        next_path = urlparse(str(next_url))
        if next_path.path != expected_path:
            raise ValueError(f"CNVRT {item_name} pagination returned an unexpected path")
        path = next_path.path + (f"?{next_path.query}" if next_path.query else "")

    raise ValueError(f"CNVRT {item_name} pagination exceeded 100 pages")


def list_cnvrt_collections(cnvrt_project_id: int, auth_token: str) -> list[dict[str, str]]:
    """Return the authenticated user's collections for a CNVRT project."""
    client = Plant360Client(ApiConfig(auth_token=auth_token))
    items = _list_cnvrt_pages(client, f"/projects/{cnvrt_project_id}/collections", "collection")

    return [
        {
            "id": str(collection["id"]),
            "name": str(collection.get("name") or ""),
        }
        for collection in items
        if isinstance(collection, dict) and collection.get("id") not in (None, "")
    ]


def list_cnvrt_drawings(cnvrt_project_id: int, collection_id: int, auth_token: str) -> list[dict[str, str]]:
    """Return the authenticated user's drawing jobs for a CNVRT collection."""
    path = f"/projects/{cnvrt_project_id}/collections/{collection_id}/jobs"
    client = Plant360Client(ApiConfig(auth_token=auth_token))
    items = _list_cnvrt_pages(client, path, "drawing")

    return [
        {
            "id": str(drawing["id"]),
            "name": str(drawing.get("name") or ""),
            "status": str(drawing.get("status") or ""),
            "current_phase": str(drawing.get("current_phase") or ""),
            "input_file_type": str(drawing.get("input_file_type") or ""),
        }
        for drawing in items
        if isinstance(drawing, dict) and drawing.get("id") not in (None, "")
    ]


def get_cnvrt_drawing_image(cnvrt_project_id: int, collection_id: int, job_id: int, auth_token: str):
    path = f"/projects/{cnvrt_project_id}/collections/{collection_id}/jobs/{job_id}/image/source"
    return Plant360Client(ApiConfig(auth_token=auth_token)).get_bytes(path)


def list_unigraph_projects(cnvrt_project_id: int, collection_id: int, auth_token: str) -> list[dict[str, str | bool]]:
    """Return every UniGraph project mapped to the selected CNVRT project and collection."""
    client = Plant360Client(ApiConfig(base_url=DEFAULT_UNIGRAPH_API_BASE_URL, auth_token=auth_token))
    project_exports = client.get_json(f"/api/projects/by-cnvrt?cnvrt_project_id={cnvrt_project_id}")
    collection_exports = client.get_json(
        f"/api/projects/by-cnvrt?cnvrt_project_id={cnvrt_project_id}&cnvrt_collection_id={collection_id}"
    )
    if not isinstance(project_exports, list) or not isinstance(collection_exports, list):
        raise ValueError("UniGraph project response does not contain a project list")

    candidates = {
        str(project["id"]): project
        for project in [*project_exports, *collection_exports]
        if isinstance(project, dict) and project.get("id") not in (None, "")
    }
    selected = []
    for project in candidates.values():
        project_id = str(project["id"])
        collections_payload = client.get_json(f"/api/projects/{project_id}/collections")
        collections = collections_payload.get("collections") if isinstance(collections_payload, dict) else collections_payload
        if not isinstance(collections, list):
            raise ValueError("UniGraph collection response does not contain a collection list")
        if not any(str(item.get("cnvrt_collection_id") or "") == str(collection_id) for item in collections if isinstance(item, dict)):
            continue
        selected.append(
            {
                "id": project_id,
                "name": str(project.get("name") or ""),
                "state": str(project.get("state") or ""),
                "status": str(project.get("status") or ""),
                "export_type": str(project.get("export_type") or ""),
                "has_taxonomy": bool(project.get("has_taxonomy")),
            }
        )
    return selected


def execute_agent_request(
    *,
    run_id: str,
    request,
    auth_token: str,
    run_dir: Path,
    on_event: Callable | None = None,
) -> dict:
    config = config_from_run_request(request, auth_token, run_dir)
    model = request.model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
    result: AgentRunResult = run_agent_pipeline(
        config,
        model=model,
        api_key=os.environ.get("GEMINI_API_KEY", ""),
        max_steps=request.max_steps,
        on_event=on_event,
    )

    trace_payload = {
        "equipment": result.config.equipment_tag,
        "model": model,
        "agent_result": result.agent_result,
        "trace": result.trace,
    }
    write_json(run_dir / "trace.json", trace_payload)

    if not result.final_payload:
        return {
            "ok": False,
            "error": {
                "kind": "no_payload",
                "message": "No final payload produced.",
                "forced": result.agent_result.get("forced") or [],
            },
            "trace": trace_payload,
        }

    final_payload = result.final_payload
    stem = result.config.equipment_tag.replace("/", "_").replace(" ", "_")
    pid_image_url = ""
    pid_image_path = ""
    if request.image_url:
        pid_image_url = request.image_url
    else:
        _file_uri, image_debug = resolve_pid_image(result.config, run_dir, stem)
        final_payload.setdefault("debug", {}).update(image_debug)
        pid_image_path = image_debug.get("pid_image_path") or ""
        if pid_image_path:
            pid_image_url = f"/isolation-runs/{run_id}/pid-image"

    write_json(run_dir / "result.json", final_payload)
    artifacts = {"trace_url": f"/isolation-runs/{run_id}/trace"}
    if pid_image_path:
        artifacts["pid_image_url"] = f"/isolation-runs/{run_id}/pid-image"
    if request.include_viewer:
        write_viewer(run_dir / "viewer.html", final_payload, image_url=pid_image_url)
        artifacts["viewer_url"] = f"/isolation-runs/{run_id}/viewer"

    return {
        "ok": True,
        "config": result.config,
        "payload": final_payload,
        "trace": trace_payload,
        "agent": {
            "model": model,
            "steps_used": result.agent_result.get("steps_used"),
            "forced": result.agent_result.get("forced") or [],
            "assurance_status": result.agent_result.get("assurance_status"),
            "validate_terminal": result.agent_result.get("validate_terminal"),
        },
        "artifacts": artifacts,
    }
