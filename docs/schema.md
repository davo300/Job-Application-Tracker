# Relational schema

All primary keys are UUIDs. Dates represent calendar dates; timestamps are
PostgreSQL timestamps with time zone. User-local timezone handling belongs in
API and analytics services. Monetary values use fixed precision, currency, and
period rather than floating-point values.

| Table | Relationship / data |
| --- | --- |
| users | Unique normalized email and password hash |
| companies | Owned by user; company metadata |
| jobs | Owned by user; company, role, salary, dates, archive timestamp |
| job_description_versions | Owned by user through job; immutable raw text and version |
| job_analyses | Same owner as description; provider/version and structured JSONB |
| applications | Same owner as job/documents; attempt, dates, stage, outcome |
| application_events | Immutable event timeline belonging to application |
| documents | User-owned resume/cover-letter metadata and storage reference |
| profiles | One per user; revision and structured JSONB |
| match_results | Same owner as analysis/profile; immutable inputs and breakdown |
| sessions | User, hashed session/CSRF tokens, expiry; registration/login/logout implemented |

Composite `(id, user_id)` unique constraints support composite ownership foreign
keys. An application cannot reference another account's job or document; a match
cannot combine another account's profile and analysis. Document role compatibility
(resume versus cover letter) is additionally checked in the service.

Application stage and outcome are independent. Stages: applied, assessment,
recruiter_screen, technical_interview, behavioral_interview, final_interview.
Outcomes: active, offer, rejected, withdrawn. Events include these transitions
and note entries. Database check constraints reject unrecognized values.

Indexes cover ownership queries, foreign-key joins, user/status and user/date
application filtering, and application/time event ordering. Add new indexes
based on actual query plans rather than indexing every possible filter.

Job archive and document archive timestamps preserve historical references.
A PostgreSQL trigger protects document version metadata while allowing archive/restore.
There are no automatic delete cascades: deleting a referenced parent is rejected.
Account erasure will require an explicit transactional deletion service.
