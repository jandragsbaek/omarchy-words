import errno
import os
import tempfile
import unittest
from unittest.mock import patch

from omawpm.blind import InputFilter
from omawpm.evdev import (
    DeviceGone,
    KeyboardDevices,
    _POLL_MASK,
    fd_is_stale,
    iter_blind,
)


class StaleFdTests(unittest.TestCase):
    def test_unlinked_file_is_stale(self):
        fd, path = tempfile.mkstemp()
        os.unlink(path)
        try:
            self.assertTrue(fd_is_stale(fd))
        finally:
            os.close(fd)

    def test_live_pipe_is_not_stale(self):
        r, w = os.pipe()
        os.set_blocking(r, False)
        try:
            self.assertFalse(fd_is_stale(r))
        finally:
            os.close(r)
            os.close(w)


class IterBlindTests(unittest.TestCase):
    def test_empty_read_is_device_gone(self):
        filt = InputFilter()
        with patch("omawpm.evdev.os.read", return_value=b""):
            with self.assertRaises(DeviceGone):
                list(iter_blind(3, filt))

    def test_enodev_is_device_gone(self):
        filt = InputFilter()
        with patch("omawpm.evdev.os.read", side_effect=OSError(errno.ENODEV, "gone")):
            with self.assertRaises(DeviceGone):
                list(iter_blind(3, filt))


class KeyboardDevicesTests(unittest.TestCase):
    def test_poll_readable_then_hup(self):
        r, w = os.pipe()
        os.set_blocking(r, False)
        devs = KeyboardDevices()
        devs.fds.append(r)
        devs.paths[r] = "/dev/input/event99"
        devs._poll.register(r, _POLL_MASK)
        try:
            os.write(w, b"x")
            readable, dead = devs.poll(0)
            self.assertEqual(readable, [r])
            self.assertEqual(dead, [])
            os.close(w)
            w = -1
            readable, dead = devs.poll(0)
            self.assertIn(r, dead)
            self.assertNotIn(r, readable)
        finally:
            devs.close()
            if w >= 0:
                os.close(w)

    def test_rescan_drops_stale_and_unwanted(self):
        fd, path = tempfile.mkstemp()
        os.unlink(path)
        devs = KeyboardDevices()
        self.addCleanup(devs.close)
        devs.fds.append(fd)
        devs.paths[fd] = "/dev/input/event99"
        devs._poll.register(fd, _POLL_MASK)
        with patch("omawpm.evdev.resolved_keyboard_paths", return_value=[]):
            errors = devs.rescan()
        self.assertEqual(errors, [])
        self.assertEqual(devs.fds, [])
        self.assertEqual(devs.paths, {})
