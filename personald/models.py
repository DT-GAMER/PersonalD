from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ScheduleBlock:
    start: datetime
    end: datetime
    type: str
    title: str
    course: str | None = None
    source: str = "weekly"
    priority: int | None = None

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)

    def is_active_at(self, moment: datetime) -> bool:
        return self.start <= moment < self.end


@dataclass(frozen=True)
class Deadline:
    due: datetime
    title: str
    course: str | None = None

    def is_upcoming_at(self, moment: datetime) -> bool:
        return self.due >= moment
