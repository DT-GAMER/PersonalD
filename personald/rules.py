from __future__ import annotations

from urllib.parse import urlparse

from personald.hyprland import ActiveWindow


def categorize(window: ActiveWindow, rules: dict) -> str:
    categories = rules.get("categories", {}) or {}
    if not isinstance(categories, dict):
        return "unknown"

    for category, raw_rule in categories.items():
        if not isinstance(raw_rule, dict):
            continue
        if _matches(window, raw_rule):
            return str(category)

    return "unknown"


def categorize_browser(url: str, title: str, rules: dict) -> str:
    websites = rules.get("websites", {}) or {}
    if isinstance(websites, dict):
        host = (urlparse(url).hostname or "").lower()
        lowered_url = url.lower()
        lowered_title = title.lower()

        for category, patterns in websites.items():
            for pattern in _as_strings(patterns):
                lowered_pattern = pattern.lower()
                if _host_matches(host, lowered_pattern) or lowered_pattern in lowered_url:
                    return str(category)

        categories = rules.get("categories", {}) or {}
        if isinstance(categories, dict):
            for category, raw_rule in categories.items():
                if not isinstance(raw_rule, dict):
                    continue
                for value in _as_strings(raw_rule.get("title_contains")):
                    if value.lower() in lowered_title:
                        return str(category)

    return "unknown"


def _matches(window: ActiveWindow, rule: dict) -> bool:
    app_class = window.app_class.lower()
    title = window.title.lower()

    for value in _as_strings(rule.get("apps")):
        if app_class == value.lower():
            return True

    for value in _as_strings(rule.get("class_contains")):
        if value.lower() in app_class:
            return True

    for value in _as_strings(rule.get("title_contains")):
        if value.lower() in title:
            return True

    return False


def _as_strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _host_matches(host: str, pattern: str) -> bool:
    if host == pattern:
        return True
    return host.endswith("." + pattern)
