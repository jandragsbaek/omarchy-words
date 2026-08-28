import os
import tempfile
import unittest
from pathlib import Path

from omawpm.explore import period_payload, render_html, render_report
from omawpm.export import expand_daily_path, git_diff, render_markdown, upsert_daily_note
from omawpm.labels import ai_tool, display_name, row_tool
from omawpm.store import Store, migrate_legacy_db, pick_sparkline_apps


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

    def test_sparkline_top_apps_and_focused(self):
        for minute, klass, words in (
            (10, "obsidian", 4),
            (11, "obsidian", 2),
            (10, "chromium", 1),
            (40, "Alacritty", 8),
            (41, "foot", 1),
            (42, "code", 1),
            (43, "slack", 1),
        ):
            self.store.add_minute_delta("2026-08-28", minute, klass, inserted_words=words)
        apps = [
            {"app_class": "Alacritty", "net_words": 8},
            {"app_class": "obsidian", "net_words": 6},
            {"app_class": "chromium", "net_words": 1},
            {"app_class": "foot", "net_words": 1},
            {"app_class": "code", "net_words": 1},
            {"app_class": "slack", "net_words": 1},
        ]
        names = pick_sparkline_apps(apps, "obsidian", 5)
        self.assertEqual(names[0], "obsidian")
        self.assertEqual(len(names), 5)
        self.assertIn("Alacritty", names)
        self.assertNotIn("slack", names)
        ten = pick_sparkline_apps(apps, "obsidian", 10)
        self.assertEqual(len(ten), 6)
        self.assertIn("slack", ten)
        spark = self.store.sparkline(
            "2026-08-28",
            apps,
            "obsidian",
            now_minute=43,
            live=[{"app_class": "obsidian", "minute": 43, "inserted_words": 3}],
        )
        obsidian = spark["series"][0]
        self.assertTrue(obsidian["focused"])
        self.assertEqual(obsidian["points"][10], 4)
        self.assertEqual(obsidian["points"][11], 2)
        self.assertEqual(obsidian["points"][43], 3)
        self.assertGreater(spark["max"], 0)
        total = spark["all"]["points"]
        self.assertEqual(total[10], 5)
        self.assertEqual(total[40], 8)
        self.assertEqual(total[43], 4)

    def test_activity_and_workspace_slices(self):
        self.store.add_slice_delta(
            "2026-08-28", "activity", "grok · grok build",
            inserted_words=20, inserted_chars=80, minute=100,
        )
        self.store.add_slice_delta(
            "2026-08-28", "herdr", "grok build",
            inserted_words=20, inserted_chars=80,
        )
        self.store.add_slice_delta(
            "2026-08-28", "hypr", "2",
            inserted_words=20, inserted_chars=80,
        )
        acts = {r["name"]: r for r in self.store.slices_for_day("2026-08-28", "activity")}
        self.assertEqual(acts["grok · grok build"]["net_words"], 20)
        herdr = {r["name"]: r for r in self.store.slices_for_day("2026-08-28", "herdr")}
        self.assertEqual(herdr["grok build"]["net_words"], 20)
        spark = self.store.sparkline(
            "2026-08-28",
            [{"app_class": "grok · grok build", "net_words": 20}],
            "grok · grok build",
            now_minute=100,
            minute_rows=self.store.minute_slice_rows("2026-08-28", "activity"),
        )
        self.assertEqual(spark["series"][0]["points"][100], 20)


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
        self.assertIn("+50 −5 chars", md)
        self.assertIn("11 words", md)
        self.assertIn("| Obsidian | 50 | 5 | 11 |", md)
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

    def test_explore_lists_every_activity(self):
        self.store.add_slice_delta(
            "2026-08-28", "activity", "chromium · x",
            inserted_words=5, inserted_chars=20,
        )
        html = render_html(self.store, "2026-08-28")
        self.assertIn(">X<", html)
        self.assertIn("Obsidian", html)
        self.assertIn("Writing — 2026-08-28", html)

    def test_display_names(self):
        self.assertEqual(display_name("md.obsidian.Obsidian"), "Obsidian")
        self.assertEqual(display_name("chromium · x"), "X")
        self.assertEqual(display_name("chromium"), "Other")
        self.assertEqual(display_name("grok-bot"), "Grok Bot")
        self.assertEqual(display_name("herdr · omarchy-wpm"), "omarchy-wpm")
        self.assertEqual(display_name("grok · omarchy-wpm"), "omarchy-wpm")
        self.assertEqual(ai_tool("grok · omarchy-wpm"), "Grok")
        self.assertEqual(ai_tool("claude · Work"), "Claude")
        self.assertEqual(ai_tool("codex"), "Codex")
        self.assertEqual(ai_tool("grok-bot"), "Grok")
        self.assertEqual(row_tool("grok · omarchy-wpm"), "Grok")
        self.assertEqual(row_tool("grok-bot"), "")
        self.assertEqual(row_tool("obsidian"), "")

    def test_migrates_legacy_sqlite(self):
        from omawpm.store import PLUGIN_ID
        self.assertEqual(PLUGIN_ID, "jandragsbaek.wpm")
        dest = Path(self.tmp.name) / "plugins" / PLUGIN_ID / "wpm.sqlite"
        migrate_legacy_db(dest)
        self.assertFalse(dest.exists())
        old_dir = Path(self.tmp.name) / "plugins" / "jan.wpm"
        old_dir.mkdir(parents=True)
        old = old_dir / "wpm.sqlite"
        import sqlite3
        conn = sqlite3.connect(old)
        conn.execute("CREATE TABLE t (x int)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        conn.close()
        migrate_legacy_db(dest)
        self.assertTrue(dest.exists())
        conn = sqlite3.connect(dest)
        self.assertEqual(conn.execute("SELECT x FROM t").fetchone()[0], 1)
        conn.close()

    def test_range_and_report(self):
        self.store.add_delta(
            "2026-08-20", "obsidian", "", inserted_chars=10, inserted_words=3
        )
        self.store.add_slice_delta(
            "2026-08-20", "activity", "obsidian", inserted_chars=10, inserted_words=3
        )
        week = period_payload(self.store, "2026-08-28", "week")
        self.assertEqual(week["total"]["net_words"], 11)
        month = period_payload(self.store, "2026-08-28", "month")
        self.assertEqual(month["total"]["net_words"], 14)
        html = render_report(self.store, "2026-08-28")
        self.assertIn("Week", html)
        self.assertIn('"id":"all"', html)

    def test_site_goal_and_table(self):
        self.store.add_slice_delta(
            "2026-08-28",
            "site",
            "x",
            inserted_words=20,
            deleted_words=2,
            inserted_chars=80,
        )
        md = render_markdown(self.store, "2026-08-28", 500, "site:x")
        self.assertIn("18 / 500", md)
        self.assertIn("### Sites", md)
        self.assertIn("| X | 80 | 0 | 18 |", md)


if __name__ == "__main__":
    unittest.main()
