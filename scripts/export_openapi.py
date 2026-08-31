"""Export the FastAPI contract used by the companion React application."""
from __future__ import annotations

import json
from pathlib import Path

from equipment_isolation.api.app import app


def main() -> int:
    target = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"
    target.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
