"""Markdown export for Obsidian daily notes."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .goals import score_goals
from .labels import display_name
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
    total = store.total_for_day(day)
    activities = store.slices_for_day(day, "activity")
    herdr = store.slices_for_day(day, "herdr")
    hypr = store.slices_for_day(day, "hypr")
    sites = store.slices_for_day(day, "site")
    scored = score_goals(
        {"goalMatch": goal_app, "goalAppClass": goal_app, "goalWords": goal_words},
        apps,
        activities,
        herdr,
        hypr,
        total,
        sites,
    )
    goal = scored[0] if scored else {"label": goal_app, "net_words": 0, "target": goal_words, "percent": 0, "match": goal_app}
    net = goal["net_words"]
    pct = int(goal.get("percent") or 0)
    lines = [
        MARKER_START,
        f"## Writing — {day}",
        "",
        f"Goal ({display_name(str(goal.get('label') or goal_app))}): **{net} / {goal.get('target') or goal_words}** words ({pct}%)",
        f"Today overall: {git_diff(total['inserted_chars'], total['deleted_chars'])} chars · "
        f"{total['net_words']} words",
    ]
    if live:
        lines.append(
            f"Session: {live.get('session_wpm', 0):.0f} WPM avg · "
            f"last burst {live.get('last_burst_wpm', 0):.0f} WPM"
        )
    lines += [
        "",
        "| App | + | − | words |",
        "|---|---:|---:|---:|",
    ]
    if not apps:
        lines.append("| — | 0 | 0 | 0 |")
    for app in apps:
        lines.append(
            "| {label} | {inserted_chars} | {deleted_chars} | {net_words} |".format(
                label=display_name(app.get("app_class") or ""),
                **app
            )
        )
    if scored and len(scored) > 1:
        lines += ["", "### Goals", "", "| Goal | match | progress |", "|---|---|---|"]
        for row in scored:
            lines.append(
                f"| {row['label']} | {row['match']} | {row['net_words']} / {row['target']} ({row['percent']}%) |"
            )
    if activities:
        lines += ["", "### Activity", "", "| Activity | + | − | words |", "|---|---:|---:|---:|"]
        for row in activities:
            lines.append(
                f"| {display_name(row['name'])} | {row['inserted_chars']} | {row['deleted_chars']} | {row['net_words']} |"
            )
    if sites:
        lines += ["", "### Sites", "", "| Site | + | − | words |", "|---|---:|---:|---:|"]
        for row in sites:
            lines.append(
                f"| {display_name(row['name'])} | {row['inserted_chars']} | {row['deleted_chars']} | {row['net_words']} |"
            )
    if herdr:
        lines += ["", "### Herdr", "", "| Workspace | + | − | words |", "|---|---:|---:|---:|"]
        for row in herdr:
            lines.append(
                f"| {display_name(row['name'])} | {row['inserted_chars']} | {row['deleted_chars']} | {row['net_words']} |"
            )
    if hypr:
        lines += ["", "### Workspaces", "", "| Workspace | + | − | words |", "|---|---:|---:|---:|"]
        for row in hypr:
            lines.append(
                f"| {display_name(row['name'])} | {row['inserted_chars']} | {row['deleted_chars']} | {row['net_words']} |"
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
