"""Restore a decrypted dump into a new temporary database and compare row digests."""

import argparse
import json
import re
import subprocess
from pathlib import Path
from uuid import uuid4

TABLES = [
    "users",
    "companies",
    "jobs",
    "job_description_versions",
    "job_analyses",
    "applications",
    "application_events",
    "documents",
    "profiles",
    "match_results",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--dump", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.@:-]*", args.host):
        parser.error("Invalid SSH host")
    prefix = [
        "/usr/bin/ssh",
        "-i",
        str(args.identity),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=10",
        args.host,
    ]
    compose = (
        "cd ~/job-tracker && sudo docker compose -f compose.tunnel.yml exec -T db "
    )
    database = "tracker_restore_verify_" + uuid4().hex[:16]

    def remote(command, **kwargs):
        return subprocess.run(
            [*prefix, compose + command], check=True, timeout=300, **kwargs
        )

    def snapshot(name):
        rows = {}
        for table in TABLES:
            query = f"SELECT count(*),coalesce(md5(string_agg(md5(row_to_json(t)::text), '' ORDER BY id)), '') FROM {table} t"
            result = remote(
                f"psql -U tracker -d {name} -At",
                input=query,
                text=True,
                capture_output=True,
            )
            rows[table] = result.stdout.strip()
        return rows

    created = False
    try:
        remote(f"createdb -U tracker {database}", capture_output=True)
        created = True
        with args.dump.open("rb") as source:
            remote(
                f"pg_restore -U tracker -d {database} --no-owner --no-acl --exit-on-error",
                stdin=source,
                capture_output=True,
            )
        restored = snapshot(database)
        live = snapshot("tracker")
        differences = [table for table in TABLES if restored[table] != live[table]]
        if differences:
            raise RuntimeError(
                f"Restore succeeded but live data differs in {differences}; check for concurrent app edits before assessing equivalence."
            )
        print(
            json.dumps(
                {
                    "restore": "passed",
                    "persistent_tables_compared": len(TABLES),
                    "all_row_counts_and_digests_match": True,
                    "temporary_database": database,
                }
            )
        )
    finally:
        if created:
            # Drop only the fresh verification database created by this invocation.
            remote(f"dropdb -U tracker {database}", capture_output=True)


if __name__ == "__main__":
    main()
