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
from .activity import Activity, infer_activity
from .blind import InputFilter
from .goals import score_goals
from .herdr import HerdrClient
from .metrics import KeyTracker
from .proc import hosts_herdr, infer_ai_agent
from .store import Store, day_key, default_db_path, minute_of_day
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
        self.filter = InputFilter()
        self.fds: list[int] = []
        self.paused = bool(self.cfg["paused"])
        self.state = "starting"
        self.message = "Starting…"
        self.last_window_class = ""
        self.last_activity = ""
        self.last_hypr_workspace = ""
        self.last_herdr_workspace = ""
        self.last_site = ""
        self.herdr = HerdrClient()
        self._last_flush = 0.0
        self._last_status = 0.0
        self._last_export = 0.0
        self._last_window_read = 0.0
        self._window = None
        self._config_mtime = 0.0
        self._day = day_key()
        self._flush_minute = minute_of_day()

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

    def context_for(self, window) -> Activity:
        herdr = self.herdr.focus()
        inside = bool(window.pid and hosts_herdr(window.pid))
        return infer_activity(
            window.app_class,
            window.title,
            hypr_workspace=window.hypr_workspace,
            herdr=herdr,
            hosts_herdr=inside,
            proc_agent="" if inside else infer_ai_agent(window.pid),
        )

    def rollover_day(self) -> str:
        today = day_key()
        if today != self._day:
            self.flush(time.time(), force=True)
            for draft in self.tracker.drafts.values():
                draft.reset_counts()
            self._day = today
            self._flush_minute = minute_of_day()
        return today

    def flush(self, now: float, force: bool = False) -> None:
        current_minute = minute_of_day()
        if not force and now - self._last_flush < 2.0 and current_minute == self._flush_minute:
            return
        self._last_flush = now
        day = self._day
        minute = self._flush_minute
        for key, draft in self.tracker.drafts.items():
            delta = draft.take_delta()
            if not any(delta.values()):
                continue
            act = Activity.from_key(key)
            self.store.add_delta(day=day, app_class=act.app_class, app_title="", **delta)
            self.store.add_minute_delta(
                day=day,
                minute=minute,
                app_class=act.app_class,
                inserted_chars=delta["inserted_chars"],
                deleted_chars=delta["deleted_chars"],
                inserted_words=delta["inserted_words"],
                deleted_words=delta["deleted_words"],
                keystrokes=delta["keystrokes"],
            )
            slice_kw = {
                "inserted_chars": delta["inserted_chars"],
                "deleted_chars": delta["deleted_chars"],
                "inserted_words": delta["inserted_words"],
                "deleted_words": delta["deleted_words"],
                "keystrokes": delta["keystrokes"],
            }
            self.store.add_slice_delta(day, "activity", act.activity, minute=minute, **slice_kw)
            if act.hypr_workspace:
                self.store.add_slice_delta(day, "hypr", act.hypr_workspace, **slice_kw)
            if act.herdr_workspace:
                self.store.add_slice_delta(day, "herdr", act.herdr_workspace, **slice_kw)
            if act.site:
                self.store.add_slice_delta(day, "site", act.site, minute=minute, **slice_kw)
        self._flush_minute = current_minute
        sess = self.tracker.session
        if sess.session_wpm:
            self.store.set_session_wpm(day, sess.session_wpm)

    def _bump(self, rows: list[dict[str, Any]], name_key: str, name: str, extra_key: str, extra: str, delta: dict[str, int]) -> None:
        if not name:
            return
        found = None
        for row in rows:
            if row.get(name_key) == name and (not extra_key or row.get(extra_key) == extra):
                found = row
                break
        if found is None:
            found = {
                name_key: name,
                "inserted_chars": 0,
                "deleted_chars": 0,
                "inserted_words": 0,
                "deleted_words": 0,
                "keystrokes": 0,
                "typing_ms": 0,
                "net_chars": 0,
                "net_words": 0,
            }
            if extra_key:
                found[extra_key] = extra
            rows.append(found)
        for field in ("inserted_chars", "deleted_chars", "inserted_words", "deleted_words", "keystrokes"):
            found[field] = int(found.get(field) or 0) + int(delta.get(field) or 0)
        found["net_chars"] = max(0, found["inserted_chars"] - found["deleted_chars"])
        found["net_words"] = max(0, found["inserted_words"] - found["deleted_words"])

    def _merge_live(
        self,
        apps: list[dict[str, Any]],
        windows: list[dict[str, Any]],
        activities: list[dict[str, Any]],
        hypr: list[dict[str, Any]],
        herdr: list[dict[str, Any]],
        sites: list[dict[str, Any]],
    ) -> None:
        for key, draft in self.tracker.drafts.items():
            delta = draft.pending_delta()
            if not any(delta.values()):
                continue
            act = Activity.from_key(key)
            self._bump(apps, "app_class", act.app_class, "", "", delta)
            self._bump(windows, "app_class", act.app_class, "title", act.title, delta)
            self._bump(activities, "name", act.activity, "", "", delta)
            self._bump(hypr, "name", act.hypr_workspace, "", "", delta)
            self._bump(herdr, "name", act.herdr_workspace, "", "", delta)
            self._bump(sites, "name", act.site, "", "", delta)

    def snapshot(self) -> dict[str, Any]:
        day = day_key()
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
        activities = self.store.slices_for_day(day, "activity")
        hypr = self.store.slices_for_day(day, "hypr")
        herdr = self.store.slices_for_day(day, "herdr")
        sites = self.store.slices_for_day(day, "site")
        self._merge_live(apps, windows, activities, hypr, herdr, sites)
        scored = score_goals(
            self.cfg, apps, activities, herdr, hypr, self.store.total_for_day(day), sites
        )
        goal = scored[0] if scored else {
            "match": "obsidian",
            "label": "obsidian",
            "target": 1000,
            "net_words": 0,
            "inserted_words": 0,
            "deleted_words": 0,
            "percent": 0,
        }
        apps.sort(key=lambda r: (-r.get("net_words", 0), -r.get("inserted_chars", 0)))
        activities.sort(key=lambda r: (-r.get("net_words", 0), -r.get("inserted_chars", 0)))
        hypr.sort(key=lambda r: (-r.get("net_words", 0), -r.get("inserted_chars", 0)))
        herdr.sort(key=lambda r: (-r.get("net_words", 0), -r.get("inserted_chars", 0)))
        sites.sort(key=lambda r: (-r.get("net_words", 0), -r.get("inserted_chars", 0)))
        cells = self.store.contribution_cells(53)
        max_words = max((c["net_words"] for c in cells), default=0)
        now_minute = minute_of_day()
        live_minutes = []
        for key, draft in self.tracker.drafts.items():
            delta = draft.pending_delta()
            if not any(delta.values()):
                continue
            act = Activity.from_key(key)
            live_minutes.append({"app_class": act.activity, "minute": now_minute, **delta})
        spark_rows = [
            {
                "app_class": row["name"],
                "inserted_chars": row["inserted_chars"],
                "net_words": row["net_words"],
            }
            for row in activities
        ]
        sparkline = self.store.sparkline(
            day,
            spark_rows,
            self.last_activity or self.last_window_class,
            now_minute=now_minute,
            live=live_minutes,
            limit=10,
            minute_rows=self.store.minute_slice_rows(day, "activity"),
        )
        sess = self.tracker.session
        paused = self.paused or self.state != "running"
        return {
            "version": 1,
            "state": "paused" if self.paused and self.state == "running" else self.state,
            "message": "Paused" if self.paused and self.state == "running" else self.message,
            "paused": paused,
            "day": day,
            "today_words": sum(int(r.get("net_words") or 0) for r in activities),
            "live_wpm": round(sess.live_wpm, 1),
            "last_burst_wpm": round(sess.last_burst_wpm, 1),
            "session_wpm": round(sess.session_wpm, 1),
            "active_class": self.last_window_class,
            "active_activity": self.last_activity,
            "active_hypr_workspace": self.last_hypr_workspace,
            "active_herdr_workspace": self.last_herdr_workspace,
            "active_site": self.last_site,
            "goal": {
                "app_class": goal.get("match") or goal.get("label") or "obsidian",
                "match": goal.get("match") or "obsidian",
                "label": goal.get("label") or goal.get("match") or "obsidian",
                "target": int(goal.get("target") or 0),
                "net_words": int(goal.get("net_words") or 0),
                "inserted_words": int(goal.get("inserted_words") or 0),
                "deleted_words": int(goal.get("deleted_words") or 0),
                "percent": int(goal.get("percent") or 0),
            },
            "goals": scored,
            "apps": apps,
            "activities": activities,
            "hypr_workspaces": hypr,
            "herdr_workspaces": herdr,
            "sites": sites,
            "windows": windows,
            "sparkline": sparkline,
            "graph": {"max": max_words, "cells": cells},
            "config": {
                "goalWords": int(self.cfg.get("goalWords") or 1000),
                "goalMatch": str(self.cfg.get("goalMatch") or self.cfg.get("goalAppClass") or "obsidian"),
                "goalAppClass": str(self.cfg.get("goalAppClass") or self.cfg.get("goalMatch") or "obsidian"),
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
            int(self.cfg.get("goalWords") or 1000),
            str(self.cfg.get("goalMatch") or self.cfg.get("goalAppClass") or "obsidian"),
            live={
                "session_wpm": self.tracker.session.session_wpm,
                "last_burst_wpm": self.tracker.session.last_burst_wpm,
            },
        )
        exportmod.upsert_daily_note(exportmod.expand_daily_path(path, day), block)

    def process_fd(self, fd: int) -> None:
        now = time.time()
        if session_looks_locked() or self.paused:
            for _ in evdev.iter_blind(fd, self.filter):
                pass
            return
        window = self.active_window(now)
        act = self.context_for(window)
        self.last_window_class = window.app_class
        self.last_activity = act.activity
        self.last_hypr_workspace = act.hypr_workspace
        self.last_herdr_workspace = act.herdr_workspace
        self.last_site = act.site
        self.rollover_day()
        for stroke in evdev.iter_blind(fd, self.filter):
            self.tracker.handle_kind(stroke.kind, stroke.now_ms, act.key)

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
