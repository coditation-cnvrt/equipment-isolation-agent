"""Verify that a built wheel is runnable without a source checkout.

Usage:
    uv run python scripts/verify_wheel.py dist/equipment_isolation-*.whl

The wheel is extracted into a temporary directory and imported with an isolated
Python path. This catches missing root modules and package data while ensuring
application migrations do not leak into Alembic's third-party namespace.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


REQUIRED_MEMBERS = {
    "agent/docs/osha_1910_147.md",
    "api/migrations/__init__.py",
    "api/migrations/alembic.ini",
    "api/migrations/env.py",
    "api/migrations/script.py.mako",
    "api/migrations/versions/__init__.py",
    "api/migrations/versions/0001_current_schema.py",
    "api/migrations/versions/0002_plan_corrections.py",
    "api/migrations/versions/0003_scoped_asset_identity.py",
    "api/migrations/versions/0004_plan_feedback_framework.py",
    "api/migrations/versions/0005_feedback_constraint_names.py",
    "config.py",
    "domain/instrument_catalog.json",
    "domain/feedback.py",
    "instrument_context.py",
}
FORBIDDEN_MEMBERS = {
    "alembic/env.py",
    "alembic/versions/0001_current_schema.py",
}
FORBIDDEN_PREFIXES = ("tests/", "scripts/", "hilt-viewer-poc/")


def verify_wheel(wheel_path: Path) -> None:
    if not wheel_path.is_file() or wheel_path.suffix != ".whl":
        raise RuntimeError(f"Wheel does not exist: {wheel_path}")

    with zipfile.ZipFile(wheel_path) as archive:
        members = set(archive.namelist())
        missing = sorted(REQUIRED_MEMBERS - members)
        leaked = sorted(FORBIDDEN_MEMBERS & members)
        unintended = sorted(
            member
            for member in members
            if member.startswith(FORBIDDEN_PREFIXES)
        )
        if missing:
            raise RuntimeError(f"Wheel is missing required runtime files: {missing}")
        if leaked:
            raise RuntimeError(
                "Application migrations leaked into the third-party Alembic namespace: "
                f"{leaked}"
            )
        if unintended:
            raise RuntimeError(
                "Wheel contains development-only packages: "
                f"{unintended[:20]}"
            )

        with tempfile.TemporaryDirectory(prefix="equipment-isolation-wheel-") as temp_dir:
            install_root = Path(temp_dir) / "site-packages"
            archive.extractall(install_root)
            probe = f"""
import sys
sys.path.insert(0, {str(install_root)!r})

from agent.osha import list_osha_topics
from agent.runner import run_agent_pipeline
from api.db import migration_head_revision
from api.service import execute_agent_request
from instrument_context import load_instrument_catalog
from run import main

assert migration_head_revision() == "0005_feedback_constraint_names"
assert list_osha_topics()
assert load_instrument_catalog().get("version")
assert callable(run_agent_pipeline)
assert callable(execute_agent_request)
assert callable(main)
print("Installed-wheel runtime resources: OK")
"""
            completed = subprocess.run(
                [sys.executable, "-I", "-c", probe],
                cwd=temp_dir,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode:
                raise RuntimeError(
                    "Installed-wheel import probe failed:\n"
                    + completed.stdout
                    + completed.stderr
                )
            print(completed.stdout.strip())


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: verify_wheel.py PATH_TO_WHEEL")
    wheel_path = Path(argv[1]).resolve()
    verify_wheel(wheel_path)
    print(f"Wheel verification passed: {wheel_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
