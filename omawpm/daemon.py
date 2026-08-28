"""Long-running keyboard monitor. Counts only; never records what you type."""

from __future__ import annotations

import select
import sys
import time
from pathlib import Path
from typing import Any

from . import config as configmod
from . import evdev
from . import export as exportmod
from . import status as statusmod
from .metrics import KeyTracker
from .store import Store, day_key, default_db_path
from .window import read_active_window, session_looks_locked


class Daemon:
    def __init__(
        self,
        db_path: Path | None = None,
        status_path: Path | None = None,
        config_path: Path | None = None,
    ):
        self.cfg = configmod.load_config(config_path)
        self.config_path = config_path or configmod.default_config_path()
        self.store = Store(db_path or default_db_path())
        self.status_path = status_path or statusmod.default_status_path()
        self.tracker = KeyTracker()
        self.tracker.session.idle_ms = int(self.cfg["burstIdleMs"])
        self.fds: list[int] = []
        self.paused = bool(self.cfg["paused"])
        self.state = "starting"
        self.message = "Starting…"
        self.last_window_class = ""
        self.last_window_title = ""
        self._last_flush = 0.0
        self._last_status = 0.0
        self._last_export = 0.0
        self._last_window_read = 0.0
        self._window = None
        self._config_mtime = 0.0
        self._day = day_key()

    def start_input(self) -> None:
        fds, errors = evdev.open_keyboards()
        self.fds = fds
        if not fds:
            if errors and all("permission denied" in e for e in errors):
                self.state = "need_input_group"
                self.message = (
                    "Cannot read keyboards. Add your user to the input group: "
                    "sudo usermod -aG input $USER  (then log out and back in)"
                )
            elif errors:
                self.state = "error"
                self.message = errors[0]
            else:
                self.state = "error"
                self.message = "No keyboard devices found"
            return
        self.state = "running"
        self.message = "Counting"

    def reload_config(self) -> None:
        try:
            mtime = self.config_path.stat().st_mtime
        except OSError:
            return
        if mtime == self._config_mtime:
            return
        self._config_mtime = mtime
        self.cfg = configmod.load_config(self.config_path)
        self.tracker.session.idle_ms = int(self.cfg["burstIdleMs"])
        self.paused = bool(self.cfg["paused"])

    def active_window(self, now: float):
        if self._window is None or now - self._last_window_read > 0.08:
            self._window = read_active_window()
            self._last_window_read = now
        return self._window

    def rollover_day(self) -> str:
        today = day_key()
        if today != self._day:
            self.flush(time.time(), force=True)
            for draft in self.tracker.drafts.values():
                draft.reset_counts()
            self._day = today
        return today

    def flush(self, now: float, force: bool = False) -> None:
        if not force and now - self._last_flush < 2.0:
            return
        self._last_flush = now
        day = self._day
        for key, draft in self.tracker.drafts.items():
            delta = draft.take_delta()
            if not any(delta.values()):
                continue
            app_class, _, title = key.partition("\n")
            self.store.add_delta(day=day, app_class=app_class, app_title=title, **delta)
        sess = self.tracker.session
        if sess.session_wpm:
            self.store.set_session_wpm(day, sess.session_wpm)

    def _merge_live(self, apps: list[dict[str, Any]], windows: list[dict[str, Any]], goal_app: str, goal: dict[str, Any]) -> None:
        for key, draft in self.tracker.drafts.items():
            delta = draft.pending_delta()
            if not any(delta.values()):
                continue
            app_class, _, title = key.partition("\n")
            found = None
            for row in apps:
                if row["app_class"] == app_class:
                    found = row
                    break
            if found is None:
                found = {
                    "app_class": app_class,
                    "inserted_chars": 0,
                    "deleted_chars": 0,
                    "inserted_words": 0,
                    "deleted_words": 0,
                    "keystrokes": 0,
                    "typing_ms": 0,
                    "net_chars": 0,
                    "net_words": 0,
                }
                apps.append(found)
            for field in ("inserted_chars", "deleted_chars", "inserted_words", "deleted_words", "keystrokes"):
                found[field] += delta[field]
            found["net_chars"] = max(0, found["inserted_chars"] - found["deleted_chars"])
            found["net_words"] = max(0, found["inserted_words"] - found["deleted_words"])
            wfound = None
            for row in windows:
                if row["app_class"] == app_class and row["title"] == title:
                    wfound = row
                    break
            if wfound is None:
                wfound = {
                    "app_class": app_class,
                    "title": title,
                    "inserted_chars": 0,
                    "deleted_chars": 0,
                    "inserted_words": 0,
                    "deleted_words": 0,
                    "net_words": 0,
                    "net_chars": 0,
                }
                windows.append(wfound)
            for field in ("inserted_chars", "deleted_chars", "inserted_words", "deleted_words"):
                wfound[field] += delta[field]
            wfound["net_chars"] = max(0, wfound["inserted_chars"] - wfound["deleted_chars"])
            wfound["net_words"] = max(0, wfound["inserted_words"] - wfound["deleted_words"])
            if app_class.lower() == goal_app.lower():
                goal["inserted_words"] += delta["inserted_words"]
                goal["deleted_words"] += delta["deleted_words"]
                goal["net_words"] = max(0, goal["inserted_words"] - goal["deleted_words"])

    def snapshot(self) -> dict[str, Any]:
        day = day_key()
        goal_app = str(self.cfg["goalAppClass"])
        goal_words = int(self.cfg["goalWords"])
        goal = self.store.goal_progress(day, goal_app)
        apps = self.store.apps_for_day(day)
        windows = [
            {
                "app_class": w.app_class,
                "title": w.app_title,
                "inserted_chars": w.inserted_chars,
                "deleted_chars": w.deleted_chars,
                "inserted_words": w.inserted_words,
                "deleted_words": w.deleted_words,
                "net_words": w.net_words,
                "net_chars": w.net_chars,
            }
            for w in self.store.windows_for_day(day)
        ]
        self._merge_live(apps, windows, goal_app, goal)
        apps.sort(key=lambda r: (-r.get("inserted_words", 0), -r.get("inserted_chars", 0)))
        cells = self.store.contribution_cells(53)
        max_words = max((c["net_words"] for c in cells), default=0)
        sess = self.tracker.session
        paused = self.paused or self.state != "running"
        return {
            "version": 1,
            "state": "paused" if self.paused and self.state == "running" else self.state,
            "message": "Paused" if self.paused and self.state == "running" else self.message,
            "paused": paused,
            "day": day,
            "live_wpm": round(sess.live_wpm, 1),
            "last_burst_wpm": round(sess.last_burst_wpm, 1),
            "session_wpm": round(sess.session_wpm, 1),
            "active_class": self.last_window_class,
            "active_title": self.last_window_title,
            "goal": {
                "app_class": goal_app,
                "target": goal_words,
                "net_words": goal["net_words"],
                "inserted_words": goal["inserted_words"],
                "deleted_words": goal["deleted_words"],
                "percent": 0
                if goal_words <= 0
                else min(100, int(round(100 * goal["net_words"] / goal_words))),
            },
            "apps": apps,
            "windows": windows,
            "graph": {"max": max_words, "cells": cells},
            "config": {
                "goalWords": goal_words,
                "goalAppClass": goal_app,
                "dailyNotePath": self.cfg["dailyNotePath"],
                "autoExport": self.cfg["autoExport"],
            },
        }

    def write_status(self, now: float, force: bool = False) -> None:
        if not force and now - self._last_status < 0.2:
            return
        self._last_status = now
        statusmod.write_atomic(self.status_path, self.snapshot())

    def maybe_export(self, now: float) -> None:
        if not self.cfg["autoExport"]:
            return
        path = str(self.cfg["dailyNotePath"] or "").strip()
        if not path:
            return
        if now - self._last_export < 20:
            return
        self._last_export = now
        self.flush(now, force=True)
        day = day_key()
        block = exportmod.render_markdown(
            self.store,
            day,
            int(self.cfg["goalWords"]),
            str(self.cfg["goalAppClass"]),
            live={
                "session_wpm": self.tracker.session.session_wpm,
                "last_burst_wpm": self.tracker.session.last_burst_wpm,
            },
        )
        exportmod.upsert_daily_note(exportmod.expand_daily_path(path, day), block)

    def process_fd(self, fd: int) -> None:
        now = time.time()
        if session_looks_locked() or self.paused:
            for _ in evdev.iter_events(fd):
                pass
            return
        window = self.active_window(now)
        self.last_window_class = window.app_class
        self.last_window_title = window.title
        now_ms = int(now * 1000)
        self.rollover_day()
        for event in evdev.iter_events(fd):
            self.tracker.handle_evdev(
                evdev.EV_KEY, event.code, event.value, now_ms, window.key
            )

    def run(self) -> int:
        self.start_input()
        self.write_status(time.time(), force=True)
        if self.state != "running":
            # Keep the status file fresh so the bar can show the setup hint.
            while True:
                time.sleep(2)
                self.reload_config()
                if self.state == "need_input_group":
                    fds, _ = evdev.open_keyboards()
                    if fds:
                        self.fds = fds
                        self.state = "running"
                        self.message = "Counting"
                        break
                self.write_status(time.time(), force=True)
        try:
            while True:
                now = time.time()
                self.reload_config()
                timeout = 0.2
                if self.fds:
                    readable, _, _ = select.select(self.fds, [], [], timeout)
                    for fd in readable:
                        self.process_fd(fd)
                else:
                    time.sleep(timeout)
                self.rollover_day()
                self.tracker.session.tick(int(now * 1000))
                self.flush(now)
                self.write_status(now)
                self.maybe_export(now)
        except KeyboardInterrupt:
            self.flush(time.time(), force=True)
            return 0
        finally:
            evdev.close_fds(self.fds)
            self.store.close()


def run_daemon() -> int:
    return Daemon().run()


if __name__ == "__main__":
    sys.exit(run_daemon())
