import unittest

from omawpm.metrics import (
    KEY_A,
    KEY_BACKSPACE,
    KEY_SPACE,
    KIND_DELETE,
    KIND_LETTER,
    KIND_SPACE,
    KeyTracker,
    WindowDraft,
    classify_key,
    count_letter_runs,
    wpm_from_net_chars,
)


class ClassifyTests(unittest.TestCase):
    def test_letters_space_delete(self):
        self.assertEqual(classify_key(KEY_A), KIND_LETTER)
        self.assertEqual(classify_key(KEY_SPACE), KIND_SPACE)
        self.assertEqual(classify_key(KEY_BACKSPACE), KIND_DELETE)


class DraftTests(unittest.TestCase):
    def test_hello_world_is_two_words(self):
        d = WindowDraft()
        for _ in "hello":
            d.apply(KIND_LETTER)
        d.apply(KIND_SPACE)
        for _ in "world":
            d.apply(KIND_LETTER)
        self.assertEqual(d.inserted_words, 2)
        self.assertEqual(d.net_words, 2)
        self.assertEqual(d.inserted_chars, 11)

    def test_backspace_undoes_a_word(self):
        d = WindowDraft()
        d.apply(KIND_LETTER)
        d.apply(KIND_LETTER)
        d.apply(KIND_SPACE)
        self.assertEqual(d.inserted_words, 1)
        d.apply(KIND_DELETE)  # space
        d.apply(KIND_DELETE)  # last letter
        d.apply(KIND_DELETE)  # first letter
        self.assertEqual(d.net_words, 0)
        self.assertEqual(d.deleted_words, 1)

    def test_pending_and_take_delta(self):
        d = WindowDraft()
        d.apply(KIND_LETTER)
        d.apply(KIND_SPACE)
        delta = d.take_delta()
        self.assertEqual(delta["inserted_words"], 1)
        self.assertEqual(d.pending_delta()["inserted_words"], 0)
        d.apply(KIND_LETTER)
        self.assertEqual(d.pending_delta()["inserted_words"], 1)

    def test_letter_runs(self):
        self.assertEqual(count_letter_runs("LLSLL"), 2)
        self.assertEqual(count_letter_runs(""), 0)
        self.assertEqual(count_letter_runs("SS"), 0)


class WpmTests(unittest.TestCase):
    def test_five_chars_per_word(self):
        # 300 net chars in 60s = 60 WPM
        self.assertAlmostEqual(wpm_from_net_chars(300, 60_000), 60.0)

    def test_short_burst_is_not_a_fantasy_number(self):
        # 15 chars in 200ms is 900 WPM if you divide by 0.2s.
        self.assertEqual(wpm_from_net_chars(15, 200), 0.0)

    def test_wpm_is_capped(self):
        self.assertEqual(wpm_from_net_chars(200, 1000), 220.0)


class TrackerTests(unittest.TestCase):
    def test_typing_goes_to_the_active_window(self):
        t = KeyTracker()
        t.handle_kind(KIND_LETTER, 1000, "obsidian")
        t.handle_kind(KIND_SPACE, 1100, "obsidian")
        t.handle_kind(KIND_LETTER, 2000, "chromium")
        self.assertEqual(t.drafts["obsidian"].inserted_words, 1)
        self.assertEqual(t.drafts["chromium"].inserted_chars, 1)

    def test_burst_wpm(self):
        t = KeyTracker()
        t.session.idle_ms = 1500
        now = 10_000
        for i in range(50):
            t.handle_kind(KIND_LETTER, now + i * 40, "obsidian")
        t.session.tick(now + 49 * 40)
        self.assertGreater(t.session.live_wpm, 0)
        self.assertLessEqual(t.session.live_wpm, 220.0)
        t.session.tick(now + 49 * 40 + 2000)
        self.assertEqual(t.session.live_wpm, 0)
        self.assertGreater(t.session.last_burst_wpm, 0)
        self.assertLessEqual(t.session.last_burst_wpm, 220.0)

    def test_opening_sprint_does_not_publish_wpm(self):
        t = KeyTracker()
        now = 10_000
        for i in range(12):
            t.handle_kind(KIND_LETTER, now + i * 15, "obsidian")
        self.assertEqual(t.session.live_wpm, 0.0)

    def test_session_reset_clears_wpm(self):
        t = KeyTracker()
        now = 10_000
        for i in range(50):
            t.handle_kind(KIND_LETTER, now + i * 40, "obsidian")
        t.session.tick(now + 49 * 40 + 2000)
        self.assertGreater(t.session.session_wpm, 0)
        t.session.reset()
        self.assertEqual(t.session.session_wpm, 0.0)
        self.assertEqual(t.session.live_wpm, 0.0)
        self.assertEqual(t.session.last_burst_wpm, 0.0)
        self.assertIsNone(t.session.burst)


if __name__ == "__main__":
    unittest.main()
