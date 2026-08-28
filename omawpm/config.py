from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "goalWords": 1000,
    "goalMatch": "obsidian",
    "goalAppClass": "obsidian",
    "goals": [],
    "dailyNotePath": "",
    "autoExport": False,
    "burstIdleMs": 1500,
    "paused": False,
}


def default_config_path() -> Path:
    return Path.home() / ".config" / "omarchy" / "omawpm.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or default_config_path()
    cfg = dict(DEFAULTS)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: data[k] for k in DEFAULTS if k in data})
        except (OSError, json.JSONDecodeError):
            pass
    try:
        cfg["goalWords"] = max(0, int(cfg["goalWords"]))
    except (TypeError, ValueError):
        cfg["goalWords"] = 1000
    cfg["burstIdleMs"] = max(400, int(cfg.get("burstIdleMs") or 1500))
    match = str(cfg.get("goalMatch") or cfg.get("goalAppClass") or "obsidian")
    cfg["goalMatch"] = match
    cfg["goalAppClass"] = str(cfg.get("goalAppClass") or match)
    goals = cfg.get("goals")
    if isinstance(goals, str) and goals.strip():
        try:
            goals = json.loads(goals)
        except json.JSONDecodeError:
            goals = []
    cfg["goals"] = goals if isinstance(goals, list) else []
    cfg["dailyNotePath"] = str(cfg["dailyNotePath"] or "")
    cfg["autoExport"] = bool(cfg["autoExport"])
    cfg["paused"] = bool(cfg["paused"])
    return cfg


def save_config(cfg: dict[str, Any], path: Path | None = None) -> None:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = dict(DEFAULTS)
    merged.update(cfg)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
