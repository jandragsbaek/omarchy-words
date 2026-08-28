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

from . import LEGACY_PLUGIN_IDS, PLUGIN_ID


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

CREATE TABLE IF NOT EXISTS minute_app (
    day TEXT NOT NULL,
    minute INTEGER NOT NULL,
    app_class TEXT NOT NULL,
    inserted_chars INTEGER NOT NULL DEFAULT 0,
    deleted_chars INTEGER NOT NULL DEFAULT 0,
    inserted_words INTEGER NOT NULL DEFAULT 0,
    deleted_words INTEGER NOT NULL DEFAULT 0,
    keystrokes INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, minute, app_class)
);

CREATE TABLE IF NOT EXISTS daily_slice (
    day TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    inserted_chars INTEGER NOT NULL DEFAULT 0,
    deleted_chars INTEGER NOT NULL DEFAULT 0,
    inserted_words INTEGER NOT NULL DEFAULT 0,
    deleted_words INTEGER NOT NULL DEFAULT 0,
    keystrokes INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, kind, name)
);

CREATE TABLE IF NOT EXISTS minute_slice (
    day TEXT NOT NULL,
    minute INTEGER NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    inserted_chars INTEGER NOT NULL DEFAULT 0,
    deleted_chars INTEGER NOT NULL DEFAULT 0,
    inserted_words INTEGER NOT NULL DEFAULT 0,
    deleted_words INTEGER NOT NULL DEFAULT 0,
    keystrokes INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, minute, kind, name)
);
"""


def day_key(when: Optional[datetime] = None) -> str:
    if when is None:
        when = datetime.now().astimezone()
    return when.date().isoformat()


def minute_of_day(when: Optional[datetime] = None) -> int:
    if when is None:
        when = datetime.now().astimezone()
    return when.hour * 60 + when.minute


def pick_sparkline_apps(apps: list[dict[str, Any]], focused: str, limit: int = 5) -> list[str]:
    names: list[str] = []
    focused = (focused or "").strip()
    if focused:
        names.append(focused)
    for row in apps:
        klass = str(row.get("app_class") or "")
        if not klass or klass in names:
            continue
        names.append(klass)
        if len(names) >= limit:
            break
    return names[:limit]


def bucket_value(row: dict[str, Any]) -> float:
    words = max(0, int(row.get("inserted_words") or 0) - int(row.get("deleted_words") or 0))
    if words > 0:
        return float(words)
    chars = max(0, int(row.get("inserted_chars") or 0) - int(row.get("deleted_chars") or 0))
    return chars / 5.0


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

    def add_minute_delta(
        self,
        day: str,
        minute: int,
        app_class: str,
        inserted_chars: int = 0,
        deleted_chars: int = 0,
        inserted_words: int = 0,
        deleted_words: int = 0,
        keystrokes: int = 0,
    ) -> None:
        if not any((inserted_chars, deleted_chars, inserted_words, deleted_words, keystrokes)):
            return
        minute = max(0, min(1439, int(minute)))
        app_class = app_class or "unknown"
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO minute_app (
                    day, minute, app_class,
                    inserted_chars, deleted_chars, inserted_words, deleted_words, keystrokes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(day, minute, app_class) DO UPDATE SET
                    inserted_chars = inserted_chars + excluded.inserted_chars,
                    deleted_chars = deleted_chars + excluded.deleted_chars,
                    inserted_words = inserted_words + excluded.inserted_words,
                    deleted_words = deleted_words + excluded.deleted_words,
                    keystrokes = keystrokes + excluded.keystrokes
                """,
                (
                    day,
                    minute,
                    app_class,
                    inserted_chars,
                    deleted_chars,
                    inserted_words,
                    deleted_words,
                    keystrokes,
                ),
            )
            self._conn.commit()

    def add_slice_delta(
        self,
        day: str,
        kind: str,
        name: str,
        inserted_chars: int = 0,
        deleted_chars: int = 0,
        inserted_words: int = 0,
        deleted_words: int = 0,
        keystrokes: int = 0,
        minute: int | None = None,
    ) -> None:
        if not name:
            return
        if not any((inserted_chars, deleted_chars, inserted_words, deleted_words, keystrokes)):
            return
        kind = kind or "activity"
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO daily_slice (
                    day, kind, name,
                    inserted_chars, deleted_chars, inserted_words, deleted_words, keystrokes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(day, kind, name) DO UPDATE SET
                    inserted_chars = inserted_chars + excluded.inserted_chars,
                    deleted_chars = deleted_chars + excluded.deleted_chars,
                    inserted_words = inserted_words + excluded.inserted_words,
                    deleted_words = deleted_words + excluded.deleted_words,
                    keystrokes = keystrokes + excluded.keystrokes
                """,
                (
                    day,
                    kind,
                    name,
                    inserted_chars,
                    deleted_chars,
                    inserted_words,
                    deleted_words,
                    keystrokes,
                ),
            )
            if minute is not None:
                minute = max(0, min(1439, int(minute)))
                self._conn.execute(
                    """
                    INSERT INTO minute_slice (
                        day, minute, kind, name,
                        inserted_chars, deleted_chars, inserted_words, deleted_words, keystrokes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(day, minute, kind, name) DO UPDATE SET
                        inserted_chars = inserted_chars + excluded.inserted_chars,
                        deleted_chars = deleted_chars + excluded.deleted_chars,
                        inserted_words = inserted_words + excluded.inserted_words,
                        deleted_words = deleted_words + excluded.deleted_words,
                        keystrokes = keystrokes + excluded.keystrokes
                    """,
                    (
                        day,
                        minute,
                        kind,
                        name,
                        inserted_chars,
                        deleted_chars,
                        inserted_words,
                        deleted_words,
                        keystrokes,
                    ),
                )
            self._conn.commit()

    def slices_for_day(self, day: str, kind: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT name,
                       inserted_chars, deleted_chars, inserted_words, deleted_words, keystrokes
                FROM daily_slice
                WHERE day = ? AND kind = ?
                ORDER BY inserted_words DESC, inserted_chars DESC, name
                """,
                (day, kind),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["net_chars"] = max(0, d["inserted_chars"] - d["deleted_chars"])
            d["net_words"] = max(0, d["inserted_words"] - d["deleted_words"])
            out.append(d)
        return out

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

    def _range_sql(self, start: str | None, end: str | None) -> tuple[str, tuple]:
        if start and end:
            return "day >= ? AND day <= ?", (start, end)
        if start:
            return "day >= ?", (start,)
        if end:
            return "day <= ?", (end,)
        return "1=1", ()

    def total_for_range(self, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        clause, args = self._range_sql(start, end)
        with self._lock:
            row = self._conn.execute(
                f"""
                SELECT
                    COALESCE(SUM(inserted_chars), 0) AS inserted_chars,
                    COALESCE(SUM(deleted_chars), 0) AS deleted_chars,
                    COALESCE(SUM(inserted_words), 0) AS inserted_words,
                    COALESCE(SUM(deleted_words), 0) AS deleted_words,
                    COALESCE(SUM(keystrokes), 0) AS keystrokes
                FROM daily_total
                WHERE {clause}
                """,
                args,
            ).fetchone()
        d = dict(row) if row else {
            "inserted_chars": 0,
            "deleted_chars": 0,
            "inserted_words": 0,
            "deleted_words": 0,
            "keystrokes": 0,
        }
        d["net_chars"] = max(0, int(d["inserted_chars"] or 0) - int(d["deleted_chars"] or 0))
        d["net_words"] = max(0, int(d["inserted_words"] or 0) - int(d["deleted_words"] or 0))
        return d

    def slices_for_range(
        self, kind: str, start: str | None = None, end: str | None = None
    ) -> list[dict[str, Any]]:
        clause, args = self._range_sql(start, end)
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT name,
                       SUM(inserted_chars) AS inserted_chars,
                       SUM(deleted_chars) AS deleted_chars,
                       SUM(inserted_words) AS inserted_words,
                       SUM(deleted_words) AS deleted_words,
                       SUM(keystrokes) AS keystrokes
                FROM daily_slice
                WHERE kind = ? AND {clause}
                GROUP BY name
                ORDER BY inserted_words DESC, inserted_chars DESC, name
                """,
                (kind, *args),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["net_chars"] = max(0, int(d["inserted_chars"] or 0) - int(d["deleted_chars"] or 0))
            d["net_words"] = max(0, int(d["inserted_words"] or 0) - int(d["deleted_words"] or 0))
            out.append(d)
        return out

    def days_for_range(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        clause, args = self._range_sql(start, end)
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT day, inserted_chars, deleted_chars, inserted_words, deleted_words
                FROM daily_total
                WHERE {clause}
                ORDER BY day
                """,
                args,
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["net_words"] = max(0, int(d["inserted_words"] or 0) - int(d["deleted_words"] or 0))
            d["net_chars"] = max(0, int(d["inserted_chars"] or 0) - int(d["deleted_chars"] or 0))
            out.append(d)
        return out

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

    def minute_rows(self, day: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT minute, app_class,
                       inserted_chars, deleted_chars, inserted_words, deleted_words, keystrokes
                FROM minute_app
                WHERE day = ?
                ORDER BY minute, app_class
                """,
                (day,),
            ).fetchall()
        return [dict(r) for r in rows]

    def minute_slice_rows(self, day: str, kind: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT minute, name AS app_class,
                       inserted_chars, deleted_chars, inserted_words, deleted_words, keystrokes
                FROM minute_slice
                WHERE day = ? AND kind = ?
                ORDER BY minute, name
                """,
                (day, kind),
            ).fetchall()
        return [dict(r) for r in rows]

    def sparkline(
        self,
        day: str,
        apps: list[dict[str, Any]],
        focused: str,
        now_minute: Optional[int] = None,
        live: Optional[list[dict[str, Any]]] = None,
        limit: int = 5,
        minute_rows: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        if now_minute is None:
            now_minute = minute_of_day()
        now_minute = max(0, min(1439, int(now_minute)))
        names = pick_sparkline_apps(apps, focused, limit)
        rows = self.minute_rows(day) if minute_rows is None else minute_rows
        length = now_minute + 1
        total = [0.0] * length
        by_app: dict[str, list[float]] = {name: [0.0] * length for name in names}
        for row in rows:
            klass = row["app_class"]
            minute = int(row["minute"])
            if minute > now_minute:
                continue
            value = bucket_value(row)
            total[minute] += value
            if klass in by_app:
                by_app[klass][minute] += value
        for extra in live or []:
            klass = str(extra.get("app_class") or "")
            minute = int(extra.get("minute") or now_minute)
            if not (0 <= minute <= now_minute):
                continue
            value = bucket_value(extra)
            total[minute] += value
            if klass in by_app:
                by_app[klass][minute] += value
        series = []
        peak = max(total) if total else 0.0
        for index, name in enumerate(names):
            points = by_app[name]
            peak = max(peak, max(points) if points else 0.0)
            series.append(
                {
                    "app_class": name,
                    "focused": name == focused,
                    "index": index,
                    "points": [round(v, 2) for v in points],
                }
            )
        return {
            "now_minute": now_minute,
            "max": round(peak, 2),
            "all": {
                "app_class": "",
                "focused": False,
                "index": -1,
                "points": [round(v, 2) for v in total],
            },
            "series": series,
        }


def _checkpoint(path: Path) -> None:
    if not path.exists():
        return
    try:
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except sqlite3.Error:
        pass


def migrate_legacy_db(dest: Path) -> None:
    """Copy jan.wpm (or other legacy) SQLite into the current plugin state dir."""
    if dest.exists():
        return
    state_root = dest.parent.parent
    for legacy in LEGACY_PLUGIN_IDS:
        old = state_root / legacy / "wpm.sqlite"
        if not old.exists():
            continue
        _checkpoint(old)
        dest.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy2(old, dest)
        wal = old.parent / (old.name + "-wal")
        shm = old.parent / (old.name + "-shm")
        if wal.exists() and wal.stat().st_size:
            shutil.copy2(wal, dest.parent / (dest.name + "-wal"))
        if shm.exists() and shm.stat().st_size:
            shutil.copy2(shm, dest.parent / (dest.name + "-shm"))
        return


def default_db_path() -> Path:
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    dest = Path(state) / "omarchy" / "plugins" / PLUGIN_ID / "wpm.sqlite"
    migrate_legacy_db(dest)
    return dest
