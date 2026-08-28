"""Read keyboard events from /dev/input without python-evdev."""

from __future__ import annotations

import glob
import os
import stat
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Iterator

if TYPE_CHECKING:
    from .blind import InputFilter

# Native 64-bit Linux input_event: timeval(2×long) + type + code + value.
EVENT = struct.Struct("llHHi")
EV_KEY = 1


@dataclass
class BlindStroke:
    """A countable keystroke with no scancode and no character."""

    kind: str
    now_ms: int


def parse_handlers() -> list[Path]:
    """Keyboards from /proc/bus/input/devices (Handlers contains 'kbd')."""
    path = Path("/proc/bus/input/devices")
    if not path.exists():
        return []
    blocks = path.read_text(errors="replace").split("\n\n")
    out: list[Path] = []
    for block in blocks:
        handlers = ""
        name = ""
        for line in block.splitlines():
            if line.startswith("N: Name="):
                name = line.split("=", 1)[1].strip().strip('"').lower()
            elif line.startswith("H: Handlers="):
                handlers = line.split("=", 1)[1]
        if "kbd" not in handlers.split():
            continue
        skip_bits = ("consumer-control", "system control", "power button", "video bus")
        if any(bit in name for bit in skip_bits):
            continue
        event = None
        for token in handlers.split():
            if token.startswith("event") and token[5:].isdigit():
                event = token
        if not event:
            continue
        out.append(Path("/dev/input") / event)
    return out


def keyboard_paths() -> list[Path]:
    by_id = sorted(Path(p) for p in glob.glob("/dev/input/by-id/*-event-kbd"))
    if by_id:
        return by_id
    return parse_handlers()


def open_keyboards() -> tuple[list[int], list[str]]:
    fds: list[int] = []
    errors: list[str] = []
    seen: set[str] = set()
    for path in keyboard_paths():
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except PermissionError:
            errors.append(f"permission denied: {path}")
            continue
        except OSError as exc:
            errors.append(f"{path}: {exc}")
            continue
        mode = os.fstat(fd).st_mode
        if not stat.S_ISCHR(mode):
            os.close(fd)
            continue
        fds.append(fd)
    return fds, errors


def iter_blind(fd: int, filt: "InputFilter") -> Iterator[BlindStroke]:
    """Read evdev, classify, forget the scancode, yield only kinds."""
    while True:
        try:
            buf = os.read(fd, EVENT.size)
        except BlockingIOError:
            return
        except OSError:
            return
        if not buf:
            return
        if len(buf) != EVENT.size:
            return
        sec, usec, ev_type, code, value = EVENT.unpack(buf)
        kind = filt.consider(ev_type, code, value)
        code = 0
        value = 0
        ev_type = 0
        if not kind:
            continue
        yield BlindStroke(kind=kind, now_ms=sec * 1000 + usec // 1000)


def close_fds(fds: Iterable[int]) -> None:
    for fd in fds:
        try:
            os.close(fd)
        except OSError:
            pass
