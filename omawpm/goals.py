"""Parse and score configurable writing goals."""

from __future__ import annotations

import json
from typing import Any

from .activity import canonical_site


def normalize_match(match: str) -> tuple[str, str]:
    text = str(match or "").strip()
    lower = text.lower()
    if lower in {"*", "all"}:
        return "all", "*"
    prefixes = (
        ("class:", "class"),
        ("activity:", "activity"),
        ("herdr:", "herdr"),
        ("site:", "site"),
        ("ws:", "hypr"),
        ("workspace:", "hypr"),
    )
    for prefix, kind in prefixes:
        if lower.startswith(prefix):
            value = text[len(prefix) :].strip()
            if kind == "site":
                value = canonical_site(value)
            return kind, value
    return "any", text


def _pick(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    needle = value.lower()
    for row in rows:
        if str(row.get(key) or "").lower() == needle:
            return row
    return None


def _class_alike(klass: str, needle: str) -> bool:
    """`obsidian` matches `md.obsidian.Obsidian` and `Obsidian`."""
    k = str(klass or "").lower()
    n = str(needle or "").strip().lower()
    if not k or not n:
        return False
    if k == n:
        return True
    parts = [p for p in k.split(".") if p]
    return n == parts[-1] or n in parts


def _pick_app(apps: list[dict[str, Any]], value: str) -> dict[str, Any] | None:
    found = _pick(apps, "app_class", value)
    if found:
        return found
    for row in apps:
        if _class_alike(str(row.get("app_class") or ""), value):
            return row
    return None


def _match_identity(kind: str, value: str) -> tuple[str, str]:
    """Collapse class/activity/any of the same window into one bucket so a
    picker that adds both `class:X` and `activity:X` does not double-count."""
    n = str(value or "").strip().lower()
    if kind in {"class", "activity", "any"}:
        return ("window", n.split(".")[-1] if "." in n else n)
    return (kind, n)


def _zeros() -> dict[str, int]:
    return {
        "inserted_words": 0,
        "deleted_words": 0,
        "inserted_chars": 0,
        "deleted_chars": 0,
        "net_words": 0,
        "net_chars": 0,
    }


def _from_row(row: dict[str, Any] | None) -> dict[str, int]:
    if not row:
        return _zeros()
    inserted_words = int(row.get("inserted_words") or 0)
    deleted_words = int(row.get("deleted_words") or 0)
    inserted_chars = int(row.get("inserted_chars") or 0)
    deleted_chars = int(row.get("deleted_chars") or 0)
    return {
        "inserted_words": inserted_words,
        "deleted_words": deleted_words,
        "inserted_chars": inserted_chars,
        "deleted_chars": deleted_chars,
        "net_words": int(row.get("net_words") or max(0, inserted_words - deleted_words)),
        "net_chars": int(row.get("net_chars") or max(0, inserted_chars - deleted_chars)),
    }


def counts_for_match(
    match: str,
    apps: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    herdr: list[dict[str, Any]],
    hypr: list[dict[str, Any]],
    total: dict[str, Any] | None = None,
    sites: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    sites = sites or []
    kind, value = normalize_match(match)
    if kind == "all":
        return _from_row(total)
    if kind == "class":
        return _from_row(_pick_app(apps, value))
    if kind == "activity":
        return _from_row(
            _pick(activities, "name", value)
            or _pick(activities, "app_class", value)
            or _pick_app(apps, value)
        )
    if kind == "herdr":
        return _from_row(_pick(herdr, "name", value))
    if kind == "hypr":
        return _from_row(_pick(hypr, "name", value))
    if kind == "site":
        return _from_row(_pick(sites, "name", value))
    row = (
        _pick_app(apps, value)
        or _pick(herdr, "name", value)
        or _pick(activities, "name", value)
        or _pick(activities, "app_class", value)
        or _pick(hypr, "name", value)
        or _pick(sites, "name", canonical_site(value))
    )
    return _from_row(row)


def match_list(match: Any) -> list[str]:
    if isinstance(match, list):
        return [str(item).strip() for item in match if str(item).strip()]
    text = str(match or "").strip()
    return [text] if text else []


def counts_for_matches(
    matches: Any,
    apps: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    herdr: list[dict[str, Any]],
    hypr: list[dict[str, Any]],
    total: dict[str, Any] | None = None,
    sites: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    items = match_list(matches)
    if not items:
        return _zeros()
    if len(items) == 1:
        return counts_for_match(items[0], apps, activities, herdr, hypr, total, sites)
    acc = _zeros()
    seen: set[tuple[str, str]] = set()
    for item in items:
        kind, value = normalize_match(item)
        identity = _match_identity(kind, value)
        if identity in seen:
            continue
        seen.add(identity)
        counts = counts_for_match(item, apps, activities, herdr, hypr, total, sites)
        for key in ("inserted_words", "deleted_words", "inserted_chars", "deleted_chars"):
            acc[key] += int(counts.get(key) or 0)
    acc["net_words"] = max(0, acc["inserted_words"] - acc["deleted_words"])
    acc["net_chars"] = max(0, acc["inserted_chars"] - acc["deleted_chars"])
    return acc


def parse_goals(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    raw = cfg.get("goals")
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = None
    goals: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            matches = match_list(item.get("match") or item.get("matches"))
            if not matches:
                continue
            words = item.get("words", item.get("target", 0))
            try:
                target = max(0, int(words))
            except (TypeError, ValueError):
                target = 0
            primary = matches[0]
            goals.append(
                {
                    "match": primary if len(matches) == 1 else matches,
                    "matches": matches,
                    "target": target,
                    "label": str(item.get("label") or primary),
                }
            )
    if not goals:
        match = str(cfg.get("goalMatch") or cfg.get("goalAppClass") or "obsidian").strip() or "obsidian"
        try:
            target = max(0, int(cfg.get("goalWords") or 1000))
        except (TypeError, ValueError):
            target = 1000
        goals.append({"match": match, "matches": [match], "target": target, "label": match})
    return goals


def score_goals(
    cfg: dict[str, Any],
    apps: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    herdr: list[dict[str, Any]],
    hypr: list[dict[str, Any]],
    total: dict[str, Any] | None = None,
    sites: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    scored = []
    for goal in parse_goals(cfg):
        counts = counts_for_matches(
            goal.get("matches") or goal["match"], apps, activities, herdr, hypr, total, sites
        )
        target = int(goal["target"] or 0)
        net = int(counts["net_words"])
        matches = match_list(goal.get("matches") or goal["match"])
        scored.append(
            {
                "match": matches[0] if len(matches) == 1 else matches,
                "matches": matches,
                "label": goal["label"],
                "target": target,
                "net_words": net,
                "inserted_words": counts["inserted_words"],
                "deleted_words": counts["deleted_words"],
                "percent": 0 if target <= 0 else min(100, int(round(100 * net / target))),
            }
        )
    return scored
