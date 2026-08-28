import os
import tempfile
import unittest
from pathlib import Path

from omawpm.export import expand_daily_path, git_diff, render_markdown, upsert_daily_note
from omawpm.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "wpm.sqlite")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_per_window_and_app_rollup(self):
        self.store.add_delta(
            "2026-08-28", "obsidian", "Daily", inserted_chars=10, inserted_words=3
        )
        self.store.add_delta(
            "2026-08-28", "obsidian", "Projects", inserted_chars=4, inserted_words=1
        )
        self.store.add_delta(
            "2026-08-28", "chromium", "X", inserted_chars=8, deleted_chars=2, inserted_words=2
        )
        apps = {a["app_class"]: a for a in self.store.apps_for_day("2026-08-28")}
        self.assertEqual(apps["obsidian"]["net_words"], 4)
        self.assertEqual(apps["chromium"]["net_chars"], 6)
        goal = self.store.goal_progress("2026-08-28", "Obsidian")
        self.assertEqual(goal["net_words"], 4)
        windows = self.store.windows_for_day("2026-08-28")
        self.assertEqual(len(windows), 3)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "wpm.sqlite")
        self.store.add_delta(
            "2026-08-28", "obsidian", "Daily", inserted_chars=50, deleted_chars=5, inserted_words=12, deleted_words=1
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_markdown_contains_goal_and_git_diff(self):
        md = render_markdown(self.store, "2026-08-28", 1000, "obsidian")
        self.assertIn("11 / 1000", md)
        self.assertIn("+12 −1", md)
        self.assertIn("obsidian", md)
        self.assertIn("omawpm:start", md)

    def test_upsert_replaces_marked_section(self):
        path = Path(self.tmp.name) / "2026-08-28.md"
        path.write_text("# Daily\n\nkeep me\n<!-- omawpm:start -->\nold\n<!-- omawpm:end -->\n", encoding="utf-8")
        block = render_markdown(self.store, "2026-08-28", 1000, "obsidian")
        upsert_daily_note(path, block)
        text = path.read_text(encoding="utf-8")
        self.assertIn("keep me", text)
        self.assertNotIn("old", text)
        self.assertIn("11 / 1000", text)
        upsert_daily_note(path, block)
        self.assertEqual(text.count("omawpm:start"), 1)

    def test_path_pattern(self):
        p = expand_daily_path("~/vault/{yyyy}/{MM}/{dd}.md", "2026-08-28")
        self.assertTrue(str(p).endswith("/vault/2026/08/28.md"))

    def test_git_diff_format(self):
        self.assertEqual(git_diff(12, 3), "+12 −3")


if __name__ == "__main__":
    unittest.main()
