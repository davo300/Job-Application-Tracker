"""Authenticated closed-loop HTTP benchmark with response-content validation."""

import argparse
import asyncio
import csv
import json
import math
import platform
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

WORKLOADS = {
    "list": "/applications?page=1&page_size=25&sort=newest",
    "search": "/applications?q=Backend&page=1&page_size=25&sort=company",
    "filter": "/applications?status=offer&location=Toronto&page=1&page_size=25&sort=oldest",
    "later_page": "/applications?page=100&page_size=25&sort=newest",
}


def valid_response(name, data, expected):
    page = 100 if name == "later_page" else 1
    expected_length = min(25, max(0, expected - (page - 1) * 25))
    if (
        data.get("total") != expected
        or data.get("page") != page
        or data.get("page_size") != 25
    ):
        return False
    items = data.get("items")
    if not isinstance(items, list) or len(items) != expected_length:
        return False
    if len({item["id"] for item in items}) != len(items):
        return False
    for item in items:
        if item["job"]["company"]["name"].startswith("Benchmark Company ") is False:
            return False
        if name == "search" and "Backend" not in item["job"]["title"]:
            return False
        if name == "filter" and (
            item["status"] != "offer" or item["job"]["location"] != "Toronto"
        ):
            return False
    if name in {"list", "later_page", "filter"}:
        dates = [item["applied_on"] for item in items]
        if dates != sorted(dates, reverse=name != "filter"):
            return False
    return True


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)] if ordered else None


def summarize(samples, elapsed):
    latencies = [row["latency_ms"] for row in samples]
    successes = sum(row["success"] for row in samples)
    good = [row["latency_ms"] for row in samples if row["success"]]
    return {
        "requests": len(samples),
        "successes": successes,
        "success_percent": 100 * successes / len(samples) if samples else None,
        "requests_per_second": len(samples) / elapsed,
        "successful_requests_per_second": successes / elapsed,
        "median_ms": percentile(latencies, 0.5),
        "p95_ms": percentile(latencies, 0.95),
        "successful_p95_ms": percentile(good, 0.95),
        "max_ms": max(latencies, default=None),
        "errors": dict(Counter(row["error"] for row in samples if not row["success"])),
    }


async def phase(clients, duration, expected, keep):
    samples = []
    started = time.perf_counter()
    deadline = started + duration
    names = list(WORKLOADS)

    async def worker(index, client):
        request_index = index
        while time.perf_counter() < deadline:
            name = names[request_index % len(names)]
            request_index += 1
            begin = time.perf_counter()
            status, success, error = 0, False, ""
            try:
                response = await client.get("/api/v1" + WORKLOADS[name])
                status = response.status_code
                # Latency includes transfer, JSON decode, and correctness validation.
                if status == 200:
                    success = valid_response(name, response.json(), expected[name])
                    if not success:
                        error = "invalid_content"
                else:
                    error = f"http_{status}"
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                error = type(exc).__name__
            if keep:
                samples.append(
                    {
                        "worker": index,
                        "endpoint": name,
                        "latency_ms": (time.perf_counter() - begin) * 1000,
                        "status": status,
                        "success": success,
                        "error": error,
                    }
                )

    await asyncio.gather(*(worker(i, client) for i, client in enumerate(clients)))
    return samples, time.perf_counter() - started


async def run(args):
    manifest = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "load_generator": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "httpx": httpx.__version__,
        },
        "dataset": {k: v for k, v in manifest.items() if k != "tokens"},
        "configuration": {
            "warmup_seconds": args.warmup,
            "measurement_seconds": args.seconds,
            "repeats": args.repeats,
            "concurrency": args.concurrency,
            "timeout_seconds": 10,
            "model": "closed loop; no think time; equal round-robin read workload",
        },
        "workloads": WORKLOADS,
        "runs": [],
    }
    for concurrency in args.concurrency:
        for repetition in range(1, args.repeats + 1):
            clients = [
                httpx.AsyncClient(
                    base_url=args.base_url,
                    cookies={"tracker_session": token},
                    timeout=10,
                    trust_env=False,
                    limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
                )
                for token in manifest["tokens"][:concurrency]
            ]
            try:
                for name, path in WORKLOADS.items():
                    response = await clients[0].get("/api/v1" + path)
                    if response.status_code != 200 or not valid_response(
                        name, response.json(), manifest["expected"][name]
                    ):
                        raise RuntimeError(
                            f"Preflight failed: {name} status {response.status_code}"
                        )
                print(
                    f"Starting c={concurrency} repetition={repetition}: warmup {args.warmup}s, measurement {args.seconds}s",
                    flush=True,
                )
                await phase(clients, args.warmup, manifest["expected"], False)
                samples, elapsed = await phase(
                    clients, args.seconds, manifest["expected"], True
                )
            finally:
                await asyncio.gather(*(client.aclose() for client in clients))
            filename = f"c{concurrency}-r{repetition}.csv"
            with (args.output / filename).open("w") as output:
                writer = csv.DictWriter(
                    output,
                    fieldnames=[
                        "worker",
                        "endpoint",
                        "latency_ms",
                        "status",
                        "success",
                        "error",
                    ],
                )
                writer.writeheader()
                writer.writerows(samples)
            result = {
                "concurrency": concurrency,
                "repetition": repetition,
                "elapsed_seconds": elapsed,
                "samples": filename,
                "overall": summarize(samples, elapsed),
                "endpoints": {
                    name: summarize(
                        [row for row in samples if row["endpoint"] == name], elapsed
                    )
                    for name in WORKLOADS
                },
            }
            report["runs"].append(result)
            (args.output / "summary.json").write_text(json.dumps(report, indent=2))
            print(json.dumps(result), flush=True)
    report["finished_at"] = datetime.now(UTC).isoformat()
    (args.output / "summary.json").write_text(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18001")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 10, 25])
    parser.add_argument("--warmup", type=float, default=30)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if url.hostname not in {"127.0.0.1", "localhost"} or url.scheme != "http":
        parser.error("This harness is restricted to local HTTP benchmark deployments")
    if (
        not all(1 <= n <= 25 for n in args.concurrency)
        or args.seconds <= 0
        or args.warmup < 0
        or args.repeats < 1
    ):
        parser.error("Invalid run duration, repetitions, or concurrency")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
