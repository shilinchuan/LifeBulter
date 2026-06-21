import contextlib
import io
import json
import os
import tempfile
import unittest

from app.cli import main
from app.database import DatabaseManager, Singleton


class LifeButlerCliTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["LIFEBUTLER_DB_PATH"] = os.path.join(self.temp_dir.name, "lifebutler.db")
        Singleton._instances.pop(DatabaseManager, None)

    def tearDown(self):
        db = Singleton._instances.pop(DatabaseManager, None)
        if db:
            db.close()
        self.temp_dir.cleanup()

    def _run_cli(self, argv):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(argv)
        return code, json.loads(stream.getvalue())

    def test_capabilities_json(self):
        code, result = self._run_cli(["system", "capabilities", "--json"])
        self.assertEqual(code, 0)
        self.assertTrue(result["ok"])
        self.assertIn("task quick-capture", result["data"]["commands"])
        self.assertEqual(result["meta"]["schemaVersion"], 5)

    def test_today_empty_database(self):
        code, result = self._run_cli(["today", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(result["data"]["top_tasks"], [])
        self.assertIn("radar", result["data"])

    def test_task_quick_capture_dry_run_and_write(self):
        code, result = self._run_cli(["task", "quick-capture", "--title", "CLI 任务", "--dry-run", "--json"])
        self.assertEqual(code, 0)
        self.assertTrue(result["data"]["dryRun"])
        self.assertNotIn("project_id", result["data"]["task"])
        code, listed = self._run_cli(["task", "list", "--json"])
        self.assertEqual(listed["data"]["total"], 0)

        code, result = self._run_cli(["task", "quick-capture", "--title", "CLI 任务", "--quadrant", "q1", "--project", "99", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("id", result["data"]["task"])
        self.assertNotIn("project_id", result["data"]["task"])
        code, listed = self._run_cli(["task", "list", "--status", "pending", "--json"])
        self.assertEqual(listed["data"]["total"], 1)

    def test_goal_list_review_week_and_invalid_command(self):
        code, result = self._run_cli(["goal", "list", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(result["data"]["items"], [])
        self.assertEqual(result["data"]["total"], 0)

        code, result = self._run_cli(["review", "week", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("task_total", result["data"])

        code, result = self._run_cli(["nope", "--json"])
        self.assertEqual(code, 1)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "UNSUPPORTED_COMMAND")


if __name__ == "__main__":
    unittest.main()
