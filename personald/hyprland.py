from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActiveWindow:
    app_class: str
    title: str
    workspace: str
    pid: int | None
    raw: dict[str, Any]

    @property
    def is_empty(self) -> bool:
        return not self.app_class and not self.title


class HyprlandError(RuntimeError):
    pass


def get_active_window() -> ActiveWindow:
    result = subprocess.run(
        ["hyprctl", "activewindow", "-j"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HyprlandError(result.stderr.strip() or "hyprctl activewindow failed")

    try:
        raw = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise HyprlandError("hyprctl returned invalid JSON") from exc

    workspace = raw.get("workspace", {})
    if isinstance(workspace, dict):
        workspace_name = str(workspace.get("name") or workspace.get("id") or "")
    else:
        workspace_name = str(workspace or "")

    pid = raw.get("pid")
    if not isinstance(pid, int):
        pid = None

    return ActiveWindow(
        app_class=str(raw.get("class") or raw.get("initialClass") or ""),
        title=str(raw.get("title") or raw.get("initialTitle") or ""),
        workspace=workspace_name,
        pid=pid,
        raw=raw,
    )

