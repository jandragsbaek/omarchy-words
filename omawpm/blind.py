"""Blind the keyboard stream: scancodes become letter/space/punct/delete only.

The rest of the plugin never sees a key code. This cannot remove the OS-level
`input` group (any process of yours could still open /dev/input). It does mean
*this* plugin has no path that retains, logs, or exports what you typed.
"""

from __future__ import annotations

from .metrics import (
    EV_KEY,
    KIND_DELETE,
    KIND_IGNORE,
    KIND_LETTER,
    KIND_MOD,
    KIND_PUNCT,
    KIND_SPACE,
    SHIFT,
    classify_key,
)


COUNTABLE = {KIND_LETTER, KIND_SPACE, KIND_PUNCT, KIND_DELETE}


class InputFilter:
    """Maps raw evdev KEY events to anonymous kinds, then drops the scancode."""

    def __init__(self) -> None:
        self._mods: set[int] = set()

    def consider(self, ev_type: int, code: int, value: int) -> str | None:
        if ev_type != EV_KEY:
            return None
        kind = classify_key(code)
        # Scancode must not leave this function except as a kind label.
        if kind == KIND_MOD:
            if code in SHIFT:
                return None
            if value:
                self._mods.add(code)
            else:
                self._mods.discard(code)
            return None
        if value == 0:
            return None
        if self._mods:
            return None
        if kind not in COUNTABLE:
            return None
        return kind
