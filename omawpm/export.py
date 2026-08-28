"""Markdown export for Obsidian daily notes."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .store import Store

MARKER_START = "<!-- omawpm:start -->"
MARKER_END = "<!-- omawpm:end -->"
MARKER_RE = re.compile(
    re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
    re.DOTALL,
)


def git_diff(inserted: int, deleted: int) -> str:
    return f"+{inserted} −{deleted}"


def render_markdown(
    store: Store,
    day: str,
    goal_words: int,
    goal_app: str,
    live: dict[str, Any] | None = None,
) -> str:
    apps = store.apps_for_day(day)
    windows = store.windows_for_day(day)
    total = store.total_for_day(day)
    goal = store.goal_progress(day, goal_app)
    net = goal["net_words"]
    pct = 0 if goal_words <= 0 else min(100, int(round(100 * net / goal_words)))
    lines = [
        MARKER_START,
        f"## Writing — {day}",
        "",
        f"Goal ({goal_app}): **{net} / {goal_words}** words ({pct}%)",
        f"Today overall: {git_diff(total['inserted_words'], total['deleted_words'])} words, "
        f"{git_diff(total['inserted_chars'], total['deleted_chars'])} chars",
    ]
    if live:
        lines.append(
            f"Session: {live.get('session_wpm', 0):.0f} WPM avg · "
            f"last burst {live.get('last_burst_wpm', 0):.0f} WPM"
        )
    lines += [
        "",
        "| App | +words | −words | net | +chars | −chars |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    if not apps:
        lines.append("| — | 0 | 0 | 0 | 0 | 0 |")
    for app in apps:
        lines.append(
            "| {app_class} | {inserted_words} | {deleted_words} | {net_words} | {inserted_chars} | {deleted_chars} |".format(
                **app
            )
        )
    titled = [w for w in windows if w.app_title]
    if titled:
        lines += ["", "### Windows", "", "| App | Window | +words | −words | net |", "|---|---|---:|---:|---:|"]
        for w in titled:
            title = w.app_title.replace("|", "\\|")
            lines.append(
                f"| {w.app_class} | {title} | {w.inserted_words} | {w.deleted_words} | {w.net_words} |"
            )
    lines += ["", MARKER_END, ""]
    return "\n".join(lines)


def expand_daily_path(pattern: str, day: str) -> Path:
    dt = datetime.fromisoformat(day)
    replaced = (
        pattern.replace("{date}", day)
        .replace("{yyyy}", f"{dt.year:04d}")
        .replace("{MM}", f"{dt.month:02d}")
        .replace("{dd}", f"{dt.day:02d}")
        .replace("{yyyy-MM-dd}", day)
    )
    return Path(replaced).expanduser()


def upsert_daily_note(path: Path, block: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = ""
    if MARKER_RE.search(text):
        text = MARKER_RE.sub(block.strip(), text)
        if not text.endswith("\n"):
            text += "\n"
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        if text:
            text += "\n"
        text += block
        if not text.endswith("\n"):
            text += "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
