"""Compare optimized pagination with the original joined-query semantics."""

from datetime import UTC, date, datetime

from sqlalchemy import func, or_, select

from app.models.entities import Application, Company, Job, User
from app.repositories.tracking import TrackingRepository


def test_application_query_preserves_search_filters_order_and_ownership(auth_context):
    _, db, _ = auth_context
    owner = User(email="query-owner@example.com", password_hash="unused")
    other = User(email="query-other@example.com", password_hash="unused")
    db.add_all([owner, other])
    db.flush()
    companies = []
    for user in (owner, other):
        for name in ("Alpha Company", "Needle_%/ Company", "alpha Company"):
            company = Company(user_id=user.id, name=name)
            db.add(company)
            db.flush()
            companies.append(company)
            for index in range(4):
                job = Job(
                    user_id=user.id,
                    company_id=company.id,
                    title=["Needle Engineer", "100% Engineer", "under_score", "Other"][index],
                    location="Detroit" if index % 2 else None,
                    archived_at=datetime.now(UTC) if index == 3 else None,
                )
                db.add(job)
                db.flush()
                for attempt in (1, 2):
                    db.add(
                        Application(
                            user_id=user.id,
                            job_id=job.id,
                            attempt_number=attempt,
                            applied_on=date(2026, 10, index + 1),
                            current_stage="applied",
                            status="active" if attempt == 1 else "rejected",
                            notes="Only notes Needle_%/" if index == 3 else None,
                        )
                    )
    db.flush()
    repo = TrackingRepository(db, owner.id)
    cases = [
        {},
        *({"q": q} for q in ("needle", "%", "_", "/", "Only notes", "missing")),
        {"company_id": companies[0].id},
        {"company_id": companies[3].id},
        {"location": "DETROIT"},
        {"status": "rejected"},
        {"date_from": date(2026, 10, 2), "date_to": date(2026, 10, 3)},
        {
            "q": "needle",
            "company_id": companies[0].id,
            "status": "rejected",
            "location": "Detroit",
            "date_from": date(2026, 10, 4),
            "date_to": date(2026, 10, 4),
        },
    ]
    for changes in cases:
        for sort in ("newest", "oldest", "company", "title"):
            for page in (1, 2, 20):
                args = {
                    "q": None,
                    "company_id": None,
                    "status": None,
                    "location": None,
                    "date_from": None,
                    "date_to": None,
                    "sort": sort,
                    "page": page,
                    "page_size": 3,
                }
                args.update(changes)
                reference = (
                    select(Application, Job, Company)
                    .join(Job, Application.job_id == Job.id)
                    .join(Company, Job.company_id == Company.id)
                    .where(Application.user_id == owner.id)
                )
                if args["q"]:
                    reference = reference.where(
                        or_(
                            Job.title.icontains(args["q"], autoescape=True),
                            Company.name.icontains(args["q"], autoescape=True),
                            Application.notes.icontains(args["q"], autoescape=True),
                        )
                    )
                for value, predicate in (
                    (args["company_id"], Job.company_id == args["company_id"]),
                    (args["status"], Application.status == args["status"]),
                ):
                    if value:
                        reference = reference.where(predicate)
                if args["location"]:
                    reference = reference.where(
                        Job.location.icontains(args["location"], autoescape=True)
                    )
                if args["date_from"]:
                    reference = reference.where(Application.applied_on >= args["date_from"])
                if args["date_to"]:
                    reference = reference.where(Application.applied_on <= args["date_to"])
                ordering = {
                    "newest": Application.applied_on.desc(),
                    "oldest": Application.applied_on.asc(),
                    "company": func.lower(Company.name),
                    "title": func.lower(Job.title),
                }[sort]
                expected_total = db.scalar(select(func.count()).select_from(reference.subquery()))
                expected = db.execute(
                    reference.order_by(ordering, Application.id).offset((page - 1) * 3).limit(3)
                ).all()
                actual, total = repo.applications(**args)
                assert total == expected_total, args
                assert [tuple(entity.id for entity in row) for row in actual] == [
                    tuple(entity.id for entity in row) for row in expected
                ], args
