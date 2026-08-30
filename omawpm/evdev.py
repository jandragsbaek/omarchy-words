"""Read keyboard events from /dev/input without python-evdev."""

from __future__ import annotations

import errno
import glob
import os
import select
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

_DEAD_ERRNOS = {errno.ENODEV, errno.EIO, errno.ENOENT, errno.EBADF}
_POLL_MASK = select.POLLIN | select.POLLERR | select.POLLHUP | select.POLLNVAL
_DEAD_MASK = select.POLLERR | select.POLLHUP | select.POLLNVAL


class DeviceGone(Exception):
    """evdev node vanished (unplug, 2.4 GHz reconnect, USB reset)."""


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


def resolved_keyboard_paths() -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for path in keyboard_paths():
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def fd_is_stale(fd: int) -> bool:
    """True if this fd's device node was replaced or unplugged."""
    try:
        link = os.readlink(f"/proc/self/fd/{fd}")
    except OSError:
        return True
    if " (deleted)" in link:
        return True
    poller = select.poll()
    try:
        poller.register(fd, _POLL_MASK)
        events = poller.poll(0)
    except (OSError, ValueError):
        return True
    return bool(events) and bool(events[0][1] & _DEAD_MASK)


def open_keyboards() -> tuple[list[int], list[str]]:
    fds: list[int] = []
    errors: list[str] = []
    for path in resolved_keyboard_paths():
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


class KeyboardDevices:
    """Open keyboard fds, drop vanished nodes, pick up reconnects."""

    def __init__(self) -> None:
        self.fds: list[int] = []
        self.paths: dict[int, str] = {}
        self._poll = select.poll()

    def rescan(self) -> list[str]:
        errors: list[str] = []
        wanted = resolved_keyboard_paths()
        wanted_set = set(wanted)
        for fd in list(self.fds):
            path = self.paths.get(fd, "")
            if fd_is_stale(fd) or path not in wanted_set:
                self.drop(fd)
        held = set(self.paths.values())
        for path in wanted:
            if path in held:
                continue
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
            self.fds.append(fd)
            self.paths[fd] = path
            self._poll.register(fd, _POLL_MASK)
        return errors

    def drop(self, fd: int) -> None:
        try:
            self._poll.unregister(fd)
        except (OSError, KeyError, ValueError):
            pass
        if fd in self.fds:
            self.fds.remove(fd)
        self.paths.pop(fd, None)
        try:
            os.close(fd)
        except OSError:
            pass

    def poll(self, timeout_ms: int) -> tuple[list[int], list[int]]:
        """Return (readable fds, dead fds)."""
        try:
            events = self._poll.poll(timeout_ms)
        except OSError:
            return [], list(self.fds)
        readable: list[int] = []
        dead: list[int] = []
        for fd, flags in events:
            if flags & _DEAD_MASK:
                dead.append(fd)
            elif flags & select.POLLIN:
                readable.append(fd)
        return readable, dead

    def close(self) -> None:
        for fd in list(self.fds):
            self.drop(fd)


def iter_blind(fd: int, filt: "InputFilter") -> Iterator[BlindStroke]:
    """Read evdev, classify, forget the scancode, yield only kinds."""
    while True:
        try:
            buf = os.read(fd, EVENT.size)
        except BlockingIOError:
            return
        except OSError as exc:
            if exc.errno in _DEAD_ERRNOS:
                raise DeviceGone() from exc
            return
        if not buf:
            raise DeviceGone()
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
