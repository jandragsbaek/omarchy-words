import unittest

from omawpm.goals import counts_for_match, counts_for_matches, parse_goals, score_goals


APPS = [{"app_class": "obsidian", "inserted_words": 40, "deleted_words": 4, "net_words": 36, "inserted_chars": 200, "deleted_chars": 10, "net_chars": 190}]
ACTIVITIES = [{"name": "grok · grok build", "inserted_words": 80, "deleted_words": 10, "net_words": 70}]
HERDR = [{"name": "grok build", "inserted_words": 80, "deleted_words": 10, "net_words": 70}]
HYPR = [{"name": "2", "inserted_words": 90, "deleted_words": 12, "net_words": 78}]
SITES = [{"name": "x", "inserted_words": 50, "deleted_words": 5, "net_words": 45}]
TOTAL = {"inserted_words": 130, "deleted_words": 16, "net_words": 114}


class ParseTests(unittest.TestCase):
    def test_single_from_match_fields(self):
        goals = parse_goals({"goalMatch": "obsidian", "goalWords": 1000})
        self.assertEqual(goals[0]["match"], "obsidian")
        self.assertEqual(goals[0]["target"], 1000)
        self.assertEqual(goals[0]["matches"], ["obsidian"])

    def test_legacy_app_class(self):
        goals = parse_goals({"goalAppClass": "obsidian", "goalWords": 500})
        self.assertEqual(goals[0]["match"], "obsidian")
        self.assertEqual(goals[0]["target"], 500)

    def test_json_list_wins(self):
        goals = parse_goals(
            {
                "goalMatch": "obsidian",
                "goalWords": 1000,
                "goals": [
                    {"match": "obsidian", "words": 1000, "label": "Notes"},
                    {"match": "herdr:grok build", "words": 200},
                ],
            }
        )
        self.assertEqual(len(goals), 2)
        self.assertEqual(goals[0]["label"], "Notes")
        self.assertEqual(goals[1]["match"], "herdr:grok build")

    def test_match_list_union(self):
        goals = parse_goals(
            {
                "goals": [
                    {"match": ["obsidian", "site:x"], "words": 500, "label": "Write"},
                ]
            }
        )
        self.assertEqual(goals[0]["matches"], ["obsidian", "site:x"])
        c = counts_for_matches(goals[0]["matches"], APPS, ACTIVITIES, HERDR, HYPR, TOTAL, SITES)
        self.assertEqual(c["net_words"], 81)


class CountTests(unittest.TestCase):
    def test_bare_class(self):
        c = counts_for_match("obsidian", APPS, ACTIVITIES, HERDR, HYPR, TOTAL)
        self.assertEqual(c["net_words"], 36)

    def test_reverse_dns_obsidian_matches_bare_name(self):
        apps = [{"app_class": "md.obsidian.Obsidian", "inserted_words": 10, "deleted_words": 2, "net_words": 8}]
        c = counts_for_match("obsidian", apps, [], [], [])
        self.assertEqual(c["net_words"], 8)
        c = counts_for_match("class:md.obsidian.Obsidian", apps, [], [], [])
        self.assertEqual(c["net_words"], 8)

    def test_class_and_activity_same_window_not_double_counted(self):
        apps = [{"app_class": "md.obsidian.Obsidian", "inserted_words": 10, "deleted_words": 2, "net_words": 8}]
        acts = [{"name": "md.obsidian.Obsidian", "inserted_words": 10, "deleted_words": 2, "net_words": 8}]
        c = counts_for_matches(
            ["class:md.obsidian.Obsidian", "activity:md.obsidian.Obsidian"],
            apps,
            acts,
            [],
            [],
        )
        self.assertEqual(c["net_words"], 8)

    def test_herdr_prefix(self):
        c = counts_for_match("herdr:grok build", APPS, ACTIVITIES, HERDR, HYPR, TOTAL)
        self.assertEqual(c["net_words"], 70)

    def test_activity_prefix(self):
        c = counts_for_match("activity:grok · grok build", APPS, ACTIVITIES, HERDR, HYPR, TOTAL)
        self.assertEqual(c["net_words"], 70)

    def test_workspace(self):
        c = counts_for_match("ws:2", APPS, ACTIVITIES, HERDR, HYPR, TOTAL)
        self.assertEqual(c["net_words"], 78)

    def test_all(self):
        c = counts_for_match("all", APPS, ACTIVITIES, HERDR, HYPR, TOTAL)
        self.assertEqual(c["net_words"], 114)

    def test_site_prefix(self):
        c = counts_for_match("site:x", APPS, ACTIVITIES, HERDR, HYPR, TOTAL, SITES)
        self.assertEqual(c["net_words"], 45)

    def test_site_twitter_alias(self):
        c = counts_for_match("site:twitter", APPS, ACTIVITIES, HERDR, HYPR, TOTAL, SITES)
        self.assertEqual(c["net_words"], 45)

    def test_bare_x_falls_back_to_site(self):
        c = counts_for_match("x", APPS, ACTIVITIES, HERDR, HYPR, TOTAL, SITES)
        self.assertEqual(c["net_words"], 45)

    def test_score_percent(self):
        scored = score_goals(
            {"goalMatch": "obsidian", "goalWords": 100},
            APPS,
            ACTIVITIES,
            HERDR,
            HYPR,
            TOTAL,
        )
        self.assertEqual(scored[0]["percent"], 36)

    def test_score_site_goal(self):
        scored = score_goals(
            {"goalMatch": "site:x", "goalWords": 500},
            APPS,
            ACTIVITIES,
            HERDR,
            HYPR,
            TOTAL,
            SITES,
        )
        self.assertEqual(scored[0]["net_words"], 45)
        self.assertEqual(scored[0]["percent"], 9)


if __name__ == "__main__":
    unittest.main()
