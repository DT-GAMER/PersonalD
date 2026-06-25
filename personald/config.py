from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = Path.home() / ".config" / "personald" / "schedule.yaml"
DEFAULT_RULES = Path.home() / ".config" / "personald" / "rules.yaml"


class ConfigError(ValueError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ConfigError("Schedule config must be a YAML mapping.")

    return data


def load_optional_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_yaml(path)
