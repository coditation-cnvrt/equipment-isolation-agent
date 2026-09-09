"""Immutable B1 context for inspection/replay; governed run admission is B2."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from equipment_isolation.domain.controlled_inputs import approved_fhr, utc_timestamp
from equipment_isolation.domain.plant_state import PlantStateDeclaration
from equipment_isolation.domain.safety_inputs import (
    FrozenJSON, SicProfile, StructuredWorkScope, ConfigurationFloor, context, digest, enum, invalid, obj, string, timestamp,
)


class ControlledInputRef(FrozenJSON):
    @staticmethod
    def _validate(value):
        obj(value, ["input_type", "input_id", "revision_id", "revision_label", "schema_version", "content_hash",
                    "decision", "decided_by", "decided_at"], "controlled_input_ref")
        enum(value["input_type"], {"fhr", "sic"}, "input_type")
        for key in ("input_id", "revision_id"):
            try:
                value[key] = str(UUID(value[key]))
            except (ValueError, TypeError, AttributeError):
                invalid(key, "expected repository UUID")
        for key in ("revision_label", "schema_version"):
            value[key] = string(value[key], key)
        digest(value["content_hash"], "content_hash")
        enum(value["decision"], {"pending", "approved", "rejected"}, "decision")
        if value["decision"] == "pending":
            if value["decided_by"] is not None or value["decided_at"] is not None:
                invalid("decision", "pending input cannot have approval metadata")
        else:
            value["decided_by"] = string(value["decided_by"], "decided_by")
            value["decided_at"] = timestamp(value["decided_at"], "decided_at")
        return value

    @classmethod
    def from_revision(cls, revision):
        keys = ("input_type", "input_id", "revision_id", "revision_label", "schema_version", "content_hash", "decision", "decided_by", "decided_at")
        return cls.from_dict({key: revision.get(key) for key in keys})


@dataclass(frozen=True)
class SafetyContext:
    planning_context: FrozenJSON
    plan_time: datetime
    work_scope: StructuredWorkScope
    sic: SicProfile
    sic_composition: FrozenJSON
    psd: PlantStateDeclaration
    graph_snapshots: tuple
    fhr_revision: FrozenJSON | None = None
    rule_engine: FrozenJSON | None = None
    governance_snapshots: FrozenJSON | None = None
    selected_asset: FrozenJSON | None = None

    def __post_init__(self):
        from equipment_isolation.domain.source_snapshots import GraphSnapshot
        for value, expected in ((self.planning_context, FrozenJSON), (self.work_scope, StructuredWorkScope),
                                (self.sic, SicProfile), (self.sic_composition, FrozenJSON), (self.psd, PlantStateDeclaration)):
            if not isinstance(value, expected):
                invalid("safety_context", f"expected {expected.__name__}")
        scope = context(self.planning_context.to_dict())
        object.__setattr__(self, "planning_context", FrozenJSON.from_dict(scope))
        utc_timestamp(self.plan_time)
        if type(self.graph_snapshots) is not tuple or any(not isinstance(graph, GraphSnapshot) for graph in self.graph_snapshots):
            invalid("graph_snapshots", "expected immutable graph snapshot tuple")
        sources = [graph.to_dict()["source"] for graph in self.graph_snapshots]
        if len(sources) != len(set(sources)):
            invalid("graph_snapshots", "duplicate source")
        if self.psd.to_dict()["context"] != scope:
            invalid("psd.context", "scope mismatch")
        if self.sic.to_dict()["context"] != {key: scope[key] for key in ("cnvrt_project_id", "collection_id")}:
            invalid("sic.context", "scope mismatch")
        composition = self.sic_composition.to_dict()
        obj(composition, ["schema_version", "base_hash", "delta_hash", "effective_hash", "parameter_origins", "non_overridable_floors"], "sic_composition")
        enum(composition["schema_version"], {"sic-composition-v1"}, "sic_composition.schema_version")
        digest(composition["base_hash"], "sic_composition.base_hash")
        if composition["delta_hash"] is not None:
            digest(composition["delta_hash"], "sic_composition.delta_hash")
        if type(composition["non_overridable_floors"]) is not list:
            invalid("non_overridable_floors", "expected floor records")
        for floor in composition["non_overridable_floors"]:
            ConfigurationFloor.from_dict(floor)
        if composition["effective_hash"] != self.sic.content_hash:
            invalid("sic_composition", "effective content hash mismatch")
        for graph in self.graph_snapshots:
            if graph.to_dict()["context"] != scope:
                invalid("graph.context", "scope mismatch")
        for value in (self.fhr_revision, self.rule_engine, self.governance_snapshots, self.selected_asset):
            if value is not None and not isinstance(value, FrozenJSON):
                invalid("snapshot", "expected immutable document")
        if self.fhr_revision is not None:
            revision = self.fhr_revision.to_dict()
            if revision.get("input_type") != "fhr":
                invalid("fhr_revision", "expected FHR revision")
            ControlledInputRef.from_revision(revision)
            if revision.get("scope") != {key: scope[key] for key in ("cnvrt_project_id", "collection_id", "job_id")}:
                invalid("fhr.scope", "scope mismatch")
            # Validate hash even for an unapproved source; approval is assessed below.
            payload = FrozenJSON.from_dict(revision.get("payload"))
            if payload.content_hash != revision["content_hash"]:
                invalid("fhr.content_hash", "content mismatch")
        if self.selected_asset is not None:
            target = obj(self.selected_asset.to_dict(), ["hilt_entity_id", "unigraph_vertex_id"], "selected_asset")
            for key, value in target.items():
                string(value, key)
        if self.rule_engine is not None:
            rule = obj(self.rule_engine.to_dict(), ["build_id", "artifact_hash", "normalization_version"], "rule_engine")
            string(rule["build_id"], "build_id")
            digest(rule["artifact_hash"], "artifact_hash")
            string(rule["normalization_version"], "normalization_version")

    @property
    def blockers(self):
        gaps = {"governed_run_admission_not_integrated", "sic_repository_pins_not_integrated"}
        gaps.update(self.sic.blockers)
        gaps.update(self.psd.assess(plan_time=self.plan_time,
            validity_hours=self.sic.to_dict()["parameters"]["plant_state"]["validity_hours"]).to_dict()["blockers"])
        sources = set()
        if self.selected_asset is None:
            gaps.add("selected_asset_missing")
        else:
            gaps.add("asset_identity_reconciliation_not_integrated")
        for graph in self.graph_snapshots:
            sources.add(graph.to_dict()["source"])
            gaps.update(graph.blockers)
            if self.selected_asset is not None:
                source = graph.to_dict()["source"]
                key = "hilt_entity_id" if source == "hilt" else "unigraph_vertex_id"
                identity = self.selected_asset.to_dict()[key]
                node = next((row for row in graph.to_dict()["graph"]["nodes"] if row["id"] == identity), None)
                if node is None:
                    gaps.add(f"selected_asset_absent:{source}")
                else:
                    record = node["record"]
                    structural_type = record.get("payload", {}).get("entity_type") if source == "hilt" else record.get("label", record.get("T.label"))
                    if structural_type != ("equipment" if source == "hilt" else "Equipment"):
                        gaps.add(f"selected_asset_not_equipment:{source}")
            if datetime.fromisoformat(graph.to_dict()["captured_at"].replace("Z", "+00:00")) > self.plan_time:
                gaps.add("graph_capture_after_plan_time")
        for source in {"hilt", "unigraph"} - sources:
            gaps.add(f"{source}_snapshot_missing")
        if self.fhr_revision is None:
            gaps.add("fhr_revision_missing")
        else:
            from equipment_isolation.domain.controlled_inputs import ControlledInputError
            try:
                revision = self.fhr_revision.to_dict()
                approved_fhr(revision)
                if datetime.fromisoformat(revision["decided_at"].replace("Z", "+00:00")) > self.plan_time:
                    gaps.add("fhr_approved_after_plan_time")
            except ControlledInputError as exc:
                gaps.add(f"fhr:{exc.code}")
        if self.rule_engine is None:
            gaps.add("rule_engine_build_missing")
        # Presence of untyped JSON cannot satisfy the future source-specific adapters.
        gaps.add("governance_snapshot_validation_not_integrated")
        return tuple(sorted(gaps))

    def to_dict(self):
        return {"schema_version": "safety-context-b1-v1", "mode": "development", "admission_status": "blocked",
            "planning_context": self.planning_context.to_dict(), "plan_time": utc_timestamp(self.plan_time),
            "work_scope": self.work_scope.to_dict(), "sic": self.sic.to_dict(),
            "sic_composition": self.sic_composition.to_dict(), "psd": self.psd.to_dict(),
            "psd_assessment": self.psd.assess(plan_time=self.plan_time, validity_hours=self.sic.to_dict()["parameters"]["plant_state"]["validity_hours"]).to_dict(),
            "graph_snapshots": [graph.to_dict() for graph in sorted(self.graph_snapshots, key=lambda graph: graph.to_dict()["source"])],
            "fhr_revision": self.fhr_revision.to_dict() if self.fhr_revision else None,
            "rule_engine": self.rule_engine.to_dict() if self.rule_engine else None,
            "governance_snapshots": self.governance_snapshots.to_dict() if self.governance_snapshots else None,
            "selected_asset": self.selected_asset.to_dict() if self.selected_asset else None,
            "blockers": list(self.blockers)}

    @property
    def content_hash(self):
        return FrozenJSON.from_dict(self.to_dict()).content_hash

    def require_executable(self):
        from equipment_isolation.domain.controlled_inputs import ControlledInputError
        raise ControlledInputError("safety_context_blocked", "; ".join(self.blockers))
