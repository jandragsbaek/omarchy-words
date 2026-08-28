"""Active Hyprland window, used to attribute keystrokes."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ActiveWindow:
    app_class: str
    title: str
    address: str
    pid: int = 0
    workspace_id: str = ""
    workspace_name: str = ""

    @property
    def hypr_workspace(self) -> str:
        return self.workspace_name or self.workspace_id or ""

    @property
    def key(self) -> str:
        return f"{self.app_class}\n{self.title}"


UNKNOWN = ActiveWindow(app_class="unknown", title="", address="")


def _hyprctl_json(args: list[str], timeout: float = 0.15) -> Optional[dict]:
    try:
        proc = subprocess.run(
            ["hyprctl", "-j", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def read_active_window() -> ActiveWindow:
    data = _hyprctl_json(["activewindow"])
    if not data:
        return UNKNOWN
    app_class = str(data.get("class") or data.get("initialClass") or "unknown")
    title = str(data.get("title") or "")
    address = str(data.get("address") or "")
    try:
        pid = int(data.get("pid") or 0)
    except (TypeError, ValueError):
        pid = 0
    workspace = data.get("workspace") if isinstance(data.get("workspace"), dict) else {}
    workspace_id = str(workspace.get("id") or "")
    workspace_name = str(workspace.get("name") or "")
    return ActiveWindow(
        app_class=app_class,
        title=title,
        address=address,
        pid=pid,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
    )


def session_looks_locked() -> bool:
    data = _hyprctl_json(["activewindow"])
    if data is None:
        # hyprlock often makes activewindow fail; treat as locked.
        return True
    klass = str(data.get("class") or "").lower()
    return klass in {"hyprlock", "lockscreen"}
