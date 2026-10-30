"""Pool raw observations without averaging percentiles; preserve per-run ranges."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from benchmarks.load import WORKLOADS, summarize


def aggregate(directory):
    report = json.loads((directory / "summary.json").read_text())
    groups = defaultdict(list)
    for run in report["runs"]:
        with (directory / run["samples"]).open() as source:
            samples = [
                {
                    **row,
                    "latency_ms": float(row["latency_ms"]),
                    "success": row["success"] == "True",
                }
                for row in csv.DictReader(source)
            ]
        if len(samples) != run["overall"]["requests"]:
            raise ValueError("Raw sample count differs from run summary")
        groups[run["concurrency"]].append((run, samples))
    results = []
    for concurrency, rows in sorted(groups.items()):
        combined = [sample for _, samples in rows for sample in samples]
        elapsed = sum(run["elapsed_seconds"] for run, _ in rows)
        result = {
            "concurrency": concurrency,
            "repetitions": len(rows),
            "elapsed_seconds": elapsed,
            "overall": summarize(combined, elapsed),
            "run_p95_range_ms": [
                min(run["overall"]["p95_ms"] for run, _ in rows),
                max(run["overall"]["p95_ms"] for run, _ in rows),
            ],
            "endpoints": {
                name: summarize([s for s in combined if s["endpoint"] == name], elapsed)
                for name in WORKLOADS
            },
        }
        results.append(result)
    return {
        "complete": bool(report.get("finished_at")),
        "started_at": report["started_at"],
        "finished_at": report.get("finished_at"),
        "configuration": report["configuration"],
        "dataset": report["dataset"],
        "workloads": report["workloads"],
        "results": results,
        "raw_sha256": {
            run["samples"]: hashlib.sha256(
                (directory / run["samples"]).read_bytes()
            ).hexdigest()
            for run in report["runs"]
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = aggregate(args.directory)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result["results"], indent=2))


if __name__ == "__main__":
    main()
