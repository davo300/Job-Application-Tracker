# Release preparation and operations

Milestone 8 release preparation is implemented. Docker verification passed on
October 7, 2026 using Apple silicon, Python 3.12 containers, and PostgreSQL 17.
Verified development Compose build/startup, migrations, the complete API smoke
workflow, all 65 backend tests inside the container, production frontend build,
Nginx syntax, static HTML/security headers, API proxy readiness, and a synthetic
backup/restore rehearsal into a separate database. Your existing local app data
was untouched; verification used project `tracker-release-check` and alternate
ports. CI execution and actual HTTPS production deployment remain pending.

## Local container verification

Install and start Docker Desktop, then copy `.env.example` to `.env`. Use a
URL-safe development database password. Before starting Compose, stop local
services using ports 5432, 8000, and 5173, or adjust Compose host port mappings.

```sh
docker compose config --quiet
docker compose up --build -d
docker compose logs migrate
curl --fail http://localhost:5173/api/v1/health/ready
backend/.venv/bin/python scripts/smoke.py --base-url http://localhost:5173
docker compose down
```

Smoke creates a unique synthetic account and records, without modifying existing
accounts. Run only against a local/disposable environment; credentials are random
and not printed. Records remain until that disposable environment is removed.
Do not use `down --volumes` on a database containing wanted data.
CI config includes Compose startup, readiness, smoke, production frontend image
build, and `nginx -t`. Local Docker verification passed; the configured CI job still needs a GitHub run.

## Production candidate

`compose.production.yml` is standalone. It builds static frontend assets into an
unprivileged Nginx container; only localhost:8080 is exposed. PostgreSQL and the
API are internal. An HTTPS ingress must forward requests to port 8080 and retain
the public Origin. Set `PRODUCTION_ORIGINS` to a JSON array containing the exact
HTTPS origin. The API uses secure host-prefixed cookies. HTTP alone cannot provide
a usable production login. Do not expose internal service ports publicly.

```sh
docker compose -f compose.production.yml config --quiet
docker compose -f compose.production.yml build
docker compose -f compose.production.yml up -d
```

Use your hosting provider's secret store for database credentials. Environment
files must stay uncommitted. The API migration service runs before API startup;
readiness checks the required schema revision. Static assets have hashed filenames
and long-lived cache headers; HTML is not cached. API responses are no-store.
Nginx enforces CSP, framing restrictions, and same-origin proxying.

Image tags are currently mutable; pin tested digests in the actual deployment.
The backend image still includes development dependencies from the locked file;
separating a verified runtime lock remains a release improvement. Use a single
API instance until shared rate limiting is configured. The built-in limiter sees
the proxy address, so production needs client-aware ingress throttling. The
app does not yet provide verified-email or public password recovery flows.
A development-only interactive recovery command is available in
`backend/scripts/reset_local_password.py`; never use it as public recovery.

## Backup and restore rehearsal

Back up before migrations. Keep dumps encrypted with restricted access and a
retention policy. The following uses the production Compose database; the backup
contains all account and application data.

```sh
docker compose -f compose.production.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > tracker-backup.dump
```

Restore into a **new disposable database**, not the running application database:

```sh
docker compose -f compose.production.yml exec -T db sh -c 'createdb -U "$POSTGRES_USER" tracker_restore_check'
docker compose -f compose.production.yml exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d tracker_restore_check --exit-on-error' < tracker-backup.dump
```

Verify restored migration revision, record counts, constraints, and authenticated
read flows in an isolated app instance before treating the backup as recoverable.
The same dump/restore commands were successfully rehearsed on the isolated
PostgreSQL 17 verification container. Real production backup scheduling, encrypted
storage, retention, and recovery through an isolated authenticated app still need
to be established.

## Deployment and rollback gate

Choose hosting/domain, provision HTTPS and secrets, pass container CI and an
isolated restore rehearsal, then verify health and authenticated flows through
the public origin before inviting users. Set alerts for readiness failures,
5xx errors, failed migrations, disk capacity, and backup failures. Avoid logging
request bodies, passwords, cookies, CSRF tokens, and snapshots.

Record deployed image digests and migration revision. To roll back application
code, restore the previous verified image only if its schema remains compatible.
Do not run migration downgrade on live data as an automatic rollback; restore
from a verified backup into a separate database if schema recovery is necessary.

## Manual browser checklist

Check registration/login/logout, refresh restoration, company/job/application
creation, description versioning, stage/outcome recording, document references,
dashboard date filters, profile editing, and match history. Verify keyboard focus
and Escape on dialogs, form labels, visible errors, and narrow-screen navigation.
Automated API smoke complements these UI checks; it does not cover accessibility
or browser interaction itself. Production CSP and secure-cookie behavior still
need verification behind the actual HTTPS ingress.

## Private SSH-tunnel demo

`compose.tunnel.yml` serves the built static frontend and API on server localhost
port 8080. It uses development-mode session cookies solely for this private
loopback HTTP setup; transport from the Mac to the server is encrypted by SSH.
This is not the public HTTPS production configuration. PostgreSQL and the API
have no published ports. Keep application port 8080 closed in the cloud firewall.

On the server, create a mode-0600 `.env` containing `POSTGRES_USER`,
`POSTGRES_DB`, and a newly generated random URL-safe `POSTGRES_PASSWORD`, then:

```sh
sudo docker compose -f compose.tunnel.yml up --build -d
curl --fail http://127.0.0.1:8080/api/v1/health/ready
```

From your Mac, use the actual key path and instance address:

```sh
ssh -i /path/to/lightsail-key.pem -o ExitOnForwardFailure=yes -N \
  -L 127.0.0.1:18080:127.0.0.1:8080 ubuntu@SERVER_IP
```

Verify the SSH host fingerprint against the server's browser SSH terminal on first
connection. Open `http://localhost:18080` and keep the tunnel process running.
This server database starts empty; your Mac's existing account and records are
not copied. Create a separate account. Ctrl+C closes the tunnel, not the AWS
instance. Lightsail billing continues until the instance is deleted.

The private Lightsail deployment now has [encrypted scheduled backups](backups.md),
an hourly Mac mirror, and a verified 10-table restore rehearsal. Public production
HTTPS deployment remains a separate step.

## Public deployment status — October 30, 2026

Public HTTPS is now active on the existing Lightsail instance. See
[public access](public-access.md) for active Compose configuration, verification,
and rollback. The trusted certificate and secure-cookie workflow passed public
smoke checks. Earlier statements about HTTPS being pending describe the previous
release preparation state. Public password recovery, email verification, and
shared ingress rate limiting remain limitations, not completed features.
