from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from personald.models import Deadline, ScheduleBlock
from personald.schedule import blocks_for_day, deadlines_for_range, get_timezone, now_in_timezone
from personald.state import DEFAULT_STATE_DIR, load_json, save_json


DEFAULT_PLANS_DIR = DEFAULT_STATE_DIR / "plans"


@dataclass(frozen=True)
class PlanItem:
    id: str
    start: datetime
    end: datetime
    type: str
    title: str
    status: str = "planned"
    course: str | None = None
    source: str = "manual"

    @property
    def duration_minutes(self) -> int:
        return max(0, int((self.end - self.start).total_seconds() // 60))

    def is_active_at(self, moment: datetime) -> bool:
        return self.start <= moment < self.end


@dataclass(frozen=True)
class DailyPlan:
    day: date
    accepted: bool
    items: list[PlanItem]


def plan_path(day: date, plans_dir: Path = DEFAULT_PLANS_DIR) -> Path:
    return plans_dir / f"{day.isoformat()}.json"


def generate_plan(config: dict, day: date) -> DailyPlan:
    items: list[PlanItem] = []

    for index, block in enumerate(blocks_for_day(config, day), start=1):
        items.append(_item_from_block(block, index))

    deadline_index = 1
    for deadline in deadlines_for_range(config, day, days=0):
        items.append(_item_from_deadline(deadline, deadline_index))
        deadline_index += 1

    return DailyPlan(day=day, accepted=False, items=sorted(items, key=lambda item: (item.start, item.end, item.id)))


def load_plan(config: dict, day: date, plans_dir: Path = DEFAULT_PLANS_DIR) -> DailyPlan:
    path = plan_path(day, plans_dir)
    data = load_json(path)
    if not data:
        return generate_plan(config, day)

    try:
        items = [_item_from_data(raw) for raw in data.get("items", []) if isinstance(raw, dict)]
        return DailyPlan(day=day, accepted=bool(data.get("accepted", False)), items=items)
    except (KeyError, ValueError, TypeError):
        return generate_plan(config, day)


def save_plan(plan: DailyPlan, plans_dir: Path = DEFAULT_PLANS_DIR) -> None:
    save_json(
        plan_path(plan.day, plans_dir),
        {
            "day": plan.day.isoformat(),
            "accepted": plan.accepted,
            "items": [_item_to_data(item) for item in plan.items],
        },
    )


def accept_plan(config: dict, day: date, plans_dir: Path = DEFAULT_PLANS_DIR) -> DailyPlan:
    plan = load_plan(config, day, plans_dir)
    updated = DailyPlan(day=plan.day, accepted=True, items=plan.items)
    save_plan(updated, plans_dir)
    return updated


def reset_plan(config: dict, day: date, plans_dir: Path = DEFAULT_PLANS_DIR) -> DailyPlan:
    path = plan_path(day, plans_dir)
    if path.exists():
        path.unlink()
    plan = generate_plan(config, day)
    save_plan(plan, plans_dir)
    return plan


def add_item(
    config: dict,
    day: date,
    title: str,
    start_time: str,
    minutes: int,
    item_type: str = "task",
    course: str | None = None,
    plans_dir: Path = DEFAULT_PLANS_DIR,
) -> DailyPlan:
    plan = load_plan(config, day, plans_dir)
    start = datetime.combine(day, time.fromisoformat(start_time), tzinfo=get_timezone(config))
    end = start + timedelta(minutes=minutes)
    item = PlanItem(
        id=_next_manual_id(plan),
        start=start,
        end=end,
        type=item_type,
        title=title,
        course=course,
        source="manual",
    )
    updated = DailyPlan(day=plan.day, accepted=plan.accepted, items=sorted([*plan.items, item], key=lambda i: (i.start, i.end, i.id)))
    save_plan(updated, plans_dir)
    return updated


def mark_item(
    config: dict,
    day: date,
    selector: str,
    status: str,
    moment: datetime | None = None,
    plans_dir: Path = DEFAULT_PLANS_DIR,
) -> DailyPlan:
    plan = load_plan(config, day, plans_dir)
    item_id = resolve_selector(plan, selector, moment or now_in_timezone(config))
    items = [_replace(item, status=status) if item.id == item_id else item for item in plan.items]
    updated = DailyPlan(day=plan.day, accepted=plan.accepted, items=items)
    save_plan(updated, plans_dir)
    return updated


def move_item(
    config: dict,
    day: date,
    selector: str,
    new_start_time: str,
    moment: datetime | None = None,
    plans_dir: Path = DEFAULT_PLANS_DIR,
) -> DailyPlan:
    plan = load_plan(config, day, plans_dir)
    item_id = resolve_selector(plan, selector, moment or now_in_timezone(config))
    new_start = datetime.combine(day, time.fromisoformat(new_start_time), tzinfo=get_timezone(config))
    items: list[PlanItem] = []
    for item in plan.items:
        if item.id != item_id:
            items.append(item)
            continue
        items.append(_replace(item, start=new_start, end=new_start + timedelta(minutes=item.duration_minutes), status="planned"))

    updated = DailyPlan(day=plan.day, accepted=plan.accepted, items=sorted(items, key=lambda item: (item.start, item.end, item.id)))
    save_plan(updated, plans_dir)
    return updated


def resolve_selector(plan: DailyPlan, selector: str, moment: datetime) -> str:
    if selector != "current":
        for item in plan.items:
            if item.id == selector:
                return item.id
        raise ValueError(f"Plan item not found: {selector}")

    active = [item for item in plan.items if item.is_active_at(moment) and item.status == "planned"]
    if active:
        return active[0].id

    upcoming = [item for item in plan.items if item.start >= moment and item.status == "planned"]
    if upcoming:
        return sorted(upcoming, key=lambda item: item.start)[0].id

    raise ValueError("No current or upcoming planned item.")


def _item_from_block(block: ScheduleBlock, index: int) -> PlanItem:
    return PlanItem(
        id=f"s{index}",
        start=block.start,
        end=block.end,
        type=block.type,
        title=block.title,
        course=block.course,
        source=block.source,
    )


def _item_from_deadline(deadline: Deadline, index: int) -> PlanItem:
    return PlanItem(
        id=f"d{index}",
        start=deadline.due,
        end=deadline.due,
        type="deadline",
        title=deadline.title,
        course=deadline.course,
        source="deadline",
    )


def _next_manual_id(plan: DailyPlan) -> str:
    existing = {item.id for item in plan.items}
    index = 1
    while f"m{index}" in existing:
        index += 1
    return f"m{index}"


def _item_to_data(item: PlanItem) -> dict:
    return {
        "id": item.id,
        "start": item.start.isoformat(),
        "end": item.end.isoformat(),
        "type": item.type,
        "title": item.title,
        "status": item.status,
        "course": item.course,
        "source": item.source,
    }


def _item_from_data(data: dict) -> PlanItem:
    return PlanItem(
        id=str(data["id"]),
        start=datetime.fromisoformat(str(data["start"])),
        end=datetime.fromisoformat(str(data["end"])),
        type=str(data["type"]),
        title=str(data["title"]),
        status=str(data.get("status", "planned")),
        course=data.get("course"),
        source=str(data.get("source", "manual")),
    )


def _replace(item: PlanItem, **changes) -> PlanItem:
    data = item.__dict__.copy()
    data.update(changes)
    return PlanItem(**data)

