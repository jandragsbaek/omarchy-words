"""Infer a stable activity label from Hyprland + herdr, without storing prompt text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

TERMINALS = {
    "foot",
    "alacritty",
    "kitty",
    "ghostty",
    "org.wezfurlong.wezterm",
    "com.mitchellh.ghostty",
}

BROWSERS = {
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "google-chrome-beta",
    "google-chrome-unstable",
    "brave-browser",
    "brave",
    "firefox",
    "firefox-esr",
    "librewolf",
    "zen",
    "zen-browser",
    "vivaldi-stable",
    "vivaldi",
    "microsoft-edge",
    "microsoft-edge-stable",
    "thorium-browser",
    "thorium",
    "opera",
}

# Title remainder → stored slug. Only these ever leave process memory.
SITE_ALIASES = {
    "twitter": "x",
    "x.com": "x",
    "twitter.com": "x",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "github.com": "github",
    "mail.google.com": "gmail",
    "reddit.com": "reddit",
    "linkedin.com": "linkedin",
    "bsky.app": "bluesky",
    "bsky": "bluesky",
    "chatgpt.com": "chatgpt",
    "chat.openai.com": "chatgpt",
    "grok.com": "grok",
    "grok.x.ai": "grok",
    "stackoverflow.com": "stackoverflow",
    "stack overflow": "stackoverflow",
    "notion.so": "notion",
    "linear.app": "linear",
    "slack.com": "slack",
    "wikipedia.org": "wikipedia",
}

_BROWSER_SUFFIX_RE = re.compile(
    r"\s+[—–-]\s+"
    r"(?:Google Chrome|Microsoft Edge|Mozilla Firefox|Zen Browser|"
    r"Chromium(?:-browser)?|Chrome|Brave|Firefox|LibreWolf|Zen|"
    r"Vivaldi|Opera|Thorium)\s*$",
    re.IGNORECASE,
)
_NOTIFY_RE = re.compile(r"^\(\d+[+]?\)\s+")
_ON_X_RE = re.compile(r"\bon x:\s", re.IGNORECASE)

# Longest first. Matched against the title with the browser suffix removed.
_SITE_ENDINGS = (
    (" - google search", "google"),
    (" / twitter", "x"),
    (" / x", "x"),
    (" · github", "github"),
    (" - github", "github"),
    (" - youtube", "youtube"),
    (" - gmail", "gmail"),
    (" - wikipedia, the free encyclopedia", "wikipedia"),
    (" - wikipedia", "wikipedia"),
    (" : reddit", "reddit"),
    (" - reddit", "reddit"),
    (" | linkedin", "linkedin"),
    (" - linkedin", "linkedin"),
    (" - bluesky", "bluesky"),
    (" · slack", "slack"),
    (" - slack", "slack"),
    (" | notion", "notion"),
    (" - notion", "notion"),
    (" - linear", "linear"),
    (" - stack overflow", "stackoverflow"),
    (" - chatgpt", "chatgpt"),
)

_SITE_EXACT = {
    "x": "x",
    "twitter": "x",
    "github": "github",
    "youtube": "youtube",
    "gmail": "gmail",
    "reddit": "reddit",
    "linkedin": "linkedin",
    "bluesky": "bluesky",
    "chatgpt": "chatgpt",
    "grok": "grok",
}

# Longer hosts first so grok.x.ai wins over x.com.
_HOST_SITES = (
    ("mail.google.com", "gmail"),
    ("chat.openai.com", "chatgpt"),
    ("stackoverflow.com", "stackoverflow"),
    ("twitter.com", "x"),
    ("github.com", "github"),
    ("youtube.com", "youtube"),
    ("linkedin.com", "linkedin"),
    ("reddit.com", "reddit"),
    ("chatgpt.com", "chatgpt"),
    ("wikipedia.org", "wikipedia"),
    ("linear.app", "linear"),
    ("notion.so", "notion"),
    ("bsky.app", "bluesky"),
    ("slack.com", "slack"),
    ("youtu.be", "youtube"),
    ("grok.x.ai", "grok"),
    ("grok.com", "grok"),
    ("x.com", "x"),
)


@dataclass(frozen=True)
class HerdrFocus:
    workspace: str
    agent: str
    pane_id: str = ""
    workspaces: tuple[str, ...] = ()


@dataclass(frozen=True)
class Activity:
    activity: str
    app_class: str
    title: str
    hypr_workspace: str
    herdr_workspace: str
    herdr_agent: str
    source: str
    site: str = ""

    @property
    def key(self) -> str:
        return "\x1f".join(
            (
                self.activity,
                self.hypr_workspace,
                self.herdr_workspace,
                self.app_class,
                self.site,
            )
        )

    @classmethod
    def from_key(cls, key: str) -> "Activity":
        parts = key.split("\x1f")
        while len(parts) < 5:
            parts.append("")
        activity, hypr_ws, herdr_ws, app_class, site = parts[:5]
        site = canonical_site(site)
        agent = ""
        if " · " in activity:
            maybe_agent, _, rest = activity.partition(" · ")
            if maybe_agent.lower() in BROWSERS:
                if not site:
                    site = canonical_site(rest)
            elif maybe_agent and maybe_agent != "herdr":
                agent = maybe_agent
        return cls(
            activity=activity or app_class or "unknown",
            app_class=app_class or "unknown",
            title="",
            hypr_workspace=hypr_ws,
            herdr_workspace=herdr_ws,
            herdr_agent=agent,
            source="key",
            site=site,
        )


def title_suffix(title: str) -> str:
    text = (title or "").strip()
    if ":" not in text:
        return ""
    return text.split(":", 1)[1].strip()


def canonical_site(value: str) -> str:
    text = (value or "").strip().lower()
    if text.startswith("www."):
        text = text[4:]
    return SITE_ALIASES.get(text, text)


def is_browser(app_class: str) -> bool:
    return (app_class or "").strip().lower() in BROWSERS


def page_title(title: str) -> str:
    """Browser chrome only: drop the app suffix and a leading (N) badge."""
    text = (title or "").strip()
    text = _BROWSER_SUFFIX_RE.sub("", text).strip()
    return _NOTIFY_RE.sub("", text).strip()


def classify_site(app_class: str, title: str) -> str:
    """Allowlisted site slug, or empty. Never returns title text."""
    if not is_browser(app_class):
        return ""
    text = page_title(title)
    if not text:
        return ""
    lower = text.lower()
    if lower in _SITE_EXACT:
        return _SITE_EXACT[lower]
    for ending, slug in _SITE_ENDINGS:
        if lower.endswith(ending):
            return slug
    if _ON_X_RE.search(text):
        return "x"
    for host, slug in _HOST_SITES:
        pattern = (
            rf"(?:^|[\s/])(?:https?://(?:www\.)?)?(?:www\.)?{re.escape(host)}(?:[:/\s]|$)"
        )
        if re.search(pattern, lower):
            return slug
    return ""


def browser_activity_label(app_class: str, site: str) -> str:
    app_class = (app_class or "chromium").strip() or "chromium"
    site = canonical_site(site)
    if site:
        return f"{app_class} · {site}"
    return app_class


def herdr_activity_label(agent: str, workspace: str) -> str:
    workspace = (workspace or "").strip()
    agent = (agent or "").strip()
    if agent and workspace:
        return f"{agent} · {workspace}"
    if workspace:
        return f"herdr · {workspace}"
    if agent:
        return agent
    return "herdr"


def infer_activity(
    app_class: str,
    title: str,
    hypr_workspace: str = "",
    herdr: Optional[HerdrFocus] = None,
    hosts_herdr: bool = False,
    proc_agent: str = "",
) -> Activity:
    app_class = (app_class or "unknown").strip() or "unknown"
    title = (title or "").strip()
    hypr_workspace = (hypr_workspace or "").strip()
    suffix = title_suffix(title)

    if hosts_herdr and herdr and (herdr.workspace or herdr.agent):
        label = herdr_activity_label(herdr.agent, herdr.workspace)
        return Activity(
            activity=label,
            app_class=app_class,
            title="",
            hypr_workspace=hypr_workspace,
            herdr_workspace=herdr.workspace,
            herdr_agent=herdr.agent,
            source="herdr",
        )

    known = {w.lower(): w for w in (herdr.workspaces if herdr else ())}
    if suffix and suffix.lower() in known:
        workspace = known[suffix.lower()]
        return Activity(
            activity=herdr_activity_label("", workspace),
            app_class=app_class,
            title="",
            hypr_workspace=hypr_workspace,
            herdr_workspace=workspace,
            herdr_agent="",
            source="title",
        )

    if proc_agent and app_class.lower() in {t.lower() for t in TERMINALS}:
        slug = proc_agent.strip().lower()
        if slug:
            label = f"{slug} · {hypr_workspace}" if hypr_workspace else slug
            return Activity(
                activity=label,
                app_class=app_class,
                title="",
                hypr_workspace=hypr_workspace,
                herdr_workspace="",
                herdr_agent=slug,
                source="proc",
            )

    site = classify_site(app_class, title)
    if site:
        return Activity(
            activity=browser_activity_label(app_class, site),
            app_class=app_class,
            title="",
            hypr_workspace=hypr_workspace,
            herdr_workspace="",
            herdr_agent="",
            source="site",
            site=site,
        )

    return Activity(
        activity=app_class,
        app_class=app_class,
        title="",
        hypr_workspace=hypr_workspace,
        herdr_workspace="",
        herdr_agent="",
        source="class",
    )
