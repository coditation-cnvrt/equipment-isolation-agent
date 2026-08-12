"""Application helpers for stable isolation plans and immutable versions."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from agent.session import jsonable


@dataclass(frozen=True)
class PlanDomainError(Exception):
    kind: str
    message: str
    status_code: int
    context: dict[str, Any] | None = None

    def detail(self) -> dict[str, Any]:
        return {"kind": self.kind, "message": self.message, **(self.context or {})}


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def model_fingerprint(runner: str, agent: dict[str, Any] | None) -> dict[str, Any]:
    agent = agent or {}
    return {
        "runner": runner,
        "model": agent.get("model"),
        "models_used": agent.get("models_used") or [],
        "build_revision": os.environ.get("EIA_BUILD_REVISION", "").strip(),
        "degraded": bool(agent.get("orchestration_error")),
    }


def derivation_status(agent: dict[str, Any] | None) -> str:
    return "completed_degraded" if (agent or {}).get("orchestration_error") else "completed"


def assurance_status(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    data = result.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return None
    value = data[0].get("assurance_status")
    return str(value) if value not in {None, ""} else None


def validate_promotable_result(result: Any) -> None:
    if assurance_status(result) is None:
        raise PlanDomainError(
            kind="invalid_run_result",
            message="The succeeded run does not contain a usable isolation plan result.",
            status_code=409,
        )
