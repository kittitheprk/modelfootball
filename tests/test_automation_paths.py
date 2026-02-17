import unittest
from pathlib import Path

from scripts import run_update


class TestAutomationPaths(unittest.TestCase):
    def test_pipeline_script_paths_exist(self):
        root = Path(__file__).resolve().parent.parent
        missing = run_update.get_missing_scripts(project_root=root)
        self.assertEqual(
            [],
            missing,
            msg=f"Missing scripts in automation pipeline: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
