# Local API benchmark — October 29, 2026

## Measured results

Nine measured runs completed: three repetitions at each concurrency, each with a 30-second excluded warm-up and a 120-second measurement. In total, **112,205 requests passed both HTTP and response-content validation**, with no measured failures.

| Concurrent sessions | Requests | Median (ms) | P95 (ms) | Requests/s | Validated success |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 21,536 | 11.0 | 37.8 | 59.8 | 100% |
| 10 | 44,467 | 78.0 | 163.5 | 123.4 | 100% |
| 25 | 46,202 | 189.9 | 318.6 | 128.2 | 100% |

Percentiles pool individual request observations across repetitions; they are not averages of run percentiles. Throughput uses actual elapsed time including draining in-flight requests.

## Endpoint breakdown at 25 concurrent sessions

| Request type | Requests | P95 (ms) | Validated success |
| --- | ---: | ---: | ---: |
| list | 11,553 | 288.3 | 100% |
| search | 11,551 | 385.8 | 100% |
| filter | 11,551 | 291.1 | 100% |
| later_page | 11,547 | 294.4 | 100% |

Individual mixed-workload p95 ranges:
- 1 sessions: 37.7–37.9 ms.
- 10 sessions: 154.7–174.9 ms.
- 25 sessions: 316.0–321.5 ms.

## Conditions and limits

- Apple M3, 8 CPU cores, 8 GiB host RAM; Docker Desktop on macOS. Exact Docker capacity and versions are in the environment snapshot.
- API: Python 3.12.16, FastAPI 0.142.2, SQLAlchemy 2.0.54, psycopg 3.3.6, Uvicorn 0.54.0; one worker; 2-CPU and 1-GiB container limit.
- Database: PostgreSQL 17.11; separate 2-CPU and 1-GiB container limit; default indexes and pool configuration, with ANALYZE after seeding.
- Verified counts: 100 companies, 10,000 jobs, 10,000 applications, 37,500 events. All synthetic; existing user data was untouched.
- Twenty-five distinct sessions access one account. These are virtual sessions, not active customers or independent accounts.
- Four equally weighted authenticated read operations: listing, search, status/location filtering, and page-100 pagination, with 25 items per response.
- Load generator on the same Mac, connecting directly to the API over localhost HTTP. No frontend rendering, reverse proxy, TLS, internet path, login time, or writes were measured.
- Timing includes response transfer, JSON decoding, and validation. Closed-loop requests have no think time; the workload does not establish maximum capacity or an SLA.
- Warm-cache, sequential concurrency levels and synthetic data limit generalization. Laptop thermal/background activity was not controlled or instrumented. There was no before/after optimization experiment.

## Evidence and reproduction

- [Sanitized pooled summary](benchmarks/2026-10-29-summary.json)
- [Hardware, container image IDs, and source SHA-256 fingerprints](benchmarks/2026-10-29-environment.json)
- [Raw per-request CSV observations and run summaries](benchmarks/2026-10-29-raw.tar.gz)
- [Harness and reproduction instructions](../benchmarks/README.md)

Raw files are also retained under `benchmarks/results/full-20261029/` locally. The archive contains no session tokens. The harness has four passing tests covering content validation, statistics, dataset expectations, and pooled percentile calculations.

## Résumé wording

The following rounds p95 upward from 318.6 to 319 ms and identifies the local synthetic workload:

```latex
\resumeItem{Benchmarked authenticated application APIs against \textbf{10,000 synthetic applications}, measuring \textbf{319 ms p95 latency} at \textbf{25 concurrent sessions} with \textbf{100\% validated request success} in a local Docker environment.}
```

For a specifically search-focused claim, use **386 ms p95** (rounded upward from 385.8), not the 319 ms mixed-workload figure. Avoid claiming real user adoption, production latency, maximum capacity, or percentage speedups from this baseline.
