import json
import unittest
from pathlib import Path

from api.app import app


class OpenApiSpecTests(unittest.TestCase):
    def test_checked_in_spec_matches_fastapi_contract(self):
        path = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), app.openapi())

    def test_correction_and_lineage_paths_are_documented(self):
        paths = app.openapi()["paths"]
        self.assertIn("/isolation-plans/{plan_id}/changes", paths)
        self.assertIn("/isolation-plans/{plan_id}/derive", paths)
        self.assertIn("/isolation-plans/{plan_id}/versions/{version_id}/diff", paths)


if __name__ == "__main__":
    unittest.main()
