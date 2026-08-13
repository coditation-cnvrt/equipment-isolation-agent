"""Canonical, source-scoped identity and planning-context contracts.

These immutable value objects define names and invariants at system boundaries.
They intentionally do not replace the pipeline's legacy dictionaries yet; callers
can adapt to and from dictionaries while deterministic stages are migrated.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from domain.models import BBox


REQUEST_SCHEMA_VERSION = "1.0"
RESULT_SCHEMA_VERSION = "1.0"


class IdentitySource(str, Enum):
    UNIGRAPH = "unigraph"
    CNVRT_HILT = "cnvrt_hilt"
    CNVRT_STLM = "cnvrt_stlm"
    MANUAL = "manual"


class SelectionSource(str, Enum):
    HILT_EQUIPMENT_LIST = "hilt_equipment_list"
    HILT_CANVAS = "hilt_canvas"
    CLI_TAG = "cli_tag"


class IdentityQuality(str, Enum):
    EXACT = "exact"
    LEGACY_TAG_ONLY = "legacy_tag_only"


class CoordinateFrame(str, Enum):
    IMAGE_TOP_LEFT = "image_top_left"


def _required(value: Any, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


@dataclass(frozen=True)
class ExternalIdentity:
    """An external identifier qualified by source system and project scope."""

    source_system: IdentitySource
    project_scope: str
    external_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_system", IdentitySource(self.source_system))
        object.__setattr__(self, "project_scope", _required(self.project_scope, "project_scope"))
        object.__setattr__(self, "external_id", _required(self.external_id, "external_id"))

    def to_dict(self) -> dict[str, str]:
        return {
            "source_system": self.source_system.value,
            "project_scope": self.project_scope,
            "external_id": self.external_id,
        }


@dataclass(frozen=True)
class PlanningContext:
    """Explicit CNVRT and UniGraph scope for one planning execution."""

    cnvrt_project_id: str
    collection_id: str
    unigraph_project_id: str
    job_id: str = ""
    job_name: str = ""
    collection_name: str = ""
    traversal_source: str = ""

    def __post_init__(self) -> None:
        for field_name in ("cnvrt_project_id", "collection_id", "unigraph_project_id"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        for field_name in ("job_id", "job_name", "collection_name", "traversal_source"):
            object.__setattr__(self, field_name, str(getattr(self, field_name) or "").strip())

    @property
    def is_drawing_scoped(self) -> bool:
        return bool(self.job_id)

    def to_dict(self, *, include_legacy_project_id: bool = False) -> dict[str, str]:
        result = {
            "cnvrt_project_id": self.cnvrt_project_id,
            "collection_id": self.collection_id,
            "unigraph_project_id": self.unigraph_project_id,
        }
        if include_legacy_project_id:
            result["project_id"] = self.unigraph_project_id
        for field_name in ("collection_name", "job_name", "job_id", "traversal_source"):
            value = getattr(self, field_name)
            if value:
                result[field_name] = value
        return result


@dataclass(frozen=True)
class DrawingEntityReference:
    """Exact identity of one entity in one exported HILT drawing."""

    cnvrt_project_id: str
    collection_id: str
    job_id: str
    entity_id: str
    entity_type: str = ""
    entity_class: str = ""

    def __post_init__(self) -> None:
        for field_name in ("cnvrt_project_id", "collection_id", "job_id", "entity_id"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "entity_type", str(self.entity_type or "").strip())
        object.__setattr__(self, "entity_class", str(self.entity_class or "").strip())

    @property
    def identity(self) -> ExternalIdentity:
        return ExternalIdentity(
            source_system=IdentitySource.CNVRT_HILT,
            project_scope=f"job:{self.job_id}",
            external_id=self.entity_id,
        )

    def to_dict(self) -> dict[str, str]:
        result = {
            "source_system": IdentitySource.CNVRT_HILT.value,
            "cnvrt_project_id": self.cnvrt_project_id,
            "collection_id": self.collection_id,
            "job_id": self.job_id,
            "entity_id": self.entity_id,
        }
        if self.entity_type:
            result["entity_type"] = self.entity_type
        if self.entity_class:
            result["entity_class"] = self.entity_class
        return result


@dataclass(frozen=True)
class GeometryFallback:
    """Source-qualified image-space geometry; never evidence of identity."""

    bbox: BBox
    source: IdentitySource
    match_method: str
    job_id: str
    coordinate_frame: CoordinateFrame = CoordinateFrame.IMAGE_TOP_LEFT

    def __post_init__(self) -> None:
        if not isinstance(self.bbox, BBox):
            raise TypeError("bbox must be a BBox")
        source = IdentitySource(self.source)
        if source not in {IdentitySource.CNVRT_HILT, IdentitySource.CNVRT_STLM, IdentitySource.MANUAL}:
            raise ValueError("geometry source must be cnvrt_hilt, cnvrt_stlm, or manual")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "coordinate_frame", CoordinateFrame(self.coordinate_frame))
        object.__setattr__(self, "match_method", _required(self.match_method, "match_method"))
        object.__setattr__(self, "job_id", _required(self.job_id, "job_id"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "bbox": self.bbox.to_list(),
            "source": self.source.value,
            "match_method": self.match_method,
            "job_id": self.job_id,
            "coordinate_frame": self.coordinate_frame.value,
        }


@dataclass(frozen=True)
class SelectedAsset:
    """User-selected target asset before authoritative graph reconciliation."""

    tag: str
    context: PlanningContext
    selection_source: SelectionSource
    hilt_entity_id: str = ""
    hilt_entity_class: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "tag", _required(self.tag, "tag"))
        if not isinstance(self.context, PlanningContext):
            raise TypeError("context must be a PlanningContext")
        source = SelectionSource(self.selection_source)
        object.__setattr__(self, "selection_source", source)
        object.__setattr__(self, "hilt_entity_id", str(self.hilt_entity_id or "").strip())
        object.__setattr__(self, "hilt_entity_class", str(self.hilt_entity_class or "").strip())
        if source != SelectionSource.CLI_TAG:
            _required(self.hilt_entity_id, "hilt_entity_id")
            if not self.context.is_drawing_scoped:
                raise ValueError("job_id is required for HILT asset selection")

    @property
    def identity_quality(self) -> IdentityQuality:
        return IdentityQuality.EXACT if self.hilt_entity_id else IdentityQuality.LEGACY_TAG_ONLY

    @property
    def drawing_entity(self) -> DrawingEntityReference | None:
        if not self.hilt_entity_id:
            return None
        return DrawingEntityReference(
            cnvrt_project_id=self.context.cnvrt_project_id,
            collection_id=self.context.collection_id,
            job_id=self.context.job_id,
            entity_id=self.hilt_entity_id,
            entity_class=self.hilt_entity_class,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "tag": self.tag,
            "selection_source": self.selection_source.value,
            "identity_quality": self.identity_quality.value,
        }
        if self.hilt_entity_id:
            result["hilt_entity_id"] = self.hilt_entity_id
        if self.hilt_entity_class:
            result["hilt_entity_class"] = self.hilt_entity_class
        return result
