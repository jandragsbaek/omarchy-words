"""Classify key events and count net words/chars without storing text.

WPM uses the typing-test convention: one word = 5 net characters.
The daily writing goal uses space-separated words reconstructed from a
class-only draft buffer (letter vs whitespace). The buffer never holds
the actual characters typed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# linux/input-event-codes.h
EV_KEY = 1

KEY_ESC = 1
KEY_1, KEY_2, KEY_3, KEY_4, KEY_5 = 2, 3, 4, 5, 6
KEY_6, KEY_7, KEY_8, KEY_9, KEY_0 = 7, 8, 9, 10, 11
KEY_MINUS, KEY_EQUAL, KEY_BACKSPACE, KEY_TAB = 12, 13, 14, 15
KEY_Q, KEY_W, KEY_E, KEY_R, KEY_T = 16, 17, 18, 19, 20
KEY_Y, KEY_U, KEY_I, KEY_O, KEY_P = 21, 22, 23, 24, 25
KEY_LEFTBRACE, KEY_RIGHTBRACE, KEY_ENTER = 26, 27, 28
KEY_LEFTCTRL = 29
KEY_A, KEY_S, KEY_D, KEY_F, KEY_G = 30, 31, 32, 33, 34
KEY_H, KEY_J, KEY_K, KEY_L = 35, 36, 37, 38
KEY_SEMICOLON, KEY_APOSTROPHE, KEY_GRAVE = 39, 40, 41
KEY_LEFTSHIFT, KEY_BACKSLASH = 42, 43
KEY_Z, KEY_X, KEY_C, KEY_V, KEY_B = 44, 45, 46, 47, 48
KEY_N, KEY_M, KEY_COMMA, KEY_DOT, KEY_SLASH = 49, 50, 51, 52, 53
KEY_RIGHTSHIFT, KEY_KPASTERISK, KEY_LEFTALT, KEY_SPACE = 54, 55, 56, 57
KEY_CAPSLOCK = 58
KEY_F1 = 59  # F1..F10 = 59..68
KEY_KP7 = 71
KEY_KPPLUS = 78
KEY_KPENTER = 96
KEY_RIGHTCTRL = 97
KEY_RIGHTALT = 100
KEY_HOME, KEY_UP, KEY_PAGEUP, KEY_LEFT = 102, 103, 104, 105
KEY_RIGHT, KEY_END, KEY_DOWN, KEY_PAGEDOWN, KEY_INSERT, KEY_DELETE = (
    106,
    107,
    108,
    109,
    110,
    111,
)
KEY_LEFTMETA, KEY_RIGHTMETA, KEY_COMPOSE = 125, 126, 127
KEY_KPSLASH = 98
KEY_KP0, KEY_KPDOT = 82, 83
KEY_KP1, KEY_KP2, KEY_KP3, KEY_KP4 = 79, 80, 81, 75
KEY_KP5, KEY_KP6, KEY_KP8, KEY_KP9 = 76, 77, 72, 73
KEY_KPMINUS = 74

MODIFIERS = {
    KEY_LEFTCTRL,
    KEY_RIGHTCTRL,
    KEY_LEFTALT,
    KEY_RIGHTALT,
    KEY_LEFTMETA,
    KEY_RIGHTMETA,
    KEY_CAPSLOCK,
}

SHIFT = {KEY_LEFTSHIFT, KEY_RIGHTSHIFT}

WORD_CHARS = {
    KEY_1,
    KEY_2,
    KEY_3,
    KEY_4,
    KEY_5,
    KEY_6,
    KEY_7,
    KEY_8,
    KEY_9,
    KEY_0,
    KEY_MINUS,
    KEY_Q,
    KEY_W,
    KEY_E,
    KEY_R,
    KEY_T,
    KEY_Y,
    KEY_U,
    KEY_I,
    KEY_O,
    KEY_P,
    KEY_A,
    KEY_S,
    KEY_D,
    KEY_F,
    KEY_G,
    KEY_H,
    KEY_J,
    KEY_K,
    KEY_L,
    KEY_Z,
    KEY_X,
    KEY_C,
    KEY_V,
    KEY_B,
    KEY_N,
    KEY_M,
    KEY_APOSTROPHE,
    KEY_KP0,
    KEY_KP1,
    KEY_KP2,
    KEY_KP3,
    KEY_KP4,
    KEY_KP5,
    KEY_KP6,
    KEY_KP7,
    KEY_KP8,
    KEY_KP9,
}

# Punctuation still inserts a character for WPM, but breaks words.
PUNCT = {
    KEY_EQUAL,
    KEY_LEFTBRACE,
    KEY_RIGHTBRACE,
    KEY_SEMICOLON,
    KEY_GRAVE,
    KEY_BACKSLASH,
    KEY_COMMA,
    KEY_DOT,
    KEY_SLASH,
    KEY_KPASTERISK,
    KEY_KPSLASH,
    KEY_KPPLUS,
    KEY_KPMINUS,
    KEY_KPDOT,
}

WHITESPACE = {KEY_SPACE, KEY_ENTER, KEY_TAB, KEY_KPENTER}
DELETES = {KEY_BACKSPACE, KEY_DELETE}

KIND_LETTER = "L"
KIND_SPACE = "S"
KIND_PUNCT = "P"
KIND_DELETE = "D"
KIND_IGNORE = "I"
KIND_MOD = "M"


def classify_key(code: int) -> str:
    if code in MODIFIERS or code in SHIFT:
        return KIND_MOD
    if code in WORD_CHARS:
        return KIND_LETTER
    if code in WHITESPACE:
        return KIND_SPACE
    if code in PUNCT:
        return KIND_PUNCT
    if code in DELETES:
        return KIND_DELETE
    return KIND_IGNORE


def wpm_from_net_chars(net_chars: int, elapsed_ms: int) -> float:
    if elapsed_ms <= 0 or net_chars <= 0:
        return 0.0
    minutes = elapsed_ms / 60000.0
    return (net_chars / 5.0) / minutes


def count_letter_runs(classes: str) -> int:
    words = 0
    in_word = False
    for ch in classes:
        if ch == KIND_LETTER and not in_word:
            words += 1
            in_word = True
        elif ch != KIND_LETTER:
            in_word = False
    return words


@dataclass
class WindowDraft:
    """Net-of-backspace reconstruction for one window. Classes only, no glyphs."""

    classes: str = ""
    inserted_chars: int = 0
    deleted_chars: int = 0
    inserted_words: int = 0
    deleted_words: int = 0
    keystrokes: int = 0
    max_len: int = 4096
    flushed_inserted_chars: int = 0
    flushed_deleted_chars: int = 0
    flushed_inserted_words: int = 0
    flushed_deleted_words: int = 0
    flushed_keystrokes: int = 0

    def _words_now(self) -> int:
        return count_letter_runs(self.classes)

    def _trim(self) -> None:
        extra = len(self.classes) - self.max_len
        if extra <= 0:
            return
        # Drop a whole prefix, preserving an in-progress trailing word.
        self.classes = self.classes[extra:]

    def apply(self, kind: str) -> None:
        if kind == KIND_IGNORE or kind == KIND_MOD:
            return
        self.keystrokes += 1
        before = self._words_now()
        if kind == KIND_DELETE:
            self.deleted_chars += 1
            if self.classes:
                self.classes = self.classes[:-1]
            after = self._words_now()
            if after < before:
                self.deleted_words += before - after
            return
        if kind == KIND_LETTER:
            self.inserted_chars += 1
            self.classes += KIND_LETTER
        elif kind == KIND_SPACE:
            self.inserted_chars += 1
            self.classes += KIND_SPACE
        elif kind == KIND_PUNCT:
            self.inserted_chars += 1
            self.classes += KIND_PUNCT
        after = self._words_now()
        if after > before:
            self.inserted_words += after - before
        self._trim()

    @property
    def net_chars(self) -> int:
        return max(0, self.inserted_chars - self.deleted_chars)

    @property
    def net_words(self) -> int:
        return max(0, self.inserted_words - self.deleted_words)

    def pending_delta(self) -> dict[str, int]:
        return {
            "inserted_chars": self.inserted_chars - self.flushed_inserted_chars,
            "deleted_chars": self.deleted_chars - self.flushed_deleted_chars,
            "inserted_words": self.inserted_words - self.flushed_inserted_words,
            "deleted_words": self.deleted_words - self.flushed_deleted_words,
            "keystrokes": self.keystrokes - self.flushed_keystrokes,
        }

    def take_delta(self) -> dict[str, int]:
        delta = self.pending_delta()
        self.flushed_inserted_chars = self.inserted_chars
        self.flushed_deleted_chars = self.deleted_chars
        self.flushed_inserted_words = self.inserted_words
        self.flushed_deleted_words = self.deleted_words
        self.flushed_keystrokes = self.keystrokes
        return delta

    def reset_counts(self) -> None:
        self.classes = ""
        self.inserted_chars = 0
        self.deleted_chars = 0
        self.inserted_words = 0
        self.deleted_words = 0
        self.keystrokes = 0
        self.flushed_inserted_chars = 0
        self.flushed_deleted_chars = 0
        self.flushed_inserted_words = 0
        self.flushed_deleted_words = 0
        self.flushed_keystrokes = 0


@dataclass
class Burst:
    started_ms: int = 0
    last_ms: int = 0
    inserted_chars: int = 0
    deleted_chars: int = 0

    @property
    def net_chars(self) -> int:
        return max(0, self.inserted_chars - self.deleted_chars)

    def elapsed_ms(self, now_ms: int) -> int:
        if self.started_ms <= 0:
            return 0
        return max(0, now_ms - self.started_ms)

    def wpm(self, now_ms: int) -> float:
        return wpm_from_net_chars(self.net_chars, self.elapsed_ms(now_ms))


@dataclass
class Session:
    idle_ms: int = 1500
    burst: Optional[Burst] = None
    last_burst_wpm: float = 0.0
    last_burst_accuracy: float = 100.0
    session_inserted: int = 0
    session_deleted: int = 0
    session_typing_ms: int = 0
    live_wpm: float = 0.0

    def on_char(self, kind: str, now_ms: int) -> None:
        if kind not in (KIND_LETTER, KIND_SPACE, KIND_PUNCT, KIND_DELETE):
            return
        if self.burst and now_ms - self.burst.last_ms > self.idle_ms:
            self._close_burst(now_ms)
        if self.burst is None:
            self.burst = Burst(started_ms=now_ms, last_ms=now_ms)
        if kind == KIND_DELETE:
            self.burst.deleted_chars += 1
            self.session_deleted += 1
        else:
            self.burst.inserted_chars += 1
            self.session_inserted += 1
        self.burst.last_ms = now_ms
        elapsed = self.burst.elapsed_ms(now_ms)
        self.live_wpm = self.burst.wpm(now_ms) if elapsed >= 300 else self.live_wpm

    def tick(self, now_ms: int) -> None:
        if self.burst and now_ms - self.burst.last_ms > self.idle_ms:
            self._close_burst(now_ms)
        elif self.burst:
            self.live_wpm = self.burst.wpm(now_ms)

    def _close_burst(self, now_ms: int) -> None:
        burst = self.burst
        self.burst = None
        if burst is None:
            return
        elapsed = max(burst.last_ms - burst.started_ms, 1)
        self.session_typing_ms += elapsed
        self.last_burst_wpm = burst.wpm(burst.last_ms)
        total = burst.inserted_chars + burst.deleted_chars
        if total > 0:
            self.last_burst_accuracy = 100.0 * burst.inserted_chars / total
        self.live_wpm = 0.0

    @property
    def session_wpm(self) -> float:
        net = max(0, self.session_inserted - self.session_deleted)
        return wpm_from_net_chars(net, self.session_typing_ms)


@dataclass
class KeyTracker:
    """Held-modifier state plus per-window drafts and the live WPM session."""

    mods_down: set[int] = field(default_factory=set)
    shift_down: set[int] = field(default_factory=set)
    drafts: dict[str, WindowDraft] = field(default_factory=dict)
    session: Session = field(default_factory=Session)

    def shortcut_held(self) -> bool:
        return bool(self.mods_down)

    def handle_evdev(self, ev_type: int, code: int, value: int, now_ms: int, window_key: str) -> Optional[str]:
        """Feed one evdev KEY event. Returns the applied kind, or None if ignored."""
        if ev_type != EV_KEY:
            return None
        kind = classify_key(code)
        if kind == KIND_MOD:
            if code in SHIFT:
                if value:
                    self.shift_down.add(code)
                else:
                    self.shift_down.discard(code)
            else:
                if value:
                    self.mods_down.add(code)
                else:
                    self.mods_down.discard(code)
            return None
        if value == 0:
            return None
        if self.shortcut_held():
            return None
        if kind == KIND_IGNORE:
            return None
        draft = self.drafts.setdefault(window_key, WindowDraft())
        draft.apply(kind)
        self.session.on_char(kind, now_ms)
        return kind
