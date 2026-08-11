"""Fetch non-versioned HILT + project-symbol fixtures for the local POC.

Reads PLANT360_AUTH_TOKEN from the repository root .env.  The artifacts contain
customer drawing data, so data/*.json is deliberately git-ignored.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "hilt-viewer-poc" / "data"
API = "https://api.plant360.ai:8080"
JOB_ID = 2100


def env_value(name: str) -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def fetch(path: str) -> object:
    token = env_value("PLANT360_AUTH_TOKEN")
    if not token:
        raise RuntimeError("PLANT360_AUTH_TOKEN must be set in the repository .env")
    request = Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read())


OUT.mkdir(exist_ok=True)
hilt = fetch(f"/jobs/get_job_hilt_graph/{JOB_ID}")
project_id = hilt["hilt_graph"]["jobData"]["projectID"]
(OUT / f"hilt-{JOB_ID}.json").write_text(json.dumps(hilt))
(OUT / f"symbols-{project_id}.json").write_text(json.dumps(fetch(f"/ui_symbol/get_ui_symbol_format?project_id={project_id}")))
print(f"Wrote HILT job {JOB_ID} and matching symbol library for project {project_id} to {OUT}")
