"""Read keyboard events from /dev/input without python-evdev."""

from __future__ import annotations

import glob
import os
import stat
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

# Native 64-bit Linux input_event: timeval(2×long) + type + code + value.
EVENT = struct.Struct("llHHi")
EV_KEY = 1


@dataclass
class KeyEvent:
    seconds: int
    microseconds: int
    code: int
    value: int

    @property
    def now_ms(self) -> int:
        return self.seconds * 1000 + self.microseconds // 1000


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


def iter_events(fd: int) -> Iterator[KeyEvent]:
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
        if ev_type != EV_KEY:
            continue
        yield KeyEvent(seconds=sec, microseconds=usec, code=code, value=value)


def close_fds(fds: Iterable[int]) -> None:
    for fd in fds:
        try:
            os.close(fd)
        except OSError:
            pass
