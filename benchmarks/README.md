# Reproducible local API benchmark

This measures authenticated read requests over localhost into Docker, not browser
rendering, public internet latency, write throughput, or production capacity.
The closed-loop virtual users issue the next request only when the previous one
finishes, without think time. A fixed concurrency is not a maximum-user claim.
All virtual users access one large synthetic account through distinct server-side
sessions. This tests a 10,000-application personal workspace, not 10,000 real users.

## Data and workload

The seed creates 100 companies, 10,000 jobs, 10,000 applications, 37,500 events,
and 25 valid session tokens with 24-hour expiry. Four roles/statuses, three
locations, and 365 application dates have deterministic distributions. UUIDs are
deterministic. There are no analyses/documents in this read workload. The seed
checks the database name is exactly `tracker_benchmark` and refuses any nonempty
user table. It never deletes or modifies real data. Reruns require a fresh database
or reusing the existing private manifest while its sessions are valid.

The four equally weighted, round-robin request types are:

- Newest applications, first page: 10,000 total; 25 returned.
- Search `Backend`, ordered by company: 2,500 total; 25 returned.
- Filter `status=offer&location=Toronto`, oldest first: 833 total; 25 returned.
- Newest applications, page 100: 10,000 total; 25 returned (offset 2,475).

Every measured request must have HTTP 200, correct total/page/page size, expected
item count, unique IDs, synthetic company data, matching filters, and date ordering
where applicable. Incorrect content and HTTP/transport failures count as failures.

## Run

Run from the repository root with Docker Desktop running and backend dependencies
installed. These are separate containers and a separate named volume. Only the API
is published at localhost:18001. PostgreSQL has no host port. The API and database
each have a 2-CPU, 1-GiB limit; a single Uvicorn worker serves requests. The default
SQLAlchemy pool is unchanged (5 pooled + 10 overflow). API access logging is disabled.

```sh
docker compose -f benchmarks/compose.yml up --build -d
# Use a new manifest path: it is created exclusively with permissions 0600.
docker compose -f benchmarks/compose.yml run --rm --no-deps \
  -v "$PWD/benchmarks:/bench:ro" -v /private/tmp:/out \
  backend python /bench/seed.py --manifest /out/tracker-benchmark-session.json
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest benchmarks/test_harness.py -q
backend/.venv/bin/python benchmarks/load.py \
  --manifest /tmp/tracker-benchmark-session.json \
  --output benchmarks/results/my-run
backend/.venv/bin/python benchmarks/metadata.py > benchmarks/results/my-run/environment.json
backend/.venv/bin/python -m benchmarks.report benchmarks/results/my-run \
  --output benchmarks/results/my-run/pooled.json
docker compose -f benchmarks/compose.yml down
```

The mount shown is for macOS. On Linux, use a dedicated writable output mount
instead of `/private/tmp`. Manifests contain synthetic session credentials: keep
them out of Git and reports. Raw CSV files and local run output are ignored by
Git; a sanitized summary and environment snapshot can be saved under `docs/`.
Volumes remain after `down`. Never delete a volume containing wanted data.

For a pilot, add `--warmup 1 --seconds 3 --repeats 1`. Do not use pilot results for
résumé claims. The full default uses concurrency 1, 10, 25, three repetitions each,
30 seconds of excluded warm-up, and 120 seconds of measured requests per run.
It takes about 23 minutes. Keep the machine awake, plugged in, and otherwise idle.
The harness performs preflight checks before each warm-up and records wall time
including draining in-flight requests at the end. It does not include session
creation, login, or database seeding in the measurement.

## Statistics and interpretation

Raw CSV observations retain worker index, request type, milliseconds, status,
success, and error category. Timing includes HTTP transport, JSON decoding, and
client response validation; it is deliberately not pure server processing time.
Nearest-rank median/p95 cover all measured requests, including failures. Successful
p95 is provided separately so fast failures cannot hide errors. RPS divides
request count by actual measured wall time, including the final in-flight drain.
The report pools raw samples across repetitions; it never averages percentiles.
It also reports the range of individual-run p95s. Warm-up samples are excluded.

Localhost, warm database caches, synthetic data, a single account, the same-machine
load generator, Docker virtualization, and laptop thermal/background activity all
limit generalization. This is a baseline, not an optimization comparison or SLA.
Reproduce on the same configuration before claiming an improvement. Source hashes
and image IDs identify the measured code even while the Git worktree is dirty.

See the [measured baseline](../docs/performance.md) for the completed October 29
run, raw observations, environment details, and defensible résumé wording.
