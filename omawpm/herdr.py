"""Read herdr's focused pane/workspace. Never stores terminal contents."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from .activity import HerdrFocus


def default_socket() -> Path:
    config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(config) / "herdr" / "herdr.sock"


def herdr_running(socket_path: Optional[Path] = None) -> bool:
    path = socket_path or default_socket()
    return path.exists()


def _snapshot_payload(raw: str) -> Optional[dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    result = data.get("result")
    if isinstance(result, dict) and isinstance(result.get("snapshot"), dict):
        return result["snapshot"]
    if isinstance(data.get("snapshot"), dict):
        return data["snapshot"]
    return None


def parse_focus(snapshot: dict) -> Optional[HerdrFocus]:
    workspaces = snapshot.get("workspaces") or []
    panes = snapshot.get("panes") or []
    labels: list[str] = []
    focused_ws = ""
    for ws in workspaces:
        if not isinstance(ws, dict):
            continue
        label = str(ws.get("label") or "").strip()
        if label:
            labels.append(label)
        if ws.get("focused") is True:
            focused_ws = label
    focused_id = str(snapshot.get("focused_workspace_id") or "")
    if not focused_ws and focused_id:
        for ws in workspaces:
            if isinstance(ws, dict) and str(ws.get("workspace_id") or "") == focused_id:
                focused_ws = str(ws.get("label") or "").strip()
    agent = ""
    pane_id = str(snapshot.get("focused_pane_id") or "")
    for pane in panes:
        if not isinstance(pane, dict):
            continue
        if pane.get("focused") is True or str(pane.get("pane_id") or "") == pane_id:
            agent = str(pane.get("agent") or "").strip()
            if not pane_id:
                pane_id = str(pane.get("pane_id") or "")
            if not focused_ws:
                ws_id = str(pane.get("workspace_id") or "")
                for ws in workspaces:
                    if isinstance(ws, dict) and str(ws.get("workspace_id") or "") == ws_id:
                        focused_ws = str(ws.get("label") or "").strip()
            break
    if not focused_ws and not agent:
        return None
    return HerdrFocus(
        workspace=focused_ws,
        agent=agent,
        pane_id=pane_id,
        workspaces=tuple(labels),
    )


class HerdrClient:
    def __init__(self, ttl: float = 0.8):
        self.ttl = ttl
        self._focus: Optional[HerdrFocus] = None
        self._at = 0.0
        self._ok = False

    def focus(self) -> Optional[HerdrFocus]:
        now = time.monotonic()
        if now - self._at < self.ttl:
            return self._focus if self._ok else None
        self._at = now
        if not herdr_running():
            self._ok = False
            self._focus = None
            return None
        try:
            proc = subprocess.run(
                ["herdr", "api", "snapshot"],
                capture_output=True,
                text=True,
                timeout=0.4,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            self._ok = False
            self._focus = None
            return None
        snap = _snapshot_payload(proc.stdout or "")
        if not snap:
            self._ok = False
            self._focus = None
            return None
        self._focus = parse_focus(snap)
        self._ok = self._focus is not None
        return self._focus
