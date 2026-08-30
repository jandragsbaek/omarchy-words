import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from omawpm import config as configmod
from omawpm.daemon import Daemon
from omawpm.metrics import KEY_LEFTCTRL


class SessionLifecycleTests(unittest.TestCase):
    def _daemon(self, tmp: Path, paused: bool = False) -> Daemon:
        cfg = dict(configmod.DEFAULTS)
        cfg["paused"] = paused
        path = tmp / "omawpm.json"
        path.write_text(json.dumps(cfg) + "\n")
        return Daemon(
            db_path=tmp / "wpm.sqlite",
            status_path=tmp / "status.json",
            config_path=path,
        )

    def test_pause_resets_session_and_modifiers(self):
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            daemon = self._daemon(tmp)
            daemon.tracker.session.session_inserted = 500
            daemon.tracker.session.session_typing_ms = 60_000
            daemon.filter._mods.add(KEY_LEFTCTRL)
            daemon._config_mtime = daemon.config_path.stat().st_mtime
            time.sleep(0.05)
            cfg = dict(configmod.DEFAULTS)
            cfg["paused"] = True
            daemon.config_path.write_text(json.dumps(cfg) + "\n")
            daemon.reload_config()
            self.assertTrue(daemon.paused)
            self.assertEqual(daemon.tracker.session.session_inserted, 0)
            self.assertEqual(daemon.tracker.session.session_wpm, 0.0)
            self.assertFalse(daemon.filter._mods)
            daemon.store.close()

    def test_day_rollover_resets_session(self):
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            daemon = self._daemon(tmp)
            daemon._day = "2020-01-01"
            daemon.tracker.session.session_inserted = 500
            daemon.tracker.session.session_typing_ms = 60_000
            daemon.rollover_day()
            self.assertNotEqual(daemon._day, "2020-01-01")
            self.assertEqual(daemon.tracker.session.session_inserted, 0)
            self.assertEqual(daemon.tracker.session.session_wpm, 0.0)
            daemon.store.close()
