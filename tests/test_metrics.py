import unittest

from omawpm.metrics import (
    EV_KEY,
    KEY_A,
    KEY_BACKSPACE,
    KEY_ENTER,
    KEY_LEFTCTRL,
    KEY_C,
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


class TrackerTests(unittest.TestCase):
    def test_ctrl_c_is_ignored(self):
        t = KeyTracker()
        t.handle_evdev(EV_KEY, KEY_LEFTCTRL, 1, 1000, "term\n")
        kind = t.handle_evdev(EV_KEY, KEY_C, 1, 1001, "term\n")
        self.assertIsNone(kind)
        self.assertEqual(t.drafts, {})

    def test_typing_goes_to_the_active_window(self):
        t = KeyTracker()
        t.handle_evdev(EV_KEY, KEY_A, 1, 1000, "obsidian\nDaily")
        t.handle_evdev(EV_KEY, KEY_SPACE, 1, 1100, "obsidian\nDaily")
        t.handle_evdev(EV_KEY, KEY_A, 1, 2000, "chromium\nX")
        self.assertEqual(t.drafts["obsidian\nDaily"].inserted_words, 1)
        self.assertEqual(t.drafts["chromium\nX"].inserted_chars, 1)

    def test_burst_wpm(self):
        t = KeyTracker()
        t.session.idle_ms = 1500
        now = 10_000
        for i in range(50):
            t.handle_evdev(EV_KEY, KEY_A, 1, now + i * 20, "obsidian\n")
        t.session.tick(now + 49 * 20)
        self.assertGreater(t.session.live_wpm, 0)
        t.session.tick(now + 49 * 20 + 2000)
        self.assertEqual(t.session.live_wpm, 0)
        self.assertGreater(t.session.last_burst_wpm, 0)


if __name__ == "__main__":
    unittest.main()
