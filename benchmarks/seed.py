"""Populate only the dedicated benchmark database; never deletes existing records."""

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.core.security import hasher, new_token, token_digest
from app.models.entities import Application, ApplicationEvent, Company, Job, User
from app.models.entities import Session as LoginSession
from sqlalchemy import create_engine, func, insert, select, text
from sqlalchemy.orm import Session

BASE_DATE = datetime(2026, 1, 1, tzinfo=UTC)
TITLES = ["Backend Engineer", "Frontend Engineer", "Data Engineer", "Platform Engineer"]
STATUSES = ["active", "offer", "rejected", "withdrawn"]
LOCATIONS = ["Toronto", "Detroit", "Remote"]


def identifier(value):
    return uuid5(NAMESPACE_URL, f"tracker-benchmark-v1/{value}")


def dataset(count):
    user_id = identifier("user")
    companies = [
        {
            "id": identifier(f"company/{i}"),
            "user_id": user_id,
            "name": f"Benchmark Company {i:03d}",
            "location": LOCATIONS[i % 3],
        }
        for i in range(100)
    ]
    jobs, applications, events = [], [], []
    filtered = 0
    for i in range(count):
        job_id, app_id = identifier(f"job/{i}"), identifier(f"application/{i}")
        applied = BASE_DATE + timedelta(days=i % 365)
        status = STATUSES[i % 4]
        location = LOCATIONS[i % 3]
        filtered += status == "offer" and location == "Toronto"
        jobs.append(
            {
                "id": job_id,
                "user_id": user_id,
                "company_id": companies[i % 100]["id"],
                "title": f"{TITLES[i % 4]} {i:05d}",
                "location": location,
                "work_arrangement": "hybrid",
                "employment_type": "full_time",
            }
        )
        applications.append(
            {
                "id": app_id,
                "user_id": user_id,
                "job_id": job_id,
                "attempt_number": 1,
                "applied_on": applied.date(),
                "current_stage": "technical_interview",
                "status": status,
                "notes": f"Synthetic benchmark application {i:05d}. " + "Notes. " * 20,
            }
        )
        kinds = ["applied", "assessment", "technical_interview"]
        if status != "active":
            kinds.append(status)
        for step, kind in enumerate(kinds):
            events.append(
                {
                    "id": identifier(f"event/{i}/{step}"),
                    "application_id": app_id,
                    "event_type": kind,
                    "occurred_at": applied + timedelta(hours=step * 24),
                    "notes": "Synthetic benchmark history",
                }
            )
    return companies, jobs, applications, events, filtered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10000)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.count < 100 or args.count > 100000 or args.count % 4:
        parser.error("Count must be a multiple of four between 100 and 100000")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        if conn.scalar(text("SELECT current_database()")) != "tracker_benchmark":
            parser.error("Refusing to seed anything except tracker_benchmark")
    companies, jobs, applications, events, filtered = dataset(args.count)
    tokens = [new_token() for _ in range(25)]
    with Session(engine) as db, db.begin():
        if db.scalar(select(func.count()).select_from(User)):
            parser.error(
                "Database must be empty. Use a fresh benchmark volume; existing records are never replaced."
            )
        db.execute(
            insert(User),
            [
                {
                    "id": identifier("user"),
                    "email": "benchmark@example.com",
                    "password_hash": hasher.hash(new_token()),
                }
            ],
        )
        for model, rows in [
            (Company, companies),
            (Job, jobs),
            (Application, applications),
            (ApplicationEvent, events),
        ]:
            for start in range(0, len(rows), 1000):
                db.execute(insert(model), rows[start : start + 1000])
        db.execute(
            insert(LoginSession),
            [
                {
                    "user_id": identifier("user"),
                    "token_hash": token_digest(token),
                    "csrf_token_hash": token_digest(new_token()),
                    "expires_at": datetime.now(UTC) + timedelta(hours=24),
                }
                for token in tokens
            ],
        )
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("ANALYZE"))
    manifest = {
        "dataset_version": 1,
        "applications": args.count,
        "jobs": len(jobs),
        "companies": len(companies),
        "events": len(events),
        "expected": {
            "list": args.count,
            "search": args.count // 4,
            "filter": filtered,
            "later_page": args.count,
        },
        "tokens": tokens,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(manifest, output)
    print(json.dumps({k: v for k, v in manifest.items() if k != "tokens"}))
    engine.dispose()


if __name__ == "__main__":
    main()
