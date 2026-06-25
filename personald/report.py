from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from personald.plan import load_plan
from personald.schedule import blocks_for_day, planned_study_minutes_this_week, study_targets
from personald.storage import (
    DEFAULT_DB,
    BrowserCategoryTotal,
    CategoryTotal,
    browser_totals_for_range,
    category_totals_for_range,
    connect,
)


@dataclass(frozen=True)
class PlanSummary:
    planned: int
    done: int
    skipped: int


@dataclass(frozen=True)
class StudySummary:
    course: str
    target_seconds: int
    planned_seconds: int
    actual_seconds: int


@dataclass(frozen=True)
class Report:
    start_day: date
    end_day: date
    categories: list[CategoryTotal]
    browser_categories: list[BrowserCategoryTotal]
    plan: PlanSummary
    study: list[StudySummary]
    recommendations: list[str]


def today_report(config: dict, moment: datetime, db_path: Path = DEFAULT_DB) -> Report:
    return build_report(config, moment.date(), moment.date(), moment, db_path=db_path)


def week_report(config: dict, moment: datetime, db_path: Path = DEFAULT_DB) -> Report:
    start = moment.date() - timedelta(days=moment.weekday())
    end = start + timedelta(days=6)
    return build_report(config, start, end, moment, db_path=db_path)


def build_report(config: dict, start_day: date, end_day: date, moment: datetime, db_path: Path = DEFAULT_DB) -> Report:
    conn = connect(db_path)
    try:
        categories = category_totals_for_range(conn, start_day, end_day)
        browser_categories = browser_totals_for_range(conn, start_day, end_day)
    finally:
        conn.close()

    plan_summary = _plan_summary(config, start_day, end_day)
    study = _study_summary(config, start_day, end_day, categories, moment)
    recommendations = _recommendations(categories, browser_categories, plan_summary, study)
    return Report(
        start_day=start_day,
        end_day=end_day,
        categories=categories,
        browser_categories=browser_categories,
        plan=plan_summary,
        study=study,
        recommendations=recommendations,
    )


def _plan_summary(config: dict, start_day: date, end_day: date) -> PlanSummary:
    planned = done = skipped = 0
    day = start_day
    while day <= end_day:
        plan = load_plan(config, day)
        for item in plan.items:
            if item.status == "done":
                done += 1
            elif item.status == "skipped":
                skipped += 1
            else:
                planned += 1
        day += timedelta(days=1)
    return PlanSummary(planned=planned, done=done, skipped=skipped)


def _study_summary(config: dict, start_day: date, end_day: date, categories: list[CategoryTotal], moment: datetime) -> list[StudySummary]:
    actual_study_seconds = sum(total.duration_seconds for total in categories if total.category == "study")
    targets = study_targets(config)
    planned_week = planned_study_minutes_this_week(config, moment)
    result: list[StudySummary] = []

    if targets:
        courses = sorted(targets.keys())
    else:
        courses = sorted(planned_week.keys())

    for course in courses:
        result.append(
            StudySummary(
                course=course,
                target_seconds=int(targets.get(course, 0) * 3600),
                planned_seconds=planned_week.get(course, 0) * 60,
                actual_seconds=actual_study_seconds if len(courses) == 1 else 0,
            )
        )

    if actual_study_seconds and len(courses) != 1:
        result.append(StudySummary("Tracked study", 0, 0, actual_study_seconds))
    return result


def _recommendations(
    categories: list[CategoryTotal],
    browser_categories: list[BrowserCategoryTotal],
    plan: PlanSummary,
    study: list[StudySummary],
) -> list[str]:
    recommendations: list[str] = []
    category_map = {item.category: item.duration_seconds for item in categories}
    browser_map = {item.category: item.count for item in browser_categories}

    if category_map.get("distracting", 0) >= 30 * 60 or browser_map.get("distracting", 0) >= 10:
        recommendations.append("Distractions are noticeable. Use a focus session before the next study/work block.")

    if plan.skipped > plan.done and plan.skipped > 0:
        recommendations.append("More items were skipped than completed. Reduce tomorrow's plan or move heavy tasks earlier.")

    for item in study:
        if item.target_seconds and item.planned_seconds < item.target_seconds:
            recommendations.append(f"{item.course} is under-planned versus the weekly target.")
            break

    if not recommendations:
        recommendations.append("No major warning signs. Keep the plan light and review again tomorrow.")
    return recommendations
