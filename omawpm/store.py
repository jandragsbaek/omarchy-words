"""SQLite persistence for daily per-window typing aggregates. Never stores keys."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional


SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS daily_window (
    day TEXT NOT NULL,
    app_class TEXT NOT NULL,
    app_title TEXT NOT NULL DEFAULT '',
    inserted_chars INTEGER NOT NULL DEFAULT 0,
    deleted_chars INTEGER NOT NULL DEFAULT 0,
    inserted_words INTEGER NOT NULL DEFAULT 0,
    deleted_words INTEGER NOT NULL DEFAULT 0,
    keystrokes INTEGER NOT NULL DEFAULT 0,
    typing_ms INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, app_class, app_title)
);

CREATE TABLE IF NOT EXISTS daily_total (
    day TEXT NOT NULL PRIMARY KEY,
    inserted_chars INTEGER NOT NULL DEFAULT 0,
    deleted_chars INTEGER NOT NULL DEFAULT 0,
    inserted_words INTEGER NOT NULL DEFAULT 0,
    deleted_words INTEGER NOT NULL DEFAULT 0,
    keystrokes INTEGER NOT NULL DEFAULT 0,
    typing_ms INTEGER NOT NULL DEFAULT 0,
    session_wpm REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def day_key(when: Optional[datetime] = None) -> str:
    if when is None:
        when = datetime.now().astimezone()
    return when.date().isoformat()


@dataclass
class WindowRow:
    day: str
    app_class: str
    app_title: str
    inserted_chars: int
    deleted_chars: int
    inserted_words: int
    deleted_words: int
    keystrokes: int
    typing_ms: int

    @property
    def net_chars(self) -> int:
        return max(0, self.inserted_chars - self.deleted_chars)

    @property
    def net_words(self) -> int:
        return max(0, self.inserted_words - self.deleted_words)


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def add_delta(
        self,
        day: str,
        app_class: str,
        app_title: str,
        inserted_chars: int = 0,
        deleted_chars: int = 0,
        inserted_words: int = 0,
        deleted_words: int = 0,
        keystrokes: int = 0,
        typing_ms: int = 0,
    ) -> None:
        if not any((inserted_chars, deleted_chars, inserted_words, deleted_words, keystrokes, typing_ms)):
            return
        app_class = app_class or "unknown"
        app_title = (app_title or "")[:240]
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO daily_window (
                    day, app_class, app_title,
                    inserted_chars, deleted_chars, inserted_words, deleted_words,
                    keystrokes, typing_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(day, app_class, app_title) DO UPDATE SET
                    inserted_chars = inserted_chars + excluded.inserted_chars,
                    deleted_chars = deleted_chars + excluded.deleted_chars,
                    inserted_words = inserted_words + excluded.inserted_words,
                    deleted_words = deleted_words + excluded.deleted_words,
                    keystrokes = keystrokes + excluded.keystrokes,
                    typing_ms = typing_ms + excluded.typing_ms
                """,
                (
                    day,
                    app_class,
                    app_title,
                    inserted_chars,
                    deleted_chars,
                    inserted_words,
                    deleted_words,
                    keystrokes,
                    typing_ms,
                ),
            )
            self._conn.execute(
                """
                INSERT INTO daily_total (
                    day, inserted_chars, deleted_chars, inserted_words, deleted_words,
                    keystrokes, typing_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(day) DO UPDATE SET
                    inserted_chars = inserted_chars + excluded.inserted_chars,
                    deleted_chars = deleted_chars + excluded.deleted_chars,
                    inserted_words = inserted_words + excluded.inserted_words,
                    deleted_words = deleted_words + excluded.deleted_words,
                    keystrokes = keystrokes + excluded.keystrokes,
                    typing_ms = typing_ms + excluded.typing_ms
                """,
                (
                    day,
                    inserted_chars,
                    deleted_chars,
                    inserted_words,
                    deleted_words,
                    keystrokes,
                    typing_ms,
                ),
            )
            self._conn.commit()

    def set_session_wpm(self, day: str, wpm: float) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO daily_total (day, session_wpm) VALUES (?, ?)
                ON CONFLICT(day) DO UPDATE SET session_wpm = excluded.session_wpm
                """,
                (day, wpm),
            )
            self._conn.commit()

    def windows_for_day(self, day: str) -> list[WindowRow]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT day, app_class, app_title,
                       inserted_chars, deleted_chars, inserted_words, deleted_words,
                       keystrokes, typing_ms
                FROM daily_window
                WHERE day = ?
                ORDER BY inserted_words DESC, inserted_chars DESC, app_class
                """,
                (day,),
            ).fetchall()
        return [WindowRow(**dict(r)) for r in rows]

    def apps_for_day(self, day: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT app_class,
                       SUM(inserted_chars) AS inserted_chars,
                       SUM(deleted_chars) AS deleted_chars,
                       SUM(inserted_words) AS inserted_words,
                       SUM(deleted_words) AS deleted_words,
                       SUM(keystrokes) AS keystrokes,
                       SUM(typing_ms) AS typing_ms
                FROM daily_window
                WHERE day = ?
                GROUP BY app_class
                ORDER BY inserted_words DESC, inserted_chars DESC
                """,
                (day,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["net_chars"] = max(0, d["inserted_chars"] - d["deleted_chars"])
            d["net_words"] = max(0, d["inserted_words"] - d["deleted_words"])
            out.append(d)
        return out

    def total_for_day(self, day: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM daily_total WHERE day = ?", (day,)
            ).fetchone()
        if row is None:
            return {
                "day": day,
                "inserted_chars": 0,
                "deleted_chars": 0,
                "inserted_words": 0,
                "deleted_words": 0,
                "keystrokes": 0,
                "typing_ms": 0,
                "session_wpm": 0.0,
                "net_chars": 0,
                "net_words": 0,
            }
        d = dict(row)
        d["net_chars"] = max(0, d["inserted_chars"] - d["deleted_chars"])
        d["net_words"] = max(0, d["inserted_words"] - d["deleted_words"])
        return d

    def goal_progress(self, day: str, app_class: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    COALESCE(SUM(inserted_words), 0) AS inserted_words,
                    COALESCE(SUM(deleted_words), 0) AS deleted_words,
                    COALESCE(SUM(inserted_chars), 0) AS inserted_chars,
                    COALESCE(SUM(deleted_chars), 0) AS deleted_chars
                FROM daily_window
                WHERE day = ? AND lower(app_class) = lower(?)
                """,
                (day, app_class),
            ).fetchone()
        d = dict(row) if row else {
            "inserted_words": 0,
            "deleted_words": 0,
            "inserted_chars": 0,
            "deleted_chars": 0,
        }
        d["net_words"] = max(0, d["inserted_words"] - d["deleted_words"])
        d["net_chars"] = max(0, d["inserted_chars"] - d["deleted_chars"])
        d["app_class"] = app_class
        d["day"] = day
        return d

    def year_days(self, year: int) -> list[dict[str, Any]]:
        start = date(year, 1, 1).isoformat()
        end = date(year, 12, 31).isoformat()
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT day, inserted_words, deleted_words, inserted_chars, deleted_chars
                FROM daily_total
                WHERE day >= ? AND day <= ?
                ORDER BY day
                """,
                (start, end),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["net_words"] = max(0, d["inserted_words"] - d["deleted_words"])
            d["net_chars"] = max(0, d["inserted_chars"] - d["deleted_chars"])
            out.append(d)
        return out

    def contribution_cells(self, weeks: int = 53) -> list[dict[str, Any]]:
        today = date.today()
        start = today - timedelta(days=weeks * 7 + today.weekday())
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT day, inserted_words, deleted_words, inserted_chars, deleted_chars
                FROM daily_total
                WHERE day >= ?
                ORDER BY day
                """,
                (start.isoformat(),),
            ).fetchall()
        by_day = {r["day"]: dict(r) for r in rows}
        cells = []
        cursor = start
        while cursor <= today:
            raw = by_day.get(cursor.isoformat())
            net_words = 0
            net_chars = 0
            if raw:
                net_words = max(0, raw["inserted_words"] - raw["deleted_words"])
                net_chars = max(0, raw["inserted_chars"] - raw["deleted_chars"])
            cells.append(
                {
                    "day": cursor.isoformat(),
                    "weekday": cursor.weekday(),
                    "net_words": net_words,
                    "net_chars": net_chars,
                }
            )
            cursor += timedelta(days=1)
        return cells


def default_db_path() -> Path:
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(state) / "omarchy" / "plugins" / "jan.wpm" / "wpm.sqlite"
