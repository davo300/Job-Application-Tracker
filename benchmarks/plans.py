"""Capture warm PostgreSQL plans for the benchmark's application search queries."""

import json
import os

from app.repositories.tracking import TrackingRepository
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from benchmarks.seed import identifier


def main():
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as connection:
        if connection.scalar(text("SELECT current_database()")) != "tracker_benchmark":
            raise RuntimeError("Plans may only be collected from tracker_benchmark")
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append((statement, parameters))

    event.listen(engine, "before_cursor_execute", capture)
    with Session(engine) as db:
        TrackingRepository(db, identifier("user")).applications(
            q="Backend",
            company_id=None,
            status=None,
            location=None,
            date_from=None,
            date_to=None,
            sort="company",
            page=1,
            page_size=25,
        )
    event.remove(engine, "before_cursor_execute", capture)
    results = []
    with engine.connect() as connection:
        for sql, params in statements:
            plans = [
                connection.exec_driver_sql(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, params
                ).scalar_one()
                for _ in range(5)
            ]
            results.append({"sql": sql, "plans": plans})
    print(json.dumps(results, indent=2, default=str))
    engine.dispose()


if __name__ == "__main__":
    main()
