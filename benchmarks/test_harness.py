from benchmarks.load import percentile, summarize, valid_response
from benchmarks.seed import dataset


def response():
    return {
        "total": 1,
        "page": 1,
        "page_size": 25,
        "items": [
            {
                "id": "a",
                "applied_on": "2026-01-01",
                "status": "offer",
                "job": {
                    "title": "Backend Engineer",
                    "location": "Toronto",
                    "company": {"name": "Benchmark Company 000"},
                },
            }
        ],
    }


def test_response_validation_rejects_false_success():
    data = response()
    assert valid_response("filter", data, 1)
    assert not valid_response("list", data, 10000)
    data["items"][0]["status"] = "rejected"
    assert not valid_response("filter", data, 1)
    data["items"][0]["job"]["title"] = "Other"
    assert not valid_response("search", data, 1)
    data["items"] = []
    assert not valid_response("list", data, 1)


def test_statistics_count_errors_and_nearest_rank():
    samples = [
        {"latency_ms": 10, "success": True, "error": ""},
        {"latency_ms": 1000, "success": False, "error": "timeout"},
    ]
    result = summarize(samples, 2)
    assert result["p95_ms"] == 1000
    assert result["successful_p95_ms"] == 10
    assert result["success_percent"] == 50
    assert result["requests_per_second"] == 1
    assert percentile([], 0.95) is None


def test_dataset_counts_and_expected_filter_are_deterministic():
    companies, jobs, applications, events, filtered = dataset(10000)
    assert len(companies) == 100
    assert len(jobs) == len(applications) == 10000
    assert len(events) == 37500
    assert filtered == 833
    assert sum("Backend" in job["title"] for job in jobs) == 2500
    assert len({a["id"] for a in applications}) == 10000


def test_report_pools_samples_instead_of_averaging_percentiles(tmp_path):
    import csv
    import json

    from benchmarks.report import aggregate

    runs = []
    for repetition, latencies in enumerate([[1] * 99 + [1000], [1000]], 1):
        filename = f"run{repetition}.csv"
        rows = [
            {
                "worker": 0,
                "endpoint": "list",
                "latency_ms": value,
                "status": 200,
                "success": True,
                "error": "",
            }
            for value in latencies
        ]
        with (tmp_path / filename).open("w") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        runs.append(
            {
                "concurrency": 1,
                "elapsed_seconds": 1,
                "samples": filename,
                "overall": summarize(rows, 1),
            }
        )
    (tmp_path / "summary.json").write_text(
        json.dumps(
            {
                "started_at": "test",
                "finished_at": "test",
                "configuration": {},
                "dataset": {},
                "workloads": {},
                "runs": runs,
            }
        )
    )
    result = aggregate(tmp_path)["results"][0]
    assert result["overall"]["requests"] == 101
    assert result["overall"]["p95_ms"] == 1
    assert result["run_p95_range_ms"] == [1, 1000]
