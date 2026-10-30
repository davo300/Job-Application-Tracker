"""Compare matched benchmark runs using pooled request observations."""

import argparse
import json
from pathlib import Path

from benchmarks.report import aggregate


def compare(before, after):
    if not before["complete"] or not after["complete"]:
        raise ValueError("Both benchmark reports must be complete")
    for field in ("configuration", "dataset", "workloads"):
        if before[field] != after[field]:
            raise ValueError(f"Benchmark {field} must match")
    results = []
    if [r["concurrency"] for r in before["results"]] != [
        r["concurrency"] for r in after["results"]
    ]:
        raise ValueError("Concurrency groups must match")
    for old, new in zip(before["results"], after["results"], strict=True):
        if old["repetitions"] != new["repetitions"]:
            raise ValueError("Measured repetition counts must match")
        if (
            old["overall"]["success_percent"] != 100
            or new["overall"]["success_percent"] != 100
        ):
            raise ValueError("Resolve failed requests before claiming a speedup")
        metrics = {}
        for name in ("overall", *before["workloads"]):
            first = old["overall"] if name == "overall" else old["endpoints"][name]
            second = new["overall"] if name == "overall" else new["endpoints"][name]
            metrics[name] = {
                "before_p95_ms": first["p95_ms"],
                "after_p95_ms": second["p95_ms"],
                "p95_reduction_percent": 100
                * (first["p95_ms"] - second["p95_ms"])
                / first["p95_ms"],
            }
        results.append({"concurrency": old["concurrency"], "metrics": metrics})
    return {"before": before, "after": after, "comparison": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(aggregate(args.before), aggregate(args.after))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["comparison"], indent=2))


if __name__ == "__main__":
    main()
