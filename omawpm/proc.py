"""Walk a window PID's descendants. Used to see if herdr is inside a terminal."""

from __future__ import annotations

from pathlib import Path


def child_pids(pid: int) -> list[int]:
    task = Path(f"/proc/{pid}/task")
    if not task.exists():
        return []
    seen: set[int] = set()
    out: list[int] = []
    try:
        tasks = list(task.iterdir())
    except OSError:
        return []
    for entry in tasks:
        children = entry / "children"
        try:
            text = children.read_text()
        except OSError:
            continue
        for token in text.split():
            if token.isdigit():
                child = int(token)
                if child not in seen:
                    seen.add(child)
                    out.append(child)
    return out


def comm(pid: int) -> str:
    path = Path(f"/proc/{pid}/comm")
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def descendant_comms(pid: int, max_depth: int = 4) -> set[str]:
    names: set[str] = set()
    if pid <= 0:
        return names
    stack = [(pid, 0)]
    seen: set[int] = {pid}
    while stack:
        current, depth = stack.pop()
        name = comm(current)
        if name:
            names.add(name)
        if depth >= max_depth:
            continue
        for child in child_pids(current):
            if child not in seen:
                seen.add(child)
                stack.append((child, depth + 1))
    return names


def hosts_herdr(pid: int) -> bool:
    names = {n.lower() for n in descendant_comms(pid)}
    return "herdr" in names


AI_COMMS = {
    "claude": "claude",
    "codex": "codex",
    "gemini": "gemini",
    "grok": "grok",
}


def infer_ai_agent(pid: int) -> str:
    """Return a short agent slug if this window's process tree looks like an AI CLI."""
    names = {n.lower() for n in descendant_comms(pid)}
    if "herdr" in names:
        return ""
    for comm, agent in AI_COMMS.items():
        if comm in names:
            return agent
    return ""
