#!/usr/bin/env bash
# Install ~/src/omarchy-wpm into the Omarchy plugins dir.
#
# Do not rsync/copy file-by-file into the live checkout while omarchy-shell
# is running. Each write retriggers a plugin reload; Omarchy tears down
# every service including the lock, and Quickshell can SIGABRT
# (basecamp/omarchy #7106 / #8647).
set -euo pipefail

PLUGIN_ID="jandragsbaek.wpm"
LEGACY_ID="jan.wpm"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${HOME}/.config/omarchy/plugins/${PLUGIN_ID}"
LEGACY_TARGET="${HOME}/.config/omarchy/plugins/${LEGACY_ID}"
RESTART_SHELL=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [--after-shell-restart]

Replace ${TARGET} with this repo in one directory move.

The shell must already be paused/stopped, unless you pass
--after-shell-restart (stop, install, start). Never copy into the live
plugins tree file-by-file while omarchy-shell is up.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --after-shell-restart) RESTART_SHELL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

shell_ping() {
  OMARCHY_SHELL_IPC_TIMEOUT=0.5s omarchy-shell shell ping >/dev/null 2>&1
}

if shell_ping && [[ $RESTART_SHELL -eq 0 ]]; then
  echo "omarchy-shell is running. Refusing to touch ${TARGET}." >&2
  echo "Develop in ${ROOT}. Pause the shell, then re-run, or:" >&2
  echo "  $0 --after-shell-restart" >&2
  exit 1
fi

if [[ $RESTART_SHELL -eq 1 ]]; then
  if command -v omarchy-hyprland-session-locked >/dev/null 2>&1 && omarchy-hyprland-session-locked; then
    echo "Refusing to restart the shell while the session is locked." >&2
    exit 1
  fi
fi

omarchy plugin validate "$ROOT"

stage="$(mktemp -d "${HOME}/.config/omarchy/.${PLUGIN_ID}-stage.XXXXXX")"
cleanup() { rm -rf "$stage" "${stage}.old"; }
trap cleanup EXIT

mkdir -p "$stage"
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$ROOT" ls-files --cached --others --exclude-standard -z |
    while IFS= read -r -d '' path; do
      [[ -e $ROOT/$path || -L $ROOT/$path ]] || continue
      mkdir -p "$stage/$(dirname -- "$path")"
      cp -a -- "$ROOT/$path" "$stage/$path"
    done
else
  rsync -a --exclude .git --exclude __pycache__ --exclude '*.pyc' "$ROOT"/ "$stage"/
fi

if [[ $RESTART_SHELL -eq 1 ]] && shell_ping; then
  config_dir="${OMARCHY_PATH:-/usr/share/omarchy}/shell"
  echo "Stopping omarchy-shell…"
  while timeout 5 quickshell kill -p "$config_dir" --any-display >/dev/null 2>&1; do :; done
fi

mkdir -p "$(dirname "$TARGET")"
if [[ -e $TARGET ]]; then
  mv "$TARGET" "${stage}.old"
fi
if ! mv "$stage" "$TARGET"; then
  [[ ! -e ${stage}.old ]] || mv "${stage}.old" "$TARGET"
  echo "Could not replace ${TARGET}" >&2
  exit 1
fi
rm -rf "${stage}.old"
trap - EXIT

if [[ -e $LEGACY_TARGET && $LEGACY_TARGET != "$TARGET" ]]; then
  rm -rf "$LEGACY_TARGET"
  echo "Removed legacy plugin dir ${LEGACY_TARGET}"
fi

python3 - "$PLUGIN_ID" "$LEGACY_ID" <<'PY'
import json, shutil, sqlite3, sys
from pathlib import Path
plugin_id, legacy_id = sys.argv[1], sys.argv[2]
state = Path.home() / ".local/state/omarchy/plugins"
old = state / legacy_id / "wpm.sqlite"
new = state / plugin_id / "wpm.sqlite"
if old.exists() and not new.exists():
    try:
        conn = sqlite3.connect(str(old))
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except sqlite3.Error:
        pass
    new.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(old, new)
    print(f"Migrated SQLite {old} -> {new}")
shell = Path.home() / ".config/omarchy/shell.json"
if shell.exists():
    data = json.loads(shell.read_text())
    layout = data.get("bar", {}).get("layout", {})
    changed = False
    for section in layout.values():
        if not isinstance(section, list):
            continue
        for entry in section:
            if isinstance(entry, dict) and entry.get("id") == legacy_id:
                entry["id"] = plugin_id
                changed = True
    if changed:
        shell.write_text(json.dumps(data, indent=2) + "\n")
        print(f"Updated bar layout id {legacy_id} -> {plugin_id}")
PY

echo "Installed ${PLUGIN_ID} at ${TARGET}"

if [[ $RESTART_SHELL -eq 1 ]]; then
  echo "Starting omarchy-shell…"
  omarchy restart shell
else
  echo "Start the shell when you are ready: omarchy restart shell"
fi
