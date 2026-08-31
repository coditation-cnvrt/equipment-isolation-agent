from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent


class PackageStructureTests(unittest.TestCase):
    def test_application_code_lives_under_owned_package(self):
        historical_modules = {
            "bbox.py",
            "boundary.py",
            "candidates.py",
            "config.py",
            "graph_client.py",
            "instrument_context.py",
            "loto.py",
            "payload.py",
            "validator.py",
            "viewer.py",
        }
        self.assertFalse(
            historical_modules.intersection(
                path.name for path in ROOT.glob("*.py")
            )
        )

    def test_only_documented_compatibility_launchers_remain_at_root(self):
        self.assertEqual(
            {path.name for path in ROOT.glob("*.py")},
            {"agent.py", "api.py", "eval_compare.py", "run.py"},
        )

    def test_old_top_level_packages_are_absent(self):
        for package in ("agent", "api", "domain", "pipeline"):
            with self.subTest(package=package):
                self.assertFalse((ROOT / package).exists())


if __name__ == "__main__":
    unittest.main()
