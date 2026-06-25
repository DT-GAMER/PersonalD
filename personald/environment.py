from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class EnvAction:
    kind: str
    value: str


def environments(config: dict) -> dict[str, dict]:
    raw = config.get("environments", {}) or {}
    return raw if isinstance(raw, dict) else {}


def environment_names(config: dict) -> list[str]:
    return sorted(environments(config).keys())


def environment_actions(config: dict, name: str) -> list[EnvAction]:
    env = _environment(config, name)
    actions: list[EnvAction] = []

    workspace = env.get("workspace")
    if workspace is not None:
        actions.append(EnvAction("workspace", str(workspace)))

    for raw in env.get("open", []) or []:
        if isinstance(raw, str):
            actions.append(_action_from_string(raw))
        elif isinstance(raw, dict):
            actions.extend(_actions_from_mapping(raw))

    return actions


def cleanup_actions(config: dict, name: str) -> list[EnvAction]:
    env = _environment(config, name)
    actions: list[EnvAction] = []
    cleanup = env.get("cleanup", {}) or {}
    if not isinstance(cleanup, dict):
        return actions

    for app_class in cleanup.get("close_windows", []) or []:
        actions.append(EnvAction("close_window", str(app_class)))
    for command in cleanup.get("commands", []) or []:
        actions.append(EnvAction("command", str(command)))
    return actions


def run_environment(config: dict, name: str, dry_run: bool = False) -> list[EnvAction]:
    actions = environment_actions(config, name)
    for action in actions:
        _run_action(action, dry_run)
    return actions


def run_cleanup(config: dict, name: str, dry_run: bool = False) -> list[EnvAction]:
    actions = cleanup_actions(config, name)
    for action in actions:
        _run_action(action, dry_run)
    return actions


def _environment(config: dict, name: str) -> dict:
    envs = environments(config)
    if name not in envs or not isinstance(envs[name], dict):
        raise ValueError(f"Environment not found: {name}")
    return envs[name]


def _action_from_string(value: str) -> EnvAction:
    if value.startswith("http://") or value.startswith("https://"):
        return EnvAction("url", value)
    return EnvAction("command", value)


def _actions_from_mapping(raw: dict) -> list[EnvAction]:
    actions: list[EnvAction] = []
    if "url" in raw:
        actions.append(EnvAction("url", str(raw["url"])))
    if "app" in raw:
        actions.append(EnvAction("command", str(raw["app"])))
    if "command" in raw:
        actions.append(EnvAction("command", str(raw["command"])))
    if "workspace" in raw:
        actions.append(EnvAction("workspace", str(raw["workspace"])))
    return actions


def _run_action(action: EnvAction, dry_run: bool) -> None:
    if dry_run:
        return

    if action.kind == "workspace":
        subprocess.Popen(["hyprctl", "dispatch", "workspace", action.value])
    elif action.kind == "url":
        subprocess.Popen(["xdg-open", action.value])
    elif action.kind == "close_window":
        subprocess.Popen(["hyprctl", "dispatch", "closewindow", f"class:{action.value}"])
    elif action.kind == "command":
        subprocess.Popen(shlex.split(action.value))

