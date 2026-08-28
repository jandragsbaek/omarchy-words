# WPM for Omarchy

Live words-per-minute from **actual keyboard input**, attributed to the
active Hyprland window. Git-style `+insertions −deletions` per app, a
daily Obsidian word goal, SQLite history, Markdown export into a daily
note, and a GitHub-style year graph in the panel.

It never stores the text you type — only counts.

## Install

```sh
omarchy plugin add /home/jan/src/omarchy-wpm --enable --yes
```

Or from a published git remote:

```sh
omarchy plugin add https://github.com/<you>/omarchy-wpm.git --enable
```

The widget lands on the right of the bar. Move it with `omarchy bar move jan.wpm`.

## Keyboard access

The daemon reads `/dev/input` (evdev). Your user must be in the `input` group:

```sh
sudo usermod -aG input $USER
```

Then log out and back in. Until that is done, the bar shows `WPM setup`.

This is the same permission OmaVibes and other input-aware tools need.
Once you are in `input`, any process running as you can read raw keys.
This plugin only counts keystrokes; it does not write characters, key
names, or sequences to disk.

## What it counts

| Metric | Rule |
|---|---|
| Live / burst / session WPM | Net characters ÷ 5 ÷ minutes (typing-test standard). A burst ends after 1.5s idle. |
| Daily goal words | Space-separated letter-runs, net of backspace. Default goal: **1000 words in `obsidian`**. |
| Git diffs | `+` printable keys, `−` backspace/delete, rolled up per Hyprland class and window title. |
| Shortcuts | Ignored while Ctrl, Alt, or Super are held. Shift still counts as typing. |
| Lock screen | Counting pauses while the session looks locked. |

Right-click the bar chip to pause or resume. Middle-click exports today's Markdown.

## Panel

Click the chip. You get live WPM, the Obsidian goal bar, per-app `+words −words`
(click a row to expand windows), and a contribution graph. Keys:

| Key | Action |
|---|---|
| `Y` | Expand / collapse the year graph |
| `E` | Export today's Markdown |
| `P` | Pause / resume |
| `Esc` | Close |

## Daily note

Set **Daily note path** in the widget settings, for example:

```
~/vault/Daily/{yyyy}-{MM}-{dd}.md
```

Tokens: `{date}`, `{yyyy}`, `{MM}`, `{dd}`, `{yyyy-MM-dd}`.

Turn on **Update daily note** to rewrite a marked section as you type, or
export on demand:

```sh
omawpm export --note ~/vault/Daily/{date}.md
omawpm export --stdout
```

The plugin owns only this block, and will not touch the rest of the note:

```markdown
<!-- omawpm:start -->
## Writing — 2026-08-28
...
<!-- omawpm:end -->
```

## Data

- SQLite: `~/.local/state/omarchy/plugins/jan.wpm/wpm.sqlite`
- Config: `~/.config/omarchy/omawpm.json`
- Live status: `$XDG_RUNTIME_DIR/omawpm/status.json` (mode 0600)

```sh
omawpm status
omawpm config goalWords 1000
omawpm config goalAppClass obsidian
omawpm pause
omawpm resume
```

## Privacy

Persisted rows are day + window class + title + numeric totals. No
keycodes, no timestamps per key, no document text. Window titles can
still leak note names (Obsidian puts the note title in the window title);
that is how per-window stats work.

## Development

```sh
PYTHONPATH=. python3 -m unittest discover -s tests -v
omarchy plugin validate .
qmllint -I /usr/share/omarchy/shell BarWidget.qml Panel.qml Service.qml
```

The counting core is stdlib Python (no `python-evdev`). The shell plugin
is Quickshell QML and follows the active Omarchy theme (`Color` / `Style`).
