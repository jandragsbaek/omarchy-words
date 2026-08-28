from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, config as configmod
from . import export as exportmod
from . import status as statusmod
from .store import Store, day_key, default_db_path


def _store() -> Store:
    return Store(default_db_path())


def cmd_daemon(_args: argparse.Namespace) -> int:
    from .daemon import run_daemon

    return run_daemon()


def cmd_status(_args: argparse.Namespace) -> int:
    payload = statusmod.read_status()
    if not payload:
        payload = {"state": "stopped", "message": "Daemon is not running"}
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    cfg = configmod.load_config()
    store = _store()
    day = args.day or day_key()
    live = statusmod.read_status()
    block = exportmod.render_markdown(
        store,
        day,
        int(cfg["goalWords"]),
        str(cfg["goalAppClass"]),
        live=live or None,
    )
    if args.stdout or not (args.note or cfg["dailyNotePath"]):
        sys.stdout.write(block if block.endswith("\n") else block + "\n")
        return 0
    pattern = args.note or cfg["dailyNotePath"]
    path = exportmod.expand_daily_path(pattern, day)
    exportmod.upsert_daily_note(path, block)
    print(f"Wrote {path}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    cfg = configmod.load_config()
    if args.key is None:
        json.dump(cfg, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.value is None:
        print(json.dumps(cfg.get(args.key)))
        return 0
    key = args.key
    if key not in configmod.DEFAULTS:
        print(f"unknown key: {key}", file=sys.stderr)
        return 2
    raw = args.value
    current = configmod.DEFAULTS[key]
    if isinstance(current, bool):
        cfg[key] = raw.lower() in {"1", "true", "yes", "on"}
    elif isinstance(current, int):
        cfg[key] = int(raw)
    else:
        cfg[key] = raw
    configmod.save_config(cfg)
    return 0


def cmd_pause(args: argparse.Namespace) -> int:
    cfg = configmod.load_config()
    cfg["paused"] = args.paused
    configmod.save_config(cfg)
    print("paused" if args.paused else "resumed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="omawpm",
        description="Actual-input WPM and per-window writing stats for Omarchy.",
    )
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("daemon", help="Run the keyboard monitor")
    d.set_defaults(func=cmd_daemon)

    s = sub.add_parser("status", help="Print the live status JSON")
    s.set_defaults(func=cmd_status)

    e = sub.add_parser("export", help="Write today's stats as Markdown")
    e.add_argument("--day", help="YYYY-MM-DD (default: today)")
    e.add_argument("--note", help="Daily-note path pattern, e.g. ~/vault/{date}.md")
    e.add_argument("--stdout", action="store_true", help="Print instead of writing a file")
    e.set_defaults(func=cmd_export)

    c = sub.add_parser("config", help="Get or set omawpm.json")
    c.add_argument("key", nargs="?")
    c.add_argument("value", nargs="?")
    c.set_defaults(func=cmd_config)

    pause = sub.add_parser("pause", help="Stop counting until resume")
    pause.set_defaults(func=cmd_pause, paused=True)
    resume = sub.add_parser("resume", help="Resume counting")
    resume.set_defaults(func=cmd_pause, paused=False)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
