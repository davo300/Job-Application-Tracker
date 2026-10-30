# Application query optimization — October 30, 2026

## Measured results

| Metric, 25 concurrent sessions | Before | After | Reduction |
| --- | ---: | ---: | ---: |
| Search p95 | 372.3 ms | 222.4 ms | **40.3%** |
| Overall p95 | 309.8 ms | 198.0 ms | 36.1% |
| Listing p95 | 277.9 ms | 174.0 ms | 37.4% |
| Filter p95 | 288.1 ms | 189.8 ms | 34.1% |
| Page-100 p95 | 288.9 ms | 180.1 ms | 37.7% |

All **23,490 baseline requests** and **36,436 optimized requests** passed HTTP and
content validation. Overall throughput rose from **130.1 to 201.9 requests/second**
under this fixed-concurrency workload; this is not a maximum throughput claim.
Search p95 ranges were **365.0–376.2 ms before** and **220.4–228.2 ms after**.
Overall p95 ranges were **306.0–313.8 ms before** and **196.7–200.5 ms after**.

The subsequent original-image control returned **375.8 ms search p95** and
**311.2 ms overall p95**, within the initial baseline ranges. All **7,781 control
requests** passed validation. The control image ID matches the original baseline
image and its observations are reported separately from the matched aggregates.

## Change

Application reads previously joined full application, job, and company records
before filtering, counting, sorting, and pagination. The revised repository:

- Counts user-scoped application IDs without unnecessary joins.
- Matches search text through scoped job/company subqueries and application notes.
- Sorts and paginates IDs before fetching complete records for the requested page.
- Preserves case-insensitive substring search, literal SQL wildcard escaping,
  all filters, UUID tie-breaking, archived-job history, and account isolation.

This uses the existing schema and indexes. No cache, new worker, resource increase,
response truncation, or removed validation was introduced.

## Experiment

The original October 29 result is historical context, not the denominator for the
percentage. Both versions were measured again on October 30 with the same local
Docker stack, database, load generator, and workload. Each version received three
runs with 20 seconds of excluded warm-up and 60 seconds of measurement per run.
Twenty-five distinct authenticated sessions accessed one synthetic account with
10,000 applications, 10,000 jobs, 100 companies, and 37,500 history events.

The four equally weighted read requests remain listing, `Backend` search sorted by
company, status/location filtering, and page-100 pagination. Each returns 25 rows.
Latency includes localhost HTTP, JSON decoding, and response-content validation.
P95 pools raw request observations across runs; it does not average percentiles.
The reduction is `(before_p95 - after_p95) / before_p95 * 100`.

The backend and PostgreSQL each retain 2 CPUs and 1 GiB limits, one Uvicorn worker,
and the original connection pool. No AWS load or deployment was performed.

## Correctness

The backend suite passes 66 tests. One new regression test compares the optimized
query against the original joined query for 156 combinations of search terms,
company/status/location/date filters, four sort orders, and first/later/empty
pages. Its fixture includes two accounts, tied sort values, null notes/locations,
literal `%`, `_`, and `/` characters, repeated attempts, and archived jobs.
Five benchmark-harness tests cover validation, pooled statistics, deterministic
fixtures, and refusal to compare incomplete, mismatched, or failing runs.

## Limits

This is a warm-cache local synthetic read experiment, not a production SLA,
maximum capacity estimate, real-user count, or prediction for the small AWS server.
Laptop thermal/background activity is not instrumented. Sequential version order
can introduce bias; the result should be interpreted together with the repeated
run ranges and the subsequent baseline control run.

## Evidence and reproduction

- [Matched pooled results, configuration, and raw CSV hashes](benchmarks/2026-10-30-comparison.json)
- [Raw observations, run reports, environments, and warm SQL plans](benchmarks/2026-10-30-raw.tar.gz)
- [Benchmark instructions](../benchmarks/README.md)

The baseline repository source is commit
`36e4f85e24160bdbb9b8150d0781a06c2458b75d`; the changed source is fingerprinted
in `optimized-environment.json` inside the archive. Its application source
fingerprints differ only for `backend/app/repositories/tracking.py`.
Both environment snapshots confirm the same host, Docker capacity/version,
workload, seed generator, Compose limits, dependency lock, and Dockerfile.
Archive filenames use `baseline-`, `optimized-`, and `baseline-control-` prefixes
to identify the original result directories.
Session creation happened outside measurement; private tokens are excluded from
all public reports and archives. The database volume contains synthetic data only.

To reproduce, build the baseline commit and the optimized version in separate
checkouts, preserving their images. Use the same benchmark Compose database and
fresh private seed manifest for both versions. Run the three-repeat command from
the benchmark instructions for each image, collect metadata and plans outside the
timed windows, and compare the resulting directories with `benchmarks.compare`.
Run one additional original-image control after the optimized measurements.

## Résumé wording

Use a rounded-down **40% reduction**, with the workload conditions attached:

```latex
\resumeItem{Optimized PostgreSQL queries to reduce application-search
\textbf{p95 latency by 40\%} (372 ms to 222 ms) across
\textbf{10,000 synthetic applications} at \textbf{25 concurrent sessions},
with \textbf{100\% validated request success} in local Docker benchmarks.}
```

The percentage refers to search p95 in this mixed read workload. It does not
claim a 40% improvement in every request, production performance, or user experience.
