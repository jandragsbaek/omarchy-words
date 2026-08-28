import json
import unittest

from omawpm.activity import (
    Activity,
    classify_site,
    herdr_activity_label,
    infer_activity,
    title_suffix,
)
from omawpm.herdr import parse_focus, _snapshot_payload


FOCUS_SNAP = {
    "focused_pane_id": "w3:p1",
    "focused_workspace_id": "w3",
    "workspaces": [
        {"workspace_id": "w1", "label": "Work", "focused": False},
        {"workspace_id": "w3", "label": "grok build", "focused": True},
    ],
    "panes": [
        {
            "pane_id": "w3:p1",
            "workspace_id": "w3",
            "focused": True,
            "agent": "grok",
        }
    ],
}


class TitleTests(unittest.TestCase):
    def test_suffix(self):
        self.assertEqual(title_suffix("nayena: grok build"), "grok build")
        self.assertEqual(title_suffix("foot"), "")


class InferTests(unittest.TestCase):
    def test_herdr_focused_pane(self):
        herdr = parse_focus(FOCUS_SNAP)
        act = infer_activity(
            "foot",
            "nayena: grok build",
            hypr_workspace="2",
            herdr=herdr,
            hosts_herdr=True,
        )
        self.assertEqual(act.activity, "grok · grok build")
        self.assertEqual(act.herdr_workspace, "grok build")
        self.assertEqual(act.herdr_agent, "grok")
        self.assertEqual(act.hypr_workspace, "2")
        self.assertEqual(act.source, "herdr")

    def test_does_not_apply_herdr_focus_to_chromium(self):
        herdr = parse_focus(FOCUS_SNAP)
        act = infer_activity(
            "chromium",
            "GitHub",
            hypr_workspace="1",
            herdr=herdr,
            hosts_herdr=False,
        )
        self.assertEqual(act.activity, "chromium · github")
        self.assertEqual(act.site, "github")
        self.assertEqual(act.herdr_workspace, "")
        self.assertEqual(act.source, "site")
        self.assertEqual(act.title, "")

    def test_title_matches_herdr_workspace_list(self):
        herdr = parse_focus(FOCUS_SNAP)
        act = infer_activity(
            "foot",
            "nayena: grok build",
            hypr_workspace="2",
            herdr=herdr,
            hosts_herdr=False,
        )
        self.assertEqual(act.activity, "herdr · grok build")
        self.assertEqual(act.source, "title")

    def test_proc_agent_in_terminal(self):
        act = infer_activity("foot", "foot", hypr_workspace="3", proc_agent="claude")
        self.assertEqual(act.activity, "claude · 3")
        self.assertEqual(act.herdr_agent, "claude")
        self.assertEqual(act.source, "proc")

    def test_proc_agent_ignored_in_browser(self):
        act = infer_activity("chromium", "Home / X - Chromium", proc_agent="claude")
        self.assertEqual(act.site, "x")
        self.assertNotEqual(act.source, "proc")

    def test_roundtrip_key(self):
        herdr = parse_focus(FOCUS_SNAP)
        act = infer_activity("foot", "nayena: grok build", "2", herdr, True)
        again = act.from_key(act.key)
        self.assertEqual(again.activity, act.activity)
        self.assertEqual(again.herdr_workspace, act.herdr_workspace)
        self.assertEqual(again.app_class, "foot")

    def test_x_tab_from_chromium_title(self):
        act = infer_activity("chromium", "Home / X - Chromium", hypr_workspace="1")
        self.assertEqual(act.activity, "chromium · x")
        self.assertEqual(act.site, "x")
        self.assertEqual(act.source, "site")
        self.assertEqual(act.title, "")

    def test_x_badge_and_tweet_title_still_just_x(self):
        act = infer_activity("chromium", "(3) Home / X - Chromium")
        self.assertEqual(act.site, "x")
        leaky = infer_activity(
            "chromium",
            'Jane Doe on X: "secret draft about bradsted" - Chromium',
        )
        self.assertEqual(leaky.site, "x")
        self.assertEqual(leaky.activity, "chromium · x")
        self.assertEqual(leaky.title, "")
        self.assertNotIn("secret", leaky.activity)
        self.assertNotIn("Jane", leaky.activity)

    def test_unknown_chromium_page_stays_class(self):
        act = infer_activity(
            "chromium",
            "bradsted gravidtræning - Google Search - Chromium",
        )
        self.assertEqual(act.site, "google")
        self.assertEqual(act.activity, "chromium · google")
        self.assertEqual(act.title, "")
        self.assertNotIn("bradsted", act.activity)
        unknown = infer_activity("chromium", "Some random docs page - Chromium")
        self.assertEqual(unknown.site, "")
        self.assertEqual(unknown.activity, "chromium")
        self.assertEqual(unknown.source, "class")

    def test_site_key_roundtrip(self):
        act = infer_activity("chromium", "Notifications / X - Chromium", "3")
        again = act.from_key(act.key)
        self.assertEqual(again.site, "x")
        self.assertEqual(again.activity, "chromium · x")
        self.assertEqual(again.herdr_agent, "")
        self.assertEqual(again.app_class, "chromium")

    def test_legacy_four_part_key(self):
        old = "\x1f".join(["grok · grok build", "2", "grok build", "foot"])
        act = Activity.from_key(old)
        self.assertEqual(act.activity, "grok · grok build")
        self.assertEqual(act.site, "")
        self.assertEqual(act.herdr_agent, "grok")
        self.assertEqual(act.app_class, "foot")


class SiteClassifyTests(unittest.TestCase):
    def test_x_live_title(self):
        self.assertEqual(classify_site("chromium", "Home / X - Chromium"), "x")

    def test_twitter_alias_and_host(self):
        self.assertEqual(classify_site("firefox", "Twitter — Mozilla Firefox"), "x")
        self.assertEqual(classify_site("chromium", "https://x.com/home - Chromium"), "x")

    def test_non_browser_ignored(self):
        self.assertEqual(classify_site("obsidian", "Home / X"), "")
        self.assertEqual(classify_site("foot", "Home / X - Chromium"), "")


class ParseTests(unittest.TestCase):
    def test_snapshot_unwrap(self):
        raw = json.dumps({"id": "x", "result": {"type": "session_snapshot", "snapshot": FOCUS_SNAP}})
        snap = _snapshot_payload(raw)
        self.assertEqual(snap["focused_pane_id"], "w3:p1")
        focus = parse_focus(snap)
        self.assertEqual(focus.workspace, "grok build")
        self.assertEqual(focus.agent, "grok")
        self.assertIn("Work", focus.workspaces)

    def test_label(self):
        self.assertEqual(herdr_activity_label("grok", "grok build"), "grok · grok build")
        self.assertEqual(herdr_activity_label("", "omarchy"), "herdr · omarchy")


if __name__ == "__main__":
    unittest.main()
