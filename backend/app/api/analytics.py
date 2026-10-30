from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.dependencies import CurrentUser, Database
from app.models.entities import Application, ApplicationEvent

router = APIRouter(tags=["analytics"])
INTERVIEWS = {"recruiter_screen", "technical_interview", "behavioral_interview", "final_interview"}
RESPONSES = INTERVIEWS | {"assessment", "offer", "rejected"}
STAGES = {"applied", "assessment"} | INTERVIEWS


def summarize(rows, date_from, date_to, timezone):
    zone = ZoneInfo(timezone)
    applications = {}
    events = defaultdict(list)
    activity = defaultdict(lambda: {"applications": 0, "events": 0})

    def week(day):
        return (day - timedelta(days=day.weekday())).isoformat()

    def included(day):
        return (date_from is None or day >= date_from) and (date_to is None or day <= date_to)

    for application, event in rows:
        applications[application.id] = application
        if event is not None:
            events[application.id].append(event)
            day = event.occurred_at.astimezone(zone).date()
            if event.event_type != "applied" and included(day):
                activity[week(day)]["events"] += 1
    cohort = [a for a in applications.values() if included(a.applied_on)]
    status = Counter(a.status for a in cohort)
    stage = Counter(a.current_stage for a in cohort if a.status == "active")
    responding = assessed = interviewed = offers = interview_offers = 0
    response_days = []
    durations = defaultdict(list)
    for application in applications.values():
        if included(application.applied_on):
            activity[week(application.applied_on)]["applications"] += 1
    for application in cohort:
        history = sorted(
            events[application.id], key=lambda e: (e.occurred_at, e.recorded_at, str(e.id))
        )
        kinds = {e.event_type for e in history}
        interviewed += bool(kinds & INTERVIEWS)
        assessed += "assessment" in kinds
        offers += "offer" in kinds
        interview_offers += bool(kinds & INTERVIEWS) and "offer" in kinds
        first = next((e for e in history if e.event_type in RESPONSES), None)
        if first:
            responding += 1
            applied = datetime.combine(application.applied_on, datetime.min.time(), tzinfo=UTC)
            response_days.append((first.occurred_at - applied).total_seconds() / 86400)
        transitions = [e for e in history if e.event_type != "note"]
        for previous, following in pairwise(transitions):
            if previous.event_type in STAGES:
                durations[previous.event_type].append(
                    (following.occurred_at - previous.occurred_at).total_seconds() / 86400
                )
    total = len(cohort)

    def ratio(numerator, denominator):
        return {
            "numerator": numerator,
            "denominator": denominator,
            "value": numerator / denominator if denominator else None,
        }

    return {
        "total": total,
        "timezone": timezone,
        "statuses": {name: status[name] for name in ["active", "offer", "rejected", "withdrawn"]},
        "active_stages": {name: stage[name] for name in sorted(STAGES)},
        "response_rate": ratio(responding, total),
        "assessment_rate": ratio(assessed, total),
        "interview_rate": ratio(interviewed, total),
        "offer_rate": ratio(offers, total),
        "interview_to_offer": ratio(interview_offers, interviewed),
        "unanswered": total - responding,
        "mean_response_days": sum(response_days) / len(response_days) if response_days else None,
        "stage_durations": [
            {
                "stage": name,
                "completed_intervals": len(values),
                "mean_days": sum(values) / len(values),
            }
            for name, values in sorted(durations.items())
        ],
        "weekly_activity": [{"week": key, **value} for key, value in sorted(activity.items())],
    }


@router.get("/analytics/dashboard")
def dashboard(
    db: Database,
    auth: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
    timezone: str = Query(default="UTC", max_length=100),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Start date must not follow end date")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Unknown timezone") from None
    # One statement gives a consistent snapshot of application state and history.
    rows = db.execute(
        select(Application, ApplicationEvent)
        .outerjoin(ApplicationEvent, ApplicationEvent.application_id == Application.id)
        .where(Application.user_id == auth.user.id)
    ).all()
    return summarize(rows, date_from, date_to, timezone)
