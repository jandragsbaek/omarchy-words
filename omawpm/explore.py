"""Local HTML explorer and multi-period writing report."""

from __future__ import annotations

import html
import json
import os
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from . import status as statusmod
from .goals import score_goals
from .labels import ai_tool, display_name, row_tool
from .store import Store, day_key, default_db_path


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _rows_table(title: str, rows: list[dict[str, Any]], name_key: str) -> str:
    if not rows:
        return ""
    body = []
    for row in rows:
        name = _esc(display_name(row.get(name_key) or row.get("name") or row.get("app_class") or ""))
        plus = int(row.get("inserted_chars") or 0)
        minus = int(row.get("deleted_chars") or 0)
        words = int(row.get("net_words") or 0)
        body.append(
            f"<tr><td>{name}</td><td class='plus'>+{plus}</td>"
            f"<td class='minus'>{'−' + str(minus) if minus else ''}</td>"
            f"<td class='words'>{words}</td></tr>"
        )
    return (
        f"<section><h2>{_esc(title)}</h2>"
        "<table><thead><tr><th></th><th>+</th><th>−</th><th>words</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></section>"
    )


def render_html(store: Store, day: str, live: dict[str, Any] | None = None) -> str:
    apps = store.apps_for_day(day)
    activities = store.slices_for_day(day, "activity")
    sites = store.slices_for_day(day, "site")
    herdr = store.slices_for_day(day, "herdr")
    hypr = store.slices_for_day(day, "hypr")
    total = store.total_for_day(day)
    cfg = {
        "goalMatch": (live or {}).get("config", {}).get("goalMatch") or "obsidian",
        "goalWords": (live or {}).get("config", {}).get("goalWords") or 1000,
        "goals": (live or {}).get("goals") or [],
    }
    if not cfg["goals"]:
        scored = score_goals(cfg, apps, activities, herdr, hypr, total, sites)
    else:
        scored = live.get("goals") if live else []
    goal_bits = []
    for row in scored or []:
        goal_bits.append(
            f"<li><strong>{_esc(row.get('label') or row.get('match'))}</strong> "
            f"{int(row.get('net_words') or 0)} / {int(row.get('target') or 0)}</li>"
        )
    session = ""
    if live:
        session = (
            f"<p class='meta'>session {float(live.get('session_wpm') or 0):.0f} WPM · "
            f"burst {float(live.get('last_burst_wpm') or 0):.0f}</p>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WPM — { _esc(day) }</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{
      margin: 0 auto; max-width: 52rem; padding: 2rem 1.25rem 4rem;
      font: 15px/1.45 ui-sans-serif, system-ui, sans-serif;
      background: #1b1e24; color: #d6dbe4;
    }}
    h1 {{ font-size: 1.6rem; font-weight: 700; margin: 0 0 .25rem; }}
    h2 {{ font-size: .72rem; letter-spacing: .12em; text-transform: uppercase;
         color: #8b93a3; margin: 2rem 0 .6rem; }}
    .meta {{ color: #8b93a3; margin: 0 0 1rem; }}
    ul.goals {{ padding: 0; margin: 0 0 1.25rem; list-style: none; }}
    ul.goals li {{ margin: .2rem 0; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: .35rem .4rem; }}
    th {{ color: #8b93a3; font-size: .72rem; letter-spacing: .08em;
         text-transform: uppercase; font-weight: 600; }}
    td:nth-child(2), td:nth-child(3), td:nth-child(4),
    th:nth-child(2), th:nth-child(3), th:nth-child(4) {{ text-align: right; }}
    tbody tr:nth-child(odd) {{ background: rgba(255,255,255,.03); }}
    .plus {{ color: #7eb8da; }}
    .minus {{ color: #e06c75; }}
    .words {{ font-weight: 700; font-size: 1.05rem; color: #f0f3f8; }}
  </style>
</head>
<body>
  <h1>Writing — {_esc(day)}</h1>
  <p class="meta">+{int(total.get("inserted_chars") or 0)} −{int(total.get("deleted_chars") or 0)} chars · {int(total.get("net_words") or 0)} words</p>
  {session}
  {"<ul class='goals'>" + "".join(goal_bits) + "</ul>" if goal_bits else ""}
  {_rows_table("Activity", activities, "name")}
  {_rows_table("Sites", sites, "name")}
  {_rows_table("Herdr", herdr, "name")}
  {_rows_table("Workspaces", hypr, "name")}
  {_rows_table("Apps", apps, "app_class")}
</body>
</html>
"""


def _period_bounds(day: str, period: str) -> tuple[str | None, str | None]:
    d = date.fromisoformat(day)
    if period == "today":
        return day, day
    if period == "week":
        start = d - timedelta(days=d.weekday())
        return start.isoformat(), day
    if period == "month":
        return d.replace(day=1).isoformat(), day
    if period == "year":
        return d.replace(month=1, day=1).isoformat(), day
    return None, None


def _pack_rows(rows: list[dict[str, Any]], name_key: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        raw = str(row.get(name_key) or row.get("name") or row.get("app_class") or "")
        out.append(
            {
                "name": raw,
                "label": display_name(raw),
                "tool": row_tool(raw) or ai_tool(raw),
                "inserted_chars": int(row.get("inserted_chars") or 0),
                "deleted_chars": int(row.get("deleted_chars") or 0),
                "net_words": int(row.get("net_words") or 0),
            }
        )
    return out


def period_payload(store: Store, day: str, period: str) -> dict[str, Any]:
    start, end = _period_bounds(day, period)
    total = store.total_for_range(start, end)
    activities = _pack_rows(store.slices_for_range("activity", start, end), "name")
    sites = _pack_rows(store.slices_for_range("site", start, end), "name")
    ai_words = sum(int(r["net_words"]) for r in activities if ai_tool(r["name"]))
    days = [
        {"day": r["day"], "net_words": int(r["net_words"])}
        for r in store.days_for_range(start, end)
    ]
    return {
        "id": period,
        "start": start or "",
        "end": end or day,
        "total": {
            "inserted_chars": int(total.get("inserted_chars") or 0),
            "deleted_chars": int(total.get("deleted_chars") or 0),
            "net_words": int(total.get("net_words") or 0),
        },
        "ai_words": ai_words,
        "activities": activities,
        "sites": sites,
        "days": days,
    }


def render_report(store: Store, day: str) -> str:
    periods = {
        key: period_payload(store, day, key)
        for key in ("today", "week", "month", "year", "all")
    }
    payload = json.dumps({"day": day, "periods": periods}, ensure_ascii=False, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WPM report</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{
      margin: 0 auto; max-width: 54rem; padding: 2rem 1.25rem 4rem;
      font: 15px/1.45 ui-sans-serif, system-ui, sans-serif;
      background: Canvas; color: CanvasText;
    }}
    h1 {{ font-size: 1.7rem; font-weight: 700; margin: 0 0 .4rem; }}
    h2 {{ font-size: .72rem; letter-spacing: .12em; text-transform: uppercase;
         color: GrayText; margin: 1.6rem 0 .55rem; }}
    .meta {{ color: GrayText; margin: 0 0 1rem; }}
    nav {{ display: flex; gap: .4rem; flex-wrap: wrap; margin: 1rem 0 1.4rem; }}
    nav button {{
      font: inherit; padding: .25rem .7rem; border: 1px solid GrayText;
      background: transparent; color: inherit; border-radius: 999px; cursor: pointer;
    }}
    nav button[aria-current="true"] {{ background: CanvasText; color: Canvas; border-color: CanvasText; }}
    .bars {{ display: flex; align-items: flex-end; gap: 2px; height: 72px; margin: .4rem 0 1.2rem; }}
    .bars span {{ flex: 1; min-width: 2px; background: AccentColor; opacity: .85; border-radius: 1px 1px 0 0; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: .35rem .4rem; }}
    th {{ color: GrayText; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; }}
    td:nth-child(n+2), th:nth-child(n+2) {{ text-align: right; }}
    tbody tr:nth-child(odd) {{ background: color-mix(in srgb, CanvasText 4%, Canvas); }}
    .plus {{ color: AccentColor; }}
    .minus {{ color: color-mix(in srgb, AccentColor 40%, red); }}
    .words {{ font-weight: 700; }}
    .tool {{ color: GrayText; font-size: .85em; }}
  </style>
</head>
<body>
  <h1 id="title">Report</h1>
  <p class="meta" id="meta"></p>
  <nav id="nav"></nav>
  <div class="bars" id="bars"></div>
  <div id="tables"></div>
  <script>
    const DATA = {payload};
    const ORDER = ["today","week","month","year","all"];
    const LABELS = {{today:"Today", week:"Week", month:"Month", year:"Year", all:"All"}};
    function rowsTable(title, rows) {{
      if (!rows || !rows.length) return "";
      const body = rows.map(r =>
        `<tr><td>${{r.label || r.name || ""}}</td>` +
        `<td class="tool">${{r.tool && r.tool !== r.label ? r.tool : ""}}</td>` +
        `<td class="plus">+${{r.inserted_chars}}</td>` +
        `<td class="minus">${{r.deleted_chars ? ("−" + r.deleted_chars) : ""}}</td>` +
        `<td class="words">${{r.net_words}}</td></tr>`
      ).join("");
      return `<section><h2>${{title}}</h2><table><thead><tr><th></th><th></th><th>+</th><th>−</th><th>words</th></tr></thead><tbody>${{body}}</tbody></table></section>`;
    }}
    function show(id) {{
      const p = DATA.periods[id];
      const t = p.total;
      document.getElementById("title").textContent = LABELS[id];
      let range = "";
      if (id === "all") range = "all days";
      else if (p.start && p.end && p.start !== p.end) range = p.start + " – " + p.end;
      else range = p.end || DATA.day;
      const ai = p.ai_words ? ` · ${{p.ai_words}} AI` : "";
      document.getElementById("meta").textContent =
        range + " · +" + t.inserted_chars + " −" + t.deleted_chars + " chars · " + t.net_words + " words" + ai;
      document.querySelectorAll("nav button").forEach(b => b.setAttribute("aria-current", b.dataset.id === id ? "true" : "false"));
      const max = Math.max(1, ...p.days.map(d => d.net_words));
      document.getElementById("bars").innerHTML = p.days.map(d =>
        `<span title="${{d.day}} · ${{d.net_words}}" style="height:${{Math.max(2, 72 * d.net_words / max)}}px"></span>`
      ).join("");
      document.getElementById("tables").innerHTML =
        rowsTable("Activity", p.activities) + rowsTable("Sites", p.sites);
    }}
    const nav = document.getElementById("nav");
    ORDER.forEach(id => {{
      const b = document.createElement("button");
      b.dataset.id = id;
      b.textContent = LABELS[id];
      b.onclick = () => show(id);
      nav.appendChild(b);
    }});
    show("week");
  </script>
</body>
</html>
"""


def default_report_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    path = Path(runtime) / "omawpm" / "report.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_report(path: Path | None = None, store: Store | None = None, day: str | None = None) -> Path:
    path = path or default_report_path()
    owned = store is None
    store = store or Store(default_db_path())
    try:
        day = day or day_key()
        path.write_text(render_report(store, day), encoding="utf-8")
        os.chmod(path, 0o600)
        return path
    finally:
        if owned:
            store.close()


def default_explore_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    path = Path(runtime) / "omawpm" / "explore.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_explore(path: Path | None = None, store: Store | None = None, day: str | None = None) -> Path:
    path = path or default_explore_path()
    owned = store is None
    store = store or Store(default_db_path())
    try:
        day = day or day_key()
        live = statusmod.read_status()
        path.write_text(render_html(store, day, live or None), encoding="utf-8")
        os.chmod(path, 0o600)
        return path
    finally:
        if owned:
            store.close()


def open_explore(path: Path) -> None:
    url = path.resolve().as_uri()
    for cmd in (
        ["omarchy", "launch", "browser", url],
        ["xdg-open", url],
    ):
        try:
            subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except FileNotFoundError:
            continue
    raise RuntimeError(f"Could not open {url}")
