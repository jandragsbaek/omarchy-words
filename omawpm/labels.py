"""Human labels for window classes, sites, and activity keys."""

from __future__ import annotations

CLASS_LABELS = {
    "md.obsidian.Obsidian": "Obsidian",
    "obsidian": "Obsidian",
    "grok-bot": "Grok Bot",
    "chromium": "Other",
    "chromium-browser": "Other",
    "google-chrome": "Other",
    "google-chrome-stable": "Other",
    "brave-browser": "Other",
    "brave": "Other",
    "firefox": "Other",
    "firefox-esr": "Other",
    "foot": "Foot",
    "Alacritty": "Alacritty",
    "alacritty": "Alacritty",
    "kitty": "Kitty",
    "ghostty": "Ghostty",
    "com.mitchellh.ghostty": "Ghostty",
    "org.wezfurlong.wezterm": "WezTerm",
    "code": "Code",
    "Code": "Code",
    "slack": "Slack",
    "herdr": "Herdr",
}

SITE_LABELS = {
    "x": "X",
    "twitter": "X",
    "github": "GitHub",
    "google": "Google",
    "youtube": "YouTube",
    "gmail": "Gmail",
    "reddit": "Reddit",
    "linkedin": "LinkedIn",
    "bluesky": "Bluesky",
    "chatgpt": "ChatGPT",
    "grok": "Grok",
    "wikipedia": "Wikipedia",
    "stackoverflow": "Stack Overflow",
    "notion": "Notion",
    "linear": "Linear",
    "slack": "Slack",
}

AGENT_LABELS = {
    "grok": "Grok",
    "claude": "Claude",
    "codex": "Codex",
    "gemini": "Gemini",
    "chatgpt": "ChatGPT",
    "cursor": "Cursor",
    "copilot": "Copilot",
    "amp": "Amp",
    "opencode": "OpenCode",
    "windsurf": "Windsurf",
}

CLASS_AI = {
    "grok-bot": "Grok",
    "Claude": "Claude",
    "claude": "Claude",
    "claude-desktop": "Claude",
    "codex-desktop": "Codex",
    "codex": "Codex",
    "Cursor": "Cursor",
    "cursor": "Cursor",
    "windsurf": "Windsurf",
}

SITE_AI = {
    "chatgpt": "ChatGPT",
    "grok": "Grok",
    "claude": "Claude",
}

BROWSER_LEFT = {
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "brave-browser",
    "brave",
    "firefox",
    "firefox-esr",
    "librewolf",
    "vivaldi",
    "vivaldi-stable",
}


def _title_case(text: str) -> str:
    return " ".join(part.capitalize() for part in text.replace("_", "-").split("-") if part)


def display_name(name: str) -> str:
    text = (name or "").strip()
    if not text:
        return ""
    if text in CLASS_LABELS:
        return CLASS_LABELS[text]
    if " · " in text:
        left, right = text.split(" · ", 1)
        site = SITE_LABELS.get(right.lower())
        if site and left in BROWSER_LEFT:
            return site
        if left.lower() in AGENT_LABELS or left == "herdr":
            return right
        left_label = CLASS_LABELS.get(left) or _title_case(left)
        return f"{left_label} · {right}"
    if "." in text:
        last = text.rsplit(".", 1)[-1]
        return CLASS_LABELS.get(last) or _title_case(last)
    return _title_case(text)


def ai_tool(name: str) -> str:
    text = (name or "").strip()
    if not text:
        return ""
    if text in CLASS_AI:
        return CLASS_AI[text]
    if " · " in text:
        left, right = text.split(" · ", 1)
        if left.lower() in AGENT_LABELS:
            return AGENT_LABELS[left.lower()]
        site = SITE_AI.get(right.lower())
        if site:
            return site
    return SITE_AI.get(text.lower(), "")


def row_tool(name: str) -> str:
    tool = ai_tool(name)
    if not tool:
        return ""
    shown = display_name(name)
    if shown == tool or shown.lower().startswith(tool.lower()):
        return ""
    return tool
