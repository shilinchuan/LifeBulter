import os
import subprocess
import sys
import unittest
from pathlib import Path


class LifeButlerUiScreenshotTest(unittest.TestCase):
    def test_capture_ui_screenshots_script(self):
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        result = subprocess.run(
            [sys.executable, "scripts/capture_ui_screenshots.py"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        output_dir = Path(result.stdout.strip().splitlines()[-1])
        self.assertTrue((output_dir / "QA_NOTES.md").exists())
        self.assertTrue((output_dir / "dark-dashboard.png").exists())
        self.assertTrue((output_dir / "quick-capture-task-dialog.png").exists())


if __name__ == "__main__":
    unittest.main()
