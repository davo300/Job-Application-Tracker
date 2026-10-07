# Architecture

## Request flow

React → REST routes → services → repositories → SQLAlchemy → PostgreSQL.
Routes validate HTTP input/output and resolve the authenticated user. Services
own transactions and business rules. Repositories issue focused queries, always
scoped to that user. Avoid generic repository frameworks and microservices.

Current implementation uses synchronous SQLAlchemy sessions with connection
pool health checks. Each request session closes deterministically. Migrations
are an explicit deployment step; application startup never creates tables.

`/api/v1/health/live` tests process responsiveness without opening a database
connection. `/api/v1/health/ready` checks connectivity and the expected migration
revision, returning 503 when either is unavailable. Update its revision when a
new migration is introduced.

## Boundaries

- `api`: routes and dependencies.
- `schemas`: Pydantic validation; implement alongside resource APIs.
- `models`: relational definitions.
- `services`: state transitions, ownership checks, transaction orchestration.
- `repositories`: database access.
- `analysis`: provider interface and deterministic extraction.
- `matching`: explainable scoring with persisted input snapshots.
- `analytics`: documented, tested metrics derived from operational records.
- `core`: configuration, password/token utilities, HTTP guards, and rate limiting.

Authentication and tracking routes, schemas, services, and repositories are
implemented. Analysis, matching, and analytics remain planned boundaries.

## History and reproducibility

Application events, description versions, and document version metadata are immutable on update, enforced
by PostgreSQL triggers. Append corrected/new records through an explicit service
workflow rather than editing old evidence. Hard deletion remains a future
explicit data-removal operation; foreign keys restrict deletion of referenced
parents. This is an audit trail, not full event sourcing.

Services atomically write events and update current application state under an
application row lock. State-changing events must follow the previous state event
strictly in time; notes may be backdated and do not change state. PostgreSQL tests
verify concurrent submissions and transaction rollback. Corrections and reopening
require a future explicit workflow. See [history behavior](history.md).

Extraction results have provider/schema versions. Matching records persist
profile revisions, inputs, and scorer versions. JSONB permits schema evolution,
but Pydantic must validate these documents before future services store them.

## Tradeoffs

The approved schema is established up front; behavior is implemented by milestone.
Additional ownership UUIDs make composite foreign keys possible, trading modest
redundancy for database-enforced isolation. UUIDs are generated in the application.
Timestamps use database creation defaults; SQLAlchemy updates `updated_at` on
ORM/Core updates, so direct SQL writers must explicitly update it.

Use a same-origin frontend/API deployment. Session-based authentication and CSRF
protection are implemented; see [security decisions](security.md).
