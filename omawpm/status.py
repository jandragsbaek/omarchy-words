from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def default_status_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    path = Path(runtime) / "omawpm" / "status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    return path


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    tmp.write_text(data + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def read_status(path: Path | None = None) -> dict[str, Any]:
    path = path or default_status_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
