import unittest

from omawpm.blind import InputFilter
from omawpm.evdev import BlindStroke
from omawpm.metrics import (
    EV_KEY,
    KEY_A,
    KEY_C,
    KEY_LEFTCTRL,
    KEY_LEFTMETA,
    KEY_SPACE,
    KIND_LETTER,
    KIND_SPACE,
)


class FilterTests(unittest.TestCase):
    def test_letter_and_space_are_anonymous_kinds(self):
        filt = InputFilter()
        self.assertEqual(filt.consider(EV_KEY, KEY_A, 1), KIND_LETTER)
        self.assertEqual(filt.consider(EV_KEY, KEY_SPACE, 1), KIND_SPACE)

    def test_ctrl_c_is_dropped(self):
        filt = InputFilter()
        self.assertIsNone(filt.consider(EV_KEY, KEY_LEFTCTRL, 1))
        self.assertIsNone(filt.consider(EV_KEY, KEY_C, 1))
        filt.consider(EV_KEY, KEY_LEFTCTRL, 0)
        self.assertEqual(filt.consider(EV_KEY, KEY_C, 1), KIND_LETTER)

    def test_super_shortcuts_are_dropped(self):
        filt = InputFilter()
        self.assertIsNone(filt.consider(EV_KEY, KEY_LEFTMETA, 1))
        self.assertIsNone(filt.consider(EV_KEY, KEY_A, 1))

    def test_reset_clears_stuck_modifiers(self):
        filt = InputFilter()
        filt.consider(EV_KEY, KEY_LEFTCTRL, 1)
        self.assertIsNone(filt.consider(EV_KEY, KEY_C, 1))
        filt.reset()
        self.assertEqual(filt.consider(EV_KEY, KEY_C, 1), KIND_LETTER)

    def test_blind_stroke_has_no_scancode(self):
        stroke = BlindStroke(kind=KIND_LETTER, now_ms=1)
        self.assertFalse(hasattr(stroke, "code"))
        self.assertEqual(stroke.__dict__, {"kind": KIND_LETTER, "now_ms": 1})


if __name__ == "__main__":
    unittest.main()
