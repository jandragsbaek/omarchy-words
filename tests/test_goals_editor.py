import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "tests" / "test_goals_editor.js"


class GoalsEditorTests(unittest.TestCase):
    def test_g_done_and_selection_state_machine(self):
        result = subprocess.run(
            ["node", str(JS)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )
