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
        return _from_row(_pick(apps, "app_class", value))
    if kind == "activity":
        return _from_row(_pick(activities, "name", value) or _pick(activities, "app_class", value))
    if kind == "herdr":
        return _from_row(_pick(herdr, "name", value))
    if kind == "hypr":
        return _from_row(_pick(hypr, "name", value))
    if kind == "site":
        return _from_row(_pick(sites, "name", value))
    row = (
        _pick(apps, "app_class", value)
        or _pick(herdr, "name", value)
        or _pick(activities, "name", value)
        or _pick(activities, "app_class", value)
        or _pick(hypr, "name", value)
        or _pick(sites, "name", canonical_site(value))
    )
    return _from_row(row)


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
            match = str(item.get("match") or "").strip()
            if not match:
                continue
            words = item.get("words", item.get("target", 0))
            try:
                target = max(0, int(words))
            except (TypeError, ValueError):
                target = 0
            goals.append(
                {
                    "match": match,
                    "target": target,
                    "label": str(item.get("label") or match),
                }
            )
    if not goals:
        match = str(cfg.get("goalMatch") or cfg.get("goalAppClass") or "obsidian").strip() or "obsidian"
        try:
            target = max(0, int(cfg.get("goalWords") or 1000))
        except (TypeError, ValueError):
            target = 1000
        goals.append({"match": match, "target": target, "label": match})
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
        counts = counts_for_match(goal["match"], apps, activities, herdr, hypr, total, sites)
        target = int(goal["target"] or 0)
        net = int(counts["net_words"])
        scored.append(
            {
                "match": goal["match"],
                "label": goal["label"],
                "target": target,
                "net_words": net,
                "inserted_words": counts["inserted_words"],
                "deleted_words": counts["deleted_words"],
                "percent": 0 if target <= 0 else min(100, int(round(100 * net / target))),
            }
        )
    return scored
