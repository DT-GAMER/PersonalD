from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_STATE_DIR = Path.home() / ".local" / "state" / "personald"
DEFAULT_HISTORY = DEFAULT_STATE_DIR / "notifications.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        return {}
    return data


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp_path.replace(path)

